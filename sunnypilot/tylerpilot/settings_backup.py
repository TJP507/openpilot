"""
TylerPilot settings backup/restore.

A backup is a small UTF-8 JSON document holding an explicit **allowlist** of
user settings. It never contains tokens, keys, identity, logs, or files under
/data/community: only the keys below are read, and only through the Params API.

    {"format": "tylerpilot-settings", "version": 1,
     "created_at": "<UTC ISO-8601 with Z>",
     "source": {device_id, dongle_id, name, firmware_version, branch},
     "params": {key: value}}

Values are JSON-native and match each param's declared type (bool/int/float/
string/json). Restore is two-phase: `diff()` classifies every incoming entry
(change / same / skipped) without writing anything, and `apply()` writes only
the "change" entries. Restore never extracts files.

The allow/deny split is validated against `common/params_keys.h` by the tests,
so an upstream change to the BACKUP flag (or a key's type) fails the suite.
"""
from __future__ import annotations

import json
import math
from datetime import UTC, datetime

from openpilot.common.params import Params

from openpilot.sunnypilot.tylerpilot import config

FORMAT = "tylerpilot-settings"
VERSION = 1

# A whole backup, and any single value, are capped so a crafted artifact cannot
# exhaust memory or wedge the UI.
MAX_BACKUP_BYTES = 256 * 1024
MAX_VALUE_BYTES = 16 * 1024

# Param key -> category, for every BACKUP-flagged key we are willing to move
# between devices. See DENYLIST for the BACKUP keys we refuse.
ALLOWLIST: dict[str, str] = {
  "AlwaysOnDM": "Driving",
  "AutoLaneChangeBsmDelay": "Lateral",
  "AutoLaneChangeTimer": "Lateral",
  "BlindSpot": "Lateral",
  "BlinkerLateralReengageDelay": "Lateral",
  "BlinkerMinLateralControlSpeed": "Lateral",
  "BlinkerPauseLateralControl": "Lateral",
  "Brightness": "Display",
  "CameraOffset": "Vehicle",
  "ChevronInfo": "Display",
  "CustomAccIncrementsEnabled": "Longitudinal",
  "CustomAccLongPressIncrement": "Longitudinal",
  "CustomAccShortPressIncrement": "Longitudinal",
  "CustomTorqueParams": "Lateral",
  "DevUIInfo": "Display",
  "DisablePowerDown": "Power",
  "DisengageOnAccelerator": "Driving",
  "DynamicExperimentalControl": "Driving",
  "EnableSunnylinkUploader": "Network",
  "EnforceTorqueControl": "Lateral",
  "ExperimentalMode": "Driving",
  "GreenLightAlert": "Driving",
  "GsmApn": "Network",
  "GsmMetered": "Network",
  "GsmRoaming": "Network",
  "HideVEgoUI": "Display",
  "HyundaiLongitudinalTuning": "Longitudinal",
  "IntelligentCruiseButtonManagement": "Longitudinal",
  "InteractivityTimeout": "Display",
  "IsLdwEnabled": "Driving",
  "IsMetric": "Display",
  "LagdToggle": "Lateral",
  "LagdToggleDelay": "Lateral",
  "LaneTurnDesire": "Lateral",
  "LaneTurnValue": "Lateral",
  "LanguageSetting": "Display",
  "LeadDepartAlert": "Driving",
  "LiveTorqueParamsRelaxedToggle": "Lateral",
  "LiveTorqueParamsToggle": "Lateral",
  "LongitudinalPersonality": "Longitudinal",
  "Mads": "Lateral",
  "MadsMainCruiseAllowed": "Lateral",
  "MadsSteeringMode": "Lateral",
  "MadsUnifiedEngagementMode": "Lateral",
  "MaxTimeOffroad": "Power",
  "ModelManager_Favs": "Models",
  "NetworkMetered": "Network",
  "NeuralNetworkLateralControl": "Lateral",
  "OnroadScreenOffBrightness": "Display",
  "OnroadScreenOffTimer": "Display",
  "OnroadUploads": "Network",
  "OpenpilotEnabledToggle": "Driving",
  "PlanplusControl": "Longitudinal",
  "QuickBootToggle": "Power",
  "QuietMode": "Display",
  "RainbowMode": "Display",
  "RecordAudio": "Recording",
  "RecordAudioFeedback": "Recording",
  "RecordFront": "Recording",
  "RoadNameToggle": "Display",
  "RocketFuel": "Driving",
  "ShowAdvancedControls": "Display",
  "ShowTurnSignals": "Display",
  "SmartCruiseControlMap": "Longitudinal",
  "SmartCruiseControlVision": "Longitudinal",
  "SpeedLimitMode": "Driving",
  "SpeedLimitOffsetType": "Driving",
  "SpeedLimitPolicy": "Driving",
  "SpeedLimitValueOffset": "Driving",
  "StandstillTimer": "Display",
  "SubaruStopAndGo": "Longitudinal",
  "SubaruStopAndGoManualParkingBrake": "Longitudinal",
  "TeslaCoopSteering": "Lateral",
  "TorqueBar": "Display",
  "TorqueControlTune": "Lateral",
  "TorqueParamsOverrideEnabled": "Lateral",
  "TorqueParamsOverrideFriction": "Lateral",
  "TorqueParamsOverrideLatAccelFactor": "Lateral",
  "ToyotaEnforceStockLongitudinal": "Longitudinal",
  "ToyotaStopAndGoHack": "Longitudinal",
  "TrueVEgoUI": "Display",
}

