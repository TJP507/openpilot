"""
Round-trip the backup logic against the REAL compiled Params binding.

The rest of the suite drives a FakeParams because the build-free CI environment
has no compiled `params_pyx`. This test runs the real binding in a subprocess
(where it isn't shadowed by the conftest stub) and skips cleanly when it can't
be imported.
"""
from __future__ import annotations

import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]

_SCRIPT = textwrap.dedent('''
  import sys
  try:
    from openpilot.common.params import Params
    from openpilot.sunnypilot.tylerpilot import settings_backup
  except Exception as e:
    print("SKIP:", e, file=sys.stderr)
    sys.exit(2)

  import json
  import tempfile

  d = tempfile.mkdtemp()
  p = Params(d)
  p.put_bool("IsMetric", True, block=True)
  p.put("LanguageSetting", "fr", block=True)
  p.put("MadsSteeringMode", 2, block=True)
  p.put("CameraOffset", 0.25, block=True)

  settings_backup.Params = lambda *a, **k: Params(d)
  settings_backup._firmware_version = lambda: "v"

  doc = settings_backup.parse_backup(settings_backup.build_backup())
  got = doc["params"]
  assert got["IsMetric"] is True, got
  assert got["LanguageSetting"] == "fr", got
  assert got["MadsSteeringMode"] == 2 and not isinstance(got["MadsSteeringMode"], bool), got
  assert isinstance(got["CameraOffset"], float) and got["CameraOffset"] == 0.25, got

  doc["params"]["MadsSteeringMode"] = 3
  counts = settings_backup.apply(doc)
  assert counts["failed"] == [], counts
  assert Params(d).get("MadsSteeringMode", return_default=True) == 3
  print(json.dumps({"ok": True, "counts": counts}))
''')


def test_real_params_binding_roundtrip():
  env = {**os.environ, "PYTHONPATH": str(REPO)}
  proc = subprocess.run([sys.executable, "-c", _SCRIPT], capture_output=True, text=True, env=env)
  if proc.returncode == 2:
    pytest.skip(f"compiled Params binding not importable: {proc.stderr.strip()[:200]}")
  assert proc.returncode == 0, proc.stderr
  assert '"ok": true' in proc.stdout
