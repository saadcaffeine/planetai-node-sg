"""The engine: SQL and arithmetic, and nothing from a model.

`compute()` reads five tables once and answers, for every issue the node declares: which state it is
in and why, the four distances with their values and provenance, the line, the attribution class, the
open asks, twenty-four hours of series at each distance, and one sentence in each of three locales.

Every sentence is a template over numbers this file worked out. There is no prompt anywhere in it: a
node with no agent container, no network and no model reachable produces exactly the same page as one
with all three, which is the invariant the whole dashboard rests on.

Three pieces of arithmetic are worth reading before changing anything:

  · `apparent()` is Steadman's no-wind form, the same expression `packs/heat/rules.yml` evaluates in
    SQL. It is applied PER SENSOR and the results are then aggregated — not the other way round.
    Apparent temperature is not linear in its inputs, so the median of four sensors' apparent
    temperatures is not the apparent temperature of their median temperature and median humidity.
    On node #1's 6 September capture the four indoor units give 30.8 the first way and 30.5 the
    second; 30.8 is what the room felt like.

  · `fenced_median()` trims with median absolute deviation, not with Tukey's fence. A ring is often
    three or four stations, and at three the outlier IS the upper quartile, so 1.5 x IQR calls
    nothing odd. Six MADs above the median, with a floor, so a ring that agrees exactly does not
    collapse onto itself. Lifted from the dashboard (index.html:761) where it was drawing an axis.

  · `_classify()` is the attribution classifier: clear · inside · everywhere · outside_worse ·
    mixed · unknown. It compares by the mode the issue declares, because a concentration compares by
    ratio and a temperature has to compare by difference. The place prompt's own release will
    replace this with the version that also reads wind direction; until then this is the shipped
    dashboard's `why()` logic, moved here and given the six names.
"""
from __future__ import annotations

import logging
import math
import os
import statistics
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from datetime import datetime, timedelta, timezone

import actions as A
import packs

from . import (CMP_WORDS, DIGEST_WORDS, DISTANCES, HEADLINE_RULE, HERO_WORDS, JOIN_WORDS, LABEL_WORDS,
               LOCALES, NOUN_WORDS, PLAIN_WORDS, PROMPT_WORDS, REASON_WORDS, SIMPLE_WORDS,
               SPAN_WORDS, WHERE_WORDS, order, pack_sections)
from . import geometry
from .schema import CLOSED_STAGES, is_open, is_seen, place_of, stage_of

log = logging.getLogger("planetai.issues")
# Said once per process, not once per request: /issues is polled by every open page.
_said_unsited = False

# A device that has said nothing for two hours is not reporting. Same number as the rules and the
# shipped page used, so the stack and the alerts cannot disagree about who is awake.
FRESH_MINUTES = 120
# An act-level ask whose reading has come back is still an ask, but it stops being *now* after this.
ASK_CURRENT_HOURS = 2
# "a warn in the last 24 h" — the window `notable` is measured over.
NOTABLE_HOURS = 24
# An ask is an alert somebody is expected to answer, and ρ is the share of them that got an answer
# (app/index.py:105 counts level='act' and nothing else). So `open_asks` holds act-level alerts only:
# an `info` note was never an ask, and saying "still open, the reading came back" about a digest is
# both untrue and a way to make the strip look busy when nothing is being asked of anyone.
ASK_LEVEL = "act"

# The metrics a station may show on the dashboard, with the unit, the places and the issue each belongs to. A
# 15-minute mean is the coarsest thing a snapshot carries and the finest a page may show per station.
METRICS = {
    "pm25": {"unit": "µg/m³", "dp": 1, "issue": "air", "label": "PM2.5"},
    "pm10": {"unit": "µg/m³", "dp": 1, "issue": "air", "label": "PM10"},
    "pm1": {"unit": "µg/m³", "dp": 1, "issue": "air", "label": "PM1"},
    "aqi": {"unit": "AQI", "dp": 0, "issue": "air", "label": "AQI"},
    "temp": {"unit": "°C", "dp": 1, "issue": "heat", "label": "temperature"},
    "humidity": {"unit": "%", "dp": 0, "issue": "heat", "label": "humidity"},
    "pressure": {"unit": "hPa", "dp": 0, "issue": None, "label": "pressure"},
    "noise": {"unit": "dB", "dp": 0, "issue": None, "label": "noise"},
    "light": {"unit": "lux", "dp": 0, "issue": None, "label": "light"},
    "gas_resistance": {"unit": "kΩ", "dp": 0, "issue": None, "label": "gas resistance"},
    "battery_v": {"unit": "V", "dp": 2, "issue": None, "label": "battery"},
}


def _source_of(sensor_id: str) -> dict:
    """Where a station's data comes from, read off its id the way app/sources.py assigns them."""
    if sensor_id.startswith("sc-"):
        return {"source": "smartcitizen", "url": f"https://smartcitizen.me/kits/{sensor_id[3:]}",
                "attribution": "Smart Citizen, smartcitizen.me"}
    if sensor_id.startswith("bad-"):
        return {"source": "baliairdispatch", "url": "https://baliairdispatch.com",
                "attribution": "Bali Air Dispatch, baliairdispatch.com"}
    if sensor_id.startswith("msh-"):
        return {"source": "meshtastic", "url": None, "attribution": None}
    return {"source": "unknown", "url": None, "attribution": None}


def _stations(stats: list[dict], hourly: list[dict], lat: float, lon: float, sited: bool = True,
              silent: list[dict] | None = None) -> list[dict]:
    """Every station with a coordinate, its own 15-minute means for the metrics the page may show, and the hourly
    series the node has for it. Nothing here is averaged across stations: the street stays a fenced median in the
    stack, and this is the thing the median hides, published beside it by decision of 15 September 2026.

    `sited` is False when this node has no NODE_LAT/NODE_LON. Then `km` is None on every station rather than a
    distance from (0, 0) — a real point in the Gulf of Guinea that every surface drawing this list would otherwise
    print as fact. An unknown distance is published as unknown; the surfaces say so in their own words.

    `silent` is the stations heard within SILENT_DAYS and not in the last day; they keep a row with `last_heard`,
    unless a station heard today stands at the same point."""
    import h3  # noqa: PLC0415 — only this path needs it, and geometry.py already requires it
    def row(r: dict) -> dict:
        return {"sensor_id": r["sensor_id"], "name": r.get("name"), "lat": r["lat"], "lon": r["lon"],
                "local": bool(r.get("local")), "indoor": bool(r.get("indoor")), "kind": r.get("kind") or "sensor",
                **_source_of(r["sensor_id"]),
                "km": round(h3.great_circle_distance((lat, lon), (r["lat"], r["lon"]), unit="km"), 1) if sited
                else None,
                "read": {}, "series": {}}
    by: dict[str, dict] = {}
    for r in stats:
        if r.get("lat") is None or r.get("lon") is None:
            continue
        s = by.setdefault(r["sensor_id"], row(r))
        m = METRICS.get(r.get("metric"))
        if m and r.get("mean_15m") is not None:
            s["read"][r["metric"]] = {"value": round(float(r["mean_15m"]), 2), "unit": m["unit"], "dp": m["dp"],
                                       "silent_minutes": None if r.get("silent_minutes") is None
                                       else round(r["silent_minutes"])}
    # The archive of silence (docs/SPEC_dashboard_figures.md §3.3): a station heard in the last 30 days and not in the
    # last day keeps its row, with when it was last heard. Unless a station heard today stands at the same point: Bali
    # Air Dispatch relays Smart Citizen kits as bad-sc-<kit> and AirGradient ones through OpenAQ, so a relay that
    # stopped is a second road to a kit that still reports, and listing it would call a working kit dead.
    heard = {(round(float(s["lat"]), 5), round(float(s["lon"]), 5)) for s in by.values()}
    for r in silent or []:
        if r.get("lat") is None or r.get("lon") is None or r["sensor_id"] in by:
            continue
        if (round(float(r["lat"]), 5), round(float(r["lon"]), 5)) in heard:
            continue
        lh = r.get("last_heard")
        by[r["sensor_id"]] = {**row(r), "last_heard": lh.isoformat() if hasattr(lh, "isoformat") else lh}
    for h in hourly or []:
        s = by.get(h.get("sensor_id"))
        if s is None:
            continue
        s["series"].setdefault(h["metric"], []).append(
            {"t": h["bucket"] if isinstance(h["bucket"], str) else h["bucket"].isoformat(),
             "mean": h.get("mean"), "min": h.get("min"), "max": h.get("max"), "n": h.get("n")})
    for s in by.values():
        for k in s["series"]:
            s["series"][k].sort(key=lambda x: x["t"])
    # Unsited, every km is None and this is the order they arrived in; the page does not present it as nearness.
    return sorted(by.values(), key=lambda s: (s["km"] is None, s["km"] or 0))


def _where_to_go(facilities: list[dict]) -> dict | None:
    """The `make` pack's sentence, per locale, or None — and this engine does not write it.

    `packs/make/rules.yml` says where the line belongs: to the asks in OTHER packs' rules, "the
    moment you have been told you need something made". So the ledger carries it and the page draws
    it under the ask it answers, rather than a freestanding tile nobody asked for.

    The wording is the pack's, including which lab is nearest and how far: `ask_line` reads the rows
    as STORED, so a distance is never re-derived here and the sentence cannot disagree with the
    database. This function only calls it and only in the languages the node speaks.

    A node with the pack off, or with no lab inside MAKE_RADIUS_KM, has no facility rows and gets
    None. So does a node whose image predates the pack: the import is guarded because `packs/make`
    is a pack, and a pack is a thing a node may simply not have.
    """
    if not facilities:
        return None
    # packs.module() knows where a node keeps its packs. This used to insert "../packs/make" on
    # sys.path and import bare, which is not where the image keeps them — /app/packs is — so the
    # import failed on every real node and the sentence was silently None. See packs.module().
    import packs as _packs                           # noqa: PLC0415
    _mod = _packs.module("make")
    if _mod is None or not hasattr(_mod, "ask_line"):
        return None
    ask_line = _mod.ask_line                         # packs/make owns the wording
    out = {}
    for loc in LOCALES:
        try:
            said = ask_line(facilities, loc)
        except Exception:                            # noqa: BLE001 — a pack must not break /issues
            log.exception("make: ask_line failed for %s", loc)
            return None
        if said:
            out[loc] = said
    return out or None


def _asks_ledger(alerts: list[dict], actions: list[dict], facilities: list[dict] | None = None) -> dict:
    """The act stage's ledger: every alert that asked a person to do something, first line only, and every answer.

    This is not `_asks()` above — that one is per-issue and only ever surfaces act-level alerts that are still
    open. This one is the whole ledger, for the page's own act-stage view, and it is never averaged or filtered
    by issue: a person reading the ledger wants every act, every answer, and the three counts."""
    def first_line(t):
        return str(t or "").split("\n")[0][:160]

    return {
        "acts": [{"id": a.get("id"), "ts": a["ts"] if isinstance(a.get("ts"), str) else a["ts"].isoformat(),
                  "rule_id": a.get("rule_id"), "sensor_id": a.get("sensor_id"), "text": first_line(a.get("text"))}
                 for a in alerts if a.get("level") == "act"],
        "actions": [{"alert_id": x.get("alert_id"), "stage": x.get("stage"), "actor": x.get("actor"),
                     "ts": x["ts"] if isinstance(x.get("ts"), str) else x["ts"].isoformat()} for x in actions],
        "levels": {lvl: sum(1 for a in alerts if a.get("level") == lvl) for lvl in ("act", "warn", "info")},
        # Nullable on purpose: most nodes have no facility rows and the page draws nothing rather
        # than a sentence about a lab that is not there.
        "where": _where_to_go(facilities or []),
    }