# BACKUP-flagged keys we refuse to back up or restore, with the reason shown to
# the user. These are credentials, identity, security-sensitive toggles,
# per-device calibration/state, caches, or one-shot migration markers.
DENYLIST: dict[str, str] = {
  "AdbEnabled": "Enables ADB debug access; security-sensitive, per device.",
  "AlphaLongitudinalEnabled": "Alpha longitudinal must be enabled on the device so its safety warning is acknowledged.",
  "CarPlatformBundle": "Vehicle fingerprint tied to this car/platform.",
  "DeviceBootMode": "Device boot/partition mode; recovery-sensitive, per device.",
  "DisableUpdates": "Blocks over-the-air updates; device fleet management, not a user setting.",
  "EnableCopyparty": "Runs a Copyparty file server (network/service exposure); per device.",
  "EnableGithubRunner": "Runs a GitHub Actions runner (network/service exposure); per device.",
  "ExperimentalModeConfirmed": "Safety acknowledgment that must be accepted per device.",
  "GithubSshKeys": "SSH keys are a credential; never copied between devices.",
  "GithubUsername": "Account identity; not a device setting.",
  "LiveDelay": "Per-device audio calibration captured on this hardware.",
  "ModelManager_ModelsCache": "Regenerated model cache; large and device-local.",
  "OnroadScreenOffBrightnessMigrated": "One-shot migration marker; meaningless on another device.",
  "OnroadScreenOffTimerMigrated": "One-shot migration marker; meaningless on another device.",
  "SecOCKey": "Vehicle secure-onboard-communication key; never leaves the car.",
  "SshEnabled": "Enables remote SSH access; security-sensitive, per device.",
}

# Allowlisted toggles whose *enable* shows a safety confirmation dialog on the
# device. Restoring them as true would bypass that notice, so diff() skips them
# (ExperimentalMode is allowed once ExperimentalModeConfirmed is already true on
# this device).
CONFIRM_REQUIRED: dict[str, str] = {
  "ExperimentalMode": "Turn on Experimental Mode once on the device to accept its safety notice",
  "ToyotaEnforceStockLongitudinal": "Enable on the device to accept its safety notice",
  "ToyotaStopAndGoHack": "Enable on the device to accept its safety notice",
}

