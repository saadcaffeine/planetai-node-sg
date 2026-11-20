"""The Place report's reading: what kind of place this is, and what is worth doing here (docs/SPEC_place_report.md §11).

Four things live here, in the order each rests on the one before:

  facts(cur)            every figure the reading may rest on, as one JSON-able document, at the precision of a
                        report that leaves the house: nothing closer than the res-8 cell, no name, no point
  rules(doc)            the node's own reading, deterministic: five sections, at least four avenues, and what it
                        cannot see. This is what every node gets, with no model anywhere
  accept(answer, doc)   a model's fuller text, kept only if its numbers are the node's
  the two routes        GET /place/reading and POST /place/reading, for this machine or a token

The facts are the only place a number may come from, as report.bundle is for the hourly report.
"""
from __future__ import annotations

import json
import logging
import math
import os
import re
import threading
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Header, HTTPException

import cells

log = logging.getLogger("planetai.reading")

# The frame for an avenue (the Fab City Full Stack's seven layers, as "Mapping agents", DRS2026, words them; the
# Implementation Guide's three key actions; the paper's three signals). A text that names anything else is refused.
LAYERS = ("Infrastructure", "Learning", "Value-generating projects", "Communities", "Place-based interventions",
          "Bioregional strategies", "Global networks")
ACTIONS = ("Map and research", "Experiment", "Rethink")
SIGNALS = ("socio-spatial", "bioregional", "asset")
SECTIONS = (("region", "The region it belongs to"), ("land", "What the land allows"), ("needs", "What people here need"),
            ("system", "How the place behaves"), ("street", "The life of the street"))

STALE_DAYS = 400      # a figure older than this counts as not held
# ... except a yearly source, which is stamped 1 July of its last complete year (earth-engine) and would go dark for
# five months of every year, and the terrain, which is computed once: the ground does not move
STALE_OVER = {"tree_share": 800, "crop_share": 800, "upslope_ha": None}
AIR_MIN_DAYS = 30     # measured days before the node states its air figure
WHO_DAY = 15          # µg/m³, the WHO 24-hour guideline for PM2.5 (2021)

# metric in `readings` -> (fact, form). A distance from the node's point becomes whole kilometres here, because the
# report leaves the house (SPEC_place_report §6); the place pack's counts and shares cover 1 km round the point.
READ = {
    "buildings": ("buildings", "n"), "sat_buildings": ("sat_buildings", "n"), "osm_building_coverage": ("osm_coverage", "share"),
    "built_share": ("built_share", "share"), "green_share": ("green_share", "share"), "commercial_share": ("commercial_share", "share"),
    "businesses_per_km2": ("businesses_km2", "n"), "roads_km": ("roads_km", "n"),
    "poi_food": ("poi_food", "n"), "poi_retail": ("poi_retail", "n"), "poi_education": ("poi_education", "n"),
    "poi_health": ("poi_health", "n"), "poi_worship": ("poi_worship", "n"), "poi_lodging": ("poi_lodging", "n"),
    "poi_services": ("poi_services", "n"),
    "nearest_school_m": ("school_km", "km"), "nearest_health_m": ("clinic_km", "km"), "nearest_market_m": ("market_km", "km"),
    "lst_delta": ("heat_delta_c", "d1"), "terrain_upslope_ha": ("upslope_ha", "d1"),
    "tree_frac": ("tree_share", "share"), "crop_frac": ("crop_share", "share"),
}
# the facts that do not come from one reading, and how each is said
FORM = {**{k: f for k, f in READ.values()},
        "place_radius_km": "g",
        "buildings_then": "n", "buildings_then_year": "y", "buildings_now": "n", "buildings_now_year": "y",
        "river_km": "n", "basin_km2": "n", "bioregion_km2": "n", "basin_ends": "s",
        "grid": "s", "fossil_low_pct": "n", "fossil_high_pct": "n",
        "index_place": "s", "index_label": "s", "index_measured": "n", "index_cells": "n",
        "labs_near": "n", "labs_radius_km": "n", "lab_km": "n", "air_days_over": "n", "air_days": "n", "cells_held": "n"}
SHARES = frozenset(k for k, f in FORM.items() if f == "share")
NEAREST = ("school_km", "clinic_km", "market_km")     # written by the place pack only when it finds one within its radius
SAT = ("sat_buildings", "osm_coverage", "buildings_then", "buildings_then_year", "buildings_now", "buildings_now_year")

_PLACE = "turn on the place pack in Set up › Packs"
_SAT = "give the earth-engine pack its key, then planetai run place refresh"
FILL = {**{k: _PLACE for k, _ in READ.values()}, "place_radius_km": _PLACE, **dict.fromkeys(SAT, _SAT),
        "heat_delta_c": "turn on the surface-heat pack in Set up › Packs",
        "upslope_ha": "planetai run terrain fetch",
        "tree_share": "turn on the earth-engine pack in Set up › Packs", "crop_share": "turn on the earth-engine pack in Set up › Packs",
        "river_km": "planetai run hydro fetch", "basin_km2": "planetai run hydro fetch", "bioregion_km2": "planetai run hydro fetch",
        "basin_ends": "planetai run hydro fetch",
        "grid": "planetai run energy fetch", "fossil_low_pct": "planetai run energy fetch", "fossil_high_pct": "planetai run energy fetch",
        "index_place": "planetai place", "index_label": "planetai place", "index_measured": "planetai place", "index_cells": "planetai place",
        "labs_near": "set MAKE_ENABLED=1, then planetai restart", "labs_radius_km": "set MAKE_ENABLED=1, then planetai restart",
        "lab_km": "set MAKE_ENABLED=1, then planetai restart",
        "air_days_over": "an outdoor sensor of your own, measuring for 30 days", "air_days": "an outdoor sensor of your own, measuring for 30 days",
        "cells_held": "planetai update"}
