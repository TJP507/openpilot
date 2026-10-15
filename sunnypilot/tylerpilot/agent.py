"""
TylerPilot Cloud background agent.

Keeps a lightweight link to the central server while the device is linked:
periodic stats heartbeats and a long-poll for commands (currently: open a
reverse SSH tunnel on request). Uses a stdlib-only HTTP client and keeps
traffic minimal, especially on LTE.
"""
from __future__ import annotations

import os
import threading
import time

import psutil

from openpilot.common.git import get_commit, get_short_branch
from openpilot.common.params import Params
from openpilot.system.hardware import HARDWARE, PC
from openpilot.system.version import get_version

from openpilot.sunnypilot.tylerpilot import config, client, log, actions

# Heartbeat cadence (seconds) by link type.
_INTERVAL = {"wifi": 15, "ethernet": 15, "cell": 15, "none": 15}

# Recordings (dash cam) directory and how long its size may be cached. Summing
# the tree is expensive, so it is refreshed at most every 10 minutes.
_RECORDINGS_DIR = "/data/media/0/realdata"
_RECORDINGS_TTL = 600.0
_recordings_cache: tuple[float, int] = (0.0, -1)  # (monotonic_at, bytes); -1 = unknown

# Idle / backoff sleeps (seconds).
_IDLE_SLEEP = 5
_REVOKED_BACKOFF = 60  # a revoked device only re-checks slowly for a new token
_ERROR_SLEEP = 5
_OUTER_ERROR_SLEEP = 10

# A 401 only confirms revocation after this many consecutive of our own
# "unauthenticated" responses, spanning at least this long (a proxy misroute or
# a server restore can 401 transiently).
_AUTH_STRIKES_REQUIRED = 3
_AUTH_MIN_SPAN = 120.0

_bridges: dict = {}
_auth_strikes = 0
_auth_first_at = 0.0
_revocation_logged = False


def _active_iface() -> str:
  """Interface of the default route with the lowest metric (the one actually used)."""
  best = ("", 1 << 30)
  try:
    with open("/proc/net/route") as f:
      for line in f.readlines()[1:]:
        fields = line.split()
        if len(fields) >= 7 and fields[1] == "00000000":
          metric = int(fields[6])
          if metric < best[1]:
            best = (fields[0], metric)
  except OSError:
    pass
  return best[0]


def _classify(iface: str) -> str | None:
  if not iface:
    return None
  if any(p in iface for p in ("rmnet", "wwan", "ppp")):
    return "cell"
  if any(p in iface for p in ("wlan", "wlp")):
    return "wifi"
  if any(p in iface for p in ("eth", "enp", "usb", "tether")):
    return "ethernet"
  return None


def _net_type() -> str:
  # Prefer the interface of the active default route (e.g. Wi-Fi over an idle modem).
  kind = _classify(_active_iface())
  if kind:
    return kind
  # Fallback: any usable interface.
  try:
    names = " ".join(psutil.net_if_addrs().keys())
  except Exception:
    return "none"
  return _classify(names) or "none"


def _cpu_temp():
  try:
    cfg = HARDWARE.get_thermal_config()
    if cfg and cfg.cpu:
      return round(cfg.cpu[0].read(), 1)
  except Exception:
    pass
  return None


def _onroad_state() -> bool | None:
  """Onroad flag, or None when it cannot be read (stats omit unknown values)."""
  try:
    return bool(Params().get_bool("IsOnroad"))
  except Exception as e:
    log.warning(f"could not read IsOnroad for stats: {e}")
    return None


def _git(fn) -> str:
  try:
    return fn() or ""
  except Exception:
    return ""


def _dir_size(path: str) -> int:
  total = 0
  try:
    with os.scandir(path) as it:
      for entry in it:
        try:
          if entry.is_dir(follow_symlinks=False):
            total += _dir_size(entry.path)
          elif entry.is_file(follow_symlinks=False):
            total += entry.stat(follow_symlinks=False).st_size
        except OSError:
          pass
  except OSError:
    pass
  return total