# The resolution the Decide sentence speaks about: the one the dashboard's dial opens at
# (app/static/dashboard.js, `Q.get('res') || defaultRes || 8`) and the one GET /health reports as the
# cell this node stands in. If that default ever moves, this moves with it, or the page and the
# page's own summary of itself quietly disagree about which cell "here" is.
DIGEST_RES = 8


def _group(n: int, loc: str) -> str:
    """639550 as "639,550" in English and "639.550" in Spanish and Indonesian.

    Not cosmetic. A comma is the DECIMAL mark in both of those, so "639,550 m\u00b2" reads there as
    six hundred and thirty-nine point five five — three orders of magnitude wrong, inside the one
    sentence whose whole job is to be the short true answer.
    """
    return f"{n:,}" if loc == "en" else f"{n:,}".replace(",", ".")


def _digest(out: dict, stations: list[dict], geom: dict, asks: dict, headline: str | None,
            now: datetime | None = None, clock=None, read_from: datetime | None = None) -> dict:
    """Four sentences, one per stage, in three languages, from figures already in this document.

    Simple mode draws these and nothing else, so they are the whole answer for a reader who wants
    one. Every number here is read off `out`, `stations`, `geom` or `asks` — nothing is queried, and
    nothing is rounded differently than the section that draws the same figure further down.
    """
    n_stations, n_issues = len(stations), len(out)
    row = next((r for r in (geom.get("grain_table") or []) if r.get("res") == DIGEST_RES), None)
    pub = geom.get("publication") or {}

    acts = asks.get("acts") or []
    closed = {a.get("alert_id") for a in (asks.get("actions") or [])
              if a.get("stage") in CLOSED_STAGES}
    waits = []
    first = {}
    for a in (asks.get("actions") or []):
        if a.get("stage") not in CLOSED_STAGES or a.get("alert_id") is None:
            continue
        k = a["alert_id"]
        if k not in first or a["ts"] < first[k]:
            first[k] = a["ts"]
    for a in acts:
        if a.get("id") in first:
            try:
                waits.append((datetime.fromisoformat(first[a["id"]])
                              - datetime.fromisoformat(a["ts"])).total_seconds() / 60)
            except (TypeError, ValueError):       # a snapshot with a timestamp we cannot parse
                pass
    answered = sum(1 for a in acts if a.get("id") in closed)

    open_by = {k: len(v.get("open_asks") or []) for k, v in out.items()}
    n_open = sum(open_by.values())
    top = max(open_by, key=lambda k: open_by[k]) if n_open else None

    digest = {}
    for loc in LOCALES:
        w = DIGEST_WORDS[loc]
        name = lambda k: (out[k].get("name") or {}).get(loc) or k       # noqa: E731
        if headline and n_stations:
            observe = w["observe"].format(issues=n_issues, stations=n_stations,
                                          headline=name(headline),
                                          phrase=w["state"].get(out[headline]["state"], ""))
        else:
            observe = w["observe_none"].format(issues=n_issues)
        decide = "" if not row else w["decide"].format(
            res=DIGEST_RES, area=_group(round(row.get("area_m2") or 0), loc), stations=n_stations,
            occupied=row.get("occupied") or 0, mine=row.get("in_my_cell") or 0,
            metres=pub.get("metres") or "?",
            leave=w["leaves"] if row.get("may_leave") else w["stays"])
        act = (w["act"].format(open=n_open, top=open_by[top], issue=name(top), answered=answered)
               if n_open else w["act_none"].format(answered=answered))
        if not acts:
            measure = w["measure_empty"]
        elif waits:
            measure = w["measure"].format(acts=len(acts), answered=answered,
                                          median=round(statistics.median(waits)))
        else:
            measure = w["measure_none"].format(acts=len(acts))
        digest[loc] = {"observe": observe, "decide": decide, "act": act, "measure": measure}
    # One key per stage, each a string per locale — the shape `dashboard.js::digest()` reads.
    got = {stage: {loc: digest[loc][stage] for loc in LOCALES}
           for stage in ("observe", "decide", "act", "measure")}
    got["simple"] = _simple(out, stations, asks, now or datetime.now(timezone.utc), clock, read_from, first)
    got["prompts"] = _prompts(out, headline)
    return got


PROMPTS_MAX = 12


def _prompts(out: dict, headline: str | None) -> dict:
    """The ask pane's questions. The first three are the ones it opens with: why the lead leads, the oldest
    open alert (or whether anything is asking), and what the lead's line means (or, with no line, where its
    number comes from). After them, the pool the pane rotates through: every other issue with a reading as
    it is now, the two newest of the other open alerts, and every other issue's line. Only two more alerts,
    because node #1 had ten open and the pool became six copies of one question. An issue that is context
    (land, coast: the satellite's year) is not asked about "right now". Nothing repeats, and there are at
    most PROMPTS_MAX. The order is the same in every locale, so a rotation lands on the same question in each."""
    opens = sorted((a for v in out.values() for a in (v.get("open_asks") or []) if a.get("id") is not None),
                   key=lambda a: str(a.get("ts")))
    oldest = opens[0] if opens else None
    others = [k for k, v in out.items() if k != headline and v.get("state") not in (None, "none")]
    said = {}
    for loc in LOCALES:
        w = PROMPT_WORDS[loc]
        nm = lambda k: ((out.get(k) or {}).get("name") or {}).get(loc, k or "").lower()  # noqa: E731
        line = lambda k: w["line" if (out[k].get("line") or {}).get("value") is not None else "model"].format(issue=nm(k))  # noqa: E731
        qs = [w["lead"].format(issue=nm(headline))] if headline else []
        qs.append(w["ask"].format(id=oldest["id"]) if oldest else w["quiet"])
        if headline:
            qs.append(line(headline))
        qs += [w["now"].format(issue=nm(k)) for k in others if out[k].get("state") != "context"]
        qs += [w["ask"].format(id=a["id"]) for a in list(reversed(opens[1:]))[:2]]
        qs += [line(k) for k in others]
        said[loc] = list(dict.fromkeys(qs))[:PROMPTS_MAX]
    return said


def _ts(v):
    if isinstance(v, datetime):
        return v
    try:
        return datetime.fromisoformat(str(v).replace("Z", "+00:00"))
    except ValueError:
        return None


def _oldest(alerts: list[dict]) -> datetime | None:
    got = [t for t in (_ts(a.get("ts")) for a in alerts) if t is not None]
    return min(got) if got else None


def _simple(out, stations, asks, now, clock, read_from, first) -> dict:
    """Simple mode's paragraph: the house's own stations and its neighbours, the oldest open alert,
    and how the last 30 days of asking went. Three sentences per locale, every figure already in this
    document. `first` is the earliest closed action per alert, computed once by `_digest`.

    `{since}` is the later of thirty days ago and the oldest alert the read reached, so a capture
    holding ten days of alerts says ten days and never claims thirty.
    """
    local = lambda t: t.astimezone(clock) if clock is not None and t.tzinfo else t   # noqa: E731
    today = local(now).date()
    start = now - timedelta(days=30)
    if read_from is not None and read_from > start:
        start = read_from
    own = sum(1 for s in stations if s.get("local"))
    others = [s for s in stations if not s.get("local") and s.get("km") is not None]
    near = [s for s in others if s["km"] <= 1]
    opens = [(k, a) for k, v in out.items() for a in (v.get("open_asks") or []) if _ts(a.get("ts"))]
    oldest = min(opens, key=lambda x: _ts(x[1]["ts"])) if opens else None
    window = [a for a in asks.get("acts") or [] if (_ts(a.get("ts")) or start) >= start]
    answered = [a for a in window if a.get("id") in first]
    waits = [(_ts(first[a["id"]]) - _ts(a["ts"])).total_seconds() / 60 for a in answered
             if _ts(first[a["id"]]) and _ts(a["ts"])]
    said = {}
    for loc in LOCALES:
        w, months = SIMPLE_WORDS[loc], HERO_WORDS[loc]["months"]
        count = lambda pair, n: pair[0 if n == 1 else 1].format(n=n)                  # noqa: E731

        def when(t, allow_time=True):
            t = local(t)
            if allow_time and t.date() == today:
                return w["today"].format(t=t.strftime("%H:%M"))
            return w["date"].format(d=t.day, month=months[t.month - 1])
        if not own:
            st = w["stations_none"]
        elif near:
            st = w["stations"].format(own=count(w["own"], own), near=count(w["near"], len(near)))
        elif others:
            st = w["stations_far"].format(own=count(w["own"], own), km=f"{min(s['km'] for s in others):.1f}")
        else:
            st = w["stations_alone"].format(own=count(w["own"], own))
        if oldest:
            k, a = oldest
            ask = w["ask"].format(id=a.get("id"), issue=((out[k].get("name") or {}).get(loc) or k).lower(),
                                  when=when(_ts(a["ts"])))
        else:
            ask = w["ask_none"]
        if not window:
            loop = w["loop_empty"]
        elif not waits:
            loop = w["loop_none"].format(since=when(start, False), asked=count(w["times"], len(window)))
        else:
            loop = w["loop"].format(since=when(start, False), asked=count(w["times"], len(window)),
                                    answered=len(answered), median=round(statistics.median(waits)))
        said[loc] = f"{st} {ask} {loop}"
    return said


def _mesh(mesh: dict | None, stats: list[dict]) -> dict | None:
    """The LoRa mesh in this house: the gateway `/health` already knows about (passed in, never fetched — see
    Ruling P3: `/issues` makes no network call, and the mesh dict is `app/main.py`'s own `mesh_state`, a
    module-level name it already keeps for `/health`), and the device's own 15-minute means from `stats`."""
    if not mesh:
        return None
    dev = next((r for r in stats if str(r.get("sensor_id", "")).startswith("msh-")), None)
    reads = [{"metric": r["metric"], "mean_15m": round(float(r["mean_15m"]), 2),
              "silent_minutes": None if r.get("silent_minutes") is None else round(r["silent_minutes"])}
             for r in stats if str(r.get("sensor_id", "")).startswith("msh-") and r.get("mean_15m") is not None]
    return {**mesh, "device": None if dev is None else
            {"sensor_id": dev["sensor_id"], "name": dev.get("name"), "indoor": bool(dev.get("indoor"))},
            "reads": reads}


# ---------------------------------------------------------------------------------------- arithmetic
def apparent(t: float | None, rh: float | None) -> float | None:
    """Steadman apparent temperature, no-wind form: AT = T + 0.33e - 4.0, e the vapour pressure in
    hPa from T and RH. The expression is character-for-character the one in packs/heat/rules.yml."""
    if t is None or rh is None:
        return None
    return t + 0.33 * (rh / 100.0 * 6.105 * math.exp(17.27 * t / (237.7 + t))) - 4.0


