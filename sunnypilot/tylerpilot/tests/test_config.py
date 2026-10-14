from __future__ import annotations

import os
import stat

import pytest

from openpilot.sunnypilot.tylerpilot import config


@pytest.fixture
def state(tmp_path, monkeypatch):
  monkeypatch.setattr(config, "STATE_DIR", str(tmp_path))
  monkeypatch.setattr(config, "STATE_PATH", str(tmp_path / "tylerpilot.json"))
  return tmp_path


def test_defaults_when_missing(state):
  s = config.load()
  assert s["host"] == config.DEFAULT_HOST
  assert s["port"] == config.DEFAULT_PORT
  assert s["linked"] is False
  assert s["token"] == ""


def test_roundtrip_and_permissions(state):
  config.set_values(device_id="dev1", token="tok", linked=True)
  s = config.load()
  assert s["device_id"] == "dev1"
  assert config.get("token") == "tok"
  # The state file holds the device token and must be 0600.
  assert stat.S_IMODE(os.stat(config.STATE_PATH).st_mode) == 0o600


def test_is_linked_requires_token_and_device(state):
  assert config.is_linked() is False
  config.set_link("dev1", "tok", "fp", "srv", "name")
  assert config.is_linked() is True
  config.clear_link()
  assert config.is_linked() is False


def test_set_error_truncates(state):
  config.set_error("x" * 1000)
  assert len(config.load()["last_error"]) == 300


def test_set_server(state):
  config.set_server("example.com", 1234)
  s = config.load()
  assert s["host"] == "example.com"
  assert s["port"] == 1234


def test_migrates_legacy_default_port(state):
  config.set_server(config.DEFAULT_HOST, config._LEGACY_DEFAULT_PORT)
  assert config.load()["port"] == config.DEFAULT_PORT


def test_corrupt_json_falls_back_to_defaults(state):
  with open(config.STATE_PATH, "w") as f:
    f.write("{not valid json")
  assert config.load()["host"] == config.DEFAULT_HOST


def test_non_dict_json_falls_back_to_defaults(state):
  with open(config.STATE_PATH, "w") as f:
    f.write("[1, 2, 3]")
  assert config.load()["linked"] is False


def test_unknown_keys_ignored(state):
  with open(config.STATE_PATH, "w") as f:
    f.write('{"unknown": 1, "device_id": "d"}')
  s = config.load()
  assert "unknown" not in s
  assert s["device_id"] == "d"
