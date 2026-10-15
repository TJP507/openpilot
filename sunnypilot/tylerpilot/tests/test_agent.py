from __future__ import annotations

import time

import pytest

from openpilot.sunnypilot.tylerpilot import agent, client, config


@pytest.fixture
def state(tmp_path, monkeypatch):
  monkeypatch.setattr(config, "STATE_DIR", str(tmp_path))
  monkeypatch.setattr(config, "STATE_PATH", str(tmp_path / "tylerpilot.json"))
  monkeypatch.setattr(agent, "_ensure_server_key", lambda: None)
  monkeypatch.setattr(agent, "gather_stats", dict)
  monkeypatch.setattr(agent, "_net_type", lambda: "wifi")
  agent._reset_revocation_log()
  return tmp_path


def test_handle_revoked_marks_state_and_logs_once(state, monkeypatch):
  config.set_link("dev1", "tok", "fp", "srv", "Car")
  warnings: list = []
  monkeypatch.setattr(agent.log, "warning", lambda msg: warnings.append(msg))

  agent._handle_revoked("bad token")
  agent._handle_revoked("bad token")

  assert config.is_revoked()
  assert not config.is_linked()
  # Host/port are kept so the user can re-link without re-entering them.
  assert config.get("host") == config.DEFAULT_HOST
  assert config.get("port") == config.DEFAULT_PORT
  assert len(warnings) == 1


def test_backoff_is_longer_when_revoked(state):
  config.set_link("dev1", "tok", "fp", "srv", "Car")
  assert agent._backoff_seconds() == agent._IDLE_SLEEP
  config.mark_revoked("x")
  assert agent._backoff_seconds() == agent._REVOKED_BACKOFF


def test_cycle_401_on_heartbeat_marks_revoked(state, monkeypatch):
  config.set_link("dev1", "tok", "fp", "srv", "Car")

  def boom(*a, **k):
    raise client.RevokedError("unauthenticated")

  monkeypatch.setattr(client, "heartbeat", boom)
  monkeypatch.setattr(client, "poll", lambda *a, **k: {"type": "none"})

  agent._cycle(0.0)

  assert config.is_revoked()
  assert not config.is_linked()
  assert agent._backoff_seconds() == agent._REVOKED_BACKOFF


def test_cycle_401_on_poll_marks_revoked(state, monkeypatch):
  config.set_link("dev1", "tok", "fp", "srv", "Car")
  monkeypatch.setattr(client, "heartbeat", lambda *a, **k: {})

  def boom(*a, **k):
    raise client.RevokedError("unauthenticated")

  monkeypatch.setattr(client, "poll", boom)

  # Pretend we just heartbeated so this cycle only polls.
  agent._cycle(time.monotonic())

  assert config.is_revoked()


def test_cycle_success_clears_error_and_revocation_log(state, monkeypatch):
  config.set_link("dev1", "tok", "fp", "srv", "Car")
  config.set_error("transient")
  agent._handle_revoked("old")  # sets the logged flag
  config.set_link("dev1", "tok2", "fp", "srv", "Car")  # re-link clears revoked

  monkeypatch.setattr(client, "heartbeat", lambda *a, **k: {})
  monkeypatch.setattr(client, "poll", lambda *a, **k: {"type": "none"})

  agent._cycle(0.0)

  assert config.get("last_error") == ""
  assert not agent._revocation_logged
