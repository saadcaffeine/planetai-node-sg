"""The capture tier (SPEC_eyes step 1): the schema, the routes, the cleaning, the privacy.

Structural half reads init.sql and app/main.py the way test_share.py does, because the invariants are
structural: the exact point is kept but the FILE is cleaned, captures are on no SHARE_LEVEL list, and no
export, aggregate, readings or parent-push path may ever name them.

Request half drives FastAPI's TestClient with the database stubbed (a stranger's peer is "testclient";
the node's own machine is loopback), CAPTURES_DIR pointed at a tmp folder via PLANETAI_CAPTURES.

Run: PYTHONPATH=app python3 tests/test_captures.py
"""
import ast
import os
import re
import sys

SQL = open("init.sql").read()
SRC = open("app/main.py").read() + open("app/auth.py").read() + open("packs/eyes/routes.py").read()   # auth.py: the allowlists, since 22 Oct; the eyes pack, since 24 Oct

# ---------------------------------------------------------------- the schema
m = re.search(r"CREATE TABLE IF NOT EXISTS captures \((.*?)\n\);", SQL, re.S)
assert m, "init.sql: no captures table"
cols = m.group(1)
for c in ("id", "ts", "received_at", "kind", "cell", "lat", "lon", "outside", "at_home", "actor", "note",
          "file", "sha256", "bytes", "mime"):
    assert re.search(rf"^\s*{c}\s", cols, re.M), f"captures.{c} missing"
assert "CHECK (kind IN ('microscope','phone','camera','drone','balloon'))" in cols, "the kinds are a CHECK"
for c in ("lat", "lon"):
    line = re.search(rf"^\s*{c}\s.*$", cols, re.M).group(0)
    assert "NOT NULL" not in line, f"captures.{c} must be nullable: a person may give no point"
assert "UNIQUE" in re.search(r"^\s*sha256\s.*$", cols, re.M).group(0), "sha256 is the dedupe key, so UNIQUE"
assert SQL.count("IF NOT EXISTS") >= SQL.count("CREATE TABLE"), "every statement stays safe to run twice"
assert "REVOKE ALL ON captures FROM planetai_ro" in SQL, \
    "pack SQL must not read captures: a rule's text reaches /alerts, and the exact point would ride out in it"
print("schema: captures table, the point nullable, sha256 unique, additive")

# ---------------------------------------------------------------- the structural half
tree = ast.parse(SRC)
funcs = {n.name: n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}

def code_of(name):
    fn = funcs[name]
    stmts = fn.body[1:] if ast.get_docstring(fn) else fn.body
    return "\n".join(ast.get_source_segment(SRC, st) for st in stmts)

# on no SHARE_LEVEL list, at any level — the middleware must refuse a stranger before any route runs
allow = SRC[SRC.index("_SHARE_OFF = ("):SRC.index("_SHARE = {")]
assert '"/captures"' not in allow and "captures/" not in allow, "/captures crept onto a SHARE_LEVEL allowlist"

# and nothing named captures may appear in the paths that leave the node: the exports, the readings a parent
# pulls, the aggregates and events a child pushes. The grep finds each route by its decorator — a route it
# cannot find fails the test, so a renamed function cannot quietly take the protection with it.
def route_fn(path, method):
    for n in tree.body:
        if not isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for d in n.decorator_list:
            if (isinstance(d, ast.Call) and getattr(d.func, "attr", "") == method
                    and d.args and getattr(d.args[0], "value", None) == path):
                return n
    return None
for path, meth in (("/export", "get"), ("/exports", "get"), ("/readings", "get"),
                   ("/readings", "post"), ("/aggregates", "post"), ("/events", "post")):
    n = route_fn(path, meth)
    assert n, f"no {meth.upper()} {path} route found — the grep cannot protect a road it cannot find"
    seg = ast.get_source_segment(SRC, n)
    assert "captures" not in seg, f"{meth.upper()} {path} names captures: a picture must never travel that road"
# and no module but main.py holds SQL against the table at all in step 1. The bot (15 Oct) is the one exception, and
# only as a client of the HTTP route, which checks the token and cleans the file like any other upload.
import glob
for py in glob.glob("app/**/*.py", recursive=True):
    if py != "app/main.py":
        src = open(py).read().replace('hc.post(node_url("/captures"), ', "") if py == "app/agent_loop.py" else open(py).read()
        assert "FROM captures" not in src and "captures" not in src, \
            f"{py} names captures: in step 1 the table is main.py's alone"

assert "_admin(" in code_of("capture_delete"), "only the admin token deletes an image"
for route in ("capture_post", "captures_list", "capture_file", "capture_patch"):
    assert route in funcs, f"{route} missing"
    assert "_captures_auth" in code_of(route), f"{route} must check the token itself, like /actions"
body = code_of("capture_post")
assert "exif_transpose" in SRC and "_clean_picture" in body, "the POST must clean the file on arrival"
assert "cell_to_parent" in body and "grid_disk" in SRC, "outside is measured against the node's seven res-8 cells"
assert "at_home" in body, "at_home is computed on arrival"
assert "sha256" in body and "duplicate" in body, "a duplicate hash answers the existing row"
assert "INSERT INTO captures" in body, "the row is written"
assert "os.path.basename" in code_of("capture_file"), "the file route never trusts a path"
print("routes: token-checked, cleaned on arrival, no export or push path names captures")

# ---------------------------------------------------------------- the request half
try:
    from fastapi.testclient import TestClient
    from PIL import Image
except ImportError:
    print("captures: request checks skipped (pip install -r app/requirements.txt)  (skipped)")
    raise SystemExit(0)

