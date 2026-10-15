#!/usr/bin/env python3
import fcntl
import json
import logging
import math
import os
import random
import serial
import signal
import subprocess
import tempfile
import time

from ipaddress import IPv4Address, AddressValueError

from enum import Enum

# The manager launches this daemon with stdout/stderr pointed at /dev/null
# (system/manager/process.py), so route the standard logging module through
# swaglog/cloudlog instead — otherwise every message is discarded. Falls back to
# a plain stderr handler when swaglog is unavailable (running the module
# standalone on a dev machine).
try:
  from openpilot.common.swaglog import cloudlog
except Exception:
  cloudlog = None


class _CloudlogHandler(logging.Handler):
  """Forward logging records to openpilot's swaglog (cloudlog)."""

  def emit(self, record: logging.LogRecord) -> None:
    try:
      cloudlog.log(record.levelno, self.format(record))
    except Exception:
      pass


def _setup_logging() -> None:
  root = logging.getLogger()
  root.setLevel(logging.INFO)
  handler: logging.Handler = _CloudlogHandler() if cloudlog is not None else logging.StreamHandler()
  handler.setFormatter(logging.Formatter("%(levelname)-7s modem: %(message)s"))
  root.addHandler(handler)


_setup_logging()

AT_PORT = "/dev/modem_at0"
PPP_PORT = "/dev/modem_at1"
STATE_PATH = "/dev/shm/modem"
AT_LOCK = "/dev/shm/modem.lock"  # shared with LPA
# The UI drops this file to ask the modem to tear down and reinitialize (re-read
# SIM/APN/roaming). Params can't be used for this: adding new param keys needs a
# rebuild, and this trigger has no persisted value anyway.
REINIT_FILE = "/data/community/modem_reinit"
# Cumulative cellular data usage, persisted across reboots and ppp0 sessions.
# The Cellular settings UI drops USAGE_RESET_FILE to zero the counters.
USAGE_FILE = "/data/community/cellular_usage.json"
USAGE_RESET_FILE = "/data/community/cellular_usage_reset"
# pppd runs with `nodetach`, so it logs to stderr; point stderr at one of these
# files so a failed dial leaves a trace. /data/log is where the other daemons
# log; /data/community is the fallback when that directory is not writable here.
PPPD_LOG_CANDIDATES = ("/data/log/modem_pppd.log", "/data/community/modem_pppd.log")
PPPD_LOG_MAX = 256 * 1024  # rotate past this so the capture file stays bounded
AT_INIT = [
  "ATE0",       # disable command echo
  "ATV1",       # verbose result codes (CONNECT/BUSY/NO CARRIER, not numeric)
  "AT+CMEE=1",  # numeric +CME ERROR codes on failures (per 3GPP 27.007)
  "ATX4",       # extended result codes: busy + dial tone detection, line speed in CONNECT
  "AT&C1",      # DCD pin follows carrier state (V.250 default)
  "AT+CREG=2",  # registration URCs include location info
  "AT+CGREG=2", # GPRS registration URCs include location info
]
CREG = {0: "not_registered", 1: "home", 2: "searching", 3: "denied", 4: "unknown", 5: "roaming"}
# 3GPP TS 27.007 +COPS <AcT> -> network type
NETWORK_TYPE = {0: "gsm", 1: "gsm", 3: "gsm", 8: "gsm",
                2: "utran", 4: "utran", 5: "utran", 6: "utran",
                7: "lte", 9: "lte", 10: "lte",
                11: "nr", 12: "nr", 13: "nr"}

DIAL_CID = 1
WEBBING_ICCID_PREFIX = "8985235"

PPPD_CMD = [
  "sudo", "pppd", PPP_PORT, "460800", "noauth", "nodetach", "noipdefault", "usepeerdns",
  "nodefaultroute", "connect",
  "/usr/sbin/chat -v ABORT 'NO CARRIER' ABORT 'NO DIALTONE' ABORT 'BUSY' " +
  f"ABORT 'NO ANSWER' ABORT 'ERROR' TIMEOUT 5 '' AT OK ATD*99***{DIAL_CID}# CONNECT ''",
  "lcp-echo-interval", "30", "lcp-echo-failure", "4", "mtu", "1500", "mru", "1500",
  "novj", "novjccomp", "ipcp-accept-local", "ipcp-accept-remote", "nomagic",
  "user", '""', "password", '""',
]

