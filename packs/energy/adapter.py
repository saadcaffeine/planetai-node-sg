"""Grid mix, fossil share, and nearest power infrastructure for the cell this node stands in.

Finds the node's synchronous grid in grids.yml, queries OpenStreetMap via Overpass once every ENERGY_REFRESH_DAYS (30)
for plants, generators, substations and cable heads in that grid's bounding box, and computes the grid's fossil share
every ENERGY_POLL_HOURS (6): a measured trailing-year share where the operator publishes daily generation (REE for the
Balearic grid), or an explicit [low, high] range from OSM capacities and capacity factors where it does not (Bali).
With ENERGY_HA_URL set it also reads the house's own power from its Home Assistant every poll (ha.py, `_home`).
The Today box is today's forecast sun on ENERGY_PANEL_KW of panels, or the roof's measured kWh (today.py, `_today`).
"""
from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))

import grids
import ha
import mix
import osm
import ree
import today

log = logging.getLogger("planetai.energy")
SID = "energy-grid"
HOME = "energy-home"
LARGE_MW = 100.0        # a large plant: large_plant_km, and the one the Wall draws its line to
USER_AGENT = "planetai-node/energy (https://planetai.fab.city; info@fab.city)"
OSM_ATTR = "© OpenStreetMap contributors, ODbL, via Overpass"
REE_ATTR = "Red Eléctrica de España (REE), apidatos.ree.es"
EMBER_ATTR = "Ember Yearly Electricity Data (CC BY 4.0)"


def _out() -> Path:
    return Path(os.getenv("PACK_OUT", "/app/out")) / "energy"


def result() -> dict:
    p = _out() / "result.json"
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text())
    except Exception:
        return {}


def _osm_sources(hc, g: dict, now: datetime) -> list[dict]:
    refresh_days = max(1, int(os.getenv("ENERGY_REFRESH_DAYS", "30") or "30"))
    cache = _out() / f"osm-{g['id']}.json"
    if cache.exists():
        try:
            saved = json.loads(cache.read_text())
            ts = datetime.fromisoformat(saved["fetched_at"])
            if now - ts < timedelta(days=refresh_days) and isinstance(saved.get("sources"), list):
                return saved["sources"]
        except Exception:
            pass
    url = os.getenv("OVERPASS_URL", "https://overpass-api.de/api/interpreter")
    s, w, n, e = grids.bbox(g.get("polygon") or [])
    q = osm.QUERY.format(s=s, w=w, n=n, e=e)
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    try:
        if hasattr(hc, "post"):
            r = hc.post(url, data={"data": q}, timeout=120, headers=headers)
        else:
            r = hc.get(url, params={"data": q}, timeout=120, headers=headers)
        r.raise_for_status()
        sources = osm.parse(r.json())
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps({"fetched_at": now.isoformat(), "sources": sources}))
        return sources
    except Exception as exc:
        log.warning("energy: overpass fetch failed for %s: %s", g["id"], exc)
        if cache.exists():
            try:
                return json.loads(cache.read_text()).get("sources") or []
            except Exception:
                pass
        return []


def _grid_mix(hc, g: dict, sources: list[dict], now: datetime) -> dict:
    poll_hours = max(1, int(os.getenv("ENERGY_POLL_HOURS", "6") or "6"))
    gm = g.get("mix") or {}
    if gm.get("source") == "ree" or gm.get("kind") == "measured":
        st = ree._load()
        if st.get("grid") == g["id"] and st.get("polled_at") and isinstance(st.get("last_out"), dict):
            try:
                if now - datetime.fromisoformat(st["polled_at"]) < timedelta(hours=poll_hours):
                    return st["last_out"]
            except Exception:
                pass
        out = ree.fetch(hc, st, now.date(), g)
        st["grid"] = g["id"]
        st["polled_at"] = now.isoformat()
        st["last_out"] = out
        ree._save(st)
        return out
    return mix.estimate(sources, g)


