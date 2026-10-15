from __future__ import annotations

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


def test_heartbeat_401_raises_revoked(monkeypatch):
  monkeypatch.setattr(client, "_request", lambda *a, **k: (401, b'{"error":"unauthenticated"}', "fp"))
  with pytest.raises(client.RevokedError):
    client.heartbeat("h", 1, "tok", "fp", {})


def test_poll_401_raises_revoked(monkeypatch):
  monkeypatch.setattr(client, "_request", lambda *a, **k: (401, b"{}", "fp"))
  with pytest.raises(client.RevokedError):
    client.poll("h", 1, "tok", "fp")


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
    key.write_text("NEW-PRIVATE")
    pub.write_text("ssh-ed25519 NEWKEY")

  monkeypatch.setattr(client.subprocess, "run", fake_run)

  assert client.rotate_tunnel_key() == "ssh-ed25519 NEWKEY"
  assert key.read_text() == "NEW-PRIVATE"
  assert pub.read_text() == "ssh-ed25519 NEWKEY"
  assert calls and calls[0][0] == "ssh-keygen"
