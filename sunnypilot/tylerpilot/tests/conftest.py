"""
Shared test setup for the TylerPilot unit tests.

These tests run build-free (the fork ships no build system yet). The one thing
that blocks importing `tylerpilot.actions` is `openpilot.common.params`, which
imports the compiled `params_pyx` extension. Install a minimal stub before any
test module imports actions so the module imports cleanly; individual tests
monkeypatch the stub as needed.
"""
from __future__ import annotations

import sys
import types

import pytest


def _install_params_stub() -> None:
  if "openpilot.common.params" in sys.modules:
    return

  class _Params:
    def __init__(self, *args, **kwargs) -> None:
      pass

    def get(self, key, *args, **kwargs):
      return None

    def get_bool(self, key, *args, **kwargs):
      return False

    def put(self, *args, **kwargs) -> None:
      pass

    def put_bool(self, *args, **kwargs) -> None:
      pass

    def put_int(self, *args, **kwargs) -> None:
      pass

    def put_float(self, *args, **kwargs) -> None:
      pass

  mod = types.ModuleType("openpilot.common.params")
  mod.Params = _Params
  mod.ParamKeyFlag = object
  mod.ParamKeyType = object
  mod.UnknownKeyName = Exception
  sys.modules["openpilot.common.params"] = mod


_install_params_stub()


class FakeParams:
  """In-memory stand-in for the compiled Params binding."""

  def __init__(self, values: dict | None = None, known: set[str] | None = None,
               defaults: dict | None = None) -> None:
    self.values = dict(values or {})
    self.known = set(known or ())
    self.defaults = dict(defaults or {})

  def check_key(self, key):
    if key not in self.known:
      raise KeyError(key)
    return key

  def get(self, key, *args, return_default=False, **kwargs):
    if key in self.values:
      return self.values[key]
    return self.defaults.get(key) if return_default else None

  def get_bool(self, key, *args, **kwargs):
    return bool(self.get(key, return_default=True))

  def put(self, key, value, *args, block=False, **kwargs) -> None:
    if self.known and key not in self.known:
      raise KeyError(key)
    self.values[key] = value


@pytest.fixture
def fake_params(monkeypatch):
  """Install a shared FakeParams into settings_backup and return it."""
  from openpilot.sunnypilot.tylerpilot import settings_backup

  fp = FakeParams(known=set(settings_backup.ALLOWLIST) | {"DongleId", "GitBranch"})
  monkeypatch.setattr(settings_backup, "Params", lambda *a, **k: fp)
  return fp
