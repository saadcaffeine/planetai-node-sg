"""Place maps without a database: what a drawing must be before it is stored, and the palette the server holds.

A drawing arrives as a GeoJSON Feature from the page, an agent or curl, and app/maps.py refuses one that is not what
its kind says, in a sentence the page shows as it is. The route-level half, against Postgres, is
tests/test_maps_pg.py. Run: PYTHONPATH=app python3 tests/test_maps.py
"""
import os
import sys
import xml.etree.ElementTree as ET

os.environ.setdefault("DATABASE_URL", "postgresql://unused/never-connected")   # db.py opens nothing at import
from fastapi import HTTPException  # noqa: E402
from maps import PALETTE, _fields, check_feature, feature_collection, photo_in, photo_words, to_dxf, to_kml, utm_epsg  # noqa: E402


def feature(kind, gtype, coords):
    return {"type": "Feature", "properties": {"kind": kind}, "geometry": {"type": gtype, "coordinates": coords}}


def area(ring):
    return feature("area", "Polygon", [ring])


def marker(lon, lat):
    return feature("marker", "Point", [lon, lat])


assert check_feature(feature("line", "LineString", [[115.1, -8.8]])) == "A line needs two points or more."
assert check_feature(feature("line", "LineString", [[115.1, -8.8], [115.1, -8.8]])) == "A line needs two points or more."
assert check_feature(feature("line", "LineString", [[115.1, -8.8], [115.2, -8.8]])) is None
assert check_feature(area([[0, 0], [1, 1], [1, 0], [0, 1], [0, 0]])) == "That area crosses itself. Draw its corners in order around it."
assert check_feature(area([[0, 0], [1, 0], [0, 0]])) == "An area needs three corners or more."
assert check_feature(area([[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]])) is None
assert check_feature(area([[0, 0], [1, 0], [1, 1], [0, 1]])) is None, "an outline left open is closed, not refused"
assert check_feature(area([[0, 0], [1, 0], [1, 0], [1, 1], [0, 0]])) is None, "a corner tapped twice is one corner"
print("  lines and areas: point counts, and an area that crosses itself")

assert check_feature(marker(115.167, -8.819)) is None
assert check_feature(feature("note", "Point", [115.167, -8.819])) is None
assert check_feature(feature("marker", "LineString", [[0, 0], [1, 1]])) == "A marker is one point."
assert check_feature(feature("note", "Polygon", [[[0, 0], [1, 0], [1, 1], [0, 0]]])) == "A note is one point."
assert check_feature(feature("circle", "Point", [0, 0])) == "A drawing is a marker, a line, an area or a note."
for bad in (marker(200, 0), marker(0, -91), marker("115", -8.8), marker(float("nan"), 0), feature("marker", "Point", [1]),
            feature("line", "LineString", [[0, 0], [True, 1]])):
    assert check_feature(bad) == "Every point needs a longitude and a latitude.", bad
for bad in (None, [], {"type": "Feature"}, {"type": "Feature", "properties": {"kind": "line"}, "geometry": None}):
    assert isinstance(check_feature(bad), str), bad          # refused in words, never a 500
print("  markers and notes are one point; kinds, coordinates and shapes that are not GeoJSON are refused in words")

# A drawing's corners are checked against each other, O(n²), on a request thread: a drawing has a ceiling, here and on
# the parent's /place/maps/received, before that check runs.
_long = [[115 + i * 1e-5, -8.8] for i in range(1001)]
assert check_feature(feature("line", "LineString", _long)) == "A drawing has 1,000 points at most.", "1,001 points are refused"
assert check_feature(feature("line", "LineString", _long[:1000])) is None, "1,000 points are a drawing"
for bad in ([2], "2", 2.5, True, 7, None):
    try:
        _fields({"colour": bad}); raise AssertionError(f"colour {bad!r} was taken")
    except HTTPException as e:
        assert e.status_code == 422 and e.detail == "A colour is a number from 1 to 6.", (bad, e.detail)   # never a 500
