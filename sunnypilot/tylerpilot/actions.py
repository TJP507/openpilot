"""
Remote actions for tylerpilotd.

Handlers return (ok, result, artifact) — and, for actions that must happen only
after the server has been told (reboot/poweroff), a fourth element: a deferred
callable the agent runs once the job result is posted. `run()` normalizes every
handler to that four-tuple. Handlers are defensive: a failure returns a message,
never raises out of the loop.
"""
from __future__ import annotations

import base64
import glob
import io
import json
import os
import subprocess
import tarfile
import time

from openpilot.common.params import Params
from openpilot.system.hardware import HARDWARE

from openpilot.sunnypilot.tylerpilot import config, log, toast

CHANNELS = ("dev-c3x", "staging-c3x", "release-c3x")
REPO = "https://github.com/TJP507/openpilot.git"

ONROAD_MSG = "Device is driving — try again when parked"


def _run(args, timeout=60, check=False) -> tuple[int, str]:
  try:
    p = subprocess.run(args, capture_output=True, timeout=timeout, text=True)
    return p.returncode, (p.stdout or "") + (p.stderr or "")
  except Exception as e:
    return 1, str(e)


def _is_onroad() -> bool:
  """Fail CLOSED: if the onroad state can't be read, assume onroad (refuse)."""
  try:
    return bool(Params().get_bool("IsOnroad"))
  except Exception as e:
    log.warning(f"could not read IsOnroad, assuming onroad: {e}")
    return True


def _json(obj) -> str:
  return json.dumps(obj, separators=(",", ":"))


def _utc_stamp() -> str:
  from datetime import UTC, datetime
  return datetime.now(UTC).strftime("%Y%m%d-%H%M%S")


# --------------------------------------------------------------------------
# power
# --------------------------------------------------------------------------
def reboot(_payload: dict):
  if _is_onroad():
    return False, ONROAD_MSG, None

  def _do() -> None:
    toast.show("TylerPilot: rebooting…")
    time.sleep(1)
    HARDWARE.reboot()

  return True, "Rebooting…", None, _do


def poweroff(_payload: dict):
  if _is_onroad():
    return False, ONROAD_MSG, None

  def _do() -> None:
    toast.show("TylerPilot: powering off…")
    time.sleep(1)
    HARDWARE.shutdown()

  return True, "Powering off…", None, _do


# --------------------------------------------------------------------------
# update / channel switch
# --------------------------------------------------------------------------
def update(payload: dict):
  channel = str(payload.get("channel") or "")
  if channel not in CHANNELS:
    return False, f"unknown channel {channel!r}", None
  if _is_onroad():
    return False, ONROAD_MSG, None
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

  rc, out = _run(["git", "-C", d, "rev-parse", "--short", "HEAD"], timeout=30)
  sha = out.strip() if rc == 0 else ""

  # Keep the boot overlay source in sync so the change survives the reboot.
  finalized = "/data/safe_staging/finalized"
  if os.path.isdir(finalized):
    _run(["rsync", "-a", "--delete", "--exclude=.git", f"{d}/", f"{finalized}/"], timeout=600)

  # A reboot is the only reliable way to run the new code: the launcher is not
  # re-run on a plain manager restart, and Params/processes are read at start-up.
  def _do() -> None:
    toast.show("TylerPilot: rebooting to apply the update…")
    time.sleep(1)
    HARDWARE.reboot()

  where = f"{channel} ({sha})" if sha else channel
  return True, f"Switched to {where}; rebooting…", None, _do


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
# diagnostics (support bundle)
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


def diagnostics(_payload: dict):
  """Support bundle: system state + logs, with every blob run through the
  redactor. Deliberately does NOT include settings, the link state
  (tylerpilot.json), tunnel keys, or the webdashcam config."""
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
    blobs[name] = log.redact_bytes(out.encode("utf-8", "replace"))

  # newest swaglog tail
  try:
    logdir = "/data/log"
    logs = sorted((os.path.join(logdir, f) for f in os.listdir(logdir) if f.startswith("swaglog")),
                  key=os.path.getmtime)
    if logs:
      with open(logs[-1], "rb") as f:
        data = f.read()
      blobs["diag/swaglog_tail.txt"] = log.redact_bytes(data[-200_000:])
  except OSError:
    pass

  # TylerPilot agent log tail
  try:
    with open("/data/community/tylerpilot.log", "rb") as f:
      blobs["diag/tylerpilot.log"] = log.redact_bytes(f.read()[-200_000:])
  except OSError:
    pass

  data = _tar([], blobs)
  return True, f"diagnostic bundle ({len(data)} bytes)", {"kind": "diagnostics", "data": base64.b64encode(data).decode()}


