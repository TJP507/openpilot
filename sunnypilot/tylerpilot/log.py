"""
TylerPilot on-device log.

A tiny, self-contained, size-capped log so TylerPilot's own messages never grow
without bound on the device. Kept deliberately separate from openpilot's swaglog
so we never touch sunnypilot's logs. When the file reaches MAX_BYTES it is
trimmed down to its most recent half, so total size stays under the cap.
"""
from __future__ import annotations

import os
import threading
import time

from openpilot.system.hardware import PC
from openpilot.system.hardware.hw import Paths

MAX_BYTES = 50 * 1024 * 1024  # 50 MB cap (TylerPilot-only)

DIR = os.path.join(Paths.comma_home(), "community") if PC else "/data/community"
PATH = os.path.join(DIR, "tylerpilot.log")

_LOCK = threading.Lock()


def _trim() -> None:
  """Bound the file to MAX_BYTES by dropping the oldest half, in place."""
  try:
    size = os.path.getsize(PATH)
  except OSError:
    return
  if size <= MAX_BYTES:
    return
  keep = MAX_BYTES // 2
  try:
    with open(PATH, "rb") as f:
      f.seek(size - keep)
      tail = f.read()
    with open(PATH, "wb") as f:
      f.write(b"tylerpilot: log trimmed\n")
      f.write(tail)
  except OSError:
    pass


def _write(level: str, msg: str) -> None:
  line = f"{time.strftime('%Y-%m-%d %H:%M:%S')} {level} {msg}\n"
  try:
    os.makedirs(DIR, exist_ok=True)
    with _LOCK:
      _trim()
      with open(PATH, "a") as f:
        f.write(line)
  except OSError:
    pass


def info(msg: str) -> None:
  _write("INFO", msg)


def warning(msg: str) -> None:
  _write("WARN", msg)


def error(msg: str) -> None:
  _write("ERROR", msg)


def exception(msg: str, exc: BaseException | None = None) -> None:
  _write("ERROR", msg if exc is None else f"{msg}: {exc}")
