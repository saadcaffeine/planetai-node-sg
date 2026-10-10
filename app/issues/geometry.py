"""The H3 geometry this node publishes: the shapes the dashboard navigates by, computed here so the page never has to.

The node already has h3 (app/ground.py, the presence announce). Nothing here is a capability it gains — only a
shape it publishes. Every function is pure: coordinates, settings and station rows in; JSON-ready dicts out. The
same functions answer for live data and for a fixture replayed at the hour it was captured.

Design provenance: planetai-design/prototypes/dashboard-directions/make-h3.mjs, which computed these for the
Phase 1 drawings with h3-js and checked them against h3geo.org's resolution table and the design repo's
kilometre-cells.json. This is the Python of the same arithmetic; tests/test_issues_geometry.py keeps the two
agreeing.

One vocabulary note. A *distance* — room, yard, ring, region — is custody, not scale (DIRECTIONS_2026-09.md
finding 1). Nothing here maps a distance to a resolution. What is published is the grid itself, and the page
says which custody a reading carries.
"""
from __future__ import annotations

import math

import h3

NAV_MIN, NAV_MAX, NAV_STEPS = 2, 12, 2


def contains(metres: float) -> int:
    """The finest resolution whose cell is at least `metres` across (two edge lengths)."""
    for res in range(15, -1, -1):
        if h3.average_hexagon_edge_length(res, unit="m") * 2 >= metres:
            return res
    return 0


def publication() -> dict:
    """The finest grain a coordinate this node publishes may honestly be drawn at.

    GET /health rounds lat and lon to three decimals (app/main.py), about 110 m at this latitude; a cell narrower
    than that is a claim of precision the node did not make.
    """
    return {"decimals": 3, "metres": 110, "res": contains(110),
            "why": "GET /health rounds lat and lon to three decimals, which is about 110 m — app/main.py"}


def ladder(lat: float, lon: float) -> list[dict]:
    """Every resolution this place can be named at, with what H3 says a cell is there, and the cell it stands in."""
    out = []
    for res in range(0, 14):
        cell = h3.latlng_to_cell(lat, lon, res)
        out.append({
            "res": res, "id": cell,
            "edge_m": round(h3.average_hexagon_edge_length(res, unit="m")),
            "area_m2": round(h3.average_hexagon_area(res, unit="m^2")),
            "cells": h3.get_num_cells(res),
            "own_area_m2": round(h3.cell_area(cell, unit="m^2")),
            "pentagon": h3.is_pentagon(cell),
        })
    return out


def edge_m(cell: str) -> int:
    """THIS cell's own mean edge, in metres — measured, not quoted.

    `h3.average_hexagon_edge_length(res)` is the average over the whole globe, and a cell's edge
    varies with latitude. At node #1, resolution 8: the table says 531 m, this cell measures 497,
    and the cell's own area — 639,778 m², which is what `cell_area` returns and what every one of
    these rows already publishes — is a hexagon with a 496 m edge. Reporting the table's number
    beside this cell's area put two different hexagons on one row, and the page drew both.

    So wherever a row says `cell_area(<a specific cell>)`, its edge is measured from that same cell.
    Where a row publishes the resolution's AVERAGE area — `_ladder` does, and labels this cell's own
    separately as `own_area_m2` — the average edge is the right partner and stays.

    This is the function `app/ground.py` has measured `/health`'s caption with all along; it lives
    here now so there is one of it.
    """
    b = h3.cell_to_boundary(cell)
    return round(sum(h3.great_circle_distance(b[i], b[(i + 1) % len(b)], unit="m")
                     for i in range(len(b))) / len(b))


def _cell_of(station: dict, res: int) -> str:
    return h3.latlng_to_cell(station["lat"], station["lon"], res)


