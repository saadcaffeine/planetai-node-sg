"""What the node knows about the window it is about to report on, and the report it writes from that on its own.

Two things live here, in this order, because the second is the ruler for everything that comes after it:

  bundle(cur, hours)      every number the node has about the last `hours`, as one JSON-able document
  sheet(bundle, locale)   the node's own report, deterministic, six parts, under a hundred words

The sheet is what a household gets on a node with no model anywhere, which is most nodes. When a model is in the
path it is handed the bundle and the sheet, and anything it writes is checked against the numbers in them before
it is allowed out. So the bundle is the only place a number may come from, and the sheet is what the node falls
back to. Neither may need the network: it is all SQL against this node's own tables.
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import index
import settings

log = logging.getLogger("planetai.report")

# What the slow sources mean, in words a model or a person can read. Lived in agent.py until the report needed it
# too; one copy, imported from there.
LABELS = {
    "marine-point": ("sea", {"wave_height_m": "wave height, m", "swell_height_m": "swell height, m", "wave_period_s": "wave period, s",
                             "swell_period_s": "swell period, s", "wave_direction": "waves coming from, degrees (0 north, 90 east, 180 south, 270 west)",
                             "sea_surface_temp": "sea surface temperature, °C"}),
    "om-point": ("weather", {"temp_model": "air temperature, °C", "humidity_model": "humidity, %", "pressure_model": "pressure, hPa",
                             "wind_speed": "wind speed, km/h", "wind_direction": "wind coming from, degrees", "precipitation": "rain this hour, mm"}),
    "cams-point": ("satellite_air", {"pm25_model": "PM2.5 the model estimates for the district, µg/m³", "pm10_model": "PM10, µg/m³", "o3": "ozone, µg/m³",
                                     "no2": "nitrogen dioxide, µg/m³", "co": "carbon monoxide, µg/m³", "dust": "dust, µg/m³", "uv_index": "UV index", "aod": "aerosol optical depth"}),
    "place-point": ("place", {"sat_buildings": "buildings the satellite sees within the radius (Google Open Buildings, confidence ≥ 0.65)",
                              "sat_confidence": "mean detection confidence of those (0-1)", "osm_building_coverage": "share of the satellite's buildings that OpenStreetMap has drawn (0-1)",
                              "sat_buildings_yearly": "building count in the latest year of the temporal dataset; use `history` for the 2016-2023 series",
                              "sat_height_m_yearly": "mean building height, m, latest year",
                              "buildings": "buildings within the radius (OpenStreetMap)", "built_share": "share of the ground covered by buildings (0-1)",
                              "commercial_share": "share of buildings that are shops, offices, hotels (0-1)", "businesses_per_km2": "mapped businesses per km²",
                              "poi_food": "places to eat on the map", "poi_retail": "shops and markets on the map", "poi_education": "schools on the map (zero often means unmapped)",
                              "poi_health": "clinics, doctors, pharmacies on the map", "poi_worship": "temples, mosques, churches on the map", "poi_lodging": "hotels, villas, guesthouses on the map",
                              "poi_services": "banks, post, police, fuel on the map", "roads_km": "kilometres of road", "green_share": "share of the ground that is green (0-1)",
                              "nearest_school_m": "walk to the nearest mapped school, m", "nearest_health_m": "walk to the nearest mapped clinic or pharmacy, m",
                              "nearest_market_m": "walk to the nearest mapped market or minimarket, m", "nearest_worship_m": "walk to the nearest place of worship, m"}),
    "ee-point": ("land", {"built_frac": "share of the surrounding km that is built-up (0-1)", "tree_frac": "share that is trees (0-1)", "crop_frac": "share that is crops (0-1)",
                          "water_frac": "share that is water (0-1)", "ndvi_median": "greenness index (NDVI, -1..1)", "night_lights": "night-time light radiance", "land_change_score": "how much the land changed since the year before (0 = none)"}),
}
POINTS = tuple(LABELS)

# How far a metric has to move across the window before the node calls it a change rather than noise. The digest
# has used ±3 for PM2.5 since v0.24; the rest are that rule read across to their own units. A metric with no entry
# gets 5% of its own range in the window, which is a guess that at least scales.
TREND = {"pm25": 3.0, "pm25_raw": 3.0, "pm10": 5.0, "pm1": 2.0, "temp": 0.5, "humidity": 3.0,
         "pressure": 0.3, "noise": 3.0, "light": 50.0, "eco2": 100.0, "tvoc": 50.0, "aqi": 5.0}

# A model with a 4k context is handed this document. 64 kB is what the smallest rung can hold and still answer.
MAX_BYTES = 64 * 1024

# WHO 2021 24-hour guideline and interim target 1. The same two numbers the rules, the digest and the dashboard use.
CLEAN, ACT = 15.0, 35.0


# Two days. A node that was off for a week does not open its first report with a hundred and sixty-eight hours of
# history: the household wants to know about now, and the bundle would not fit anyway.
MAX_WINDOW = 48


def due_hours(every: int, anchor: int) -> list[int]:
    """The local hours a report is due: the anchor, and every `every` hours after it, wrapping at midnight.

    An interval that does not divide 24 would walk round the clock — 06:00 on Monday, 05:00 on Tuesday — so it
    falls back to six rather than leaving the household with a rhythm nobody chose. settings.set refuses those
    values, but .env is edited by hand and the scheduler is the last place that can catch it."""
    if not every or every <= 0 or every > 24 or 24 % every:
        every = 6
    return sorted({(anchor % 24 + k * every) % 24 for k in range(24 // every)})


def held_hours(since, due, every: int, cap: int = MAX_WINDOW) -> int:
    """The hours a report must cover beyond its own interval, because the reports before it were held.

    `since` is the end of the last window a household actually read. Counted as the span from there, not as the
    sum of the held reports' windows: a held report already carries the hours held before it, so summing them
    counts the same night twice, and by the third held report in a row the window was three times the truth."""
    if not since:
        return 0
    return max(0, min(round((due - since).total_seconds() / 3600), cap) - every)


# The names the bundle owns. A pack that contributes under one of these would overwrite the node's own numbers,
# and a model reading the document would have no way to tell.
RESERVED = ("meta", "series", "now", "observations", "alerts", "open_act", "sensors_quiet", "rho", "previous",
            "cells", "health", "rules")


def _tz() -> str:
    return os.getenv("NODE_TZ", "").strip() or "UTC"


def _local_now() -> datetime:
    try:
        return datetime.now(ZoneInfo(_tz()))
    except Exception:  # noqa: BLE001
        return datetime.now(timezone.utc)


SERIES_SQL = """
WITH win AS (
  SELECT r.sensor_id, r.metric, r.bucket, r.mean, r.min AS lo, r.max AS hi, r.n
    FROM readings_1h r
   WHERE r.bucket > now() - make_interval(hours => %(h)s)
), agg AS (
  SELECT sensor_id, metric, min(bucket) AS t0, max(bucket) AS t1,
         min(lo) AS lo, max(hi) AS hi, sum(n)::int AS n,
         sum(mean * n) / nullif(sum(n), 0) AS mean,
         sum(mean * n) FILTER (WHERE bucket <  now() - make_interval(secs => %(half_s)s))
           / nullif(sum(n) FILTER (WHERE bucket <  now() - make_interval(secs => %(half_s)s)), 0) AS mean_first,
         sum(mean * n) FILTER (WHERE bucket >= now() - make_interval(secs => %(half_s)s))
           / nullif(sum(n) FILTER (WHERE bucket >= now() - make_interval(secs => %(half_s)s)), 0) AS mean_last
    FROM win GROUP BY 1, 2
), hrs AS (
  SELECT DISTINCT extract(hour FROM bucket)::int AS h FROM win
), base AS (
  -- the same local hours on each of the previous seven days, one mean per day. The session time zone is NODE_TZ,
  -- so extract(hour) and ::date are already this household's hours and days, not UTC's.
  SELECT r.sensor_id, r.metric, r.bucket::date AS d, sum(r.mean * r.n) / nullif(sum(r.n), 0) AS m
    FROM readings_1h r
   WHERE r.bucket <= now() - make_interval(hours => %(h)s)
     AND r.bucket >  now() - make_interval(hours => %(h)s) - interval '7 days'
     AND extract(hour FROM r.bucket)::int IN (SELECT h FROM hrs)
   GROUP BY 1, 2, 3
), bstat AS (
  SELECT sensor_id, metric, avg(m) AS bmean, stddev_samp(m) AS bsd, count(*)::int AS ndays
    FROM base GROUP BY 1, 2
)
SELECT a.sensor_id, a.metric, a.t0, a.t1, a.lo, a.hi, a.n, a.mean, a.mean_first, a.mean_last,
       s.name, s.local, s.indoor, s.kind, b.ndays, b.bmean,
       CASE WHEN b.ndays >= 3 AND b.bsd > 0 THEN (a.mean - b.bmean) / b.bsd END AS notability
  FROM agg a JOIN sensors s USING (sensor_id) LEFT JOIN bstat b USING (sensor_id, metric)
 ORDER BY abs(coalesce(CASE WHEN b.ndays >= 3 AND b.bsd > 0 THEN (a.mean - b.bmean) / b.bsd END, 0)) DESC,
          a.sensor_id, a.metric
