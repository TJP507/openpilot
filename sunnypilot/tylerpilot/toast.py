"""
Tiny on-device toast for TylerPilot.

Writes a short message + timestamp to a file the UI reads (see the mici home
overlay). Kept as a file, not a Params key, because this branch ships no build.
"""
from __future__ import annotations

import json
import os
import time

from openpilot.system.hardware import PC
from openpilot.system.hardware.hw import Paths

DIR = os.path.join(Paths.comma_home(), "community") if PC else "/data/community"
PATH = os.path.join(DIR, "tylerpilot_toast.json")


def show(text: str, ttl: float = 8.0) -> None:
  try:
    os.makedirs(DIR, exist_ok=True)
    # Wall-clock (not monotonic): the timestamp is persisted to disk and
    # compared by a separate process (the UI).
    with open(PATH, "w") as f:
      json.dump({"text": text[:200], "until": time.time() + ttl}, f)  # noqa: TID251
  except OSError:
    pass


def current() -> str | None:
  """Return the active toast text, or None."""
  try:
    with open(PATH) as f:
      d = json.load(f)
    if float(d.get("until", 0)) > time.time():  # noqa: TID251
      return str(d.get("text", ""))
  except (OSError, ValueError):
    pass
  return None
