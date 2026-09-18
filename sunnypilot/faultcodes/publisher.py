"""
Copyright (c) 2021-, Haibin Wen, sunnypilot, and a number of other contributors.

This file is part of sunnypilot and is licensed under the MIT License.
See the LICENSE.md file in the root directory for more details.

Fault code publisher.

Runs as an openpilot manager process. It samples the fault flags openpilot
already parses (carState), the panda's own faults, the device thermal status and
recent fault events, then publishes a small read-only JSON snapshot that the
on-device panel and the web UI both read.

Nothing here transmits on CAN, changes panda safety, or writes Params, so it is
safe to run at all times.
"""
from __future__ import annotations

import json
import os
import time

from cereal import messaging
from openpilot.common.swaglog import cloudlog

from openpilot.sunnypilot.faultcodes import config as fc_config

PUBLISH_HZ = 2.0
MAX_EVENTS = 40
# openpilot event flags that describe a fault rather than a normal button press
FAULT_EVENT_TYPES = ("permanent", "softDisable", "immediateDisable")


def _event_types(event) -> list:
  return [flag for flag in FAULT_EVENT_TYPES if getattr(event, flag, False)]


def _panda_items(states) -> list:
  items: list = []
  if len(states):
    state = states[0]
    for name in state.faults:
      items.append({"id": str(name), "label": str(name), "active": True})
    if state.heartbeatLost:
      items.append({"id": "heartbeatLost", "label": "Heartbeat lost", "active": True})
    if state.rxBufferOverflow:
      items.append({"id": "rxBufferOverflow", "label": f"RX buffer overflow x{state.rxBufferOverflow}", "active": True})
    if state.txBufferOverflow:
      items.append({"id": "txBufferOverflow", "label": f"TX buffer overflow x{state.txBufferOverflow}", "active": True})
  if not items:
    items.append({"id": "ok", "label": "No panda faults", "active": False})
  return items


def _write(snapshot: dict) -> None:
  try:
    os.makedirs(fc_config.STATE_DIR, exist_ok=True)
    tmp = fc_config.VALUES_PATH + ".tmp"
    with open(tmp, "w") as f:
      json.dump(snapshot, f)
    os.replace(tmp, fc_config.VALUES_PATH)
  except OSError:
    cloudlog.exception("fault codes: failed to write snapshot")


def main() -> None:
  sm = messaging.SubMaster(["carState", "onroadEvents", "pandaStates", "deviceState"])

  events: list = []
  last_keys: set = set()
  last_write = 0.0

  while True:
    try:
      sm.update(0)

      # Record fault events on the rising edge, newest first.
      if sm.updated["onroadEvents"]:
        current: set = set()
        for event in sm["onroadEvents"]:
          types = _event_types(event)
          if not types:
            continue
          key = (str(event.name), tuple(types))
          current.add(key)
          if key not in last_keys:
            events.insert(0, {"time": time.monotonic(), "name": str(event.name), "types": types})
            del events[MAX_EVENTS:]
        last_keys = current

      now = time.monotonic()
      if now - last_write >= 1.0 / PUBLISH_HZ:
        last_write = now

        car_state = sm["carState"]
        vehicle = [{"id": fid, "label": label, "detail": detail, "active": bool(getattr(car_state, fid))}
                   for fid, label, detail in fc_config.VEHICLE_FAULTS]
        status = [{"id": sid, "label": label, "detail": detail, "active": bool(getattr(car_state, sid))}
                  for sid, label, detail in fc_config.VEHICLE_STATUS]

        snapshot = {
          "active_count": sum(1 for item in vehicle if item["active"]),
          "vehicle": vehicle,
          "status": status,
          "panda": _panda_items(sm["pandaStates"]),
          "thermal": str(sm["deviceState"].thermalStatus),
          "events": [{"name": e["name"], "types": e["types"], "age": round(now - e["time"], 1)} for e in events],
          "note": fc_config.NOTE,
        }
        _write(snapshot)

      time.sleep(0.005)
    except Exception:
      cloudlog.exception("fault codes publisher tick failed")
      time.sleep(0.5)
