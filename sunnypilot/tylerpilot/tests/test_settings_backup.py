from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from openpilot.sunnypilot.tylerpilot import settings_backup

HEADER = Path(__file__).resolve().parents[3] / "common" / "params_keys.h"
_TYPES = ("STRING", "BOOL", "INT", "FLOAT", "TIME", "JSON", "BYTES")


def _registry() -> dict[str, str]:
  """Parse common/params_keys.h -> {key: declared type name}."""
  src = HEADER.read_text()
  out: dict[str, str] = {}
  for key, body in re.findall(r'\{\s*"([^"]+)"\s*,\s*\{([^}]*)\}\s*\}', src):
    typ = next((t for t in _TYPES if re.search(r"\b" + t + r"\b", body)), "?")
    out[key] = typ.lower()
  return out


def _backup_keys() -> set[str]:
  src = HEADER.read_text()
  return {k for k, body in re.findall(r'\{\s*"([^"]+)"\s*,\s*\{([^}]*)\}\s*\}', src) if "BACKUP" in body}


def _doc(params: dict) -> dict:
  return {
    "format": settings_backup.FORMAT,
    "version": settings_backup.VERSION,
    "created_at": "2026-01-01T00:00:00Z",
    "source": {"device_id": "d", "dongle_id": "x", "name": "n",
               "firmware_version": "v", "branch": "b"},
    "params": params,
  }


# --------------------------------------------------------------------------
# allow/deny lists stay honest against the registry
# --------------------------------------------------------------------------
def test_allowlist_and_denylist_are_disjoint():
  assert set(settings_backup.ALLOWLIST) & set(settings_backup.DENYLIST) == set()


def test_every_backup_key_is_classified():
  classified = set(settings_backup.ALLOWLIST) | set(settings_backup.DENYLIST)
  assert classified == _backup_keys()


def test_allowlist_keys_exist_in_registry():
  reg = _registry()
  assert [k for k in settings_backup.ALLOWLIST if k not in reg] == []


def test_allowlist_types_match_registry():
  reg = _registry()
  mismatched = {k: (settings_backup._TYPES.get(k), reg[k])
                for k in settings_backup.ALLOWLIST if settings_backup._TYPES.get(k) != reg[k]}
  assert mismatched == {}


def test_denylist_keys_exist_in_registry():
  reg = _registry()
  assert [k for k in settings_backup.DENYLIST if k not in reg] == []


def test_confirm_required_keys_are_allowlisted():
  assert [k for k in settings_backup.CONFIRM_REQUIRED if k not in settings_backup.ALLOWLIST] == []


def test_alpha_longitudinal_is_denied():
  assert "AlphaLongitudinalEnabled" in settings_backup.DENYLIST
  assert "AlphaLongitudinalEnabled" not in settings_backup.ALLOWLIST


# --------------------------------------------------------------------------
# build / parse
# --------------------------------------------------------------------------
def test_build_backup_is_deterministic_and_typed(fake_params, monkeypatch):
  monkeypatch.setattr(settings_backup, "_firmware_version", lambda: "v")
  fake_params.values.update({"IsMetric": True, "GsmApn": "internet", "CameraOffset": 0.5})
  data = settings_backup.build_backup()
  doc = json.loads(data)
  assert doc["format"] == settings_backup.FORMAT
  assert doc["version"] == settings_backup.VERSION
  assert doc["created_at"].endswith("Z")
  assert doc["params"] == {"CameraOffset": 0.5, "GsmApn": "internet", "IsMetric": True}
  assert list(doc["params"]) == sorted(doc["params"])


def test_build_backup_skips_unset(fake_params, monkeypatch):
  monkeypatch.setattr(settings_backup, "_firmware_version", lambda: "v")
  assert json.loads(settings_backup.build_backup())["params"] == {}


def test_parse_roundtrip(fake_params):
  raw = json.dumps(_doc({"IsMetric": True})).encode()
  assert settings_backup.parse_backup(raw)["params"] == {"IsMetric": True}


def test_parse_rejects_wrong_format():
  raw = json.dumps({"format": "other", "version": 1, "created_at": "z", "source": {}, "params": {}}).encode()
  with pytest.raises(settings_backup.BackupError, match="format"):
    settings_backup.parse_backup(raw)


def test_parse_rejects_wrong_version():
  doc = _doc({})
  doc["version"] = 2
  with pytest.raises(settings_backup.BackupError, match="version"):
    settings_backup.parse_backup(json.dumps(doc).encode())


def test_parse_rejects_oversize():
  raw = b"x" * (settings_backup.MAX_BACKUP_BYTES + 1)
  with pytest.raises(settings_backup.BackupError, match="too large"):
    settings_backup.parse_backup(raw)


def test_parse_rejects_non_json():
  with pytest.raises(settings_backup.BackupError, match="JSON"):
    settings_backup.parse_backup(b"{not json")


def test_parse_rejects_missing_params():
  doc = _doc({})
  doc.pop("params")
  with pytest.raises(settings_backup.BackupError, match="params"):
    settings_backup.parse_backup(json.dumps(doc).encode())


def test_parse_rejects_non_finite_number():
  raw = b'{"format":"tylerpilot-settings","version":1,"created_at":"z","source":{},"params":{"CameraOffset":NaN}}'
  with pytest.raises(settings_backup.BackupError, match="non-finite"):
    settings_backup.parse_backup(raw)