# After MAX_FAILS consecutive dial failures the modem reinitializes, but only
# after waiting out an exponential backoff (capped, with jitter) so a broken
# link cannot spin through INITIALIZING…CONNECTED every few seconds. A
# connection that holds for STABLE_SECONDS clears the failure/backoff state.
BACKOFF_SCHEDULE = (10, 30, 60, 120, 300)
BACKOFF_MAX = 300
BACKOFF_JITTER = 0.2
STABLE_SECONDS = 60.0
# pppd must produce a ppp0 IPv4 address within this many seconds of starting;
# otherwise it is treated as a dial failure (e.g. an IPCP stall).
CONNECT_TIMEOUT = 60.0

INITIAL_STATE = {
  "seconds_since_boot": 0,
  "state": "INITIALIZING",
  "connected": False, "ip_address": "",
  "iccid": "", "mcc_mnc": "", "imei": "", "modem_version": "",
  "signal_strength": 0, "signal_quality": 0,
  "network_type": "unknown", "operator": "", "band": "", "channel": 0,
  "registration": "unknown", "temperatures": [], "extra": "",
  "tx_bytes": 0, "rx_bytes": 0,
  "total_tx_bytes": 0, "total_rx_bytes": 0,
}

# Failure diagnostics (survive a reinit so the UI/heartbeat can still show why
# the link last dropped; cleared once a connection becomes stable). Seeded
# separately from INITIAL_STATE so a DISCONNECTING reset does not wipe them.
FAILURE_STATE = {"fail_count": 0, "max_fails": 0, "last_error": "", "last_error_at": 0, "retry_in": 0}


def _load_cellular_usage() -> dict:
  try:
    with open(USAGE_FILE) as f:
      d = json.load(f)
  except (OSError, ValueError):
    d = {}
  return {
    "tx": int(d.get("tx", 0)),
    "rx": int(d.get("rx", 0)),
    "raw_tx": int(d.get("raw_tx", 0)),
    "raw_rx": int(d.get("raw_rx", 0)),
  }


def _save_cellular_usage(u: dict) -> None:
  try:
    os.makedirs(os.path.dirname(USAGE_FILE), exist_ok=True)
    tmp = USAGE_FILE + ".tmp"
    with open(tmp, "w") as f:
      json.dump(u, f)
    os.replace(tmp, USAGE_FILE)
  except OSError:
    pass


def _file_size(path: str) -> int:
  try:
    return os.path.getsize(path)
  except OSError:
    return 0


def _read_tail(path: str, offset: int, max_lines: int = 12, max_bytes: int = 4096) -> list[str]:
  """Last non-empty lines written to path since offset (best effort)."""
  try:
    size = os.path.getsize(path)
    start = max(offset, size - max_bytes)
    with open(path, "rb") as f:
      f.seek(start)
      data = f.read()
  except OSError:
    return []
  lines = [ln.strip() for ln in data.decode("utf-8", "replace").splitlines() if ln.strip()]
  return lines[-max_lines:]


def _summarize_pppd_failure(returncode: int | None, tail: list[str]) -> str:
  """A short, human-readable reason for a pppd session ending."""
  text = " ".join(tail).lower()
  if "modem hangup" in text:
    reason = "modem hung up after connecting"
  elif "no carrier" in text:
    reason = "no carrier"
  elif "no dialtone" in text:
    reason = "no dial tone"
  elif "no answer" in text:
    reason = "no answer"
  elif "busy" in text:
    reason = "line busy"
  elif "authentication" in text and ("fail" in text or "denied" in text):
    reason = "authentication failed"
  elif "timeout" in text or "timed out" in text:
    reason = "dial timed out"
  elif tail:
    reason = tail[-1]
  else:
    reason = "pppd exited"
  return f"{reason} (pppd exit {returncode})" if returncode is not None else reason


class State(Enum):
  INITIALIZING = "INITIALIZING"
  SEARCHING = "SEARCHING"
  CONNECTING = "CONNECTING"
  CONNECTED = "CONNECTED"
  DIAL_FAILED = "DIAL_FAILED"  # gave up on immediate retries; backing off before reinit
  DISCONNECTING = "DISCONNECTING"


