from __future__ import annotations

from openpilot.sunnypilot.tylerpilot import trips


class _Data:
  def __init__(self, **attrs):
    self.__dict__.update(attrs)


class _Msg:
  """Stand-in for a cereal message: which() + logMonoTime + a typed payload."""

  def __init__(self, which: str, t: float, **attrs):
    self._which = which
    self.logMonoTime = int(t * 1e9)
    setattr(self, which, _Data(**attrs))

  def which(self) -> str:
    return self._which


def _patch_stream(monkeypatch, msgs):
  monkeypatch.setattr(trips, "_segments", lambda route: ["/fake/qlog.zst"])
  monkeypatch.setattr(trips, "_iter_msgs", lambda path: iter(msgs))


def test_parse_route_summary(monkeypatch):
  msgs = [
    _Msg("gpsLocationExternal", 0.0, latitude=37.0, longitude=-122.0, bearingDeg=90.0, speed=10.0),
    _Msg("carState", 1.0, vEgo=20.0),
    _Msg("selfdriveState", 2.0, enabled=True, alertType="a", alertStatus=1),
    _Msg("gpsLocationExternal", 3.0, latitude=37.001, longitude=-122.001, bearingDeg=91.0, speed=12.0),
    _Msg("driverMonitoringState", 4.0, alert=1, isActive=False),
  ]
  _patch_stream(monkeypatch, msgs)

  t = trips.parse_route("route|2026-01-01")
  assert t is not None
  assert t["id"] == "route_2026-01-01"
  assert t["distance_m"] > 0
  assert t["max_speed"] == 20.0
  assert t["avg_speed"] == 20.0
  assert t["alerts"] == 1
  assert t["dm_events"] == 1
  assert t["started_at"] == 0
  assert t["ended_at"] == 4000
  assert len(t["route"]) == 2


def test_parse_route_none_without_gps(monkeypatch):
  _patch_stream(monkeypatch, [_Msg("carState", 1.0, vEgo=5.0)])
  assert trips.parse_route("route|1") is None


def test_parse_route_none_when_no_messages(monkeypatch):
  _patch_stream(monkeypatch, [])
  assert trips.parse_route("route|1") is None


def test_haversine_one_degree_longitude():
  d = trips._haversine((0.0, 0.0), (0.0, 1.0))
  assert 111_000 < d < 111_500


def test_segments_discovers_qlogs(tmp_path, monkeypatch):
  monkeypatch.setattr(trips, "LOG_ROOT", str(tmp_path))
  route = tmp_path / "route|1"
  (route / "0").mkdir(parents=True)
  (route / "0" / "qlog.zst").write_text("x")
  (route / "1").mkdir()  # segment with no qlog
  segs = trips._segments("route|1")
  assert segs == [str(route / "0" / "qlog.zst")]


def test_routes_by_mtime_orders_newest_first(tmp_path, monkeypatch):
  monkeypatch.setattr(trips, "LOG_ROOT", str(tmp_path))
  (tmp_path / "old|1").mkdir()
  (tmp_path / "new|1").mkdir()
  import os
  os.utime(tmp_path / "old|1", (1, 1))
  os.utime(tmp_path / "new|1", (2, 2))
  (tmp_path / "notaroute").mkdir()  # no "|" -> excluded
  routes = trips._routes_by_mtime()
  assert routes == ["new|1", "old|1"]


def test_routes_by_mtime_missing_root(monkeypatch):
  monkeypatch.setattr(trips, "LOG_ROOT", "/nonexistent/realdata")
  assert trips._routes_by_mtime() == []


def test_parse_recent_swallows_errors(monkeypatch):
  monkeypatch.setattr(trips, "_routes_by_mtime", lambda limit=8: ["r|1"])

  def boom(route):
    raise RuntimeError("bad route")

  monkeypatch.setattr(trips, "parse_route", boom)
  assert trips.parse_recent() == []
