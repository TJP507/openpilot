"""
Copyright (c) 2021-, Haibin Wen, sunnypilot, and a number of other contributors.

This file is part of sunnypilot and is licensed under the MIT License.
See the LICENSE.md file in the root directory for more details.

Compact live-gauge overlay drawn over the onroad screen.

Reads the same snapshot as the Developer panel (published by
sunnypilot.cangauges.publisher) and shows the first few gauges as a small strip,
only when the user has enabled "show onroad" in the gauge config.
"""
from __future__ import annotations

import os
import time

import pyray as rl

from openpilot.sunnypilot.cangauges import config as gauge_config
from openpilot.system.ui.lib.application import gui_app, FontWeight
from openpilot.system.ui.lib.text_measure import measure_text_cached

MAX_ONROAD = 5
TILE_W = 250
TILE_H = 110
GAP = 12
MARGIN = 30

_STATE = {"mtime": -1.0, "snap": {}, "cfg": None, "cfg_at": -10.0}
_font = None
_small = None


def _ensure_fonts():
  global _font, _small
  if _font is None:
    _font = gui_app.font(FontWeight.BOLD)
    _small = gui_app.font(FontWeight.NORMAL)


def _snapshot() -> dict:
  try:
    mtime = os.path.getmtime(gauge_config.VALUES_PATH)
  except OSError:
    mtime = -1.0
  if mtime != _STATE["mtime"]:
    _STATE["snap"] = gauge_config.read_values()
    _STATE["mtime"] = mtime
  return _STATE["snap"]


def _show_onroad() -> bool:
  now = time.monotonic()
  if now - _STATE["cfg_at"] > 2.0:
    _STATE["cfg"] = gauge_config.load()
    _STATE["cfg_at"] = now
  return bool(_STATE["cfg"] and _STATE["cfg"].get("show_onroad"))


def _fmt(value) -> str:
  if value is None:
    return "--"
  if abs(value) >= 1000:
    return f"{value:,.0f}"
  if abs(value) >= 100:
    return f"{value:.0f}"
  return f"{value:.1f}"


def draw(rect: rl.Rectangle) -> None:
  if not _show_onroad():
    return
  gauges = _snapshot().get("gauges", [])
  if not gauges:
    return

  _ensure_fonts()
  shown = gauges[:MAX_ONROAD]
  y = rect.y + rect.height - TILE_H - MARGIN
  x = rect.x + MARGIN
  for gauge in shown:
    box = rl.Rectangle(x, y, TILE_W, TILE_H)
    rl.draw_rectangle_rounded(box, 0.16, 8, rl.Color(0, 0, 0, 160))
    rl.draw_text_ex(_small, str(gauge.get("label", "")), rl.Vector2(x + 16, y + 12), 28, 0, rl.Color(200, 200, 200, 255))

    value = gauge.get("text")
    if value is None:
      value = _fmt(gauge.get("value"))
    color = rl.WHITE if gauge.get("ok") else rl.Color(150, 150, 150, 255)
    rl.draw_text_ex(_font, str(value), rl.Vector2(x + 16, y + 44), 48, 0, color)

    unit = str(gauge.get("unit") or "")
    if unit:
      width = measure_text_cached(_font, str(value), 48).x
      rl.draw_text_ex(_small, unit, rl.Vector2(x + 22 + width, y + 60), 28, 0, rl.Color(180, 180, 180, 255))

    if gauge.get("style") != "value" and gauge.get("value") is not None:
      lo, hi = float(gauge.get("min", 0.0)), float(gauge.get("max", 1.0))
      frac = max(0.0, min(1.0, (float(gauge["value"]) - lo) / (hi - lo))) if hi > lo else 0.0
      track = rl.Rectangle(x + 16, y + TILE_H - 20, TILE_W - 32, 8)
      rl.draw_rectangle_rounded(track, 0.5, 6, rl.Color(70, 70, 70, 220))
      if frac > 0:
        rl.draw_rectangle_rounded(rl.Rectangle(track.x, track.y, track.width * frac, track.height), 0.5, 6, rl.Color(74, 144, 217, 230))

    x += TILE_W + GAP
