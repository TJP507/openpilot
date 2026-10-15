from __future__ import annotations

import base64
import io
import json
import os
import tarfile

from openpilot.sunnypilot.tylerpilot import actions, client, config, settings_backup, trips


class _OnroadParams:
  def get_bool(self, key, *args, **kwargs):
    return True


def test_run_unknown_action():
  ok, msg, artifact, deferred = actions.run("nope", {})
  assert ok is False
  assert "unknown action" in msg
  assert artifact is None and deferred is None


def test_run_normalizes_three_tuple(monkeypatch):
  monkeypatch.setattr(trips, "recent_positions", lambda n=1: [{"lat": 1.0}])
  ok, msg, artifact, deferred = actions.run("location", {})
  assert ok is True and artifact["kind"] == "_location" and deferred is None


# --------------------------------------------------------------------------
# power
# --------------------------------------------------------------------------
def test_reboot_defers_until_after_report(monkeypatch):
  calls = {}
  monkeypatch.setattr(actions.toast, "show", lambda *a, **k: calls.setdefault("toast", True))
  monkeypatch.setattr(actions.time, "sleep", lambda s: None)
  monkeypatch.setattr(actions.HARDWARE, "reboot", lambda: calls.setdefault("reboot", True))
  ok, msg, artifact, deferred = actions.reboot({})
  assert ok is True and msg == "Rebooting…" and artifact is None
  assert callable(deferred)
  assert "reboot" not in calls  # nothing has happened yet
  deferred()
  assert calls["reboot"] and calls["toast"]


def test_poweroff_defers(monkeypatch):
  calls = {}
  monkeypatch.setattr(actions.toast, "show", lambda *a, **k: None)
  monkeypatch.setattr(actions.time, "sleep", lambda s: None)
  monkeypatch.setattr(actions.HARDWARE, "shutdown", lambda: calls.setdefault("shutdown", True))
  ok, msg, _, deferred = actions.poweroff({})
  assert ok is True and msg == "Powering off…"
  assert "shutdown" not in calls
  deferred()
  assert calls["shutdown"]


def test_reboot_refuses_when_onroad(monkeypatch):
  monkeypatch.setattr(actions, "Params", _OnroadParams)
  ok, msg, artifact, deferred = actions.run("reboot", {})
  assert ok is False and msg == actions.ONROAD_MSG and deferred is None


def test_poweroff_refuses_when_onroad(monkeypatch):
  monkeypatch.setattr(actions, "Params", _OnroadParams)
  assert actions.poweroff({})[0] is False


class _BrokenParams:
  def get_bool(self, key, *args, **kwargs):
    raise OSError("params unavailable")


def test_is_onroad_fails_closed(monkeypatch):
  monkeypatch.setattr(actions, "Params", _BrokenParams)
  assert actions._is_onroad() is True
  ok, msg, _, deferred = actions.run("reboot", {})
  assert ok is False and msg == actions.ONROAD_MSG and deferred is None


# --------------------------------------------------------------------------
# update
# --------------------------------------------------------------------------
def test_update_rejects_unknown_channel():
  ok, msg, _ = actions.update({"channel": "nope"})
  assert ok is False and "unknown channel" in msg


def test_update_refuses_when_onroad(monkeypatch):
  monkeypatch.setattr(actions, "Params", _OnroadParams)
  ok, msg, _ = actions.update({"channel": "dev-c3x"})
  assert ok is False and msg == actions.ONROAD_MSG


def test_update_switches_channel_and_reboots(tmp_path, monkeypatch):
  real_isdir = os.path.isdir
  monkeypatch.setattr(os.path, "isdir", lambda p: True if str(p).endswith(".git") else real_isdir(p))
  runs = []

  def fake_run(args, timeout=60, check=False):
    runs.append(args)
    if args[-3:-1] == ["rev-parse", "--short"]:
      return 0, "abc1234\n"
    return 0, ""

  monkeypatch.setattr(actions, "_run", fake_run)
  monkeypatch.setattr(config, "STATE_DIR", str(tmp_path))
  calls: dict = {}
  monkeypatch.setattr(actions.toast, "show", lambda *a, **k: None)
  monkeypatch.setattr(actions.time, "sleep", lambda s: None)
  monkeypatch.setattr(actions.HARDWARE, "reboot", lambda: calls.setdefault("reboot", True))

  ok, msg, artifact, deferred = actions.update({"channel": "dev-c3x"})
  assert ok is True and artifact is None
  assert msg == "Switched to dev-c3x (abc1234); rebooting…"
  assert any(args[:3] == ["git", "-C", "/data/openpilot"] for args in runs)
  # No restart-manager flag is written any more.
  assert not (tmp_path / "tylerpilot_restart_manager").exists()
  assert "reboot" not in calls  # deferred until the job result is posted
  deferred()
  assert calls["reboot"]


