from __future__ import annotations

import json

import pytest

from openpilot.sunnypilot.tylerpilot import client


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


def test_read_ssh_host_keys_reads_ed25519_first(tmp_path, monkeypatch):
  ed = tmp_path / "ssh_host_ed25519_key.pub"
  rsa = tmp_path / "ssh_host_rsa_key.pub"
  ed.write_text("ssh-ed25519 AAAAed25519 dev\n")
  rsa.write_text("ssh-rsa AAAArsa dev\n")
  monkeypatch.setattr(client, "SSH_HOST_KEY_PATHS", (str(ed), str(rsa)))
  assert client.read_ssh_host_keys() == ["ssh-ed25519 AAAAed25519 dev", "ssh-rsa AAAArsa dev"]


def test_read_ssh_host_keys_skips_missing_and_junk(tmp_path, monkeypatch):
  good = tmp_path / "good.pub"
  junk = tmp_path / "junk.pub"
  good.write_text("ssh-ed25519 AAAAok dev")
  junk.write_text("not a key")
  monkeypatch.setattr(client, "SSH_HOST_KEY_PATHS", (str(tmp_path / "missing.pub"), str(junk), str(good)))
  assert client.read_ssh_host_keys() == ["ssh-ed25519 AAAAok dev"]


def test_register_sends_ssh_host_keys(monkeypatch):
  captured: dict = {}

  def fake_request(host, port, method, path, headers=None, body=None, pin=None, timeout=15.0):
    captured["path"] = path
    captured["body"] = json.loads(body)
    return 200, b'{"device_id":"dev1","token":"tok"}', "fp"

  monkeypatch.setattr(client, "_request", fake_request)
  out = client.register("h", 7448, "123456789012", "Car", "uid", "v1", "dongle",
                        ["ssh-ed25519 AAAAone"])
  assert captured["path"] == "/api/v1/device/register"
  assert captured["body"]["ssh_host_keys"] == ["ssh-ed25519 AAAAone"]
  assert "tunnel_pubkey" not in captured["body"]
  assert out["device_id"] == "dev1"
