"""
Copyright (c) 2021-, Haibin Wen, sunnypilot, and a number of other contributors.

This file is part of sunnypilot and is licensed under the MIT License.
See the LICENSE.md file in the root directory for more details.

Developer submenu: live gauges.

Renders whatever the cangauges publisher is currently emitting (built-in
openpilot state and/or arbitrary decoded CAN signals). The gauge set is edited
from the web UI, which writes the same config file.
"""
from __future__ import annotations

import os
import math

import pyray as rl

from openpilot.selfdrive.ui.ui_state import device
from openpilot.sunnypilot.cangauges import config as gauge_config
from openpilot.system.ui.lib.application import gui_app, FontWeight
from openpilot.system.ui.lib.multilang import tr
from openpilot.system.ui.lib.text_measure import measure_text_cached
from openpilot.system.ui.widgets.button import Button
from openpilot.system.ui.widgets.nav_widget import NavWidget

TEXT_COLOR = rl.Color(255, 255, 255, 255)
SUBTEXT_COLOR = rl.Color(170, 170, 170, 255)
GOOD_COLOR = rl.Color(140, 220, 140, 255)
WARN_COLOR = rl.Color(255, 180, 120, 255)
TRACK_COLOR = rl.Color(70, 70, 70, 255)
FILL_COLOR = rl.Color(74, 144, 217, 255)
COLS = 3

_ACTIVE_PANEL = None
_TIMEOUT_CB_REGISTERED = False


def _dismiss_active_panel() -> None:
  panel = _ACTIVE_PANEL
  if panel is None:
    return
  for _ in range(4):
    top = gui_app.get_active_widget()
    if top is None or top is panel:
      break
    gui_app.pop_widget()
  if gui_app.get_active_widget() is panel:
    gui_app.pop_widget()


def _fmt(value) -> str:
  if value is None:
    return "--"
  if abs(value) >= 1000:
    return f"{value:,.0f}"
  if abs(value) >= 100:
    return f"{value:.0f}"
  return f"{value:.1f}"


class CanGaugesPanel(NavWidget):
  """Live gauge tiles sourced from the cangauges publisher snapshot."""

  def __init__(self):
    super().__init__()
    self._font = gui_app.font(FontWeight.BOLD)
    self._small = gui_app.font(FontWeight.NORMAL)
    self._btn_back = self._child(Button(tr("Back"), lambda: self.dismiss(), font_size=40))
    self._snapshot: dict = {}
    self._snapshot_mtime = -1.0

    global _TIMEOUT_CB_REGISTERED
    if not _TIMEOUT_CB_REGISTERED:
      device.add_interactive_timeout_callback(_dismiss_active_panel)
      _TIMEOUT_CB_REGISTERED = True

  def _back_enabled(self) -> bool:
    return False

  def show_event(self) -> None:
    super().show_event()
    global _ACTIVE_PANEL
    _ACTIVE_PANEL = self

  def hide_event(self) -> None:
    super().hide_event()
    global _ACTIVE_PANEL
    if _ACTIVE_PANEL is self:
      _ACTIVE_PANEL = None

  def _update_state(self) -> None:
    super()._update_state()
    try:
      mtime = os.path.getmtime(gauge_config.VALUES_PATH)
    except OSError:
      mtime = -1.0
    if mtime != self._snapshot_mtime:
      self._snapshot = gauge_config.read_values()
      self._snapshot_mtime = mtime

  def _render(self, rect: rl.Rectangle) -> None:
    self._btn_back.render(rl.Rectangle(rect.x, rect.y, 200, 84))
    rl.draw_text_ex(self._font, tr("Live Gauges"), rl.Vector2(rect.x + 240, rect.y + 8), 56, 0, TEXT_COLOR)

    gauges = self._snapshot.get("gauges", []) if isinstance(self._snapshot, dict) else []
    if not gauges:
      self._draw_center(rect, tr("No gauges configured"))
      return

    grid = rl.Rectangle(rect.x, rect.y + 120, rect.width, rect.height - 120)
    rows = max(1, math.ceil(len(gauges) / COLS))
    rows = min(rows, 4)
    pad = 22
    tile_w = (grid.width - pad * (COLS + 1)) / COLS
    tile_h = (grid.height - pad * (rows + 1)) / rows

    for i, gauge in enumerate(gauges[:COLS * rows]):
      col, row = i % COLS, i // COLS
      tile = rl.Rectangle(grid.x + pad + col * (tile_w + pad), grid.y + pad + row * (tile_h + pad), tile_w, tile_h)
      self._draw_tile(tile, gauge)

  def _draw_tile(self, rect: rl.Rectangle, gauge: dict) -> None:
    ok = bool(gauge.get("ok"))
    value = gauge.get("value")
    text = gauge.get("text")
    bg = rl.Color(45, 45, 45, 255) if ok else rl.Color(34, 34, 34, 255)
    rl.draw_rectangle_rounded(rect, 0.08, 8, bg)
    rl.draw_rectangle_rounded_lines_ex(rect, 0.08, 8, 2, rl.Color(90, 90, 90, 120) if ok else rl.Color(70, 70, 70, 120))

    rl.draw_text_ex(self._small, str(gauge.get("label", "")), rl.Vector2(rect.x + 26, rect.y + 18), 34, 0, SUBTEXT_COLOR)

    value_str = text if text is not None else _fmt(value)
    color = TEXT_COLOR if ok else rl.Color(140, 140, 140, 255)
    value_pos = rl.Vector2(rect.x + 26, rect.y + 60)
    rl.draw_text_ex(self._font, value_str, value_pos, 62, 0, color)
    unit = str(gauge.get("unit") or "")
    if unit:
      width = measure_text_cached(self._font, value_str, 62).x
      rl.draw_text_ex(self._small, unit, rl.Vector2(value_pos.x + width + 10, value_pos.y + 26), 34, 0, SUBTEXT_COLOR)

    if gauge.get("style") == "value":
      return

    frac = 0.0
    if value is not None:
      lo, hi = float(gauge.get("min", 0.0)), float(gauge.get("max", 1.0))
      if hi > lo:
        frac = max(0.0, min(1.0, (float(value) - lo) / (hi - lo)))

    bar = rl.Rectangle(rect.x + 26, rect.y + rect.height - 54, rect.width - 52, 22)
    rl.draw_rectangle_rounded(bar, 0.5, 8, TRACK_COLOR)
    color = FILL_COLOR if ok else rl.Color(90, 90, 90, 255)
    if frac > 0:
      rl.draw_rectangle_rounded(rl.Rectangle(bar.x, bar.y, bar.width * frac, bar.height), 0.5, 8, color)

  def _draw_center(self, rect: rl.Rectangle, text: str) -> None:
    size = measure_text_cached(self._font, text, 46)
    pos = rl.Vector2(rect.x + (rect.width - size.x) / 2, rect.y + (rect.height - size.y) / 2)
    rl.draw_text_ex(self._font, text, pos, 46, 0, WARN_COLOR)

  def __del__(self):
    pass
