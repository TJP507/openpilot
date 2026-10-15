"""
Presentation helpers for the modem state JSON written by
`system.hardware.tici.modem` to /dev/shm/modem.

Kept free of hardware imports (pyserial/swaglog) so the Cellular settings UI and
its unit tests can format modem state without pulling in the daemon's
dependencies.
"""
from __future__ import annotations

# Human-readable labels for the modem state machine. DIAL_FAILED is the backoff
# state entered after a run of dial failures (see modem.py BACKOFF_SCHEDULE).
STATE_LABELS = {
  "INITIALIZING": "Initializing",
  "SEARCHING": "Searching",
  "CONNECTING": "Connecting",
  "CONNECTED": "Connected",
  "DIAL_FAILED": "Dial failed",
  "DISCONNECTING": "Disconnecting",
}


def state_label(state: object) -> str:
  """Short label for a modem state value."""
  if not isinstance(state, str) or not state:
    return "N/A"
  return STATE_LABELS.get(state, state.replace("_", " ").title())


def error_text(modem: dict) -> str:
  """The last recorded failure reason, or "" when there is none."""
  err = modem.get("last_error")
  return err if isinstance(err, str) else ""


def retry_text(modem: dict) -> str:
  """Countdown text while a failed dial is backing off, else ""."""
  if modem.get("state") != "DIAL_FAILED":
    return ""
  retry_in = modem.get("retry_in")
  if not isinstance(retry_in, int) or isinstance(retry_in, bool):
    return ""
  return f"in {retry_in} s" if retry_in > 0 else "now"


def status_detail(modem: dict) -> str:
  """A one-line explanation for a failed dial, e.g.
  "Dial failed — modem hung up after connecting (3/3). Retrying in 30 s." """
  if modem.get("state") != "DIAL_FAILED":
    return ""
  reason = error_text(modem) or "dial failed"
  fails = modem.get("fail_count")
  total = modem.get("max_fails")
  count = ""
  if isinstance(fails, int) and isinstance(total, int) and not isinstance(fails, bool) and total > 0:
    count = f" ({fails}/{total})"
  retry = retry_text(modem)
  tail = f" Retrying {retry}." if retry else ""
  return f"Dial failed — {reason}{count}.{tail}"
