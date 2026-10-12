"""
TylerPilot Cloud background agent.

Keeps a lightweight link to the central server while the device is linked:
periodic stats heartbeats and a long-poll for commands (currently: open a
reverse SSH tunnel on request). Uses a stdlib-only HTTP client and keeps
traffic minimal, especially on LTE.
"""
from __future__ import annotations

import subprocess
import time

import psutil

from openpilot.system.hardware import HARDWARE, PC
from openpilot.system.version import get_version

from openpilot.sunnypilot.tylerpilot import config, client, log, actions

# Heartbeat cadence (seconds) by link type.
_INTERVAL = {"wifi": 15, "lan": 15, "lte": 15, "none": 15}

_tunnels: list[tuple[subprocess.Popen, int]] = []


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
    return "lte"
  if any(p in iface for p in ("wlan", "wlp")):
    return "wifi"
  if any(p in iface for p in ("eth", "enp", "usb", "tether")):
    return "lan"
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


def gather_stats() -> dict:
  stats: dict = {"net": _net_type()}
  try:
    stats["version"] = get_version()
  except Exception:
    stats["version"] = ""
  try:
    stats["uptime"] = int(time.time() - psutil.boot_time())  # noqa: TID251 — wall-clock uptime
  except Exception:
    pass
  temp = _cpu_temp()
  if temp:
    stats["cpu_temp"] = temp
  try:
    stats["free_storage"] = psutil.disk_usage("/" if PC else "/data").free
  except Exception:
    pass
  try:
    stats["device_type"] = HARDWARE.get_device_type()
  except Exception:
    pass
  return stats


def _reap_tunnels() -> None:
  global _tunnels
  _tunnels = [(p, port) for p, port in _tunnels if p.poll() is None]


def _handle_command(cmd: dict) -> None:
  ctype = cmd.get("type")
  if ctype == "ssh_request":
    _handle_ssh(cmd)
  elif ctype == "job":
    _run_job(cmd)


def _handle_ssh(cmd: dict) -> None:
  _reap_tunnels()
  remote_port = int(cmd.get("port"))

  # Already have a live tunnel on the requested port — nothing to do.
  if any(port == remote_port for _proc, port in _tunnels):
    return

  # Replace any tunnel on a different (stale) port.
  for proc, _port in _tunnels:
    try:
      proc.kill()
    except Exception:
      pass
  _tunnels.clear()

  try:
    proc = client.open_tunnel(config.get("host"), remote_port, ssh_port=int(config.get("ssh_port") or 22))
    _tunnels.append((proc, remote_port))
    log.info(f"opened reverse tunnel on server port {remote_port}")
  except Exception as e:
    config.set_error(f"tunnel failed: {e}")


def _run_job(cmd: dict) -> None:
  job_id = str(cmd.get("id") or "")
  kind = str(cmd.get("kind") or "")
  payload = cmd.get("payload") or {}
  log.info(f"job {kind} ({job_id})")

  ok, result, extra = actions.run(kind, payload)

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


def _ensure_server_key() -> None:
  """Re-assert the server's SSH login key (idempotent; survives reboots / UI edits)."""
  key = config.get("server_ssh_key")
  if key:
    client.install_server_key(key)


def main() -> None:
  log.info("agent starting")
  last_heartbeat = 0.0
  while True:
    try:
      if not config.is_linked():
        time.sleep(5)
        continue

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
          if config.get("last_error"):
            config.set_error("")
        except client.PinError as e:
          config.set_error(f"cert pin mismatch: {e}")
        except Exception as e:
          config.set_error(str(e))
        last_heartbeat = time.monotonic()

      # Poll continuously (long-poll holds ~25s) so commands arrive promptly
      # instead of waiting for the next heartbeat cycle.
      try:
        _handle_command(client.poll(host, port, token, pin))
      except client.PinError as e:
        config.set_error(f"cert pin mismatch: {e}")
        time.sleep(5)
      except Exception as e:
        config.set_error(str(e))
        time.sleep(5)
    except Exception as e:
      log.warning(f"agent loop error: {e}")
      time.sleep(10)


if __name__ == "__main__":
  main()
