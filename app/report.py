"""What the node knows about the window it is about to report on, and the report it writes from that on its own.

Two things live here, in this order, because the second is the ruler for everything that comes after it:

  bundle(cur, hours)      every number the node has about the last `hours`, as one JSON-able document
  sheet(bundle, locale)   the node's own report, deterministic, four parts, under a hundred words

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
import learn
from actions import rooms_said
import packs
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
RESERVED = ("meta", "series", "now", "observations", "alerts", "open_act", "open_events", "sensors_quiet", "rho", "previous",
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
   WHERE r.bucket > now() - make_interval(hours => %(h)s) AND """ + packs.public_sql("r") + """
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
 WHERE s.local AND s.kind = 'sensor'
   AND NOT EXISTS (SELECT 1 FROM stats t WHERE t.sensor_id = s.sensor_id AND t.silent_minutes < 180)
 ORDER BY s.sensor_id
"""

# Where every sensor stands right now, from the same view the rules read. The window says what happened; this says
# whether it is over. Part four of the sheet ("the kitchen is back under 35") is this against the rule's threshold.
NOW_SQL = """
SELECT sensor_id, name, metric, indoor, local, kind,
       round(last::numeric, 2) AS last, round(mean_15m::numeric, 2) AS mean_15m,
       round(mean_1h::numeric, 2) AS mean_1h, round(silent_minutes) AS silent_minutes
  FROM stats WHERE """ + packs.public_sql("stats") + """ ORDER BY local DESC, indoor DESC, sensor_id, metric
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
                 "mean_1h": _f(r["mean_1h"], 2), "silent_minutes": int(r["silent_minutes"]) if r["silent_minutes"] is not None else None}
                for r in index.run_ro(cur, NOW_SQL)]

    # On ALERT_ENGINE=events the engine speaks for the packs it replaced, from its first message on, and their rules
    # still record rows nobody received (learn.silent). The report tells what was sent: node #1's 19:00 report on
    # 14 Oct opened "It is hot inside" from a heat row the household never got, while the page said it was bearable.
    try:
        rep = learn.replaced(packs.load_rules(), settings.get("ALERT_ENGINE", "rules") or "rules")
    except Exception as e:  # noqa: BLE001 — no rule set, nothing to leave out
        log.warning("report: cannot read the rule set to leave silent alerts out: %s", e)
        rep = set()
    since = None
    if rep:
        cur.execute("SELECT min(ts) AS t FROM event_messages WHERE mode = 'events'")
        since = (cur.fetchone() or {}).get("t")
    told = lambda r: not learn.silent(r["rule_id"], r["ts"], rep, since)  # noqa: E731
    b["alerts"] = [{"id": r["id"], "at": r["ts"].isoformat(), "rule": r["rule_id"], "sensor_id": r["sensor_id"],
                    "level": r["level"], "line": r["line"], "acted": r["acted"]}
                   for r in index.run_ro(cur, ALERTS_SQL, p) if told(r)]
    b["open_act"] = [{"id": r["id"], "at": r["ts"].isoformat(), "rule": r["rule_id"], "sensor_id": r["sensor_id"],
                      "line": r["line"]} for r in index.run_ro(cur, OPEN_ACT_SQL) if told(r)]
    # what the engine has open and has told the household, which stands in for the replaced packs' open alerts
    b["open_events"] = []
    if rep:
        cur.execute("""SELECT issue, kind, opened_at, rooms FROM alert_events
                       WHERE cleared_at IS NULL AND ever_sent AND level = 'act' ORDER BY opened_at""")
        b["open_events"] = [{"issue": r["issue"], "kind": r["kind"], "at": r["opened_at"].isoformat(),
                             "rooms": sorted(r.get("rooms") or [])} for r in cur.fetchall()]
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
def thresholds() -> dict:
    """{rule id: (metric, line, whose line)}: what an act-level rule watches, the line it watches for, and whose line
    that is, so the report can say whether the value came back down and name the line with its unit (Tomas, 14 Oct:
    never a bare "35.5"). A rule declares it as `line: {value, label}` in its pack's rules.yml, and the metric is its
    issue's own (issues.owners()); until 23 Oct 2026 this was a map here naming air-quality's four rules.
    tests/test_report_templates.py refuses a value that is not in that rule's SQL, the same way a pack README's
    thresholds are checked against its files. A rule without one gets no sentence rather than a guessed one: heat
    speaks through HEAT_LINE and the open episodes instead."""
    import issues                    # noqa: PLC0415
    own = issues.owners()
    return {r["id"]: ((own.get(r["id"].split("/")[0]) or {}).get("metric"), float(r["line"]["value"]), r["line"]["label"])
            for r in packs.load_rules() if isinstance(r.get("line"), dict) and "/" in r["id"]}
# This house's heat line, feels-like. The same number as packs/heat/issue.yml's `line.value`; the test holds them equal.
HEAT_LINE = 35.0

# What the node may mention beyond its own sensors: an observation that crossed a line a rule on this node cares
# about. Nothing else. There is no UV rule and no rain rule in any pack that ships, so the report says nothing
# about UV or rain — a number with no rule behind it is a fact nobody asked for.
BEYOND = {
    "coast/heavy_swell": ("beyond_swell", lambda o: (o.get(("marine-point", "swell_height_m")) or 0) >= 2.5
                                                and (o.get(("marine-point", "swell_period_s")) or 0) >= 12),
    "air-quality/indoor_pm25_high": ("beyond_satellite", lambda o: (o.get(("cams-point", "pm25_model")) or 0) > 35.5),
}

# One dict per language. Every phrase a household reads is in here; the code decides which key, never the words,
# so a new language is this dict again and nothing else. `id` and `es` are ASSISTANT-WRITTEN and are waiting on a
# native reader — see docs/BETA_TESTER_GUIDE.md.
#
# THE VOICE (design review of node #1, 14 Oct): the headline is the state in words, with one sign and no number; then
# what happened, per room and with the local time; then the one thing to do; then the invitation, last. A line is
# always named with its owner and its unit. A "what changed" sentence says what a person would say about the room
# ("Studio was more humid than usual"), never "the damp ran higher".
T = {
    "en": {
        "folded": "Overnight and this morning.",
        "state_hot": "🥵 It is dangerously hot inside.",
        "state_heat": "🌡️ It is hot inside.",
        "state_bad": "😷 The air inside is unhealthy right now.",
        "state_warm": "🌫️ The air inside is middling: not clean, not unhealthy.",
        "state_clean": "✅ The air inside is clean.",
        "state_no_sensor": "🛰️ No sensor inside yet, so what follows is the district and not your rooms.",
        "high_pm25": "The air in {place} was dirtier than usual.",
        "low_pm25": "The air in {place} was cleaner than usual.",
        "high_temp": "{place} was warmer than usual.",
        "low_temp": "{place} was cooler than usual.",
        "high_humidity": "{place} was more humid than usual.",
        "low_humidity": "{place} was drier than usual.",
        "beyond_swell": "Out at sea a big, long-period swell is arriving.",
        "beyond_satellite": "The European air model puts the whole district past the US EPA's unhealthy level, 35.5 µg/m³.",
        "heat_over": "In {rooms} it has felt past {line}, since {at}.",
        "heat_usual": "In {rooms} it has been hotter than usual since {at}.",
        "line_heat": "this house's heat line, {n} °C feels-like",
        "line_who": "the WHO line, {n} µg/m³",
        "line_epa": "the US EPA's unhealthy level, {n} µg/m³",
        "line_epa_all": "the US EPA's level unhealthy for everyone, {n} µg/m³",
        "after_under": "{place} went past {line}, at {at}; it is back under now.",
        "after_above": "{place} went past {line}, at {at}, and is still past it.",
        # packs/make. A report that ends on a number leaves nowhere to go; this ends on a place.
        "make": "Nearest place to make or fix something: {where}.",
        "todo_above": "{place} is the one to deal with before the next report.",
        "todo_quiet": "Check {place}: it has stopped sending.",
        "health_poll": "The node has stopped reading its sensors. Check it is switched on.",
        "health_backup": "The last backup did not run. Whoever set up the node can check it.",
        "health_frozen": "A sensor is stuck on the same number: {place}. Switching it off and on again usually fixes it.",
        "health_quiet": "A sensor has gone quiet: {place}.",
        "health_quiet_any": "A sensor has gone quiet.",
        "health_other": "The node itself needs a look. Whoever set it up can see what on the Node page.",
        "todo_none": "Nothing needs doing before the next report.",
        "ask": "Ask me anything about the air, the heat or the sea.",
    },
    "id": {
        "folded": "Semalam dan pagi ini.",
        "state_hot": "🥵 Di dalam panasnya berbahaya.",
        "state_heat": "🌡️ Di dalam panas.",
        "state_bad": "😷 Udara di dalam sedang tidak sehat.",
        "state_warm": "🌫️ Udara di dalam sedang-sedang: belum bersih, belum tidak sehat.",
        "state_clean": "✅ Udara di dalam bersih.",
        "state_no_sensor": "🛰️ Belum ada sensor di dalam, jadi ini kecamatan, bukan ruangan Anda.",
        "high_pm25": "Udara di {place} lebih kotor dari biasanya.",
        "low_pm25": "Udara di {place} lebih bersih dari biasanya.",
        "high_temp": "{place} lebih hangat dari biasanya.",
        "low_temp": "{place} lebih sejuk dari biasanya.",
        "high_humidity": "{place} lebih lembap dari biasanya.",
        "low_humidity": "{place} lebih kering dari biasanya.",
        "beyond_swell": "Di laut ombak besar berperiode panjang sedang datang.",
        "beyond_satellite": "Model udara Eropa menempatkan seluruh kecamatan di atas batas tidak sehat US EPA, 35.5 µg/m³.",
        "heat_over": "Di {rooms} terasa melewati {line}, sejak {at}.",
        "heat_usual": "Di {rooms} lebih panas dari biasanya sejak {at}.",
        "line_heat": "batas panas rumah ini, {n} °C terasa",
        "line_who": "batas WHO, {n} µg/m³",
        "line_epa": "tingkat tidak sehat US EPA, {n} µg/m³",
        "line_epa_all": "tingkat US EPA yang tidak sehat bagi semua orang, {n} µg/m³",
        "after_under": "{place} melewati {line}, pukul {at}; sekarang sudah di bawahnya.",
        "after_above": "{place} melewati {line}, pukul {at}, dan masih di atasnya.",
        "make": "Tempat terdekat untuk membuat atau memperbaiki sesuatu: {where}.",
        "todo_above": "{place} yang perlu diurus sebelum laporan berikutnya.",
        "todo_quiet": "Cek {place}: sudah tidak mengirim data.",
        "health_poll": "Node berhenti membaca sensornya. Pastikan node menyala.",
        "health_backup": "Cadangan terakhir tidak berjalan. Orang yang memasang node bisa memeriksanya.",
        "health_frozen": "Sebuah sensor terus menunjukkan angka yang sama: {place}. Biasanya beres jika dimatikan lalu dinyalakan lagi.",
        "health_quiet": "Sebuah sensor tidak mengirim lagi: {place}.",
        "health_quiet_any": "Sebuah sensor tidak mengirim lagi.",
        "health_other": "Node-nya sendiri perlu dilihat. Orang yang memasangnya bisa melihat apa di halaman Node.",
        "todo_none": "Tidak ada yang perlu dilakukan sebelum laporan berikutnya.",
        "ask": "Tanya apa saja tentang udara, panas, atau laut.",
    },
    "es": {
        "folded": "La noche y esta mañana.",
        "state_hot": "🥵 Dentro hace un calor peligroso.",
        "state_heat": "🌡️ Dentro hace calor.",
        "state_bad": "😷 El aire de dentro está insalubre ahora mismo.",
        "state_warm": "🌫️ El aire de dentro está a medias: ni limpio ni insalubre.",
        "state_clean": "✅ El aire de dentro está limpio.",
        "state_no_sensor": "🛰️ Aún no hay sensor dentro, así que esto es la zona y no tus habitaciones.",
        "high_pm25": "El aire en {place} estuvo más sucio de lo habitual.",
        "low_pm25": "El aire en {place} estuvo más limpio de lo habitual.",
        "high_temp": "En {place} hizo más calor de lo habitual.",
        "low_temp": "En {place} hizo más fresco de lo habitual.",
        "high_humidity": "En {place} hubo más humedad de lo habitual.",
        "low_humidity": "En {place} el aire estuvo más seco de lo habitual.",
        "beyond_swell": "Mar adentro llega un oleaje grande y de periodo largo.",
        "beyond_satellite": "El modelo europeo del aire pone toda la zona por encima del nivel insalubre de la US EPA, 35.5 µg/m³.",
        "heat_over": "En {rooms} la sensación pasa de {line}, desde las {at}.",
        "heat_usual": "En {rooms} hace más calor de lo habitual desde las {at}.",
        "line_heat": "el límite de calor de esta casa, {n} °C de sensación",
        "line_who": "el límite de la OMS, {n} µg/m³",
        "line_epa": "el nivel insalubre de la EPA de EE. UU., {n} µg/m³",
        "line_epa_all": "el nivel de la EPA de EE. UU. insalubre para todos, {n} µg/m³",
        "after_under": "{place} pasó {line}, a las {at}; ya volvió a bajar.",
        "after_above": "{place} pasó {line}, a las {at}, y sigue por encima.",
        "make": "El lugar más cercano para fabricar o reparar algo: {where}.",
        "todo_above": "{place} es lo que hay que atender antes del próximo informe.",
        "todo_quiet": "Revisa {place}: dejó de enviar datos.",
        "health_poll": "El nodo dejó de leer sus sensores. Comprueba que está encendido.",
        "health_backup": "La última copia de seguridad no se hizo. Quien instaló el nodo puede revisarlo.",
        "health_frozen": "Un sensor se quedó en el mismo número: {place}. Apagarlo y encenderlo de nuevo suele arreglarlo.",
        "health_quiet": "Un sensor dejó de enviar: {place}.",
        "health_quiet_any": "Un sensor dejó de enviar.",
        "health_other": "El nodo mismo necesita una revisión. Quien lo instaló puede ver qué en la página Nodo.",
        "todo_none": "No hay nada que hacer antes del próximo informe.",
        "ask": "Pregúntame lo que quieras sobre el aire, el calor o el mar.",
    },
}


# app/agent.py::health_check's `fix` is for whoever runs the node (shell commands, ids); the morning message says the
# same failure in the household's words, keyed by the check's name. A check not listed here gets health_other.
HEALTH = {"polled in the last 15 min": "health_poll", "a backup in the last 2 days": "health_backup",
          "no local sensor's ambient channel is frozen": "health_frozen", "LoRa radios heard in the last hour": "health_quiet"}


def _health_line(check: dict, t: dict) -> str:
    key = HEALTH.get(check.get("check"), "health_other")
    who = ", ".join(_place({"name": n}) for n in check.get("who") or [])
    if key in ("health_frozen", "health_quiet") and not who:   # never the id: no name, no name in the sentence
        key = "health_quiet_any" if key == "health_quiet" else "health_other"
    return t[key].format(place=who)


def _place(row: dict) -> str:
    """What a household calls the thing. Sensors are named '<node> - <room>' by the wizard, so the room is what
    is left after the dash; anything else is used whole, and a sensor with no name at all is its id."""
    name = (row.get("name") or "").strip()
    return (name.split(" - ")[-1].strip() or name) if name else str(row.get("sensor_id") or "")


def _n(v: float) -> str:
    return str(int(v)) if float(v) == int(v) else f"{float(v):g}"


def _at(iso, tz: str) -> str | None:
    """HH:MM in the household's own zone, from the bundle's ISO time; None when it cannot be read, and the
    sentence that needed it is then left out rather than said without its time."""
    try:
        return datetime.fromisoformat(iso).astimezone(ZoneInfo(tz or "UTC")).strftime("%H:%M")
    except Exception:  # noqa: BLE001
        return None


def sheet(b: dict, locale: str = "en") -> str:
    """The node's own report: four parts, plain text, deterministic, under a hundred words. This is what a household
    on a node with no model gets, and it is the ruler a model's rewrite is checked against."""
    loc = (locale or "en").split("-")[0]
    t = T.get(loc, T["en"])
    rules = set(b.get("rules") or [])
    now = b.get("now") or []
    tz = (b.get("meta") or {}).get("tz") or _tz()
    parts = []

    # 1. the headline: where the place stands, in words
    lead = t["folded"] + " " if b.get("meta", {}).get("folds_a_held_report") else ""
    indoor = [r.get("mean_15m") or r.get("mean_1h") or r.get("last")
              for r in now if r.get("local") and r.get("indoor") and r["metric"] == "pm25"]
    indoor = [v for v in indoor if v is not None]
    # heat, per room: the old engine's open act rows (one sensor each) and the event engine's open episodes (rooms)
    heat = [(a.get("rule") or "", _place(next((r for r in now if r["sensor_id"] == a.get("sensor_id")), a)), a.get("at"))
            for a in b.get("open_act") or [] if (a.get("rule") or "").startswith("heat/")]
    heat += [(f"heat/{e.get('kind')}", rooms_said(e.get("rooms") or [], loc), e.get("at"))
             for e in b.get("open_events") or [] if e.get("issue") == "heat"]
    kinds = {k for k, _, _ in heat}
    if "heat/heat_danger" in kinds or "heat/danger" in kinds:
        parts.append(lead + t["state_hot"])          # feels like 40 °C or more: the one heat line called danger
    elif heat:
        # heat_stress_now's 35 is node #1's ordinary afternoon (SPEC_alerts §1): said as a fact, never as danger
        parts.append(lead + t["state_heat"])
    elif not indoor:
        parts.append(lead + t["state_no_sensor"])
    else:
        worst = max(indoor)
        parts.append(lead + t["state_bad" if worst >= ACT else "state_warm" if worst >= CLEAN else "state_clean"])

    # 2. what happened, per room, with the local time: heat, the act alerts and where they stand now, what ran unusual,
    # and what only the models know — one paragraph
    body, told = [], set()
    for kind, rooms, at in heat:
        hm = _at(at, tz)
        if not (rooms and hm) or rooms in told:
            continue
        told.add(rooms)
        over = kind not in ("heat/unusual",)        # the old rules and sustained/danger are past the line; unusual is not
        body.append(t["heat_over" if over else "heat_usual"].format(
            rooms=rooms, at=hm, line=t["line_heat"].format(n=_n(HEAT_LINE))))
        if len(told) == 2:
            break
    still_above, places, lines = None, set(), thresholds()
    for a in [x for x in b.get("alerts") or [] if x.get("level") == "act"]:
        watch = lines.get(a.get("rule") or "")
        if not watch:
            continue
        metric, line, owner = watch
        cur = next((r for r in now if r["sensor_id"] == a.get("sensor_id") and r["metric"] == metric), None)
        v = None if not cur else (cur.get("mean_15m") or cur.get("mean_1h") or cur.get("last"))
        hm = _at(a.get("at"), tz)
        if v is None or hm is None or _place(cur) in places:
            continue                    # one sentence per room: the newest alert on it (alerts come newest first)
        places.add(_place(cur))
        over = v >= line
        body.append(t["after_above" if over else "after_under"].format(
            place=_place(cur), at=hm, line=t[owner].format(n=_n(line))))
        if over and still_above is None:
            still_above = cur
        if len(places) == 2:
            break
    # one sentence per place, not per metric: "the kitchen's air ran higher, the kitchen's heat ran lower" is one
    # story told twice, and the second half of it is noise.
    moved, seen = [], set()
    for s in b.get("series") or []:
        if not (s.get("local") and s.get("kind") == "sensor" and abs(s.get("notability") or 0) >= 1.5):
            continue
        if f"high_{s['metric']}" not in t:
            continue                    # a metric with no household word (bme_iaq) is never named: it reached a report raw
        if s["sensor_id"] in seen:
            continue
        seen.add(s["sensor_id"]); moved.append(s)
        if len(moved) == 2:
            break
    for s in moved:
        body.append(t[("high_" if (s["notability"] or 0) > 0 else "low_") + s["metric"]].format(place=_place(s)))
    obs = {(o["sensor_id"], o["metric"]): o.get("value") for o in b.get("observations") or []}
    for rule, (key, crossed) in BEYOND.items():
        if rule in rules and crossed(obs):
            body.append(t[key])
            break                       # one clause, not a weather report
    if body:
        parts.append(" ".join(body))

    # 3. the one thing to do. Where to go, if this node knows, comes first: a person reads what happened, then where
    # somebody could do something about it, then what is theirs to do.
    tail = []
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
    # A source refusing (Open-Meteo's daily limit, node #1 14 Oct) is not the household's to fix, and its raw error went
    # out cut mid-URL; Node's Running section names failing sources. The to-do keeps what someone here can do.
    bad_check = next((c for c in (b.get("health") or {}).get("checks") or []
                      if not c.get("ok") and c.get("fix") and c.get("check") != "no source errors"), None)
    if still_above is not None:
        tail.append(t["todo_above"].format(place=_place(still_above)))
    elif quiet:
        tail.append(t["todo_quiet"].format(place=_place(quiet)))
    elif bad_check:
        tail.append(_health_line(bad_check, t))
    else:
        tail.append(t["todo_none"])
    parts.append(" ".join(tail))

    # 4. the invitation, always last: main.run_report puts the morning memory above it, not below
    parts.append(t["ask"])
    return "\n\n".join(parts)      # a part with nothing to say was never appended