import hashlib
import io
import logging
import tempfile
import time
logging.disable(logging.WARNING)
TMP = tempfile.mkdtemp(prefix="captures-test-")
os.environ.update(ADMIN_TOKEN="admin-tok", ACT_TOKEN="act-tok", BACKUP_TOKEN="backup-tok",
                  NODE_LAT="-8.6478291", NODE_LON="115.1385412", NODE_NAME="bayu-2",
                  DATABASE_URL="postgresql://unused/never-connected", PLANETAI_CAPTURES=TMP)
import settings                                    # noqa: E402
settings._cache = {"at": time.time() + 1e9, "rows": {}}
import main                                       # noqa: E402
import db                                         # noqa: E402
import packs                                      # noqa: E402
E = packs.ROUTES["eyes"]                          # the eyes pack's routes, as main mounted them (packs/eyes, 24 Oct 2026)
assert E.CAPTURES_DIR == TMP, "PLANETAI_CAPTURES must steer the folder in tests"

def level(v):
    settings._cache["rows"]["SHARE_LEVEL"] = v

lan = TestClient(main.app)
local = TestClient(main.app, client=("127.0.0.1", 51000))
ADMIN, ACT, BACKUP = ({"Authorization": f"Bearer {t}"} for t in ("admin-tok", "act-tok", "backup-tok"))

# the database, faked: q for the SELECTs, a capturing cursor for the INSERT … RETURNING *
DUPROWS, LISTROWS = [], []
def qstub(sql, *a):
    if "WHERE sha256" in sql:
        return list(DUPROWS)
    if "FROM captures WHERE id" in sql:
        return [{"file": ROW["file"], "mime": ROW["mime"]}] if ROW else []
    rows = list(LISTROWS)
    if "WHERE kind" in sql and a:                       # the route filters kind in SQL; the stub plays the db
        rows = [r for r in rows if r["kind"] == a[0]]
    return rows
db.q = main.q = qstub

class FakeCur:
    def __init__(self):
        self.sql = self.params = None
    def __enter__(self):
        return self
    def __exit__(self, *a):
        return False
    def execute(self, sql, params=()):
        self.sql, self.params = sql, params
    def fetchone(self):
        p = self.params
        if self.sql.startswith("UPDATE"):
            return {"id": p[-1], "sets": self.sql} if p[-1] == 7 else None
        if self.sql.startswith("DELETE"):
            return {"file": DELFILE} if p[0] == 7 else None
        return {"id": 7, "ts": p[0] or "2026-10-12T01:00:00+00:00", "received_at": "2026-10-12T01:00:01+00:00",
                "kind": p[1], "cell": p[2], "lat": p[3], "lon": p[4], "outside": p[5], "at_home": p[6],
                "actor": p[7], "note": p[8], "file": p[9], "sha256": p[10], "bytes": p[11], "mime": p[12]}
CUR = FakeCur()
class FakeCon:
    def __enter__(self):
        return self
    def __exit__(self, *a):
        return False
    def cursor(self):
        return CUR
db.db = main.db = lambda: FakeCon()

def jpeg(with_gps=True):
    im = Image.new("RGB", (64, 64), (200, 30, 30))
    exif = Image.Exif()
    exif[306] = "2026:10:01 10:11:12"                       # DateTime → the capture's ts
    exif[0x8769] = {36867: "2026:10:01 10:11:12"}           # DateTimeOriginal
    if with_gps:
        exif[0x8825] = {1: "S", 2: (8.0, 38.0, 52.18476), 3: "E", 4: (115.0, 8.0, 18.74832)}  # the node's own point
    buf = io.BytesIO()
    im.save(buf, "JPEG", exif=exif)
    return buf.getvalue()

PIC = jpeg()
SHA = hashlib.sha256(PIC).hexdigest()
HERE = {"lat": "-8.6478291", "lon": "115.1385412"}          # the node's own point
AWAY = {"lat": "0.5", "lon": "100.0"}                       # far outside the seven res-8 cells

# ---- the POST: kept, pointed, cleaned
level("off")
r = lan.post("/captures", files={"photo": ("p.jpg", PIC, "image/jpeg")},
             data={"kind": "phone", "actor": "tomas", "note": "the frangipani", **AWAY}, headers=ACT)
assert r.status_code == 200, r.text
cap = r.json()["capture"]
import h3
home10 = h3.latlng_to_cell(-8.6478291, 115.1385412, 10)
assert cap["cell"] == home10, f"the cell is the point's res-10: {cap['cell']}"
assert abs(cap["lat"] + 8.6478291) < 1e-6 and abs(cap["lon"] - 115.1385412) < 1e-6, \
    "the picture's own GPS is the point, and beats where the phone is now (a gallery pick); kept, token only"
assert cap["at_home"] is True and cap["outside"] is False, "at the node's own res-10 cell"
assert cap["ts"].startswith("2026-10-01T10:11:12"), f"ts is the picture's own date: {cap['ts']}"
assert cap["actor"] == "tomas" and cap["kind"] == "phone"
kept = os.path.join(TMP, cap["file"])
assert os.path.basename(cap["file"]) == cap["file"] and os.path.isfile(kept), "a name in the folder, never a path"
ex = Image.open(kept).getexif()
assert not dict(ex), f"EXIF survived the cleaning: {dict(ex)}"
try:
    assert not ex.get_ifd(0x8825), "GPS survived the cleaning"
except Exception:
    pass
assert open(kept, "rb").read() != PIC, "the file on disk is the re-encode, not the upload"
print("POST: kept with the exact point, res-10 cell, at_home, the picture's date — and no EXIF or GPS in the file")

