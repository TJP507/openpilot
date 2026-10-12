from __future__ import annotations

import pytest

from openpilot.sunnypilot.tylerpilot import toast


@pytest.fixture
def toast_file(tmp_path, monkeypatch):
  monkeypatch.setattr(toast, "DIR", str(tmp_path))
  monkeypatch.setattr(toast, "PATH", str(tmp_path / "tylerpilot_toast.json"))
  return tmp_path


def test_show_then_current(toast_file):
  toast.show("hello", ttl=8.0)
  assert toast.current() == "hello"


def test_expired_ttl_returns_none(toast_file):
  toast.show("gone", ttl=-1.0)
  assert toast.current() is None


def test_text_truncated_to_200(toast_file):
  toast.show("x" * 300, ttl=8.0)
  assert toast.current() == "x" * 200


def test_missing_file_returns_none(toast_file):
  assert toast.current() is None


def test_corrupt_file_returns_none(toast_file):
  with open(toast.PATH, "w") as f:
    f.write("not json")
  assert toast.current() is None