FUNCTIONS = {"apparent": apparent}


def fenced_median(values: list[float]) -> tuple[float | None, list[float]]:
    """The median of the values inside a median-absolute-deviation fence, and the ones outside it.

    Returns (median, outliers). One station reading 152 while the rest read 5 to 12 is either a fire
    in that lane or a broken sensor; either way it is not the neighbourhood, and it is worth naming
    rather than averaging away. The floor on the MAD keeps a ring that agrees exactly from fencing
    itself down to a single value.
    """
    if not values:
        return None, []
    m0 = statistics.median(values)
    mad = statistics.median([abs(v - m0) for v in values])
    fence = m0 + 6 * max(mad, 5 / 6)
    inside = [v for v in values if v <= fence]
    return (statistics.median(inside) if inside else m0), [v for v in values if v > fence]


def _aggregate(values: list[float], how: str) -> tuple[float | None, list[float]]:
    if not values:
        return None, []
    if how == "mean":
        return statistics.fmean(values), []
    if how == "median":
        return statistics.median(values), []
    if how == "fenced_median":
        return fenced_median(values)
    log.warning("unknown aggregate %r — treating it as a mean", how)
    return statistics.fmean(values), []


def _combine(per_sensor: dict[str, dict[str, float | None]], metrics: list[str],
             function: str | None, how: str) -> tuple[float | None, int, list[float]]:
    """One value from many sensors: the function per sensor, then the aggregate over the results.

    A sensor missing any of the metrics is left out entirely rather than half-counted — which is how
    "public sensors carrying both channels" is enforced without a separate query for it.
    """
    fn = FUNCTIONS.get(function) if function else None
    out = []
    for vals in per_sensor.values():
        got = [vals.get(m) for m in metrics]
        if any(v is None for v in got):
            continue
        out.append(fn(*got) if fn else got[0])
    value, outliers = _aggregate(out, how)
    return value, len(out), outliers


def _worse(a: float | None, b: float | None, compare: dict) -> str | None:
    """Where a stands against b: over · under · level. None when either side is missing."""
    if a is None or b is None:
        return None
    margin = float(compare.get("margin", 1.5))
    if compare.get("mode") == "difference":
        if a - b > margin:
            return "over"
        return "under" if b - a > margin else "level"
    hi = b * margin if b else None
    if hi is not None and a > hi:
        return "over"
    if a and b > a * margin:
        return "under"
    return "level"


def _ambient(row: dict, place: str) -> bool:
    """Whether this row may enter this distance's number.

    SPEC.md §1: "Indoor sensors never enter an ambient average." `place_of` answers geography —
    somebody else's kit indoors is still in the ring — so the ambient rule lives here, once, where no
    issue's .yml can forget it and where the stack and the series cannot disagree about it. Node #1's
    own capture is why: two of its eleven ring stations are other people's indoor kits, one reading
    0.3 µg/m³, and leaving them in moved the street from 7.0 to 6.1.
    """
    # A room the owner has marked `secondary` (a sun-baked workshop, a store room) is still read and still drawn
    # among the sensors, but it is not what "the house" feels like, so it stays out of the room number.
    if place == "room" and row.get("role") == "secondary":
        return False
    return place_of(row) == place and (place == "room" or not row.get("indoor"))


# ------------------------------------------------------------------------------------------ the stack
def _cell(value, n, source, provenance, age_min, sensors, outliers=()) -> dict:
    return {"value": None if value is None else round(value, 6), "n": n, "source": source,
            "provenance": provenance, "age_minutes": None if age_min is None else round(age_min),
            "sensors": sensors, "outliers": len(outliers)}


def _word(place: str) -> str:
    """A distance's provenance word: ours is measured here; somebody else's is theirs, which is a different word
    whatever its quality."""
    return "live" if place in ("room", "yard") else "partial"


def _from_stats(spec: dict, stats: list[dict], names: dict) -> dict | None:
    """One distance's value from the rolling means. See `_ambient` for the indoor rule."""
    place, field = spec["place"], spec["field"]
    rows = [r for r in stats
            if _ambient(r, place) and r.get("metric") in spec["metrics"]
            and (r.get("silent_minutes") is None or r["silent_minutes"] < FRESH_MINUTES)]
    if not rows:
        return None
    per: dict[str, dict] = {}
    for r in rows:
        per.setdefault(r["sensor_id"], {})[r["metric"]] = r.get(field)
    value, n, outliers = _combine(per, spec["metrics"], spec.get("function"), spec["aggregate"])
    if value is None:
        return None
    used = sorted(s for s in per if all(per[s].get(m) is not None for m in spec["metrics"]))
    age = min((r["silent_minutes"] for r in rows if r.get("silent_minutes") is not None), default=None)
    word = _word(place)
    if len(used) == 1:
        source = names.get(used[0]) or used[0]
    else:
        source = f"{len(used)} sensors"
    return _cell(value, n, source, word, age, used, outliers)


def _from_observations(spec: dict, obs: list[dict], now: datetime) -> dict | None:
    sid = spec["sensor_id"]
    rows = {r["metric"]: r for r in obs if r["sensor_id"] == sid and r["metric"] in spec["metrics"]}
    if len(rows) < len(spec["metrics"]):
        return None
    per = {sid: {m: r["value"] for m, r in rows.items()}}
    value, n, _ = _combine(per, spec["metrics"], spec.get("function"), "mean")
    if value is None:
        return None
    first = next(iter(rows.values()))
    age = _age_minutes(first.get("ts"), now)
    # SPEC.md §1: a model or a portal is partial, whatever its quality. The layer's provenance
    # vocabulary is finer than that — `model` says which kind of partial — so a model row gets
    # `model` and a portal row keeps `partial`.
    word = "model" if first.get("kind") == "model" else "partial"
    return _cell(value, n, first.get("name") or sid, word, age, [sid])


def _from_earth(spec: dict, earth: dict | None, obs: list[dict], now: datetime) -> dict | None:
    """The node's own AlphaEarth record: what packs/earth computed here, from files it downloaded.

    No fallback, on purpose. See the comment on land.yml's region column: the candidate metric was
    retired in v0.33.1 as a second number for one idea, and `observations` would still be holding a
    stale row for it on any node that ran the pack before then. With no record this returns None, the
    issue is `none`, and the page says how to fetch one.
    """
    latest = (earth or {}).get("latest") or {}
    if latest.get("share_over_threshold") is None:
        return None
    over = latest.get("threshold")
    cell = _cell(latest["share_over_threshold"] * 100, 1,
                 f"this node's own AlphaEarth comparison, {latest.get('year_a')}"
                 f"\u2013{latest.get('year_b')}"
                 + (f", pixels that moved more than {over}" if over is not None else ""),
                 "model", _age_minutes(latest.get("computed_at"), now), ["earth"])
    # The share is the statistic the sentence uses because it accumulates the way a reader expects:
    # on node #1, 2024-2025 is 1.3 % and 2017-2025 is 8.5 %. `mean` does not — its 2017-2025 figure
    # (0.027) is SMALLER than one year's (0.043), because it is a mean per-pixel distance in
    # embedding space and not a quantity of change. Both travel in `extra` so the band can draw the
    # span without a second request, and so Figures can name the one the Index cell uses.
    cell["extra"] = {k: latest.get(k) for k in
                     ("mean", "median", "p95", "threshold", "hectares_over_threshold",
                      "year_a", "year_b", "metres_per_pixel", "radius_m")}
    # The longest span the pack has computed to the same end year: on node #1, 2017-2025 at 8.5 %.
    # That is the sentence's history — one year is a number, eight years is a direction.
    spans = [c for c in (earth or {}).get("changes") or []
             if c.get("year_b") == latest.get("year_b") and c.get("share_over_threshold") is not None
             and (c.get("year_b") or 0) - (c.get("year_a") or 0) > 1]
    if spans:
        first = min(spans, key=lambda c: c.get("year_a") or 9999)
        cell["extra"]["since_year"] = first["year_a"]
        cell["extra"]["since_pct"] = round(first["share_over_threshold"] * 100, 1)
    return cell


def _age_minutes(ts, now: datetime) -> float | None:
    if not ts:
        return None
    if isinstance(ts, str):
        try:
            ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except ValueError:
            return None
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return (now - ts).total_seconds() / 60


def _stack(d: dict, stats, obs, earth, names, now) -> dict:
    out = {}
    for dist in DISTANCES:
        spec = (d.get("distances") or {}).get(dist)
        if not spec:
            out[dist] = None
            continue
        src = spec.get("from")
        if src == "stats":
            out[dist] = _from_stats(spec, stats, names)
        elif src == "observations":
            out[dist] = _from_observations(spec, obs, now)
        elif src == "earth":
            out[dist] = _from_earth(spec, earth, obs, now)
        else:
            out[dist] = None
    return out


# ------------------------------------------------------------------------------------- attribution
def _classify(stack: dict, line: dict | None, compare: dict) -> str:
    """Which of the six stories the stack tells.

    `outside` is the yard if the node has one and the ring if it does not — the same order as
    everywhere else in this repo ("the person's own outdoor sensors, else the nearest public
    references, else the model", AGENTS.md).
    """
    room = (stack.get("room") or {}).get("value")
    outside = (stack.get("yard") or {}).get("value")
    if outside is None:
        outside = (stack.get("ring") or {}).get("value")
    if room is None:
        return "unknown"
    over = line is not None and room > float(line["value"])
    out_over = line is not None and outside is not None and outside > float(line["value"])
    if not over and not out_over:
        return "clear"
    rel = _worse(room, outside, compare)
    if rel == "over" and over:
        return "inside"
    if rel == "under" and out_over:
        return "outside_worse"
    if rel == "level" and over and out_over:
        return "everywhere"
    return "mixed"


# ------------------------------------------------------------------------------------------ the asks
def _mine(d: dict, rule_id: str, domain_of: dict) -> bool:
    """Whether an alert belongs to this issue: its pack's domain, or the rule named by hand."""
    if not rule_id or "/" not in rule_id:
        return False                       # a core rule is domain-blind and belongs to no issue
    pack = rule_id.split("/", 1)[0]
    return domain_of.get(pack) in (d["packs"]["domains"] or []) or rule_id in (d["packs"]["rules"] or [])