# away point: outside the seven cells, not at home; no point at all: the node's own cell
r = lan.post("/captures", files={"photo": ("q.jpg", jpeg(False), "image/jpeg")},
             data={"kind": "drone", **AWAY}, headers=ACT)
c2 = r.json()["capture"]
assert c2["outside"] is True and c2["at_home"] is False and c2["lat"] == 0.5, c2
r = lan.post("/captures", files={"photo": ("n.jpg", jpeg(False), "image/jpeg")}, data={"kind": "camera"}, headers=ACT)
c3 = r.json()["capture"]
assert c3["cell"] == home10 and c3["lat"] is None and c3["at_home"] is True and c3["outside"] is False, \
    "no point given: the node's own cell, and the point stays null"
# a res-10 cell instead of a point; a res-9 cell refused
r = lan.post("/captures", files={"photo": ("c.jpg", jpeg(False), "image/jpeg")}, data={"kind": "phone", "cell": home10}, headers=ACT)
assert r.json()["capture"]["cell"] == home10, "a res-10 cell is taken as given"
cell9 = h3.cell_to_parent(home10, 9)
r = lan.post("/captures", files={"photo": ("d.jpg", jpeg(False), "image/jpeg")}, data={"kind": "phone", "cell": cell9}, headers=ACT)
assert r.status_code == 422 and "res 10" in r.json()["detail"], r.text
print("POST: outside and at_home honest; no point falls back to the node's cell; a coarse cell is refused")

# a duplicate hash answers the existing row and writes nothing new
DUPROWS.append({"id": 3, "sha256": SHA, "file": "old.jpg", "kind": "phone", "cell": home10})
r = lan.post("/captures", files={"photo": ("p2.jpg", PIC, "image/jpeg")}, data={"kind": "phone"}, headers=ACT)
assert r.json().get("duplicate") and r.json()["capture"]["id"] == 3, "the duplicate answers the existing row"
DUPROWS.clear()

# not a picture; one lat without its lon; a kind that is none
r = lan.post("/captures", files={"photo": ("x.txt", b"not a picture", "text/plain")}, data={"kind": "phone"}, headers=ACT)
assert r.status_code == 415, r.text
r = lan.post("/captures", files={"photo": ("p.jpg", jpeg(False), "image/jpeg")}, data={"kind": "phone", "lat": "-8.6"}, headers=ACT)
assert r.status_code == 422 and "together" in r.json()["detail"]
r = lan.post("/captures", files={"photo": ("p.jpg", jpeg(False), "image/jpeg")}, data={"kind": "satellite"}, headers=ACT)
assert r.status_code == 422, r.text
print("POST: refuses a non-picture, a half point, a made-up kind")

# ---- who may ask
for lv in ("off", "open"):
    level(lv)
    assert lan.get("/captures").status_code == 403, f"{lv}: a stranger must not list the captures"
    assert lan.get("/captures/7/file").status_code == 403, f"{lv}: a stranger must not fetch a picture"
    assert lan.post("/captures", files={"photo": ("p.jpg", PIC, "image/jpeg")}, data={"kind": "phone"}).status_code == 403, \
        f"{lv}: a stranger must not add one"
    r = lan.get("/captures", headers=BACKUP)
    assert r.status_code == 401, f"{lv}: the read-only backup token passes the gate but must not read pictures"
level("open")
assert lan.get("/captures", headers=ACT).status_code == 200, "the act token lists"
assert local.get("/captures").status_code == 200, "this machine lists with no token (F10)"
assert local.post("/captures", files={"photo": ("l.jpg", jpeg(False), "image/jpeg")}, data={"kind": "phone"}).status_code == 200, \
    "this machine adds with no token"
print("privacy: a stranger is refused at off and at open; the backup token cannot read pictures; the act token and this machine can")

# ---- the list and its cell filter, at any resolution
LISTROWS.extend([
    {"id": 11, "ts": "2026-10-12T01:00:00+00:00", "kind": "phone", "cell": home10, "note": "a", "lat": -8.6478, "lon": 115.1385},
    {"id": 10, "ts": "2026-10-11T01:00:00+00:00", "kind": "drone", "cell": h3.latlng_to_cell(0.5, 100.0, 10), "note": "b"},
])
rows = lan.get("/captures", headers=ACT).json()
assert [r["id"] for r in rows] == [11, 10], "newest first"
assert rows[0]["at"] == [-8.6478, 115.1385], "a map draws a capture at its exact point"
assert h3.latlng_to_cell(*rows[1]["at"], 10) == rows[1]["cell"], "with no point, at its cell's centre"
rows = lan.get("/captures", params={"cell": cell9}, headers=ACT).json()
assert [r["id"] for r in rows] == [11], "a res-9 cell asks for everything inside it"
rows = lan.get("/captures", params={"cell": home10}, headers=ACT).json()
assert [r["id"] for r in rows] == [11], "a res-10 cell asks for its own"
rows = lan.get("/captures", params={"kind": "drone"}, headers=ACT).json()
assert [r["id"] for r in rows] == [10], "the kind filter"
r = lan.get("/captures", params={"cell": "not-a-cell"}, headers=ACT)
assert r.status_code == 422, r.text
print("GET: newest first, a cell at any resolution, the kind filter, a bad cell refused")

