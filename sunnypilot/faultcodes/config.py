"""
Copyright (c) 2021-, Haibin Wen, sunnypilot, and a number of other contributors.

This file is part of sunnypilot and is licensed under the MIT License.
See the LICENSE.md file in the root directory for more details.

Fault code reader: catalog and snapshot I/O.

The reader is strictly read-only. It surfaces the fault flags openpilot already
parses from the car (carState), the panda's own faults, the device thermal status
and recent fault events.

Real OBD-II trouble codes (P/C/B/U) are deliberately NOT read: querying them
needs the panda in ELM327 service mode, which means stopping openpilot, so the
device only ever reports the live fault state it can already see.

State is a JSON file rather than Params keys: Params only accepts keys compiled
into the prebuilt params library, and this branch ships no build system.
"""
from __future__ import annotations

import json
import os

STATE_DIR = "/data/community"
VALUES_PATH = os.path.join(STATE_DIR, "fault_codes.json")

# Boolean fault flags openpilot already decodes from the car (see the carstate.py
# of each brand). Shown as "active faults" when true.
VEHICLE_FAULTS = [
  ("steerFaultTemporary", "Steering fault (temporary)", "EPS reports a temporary LKA/LTA fault"),
  ("steerFaultPermanent", "Steering fault (permanent)", "EPS reports a permanent LKA/LTA fault"),
  ("accFaulted", "ACC faulted", "Adaptive cruise reports a fault and disallows engagement"),
  ("carFaultedNonCritical", "Car faulted (non-critical)", "An ECU is faulted but the car remains controllable"),
  ("vehicleSensorsInvalid", "Vehicle sensors invalid", "Wheel speed or steering angle sensor fault"),
  ("espDisabled", "ESP disabled", "Stability control is off or faulted"),
  ("invalidLkasSetting", "LKAS misconfigured", "Stock LKAS setting does not match the car"),
  ("canTimeout", "CAN timeout", "CAN bus dropped out"),
  ("lowSpeedAlert", "Low-speed steering limit", "Steering control lost below the minimum speed"),
]

# Informational status shown next to the faults (true usually means "normal").
VEHICLE_STATUS = [
  ("canValid", "CAN valid", "CAN counters and checksums are valid"),
  ("espActive", "ESP active", "Stability control is currently intervening"),
]

NOTE = ("Live fault state only. OBD-II trouble codes (P/C/B/U) are not read: " +
        "querying them requires the panda in service mode, with openpilot stopped.")


def read_snapshot() -> dict:
  """Last published snapshot, for the UI and web. Never blocks."""
  try:
    with open(VALUES_PATH) as f:
      data = json.load(f)
  except (OSError, ValueError):
    data = {}
  return data if isinstance(data, dict) else {}