# Declared type of every ALLOWLIST key, mirroring common/params_keys.h. The
# tests assert this matches the registry so an upstream type change is caught.
_TYPES: dict[str, str] = {
  "AlwaysOnDM": "bool",
  "AutoLaneChangeBsmDelay": "bool",
  "AutoLaneChangeTimer": "int",
  "BlindSpot": "bool",
  "BlinkerLateralReengageDelay": "int",
  "BlinkerMinLateralControlSpeed": "int",
  "BlinkerPauseLateralControl": "int",
  "Brightness": "int",
  "CameraOffset": "float",
  "ChevronInfo": "int",
  "CustomAccIncrementsEnabled": "bool",
  "CustomAccLongPressIncrement": "int",
  "CustomAccShortPressIncrement": "int",
  "CustomTorqueParams": "bool",
  "DevUIInfo": "int",
  "DisablePowerDown": "bool",
  "DisengageOnAccelerator": "bool",
  "DynamicExperimentalControl": "bool",
  "EnableSunnylinkUploader": "bool",
  "EnforceTorqueControl": "bool",
  "ExperimentalMode": "bool",
  "GreenLightAlert": "bool",
  "GsmApn": "string",
  "GsmMetered": "bool",
  "GsmRoaming": "bool",
  "HideVEgoUI": "bool",
  "HyundaiLongitudinalTuning": "int",
  "IntelligentCruiseButtonManagement": "bool",
  "InteractivityTimeout": "int",
  "IsLdwEnabled": "bool",
  "IsMetric": "bool",
  "LagdToggle": "bool",
  "LagdToggleDelay": "float",
  "LaneTurnDesire": "bool",
  "LaneTurnValue": "float",
  "LanguageSetting": "string",
  "LeadDepartAlert": "bool",
  "LiveTorqueParamsRelaxedToggle": "bool",
  "LiveTorqueParamsToggle": "bool",
  "LongitudinalPersonality": "int",
  "Mads": "bool",
  "MadsMainCruiseAllowed": "bool",
  "MadsSteeringMode": "int",
  "MadsUnifiedEngagementMode": "bool",
  "MaxTimeOffroad": "int",
  "ModelManager_Favs": "string",
  "NetworkMetered": "bool",
  "NeuralNetworkLateralControl": "bool",
  "OnroadScreenOffBrightness": "int",
  "OnroadScreenOffTimer": "int",
  "OnroadUploads": "bool",
  "OpenpilotEnabledToggle": "bool",
  "PlanplusControl": "float",
  "QuickBootToggle": "bool",
  "QuietMode": "bool",
  "RainbowMode": "bool",
  "RecordAudio": "bool",
  "RecordAudioFeedback": "bool",
  "RecordFront": "bool",
  "RoadNameToggle": "bool",
  "RocketFuel": "bool",
  "ShowAdvancedControls": "bool",
  "ShowTurnSignals": "bool",
  "SmartCruiseControlMap": "bool",
  "SmartCruiseControlVision": "bool",
  "SpeedLimitMode": "int",
  "SpeedLimitOffsetType": "int",
  "SpeedLimitPolicy": "int",
  "SpeedLimitValueOffset": "int",
  "StandstillTimer": "bool",
  "SubaruStopAndGo": "bool",
  "SubaruStopAndGoManualParkingBrake": "bool",
  "TeslaCoopSteering": "bool",
  "TorqueBar": "bool",
  "TorqueControlTune": "float",
  "TorqueParamsOverrideEnabled": "bool",
  "TorqueParamsOverrideFriction": "float",
  "TorqueParamsOverrideLatAccelFactor": "float",
  "ToyotaEnforceStockLongitudinal": "bool",
  "ToyotaStopAndGoHack": "bool",
  "TrueVEgoUI": "bool",
}

_JSON_TYPES = ("bool", "int", "float", "string", "json")


class BackupError(ValueError):
  """A backup artifact is not a valid, supported TylerPilot settings backup."""


# --------------------------------------------------------------------------
# Params seam (narrow wrappers, so tests can drive the logic without the
# compiled binding)
# --------------------------------------------------------------------------
def param_exists(key: str) -> bool:
  """Whether the params registry knows this key."""
  try:
    Params().check_key(key)
    return True
  except Exception:
    # Without the compiled binding (tests), trust our header-derived allowlist.
    return key in _TYPES


def param_type(key: str) -> str | None:
  """Declared type name for an allowlisted key ("bool"/"int"/"float"/"string")."""
  return _TYPES.get(key)


def read_param(key: str):
  """Current value (falling back to the registry default) or None if unset.

  return_default=True so a never-touched setting is captured at its default;
  otherwise a restore would leave the target's differing value in place.
  """
  try:
    return Params().get(key, return_default=True)
  except Exception:
    return None


def write_param(key: str, value) -> None:
  """Write and block until the value is on disk."""
  Params().put(key, value, block=True)


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------
def _utc_now() -> str:
  return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _json_native(value) -> bool:
  return isinstance(value, (bool, int, float, str, dict, list))


def _value_size(value) -> int:
  return len(json.dumps(value, separators=(",", ":")).encode("utf-8"))


def _as_str(value) -> str:
  return value if isinstance(value, str) else ""


def _firmware_version() -> str:
  try:
    from openpilot.system.version import get_version
    return str(get_version())
  except Exception:
    return ""


def _source_info() -> dict:
  return {
    "device_id": _as_str(config.get("device_id")),
    "dongle_id": _as_str(read_param("DongleId")),
    "name": _as_str(config.get("name")),
    "firmware_version": _firmware_version(),
    "branch": _as_str(read_param("GitBranch")),
  }


def _value_matches(expected: str | None, value) -> bool:
  if expected == "bool":
    return isinstance(value, bool)
  if expected == "int":
    return isinstance(value, int) and not isinstance(value, bool)
  if expected == "float":
    return isinstance(value, (int, float)) and not isinstance(value, bool)
  if expected == "string":
    return isinstance(value, str)
  if expected == "json":
    return isinstance(value, (dict, list))
  return False


def _coerce(value, expected: str | None):
  if expected == "float" and isinstance(value, int) and not isinstance(value, bool):
    return float(value)
  return value


def _validate_value(key: str, value) -> None:
  if isinstance(value, (bool, int, str, dict, list)):
    return
  if isinstance(value, float):
    if math.isfinite(value):
      return
    raise BackupError(f"{key}: non-finite number")
  raise BackupError(f"{key}: unsupported value type {type(value).__name__}")