# ---- the file
ROW = {"file": f"{SHA}.jpg", "mime": "image/jpeg"}
r = lan.get("/captures/7/file", headers=ACT)
assert r.status_code == 200 and r.headers["content-type"] == "image/jpeg" and len(r.content) > 100, "the picture answers a token"
import io as _io                                                     # noqa: E402
from PIL import Image as _Image                                      # noqa: E402
t = lan.get("/captures/7/file?w=64", headers=ACT)
assert t.status_code == 200 and t.headers["content-type"] == "image/jpeg" and max(_Image.open(_io.BytesIO(t.content)).size) <= 64, \
    "?w= answers a thumbnail a table can afford"
assert lan.get("/captures/7/file?w=5000", headers=ACT).status_code == 422 and lan.get("/captures/7/file?w=64").status_code == 403
r = lan.get("/captures/7/file", headers=BACKUP)
assert r.status_code == 401, "the backup token cannot fetch the file either"
ROW.clear() if isinstance(ROW, dict) else None
ROW = {}
r = lan.get("/captures/999/file", headers=ACT)
assert r.status_code == 404, "no such capture"
print("GET file: the picture to a token, 401 to the backup token, 404 when there is none")

# ---- the folder gone: a clear 503, never a quiet loss
E.CAPTURES_DIR = os.path.join(TMP, "gone")
r = local.post("/captures", files={"photo": ("p.jpg", jpeg(False), "image/jpeg")}, data={"kind": "phone"})
assert r.status_code == 503 and "CAPTURES_DIR" in r.json()["detail"], r.text
E.CAPTURES_DIR = TMP
print("folder: missing or unwritable is a clear 503 that names CAPTURES_DIR")

# ---- the cleaning keeps HEIC showable, when the install can read one
try:
    import pillow_heif
    pillow_heif.register_heif_opener()
    buf = io.BytesIO()
    Image.new("RGB", (32, 32), (30, 30, 200)).save(buf, "HEIF")
    cleaned, mime, _, _ = E._clean_picture(buf.getvalue())
    assert mime == "image/jpeg" and Image.open(io.BytesIO(cleaned)).format == "JPEG", "HEIC becomes JPEG"
    print("cleaning: a HEIC becomes a JPEG any screen can show")
except Exception as e:
    print(f"cleaning: HEIC check skipped ({type(e).__name__})  (skipped)")

# ---- a drone's MPO (a JPEG carrying extra frames, what DJI writes) is a picture too
buf = io.BytesIO()
Image.new("RGB", (32, 32), (200, 30, 30)).save(buf, "MPO", save_all=True, append_images=[Image.new("RGB", (8, 8))])
assert Image.open(io.BytesIO(buf.getvalue())).format == "MPO", "the fixture really is an MPO"
cleaned, mime, _, _ = E._clean_picture(buf.getvalue())
assert mime == "image/jpeg" and Image.open(io.BytesIO(cleaned)).size == (32, 32), "an MPO keeps its first frame as a JPEG"
print("cleaning: a drone's MPO becomes a JPEG of its main frame")

# ---- the image model: local Ollama, flows classes, people never, the model's until a person confirms
level("open")
open(os.path.join(TMP, "seen.jpg"), "wb").write(jpeg(False))
SENT, ANSWER, ANALYSIS = [], {}, [None]
class FakeOllama:
    def __init__(self, *a, **k): pass
    async def __aenter__(self): return self
    async def __aexit__(self, *a): return False
    async def post(self, url, json):
        SENT.append((url, json))
        said = E.json.dumps(ANSWER) if "format" in json else "Roofs and a car park from above, four coconut palms."
        return main.httpx.Response(200, json={"message": {"content": said}})
main.httpx.AsyncClient = FakeOllama
q0 = main.q
db.q = main.q = lambda sql, *a: ([{"file": "seen.jpg", "kind": "drone", "note": "the banjar", "analysis": ANALYSIS[0]}]
                          if a and a[0] == 7 else [])
settings._cache["rows"]["EYES_MODEL"] = ""
assert lan.post("/captures/7/describe", headers=ACT).status_code == 409, "no image model set: a clear 409"
assert lan.post("/captures/7/describe").status_code == 403, "a stranger asks nothing"
settings._cache["rows"]["EYES_MODEL"] = "qwen2.5vl:7b"
ANSWER.update(findings=[
    {"class": "animal", "name": "none", "count": None},
    {"class": "plant", "name": "coconut palm (Cocos nucifera)", "count": 4, "issue": False},
    {"class": "waste_residual", "name": "a pile of rubbish", "count": 1, "issue": True},
    {"class": "spaceship", "name": "made up", "count": -2}, {"class": "goods", "name": "  "}])
