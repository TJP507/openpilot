from __future__ import annotations

import types

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


# --------------------------------------------------------------------------
# gather_stats
# --------------------------------------------------------------------------
class _OnroadParams:
  def get_bool(self, key, *args, **kwargs):
    return True


class _BrokenParams:
  def get_bool(self, key, *args, **kwargs):
    raise OSError("params unavailable")


def test_classify_network_types():
  assert agent._classify("rmnet_data0") == "cell"
  assert agent._classify("wwan0") == "cell"
  assert agent._classify("wlan0") == "wifi"
  assert agent._classify("eth0") == "ethernet"
  assert agent._classify("usb0") == "ethernet"
  assert agent._classify("") is None


def test_gather_stats_reports_available_fields(monkeypatch):
  monkeypatch.setattr(agent, "get_version", lambda: "2026.002.029")
  monkeypatch.setattr(agent, "get_short_branch", lambda: "dev-c3x")
  monkeypatch.setattr(agent, "get_commit", lambda: "abcdef1234567890")
  monkeypatch.setattr(agent, "_net_type", lambda: "wifi")
  monkeypatch.setattr(agent, "_cpu_temp", lambda: 42.5)
  monkeypatch.setattr(agent, "_recordings_bytes", lambda: 999)
  monkeypatch.setattr(agent, "Params", _OnroadParams)
  monkeypatch.setattr(agent.psutil, "boot_time", lambda: 1000.0)
  monkeypatch.setattr(agent.psutil, "cpu_percent", lambda interval=None: 12.34)
  monkeypatch.setattr(agent.psutil, "virtual_memory", lambda: types.SimpleNamespace(percent=55.5))
  monkeypatch.setattr(agent.psutil, "disk_usage", lambda p: types.SimpleNamespace(free=100, total=200))
  monkeypatch.setattr(agent.time, "time", lambda: 1060.0)

  s = agent.gather_stats()
  assert s["version"] == "2026.002.029"
  assert s["branch"] == "dev-c3x"
  assert s["commit"] == "abcdef1"  # short
  assert s["uptime_s"] == 60
  assert s["started_at"] == 1000
  assert s["cpu_temp_c"] == 42.5
  assert s["cpu_pct"] == 12.3
  assert s["mem_pct"] == 55.5
  assert s["storage_free_bytes"] == 100
  assert s["storage_total_bytes"] == 200
  assert s["recordings_bytes"] == 999
  assert s["net_type"] == "wifi"
  assert s["onroad"] is True


def test_gather_stats_omits_unknown_values(monkeypatch):
  def boom(*a, **k):
    raise OSError("unavailable")

  monkeypatch.setattr(agent, "get_version", lambda: "")
  monkeypatch.setattr(agent, "get_short_branch", lambda: "")
  monkeypatch.setattr(agent, "get_commit", lambda: "")
  monkeypatch.setattr(agent, "_net_type", lambda: "none")
  monkeypatch.setattr(agent, "_cpu_temp", lambda: None)
  monkeypatch.setattr(agent, "_recordings_bytes", lambda: None)
  monkeypatch.setattr(agent, "Params", _BrokenParams)  # onroad unreadable
  monkeypatch.setattr(agent.psutil, "boot_time", boom)
  monkeypatch.setattr(agent.psutil, "cpu_percent", boom)
  monkeypatch.setattr(agent.psutil, "virtual_memory", boom)
  monkeypatch.setattr(agent.psutil, "disk_usage", boom)

  s = agent.gather_stats()
  assert s == {"net_type": "none"}  # nothing faked, unknowns omitted


def test_recordings_bytes_cached(tmp_path, monkeypatch):
  monkeypatch.setattr(agent, "_RECORDINGS_DIR", str(tmp_path))
  monkeypatch.setattr(agent, "_recordings_cache", (0.0, -1))
  clock = Clock()
  monkeypatch.setattr(agent.time, "monotonic", clock)
  (tmp_path / "a.mp4").write_bytes(b"x" * 100)

  assert agent._recordings_bytes() == 100
  # A change within the TTL is not re-scanned.
  (tmp_path / "b.mp4").write_bytes(b"y" * 50)
  assert agent._recordings_bytes() == 100
  clock.t += agent._RECORDINGS_TTL + 1
  assert agent._recordings_bytes() == 150


def test_recordings_bytes_missing_dir(monkeypatch):
  monkeypatch.setattr(agent, "_RECORDINGS_DIR", "/no/such/dir")
  monkeypatch.setattr(agent, "_recordings_cache", (0.0, -1))
  assert agent._recordings_bytes() is None