print("  a drawing has 1,000 points at most; a colour that is not 1 to 6, a list included, is refused in words")

assert set(PALETTE) == {1, 2, 3, 4, 5, 6} and all(h.startswith("#") and 1 <= aci <= 255 for h, aci in PALETTE.values())
assert len({h.lower() for h, _ in PALETTE.values()}) == 6 and len({a for _, a in PALETTE.values()}) == 6
print("  six colours, each a hex for the screen and an ACI number for DXF")

# ---------------------------------------------------------------- the downloads

def mark_row(**over):
    """A row as place_marks gives it back, with a geometry in WGS84."""
    ring = [[115.167, -8.819], [115.168, -8.819], [115.168, -8.818], [115.167, -8.819]]
    return {"id": 1, "kind": "marker", "colour": 1, "label": None, "note": None, "capture_id": None, "length_m": None,
            "area_m2": None, "drawn_by": "Tomas", "updated_at": None, "geometry": {"type": "Polygon", "coordinates": [ring]}, **over}


assert utm_epsg(115.167, -8.819) == 32750 and utm_epsg(2.17, 41.39) == 32631 and utm_epsg(-179.9, 10) == 32601
assert utm_epsg(180, 1) == 32660, "the antimeridian is zone 60, not 61"
fc = feature_collection({"id": 3, "name": "Garden plan", "owner": "Tomas"},
                        [mark_row(kind="area", label='Rain <garden> & "pond"', colour=3, capture_id=9)], "bayu-ungasan")
assert fc["schema"] == "planetai.place.map/v0" and fc["map"] == "Garden plan" and fc["node"] == "bayu-ungasan"
assert fc["owner"] == "Tomas" and fc["type"] == "FeatureCollection"
p = fc["features"][0]["properties"]
# the household's own download keeps who drew each drawing; what goes to the node upstream names nobody
assert set(p) == {"kind", "label", "note", "colour", "colour_hex", "length_m", "area_m2", "image", "drawn_by", "updated_at"}, p
assert p["drawn_by"] == "Tomas"
up = feature_collection({"id": 3, "name": "Garden plan", "owner": "Tomas"}, [mark_row(kind="area")], "bayu-ungasan", upstream=True)
assert set(up["features"][0]["properties"]) == set(p) - {"drawn_by"}, up["features"][0]["properties"]
assert up["owner"] == "bayu-ungasan", "upstream, the node is the map's owner, never a person"
assert p["colour_hex"] == PALETTE[3][0] and p["image"] == 9 and fc["features"][0]["geometry"]["type"] == "Polygon"
k = to_kml(fc)
ET.fromstring(k)                                          # valid XML with the hostile label
assert "Rain &lt;garden&gt; &amp;" in k
ns = {"k": "http://www.opengis.net/kml/2.2"}
assert len(ET.fromstring(k).findall(".//k:Placemark", ns)) == 1 and ET.fromstring(k).find(".//k:Polygon", ns) is not None
pts = feature_collection({"id": 3, "name": "m", "owner": None},
                         [mark_row(geometry={"type": "Point", "coordinates": [115.1, -8.8]}),
                          mark_row(kind="line", geometry={"type": "LineString", "coordinates": [[115.1, -8.8], [115.2, -8.8]]})], "n")
assert ET.fromstring(to_kml(pts)).find(".//k:Point/k:coordinates", ns).text == "115.1,-8.8"
assert ET.fromstring(to_kml(pts)).find(".//k:LineString/k:coordinates", ns).text == "115.1,-8.8 115.2,-8.8"
print("  GeoJSON carries the contract's properties, without drawn_by upstream; KML is valid XML for a hostile label")