def _recordings_bytes() -> int | None:
  """Size of the dash cam recordings directory, cached for up to 10 minutes."""
  global _recordings_cache
  at, cached = _recordings_cache
  now = time.monotonic()
  if cached >= 0 and now - at < _RECORDINGS_TTL:
    return cached
  if not os.path.isdir(_RECORDINGS_DIR):
    _recordings_cache = (now, -1)
    return None
  size = _dir_size(_RECORDINGS_DIR)
  _recordings_cache = (now, size)
  return size


def gather_stats() -> dict:
  """A cheap device-health snapshot. Unavailable values are omitted, never faked."""
  stats: dict = {"net_type": _net_type()}
  version = _git(get_version)
  if version:
    stats["version"] = version
  branch = _git(get_short_branch)
  if branch:
    stats["branch"] = branch
  commit = _git(get_commit)
  if commit:
    stats["commit"] = commit[:7]
  try:
    boot = psutil.boot_time()
    stats["uptime_s"] = int(time.time() - boot)  # noqa: TID251 — wall-clock uptime
    stats["started_at"] = int(boot)
  except Exception:
    pass
  temp = _cpu_temp()
  if temp is not None:
    stats["cpu_temp_c"] = temp
  try:
    stats["cpu_pct"] = round(psutil.cpu_percent(interval=None), 1)
  except Exception:
    pass
  try:
    stats["mem_pct"] = round(psutil.virtual_memory().percent, 1)
  except Exception:
    pass
  try:
    usage = psutil.disk_usage("/" if PC else "/data")
    stats["storage_free_bytes"] = usage.free
    stats["storage_total_bytes"] = usage.total
  except Exception:
    pass
  recordings = _recordings_bytes()
  if recordings is not None:
    stats["recordings_bytes"] = recordings
  onroad = _onroad_state()
  if onroad is not None:
    stats["onroad"] = onroad
  return stats


def _reap_bridges() -> None:
  global _bridges
  _bridges = {sid: t for sid, t in _bridges.items() if t.is_alive()}


def _handle_command(cmd: dict) -> None:
  ctype = cmd.get("type")
  if ctype == "ssh_request":
    _handle_ssh(cmd)
  elif ctype == "job":
    _run_job(cmd)


def _handle_ssh(cmd: dict) -> None:
  """Open a single-port SSH-over-WebSocket bridge for the requested session."""
  _reap_bridges()
  session = str(cmd.get("session") or "")
  if not session or session in _bridges:
    return
  host = config.get("host")
  token = config.get("token")
  pin = config.get("fingerprint")
  if not (host and token):
    return
  port = int(config.get("port"))

  def _run() -> None:
    try:
      client.bridge_ssh(host, port, token, pin, session)
    except Exception as e:
      config.set_error(f"tunnel failed: {e}")

  t = threading.Thread(target=_run, daemon=True)
  _bridges[session] = t
  t.start()
  log.info(f"opened ssh bridge {session[:8]}")


def _run_job(cmd: dict) -> None:
  job_id = str(cmd.get("id") or "")
  kind = str(cmd.get("kind") or "")
  payload = cmd.get("payload") or {}
  log.info(f"job {kind} ({job_id})")

  ok, result, extra, deferred = actions.run(kind, payload)

  host, port = config.get("host"), int(config.get("port"))
  token, pin = config.get("token"), config.get("fingerprint")
  try:
    if extra and extra.get("kind") == "_location":
      client.post_location(host, port, token, pin, extra.get("points") or [])
      extra = None
    elif extra and extra.get("kind") == "_trips":
      client.post_trips(host, port, token, pin, extra.get("trips") or [])
      extra = None
    client.job_result(host, port, token, pin, job_id, ok, result, extra)
  except Exception as e:
    log.warning(f"job result report failed: {e}")
    return

  # Side-effecting actions (reboot/poweroff) report back first, then act.
  if deferred is not None:
    try:
      deferred()
    except Exception as e:
      log.warning(f"deferred action {kind} failed: {e}")


def _ensure_server_key() -> None:
  """Re-assert the server's SSH login key (idempotent; survives reboots / UI
  edits). Never re-adds it while the device is revoked — a re-link reinstalls it."""
  if config.is_revoked():
    return
  key = config.get("server_ssh_key")
  if key:
    client.install_server_key(key)


