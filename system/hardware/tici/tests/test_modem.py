"""
Unit tests for the modem daemon's state machine (system.hardware.tici.modem).

These run build-free: a fake PPPSession stands in for pppd and the AT layer is
never touched (no serial device). Timing is driven by a controllable clock.
"""
from __future__ import annotations

import json

import pytest

from openpilot.system.hardware.tici import modem


class Clock:
  """A controllable stand-in for time.monotonic()."""

  def __init__(self, t: float = 1000.0) -> None:
    self.t = t

  def __call__(self) -> float:
    return self.t


class FakePPP:
  """Stands in for PPPSession without touching pppd or the routing table."""

  MAX_FAILS = 3

  def __init__(self) -> None:
    self._fails = 0
    self._running = False
    self._exited = False
    self.returncode: int | None = 16
    self.tail = ["CHAP authentication succeeded", "Modem hangup", "Connection terminated."]
    self.starts = 0
    self.kills = 0
    self.resets = 0
    self.started_at = 0.0

  def start(self) -> None:
    self.starts += 1
    self._running = True
    self._exited = False
    self.started_at = modem.time.monotonic()

  def kill(self) -> None:
    self.kills += 1
    self._running = False
    self._exited = False  # mirrors PPPSession.kill() clearing the exited process

  def capture_exit(self):
    self._running = False
    self._exited = True
    return self.returncode, list(self.tail)

  def reset_data_port(self) -> None:
    self.resets += 1

  def reset_fail_counter(self) -> None:
    self._fails = 0

  def record_fail(self) -> bool:
    self._fails += 1
    return self._fails >= self.MAX_FAILS

  @property
  def fails(self) -> int:
    return self._fails

  @property
  def running(self) -> bool:
    return self._running

  def has_exited(self) -> bool:
    return self._exited

  def maybe_install_routes(self, ip: str, peer: str) -> bool:
    return False

  def maybe_install_dns(self, dns_servers: list[str]) -> bool:
    return False

  def cleanup_routes(self) -> None:
    pass


@pytest.fixture
def env(tmp_path, monkeypatch):
  """A Modem wired to a FakePPP, a temp state file, and a controllable clock."""
  at_port = tmp_path / "at0"
  at_port.write_text("")  # AT_PORT must exist for the CONNECTED checks
  monkeypatch.setattr(modem, "STATE_PATH", str(tmp_path / "modem"))
  monkeypatch.setattr(modem, "AT_PORT", str(at_port))
  monkeypatch.setattr(modem, "REINIT_FILE", str(tmp_path / "reinit"))
  monkeypatch.setattr(modem, "USAGE_FILE", str(tmp_path / "usage.json"))
  monkeypatch.setattr(modem, "USAGE_RESET_FILE", str(tmp_path / "usage_reset"))
  clock = Clock()
  monkeypatch.setattr(modem.time, "monotonic", clock)
  # Deterministic backoff: no jitter.
  monkeypatch.setattr(modem.random, "uniform", lambda _a, _b: 0.0)
  m = modem.Modem()
  fake = FakePPP()
  m._ppp = fake
  m._params_changed = lambda: False
  return m, fake, clock, tmp_path


def read_state(tmp_path) -> dict:
  return json.loads((tmp_path / "modem").read_text())


def fail_next_dial(fake: FakePPP) -> None:
  """Make the next _do_connecting tick look like pppd died right after start."""
  fake.start()
  fake._running = False
  fake._exited = True


# ---- pure helpers ---------------------------------------------------------

def test_backoff_schedule_is_capped(monkeypatch):
  monkeypatch.setattr(modem.random, "uniform", lambda _a, _b: 0.0)
  assert [modem.Modem._backoff_delay(i) for i in range(6)] == [10, 30, 60, 120, 300, 300]


def test_backoff_delay_is_capped_after_jitter(monkeypatch):
  monkeypatch.setattr(modem.random, "uniform", lambda _a, _b: 0.9)
  assert modem.Modem._backoff_delay(4) == modem.BACKOFF_MAX


