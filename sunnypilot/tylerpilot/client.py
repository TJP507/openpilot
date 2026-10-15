"""
Device <-> server client.

Deliberately stdlib-only (http.client + ssl + hashlib + subprocess) so the
agent stays tiny and adds no dependencies. The server's self-signed TLS
certificate is pinned: the fingerprint is captured on first registration
(trust-on-first-use, authorized by the pairing code) and verified on every
later connection.
"""
from __future__ import annotations

import asyncio
import hashlib
import http.client
import json
import os
import socket
import ssl
import subprocess

from . import config


class PinError(Exception):
  """Server certificate did not match the pinned fingerprint."""


class LinkError(Exception):
  """Server rejected the request (non-200)."""


class RevokedError(Exception):
  """The server revoked this device's key (HTTP 401); re-link to continue."""


def _fingerprint(der: bytes) -> str:
  return ":".join(f"{b:02X}" for b in hashlib.sha256(der).digest())


def _err(data: bytes) -> str:
  try:
    return json.loads(data).get("error", data.decode(errors="replace"))
  except Exception:
    return data.decode(errors="replace")


def normalize_pairing_code(text: str) -> str:
  """Strip everything but digits, so a code entered as XXXX-XXXX-XXXX or with
  spaces is accepted. Returns "" when it is not a 12-digit code."""
  digits = "".join(ch for ch in (text or "") if ch.isdigit())
  return digits if len(digits) == 12 else ""


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

def _generate_tunnel_key() -> str:
  subprocess.run(
    ["ssh-keygen", "-t", "ed25519", "-N", "", "-C", "tylerpilot-device", "-f", config.TUNNEL_KEY_PATH],
    check=True, capture_output=True,
  )
  os.chmod(config.TUNNEL_KEY_PATH, 0o600)
  with open(config.TUNNEL_PUB_PATH) as f:
    return f.read().strip()


def rotate_tunnel_key() -> str:
  """Generate a fresh key pair, discarding any existing one. Called on every
  (re)link so a device never reuses a key the server has already seen."""
  for path in (config.TUNNEL_KEY_PATH, config.TUNNEL_PUB_PATH):
    try:
      os.remove(path)
    except FileNotFoundError:
      pass
  return _generate_tunnel_key()


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
  if status == 401:
    raise RevokedError(_err(data))
  if status != 200:
    raise LinkError(_err(data))
  return json.loads(data)


def poll(host: str, port: int, token: str, pin: str, timeout: float = 40.0) -> dict:
  status, data, _ = _request(
    host, port, "GET", "/api/v1/device/poll",
    {"authorization": f"Bearer {token}"}, None, pin=pin, timeout=timeout,
  )
  if status == 401:
    raise RevokedError(_err(data))
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


def bridge_ssh(host: str, port: int, token: str, pin: str, session: str,
               local_ssh_port: int = 22) -> None:
  """Single-port SSH-over-WebSocket bridge.

  Opens a WebSocket to the server on the SAME host:port as the device API and
  bridges it to this device's sshd, so the server reaches the device's SSH over
  the one API port. Blocks until the bridge closes.

  Uses asyncio + aiohttp (rather than websocket-client) so both directions are
  driven by one event loop with proper flow control; the previous two-thread
  websocket-client model dropped large sustained transfers.
  """
  try:
    import aiohttp
  except ImportError as e:  # pragma: no cover
    raise LinkError(f"aiohttp unavailable: {e}") from e

  if pin:
    _verify_pin(host, port, pin)
  asyncio.run(_bridge_loop(aiohttp, host, port, token, session, local_ssh_port))


def _verify_pin(host: str, port: int, pin: str) -> None:
  """Verify the server presents the pinned certificate (TOFU trust anchor)."""
  ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
  ctx.check_hostname = False
  ctx.verify_mode = ssl.CERT_NONE  # verified manually against the pinned fingerprint
  with socket.create_connection((host, port), timeout=15) as raw:
    with ctx.wrap_socket(raw, server_hostname=host) as tls:
      der = tls.getpeercert(binary_form=True)
  if _fingerprint(der) != pin:
    raise PinError("server certificate does not match the pinned fingerprint")


async def _bridge_loop(aiohttp, host: str, port: int, token: str, session: str,
                       local_ssh_port: int) -> None:
  ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
  ctx.check_hostname = False
  ctx.verify_mode = ssl.CERT_NONE  # verified manually against the pinned fingerprint
  url = f"wss://{host}:{port}/api/v1/device/ssh-bridge?session={session}"
  timeout = aiohttp.ClientTimeout(total=None, sock_connect=15, sock_read=None)
  async with aiohttp.ClientSession(timeout=timeout) as cs:
    async with cs.ws_connect(
      url, ssl=ctx, headers={"Authorization": f"Bearer {token}"}, max_msg_size=0,
    ) as ws:
      reader, writer = await asyncio.open_connection("127.0.0.1", local_ssh_port)

      async def sshd_to_ws() -> None:
        try:
          while True:
            data = await reader.read(65536)
            if not data:
              break
            await ws.send_bytes(data)
        except Exception:
          pass
        finally:
          await ws.close()

      async def ws_to_sshd() -> None:
        try:
          async for msg in ws:
            if msg.type == aiohttp.WSMsgType.BINARY:
              writer.write(msg.data)
              await writer.drain()
            elif msg.type in (aiohttp.WSMsgType.CLOSE, aiohttp.WSMsgType.CLOSED,
                              aiohttp.WSMsgType.ERROR):
              break
        except Exception:
          pass
        finally:
          try:
            writer.close()
          except Exception:
            pass

      try:
        await asyncio.gather(sshd_to_ws(), ws_to_sshd())
      finally:
        try:
          writer.close()
        except Exception:
          pass
