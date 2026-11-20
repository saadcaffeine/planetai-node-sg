"""The household's own power, read from its Home Assistant over the REST API. Read only: nothing here switches a device.

`state()` reads one entity in W. `clip()` cuts the 5-minute samples to one hour, `kwh()` integrates them, and
`share()` is the part of the house's use that came from the grid, times the grid's fossil share. A read that failed is
None, and an hour holding one has no line, never a house on 100% grid.
"""
from __future__ import annotations

import math
from datetime import datetime, timedelta

HOUR = timedelta(hours=1)
# ponytail: two missed 5-minute polls (POLL_SECONDS=300) and the hour is not counted. Raise it if a node polls slower.
MAX_GAP = timedelta(minutes=15)
TO_W = {"W": 1.0, "kW": 1000.0, None: 1.0}   # a power entity with no unit is taken as W, as ENERGY_HA_* asks


def state(hc, url: str, token: str, entity: str) -> float | None:
    """GET {url}/api/states/{entity}: the entity's state in W, or None for unavailable, unknown, a non-number, a unit
    that is not power, or any error."""
    try:
        r = hc.get(f"{url.rstrip('/')}/api/states/{entity}", headers={"Authorization": f"Bearer {token}"}, timeout=10)
        if r.status_code != 200:
            return None
        body = r.json()
        v = float(body["state"]) * TO_W[(body.get("attributes") or {}).get("unit_of_measurement")]
        return v if math.isfinite(v) else None
    except Exception:  # noqa: BLE001 — "unavailable", a 401, a timeout, a kWh entity: all the same missing number
        return None


def clip(samples: list[tuple[datetime, float | None]], start: datetime) -> list[tuple[datetime, float]] | None:
    """The samples of the hour from `start`, with each edge read on the line between the polls either side. None when
    a poll failed, two polls are MAX_GAP or more apart, or the polls do not reach both edges."""
    end = start + HOUR
    pts = ([s for s in samples if s[0] < start][-1:] + [s for s in samples if start <= s[0] <= end]
           + [s for s in samples if s[0] > end][:1])
    if not pts or pts[0][0] > start or pts[-1][0] < end or any(w is None for _, w in pts):
        return None
    if any(b[0] - a[0] >= MAX_GAP for a, b in zip(pts, pts[1:])):
        return None

    def at(a, b, t):
        return a[1] + (b[1] - a[1]) * ((t - a[0]) / (b[0] - a[0]))
    if pts[0][0] < start:
        pts[0] = (start, at(pts[0], pts[1], start))
    if pts[-1][0] > end:
        pts[-1] = (end, at(pts[-2], pts[-1], end))
    return pts


def kwh(samples: list[tuple[datetime, float]]) -> float:
    """Trapezoid over W samples inside one hour, in kWh."""
    return sum((b[0] - a[0]) / HOUR * (a[1] + b[1]) / 2 for a, b in zip(samples, samples[1:])) / 1000.0


def share(roof_kwh: float, grid_kwh: float, grid_fossil: float) -> float | None:
    """The household's fossil share for the hour: what it drew from the grid over what it used, times the grid's
    share. None when it neither made nor drew anything."""
    used = roof_kwh + grid_kwh
    return grid_kwh / used * grid_fossil if used else None