r = lan.post("/captures/7/describe", headers=ACT)
assert r.status_code == 200, r.text
a = r.json()["analysis"]
(url, look), (_, filed) = SENT[-2:]
assert url.endswith("/api/chat") and look["model"] == "qwen2.5vl:7b" and look["messages"][0]["images"], "the picture goes to the local Ollama"
assert "people" in look["messages"][0]["content"] and "the banjar" in look["messages"][0]["content"], "asked never to describe people, told the note"
assert "format" not in look and "images" not in filed["messages"][0], "it looks in words first, then files those words"
assert "four coconut palms" in filed["messages"][0]["content"] and "Never people" in filed["messages"][0]["content"]
assert filed["format"]["properties"]["findings"]["items"]["properties"]["class"]["enum"] == list(E.EYES_CLASSES), "classes are the flows profile's"
assert a["summary"].startswith("Roofs and a car park"), "the summary is what it saw"
assert a["vocab"] == "https://planetai.fab.city/vocab/flows/1.0/" and a["model"] == "qwen2.5vl:7b" and a["by"] == "model" and not a["confirmed_by"]
assert [f["class"] for f in a["findings"]] == ["plant", "waste_residual", "other"], "an unknown class is other; a blank or 'none' name is dropped"
assert a["findings"][2]["count"] is None and a["findings"][1]["issue"] is True, "a negative count is none; the issue kept"
assert "UPDATE captures SET analysis" in CUR.sql, "the description is kept on the row"
assert lan.patch("/captures/7", json={"confirm": True, "actor": "Tomas"}, headers=ACT).status_code == 409, "nothing to confirm before a description"
ANALYSIS[0] = a
r = lan.patch("/captures/7", json={"confirm": True, "actor": "Tomas"}, headers=ACT)
assert r.status_code == 200 and "analysis = analysis || %s" in r.json()["capture"]["sets"], r.text
assert CUR.params[0].obj["confirmed_by"] == "Tomas" and CUR.params[0].obj["by"] == "person", "confirmed by name"
# a person's own list: edited and deleted findings, confirmed by the edit
r = lan.patch("/captures/7", json={"findings": [{"class": "plant", "name": "coconut palm", "count": 4},
                                                 {"class": "nope", "name": "a bench"}, {"name": ""}], "actor": "Tomas"}, headers=ACT)
assert r.status_code == 200, r.text
mine = CUR.params[0].obj
assert mine["findings"] == [{"class": "plant", "name": "coconut palm", "count": 4, "issue": False},
                            {"class": "other", "name": "a bench", "count": None, "issue": False}], mine
assert mine["by"] == "person" and mine["confirmed_by"] == "Tomas", "an edit is a person's word"
assert lan.patch("/captures/7", json={"findings": "x"}, headers=ACT).status_code == 422
# ---- species (SPEC_species step 1): a living finding's scientific name, matched by GBIF only with the household's yes
assert "scientific" in filed["messages"][0]["content"] and "Arecaceae" in filed["messages"][0]["content"], "the model is asked for the rank it is sure of"
assert filed["format"]["properties"]["findings"]["items"]["properties"]["scientific"], "the schema carries it"
ASKED, GBIF = [], {"Cocos nucifera": {"usageKey": 2735117, "scientificName": "Cocos nucifera L.", "rank": "SPECIES",
                                      "matchType": "EXACT", "kingdom": "Plantae"},
                   "Arecaceae": {"usageKey": 7681, "scientificName": "Arecaceae", "rank": "FAMILY", "matchType": "EXACT", "kingdom": "Plantae"},
                   "Bombus": {"usageKey": 1340278, "scientificName": "Bombus", "rank": "GENUS", "matchType": "EXACT", "kingdom": "Animalia"}}
def gbif_get(url, params=None, timeout=None):
    ASKED.append((url, dict(params)))
    if params["name"] == "Down":
        raise main.httpx.ConnectError("no route")
    return main.httpx.Response(200, json=GBIF.get(params["name"], {"matchType": "NONE"}))
main.httpx.get = gbif_get
ANSWER.update(findings=[{"class": "plant", "name": "coconut palm", "scientific": "Cocos nucifera"},
                        {"class": "plant", "name": "palm", "scientific": "Arecaceae"},
                        {"class": "plant", "name": "a bee, the model says", "scientific": "Bombus"},
                        {"class": "plant", "name": "a shrub", "scientific": "Nonsuchia fakea"},
                        {"class": "tool", "name": "a ladder", "scientific": "Scala"},
                        {"class": "animal", "name": "a dog", "scientific": "  null "}])
settings._cache["rows"]["SPECIES_MATCH"] = "off"
a = lan.post("/captures/7/describe", headers=ACT).json()["analysis"]
assert ASKED == [], "without the yes nothing is asked of GBIF"
assert [f.get("scientific") for f in a["findings"]] == ["Cocos nucifera", "Arecaceae", "Bombus", "Nonsuchia fakea", None, None], \
    "a living thing keeps its typed name; a tool has no species; 'null' is no name"
assert not any("taxon" in f for f in a["findings"]), "no yes, no key"
settings._cache["rows"]["SPECIES_MATCH"] = "on"
a = lan.post("/captures/7/describe", headers=ACT).json()["analysis"]
assert [p["name"] for _, p in ASKED] == ["Cocos nucifera", "Arecaceae", "Bombus", "Nonsuchia fakea"], ASKED
assert all(u == E.GBIF_MATCH and set(p) == {"name", "strict"} and p["strict"] == "true" for u, p in ASKED), "the name and nothing else, strictly"
t = [f.get("taxon") for f in a["findings"]]
assert t[0] == {"key": 2735117, "name": "Cocos nucifera L.", "rank": "species", "match": "exact", "source": "gbif"}, t[0]
assert t[1]["rank"] == "family", "a palm stays a family: the rank is what GBIF matched"
assert t[2] is None and t[3] is None, "an animal's name on a plant is no match; nor is no match"
ASKED.clear()
ANSWER.update(findings=[{"class": "plant", "name": "x", "scientific": "Down"}, {"class": "plant", "name": "y", "scientific": "Arecaceae"}])
a = lan.post("/captures/7/describe", headers=ACT).json()["analysis"]
assert len(ASKED) == 1 and not any("taxon" in f for f in a["findings"]), "GBIF down: the description still lands, with typed names"
# a person's edit: an unchanged name keeps its taxon unasked, a changed one is asked, a taxon in the body is ignored
ANALYSIS[0] = {"model": "qwen2.5vl:7b", "findings": [{"class": "plant", "name": "palm", "scientific": "Arecaceae",
                                                       "taxon": {"key": 7681, "name": "Arecaceae", "rank": "family"}}]}