"""

OBS_SQL = """
SELECT o.sensor_id, o.metric, o.value, o.ts,
       (SELECT r.value FROM readings r
         WHERE r.sensor_id = o.sensor_id AND r.metric = o.metric AND r.ts <= now() - interval '24 hours'
         ORDER BY r.ts DESC LIMIT 1) AS day_ago
  FROM observations o
 WHERE o.sensor_id = ANY(%(points)s)
 ORDER BY o.sensor_id, o.metric
"""

ALERTS_SQL = """
SELECT a.id, a.ts, a.rule_id, a.sensor_id, a.level, split_part(a.text, E'\\n', 1) AS line,
       EXISTS (SELECT 1 FROM actions x WHERE x.alert_id = a.id) AS acted
  FROM alerts a
 WHERE a.ts > now() - make_interval(hours => %(h)s) AND a.rule_id NOT LIKE 'briefing%%'
 ORDER BY a.ts DESC
"""

OPEN_ACT_SQL = """
SELECT a.id, a.ts, a.rule_id, a.sensor_id, split_part(a.text, E'\\n', 1) AS line
  FROM alerts a
 WHERE a.level = 'act' AND a.ts > now() - interval '24 hours'
   AND NOT EXISTS (SELECT 1 FROM actions x WHERE x.alert_id = a.id)
 ORDER BY a.ts DESC LIMIT 5