def _reset_auth_strikes() -> None:
  global _auth_strikes, _auth_first_at
  _auth_strikes = 0
  _auth_first_at = 0.0


def _confirm_revoked(reason: str) -> None:
  """A confirmed revocation: drop the token (keep host/port), remove the server's
  SSH login key, and log once until the device is re-linked."""
  global _revocation_logged
  server_key = config.get("server_ssh_key")
  config.mark_revoked(reason)
  if server_key:
    client.remove_server_key(server_key)
  config.set_values(server_ssh_key="")
  if not _revocation_logged:
    log.warning(f"server revoked this device's link; re-link to continue: {reason}")
    _revocation_logged = True


def _handle_auth_error(code: str, reason: str) -> None:
  """A 401. Only a run of our own 'unauthenticated' responses — at least
  _AUTH_STRIKES_REQUIRED of them spanning >= _AUTH_MIN_SPAN — confirms
  revocation; a foreign 401 (e.g. a proxy's Basic auth) never does."""
  global _auth_strikes, _auth_first_at
  if code != "unauthenticated":
    config.set_error(f"server rejected the request (401): {reason}")
    return
  now = time.monotonic()
  if _auth_strikes == 0:
    _auth_first_at = now
  _auth_strikes += 1
  if _auth_strikes >= _AUTH_STRIKES_REQUIRED and now - _auth_first_at >= _AUTH_MIN_SPAN:
    _confirm_revoked(reason)
  else:
    config.set_error(
      f"Server rejected this device's key ({_auth_strikes}/{_AUTH_STRIKES_REQUIRED}) — re-link if this persists")


def _backoff_seconds() -> int:
  """How long to idle: a revoked device waits longer (it only resumes when the
  user links a new code, which sets a fresh token)."""
  return _REVOKED_BACKOFF if config.is_revoked() else _IDLE_SLEEP


def _cycle(last_heartbeat: float) -> float:
  """One pass of the agent loop: heartbeat on cadence, then one poll. Returns
  the (possibly updated) heartbeat time."""
  _ensure_server_key()

  host = config.get("host")
  port = int(config.get("port"))
  token = config.get("token")
  pin = config.get("fingerprint")

  # Heartbeat on a cadence that scales with the link type.
  interval = _INTERVAL.get(_net_type(), 15)
  if time.monotonic() - last_heartbeat >= interval:
    try:
      client.heartbeat(host, port, token, pin, gather_stats())
      _reset_auth_strikes()
      if config.get("last_error"):
        config.set_error("")
    except client.AuthError as e:
      _handle_auth_error(e.code, str(e))
      if config.is_revoked():
        return last_heartbeat
    except client.PinError as e:
      config.set_error(f"cert pin mismatch: {e}")
    except Exception as e:
      config.set_error(str(e))
    last_heartbeat = time.monotonic()

  # Poll continuously (long-poll holds ~25s) so commands arrive promptly
  # instead of waiting for the next heartbeat cycle.
  try:
    _handle_command(client.poll(host, port, token, pin))
    _reset_auth_strikes()
    if config.get("last_error"):
      config.set_error("")
  except client.AuthError as e:
    _handle_auth_error(e.code, str(e))
  except client.PinError as e:
    config.set_error(f"cert pin mismatch: {e}")
    time.sleep(_ERROR_SLEEP)
  except Exception as e:
    config.set_error(str(e))
    time.sleep(_ERROR_SLEEP)
  return last_heartbeat


def main() -> None:
  log.info("agent starting")
  actions.cleanup_legacy_prerestore()
  actions.cleanup_stale_restart_flag()
  last_heartbeat = 0.0
  while True:
    try:
      if not config.is_linked():
        time.sleep(_backoff_seconds())
        continue
      last_heartbeat = _cycle(last_heartbeat)
    except Exception as e:
      log.warning(f"agent loop error: {e}")
      time.sleep(_OUTER_ERROR_SLEEP)


if __name__ == "__main__":
  main()