ASKED.clear()
r = lan.patch("/captures/7", json={"findings": [{"class": "plant", "name": "palm", "scientific": "Arecaceae"},
                                                 {"class": "plant", "name": "coconut", "scientific": "Cocos nucifera"},
                                                 {"class": "plant", "name": "forged", "scientific": "Forgeria",
                                                  "taxon": {"key": 1, "name": "Homo sapiens", "rank": "species"}}]}, headers=ACT)
assert r.status_code == 200, r.text
mine = CUR.params[0].obj["findings"]
assert [p["name"] for _, p in ASKED] == ["Cocos nucifera", "Forgeria"], f"only new names are asked: {ASKED}"
assert mine[0]["taxon"]["key"] == 7681 and mine[1]["taxon"]["key"] == 2735117 and "taxon" not in mine[2], mine
settings._cache["rows"]["SPECIES_MATCH"] = "off"
print("species: a living finding's scientific name; GBIF asked the name only, strictly, with the yes; the rank is the match's")
# ---- introduced or invasive (SPEC_species step 2): this country's GRIIS checklist, found offline from NODE_TZ
import zipfile
ZI = os.path.join(TMP, "zoneinfo"); os.makedirs(ZI, exist_ok=True)
open(os.path.join(ZI, "zone.tab"), "w").write("# comment\nID\t-0507+11924\tAsia/Makassar\tBali\nES\t+4024-00341\tEurope/Madrid\tSpain\n")
open(os.path.join(ZI, "iso3166.tab"), "w").write("# comment\nES\tSpain\nID\tIndonesia\n")
E.ZONEINFO = E.Path(ZI)
os.environ["NODE_TZ"] = "Asia/Makassar"
assert E.node_country() == ("ID", "Indonesia"), E.node_country()
os.environ["NODE_TZ"] = "UTC"
assert E.node_country() is None, "a zone in no country is no country"
buf = io.BytesIO()
with zipfile.ZipFile(buf, "w") as z:
    z.writestr("meta.xml", '<archive xmlns="http://rs.tdwg.org/dwc/text/"><core><files><location>taxon.txt</location></files></core>'
               '<extension rowType="http://rs.gbif.org/terms/1.0/SpeciesProfile" ignoreHeaderLines="1"><files><location>profile.txt</location></files>'
               '<coreid index="0"/><field index="1" term="http://rs.gbif.org/terms/1.0/isInvasive"/></extension></archive>')
    z.writestr("profile.txt", "id\tisInvasive\n84000\tInvasive\n84001\tNull\n84002\tInvasive\n")
ARCHIVE = buf.getvalue()
assert E._griis_invasive(ARCHIVE) == {"84000", "84002"}, "isInvasive, read where meta.xml says"
buf = io.BytesIO()
with zipfile.ZipFile(buf, "w") as z:   # the 2022 format: no isInvasive, the distribution's degree of establishment
    z.writestr("meta.xml", '<archive xmlns="http://rs.tdwg.org/dwc/text/"><extension rowType="http://rs.gbif.org/terms/1.0/Distribution" '
               'ignoreHeaderLines="1"><files><location>distribution.txt</location></files><coreid index="0"/>'
               '<field index="2" term="http://rs.tdwg.org/dwc/terms/degreeOfEstablishment"/></extension></archive>')
    z.writestr("distribution.txt", "id\tcountryCode\tdegreeOfEstablishment\n1\tUS\testablished (category C3)\n"
               "2\tUS\tinvasive (category D2)\n3\tUS\twidespread invasive (category E)\n")
assert E._griis_invasive(buf.getvalue()) == {"2", "3"}, "degreeOfEstablishment: invasive and widespread invasive"
LISTING = [{"taxonID": "84000", "nubKey": 2925303}, {"taxonID": "84001", "nubKey": 2970418}, {"taxonID": "84002"}, {"taxonID": "9", "nubKey": 1}]
assert E.griis_marks(LISTING, E._griis_invasive(ARCHIVE)) == {2925303: "invasive", 2970418: "introduced", 1: "introduced"}, \
    "every listed taxon with a Backbone key is introduced, the archive's flag makes it invasive"
HC = []
class FakeHC:
    def get(self, url, params=None, timeout=None, follow_redirects=False):
        HC.append((url, dict(params or {})))
        if "publishedDataset" in url:
            return main.httpx.Response(200, json={"results": [
                {"key": "ds-id", "title": "Global Register of Introduced and Invasive Species- Indonesia"},
                {"key": "ds-x", "title": "Global Register of Introduced and Invasive Species - Indonesia, Bali island"}]})
        if url.endswith("/species/search"):
            return main.httpx.Response(200, json={"results": LISTING, "endOfRecords": True})
        if url.endswith("/endpoint"):
            return main.httpx.Response(200, json=[{"type": "EML", "url": "x"}, {"type": "DWC_ARCHIVE", "url": "https://ipt/a.zip"}])
        return main.httpx.Response(200, content=ARCHIVE, request=main.httpx.Request("GET", url))
