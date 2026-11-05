"""Weather forecast for this point: BMKG where the node is in Indonesia, Open-Meteo anywhere.

Context for reading the node's own air, not a prediction of it. The node fetches what a meteorological agency
already published and stores it beside its own readings so a person can see whether the smoke is arriving or
leaving. Forecasting is the upstream tiers' job; this pack has no rules that speak and no cells.

Every value is stored at its VALID time with the issue time beside it, as `fc_lead_hours`. A forecast without
its issue time cannot be checked afterwards, and one that has quietly stopped refreshing looks exactly like one
that is right.
"""
from __future__ import annotations

import logging
import os
import sys
import time
from datetime import datetime, timedelta, timezone

log = logging.getLogger("planetai.forecast")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))   # the pack loader does not put the pack on the path
import territory  # noqa: E402

BMKG = "https://api.bmkg.go.id/publik/prakiraan-cuaca"
OPEN_METEO = "https://api.open-meteo.com/v1/forecast"
CAMS = "https://air-quality-api.open-meteo.com/v1/air-quality"
MARINE = "https://marine-api.open-meteo.com/v1/marine"
HOURS = 72                      # what the Next days view needs: today's rest, tomorrow and the day after
WIND_HOURS = 24                 # the map's wind field shows the next day only, as it always has


def _utc(s: str | None) -> datetime | None:
    if not s:
        return None
    s = s.strip().replace(" ", "T")
    try:
        d = datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None
    return d.astimezone(timezone.utc) if d.tzinfo else d.replace(tzinfo=timezone.utc)


def _sensor(sid: str, name: str, lat, lon, meta: dict) -> dict:
    return {"sensor_id": sid, "source": sid, "name": name, "lat": lat, "lon": lon,
            "indoor": False, "local": False, "kind": "model", "scale": "community",
            "cadence": "PT3H", "meta": meta}


def bmkg(hc, adm4: str, node_lat: float, node_lon: float):
    """BMKG's 3-hourly forecast for one Permendagri village code. `ws` is km/h and `wd_deg` is the direction the
    wind comes FROM, both as documented. `tp` is rain in mm for the step, which the node stores as the amount —
    BMKG publishes no probability, so the node does not invent one."""
    r = hc.get(BMKG, params={"adm4": adm4}, headers={"user-agent": "planetai-node"})
    r.raise_for_status()
    d = r.json()
    loc = d.get("lokasi") or {}
    if not loc:
        log.info("forecast: BMKG has no data for adm4=%s", adm4)
        return [], []
    steps = [s for group in (d.get("data") or [{}])[0].get("cuaca") or [] for s in group]
    issued = _utc((steps[0] if steps else {}).get("analysis_date"))
    sid = "forecast-bmkg"
    sensors = [_sensor(sid, f"BMKG forecast — {loc.get('desa')}, {loc.get('kecamatan')}",
                       loc.get("lat"), loc.get("lon"),
                       {"adm4": adm4, "desa": loc.get("desa"), "kecamatan": loc.get("kecamatan"),
                        "kotkab": loc.get("kotkab"), "issued": issued.isoformat() if issued else None,
                        "km_from_node": None if loc.get("lat") is None else round(
                            _km(node_lat, node_lon, float(loc["lat"]), float(loc["lon"])), 2),
                        "attribution": "BMKG (Badan Meteorologi, Klimatologi, dan Geofisika), api.bmkg.go.id"})]
    cutoff = datetime.now(timezone.utc) + timedelta(hours=HOURS)
    readings = []
    for s in steps:
        ts = _utc(s.get("utc_datetime") or s.get("datetime"))
        if ts is None or ts > cutoff:
            continue
        for key, metric in (("t", "fc_temp"), ("hu", "fc_humidity"), ("ws", "fc_wind_speed"),
                            ("wd_deg", "fc_wind_direction"), ("tcc", "fc_cloud"), ("tp", "fc_rain")):
            if s.get(key) is not None:
                readings.append((ts, sid, metric, float(s[key])))
        if issued is not None:
            readings.append((ts, sid, "fc_lead_hours", round((ts - issued).total_seconds() / 3600, 1)))
    return sensors, readings


OM_HOURLY = ("temperature_2m,relative_humidity_2m,precipitation,wind_speed_10m,wind_direction_10m,cloud_cover,"
             "wind_gusts_10m,precipitation_probability,shortwave_radiation,et0_fao_evapotranspiration,soil_moisture_0_to_1cm")
