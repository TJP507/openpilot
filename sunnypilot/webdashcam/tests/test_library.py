"""
Tests for the dash cam filesystem grouping logic: UTC day buckets plus the
"unknown date" group for segments recorded before the clock was set.
"""
from __future__ import annotations

from openpilot.sunnypilot.webdashcam import timeutil
from openpilot.sunnypilot.webdashcam.library import Clip, date_label, date_of, group_dates, sorted_date_groups

# 2026-10-14T19:42:10Z and 2026-10-13T08:00:00Z.
DAY_A = 1792006930.0
DAY_B = 1791878400.0
# Before 2020-01-01: the clock had not synced yet.
UNSYNCED = 1000000000.0


def _seg(name: str, mtime: float) -> tuple:
  return (name, "/data/media/0/realdata/" + name, mtime)


def test_date_of_utc_day():
  assert date_of(DAY_A) == "2026-10-14"
  assert date_of(DAY_B) == "2026-10-13"


def test_date_of_unknown_for_unsynced_clock():
  assert date_of(UNSYNCED) == timeutil.UNKNOWN_DATE


def test_group_dates_counts_and_buckets():
  segments = [_seg("a--1", DAY_A), _seg("a--2", DAY_A), _seg("b--1", DAY_B), _seg("c--1", UNSYNCED)]
  assert group_dates(segments) == {"2026-10-14": 2, "2026-10-13": 1, timeutil.UNKNOWN_DATE: 1}


def test_sorted_date_groups_newest_first_unknown_last():
  counts = {"2026-10-13": 1, timeutil.UNKNOWN_DATE: 4, "2026-10-14": 2}
  assert sorted_date_groups(counts) == ["2026-10-14", "2026-10-13", timeutil.UNKNOWN_DATE]


def test_sorted_date_groups_without_unknown():
  assert sorted_date_groups({"2026-10-13": 1, "2026-10-14": 2}) == ["2026-10-14", "2026-10-13"]


def test_clip_text_is_utc():
  clip = Clip(path="/x/fcamera.hevc", name="a--1", segment=1, mtime=DAY_A)
  assert clip.date_text == "2026-10-14"
  assert clip.time_text == "19:42:10"


def test_clip_text_unknown_date():
  clip = Clip(path="/x/fcamera.hevc", name="a--1", segment=1, mtime=UNSYNCED)
  assert clip.date_text == "Unknown date"
  assert date_label(date_of(clip.mtime)) == "Unknown date"