def test_update_reports_channel_without_sha(tmp_path, monkeypatch):
  real_isdir = os.path.isdir
  monkeypatch.setattr(os.path, "isdir", lambda p: True if str(p).endswith(".git") else real_isdir(p))
  monkeypatch.setattr(actions, "_run", lambda args, timeout=60, check=False: (1, "") if "rev-parse" in args else (0, ""))
  monkeypatch.setattr(actions.toast, "show", lambda *a, **k: None)
  monkeypatch.setattr(actions.time, "sleep", lambda s: None)
  monkeypatch.setattr(actions.HARDWARE, "reboot", lambda: None)

  ok, msg, _, deferred = actions.update({"channel": "staging-c3x"})
  assert ok is True and msg == "Switched to staging-c3x; rebooting…"
  assert callable(deferred)


# --------------------------------------------------------------------------
# location / trips
# --------------------------------------------------------------------------
def test_location_no_fix(monkeypatch):
  monkeypatch.setattr(trips, "recent_positions", lambda n=1: [])
  ok, msg, _ = actions.location({})
  assert ok is False and "no GPS" in msg


def test_location_with_fix(monkeypatch):
  monkeypatch.setattr(trips, "recent_positions", lambda n=1: [{"lat": 1.0, "lon": 2.0}])
  ok, msg, artifact = actions.location({})
  assert ok is True and msg == "gps"
  assert artifact["kind"] == "_location"


# --------------------------------------------------------------------------
# diagnostics
# --------------------------------------------------------------------------
def test_tar_dereferences_symlinks(tmp_path):
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


def test_diagnostics_excludes_settings(monkeypatch):
  monkeypatch.setattr(actions, "_run", lambda *a, **k: (0, "output"))
  _, _, artifact = actions.diagnostics({})
  with tarfile.open(fileobj=io.BytesIO(base64.b64decode(artifact["data"])), mode="r:gz") as t:
    names = t.getnames()
  assert names and all(n.startswith("diag/") for n in names)
  assert not any(n.startswith(("data/params", "data/community")) for n in names)


def test_diagnostics_redacts_secrets(monkeypatch):
  pem = "-----BEGIN OPENSSH PRIVATE KEY-----\nAAAAsecretAAAA\n-----END OPENSSH PRIVATE KEY-----"
  hex_token = "0123456789abcdef" * 4  # 64 hex, like the device token
  blob = f'{{"token":"abc123"}} {pem} {hex_token}'
  monkeypatch.setattr(actions, "_run", lambda *a, **k: (0, blob))
  _, _, artifact = actions.diagnostics({})
  with tarfile.open(fileobj=io.BytesIO(base64.b64decode(artifact["data"])), mode="r:gz") as t:
    text = b"".join(t.extractfile(n).read() for n in t.getnames() if t.extractfile(n))
  assert hex_token.encode() not in text
  assert b"BEGIN OPENSSH PRIVATE KEY" not in text
  assert b"abc123" not in text
  assert b"<redacted" in text


def test_diagnostics_keeps_git_sha(monkeypatch):
  sha = "0123456789abcdef0123456789abcdef01234567"  # 40-char git SHA
  monkeypatch.setattr(actions, "_run", lambda *a, **k: (0, sha))
  _, _, artifact = actions.diagnostics({})
  with tarfile.open(fileobj=io.BytesIO(base64.b64decode(artifact["data"])), mode="r:gz") as t:
    text = b"".join(t.extractfile(n).read() for n in t.getnames() if t.extractfile(n))
  assert sha.encode() in text


# --------------------------------------------------------------------------
# backup / restore
# --------------------------------------------------------------------------
def test_backup_returns_json_artifact(fake_params, monkeypatch):
  monkeypatch.setattr(settings_backup, "_firmware_version", lambda: "v")
  fake_params.values["IsMetric"] = True
  ok, msg, artifact = actions.backup({})
  assert ok is True and artifact["kind"] == "backup"
  assert artifact["label"].startswith("settings-") and artifact["label"].endswith(".json")
  doc = json.loads(base64.b64decode(artifact["data"]))
  assert doc["format"] == settings_backup.FORMAT and doc["params"] == {"IsMetric": True}


def test_restore_requires_artifact_id():
  ok, msg, _ = actions.restore({})
  assert ok is False and msg == "no artifact id"


