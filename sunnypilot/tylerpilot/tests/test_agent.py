from __future__ import annotations

import pytest

from openpilot.sunnypilot.tylerpilot import agent, client, config


class Clock:
  """A controllable stand-in for time.monotonic()."""

  def __init__(self, t: float = 1000.0) -> None:
    self.t = t

  def __call__(self) -> float:
    return self.t


@pytest.fixture
def state(tmp_path, monkeypatch):
  monkeypatch.setattr(config, "STATE_DIR", str(tmp_path))
  monkeypatch.setattr(config, "STATE_PATH", str(tmp_path / "tylerpilot.json"))
  monkeypatch.setattr(agent, "gather_stats", dict)
  monkeypatch.setattr(agent, "_net_type", lambda: "wifi")
  agent._reset_auth_strikes()
  return tmp_path


def test_backoff_is_longer_when_revoked(state):
  config.set_link("dev1", "tok", "fp", "srv", "Car")
  assert agent._backoff_seconds() == agent._IDLE_SLEEP
  config.mark_revoked("x")
  assert agent._backoff_seconds() == agent._REVOKED_BACKOFF


def test_foreign_401_never_revokes(state, monkeypatch):
  config.set_link("dev1", "tok", "fp", "srv", "Car")
  clock = Clock()
  monkeypatch.setattr(agent.time, "monotonic", clock)

  # A non-JSON / foreign 401 (empty code), repeated for a long time, never
  # revokes — the token is kept and the counter stays at zero.
  for _ in range(5):
    agent._handle_auth_error("", "unauthorized")
    clock.t += 120

  assert not config.is_revoked()
  assert config.is_linked()
  assert agent._auth_strikes == 0
  assert "401" in config.get("last_error")


def test_two_strikes_do_not_revoke(state, monkeypatch):
  config.set_link("dev1", "tok", "fp", "srv", "Car")
  clock = Clock()
  monkeypatch.setattr(agent.time, "monotonic", clock)

  agent._handle_auth_error("unauthenticated", "x")
  clock.t += 300
  agent._handle_auth_error("unauthenticated", "x")

  assert not config.is_revoked()
  assert config.is_linked()
  assert agent._auth_strikes == 2
  assert "2/3" in config.get("last_error")


def test_three_strikes_over_two_minutes_revokes(state, monkeypatch):
  config.set_link("dev1", "tok", "fp", "srv", "Car")
  config.set_values(server_ssh_key="ssh-ed25519 SERVERKEY")
  removed: list = []
  monkeypatch.setattr(client, "remove_server_key", lambda k: removed.append(k))
  clock = Clock()
  monkeypatch.setattr(agent.time, "monotonic", clock)

  agent._handle_auth_error("unauthenticated", "x")  # strike 1
  assert not config.is_revoked()
  clock.t += 61
  agent._handle_auth_error("unauthenticated", "x")  # strike 2, span 61 < 120
  assert not config.is_revoked()
  assert config.is_linked()  # the token is kept until confirmed
  clock.t += 69
  agent._handle_auth_error("unauthenticated", "x")  # strike 3, span 130 >= 120

  assert config.is_revoked()
  assert not config.is_linked()
  # The server's SSH login key is removed and forgotten.
  assert removed == ["ssh-ed25519 SERVERKEY"]
  assert config.get("server_ssh_key") == ""


def test_cycle_single_401_keeps_token(state, monkeypatch):
  config.set_link("dev1", "tok", "fp", "srv", "Car")

  def fail(*a, **k):
    raise client.AuthError("unauthenticated", "unauthenticated")

  monkeypatch.setattr(client, "heartbeat", fail)
  monkeypatch.setattr(client, "poll", fail)

  agent._cycle(0.0)

  assert not config.is_revoked()
  assert config.is_linked()
  assert agent._auth_strikes == 2  # one heartbeat + one poll this cycle
  assert "2/3" in config.get("last_error")


def test_success_resets_strikes_and_error(state, monkeypatch):
  config.set_link("dev1", "tok", "fp", "srv", "Car")
  clock = Clock()
  monkeypatch.setattr(agent.time, "monotonic", clock)
  agent._handle_auth_error("unauthenticated", "x")
  agent._handle_auth_error("unauthenticated", "x")
  assert agent._auth_strikes == 2

  monkeypatch.setattr(client, "heartbeat", lambda *a, **k: {})
  monkeypatch.setattr(client, "poll", lambda *a, **k: {"type": "none"})
  agent._cycle(0.0)

  assert agent._auth_strikes == 0
  assert config.get("last_error") == ""


def test_ensure_server_key_installs_when_linked(state, monkeypatch):
  config.set_values(server_ssh_key="ssh-ed25519 SERVERKEY")
  installed: list = []
  monkeypatch.setattr(client, "install_server_key", lambda k: installed.append(k))
  agent._ensure_server_key()
  assert installed == ["ssh-ed25519 SERVERKEY"]


def test_ensure_server_key_noop_when_revoked(state, monkeypatch):
  config.set_values(server_ssh_key="ssh-ed25519 SERVERKEY")
  config.mark_revoked("x")
  installed: list = []
  monkeypatch.setattr(client, "install_server_key", lambda k: installed.append(k))
  agent._ensure_server_key()
  assert installed == []