def _asks(d, alerts, actions, stack, line, domain_of, now, owned=frozenset()) -> tuple[list[dict], list[dict]]:
    """(the open asks, every alert of this issue's in the last 24 h), newest first.

    An open act-level ask is `current` only while its condition still holds: the room is over the
    issue's line, or the alert is under two hours old. On the 6 September capture six act alerts were
    open across twelve hours and one of them (#53, cooking, 14:30) was still open at 22:08 with the
    room at 5 µg/m³. It is still an open ask — ρ counts it — but it is not what is happening now, and
    a page that headlines it is lying about the present.

    `owned` is the packs the alert engine replaced (docs/SPEC_event_led_state.md §3.1): on a shadow or
    events node their alerts are what the events stand for, so they are not this issue's asks.
    """
    room = (stack.get("room") or {}).get("value")
    over = line is not None and room is not None and room > float(line["value"])
    mine = [a for a in alerts if _mine(d, a.get("rule_id", ""), domain_of) and str(a.get("rule_id") or "").split("/", 1)[0] not in owned]
    recent = [a for a in mine if (_age_minutes(a.get("ts"), now) or 1e9) < NOTABLE_HOURS * 60]
    open_asks = []
    for a in mine:
        if a.get("level") != ASK_LEVEL or not is_open(a, actions):
            continue
        age = _age_minutes(a.get("ts"), now)
        open_asks.append({
            "id": a.get("id"), "ts": a.get("ts"), "rule_id": a.get("rule_id"),
            "sensor_id": a.get("sensor_id"), "level": a.get("level"), "text": a.get("text"),
            "age_minutes": None if age is None else round(age),
            "stage": stage_of(a, actions), "seen": is_seen(a, actions),
            "current": bool(over or (age is not None and age < ASK_CURRENT_HOURS * 60)),
        })
    open_asks.sort(key=lambda a: (not a["current"], -(a["id"] or 0)))
    # Each ask carries its own two sentences in every locale — what it is, and how to close it — so a
    # phone, a wall screen and Telegram all say the same thing and none of them writes it themselves.
    for a in open_asks:
        code = "open_ask_current" if a["current"] else "open_ask_stale"
        a["says"] = {loc: _reason_text({"code": code, "at": a["ts"]}, loc) for loc in LOCALES}
        a["how"] = {loc: _reason_text({"code": "ask_how", "alert_id": a["id"]}, loc) for loc in LOCALES}
    return open_asks, recent


# ------------------------------------------------------------------------------------------ the state
def _state(d, stack, open_asks, recent, line, ev=None) -> tuple[str, dict]:
    """One of act · notable · quiet · context · none, and the reason, as a code plus its parts."""
    if not any(stack.values()):
        return "none", {"code": "no_source"}
    if d["kind"] == "context":
        return "context", {"code": "context_only"}

    # docs/SPEC_event_led_state.md §3.2: on a shadow or events node the open event says whether something is asked.
    e = (ev or {}).get("open")
    if e:
        a = e.get("answer")
        if (e.get("level") == "act" and not a) or e.get("kind") == "danger":
            return "act", {"code": "event_open", "at": e.get("opened_at"), "kind": e.get("kind"),
                           "event_id": e.get("id")}
        if a:
            return "notable", {"code": "event_answered", "at": a.get("ts"), "kind": e.get("kind"),
                               "who": a.get("actor") or "", "stage": a.get("stage"), "event_id": e.get("id")}
        return "notable", {"code": "event_open", "at": e.get("opened_at"), "kind": e.get("kind"),
                           "event_id": e.get("id")}

    current = [a for a in open_asks if a["current"]]
    if current:
        a = current[0]
        return "act", {"code": "open_ask_current", "at": a["ts"], "alert_id": a["id"]}

    room = (stack.get("room") or {}).get("value")
    over = line is not None and room is not None and room > float(line["value"])
    loud = [a for a in recent if a.get("level") in ("act", "warn")]
    if open_asks:                          # act-level by construction, and none of them current
        a = open_asks[0]
        return "notable", {"code": "open_ask_stale", "at": a["ts"], "alert_id": a["id"]}
    c = (ev or {}).get("cleared")
    if c:
        return "notable", {"code": "event_cleared", "at": c.get("cleared_at"), "kind": c.get("kind"),
                           "event_id": c.get("id")}
    if loud:
        a = loud[0]
        return "notable", {"code": "alert_today", "at": a.get("ts"), "level": a.get("level"),
                           "alert_id": a.get("id")}
    if over and not open_asks:
        return "notable", {"code": "over_line"}
    return "quiet", {"code": "no_alert"}


# --------------------------------------------------------------------------------------- the sentence
def _hhmm(ts) -> str:
    if isinstance(ts, str):
        try:
            ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except ValueError:
            return ""
    return ts.strftime("%H:%M") if isinstance(ts, datetime) else ""


def _reason_text(reason: dict, loc: str) -> str:
    """One line of why, in one language. Every word comes from REASON_WORDS; nothing is typed here.

    A reason that knows the day's high (`peak`, `peak_at`) takes the `_peak` form of its line where
    one exists. On a quiet evening that is the whole of what there is to say, and "nothing to say"
    was leaving it out.
    """
    words = REASON_WORDS.get(loc, REASON_WORDS["en"])
    code = reason["code"]
    if reason.get("peak_at") and code + "_peak" in words:
        code += "_peak"
    stage_key = {"acted": "done", "acknowledged": "not_now", "dismissed": "doesnt_fit"}.get(reason.get("stage"), "")
    word = (A.BUTTONS.get(loc) or A.BUTTONS["en"]).get(stage_key, "")
    return words.get(code, "").format(when=_hhmm(reason.get("at")), level=reason.get("level", ""),
                                      id=reason.get("alert_id", ""), peak=reason.get("peak", ""),
                                      peak_at=reason.get("peak_at", ""), kind=reason.get("kind", ""),
                                      who=reason.get("who") or words.get("someone", ""), word=word)


def _clock(data: dict):
    """The zone every hour on the page is printed in.

    On a node it is NODE_TZ: Postgres runs the session in it (app/main.py), so buckets and alert
    times arrive in one zone already. A snapshot is the case that needs this — `planetai snapshot`
    wrote node #1's hourly buckets in UTC and its alerts in +08:00, and without a rule the quiet line
    said "the day's high was at 06:00" beside an ask "at 14:30" on the same evening. The alerts' own
    zone is the one the household already reads its times in, so it wins when NODE_TZ is not set.
    """
    name = os.getenv("NODE_TZ", "").strip()
    if name:
        try:
            return ZoneInfo(name)
        except (ZoneInfoNotFoundError, ValueError):
            pass
    for a in data.get("alerts") or []:
        ts = a.get("ts")
        if isinstance(ts, str):
            try:
                ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            except ValueError:
                continue
        if isinstance(ts, datetime) and ts.tzinfo is not None:
            return ts.tzinfo
    return None


def _peak(series: list[float | None] | None, buckets: list, dp: int, unit: str = "", tz=None) -> dict:
    """The day's high and the hour it landed in, from the 24 hourly values the page already draws.

    History, not statistics: the largest of 24 numbers and its position. Empty with fewer than six
    hours, because "the day's high" of a sensor that came online at lunch is not a day."""
    vals = list(series or [])
    have = [(v, i) for i, v in enumerate(vals) if v is not None]
    if len(have) < 6 or len(buckets) != len(vals):
        return {}
    v, i = max(have)
    at = buckets[i]
    if tz is not None and isinstance(at, datetime) and at.tzinfo is not None:
        at = at.astimezone(tz)
    return {"peak": f"{v:.{dp}f} {unit}".strip(), "peak_at": _hhmm(at)}


def _trend(series: list[float | None], compare: dict) -> str:
    """Which way the room's last three hours went against the three before them."""
    v = [x for x in (series or []) if x is not None]
    if len(v) < 6:
        return "steady"
    a, b = statistics.fmean(v[-3:]), statistics.fmean(v[-6:-3])
    rel = _worse(a, b, compare)
    return {"over": "rising", "under": "falling"}.get(rel, "steady")


def _moved(series: list[float | None]) -> float:
    """How far the room's last three hours moved against the three before them, as a proportion.

    The same two means `_trend` computes and then throws away: it keeps the direction and loses the
    size, and the size is what decides which of two issues has more to say today. No new query, no
    new arithmetic, and the same six buckets — an issue with fewer than six is not moving as far as
    this node knows, which is 0.0 and not a small number that would outrank a real one by accident.

    Relative and not absolute, because the issues are not in the same unit: 2 ug/m3 of PM2.5 and
    2 degrees are not comparable quantities and ranking them against each other by magnitude would
    be arithmetic on a category error. A proportion of each issue's own recent level is comparable.
    Unsigned: a reading halving is as much news as a reading doubling, and which way it went is
    already said by `trend`.
    """
    v = [x for x in (series or []) if x is not None]
    if len(v) < 6:
        return 0.0
    a, b = statistics.fmean(v[-3:]), statistics.fmean(v[-6:-3])
    if not b:
        return 0.0
    return abs(a - b) / abs(b)


def _where(d: dict, dist: str, loc: str) -> str:
    override = ((d.get("where") or {}).get(loc) or {}).get(dist)
    return override or WHERE_WORDS.get(loc, WHERE_WORDS["en"]).get(dist, dist)


def _join(items: list[str], word: str) -> str:
    """a, b and c."""
    if len(items) < 2:
        return "".join(items)
    return f"{', '.join(items[:-1])} {word} {items[-1]}"


def _cmp(d, stack, headline_dist, loc, compare) -> str:
    """{cmp}: where the headline number stands against every other distance that has one.

    A sensed issue compares. A context issue has nothing to compare against — one model row and no
    line — so its {cmp} is its readouts, which is what the review gives a context band instead of a
    stack strip.
    """
    if d["kind"] == "context":
        parts = [r["_text"][loc] for r in (d.get("_readouts") or []) if r.get("_text")]
    else:
        head = (stack.get(headline_dist) or {}).get("value")
        # An issue may name its own comparison words in its yml (`cmp_words`): air says "cleaner
        # than the street" where heat says "cooler than the street". The shared table is the
        # fallback, not the voice.
        words = ((d.get("sentences") or {}).get(loc, {}).get("cmp_words")
                 or CMP_WORDS.get(loc, CMP_WORDS["en"]))
        nouns = NOUN_WORDS.get(loc, NOUN_WORDS["en"])
        # One clause per RELATION, not one per distance. Node #1 has a yard, so three distances all
        # answered "level" and the hero read "Level with the wall outside, level with the street,
        # level with the model" — the same three words three times, five lines of headline on a
        # screen budgeted for two. Grouped, that is "Level with the wall outside, the street and the
        # model", and a household reads one comparison instead of counting three.
        grouped: dict[str, list[str]] = {}
        for dist in DISTANCES:
            if dist == headline_dist or not stack.get(dist):
                continue
            rel = _worse(head, stack[dist]["value"], compare)
            if rel:
                grouped.setdefault(rel, []).append(nouns.get(dist, dist))
        join = JOIN_WORDS.get(loc, JOIN_WORDS["en"])
        parts = [words[rel].format(noun=_join(ns, join)) for rel, ns in grouped.items()]
    if not parts:
        return ""
    s = ", ".join(parts)
    return s[0].upper() + s[1:] + "."


def _sentence(d, stack, state, headline_dist, verb_key, loc, compare, attribution,
              line=None, reason=None) -> str:
    """The full sentence. `_sentence_parts` returns the title/tagline split with it."""
    return _sentence_parts(d, stack, state, headline_dist, verb_key, loc, compare,
                           attribution, line, reason)[0]