def test_restore_rejects_non_boolean_dry_run(monkeypatch):
  ok, msg, _ = actions.restore({"artifact_id": "a", "dry_run": "yes"})
  assert ok is False and "dry_run" in msg


def test_restore_preview_writes_nothing(fake_params, monkeypatch):
  monkeypatch.setattr(settings_backup, "_firmware_version", lambda: "v")
  raw = settings_backup.build_backup()  # empty params
  monkeypatch.setattr(client, "download_artifact", lambda *a, **k: raw)
  ok, result, artifact = actions.restore({"artifact_id": "a"})
  assert ok is True and artifact is None
  assert "entries" in json.loads(result)
  assert fake_params.values == {}  # dry run wrote nothing


def test_restore_apply_writes_and_snapshots(fake_params, monkeypatch):
  monkeypatch.setattr(settings_backup, "_firmware_version", lambda: "v")
  raw = json.dumps({
    "format": settings_backup.FORMAT, "version": 1, "created_at": "2026-01-01T00:00:00Z",
    "source": {"device_id": "d"}, "params": {"Mads": True, "GithubSshKeys": "x"},
  }).encode()
  monkeypatch.setattr(client, "download_artifact", lambda *a, **k: raw)
  ok, result, artifact = actions.restore({"artifact_id": "a", "dry_run": False})
  assert ok is True
  out = json.loads(result)
  assert out == {"applied": 1, "skipped": 1, "unchanged": 0, "failed": [], "reboot_recommended": True}
  assert fake_params.values["Mads"] is True
  assert artifact["kind"] == "backup" and artifact["label"].startswith("pre-restore-")


def test_restore_apply_refuses_when_onroad(fake_params, monkeypatch):
  monkeypatch.setattr(actions, "Params", _OnroadParams)
  raw = json.dumps({"format": settings_backup.FORMAT, "version": 1, "created_at": "z",
                    "source": {}, "params": {"Mads": True}}).encode()
  monkeypatch.setattr(client, "download_artifact", lambda *a, **k: raw)
  ok, msg, _ = actions.restore({"artifact_id": "a", "dry_run": False})
  assert ok is False and msg == actions.ONROAD_MSG


def test_restore_rejects_bad_backup(monkeypatch):
  monkeypatch.setattr(client, "download_artifact", lambda *a, **k: b"not a backup")
  ok, msg, _ = actions.restore({"artifact_id": "a"})
  assert ok is False and "invalid backup" in msg


# --------------------------------------------------------------------------
# legacy cleanup / registry
# --------------------------------------------------------------------------
def test_cleanup_legacy_prerestore(tmp_path, monkeypatch):
  monkeypatch.setattr(config, "STATE_DIR", str(tmp_path))
  (tmp_path / "prerestore-1.tgz").write_bytes(b"x")
  (tmp_path / "keep.json").write_text("{}")
  assert actions.cleanup_legacy_prerestore() == 1
  assert not (tmp_path / "prerestore-1.tgz").exists()
  assert (tmp_path / "keep.json").exists()


def test_cleanup_stale_restart_flag(tmp_path, monkeypatch):
  monkeypatch.setattr(config, "STATE_DIR", str(tmp_path))
  (tmp_path / "tylerpilot_restart_manager").write_text("")
  assert actions.cleanup_stale_restart_flag() is True
  assert not (tmp_path / "tylerpilot_restart_manager").exists()
  # Idempotent: a missing flag is not an error.
  assert actions.cleanup_stale_restart_flag() is False


def test_cleanup_legacy_tunnel_key(tmp_path, monkeypatch):
  monkeypatch.setattr(config, "STATE_DIR", str(tmp_path))
  (tmp_path / "tylerpilot_tunnel").write_text("PRIVATE")
  (tmp_path / "tylerpilot_tunnel.pub").write_text("ssh-ed25519 PUB")
  (tmp_path / "tylerpilot_known_hosts").write_text("host key")
  (tmp_path / "keep.json").write_text("{}")
  assert actions.cleanup_legacy_tunnel_key() == 3
  assert not (tmp_path / "tylerpilot_tunnel").exists()
  assert not (tmp_path / "tylerpilot_tunnel.pub").exists()
  assert not (tmp_path / "tylerpilot_known_hosts").exists()
  assert (tmp_path / "keep.json").exists()
  # Idempotent: nothing left to remove.
  assert actions.cleanup_legacy_tunnel_key() == 0


def test_handlers_registry():
  for name in ("reboot", "poweroff", "update", "location", "trips", "diagnostics", "backup", "restore"):
    assert name in actions.HANDLERS
  for removed in ("restart_manager", "param_get", "param_set"):
    assert removed not in actions.HANDLERS