# which pack a fact comes from, for the report's sources page: a held figure owes its pack's credit
PACK_OF = {**{k: "place" for k, _ in READ.values()}, "place_radius_km": "place", **dict.fromkeys(SAT, "place"),
           "heat_delta_c": "surface-heat", "upslope_ha": "terrain", "tree_share": "earth-engine", "crop_share": "earth-engine",
           **dict.fromkeys(("river_km", "basin_km2", "bioregion_km2", "basin_ends"), "hydro"), **dict.fromkeys(("grid", "fossil_low_pct", "fossil_high_pct"), "energy"),
           **dict.fromkeys(("index_place", "index_label", "index_measured", "index_cells"), "index"), **dict.fromkeys(("labs_near", "labs_radius_km", "lab_km"), "make")}


def say(key: str, v) -> str:
    """A fact as text. The rules and the check on a model's numbers both go through here, so they cannot disagree."""
    form = FORM[key]
    if form == "s":
        return str(v)
    if form == "share":
        return f"{round(v * 100)}%"
    if form == "d1":
        return f"{v:.1f}"
    if form == "y":
        return str(int(v))
    if form == "g":
        return f"{v:g}"
    return f"{round(v):,}" if round(v) >= 10000 else str(round(v))


def _d(x) -> dict:
    return x if isinstance(x, dict) else {}


def shape(latest: dict, hydro: dict | None, energy: dict | None, index: dict | None, labs: list | None, air: tuple | None,
          held: int | None, yearly: list, today: date, labs_radius_km: float = 50, radius_m: float = 1000) -> dict:
    """The facts document, from what the node read. Pure: the I/O is facts(), below.

    `latest` is metric -> (value, "YYYY-MM-DD"); `labs` the labs' distances in km, or None with the make pack off;
    `air` (days over, days measured); `yearly` [(year, buildings the satellite counted)]; `radius_m` the radius the
    place pack counts in. A figure the node does not hold is None and named in `fill`."""
    day = today.isoformat()
    F: dict = dict.fromkeys(FORM)

    def put(key, v, at=day):
        age = STALE_OVER.get(key, STALE_DAYS)
        if v is None or (age is not None and at < (today - timedelta(days=age)).isoformat()):
            return
        form = FORM[key]
        if form == "share" and not 0 <= float(v) <= 1:        # an unclipped polygon sum (green over green) is not a share
            return
        F[key] = {"v": str(v) if form == "s" else round(float(v), 3) if form in ("share", "g") else round(float(v), 1) if form == "d1"
                  else int(round(float(v))), "at": at[:10]}   # "n", "km" and "y" are whole numbers

    ran = latest["buildings"][1] if "buildings" in latest else None      # the place pack's last run
    for metric, (key, form) in READ.items():
        if metric in latest:
            v, at = latest[metric]
            # the pack writes a nearest_* only when it finds one: a distance from an older run outlives the run that
            # found none (node #1: a clinic at 948 m on 6 Sep, none on 14 Nov), so it is not held
            if key in NEAREST and ran and at[:10] < ran[:10]:
                continue
            put(key, v / 1000.0 if form == "km" else v, at)
    if F["buildings"]:
        put("place_radius_km", radius_m / 1000.0)
    years = sorted((int(y), float(n)) for y, n in yearly or [])
    # The yearly series and the footprints count the same circle. A last year several times off the footprints is the
    # band misread (packs/place/satellite.py says so), and is not held: node #1 read 128 a year beside 5994 footprints.
    sat = F["sat_buildings"]
    if len(years) >= 3 and (not sat or sat["v"] / 3 <= years[-1][1] <= sat["v"] * 3):   # history: its last year is said, never passed off as today
        put("buildings_then", years[0][1]); put("buildings_then_year", years[0][0])
        put("buildings_now", years[-1][1]); put("buildings_now_year", years[-1][0])
    h, b = _d(hydro), _d(_d(hydro).get("basin"))
    if _d(h.get("nearest")).get("dist_m") is not None:
        put("river_km", h["nearest"]["dist_m"] / 1000.0)
    put("basin_km2", _d(b.get("level12")).get("up_area"))
    put("bioregion_km2", _d(b.get("level4")).get("sub_area"))
    if F["basin_km2"] and _d(b.get("level12")).get("endo") is not None:
        put("basin_ends", "the sea" if not b["level12"]["endo"] else "a closed basin")
    e, sh = _d(energy), _d(_d(energy).get("share"))
    if e.get("grid") and sh.get("low") is not None and sh.get("high") is not None:   # the low end down, the high end up: never "at least 85%" for 84.6
        put("grid", str(e["grid"]).replace("-", " ").title()); put("fossil_low_pct", math.floor(sh["low"] * 100 + 1e-9)); put("fossil_high_pct", math.ceil(sh["high"] * 100 - 1e-9))
    i, sc = _d(index), _d(_d(index).get("score"))
    if _d(i.get("read")).get("ok") and _d(i.get("place")).get("name") and sc.get("cells_total"):
        put("index_place", i["place"]["name"]); put("index_label", sc.get("status_label")); put("index_measured", sc.get("cells_measured") or 0)
        put("index_cells", sc["cells_total"])
    if labs is not None:                                                 # the make pack is on: none in its radius is a held zero
        r = min(float(labs_radius_km), 50.0)
        near = sorted(float(k) for k in labs if k is not None and float(k) <= r)
        put("labs_near", len(near)); put("labs_radius_km", r)
        if near:
            put("lab_km", near[0])
    if air and air[1] >= AIR_MIN_DAYS:
        put("air_days_over", air[0]); put("air_days", air[1])
    put("cells_held", held)
    return {"at": day, "facts": F, "fill": {k: FILL[k] for k, v in F.items() if v is None}}


def credits(doc: dict, manifests: list) -> list[str]:
    """The credit each held figure owes: the `attribution` of every pack the reading rests on, in the packs' order."""
    packs_held = {PACK_OF[k] for k, f in doc["facts"].items() if f and k in PACK_OF}
    out: list[str] = []
    for m in manifests:
        if m.get("id") in packs_held:
            a = m.get("attribution")
            out += [str(x) for x in (a if isinstance(a, list) else [a]) if x and str(x) not in out]
    return out