"""

# A sensor silent for three days has no row in `stats` at all (it looks back 24 hours), so "quiet" has to be asked
# of `sensors` and answered by the absence of a fresh row, not by a large silent_minutes.
QUIET_SQL = """
SELECT s.sensor_id, s.name,
       (SELECT round(extract(epoch FROM now() - max(r.ts)) / 60) FROM readings r WHERE r.sensor_id = s.sensor_id) AS silent_minutes
  FROM sensors s
 WHERE s.local
   AND NOT EXISTS (SELECT 1 FROM stats t WHERE t.sensor_id = s.sensor_id AND t.silent_minutes < 180)
 ORDER BY s.sensor_id
"""

# Where every sensor stands right now, from the same view the rules read. The window says what happened; this says
# whether it is over. Part four of the sheet ("the kitchen is back under 35") is this against the rule's threshold.
NOW_SQL = """
SELECT sensor_id, name, metric, indoor, local, kind,
       round(last::numeric, 2) AS last, round(mean_15m::numeric, 2) AS mean_15m,
       round(mean_1h::numeric, 2) AS mean_1h, round(silent_minutes) AS silent_minutes,
       (SELECT s.meta->>'role' FROM sensors s WHERE s.sensor_id = stats.sensor_id) AS role
  FROM stats ORDER BY local DESC, indoor DESC, sensor_id, metric
