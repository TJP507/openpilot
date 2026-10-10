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

from openpilot.common.swaglog import cloudlog
from openpilot.system.hardware import HARDWARE, PC
from openpilot.system.version import get_version

from openpilot.sunnypilot.tylerpilot import config, client

# Heartbeat cadence by link type. Cellular is deliberately slowest.
_INTERVAL = {"wifi": 30, "lan": 30, "lte": 60, "none": 90}

_tunnels: list[subprocess.Popen] = []


def _net_type() -> str:
  try:
    names = " ".join(psutil.net_if_addrs().keys())
  except Exception:
    return "none"
  if any(p in names for p in ("rmnet", "wwan", "ppp")):
    return "lte"
  if any(p in names for p in ("wlan", "wlp")):
    return "wifi"
  if any(p in names for p in ("eth", "enp", "usb")):
    return "lan"
  return "none"


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
    stats["uptime"] = int(time.time() - psutil.boot_time())
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
  _tunnels = [p for p in _tunnels if p.poll() is None]


def _handle_command(cmd: dict) -> None:
  if cmd.get("type") == "ssh_request":
    _reap_tunnels()
    if any(p.poll() is None for p in _tunnels):
      return  # a tunnel is already up
    remote_port = int(cmd.get("port"))
    try:
      proc = client.open_tunnel(config.get("host"), remote_port)
      _tunnels.append(proc)
      cloudlog.info(f"tylerpilot: opened reverse tunnel on server port {remote_port}")
    except Exception as e:
      config.set_error(f"tunnel failed: {e}")


def main() -> None:
  cloudlog.info("tylerpilot agent starting")
  while True:
    try:
      if not config.is_linked():
        time.sleep(5)
        continue

      host = config.get("host")
      port = int(config.get("port"))
      token = config.get("token")
      pin = config.get("fingerprint")

      stats = gather_stats()
      try:
        client.heartbeat(host, port, token, pin, stats)
        if config.get("last_error"):
          config.set_error("")
      except client.PinError as e:
        config.set_error(f"cert pin mismatch: {e}")
      except Exception as e:
        config.set_error(str(e))

      try:
        _handle_command(client.poll(host, port, token, pin))
      except Exception as e:
        config.set_error(str(e))

      time.sleep(_INTERVAL.get(stats.get("net", "none"), 60))
    except Exception as e:
      cloudlog.warning(f"tylerpilot agent loop error: {e}")
      time.sleep(15)


if __name__ == "__main__":
  main()
