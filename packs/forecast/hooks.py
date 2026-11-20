"""area(cells, bbox): Open-Meteo now and the next 24 h at the selection's centroid (spec 2026-11-10 §2).

One call per selection, cached an hour: Open-Meteo's daily limit is per IP and node #1's own poll already spends most
of it, so never one call per cell. Only with FORECAST_OPENMETEO=1, the operator's yes to its non-commercial free tier;
off, forecast answers nothing. Open-Meteo is sent the centroid and nothing else.
"""
from __future__ import annotations

import importlib.util
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import h3
import httpx

import settings

_spec = importlib.util.spec_from_file_location("planetai_pack_forecast_adapter_for_hooks", Path(__file__).with_name("adapter.py"))
A = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(A)  # type: ignore[union-attr]

HOUR = 3600
AREA_SWITCH = ("FORECAST_OPENMETEO", "1")    # POST /area reads it too, to say "off on this node" rather than "nothing here"
_cache: dict = {}


def area(cells, bbox):
    if settings.get(AREA_SWITCH[0], "0") != AREA_SWITCH[1]:
        return None
    key, now = tuple(sorted(cells)), time.time()
    hit = _cache.get(key)
    if hit and now - hit[0] < HOUR:
        return hit[1]
    pts = [h3.cell_to_latlng(c) for c in key]
    point = {"lat": round(sum(p[0] for p in pts) / len(pts), 5), "lon": round(sum(p[1] for p in pts) / len(pts), 5)}
    try:
        with httpx.Client(timeout=30) as hc:
            d = A._om_points(hc, A.OPEN_METEO, [point], A.OM_HOURLY)[0]
    except (httpx.HTTPError, ValueError) as e:
        return {"pack": "forecast", "error": f"Open-Meteo did not answer ({type(e).__name__})."}
    fetched = datetime.now(timezone.utc)
    rows = [{"ts": ts.isoformat(), "metric": m, "value": v} for ts, _, m, v in A._om_rows(d, "forecast-area", A.OM_MAP, fetched)
            if m != "fc_lead_hours" and ts <= fetched + timedelta(hours=24)]
    out = {"pack": "forecast", "source": "Open-Meteo, open-meteo.com", "licence": "CC-BY 4.0, free tier non-commercial only",
           "rows": rows, "as_of": fetched.isoformat(timespec="seconds")}
    for k in [k for k, v in _cache.items() if now - v[0] >= HOUR]:
        del _cache[k]
    _cache[key] = (now, out)
    return out
