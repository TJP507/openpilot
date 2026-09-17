"""
Copyright (c) 2021-, Haibin Wen, sunnypilot, and a number of other contributors.

This file is part of sunnypilot and is licensed under the MIT License.
See the LICENSE.md file in the root directory for more details.

Persistent configuration for the live CAN gauges.

A gauge is a small descriptor: where to read the value from, how to scale it,
and how to render it. Sources:

  carState | carControl | panda | device | gps   -> dotted path into that cereal
                                                    message (openpilot already
                                                    decoded it)
  can                                            -> "<MESSAGE>.<SIGNAL>" decoded
                                                    from the raw CAN stream using
                                                    the car's own DBC

Config is a JSON file rather than Params keys: Params only accepts keys compiled
into the prebuilt params library, and this branch ships no build system.
"""
from __future__ import annotations

import json
import os
import threading

STATE_DIR = "/data/community"
CONFIG_PATH = os.path.join(STATE_DIR, "can_gauges.json")
VALUES_PATH = os.path.join(STATE_DIR, "can_gauges_values.json")
CATALOG_PATH = os.path.join(STATE_DIR, "can_gauges_catalog.json")

DEFAULT_UPDATE_HZ = 10.0
_LOCK = threading.Lock()

# (id, label, source, key, unit, scale, min, max, style)
DEFAULT_GAUGES = [
  {"id": "speed", "label": "Speed", "source": "carState", "key": "vEgo",
   "unit": "mph", "scale": 2.23694, "min": 0, "max": 100, "style": "arc"},
  {"id": "rpm", "label": "RPM", "source": "can", "key": "ENGINE_RPM.RPM",
   "unit": "rpm", "scale": 1.0, "min": 0, "max": 6000, "style": "arc"},
  {"id": "steer_angle", "label": "Steer Angle", "source": "carState", "key": "steeringAngleDeg",
   "unit": "deg", "scale": 1.0, "min": -180, "max": 180, "style": "bar"},
  {"id": "steer_torque", "label": "Steer Torque", "source": "carState", "key": "steeringTorque",
   "unit": "", "scale": 1.0, "min": -400, "max": 400, "style": "bar"},
  {"id": "gas", "label": "Gas %", "source": "can", "key": "GAS_PEDAL.GAS_PEDAL",
   "unit": "%", "scale": 1.0, "min": 0, "max": 100, "style": "bar"},
  {"id": "brake", "label": "Brake", "source": "can", "key": "BRAKE_MODULE.BRAKE_PRESSURE",
   "unit": "", "scale": 1.0, "min": 0, "max": 100, "style": "bar"},
  {"id": "accel", "label": "Accel", "source": "carState", "key": "aEgo",
   "unit": "m/s2", "scale": 1.0, "min": -3, "max": 3, "style": "bar"},
  {"id": "battery", "label": "Battery", "source": "panda", "key": "voltage",
   "unit": "V", "scale": 0.001, "min": 10, "max": 15, "style": "value"},
  {"id": "cpu_temp", "label": "Max Temp", "source": "device", "key": "maxTempC",
   "unit": "C", "scale": 1.0, "min": 0, "max": 100, "style": "value"},
]

VALID_SOURCES = ("carState", "carControl", "panda", "device", "gps", "can")
VALID_STYLES = ("arc", "bar", "value")


def default_config() -> dict:
  return {"update_hz": DEFAULT_UPDATE_HZ, "show_onroad": True, "gauges": [dict(g) for g in DEFAULT_GAUGES]}


def _clean_gauge(g: dict) -> dict | None:
  try:
    source = str(g.get("source", ""))
    if source not in VALID_SOURCES or not g.get("key"):
      return None
    style = str(g.get("style", "value"))
    return {
      "id": str(g.get("id") or g["key"]).replace(" ", "_"),
      "label": str(g.get("label") or g["key"]),
      "source": source,
      "key": str(g["key"]),
      "unit": str(g.get("unit", "")),
      "scale": float(g.get("scale", 1.0)),
      "min": float(g.get("min", 0.0)),
      "max": float(g.get("max", 1.0)),
      "style": style if style in VALID_STYLES else "value",
    }
  except (TypeError, ValueError):
    return None


def load() -> dict:
  try:
    with open(CONFIG_PATH) as f:
      data = json.load(f)
  except (OSError, ValueError):
    data = None

  if not isinstance(data, dict):
    return default_config()

  cfg = default_config()
  if isinstance(data.get("update_hz"), (int, float)) and data["update_hz"] > 0:
    cfg["update_hz"] = max(1.0, min(float(data["update_hz"]), 50.0))
  if isinstance(data.get("show_onroad"), bool):
    cfg["show_onroad"] = data["show_onroad"]

  gauges = data.get("gauges")
  if isinstance(gauges, list) and gauges:
    cleaned = [_clean_gauge(g) for g in gauges if isinstance(g, dict)]
    cfg["gauges"] = [g for g in cleaned if g is not None]
  return cfg


def save(state: dict) -> dict:
  with _LOCK:
    os.makedirs(STATE_DIR, exist_ok=True)
    tmp = CONFIG_PATH + ".tmp"
    with open(tmp, "w") as f:
      json.dump(state, f, indent=2)
    os.replace(tmp, CONFIG_PATH)
  return state


def read_values() -> dict:
  """Last published snapshot, for the UI and web. Never blocks."""
  try:
    with open(VALUES_PATH) as f:
      data = json.load(f)
  except (OSError, ValueError):
    data = {}
  return data if isinstance(data, dict) else {}


def read_catalog() -> list:
  try:
    with open(CATALOG_PATH) as f:
      data = json.load(f)
  except (OSError, ValueError):
    data = []
  return data if isinstance(data, list) else []