def plates(lat: float, lon: float, stations: list[dict], res_min: int = NAV_MIN, res_max: int = NAV_MAX,
           steps: int = NAV_STEPS) -> dict:
    """One plate per resolution: the node's cell and `steps` rings around it, with every cell's parent, neighbours,
    size and contents. A page navigates only inside what is published — a child or neighbour outside the plate is a
    count, not a door. A dashboard is not a map of the planet."""
    chain = {res: h3.latlng_to_cell(lat, lon, res) for res in range(res_min, res_max + 1)}
    plates_ = {}
    for res in range(res_min, res_max + 1):
        centre = chain[res]
        ids = h3.grid_disk(centre, steps)
        plates_[res] = {"res": res, "centre": centre, "cells": ids,
                        "cells_ll": [[cid] + [round(v, 6) for pt in h3.cell_to_boundary(cid) for v in pt]
                                     for cid in ids]}
    in_plate = lambda res, cid: res_min <= res <= res_max and cid in plates_[res]["cells"]  # noqa: E731
    cells = {}
    for res in range(res_min, res_max + 1):
        for cid in plates_[res]["cells"]:
            parent = h3.cell_to_parent(cid, res - 1) if res > res_min else None
            kids = h3.cell_to_children(cid, res + 1) if res < res_max else []
            try:
                around = h3.grid_ring(cid, 1)
            except Exception:  # noqa: BLE001 — a pentagon's ring is undefined; the disk minus the centre is the answer
                around = [x for x in h3.grid_disk(cid, 1) if x != cid]
            cells[cid] = {
                "res": res,
                "parent": parent if parent and in_plate(res - 1, parent) else None,
                "parent_outside": bool(parent and not in_plate(res - 1, parent)),
                "children_total": len(kids),
                "children_here": sum(1 for k in kids if in_plate(res + 1, k)),
                "neighbours": [n for n in around if in_plate(res, n)],
                "neighbours_total": len(around),
                "area_m2": round(h3.cell_area(cid, unit="m^2")),
                "edge_m": edge_m(cid),
                "pentagon": h3.is_pentagon(cid),
                "sensors": [i for i, s in enumerate(stations) if _cell_of(s, res) == cid],
            }
    return {"res_min": res_min, "res_max": res_max, "steps": steps, "chain": chain,
            "plates": plates_, "cells": cells, "cell_count": len(cells)}


def grain_table(lat: float, lon: float, stations: list[dict], floor_res: int, publication_res: int) -> list[dict]:
    """What every grain is worth: one cell's size, how many cells the stations fall in, and which side of the two
    lines the product already draws it is on."""
    out = []
    for res in range(NAV_MIN, NAV_MAX + 1):
        home = h3.latlng_to_cell(lat, lon, res)
        cells = {_cell_of(s, res) for s in stations}
        mine = [s for s in stations if _cell_of(s, res) == home]
        out.append({
            "res": res, "home": home,
            "area_m2": round(h3.cell_area(home, unit="m^2")),
            "edge_m": edge_m(home),
            "occupied": len(cells),
            "in_my_cell": len(mine),
            "mine_in_my_cell": sum(1 for s in mine if s.get("local")),
            "may_leave": res <= floor_res,
            "finer_than_published": res > publication_res,
        })
    return out


def metres(cid: str, lat: float, lon: float) -> list[float]:
    """A cell's boundary in metres east and south of the node, in the dashboard's own local frame —
    NODE_DASHBOARD_PLAN_SPEC.md rule 1, measured within 0.015 px of geoAzimuthalEqualArea over node #1's plan."""
    k = math.cos(math.radians(lat)) * 111320
    out = []
    for plat, plng in h3.cell_to_boundary(cid):
        out += [round((plng - lon) * k, 1), round(-(plat - lat) * 111320, 1)]
    return out


FLOOR_RES = 6            # PRESENCE_RES_FLOOR in app/main.py: the finest any node may announce


def _circle(lat: float, lon: float, r_m: float, n: int = 90) -> list[list[float]]:
    d_lat = lambda m: m / 111320  # noqa: E731
    d_lon = lambda m: m / (111320 * math.cos(math.radians(lat)))  # noqa: E731
    ring = [[lat + d_lat(r_m * math.cos(a)), lon + d_lon(r_m * math.sin(a))]
            for a in (2 * math.pi * i / n for i in range(n))]
    return ring + [ring[0]]


def _square(lat: float, lon: float, half_m: float) -> list[list[float]]:
    dl, dn = half_m / 111320, half_m / (111320 * math.cos(math.radians(lat)))
    c = [[lat - dl, lon - dn], [lat - dl, lon + dn], [lat + dl, lon + dn], [lat + dl, lon - dn]]
    return c + [c[0]]


def _by_res(cells) -> dict:
    out: dict = {}
    for c in cells:
        out[h3.get_resolution(c)] = out.get(h3.get_resolution(c), 0) + 1
    return out


def cells_at(cells: list[str], res: int) -> int:
    """How many cells of `res` a compacted covering amounts to. Exact for hexagons: seven children per step down,
    distinct ancestors going up. A covering that contains one of the twelve pentagons, or one of its descendants,
    is overcounted — a pentagon has six children, not seven — but no place this node knows is near one."""
    n, up = 0, set()
    for c in cells:
        r = h3.get_resolution(c)
        if res >= r:
            n += 7 ** (res - r)
        else:
            up.add(h3.cell_to_parent(c, res))
    return n + len(up)