OM_MAP = {"temperature_2m": "fc_temp", "relative_humidity_2m": "fc_humidity", "precipitation": "fc_rain",
          "wind_speed_10m": "fc_wind_speed", "wind_direction_10m": "fc_wind_direction", "cloud_cover": "fc_cloud",
          "wind_gusts_10m": "fc_wind_gusts", "precipitation_probability": "fc_rain_prob",
          "shortwave_radiation": "fc_shortwave", "et0_fao_evapotranspiration": "fc_et0",
          "soil_moisture_0_to_1cm": "fc_soil_moisture"}


def _om_points(hc, url: str, points: list[dict], hourly: str):
    """One Open-Meteo request for every point. `forecast_days=4` counts from midnight UTC, so it always reaches past
    now + HOURS (three days would leave ~52 h at 20:00 UTC); `_om_rows` trims at HOURS. The ask is days, not
    `forecast_hours`, because only the weather API's support for that is certain.
    One location answers a dict and several answer a list in
    the order asked; both come back as a list, and a short answer is refused rather than matched to the wrong place."""
    r = hc.get(url, params={"latitude": ",".join(str(p["lat"]) for p in points),
                            "longitude": ",".join(str(p["lon"]) for p in points),
                            "hourly": hourly, "forecast_days": 4, "timezone": "UTC"})
    r.raise_for_status()
    d = r.json()
    d = d if isinstance(d, list) else [d]
    if len(d) != len(points):
        raise ValueError(f"Open-Meteo answered {len(d)} points for {len(points)} asked")
    return d


def _om_rows(d: dict, sid: str, mapping: dict, fetched: datetime) -> list:
    """The hourly rows of one point from `fetched - 1 h` to HOURS ahead, each with how far ahead it is."""
    h = d.get("hourly") or {}
    times = h.get("time") or []
    cutoff = fetched + timedelta(hours=HOURS)
    readings = []
    for i, t in enumerate(times):
        ts = _utc(t if str(t).endswith("Z") else f"{t}Z")
        if ts is None or ts < fetched - timedelta(hours=1) or ts > cutoff:
            continue
        for key, metric in mapping.items():
            v = (h.get(key) or [None] * len(times))[i]
            if v is not None:
                readings.append((ts, sid, metric, float(v)))
        readings.append((ts, sid, "fc_lead_hours", round((ts - fetched).total_seconds() / 3600, 1)))
    return readings


def openmeteo(hc, points: list[dict]):
    """Open-Meteo's hourly forecast at each point, {"sid", "cell", "lat", "lon"}, in one request. `wind_speed_10m` is
    km/h by default, the same unit BMKG publishes, so the two are comparable without conversion — checked against the
    API's own `hourly_units` in verify.

    Open-Meteo publishes no issue time: there is no analysis_date in the response, and `generationtime_ms` is how
    long the request took, not when the model ran. The node records when IT fetched, and says so rather than
    dressing a fetch time up as a model run."""
    answers = _om_points(hc, OPEN_METEO, points, OM_HOURLY)
    fetched = datetime.now(timezone.utc)
    sensors, readings = [], []
    for p, d in zip(points, answers):
        sensors.append(_sensor(p["sid"], "Open-Meteo forecast (model point sample)", d.get("latitude"), d.get("longitude"),
                               {"fetched": fetched.isoformat(), "issued": None, "cell": p.get("cell"),
                                "note": "Open-Meteo publishes no model run time; `fetched` is when this node asked.",
                                "licence": "CC-BY 4.0, free tier non-commercial only",
                                "attribution": "Open-Meteo, open-meteo.com"}))
        readings += _om_rows(d, p["sid"], OM_MAP, fetched)
    return sensors, readings


CAMS_MAP = {"pm2_5": "fc_pm25", "uv_index": "fc_uv"}
MARINE_MAP = {"wave_height": "fc_wave_m", "swell_wave_height": "fc_swell_m", "swell_wave_period": "fc_swell_s",
              "swell_wave_direction": "fc_swell_dir"}


def cams(hc, points: list[dict]):
    """CAMS air at each point, one request through Open-Meteo's air-quality API: PM2.5 (µg/m³) and the UV index, the next
    72 hours. A point's id is the same as its weather point's with `forecast-cams` for `forecast-om`. A model of what the
    air will do, never a reading: it is stored `derived` and `comparable: false`, like every fc_ metric."""
    answers = _om_points(hc, CAMS, points, ",".join(CAMS_MAP))
    fetched = datetime.now(timezone.utc)
    sensors, readings = [], []
    for p, d in zip(points, answers):
        sid = "forecast-cams" + p["sid"].removeprefix("forecast-om")
        sensors.append(_sensor(sid, "CAMS air forecast via Open-Meteo (model point sample)", d.get("latitude"), d.get("longitude"),
                               {"fetched": fetched.isoformat(), "issued": None, "cell": p.get("cell"),
                                "note": "Open-Meteo publishes no model run time; `fetched` is when this node asked.",
                                "licence": "CC-BY 4.0, free tier non-commercial only",
                                "attribution": "Open-Meteo Air Quality, open-meteo.com; Copernicus Atmosphere Monitoring Service"}))
        readings += _om_rows(d, sid, CAMS_MAP, fetched)
    return sensors, readings