"""

PREV_SQL = "SELECT id, ts, text, cells, window_hours, held_quiet FROM reports WHERE sent ORDER BY ts DESC LIMIT 1"


def _trend(row: dict) -> str:
    """rising / falling / steady, from the second half of the window against the first."""
    a, b = row.get("mean_first"), row.get("mean_last")
    if a is None or b is None:
        return "steady"
    lo, hi = row.get("lo"), row.get("hi")
    span = (float(hi) - float(lo)) if lo is not None and hi is not None else 0.0
    step = TREND.get(row["metric"], max(span * 0.05, 1e-9))
    d = float(b) - float(a)
    return "rising" if d > step else "falling" if d < -step else "steady"


def _f(v, d=1):
    return None if v is None else round(float(v), d)


def _num(v):
    """A number from Postgres as JSON sees it: `numeric` arrives as Decimal, which is not JSON and reads as
    "Decimal('17')" to anything that stringifies it. Counts stay whole; everything else keeps two decimals."""
    if v is None or isinstance(v, (bool, str)):
        return v
    try:
        f = float(v)
    except (TypeError, ValueError):
        return v
    return int(f) if f == int(f) else round(f, 2)


def bundle(cur, hours: int, held_hours: int = 0) -> dict:
    """Every number the node has about the last `hours`, as one JSON-able document. SQL only: no source is polled
    and nothing leaves the machine. `held_hours` are the extra hours folded in from a report quiet hours held.

    Read as planetai_ro wherever the pack pattern allows, so a query here cannot write and cannot see `settings`.
    """
    hours = int(hours) + int(held_hours)
    loc = _local_now()
    b: dict = {"meta": {
        "node": os.getenv("NODE_NAME", "node"), "locale": settings.get("ALERT_LOCALE", "en") or "en",
        "tz": _tz(), "local_time": loc.strftime("%H:%M"), "local_date": loc.strftime("%Y-%m-%d"),
        "local_weekday": loc.strftime("%A"), "local_hour": loc.hour,
        "window_hours": hours, "held_hours": int(held_hours), "folds_a_held_report": bool(held_hours),
        "truncated": 0,
    }}

    p = {"h": hours, "half_s": hours * 1800}      # make_interval(hours =>) wants an integer; half the window in seconds does not
    rows = index.run_ro(cur, SERIES_SQL, p)
    b["series"] = [{
        "sensor_id": r["sensor_id"], "metric": r["metric"], "name": r["name"], "local": r["local"],
        "indoor": r["indoor"], "kind": r["kind"],
        "start": r["t0"].isoformat() if r["t0"] else None, "end": r["t1"].isoformat() if r["t1"] else None,
        "min": _f(r["lo"]), "max": _f(r["hi"]), "mean": _f(r["mean"]), "n": r["n"],
        "trend": _trend(r), "notability": _f(r["notability"], 2),
        "usual": _f(r["bmean"]), "baseline_days": r["ndays"] or 0,
    } for r in rows]

    b["observations"] = []
    for r in index.run_ro(cur, OBS_SQL, {"points": list(POINTS)}):
        group, labels = LABELS.get(r["sensor_id"], (r["sensor_id"], {}))
        b["observations"].append({"group": group, "sensor_id": r["sensor_id"], "metric": r["metric"],
                                  "means": labels.get(r["metric"], r["metric"]), "value": _f(r["value"], 2),
                                  "day_ago": _f(r["day_ago"], 2), "at": r["ts"].isoformat() if r["ts"] else None})

    b["now"] = [{"sensor_id": r["sensor_id"], "name": r["name"], "metric": r["metric"], "indoor": r["indoor"],
                 "local": r["local"], "kind": r["kind"], "last": _f(r["last"], 2), "mean_15m": _f(r["mean_15m"], 2),
                 "mean_1h": _f(r["mean_1h"], 2), "silent_minutes": int(r["silent_minutes"]) if r["silent_minutes"] is not None else None,
                 "role": r.get("role")}
                for r in index.run_ro(cur, NOW_SQL)]

    b["alerts"] = [{"id": r["id"], "at": r["ts"].isoformat(), "rule": r["rule_id"], "sensor_id": r["sensor_id"],
                    "level": r["level"], "line": r["line"], "acted": r["acted"]}
                   for r in index.run_ro(cur, ALERTS_SQL, p)]
    b["open_act"] = [{"id": r["id"], "at": r["ts"].isoformat(), "rule": r["rule_id"], "sensor_id": r["sensor_id"],
                      "line": r["line"]} for r in index.run_ro(cur, OPEN_ACT_SQL)]
    b["sensors_quiet"] = [{"sensor_id": r["sensor_id"], "name": r["name"],
                           "silent_minutes": int(r["silent_minutes"]) if r["silent_minutes"] is not None else None}
                          for r in index.run_ro(cur, QUIET_SQL)]

    b["rho"] = {"now": index.rho(cur), "week_ago": index.rho(cur, days_ago=7)}

    # the previous report, and the cells it carried, so this one can say which numbers moved
    cur.execute(PREV_SQL)
    prev = cur.fetchone()
    b["previous"] = None if not prev else {"id": prev["id"], "at": prev["ts"].isoformat(), "text": prev["text"],
                                           "window_hours": prev["window_hours"]}
    was = {c["id"]: c.get("value") for c in (prev or {}).get("cells") or []}
    b["cells"] = []
    try:
        for c in index.cells(cur):
            v = c.get("value")
            b["cells"].append({"id": c["cell"], "value": v, "unit": c.get("unit", ""),
                               "provenance": c.get("state", "partial"),
                               "changed": None if c["cell"] not in was else was[c["cell"]] != v})
    except Exception as e:  # noqa: BLE001 — a broken pack cell must not cost the household its report
        log.warning("cells unavailable for the report: %s", e)

    try:
        import packs
        b["rules"] = sorted(r["id"] for r in packs.rules())
        for r in packs.contributors("report"):
            key = r["id"].split("/")[-1]
            if key in RESERVED:
                log.warning("pack rule %s contributes under a name the bundle already uses; skipped", r["id"])
                continue
            try:
                rows = index.run_ro(cur, r["sql"])
            except Exception as e:  # noqa: BLE001 — one broken pack must not cost the household its report
                log.warning("pack rule %s failed: %s", r["id"], e); continue
            b[key] = {k: _num(v) for k, v in (rows[0] if rows else {}).items()} or None
    except Exception as e:  # noqa: BLE001
        b["rules"] = []
        log.warning("pack rules unavailable for the report: %s", e)

    # packs/make, when it is on. One row, the nearest, read straight out of what the pack stored so the
    # report cannot disagree with the database about which lab is closest. Absent when no pack has run:
    # the report then simply has nothing to say about where to go, which is honest.
    try:
        fac = index.run_ro(cur, """SELECT name, meta FROM sensors
                                   WHERE kind = 'facility' AND source = 'fablabs-io'
                                   ORDER BY (meta->>'distance_km')::float NULLS LAST LIMIT 1""", {})
        b["facility"] = ({"name": fac[0]["name"], "meta": fac[0]["meta"]} if fac else None)
    except Exception as e:  # noqa: BLE001
        b["facility"] = None
        log.warning("facilities unavailable for the report: %s", e)

    try:
        import agent
        b["health"] = agent.health_check()
    except Exception as e:  # noqa: BLE001
        b["health"] = {"ok": None, "checks": [], "error": type(e).__name__}
        log.warning("health check unavailable for the report: %s", e)

    return _fit(b)


def _fit(b: dict) -> dict:
    """Keep the document under MAX_BYTES by dropping the least notable series first — they are already sorted, so
    the ones that go are the ones the report would not have mentioned. meta.truncated says how many went."""
    while len(json.dumps(b, default=str).encode()) > MAX_BYTES and b.get("series"):
        b["series"].pop()
        b["meta"]["truncated"] += 1
    if b["meta"]["truncated"]:
        log.info("report bundle over %d kB: dropped %d series", MAX_BYTES // 1024, b["meta"]["truncated"])
    return b


# ---------------------------------------------------------------------------------------------------- the sheet
# What an act-level rule watches, and the line it watches for, so the report can say whether the value came back
# down. The numbers are the rules' own; tests/test_report_templates.py refuses a value here that is not in that
# rule's SQL, the same way a pack README's thresholds are checked against its files. A rule that is not here gets
# no sentence rather than a guessed one: heat_stress_now watches an apparent temperature that no column holds, and
# in v0.39 it becomes a condition with an outcome of its own.
THRESHOLDS = {
    "air-quality/indoor_pm25_high":      ("pm25", 35.5),
    "air-quality/outside_worse_keep_shut": ("pm25", 35.5),
    "air-quality/outdoor_pm25_high":     ("pm25", 55.5),
    "air-quality/inside_worse_ventilate": ("pm25", 15.0),
}

# What the node may mention beyond its own sensors: an observation that crossed a line a rule on this node cares
# about. Nothing else. There is no UV rule and no rain rule in any pack that ships, so the report says nothing
# about UV or rain — a number with no rule behind it is a fact nobody asked for.
BEYOND = {
    "coast/heavy_swell": ("beyond_swell", lambda o: (o.get(("marine-point", "swell_height_m")) or 0) >= 2.5
                                                and (o.get(("marine-point", "swell_period_s")) or 0) >= 12),
    "air-quality/indoor_pm25_high": ("beyond_satellite", lambda o: (o.get(("cams-point", "pm25_model")) or 0) > ACT),
}

# One dict per language. Every phrase a household reads is in here; the code decides which key, never the words,
# so a new language is this dict again and nothing else. `id` and `es` are assistant-written and are waiting on a
# native reader — see docs/BETA_TESTER_GUIDE.md.
T = {
    "en": {
        "folded": "Overnight and this morning.",
        "state_hot": "🥵 It is dangerously hot inside.",
        "state_heat": "🌡️ It is hot inside: it feels like 35 °C or more.",
        "state_bad": "😷 The air inside is unhealthy right now.",
        "state_warm": "🌫️ The air inside is middling: not clean, not unhealthy.",
        "state_clean": "✅ The air inside is clean.",
        "state_no_sensor": "🛰️ No sensor inside yet, so what follows is the district and not your rooms.",
        "state_climate": "🏠 Inside it is {t}°C and {h}% humidity.", "state_climate_t": "🏠 Inside it is {t}°C.",
        "wind": "Wind from the {dir}, {kn} knots.",
        "changed": "What changed: {clauses}.",
        "changed_high": "{place}: the {what} ran higher than usual",
        "changed_low": "{place}: the {what} sat lower than usual",
        "what_pm25": "air", "what_temp": "heat", "what_humidity": "damp",
        "beyond_swell": "Out at sea a big, long-period swell is arriving.",
        "beyond_satellite": "The satellite has the whole district above the line to act on.",
        "after": "After the alert: {clauses}.",
        # packs/make. A report that ends on a number leaves nowhere to go; this ends on a place.
        "make": "Nearest place to make or fix something: {where}.",
        "after_under": "{place} is back under {n}",
        "after_above": "{place} is still above {n}",
        "todo_above": "👉 {place} is the one to deal with before the next report.",
        "todo_quiet": "👉 Check {place}: it has stopped sending.",
        "todo_health": "👉 The node itself needs a look: {fix}",
        "todo_none": "👉 Nothing needs doing before the next report.",
        "ask": "Ask me anything about the air, the heat, the sea or what is around here.",
    },
    "id": {
        "folded": "Semalam dan pagi ini.",
        "state_hot": "🥵 Di dalam panasnya berbahaya.",
        "state_heat": "🌡️ Di dalam panas: terasa 35 °C atau lebih.",
        "state_bad": "😷 Udara di dalam sedang tidak sehat.",
        "state_warm": "🌫️ Udara di dalam sedang-sedang: belum bersih, belum tidak sehat.",
        "state_clean": "✅ Udara di dalam bersih.",
        "state_no_sensor": "🛰️ Belum ada sensor di dalam, jadi ini kecamatan, bukan ruangan Anda.",
        "state_climate": "🏠 Di dalam {t}°C, kelembapan {h}%.", "state_climate_t": "🏠 Di dalam {t}°C.",
        "wind": "Angin dari {dir}, {kn} knot.",
        "changed": "Yang berubah: {clauses}.",
        "changed_high": "{place}: {what}nya lebih tinggi dari biasanya",
        "changed_low": "{place}: {what}nya lebih rendah dari biasanya",
        "what_pm25": "udara", "what_temp": "panas", "what_humidity": "kelembapan",
        "beyond_swell": "Di laut ombak besar berperiode panjang sedang datang.",
        "beyond_satellite": "Satelit melihat seluruh kecamatan di atas batas untuk bertindak.",
        "after": "Setelah peringatan: {clauses}.",
        "make": "Tempat terdekat untuk membuat atau memperbaiki sesuatu: {where}.",
        "after_under": "{place} sudah di bawah {n}",
        "after_above": "{place} masih di atas {n}",
        "todo_above": "👉 {place} yang perlu diurus sebelum laporan berikutnya.",
        "todo_quiet": "👉 Cek {place}: sudah tidak mengirim data.",
        "todo_health": "👉 Node-nya sendiri perlu dilihat: {fix}",
        "todo_none": "👉 Tidak ada yang perlu dilakukan sebelum laporan berikutnya.",
        "ask": "Tanya apa saja tentang udara, panas, laut, atau apa yang ada di sekitar sini.",
    },
    "es": {
        "folded": "La noche y esta mañana.",
        "state_hot": "🥵 Dentro hace un calor peligroso.",
        "state_heat": "🌡️ Dentro hace calor: la sensación es de 35 °C o más.",
        "state_bad": "😷 El aire de dentro está insalubre ahora mismo.",
        "state_warm": "🌫️ El aire de dentro está a medias: ni limpio ni insalubre.",
        "state_clean": "✅ El aire de dentro está limpio.",
        "state_no_sensor": "🛰️ Aún no hay sensor dentro, así que esto es la comuna y no tus habitaciones.",
        "state_climate": "🏠 Dentro hay {t}°C y {h}% de humedad.", "state_climate_t": "🏠 Dentro hay {t}°C.",
        "wind": "Viento del {dir}, {kn} nudos.",
        "changed": "Lo que cambió: {clauses}.",
        "changed_high": "{place}: el {what} estuvo más alto de lo habitual",
        "changed_low": "{place}: el {what} estuvo más bajo de lo habitual",
        "what_pm25": "aire", "what_temp": "calor", "what_humidity": "vapor",
        "beyond_swell": "Mar adentro llega un oleaje grande y de periodo largo.",
        "beyond_satellite": "El satélite ve toda la comuna por encima de la línea para actuar.",
        "after": "Después de la alerta: {clauses}.",
        "make": "El lugar más cercano para fabricar o reparar algo: {where}.",
        "after_under": "{place} volvió por debajo de {n}",
        "after_above": "{place} sigue por encima de {n}",
        "todo_above": "👉 {place} es lo que hay que atender antes del próximo informe.",
        "todo_quiet": "👉 Revisa {place}: dejó de enviar datos.",
        "todo_health": "👉 El nodo mismo necesita una revisión: {fix}",
        "todo_none": "👉 No hay nada que hacer antes del próximo informe.",
        "ask": "Pregúntame lo que quieras sobre el aire, el calor, el mar o lo que hay por aquí.",
    },
}


def _place(row: dict) -> str:
    """What a household calls the thing. Sensors are named '<node> - <room>' by the wizard, so the room is what
    is left after the dash; anything else is used whole, and a sensor with no name at all is its id."""
    name = (row.get("name") or "").strip()
    return (name.split(" - ")[-1].strip() or name) if name else str(row.get("sensor_id") or "")


def _n(v: float) -> str:
    return str(int(v)) if float(v) == int(v) else f"{float(v):g}"


def sheet(b: dict, locale: str = "en") -> str:
    """The node's own report: six parts, plain text, deterministic, under a hundred words. This is what a household
    on a node with no model gets, and it is the ruler a model's rewrite is checked against."""
    t = T.get((locale or "en").split("-")[0], T["en"])
    rules = set(b.get("rules") or [])
    now = b.get("now") or []
    parts = []

    # 1. where the place stands
    lead = t["folded"] + " " if b.get("meta", {}).get("folds_a_held_report") else ""
    indoor = [r.get("mean_15m") or r.get("mean_1h") or r.get("last")
              for r in now if r.get("local") and r.get("indoor") and r["metric"] == "pm25"]
    indoor = [v for v in indoor if v is not None]
    heat = [(a.get("rule") or "") for a in b.get("open_act") or [] if (a.get("rule") or "").startswith("heat/")]
    if "heat/heat_danger" in heat:
        parts.append(lead + t["state_hot"])          # feels like 40 °C or more: the one heat line called danger
    elif heat:
        # heat_stress_now's 35 is node #1's ordinary afternoon (SPEC_alerts §1): said as a fact, never as danger
        parts.append(lead + t["state_heat"])
    elif not indoor:
        # No indoor air sensor, but a room with a thermometer is still "a sensor inside". The one the household chose
        # as its reference (not a `secondary` room) speaks for the house.
        room = {r["metric"]: (r.get("mean_15m") or r.get("mean_1h") or r.get("last"))
                for r in now if r.get("local") and r.get("indoor") and r.get("role") != "secondary"
                and r["metric"] in ("temp", "humidity") and (r.get("silent_minutes") or 0) <= 180}
        if room.get("temp") is not None:
            parts.append(lead + (t["state_climate"].format(t=round(room["temp"], 1), h=round(room["humidity"]))
                                 if room.get("humidity") is not None else t["state_climate_t"].format(t=round(room["temp"], 1))))
        else:
            parts.append(lead + t["state_no_sensor"])
    else:
        worst = max(indoor)
        parts.append(lead + t["state_bad" if worst >= ACT else "state_warm" if worst >= CLEAN else "state_clean"])

    # 2. what changed, and 3. what only the models know — one paragraph
    body = []
    # one clause per place, not per metric: "the kitchen's air ran higher, the kitchen's heat ran lower" is one
    # story told twice, and the second half of it is noise.
    moved, seen = [], set()
    for s in b.get("series") or []:
        if not (s.get("local") and s.get("kind") == "sensor" and abs(s.get("notability") or 0) >= 1.5):
            continue
        if s["sensor_id"] in seen:
            continue
        seen.add(s["sensor_id"]); moved.append(s)
        if len(moved) == 2:
            break
    if moved:
        clauses = [t["changed_high" if (s["notability"] or 0) > 0 else "changed_low"].format(
            place=_place(s), what=t.get(f"what_{s['metric']}", s["metric"])) for s in moved]
        body.append(t["changed"].format(clauses=", ".join(clauses)))
    obs = {(o["sensor_id"], o["metric"]): o.get("value") for o in b.get("observations") or []}
    for rule, (key, crossed) in BEYOND.items():
        if rule in rules and crossed(obs):
            body.append(t[key])
            break                       # one clause, not a weather report
    spd = next((r for r in now if r["sensor_id"] == "nea-windspeed" and r["metric"] == "wind_speed"), None)
    dr = next((r for r in now if r["sensor_id"] == "nea-winddir" and r["metric"] == "wind_dir"), None)
    if spd and dr and spd.get("last") is not None and dr.get("last") is not None \
            and (spd.get("silent_minutes") or 0) <= 180 and (dr.get("silent_minutes") or 0) <= 180:
        pts = ("N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW")
        body.append(t["wind"].format(dir=pts[int((dr["last"] % 360) / 22.5 + 0.5) % 16], kn=_n(round(spd["last"]))))
    if body:
        parts.append(" ".join(body))

    # 4. what happened after this window's alerts, and 5. the one thing to do — one paragraph
    tail = []
    outcomes, still_above = [], None
    for a in [x for x in b.get("alerts") or [] if x.get("level") == "act"]:
        watch = THRESHOLDS.get(a.get("rule") or "")
        if not watch:
            continue
        metric, line = watch
        cur = next((r for r in now if r["sensor_id"] == a.get("sensor_id") and r["metric"] == metric), None)
        v = None if not cur else (cur.get("mean_15m") or cur.get("mean_1h") or cur.get("last"))
        if v is None:
            continue
        over = v >= line
        outcomes.append(t["after_above" if over else "after_under"].format(place=_place(cur), n=_n(line)))
        if over and still_above is None:
            still_above = cur
        if len(outcomes) == 2:
            break
    if outcomes:
        tail.append(t["after"].format(clauses=", ".join(outcomes)))

    # Where to go, if this node knows. It is deliberately AFTER the outcomes: a person reads what
    # happened first, and only then is told where somebody could do something about it.
    fac = b.get("facility")
    if fac:
        try:
            # Same fix as app/issues/engine.py::_where_to_go: the old "../packs" default is not
            # where a node keeps its packs, so this line never ran on one. packs.module() knows.
            # Imported here because sheet() is not the function that imports packs at module level.
            import packs as _packs
            _mod = _packs.module("make")
            where = _mod.ask_line([fac], locale) if hasattr(_mod, "ask_line") else None
        except Exception:  # noqa: BLE001 — a missing or broken pack must not cost the report
            where = None
        if where:
            tail.append(t["make"].format(where=where))

    quiet = (b.get("sensors_quiet") or [None])[0]
    bad_check = next((c for c in (b.get("health") or {}).get("checks") or [] if not c.get("ok") and c.get("fix")), None)
    if still_above is not None:
        tail.append(t["todo_above"].format(place=_place(still_above)))
    elif quiet:
        tail.append(t["todo_quiet"].format(place=_place(quiet)))
    elif bad_check:
        tail.append(t["todo_health"].format(fix=bad_check["fix"].split(";")[0].split(".")[0]))
    else:
        tail.append(t["todo_none"])
    parts.append(" ".join(tail))

    # 6. the invitation
    parts.append(t["ask"])
    return "\n\n".join(parts)      # a part with nothing to say was never appended
