"""What GET /forecast says about the next days, from the hours the node stored (docs/SPEC_next_days.md §4). Pure: no
database, no environment, no clock of its own. routes.py reads the rows and hands them in.

Days are local. The first is "rest", from the next whole hour to midnight, then tomorrow and the day after. Air and
heat are judged with the engine's own comparison (issues.engine._line_key, apparent) against the line the issue
declares, so this view and /issues cannot disagree about what "over" means. A row whose source or issue is off is
left out, and a day with nothing to say has `rows: {}`. `hours_over` and `n` are hours: a 3-hourly source (BMKG) counts
each value as the 3 hours it stands for. `cells` are the distinct model grid points the territory's sensors answered
from, not the sensors: res-7 neighbours sit ~2.5 km apart and the models' own cells are 10-44 km.
"""
from __future__ import annotations

from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from issues.engine import _line_key, apparent

OM, CAMS, MARINE, BMKG, GAP = "forecast-om", "forecast-cams", "forecast-marine", "forecast-bmkg", "forecast-gap"
BASES = (BMKG, OM, CAMS, MARINE, GAP)
ATTRIBUTION = ["BMKG (Badan Meteorologi, Klimatologi, dan Geofisika), api.bmkg.go.id",
               "Open-Meteo, open-meteo.com, CC-BY 4.0 (free tier: non-commercial use only)"]


def base(sid: str) -> str:
    """`forecast-om-8a1` is a neighbouring cell of `forecast-om`; the bare id is the node's own point."""
    return next((b for b in BASES if sid == b or sid.startswith(b + "-")), sid)


def _dt(ts) -> datetime:
    return ts if isinstance(ts, datetime) else datetime.fromisoformat(ts)


def _utc(ts) -> str:
    return _dt(ts).astimezone(timezone.utc).isoformat()


def _hrs(x: float):
    """Hours as a whole number when they are one."""
    return int(x) if x == int(x) else round(x, 1)


def _cadence(hours: list[dict]) -> dict:
    """Hours one value of each source stands for: the smallest gap between consecutive timestamps of that source's own
    series (BMKG 3, Open-Meteo and CAMS 1), 1 where there is only one value. The smallest, not each value's own gap: a
    missing hour in the store must not make its neighbour count for two."""
    seen: dict = {}
    for h in hours:
        seen.setdefault(h["source"], set()).add(_dt(h["ts"]))
    out = {}
    for src, ts in seen.items():
        ts = sorted(ts)
        out[src] = min(((b - a).total_seconds() / 3600 for a, b in zip(ts, ts[1:])), default=1)
    return out


def answered_at(w: dict):
    """Where a forecast sensor answered from: its stored lat/lon, which is the model's grid point as the API answered it
    (the cell asked for is `meta.cell`). One with no place counts as its own."""
    return (round(float(w["lat"]), 3), round(float(w["lon"]), 3)) if w.get("lat") is not None and w.get("lon") is not None \
        else w["sensor_id"]


def _r(x: float, dp: int):
    return round(x) if dp == 0 else round(x, dp)


def _judge(x: float, line: dict) -> tuple:
    """(the value as shown, its state). The state is the engine's, read off the unrounded figure as /issues reads it;
    only the value is rounded for the page."""
    return _r(x, line.get("dp", 0)), _line_key({"kind": "sensed"}, x, line)


def _wettest(rain: list, end: datetime) -> str | None:
    """The 3 hours with the most rain, "HH:00–HH:00" local; a block stops at the day's end. None with no rain."""
    best, at = 0.0, None
    for t0, _ in rain:
        s = sum(v for t, v in rain if t0 <= t < t0 + timedelta(hours=3))
        if s > best:
            best, at = s, t0
    if at is None:
        return None
    return f"{at:%H:00}–{min(at + timedelta(hours=3), end):%H:00}"


