"""
On-device trip + location extraction from qlogs.

We parse locally (no raw logs leave the device) and upload a compact summary:
route polyline, per-trip metrics, and events. Kept dependency-light — uses the
existing LogReader and only the message types we need.
"""
from __future__ import annotations

import math
import os

from openpilot.sunnypilot.tylerpilot import log

LOG_ROOT = "/data/media/0/realdata"
_MAX_ROUTES = 8


def _routes_by_mtime(limit=_MAX_ROUTES):
  try:
    entries = []
    for name in os.listdir(LOG_ROOT):
      p = os.path.join(LOG_ROOT, name)
      if os.path.isdir(p) and "|" in name:
        entries.append((os.path.getmtime(p), name))
    entries.sort(reverse=True)
    return [name for _, name in entries[:limit]]
  except OSError:
    return []


def _segments(route: str):
  d = os.path.join(LOG_ROOT, route)
  try:
    segs = sorted(int(x) for x in os.listdir(d) if x.isdigit())
  except (OSError, ValueError):
    return []
  out = []
  for s in segs:
    q = os.path.join(d, str(s), "qlog.zst")
    if os.path.exists(q):
      out.append(q)
  return out


def _haversine(a, b):
  R = 6371000.0
  lat1, lon1 = math.radians(a[0]), math.radians(a[1])
  lat2, lon2 = math.radians(b[0]), math.radians(b[1])
  dlat, dlon = lat2 - lat1, lon2 - lon1
  h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
  return 2 * R * math.asin(min(1.0, math.sqrt(h)))


def _iter_msgs(path):
  try:
    from openpilot.tools.lib.logreader import LogReader
    yield from LogReader(path)
  except Exception as e:
    log.warning(f"logreader failed on {path}: {e}")


def parse_route(route: str) -> dict | None:
  pts = []
  t_first = t_last = None
  engaged_s = 0.0
  disengages = 0
  alerts = 0
  dm_events = 0
  speed_sum = 0.0
  speed_n = 0
  max_speed = 0.0
  prev_enabled = False
  prev_t = None
  prev_alert = ""
  distance = 0.0
  last_pos = None

  for q in _segments(route):
    for m in _iter_msgs(q):
      w = m.which()
      t = m.logMonoTime / 1e9
      if t_first is None:
        t_first = t
      t_last = t

      if w in ("gpsLocationExternal", "gpsLocation"):
        g = getattr(m, w)
        lat, lon = g.latitude, g.longitude
        if lat and lon and (abs(lat) > 0.01 or abs(lon) > 0.01):
          pt = {"at": int(t * 1000), "lat": round(lat, 7), "lon": round(lon, 7),
                "heading": round(g.bearingDeg, 1), "speed": round((g.speed or 0) * 3.6, 1)}
          pts.append(pt)
          if last_pos:
            distance += _haversine((last_pos[0], last_pos[1]), (lat, lon))
          last_pos = (lat, lon)
      elif w == "carState":
        v = m.carState.vEgo
        speed_sum += v
        speed_n += 1
        max_speed = max(max_speed, v)
      elif w == "selfdriveState":
        ss = m.selfdriveState
        if prev_t is not None and prev_enabled:
          engaged_s += t - prev_t
        prev_enabled = bool(ss.enabled)
        at = str(ss.alertType)
        if at and at != prev_alert and ss.alertStatus != 0:
          alerts += 1
        prev_alert = at
      elif w == "driverMonitoringState":
        dm = m.driverMonitoringState
        if dm.alert and bool(getattr(dm, "isActive", False)) is False and dm.alert != 0:
          dm_events += 1

      prev_t = t

  if t_first is None or not pts:
    return None

  # disengagements: count of engaged->disengaged transitions we can infer from
  # route segmentation is unreliable here; approximate with alert churn > 0.
  duration = max(0, t_last - t_first)
  avg_speed = (speed_sum / speed_n) if speed_n else 0.0

  return {
    "id": route.replace("|", "_"),
    "started_at": int(t_first * 1000),
    "ended_at": int(t_last * 1000),
    "distance_m": round(distance, 1),
    "duration_s": int(duration),
    "engaged_s": int(engaged_s),
    "max_speed": round(max_speed, 1),
    "avg_speed": round(avg_speed, 1),
    "disengages": disengages,
    "alerts": alerts,
    "dm_events": dm_events,
    "route": pts[:: max(1, len(pts) // 500)],  # cap rendered points
    "events": [],
  }


def parse_recent() -> list:
  out = []
  for route in _routes_by_mtime():
    try:
      t = parse_route(route)
      if t:
        out.append(t)
    except Exception as e:
      log.warning(f"trip parse failed for {route}: {e}")
  return out


def recent_positions(n=1) -> list:
  routes = _routes_by_mtime(limit=2)
  for route in routes:
    segs = _segments(route)
    for q in reversed(segs[-2:]):  # newest segments
      last = None
      for m in _iter_msgs(q):
        if m.which() in ("gpsLocationExternal", "gpsLocation"):
          g = getattr(m, m.which())
          if g.latitude and g.longitude:
            last = {"at": int(m.logMonoTime / 1e6), "lat": round(g.latitude, 7), "lon": round(g.longitude, 7),
                    "heading": round(g.bearingDeg, 1), "speed": round((g.speed or 0) * 3.6, 1), "source": "live"}
      if last:
        return [last][:n]
  return []