def test_summarize_pppd_failure():
  assert "modem hung up" in modem._summarize_pppd_failure(16, ["Modem hangup"])
  assert "no carrier" in modem._summarize_pppd_failure(1, ["NO CARRIER"])
  assert "authentication failed" in modem._summarize_pppd_failure(4, ["CHAP authentication failed"])
  assert modem._summarize_pppd_failure(None, []) == "pppd exited"
  assert modem._summarize_pppd_failure(5, ["weird"]) == "weird (pppd exit 5)"


# ---- CONNECTING -> CONNECTED only with an IP ------------------------------

def test_connecting_starts_pppd_once_and_waits_for_ip(env, monkeypatch):
  m, fake, _clock, _tmp = env
  monkeypatch.setattr(m, "_ppp0_addr", lambda: ("", ""))
  assert m._step(modem.State.CONNECTING) == modem.State.CONNECTING
  assert fake.starts == 1
  # No IP yet: pppd is not restarted, we keep waiting.
  assert m._step(modem.State.CONNECTING) == modem.State.CONNECTING
  assert fake.starts == 1


def test_connecting_times_out_waiting_for_ip(env, monkeypatch):
  m, fake, clock, tmp_path = env
  monkeypatch.setattr(m, "_ppp0_addr", lambda: ("", ""))
  assert m._step(modem.State.CONNECTING) == modem.State.CONNECTING  # starts pppd
  assert fake.started_at == clock.t
  # pppd is alive but never gets an IP: past the timeout it's a dial failure.
  clock.t += modem.CONNECT_TIMEOUT + 1
  assert m._step(modem.State.CONNECTING) == modem.State.CONNECTING  # retry (fail 1)
  assert fake.kills == 1
  assert fake.fails == 1
  assert read_state(tmp_path)["last_error"] == "Timed out waiting for an IP address"


def test_ip_appears_transitions_to_connected(env, monkeypatch):
  m, fake, _clock, tmp_path = env
  fake.start()
  monkeypatch.setattr(m, "_ppp0_addr", lambda: ("10.20.30.40", "10.64.64.64"))
  assert m._step(modem.State.CONNECTING) == modem.State.CONNECTED
  state = read_state(tmp_path)
  assert state["state"] == "CONNECTED"
  assert state["connected"] is True
  assert state["ip_address"] == "10.20.30.40"


def test_connected_without_ip_is_a_dial_failure(env, monkeypatch):
  m, fake, _clock, tmp_path = env
  fake.start()
  monkeypatch.setattr(m, "_ppp0_addr", lambda: ("", ""))
  assert m._step(modem.State.CONNECTED) == modem.State.CONNECTING
  assert fake.kills == 1
  assert fake.fails == 1
  assert read_state(tmp_path)["last_error"] == "Connection lost (no IP on ppp0)"


def test_pppd_exit_while_connected_is_a_dial_failure(env):
  m, fake, _clock, _tmp = env
  fake.start()
  fake._running = False
  fake._exited = True
  assert m._step(modem.State.CONNECTED) == modem.State.CONNECTING
  assert fake.fails == 1


def test_teardown_forgets_the_previous_process(env):
  m, fake, _clock, _tmp = env
  fail_next_dial(fake)
  m._step(modem.State.CONNECTING)  # fail 1 -> retry
  # A full teardown must forget the previous pppd, so the next CONNECTING dials
  # fresh instead of re-recording the old exit as another failure.
  m._do_disconnecting()
  assert not fake.has_exited()
  assert m._do_connecting() == modem.State.CONNECTING
  assert fake.fails == 0


# ---- retries then exponential backoff -------------------------------------