def build(hours: list[dict], lines: dict, tz: str, now: datetime, grid: dict) -> list[dict]:
    """The `days` array. `hours` are steps {"ts", "source", <metric>: value} of every forecast sensor, neighbouring
    cells included; `lines` is {"air": {value, unit, dp}, "heat": {…}} for the issues this node has on;
    `grid` is {sensor_id: the model grid point it answered from} (`answered_at`), which is what counts a territory's cells."""
    zone = ZoneInfo(tz)
    local = now.astimezone(zone)
    first = local.date()
    start = local.replace(minute=0, second=0, microsecond=0)
    if start < local:
        start += timedelta(hours=1)
    days, step = [], _cadence(hours)
    for k in range(3):
        d = first + timedelta(days=k)
        end = datetime.combine(d + timedelta(days=1), time(0), tzinfo=zone)
        lo = start if k == 0 else datetime.combine(d, time(0), tzinfo=zone)
        mine = [(_dt(h["ts"]).astimezone(zone), h) for h in hours]
        mine = [(t, h) for t, h in mine if lo <= t < end]
        days.append({"date": d.isoformat(), "part": "rest" if k == 0 else "day",
                     "rows": _rows(mine, lines, end, grid, step)})
    return days


def _rows(steps, lines, end, grid, step) -> dict:
    def series(source, metric):
        return [(t, h[metric]) for t, h in steps if h["source"] == source and h.get(metric) is not None]

    def over(per_sid, line) -> dict:
        """cells and cells_over, only when more than one grid point has a figure; sensors on one point are one cell."""
        cell = {}
        for sid, x in per_sid.items():
            cell[grid.get(sid, sid)] = x
        if len(cell) < 2:
            return {}
        return {"cells": len(cell), "cells_over": sum(_judge(x, line)[1] == "over" for x in cell.values())}

    def sids(root, metric):
        return {h["source"] for _, h in steps if base(h["source"]) == root and h.get(metric) is not None}

    rows = {}
    line = lines.get("air")
    vals = series(CAMS, "fc_pm25")
    if line and vals:
        mean = sum(v for _, v in vals) / len(vals)
        peak_t, peak = max(vals, key=lambda tv: tv[1])
        value, state = _judge(mean, line)
        per = {s: (lambda x: sum(v for _, v in x) / len(x))(series(s, "fc_pm25")) for s in sids(CAMS, "fc_pm25")}
        rows["air"] = {"value": value, "unit": line.get("unit"), "metric": "fc_pm25", "of": "mean",
                       "peak": _r(peak, line.get("dp", 0)), "peak_at": f"{peak_t:%H:%M}", "source": CAMS,
                       "line": line["value"], "state": state,
                       "hours_over": _hrs(sum(v > line["value"] for _, v in vals) * step[CAMS]),
                       "n": _hrs(len(vals) * step[CAMS]), **over(per, line)}

    line = lines.get("heat")
    if line:
        def at(source):
            return [(t, apparent(h["fc_temp"], h["fc_humidity"])) for t, h in steps
                    if h["source"] == source and h.get("fc_temp") is not None and h.get("fc_humidity") is not None]
        src = next((s for s in (OM, BMKG) if at(s)), None)
        if src:
            vals = at(src)
            value, state = _judge(max(v for _, v in vals), line)
            other = [s for s in (OM, BMKG) if s != src and at(s)]
            per = {s: max(v for _, v in at(s)) for s in {h["source"] for _, h in steps if base(h["source"]) == OM
                   and h.get("fc_temp") is not None and h.get("fc_humidity") is not None}} if src == OM else {}
            rows["heat"] = {"value": value, "unit": line.get("unit"), "metric": "apparent", "of": "max", "source": src,
                            "line": line["value"], "state": state,
                            "hours_over": _hrs(sum(v > line["value"] for _, v in vals) * step[src]),
                            "n": _hrs(len(vals) * step[src]), **({"also": other} if other else {}), **over(per, line)}

    def wr(source):
        return series(source, "fc_wind_gusts"), series(source, "fc_rain")
    src = next((s for s in (OM, BMKG) if any(wr(s))), None)
    if src:
        gust, rain = wr(src)
        total = sum(v for _, v in rain)
        other = [s for s in (OM, BMKG) if s != src and any(wr(s))]
        rows["wind_rain"] = {"gust": _r(max(v for _, v in gust), 0) if gust else None,
                             "rain_mm": round(total, 1) if rain else None,
                             "rain_hours": _wettest(rain, end), "source": src,
                             "n": _hrs(len({t for t, _ in gust + rain}) * step[src]), **({"also": other} if other else {})}

    wave = series(MARINE, "fc_wave_m")
    if wave:
        rows["sea"] = {"value": round(max(v for _, v in wave), 1), "unit": "m", "metric": "fc_wave_m", "of": "max",
                       "source": MARINE, "n": _hrs(len(wave) * step[MARINE])}
    return rows


