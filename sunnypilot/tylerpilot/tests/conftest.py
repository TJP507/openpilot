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


def _install_params_stub() -> None:
  if "openpilot.common.params" in sys.modules:
    return

  class _Params:
    def __init__(self, *args, **kwargs) -> None:
      pass

    def get(self, key, *args, **kwargs):
      return None

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