def _sentence_parts(d, stack, state, headline_dist, verb_key, loc, compare, attribution,
                    line=None, reason=None) -> tuple[str, str, str]:
    """(sentence, title, tagline): the sentence whole, then split at the {line} clause.

    The title is the qualitative head — what is happening, in the household's words, with no
    number and no indicator in it ("The air is getting worse inside"). The tagline is the rest:
    the line, the comparison, the day's event — the readings, introduced slowly and set smaller.
    A page titles with the title and explains with the tagline; the full sentence stays for the
    places that speak prose (the bot, the asks). Templates without a {line} clause (the none and
    context states) do not split: the title is the whole and the tagline is empty.
    """
    block = (d.get("sentences") or {}).get(loc) or {}
    if state in ("none", "context"):
        tpl = (block.get("state") or {}).get(state)
        if not tpl and state == "none":
            empty = (d.get("empty") or {}).get(loc, "")
            return empty, empty, ""
    else:
        tpl = (block.get("state") or {}).get(state) or (block.get("attribution") or {}).get(attribution)
    if not tpl:
        empty = (d.get("empty") or {}).get(loc, "")
        return empty, empty, ""
    cell = stack.get(headline_dist) or {}
    n = cell.get("value")
    extra = cell.get("extra") or {}
    sw = SPAN_WORDS.get(loc, SPAN_WORDS["en"])
    span = sw["between"].format(a=extra["year_a"], b=extra["year_b"]) \
        if extra.get("year_a") and extra.get("year_b") else ""
    since = sw["since"].format(pct=f"{extra['since_pct']:.1f}", year=extra["since_year"]) \
        if extra.get("since_year") and extra.get("since_pct") is not None else ""
    # The {line} clause is computed from the live value against the line, never written into a
    # template — so a template can never assert "under the line" on a day the reading is past it.
    line_key = ""
    if d["kind"] == "sensed" and line is not None and n is not None:
        lv = float(line["value"])
        line_key = "over" if n > lv else ("near" if n >= 0.9 * lv else "under")
    line_clause = (block.get("line") or {}).get(line_key, "")
    # The {event} clause for the day it crossed and came back: the state band says act or notable
    # because of what happened earlier, while the sentence says now. Naming the crossing keeps the
    # two from reading as a contradiction. Only codes that certainly happened today, and never
    # while the reading is over the line right now — then the {line} clause already says it.
    event_clause = ""
    if line_key in ("under", "near") and (reason or {}).get("code") in (
            "open_ask_current", "alert_today", "event_answered", "event_cleared"):
        event_clause = (block.get("event") or {}).get("earlier", "")
    slots = dict(verb=(block.get("verbs") or {}).get(verb_key, ""),
                 n="" if n is None else f"{n:.{d['dp']}f}",
                 unit=d["unit"],
                 where=_where(d, headline_dist, loc),
                 cmp=_cmp(d, stack, headline_dist, loc, compare),
                 line=line_clause, event=event_clause,
                 span=span, since=since)

    def _fmt(t):
        return " ".join(t.format(**slots).split()).replace(" ,", ",").replace(" .", ".")

    full = _fmt(tpl)
    head, sep, tail = tpl.partition("{line}")
    if not sep:
        return full, full, ""
    title = _fmt(head).strip().rstrip(",—–- ").strip()
    tagline = _fmt("{line}" + tail).strip()
    # with no reading there is no line clause, and the tagline would open on the template's own
    # punctuation — ". cleaner than the street" is not a sentence start
    if tagline.startswith(". "):
        tagline = tagline[2:]
    # the clause is written to sit mid-sentence; standing alone under the title it is a sentence
    if tagline:
        tagline = tagline[0].upper() + tagline[1:]
    return full, title, tagline


# ------------------------------------------------------------------------------------------- readouts
def _readouts(d, obs, loc_all=LOCALES) -> list[dict]:
    out = []
    for r in d.get("readouts") or []:
        row = next((o for o in obs if o["sensor_id"] == r["sensor_id"] and o["metric"] == r["metric"]), None)
        if not row or row.get("value") is None:
            continue
        dp = int(r.get("dp", 0))
        v = round(row["value"] * float(r.get("scale", 1)), dp)
        shown = f"{v:.{dp}f}"
        out.append({"metric": r["metric"], "value": v, "dp": dp, "unit": r["unit"],
                    "label": r["label"], "source": row.get("name") or r["sensor_id"],
                    "provenance": "model" if row.get("kind") == "model" else "partial",
                    "_ts": row.get("ts"), "_sid": r["sensor_id"],
                    "_text": {loc: f"{r['label'][loc]} {shown} {r['unit']}" for loc in loc_all}})
    return out


# ----------------------------------------------------------------------------------------------- hero
def _hero(d, stack, headline, sentence, now, clock) -> dict | None:
    """The lead slot filled with tonight's values, from the issue's `hero:` contract.

    The page draws this and nothing else when the issue leads, so every word and every number in it
    is decided here: which figure is the numeral, which distances sit on the rule and where the line
    is, and a stamp that is a time for a reading and a date for a yearly record. None when the issue
    declares no hero, which is also what keeps it from leading (see `_lead`).
    """
    h = d.get("hero")
    if not h:
        return None
    dp = h["dp"]
    numeral = h.get("numeral", "headline")
    if numeral == "headline":
        numeral = headline
    if numeral in DISTANCES:
        cell = stack.get(numeral) or {}
        value = cell.get("value")
        age = cell.get("age_minutes")
        at = now - timedelta(minutes=age) if value is not None and age is not None else now
    else:
        r = next((x for x in d.get("_readouts") or [] if x["metric"] == numeral), {})
        value, at = r.get("value"), r.get("_ts")
        # A readout can outlive the record the issue reads: node #1 on 6 September had its built
        # share and no satellite comparison, and the hero read "91 %" over "No satellite record yet".
        # An issue with nothing in its stack is `none`, and its numeral says so too.
        if not any(stack.values()):
            value = None
    if isinstance(at, str):
        try:
            at = datetime.fromisoformat(at.replace("Z", "+00:00"))
        except ValueError:
            at = None
    if isinstance(at, datetime) and clock is not None and at.tzinfo is not None:
        at = at.astimezone(clock)

    def stamp(loc):
        w = HERO_WORDS[loc]
        if not isinstance(at, datetime) or value is None:
            return ""
        if h["clock"] == "time":
            return w["time"].format(t=at.strftime("%H:%M"))
        month = w["months"][at.month - 1]
        return w["date"].format(d=f"{month} {at.year}", n=f"{month} {at.year + 1}")

    rule = None
    r = h.get("rule")
    if r:
        rule = {"min": r["min"], "max": r["max"], "ends": r["ends"],
                "dots": [{"distance": x, "value": round(stack[x]["value"], dp)} for x in r["dots"]
                         if (stack.get(x) or {}).get("value") is not None],
                "line": ({"value": d["line"]["value"], "name": {loc: HERO_WORDS[loc]["line"] for loc in LOCALES}}
                         if r["line"] and d.get("line") else None)}
    return {"sign": h["sign"], "pictogram": h.get("pictogram"), "numeral": numeral,
            "value": None if value is None else round(value, dp), "unit": h["unit"], "dp": dp,
            "sentence": sentence,
            "plain": {loc: _plain(d, numeral, value, stack, rule, loc) for loc in LOCALES},
            "rule": rule, "clock": h["clock"],
            "stamp": {loc: stamp(loc) for loc in LOCALES}}


def _plain(d, numeral, value, stack, rule, loc) -> str:
    """One more sentence under the hero's: the figures, in the household's words.

    The reading layer (docs/SPEC_language.md): the headline above it carries no number, so this
    sentence does. A sensed issue names the numeral distance first, then the others on its rule,
    and says whether anything here is over the line. A context issue's figures are its
    `context_plain` template — the string that was its whole sentence before the split — followed
    by where the number comes from and that it never asks. Every figure is one the rule already
    draws.
    """
    if value is None:
        return ""
    w = PLAIN_WORDS[loc]
    if d["kind"] == "context":
        prov = w["yearly"] if d["hero"]["clock"] == "date" else w["model"]
        tpl = ((d.get("sentences") or {}).get(loc) or {}).get("state", {}).get("context_plain")
        cell = stack.get("region") or {}
        n = cell.get("value")
        if not tpl or n is None:
            return prov
        extra = cell.get("extra") or {}
        sw = SPAN_WORDS.get(loc, SPAN_WORDS["en"])
        span = sw["between"].format(a=extra["year_a"], b=extra["year_b"]) \
            if extra.get("year_a") and extra.get("year_b") else ""
        since = sw["since"].format(pct=f"{extra['since_pct']:.1f}", year=extra["since_year"]) \
            if extra.get("since_year") and extra.get("since_pct") is not None else ""
        figures = " ".join(tpl.format(
            verb="", n=f"{n:.{d['dp']}f}", unit=d["unit"], where=_where(d, "region", loc),
            cmp=_cmp(d, stack, "region", loc, None), span=span, since=since,
        ).split()).replace(" ,", ",").replace(" .", ".")
        return f"{figures} {prov}"
    dp = d["hero"]["dp"]
    fmt = lambda v: f"{v:.{dp}f}"                                              # noqa: E731
    dists = [x["distance"] for x in rule["dots"]] if rule else [x for x in DISTANCES if stack.get(x)]
    others = [x for x in dists if x != numeral and (stack.get(x) or {}).get("value") is not None]
    # The numeral first: off the doors there is no big figure above this sentence, and a reading
    # layer that never says the headline number is not a reading layer. The page may drop the
    # clause where the numeral is drawn directly above.
    chain = ([numeral] if numeral in dists and (stack.get(numeral) or {}).get("value") is not None
             else []) + others
    if chain:
        parts = [w["first" if i == 0 else "more"].format(where=_where(d, x, loc), n=fmt(stack[x]["value"]))
                 for i, x in enumerate(chain)]
        said = "".join(parts)
        said = said[0].upper() + said[1:] + "."
    else:
        said = w["alone"]
    line = (rule or {}).get("line")
    if line:
        over = [x for x in [numeral] + others if stack[x]["value"] > float(line["value"])]
        nouns = NOUN_WORDS.get(loc, NOUN_WORDS["en"])
        key = "under" if not over else "over_one" if len(over) == 1 else "over_many"
        said += " " + w[key].format(line=f"{float(line['value']):g}",
                                    over=_join([nouns.get(x, x) for x in over], JOIN_WORDS[loc]))
    return said


# --------------------------------------------------------------------------------------------- series
def _values(spec: dict, hourly: dict, buckets: list, keep) -> list:
    """One distance's value at each bucket: the rows `keep` admits, the function per sensor, then the aggregate."""
    vals = []
    for b in buckets:
        per: dict[str, dict] = {}
        for r in hourly.get(b, []):
            if not keep(r) or r["metric"] not in spec["metrics"]:
                continue
            per.setdefault(r["sensor_id"], {})[r["metric"]] = r.get("mean")
        v, _, _ = _combine(per, spec["metrics"], spec.get("function"), spec["aggregate"])
        vals.append(None if v is None else round(v, 6))
    return vals


def _series(d, hourly, buckets, names) -> dict:
    """Twenty-four hourly values at each distance, on the same buckets, so the traces line up."""
    out = {}
    for dist in DISTANCES:
        spec = (d.get("distances") or {}).get(dist)
        if not spec or spec.get("from") != "stats":
            out[dist] = None
            continue
        vals = _values(spec, hourly, buckets, lambda r, place=spec["place"]: _ambient(r, place))
        out[dist] = vals if any(v is not None for v in vals) else None
    return out


