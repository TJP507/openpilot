"""
TylerPilot on-device log.

A tiny, self-contained, size-capped log so TylerPilot's own messages never grow
without bound on the device. Kept deliberately separate from openpilot's swaglog
so we never touch sunnypilot's logs. When the file reaches MAX_BYTES it is
trimmed down to its most recent half, so total size stays under the cap.
"""
from __future__ import annotations

import os
import re
import threading
import time

from openpilot.system.hardware import PC
from openpilot.system.hardware.hw import Paths

MAX_BYTES = 50 * 1024 * 1024  # 50 MB cap (TylerPilot-only)

DIR = os.path.join(Paths.comma_home(), "community") if PC else "/data/community"
PATH = os.path.join(DIR, "tylerpilot.log")

_LOCK = threading.Lock()

# Secrets that must never leave the device in a log line or a diagnostic bundle.
# Ordered: structural secrets first, then high-entropy blobs.
_SECRET_FIELD = "token|password|passwd|secret|api[_-]?key|private[_-]?key|ssh[_-]?keys?|access[_-]?token|refresh[_-]?token"


def _looks_like_secret(token: str) -> bool:
  """High-entropy base64 that real secrets have: a digit, upper, and lower."""
  return (any(c.isdigit() for c in token)
          and any(c.isupper() for c in token)
          and any(c.islower() for c in token))


def _redact_base64(match: re.Match) -> str:
  # A bare 40-char lowercase git SHA is not a secret; a mixed-case+digit base64
  # blob (a key body, a token) is.
  token = match.group(0)
  return "<redacted>" if _looks_like_secret(token) else token


_REDACTIONS: list[tuple[re.Pattern, object]] = [
  (re.compile(r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----.*?-----END [A-Z0-9 ]*PRIVATE KEY-----", re.S),
   "<redacted private key>"),
  (re.compile(r"\b(?:ghp_|gho_|ghu_|ghs_|ghr_|github_pat_)[A-Za-z0-9_]{10,}"), "<redacted token>"),
  (re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._\-]{8,}"), "Bearer <redacted>"),
  (re.compile(r'(?i)"(' + _SECRET_FIELD + r')"\s*:\s*"[^"]*"'), '"<redacted>":"<redacted>"'),
  # 48+ hex: device tokens are 64 hex; 40-char git SHAs must survive.
  (re.compile(r"\b[0-9a-fA-F]{48,}\b"), "<redacted>"),
  (re.compile(r"(?<![A-Za-z0-9+_\-])[A-Za-z0-9+_\-]{40,}={0,2}(?![A-Za-z0-9+_\-])"), _redact_base64),
]


def redact(text: str) -> str:
  """Strip credentials and high-entropy secrets from a string."""
  for pattern, repl in _REDACTIONS:
    text = pattern.sub(repl, text)
  return text


def redact_bytes(data: bytes) -> bytes:
  """redact() for a possibly-binary blob, decoded lossily and re-encoded."""
  return redact(data.decode("utf-8", "replace")).encode("utf-8")


def _trim() -> None:
  """Bound the file to MAX_BYTES by dropping the oldest half, in place."""
  try:
    size = os.path.getsize(PATH)
  except OSError:
    return
  if size <= MAX_BYTES:
    return
  keep = MAX_BYTES // 2
  try:
    with open(PATH, "rb") as f:
      f.seek(size - keep)
      tail = f.read()
    with open(PATH, "wb") as f:
      f.write(b"tylerpilot: log trimmed\n")
      f.write(tail)
  except OSError:
    pass


def _write(level: str, msg: str) -> None:
  line = f"{time.strftime('%Y-%m-%d %H:%M:%S')} {level} {redact(msg)}\n"
  try:
    os.makedirs(DIR, exist_ok=True)
    with _LOCK:
      _trim()
      with open(PATH, "a") as f:
        f.write(line)
  except OSError:
    pass


def info(msg: str) -> None:
  _write("INFO", msg)


def warning(msg: str) -> None:
  _write("WARN", msg)


def error(msg: str) -> None:
  _write("ERROR", msg)


def exception(msg: str, exc: BaseException | None = None) -> None:
  _write("ERROR", msg if exc is None else f"{msg}: {exc}")
