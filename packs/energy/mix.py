"""Capacity-factor grid mix estimator for grids whose dispatch is not published (e.g. PLN Bali)."""
from __future__ import annotations

import grids


def _cf(cf: dict, fuel: str | None) -> float | None:
    if not fuel:
        return None
    if fuel in cf and cf[fuel] is not None:
        return float(cf[fuel])
    if fuel == "diesel" and cf.get("oil") is not None:
        return float(cf["oil"])
    return None


def estimate(sources: list[dict], g: dict) -> dict:
    """Estimate fossil share range and ring split from OSM plant capacities and fuel capacity factors."""
    poly = g.get("polygon") or []
    cf = g.get("capacity_factors") or {}
    fossil_w = 0.0
    total_w = 0.0
    ring_w = {"city": 0.0, "region": 0.0}

    for s in sources or []:
        if s.get("kind") != "plant":
            continue
        cap = s.get("mw")
        if cap is None or cap <= 0:
            continue
        lat, lon = s.get("lat"), s.get("lon")
        if lat is None or lon is None or not grids.inside(lat, lon, poly):
            continue
        factor = _cf(cf, s.get("fuel"))
        if factor is None or factor <= 0 or s.get("fossil") is None:
            continue
        w = float(cap) * factor
        total_w += w
        if s.get("fossil"):
            fossil_w += w
        ring = grids.ring_for(lat, lon, g)
        ring_w[ring] = ring_w.get(ring, 0.0) + w

    if total_w <= 0:
        return {
            "low": None,
            "high": None,
            "mid": None,
            "island": None,
            "import_max": None,
            "method": "capacity-factors",
            "kind": "estimated",
            "split": {"city": None, "region": None, "beyond": None},
        }

    island = fossil_w / total_w
    links = g.get("links") or []
    demand = g.get("demand_mw")

    import_max: float | None = 0.0
    low: float | None = island
    high: float | None = island
    mid: float | None = island
    if links and any(lk.get("fossil_share") is None for lk in links):
        # The link's own mix is unknown, so it could pull the share anywhere: no figure.
        import_max = low = high = mid = None
    elif links:
        rated = [lk.get("rated_mw") for lk in links]
        known = demand is not None and demand > 0 and all(r is not None for r in rated)
        if known and sum(rated) > 0:
            link_fossil = sum(float(r) * float(lk["fossil_share"]) for r, lk in zip(rated, links)) / sum(rated)
        else:
            link_fossil = sum(float(lk["fossil_share"]) for lk in links) / len(links)
        # Unknown rating: imports can still be no more than all of demand, so the range runs to the link's own share.
        # It is never "at least the island", which is wrong whenever the link is cleaner than the island.
        import_max = min(1.0, sum(rated) / float(demand)) if known else None
        j_hi = import_max if import_max is not None else 1.0
        low, high = sorted((island, (1.0 - j_hi) * island + j_hi * link_fossil))
        mid = (low + high) / 2.0 if import_max is not None else None

    if import_max is None:
        # How much comes over the link is unknown: city and region are shares of what the island makes.
        split = {"city": ring_w["city"] / total_w, "region": ring_w["region"] / total_w, "beyond": None}
    else:
        j_mid = import_max / 2.0
        split = {
            "city": (ring_w["city"] / total_w) * (1.0 - j_mid),
            "region": (ring_w["region"] / total_w) * (1.0 - j_mid),
            "beyond": j_mid,
        }

    return {
        "low": low,
        "high": high,
        "mid": mid,
        "island": island,
        "import_max": import_max,
        "method": "capacity-factors",
        "kind": "estimated",
        "split": split,
    }