# ---------------------------------------------------------------- the rules: the node's own reading
NOTHING = "The node holds nothing yet that speaks to this."
THIN = 0.6            # under this share of the satellite's buildings on the public map, an OpenStreetMap count is said to be thin

# What is missing, said for a person, in the order the gaps become avenues: (what, the facts it covers, an avenue to map
# it). A group is a gap when its first fact is missing. A nearest school, clinic or market that is missing while the
# place pack ran is a finding (none drawn within its radius), not a gap.
GAPS = (
    ("the rivers and basins round this place", ("basin_km2", "river_km", "bioregion_km2", "basin_ends"),
     ("Find where this place's water goes", "Bioregional strategies", "bioregional")),
    ("where the grid's power comes from", ("grid", "fossil_low_pct", "fossil_high_pct"),
     ("Find where the power comes from", "Infrastructure", "asset")),
    ("what stands round it: buildings, roads, shops, green", ("buildings", "place_radius_km", "built_share", "green_share", "commercial_share",
     "businesses_km2", "roads_km", "poi_food", "poi_retail", "poi_education", "poi_health", "poi_worship", "poi_lodging", "poi_services") + NEAREST,
     ("Count what stands here", "Place-based interventions", "socio-spatial")),
    ("this place on the Fab City Index", ("index_place", "index_label", "index_measured", "index_cells"),
     ("Choose this node's place on the Fab City Index", "Global networks", "asset")),
    ("the air outside over a year", ("air_days", "air_days_over"),
     ("Measure the air outside for a month", "Learning", "socio-spatial")),
    ("where rain runs across the ground", ("upslope_ha",), ("See where the rain runs", "Place-based interventions", "bioregional")),
    ("the nearest place to make and fix things", ("labs_near", "labs_radius_km", "lab_km"), ("Look for the nearest place to make and fix", "Infrastructure", "asset")),
    ("what the satellite counts here, year by year", SAT, None),
    ("how hot the ground gets", ("heat_delta_c",), None),
    ("trees and farmed land from the satellite", ("tree_share", "crop_share"), None),
    ("which of its seven cells the node holds", ("cells_held",), None),
)