def _claim(lat, lon, *, key, name, what, footprint_m, shape, declared, where, note, native_res, base_res) -> dict:
    out = {"key": key, "name": name, "what": what, "footprint_m": footprint_m, "shape": shape,
           "declared": declared, "where": where, "note": note, "native": None}
    if footprint_m <= 0:
        # not a floor: a radius of zero or less is a source declaring no ground, not a typo to round up. Publish
        # the claim with an empty covering rather than invent a metre nobody declared — h3.polygon_to_cells raises
        # on a degenerate polygon, so this is caught before it ever builds one.
        out["drawn"] = {"base_res": base_res, "cells": 0, "compact": 0, "by_res": {}}
        out["area_km2"] = 0
        out["cells"] = []
        out["cells_ll"] = []
        out["cells_at"] = {res: 0 for res in range(NAV_MIN, NAV_MAX + 1)}
        return out
    poly = _square(lat, lon, footprint_m) if shape == "square" else _circle(lat, lon, footprint_m)
    shape_ = h3.LatLngPoly(poly)
    if native_res is not None:
        native = h3.polygon_to_cells(shape_, native_res)
        comp = h3.compact_cells(native)
        out["native"] = {"res": native_res, "cells": len(native), "compact": len(comp),
                         "by_res": _by_res(comp), "saving": round(len(native) / max(1, len(comp)))}
    # the set the page can draw: step the base grain back until the compacted covering fits in one drawing
    base = native_res if native_res is not None else base_res
    cells, comp = [], []
    for r in range(min(base, 11), -1, -1):
        cells = h3.polygon_to_cells(shape_, r)
        comp = h3.compact_cells(cells)
        if 0 < len(comp) <= 140:
            base = r
            break
    out["drawn"] = {"base_res": base, "cells": len(cells), "compact": len(comp), "by_res": _by_res(comp)}
    out["area_km2"] = round(sum(h3.cell_area(c, unit="m^2") for c in comp) / 1e4) / 100
    out["cells"] = sorted(comp)
    # The boundaries of that covering, same shape and same six decimals as plates() publishes, because the
    # dashboard draws a claim as the cells that cover it and a browser here has no h3 to turn an id into a
    # ring. Counts alone would make "resolution is provenance" a sentence instead of a picture. The covering
    # is capped at 140 cells above, so this is bounded: six claims, at most 140 rings of six or seven points.
    out["cells_ll"] = [[cid] + [round(v, 6) for pt in h3.cell_to_boundary(cid) for v in pt]
                       for cid in out["cells"]]
    out["cells_at"] = {res: cells_at(out["cells"], res) for res in range(NAV_MIN, NAV_MAX + 1)}
    return out


def claims(lat: float, lon: float, settings) -> list[dict]:
    """What each source's word covers, as the compacted cell set that covers it. Every footprint is a number a pack or
    a preset already declares; each names the file it came from. Ordered widest first."""
    pub = publication()
    out = [
        _claim(lat, lon, key="coast", name="The sea", what="waves and sea-surface temperature at the nearest ocean cell",
               footprint_m=settings.num("COAST_MAX_KM", 30) * 1000, shape="circle", native_res=None, base_res=7,
               declared=f"COAST_MAX_KM={settings.num('COAST_MAX_KM', 30)}", where="packs/coast/pack.yaml",
               note="the pack refuses if the nearest ocean cell is further than this; the model cell it reads is not "
                    "declared anywhere, so the refusal radius is the only footprint there is"),
        _claim(lat, lon, key="ring", name="The ring", what="public stations this node is allowed to read",
               footprint_m=settings.num("BAD_RADIUS_KM", 15) * 1000, shape="circle", native_res=None, base_res=8,
               declared=f"BAD_RADIUS_KM={settings.num('BAD_RADIUS_KM', 15)}", where=".env / presets",
               note=""),
        _claim(lat, lon, key="region", name="The square this node keeps", what="AlphaEarth satellite embeddings, year against year",
               footprint_m=settings.num("EARTH_RADIUS_M", 5000), shape="square", native_res=contains(10), base_res=9,
               declared=f"EARTH_RADIUS_M={settings.num('EARTH_RADIUS_M', 5000)}, at 10 m a pixel", where="packs/earth/pack.yaml",
               note="the only source whose own resolution is finer than a household sensor, and the only one whose footprint is a square"),
        _claim(lat, lon, key="place", name="The kilometre it draws", what="the plan: buildings, water, green, from OpenStreetMap",
               footprint_m=settings.num("PLACE_RADIUS_M", 1000), shape="circle", native_res=None, base_res=10,
               declared=f"PLACE_RADIUS_M={settings.num('PLACE_RADIUS_M', 1000)}", where="packs/place/pack.yaml", note=""),
        _claim(lat, lon, key="yard", name="The street", what="this node's own ground",
               footprint_m=settings.num("LOCAL_RADIUS_M", 500), shape="circle", native_res=None, base_res=11,
               declared=f"LOCAL_RADIUS_M={settings.num('LOCAL_RADIUS_M', 500)}", where=".env", note=""),
        _claim(lat, lon, key="room", name="This house", what="the probes in this house",
               footprint_m=pub["metres"], shape="circle", native_res=pub["res"], base_res=pub["res"],
               declared="lat and lon rounded to three decimals", where="app/main.py, GET /health",
               note="not a radius anybody chose: it is how precisely this node is willing to say where it is, and no "
                    "reading from it may be drawn finer"),
    ]
    return sorted(out, key=lambda c: -c["area_km2"])


