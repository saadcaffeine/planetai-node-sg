"""GET /nearby: the ring of other people's stations around this node, and where this node sits inside it.

A route of this pack since 23 Oct 2026; until then app/main.py, moved unchanged. The node mounts it from here
(app/packs.py::routers) and answers 404 while this pack is off. The stations themselves are whichever pack declares
`stations:` (packs.stations()), Bali Air Dispatch on node #1.
"""
from __future__ import annotations

import httpx
from fastapi import APIRouter

import packs
import settings
from db import q

router = APIRouter()


@router.get("/nearby")
def nearby(audit: bool = False):
    """The ring: other people's stations around this node, and where this node sits inside it.

    `?audit=1` calls the archive and returns a verdict for every station it lists, which is the same answer
    `planetai run nearby stations` prints. Without it this reads only what is already stored, so the dashboard
    never waits on someone else's server.

    A station excluded after it was already stored keeps its row and stops getting readings, so `reporting` goes
    false and it leaves the ring's numbers within two hours on its own. The row is left alone rather than deleted:
    what it measured while it was in the ring was still measured.
    """
    on = [p for p in packs.stations() if p["on"]]
    src = [p["source"] for p in on]
    ring = q("""
        SELECT s.sensor_id, s.name, s.lat, s.lon, s.indoor, s.meta->>'network' AS network,
               round((s.meta->>'km')::numeric, 2) AS km,
               round(st.mean_1h::numeric, 1) AS pm25,
               round(st.silent_minutes::numeric) AS silent_minutes, st.last_ts,
               (st.silent_minutes IS NOT NULL AND st.silent_minutes < 120) AS reporting
        FROM sensors s LEFT JOIN stats st
          ON st.sensor_id = s.sensor_id AND st.metric = 'pm25'
        WHERE s.source = ANY(%s) AND NOT s.local
          -- a station excluded after it was stored keeps its row but stops getting readings. Drop it from the
          -- list after a day rather than leaving it on the card as a neighbour that never answers.
          AND st.last_ts > now() - interval '24 hours'
        ORDER BY (s.meta->>'km')::numeric NULLS LAST""", src)
    shape = q("""
        WITH ring AS (
          SELECT st.mean_1h AS pm,
                 sqrt(power((st.lat - current_setting('planetai.lat')::float) * 111320, 2)
                    + power((st.lon - current_setting('planetai.lon')::float) * 111320
                            * cos(radians(current_setting('planetai.lat')::float)), 2)) / 1000 AS km
          FROM stats st JOIN sensors sn USING (sensor_id)
          WHERE sn.source = ANY(%s) AND NOT st.local AND NOT st.indoor AND st.kind = 'sensor' AND st.metric = 'pm25'
            AND st.mean_1h IS NOT NULL AND st.silent_minutes < 120 AND st.lat IS NOT NULL),
        mine AS (
          SELECT avg(mean_1h) AS pm, count(*) AS n FROM stats
          WHERE local AND NOT indoor AND kind = 'sensor' AND metric = 'pm25'
            AND mean_1h IS NOT NULL AND silent_minutes < 120)
        SELECT (SELECT count(*) FROM ring)                                                        AS stations,
               (SELECT round(min(pm)::numeric, 1) FROM ring)                                      AS lowest,
               (SELECT round(percentile_cont(0.25) WITHIN GROUP (ORDER BY pm)::numeric, 1) FROM ring) AS p25,
               (SELECT round(percentile_cont(0.5)  WITHIN GROUP (ORDER BY pm)::numeric, 1) FROM ring) AS median,
               (SELECT round(percentile_cont(0.75) WITHIN GROUP (ORDER BY pm)::numeric, 1) FROM ring) AS p75,
               (SELECT round(max(pm)::numeric, 1) FROM ring)                                      AS highest,
               (SELECT round(min(km)::numeric, 1) FROM ring)                                      AS nearest_km,
               (SELECT round(pm::numeric, 1) FROM mine)                                           AS mine,
               (SELECT n FROM mine)                                                               AS mine_sensors""", src)
    out = {"ring": ring, **(shape[0] if shape else {}),
           "radius_km": max([float(settings.get(p["radius"], "15") or 15) for p in on if p.get("radius")] or [0.0]),
           "attribution": [w for p in on for w in (p.get("attribution") or [])]
           + (["and the network named in each station's `network` field"] if on else [])}
    m, med = out.get("mine"), out.get("median")
    out["mine_minus_ring"] = None if m is None or med is None else round(float(m) - float(med), 1)
    if audit:
        out["audit"] = []
        try:
            hc = httpx.Client(timeout=30, headers={"user-agent": "planetai-node"})
            for p in on:
                mod = packs.module(p["pack"])
                out["audit"] += mod.audit(hc) if mod and hasattr(mod, "audit") else []
        except Exception as e:  # noqa: BLE001  — a source that is down must not take the endpoint down
            out["audit_error"] = f"{type(e).__name__}: {str(e)[:160]}"
    return out