def _sources(who: list[dict], rows: list[dict], openmeteo: bool, coast: bool) -> list[dict]:
    """One entry a source: the node's own sensor's, with `cells` for the ones that cover a territory. A source whose
    switch is on and that has no rows is named as absent; one that is off is not mentioned."""
    out = []
    for b in BASES:
        mine = sorted((w for w in who if base(w["sensor_id"]) == b), key=lambda w: w["sensor_id"])
        own = next((w for w in mine if w["sensor_id"] == b), mine[0] if mine else None)
        if own is None or not any(base(r["sensor_id"]) == b for r in rows):
            if (b in (OM, CAMS) and openmeteo) or (b == MARINE and openmeteo and coast):
                out.append({"sensor_id": b, "absent": True})
            elif own is not None:
                out.append(_source(own))
            continue
        out.append({**_source(own), **({"cells": len({answered_at(w) for w in mine})} if b in (OM, CAMS) else {})})
    return out


def _source(w: dict) -> dict:
    m = w.get("meta") or {}
    return {"sensor_id": w["sensor_id"], "name": w["name"], "lat": w["lat"], "lon": w["lon"],
            "issued": m.get("issued"), "fetched": m.get("fetched"),
            # BMKG's meta says km_from_node, the sea's says distance_km (the adapter writes both as they are)
            "km_from_node": m["km_from_node"] if m.get("km_from_node") is not None else m.get("distance_km")}


def answer(*, who: list[dict], rows: list[dict], issue_lines: dict, ahead: list[dict], tz: str, now: datetime,
           point: dict, hours: int, openmeteo: bool, coast: bool) -> dict:
    """The whole GET /forecast body (schema forecast-v0) from the sensors, the readings (sensor_id, ts, metric, value;
    ts as ISO text or datetimes), the issues' lines and the packs' `ahead` lines. The dict is written out as a literal
    so tools/check_wire.py can read its keys."""
    # a source that is switched off draws nothing: its last fetch sits up to 72 h in the future and would keep showing.
    # Open-Meteo's three sources and the gap against BMKG (derived from it) go with FORECAST_OPENMETEO; the sea also
    # needs the coast pack.
    off = {OM, CAMS, MARINE, GAP} if not openmeteo else ({MARINE} if not coast else set())
    who = [w for w in who if base(w["sensor_id"]) not in off]
    rows = [r for r in rows if base(r["sensor_id"]) not in off]
    steps: dict = {}
    for r in rows:
        steps.setdefault((_utc(r["ts"]), r["sensor_id"]), {})[r["metric"]] = r["value"]
    every = [{"ts": k[0], "source": k[1], **v} for k, v in sorted(steps.items())]
    cutoff = _utc(now + timedelta(hours=hours))
    # an hour with temperature and humidity also carries the feels-like heat's line is on, from the engine's own
    # function, so Next days draws heat's 72 h against its line and the page never computes it a second way
    own = [{**h, **({"apparent": _r(apparent(h["fc_temp"], h["fc_humidity"]), 1)}
                    if h.get("fc_temp") is not None and h.get("fc_humidity") is not None else {})}
           for h in every if base(h["source"]) == h["source"] and h["ts"] <= cutoff]
    srcs = _sources(who, rows, openmeteo, coast)
    # a forecast for somewhere else is still a forecast, but the card has to say so rather than imply this point. The sea
    # is left out: it is always a cell of water, the classic card reads far_from_node[0] as the weather point, and Next
    # days reads the sea's distance from its own source (`km_from_node`)
    far = [{"sensor_id": s["sensor_id"], "km": s["km_from_node"]} for s in srcs
           if (s.get("km_from_node") or 0) > 10 and s["sensor_id"] != MARINE]
    grid = {w["sensor_id"]: answered_at(w) for w in who}
    return {"point": point,
            "sources": srcs,
            "hours": own,
            "attribution": ATTRIBUTION,
            "far_from_node": far or None,
            "days": build(every, issue_lines, tz, now, grid),
            "lines": ahead,
            "openmeteo": openmeteo,
            "schema": "forecast-v0"}
