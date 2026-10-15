"""
Remote actions for tylerpilotd.

Every handler returns (ok: bool, result: str, artifact: dict | None). The agent
reports the tuple back to the server via client.job_result(). Handlers are
defensive: a failure returns a message, never raises out of the loop.
"""
from __future__ import annotations

import base64
import io
import os
import subprocess
import tarfile
import time

from openpilot.common.params import Params
from openpilot.system.hardware import HARDWARE

from openpilot.sunnypilot.tylerpilot import config, log, toast

CHANNELS = ("dev-c3x", "staging-c3x", "release-c3x")
REPO = "https://github.com/TJP507/openpilot.git"


def _run(args, timeout=60, check=False) -> tuple[int, str]:
  try:
    p = subprocess.run(args, capture_output=True, timeout=timeout, text=True)
    return p.returncode, (p.stdout or "") + (p.stderr or "")
  except Exception as e:
    return 1, str(e)


# --------------------------------------------------------------------------
# power / manager
# --------------------------------------------------------------------------
def reboot(_payload: dict):
  toast.show("TylerPilot: rebooting…")
  time.sleep(1)
  HARDWARE.reboot()
  return True, "rebooting", None


def poweroff(_payload: dict):
  toast.show("TylerPilot: powering off…")
  time.sleep(1)
  HARDWARE.shutdown()
  return True, "powering off", None


def restart_manager(_payload: dict):
  toast.show("TylerPilot: restarting manager…")
  # launch_chffrplus.sh restarts the manager when this flag file is present.
  flag = os.path.join(config.STATE_DIR, "tylerpilot_restart_manager")
  try:
    open(flag, "w").close()
  except OSError as e:
    return False, f"could not set restart flag: {e}", None
  _run(["pkill", "-f", "manager.py"])
  return True, "manager restart requested", None


# --------------------------------------------------------------------------
# params
# --------------------------------------------------------------------------
def _typed(value):
  """Coerce a stored param value (bytes) to a JSON-friendly type."""
  if value is None:
    return None
  try:
    s = value.decode("utf-8")
  except Exception:
    return base64.b64encode(value).decode()
  low = s.lower()
  if low in ("0", "1"):
    return low == "1"
  return s


def param_get(payload: dict):
  key = str(payload.get("key") or "")
  if not key:
    return False, "no key", None
  try:
    val = Params().get(key)
    return True, val.decode("utf-8", "replace") if isinstance(val, bytes) else str(val), None
  except Exception as e:
    return False, str(e), None


def param_set(payload: dict):
  key = str(payload.get("key") or "")
  if not key:
    return False, "no key", None
  value = payload.get("value")
  try:
    p = Params()
    if isinstance(value, bool):
      p.put_bool(key, value)
    elif isinstance(value, int):
      p.put_int(key, value)
    elif isinstance(value, float):
      p.put_float(key, value)
    else:
      p.put(key, str(value))
    return True, f"{key} set", None
  except Exception as e:
    return False, str(e), None


# --------------------------------------------------------------------------
# update / channel switch
# --------------------------------------------------------------------------
def update(payload: dict):
  channel = str(payload.get("channel") or "")
  if channel not in CHANNELS:
    return False, f"unknown channel {channel!r}", None
  d = "/data/openpilot"
  if not os.path.isdir(os.path.join(d, ".git")):
    return False, "no git checkout at /data/openpilot", None

  _run(["git", "-C", d, "remote", "set-url", "origin", REPO])
  rc, out = _run(["git", "-C", d, "fetch", "--depth=1", "origin", channel], timeout=300)
  if rc != 0:
    return False, f"fetch failed: {out[-400:]}", None
  rc, out = _run(["git", "-C", d, "checkout", "-f", channel], timeout=120)
  if rc != 0:
    return False, f"checkout failed: {out[-400:]}", None
  _run(["git", "-C", d, "reset", "--hard", f"origin/{channel}"], timeout=120)

  # Keep the boot overlay source in sync so the change survives a reboot.
  finalized = "/data/safe_staging/finalized"
  if os.path.isdir(finalized):
    _run(["rsync", "-a", "--delete", "--exclude=.git", f"{d}/", f"{finalized}/"], timeout=600)

  restart_manager({})
  return True, f"switched to {channel}; restarting manager", None


# --------------------------------------------------------------------------
# location (live)
# --------------------------------------------------------------------------
def location(payload: dict):
  from openpilot.sunnypilot.tylerpilot import trips
  pts = trips.recent_positions(1)
  if not pts:
    return False, "no GPS fix available", None
  return True, "gps", {"kind": "_location", "points": pts}