def rules(doc: dict) -> dict:
    """The node's own reading of its place. Pure: the same facts give the same text.

    Every sentence carries its figure and says no more than the figure does, a rule whose facts are missing does not
    fire, and an avenue that rests on a held figure cites it. Where fewer than four avenues fire, the gaps supply the
    rest as things to map. The words are for any node anywhere: no place's own word for its council, no season."""
    F = doc["facts"]
    v = lambda k: F[k]["v"] if F.get(k) else None            # noqa: E731
    has = lambda *ks: all(F.get(k) is not None for k in ks)  # noqa: E731
    t = lambda k: say(k, v(k))                               # noqa: E731
    near = lambda k: "within a kilometre" if v(k) == 0 else f"about {t(k)} km away"   # noqa: E731
    within = "within a kilometre" if not has("place_radius_km") or v("place_radius_km") == 1 else f"within {t('place_radius_km')} km"
    thin = has("osm_coverage") and v("osm_coverage") < THIN
    osm = lambda text: text[:-1] + ", as far as the public map goes." if thin else text   # noqa: E731
    count = lambda k, one, many: f"{t(k)} {one if v(k) == 1 else many}"   # noqa: E731
    lines: dict = {i: [] for i, _ in SECTIONS}
    found: list = []                                         # (figures it rests on, avenue)
    lab = f"the lab {near('lab_km')}" if has("lab_km") else None

    def avenue(rests, title, why, first, layer, action, signal):
        found.append((len(rests), {"title": title, "why": why, "first_step": first, "layer": layer, "action": action, "signal": signal,
                                   "with": lab if action == "Experiment" else None}))

    # --- the region it belongs to
    if has("basin_km2", "bioregion_km2"):
        ends = f" that ends in {t('basin_ends')}" if has("basin_ends") else ""
        sea = has("basin_ends") and v("basin_ends") == "the sea"
        lines["region"].append(f"Rain that falls here leaves by a basin of {t('basin_km2')} km²{ends}, inside a bioregion of {t('bioregion_km2')} km².")
        avenue(("basin_km2", "bioregion_km2"), "Walk the water from here to the sea, and mark what enters it" if sea else "Walk the water downstream, and mark what enters it",
               f"This place drains through a basin of {t('basin_km2')} km²{ends}. What leaves the ground here goes down it.",
               "Follow the nearest river downstream for a morning with the neighbours, and photograph every drain and outfall on the way.",
               "Bioregional strategies", "Map and research", "bioregional")
    if has("river_km"):
        lines["region"].append("A river runs within a kilometre." if v("river_km") == 0 else f"The nearest river is about {t('river_km')} km away.")
    if has("grid", "fossil_low_pct", "fossil_high_pct"):
        span = f"{t('fossil_low_pct')}%" if v("fossil_low_pct") == v("fossil_high_pct") else f"Between {t('fossil_low_pct')}% and {t('fossil_high_pct')}%"
        lines["region"].append(f"{span} of the electricity here is made by burning fuel, on the {t('grid')} grid.")
        if v("fossil_low_pct") >= 60:
            avenue(("fossil_low_pct", "fossil_high_pct", "grid"), "Count the roofs that could carry panels, then share one array among neighbours",
                   f"At least {t('fossil_low_pct')}% of the power on the {t('grid')} grid is made by burning fuel.",
                   "List ten roofs on the street that face the sun, and ask who would share the cost of one array.",
                   "Infrastructure", "Experiment", "asset")
    if has("index_place", "index_label", "index_measured", "index_cells"):
        lines["region"].append(f"{t('index_place')} is on the Fab City Index as {t('index_label')}, with {t('index_measured')} of {t('index_cells')} cells measured.")
        if v("index_measured") < v("index_cells"):
            avenue(("index_measured", "index_cells"), "Fill one cell of the city's Index from this node",
                   f"{t('index_measured')} of the {t('index_cells')} cells of {t('index_place')} on the Fab City Index {'is' if v('index_measured') == 1 else 'are'} measured. "
                   "A node that measures here can fill another.",
                   f"Open index.fab.city, find a cell of {t('index_place')} with no source, and see whether this node already holds the figure.",
                   "Global networks", "Map and research", "asset")
    if has("lab_km", "labs_near", "labs_radius_km"):
        lines["region"].append(f"The nearest place to make or fix something is {near('lab_km')}, "
                               + (f"the only one within {t('labs_radius_km')} km." if v("labs_near") == 1 else f"one of {t('labs_near')} within {t('labs_radius_km')} km."))
    elif has("labs_near", "labs_radius_km") and v("labs_near") == 0:
        lines["region"].append(f"No fab lab is listed within {t('labs_radius_km')} km.")
        avenue(("labs_near", "labs_radius_km"), "Start a shared bench before a lab", f"No fab lab is listed within {t('labs_radius_km')} km of here.",
               "Put tools and a table in one room, one evening a week, and see who comes.", "Infrastructure", "Experiment", "socio-spatial")

    # --- what the land allows
    if has("green_share", "built_share"):
        lines["land"].append(osm(f"{t('green_share')} of the ground {within} is green, and {t('built_share')} is built on."))
    if has("heat_delta_c"):
        hot = v("heat_delta_c") > 0.5
        lines["land"].append(f"The surface here runs {t('heat_delta_c')} °C hotter than the land around it." if hot
                             else "The surface here is no hotter than the land around it.")
        if hot:
            avenue(("heat_delta_c",) + (("green_share",) if has("green_share") else ()), "Shade and soak the hardest ground",
                   f"The surface runs {t('heat_delta_c')} °C hotter than the land around it" + (f", with {t('green_share')} of the ground green." if has("green_share") else "."),
                   "Pick the hottest stretch of street, and plant or shade twenty metres of it before the next hot season.",
                   "Place-based interventions", "Experiment", "bioregional")
    if has("upslope_ha"):
        if v("upslope_ha") >= 1:
            lines["land"].append(f"Water from {t('upslope_ha')} ha of higher ground passes this point.")
            avenue(("upslope_ha",), "Slow the water where it gathers", f"Rain from {t('upslope_ha')} ha of higher ground runs past this point.",
                   "After the next heavy rain, mark where water stands, and dig one soakaway there.", "Place-based interventions", "Experiment", "bioregional")
        else:
            lines["land"].append(f"Little water arrives from above: {t('upslope_ha')} ha of higher ground drains past this point.")
    if has("tree_share", "crop_share"):
        lines["land"].append(f"{t('tree_share')} of the land is under trees, and {t('crop_share')} is farmed.")
    if has("sat_buildings", "roads_km"):
        lines["land"].append(f"The satellite counts {t('sat_buildings')} buildings {within}, along {t('roads_km')} km of road.")

    # --- what people here need
    if has("air_days_over", "air_days"):
        lines["needs"].append(f"On {t('air_days_over')} of the {t('air_days')} days the node measured, the air outside was over the WHO guideline for a day."
                              if v("air_days_over") else f"On none of the {t('air_days')} days the node measured was the air outside over the WHO guideline for a day.")
        if v("air_days_over") * 10 >= v("air_days"):
            avenue(("air_days_over", "air_days"), "Build sensors with the neighbours, and agree what to do on a bad day",
                   f"The air outside was over the WHO guideline on {t('air_days_over')} of the {t('air_days')} days the node measured.",
                   "Hold one evening to assemble two kits, and write down who closes which window when the figure passes the guideline.",
                   "Learning", "Experiment", "socio-spatial")
    # the place pack looks no further than its radius: a distance when it found one, and a finding when it found none
    for key, poi, what, short in (("clinic_km", "poi_health", "clinic or pharmacy", "clinic"), ("school_km", "poi_education", "school", "school")):
        if has(key):
            lines["needs"].append(osm(f"A {what} is drawn within a kilometre." if v(key) == 0 else f"The nearest {what} drawn is about {t(key)} km away."))
        elif has(poi) and v(poi) == 0:
            lines["needs"].append(osm(f"No {what} is drawn {within}."))
            avenue((poi,) + (("osm_coverage",) if has("osm_coverage") else ()), f"Ask who walks to the {short}, and what would shorten the way",
                   f"The public map shows {t(poi)} {what}s {within}" + (f", and it holds {t('osm_coverage')} of the buildings here." if has("osm_coverage") else "."),
                   "Ask ten households how they get there and what it costs them, and take the answers to the neighbourhood council.", "Communities", "Rethink", "socio-spatial")
    if has("market_km"):
        lines["needs"].append(osm("A market is drawn within a kilometre." if v("market_km") == 0 else f"The nearest market drawn is about {t('market_km')} km away."))
    if has("lab_km", "labs_near", "labs_radius_km"):
        lines["needs"].append(f"What breaks here can be mended {near('lab_km')}.")
        avenue(("lab_km", "labs_near"), "Hold a repair evening", f"A place to make and fix things is {near('lab_km')}, "
               + (f"the only one within {t('labs_radius_km')} km." if v("labs_near") == 1 else f"one of {t('labs_near')} within {t('labs_radius_km')} km."),
               "Bring five broken things to one table, and see which can be mended with what is at hand.", "Learning", "Experiment", "asset")

    # --- how the place behaves
    if has("buildings_then", "buildings_then_year", "buildings_now", "buildings_now_year"):
        up = v("buildings_now") > v("buildings_then")
        lines["system"].append(f"The satellite counted {t('buildings_now')} buildings here in {t('buildings_now_year')}, {'up from' if up else 'against'} "
                               f"{t('buildings_then')} in {t('buildings_then_year')}."
                               + (" More roofs, less soak, more heat: each feeds the next." if up and (has("green_share") or has("heat_delta_c")) else ""))
        if up:
            avenue(("buildings_then", "buildings_then_year", "buildings_now", "buildings_now_year"), "Agree a rule for new ground",
                   f"{t('buildings_then')} buildings in {t('buildings_then_year')}, {t('buildings_now')} in {t('buildings_now_year')}.",
                   "Write one line the neighbourhood council can hold a builder to: what each new roof gives back in shade, or in ground that soaks.",
                   "Bioregional strategies", "Rethink", "bioregional")
    if has("osm_coverage"):
        lines["system"].append(f"{t('osm_coverage')} of the buildings the satellite sees are on the public map." + (" What is not drawn is not planned for." if thin else ""))
        if thin:
            avenue(("osm_coverage",), "Map the missing buildings and paths together", f"Only {t('osm_coverage')} of the buildings the satellite sees are on the public map.",
                   "Spend two hours on openstreetmap.org with a neighbour, and draw the buildings of one street.", "Communities", "Map and research", "asset")
    if has("fossil_low_pct") and v("fossil_low_pct") >= 60:
        lines["system"].append(f"At least {t('fossil_low_pct')}% of the power used here is made by burning fuel, so every hour of use here adds to it.")
    if has("cells_held"):
        lines["system"].append(("The node measures in none of its 7 cells." if v("cells_held") == 0 else f"The node measures in {t('cells_held')} of its 7 cells.")
                               + (" What happens in the others reaches nobody." if v("cells_held") < 7 else ""))
        if v("cells_held") < 3:
            avenue(("cells_held",), "Lend a kit to a neighbour in a cell nobody measures",
                   "The node measures in none of its 7 cells." if v("cells_held") == 0 else f"The node measures in {t('cells_held')} of its 7 cells.",
                   "Open Place at Cell scale, pick an open cell, and ask one household in it to keep a sensor for a month.", "Communities", "Experiment", "asset")

    # --- the life of the street
    kinds = [(k, one, many) for k, one, many in (("poi_food", "to eat", "to eat"), ("poi_lodging", "to stay", "to stay"), ("poi_retail", "shop", "shops"),
                                                 ("poi_services", "service", "services"), ("poi_education", "school", "schools"),
                                                 ("poi_health", "clinic or pharmacy", "clinics or pharmacies"), ("poi_worship", "place of worship", "places of worship")) if has(k)]
    if kinds:
        drawn = [(k, one, many) for k, one, many in kinds if v(k) > 0]
        if drawn:
            lines["street"].append(osm(f"{len(drawn)} kind{'s' if len(drawn) > 1 else ''} of place {'are' if len(drawn) > 1 else 'is'} drawn {within}: "
                                       + ", ".join(count(*d) for d in drawn) + "."))
        else:
            lines["street"].append(osm(f"No shop, café or service is drawn {within}."))
        if has("poi_lodging", "poi_retail", "poi_services") and v("poi_lodging") > 0 and v("poi_lodging") >= v("poi_retail") + v("poi_services"):
            lines["street"].append("More places house visitors than sell what a household needs from day to day.")
            avenue(("poi_lodging", "poi_retail", "poi_services"), "Give one ground floor a second use that serves the people who live here",
                   f"{count('poi_lodging', 'place', 'places')} to stay {within}, against {count('poi_retail', 'shop', 'shops')} and {count('poi_services', 'service', 'services')}.",
                   "Find one ground floor that is closed most of the day, and ask its owner for two mornings a week.",
                   "Value-generating projects", "Experiment", "socio-spatial")
    if has("businesses_km2", "roads_km"):
        lines["street"].append(osm(f"{t('businesses_km2')} businesses a square kilometre, along {t('roads_km')} km of road."))
        if v("businesses_km2") < 10:
            avenue(("businesses_km2", "roads_km"), "Open one shared space for a season, and see who comes",
                   f"{t('businesses_km2')} businesses a square kilometre along {t('roads_km')} km of road leave few places to meet by chance.",
                   "Ask the neighbourhood council for one unused ground floor or yard for three months, with a table, shade and a notice board.",
                   "Place-based interventions", "Experiment", "socio-spatial")
    if has("commercial_share"):
        lines["street"].append(osm(f"{t('commercial_share')} of the buildings are shops or workplaces." if v("commercial_share") > 0
                                   else f"No building {within} is drawn as a shop or a workplace."))

    blind = [{"what": what, "command": FILL[keys[0]], "facts": [k for k in keys if F.get(k) is None]} for what, keys, _ in GAPS if F.get(keys[0]) is None]
    avenues = [a for _, a in sorted(found, key=lambda x: -x[0])][:6]         # sorted is stable: the order above breaks a tie
    for what, keys, gap in GAPS:
        if len(avenues) >= 4:
            break
        if gap and F.get(keys[0]) is None:
            avenues.append({"title": gap[0], "why": f"The node does not hold {what} yet.", "first_step": f"On the node: {FILL[keys[0]]}. Then open Place again.",
                            "layer": gap[1], "action": "Map and research", "signal": gap[2], "with": None})
    return {"sections": [{"id": i, "heading": h, "lines": lines[i] or [NOTHING]} for i, h in SECTIONS], "avenues": avenues, "blind": blind}


