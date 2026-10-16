#!/usr/bin/env python3
import os
import time
import traceback

import pyray as rl

from cereal import messaging
from openpilot.system.hardware import TICI
from openpilot.common.realtime import Priority, config_realtime_process, set_core_affinity
from openpilot.system.ui.lib.application import gui_app
try:
  from openpilot.sunnypilot.tylerpilot import toast as _tp_toast
except Exception:
  _tp_toast = None
def _ui_fatal() -> None:
  # TEMP diagnostic: if the UI fails to start, the screen would otherwise just
  # stay on the boot logo (the UI is what draws). Surface the traceback on screen.
  txt = traceback.format_exc()
  print(txt, flush=True)
  try:
    with open("/data/ui_startup_error.txt", "w") as f:
      f.write(txt)
  except OSError:
    pass
  try:
    if not rl.is_window_ready():
      rl.init_window(2160, 1080, "ui error")
    while not rl.window_should_close():
      rl.begin_drawing()
      rl.clear_background(rl.BLACK)
      y = 20
      for line in txt.splitlines()[:45]:
        rl.draw_text(line[:150], 20, y, 24, rl.RED)
        y += 32
      rl.end_drawing()
    rl.close_window()
  except Exception:
    pass


try:
  from openpilot.selfdrive.ui.layouts.main import MainLayout
  from openpilot.selfdrive.ui.mici.layouts.main import MiciMainLayout
  from openpilot.selfdrive.ui.ui_state import ui_state
except Exception:
  _ui_fatal()
  raise

BIG_UI = gui_app.big_ui()


def _draw_tylerpilot_toast():
  """Small overlay shown when TylerPilot runs a remote action."""
  if _tp_toast is None:
    return
  try:
    text = _tp_toast.current()
  except Exception:
    text = None
  if not text:
    return
  font_size = 42
  pad = 22
  w = rl.measure_text(text, font_size) + pad * 2
  h = font_size + pad
  x = (gui_app.width - w) / 2
  y = 44
  rect = rl.Rectangle(x, y, w, h)
  rl.draw_rectangle_rounded(rect, 0.3, 8, rl.Color(20, 22, 28, 235))
  rl.draw_rectangle_rounded_lines(rect, 0.3, 8, rl.Color(76, 141, 255, 255))
  rl.draw_text(text, int(x + pad), int(y + pad / 2) - 2, font_size, rl.WHITE)


def main():
  try:
    cores = {5, }
    # above plannerd and radard
    config_realtime_process(0, Priority.CTRL_HIGH)

    gui_app.init_window("UI")
    if BIG_UI:
      MainLayout()
    else:
      MiciMainLayout()

    pm = messaging.PubMaster(['uiDebug'])
    for should_render, frame_time, cpu_time in gui_app.render():
      extra_start = time.monotonic()
      ui_state.update()

      if should_render:
        # reaffine after power save offlines our core
        if TICI and os.sched_getaffinity(0) != cores:
          try:
            set_core_affinity(list(cores))
          except OSError:
            pass

        extra_cpu = time.monotonic() - extra_start
        msg = messaging.new_message('uiDebug')
        msg.uiDebug.cpuTimeMillis = (cpu_time + extra_cpu) * 1000
        msg.uiDebug.frameTimeMillis = frame_time * 1000
        pm.send('uiDebug', msg)

        _draw_tylerpilot_toast()
  except Exception:
    _ui_fatal()
    raise


if __name__ == "__main__":
  main()
