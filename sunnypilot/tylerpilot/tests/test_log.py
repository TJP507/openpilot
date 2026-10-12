from __future__ import annotations

import os

import pytest

from openpilot.sunnypilot.tylerpilot import log


@pytest.fixture
def log_file(tmp_path, monkeypatch):
  monkeypatch.setattr(log, "DIR", str(tmp_path))
  monkeypatch.setattr(log, "PATH", str(tmp_path / "tylerpilot.log"))
  return tmp_path


def test_levels_written(log_file):
  log.info("i")
  log.warning("w")
  log.error("e")
  log.exception("boom", ValueError("bad"))
  with open(log.PATH) as f:
    text = f.read()
  assert " INFO i" in text
  assert " WARN w" in text
  assert " ERROR e" in text
  assert " ERROR boom: bad" in text


def test_exception_without_exc(log_file):
  log.exception("just a message")
  with open(log.PATH) as f:
    assert " ERROR just a message" in f.read()


def test_trim_caps_file(tmp_path, monkeypatch):
  path = str(tmp_path / "tylerpilot.log")
  monkeypatch.setattr(log, "PATH", path)
  monkeypatch.setattr(log, "MAX_BYTES", 100)
  with open(path, "wb") as f:
    f.write(b"Z" * 500)
  log._trim()
  with open(path, "rb") as f:
    data = f.read()
  assert data.startswith(b"tylerpilot: log trimmed\n")
  assert len(data) < 500


def test_trim_noop_below_cap(tmp_path, monkeypatch):
  path = str(tmp_path / "tylerpilot.log")
  monkeypatch.setattr(log, "PATH", path)
  monkeypatch.setattr(log, "MAX_BYTES", 1000)
  with open(path, "wb") as f:
    f.write(b"small")
  log._trim()
  assert os.path.getsize(path) == 5


def test_trim_missing_file_is_noop(tmp_path, monkeypatch):
  monkeypatch.setattr(log, "PATH", str(tmp_path / "missing.log"))
  monkeypatch.setattr(log, "MAX_BYTES", 10)
  log._trim()  # must not raise