# ---------------------------------------------------------------- the fuller text: a model's, kept only if it holds
# The manner each section is read in. The names steer the model and stop here: a text that carries one is refused,
# and no page, button, doc or answer of the node says them (Tomas, 17 Nov 2026: "do not mention the names of experts").
MANNER = (("region", "the region as the unit, its limits and its balance, the way Lewis Mumford read a city in its region"),
          ("land", "what the land is fit for against what it is used for, as Ian McHarg would lay it out"),
          ("needs", "real needs before wants, met with local means, as Victor Papanek asked of design"),
          ("system", "stocks, flows, loops and delays, and where a small push counts, as Donella Meadows would trace them"),
          ("street", "the mix of uses, short blocks and eyes on the street, as Jane Jacobs watched them"))
# Three of the names are no other word. The last two are (a water meadow), so those count only with their capital.
PERSON = re.compile(r"(?i:mumford|mcharg|papanek)|\b(?:Meadows|MEADOWS|Jacobs|JACOBS)\b")
UNITS = re.compile(r"\b(?:PM2\.5|PM10|PM1|CO2|NO2|O3)\b", re.I)    # a unit's own digits are not a figure
COUNTS = frozenset(range(1, 8))                                    # "2 of its 7 cells", "4 avenues": a bare count, never a measure
# what turns a number into a measurement. A small count before one of these is a figure the node must hold
MEASURE = re.compile(r"\s*(?:%|°|º|percent\b|per cent\b|km|ha\b|m\b|m²|µg|kWh?\b|MW\b|mm\b|cm\b|degrees?\b|times\b|fold\b)", re.I)
# a quantity in words is a number the check cannot read: the model is asked for digits, and these are refused
QUANTITY = re.compile(r"\b(?:half|halves|thirds?|quarters?|fifths?|tenths?|twice|thrice|doubl\w+|tripl\w+|dozens?|hundreds?|thousands?|millions?)\b", re.I)
# A report page is one A4 sheet and does not grow in print, so each part of a model's text has a ceiling, in characters
# (measured in print: five sections of 800 keep the first page whole, five of 900 overrun it)
LONGEST = {"section": 780, "title": 100, "why": 300, "first_step": 220}


