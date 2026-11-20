"""The household's maps on the Place door: named maps, the drawings on them, their rows in the ledger, and a drawing
tied to an issue as the issue's acted step. planetai-design/node-docs/superpowers/specs/2026-11-04-place-light-gis-design.md §5 and §8.

Every route here is the household's alone, at every SHARE_LEVEL: none is on an allowlist in app/auth.py, and the router
checks the admin or act token itself because the middleware also lets BACKUP_TOKEN through, and a NAS's read token
must not draw or write ρ (the same reason POST /actions checks its own). PostGIS measures every drawing: `length_m`
and `area_m2` come from `geom::geography` on every insert and update, so the page computes no distance.

An agent's own map (`agent` set) is refused to the household's edits in this pull request; agents become writers in
the third (§7). A map received from a child node (`from_node` set) is refused to them always: it is the child's.
Never import app/main.py from here: it starts a second MQTT client.

A shared map goes to the node upstream exactly as drawn (Tomas, 4 Nov: "Exact, with a warning"), by the child's
push, never a pull: push_maps() every minute, and POST /place/maps/received on the parent, one of the two routes here
that answer AGGREGATE_TOKEN and nothing else.

A shared drawing's photo goes up as words, never the file (Tomas, 5 Nov; §14): its kind, note, the household's own
`meta` and the day it was taken. The parent may ask for the file. The ask comes down in the parent's answer to the
child's hourly /aggregates push (asks_for, take_asks), because a parent cannot reach a home node; the file goes up only
when somebody here presses Send, by push_maps() to POST /place/photos/received, and only while the photo is on a
shared drawing. The parent serves it to its own token holders and deletes it once no map of that child carries it.
"""
from __future__ import annotations

import base64
import json
import logging
import math
import os
import re
import unicodedata
import xml.etree.ElementTree as ET
from contextlib import contextmanager
from datetime import datetime
from hashlib import sha256
from zoneinfo import ZoneInfo

import psycopg

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response
from fastapi.responses import FileResponse
from psycopg.types.json import Jsonb

import events_pg
import geo
import identity
from auth import ACT_TOKEN, AGG_TOKEN, PARENT, PARENT_TOKEN, _bearer_ok, _is_local
from db import NODE_TZ, db

log = logging.getLogger("planetai")


def _household(request: Request, authorization: str = Header("")) -> None:
    if not (_is_local(request) or _bearer_ok(authorization, os.getenv("ADMIN_TOKEN", "").strip(), ACT_TOKEN())):
        raise HTTPException(401, "Maps need the household's token.")


router = APIRouter(dependencies=[Depends(_household)])
received = APIRouter()                                     # a child's writes: AGGREGATE_TOKEN, never the household's

SHARE_WARNING = ("Sharing sends every drawing in this map, at its exact place, with its labels, notes and measures, to "
                 "the node upstream, where the people holding its token can see it. A photo on a drawing goes as what "
                 "you wrote about it and the day it was taken, and the picture stays here. Press Share again to send it.")
NO_PARENT = "There is no node upstream to share with. Set PARENT in Set up first."
ON_HOUSE = "This drawing touches the cell the house stands in. Press Share again to send the map with it."
NOT_YET = "The node upstream does not take maps yet."
NOT_SENT = "The map did not reach the node upstream. The node tries again in an hour."
NO_TOKEN = "The node upstream did not take this node's token. Set PARENT_TOKEN in Set up to the one it gave you."

# Colour → (hex for the screen, AutoCAD Colour Index for DXF). A drawing stores the number, so this can change without
# a migration. None is the satellite's orange or the cells' blue, and each reads on the satellite and on black.
PALETTE: dict[int, tuple[str, int]] = {
    1: ("#FFFFFF", 7), 2: ("#FFE600", 2), 3: ("#9BFF2E", 70), 4: ("#00E5FF", 4), 5: ("#FF3DCB", 6), 6: ("#FF3B30", 1)}

_TYPE = {"marker": "Point", "note": "Point", "line": "LineString", "area": "Polygon"}
_COORDS = "Every point needs a longitude and a latitude."
# ponytail: ceilings, not a queue. _crosses() is O(n²) on the request thread: 1,000 corners take 0.2 s and 5,000 took
# 4.6 s on a Mac. Nobody taps 1,000 points by hand; an import of surveyed outlines would need a bigger cap and a
# faster check (a sweep line, or PostGIS's ST_IsSimple) first.
MAX_POINTS = 1_000                                         # one drawing
MAX_DRAWINGS, MAX_MAP_POINTS = 2_000, 20_000               # a child's shared map, on /place/maps/received
TOO_BIG = "A shared map holds 2,000 drawings and 20,000 points at most."

# The two reads of the picture table this module makes, and the folder: the words a shared drawing's photo carries
# upstream (never lat, lon, cell, at_home or actor; the pictures suite holds it to these) and the file Send sends.
_PHOTO_WORDS = "SELECT id, kind, note, meta, ts FROM captures WHERE id = ANY(%s)"
_PHOTO_FILE = "SELECT file, mime FROM captures WHERE id = %s"
_PHOTO_DIR = lambda: os.getenv("PLANETAI_CAPTURES", "/app/captures")   # noqa: E731
PHOTO_KINDS = ("microscope", "phone", "camera", "drone", "balloon")
MAX_PHOTO = 25 * 1024 * 1024
_PHOTOS = "planetai.place.photo/v0"
_NO_ASK, _CLOSED = "No such ask.", "That ask is closed."   # the parent no longer wants it: the child is done


# ---------------------------------------------------------------- what a drawing must be

def _pt(p) -> bool:
    return (isinstance(p, (list, tuple)) and len(p) == 2
            and all(isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x) for x in p)
            and -180 <= p[0] <= 180 and -90 <= p[1] <= 90)


def _dedupe(pts: list) -> list:
    """A point tapped twice in a row is one point."""
    return [list(p) for i, p in enumerate(pts) if i == 0 or list(p) != list(pts[i - 1])]


def _ring(pts: list) -> list:
    """An area's outline, closed: an outline left open is closed here rather than refused."""
    r = _dedupe(pts)
    return r + [r[0]] if r and r[0] != r[-1] else r


