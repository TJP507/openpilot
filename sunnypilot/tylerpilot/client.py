"""
Device <-> server client.

Deliberately stdlib-only (http.client + ssl + hashlib + subprocess) so the
agent stays tiny and adds no dependencies. The server's self-signed TLS
certificate is pinned: the fingerprint is captured on first registration
(trust-on-first-use, authorized by the pairing code) and verified on every
later connection.
"""
from __future__ import annotations

import hashlib
import http.client
import json
import os
import ssl
import subprocess

from . import config


class PinError(Exception):
  """Server certificate did not match the pinned fingerprint."""


class LinkError(Exception):
  """Server rejected the request (non-200)."""


def _fingerprint(der: bytes) -> str:
  return ":".join(f"{b:02X}" for b in hashlib.sha256(der).digest())


def _err(data: bytes) -> str:
  try:
    return json.loads(data).get("error", data.decode(errors="replace"))
  except Exception:
    return data.decode(errors="replace")


def _request(host: str, port: int, method: str, path: str, headers: dict | None = None,
             body: str | None = None, pin: str | None = None, timeout: float = 15.0):
  ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
  ctx.check_hostname = False
  ctx.verify_mode = ssl.CERT_NONE  # verified manually against the pinned fingerprint
  conn = http.client.HTTPSConnection(host, port, context=ctx, timeout=timeout)
  try:
    conn.connect()
    der = conn.sock.getpeercert(binary_form=True)
    fp = _fingerprint(der)
    if pin and fp != pin:
      raise PinError("server certificate does not match the pinned fingerprint")
    conn.request(method, path, body=body, headers=headers or {})
    resp = conn.getresponse()
    data = resp.read()
    return resp.status, data, fp
  finally:
    conn.close()


# ---- tunnel key (device -> server, used for ssh -R) ----

def ensure_tunnel_key() -> str:
  if not (os.path.exists(config.TUNNEL_KEY_PATH) and os.path.exists(config.TUNNEL_PUB_PATH)):
    subprocess.run(
      ["ssh-keygen", "-t", "ed25519", "-N", "", "-C", "tylerpilot-device", "-f", config.TUNNEL_KEY_PATH],
      check=True, capture_output=True,
    )
    os.chmod(config.TUNNEL_KEY_PATH, 0o600)
  with open(config.TUNNEL_PUB_PATH) as f:
    return f.read().strip()


def _authorized_keys_paths() -> list[str]:
  # On a comma 3X, sshd reads `authorizedkeysfile /data/params/d/GithubSshKeys
  # /tmp/authorized_keys`. We deliberately use /tmp/authorized_keys: the comma UI
  # only manages the GithubSshKeys param, so our key survives the user adding or
  # removing their own GitHub keys. The agent re-installs it on boot, so it also
  # survives reboots.
  paths = ["/tmp/authorized_keys"]
  for home in {f"/home/{config.DEVICE_SSH_USER}", os.path.expanduser("~")}:
    paths.append(os.path.join(home, ".ssh", "authorized_keys"))
  return paths


def install_server_key(pubkey: str) -> None:
  """Authorize the server's login key on this device (idempotent)."""
  pub = (pubkey or "").strip()
  if not pub.startswith("ssh-"):
    return
  b64 = pub.split()[1]
  for path in _authorized_keys_paths():
    try:
      os.makedirs(os.path.dirname(path), exist_ok=True)
      existing = ""
      if os.path.exists(path):
        with open(path) as f:
          existing = f.read()
      if b64 not in existing:
        with open(path, "a") as f:
          if existing and not existing.endswith("\n"):
            f.write("\n")
          f.write(pub + "\n")
      os.chmod(path, 0o600)
    except OSError:
      pass


def remove_server_key(pubkey: str) -> None:
  """Remove the server's login key (used on unlink)."""
  pub = (pubkey or "").strip()
  if not pub.startswith("ssh-"):
    return
  b64 = pub.split()[1]
  for path in _authorized_keys_paths():
    try:
      if not os.path.exists(path):
        continue
      with open(path) as f:
        kept = [ln for ln in f.read().splitlines() if b64 not in ln]
      with open(path, "w") as f:
        f.write("\n".join(kept) + ("\n" if kept else ""))
      os.chmod(path, 0o600)
    except OSError:
      pass


