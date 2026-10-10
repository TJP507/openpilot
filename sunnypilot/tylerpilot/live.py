#!/usr/bin/env python3
"""
TylerPilot live camera view.

Reads a comma camera stream (road / wide / driver) from vision IPC, encodes
JPEG frames with Pillow, and writes a multipart/x-mixed-replace (MJPEG) stream to
stdout. The TylerPilot server runs this over the reverse-SSH tunnel and pipes it
straight to the browser, so no extra ports or keys are needed.

Off-road, camerad may not be running; we start it for the duration (the same way
`system/camerad/snapshot.py` does) and stop it again on exit.
"""
from __future__ import annotations

import argparse
import io
import os
import subprocess
import sys
import time

import numpy as np
from PIL import Image

from msgq.visionipc import VisionIpcClient, VisionStreamType
from openpilot.system.hardware import PC

BOUNDARY = "frame"

STREAMS = {
  "road": VisionStreamType.VISION_STREAM_ROAD,
  "wide": VisionStreamType.VISION_STREAM_WIDE_ROAD,
  "driver": VisionStreamType.VISION_STREAM_DRIVER,
}

PARAMS_DIR = "/data/params/d"


def _params_owner():
  """uid/gid that should own the params dir (comma), so root-run cleanups match."""
  for path in (PARAMS_DIR, "/data/params"):
    try:
      st = os.stat(path)
      if st.st_uid != 0:
        return st.st_uid, st.st_gid
    except OSError:
      pass
  return None


def _restore_params_owner(owner):
  """We run as root (camerad needs it); never leave root-owned params behind,
  the manager runs as comma and hard-fails if it can't read /data/params/d."""
  if owner is None or os.geteuid() != 0:
    return
  uid, gid = owner
  try:
    names = os.listdir(PARAMS_DIR)
  except OSError:
    return
  for name in names:
    p = os.path.join(PARAMS_DIR, name)
    try:
      st = os.lstat(p)
      if st.st_uid == 0 or st.st_gid == 0:
        os.chown(p, uid, gid)
    except OSError:
      pass


def yuv_to_rgb(y, u, v):
  ul = np.repeat(np.repeat(u, 2).reshape(u.shape[0], y.shape[1]), 2, axis=0).reshape(y.shape)
  vl = np.repeat(np.repeat(v, 2).reshape(v.shape[0], y.shape[1]), 2, axis=0).reshape(y.shape)
  yuv = np.dstack((y, ul, vl)).astype(np.int16)
  yuv[:, :, 1:] -= 128
  m = np.array([[1.0, 1.0, 1.0], [0.0, -0.39465, 2.03211], [1.13983, -0.58060, 0.0]])
  return np.dot(yuv, m).clip(0, 255).astype(np.uint8)


def extract_image(buf, subsample=2):
  # NV12: Y plane followed by interleaved UV plane.
  uv_height = ((buf.height // 2) + 15) // 16 * 16
  uv_plane_size = buf.stride * uv_height
  y = np.array(buf.data[:buf.uv_offset], dtype=np.uint8).reshape((-1, buf.stride))[:buf.height, :buf.width]
  uv_data = buf.data[buf.uv_offset:buf.uv_offset + uv_plane_size]
  u = np.array(uv_data[::2], dtype=np.uint8).reshape((-1, buf.stride // 2))[:buf.height // 2, :buf.width // 2]
  v = np.array(uv_data[1::2], dtype=np.uint8).reshape((-1, buf.stride // 2))[:buf.height // 2, :buf.width // 2]
  if subsample > 1:
    y = y[::subsample, ::subsample]
    u = u[::subsample, ::subsample]
    v = v[::subsample, ::subsample]
  return yuv_to_rgb(y, u, v)


def _camerad_running() -> bool:
  """True only if a *live* camerad exists (ignore zombies/defunct)."""
  try:
    states = subprocess.check_output(["ps", "-o", "stat=", "-C", "camerad"], stderr=subprocess.DEVNULL).decode()
  except subprocess.CalledProcessError:
    return False
  return any(not s.startswith("Z") for s in states.split())


def main() -> int:
  ap = argparse.ArgumentParser()
  ap.add_argument("--camera", default="road", choices=list(STREAMS))
  ap.add_argument("--width", type=int, default=960)
  ap.add_argument("--quality", type=int, default=70)
  ap.add_argument("--fps", type=float, default=10.0)
  ap.add_argument("--subsample", type=int, default=2)
  args = ap.parse_args()

  owner = _params_owner()

  # Off-road camerad isn't running; start it exactly like
  # system/camerad/snapshot.py does. camerad is noisy on stdout/stderr, which is
  # our MJPEG stream, so we point fd 1/2 at /dev/null only while it starts.
  started_camerad = False
  manager_proc = None
  if not PC and not _camerad_running():
    s1, s2 = os.dup(1), os.dup(2)
    dn = os.open(os.devnull, os.O_WRONLY)
    os.dup2(dn, 1)
    os.dup2(dn, 2)
    try:
      from openpilot.system.manager.process_config import managed_processes
      manager_proc = managed_processes["camerad"]
      manager_proc.start()
      started_camerad = True
      time.sleep(2.5)
    except Exception as e:
      os.dup2(s1, 1)
      os.dup2(s2, 2)
      sys.stderr.write(f"could not start camerad: {e}\n")
    finally:
      os.dup2(s1, 1)
      os.dup2(s2, 2)
      os.close(s1)
      os.close(s2)
      os.close(dn)

  client = VisionIpcClient("camerad", STREAMS[args.camera], True)
  for _ in range(200):
    if client.connect(True):
      break
    time.sleep(0.2)
  else:
    sys.stderr.write("camerad not available\n")
    if started_camerad and manager_proc:
      try:
        manager_proc.stop()
      except Exception:
        pass
    _restore_params_owner(owner)
    return 1

  interval = 1.0 / max(args.fps, 0.5)
  out = sys.stdout.buffer
  try:
    while True:
      t0 = time.monotonic()
      try:
        buf = client.recv(1000)
      except Exception:
        continue
      if buf is None:
        continue
      rgb = extract_image(buf, max(1, args.subsample))
      img = Image.fromarray(rgb)
      if args.width and img.width > args.width:
        img = img.resize((args.width, int(img.height * args.width / img.width)))
      bio = io.BytesIO()
      img.save(bio, "JPEG", quality=args.quality)
      jpg = bio.getvalue()
      out.write(f"--{BOUNDARY}\r\n".encode())
      out.write(b"Content-Type: image/jpeg\r\n")
      out.write(f"Content-Length: {len(jpg)}\r\n\r\n".encode())
      out.write(jpg)
      out.write(b"\r\n")
      out.flush()
      dt = time.monotonic() - t0
      if dt < interval:
        time.sleep(interval - dt)
  except (BrokenPipeError, KeyboardInterrupt):
    pass
  finally:
    try:
      client.disconnect()
    except Exception:
      pass
    if started_camerad and manager_proc:
      try:
        manager_proc.stop()
      except Exception:
        pass
    _restore_params_owner(owner)
  return 0


if __name__ == "__main__":
  os.environ.setdefault("ZMQ", "1")
  sys.exit(main())