def marine(hc, points: list[dict]):
    """Waves and swell, the next 72 hours, at the node's own point (the first of `points`; the sea is never a grid here).
    Open-Meteo Marine snaps the ask to the nearest sea cell itself, so the cell it answers with is stored as the
    sensor's place, and a cell farther than COAST_MAX_KM (default 30, the coast pack's own rule) is refused: an
    inland node would otherwise be given a number about a sea it has never seen."""
    p = points[0]
    d = _om_points(hc, MARINE, [p], ",".join(MARINE_MAP))[0]
    fetched = datetime.now(timezone.utc)
    cell_lat, cell_lon = float(d["latitude"]), float(d["longitude"])
    km = _km(p["lat"], p["lon"], cell_lat, cell_lon)
    if km > float(os.getenv("COAST_MAX_KM", "30")):
        log.info("forecast: nearest sea cell is %.0f km away; this node is not coastal (COAST_MAX_KM), no sea forecast", km)
        return [], []
    sensor = _sensor("forecast-marine", f"Open-Meteo Marine forecast, sea cell {km:.0f} km off", cell_lat, cell_lon,
                     {"fetched": fetched.isoformat(), "issued": None, "cell": p.get("cell"), "distance_km": round(km, 1),
                      "note": "Open-Meteo publishes no model run time; `fetched` is when this node asked.",
                      "licence": "CC-BY 4.0, free tier non-commercial only",
                      "attribution": "Open-Meteo Marine, open-meteo.com; Copernicus Marine / MFWAM"})
    return [sensor], _om_rows(d, "forecast-marine", MARINE_MAP, fetched)


def _pack_on(pid: str) -> bool:
    """Is that pack loaded on this node? Asks the loader (app/packs.py), which reads PACKS_ENABLED from Settings."""
    import packs
    return pid in {d.name for d in packs._enabled()}


WIND_N = int(os.getenv("FORECAST_WIND_N", "8"))            # points a side: 8 x 8 = 64, as Bali Air Dispatch draws its field
WIND_KM = float(os.getenv("FORECAST_WIND_KM", "30"))       # half-width of the square, km


def wind_grid(lat: float, lon: float, km: float = WIND_KM, n: int = WIND_N):
    """The n×n points of a square of half-width `km` round (lat, lon): latitudes south to north, longitudes west to
    east, so the page can draw the field without working out where a point is."""
    import math
    dlat, dlon = km / 110.574, km / (111.320 * math.cos(math.radians(lat)))
    step = lambda lo, hi, i: round(lo + (hi - lo) * i / (n - 1), 5)  # noqa: E731
    return [step(lat - dlat, lat + dlat, i) for i in range(n)], [step(lon - dlon, lon + dlon, i) for i in range(n)]