def _orient(a, b, c) -> int:
    v = (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
    return (v > 0) - (v < 0)


def _on(a, b, c) -> bool:
    """c, collinear with a-b, lies on the segment."""
    return min(a[0], b[0]) <= c[0] <= max(a[0], b[0]) and min(a[1], b[1]) <= c[1] <= max(a[1], b[1])


def _meet(p1, p2, p3, p4) -> bool:
    d1, d2, d3, d4 = _orient(p3, p4, p1), _orient(p3, p4, p2), _orient(p1, p2, p3), _orient(p1, p2, p4)
    if d1 * d2 < 0 and d3 * d4 < 0:
        return True
    return ((d1 == 0 and _on(p3, p4, p1)) or (d2 == 0 and _on(p3, p4, p2))
            or (d3 == 0 and _on(p1, p2, p3)) or (d4 == 0 and _on(p1, p2, p4)))


def _crosses(ring: list) -> bool:
    """Any two sides that are not neighbours touch or cross.
    ponytail: O(n²) crossing check, held to MAX_POINTS corners (0.2 s at 1,000)."""
    pts = ring[:-1]
    n = len(pts)
    for i in range(n):
        for j in range(i + 2, n):
            if i == 0 and j == n - 1:
                continue                                   # the last side meets the first at the start: neighbours
            if _meet(pts[i], pts[(i + 1) % n], pts[j], pts[(j + 1) % n]):
                return True
    return False


def _points(feature) -> int:
    """How many points a drawing claims, counted before any is checked: a Point is one, a line its points, an area its
    outlines' points. Anything else counts one, and check_feature() refuses it in words."""
    g = feature.get("geometry") if isinstance(feature, dict) else None
    c = g.get("coordinates") if isinstance(g, dict) else None
    if not (isinstance(c, list) and c and isinstance(c[0], list)):
        return 1
    return sum(len(x) if isinstance(x, list) and x and isinstance(x[0], list) else 1 for x in c)


def check_feature(feature: dict) -> str | None:
    """The sentence a drawing is refused with, or None. Its kind says which geometry it must be."""
    props = feature.get("properties") if isinstance(feature, dict) else None
    kind = props.get("kind") if isinstance(props, dict) else None
    if kind not in _TYPE:
        return "A drawing is a marker, a line, an area or a note."
    if _points(feature) > MAX_POINTS:
        return "A drawing has 1,000 points at most."
    geom = feature.get("geometry")
    gtype, c = (geom.get("type"), geom.get("coordinates")) if isinstance(geom, dict) else (None, None)
    if kind in ("marker", "note"):
        if gtype != "Point":
            return f"A {kind} is one point."
        return None if _pt(c) else _COORDS
    if kind == "line":
        if gtype != "LineString" or not isinstance(c, list):
            return "A line needs two points or more."
        if not all(_pt(p) for p in c):
            return _COORDS
        return None if len(_dedupe(c)) >= 2 else "A line needs two points or more."
    if gtype != "Polygon" or not isinstance(c, list) or not c or not isinstance(c[0], list):
        return "An area needs three corners or more."
    if len(c) > 1:
        return "An area is one outline, with no holes."
    if not all(_pt(p) for p in c[0]):
        return _COORDS
    ring = _ring(c[0])
    if len(ring) < 4 or len({tuple(p) for p in ring}) < 3:
        return "An area needs three corners or more."
    return "That area crosses itself. Draw its corners in order around it." if _crosses(ring) else None


def _geometry(kind: str, geom: dict) -> str:
    """The checked geometry as stored: repeats dropped, an area's outline closed."""
    c = geom["coordinates"]
    if kind == "line":
        c = _dedupe(c)
    elif kind == "area":
        c = [_ring(c[0])]
    return json.dumps({"type": _TYPE[kind], "coordinates": c})


def _text(x, n: int) -> str | None:
    return (str(x).strip()[:n] or None) if x is not None else None


def _fields(src: dict) -> dict:
    """The columns a drawing's form may set, only those present: label, note, colour, image."""
    out = {}
    if "label" in src:
        out["label"] = _text(src["label"], 80)
    if "note" in src:
        out["note"] = _text(src["note"], 500)
    if "colour" in src:
        c = src["colour"]
        if isinstance(c, bool) or not isinstance(c, int) or c not in PALETTE:     # a list is unhashable: refused, not a 500
            raise HTTPException(422, "A colour is a number from 1 to 6.")
        out["colour"] = c
    if "image" in src:
        i = src["image"]
        if i is not None and (isinstance(i, bool) or not isinstance(i, int)):
            raise HTTPException(422, "An image is a picture's number on this node.")
        out["capture_id"] = i
    return out


def photo_words(cap: dict) -> dict:
    """What a shared drawing says about its photo (§14): the kind of camera, the note, the household's own words and
    the day it was taken. Never where, never who, never the file."""
    ts = cap.get("ts")
    return {"kind": cap["kind"], "note": cap.get("note"), "meta": dict(cap.get("meta") or {}),
            "taken": ts.astimezone(ZoneInfo(NODE_TZ)).date().isoformat() if ts else None}


_NOT_A_PHOTO = "A photo is described by its kind, a note, short words and the day it was taken."


def photo_in(image, photo) -> dict | None:
    """A child's words about the photo on a drawing, checked as any child input is, kept with the child's number as
    `ref`. None when the drawing names no photo; a 422 when the words are not a photo's."""
    if photo is None or image is None:
        return None
    if isinstance(image, bool) or not isinstance(image, int) or not isinstance(photo, dict):
        raise HTTPException(422, _NOT_A_PHOTO)
    meta, taken = photo.get("meta") or {}, photo.get("taken")
    if (photo.get("kind") not in PHOTO_KINDS or not isinstance(meta, dict) or len(meta) > 40
            or not all(isinstance(v, str) for v in meta.values())):
        raise HTTPException(422, _NOT_A_PHOTO)
    if taken is not None:
        try:
            taken = datetime.strptime(str(taken), "%Y-%m-%d").date().isoformat()
        except ValueError:
            raise HTTPException(422, _NOT_A_PHOTO) from None
    return {"ref": image, "kind": photo["kind"], "note": _text(photo.get("note"), 500),
            "meta": {str(k)[:60]: v[:500] for k, v in meta.items()}, "taken": taken}


# ---------------------------------------------------------------- downloads

_SCHEMA = "planetai.place.map/v0"
_DXF_LAYER = {"marker": "MARKERS", "line": "LINES", "area": "AREAS", "note": "NOTES"}
_TEXT_H = 1.5                                              # metres: a label on a garden plan


def feature_collection(map_row: dict, marks: list[dict], node: str, upstream: bool = False) -> dict:
    """The map as GeoJSON in WGS84: the same shape the page draws, and what a pull from another node reads back.
    `image` is the picture's capture id and never a file. `upstream` is the copy push_maps() sends: it leaves out
    `drawn_by`, and its `owner` is the node (Tomas, 5 Nov: "the node is the owner"), by its ID when it has a key
    (docs/SPEC_identity.md), so no household member's name
    goes up (§5 lists what does); the household's own download keeps both."""
    def props(m):
        at = m.get("updated_at")
        p = {"kind": m["kind"], "label": m.get("label"), "note": m.get("note"), "colour": m["colour"],
             "colour_hex": PALETTE[m["colour"]][0], "length_m": m.get("length_m"), "area_m2": m.get("area_m2"),
             "image": m.get("capture_id"), "drawn_by": m.get("drawn_by"), "updated_at": at.isoformat() if at else None}
        if upstream:
            del p["drawn_by"]
        if m.get("photo"):
            p["photo"] = m["photo"]                       # upstream: photo_words(); a received map's download: its words
        return p
    return {"type": "FeatureCollection", "schema": _SCHEMA, "map": map_row["name"],
            "owner": (identity.node_id() or node) if upstream else map_row.get("owner"), "node": node, "features": [{"type": "Feature", "properties": props(m), "geometry": m["geometry"]} for m in marks]}


def to_kml(fc: dict) -> str:
    """KML 2.2 for Google Earth and QGIS. Each Placemark carries the drawing's colour (KML wants aabbggrr).
    ponytail: geometry is written here from the GeoJSON rather than read back from ST_AsKML; the three shapes are
    the same coordinates, and the pure function stays testable without a database."""
    ns = "http://www.opengis.net/kml/2.2"
    ET.register_namespace("", ns)
    q = lambda t: f"{{{ns}}}{t}"                           # noqa: E731
    clean = lambda t: re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", str(t))   # noqa: E731 — XML 1.0 refuses these
    root = ET.Element(q("kml"))
    doc = ET.SubElement(root, q("Document"))
    ET.SubElement(doc, q("name")).text = clean(fc["map"])
    for f in fc["features"]:
        p, g = f["properties"], f["geometry"]
        pm = ET.SubElement(doc, q("Placemark"))
        ET.SubElement(pm, q("name")).text = clean(p["label"] or p["kind"])
        if p["note"]:
            ET.SubElement(pm, q("description")).text = clean(p["note"])
        h = p["colour_hex"]
        kc = "ff" + h[5:7] + h[3:5] + h[1:3]
        st = ET.SubElement(pm, q("Style"))
        for tag in ("IconStyle", "LineStyle", "PolyStyle"):
            ET.SubElement(ET.SubElement(st, q(tag)), q("color")).text = kc
        c = g["coordinates"]
        line = lambda pts: " ".join(",".join(map(str, pt)) for pt in pts)   # noqa: E731
        if g["type"] == "Point":
            ET.SubElement(ET.SubElement(pm, q("Point")), q("coordinates")).text = line([c])
        elif g["type"] == "LineString":
            ET.SubElement(ET.SubElement(pm, q("LineString")), q("coordinates")).text = line(c)
        else:
            ring = ET.SubElement(ET.SubElement(ET.SubElement(pm, q("Polygon")), q("outerBoundaryIs")), q("LinearRing"))
            ET.SubElement(ring, q("coordinates")).text = line(c[0])
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(root, encoding="unicode")


def utm_epsg(lon: float, lat: float) -> int:
    """The WGS84 UTM zone a point lies in: 326zz north of the equator, 327zz south."""
    zone = min(60, max(1, int((lon + 180) // 6) + 1))
    return (32600 if lat >= 0 else 32700) + zone


def to_dxf(features_xy: list[dict], epsg: int) -> str:
    """AutoCAD R12 DXF, hand-written: every CAD reads it. Each item is {kind, label, note, colour, xy}, `xy` the
    drawing's vertices already in metres of `epsg`, which the first comment line says. Non-ASCII text is written the
    way AutoCAD writes it (\\U+00F1), because R12 has no encoding."""
    def txt(t):
        return "".join(ch if ord(ch) < 128 else f"\\U+{ord(ch):04X}" for ch in " ".join(str(t).split()))
    out = [999, f"EPSG:{epsg}, metres", 0, "SECTION", 2, "HEADER", 9, "$ACADVER", 1, "AC1009", 0, "ENDSEC",
           0, "SECTION", 2, "TABLES", 0, "TABLE", 2, "LTYPE", 70, 1, 0, "LTYPE", 2, "CONTINUOUS", 70, 0, 3, "Solid line",
           72, 65, 73, 0, 40, 0.0, 0, "ENDTAB", 0, "TABLE", 2, "LAYER", 70, len(_DXF_LAYER)]
    for name in _DXF_LAYER.values():
        out += [0, "LAYER", 2, name, 70, 0, 62, 7, 6, "CONTINUOUS"]
    out += [0, "ENDTAB", 0, "ENDSEC", 0, "SECTION", 2, "ENTITIES"]
    xyz = lambda x, y: [10, f"{x:.3f}", 20, f"{y:.3f}", 30, 0]   # noqa: E731
    for f in features_xy:
        layer, aci, pts = _DXF_LAYER[f["kind"]], PALETTE[f["colour"]][1], f["xy"]
        head = [8, layer, 62, aci]
        if f["kind"] in ("marker", "note"):
            out += [0, "POINT", *head, *xyz(*pts[0])]
        else:
            out += [0, "POLYLINE", *head, 66, 1, *xyz(0, 0), 70, 1 if f["kind"] == "area" else 0]
            for x, y in pts:
                out += [0, "VERTEX", 8, layer, *xyz(x, y)]
            out += [0, "SEQEND", 8, layer]
        x, y = pts[0]
        for t in (f.get("label"), f.get("note")):
            if t and txt(t):
                out += [0, "TEXT", 8, _DXF_LAYER["note"], 62, aci, *xyz(x, y), 40, _TEXT_H, 1, txt(t)]
                y -= _TEXT_H * 1.5                         # a note sits under its label
    out += [0, "ENDSEC", 0, "EOF"]
    return "\n".join(map(str, out)) + "\n"


# ---------------------------------------------------------------- the ledger and the issue

def ledger(cur, actor: str, verb: str, note: str, key: str) -> None:
    """One `place` row in the actions ledger. The same person doing the same thing to the same drawing within a minute
    is one row: its time and note move on. `key` (`mark:12`, `map:3`) ends the note as `(mark 12)`."""
    tail = f" ({key.replace(':', ' ', 1)})"
    text = note[:500 - len(tail)] + tail
    # ponytail: two writes in the same instant could both miss the update and insert twice; harmless in a ledger
    cur.execute("""UPDATE actions SET ts = now(), note = %s WHERE ctid = (
                     SELECT ctid FROM actions WHERE stage = 'place' AND actor = %s AND choice = %s
                        AND right(note, %s) = %s AND ts > now() - interval '60 seconds' ORDER BY ts DESC LIMIT 1)""",
                (text, actor, verb, len(tail), tail))
    if not cur.rowcount:
        cur.execute("INSERT INTO actions (stage, actor, note, choice) VALUES ('place', %s, %s, %s)", (actor, text, verb))


def tie(cur, mark_id: int, issue: dict | None, words: str, actor: str) -> None:
    """A drawing as an issue's acted step (§8): the row the Done button writes, with `choice = 'place.mark:<id>'` and the
    person's own words. Written here, not through POST /actions, whose choice check would refuse it. `issue` is
    `{"alert_id": A}` or `{"event_id": E}`, the way the Done button on that issue carries it; None unties, deleting the
    row. Tying again replaces it; to the same issue it keeps the act's time, so new words do not move it out of ρ's
    24 h, and to another issue it is a new act. Deleting the drawing keeps it, because the person did act."""
    choice = f"place.mark:{mark_id}"
    cur.execute("DELETE FROM actions WHERE stage = 'acted' AND choice = %s RETURNING ts, alert_id, event_id", (choice,))
    was = cur.fetchone()
    alert_id = event_id = None
    if issue is not None:
        words = str(words or "").strip()
        if not words:
            raise HTTPException(422, "Say what you did, in your own words.")
        ok = (isinstance(issue, dict) and len(issue) == 1 and next(iter(issue)) in ("alert_id", "event_id")
              and isinstance(next(iter(issue.values())), int) and not isinstance(next(iter(issue.values())), bool))
        if not ok:
            raise HTTPException(422, 'Tie a drawing to one issue: {"alert_id": …} or {"event_id": …}.')
        (key, iid), = issue.items()
        if key == "alert_id":
            cur.execute("SELECT 1 FROM alerts WHERE id = %s", (iid,))
            if not cur.fetchone():
                raise HTTPException(404, "no such alert")
            if refusal := events_pg.decision_first(cur, iid):
                raise HTTPException(409, refusal)
            alert_id = iid
        else:
            cur.execute("SELECT 1 FROM alert_events WHERE id = %s", (iid,))
            if not cur.fetchone():
                raise HTTPException(404, "no such event")
            event_id = iid
        ts = was["ts"] if was and (was["alert_id"], was["event_id"]) == (alert_id, event_id) else None
        cur.execute("INSERT INTO actions (ts, alert_id, event_id, stage, actor, note, choice) "
                    "VALUES (COALESCE(%s, now()), %s, %s, 'acted', %s, %s, %s)", (ts, alert_id, event_id, actor, words[:500], choice))
    cur.execute("UPDATE place_marks SET alert_id = %s, event_id = %s WHERE id = %s", (alert_id, event_id, mark_id))


# ---------------------------------------------------------------- reads and guards

_MAP = """SELECT p.id, p.name, p.owner, p.agent, p.shared, p.held, p.share_error, p.from_node, p.updated_at,
                 (SELECT count(*) FROM place_marks k WHERE k.map_id = p.id)::int AS marks
            FROM place_maps p"""
_MARK = """SELECT id, map_id, kind, colour, label, note, capture_id, photo, length_m, area_m2, drawn_by, alert_id, event_id,
                  updated_at, ST_AsGeoJSON(geom)::json AS geometry FROM place_marks"""
# Measured from the geometry the row ends with; `g.geom` is the new one, NULL when the geometry did not change.
_MEASURE = """length_m = CASE WHEN m.kind = 'line' THEN ST_Length(COALESCE(g.geom, m.geom)::geography) END,
              area_m2 = CASE WHEN m.kind = 'area' THEN ST_Area(COALESCE(g.geom, m.geom)::geography) END"""


def _actor(request: Request, body: dict) -> str:
    """The page's `planetai_actor`, or an agent's X-Agent, which wins."""
    return str(request.headers.get("x-agent") or body.get("actor") or "")[:80]


def _map(cur, map_id: int) -> dict:
    """The map, if the household may edit it."""
    cur.execute("SELECT id, name, agent, from_node, shared FROM place_maps WHERE id = %s", (map_id,))
    m = cur.fetchone()
    if not m:
        raise HTTPException(404, "No such map.")
    _yours(m)
    return m


def _mark(cur, mark_id: int) -> dict:
    """The drawing with its map's name, if the household may edit it."""
    cur.execute("""SELECT k.id, k.kind, k.label, k.map_id, p.name, p.agent, p.from_node, p.shared FROM place_marks k
                   JOIN place_maps p ON p.id = k.map_id WHERE k.id = %s""", (mark_id,))
    k = cur.fetchone()
    if not k:
        raise HTTPException(404, "No such drawing.")
    _yours(k)
    return k


def _yours(m: dict) -> None:
    if m["agent"]:
        raise HTTPException(403, f"This is {m['agent']}'s map.")
    if m["from_node"]:
        raise HTTPException(403, f"This map came from {m['from_node']}; it is read-only here.")


def _house_hold(cur, shared: bool, map_id: int, mark_id: int) -> dict:
    """A drawing on the house's own res-10 cell holds a shared map: nothing goes up until Share is pressed again (§5).
    The hold is the `held` flag, which push_maps() never sends past; the sentence is only what the page shows.
    {"warn": …} or {}."""
    try:
        house = geo.home_cell(10) if shared else None
    except HTTPException:
        house = None                                       # a node with no point has no house to warn about
    if not house:
        return {}
    import h3  # noqa: PLC0415
    ring = [[lng, lat] for lat, lng in h3.cell_to_boundary(house)]
    cur.execute("SELECT ST_Intersects(geom, ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326)) AS on_house FROM place_marks WHERE id = %s",
                (json.dumps({"type": "Polygon", "coordinates": [ring + ring[:1]]}), mark_id))
    if not cur.fetchone()["on_house"]:
        return {}
    cur.execute("UPDATE place_maps SET held = true WHERE id = %s", (map_id,))
    return {"warn": ON_HOUSE}


def _shown(m: dict) -> dict:
    """A map as the page reads it: a held map says why in `share_error`, in today's words."""
    if m["held"]:
        m["share_error"] = ON_HOUSE
    return m


@contextmanager
def _image_here():
    """The picture a drawing names must be on this node. The foreign key decides, so this module reads no picture
    table: in step 1 that table is main.py's alone, and a test holds it there."""
    try:
        yield
    except psycopg.errors.ForeignKeyViolation:
        raise HTTPException(404, "That picture is not on this node.") from None


def _one(cur, sql: str, id_: int) -> dict:
    cur.execute(sql, (id_,))
    return cur.fetchone()


# ---------------------------------------------------------------- maps

@router.get("/place/maps")
def maps_():
    """The maps, each with how many drawings it holds, and the palette the drawings' colour numbers mean."""
    with db() as con, con.cursor() as cur:
        cur.execute(_MAP + " ORDER BY p.updated_at DESC, p.id DESC")
        return {"maps": [_shown(m) for m in cur.fetchall()], "palette": {str(k): h for k, (h, _) in PALETTE.items()}}


@router.get("/place/maps/{map_id}/marks")
def map_marks(map_id: int):
    """A map's drawings, each with its id, as the page draws and edits them. Reading writes nothing to the ledger: a
    download (map_download) is a row, the screen drawing what it holds is not."""
    with db() as con, con.cursor() as cur:
        m = _one(cur, "SELECT id, from_node FROM place_maps WHERE id = %s", map_id)
        if not m:
            raise HTTPException(404, "No such map.")
        cur.execute(_MARK + " WHERE map_id = %s ORDER BY id", (map_id,))
        marks = cur.fetchall()
        if m["from_node"]:                                  # a child's drawing: where the ask for its photo stands
            cur.execute("SELECT ref, state, asked_by, asked_at, answered_at FROM place_photo_asks WHERE from_node = %s",
                        (m["from_node"],))
            asks = {a.pop("ref"): a for a in cur.fetchall()}
            for k in marks:
                if k["photo"]:
                    k["photo"]["ask"] = asks.get(k["photo"]["ref"])
        return {"marks": marks}


@router.post("/place/maps")
def map_new(body: dict, request: Request):
    """{"name": "Garden plan", "owner": "Tomas"?, "actor": "Tomas"} → {"map": …}."""
    name = _text(body.get("name"), 80)
    if not name:
        raise HTTPException(422, "A map needs a name.")
    with db() as con, con.transaction(), con.cursor() as cur:
        cur.execute("INSERT INTO place_maps (name, owner) VALUES (%s, %s) RETURNING id", (name, _text(body.get("owner"), 80)))
        mid = cur.fetchone()["id"]
        ledger(cur, _actor(request, body), "drew", name, f"map:{mid}")
        return {"map": _shown(_one(cur, _MAP + " WHERE p.id = %s", mid))}


@router.patch("/place/maps/{map_id}")
def map_edit(map_id: int, body: dict, request: Request):
    """{"name"?, "owner"?, "shared"?, "confirm"?, "actor"} → {"map": …}. `"shared": true` needs a node upstream and
    `"confirm": "exact"`, which the page sends on the second press, after the warning; without it, 409 with
    `{"code": "share_warning", "text": SHARE_WARNING}`.
    It also releases a map a drawing on the house held. `"shared": false` owes the node upstream one delete."""
    sets = {}
    if "name" in body:
        sets["name"] = _text(body["name"], 80)
        if not sets["name"]:
            raise HTTPException(422, "A map needs a name.")
    if "owner" in body:
        sets["owner"] = _text(body["owner"], 80)
    with db() as con, con.transaction(), con.cursor() as cur:
        m = _map(cur, map_id)
        if sets:
            cur.execute(f"UPDATE place_maps SET {''.join(f'{k} = %({k})s, ' for k in sets)}updated_at = now() WHERE id = %(id)s",
                        {**sets, "id": map_id})
            ledger(cur, _actor(request, body), "changed", sets.get("name", m["name"]), f"map:{map_id}")
        if body.get("shared") is True:
            if not PARENT():
                raise HTTPException(409, NO_PARENT)
            if body.get("confirm") != "exact":
                # the code is what the page arms its second press on; any other refusal is only words
                raise HTTPException(409, {"code": "share_warning", "text": SHARE_WARNING})
            # pushed_at cleared: the next push sends it whole, whatever the parent had before
            cur.execute("""UPDATE place_maps SET shared = true, held = false, shared_at = now(), share_error = NULL,
                             pushed_at = NULL, push_tried_at = NULL WHERE id = %s""", (map_id,))
            cur.execute("DELETE FROM place_maps_unshared WHERE map_id = %s", (map_id,))
            ledger(cur, _actor(request, body), "shared", sets.get("name", m["name"]), f"map:{map_id}")
        elif body.get("shared") is False and m["shared"]:
            _owe_delete(cur, map_id)
            cur.execute("""UPDATE place_maps SET shared = false, held = false, share_error = NULL, pushed_at = NULL,
                             push_tried_at = NULL WHERE id = %s""", (map_id,))
            ledger(cur, _actor(request, body), "unshared", sets.get("name", m["name"]), f"map:{map_id}")
        return {"map": _shown(_one(cur, _MAP + " WHERE p.id = %s", map_id))}


def _owe_delete(cur, map_id: int) -> None:
    cur.execute("INSERT INTO place_maps_unshared (map_id) VALUES (%s) ON CONFLICT (map_id) DO UPDATE SET tried_at = NULL",
                (map_id,))


@router.delete("/place/maps/{map_id}")
def map_delete(map_id: int, request: Request, confirm: str = Query(""), actor: str = Query("")):
    """?confirm=<the map's name>&actor=<who>. The map goes with every drawing on it."""
    with db() as con, con.transaction(), con.cursor() as cur:
        m = _map(cur, map_id)
        if confirm != m["name"]:
            raise HTTPException(409, "Deleting needs the map's name.")
        if m["shared"]:
            _owe_delete(cur, map_id)
        cur.execute("DELETE FROM place_maps WHERE id = %s", (map_id,))
        ledger(cur, _actor(request, {"actor": actor}), "deleted", m["name"], f"map:{map_id}")
    return {"ok": True}


_MIME = {"geojson": "application/geo+json", "kml": "application/vnd.google-earth.kml+xml", "dxf": "image/vnd.dxf"}


def _slug(text: str) -> str:
    plain = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", plain.lower()).strip("-")


@router.get("/place/maps/{map_id:int}.{ext}")
def map_download(map_id: int, ext: str, request: Request, actor: str = Query("")):
    """.geojson, .kml or .dxf of a map, as a file named <node>-<map>-<date>. DXF is in the metres of the UTM zone the
    node stands in, so it opens in a CAD at a scale. Any map may be read, an agent's too; each download is a ledger row."""
    if ext not in _MIME:
        raise HTTPException(404, "A map downloads as .geojson, .kml or .dxf.")
    node = os.getenv("NODE_NAME", "node")
    with db() as con, con.transaction(), con.cursor() as cur:
        cur.execute("SELECT id, name, owner FROM place_maps WHERE id = %s", (map_id,))
        m = cur.fetchone()
        if not m:
            raise HTTPException(404, "No such map.")
        if ext == "dxf":
            lat, lon = float(os.getenv("NODE_LAT", 0) or 0), float(os.getenv("NODE_LON", 0) or 0)
            if not (lat or lon):
                raise HTTPException(409, "This node has no NODE_LAT and NODE_LON yet, so there is no UTM zone to draw in.")
            epsg = utm_epsg(lon, lat)
            cur.execute("""SELECT kind, colour, label, note, ST_AsGeoJSON(ST_Transform(geom, %s))::json AS g
                             FROM place_marks WHERE map_id = %s ORDER BY id""", (epsg, map_id))
            vertices = {"Point": lambda c: [c], "LineString": lambda c: c, "Polygon": lambda c: c[0]}
            body = to_dxf([{**r, "xy": vertices[r["g"]["type"]](r["g"]["coordinates"])} for r in cur.fetchall()], epsg)
        else:
            cur.execute(_MARK + " WHERE map_id = %s ORDER BY id", (map_id,))
            fc = feature_collection(m, cur.fetchall(), node)
            body = json.dumps(fc) if ext == "geojson" else to_kml(fc)
        ledger(cur, _actor(request, {"actor": actor}), f"downloaded:{ext}", m["name"], f"map:{map_id}")
    day = datetime.now(ZoneInfo(NODE_TZ)).strftime("%Y-%m-%d")
    return Response(body, media_type=_MIME[ext], headers={
        "Content-Disposition": f'attachment; filename="{_slug(node) or "node"}-{_slug(m["name"]) or "map"}-{day}.{ext}"'})


# ---------------------------------------------------------------- drawings

@router.post("/place/maps/{map_id}/marks")
def mark_new(map_id: int, body: dict, request: Request):
    """A GeoJSON Feature, its `properties` {kind, label?, note?, colour?, image?}, and `actor` beside them → {"mark": …}."""
    with db() as con, con.transaction(), con.cursor() as cur:
        m = _map(cur, map_id)
        if refusal := check_feature(body):
            raise HTTPException(422, refusal)
        kind = body["properties"]["kind"]
        f = {"colour": 1, "label": None, "note": None, "capture_id": None, **_fields(body["properties"])}
        actor = _actor(request, body)
        with _image_here():
            cur.execute("""WITH g AS (SELECT ST_SetSRID(ST_GeomFromGeoJSON(%(g)s::text), 4326) AS geom)
                           INSERT INTO place_marks (map_id, kind, geom, colour, label, note, capture_id, drawn_by, length_m, area_m2)
                           SELECT %(map)s, %(kind)s, geom, %(colour)s, %(label)s, %(note)s, %(capture_id)s, %(actor)s,
                                  CASE WHEN %(kind)s = 'line' THEN ST_Length(geom::geography) END,
                                  CASE WHEN %(kind)s = 'area' THEN ST_Area(geom::geography) END
                             FROM g RETURNING id""",
                        {**f, "g": _geometry(kind, body["geometry"]), "map": map_id, "kind": kind, "actor": actor or None})
        kid = cur.fetchone()["id"]
        cur.execute("UPDATE place_maps SET updated_at = now() WHERE id = %s", (map_id,))
        ledger(cur, actor, "drew", f"{f['label'] or kind} on {m['name']}", f"mark:{kid}")
        return {"mark": _one(cur, _MARK + " WHERE id = %s", kid), **_house_hold(cur, m["shared"], map_id, kid)}


@router.patch("/place/marks/{mark_id}")
def mark_edit(mark_id: int, body: dict, request: Request):
    """{"geometry"?, "label"?, "note"?, "colour"?, "image"?, "issue"?, "words"?, "actor"} → {"mark": …}.
    `issue` ties the drawing to an open issue ({"alert_id": A} or {"event_id": E}, with `words`), null unties it."""
    with db() as con, con.transaction(), con.cursor() as cur:
        k = _mark(cur, mark_id)
        f = _fields(body)
        g = None
        if "geometry" in body:
            if refusal := check_feature({"properties": {"kind": k["kind"]}, "geometry": body["geometry"]}):
                raise HTTPException(422, refusal)
            g = _geometry(k["kind"], body["geometry"])
        actor = _actor(request, body)
        if not f and g is None and "issue" not in body:
            return {"mark": _one(cur, _MARK + " WHERE id = %s", mark_id)}    # nothing to change: no row, no resend
        if "issue" in body:
            if request.headers.get("x-agent"):
                raise HTTPException(403, "Only a person ties a drawing to an issue.")   # §8: an agent's suggestion is kept first
            tie(cur, mark_id, body["issue"], body.get("words"), actor)
        with _image_here():
            cur.execute(f"""UPDATE place_marks m SET {''.join(f'{c} = %({c})s, ' for c in f)}geom = COALESCE(g.geom, m.geom),
                              {_MEASURE}, updated_at = now()
                              FROM (SELECT ST_SetSRID(ST_GeomFromGeoJSON(%(g)s::text), 4326) AS geom) g WHERE m.id = %(id)s""",
                        {**f, "g": g, "id": mark_id})
        cur.execute("UPDATE place_maps SET updated_at = now() WHERE id = %s", (k["map_id"],))
        ledger(cur, actor, "changed", f"{f.get('label') or k['label'] or k['kind']} on {k['name']}", f"mark:{mark_id}")
        return {"mark": _one(cur, _MARK + " WHERE id = %s", mark_id),
                **(_house_hold(cur, k["shared"], k["map_id"], mark_id) if g else {})}


@router.delete("/place/marks/{mark_id}")
def mark_delete(mark_id: int, request: Request, actor: str = Query("")):
    """?actor=<who>. An act it was tied to stays in the ledger."""
    with db() as con, con.transaction(), con.cursor() as cur:
        k = _mark(cur, mark_id)
        cur.execute("DELETE FROM place_marks WHERE id = %s", (mark_id,))
        cur.execute("UPDATE place_maps SET updated_at = now() WHERE id = %s", (k["map_id"],))
        ledger(cur, _actor(request, {"actor": actor}), "deleted", f"{k['label'] or k['kind']} on {k['name']}", f"mark:{mark_id}")
    return {"ok": True}


# ---------------------------------------------------------------- sharing upstream (§5)

def push_maps() -> None:
    """Child side, every minute: each shared map changed since it last went up is sent whole (`put`), and each map
    unshared or deleted since is sent as a `delete`. Two changes inside a minute are one put. A failed send keeps the
    map shared, says why in `share_error` and waits an hour; a 404 is a parent from before maps, a 401 or 403 a token
    to fix rather than an hour to wait. A map a drawing on the house holds is never sent until the household presses
    Share again."""
    if not PARENT():          # the function, not the setting: a bare PARENT is always truthy
        return
    node = os.getenv("NODE_NAME", "node")
    with db() as con, con.transaction(), con.cursor() as cur:
        # one snapshot: a drawing on the house and the hold it writes are seen together or not at all
        cur.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")
        cur.execute("SELECT map_id FROM place_maps_unshared WHERE tried_at IS NULL OR tried_at < now() - interval '1 hour'")
        out = [(r["map_id"], "delete", None, None) for r in cur.fetchall()]
        cur.execute("""SELECT id, name, owner, updated_at FROM place_maps
                        WHERE shared AND NOT held AND from_node IS NULL AND (pushed_at IS NULL OR updated_at > pushed_at)
                          AND (share_error IS NULL OR push_tried_at < now() - interval '1 hour')""")
        for m in cur.fetchall():
            cur.execute(_MARK + " WHERE map_id = %s ORDER BY id", (m["id"],))
            marks = cur.fetchall()
            cur.execute(_PHOTO_WORDS, ([k["capture_id"] for k in marks if k["capture_id"]],))
            words = {c["id"]: photo_words(c) for c in cur.fetchall()}
            for k in marks:
                k["photo"] = words.get(k["capture_id"])
            out.append((m["id"], "put", feature_collection(m, marks, node, upstream=True), m["updated_at"]))
    for map_id, op, fc, snap in out:
        try:
            # signed with this node's key (docs/SPEC_identity.md §8); a parent that refuses the key says why, in a
            # sentence that is the map's share_error until the parent's keeper does what it says
            r = identity.post(PARENT(), "/place/maps/received",
                              {"schema": _SCHEMA, "node": node, "map_id": map_id, "op": op, "geojson": fc}, PARENT_TOKEN())
            why = identity.refusal(r) if r.status_code >= 400 else ""
            # a parent refuses the token with 403 or with a 401 that names it; any other 401 or a 409 is about the key
            token = r.status_code == 403 or r.status_code == 401 and (not why or "AGGREGATE_TOKEN" in why)
            error = NOT_YET if r.status_code == 404 else NO_TOKEN if token else why if r.status_code in (401, 409) else None
            if not error:
                r.raise_for_status()
        except Exception as e:  # noqa: BLE001
            log.warning("map %s %s to parent failed: %s", map_id, op, e)
            error = NOT_SENT
        with db() as con, con.cursor() as cur:
            if op == "delete" and error in (NOT_SENT, NO_TOKEN):
                cur.execute("UPDATE place_maps_unshared SET tried_at = now() WHERE map_id = %s", (map_id,))
            elif op == "delete":                           # sent, or a parent with no maps to delete it from
                cur.execute("DELETE FROM place_maps_unshared WHERE map_id = %s", (map_id,))
            else:
                # pushed_at is the snapshot's own time, so a change made while this was in flight goes next minute;
                # `held` is not touched, so a hold written meanwhile stays a hold
                cur.execute("""UPDATE place_maps SET push_tried_at = now(), share_error = %(err)s,
                                 pushed_at = CASE WHEN %(err)s::text IS NULL THEN %(snap)s ELSE pushed_at END
                                WHERE id = %(id)s AND shared""", {"err": error, "snap": snap, "id": map_id})
    _answers()


async def _raw_body(request: Request) -> bytes:
    """The bytes the child signed. FastAPI keeps the body it read for `body: dict`, so this is the same bytes."""
    return await request.body()


@received.post("/place/maps/received")
def map_received(body: dict, request: Request, raw: bytes = Depends(_raw_body), authorization: str = Header("")):
    """Parent side. {schema, node, map_id, op: "put" | "delete", geojson}: a child's shared map, kept whole under
    (from_node, remote_id) and read-only here. A put replaces every drawing; a delete removes the map. Measures are
    PostGIS's own again. A picture's number is the child's: it is kept with the photo's words as `photo`, and the
    file comes only when somebody here asks and somebody there sends it (§14)."""
    if not AGG_TOKEN():
        raise HTTPException(403, "this node accepts no children: set AGGREGATE_TOKEN in .env and give it to them")
    if not _bearer_ok(authorization, AGG_TOKEN()):
        raise HTTPException(401, "bad or missing Authorization: Bearer <AGGREGATE_TOKEN>")
    child, rid, op = _text(body.get("node"), 80), body.get("map_id"), body.get("op")
    if not child or isinstance(rid, bool) or not isinstance(rid, int) or op not in ("put", "delete"):
        raise HTTPException(422, "A shared map says its node, its map_id and put or delete.")
    feats = []
    with db() as con, con.transaction(), con.cursor() as cur:
        # the key pinned to this name, and no other, may write under it (docs/SPEC_identity.md §5); its ID owns the map
        owner = identity.admit(cur, child, "/place/maps/received", raw, request.headers) or child
        if op == "delete":
            cur.execute("DELETE FROM place_maps WHERE from_node = %s AND remote_id = %s", (child, rid))
        else:
            fc = body.get("geojson") if isinstance(body.get("geojson"), dict) else {}
            feats = fc.get("features") if isinstance(fc.get("features"), list) else []
            if len(feats) > MAX_DRAWINGS or sum(map(_points, feats)) > MAX_MAP_POINTS:
                raise HTTPException(413, TOO_BIG)              # before any outline is compared with itself
            for f in feats:
                if refusal := check_feature(f):
                    raise HTTPException(422, refusal)
                if "colour" in f["properties"]:
                    _fields({"colour": f["properties"]["colour"]})
                f["properties"]["photo"] = photo_in(f["properties"].get("image"), f["properties"].get("photo"))
            cur.execute("""INSERT INTO place_maps (name, owner, from_node, remote_id) VALUES (%s, %s, %s, %s)
                           ON CONFLICT (from_node, remote_id) DO UPDATE SET name = EXCLUDED.name, owner = EXCLUDED.owner,
                                                                            updated_at = now()
                           RETURNING id""", (_text(fc.get("map"), 80) or "map", owner, child, rid))   # the child node owns it, never a person
            mid = cur.fetchone()["id"]
            cur.execute("DELETE FROM place_marks WHERE map_id = %s", (mid,))
            for f in feats:
                p, kind = f["properties"], f["properties"]["kind"]
                colour = p.get("colour", 1)
                cur.execute("""WITH g AS (SELECT ST_SetSRID(ST_GeomFromGeoJSON(%(g)s::text), 4326) AS geom)
                               INSERT INTO place_marks (map_id, kind, geom, colour, label, note, photo, length_m, area_m2)
                               SELECT %(map)s, %(kind)s, geom, %(colour)s, %(label)s, %(note)s, %(photo)s,
                                      CASE WHEN %(kind)s = 'line' THEN ST_Length(geom::geography) END,
                                      CASE WHEN %(kind)s = 'area' THEN ST_Area(geom::geography) END FROM g""",
                            {"g": _geometry(kind, f["geometry"]), "map": mid, "kind": kind, "colour": colour,
                             "label": _text(p.get("label"), 80), "note": _text(p.get("note"), 500),
                             "photo": Jsonb(p["photo"]) if p["photo"] else None})
        gone = _forget(cur, child)                        # a photo no map of the child carries any more
    _unlink(gone)
    return {"ok": True} if op == "delete" else {"ok": True, "marks": len(feats)}


# ---------------------------------------------------------------- photos on demand (§14)

def _forget(cur, child: str) -> list[str]:
    """Parent side: a child's photo is kept only while it is on a drawing of that child's this node holds. An ask
    whose photo is no longer on one turns `gone`, its file with it. Returns the files to delete once committed."""
    cur.execute("""WITH g AS (SELECT a.id, a.file FROM place_photo_asks a
                               WHERE a.from_node = %s AND a.state IN ('asked', 'sent') AND NOT EXISTS (
                                     SELECT 1 FROM place_marks k JOIN place_maps m ON m.id = k.map_id
                                      WHERE m.from_node = a.from_node AND (k.photo->>'ref')::bigint = a.ref)
                               FOR UPDATE)
                   UPDATE place_photo_asks a SET state = 'gone', answered_at = now(), file = NULL FROM g WHERE a.id = g.id
                   RETURNING a.id, g.file, a.label""", (child,))
    rows = cur.fetchall()
    for r in rows:
        ledger(cur, child, "photo:gone", f"the photo on {r['label'] or 'a drawing'} is no longer shared", f"ask:{r['id']}")
    return [r["file"] for r in rows if r["file"]]


def _unlink(files: list[str]) -> None:
    for f in files:
        try:
            os.remove(os.path.join(_PHOTO_DIR(), "received", os.path.basename(f)))
        except OSError:
            pass                                           # already gone is gone


def _ask_out(a: dict) -> dict:
    return {k: (v.isoformat() if isinstance(v, datetime) else v) for k, v in a.items() if k not in ("file",)}


@router.post("/place/marks/{mark_id}/ask")
def photo_ask(mark_id: int, body: dict, request: Request):
    """Parent side. {"actor"} → {"ask": …}: ask the child for the file of the photo on one of its drawings. One ask a
    photo; asking again while it waits, or after it came, changes nothing, and after a No or a gone it opens again."""
    with db() as con, con.transaction(), con.cursor() as cur:
        k = _one(cur, """SELECT k.label, k.photo, m.name, m.from_node FROM place_marks k JOIN place_maps m ON m.id = k.map_id
                          WHERE k.id = %s""", mark_id)
        if not k:
            raise HTTPException(404, "No such drawing.")
        if not k["from_node"]:
            raise HTTPException(409, "This drawing is this node's own: its image is here already.")
        if not k["photo"]:
            raise HTTPException(409, "This drawing carries no photo.")
        actor = _actor(request, body)
        cur.execute("""INSERT INTO place_photo_asks (from_node, ref, label, map_name, asked_by) VALUES (%s, %s, %s, %s, %s)
                       ON CONFLICT (from_node, ref) DO UPDATE SET state = 'asked', asked_by = EXCLUDED.asked_by,
                              asked_at = now(), answered_at = NULL, label = EXCLUDED.label, map_name = EXCLUDED.map_name
                        WHERE place_photo_asks.state IN ('no', 'gone')
                       RETURNING *""", (k["from_node"], k["photo"]["ref"], k["label"], k["name"], actor or None))
        a = cur.fetchone()
        if a:
            ledger(cur, actor, "photo:asked", f"the photo on {k['label'] or 'a drawing'} from {k['from_node']}", f"ask:{a['id']}")
        else:                                              # waiting, or come: as it is
            cur.execute("SELECT * FROM place_photo_asks WHERE from_node = %s AND ref = %s", (k["from_node"], k["photo"]["ref"]))
            a = cur.fetchone()
        return {"ask": _ask_out(a)}


@router.get("/place/marks/{mark_id}/photo")
def mark_photo(mark_id: int):
    """Parent side: the file a child sent for the photo on this drawing, to this node's own token holders only."""
    rows = _q1("""SELECT a.file, a.mime FROM place_marks k JOIN place_maps m ON m.id = k.map_id
                   JOIN place_photo_asks a ON a.from_node = m.from_node AND a.ref = (k.photo->>'ref')::bigint
                  WHERE k.id = %s AND a.state = 'sent'""", mark_id)
    path = rows and os.path.join(_PHOTO_DIR(), "received", os.path.basename(rows["file"]))
    if not path or not os.path.isfile(path):
        raise HTTPException(404, "No photo has come for this drawing.")
    return FileResponse(path, media_type=rows["mime"])


def _q1(sql: str, *args):
    with db() as con, con.cursor() as cur:
        cur.execute(sql, args)
        return cur.fetchone()


def asks_for(child: str) -> dict:
    """Parent side, in the answer to a child's hourly /aggregates push: what this node is waiting for from that child.
    A parent cannot reach a home node, so this is how an ask goes down. Never fails the push it rides on."""
    try:
        with db() as con, con.cursor() as cur:
            cur.execute("""SELECT id, ref, asked_by, asked_at FROM place_photo_asks
                            WHERE from_node = %s AND state = 'asked' ORDER BY id LIMIT 50""", (child,))
            node = os.getenv("NODE_NAME", "node")
            return {"photo_asks": [{"id": a["id"], "image": a["ref"], "node": node, "by": a["asked_by"],
                                    "at": a["asked_at"].isoformat()} for a in cur.fetchall()]}
    except Exception as e:  # noqa: BLE001
        log.warning("photo asks for %s: %s", child, e)
        return {}


def take_asks(reply) -> None:
    """Child side: the asks the node upstream sent back with its answer to this node's push. Each is kept once and is a
    ledger row; one the parent opened again after a No (a new time) waits for an answer again."""
    asks = reply.get("photo_asks") if isinstance(reply, dict) else None
    if not isinstance(asks, list) or not PARENT():
        return
    ok = lambda x: isinstance(x, int) and not isinstance(x, bool)   # noqa: E731
    with db() as con, con.transaction(), con.cursor() as cur:
        for a in asks[:50]:
            if not (isinstance(a, dict) and ok(a.get("id")) and ok(a.get("image"))):
                continue
            try:
                at = datetime.fromisoformat(str(a.get("at")))
            except ValueError:
                at = None
            node, by = _text(a.get("node"), 80) or "the node upstream", _text(a.get("by"), 80)
            cur.execute("""INSERT INTO place_photo_asks_in (parent, ask_id, node, asked_by, asked_at, capture_id)
                           VALUES (%s, %s, %s, %s, %s, %s)
                           ON CONFLICT (parent, ask_id) DO UPDATE SET node = EXCLUDED.node, asked_by = EXCLUDED.asked_by,
                                  asked_at = EXCLUDED.asked_at, capture_id = EXCLUDED.capture_id, got_at = now(),
                                  answer = NULL, answered_by = NULL, answered_at = NULL, sent_at = NULL,
                                  tried_at = NULL, error = NULL
                            WHERE place_photo_asks_in.asked_at IS DISTINCT FROM EXCLUDED.asked_at
                           RETURNING id""", (PARENT(), a["id"], node, by, at, a["image"]))
            r = cur.fetchone()
            if r:
                ledger(cur, node, "photo:asked", f"{by or 'somebody'} at {node} asked for a photo", f"ask:{r['id']}")


_ON_SHARED = """EXISTS (SELECT 1 FROM place_marks k JOIN place_maps m ON m.id = k.map_id
                         WHERE k.capture_id = a.capture_id AND m.shared AND m.agent IS NULL AND m.from_node IS NULL)"""


@router.get("/place/photos/asks")
def photo_asks():
    """Child side: the asks waiting for somebody here, each with the shared drawings that carry the photo."""
    with db() as con, con.cursor() as cur:
        cur.execute("""SELECT a.id, a.node, a.asked_by, a.asked_at, a.capture_id,
                              json_agg(json_build_object('mark', k.id, 'label', k.label, 'kind', k.kind, 'map', m.name)
                                       ORDER BY k.id) AS drawings
                         FROM place_photo_asks_in a JOIN place_marks k ON k.capture_id = a.capture_id
                         JOIN place_maps m ON m.id = k.map_id AND m.shared AND m.agent IS NULL AND m.from_node IS NULL
                        WHERE a.answer IS NULL AND a.parent = %s GROUP BY a.id ORDER BY a.got_at""", (PARENT() or "",))
        return {"asks": cur.fetchall()}


@router.post("/place/photos/asks/{ask_id}")
def photo_answer(ask_id: int, body: dict, request: Request):
    """Child side. {"answer": "send" | "no", "actor"} → {"ok": true}. Only a person at home answers: the file leaves
    only when somebody presses Send. It goes within the minute, once (push_maps)."""
    answer = body.get("answer")
    if answer not in ("send", "no"):
        raise HTTPException(422, "Answer send or no.")
    if request.headers.get("x-agent"):
        raise HTTPException(403, "Only a person at home answers for a photo.")
    with db() as con, con.transaction(), con.cursor() as cur:
        cur.execute(f"""SELECT a.id, a.node, a.answer, {_ON_SHARED} AS shared FROM place_photo_asks_in a
                         WHERE a.id = %s FOR UPDATE""", (ask_id,))
        a = cur.fetchone()
        if not a:
            raise HTTPException(404, _NO_ASK)
        if a["answer"]:
            raise HTTPException(409, "This ask is answered already.")
        if not a["shared"]:
            raise HTTPException(409, "That photo is no longer on a shared map, so there is nothing to send.")
        actor = _actor(request, body)
        cur.execute("UPDATE place_photo_asks_in SET answer = %s, answered_by = %s, answered_at = now() WHERE id = %s",
                    (answer, actor or None, ask_id))
        ledger(cur, actor, "photo:sent" if answer == "send" else "photo:no",
               f"{'sent' if answer == 'send' else 'kept'} the photo {'to' if answer == 'send' else 'from'} {a['node']}", f"ask:{ask_id}")
    return {"ok": True}


def _answer(row: dict, path: str | None):
    """One answer up to the node upstream, signed as the maps are (docs/SPEC_identity.md §8). The picture rides in it,
    as base64, only on a Send, so the signature covers the file too."""
    pic = None
    if path:
        with open(path, "rb") as fh:
            pic = base64.b64encode(fh.read()).decode()
    return identity.post(PARENT(), "/place/photos/received",
                         {"schema": _PHOTOS, "node": os.getenv("NODE_NAME", "node"), "ask": row["ask_id"],
                          "image": row["capture_id"], "answer": "sent" if path else row["answer"], "picture": pic},
                         PARENT_TOKEN())


def _answers() -> None:
    """Child side, after the map pushes: an unanswered ask, or a Send not yet gone, for a photo no longer on a shared
    drawing is answered `gone` by the node; then every answer not yet taken goes up, once."""
    if not PARENT():
        return
    with db() as con, con.transaction(), con.cursor() as cur:
        cur.execute(f"""UPDATE place_photo_asks_in a SET answer = 'gone', answered_by = NULL, answered_at = now()
                         WHERE (a.answer IS NULL OR a.answer = 'send') AND a.sent_at IS NULL AND NOT {_ON_SHARED}
                        RETURNING a.id, a.node""")
        for r in cur.fetchall():
            ledger(cur, "this node", "photo:gone", f"the photo {r['node']} asked for is no longer shared", f"ask:{r['id']}")
        cur.execute("""SELECT id, ask_id, capture_id, answer FROM place_photo_asks_in
                        WHERE answer IS NOT NULL AND sent_at IS NULL AND parent = %s
                          AND (tried_at IS NULL OR tried_at < now() - interval '1 hour') ORDER BY id""", (PARENT(),))
        todo = cur.fetchall()
        files = {}
        for r in todo:
            if r["answer"] == "send":
                cur.execute(_PHOTO_FILE, (r["capture_id"],))
                f = cur.fetchone()
                path = f and os.path.join(_PHOTO_DIR(), os.path.basename(f["file"]))
                files[r["id"]] = path if path and os.path.isfile(path) else None
    for r in todo:
        path = files.get(r["id"])
        if r["answer"] == "send" and not path:
            r = {**r, "answer": "gone"}                    # pressed Send, and the file went before it could
        try:
            resp = _answer(r, path)
            why = identity.refusal(resp) if resp.status_code >= 400 else ""
            token = resp.status_code == 403 or resp.status_code == 401 and (not why or "AGGREGATE_TOKEN" in why)
            # the parent no longer wants it (done), the token is wrong, or the key is refused and says why (as push_maps)
            error = None if why in (_NO_ASK, _CLOSED) else NO_TOKEN if token else why if resp.status_code in (401, 409) else None
            if not error and why not in (_NO_ASK, _CLOSED):
                resp.raise_for_status()
        except Exception as e:  # noqa: BLE001
            log.warning("photo answer %s to parent failed: %s", r["id"], e)
            error = NOT_SENT
        with db() as con, con.cursor() as cur:
            cur.execute("""UPDATE place_photo_asks_in SET tried_at = now(), error = %(err)s, answer = %(answer)s,
                                  sent_at = CASE WHEN %(err)s::text IS NULL THEN now() END WHERE id = %(id)s""",
                        {"err": error, "answer": r["answer"], "id": r["id"]})


def _picture(raw: bytes) -> tuple[bytes, str, str]:
    """Parent side: a child's file, opened as a picture and written again with no metadata, whatever the child did."""
    import io  # noqa: PLC0415
    from PIL import Image  # noqa: PLC0415
    try:
        im = Image.open(io.BytesIO(raw))
        im.load()
    except Exception:  # noqa: BLE001
        raise HTTPException(422, "That file is not a picture.") from None
    fmt = {"JPEG": ("JPEG", "image/jpeg", "jpg"), "PNG": ("PNG", "image/png", "png"), "WEBP": ("WEBP", "image/webp", "webp")}.get(im.format or "")
    if not fmt:
        raise HTTPException(422, "A photo comes as JPEG, PNG or WebP.")
    out = io.BytesIO()
    (im.convert("RGB") if fmt[0] == "JPEG" else im).save(out, fmt[0], quality=90)
    return out.getvalue(), fmt[1], fmt[2]


@received.post("/place/photos/received")
def photo_received(body: dict, request: Request, raw: bytes = Depends(_raw_body), authorization: str = Header("")):
    """Parent side, AGGREGATE_TOKEN only, signed as the maps are. A child's answer to an ask: `sent` with the picture
    as base64, `no`, or `gone`. The ask must be that child's, for that photo, still waiting, and the photo still on a
    drawing this node holds."""
    if not AGG_TOKEN():
        raise HTTPException(403, "this node accepts no children: set AGGREGATE_TOKEN in .env and give it to them")
    if not _bearer_ok(authorization, AGG_TOKEN()):
        raise HTTPException(401, "bad or missing Authorization: Bearer <AGGREGATE_TOKEN>")
    child, ask, image, answer = _text(body.get("node"), 80), body.get("ask"), body.get("image"), body.get("answer")
    if not child or any(isinstance(x, bool) or not isinstance(x, int) for x in (ask, image)) \
            or answer not in ("sent", "no", "gone"):
        raise HTTPException(422, "An answer says its node, its ask, its image, and sent, no or gone.")
    pic = None
    if answer == "sent":
        b64 = body.get("picture")
        if not isinstance(b64, str) or not b64:
            raise HTTPException(422, "A photo sent comes with its picture.")
        if len(b64) > (MAX_PHOTO + 2) // 3 * 4:
            raise HTTPException(413, "A photo is 25 MB at most.")
        try:
            pic = base64.b64decode(b64, validate=True)
        except ValueError:
            raise HTTPException(422, "That file is not a picture.") from None
    kept, gone = None, []
    with db() as con, con.transaction(), con.cursor() as cur:
        identity.admit(cur, child, "/place/photos/received", raw, request.headers)   # the key pinned to this name, as a map
        cur.execute("SELECT id, state, label FROM place_photo_asks WHERE id = %s AND from_node = %s AND ref = %s FOR UPDATE",
                    (ask, child, image))
        a = cur.fetchone()
        if not a:
            raise HTTPException(404, _NO_ASK)
        if a["state"] != "asked":
            raise HTTPException(409, _CLOSED)
        gone = _forget(cur, child)
        cur.execute("SELECT state FROM place_photo_asks WHERE id = %s", (ask,))
        if cur.fetchone()["state"] != "asked":              # _forget just closed it: the photo is no longer here
            kept = "gone"
        elif pic:
            pic, mime, ext = _picture(pic)
            name = f"{sha256(pic).hexdigest()}.{ext}"
            os.makedirs(os.path.join(_PHOTO_DIR(), "received"), exist_ok=True)
            with open(os.path.join(_PHOTO_DIR(), "received", name), "wb") as f:
                f.write(pic)
            cur.execute("""UPDATE place_photo_asks SET state = 'sent', answered_at = now(), file = %s, mime = %s, bytes = %s
                            WHERE id = %s""", (name, mime, len(pic), ask))
            kept = "sent"
            ledger(cur, child, "photo:received", f"the photo on {a['label'] or 'a drawing'}", f"ask:{ask}")
        else:
            cur.execute("UPDATE place_photo_asks SET state = %s, answered_at = now() WHERE id = %s", (answer, ask))
            kept = answer
            ledger(cur, child, f"photo:{answer}", f"the photo on {a['label'] or 'a drawing'}", f"ask:{ask}")
    _unlink(gone)
    return {"ok": True, "state": kept}


def daily_readings() -> None:
    """Hourly, once a local day: how many drawings the household has made and how much ground they cover, on the
    node's own `place-gis` survey sensor. Both are `private` (config/channels.yml), so no road out of the house carries
    them. The reading's time is the start of the node's local day (the session runs in NODE_TZ), so a later call the
    same day updates that row and a duplicate is impossible. Nothing is written, and no sensor made, until the
    household has drawn something. An agent's map and a child's are not the household's."""
    with db() as con, con.transaction(), con.cursor() as cur:
        cur.execute("""SELECT EXISTS (SELECT 1 FROM sensors WHERE sensor_id = 'place-gis') AS known,
                              EXISTS (SELECT 1 FROM place_marks k JOIN place_maps m ON m.id = k.map_id
                                       WHERE m.agent IS NULL AND m.from_node IS NULL) AS drew""")
        if not any(cur.fetchone().values()):
            return          # a node that never drew has no sensor and no zeros; once it has one, it keeps writing
        cur.execute("""INSERT INTO sensors (sensor_id, source, name, kind, local, indoor, cadence)
                       VALUES ('place-gis', 'place', 'What this home has drawn', 'survey', TRUE, FALSE, 'P1D')
                       ON CONFLICT (sensor_id) DO NOTHING""")
        cur.execute("""SELECT count(*) AS marks, coalesce(sum(k.area_m2), 0) AS marked_area_m2
                         FROM place_marks k JOIN place_maps m ON m.id = k.map_id
                        WHERE m.agent IS NULL AND m.from_node IS NULL""")
        n = cur.fetchone()
        for metric in ("marks", "marked_area_m2"):
            cur.execute("INSERT INTO readings (ts, sensor_id, metric, value) VALUES (date_trunc('day', now()), 'place-gis', %s, %s) "
                        "ON CONFLICT (sensor_id, metric, ts) DO UPDATE SET value = EXCLUDED.value", (metric, float(n[metric])))
