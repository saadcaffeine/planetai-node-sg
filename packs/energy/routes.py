"""GET /energy: the grid behind this node's cells, its fossil share, its sources and today's sun.

Mounted from here by app/packs.py::routers() and answered 404 while the energy pack is off. Reads the latest
out/energy/result.json from adapter.result(), cuts `sources` to the nearest substation, every plant >= 1 MW and each
link, and serves `household` only through _shows_private (the admin token, never an agent). Each source's point and
the node's seven cells (the Place map's energy row) go only to the household's own tokens, admin or act. Anyone else
gets every km from the middle of the res-8 cell /health names, as /wall does, and the substation nearest that middle:
a name with its km from the house, beside /wall's points at 3 dp, placed the house inside its cell from three plants.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

from fastapi import APIRouter, Header, Request

import db
import wall
from auth import _shows_private

router = APIRouter()

_spec = importlib.util.spec_from_file_location("planetai_pack_energy_adapter_for_routes", Path(__file__).with_name("adapter.py"))
adapter = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(adapter)  # type: ignore[union-attr]


def _cut_sources(sources: list[dict], points: bool = False, centre: tuple[float, float] | None = None,
                 same_cell: bool = True) -> list[dict]:
    """`sources` cut to the nearest substation, every plant >= 1 MW and each link. With `points` (the household),
    as the pack measured them from the house. Without, ranked by the unrounded km from the cell's middle, ties by
    name then point, so the order does not follow the pack's house-nearest one, and only then each km made whole;
    no substation at all when the result was computed for another cell (`same_cell`), whose nearest few it holds."""
    items = [s for s in (sources or []) if isinstance(s, dict)]
    if not points:     # every km again from the cell's middle, whole only once ranked; none with no point or no place
        items = [dict(s, km=wall.dist_km(centre, s["lon"], s["lat"])
                      if centre and s.get("lat") is not None and s.get("lon") is not None else None) for s in items]
    km_key = lambda s: (float(s["km"]) if s.get("km") is not None else float("inf"),) + \
        (() if points else (str(s.get("name") or ""), s.get("lat") or 0, s.get("lon") or 0))  # noqa: E731
    subs = sorted([s for s in items if s.get("kind") == "substation" and (points or same_cell)], key=km_key)[:1]
    plants = sorted([s for s in items if s.get("kind") == "plant" and (s.get("mw") or 0) >= 1.0], key=km_key)
    links = [s for s in items if s.get("kind") == "link"]
    out: list[dict] = []
    for s in subs + plants + links:
        row = {
            "name": s.get("name"),
            "kind": s.get("kind"),
            "fuel": s.get("fuel"),
            "mw": s.get("mw"),
            "km": s.get("km") if points or s.get("km") is None else round(s["km"]),
            "ring": s.get("ring"),
        }
        if "fossil" in s:
            row["fossil"] = s.get("fossil")
        if points:
            row["lat"], row["lon"] = s.get("lat"), s.get("lon")
        out.append(row)
    return out


def _ha_household() -> dict | None:
    try:
        rows = db.q(
            "SELECT metric, value FROM readings WHERE sensor_id = 'energy-home' "
            "AND ts > now() - interval '24 hours' ORDER BY ts DESC"
        )
    except Exception:
        return None
    if not rows:
        return None
    latest: dict[str, float] = {}
    for r in rows:
        m = r.get("metric")
        v = r.get("value")
        if m and v is not None and m not in latest:
            latest[m] = float(v)
    if not latest:
        return None
    return {
        "roof_w": latest.get("home_roof_w"),
        "grid_w": latest.get("home_grid_w"),
        "battery_w": latest.get("home_battery_w"),
        "roof_kwh": latest.get("home_roof_kwh"),
        "grid_kwh": latest.get("home_grid_kwh"),
        "fossil_pct": latest.get("home_fossil_pct"),
    }


@router.get("/energy")
def energy(request: Request, authorization: str = Header("")):
    raw = adapter.result() or {}
    share = raw.get("share") if isinstance(raw.get("share"), dict) else {}
    today = raw.get("today") if isinstance(raw.get("today"), dict) else {}
    household = (raw.get("household") or _ha_household()) if _shows_private(request, authorization) else None
    # The Place map's points and the seven cells go to the household's own screen only, as /geo/* do: /energy is on the
    # SHARE_LEVEL=open list, and a plant's point beside its km from the node gives the node's point away.
    mine = _shows_private(request, authorization, raw=False)
    return {
        "grid": raw.get("grid"),
        "kind": raw.get("kind"),
        "method": raw.get("method"),
        "months": raw.get("months"),
        "share": {
            "low": share.get("low"),
            "high": share.get("high"),
            "value": share.get("value"),
            "now": share.get("now"),
            "stale": bool(share.get("stale", False)),
            "as_of": share.get("as_of"),
        },
        "bar": list(raw.get("bar") or []),
        "sources": _cut_sources(raw.get("sources") or [], points=mine, centre=None if mine else wall.cell_centre(),
                                same_cell=raw.get("cell") == wall.home_cell()),
        "today": {
            "sun_kwh_m2": today.get("sun_kwh_m2"),
            "roof_kwh": today.get("roof_kwh"),
            "use_kwh": today.get("use_kwh"),
            "measured": bool(today.get("measured", False)),
            "panel_kw": today.get("panel_kw"),
        },
        "household": household,
        "attribution": list(raw.get("attribution") or []),
        "counts": raw.get("counts"),
        "cells": raw.get("cells") if mine else None,
    }