def wind_field(hc, lat: float, lon: float, km: float = WIND_KM, n: int = WIND_N) -> dict:
    """The wind over the node's square, for a map that draws it moving: Open-Meteo's hourly 10 m wind at n×n points,
    the next day, in one request. Speeds km/h, directions the way the wind comes FROM, as the point forecast stores
    them. Not readings: a model's field, kept as a file (out/ground/wind.json) for the map and nothing else."""
    lats, lons = wind_grid(lat, lon, km, n)
    pts = [(la, lo) for la in lats for lo in lons] + [(round(lat, 5), round(lon, 5))]   # the node's own point last
    r = hc.get(OPEN_METEO, params={"latitude": ",".join(str(p[0]) for p in pts), "longitude": ",".join(str(p[1]) for p in pts),
                                   "hourly": "wind_speed_10m,wind_direction_10m", "forecast_days": 2, "timezone": "UTC",
                                   "cell_selection": "nearest"})   # the default, "land", moves a sea point to the nearest land cell, 12 km off
    r.raise_for_status()
    d = r.json()
    d = d if isinstance(d, list) else [d]
    if len(d) != len(pts):
        raise ValueError(f"Open-Meteo answered {len(d)} points for {len(pts)} asked")
    fetched = datetime.now(timezone.utc)
    times = [f"{t}Z" for t in (d[0].get("hourly") or {}).get("time", [])]
    keep = [i for i, t in enumerate(times) if fetched - timedelta(hours=1) <= _utc(t) <= fetched + timedelta(hours=WIND_HOURS)]
    grid = lambda key: [[[(p.get("hourly") or {}).get(key, [None] * len(times))[i] for p in d[j * n:(j + 1) * n]]  # noqa: E731
                         for j in range(n)] for i in keep]
    me = (d[-1].get("hourly") or {})
    return {"source": "Open-Meteo, 10 m wind", "licence": "CC-BY 4.0, free tier non-commercial only",
            "attribution": "Open-Meteo, open-meteo.com", "fetched": fetched.isoformat(), "n": n, "km": km,
            "lats": lats, "lons": lons, "times": [times[i] for i in keep],
            "speed_kmh": grid("wind_speed_10m"), "from_deg": grid("wind_direction_10m"),
            # the readout's one number is the node's own point, asked as such, not a value the page picks off the grid
            "at_node": {"speed_kmh": [me.get("wind_speed_10m", [None] * len(times))[i] for i in keep],
                        "from_deg": [me.get("wind_direction_10m", [None] * len(times))[i] for i in keep]}}


def write_wind_field(hc, lat: float, lon: float):
    """Fetch the field and replace out/ground/wind.json whole, or leave the last one standing."""
    import json
    from pathlib import Path
    out = Path(os.getenv("PACK_OUT", "/app/out")) / "ground"
    f = wind_field(hc, lat, lon)
    out.mkdir(parents=True, exist_ok=True)
    tmp = out / "wind.json.part"
    tmp.write_text(json.dumps(f))
    tmp.replace(out / "wind.json")
    return f


def gap(a: list, b: list):
    """Where the two sources disagree, on the variables they both give. One derived channel, not a judgement:
    neither source is the truth, and a wide gap is the node saying so out loud."""
    def by(rows, metric):
        return {ts: v for ts, _sid, m, v in rows if m == metric}
    out = []
    for metric, name in (("fc_temp", "fc_temp_gap"), ("fc_wind_speed", "fc_wind_speed_gap")):
        x, y = by(a, metric), by(b, metric)
        for ts in sorted(set(x) & set(y)):
            out.append((ts, "forecast-gap", name, round(abs(x[ts] - y[ts]), 2))) 
    if not out:
        return [], []
    return [_sensor("forecast-gap", "BMKG against Open-Meteo", None, None,
                    {"note": "how far apart the two forecasts are for the same hour; neither is the truth"})], out


def _km(lat1, lon1, lat2, lon2):
    import math
    p = math.pi / 180
    a = 0.5 - math.cos((lat2 - lat1) * p) / 2 + math.cos(lat1 * p) * math.cos(lat2 * p) * (1 - math.cos((lon2 - lon1) * p)) / 2
    return 12742 * math.asin(math.sqrt(a))


RETRY_S = 1800                  # a refused or unreachable source is asked again after half an hour


def _stamp_file(source: str):
    from pathlib import Path
    return Path(os.getenv("PACK_OUT", "/app/out")) / f"forecast.{source}.last"


def _due(source: str, force: bool = False) -> bool:
    """Is this source due? One stamp a source, out/forecast.<source>.last, and its mtime is the one clock: a source that
    answered waits FORECAST_POLL_HOURS (default 6), one that failed waits RETRY_S, and a source never asked is due.
    The pack runs in the node's 300 s loop, so without the wait it asked Open-Meteo for 65 points ~275 times a day and
    spent the whole IP's free tier by 14:00 in Bali (13 Oct). Open-Meteo's daily limit is per IP, so a refused call
    is not retried on the next poll either: that would hit an IP already over its cap about 200 times a day. One
    source failing never holds back another, because each has its own stamp. The stamp lives in out/, so a restart
    does not ask again. `force` is `planetai run forecast fetch` and verify: now, and the clocks are left alone."""
    if force:
        return True
    f = _stamp_file(source)
    return not f.is_file() or time.time() - f.stat().st_mtime >= float(os.getenv("FORECAST_POLL_HOURS", "6")) * 3600