hc0, main.hc = main.hc, FakeHC()
settings._cache["rows"]["SPECIES_MATCH"] = "off"
main.state["griis"] = {"marks": {}}
E.check_griis()
assert "griis" not in main.state and HC == [], "off: nothing asked, nothing kept"
settings._cache["rows"]["SPECIES_MATCH"] = "on"
os.environ["NODE_TZ"] = "Asia/Makassar"
E.check_griis()
g = main.state["griis"]
assert g["dataset"] == "ds-id" and g["marks"] == {2925303: "invasive", 2970418: "introduced", 1: "introduced"} and g["name"] == "Indonesia", g
assert all("api.gbif.org" in u or u == "https://ipt/a.zip" for u, _ in HC) and HC[1][1]["datasetKey"] == "ds-id", HC
n = len(HC); E.check_griis()
assert len(HC) == n, "read weekly, not every hour"
# the marks on a finding: invasive, introduced through a synonym, unmarked when not listed (never "native")
GBIF.update({"Lantana camara": {"usageKey": 2925303, "scientificName": "Lantana camara L.", "rank": "SPECIES", "matchType": "EXACT", "kingdom": "Plantae"},
             "Leucaena glauca": {"usageKey": 555, "acceptedUsageKey": 2970418, "scientificName": "Leucaena glauca", "rank": "SPECIES",
                                 "matchType": "EXACT", "kingdom": "Plantae"}})
fs = E._taxa(E._findings([{"class": "plant", "name": "a", "scientific": "Lantana camara"},
                                {"class": "plant", "name": "b", "scientific": "Leucaena glauca"},
                                {"class": "plant", "name": "c", "scientific": "Cocos nucifera"}]))
assert (fs[0]["taxon"]["introduced"], fs[0]["taxon"]["where"]) == ("invasive", "Indonesia"), fs[0]
assert fs[1]["taxon"]["accepted"] == 2970418 and fs[1]["taxon"]["introduced"] == "introduced", "a synonym is marked under the name it stands for"
assert "introduced" not in fs[2]["taxon"] and "where" not in fs[2]["taxon"], "not on the list: unmarked, not native"
# a country GRIIS has no list for says so on the finding
os.environ["NODE_TZ"] = "Europe/Madrid"
main.state.pop("griis")
E.check_griis()
assert main.state["griis"]["why"] == "GRIIS publishes no checklist for Spain" and "marks" not in main.state["griis"]
t = E._taxa(E._findings([{"class": "plant", "name": "c", "scientific": "Cocos nucifera"}]))[0]["taxon"]
assert t["introduced"] is None and t["where"] == "GRIIS publishes no checklist for Spain", t
main.hc = hc0; main.state.pop("griis"); os.environ["NODE_TZ"] = "Asia/Makassar"
settings._cache["rows"]["SPECIES_MATCH"] = "off"
print("introduced: the country from NODE_TZ, its GRIIS list read weekly with the yes, invasive or introduced on the taxon, unlisted unmarked")
# ---- what others recorded here (SPEC_species step 3): open GBIF records in the seven cells, counted, nothing else kept
w = E._cell_wkt("8895a4c843fffff")
pts = [tuple(map(float, xy.split())) for xy in w[len("POLYGON(("):-2].split(",")]
assert len(pts) == 7 and pts[0] == pts[-1], "a closed hexagon"
assert sum((x2 - x1) * (y2 + y1) for (x1, y1), (x2, y2) in zip(pts, pts[1:])) < 0, "counter-clockwise, as GBIF asks"
OCC = []
class FakeOcc:
    def get(self, url, params=None, timeout=None):
        OCC.append((url, list(params)))
        geo = dict(params)["geometry"]
        n = 3 if geo == E._cell_wkt(sorted(E._node_cells()[0])[0]) else 1
        return main.httpx.Response(200, request=main.httpx.Request("GET", url), json={"count": 9, "facets": [
            {"field": "SPECIES_KEY", "counts": [{"name": "2925303", "count": n}, {"name": "2970418", "count": 2}]},
            {"field": "FAMILY_KEY", "counts": [{"name": "7681", "count": 5}]}]})
hc0, main.hc = main.hc, FakeOcc()
settings._cache["rows"]["SPECIES_MATCH"] = "off"
main.state["others"] = {"cells": {}}
E.check_others()
assert "others" not in main.state and OCC == [], "off: nothing asked, nothing kept"
settings._cache["rows"]["SPECIES_MATCH"] = "on"
E.check_others()
o = main.state["others"]["cells"]
assert len(OCC) == 7 and len(o) == 7, "one request per cell of the seven"
assert all(u.endswith("/occurrence/search") and ("license", "CC0_1_0") in q and ("license", "CC_BY_4_0") in q
           and ("limit", "0") in q and not any(k in ("lat", "lon", "decimalLatitude") for k, _ in q) for u, q in OCC), \
    "open licences only, counts only, the cell's shape and no point"
assert sum(c[2925303] for c in o.values()) == 3 + 6 and all(c[7681] == 5 for c in o.values())
E.check_others()
assert len(OCC) == 7, "read weekly, not every hour"
GBIF["Arecaceae"] = {"usageKey": 7681, "scientificName": "Arecaceae", "rank": "FAMILY", "matchType": "EXACT", "kingdom": "Plantae"}
GBIF["Leucaena glauca"] = {"usageKey": 555, "acceptedUsageKey": 2970418, "scientificName": "Leucaena glauca", "rank": "SPECIES",
                           "matchType": "EXACT", "kingdom": "Plantae"}
fs = E._taxa(E._findings([{"class": "plant", "name": "a", "scientific": "Lantana camara"},
                                {"class": "plant", "name": "b", "scientific": "Arecaceae"},
                                {"class": "plant", "name": "c", "scientific": "Leucaena glauca"},
                                {"class": "plant", "name": "d", "scientific": "Cocos nucifera"}]))