# --------------------------------------------------------------------------
# trips (parse qlogs locally)
# --------------------------------------------------------------------------
def trips_action(payload: dict):
  from openpilot.sunnypilot.tylerpilot import trips
  found = trips.parse_recent()
  return True, f"parsed {len(found)} trip(s)", {"kind": "_trips", "trips": found}


# --------------------------------------------------------------------------
# diagnostics + settings backup/restore (produce / consume artifacts)
# --------------------------------------------------------------------------
def _tar(paths: list[str], blobs: dict[str, bytes] | None = None) -> bytes:
  buf = io.BytesIO()
  # dereference=True: /data/params/d is a symlink to the real params store, so
  # without this the archive holds the link and no param files.
  with tarfile.open(fileobj=buf, mode="w:gz", dereference=True) as t:
    for p in paths:
      if os.path.exists(p):
        try:
          t.add(p, arcname=os.path.relpath(p, "/"))
        except (OSError, ValueError):
          pass
    for name, data in (blobs or {}).items():
      info = tarfile.TarInfo(name=name)
      info.size = len(data)
      info.mtime = int(time.time())  # noqa: TID251 — tar mtime is wall-clock
      t.addfile(info, io.BytesIO(data))
  return buf.getvalue()


D_INCLUDES = ["/data/params/d", "/data/community"]


def diagnostics(_payload: dict):
  blobs: dict[str, bytes] = {}
  cmds = {
    "diag/dmesg.txt": ["dmesg"],
    "diag/journal.txt": ["journalctl", "-n", "800", "--no-pager"],
    "diag/network.txt": ["ip", "addr"],
    "diag/routes.txt": ["ip", "route"],
    "diag/df.txt": ["df", "-h"],
    "diag/ps.txt": ["ps", "aux"],
    "diag/git.txt": ["git", "-C", "/data/openpilot", "log", "-1", "--oneline"],
    "diag/version.txt": ["cat", "/data/openpilot/sunnypilot/common/version.h"],
  }
  for name, args in cmds.items():
    _, out = _run(args, timeout=30)
    blobs[name] = out.encode("utf-8", "replace")

  # newest swaglog tail
  try:
    logdir = "/data/log"
    logs = sorted((os.path.join(logdir, f) for f in os.listdir(logdir) if f.startswith("swaglog")),
                  key=os.path.getmtime)
    if logs:
      with open(logs[-1], "rb") as f:
        data = f.read()
      blobs["diag/swaglog_tail.txt"] = data[-200_000:]
  except OSError:
    pass

  data = _tar(D_INCLUDES, blobs)  # params+community included per "no redaction"
  return True, f"diagnostic bundle ({len(data)} bytes)", {"kind": "diagnostics", "data": base64.b64encode(data).decode()}


def backup(_payload: dict):
  data = _tar(D_INCLUDES)
  return True, f"backup ({len(data)} bytes)", {"kind": "backup", "data": base64.b64encode(data).decode()}


def restore(payload: dict):
  """Restore a settings backup uploaded earlier (identified by artifact_id)."""
  from openpilot.sunnypilot.tylerpilot import client
  aid = str(payload.get("artifact_id") or "")
  if not aid:
    return False, "no artifact id", None
  raw = client.download_artifact(config.get("host"), int(config.get("port")), config.get("token"),
                                 config.get("fingerprint"), aid)
  # Safety: snapshot current state first.
  pre = _tar(D_INCLUDES)
  pre_path = os.path.join(config.STATE_DIR, f"prerestore-{int(time.time())}.tgz")  # noqa: TID251 — filename timestamp
  try:
    with open(pre_path, "wb") as f:
      f.write(pre)
  except OSError:
    pass
  try:
    with tarfile.open(fileobj=io.BytesIO(raw), mode="r:gz") as t:
      t.extractall("/")
  except Exception as e:
    return False, f"restore failed: {e}", None
  restart_manager({})
  return True, f"restored settings (prev saved to {os.path.basename(pre_path)})", None


HANDLERS = {
  "reboot": reboot,
  "poweroff": poweroff,
  "restart_manager": restart_manager,
  "param_get": param_get,
  "param_set": param_set,
  "update": update,
  "location": location,
  "trips": trips_action,
  "diagnostics": diagnostics,
  "backup": backup,
  "restore": restore,
}


def run(kind: str, payload: dict):
  fn = HANDLERS.get(kind)
  if not fn:
    return False, f"unknown action {kind!r}", None
  try:
    return fn(payload or {})
  except Exception as e:
    log.exception(f"action {kind} failed", e)
    return False, f"{type(e).__name__}: {e}", None
