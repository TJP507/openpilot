"""
UTC time formatting for the dash cam.

The comma's OS clock is UTC, and every time the dash cam shows is UTC, 24-hour,
and labeled as such, so the on-device panel and the web UI agree with each
other and with the TylerPilot Cloud Recordings screen (which formats the same
epoch-millisecond timestamps in UTC). Centralized here so both front ends format
identically.
"""
from __future__ import annotations

import time

# A segment's mtime is the recording time only once the clock has been set from
# GPS/NTP. Anything before this is treated as an unknown date rather than shown
# as a bogus 1970/2015 day.
MIN_VALID_MTIME = 1577836800.0  # 2020-01-01T00:00:00Z

# Group key for segments recorded before the clock was set.
UNKNOWN_DATE = "unknown"


def is_valid(mtime: float) -> bool:
  """True when mtime is a real recording time (clock was set)."""
  return mtime >= MIN_VALID_MTIME


def date_text(mtime: float) -> str:
  """UTC date as YYYY-MM-DD."""
  return time.strftime("%Y-%m-%d", time.gmtime(mtime))


def today_text() -> str:
  """Today's UTC date as YYYY-MM-DD."""
  return time.strftime("%Y-%m-%d", time.gmtime())


def time_text(mtime: float) -> str:
  """UTC time as HH:MM:SS (24-hour)."""
  return time.strftime("%H:%M:%S", time.gmtime(mtime))


def time_text_utc(mtime: float) -> str:
  """UTC time labeled, e.g. "19:42:10 UTC"."""
  return time_text(mtime) + " UTC"


def datetime_text(mtime: float) -> str:
  """UTC date and time, e.g. "2026-10-14 19:42:10 UTC"."""
  return date_text(mtime) + " " + time_text_utc(mtime)


def date_label(date: str) -> str:
  """Display label for a date group key (maps the unknown sentinel)."""
  return "Unknown date" if date == UNKNOWN_DATE else date


def dos_datetime(mtime: float) -> tuple[int, int]:
  """(dos_time, dos_date) for a ZIP entry, computed in UTC."""
  t = time.gmtime(mtime)
  dos_time = (t.tm_hour << 11) | (t.tm_min << 5) | (t.tm_sec // 2)
  dos_date = (max(t.tm_year - 1980, 0) << 9) | (t.tm_mon << 5) | t.tm_mday
  return dos_time, dos_date