def _build_bar(sources: list[dict], g: dict, m: dict) -> list[dict]:
    if m.get("kind") == "measured":
        val = m.get("value")
        if val is None:
            return []
        return [
            {"label": "fossil", "fossil": True, "share": round(float(val), 4), "hatched": False},
            {"label": "clean", "fossil": False, "share": round(max(0.0, 1.0 - float(val)), 4), "hatched": False},
        ]
    poly = g.get("polygon") or []
    cf = g.get("capacity_factors") or {}
    by_fuel: dict[str, tuple[float, bool]] = {}
    total_w = 0.0
    for s in sources or []:
        if s.get("kind") != "plant" or not (s.get("mw") and s["mw"] > 0):
            continue
        if s.get("lat") is None or s.get("lon") is None or not grids.inside(s["lat"], s["lon"], poly):
            continue
        factor = mix._cf(cf, s.get("fuel"))
        if not factor or factor <= 0 or s.get("fossil") is None:
            continue
        w = float(s["mw"]) * factor
        total_w += w
        fl = str(s.get("fuel") or "other")
        prev_w, _ = by_fuel.get(fl, (0.0, bool(s["fossil"])))
        by_fuel[fl] = (prev_w + w, bool(s["fossil"]))
    if total_w <= 0:
        return []
    links = g.get("links") or []
    imp_max = m.get("import_max")
    # An unknown import share stays unknown: the island's fuels are shares of what the island makes, and the link's
    # segment has no width, never a guessed one.
    imp_sh = (imp_max if imp_max is not None else None) if links else 0.0
    scale = max(0.0, 1.0 - (imp_sh or 0.0))
    bar: list[dict] = []
    for fl, (w, is_f) in sorted(by_fuel.items(), key=lambda kv: (-kv[1][1], -kv[1][0])):
        bar.append({"label": fl, "fossil": is_f, "share": round((w / total_w) * scale, 4), "hatched": False})
    for lk in links:
        seg = {"label": lk["name"], "fossil": True, "hatched": True,
               "share": round(imp_sh / len(links), 4) if imp_sh is not None else None}
        if imp_max is None:
            seg["note"] = "share not published"
        bar.append(seg)
    return bar


def _today() -> dict:
    """The Today box: today's forecast sun (or the roof's measured kWh) and the pack's panel and daily-use settings."""
    sun, roof = today.read()
    return today.box(sun, today.setting("ENERGY_PANEL_KW", "2"), today.setting("ENERGY_HOUSE_KWH_DAY", "9"), roof)


def _cells(sources: list[dict], lat: float, lon: float) -> list[dict] | None:
    """The node's seven res-8 cells (its own and the six touching it, SPEC_eyes §5, as packs/eyes counts them), each
    with its outline from h3 and the MW of the OSM plants standing in it. A generator is listed, never summed (its plant
    carries the MW). A plant with no capacity makes its cell's MW unknown (None), never 0. No sources at all is an
    Overpass fetch that never landed, so there are no cells to say anything about: None, not seven zeros."""
    if not sources:
        return None
    import h3  # noqa: PLC0415 — the app's own dependency; the pack runs in its container

    home = h3.latlng_to_cell(lat, lon, 8)
    seven = h3.grid_disk(home, 1)
    mw: dict[str, float | None] = {c: 0.0 for c in seven}
    for s in sources:
        if s.get("kind") != "plant" or s.get("lat") is None or s.get("lon") is None:
            continue
        c = h3.latlng_to_cell(s["lat"], s["lon"], 8)
        if c in mw:
            mw[c] = None if mw[c] is None or s.get("mw") is None else mw[c] + float(s["mw"])
    out = []
    for c in sorted(seven):
        ring = [[round(x, 6), round(y, 6)] for y, x in h3.cell_to_boundary(c)]
        clat, clon = h3.cell_to_latlng(c)
        out.append({"id": c, "home": c == home, "lat": round(clat, 6), "lon": round(clon, 6),
                    "ring": ring + ring[:1], "mw": mw[c]})
    return out


