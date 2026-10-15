from __future__ import annotations

from openpilot.sunnypilot.webdashcam import auth, config


def test_login_limiter_locks_after_free_attempts():
  t = [0.0]
  lim = auth.LoginLimiter(now=lambda: t[0])
  for _ in range(auth.FREE_ATTEMPTS - 1):
    lim.fail("ip")
    assert lim.locked("ip") == 0.0
  lim.fail("ip")  # the FREE_ATTEMPTS-th failure locks
  assert lim.locked("ip") > 0


def test_login_limiter_backoff_grows_and_is_capped():
  t = [0.0]
  lim = auth.LoginLimiter(now=lambda: t[0])
  for _ in range(auth.FREE_ATTEMPTS):
    lim.fail("ip")
  first = lim.locked("ip")
  lim.fail("ip")
  assert lim.locked("ip") > first
  for _ in range(50):
    lim.fail("ip")
  assert lim.locked("ip") <= auth.MAX_LOCKOUT


def test_login_limiter_unlocks_and_resets_on_success():
  t = [0.0]
  lim = auth.LoginLimiter(now=lambda: t[0])
  for _ in range(auth.FREE_ATTEMPTS):
    lim.fail("ip")
  assert lim.locked("ip") > 0
  t[0] += auth.MAX_LOCKOUT + 1
  assert lim.locked("ip") == 0.0
  lim.succeed("ip")
  assert lim.locked("ip") == 0.0


def test_same_origin():
  assert auth.same_origin("", "", "10.0.0.5:8443") is True
  assert auth.same_origin("https://10.0.0.5:8443", "", "10.0.0.5:8443") is True
  assert auth.same_origin("", "https://10.0.0.5/login", "10.0.0.5") is True
  assert auth.same_origin("https://evil.example", "", "10.0.0.5:8443") is False
  assert auth.same_origin("", "https://evil.example/x", "10.0.0.5") is False


def test_new_password_length_and_readable_alphabet():
  pw = config._new_password()
  assert len(pw) == config.PASSWORD_LENGTH
  assert pw.isalnum()
  assert not (set(pw) & set("0O1lI"))
