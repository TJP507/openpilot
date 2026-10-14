"""
Persistent link state for TylerPilot Cloud.

Like the web dash cam config, this lives in a small JSON file rather than a
Params key (Params only accepts keys compiled into the prebuilt params library,
and this branch ships no build system to recompile it). The file is the single
source of truth shared by the settings UI and the background agent, and is
written 0600 because it holds the device token.

The server address is hardcoded for the proof of concept.
"""
from __future__ import annotations

import json
import os
import threading

from openpilot.system.hardware import PC
from openpilot.system.hardware.hw import Paths

STATE_DIR = Paths.comma_home() if PC else "/data/community"
STATE_PATH = os.path.join(STATE_DIR, "tylerpilot.json")
TUNNEL_KEY_PATH = os.path.join(STATE_DIR, "tylerpilot_tunnel")
TUNNEL_PUB_PATH = TUNNEL_KEY_PATH + ".pub"
KNOWN_HOSTS_PATH = os.path.join(STATE_DIR, "tylerpilot_known_hosts")

# The comma's SSH login user (where the server's login key is installed).
DEVICE_SSH_USER = "comma"

# Server address. TCP-passthrough endpoint (the reverse proxy forwards raw TLS
# to the backend, so the device sees our pinned self-signed cert). A single port
# carries both the device API and the SSH-over-WebSocket tunnel.
DEFAULT_HOST = "pilot-connect.tylerjp.com"
DEFAULT_PORT = 7448

# Previous hardcoded defaults; linked devices are migrated off them on load.
_LEGACY_DEFAULT_PORTS = (8021, 443)

_LOCK = threading.Lock()

_DEFAULTS: dict = {
  "host": DEFAULT_HOST,
  "port": DEFAULT_PORT,
  "device_id": "",
  "token": "",
  "fingerprint": "",
  "name": "",
  "server_name": "",
  "server_ssh_key": "",
  "linked": False,
  "last_error": "",
}


def load() -> dict:
  try:
    with open(STATE_PATH) as f:
      data = json.load(f)
  except (OSError, ValueError):
    data = {}
  if not isinstance(data, dict):
    data = {}
  out = dict(_DEFAULTS)
  out.update({k: data[k] for k in _DEFAULTS if k in data})
  # Migrate linked devices off any previous hardcoded default port.
  if out.get("port") in _LEGACY_DEFAULT_PORTS:
    out["port"] = DEFAULT_PORT
  return out


def _save(state: dict) -> None:
  os.makedirs(STATE_DIR, exist_ok=True)
  tmp = STATE_PATH + ".tmp"
  with open(tmp, "w") as f:
    json.dump(state, f)
  os.chmod(tmp, 0o600)
  os.replace(tmp, STATE_PATH)


def get(key: str):
  return load().get(key, _DEFAULTS.get(key))


def set_values(**kwargs) -> dict:
  with _LOCK:
    state = load()
    state.update(kwargs)
    _save(state)
    return state


def is_linked() -> bool:
  s = load()
  return bool(s["linked"] and s["token"] and s["device_id"])


def set_link(device_id: str, token: str, fingerprint: str, server_name: str, name: str,
             server_ssh_key: str = "") -> dict:
  return set_values(device_id=device_id, token=token, fingerprint=fingerprint,
                    server_name=server_name, name=name, server_ssh_key=server_ssh_key,
                    linked=True, last_error="")


def clear_link() -> dict:
  return set_values(device_id="", token="", fingerprint="", server_name="", server_ssh_key="",
                    linked=False, last_error="")


def set_error(msg: str) -> None:
  set_values(last_error=msg[:300])


def set_server(host: str, port: int) -> dict:
  return set_values(host=host, port=port)