def _grid(hc) -> tuple[list[dict], list[tuple], dict | None]:
    try:
        lat, lon = float(os.getenv("NODE_LAT", "0")), float(os.getenv("NODE_LON", "0"))
    except ValueError:
        return [], [], None
    if lat == 0.0 and lon == 0.0:
        return [], [], None
    g = grids.grid_for(lat, lon, grids.load())
    if g is None:
        return [], [], None

    now = datetime.now(timezone.utc)
    raw_sources = _osm_sources(hc, g, now)
    near_all = [
        dict(s, km=round(float(s["km"]), 2), ring=grids.ring_for(s["lat"], s["lon"], g))
        for s in osm.near(raw_sources, lat, lon)
    ]
    m = _grid_mix(hc, g, raw_sources, now)

    gm = g.get("mix") or {}
    is_meas = m.get("kind") == "measured"
    method = m.get("method") or gm.get("method") or gm.get("source") or "unknown"
    attrs = [OSM_ATTR, REE_ATTR if is_meas else EMBER_ATTR]

    # only what stands on this grid: the Bali box also holds Nusa Penida's own island grid and a corner of Java
    near_all = [s for s in near_all if grids.inside(s["lat"], s["lon"], g.get("polygon") or [])]
    # the five nearest substations: /energy says one, the nearest the house for the household and the nearest the
    # cell's middle for anyone else, and that one need not be the house's
    subs = [s for s in near_all if s["kind"] == "substation"][:5]
    plants = [s for s in near_all if s["kind"] == "plant" and (s.get("mw") or 0) >= 1.0]
    big_plants = [s for s in near_all if s["kind"] == "plant" and (s.get("mw") or 0) >= LARGE_MW]
    import h3  # noqa: PLC0415
    cell = h3.latlng_to_cell(lat, lon, 8)
    mid = h3.cell_to_latlng(cell)
    from_mid = lambda s: osm.km(mid[0], mid[1], s["lat"], s["lon"])  # noqa: E731
    # ties by name then point, as routes.py ranks them: never by the house-nearest order near_all comes in
    mid_key = lambda s: (from_mid(s), str(s.get("name") or ""), s["lat"], s["lon"])  # noqa: E731
    links = []
    for lk in g.get("links") or []:
        at = (lk.get("at") or "").lower()
        # the link's cable head nearest the cell's middle: its km leaves without a token, from the middle
        ch = min((s for s in near_all if s["kind"] == "cable_head" and (not at or at in s["name"].lower())),
                 key=mid_key, default=None)
        links.append({
            "name": lk["name"], "kind": "link", "fuel": None,
            "fossil": True if (lk.get("fossil_share") or 0) > 0.5 else None,
            "mw": lk.get("rated_mw"), "km": ch["km"] if ch else None,
            "ring": lk.get("ring", "beyond"),
            "lat": ch["lat"] if ch else None, "lon": ch["lon"] if ch else None,
        })
    # R25: the substation nearest the middle of the res-8 cell, over every one on this grid, rides beside the house's.
    # A screen without a token is told that one (routes.py); picked from the house's nearest few it moved with the house
    # wherever substations stand close together. The km readings below are from the middle too, in whole km: they are
    # derived, so /readings, /stats, /series and the energy issue's stack hand them to anyone.
    mid_sub = min((s for s in near_all if s["kind"] == "substation"), key=mid_key, default=None)
    if mid_sub is not None and mid_sub not in subs:
        subs = subs + [mid_sub]
    mid_big = min(big_plants, key=from_mid, default=None)
    cut_sources = [
        {"name": s["name"], "kind": s["kind"], "fuel": s.get("fuel"),
         "fossil": s.get("fossil"), "mw": s.get("mw"), "km": s["km"], "ring": s["ring"],
         "lat": s["lat"], "lon": s["lon"]}
        for s in (subs + plants)
    ] + links
    on_grid = [s for s in raw_sources if grids.inside(s["lat"], s["lon"], g.get("polygon") or [])]
    counts = {"plants": sum(1 for s in on_grid if s["kind"] == "plant"),
              "substations": sum(1 for s in on_grid if s["kind"] in ("substation", "cable_head"))}

    val = m.get("value")
    low = val if is_meas else m.get("low")
    high = val if is_meas else m.get("high")
    bar = _build_bar(raw_sources, g, m)

    body = {
        "grid": g["id"],
        "kind": m.get("kind"),
        "method": method,
        "months": m.get("months"),
        "share": {
            "low": low,
            "high": high,
            "value": val if is_meas else None,
            "now": m.get("now") if is_meas else None,
            "stale": bool(m.get("stale", False)),
            "as_of": m.get("as_of") or now.isoformat(),
        },
        "bar": bar,
        "sources": cut_sources,
        "today": _today(),
        "household": None,
        "attribution": attrs,
        "counts": counts,
        "cells": _cells(raw_sources, lat, lon),
        "cell": cell,           # the res-8 cell the sources were picked for: routes.py names no substation for another
        "computed_at": now.isoformat(),
    }
    out_dir = _out()
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "result.json").write_text(json.dumps(body))

    readings: list[tuple] = []
    if is_meas and val is not None:
        readings.append((now, SID, "fossil_share_pct", round(float(val) * 100.0, 2)))
    if low is not None:
        readings.append((now, SID, "fossil_share_low_pct", round(float(low) * 100.0, 2)))
    if high is not None:
        readings.append((now, SID, "fossil_share_high_pct", round(float(high) * 100.0, 2)))
    if is_meas and m.get("now") is not None:
        readings.append((now, SID, "fossil_share_day_pct", round(float(m["now"]) * 100.0, 2)))
    if mid_sub is not None:
        readings.append((now, SID, "substation_km", float(round(from_mid(mid_sub)))))
    if mid_big is not None:
        readings.append((now, SID, "large_plant_km", float(round(from_mid(mid_big)))))
    imp_max = m.get("beyond") if is_meas else m.get("import_max")
    if imp_max is not None:
        readings.append((now, SID, "import_share_max_pct", round(float(imp_max) * 100.0, 2)))
    if m.get("months") is not None:
        readings.append((now, SID, "grid_months", float(m["months"])))

    sensor = {
        "sensor_id": SID,
        "source": "energy",
        "name": f"Grid mix ({g['name']})",
        "kind": "model",
        "scale": "region",
        "indoor": False,
        "local": False,
        "cadence": "PT1H",
        "lat": lat,
        "lon": lon,
        "meta": {
            "attribution": "; ".join(attrs),
            "grid": g["id"],
            "provenance": m.get("kind"),
            "method": method,
            # REE's terms are non-commercial (ruled 9 Nov 2026): on the page and to the bot, never in the open export
            # (packs.open_sql). Written every time, since sensors.meta merges and a stale key would linger.
            "licence": "non-commercial" if is_meas else "open",
        },
    }
    return [sensor], readings, m