STATE_WAIT = 1.0  # seconds to wait after each state handler returns


class PPPSession:
  """Owns pppd lifecycle, fail tracking, and PPP routing."""
  MAX_FAILS = 3

  def __init__(self):
    self._proc: subprocess.Popen | None = None
    self._fails = 0
    self._peer = ""
    self._log_fh = None
    self._log_path = ""
    self._log_offset = 0
    self.started_at = 0.0

  def start(self):
    self._rotate_log()
    self._log_offset = _file_size(self._log_path)
    out = self._open_log()
    self._proc = subprocess.Popen(PPPD_CMD, stdout=out, stderr=out)
    self.started_at = time.monotonic()
    self._peer = ""
    logging.info(f"PPP dialing CID {DIAL_CID}")

  def _open_log(self):
    for path in PPPD_LOG_CANDIDATES:
      try:
        self._log_fh = open(path, "ab", buffering=0)
        self._log_path = path
        return self._log_fh
      except OSError:
        continue
    self._log_fh = None
    self._log_path = PPPD_LOG_CANDIDATES[0]
    return subprocess.DEVNULL

  def _rotate_log(self):
    try:
      if self._log_path and os.path.getsize(self._log_path) > PPPD_LOG_MAX:
        os.replace(self._log_path, self._log_path + ".1")
    except OSError:
      pass

  def _close_log(self):
    if self._log_fh is not None:
      try:
        self._log_fh.close()
      except OSError:
        pass
      self._log_fh = None

  def capture_exit(self) -> tuple[int | None, list[str]]:
    """Return (returncode, log tail) for the session that just ended."""
    rc = self._proc.returncode if self._proc is not None else None
    tail = _read_tail(self._log_path, self._log_offset)
    self._close_log()
    return rc, tail

  def kill(self):
    subprocess.run(["sudo", "killall", "-9", "pppd"], capture_output=True)
    self._close_log()
    self._proc = None  # a fresh CONNECTING must not see the old exit as a failure
    self._peer = ""

  @staticmethod
  def reset_data_port():
    """Drop DTR on PPP_PORT so the modem terminates any stuck PPP session."""
    try:
      with serial.Serial(PPP_PORT, 460800, timeout=1) as s:
        s.dtr = False
        time.sleep(0.2)
        s.dtr = True
    except Exception as e:
      logging.warning(f"data port reset failed: {e}")

  @property
  def running(self) -> bool:
    return self._proc is not None and self._proc.poll() is None

  def has_exited(self) -> bool:
    return self._proc is not None and self._proc.poll() is not None

  def reset_fail_counter(self):
    self._fails = 0

  def record_fail(self) -> bool:
    """Bump fail counter; return True if at the give-up limit."""
    self._fails += 1
    return self._fails >= self.MAX_FAILS

  @property
  def fails(self) -> int:
    return self._fails

  def maybe_install_routes(self, ip: str, peer: str) -> bool:
    """Install routes if peer changed; kill the session on failure so the state machine reconnects."""
    if not peer or peer == self._peer:
      return False
    try:
      IPv4Address(ip)
      IPv4Address(peer)
    except AddressValueError:
      logging.warning(f"refusing route install with non-IPv4 ip={ip!r} peer={peer!r}")
      self.kill()
      return False
    self.cleanup_routes()
    cmds = [
      ["sudo", "ip", "route", "add", "default", "via", peer, "dev", "ppp0", "metric", "1000"],
      ["sudo", "ip", "route", "add", "default", "via", peer, "dev", "ppp0", "table", "1000"],
      ["sudo", "ip", "rule", "add", "from", ip, "table", "1000"],
    ]
    for cmd in cmds:
      r = subprocess.run(cmd, capture_output=True, text=True)
      if r.returncode != 0:
        logging.warning(f"route install failed ({' '.join(cmd[1:])}): {r.stderr.strip()}")
        self.cleanup_routes()
        self.kill()
        return False
    logging.info(f"route set up for {ip} via {peer}")
    self._peer = peer
    return True

  def maybe_install_dns(self, dns_servers: list[str]) -> bool:
    """Register DNS servers with systemd-resolved; kill the session on failure to force a retry."""
    if not dns_servers:
      return False
    for cmd in (["sudo", "resolvectl", "dns", "ppp0", *dns_servers],
                ["sudo", "resolvectl", "default-route", "ppp0", "yes"]):
      r = subprocess.run(cmd, capture_output=True, text=True)
      if r.returncode != 0:
        logging.warning(f"resolvectl failed ({' '.join(cmd[1:])}): {r.stderr.strip()}")
        self.kill()
        return False
    logging.info(f"resolvectl: ppp0 DNS = {dns_servers}")
    return True

  @staticmethod
  def cleanup_routes():
    subprocess.run(["sudo", "ip", "route", "del", "default", "dev", "ppp0"], capture_output=True)
    subprocess.run(["sudo", "ip", "route", "flush", "table", "1000"], capture_output=True)
    # rules don't have a flush; delete until none remain
    while subprocess.run(["sudo", "ip", "rule", "del", "table", "1000"], capture_output=True).returncode == 0:
      pass
    subprocess.run(["sudo", "resolvectl", "revert", "ppp0"], capture_output=True)


