"""
Copyright (c) 2021-, Haibin Wen, sunnypilot, and a number of other contributors.

This file is part of sunnypilot and is licensed under the MIT License.
See the LICENSE.md file in the root directory for more details.

Live CAN gauge publisher.

Runs as an openpilot manager process. It samples the already-decoded openpilot
state (carState/carControl/pandaStates/deviceState/gps) and decodes arbitrary
signals straight off the raw CAN stream with the car's own DBC, then publishes a
small JSON snapshot that the on-device panel and the web UI both read.

A file is used for the snapshot rather than a new cereal message because cereal
services are compiled into the prebuilt library this branch ships.
"""
from __future__ import annotations

import json
import os
import time

from cereal import car, messaging
from openpilot.common.params import Params
from openpilot.common.swaglog import cloudlog

from openpilot.sunnypilot.cangauges import config as gauge_config

TICK = 0.005
CONFIG_RELOAD = 1.0

# gauge source -> cereal service name
SERVICE = {
  "carState": "carState",
  "carControl": "carControl",
  "device": "deviceState",
  "gps": "gpsLocationExternal",
}


def _platform_dbc_names() -> list:
  """DBC names for the car this device is configured for."""
  try:
    cp = Params().get("CarParamsPersistent")
    if not cp:
      return []
    car_params = messaging.log_from_bytes(cp, car.CarParams)
    from opendbc.car.values import PLATFORMS
    platform = PLATFORMS.get(car_params.carFingerprint)
    if platform is None:
      return []
    return [name for name in dict(platform.config.dbc_dict).values() if name]
  except Exception:
    cloudlog.exception("can gauges: failed to resolve platform DBCs")
    return []


def _build_decoders(dbc_names: list) -> tuple:
  """(by_message_name, catalog) for the platform DBCs. Never raises."""
  from opendbc.can.dbc import DBC
  by_name: dict = {}
  catalog: list = []
  for name in dbc_names:
    try:
      dbc = DBC(name)
    except Exception:
      cloudlog.warning(f"can gauges: could not load DBC {name}")
      continue
    for addr, msg in dbc.addr_to_msg.items():
      by_name.setdefault(msg.name, (name, msg, addr))
      for sig in msg.sigs:
        catalog.append({"key": f"{msg.name}.{sig}", "message": msg.name, "signal": sig,
                        "addr": f"0x{addr:03X}", "dbc": name})
  catalog.sort(key=lambda c: c["key"])
  return by_name, catalog


def _write_catalog(catalog: list) -> None:
  try:
    os.makedirs(gauge_config.STATE_DIR, exist_ok=True)
    tmp = gauge_config.CATALOG_PATH + ".tmp"
    with open(tmp, "w") as f:
      json.dump(catalog, f)
    os.replace(tmp, gauge_config.CATALOG_PATH)
  except OSError:
    cloudlog.exception("can gauges: failed to write catalog")


def _dig(message, path: str):
  current = message
  for part in path.split("."):
    current = getattr(current, part)
  return current


def _decode_can_gauges(sm, gauges: list, by_name: dict, can_values: dict, can_ok: dict) -> None:
  if not sm.updated["can"]:
    return
  frames = sm["can"]
  for gauge in gauges:
    if gauge["source"] != "can":
      continue
    message_name, _, signal_name = gauge["key"].partition(".")
    entry = by_name.get(message_name)
    if entry is None:
      can_ok[gauge["id"]] = False
      continue
    _dbc, msg, addr = entry
    sig = msg.sigs.get(signal_name)
    if sig is None:
      can_ok[gauge["id"]] = False
      continue
    payload = next((bytes(fr.dat) for fr in frames if fr.address == addr), None)
    if payload is None or len(payload) < msg.size:
      continue  # no frame this tick, keep the previous value
    from opendbc.can.parser import get_raw_value
    raw = get_raw_value(payload, sig)
    if sig.is_signed:
      raw -= ((raw >> (sig.size - 1)) & 0x1) * (1 << sig.size)
    can_values[gauge["id"]] = raw * sig.factor + sig.offset
    can_ok[gauge["id"]] = True


def _builtin_value(sm, gauge: dict, values: dict, ok: dict) -> None:
  source = gauge["source"]
  if source == "panda":
    states = sm["pandaStates"]
    if len(states) == 0:
      ok[gauge["id"]] = False
      return
    message = states[0]
  else:
    message = sm[SERVICE[source]]
  try:
    value = _dig(message, gauge["key"])
  except Exception:
    ok[gauge["id"]] = False
    return
  try:
    values[gauge["id"]] = {"value": float(value), "text": None}
  except (TypeError, ValueError):
    # Some fields are per-core/per-zone lists (e.g. cpuTempC); show the hottest.
    try:
      values[gauge["id"]] = {"value": max(float(v) for v in value), "text": None}
    except Exception:
      values[gauge["id"]] = {"value": None, "text": str(value)}
  ok[gauge["id"]] = True


def _write_values(sm, cfg: dict, can_values: dict, can_ok: dict) -> None:
  builtin_values: dict = {}
  builtin_ok: dict = {}
  out = []
  for gauge in cfg["gauges"]:
    if gauge["source"] == "can":
      raw = can_values.get(gauge["id"])
      entry = {"value": None if raw is None else raw * gauge["scale"], "text": None}
      valid = bool(can_ok.get(gauge["id"], False)) and raw is not None
    else:
      _builtin_value(sm, gauge, builtin_values, builtin_ok)
      entry = builtin_values.get(gauge["id"], {"value": None, "text": None})
      if entry.get("value") is not None:
        entry = {"value": entry["value"] * gauge["scale"], "text": None}
      valid = bool(builtin_ok.get(gauge["id"], False))
    out.append({"id": gauge["id"], "label": gauge["label"], "unit": gauge["unit"],
                "min": gauge["min"], "max": gauge["max"], "style": gauge["style"],
                "value": entry["value"], "text": entry["text"], "ok": valid})

  snapshot = {"updated": time.monotonic(), "gauges": out}
  try:
    os.makedirs(gauge_config.STATE_DIR, exist_ok=True)
    tmp = gauge_config.VALUES_PATH + ".tmp"
    with open(tmp, "w") as f:
      json.dump(snapshot, f)
    os.replace(tmp, gauge_config.VALUES_PATH)
  except OSError:
    cloudlog.exception("can gauges: failed to write values")


def main() -> None:
  sm = messaging.SubMaster(["carState", "carControl", "pandaStates", "deviceState", "gpsLocationExternal", "can"])
  by_name, catalog = _build_decoders(_platform_dbc_names())
  _write_catalog(catalog)

  can_values: dict = {}
  can_ok: dict = {}
  cfg = gauge_config.load()
  last_cfg = last_write = 0.0

  while True:
    try:
      sm.update(0)
      now = time.monotonic()
      if now - last_cfg >= CONFIG_RELOAD:
        last_cfg = now
        cfg = gauge_config.load()
      _decode_can_gauges(sm, cfg["gauges"], by_name, can_values, can_ok)
      if now - last_write >= 1.0 / cfg["update_hz"]:
        last_write = now
        _write_values(sm, cfg, can_values, can_ok)
      time.sleep(TICK)
    except Exception:
      cloudlog.exception("can gauges publisher tick failed")
      time.sleep(0.5)