def test_parse_rejects_null_value():
  doc = _doc({"IsMetric": None})
  with pytest.raises(settings_backup.BackupError, match="unsupported"):
    settings_backup.parse_backup(json.dumps(doc).encode())


# --------------------------------------------------------------------------
# diff
# --------------------------------------------------------------------------
def test_diff_classifies_entries(fake_params, monkeypatch):
  fake_params.values["IsMetric"] = True
  monkeypatch.setattr(settings_backup, "param_exists", lambda k: True)
  doc = _doc({
    "IsMetric": True,                       # same
    "Mads": False,                          # change
    "GsmApn": "internet",                   # change
    "GithubSshKeys": "secret",              # denied
    "NotARealParam": 1,                     # not allowlisted
    "MadsSteeringMode": "wrong-type",       # wrong type
    "LanguageSetting": "x" * 20000,         # oversize
  })
  by_key = {e["key"]: e for e in settings_backup.diff(doc)}
  assert by_key["IsMetric"]["status"] == "same"
  assert by_key["Mads"]["status"] == "change"
  assert by_key["GsmApn"]["category"] == "Network"
  assert by_key["GithubSshKeys"]["status"] == "skipped"
  assert "credential" in by_key["GithubSshKeys"]["reason"]
  assert by_key["NotARealParam"]["reason"] == "not in allowlist"
  assert by_key["MadsSteeringMode"]["reason"] == "expected int"
  assert "exceeds" in by_key["LanguageSetting"]["reason"]


def test_diff_unknown_parameter(fake_params, monkeypatch):
  monkeypatch.setattr(settings_backup, "param_exists", lambda k: False)
  entry = settings_backup.diff(_doc({"IsMetric": True}))[0]
  assert entry["status"] == "skipped"
  assert entry["reason"] == "unknown parameter"


def test_diff_experimental_mode_skipped_until_confirmed(fake_params, monkeypatch):
  monkeypatch.setattr(settings_backup, "param_exists", lambda k: True)
  entry = settings_backup.diff(_doc({"ExperimentalMode": True}))[0]
  assert entry["status"] == "skipped"
  assert entry["reason"] == settings_backup.CONFIRM_REQUIRED["ExperimentalMode"]


def test_diff_experimental_mode_allowed_once_confirmed(fake_params, monkeypatch):
  monkeypatch.setattr(settings_backup, "param_exists", lambda k: True)
  fake_params.values["ExperimentalModeConfirmed"] = True
  entry = settings_backup.diff(_doc({"ExperimentalMode": True}))[0]
  assert entry["status"] == "change"


def test_diff_experimental_mode_false_is_allowed(fake_params, monkeypatch):
  monkeypatch.setattr(settings_backup, "param_exists", lambda k: True)
  entry = settings_backup.diff(_doc({"ExperimentalMode": False}))[0]
  assert entry["status"] == "change"


def test_diff_toyota_toggles_require_on_device_enable(fake_params, monkeypatch):
  monkeypatch.setattr(settings_backup, "param_exists", lambda k: True)
  by_key = {e["key"]: e for e in settings_backup.diff(
    _doc({"ToyotaStopAndGoHack": True, "ToyotaEnforceStockLongitudinal": True}))}
  assert by_key["ToyotaStopAndGoHack"]["status"] == "skipped"
  assert by_key["ToyotaEnforceStockLongitudinal"]["status"] == "skipped"


def test_build_backup_uses_registry_defaults(fake_params, monkeypatch):
  monkeypatch.setattr(settings_backup, "_firmware_version", lambda: "v")
  fake_params.defaults["IsMetric"] = True
  fake_params.defaults["LanguageSetting"] = "en"
  doc = json.loads(settings_backup.build_backup())
  assert doc["params"] == {"IsMetric": True, "LanguageSetting": "en"}


def test_diff_current_uses_registry_defaults(fake_params, monkeypatch):
  monkeypatch.setattr(settings_backup, "param_exists", lambda k: True)
  fake_params.defaults["IsMetric"] = True
  entry = settings_backup.diff(_doc({"IsMetric": True}))[0]
  assert entry["status"] == "same"
  assert entry["current"] is True


# --------------------------------------------------------------------------
# apply
# --------------------------------------------------------------------------
def test_apply_writes_only_changes(fake_params, monkeypatch):
  monkeypatch.setattr(settings_backup, "param_exists", lambda k: True)
  fake_params.values["IsMetric"] = True
  counts = settings_backup.apply(_doc({"IsMetric": True, "Mads": True, "GithubSshKeys": "x"}))
  assert counts == {"applied": 1, "skipped": 1, "unchanged": 1, "failed": []}
  assert fake_params.values["Mads"] is True
  assert fake_params.values["IsMetric"] is True


def test_apply_reports_write_failures(fake_params, monkeypatch):
  monkeypatch.setattr(settings_backup, "param_exists", lambda k: True)

  def _boom(key, value, *args, **kwargs):
    raise RuntimeError("disk full")

  monkeypatch.setattr(fake_params, "put", _boom)
  counts = settings_backup.apply(_doc({"Mads": True}))
  assert counts["applied"] == 0
  assert counts["failed"] == [{"key": "Mads", "error": "disk full"}]


def test_apply_coerces_int_to_float(fake_params, monkeypatch):
  monkeypatch.setattr(settings_backup, "param_exists", lambda k: True)
  settings_backup.apply(_doc({"CameraOffset": 1}))
  assert fake_params.values["CameraOffset"] == 1.0
  assert isinstance(fake_params.values["CameraOffset"], float)
