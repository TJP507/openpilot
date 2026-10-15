from __future__ import annotations

import base64
import os

from openpilot.sunnypilot.tylerpilot import actions, config, trips


def test_run_unknown_action():
  ok, msg, artifact = actions.run("nope", {})
  assert ok is False
  assert "unknown action" in msg
  assert artifact is None


def test_typed_coercion():
  assert actions._typed(None) is None
  assert actions._typed(b"1") is True
  assert actions._typed(b"0") is False
  assert actions._typed(b"hello") == "hello"
  raw = b"\xff\xfe"
  assert actions._typed(raw) == base64.b64encode(raw).decode()


def test_reboot(monkeypatch):
  calls = {}
  monkeypatch.setattr(actions.toast, "show", lambda *a, **k: calls.setdefault("toast", True))
  monkeypatch.setattr(actions.time, "sleep", lambda s: None)
  monkeypatch.setattr(actions.HARDWARE, "reboot", lambda: calls.setdefault("reboot", True))
  ok, msg, artifact = actions.reboot({})
  assert ok is True
  assert msg == "rebooting"
  assert calls["toast"] and calls["reboot"]
  assert artifact is None


def test_poweroff(monkeypatch):
  calls = {}
  monkeypatch.setattr(actions.toast, "show", lambda *a, **k: None)
  monkeypatch.setattr(actions.time, "sleep", lambda s: None)
  monkeypatch.setattr(actions.HARDWARE, "shutdown", lambda: calls.setdefault("shutdown", True))
  ok, msg, _ = actions.poweroff({})
  assert ok is True and msg == "powering off" and calls["shutdown"]


def test_restart_manager_sets_flag(tmp_path, monkeypatch):
  monkeypatch.setattr(config, "STATE_DIR", str(tmp_path))
  monkeypatch.setattr(actions.toast, "show", lambda *a, **k: None)
  monkeypatch.setattr(actions, "_run", lambda *a, **k: (0, ""))
  ok, msg, _ = actions.restart_manager({})
  assert ok is True
  assert (tmp_path / "tylerpilot_restart_manager").exists()


def test_param_get(monkeypatch):
  class _P:
    def get(self, key):
      return b"value"

  monkeypatch.setattr(actions, "Params", _P)
  ok, val, _ = actions.param_get({"key": "Foo"})
  assert ok is True and val == "value"
  ok, msg, _ = actions.param_get({})
  assert ok is False and msg == "no key"


def test_param_set_dispatch(monkeypatch):
  calls = {}

  class _P:
    def put_bool(self, k, v):
      calls[k] = ("bool", v)

    def put_int(self, k, v):
      calls[k] = ("int", v)

    def put_float(self, k, v):
      calls[k] = ("float", v)

    def put(self, k, v):
      calls[k] = ("str", v)

  monkeypatch.setattr(actions, "Params", _P)
  assert actions.param_set({"key": "B", "value": True})[0] is True
  assert actions.param_set({"key": "I", "value": 3})[0] is True
  assert actions.param_set({"key": "F", "value": 1.5})[0] is True
  assert actions.param_set({"key": "S", "value": "x"})[0] is True
  assert calls["B"] == ("bool", True)
  assert calls["I"] == ("int", 3)
  assert calls["F"] == ("float", 1.5)
  assert calls["S"] == ("str", "x")
  assert actions.param_set({})[0] is False


def test_update_rejects_unknown_channel():
  ok, msg, _ = actions.update({"channel": "nope"})
  assert ok is False and "unknown channel" in msg


def test_update_switches_channel(tmp_path, monkeypatch):
  real_isdir = os.path.isdir
  monkeypatch.setattr(os.path, "isdir", lambda p: True if str(p).endswith(".git") else real_isdir(p))
  runs = []
  monkeypatch.setattr(actions, "_run", lambda args, timeout=60, check=False: (runs.append(args), (0, ""))[1])
  monkeypatch.setattr(actions.toast, "show", lambda *a, **k: None)
  monkeypatch.setattr(config, "STATE_DIR", str(tmp_path))

  ok, msg, _ = actions.update({"channel": "dev-c3x"})
  assert ok is True and "switched to dev-c3x" in msg
  assert any(args[:3] == ["git", "-C", "/data/openpilot"] for args in runs)


def test_location_no_fix(monkeypatch):
  monkeypatch.setattr(trips, "recent_positions", lambda n=1: [])
  ok, msg, _ = actions.location({})
  assert ok is False and "no GPS" in msg


def test_location_with_fix(monkeypatch):
  monkeypatch.setattr(trips, "recent_positions", lambda n=1: [{"lat": 1.0, "lon": 2.0}])
  ok, msg, artifact = actions.location({})
  assert ok is True and msg == "gps"
  assert artifact["kind"] == "_location"


def test_backup_returns_tarball():
  ok, msg, artifact = actions.backup({})
  assert ok is True
  assert artifact["kind"] == "backup"
  assert len(base64.b64decode(artifact["data"])) > 0


def test_tar_dereferences_symlinks(tmp_path):
  import io
  import tarfile

  real = tmp_path / "real"
  real.mkdir()
  (real / "CarParams").write_text("value")
  linkdir = tmp_path / "linkdir"
  linkdir.mkdir()
  os.symlink(real, linkdir / "d")

  data = actions._tar([str(linkdir / "d")])
  with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as t:
    members = t.getmembers()
    assert not any(m.issym() for m in members), "symlink archived instead of its contents"
    assert any(m.name.endswith("d/CarParams") for m in members)


def test_diagnostics_returns_tarball(monkeypatch):
  monkeypatch.setattr(actions, "_run", lambda *a, **k: (0, "output"))
  ok, msg, artifact = actions.diagnostics({})
  assert ok is True
  assert artifact["kind"] == "diagnostics"
  assert len(base64.b64decode(artifact["data"])) > 0


def test_restore_requires_artifact_id():
  ok, msg, _ = actions.restore({})
  assert ok is False and msg == "no artifact id"


def test_handlers_registry_complete():
  for name in ("reboot", "poweroff", "restart_manager", "param_get", "param_set",
               "update", "location", "trips", "diagnostics", "backup", "restore"):
    assert name in actions.HANDLERS