def radio(lat: float, lon: float, settings, peers: list[dict]) -> dict:
    """What the radio says about where: this node's announce cell, and for each peer either the cell it announced or
    — when only a distance survived — the cells around this one that distance could be in. Never a point."""
    # Clamped at both ends, the way app/main.py's own presence path clamps it. A negative resolution
    # is a number a keeper can type into Set up, and h3.latlng_to_cell raises H3ResDomainError on one
    # — which would take GET /issues down, and with it the whole dashboard, over a setting that only
    # ever decides how coarsely this node announces itself.
    res = max(0, min(int(settings.num("RETICULUM_PRESENCE_RES", 3)), FLOOR_RES))
    mine = h3.latlng_to_cell(lat, lon, res)
    around = h3.grid_disk(mine, 2)

    def rng(cid):
        ds = [h3.great_circle_distance((lat, lon), pt, unit="km") for pt in h3.cell_to_boundary(cid)]
        return min(ds), max(ds)

    cands: list[str] = []
    km = None
    for p in peers or []:
        km = p.get("km", km)
        if p.get("cell"):
            if p["cell"] not in cands:
                cands.append(p["cell"])
        elif p.get("km") is not None:
            for cid in around:
                lo, hi = rng(cid)
                if cid != mine and lo <= p["km"] <= hi and cid not in cands:
                    cands.append(cid)
    return {"res": res, "mine": mine, "candidates": cands, "peer_km": km,
            "edge_m": edge_m(mine),
            "area_m2": round(h3.cell_area(mine, unit="m^2")), "cells": around}


# ---------------------------------------------------------------- the map workbench (GET /geo/*)
# The redesign's Place door pans, zooms, inspects and measures. Every shape and every distance it draws is
# answered here, so the page stays a drawing: the same `cells_ll` rows plates() publishes, and metres from
# h3's own great-circle distance. All pure; app/main.py adds the node's point and the gate.

GRID_CAP = 2500          # cells one answer may carry: a 1440 px map at its finest useful rung is about 600


def _row(cid: str) -> list:
    return [cid] + [round(v, 6) for pt in h3.cell_to_boundary(cid) for v in pt]


def grid(west: float, south: float, east: float, north: float, res: int, lat: float, lon: float) -> dict:
    """The cells that cover a box at `res`, plus one ring round them so the grid runs off the frame's edge,
    and the node's own cell at that resolution. Refuses a box that would cost more than GRID_CAP cells,
    estimated before any is computed, rather than truncating a covering silently."""
    if not (-90 <= south < north <= 90 and -180 <= west < east <= 180):
        raise ValueError("bbox must be west,south,east,north in degrees, with west < east and south < north")
    mid = math.radians((south + north) / 2)
    area = (east - west) * 111320 * math.cos(mid) * (north - south) * 111320
    if area / h3.average_hexagon_area(res, unit="m^2") > GRID_CAP:
        raise ValueError(f"that box holds more than {GRID_CAP} cells at resolution {res}: zoom in or ask coarser")
    poly = h3.LatLngPoly([(south, west), (south, east), (north, east), (north, west)])
    inner = h3.polygon_to_cells(poly, res) or [h3.latlng_to_cell((south + north) / 2, (west + east) / 2, res)]
    cells = sorted({n for c in inner for n in h3.grid_disk(c, 1)})[:GRID_CAP]
    return {"res": res, "may_leave": res <= FLOOR_RES, "edge_m": round(h3.average_hexagon_edge_length(res, unit="m")),
            "node": _row(h3.latlng_to_cell(lat, lon, res)), "cells_ll": [_row(c) for c in cells]}


