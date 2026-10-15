from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from openpilot.sunnypilot.tylerpilot import client, config


def test_normalize_pairing_code_accepts_dashes_and_spaces():
  assert client.normalize_pairing_code("1234-5678-9012") == "123456789012"
  assert client.normalize_pairing_code("1234 5678 9012") == "123456789012"
  assert client.normalize_pairing_code("123456789012") == "123456789012"
  # Anything that is not exactly 12 digits is rejected.
  assert client.normalize_pairing_code("1234-5678") == ""
  assert client.normalize_pairing_code("") == ""
  assert client.normalize_pairing_code("abcd-efgh-ijkl") == ""


def test_heartbeat_401_raises_auth_error_with_code(monkeypatch):
  body = b'{"error":{"code":"unauthenticated","message":"bad device token"}}'
  monkeypatch.setattr(client, "_request", lambda *a, **k: (401, body, "fp"))
  with pytest.raises(client.AuthError) as ei:
    client.heartbeat("h", 1, "tok", "fp", {})
  assert ei.value.code == "unauthenticated"


def test_poll_401_raises_auth_error_with_code(monkeypatch):
  body = b'{"error":{"code":"unauthenticated","message":"bad device token"}}'
  monkeypatch.setattr(client, "_request", lambda *a, **k: (401, body, "fp"))
  with pytest.raises(client.AuthError) as ei:
    client.poll("h", 1, "tok", "fp")
  assert ei.value.code == "unauthenticated"


def test_non_json_401_has_empty_code(monkeypatch):
  # A proxy's Basic-auth 401 is HTML, not our envelope.
  monkeypatch.setattr(client, "_request", lambda *a, **k: (401, b"<html>401</html>", "fp"))
  with pytest.raises(client.AuthError) as ei:
    client.heartbeat("h", 1, "tok", "fp", {})
  assert ei.value.code == ""


def test_heartbeat_non_200_raises_link_error(monkeypatch):
  monkeypatch.setattr(client, "_request", lambda *a, **k: (500, b'{"error":"boom"}', "fp"))
  with pytest.raises(client.LinkError):
    client.heartbeat("h", 1, "tok", "fp", {})


@pytest.fixture
def key_paths(tmp_path, monkeypatch):
  key = tmp_path / "tylerpilot_tunnel"
  pub = tmp_path / "tylerpilot_tunnel.pub"
  monkeypatch.setattr(config, "TUNNEL_KEY_PATH", str(key))
  monkeypatch.setattr(config, "TUNNEL_PUB_PATH", str(pub))
  return key, pub


def test_rotate_tunnel_key_replaces_existing(key_paths, monkeypatch):
  key, pub = key_paths
  key.write_text("OLD-PRIVATE")
  pub.write_text("ssh-ed25519 OLDKEY")
  calls: list = []

  def fake_run(cmd, **kwargs):
    calls.append(cmd)
    tmp = cmd[-1]
    Path(tmp).write_text("NEW-PRIVATE")
    Path(tmp + ".pub").write_text("ssh-ed25519 NEWKEY")

  monkeypatch.setattr(client.subprocess, "run", fake_run)

  assert client.rotate_tunnel_key() == "ssh-ed25519 NEWKEY"
  assert key.read_text() == "NEW-PRIVATE"
  assert pub.read_text() == "ssh-ed25519 NEWKEY"
  assert calls and calls[0][0] == "ssh-keygen"
  # The temp files are renamed away, not left behind.
  assert not Path(str(key) + ".new").exists()


def test_rotate_tunnel_key_failure_keeps_old_key(key_paths, monkeypatch):
  key, pub = key_paths
  key.write_text("OLD-PRIVATE")
  pub.write_text("ssh-ed25519 OLDKEY")

  def boom(cmd, **kwargs):
    raise subprocess.CalledProcessError(1, cmd)

  monkeypatch.setattr(client.subprocess, "run", boom)

  with pytest.raises(subprocess.CalledProcessError):
    client.rotate_tunnel_key()
  # The old key pair is untouched, so the device is never left keyless.
  assert key.read_text() == "OLD-PRIVATE"
  assert pub.read_text() == "ssh-ed25519 OLDKEY"