def _home(hc, fossil: float | None, now: datetime) -> tuple[list[dict], list[tuple]]:
    """The house, through its Home Assistant (ha.py), when ENERGY_HA_URL, the token and both entities are set: W every
    poll, and on the first poll after an hour closes, that hour's kWh and, where the grid has one measured fossil
    share (`fossil`), the household's own. Samples wait for their hour in out/energy/ha.json."""
    url, token = os.getenv("ENERGY_HA_URL", "").strip(), os.getenv("ENERGY_HA_TOKEN", "").strip()
    ents = {m: os.getenv(k, "").strip() for k, m in
            (("ENERGY_HA_SOLAR", "home_roof_w"), ("ENERGY_HA_GRID", "home_grid_w"), ("ENERGY_HA_BATTERY", "home_battery_w"))}
    if not (url and token and ents["home_roof_w"] and ents["home_grid_w"]):
        return [], []
    w = {m: ha.state(hc, url, token, e) if e else None for m, e in ents.items()}
    readings: list[tuple] = [(now, HOME, m, v) for m, v in w.items() if v is not None]

    p = _out() / "ha.json"
    try:
        st = json.loads(p.read_text())
    except Exception:
        st = {}
    samples = [(datetime.fromisoformat(t), r, g) for t, r, g in st.get("samples") or []]
    samples.append((now, w["home_roof_w"], w["home_grid_w"]))
    hour = now.replace(minute=0, second=0, microsecond=0)
    done = datetime.fromisoformat(st["done"]) if st.get("done") else None
    pos = lambda v: None if v is None else max(v, 0.0)  # noqa: E731 — power sent out is not power drawn or made here
    for h in sorted({t.replace(minute=0, second=0, microsecond=0) for t, _, _ in samples if t < hour}):
        if done and h <= done:
            continue
        roof = ha.clip([(t, pos(r)) for t, r, _ in samples], h)
        grid = ha.clip([(t, pos(g)) for t, _, g in samples], h)
        roof_kwh = round(ha.kwh(roof), 3) if roof else None
        grid_kwh = round(ha.kwh(grid), 3) if grid else None
        if roof_kwh is not None:
            readings.append((h, HOME, "home_roof_kwh", float(roof_kwh)))
        if grid_kwh is not None:
            readings.append((h, HOME, "home_grid_kwh", float(grid_kwh)))
        if roof_kwh is not None and grid_kwh is not None and fossil is not None:
            sh = ha.share(roof_kwh, grid_kwh, fossil)
            if sh is not None:
                readings.append((h, HOME, "home_fossil_pct", round(sh * 100.0, 2)))
    keep = [s for s in samples if s[0] < hour][-1:] + [s for s in samples if s[0] >= hour]
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"done": (hour - ha.HOUR).isoformat(),
                             "samples": [[t.isoformat(), r, g] for t, r, g in keep]}))
    try:
        lat, lon = float(os.getenv("NODE_LAT", "")), float(os.getenv("NODE_LON", ""))
    except ValueError:
        lat = lon = None
    sensor = {"sensor_id": HOME, "source": "energy", "name": "This house (Home Assistant)", "kind": "sensor",
              "indoor": False, "local": True, "cadence": "PT5M", "lat": lat, "lon": lon,
              "meta": {"via": "Home Assistant REST API"}}
    return [sensor], readings


def fetch(hc) -> tuple[list[dict], list[tuple]]:
    sensors, readings, m = _grid(hc)
    # The house's share uses the grid's one measured figure, the latest full day where there is one (REE), else the
    # trailing year. Bali's is a range, so the house gets its kWh and no share until one figure is published.
    fossil = None
    if m and m.get("kind") == "measured":
        fossil = m["now"] if m.get("now") is not None else m.get("value")
    hs, hr = _home(hc, fossil, datetime.now(timezone.utc))
    return sensors + hs, readings + hr