# --------------------------------------------------------------------------
# build / parse
# --------------------------------------------------------------------------
def build_backup() -> bytes:
  """Snapshot the allowlisted settings as a compact JSON document."""
  params: dict = {}
  for key in ALLOWLIST:
    value = read_param(key)
    if value is None or not _json_native(value):
      continue
    params[key] = value
  doc = {
    "format": FORMAT,
    "version": VERSION,
    "created_at": _utc_now(),
    "source": _source_info(),
    "params": params,
  }
  return json.dumps(doc, sort_keys=True, separators=(",", ":")).encode("utf-8")


def parse_backup(raw: bytes) -> dict:
  """Validate raw artifact bytes and return the parsed document."""
  if not isinstance(raw, (bytes, bytearray)):
    raise BackupError("backup is not bytes")
  if len(raw) > MAX_BACKUP_BYTES:
    raise BackupError(f"backup too large ({len(raw)} > {MAX_BACKUP_BYTES} bytes)")
  try:
    doc = json.loads(bytes(raw).decode("utf-8"))
  except (UnicodeDecodeError, ValueError) as e:
    raise BackupError(f"not valid UTF-8 JSON: {e}") from e
  if not isinstance(doc, dict):
    raise BackupError("backup root is not an object")
  if doc.get("format") != FORMAT:
    raise BackupError(f"unexpected format {doc.get('format')!r}")
  if doc.get("version") != VERSION:
    raise BackupError(f"unsupported version {doc.get('version')!r}")
  if not isinstance(doc.get("created_at"), str):
    raise BackupError("missing created_at")
  if not isinstance(doc.get("source"), dict):
    raise BackupError("missing source")
  params = doc.get("params")
  if not isinstance(params, dict):
    raise BackupError("missing params")
  for key, value in params.items():
    if not isinstance(key, str):
      raise BackupError("param key is not a string")
    _validate_value(key, value)
  return doc


# --------------------------------------------------------------------------
# diff / apply
# --------------------------------------------------------------------------
def _confirmed_on_device(key: str) -> bool:
  """Whether the on-device safety acknowledgment for `key` is already given.

  Only ExperimentalMode has a persisted confirmation flag; the Toyota toggles
  show their dialog every time, so they can never be confirmed remotely.
  """
  return key == "ExperimentalMode" and bool(read_param("ExperimentalModeConfirmed"))


def diff(backup: dict) -> list[dict]:
  """Classify every incoming entry without writing anything.

  Each entry is {key, category, current, incoming, status, reason?} where
  status is "change", "same", or "skipped".
  """
  entries: list[dict] = []
  for key in sorted(backup["params"]):
    value = backup["params"][key]
    entry = {
      "key": key,
      "category": ALLOWLIST.get(key),
      "current": None,
      "incoming": value,
      "status": "change",
    }
    if key in DENYLIST:
      entry["status"] = "skipped"
      entry["reason"] = DENYLIST[key]
    elif key not in ALLOWLIST:
      entry["status"] = "skipped"
      entry["reason"] = "not in allowlist"
    elif not param_exists(key):
      entry["status"] = "skipped"
      entry["reason"] = "unknown parameter"
    elif not _value_matches(param_type(key), value):
      entry["status"] = "skipped"
      entry["reason"] = f"expected {param_type(key)}"
    elif _value_size(value) > MAX_VALUE_BYTES:
      entry["status"] = "skipped"
      entry["reason"] = f"value exceeds {MAX_VALUE_BYTES} bytes"
    elif key in CONFIRM_REQUIRED and value is True and not _confirmed_on_device(key):
      entry["status"] = "skipped"
      entry["reason"] = CONFIRM_REQUIRED[key]
    else:
      current = read_param(key)
      entry["current"] = current if _json_native(current) else None
      entry["status"] = "same" if current == value else "change"
    entries.append(entry)
  return entries


def apply(backup: dict) -> dict:
  """Write only the "change" entries; report per-key failures.

  Returns {"applied", "skipped", "unchanged", "failed": [{key, error}, ...]}.
  A write that raises is reported in "failed" (never counted as skipped).
  """
  applied = skipped = unchanged = 0
  failed: list[dict] = []
  for entry in diff(backup):
    if entry["status"] == "skipped":
      skipped += 1
    elif entry["status"] == "same":
      unchanged += 1
    else:
      try:
        write_param(entry["key"], _coerce(entry["incoming"], param_type(entry["key"])))
        applied += 1
      except Exception as e:
        failed.append({"key": entry["key"], "error": str(e)})
  return {"applied": applied, "skipped": skipped, "unchanged": unchanged, "failed": failed}
