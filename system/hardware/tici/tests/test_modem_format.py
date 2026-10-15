"""Unit tests for the modem state presentation helpers used by the UI."""
from __future__ import annotations

from openpilot.system.hardware.tici import modem_format as f


def test_state_label():
  assert f.state_label("CONNECTED") == "Connected"
  assert f.state_label("DIAL_FAILED") == "Dial failed"
  assert f.state_label("CONNECTING") == "Connecting"
  assert f.state_label("SOME_NEW_STATE") == "Some New State"
  assert f.state_label("") == "N/A"
  assert f.state_label(None) == "N/A"


def test_error_text():
  assert f.error_text({"last_error": "no carrier"}) == "no carrier"
  assert f.error_text({}) == ""
  assert f.error_text({"last_error": 5}) == ""


def test_retry_text():
  assert f.retry_text({"state": "DIAL_FAILED", "retry_in": 30}) == "in 30 s"
  assert f.retry_text({"state": "DIAL_FAILED", "retry_in": 0}) == "now"
  assert f.retry_text({"state": "DIAL_FAILED", "retry_in": "x"}) == ""
  assert f.retry_text({"state": "CONNECTED", "retry_in": 30}) == ""


def test_status_detail():
  modem = {
    "state": "DIAL_FAILED",
    "last_error": "modem hung up after connecting (pppd exit 16)",
    "fail_count": 3,
    "max_fails": 3,
    "retry_in": 30,
  }
  assert f.status_detail(modem) == (
    "Dial failed — modem hung up after connecting (pppd exit 16) (3/3). Retrying in 30 s."
  )


def test_status_detail_without_count_or_retry():
  assert f.status_detail({"state": "DIAL_FAILED"}) == "Dial failed — dial failed."


def test_status_detail_is_empty_when_not_failed():
  assert f.status_detail({"state": "CONNECTED"}) == ""
  assert f.status_detail({}) == ""
