"""
Copyright (c) 2021-, Haibin Wen, sunnypilot, and a number of other contributors.

This file is part of sunnypilot and is licensed under the MIT License.
See the LICENSE.md file in the root directory for more details.

Developer submenu: fault codes.

Read-only view of the fault state the faultcodes publisher is emitting: the
fault flags openpilot already parses from the car, the panda's own faults, the
device thermal status and recent fault events. Nothing here queries the car.
"""
from __future__ import annotations

import os

import pyray as rl

from openpilot.selfdrive.ui.ui_state import device
from openpilot.sunnypilot.faultcodes import config as fc_config
from openpilot.system.ui.lib.application import gui_app, FontWeight
from openpilot.system.ui.lib.multilang import tr
from openpilot.system.ui.lib.text_measure import measure_text_cached
from openpilot.system.ui.widgets.button import Button
from openpilot.system.ui.widgets.nav_widget import NavWidget

TEXT_COLOR = rl.Color(255, 255, 255, 255)
SUBTEXT_COLOR = rl.Color(170, 170, 170, 255)
GOOD_COLOR = rl.Color(140, 220, 140, 255)
WARN_COLOR = rl.Color(255, 180, 120, 255)
FAULT_COLOR = rl.Color(235, 100, 90, 255)
MAX_FAULTS = 5
MAX_EVENTS = 4

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


def _age_text(seconds: float) -> str:
  if seconds < 90:
    return tr("{n}s ago").format(n=int(seconds))
  if seconds < 3600:
    return tr("{n}m ago").format(n=int(seconds // 60))
  return tr("{n}h ago").format(n=int(seconds // 3600))


class FaultCodesPanel(NavWidget):
  """Read-only fault list sourced from the faultcodes publisher snapshot."""

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
      mtime = os.path.getmtime(fc_config.VALUES_PATH)
    except OSError:
      mtime = -1.0
    if mtime != self._snapshot_mtime:
      self._snapshot = fc_config.read_snapshot()
      self._snapshot_mtime = mtime

  def _render(self, rect: rl.Rectangle) -> None:
    self._btn_back.render(rl.Rectangle(rect.x, rect.y, 200, 84))
    rl.draw_text_ex(self._font, tr("Fault Codes"), rl.Vector2(rect.x + 240, rect.y + 8), 56, 0, TEXT_COLOR)

    x = rect.x + 40
    width = rect.width - 80
    y = rect.y + 130

    if not self._snapshot:
      self._center(rect, tr("Waiting for data..."), WARN_COLOR)
      return

    vehicle = [item for item in self._snapshot.get("vehicle", []) if item.get("active")]
    if not vehicle:
      rl.draw_text_ex(self._font, tr("No active faults"), rl.Vector2(x, y), 52, 0, GOOD_COLOR)
      y += 90
    else:
      y = self._section(x, y, tr("Active faults ({n})").format(n=len(vehicle)), FAULT_COLOR)
      for item in vehicle[:MAX_FAULTS]:
        y = self._row(x, width, y, item.get("label", ""), item.get("detail", ""), FAULT_COLOR)
      if len(vehicle) > MAX_FAULTS:
        y = self._row(x, width, y, tr("+{n} more").format(n=len(vehicle) - MAX_FAULTS), "", SUBTEXT_COLOR)

    y += 16
    y = self._section(x, y, tr("System"), SUBTEXT_COLOR)
    panda = [item for item in self._snapshot.get("panda", []) if item.get("active")]
    if panda:
      for item in panda[:3]:
        y = self._row(x, width, y, item.get("label", ""), "", FAULT_COLOR)
    else:
      y = self._row(x, width, y, tr("No panda faults"), "", GOOD_COLOR)

    thermal = str(self._snapshot.get("thermal", ""))
    if thermal and thermal != "ok":
      y = self._row(x, width, y, tr("Device thermal: {t}").format(t=thermal), "", WARN_COLOR)

    events = self._snapshot.get("events", [])
    if events:
      y += 16
      y = self._section(x, y, tr("Recent events"), SUBTEXT_COLOR)
      for event in events[:MAX_EVENTS]:
        types = ", ".join(event.get("types", []))
        y = self._row(x, width, y, str(event.get("name", "")), types, WARN_COLOR,
                      trailing=_age_text(float(event.get("age", 0.0))))

  def _section(self, x: float, y: float, title: str, color: rl.Color) -> float:
    rl.draw_text_ex(self._small, title, rl.Vector2(x, y), 34, 0, color)
    return y + 52

  def _row(self, x: float, width: float, y: float, label: str, detail: str, color: rl.Color,
           trailing: str = "") -> float:
    rl.draw_rectangle_rounded(rl.Rectangle(x, y, width, 66), 0.06, 6, rl.Color(38, 38, 38, 255))
    rl.draw_rectangle_rounded(rl.Rectangle(x, y, 8, 66), 0.4, 4, color)
    rl.draw_text_ex(self._font, label, rl.Vector2(x + 28, y + 8), 38, 0, TEXT_COLOR)
    if detail:
      rl.draw_text_ex(self._small, detail, rl.Vector2(x + 28, y + 52), 26, 0, SUBTEXT_COLOR)
    if trailing:
      size = measure_text_cached(self._small, trailing, 28)
      rl.draw_text_ex(self._small, trailing, rl.Vector2(x + width - size.x - 24, y + 20), 28, 0, SUBTEXT_COLOR)
    return y + 78

  def _center(self, rect: rl.Rectangle, text: str, color: rl.Color) -> None:
    size = measure_text_cached(self._font, text, 46)
    pos = rl.Vector2(rect.x + (rect.width - size.x) / 2, rect.y + (rect.height - size.y) / 2)
    rl.draw_text_ex(self._font, text, pos, 46, 0, color)

  def __del__(self):
    pass