CHILDREN_CAP = 400       # child rings one answer may carry; the count is always given


def bearing(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Initial great-circle bearing from the first point to the second, degrees clockwise from north."""
    p1, p2, dl = math.radians(lat1), math.radians(lat2), math.radians(lon2 - lon1)
    y = math.sin(dl) * math.cos(p2)
    x = math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dl)
    return round((math.degrees(math.atan2(y, x)) + 360) % 360, 2)


def polar(cid: str, lat: float, lon: float) -> list:
    """A cell's boundary as [id, metres, bearing, metres, bearing, …] from (lat, lon): what a drawing that places
    things by distance and direction from the node needs, so it works out neither."""
    out = [cid]
    for plat, plng in h3.cell_to_boundary(cid):
        out += [round(h3.great_circle_distance((lat, lon), (plat, plng), unit="m"), 1), bearing(lat, lon, plat, plng)]
    return out


def cell(cid: str, lat: float, lon: float, children: int | None = None, as_polar: bool = False) -> dict:
    """What the inspector says about one cell: its own area and edge, its parent, and how far it is from the
    node's cell at the same resolution, in cells (None when h3 cannot walk the grid that far). With `children`, the
    count of its children at that resolution and, up to CHILDREN_CAP, their rings; with `as_polar`, every ring also
    as distance and bearing from the node."""
    if not h3.is_valid_cell(cid):
        raise ValueError(f"{cid!r} is not an H3 cell")
    res = h3.get_resolution(cid)
    mine = h3.latlng_to_cell(lat, lon, res)
    try:
        steps = h3.grid_distance(cid, mine)
    except Exception:  # noqa: BLE001 — h3 refuses across a pentagon or past its walk limit; say so, do not guess
        steps = None
    out = {"id": cid, "res": res, "area_m2": round(h3.cell_area(cid, unit="m^2")), "edge_m": edge_m(cid),
           "parent": h3.cell_to_parent(cid, res - 1) if res else None, "may_leave": res <= FLOOR_RES,
           "is_node": cid == mine, "cells_from_node": steps, "ring": _row(cid)}
    if as_polar:
        out["ring_polar"] = polar(cid, lat, lon)
    if children is not None:
        if not res < children <= 15:
            raise ValueError(f"children must be finer than this cell's resolution {res}, and at most 15")
        out["children_res"] = children
        out["children_n"] = h3.cell_to_children_size(cid, children)
        if out["children_n"] <= CHILDREN_CAP:
            kids = sorted(h3.cell_to_children(cid, children))
            out["children_ll"] = [_row(k) for k in kids]
            if as_polar:
                out["children_polar"] = [polar(k, lat, lon) for k in kids]
    return out


def measure(points: list[tuple[float, float]]) -> dict:
    """A path as the reader clicked it, (lon, lat) pairs: each leg and the total, in metres, great-circle."""
    legs = [round(h3.great_circle_distance((a[1], a[0]), (b[1], b[0]), unit="m"), 1)
            for a, b in zip(points, points[1:])]
    return {"legs_m": legs, "total_m": round(sum(legs), 1), "points": len(points)}


def each(points: list[tuple[float, float]]) -> list[dict]:
    """From the first (lon, lat) point to every other: metres and initial bearing, for a drawing that places
    each by distance and direction."""
    lon0, lat0 = points[0]
    return [{"m": round(h3.great_circle_distance((lat0, lon0), (la, lo), unit="m"), 1), "deg": bearing(lat0, lon0, la, lo)}
            for lo, la in points[1:]]


def planet(res: int) -> list:
    """Every cell on the planet at a coarse resolution, as cells_ll rows: 122 at res 0, 842 at 1, 5,882 at 2."""
    if not 0 <= res <= 2:
        raise ValueError("the planet grid is drawn at resolution 0, 1 or 2")
    return [_row(c) for r0 in sorted(h3.get_res0_cells()) for c in sorted(h3.cell_to_children(r0, res))]


def rings(lat: float, lon: float, kms: list[float]) -> list[dict]:
    """Circles round the node, as [lat, lng] rings, so the page draws a distance it did not work out."""
    return [{"km": k, "ring": [[round(a, 6), round(b, 6)] for a, b in _circle(lat, lon, k * 1000)]} for k in kms]