ring = [[500000, 9025000], [500010, 9025000], [500010, 9025010], [500000, 9025000]]
d = to_dxf([{"kind": "area", "label": "two\nlines", "note": "", "colour": 3, "xy": ring}], 32750)
assert d.startswith("999\nEPSG:32750") and "\nAREAS\n" in d and "two lines" in d and d.rstrip().endswith("EOF")
assert d.count("\nPOLYLINE\n") == 1 and d.count("\nVERTEX\n") == 4 and d.count("\nSEQEND\n") == 1
assert "\n70\n1\n0\nVERTEX" in d, "an area's polyline is closed (flag 1)"
assert "\n62\n70\n" in d, "the drawing's ACI colour"
d = to_dxf([{"kind": "marker", "label": "Pozo", "note": "Año 2026", "colour": 1, "xy": [[500000, 9025000]]},
            {"kind": "line", "label": None, "note": None, "colour": 2, "xy": [[1, 2], [3, 4]]}], 32750)
assert d.count("\nPOINT\n") == 1 and d.count("\nPOLYLINE\n") == 1 and "\n70\n0\n0\nVERTEX" in d
assert "A\\U+00F1o 2026" in d and d.isascii(), "DXF R12 is ASCII; ñ is written the way AutoCAD writes it"
assert d.count("\nTEXT\n") == 2 and "Pozo" in d, "a label and a note are each a TEXT"
print("  DXF is R12: EPSG comment, layers, points, polylines closed for areas, text, ASCII")

# A shared drawing's photo (light GIS §14): the words go up, never where, who or the file; the parent checks them.
from datetime import datetime, timezone  # noqa: E402
cap = {"id": 7, "kind": "drone", "note": "north field", "meta": {"crop": "rice"}, "lat": -8.7, "lon": 115.2, "actor": "Tomas",
       "file": "x.jpg", "ts": datetime(2026, 11, 5, 3, 0, tzinfo=timezone.utc)}
w = photo_words(cap)
assert set(w) == {"kind", "note", "meta", "taken"} and w["kind"] == "drone" and w["meta"] == {"crop": "rice"}, w
assert w["taken"] in ("2026-11-04", "2026-11-05") and len(w["taken"]) == 10, "the day, never the hour"
assert photo_words({**cap, "ts": None, "meta": None}) == {"kind": "drone", "note": "north field", "meta": {}, "taken": None}
fc = feature_collection({"name": "m", "owner": "Tomas"}, [{"kind": "marker", "colour": 1, "capture_id": 7, "photo": w,
                         "drawn_by": "Tomas", "geometry": {"type": "Point", "coordinates": [0, 0]}}], "n", upstream=True)
assert fc["features"][0]["properties"]["photo"] == w and fc["features"][0]["properties"]["image"] == 7
assert "photo" not in feature_collection({"name": "m"}, [{"kind": "marker", "colour": 1, "geometry": {"type": "Point", "coordinates": [0, 0]}}],
                                         "n", upstream=True)["features"][0]["properties"], "no image, no photo"
assert photo_in(7, {**w, "meta": {"k" * 80: "v" * 900}}) == {"ref": 7, "kind": "drone", "note": "north field",
                                                             "meta": {"k" * 60: "v" * 500}, "taken": w["taken"]}
assert photo_in(None, w) is None and photo_in(7, None) is None, "an older child sends a number and no words"
for image, photo in ((True, w), ("7", w), (7, "a photo"), (7, {**w, "kind": "selfie"}), (7, {**w, "taken": "5 Nov"}),
                     (7, {**w, "meta": {"a": 1}}), (7, {**w, "meta": {str(i): "x" for i in range(41)}})):
    try:
        photo_in(image, photo)
        raise AssertionError(f"accepted {image!r}, {photo!r}")
    except HTTPException as e:
        assert e.status_code == 422 and "photo" in e.detail, e.detail
print("  a shared photo: the day it was taken, its kind, note and words; the parent refuses anything else")

print("maps: every check passed")
sys.exit(0)
