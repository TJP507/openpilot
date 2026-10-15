"""
TylerPilot Cloud settings panel.

Link this comma 3X to the central TylerPilot server: enter a 12-digit pairing
code, see link status, and unlink. The background agent
(sunnypilot/tylerpilot/agent.py) does the actual heartbeats and tunnels; this
panel only writes the link state via sunnypilot/tylerpilot/config.py.
"""
from __future__ import annotations

import socket
import threading

import pyray as rl

from openpilot.selfdrive.ui.ui_state import device, ui_state
from openpilot.system.hardware import HARDWARE
from openpilot.system.ui.lib.application import gui_app, FontWeight
from openpilot.system.ui.lib.multilang import tr
from openpilot.system.ui.widgets import DialogResult
from openpilot.system.ui.widgets.button import Button
from openpilot.system.ui.widgets.confirm_dialog import ConfirmDialog
from openpilot.system.ui.widgets.list_view import text_item
from openpilot.system.ui.widgets.nav_widget import NavWidget
from openpilot.system.ui.widgets.scroller_tici import Scroller
from openpilot.system.ui.sunnypilot.widgets.input_dialog import InputDialogSP
from openpilot.system.ui.sunnypilot.widgets.list_view import button_item_sp
from openpilot.system.version import get_version

from openpilot.sunnypilot.tylerpilot import config as tp

TEXT_COLOR = rl.Color(255, 255, 255, 255)

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


def _device_name() -> str:
  try:
    return socket.gethostname()
  except Exception:
    return "comma"


def _device_uid() -> str:
  try:
    return HARDWARE.get_serial()
  except Exception:
    return _device_name()


def _dongle_id() -> str:
  try:
    return ui_state.params.get("DongleId") or ""
  except Exception:
    return ""


class TylerPilotPanel(NavWidget):
  """Link/unlink this device to the TylerPilot server."""

  def __init__(self):
    super().__init__()
    self._font = gui_app.font(FontWeight.MEDIUM)
    self._btn_back = self._child(Button(tr("Back"), lambda: self.dismiss(), font_size=40))

    self._status = text_item(lambda: tr("Status"), lambda: self._status_text())
    self._server = text_item(lambda: tr("Server"), lambda: self._server_text())
    self._link = button_item_sp(
      lambda: tr("Link Device"),
      lambda: tr("LINK"),
      lambda: tr("Enter the pairing code from the TylerPilot web app, e.g. XXXX-XXXX-XXXX. The code is valid for 10 minutes."),
      callback=self._on_link,
    )
    self._unlink = button_item_sp(
      lambda: tr("Unlink Device"),
      lambda: tr("UNLINK"),
      lambda: tr("Remove this device from the server. You will need a new pairing code to link again."),
      callback=self._on_unlink,
    )
    self._scroller = Scroller([self._status, self._server, self._link, self._unlink],
                              spacing=0, line_separator=True, pad_end=True)

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
    self._scroller.show_event()

  def hide_event(self) -> None:
    super().hide_event()
    global _ACTIVE_PANEL
    if _ACTIVE_PANEL is self:
      _ACTIVE_PANEL = None

  def _update_state(self) -> None:
    super()._update_state()
    linked = tp.is_linked()
    self._link.set_visible(not linked)
    self._unlink.set_visible(linked)

  @staticmethod
  def _status_text() -> str:
    if tp.is_revoked():
      return tr("Disconnected from TylerPilot Cloud — enter a new code to re-link")
    if not tp.is_linked():
      return tr("Not linked")
    err = tp.get("last_error")
    base = tr("Linked as {name}").format(name=tp.get("name") or _device_name())
    return base + (f"\n{tr('Error')}: {err}" if err else "")

  @staticmethod
  def _server_text() -> str:
    return f"{tp.get('host')}:{tp.get('port')}"

  def _on_link(self) -> None:
    def _cb(result: int, text: str):
      if result != DialogResult.CONFIRM:
        return
      from openpilot.sunnypilot.tylerpilot import client
      code = client.normalize_pairing_code(text)
      if not code:
        tp.set_error(tr("Pairing code must be 12 digits"))
        return
      threading.Thread(target=self._do_link, args=(code,), daemon=True).start()

    InputDialogSP(tr("Pairing Code"), tr("Enter the code from the web app (XXXX-XXXX-XXXX)"),
                  callback=_cb, min_text_size=12).show()

  @staticmethod
  def _do_link(code: str) -> None:
    from openpilot.sunnypilot.tylerpilot import client
    host, port = tp.get("host"), int(tp.get("port"))
    try:
      pubkey = client.rotate_tunnel_key()
      result = client.register(host, port, code, _device_name(), _device_uid(),
                               get_version(), _dongle_id(), pubkey)
      srv_key = result.get("ssh_pubkey", "")
      client.install_server_key(srv_key)
      tp.set_link(result["device_id"], result["token"], result["fingerprint"],
                  result.get("server_name", ""), _device_name(), srv_key)
    except Exception as e:
      tp.set_error(str(e))

  @staticmethod
  def _on_unlink() -> None:
    def _do(result: int):
      if result == DialogResult.CONFIRM:
        from openpilot.sunnypilot.tylerpilot import client
        client.remove_server_key(tp.get("server_ssh_key"))
        tp.clear_link()

    gui_app.push_widget(ConfirmDialog(
      tr("Unlink this device from the TylerPilot server?"), tr("Unlink"), callback=_do))

  def _render(self, rect: rl.Rectangle) -> None:
    self._btn_back.render(rl.Rectangle(rect.x, rect.y, 200, 84))
    rl.draw_text_ex(self._font, tr("TylerPilot Cloud"), rl.Vector2(rect.x + 240, rect.y + 8), 56, 0, TEXT_COLOR)
    list_rect = rl.Rectangle(rect.x, rect.y + 150, rect.width, max(rect.height - 150, 0))
    self._scroller.render(list_rect)