class Modem:
  def __init__(self):
    self._ppp = PPPSession()
    self._sim_change = False
    self._apn = ""  # blank = network-provided via PCO
    self._roaming_allowed = True
    self.running = True
    self._backoff_attempt = 0
    self._backoff_until = 0.0
    self._connected_at = 0.0
    self.S = INITIAL_STATE.copy()
    self.S.update(FAILURE_STATE)
    self.S["max_fails"] = PPPSession.MAX_FAILS
    self._handlers = {
      State.INITIALIZING: self._do_initializing,
      State.SEARCHING: self._do_searching,
      State.CONNECTING: self._do_connecting,
      State.CONNECTED: self._do_connected,
      State.DIAL_FAILED: self._do_dial_failed,
      State.DISCONNECTING: self._do_disconnecting,
    }

  @staticmethod
  def _read_param(key):
    try:
      with open(f"/data/params/d/{key}") as f:
        return f.read().strip()
    except FileNotFoundError:
      return ""

  @staticmethod
  def _parse_reg(v: str) -> str:
    try:
      return CREG.get(int(v.split(",")[1].strip('"')), "unknown")
    except (ValueError, IndexError):
      return "unknown"

  @staticmethod
  def _has_modem_manager() -> bool:
    return os.path.isfile("/lib/systemd/system/ModemManager.service")

  def _is_roaming_allowed(self) -> bool:
    if self.S["iccid"].startswith(WEBBING_ICCID_PREFIX):
      return True
    return self._read_param("GsmRoaming") == "1"

  def _fail_fields(self) -> dict:
    return {"fail_count": self._ppp.fails, "max_fails": self._ppp.MAX_FAILS}

  def _publish_state(self, **kwargs):
    self.S.update(kwargs)
    self.S["seconds_since_boot"] = time.monotonic()
    with tempfile.NamedTemporaryFile(mode="w", dir=os.path.dirname(STATE_PATH), delete=False) as f:
      json.dump(self.S, f, indent=2)
    os.chmod(f.name, 0o644)
    os.replace(f.name, STATE_PATH)

  def _at(self, cmd):
    """Send AT command, return response lines. [] on error or if LPA holds port."""
    fd = os.open(AT_LOCK, os.O_CREAT | os.O_RDWR, 0o666)
    try:
      fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
      os.close(fd)
      return []
    try:
      with serial.Serial(AT_PORT, 9600, timeout=5) as ser:
        ser.reset_input_buffer()
        ser.write((cmd + "\r").encode())
        lines = []
        while True:
          raw = ser.readline()
          if not raw:
            raise TimeoutError("AT timeout")
          line = raw.decode(errors="ignore").strip()
          if not line:
            continue
          if line == "OK":
            break
          if line == "ERROR" or line.startswith("+CME ERROR"):
            raise RuntimeError(line)
          lines.append(line)
        return lines
    except (RuntimeError, TimeoutError, OSError) as e:
      logging.info(f"AT {cmd} failed: {e}")
      return []
    finally:
      fcntl.flock(fd, fcntl.LOCK_UN)
      os.close(fd)

  def _atv(self, cmd, pfx):
    for line in self._at(cmd):
      if pfx in line and ":" in line:
        return line.split(":", 1)[1].strip()
    return None

  def _init_at_channel(self) -> bool:
    """Run AT_INIT and confirm ATE0 took effect. Returns False if echo is still on."""
    for c in AT_INIT:
      self._at(c)
    r = self._at("AT+CGMI")
    return bool(r) and not r[0].startswith("AT")

  def _configure_modem(self, modem_version: str):
    if not modem_version.startswith("EG25"):
      return
    cmds = [
      # clear initial EPS bearer APN (some carriers reject the default)
      'AT+CGDCONT=0,"IP",""',

      # SIM hot swap
      'AT+QSIMDET=1,0',
      'AT+QSIMSTAT=1',

      # configure modem as data-centric
      'AT+QNVW=5280,0,"0102000000000000"',
      'AT+QNVFW="/nv/item_files/ims/IMS_enable",00',
      'AT+QNVFW="/nv/item_files/modem/mmode/ue_usage_setting",01',
    ]
    for c in cmds:
      self._at(c)

  def _do_initializing(self):
    if not os.path.exists(AT_PORT):
      return State.INITIALIZING
    logging.info("port found, initializing")
    self._ppp.kill()
    self._ppp.cleanup_routes()

    if not self._init_at_channel():
      logging.warning("AT echo still on, retrying")
      return State.INITIALIZING

    identity = self._read_identity()
    if not identity["iccid"] or not identity["imei"]:
      logging.warning(f"identity read incomplete: {identity}, retrying")
      return State.INITIALIZING

    self._configure_modem(identity["modem_version"])

    self.S.update(identity)
    self._apn = self._read_param("GsmApn")
    self._roaming_allowed = self._is_roaming_allowed()
    # blank APN lets the carrier supply one via PCO
    self._at(f'AT+CGDCONT={DIAL_CID},"IP","{self._apn}"')
    logging.info(f"APN '{self._apn or '(network-provided)'}' written to CID {DIAL_CID}, roaming={'on' if self._roaming_allowed else 'off'}")

    self._sim_change = False  # clear since we just re-read identity with the new SIM
    self._publish_state(**identity)
    return State.SEARCHING

  def _read_identity(self):
    def first_line(cmd):
      r = self._at(cmd)
      return r[0].strip() if r else ""

    imei = first_line("AT+CGSN")
    if not (imei.isdigit() and 14 <= len(imei) <= 17):  # 3GPP TS 23.003
      imei = ""

    iccid = (self._atv("AT+QCCID", "+QCCID:") or "").rstrip("F")
    if not iccid.isdigit():
      iccid = ""

    imsi = first_line("AT+CIMI")
    mcc_mnc = imsi[:6] if imsi.isdigit() and len(imsi) >= 6 else ""

    modem_version = first_line("AT+GMR")

    logging.info(f"imei={imei} iccid={iccid} mcc_mnc={mcc_mnc} ver={modem_version}")
    return {"imei": imei, "iccid": iccid, "mcc_mnc": mcc_mnc, "modem_version": modem_version}

  def _do_searching(self):
    new_roaming = self._is_roaming_allowed()
    if new_roaming != self._roaming_allowed:
      logging.info(f"roaming changed: {self._roaming_allowed} -> {new_roaming}")
      self._roaming_allowed = new_roaming

    v = self._atv("AT+CREG?", "+CREG:")
    if not v:
      return self._searching_idle()

    reg = self._parse_reg(v)
    greg = self._parse_reg(self._atv("AT+CGREG?", "+CGREG:") or "")
    logging.debug(f"creg={reg} cgreg={greg} roaming_allowed={self._roaming_allowed}")

    if reg == "roaming" and not self._roaming_allowed:
      self._publish_state(registration=reg)
      return State.SEARCHING

    if reg in ("home", "roaming") and greg in ("home", "roaming"):
      self._publish_state(registration=reg)
      return State.CONNECTING

    if reg != self.S.get("registration"):
      self._publish_state(registration=reg)
    return self._searching_idle()

  def _searching_idle(self):
    if self._sim_change or not os.path.exists(AT_PORT):
      logging.info(f"-> reconnecting (sim_change={self._sim_change} port={os.path.exists(AT_PORT)})")
      return State.DISCONNECTING
    return State.SEARCHING

  def _do_connecting(self):
    # pppd dials in the background; CONNECTING lasts until ppp0 actually has an
    # IPv4 address. A pppd exit before that — or an IPCP stall past
    # CONNECT_TIMEOUT — is a dial failure, not a drop from CONNECTED.
    if self._ppp.has_exited():
      return self._on_dial_failure()
    if self._ppp.running:
      ip, peer = self._ppp0_addr()
      if ip:
        return self._on_connected(ip, peer)
      if self._ppp.started_at and time.monotonic() - self._ppp.started_at >= CONNECT_TIMEOUT:
        _, tail = self._ppp.capture_exit()
        logging.warning(f"no IP after {CONNECT_TIMEOUT:.0f}s (last pppd log: {tail[-1] if tail else 'none'})")
        self._ppp.kill()
        return self._on_dial_failure("Timed out waiting for an IP address")
      return State.CONNECTING
    logging.info("starting pppd")
    self._ppp.reset_fail_counter()
    self._sim_change = False
    self._ppp.start()
    self._publish_state(**self._fail_fields())
    return State.CONNECTING

  def _on_connected(self, ip: str, peer: str):
    self._connected_at = time.monotonic()
    if self._ppp.maybe_install_routes(ip, peer):
      self._ppp.maybe_install_dns(self._read_cellular_dns())
    logging.info(f"connected, ip {ip}")
    self._publish_state(ip_address=ip, connected=True, last_error="", last_error_at=0, retry_in=0, **self._fail_fields())
    return State.CONNECTED

  def _on_dial_failure(self, reason: str | None = None):
    if reason is None:
      rc, tail = self._ppp.capture_exit()
      reason = _summarize_pppd_failure(rc, tail)
    give_up = self._ppp.record_fail()
    logging.warning(f"PPP dial failed ({self._ppp.fails}/{self._ppp.MAX_FAILS}): {reason}")
    self._publish_state(last_error=reason, last_error_at=time.monotonic(), **self._fail_fields())
    if not give_up:
      self._ppp.reset_data_port()
      self._ppp.start()
      return State.CONNECTING
    return self._enter_backoff(reason)

  def _enter_backoff(self, reason: str):
    """Wait an exponentially longer time before the next full reinit."""
    delay = self._backoff_delay(self._backoff_attempt)
    self._backoff_attempt += 1
    self._backoff_until = time.monotonic() + delay
    logging.warning(f"backing off {delay:.0f}s before reinitializing: {reason}")
    self._publish_state(state=State.DIAL_FAILED.value, retry_in=math.ceil(delay),
                        last_error=reason, last_error_at=time.monotonic(), **self._fail_fields())
    return State.DIAL_FAILED

  @staticmethod
  def _backoff_delay(attempt: int) -> float:
    base = BACKOFF_SCHEDULE[attempt] if attempt < len(BACKOFF_SCHEDULE) else BACKOFF_MAX
    jitter = random.uniform(-BACKOFF_JITTER, BACKOFF_JITTER)
    return max(1.0, min(base * (1 + jitter), BACKOFF_MAX))

  def _reset_backoff(self):
    self._backoff_attempt = 0
    self._backoff_until = 0.0

  def _do_dial_failed(self):
    remaining = self._backoff_until - time.monotonic()
    if remaining <= 0:
      logging.info("backoff elapsed, reinitializing")
      return State.DISCONNECTING
    self._publish_state(state=State.DIAL_FAILED.value, retry_in=max(0, math.ceil(remaining)))
    return State.DIAL_FAILED

  def _do_connected(self):
    if self._ppp.has_exited():
      return self._on_dial_failure()

    if self._sim_change or not os.path.exists(AT_PORT):
      return State.DISCONNECTING

    ip, _ = self._ppp0_addr()
    if not ip:
      # pppd is still up but ppp0 lost its address: treat it as a dial failure
      # so we never report CONNECTED without an IP. Capture the pppd tail before
      # kill() clears the process.
      logging.warning("ppp0 lost its address while connected")
      self._ppp.capture_exit()
      self._ppp.kill()
      return self._on_dial_failure("Connection lost (no IP on ppp0)")

    self._poll()
    self._mark_stable()
    return State.CONNECTED

  def _mark_stable(self):
    if self._connected_at and time.monotonic() - self._connected_at >= STABLE_SECONDS:
      if self._ppp.fails or self._backoff_attempt:
        logging.info(f"connection stable for {STABLE_SECONDS:.0f}s, clearing failure/backoff state")
        self._ppp.reset_fail_counter()
        self._reset_backoff()
      self._connected_at = 0.0

  def _do_disconnecting(self):
    logging.warning("reconnecting")
    self._publish_state(**INITIAL_STATE, retry_in=0)
    self._ppp.kill()
    self._ppp.cleanup_routes()
    self._ppp.reset_data_port()
    self._sim_change = False
    return State.INITIALIZING

  def _params_changed(self) -> bool:
    new_apn = self._read_param("GsmApn")
    if new_apn != self._apn:
      logging.info(f"GsmApn changed: '{self._apn}' -> '{new_apn}'")
      return True
    new_roaming = self._is_roaming_allowed()
    if new_roaming != self._roaming_allowed:
      logging.info(f"roaming changed: {self._roaming_allowed} -> {new_roaming}")
      return True
    return False

  def _check_iccid(self, state):
    if state in (State.INITIALIZING, State.DISCONNECTING) or not self.S["iccid"]:
      return
    iccid = (self._atv("AT+QCCID", "+QCCID:") or "").rstrip("F")
    if iccid and iccid != self.S["iccid"]:
      logging.warning(f"iccid changed: {self.S['iccid']} -> {iccid}")
      self._sim_change = True

  def _preflight(self, state: State) -> State:
    """React to reinit requests and APN/roaming edits from any live state.

    Acting here (not just while CONNECTED) means an APN typed in while the modem
    is still SEARCHING/CONNECTING is applied, and it resets the backoff so the
    user's explicit request takes effect immediately."""
    if state in (State.INITIALIZING, State.DISCONNECTING):
      return state
    if os.path.exists(REINIT_FILE):
      try:
        os.remove(REINIT_FILE)
      except OSError:
        pass
      logging.info("reinitialize requested")
      self._reset_backoff()
      return State.DISCONNECTING
    if self._params_changed():
      self._reset_backoff()
      return State.DISCONNECTING
    return state

  def _poll_signal(self) -> dict:
    v = self._atv("AT+CSQ", "+CSQ:")
    if not v:
      return {}
    try:
      rssi = int(v.split(",")[0])
      if rssi == 99:
        return {}
      return {"signal_strength": rssi, "signal_quality": min(100, int(rssi / 31 * 100))}
    except (ValueError, IndexError):
      return {}

  def _poll_operator(self) -> dict:
    v = self._atv("AT+COPS?", "+COPS:")
    if not v:
      return {}
    p = v.split(",")
    out: dict = {}
    try:
      if len(p) >= 3:
        out["operator"] = p[2].strip('"')
      if len(p) >= 4:
        out["network_type"] = NETWORK_TYPE.get(int(p[3]), "unknown")
    except (ValueError, IndexError):
      pass
    return out

  def _poll_band(self) -> dict:
    v = self._atv("AT+QNWINFO", "+QNWINFO:")
    if not v:
      return {}
    info = v.replace('"', '').split(",")
    try:
      if len(info) >= 4:
        return {"band": info[2], "channel": int(info[3])}
    except ValueError:
      pass
    return {}

  def _poll_extra(self) -> dict:
    v = self._atv('AT+QENG="servingcell"', "+QENG:")
    return {"extra": v.replace('"', '')} if v else {}

  def _poll_temps(self) -> dict:
    v = self._atv("AT+QTEMP", "+QTEMP:")
    if not v:
      return {}
    try:
      return {"temperatures": [t for t in (int(x) for x in v.split(",") if x.strip()) if t != 255]}
    except (ValueError, IndexError):
      return {}

  @staticmethod
  def _ppp0_addr() -> tuple[str, str]:
    """Return (ip, peer) for ppp0, or ("", "") when it has no IPv4 address."""
    try:
      r = subprocess.run(["ip", "-4", "addr", "show", "ppp0"], capture_output=True, text=True, timeout=2)
      for line in r.stdout.splitlines():
        # `inet 10.x.x.x peer 10.64.64.64/32 ...`
        parts = line.strip().split()
        if "inet" in parts:
          i = parts.index("inet")
          ip = parts[i + 1].split("/")[0]
          peer = ""
          if "peer" in parts:
            peer = parts[parts.index("peer") + 1].split("/")[0]
          return ip, peer
    except Exception:
      pass
    return "", ""

  def _poll_iface(self) -> dict:
    ip, peer = self._ppp0_addr()
    if ip:
      if self._ppp.maybe_install_routes(ip, peer):
        self._ppp.maybe_install_dns(self._read_cellular_dns())
      return {"ip_address": ip, "connected": True}
    if self.S["connected"]:
      return {"connected": False, "ip_address": ""}
    return {}

  def _read_cellular_dns(self) -> list[str]:
    v = self._atv(f"AT+CGCONTRDP={DIAL_CID}", "+CGCONTRDP:")
    if not v:
      return []
    # +CGCONTRDP: <cid>,<bearer_id>,<apn>,<local_addr>,<gw_addr>,<dns_prim>,<dns_sec>,...
    fields = [f.strip().strip('"') for f in v.split(",")]
    dns_servers = []
    for d in fields[5:7]:
      try:
        dns_servers.append(str(IPv4Address(d)))
      except (AddressValueError, ValueError):
        pass
    if not dns_servers:
      logging.warning(f"no cellular DNS servers reported by modem: {v!r}")
    return dns_servers

  def _poll_byte_counters(self) -> dict:
    try:
      with open("/sys/class/net/ppp0/statistics/tx_bytes") as f:
        tx = int(f.read().strip())
      with open("/sys/class/net/ppp0/statistics/rx_bytes") as f:
        rx = int(f.read().strip())
    except Exception:
      return {}

    usage = _load_cellular_usage()
    if os.path.exists(USAGE_RESET_FILE):
      try:
        os.remove(USAGE_RESET_FILE)
      except OSError:
        pass
      usage["tx"] = usage["rx"] = 0
      usage["raw_tx"], usage["raw_rx"] = tx, rx
    else:
      # ppp0 counters reset to 0 on every new session, so a decrease means the
      # interface was recreated: count the new value from zero.
      usage["tx"] += tx - usage["raw_tx"] if tx >= usage["raw_tx"] else tx
      usage["rx"] += rx - usage["raw_rx"] if rx >= usage["raw_rx"] else rx
      usage["raw_tx"], usage["raw_rx"] = tx, rx
    _save_cellular_usage(usage)

    return {"tx_bytes": tx, "rx_bytes": rx,
            "total_tx_bytes": usage["tx"], "total_rx_bytes": usage["rx"]}

  def _poll(self):
    s: dict = {}
    for fn in (self._poll_signal, self._poll_operator, self._poll_band,
               self._poll_extra, self._poll_temps, self._poll_iface,
               self._poll_byte_counters):
      s.update(fn())
    if s:
      self._publish_state(**s)

  def _step(self, state: State) -> State:
    """One state-machine tick: check for external triggers, run the handler, and
    contain any exception as a backoff instead of a tight reinit loop."""
    try:
      self._check_iccid(state)
      state = self._preflight(state)
      prev = state
      state = self._handlers[state]()
      if state != prev:
        self._publish_state(state=state.value)
        logging.info(f"{prev.value} -> {state.value}")
    except Exception as e:
      logging.exception(f"error in {state.value}")
      state = self._enter_backoff(f"internal error: {e}")
    return state

  def run(self):
    logging.info("starting")
    self._publish_state(state=State.INITIALIZING.value)
    if self._has_modem_manager():
      subprocess.run(["sudo", "systemctl", "mask", "--runtime", "ModemManager"], capture_output=True)
      subprocess.run(["sudo", "systemctl", "stop", "ModemManager"], capture_output=True)
    self._ppp.kill()

    state = State.INITIALIZING
    while self.running:
      state = self._step(state)
      time.sleep(STATE_WAIT)

  def stop(self):
    self.running = False
    self._ppp.kill()
    self._ppp.cleanup_routes()
    try:
      os.remove(STATE_PATH)
    except FileNotFoundError:
      pass
    if self._has_modem_manager():
      subprocess.run(["sudo", "systemctl", "unmask", "--runtime", "ModemManager"], capture_output=True)
      subprocess.run(["sudo", "systemctl", "start", "ModemManager"], capture_output=True)


def main():
  m = Modem()

  def _sig(*_):
    m.running = False

  signal.signal(signal.SIGINT, _sig)
  signal.signal(signal.SIGTERM, _sig)
  m.run()
  m.stop()


if __name__ == "__main__":
  main()