def test_repeated_dial_failures_retry_then_back_off(env):
  m, fake, clock, tmp_path = env
  fail_next_dial(fake)
  assert m._step(modem.State.CONNECTING) == modem.State.CONNECTING  # retry 1
  assert fake.fails == 1
  assert fake.starts == 2

  fail_next_dial(fake)
  assert m._step(modem.State.CONNECTING) == modem.State.CONNECTING  # retry 2
  assert fake.fails == 2

  fail_next_dial(fake)
  assert m._step(modem.State.CONNECTING) == modem.State.DIAL_FAILED  # give up -> backoff
  assert fake.fails == 3
  assert m._backoff_until == clock.t + 10  # first backoff step

  state = read_state(tmp_path)
  assert state["state"] == "DIAL_FAILED"
  assert state["fail_count"] == 3
  assert state["max_fails"] == 3
  assert state["retry_in"] == 10
  assert "modem hung up" in state["last_error"]
  assert state["last_error_at"] > 0


def test_backoff_grows_across_reinit_cycles(env):
  m, fake, clock, _tmp = env

  def give_up():
    for _ in range(m._ppp.MAX_FAILS):
      fail_next_dial(fake)
      m._step(modem.State.CONNECTING)

  give_up()
  assert m._backoff_attempt == 1
  assert m._backoff_until == clock.t + 10  # first backoff step

  # Elapse the backoff and reinitialize, then a fresh dial cycle resets the
  # consecutive-failure counter but not the backoff step.
  clock.t += 10
  assert m._step(modem.State.DIAL_FAILED) == modem.State.DISCONNECTING
  m._step(modem.State.DISCONNECTING)
  fake._running, fake._exited = False, False
  m._step(modem.State.CONNECTING)  # fresh dial: resets fail counter

  give_up()
  assert m._backoff_attempt == 2
  assert m._backoff_until == clock.t + 30  # next backoff step is longer


def test_backoff_waits_then_reinitializes(env):
  m, _fake, clock, tmp_path = env
  m._backoff_until = clock.t + 10
  assert m._step(modem.State.DIAL_FAILED) == modem.State.DIAL_FAILED
  assert read_state(tmp_path)["retry_in"] == 10
  clock.t += 11
  assert m._step(modem.State.DIAL_FAILED) == modem.State.DISCONNECTING


def test_stable_connection_clears_failures_and_backoff(env):
  m, fake, clock, _tmp = env
  fake._fails = 2
  m._backoff_attempt = 3
  m._connected_at = clock.t - modem.STABLE_SECONDS - 1
  m._mark_stable()
  assert fake.fails == 0
  assert m._backoff_attempt == 0


# ---- external triggers reset the backoff ----------------------------------

def test_reinit_file_acts_immediately_and_resets_backoff(env):
  m, _fake, clock, tmp_path = env
  m._backoff_attempt = 4
  m._backoff_until = clock.t + 300
  (tmp_path / "reinit").write_text("")
  assert m._preflight(modem.State.DIAL_FAILED) == modem.State.DISCONNECTING
  assert m._backoff_attempt == 0
  assert m._backoff_until == 0.0
  assert not (tmp_path / "reinit").exists()


def test_params_change_resets_backoff(env):
  m, _fake, clock, _tmp = env
  m._params_changed = lambda: True
  m._backoff_attempt = 2
  assert m._preflight(modem.State.SEARCHING) == modem.State.DISCONNECTING
  assert m._backoff_attempt == 0


def test_preflight_is_a_noop_for_initializing(env):
  m, _fake, _clock, tmp_path = env
  (tmp_path / "reinit").write_text("")
  assert m._preflight(modem.State.INITIALIZING) == modem.State.INITIALIZING
  assert (tmp_path / "reinit").exists()  # left for the reinit handler


# ---- exceptions back off instead of tight-looping -------------------------

def test_handler_exception_backs_off(env):
  m, _fake, clock, tmp_path = env

  def boom():
    raise RuntimeError("kaboom")

  m._handlers[modem.State.CONNECTED] = boom
  assert m._step(modem.State.CONNECTED) == modem.State.DIAL_FAILED
  assert m._backoff_attempt == 1
  assert m._backoff_until == clock.t + 10
  state = read_state(tmp_path)
  assert state["state"] == "DIAL_FAILED"
  assert state["last_error"].startswith("internal error")
  assert "kaboom" in state["last_error"]
