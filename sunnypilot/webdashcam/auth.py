"""
Web dash cam authentication helpers.

Pure, dependency-free logic (no aiohttp/psutil/cereal) so it can be unit tested
on a PC: a per-key login brute-force limiter and a same-origin check for
state-changing requests.
"""
from __future__ import annotations

import time
from urllib.parse import urlparse

# Login brute-force backoff: after this many consecutive failures for a key,
# further attempts are refused until the lockout elapses. The lockout grows with
# the failure count, capped, so a persistent attacker is throttled hard while a
# user who mistypes a few times is barely affected.
FREE_ATTEMPTS = 5
BASE_LOCKOUT = 5.0   # seconds
MAX_LOCKOUT = 300.0  # seconds


class LoginLimiter:
  """Per-key consecutive-failure limiter with an exponential lockout."""

  def __init__(self, now=time.monotonic):
    self._now = now
    self._failures: dict[str, int] = {}
    self._until: dict[str, float] = {}

  def locked(self, key: str) -> float:
    """Seconds remaining on the lockout for key, or 0 when not locked."""
    remaining = self._until.get(key, 0.0) - self._now()
    return remaining if remaining > 0 else 0.0

  def fail(self, key: str) -> None:
    """Record a failed attempt and extend the lockout once the free attempts are used."""
    n = self._failures.get(key, 0) + 1
    self._failures[key] = n
    if n >= FREE_ATTEMPTS:
      extra = n - FREE_ATTEMPTS + 1
      self._until[key] = self._now() + min(BASE_LOCKOUT * (2 ** (extra - 1)), MAX_LOCKOUT)

  def succeed(self, key: str) -> None:
    """Clear a key's failures after a successful login."""
    self._failures.pop(key, None)
    self._until.pop(key, None)


def _host_of(value: str) -> str:
  """Host (no scheme/port/userinfo) of a URL or bare host:port, lowercased."""
  value = (value or "").strip()
  if not value:
    return ""
  if "//" not in value:
    value = "//" + value
  parsed = urlparse(value)
  host = parsed.hostname or ""
  return host.lower()


def same_origin(origin: str, referer: str, host: str) -> bool:
  """True when a state-changing request is same-origin.

  A browser sends Origin (and/or Referer) on cross-site requests, so a mismatched
  host is rejected. A request with neither header (curl, some same-origin form
  clients) is allowed: the session cookie is HttpOnly + SameSite, and the server
  is only reachable on the LAN.
  """
  src = origin or referer
  if not src:
    return True
  return _host_of(src) == _host_of(host)