def prompt(doc: dict, ruled: dict) -> str:
    """What the model is handed: the frame, the manner, the facts, the node's own reading, and the shape to answer in."""
    head = dict(SECTIONS)
    held = {k: f["v"] for k, f in doc["facts"].items() if f}
    return (
        "You are writing two pages of a report about one place, for the people who live there and for whoever they hand it to: "
        "neighbours, a village council, a funder. Read the place five ways, one paragraph each, in this order:\n"
        + "".join(f"- {i} · {head[i]}: {how}.\n" for i, how in MANNER)
        + "Write in their manner and name no person: not them, not anyone. Plain words, no headings, no lists, 60 to 120 words a section "
        f"({LONGEST['section']} characters at most). "
        "THE NODE'S OWN READING below is the findings, one line each, and the reader already has it. Do not give its sentences back. "
        "Say in sentences of your own what the findings mean taken together for the people here: what follows from them, "
        "what they hold back and what they make possible.\n"
        "Use only numbers that are in FACTS, written in digits as THE NODE'S OWN READING writes them. No dates, no coordinates, no other figure, "
        "and no quantity in words: never 'half', 'a third', 'twice' or 'double'. "
        "Work nothing out from the figures: no sum, no difference, no remainder of a share.\n"
        "A count or a share that comes from the public map covers one kilometre round the place, never 'this cell'. "
        "A cell of the Fab City Index is one entry in a city's table of scores, not a piece of land.\n"
        "Claim nothing the findings do not support, and give no cause they do not give. Where the manner asks about something "
        "the node holds no figure for, say that it is not known here.\n\n"
        "Then give four to six ways to improve the place. You may keep, sharpen or replace the node's own. Each has:\n"
        f"- title: a plain imperative, {LONGEST['title']} characters at most;\n- why: one or two sentences with the figures it rests on, {LONGEST['why']} characters at most;\n"
        f"- first_step: something a household, a village council or a lab can start this month, {LONGEST['first_step']} characters at most;\n"
        f"- layer: one of {json.dumps(LAYERS)};\n- action: one of {json.dumps(ACTIONS)};\n- signal: one of {json.dumps(SIGNALS)}.\n\n"
        'Answer with JSON only: {"sections": {"region": "...", "land": "...", "needs": "...", "system": "...", "street": "..."}, '
        '"avenues": [{"title": "...", "why": "...", "first_step": "...", "layer": "...", "action": "...", "signal": "..."}]}\n\n'
        f"FACTS\n{json.dumps(held, ensure_ascii=False)}\n\nTHE NODE'S OWN READING\n"
        # as findings, never in the shape of the answer: handed that, the model gave it back (node #1, 18 Nov 2026)
        + "".join(f"{s['id']}:\n" + "".join(f"- {line}\n" for line in s["lines"]) for s in ruled["sections"])
        + "its ways to improve the place:\n"
        + json.dumps([{k: a[k] for k in ("title", "why", "first_step", "layer", "action", "signal")} for a in ruled["avenues"]], ensure_ascii=False))


def stray_numbers(text: str, doc: dict) -> list[str]:
    """The numbers in `text` that are not the node's. A share may be said as a percentage or as a fraction, and a
    negative figure without its sign ("1.2 °C cooler"). A count from one to seven passes bare ("2 of its 7 cells") and
    never before a unit: "5 °C" is a measurement, and the node must hold it. The WHO guideline passes before µg.

    This checks that a number is the node's, not that it is said of the right thing: that ceiling is the page's line
    saying a model wrote it."""
    allowed: set = set()
    for k, f in doc["facts"].items():
        if not f or FORM[k] == "s":
            continue
        v = f["v"]
        allowed.add(abs(float(say(k, v).replace(",", "").rstrip("%"))))
        if k in SHARES:
            allowed.update((round(v, 2), round(v, 3), round(v * 100, 1)))
    text = re.sub(r"(?<=\d),(?=\d{3}(?!\d))", "", UNITS.sub("", text))
    stray = []
    for m in re.finditer(r"\d+(?:\.\d+)?", text):
        n, after = float(m.group()), text[m.end():m.end() + 12]
        if n in allowed or (n in COUNTS and "." not in m.group() and not MEASURE.match(after)) or (n == WHO_DAY and re.match(r"\s*µg", after)):
            continue
        stray.append(m.group())
    return stray