def _room_series(d: dict, hourly: dict, buckets: list, names: dict, rooms) -> dict | None:
    """An open event's own rooms, hour by hour, combined the way the issue combines its house: air the mean, heat the
    median of each room's apparent temperature (docs/SPEC_dashboard_figures.md §3.2). The page draws it beside the
    house, so a one-room event inside a cooler house is visible as the room it is. Rooms are names or ids, as the
    engine writes them on alert_events."""
    spec = (d.get("distances") or {}).get("room")
    want = set(rooms or [])
    if not spec or spec.get("from") != "stats" or not want:
        return None
    vals = _values(spec, hourly, buckets,
                   lambda r: r.get("sensor_id") in want or names.get(r.get("sensor_id")) in want)
    return {"rooms": sorted(want), "values": vals} if any(v is not None for v in vals) else None


# ----------------------------------------------------------------------------------------------- read
def _rows(cur, sql, *args) -> list[dict]:
    cur.execute(sql, args)
    return [dict(r) for r in cur.fetchall()]


# usual_by_hour (init.sql): each sensor's median and p90 for each local hour, over the 14 complete days before today.
USUAL_DAYS = 14
USUAL_SQL = "SELECT sensor_id, metric, hour, median, p90 FROM usual_by_hour"

# The archive of silence (docs/SPEC_dashboard_figures.md §3.3): stations heard within SILENT_DAYS and not in the last
# day. `stats` holds the last 24 hours only, so without this a station silent for a day leaves /issues with no word.
SILENT_DAYS = 30
SILENT_SQL = ("SELECT s.sensor_id, s.name, s.lat, s.lon, s.local, s.indoor, s.kind, max(r.ts) AS last_heard "
              "FROM readings r JOIN sensors s USING (sensor_id) "
              "WHERE s.kind = 'sensor' AND r.ts > now() - make_interval(days => %s) "
              "GROUP BY 1, 2, 3, 4, 5, 6, 7 HAVING max(r.ts) <= now() - interval '24 hours'")


def _optional(cur, sql: str, *args) -> list[dict] | None:
    """A read a fresh node may not answer and a capture does not carry: None, never a failed /issues.

    usual_by_hour is created WITH NO DATA and raises until the app's first hourly refresh, and on a live cursor an
    error inside the /issues transaction would abort every read after it, so the read gets a savepoint of its own. A
    Replay has no connection and refuses a query it cannot answer with LookupError, which ends in the same None."""
    conn = getattr(cur, "connection", None)
    try:
        if conn is None:
            return _rows(cur, sql, *args)
        with conn.transaction():
            return _rows(cur, sql, *args)
    except Exception as e:  # noqa: BLE001
        log.info("issues: an optional read did not answer (%s)", type(e).__name__)
        return None


def _usual(d: dict, dist: str, cell: dict | None, rows: list[dict] | None) -> tuple[dict | None, str | None]:
    """The issue's usual day at its hero distance (docs/SPEC_dashboard_figures.md §3.1): for each local hour, the mean
    over that distance's sensors of usual_by_hour's median and p90, for the issue's own metric. The same reading
    events_wire.USUAL_SQL makes for an event's card, so the band and the card agree. (block, None) or (None, why)."""
    if rows is None:
        return None, "unread"
    ids = set((cell or {}).get("sensors") or [])
    if not ids:
        return None, "no_source"
    by: dict[int, list[dict]] = {}
    for r in rows:
        if r.get("sensor_id") in ids and r.get("metric") == d.get("metric") and r.get("median") is not None:
            by.setdefault(int(r["hour"]), []).append(r)
    if not by:
        return None, "no_history"

    def mean(xs):
        xs = [float(x) for x in xs if x is not None]
        return round(statistics.fmean(xs), 2) if xs else None
    return {"window_days": USUAL_DAYS, "distance": dist,
            "hours": [{"hour": h, "median": mean(r["median"] for r in by.get(h, [])),
                       "p90": mean(r.get("p90") for r in by.get(h, []))} for h in range(24)]}, None


def _read(cur) -> dict:
    """Five reads, once, for every issue. Nothing here is per-issue: an eighth issue costs no query."""
    return {
        "stats": _rows(cur, "SELECT sensor_id, metric, indoor, local, kind, scale, lat, lon, name, "
                            "last, last_ts, silent_minutes, mean_15m, mean_1h, mean_24h, "
                            "(SELECT s.meta->>'role' FROM sensors s WHERE s.sensor_id = stats.sensor_id) AS role "
                            "FROM stats"),
        "obs": _rows(cur, "SELECT sensor_id, metric, value, ts, name, kind, scale, local, cadence, "
                          "meta FROM observations"),
        # Every act-level alert of the last 30 days, plus the last 200 of anything. The 200 alone
        # reached back ten days on node #1, so simple mode's "since" would have been ten days while
        # its sentence said thirty; info notes stay capped, because nothing here counts them.
        "alerts": _rows(cur, "SELECT id, ts, rule_id, sensor_id, level, text FROM alerts "
                             "WHERE (level = 'act' AND ts > now() - interval '30 days') "
                             "OR id IN (SELECT id FROM alerts ORDER BY ts DESC LIMIT 200) "
                             "ORDER BY ts DESC"),
        "actions": _rows(cur, "SELECT ts, alert_id, stage, actor, note FROM actions "
                              "WHERE alert_id IS NOT NULL"),
        # min/max/n ride along for the station series' min-max band (Task 3); readings_1h already
        # carries them, the same three columns app/main.py:452 and :1724 already select off it.
        "hourly": _rows(cur, "SELECT h.bucket, h.sensor_id, h.metric, h.mean, h.min, h.max, h.n, "
                             "s.indoor, s.local, s.kind, s.meta->>'role' AS role FROM readings_1h h JOIN sensors s "
                             "USING (sensor_id) WHERE h.bucket > now() - interval '24 hours'"),
    }


class Replay:
    """A cursor that answers `_read`'s five queries from a snapshot instead of from Postgres.

    This is what makes `?fixture=<name>` worth having: a fixture is rendered through the real engine,
    at the hour it was captured, so a design round and a wall screen are looking at the same code. A
    fixture with a baked-in `issues` block would go stale the first time the state machine changed
    and nothing would say so.

    It matches on the table name rather than the whole statement, so a whitespace change in the SQL
    does not break every fixture and every test.

    All five tables must be present, even as empty lists. That is not pedantry: `planetai snapshot`
    fetched only three of them until v0.67, and because a missing key used to read as an empty one,
    every fixture taken in between rendered with no act ledger, no stages, no series and no barcode,
    and nothing anywhere said so. An absent table now refuses out loud.
    """
    TABLES = (("FROM stats", "stats"), ("FROM observations", "observations"),
              ("FROM alerts", "alerts"), ("FROM actions", "actions"),
              ("FROM readings_1h", "readings_1h"))

    def __init__(self, snapshot: dict):
        self.snapshot, self.rows = snapshot, []

    def execute(self, sql: str, args=()):
        for needle, key in self.TABLES:
            if needle in sql:
                # A table that is ABSENT and a table that is EMPTY are different facts, and reading
                # them as one is how a fixture came to render with no act ledger and no series while
                # saying nothing. A node with nothing to report sends `[]`; a snapshot that never
                # fetched the table has no key at all, and that is a broken fixture, not a quiet node.
                if key not in self.snapshot:
                    raise LookupError(
                        f"this snapshot carries no {key}, so its issues cannot be replayed. Every "
                        f"snapshot taken before v0.67 is missing actions and readings_1h, because "
                        f"planetai snapshot did not fetch them; take a new one on a node running "
                        f"v0.67 or later. See docs/design/fixtures/README.md.")
                self.rows = [dict(r) for r in (self.snapshot[key] or [])]
                if key == "actions":
                    self.rows = [r for r in self.rows if r.get("alert_id") is not None]
                if key == "readings_1h":
                    for r in self.rows:
                        if isinstance(r.get("bucket"), str):
                            r["bucket"] = datetime.fromisoformat(r["bucket"])
                return
        raise LookupError(f"a snapshot cannot answer this query: {sql[:80]}")

    def fetchall(self):
        return self.rows


def replay(snapshot: dict, settings, decl: dict) -> dict:
    """A snapshot's own issues, computed at the hour it was captured.

    `now` comes from the snapshot: a stack computed against today's wall clock would report every
    figure in a week-old capture as hours stale, which is true of the clock and false of the data.

    `place` and `mesh` also come from the snapshot rather than from `settings` or a live call: a
    fixture is a fixed moment and may be replayed on a different node than the one that captured it.
    Both ride in `health`, the same row `/health` itself was built from, so a snapshot missing
    coordinates there falls back to `compute()`'s own default rather than crashing on it.

    `peers` comes from the snapshot's own top-level `peer`, when one is there. The committed fixture
    (node1-2026-09-06.json) has none — its peer was synthetic, added by a design-repo script for the
    Phase 1 drawings — so a replay of it publishes an empty radio candidate list, correctly: no other
    node has been heard from that capture.

    `events` is the block the capture carried in its own /issues, verbatim: the events are rows the node read, not
    arithmetic, and replaying them through compute is what ranks the headline and recomputes uncovered_asks.

    `usual` is each issue's usual day as the capture carried it, verbatim; a capture from before v0.79 has none, and
    the engine's own read of `usual_by_hour` then fails on the Replay and says `unread`.
    """
    now = snapshot.get("as_of")
    if isinstance(now, str):
        now = datetime.fromisoformat(now)
    health = snapshot.get("health") or {}
    place = (health["lat"], health["lon"]) if health.get("lat") is not None and health.get("lon") is not None \
        else None
    peer = snapshot.get("peer")
    # Facilities are an input like `earth` and `peers`, not a sixth table: they postdate every
    # fixture but the newest, and a snapshot that has none simply has none. Read off the snapshot's
    # own /sensors body, which is where the pack's rows land.
    sensors = snapshot.get("sensors") or []
    facilities = [r for r in sensors if isinstance(r, dict) and r.get("kind") == "facility"]
    body = snapshot.get("issues") if isinstance(snapshot.get("issues"), dict) else {}
    captured = body.get("issues") if isinstance(body.get("issues"), dict) else {}
    usual = {k: (v.get("usual"), v.get("usual_absent")) for k, v in captured.items()
             if isinstance(v, dict) and "usual" in v} or None
    quiet = body.get("stations_silent") or {}
    silent = ([s for s in quiet.get("stations") or [] if isinstance(s, dict) and s.get("last_heard")]
              if quiet.get("read") else None)
    return compute(Replay(snapshot), settings, decl, earth=snapshot.get("earth"), now=now,
                   place=place, mesh=health.get("mesh"), peers=[peer] if peer else [],
                   facilities=facilities, events=body.get("events"), usual=usual, silent=silent)