def _stamp(source: str, ok: bool = True) -> None:
    """After an attempt. The mtime is set so that `_due` stays one comparison: now when it answered, and far enough
    back that it is due again in RETRY_S when it did not (never longer than the poll itself)."""
    poll = float(os.getenv("FORECAST_POLL_HOURS", "6")) * 3600
    f = _stamp_file(source)
    f.parent.mkdir(parents=True, exist_ok=True)
    f.touch()
    t = time.time() - (0 if ok else poll - min(RETRY_S, poll))
    os.utime(f, (t, t))


GAP_METRICS = ("fc_temp", "fc_wind_speed")


def _rows_file(source: str):
    return _stamp_file(source).with_name(f"forecast.{source}.rows.json")


def _save_rows(source: str, readings: list) -> None:
    """The last rows this source answered, only the metrics the gap compares, in out/. Sources keep different clocks
    (one that failed retries alone), so the gap against the other source has to read what that one last stored. A
    file, not module state: the pack is re-imported and a module forgets. Written whole, then moved into place."""
    import json
    f = _rows_file(source)
    f.parent.mkdir(parents=True, exist_ok=True)
    tmp = f.with_name(f.name + ".part")
    tmp.write_text(json.dumps([[ts.isoformat(), sid, m, v] for ts, sid, m, v in readings if m in GAP_METRICS]))
    tmp.replace(f)


def _load_rows(source: str) -> list:
    """That source's last stored rows, future hours only. Nothing stored, or a file that does not parse, is no rows."""
    import json
    try:
        rows = [(_utc(t), sid, m, float(v)) for t, sid, m, v in json.loads(_rows_file(source).read_text())]
    except (OSError, ValueError, TypeError):
        return []
    now = datetime.now(timezone.utc)
    return [r for r in rows if r[0] is not None and r[0] > now]


def _try(source: str, force: bool, what: str, call):
    """Run `call` if `source` is due; stamp the attempt. Returns what it returned, or None when it was not due or failed.
    A source that is down is never an alert: log once and carry on with the others. The retry stamp is written BEFORE
    the request and replaced by the full one after it answered, so an out/ that cannot be written raises before
    anything is asked, not after (stamped after, the source was due again in 300 s: the 13 Oct cap)."""
    if not _due(source, force):
        return None
    if not force:
        _stamp(source, ok=False)
    try:
        out = call()
    except Exception as e:  # noqa: BLE001
        log.warning("forecast: %s not fetched (%s)", what, e)
        return None
    if not force and out is not None:
        _stamp(source)
    return out


def fetch(hc, force: bool = False):
    """Every source that is configured and due, each on its own clock; one refused or down does not hold the others.
    `force` is `planetai run forecast fetch`: now."""
    lat, lon = float(os.environ["NODE_LAT"]), float(os.environ["NODE_LON"])
    sensors, readings, bm, om = [], [], [], []
    adm4 = os.getenv("FORECAST_BMKG_ADM4", "").strip()
    if os.getenv("FORECAST_BMKG", "1") == "1":
        if not adm4:
            log.info("forecast: FORECAST_BMKG_ADM4 is not set — `planetai run forecast verify` finds the code for this point")
        else:
            got = _try("bmkg", force, "BMKG", lambda: bmkg(hc, adm4, lat, lon))
            if got:
                sensors += got[0]; readings += got[1]; bm = got[1]
                _save_rows("bmkg", bm)
    if os.getenv("FORECAST_OPENMETEO", "0") == "1":
        scale = os.getenv("NODE_SCALE", "community").strip().lower()
        node = territory.points(scale, lat, lon, "forecast-om")   # the weather and the air take the territory
        sea = territory.points("home", lat, lon, "forecast-marine")   # the sea is one point, the API snaps it to water

        got = _try("om", force, "Open-Meteo", lambda: openmeteo(hc, node))
        if got:
            sensors += got[0]; readings += got[1]
            om = [r for r in got[1] if r[1] == "forecast-om"]   # the gap is against the node's own point, not a neighbouring cell
            _save_rows("om", om)
        # the field the map draws moving: same switch, its own stamp, so a refused field never re-asks the points
        _try("wind", force, "the wind field", lambda: write_wind_field(hc, lat, lon))
        got = _try("cams", force, "Open-Meteo air", lambda: cams(hc, node))
        if got:
            sensors += got[0]; readings += got[1]
        if _pack_on("coast"):               # the sea is the coast pack's question; without it there is nobody to ask for
            got = _try("marine", force, "Open-Meteo marine", lambda: marine(hc, sea))
            if got:
                sensors += got[0]; readings += got[1]
    if bm or om:         # either one fresh is enough: the other is what it last stored
        s, g = gap(bm or _load_rows("bmkg"), om or _load_rows("om")); sensors += s; readings += g
    return sensors, readings