def accept(answer: str, doc: dict, ruled: dict | None = None) -> tuple[dict | None, str]:
    """A model's answer, as (written, "") when it holds and (None, why) when it does not. Never raises. `ruled` is
    the node's own reading: a section that gives most of its sentences back is a copy, and is refused."""
    # a model may think aloud first and add a word after: the answer is the first JSON object that holds `sections`
    got, text = None, re.sub(r"<think>.*?</think>", "", answer, flags=re.S) if isinstance(answer, str) else ""
    for m in re.finditer(r"\{", text):
        try:
            obj = json.JSONDecoder().raw_decode(text, m.start())[0]
        except ValueError:
            continue
        if isinstance(obj, dict) and "sections" in obj:
            got = obj
            break
    if got is None:
        return None, "not the JSON it was asked for"
    sec, av = got.get("sections"), got.get("avenues")
    ids = [i for i, _ in SECTIONS]
    if not isinstance(sec, dict) or sorted(sec) != sorted(ids):
        return None, f"sections: the five of the frame were asked for, and it gave {sorted(sec) if isinstance(sec, dict) else 'none'}"
    for i in ids:
        if not isinstance(sec[i], str) or not sec[i].strip():
            return None, f"section {i} is empty"
        if len(sec[i].strip()) > LONGEST["section"]:
            return None, f"section {i} is too long for its page ({len(sec[i].strip())} characters, {LONGEST['section']} at most)"
    for s in (ruled or {}).get("sections", ()):       # node #1, 18 Nov 2026: handed the node's reading, the model gave it back
        if s["lines"] != [NOTHING] and 2 * sum(line in sec[s["id"]] for line in s["lines"]) > len(s["lines"]):
            return None, f"section {s['id']} gives the node's own sentences back"
    if not isinstance(av, list) or not 4 <= len(av) <= 6:
        return None, f"avenues: four to six were asked for, and it gave {len(av) if isinstance(av, list) else 'none'}"
    out = []
    for n, a in enumerate(av, 1):
        if not isinstance(a, dict) or not all(isinstance(a.get(k), str) and a[k].strip() for k in ("title", "why", "first_step")):
            return None, f"avenue {n} lacks its title, its why or its first step"
        for key in ("title", "why", "first_step"):
            if len(a[key].strip()) > LONGEST[key]:
                return None, f"avenue {n}: its {key.replace('_', ' ')} is too long for the page ({len(a[key].strip())} characters, {LONGEST[key]} at most)"
        if not re.search(r"\d", a["why"]):          # an avenue that could be about anywhere: it must rest on a figure of this place
            return None, f"avenue {n} rests on no figure of this place"
        framed = {}
        for key, frame in (("layer", LAYERS), ("action", ACTIONS), ("signal", SIGNALS)):
            framed[key] = next((f for f in frame if f.lower() == str(a.get(key)).strip().lower()), None)   # a model's capitals are not the frame's
            if framed[key] is None:
                return None, f"avenue {n}: its {key} is not one of the frame's ({str(a.get(key))[:40]!r})"
        out.append({**{k: a[k].strip() for k in ("title", "why", "first_step")}, **framed, "with": None})
    text = "\n".join([sec[i] for i in ids] + [f"{a['title']} {a['why']} {a['first_step']}" for a in out])
    if PERSON.search(text):
        return None, "it names a person"
    words = QUANTITY.search(text)
    if words:
        return None, f"a quantity in words ('{words.group().lower()}'), which the node cannot check"
    stray = stray_numbers(text, doc)
    if stray:
        return None, "numbers the node does not hold: " + ", ".join(dict.fromkeys(stray))
    return {"sections": {i: sec[i].strip() for i in ids}, "avenues": out}, ""


SENSORS = ("place-point", "ee-point", "surface-cell", "terrain-point")   # the place-scale sensors the latest figures come from


def _held(cur) -> tuple:
    """What the packs and the cells hold, read in process: (hydro, energy, the Index place, held cells). A pack that is
    off gives None, which is a gap. A read that fails is logged and gives None too, so one pack cannot stop the page."""
    import packs  # noqa: PLC0415 — the loader reads PACKS_DIR at import

    def read(what, fn):
        try:
            return fn()
        except Exception as e:  # noqa: BLE001
            log.warning("reading: %s did not answer (%s)", what, type(e).__name__)
            return None

    def of(pack, name, call):
        m = packs.module(pack, name)
        return read(pack, lambda: getattr(m, call)()) if m else None

    return (of("hydro", "adapter", "result"), of("energy", "adapter", "result"), of("index", "routes", "index_place"),
            read("cells", lambda: cells._body(cur, cells._home())["held"]))


def facts(cur, held=None, today: date | None = None) -> dict:
    """Every figure the reading may rest on. `cur` is a dict-row cursor; `held` reads the packs and the cells (_held)."""
    import packs  # noqa: PLC0415

    pub = packs.public_sql("r")
    # the place-scale sensors only (a wild pack or POST /readings cannot supply a figure), and never a row dated ahead
    cur.execute(f"SELECT DISTINCT ON (r.metric) r.metric, r.value, r.ts FROM readings r WHERE r.sensor_id = ANY(%s) AND r.metric = ANY(%s) "
                f"AND r.ts <= now() AND {pub} ORDER BY r.metric, r.ts DESC", (list(SENSORS), list(READ)))
    latest = {r["metric"]: (r["value"], r["ts"].date().isoformat()) for r in cur.fetchall()}
    cur.execute(f"SELECT r.ts, r.value FROM readings r WHERE r.sensor_id = 'place-point' AND r.metric = 'sat_buildings_yearly' AND {pub} ORDER BY r.ts")
    yearly = [(r["ts"].year, r["value"]) for r in cur.fetchall()]
    # the make pack keeps the labs inside its radius as facility rows: on with none there is a finding, off is a gap
    labs, make = None, packs.module("make")
    if make and make.enabled():          # MAKE_ENABLED=0 is the pack's own off: it holds no lab and has looked for none
        cur.execute("SELECT (meta->>'distance_km')::float AS km FROM sensors WHERE kind = 'facility' AND meta ? 'distance_km'")
        labs = [r["km"] for r in cur.fetchall()]
    # days on which this node's own outdoor sensors gave 18 hourly means or more, and how many of them were over the guideline
    cur.execute(f"""SELECT count(*) FILTER (WHERE m > %s) AS over, count(*) AS days FROM (
                      SELECT avg(r.mean) AS m FROM readings_1h r JOIN sensors s ON s.sensor_id = r.sensor_id
                      WHERE r.metric = 'pm25' AND r.bucket > now() - interval '365 days' AND r.bucket <= now()
                        AND s.local AND NOT s.indoor AND s.kind = 'sensor' AND {pub}
                      GROUP BY date_trunc('day', r.bucket) HAVING count(DISTINCT r.bucket) >= 18) d""", (WHO_DAY,))
    a = cur.fetchone() or {}
    hydro, energy, index, cells_held = (held or _held)(cur)
    return shape(latest, hydro, energy, index, labs, (a.get("over") or 0, a.get("days") or 0), cells_held, yearly, today or date.today(),
                 labs_radius_km=float(os.getenv("MAKE_RADIUS_KM", "50") or 50), radius_m=float(os.getenv("PLACE_RADIUS_M", "1000") or 1000))