# --------------------------------------------------------------------------
# settings backup / restore (JSON artifacts)
# --------------------------------------------------------------------------
def backup(_payload: dict):
  from openpilot.sunnypilot.tylerpilot import settings_backup
  data = settings_backup.build_backup()
  name = str(config.get("name") or "device")
  label = f"settings-{name}-{_utc_stamp()}.json"
  return True, f"backup ({len(data)} bytes)", {"kind": "backup", "label": label, "data": base64.b64encode(data).decode()}


def restore(payload: dict):
  """Preview (dry_run, the default) or apply a settings backup artifact."""
  from openpilot.sunnypilot.tylerpilot import client, settings_backup
  aid = str(payload.get("artifact_id") or "")
  if not aid:
    return False, "no artifact id", None
  dry_run = payload.get("dry_run", True)
  if not isinstance(dry_run, bool):
    return False, "dry_run must be a boolean", None

  raw = client.download_artifact(config.get("host"), int(config.get("port")), config.get("token"),
                                 config.get("fingerprint"), aid)
  try:
    doc = settings_backup.parse_backup(raw)
  except settings_backup.BackupError as e:
    return False, f"invalid backup: {e}", None

  entries = settings_backup.diff(doc)
  if dry_run:
    preview = {"source": doc["source"], "created_at": doc["created_at"], "entries": entries}
    return True, _json(preview), None

  if _is_onroad():
    return False, ONROAD_MSG, None

  # Snapshot the current settings first — returned as an artifact, never
  # written to the device.
  pre = settings_backup.build_backup()
  artifact = {"kind": "backup", "label": f"pre-restore-{_utc_stamp()}.json",
              "data": base64.b64encode(pre).decode()}
  counts = settings_backup.apply(doc)
  result = dict(counts)
  # Params are read at start-up by many processes; recommend a reboot whenever
  # anything changed rather than tracking which keys live-reload.
  result["reboot_recommended"] = counts["applied"] > 0
  return True, _json(result), artifact


def cleanup_legacy_prerestore() -> int:
  """One-time cleanup of pre-restore tarballs written by the old restore flow."""
  removed = 0
  for path in glob.glob(os.path.join(config.STATE_DIR, "prerestore-*.tgz")):
    try:
      os.remove(path)
      removed += 1
    except OSError:
      pass
  if removed:
    log.info(f"removed {removed} legacy pre-restore snapshot(s)")
  return removed


def cleanup_stale_restart_flag() -> bool:
  """Remove the obsolete restart-manager flag.

  Older firmware dropped a flag the launcher watched to restart the manager;
  a reboot is now used instead, so any file left behind is inert."""
  flag = os.path.join(config.STATE_DIR, "tylerpilot_restart_manager")
  try:
    os.remove(flag)
    log.info("removed stale restart-manager flag")
    return True
  except OSError:
    return False


def cleanup_legacy_tunnel_key() -> int:
  """Delete the legacy reverse-SSH device tunnel key files.

  The device no longer needs its own tunnel key pair: SSH is bridged over the
  WebSocket and authorized by the server's login key. Any files left by an older
  firmware (the tunnel key pair, and the unused known-hosts file) are removed."""
  removed = 0
  for name in ("tylerpilot_tunnel", "tylerpilot_tunnel.pub", "tylerpilot_known_hosts"):
    try:
      os.remove(os.path.join(config.STATE_DIR, name))
      removed += 1
    except OSError:
      pass
  if removed:
    log.info(f"removed {removed} legacy tunnel key file(s)")
  return removed


HANDLERS = {
  "reboot": reboot,
  "poweroff": poweroff,
  "update": update,
  "location": location,
  "trips": trips_action,
  "diagnostics": diagnostics,
  "backup": backup,
  "restore": restore,
}


def run(kind: str, payload: dict):
  """Run a handler and normalize its return to (ok, result, artifact, deferred)."""
  fn = HANDLERS.get(kind)
  if not fn:
    return False, f"unknown action {kind!r}", None, None
  try:
    res = fn(payload or {})
  except Exception as e:
    log.exception(f"action {kind} failed", e)
    return False, f"{type(e).__name__}: {e}", None, None
  if len(res) == 4:
    return res
  ok, result, artifact = res
  return ok, result, artifact, None