def _geometry(lat: float, lon: float, settings, stations: list[dict], peers) -> dict:
    """The H3 shapes the dashboard's one control — the resolution dial — turns on, computed here so
    the page never has to. The plates alone are a few kB per resolution; the whole object is published
    in one shot because the page turns a dial across eleven resolutions, and asking per stop would be
    eleven round trips to draw one thing.

    Published under the names planetai-design's `h3.js` used (`nav.chain`, `nav.cells`, `nav.plates`,
    `grain_table`, `claims[i].cells_at`, `ladder`, `publication.res`, `radio.mine/candidates/res`,
    `settings.PRESENCE_RES_FLOOR`, `settings.RETICULUM_PRESENCE_RES`) so the prototype's kits port
    without a rename.

    A distance — room, yard, ring, region — is custody, not scale: nothing here maps a custody word to
    a resolution. This publishes the grid; the page says which custody a reading carries.
    """
    import h3  # noqa: PLC0415 — only this path needs it, same lazy import _stations already uses
    floor = geometry.FLOOR_RES
    pub = geometry.publication()
    peer_rows = [{"cell": p.get("cell"), "res": p.get("res"), "km": p.get("km")} for p in (peers or [])]
    return {
        "publication": pub,
        "ladder": geometry.ladder(lat, lon),
        "nav": geometry.plates(lat, lon, stations),
        "grain_table": geometry.grain_table(lat, lon, stations, floor_res=floor, publication_res=pub["res"]),
        "claims": geometry.claims(lat, lon, settings),
        "radio": geometry.radio(lat, lon, settings, peer_rows),
        "settings": {k: settings.num(k, d) for k, d in (
            ("LOCAL_RADIUS_M", 500), ("BAD_RADIUS_KM", 15), ("EARTH_RADIUS_M", 5000),
            ("PLACE_RADIUS_M", 1000), ("RETICULUM_PRESENCE_RES", 3))} | {"PRESENCE_RES_FLOOR": floor},
        "source": f"h3 {h3.__version__}, computed by this node",
    }


def _safe_geometry(lat: float, lon: float, settings, stations: list[dict], peers) -> dict | None:
    """The geometry, or None. One bad number in a setting — a radius, a resolution — reaches h3 through _geometry
    and an h3 exception would otherwise fail the whole /issues response, so the page that draws the air, the asks
    and the stations goes blank over the map. The page's `needs` machinery already prints one honest line for a
    section whose global is absent, which is the true thing to say here."""
    try:
        return _geometry(lat, lon, settings, stations, peers)
    except Exception:  # noqa: BLE001 — whatever h3 raises, the rest of the body is still an answer
        log.exception("geometry failed; /issues publishes geometry: null and the page says so")
        return None


def compute(cur, settings, decl: dict, earth: dict | None = None, now: datetime | None = None,
            place: tuple[float, float] | None = None, mesh: dict | None = None,
            peers=(), facilities=(), events: dict | None = None, usual: dict | None = None,
            silent: list[dict] | None = None) -> dict:
    """Every declared issue, computed. See the module docstring for what is arithmetic and what is not.

    `earth` is `/earth`'s body, passed in rather than re-read here so that the earth pack's record has
    exactly one reader in this repo. `now` is injectable so a fixture can be replayed at the hour it
    was captured; a stack computed against the wall clock of a different day is all `cached`.

    `place` is the coordinate `stations` measures `km` from; it defaults to this node's own position.
    `mesh` is `/health`'s mesh dict, passed in rather than read here — `/issues` makes no network call
    and no query the live cursor cannot answer, so a live call hands it `app/main.py`'s own module-level
    `mesh_state` (Ruling P3 in the Task 3 brief: neither `health` nor `presence` is a table to SELECT).

    `peers` is the Reticulum bridge's peer list, in the same spirit: a live call passes none, because
    fetching it costs an HTTP request and `/issues` makes no network call of its own. It only ever
    arrives here already in hand — from a snapshot's `peer`, when a replay has one.

    `events` is the alert events block (app/events_wire.py), built by the route on its own cursor, or the block a
    fixture captured. None is a node, or a capture, from before events: the page says so (SPEC_dashboard_events §5).

    `silent` is the capture's own silent stations, from a replay; None reads them.

    `usual` maps an issue to the (usual, usual_absent) pair a capture carried; a replay passes it, because a snapshot
    holds the /issues answer and not usual_by_hour. None reads the view, on a savepoint of its own.
    """
    global _said_unsited
    now = now or datetime.now(timezone.utc)
    if place is None:
        place = (float(settings.get("NODE_LAT", 0) or 0), float(settings.get("NODE_LON", 0) or 0))
    lat, lon = place
    # Both falsy is "unsited": /health publishes float(os.getenv("NODE_LAT", 0) or 0), so absent and unset arrive
    # as exactly 0, and 0,0 is open water. Once a day of logs, not once a request: /issues is polled.
    sited = bool(lat or lon)
    if not sited and not _said_unsited:
        log.warning("this node has no NODE_LAT/NODE_LON: station distances are published as unknown, "
                    "not measured from (0, 0). `planetai setup` sites it.")
        _said_unsited = True
    data = _read(cur)
    declared, dropped = order(settings.get("NODE_ISSUES", ""), decl)
    undeclared = [k for k in sorted(decl) if k not in declared]
    manifests = packs.manifests()
    domain_of = {m["id"]: m.get("domain") for m in manifests}
    # The packs the alert engine replaced: any pack that ships a kinded rule (app/main.py run_rules, #184). On shadow
    # and events their old rules' alerts are what the events stand for, so they are not asks of their own: not in
    # open_asks, not in uncovered_asks, and not what an issue's state is read from (docs/SPEC_event_led_state.md).
    owned = ({r["id"].split("/", 1)[0] for r in packs.load_rules() if r.get("kind")}
             if events is not None and events.get("engine") in ("shadow", "events") and not events.get("error")
             else set())
    # An issue's open event, and its latest clear within NOTABLE_HOURS, say its state on shadow and events (SPEC_event_led_state
    # §3.2). `owned` is empty on rules, and on a node whose packs ship no kinded rules, even on events: there the engine has
    # nothing to replace and no events open, so today's state is right.
    ev_open, ev_cleared = {}, {}
    if owned:
        for e in events.get("open") or []:
            ev_open.setdefault(e.get("issue"), e)
        for e in events.get("recent") or []:
            age = _age_minutes(e.get("cleared_at"), now)      # tz-safe: a naive value counts as UTC
            if age is not None and age <= NOTABLE_HOURS * 60:
                prev = ev_cleared.get(e.get("issue"))
                if prev is None or age < _age_minutes(prev["cleared_at"], now):
                    ev_cleared[e.get("issue")] = e
    names = {r["sensor_id"]: r.get("name") for r in data["stats"]}
    clock = _clock(data)

    buckets = sorted({r["bucket"] for r in data["hourly"]})[-24:]
    hourly: dict = {b: [] for b in buckets}
    for r in data["hourly"]:
        if r["bucket"] in hourly:
            hourly[r["bucket"]].append(r)

    # The usual band (docs/SPEC_dashboard_figures.md §3.1): a replay hands it over as the capture carried it.
    usual_rows = None if usual is not None else _optional(cur, USUAL_SQL)
    silent_rows = silent if silent is not None else _optional(cur, SILENT_SQL, SILENT_DAYS)
    out = {}
    for key in declared + undeclared:
        d = dict(decl[key])
        if key in undeclared:
            # Still shown, at the foot of the index, so a stranger sees what this node could do.
            out[key] = {"state": "none", "watched": False,
                        "reason": {"code": "not_watched"},
                        "reason_text": {loc: _reason_text({"code": "not_watched"}, loc) for loc in LOCALES},
                        "name": d["name"], "kind": d["kind"], "unit": d["unit"], "dp": d["dp"],
                        "stack": {dist: None for dist in DISTANCES}, "line": d.get("line"),
                        "attribution": None, "open_asks": [], "series": {dist: None for dist in DISTANCES},
                        "readouts": [], "provenance": [],
                        # "not watched here", not "no source". The node may well have a source for
                        # this — coast has a marine model wherever there is a sea — and telling a
                        # stranger there is none would be false. The row is greyed and says the
                        # true thing: nobody here asked for it.
                        "sentence": {loc: _reason_text({"code": "not_watched"}, loc)[0].upper()
                                          + _reason_text({"code": "not_watched"}, loc)[1:] + "."
                                     for loc in LOCALES},
                        "title": {loc: _reason_text({"code": "not_watched"}, loc)[0].upper()
                                       + _reason_text({"code": "not_watched"}, loc)[1:] + "."
                                  for loc in LOCALES},
                        "tagline": {loc: "" for loc in LOCALES},
                        "hero": None, "usual": None, "usual_absent": "not_watched"}
            continue

        compare = d.get("compare") or {"mode": "ratio", "margin": 1.5}
        line = d.get("line")
        stack = _stack(d, data["stats"], data["obs"], earth, names, now)
        d["_readouts"] = _readouts(d, data["obs"])
        open_asks, recent = _asks(d, data["alerts"], data["actions"], stack, line, domain_of, now, owned)
        state, reason = _state(d, stack, open_asks, recent, line,
                               {"open": ev_open.get(key), "cleared": ev_cleared.get(key)})
        series = _series(d, hourly, buckets, names)
        # the headline number is the nearest distance that has one: the room if there is one, else
        # the yard, else the ring, else the model. Same order as every other answer in this repo.
        headline = next((x for x in DISTANCES if stack.get(x)), DISTANCES[0])
        attribution = _classify(stack, line, compare) if d["kind"] == "sensed" else None
        verb_key = _trend(series.get("room") or series.get(headline), compare)
        if reason.get("code") in ("no_alert", "over_line"):
            reason = {**reason, **_peak(series.get("room") or series.get(headline), buckets, d["dp"], d["unit"], clock)}
        _parts = {loc: _sentence_parts(d, stack, state, headline, verb_key, loc, compare,
                                       attribution, line, reason)
                  for loc in LOCALES}
        out[key] = {
            "state": state, "watched": True,
            "reason": reason,
            "reason_text": {loc: _reason_text(reason, loc) for loc in LOCALES},
            "name": d["name"], "kind": d["kind"], "metric": d["metric"], "unit": d["unit"], "dp": d["dp"],
            "about": d.get("about"),
            "headline": headline, "stack": stack, "line": line, "attribution": attribution,
            "trend": verb_key,
            # How far it moved, beside which way it went. The page shows it; _headline ranks on it (_lead).
            "moved": round(_moved(series.get("room") or series.get(headline)), 4),
            "open_asks": open_asks,
            "series": series, "buckets": [b.isoformat() if hasattr(b, "isoformat") else b for b in buckets],
            "readouts": [{k: v for k, v in r.items() if not k.startswith("_")} for r in d["_readouts"]],
            "provenance": _provenance(d, stack, earth),
            "sentence": {loc: _parts[loc][0] for loc in LOCALES},
            # The page's title is the sentence's qualitative head — no numbers, no indicators;
            # the tagline explains, smaller. The full sentence stays for prose (the bot, the asks).
            "title": {loc: _parts[loc][1] for loc in LOCALES},
            "tagline": {loc: _parts[loc][2] for loc in LOCALES},
        }
        out[key]["hero"] = _hero(d, stack, headline, out[key]["sentence"], now, clock)
        out[key]["usual"], out[key]["usual_absent"] = (usual[key] if usual is not None and key in usual
                                                       else _usual(d, headline, stack.get(headline), usual_rows))

    lead = _lead(out, declared, events)
    if events is not None:
        covered = {a for e in events.get("open") or [] for a in e.get("alerts") or []}
        events = {**events, "open": [{**e, "series": _room_series(decl.get(e.get("issue")) or {}, hourly, buckets,
                                                                     names, e.get("rooms"))}
                                     for e in events.get("open") or []],
                  "uncovered_asks": [
            a["id"] for v in out.values() for a in (v.get("open_asks") or [])
            if a.get("id") is not None and a["id"] not in covered
            and str(a.get("rule_id") or "").split("/", 1)[0] not in owned]}
    headline_issue = lead["issue"] if lead else None
    stations = _stations(data["stats"], data.get("hourly"), lat, lon, sited, silent_rows)
    # A station that stopped is published for the page's fold under `stations_silent.stations`, never in `stations`:
    # geometry's cell `sensors` are positions in the list it is given, and every existing reader of `stations` (the
    # digest, simple mode's neighbours, the grain table, the page) means the stations heard in the last day
    # (SPEC_dashboard_figures §3.3).
    heard = [s for s in stations if not s.get("last_heard")]
    stopped = [s for s in stations if s.get("last_heard")]
    geom = _safe_geometry(lat, lon, settings, heard, peers)
    asks = _asks_ledger(data["alerts"], data["actions"], list(facilities or []))
    # ARCHITECTURE.md §3: the one document a client draws says which document it is. A reader that
    # sees a schema it does not know draws what it recognises; it never refuses, and the dashboard's
    # assertion is one sentence rather than a blank page.
    return {"schema": "issues-v0",
            "order": declared, "undeclared": undeclared, "dropped": dropped,
            "headline": headline_issue, "as_of": now.isoformat(),
            # the same pick, and which step of HEADLINE_RULE made it: event, state, moved or order
            "lead": lead,
            # why that one is at the top, in three languages — see HEADLINE_RULE
            "headline_rule": HEADLINE_RULE,
            # the column headings, so the page and Telegram both take their words from the node
            "distances": list(DISTANCES), "labels": LABEL_WORDS,
            "issues": out,
            # what the modular dashboard reads beside the issues — 15 September 2026's decisions
            "stations": heard,
            # whether the stations that stopped were read, how far back, and which (docs/SPEC_dashboard_figures.md §3.3)
            "stations_silent": {"read": silent_rows is not None, "within_days": SILENT_DAYS, "stations": stopped},
            "metrics": METRICS,
            "asks": asks,
            # simple mode's whole answer, written here because the page may not compose a sentence
            "digest": _digest(out, heard, geom, asks, headline_issue, now, clock,
                              _oldest(data["alerts"])),
            "mesh": _mesh(mesh, data["stats"]),
            "geometry": geom,
            # sections the enabled packs declare as data, with the node's own numbers in them; the page draws them
            # with its readout cards (docs/decisions/2026-10-01-packs.md, point 5)
            "sections": _sections(pack_sections(manifests), data["obs"], now),
            # the alert events, one per issue per house, as the bot tells them (docs/SPEC_dashboard_events.md §3.1)
            "events": events}