# ---- server API ----

def register(host: str, port: int, code: str, name: str, uid: str, version: str,
             dongle_id: str, tunnel_pubkey: str) -> dict:
  payload = {
    "code": code, "name": name, "uid": uid, "version": version,
    "dongle_id": dongle_id, "tunnel_pubkey": tunnel_pubkey,
    "ssh_user": config.DEVICE_SSH_USER,
  }
  status, data, fp = _request(
    host, port, "POST", "/api/v1/device/register",
    {"content-type": "application/json"}, json.dumps(payload), pin=None, timeout=20.0,
  )
  if status != 200:
    raise LinkError(_err(data))
  j = json.loads(data)
  j.setdefault("fingerprint", fp)
  return j


def heartbeat(host: str, port: int, token: str, pin: str, stats: dict) -> dict:
  status, data, _ = _request(
    host, port, "POST", "/api/v1/device/heartbeat",
    {"content-type": "application/json", "authorization": f"Bearer {token}"},
    json.dumps({"version": stats.get("version", ""), "stats": stats}), pin=pin, timeout=15.0,
  )
  if status != 200:
    raise LinkError(_err(data))
  return json.loads(data)


def poll(host: str, port: int, token: str, pin: str, timeout: float = 40.0) -> dict:
  status, data, _ = _request(
    host, port, "GET", "/api/v1/device/poll",
    {"authorization": f"Bearer {token}"}, None, pin=pin, timeout=timeout,
  )
  if status != 200:
    raise LinkError(_err(data))
  return json.loads(data)


def job_result(host: str, port: int, token: str, pin: str, job_id: str,
               ok: bool, result: str = "", artifact: dict | None = None) -> None:
  payload: dict = {"id": job_id, "status": "done" if ok else "failed", "result": result}
  if artifact:
    payload["artifact"] = artifact  # {kind, label, data(base64)}
  status, data, _ = _request(
    host, port, "POST", "/api/v1/device/job_result",
    {"content-type": "application/json", "authorization": f"Bearer {token}"},
    json.dumps(payload), pin=pin, timeout=120.0,
  )
  if status != 200:
    raise LinkError(_err(data))


def post_location(host: str, port: int, token: str, pin: str, points: list) -> None:
  _request(host, port, "POST", "/api/v1/device/location",
           {"content-type": "application/json", "authorization": f"Bearer {token}"},
           json.dumps({"points": points}), pin=pin, timeout=30.0)


def post_trips(host: str, port: int, token: str, pin: str, trips: list) -> None:
  _request(host, port, "POST", "/api/v1/device/trips",
           {"content-type": "application/json", "authorization": f"Bearer {token}"},
           json.dumps({"trips": trips}), pin=pin, timeout=60.0)


def download_artifact(host: str, port: int, token: str, pin: str, artifact_id: str) -> bytes:
  status, data, _ = _request(
    host, port, "GET", f"/api/v1/device/artifact?id={artifact_id}",
    {"authorization": f"Bearer {token}"}, None, pin=pin, timeout=120.0,
  )
  if status != 200:
    raise LinkError(_err(data))
  return data


def open_tunnel(host: str, remote_port: int, ssh_port: int = 22, local_ssh_port: int = 22):
  """Open a reverse tunnel 127.0.0.1:<remote_port> on the server -> this device's SSH."""
  args = [
    "ssh", "-N",
    "-R", f"127.0.0.1:{remote_port}:localhost:{local_ssh_port}",
    "-p", str(ssh_port),
    "-i", config.TUNNEL_KEY_PATH,
    "-o", "StrictHostKeyChecking=accept-new",
    "-o", f"UserKnownHostsFile={config.KNOWN_HOSTS_PATH}",
    "-o", "ExitOnForwardFailure=yes",
    "-o", "ServerAliveInterval=15", "-o", "ServerAliveCountMax=3",
    "-o", "BatchMode=yes", "-o", "ConnectTimeout=10",
    f"tunnel@{host}",
  ]
  return subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                          start_new_session=True)