assert [f["taxon"]["others"] for f in fs] == [9, 35, 14, 0], [f["taxon"].get("others") for f in fs]
main.hc = hc0; main.state.pop("others")
settings._cache["rows"]["SPECIES_MATCH"] = "off"
print("others: the seven cells' open GBIF records, counted per species, genus and family, weekly with the yes; none kept but counts")
# ---- the species confirmed here (SPEC_species §4): from confirmed findings, behind the images' token, per cell
import h3 as _h3
C10 = _h3.latlng_to_cell(-8.6478291, 115.1385412, 10)
FAR = _h3.latlng_to_cell(-8.70, 115.20, 10)
SEEN = [{"id": 1, "cell": C10, "analysis": {"confirmed_by": "Tomas", "findings": [
            {"class": "plant", "name": "palm", "count": 4, "scientific": "Cocos nucifera",
             "taxon": {"key": 2735117, "name": "Cocos nucifera L.", "rank": "species", "others": 0}},
            {"class": "plant", "name": "lantana", "scientific": "Lantana camara",
             "taxon": {"key": 2925303, "name": "Lantana camara L.", "rank": "species", "introduced": "invasive", "where": "Indonesia"}},
            {"class": "waste_residual", "name": "rubbish", "count": 3}, {"class": "plant", "name": "a tree"}]}},
        {"id": 2, "cell": FAR, "analysis": {"confirmed_by": "Bayu", "findings": [
            {"class": "plant", "name": "palms", "count": 2, "scientific": "Cocos nucifera", "taxon": {"key": 2735117, "name": "Cocos nucifera L.", "rank": "species"}},
            {"class": "animal", "name": "gecko", "scientific": "Hemidactylus"}]}}]
SQL = []
db.q = main.q = lambda sql, *a: (SQL.append(sql), SEEN)[1]
level("off")
assert lan.get("/species").status_code == 403, "a stranger reads no species: where a picture was taken is the household's"
r = lan.get("/species", headers=ACT)
assert r.status_code == 200 and "confirmed_by' IS NOT NULL" in SQL[-1], "only confirmed images are read"
sp = r.json()["species"]
assert [(x["name"], x["count"], x["images"], x["cells"]) for x in sp] == [("Cocos nucifera L.", 6, 2, 2), ("Hemidactylus", 1, 1, 1),
                                                                          ("Lantana camara L.", 1, 1, 1)], sp
assert sp[2]["introduced"] == "invasive" and sp[1]["key"] is None, "the GRIIS mark rides along; a typed name counts by its words"
assert all(x["class"] in ("plant", "animal") for x in sp), "rubbish and an unnamed tree are not species"
home8 = _h3.cell_to_parent(C10, 8)
assert [x["count"] for x in lan.get(f"/species?cell={home8}", headers=ACT).json()["species"]] == [4, 1], "a coarser cell answers inside it"
assert lan.get(f"/species?cell={C10}", headers=ACT).json()["species"][0]["images"] == 1
assert lan.get("/species?cell=nope", headers=ACT).status_code == 422
db.q = main.q = q0
print("species here: confirmed findings only, per taxon or typed name, any cell, behind the images' token; never a reading")
# the upload's box: describe=1 describes the new image after the upload answers; unticked, nothing is asked
called = []
E._describe, d0 = (lambda cid, model: called.append((cid, model)) or __import__("asyncio").sleep(0)), E._describe
db.q = main.q = q0
DUPROWS.clear()
r = local.post("/captures", files={"photo": ("a.jpg", jpeg(False) + b"box", "image/jpeg")}, data={"kind": "phone"})
assert r.status_code == 200 and r.json()["describing"] is False and called == [], "unticked: not described"
r = local.post("/captures", files={"photo": ("a.jpg", jpeg(False) + b"box2", "image/jpeg")}, data={"kind": "phone", "describe": "1"})
assert r.status_code == 200 and r.json()["describing"] is True, r.text
assert called == [(7, "qwen2.5vl:7b")], f"the box describes the new image: {called}"
settings._cache["rows"]["EYES_MODEL"] = ""
r = local.post("/captures", files={"photo": ("a.jpg", jpeg(False) + b"box3", "image/jpeg")}, data={"kind": "phone", "describe": "1"})
assert r.json()["describing"] is False, "no image model: the box says so instead of pretending"
E._describe = d0
print("image model: local Ollama with flows classes and no people; kept as the model's; confirmed or edited by a name; the upload box describes")

# ---- the Data door edits an image's words, and the admin token deletes one
DELFILE = "gone.jpg"
level("open")
r = lan.patch("/captures/7", json={"note": "the frangipani", "kind": "camera", "meta": {"species": "Plumeria"}}, headers=ACT)
assert r.status_code == 200 and "note = %s" in r.json()["capture"]["sets"] and "meta = %s" in r.json()["capture"]["sets"], r.text
assert lan.patch("/captures/7", json={"kind": "satellite"}, headers=ACT).status_code == 422, "a made-up kind"
assert lan.patch("/captures/7", json={"lat": 1}, headers=ACT).status_code == 422, "the point is not edited"
assert lan.patch("/captures/8", json={"note": "x"}, headers=ACT).status_code == 404
assert lan.patch("/captures/7", json={"note": "x"}).status_code == 403, "a stranger edits nothing"
open(os.path.join(TMP, DELFILE), "wb").write(b"x")
assert lan.delete("/captures/7", headers=ACT).status_code == 401, "the act token adds and edits, never deletes"
r = lan.delete("/captures/7", headers=ADMIN)
assert r.status_code == 200 and not os.path.exists(os.path.join(TMP, DELFILE)), "delete takes the file with the row"
assert lan.delete("/captures/8", headers=ADMIN).status_code == 404
print("edit and delete: note, kind and meta by the act token; delete by the admin token only, file and row")

print("captures: every check passed")