DAYS_MAX = 90


def _local_days(buckets: list, tz) -> list[tuple]:
    """(local date, [indexes into buckets]) in order. A window starts and ends inside a day, so `of` says how many of
    that day's hours the window holds."""
    out: list[tuple] = []
    for i, b in enumerate(buckets):
        day = b.astimezone(tz).date()
        if out and out[-1][0] == day:
            out[-1][1].append(i)
        else:
            out.append((day, [i]))
    return out


def days(cur, settings, decl: dict, n: int, now: datetime | None = None) -> dict:
    """GET /issues/days: each declared issue's hourly series over n local days, computed by the same `_series` that
    gives /issues its 24 hours, so a cell of the page's strip is what the lead's numeral said at that hour
    (docs/SPEC_dashboard_figures.md §3.4). The node counts the hours over the line, so the page prints a count it did
    not make. Buckets are generated, not observed: an hour with no row at all is a null, never a skipped column.
    Node #1 reads 90 days of readings_1h in 164 ms (6 October 2026), so there is no cache."""
    now = now or datetime.now(timezone.utc)
    n = max(1, min(int(n), DAYS_MAX))
    cur.execute("SELECT current_setting('TimeZone') AS tz")
    tzname = (cur.fetchone() or {}).get("tz") or "UTC"
    try:
        tz = ZoneInfo(tzname)
    except (ZoneInfoNotFoundError, ValueError):
        tz = timezone.utc
    top = now.astimezone(tz).replace(minute=0, second=0, microsecond=0).astimezone(timezone.utc)
    # Stepped in UTC and shown in the node's zone: across a daylight-saving change, wall-clock arithmetic would skip
    # the repeated hour or invent one that does not exist. A fall-back day then holds 25 hours, a spring-forward 23.
    buckets = [(top - timedelta(hours=k)).astimezone(tz) for k in range(n * 24 - 1, -1, -1)]
    hourly: dict = {b: [] for b in buckets}
    for r in _rows(cur, "SELECT h.bucket, h.sensor_id, h.metric, h.mean, s.indoor, s.local, s.kind "
                        "FROM readings_1h h JOIN sensors s USING (sensor_id) WHERE h.bucket >= %s", buckets[0]):
        b = r["bucket"] if isinstance(r["bucket"], datetime) else datetime.fromisoformat(r["bucket"])
        if b in hourly:
            hourly[b].append(r)
    declared, _ = order(settings.get("NODE_ISSUES", ""), decl)
    groups = _local_days(buckets, tz)
    issues: dict = {}
    for key in declared:
        d = decl[key]
        series = _series(d, hourly, buckets, {})
        dist = next((x for x in DISTANCES if series.get(x)), None)
        line = d.get("line")
        lv = float(line["value"]) if line and line.get("value") is not None else None
        per_day = []
        for day, idx in (groups if dist else []):
            got = [series[dist][i] for i in idx if series[dist][i] is not None]
            per_day.append({"date": day.isoformat(), "over": None if lv is None else sum(1 for v in got if v > lv),
                            "read": len(got), "of": len(idx)})
        issues[key] = {"distance": dist, "series": series,
                       "provenance": {x: _word(x) for x in DISTANCES if series.get(x)},
                       "per_day": per_day, "line": line}
    events = _rows(cur, "SELECT id, issue, kind, level, opened_at, cleared_at FROM alert_events "
                        "WHERE opened_at >= %s OR cleared_at IS NULL OR cleared_at >= %s ORDER BY opened_at",
                   buckets[0], buckets[0])
    iso = lambda v: v.isoformat() if hasattr(v, "isoformat") else v  # noqa: E731
    return {"schema": "days-v0", "as_of": now.isoformat(), "tz": tzname, "days": n,
            "buckets": [b.isoformat() for b in buckets],
            "issues": issues,
            "events": [{**e, "opened_at": iso(e["opened_at"]), "cleared_at": iso(e["cleared_at"])} for e in events]}


def _sections(decl: list[dict], obs: list[dict], now: datetime) -> list[dict]:
    """Each declared section with its readouts computed the way an issue's are: the latest row of each sensor and
    metric, and nothing for a pair with no row. `expected` is how many it declared, so the page can say how many have
    not arrived rather than drawing a short card as if it were whole."""
    out = []
    for sec in decl:
        rows = _readouts(sec, obs)
        out.append({"id": sec["id"], "pack": sec["pack"], "stage": sec["stage"], "title": sec["title"],
                    "order": sec.get("order", 50), "wall": bool(sec.get("wall")), "note": sec.get("note"),
                    "expected": len(sec["readouts"]),
                    "readouts": [{**{k: v for k, v in r.items() if not k.startswith("_")}, "sensor_id": r["_sid"],
                                  "age_minutes": _age_minutes(r.get("_ts"), now)} for r in rows]})
    return out


STATE_RANK = {"act": 4, "notable": 3, "quiet": 2, "context": 1, "none": 0}


def _lead(out: dict, declared: list[str], events: dict | None = None) -> dict | None:
    """The issue with the highest state; among equals, the one that has moved most; then declared order.

    STATE STILL WINS OUTRIGHT, and that is the whole shape of this. Something that needs doing cannot
    be pushed down the page by something that merely moved a lot — an `act` outranks every `notable`
    however dramatic. Change is the tie-break INSIDE a state, where the old rule had nothing but the
    order the household typed and two issues saying the same thing were separated by alphabet.

    Asked for 18 September: lead with the data showing the most significant change. `moved` is that,
    per issue, relative to its own recent level so that micrograms and degrees can be compared at all.

    AN OPEN EVENT LEADS FIRST (docs/SPEC_dashboard_events.md §3.1). The bot has interrupted somebody about it, or would
    have in shadow, so the page opens on the same story. `events["open"]` is already ranked (danger, then sustained,
    then unusual, then spike; then the one open longest), so the first whose issue can lead is the lead, `by: event`.

    Deterministic: `moved` is a rounded float off the same six buckets every time, and the declared
    order still breaks an exact tie, so the same capture always produces the same headline. And still
    printable in one sentence, which is the reason the old rule was worth keeping the shape of.

    Only an issue with a hero can lead: the page draws the lead blind from `hero`, so an issue that
    declares none has nothing to draw there. It is still watched, and still in the also line.

    Returns `{issue, by}`, where `by` is the step that separated the leader from the runner-up —
    `state`, `moved`, or `order` when the two were level on both (or there was nobody else).
    """
    cands = [k for k in declared if out[k].get("hero")]
    if not cands:
        return None
    first = next((e["issue"] for e in ((events or {}).get("open") or []) if e.get("issue") in cands), None)
    if first:
        return {"issue": first, "by": "event"}
    rank = lambda k: (STATE_RANK.get(out[k]["state"], 0), out[k].get("moved", 0.0))  # noqa: E731
    best = max(cands, key=rank)             # max keeps the first of equals: declared order breaks a tie
    rest = [k for k in cands if k != best]
    by = "order"
    if rest:
        runner = max(rest, key=rank)
        if rank(best)[0] > rank(runner)[0]:
            by = "state"
        elif rank(best)[1] > rank(runner)[1]:
            by = "moved"
    return {"issue": best, "by": by}


def _provenance(d: dict, stack: dict, earth: dict | None) -> list[dict]:
    """Every figure this issue puts on the page, with where it came from and its word.

    This is what makes `live` an earned word rather than a decoration: the Figures band is generated
    from this list, so a number with no row here cannot be drawn.
    """
    rows = []
    for dist in DISTANCES:
        cell = stack.get(dist)
        if not cell:
            continue
        rows.append({"figure": f"{d['key']}.{dist}", "value": cell["value"], "unit": d["unit"],
                     "source": cell["source"], "provenance": cell["provenance"],
                     "age_minutes": cell["age_minutes"], "n": cell["n"]})
    for r in d.get("_readouts") or []:
        rows.append({"figure": f"{d['key']}.{r['metric']}", "value": r["value"], "unit": r["unit"],
                     "source": r["source"], "provenance": r["provenance"], "age_minutes": None,
                     "n": 1})
    if d.get("line"):
        rows.append({"figure": f"{d['key']}.line", "value": d["line"]["value"],
                     "unit": d["line"].get("unit", d["unit"]), "source": d["line"]["source"],
                     "provenance": "reference", "age_minutes": None, "n": 1})
    if (d.get("distances") or {}).get("region", {}) and \
            ((d.get("distances") or {}).get("region") or {}).get("from") == "earth" and earth:
        rows.append({"figure": f"{d['key']}.square", "value": earth.get("radius_m"), "unit": "m",
                     "source": earth.get("attribution", ""), "provenance": "model",
                     "age_minutes": None, "n": 1})
    return rows
