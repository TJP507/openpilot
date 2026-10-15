"""
Tests for the dash cam's shared UTC time formatting.

Every dash cam time is UTC, 24-hour, and labeled, so these lock the exact
strings the on-device panel and the web UI render.
"""
from __future__ import annotations

import time

from openpilot.sunnypilot.webdashcam import timeutil

# 2020-01-01T00:00:00Z, the boundary between a real recording time and the
# unknown-date group.
EPOCH_2020 = 1577836800.0
# 2023-11-14T22:13:20Z.
SAMPLE = 1700000000.0


def test_is_valid_boundary():
  assert not timeutil.is_valid(EPOCH_2020 - 1)
  assert timeutil.is_valid(EPOCH_2020)
  assert not timeutil.is_valid(0.0)


def test_date_text_is_utc():
  assert timeutil.date_text(EPOCH_2020) == "2020-01-01"
  assert timeutil.date_text(SAMPLE) == "2023-11-14"


def test_time_text_is_utc_24h():
  assert timeutil.time_text(EPOCH_2020) == "00:00:00"
  assert timeutil.time_text(SAMPLE) == "22:13:20"


def test_time_text_utc_labels_zone():
  assert timeutil.time_text_utc(SAMPLE) == "22:13:20 UTC"


def test_datetime_text():
  assert timeutil.datetime_text(SAMPLE) == "2023-11-14 22:13:20 UTC"


def test_date_label_maps_unknown():
  assert timeutil.date_label(timeutil.UNKNOWN_DATE) == "Unknown date"
  assert timeutil.date_label("2026-10-14") == "2026-10-14"


def test_dos_datetime_uses_utc():
  gm = time.gmtime(SAMPLE)
  want_time = (gm.tm_hour << 11) | (gm.tm_min << 5) | (gm.tm_sec // 2)
  want_date = ((gm.tm_year - 1980) << 9) | (gm.tm_mon << 5) | gm.tm_mday
  assert timeutil.dos_datetime(SAMPLE) == (want_time, want_date)


def test_dos_datetime_pre_1980_clamps_year():
  _, dos_date = timeutil.dos_datetime(0.0)
  assert (dos_date >> 9) == 0