# ---------------------------------------------------------------- the routes: GET and POST /place/reading
# The household's alone at every SHARE_LEVEL, as /place/cells and /hydro are: on no allowlist in app/auth.py, so this
# machine or a token. One facts document for one kind of reader keeps a model's text safe to show to all of them.
# Reading it takes the admin or the act token; asking a model for the fuller text takes the admin token.
NO_MODEL = "No model on this house's network can write this. The reading above is the node's own."
WRITING_MAX = timedelta(minutes=10)     # a `writing` row older than this failed: a restart must not leave the button stuck
router = APIRouter(dependencies=[Depends(cells._household)])
_lock = threading.Lock()


def _db():
    from db import db  # noqa: PLC0415 — db.py needs DATABASE_URL at import
    return db()


def _rungs() -> list:
    import ask  # noqa: PLC0415 — the same ladder and AGENT_PREFER the pane reads
    return ask.rungs()


def _spawn(fn, *args) -> None:
    threading.Thread(target=fn, args=args, daemon=True, name="place-reading").start()


def pick(rungs: list):
    """The model that may write: the first that is neither small nor off the house's network, whatever AGENT_PREFER
    lets the pane use. The facts stay at home. The local rung is always `small` in the ladder today, so a node whose
    only strong model is its local one has no writer yet."""
    return next((r for r in rungs if not r.small and not r.leaves), None)


def _ask(rung, system: str) -> str:
    """One answer from one rung, with ten minutes to give it. No tools, so chat() runs it without thinking."""
    import asyncio  # noqa: PLC0415
    import httpx  # noqa: PLC0415
    import agent_loop  # noqa: PLC0415

    async def go():
        async with httpx.AsyncClient(timeout=WRITING_MAX.total_seconds()) as hc:
            m = await agent_loop.chat(hc, rung, [{"role": "system", "content": system}, {"role": "user", "content": "Write the reading."}], None, final=True)
            return m.get("content") or ""
    return asyncio.run(go())


def write(rid: int, rung, doc: dict, ruled: dict) -> None:
    """Ask the model, check what it wrote, and keep it or the reason it was refused. Runs off the request."""
    from psycopg.types.json import Jsonb  # noqa: PLC0415
    try:
        ask = prompt(doc, ruled)
        written, why = accept(_ask(rung, ask), doc, ruled)
        if written is None:      # told why, it writes once more: on node #1 half of the first answers tripped on 'half' or a figure the model worked out
            written, why = accept(_ask(rung, f"{ask}\n\nYour last answer was refused: {why}. Write it again, and keep clear of that."), doc, ruled)
    except Exception as e:  # noqa: BLE001 — whatever went wrong, the row must leave `writing`
        written, why = None, f"the model did not answer ({type(e).__name__})"
    log.info("reading %d: %s", rid, "written" if written else f"refused, {why}")
    with _db() as con, con.transaction(), con.cursor() as cur:
        cur.execute("UPDATE place_readings SET state = %s, text = %s, refused = %s WHERE id = %s",
                    ("written" if written else "refused", Jsonb(written) if written else None, why or None, rid))


def _rows(cur) -> list:
    cur.execute("SELECT id, ts, state, model, wherefrom, text, refused FROM place_readings ORDER BY id DESC LIMIT 20")
    return list(cur.fetchall())


def _stale(row) -> bool:
    return row["state"] == "writing" and datetime.now(timezone.utc) - row["ts"] > WRITING_MAX


@router.get("/place/reading")
def place_reading(authorization: str = Header("")):
    """The node's own reading of its place, the fuller text if a model wrote one that held, and whether this caller
    may ask for one."""
    import packs  # noqa: PLC0415
    from auth import _bearer_ok  # noqa: PLC0415
    with _db() as con, con.transaction(), con.cursor() as cur:
        doc = facts(cur)
        rows = _rows(cur)
    last = rows[0] if rows else None
    kept = next((r for r in rows if r["state"] == "written"), None)
    state, refused = (("refused", "took too long") if _stale(last) else (last["state"], last["refused"])) if last else ("none", None)
    return {"facts_at": doc["at"], "rules": rules(doc), "written": kept["text"] if kept else None,
            "written_at": kept["ts"].isoformat() if kept else None, "by": {"model": kept["model"], "where": kept["wherefrom"]} if kept else "node",
            "state": state, "refused": refused, "credits": credits(doc, packs.manifests()),
            "can_write": _bearer_ok(authorization, os.getenv("ADMIN_TOKEN", "").strip()) and pick(_rungs()) is not None}


@router.post("/place/reading", status_code=202)
def write_reading(authorization: str = Header("")):
    """Ask a model on the house's network for the fuller text. 202 at once; GET says when it is written or refused."""
    from psycopg.types.json import Jsonb  # noqa: PLC0415
    import agent_loop  # noqa: PLC0415
    from auth import _admin  # noqa: PLC0415
    _admin(authorization)
    rung = pick(_rungs())
    if rung is None:
        raise HTTPException(409, NO_MODEL)
    with _lock, _db() as con, con.transaction(), con.cursor() as cur:      # one writing at a time: a second press joins the first
        rows = _rows(cur)
        if rows and rows[0]["state"] == "writing" and not _stale(rows[0]):
            return {"state": "writing", "id": rows[0]["id"]}
        doc = facts(cur)
        cur.execute("INSERT INTO place_readings (state, rung, model, wherefrom, facts) VALUES ('writing', %s, %s, %s, %s) RETURNING id",
                    (rung.name, rung.model, agent_loop.where_of(rung)["where"], Jsonb(doc)))
        rid = cur.fetchone()["id"]
    _spawn(write, rid, rung, doc, rules(doc))
    return {"state": "writing", "id": rid}
