"""Eyes: the pictures a household takes of its place, what the image model sees in them, and the species GBIF names.

POST/GET /captures, PATCH/DELETE /captures/{id}, GET /captures/{id}/file, POST /captures/{id}/describe, GET /species,
and two weekly reads, check_griis (this country's introduced and invasive species, GRIIS) and check_others (what open
records GBIF holds in the node's seven cells), which the node's timers run while this pack is on (main._pack_job).

A pack since 24 Oct 2026; until then app/main.py, moved unchanged (docs/decisions/2026-10-21-core-and-packs.md:
species is a category a node watches, like air or heat). The node mounts these routes from here (app/packs.py::routers)
and answers 404 while this pack is off. The `captures` table stays in init.sql, the pictures stay on their disk, and
CAPTURES_DIR, EYES_MODEL and SPECIES_MATCH stay core settings, because the last two change what leaves the house.
"""
from __future__ import annotations

import json
import logging
import os
import re
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx
from fastapi import APIRouter, File, Form, Header, HTTPException, Query, Request, UploadFile
from psycopg.types.json import Jsonb

import db as _db                 # through the module, so a test can stub the database (db.q, db.db)
import settings
from auth import ACT_TOKEN, _admin, _bearer_ok, _is_local, _node_tokens

log = logging.getLogger("planetai")
NODE = os.getenv("NODE_NAME", "node")
NODE_TZ = os.getenv("NODE_TZ", "").strip() or "UTC"

router = APIRouter()


def _here() -> tuple[float, float]:
    from geo import _here as here    # noqa: PLC0415 — the node's point, as the map workbench reads it
    return here()


# ---------------------------------------------------------------- introduced or invasive (docs/SPEC_species.md §3)
# GRIIS, the Global Register of Introduced and Invasive Species, publishes one checklist per country on GBIF under CC BY
# 4.0, all from one publisher (ISSG). The node finds its own country's by title, offline from NODE_TZ, and keeps a map
# Backbone key -> invasive | introduced, read weekly while SPECIES_MATCH is on: three requests that say which country
# this node is in and nothing else. A species not on the list is unmarked, never "native": absence is not evidence.
GRIIS_PUBLISHER = "cdef28b1-db4e-4c58-aa71-3c5238c2d0b5"
GRIIS_TITLE = "Global Register of Introduced and Invasive Species"
GRIIS_EVERY = 7 * 86400
# ponytail: iso3166.tab names that GRIIS titles spell otherwise, for the pilots' and nodes' countries; add one when a
# node lands in a country whose list the node cannot find
GRIIS_ALIAS = {"GB": "United Kingdom", "KR": "Republic of Korea", "US": "United States (Contiguous) (ver.2.0, 2022)"}
ZONEINFO = Path("/usr/share/zoneinfo")


def node_country() -> tuple[str, str] | None:
    """(ISO code, name) of the country NODE_TZ is in, from the zone tables every system ships. None when the zone
    names no single country (UTC, a typo)."""
    tz = os.getenv("NODE_TZ", "").strip()
    try:
        code = next((cols[0] for cols in (ln.split("\t") for ln in (ZONEINFO / "zone.tab").read_text().splitlines())
                     if len(cols) > 2 and cols[2] == tz and not cols[0].startswith("#")), None)
        names = dict(ln.split("\t", 1) for ln in (ZONEINFO / "iso3166.tab").read_text().splitlines()
                     if ln and not ln.startswith("#"))
    except OSError:
        return None
    return (code, names.get(code, code)) if code else None


def griis_marks(listing: list[dict], invasive: set[str]) -> dict[int, str]:
    """A checklist's own rows (GBIF's species search: taxonID, nubKey) as Backbone key -> invasive | introduced. Every
    taxon on a GRIIS list is introduced; the archive says which of them are invasive."""
    return {r["nubKey"]: "invasive" if r.get("taxonID") in invasive else "introduced" for r in listing if r.get("nubKey")}


def _griis_invasive(zbytes: bytes) -> set[str]:
    """The taxonIDs a Darwin Core archive calls invasive, in either GRIIS format: the species profile's isInvasive
    (Indonesia, 2020) or the distribution's degreeOfEstablishment, "invasive (category D2)" and the like (the US, 2022).
    Columns are found where meta.xml says, not assumed."""
    import csv, io, zipfile, xml.etree.ElementTree as ET  # noqa: E401, PLC0415
    z = zipfile.ZipFile(io.BytesIO(zbytes))
    ns = {"d": "http://rs.tdwg.org/dwc/text/"}
    out = set()
    for ext in ET.fromstring(z.read("meta.xml")).findall("d:extension", ns):
        col = next((int(f.get("index")) for f in ext.findall("d:field", ns)
                    if f.get("term", "").endswith(("/isInvasive", "/degreeOfEstablishment"))), None)
        if col is None:
            continue
        cid, skip = int(ext.find("d:coreid", ns).get("index")), int(ext.get("ignoreHeaderLines", "0"))
        rows = csv.reader(io.StringIO(z.read(ext.find("d:files/d:location", ns).text).decode("utf-8")), delimiter="\t")
        out |= {r[cid] for i, r in enumerate(rows) if i >= skip and len(r) > max(cid, col) and "invasive" in r[col].lower()}
    return out


def check_griis() -> None:
    """Weekly while SPECIES_MATCH is on: find this country's GRIIS checklist and keep its marks. What it could not
    find is kept as `why`, so a finding says "no checklist for here" instead of saying nothing."""
    from main import state, hc  # noqa: PLC0415 — main imports packs: its timers' state and http client
    if settings.get("SPECIES_MATCH", "off") != "on":
        state.pop("griis", None)
        return
    known = state.get("griis") or {}
    if time.time() - known.get("asked", 0) < GRIIS_EVERY:
        return
    c = node_country()
    if not c:
        state["griis"] = {"why": "NODE_TZ names no country", "asked": time.time()}
        return
    code, name = c
    try:
        sets = hc.get(f"https://api.gbif.org/v1/organization/{GRIIS_PUBLISHER}/publishedDataset",
                      params={"limit": 1000}, timeout=30).json()["results"]
        want = GRIIS_ALIAS.get(code, name)
        ds = next((d["key"] for d in sets if re.fullmatch(rf"{GRIIS_TITLE}\s*-\s*{re.escape(want)}", d["title"].strip())), None)
        if not ds:
            state["griis"] = {"country": code, "name": name, "why": f"GRIIS publishes no checklist for {name}",
                              "asked": time.time()}
            return
        listing, offset = [], 0
        while True:
            page = hc.get("https://api.gbif.org/v1/species/search", params={"datasetKey": ds, "origin": "SOURCE",
                          "limit": 1000, "offset": offset}, timeout=60).json()
            listing += page["results"]
            offset += len(page["results"])
            if page.get("endOfRecords", True) or not page["results"]:
                break
        archive = next(e["url"] for e in hc.get(f"https://api.gbif.org/v1/dataset/{ds}/endpoint", timeout=30).json()
                       if e["type"] == "DWC_ARCHIVE")
        r = hc.get(archive, timeout=120, follow_redirects=True)
        r.raise_for_status()
        marks = griis_marks(listing, _griis_invasive(r.content))
    except Exception as e:  # noqa: BLE001 — no route out keeps the last good list and tries again in a day
        state["griis"] = {**known, "error": type(e).__name__, "asked": time.time() - GRIIS_EVERY + 86400}
        return
    state["griis"] = {"country": code, "name": name, "dataset": ds, "marks": marks, "asked": time.time(),
                      "read": datetime.now(timezone.utc).isoformat(timespec="seconds")}



# ---------------------------------------------------------------- what others recorded here (docs/SPEC_species.md §3)
# GBIF's open occurrence records in the node's seven res-8 cells, counted per species, genus and family key, so a
# matched finding can say "also recorded here by others, N times". Only CC0 and CC BY records: iNaturalist's CC BY-NC
# ones are not open, and the node does not keep them. Counts only: no record, observer or point is kept. The request
# carries the seven hexagons, which tells GBIF the area this node is in, about 2 km across. Weekly, with SPECIES_MATCH.
OTHERS_EVERY = 7 * 86400
OTHERS_LICENCES = ("CC0_1_0", "CC_BY_4_0")


def _cell_wkt(cell: str) -> str:
    """One H3 cell as the counter-clockwise WKT polygon GBIF's geometry filter asks for."""
    import h3  # noqa: PLC0415
    ring = [(lng, lat) for lat, lng in h3.cell_to_boundary(cell)]
    if sum((x2 - x1) * (y2 + y1) for (x1, y1), (x2, y2) in zip(ring, ring[1:] + ring[:1])) > 0:
        ring.reverse()   # the shoelace sum is positive for a clockwise ring
    return "POLYGON((" + ",".join(f"{x:.6f} {y:.6f}" for x, y in ring + ring[:1]) + "))"


def check_others() -> None:
    """Weekly while SPECIES_MATCH is on: per cell, how many open records GBIF holds of each species, genus and family."""
    from main import state, hc  # noqa: PLC0415 — main imports packs: its timers' state and http client
    if settings.get("SPECIES_MATCH", "off") != "on":
        state.pop("others", None)
        return
    known = state.get("others") or {}
    if time.time() - known.get("asked", 0) < OTHERS_EVERY:
        return
    try:
        cells = {}
        for cell in sorted(_node_cells()[0]):
            r = hc.get("https://api.gbif.org/v1/occurrence/search", timeout=60, params=[
                ("geometry", _cell_wkt(cell)), *(("license", lc) for lc in OTHERS_LICENCES), ("limit", "0"),
                ("facet", "speciesKey"), ("facet", "genusKey"), ("facet", "familyKey"), ("facetLimit", "1000")])
            r.raise_for_status()
            cells[cell] = {int(c["name"]): c["count"] for f in r.json().get("facets", []) for c in f["counts"]}
    except Exception as e:  # noqa: BLE001 — no route out keeps the last good counts and tries again in a day
        state["others"] = {**known, "error": type(e).__name__, "asked": time.time() - OTHERS_EVERY + 86400}
        return
    state["others"] = {"cells": cells, "asked": time.time(), "read": datetime.now(timezone.utc).isoformat(timespec="seconds")}


# ---------------------------------------------------------------- captures (SPEC_eyes step 1)
# One picture with the facts a reading has: when, which cell, who, with what. The file lives in the folder the
# household chose (CAPTURES_DIR in .env → /app/captures here; unlike DATA_DIR it MAY be a NAS share — these are
# files, not Postgres). On NO SHARE_LEVEL list at any level, in no export, aggregate, readings or parent push:
# the middleware refuses a stranger outright, and the route then refuses every token but ACT/ADMIN, so the
# read-only BACKUP_TOKEN that passes the gate cannot read a picture. The exact point is kept (token only); only
# the FILE is cleaned of EXIF/GPS, so a picture that is ever shared carries no hidden place.

CAPTURE_KINDS = ("microscope", "phone", "camera", "drone", "balloon")
CAPTURES_DIR = os.getenv("PLANETAI_CAPTURES", "/app/captures")   # the compose mount's inside path; tests point it aside


def _captures_auth(request: Request, authorization: str) -> None:
    """The /actions rule (F10): unchanged and open on this machine; from anywhere else ACT_TOKEN or ADMIN_TOKEN —
    the weaker one on purpose, so a household member adds pictures without holding the key to /settings/raw."""
    if not _is_local(request):
        tokens = [t for t in (ACT_TOKEN(), os.getenv("ADMIN_TOKEN", "").strip()) if t]
        if not tokens:
            raise HTTPException(403, "no ACT_TOKEN or ADMIN_TOKEN set on this node; run `planetai ui` to create one")
        if not _bearer_ok(authorization, *tokens):
            raise HTTPException(401, "the captures answer only this machine or Authorization: Bearer ***")


def _captures_dir() -> str:
    """The folder, or a clear 503: a capture is refused when there is nowhere honest to keep it. `planetai doctor`
    says the same from the host side."""
    d = CAPTURES_DIR
    if not os.path.isdir(d) or not os.access(d, os.W_OK):
        raise HTTPException(503, f"the captures folder ({d}) is missing or not writable, so this node is not taking "
                                 "pictures. It may be any disk, a NAS share included: mount it, or point CAPTURES_DIR "
                                 "in .env at one that is there, and `planetai restart`.")
    return d


def _node_cells() -> tuple[set, str]:
    """The node's seven res-8 cells (its own and the six touching it, SPEC_eyes §5) and its own res-10 cell —
    the yardsticks `outside` and `at_home` are measured with once, on arrival."""
    import h3  # noqa: PLC0415
    lat, lon = _here()
    home8 = h3.latlng_to_cell(lat, lon, 8)
    return set(h3.grid_disk(home8, 1)), h3.latlng_to_cell(lat, lon, 10)


def _clean_picture(raw: bytes) -> tuple[bytes, str, str | None, tuple[float, float] | None]:
    """Re-encode with no metadata: EXIF, GPS and the thumbnail die here and only the pixels survive. Returns the
    cleaned bytes, their mime, and the picture's own date when it carried one (kept as `ts`, the taken time —
    a date is not a place). HEIC becomes JPEG so any screen can show it back."""
    import io  # noqa: PLC0415
    from PIL import Image, ImageOps  # noqa: PLC0415
    try:
        import pillow_heif  # noqa: PLC0415
        pillow_heif.register_heif_opener()
    except ImportError:
        pass  # no HEIC on this install: a HEIC upload then reads as not-a-picture below, honestly
    try:
        im = Image.open(io.BytesIO(raw))
        im.load()
    except Exception:
        raise ValueError("that file is not a picture this node can read (jpeg, png, heic or webp)") from None
    fmt0 = (im.format or "").upper()
    if fmt0 not in ("JPEG", "MPO", "PNG", "WEBP", "HEIF", "HEIC", "AVIF"):  # MPO: a JPEG with extra frames, what DJI drones write
        raise ValueError(f"a {fmt0 or 'unknown'} is not a picture this node keeps (jpeg, png, heic or webp)")
    taken = None
    try:
        exif = im.getexif()
        dtor = exif.get_ifd(0x8769).get(36867) or exif.get(306)  # DateTimeOriginal (taken), else DateTime (saved)
        if dtor:
            taken = datetime.strptime(dtor.strip(), "%Y:%m:%d %H:%M:%S").replace(tzinfo=ZoneInfo(NODE_TZ)).isoformat()  # a camera writes local time
    except Exception:  # noqa: BLE001 — a picture with a broken date is still a picture; taken falls back to now
        taken = None
    point = None   # where the camera says it was taken: read here, kept in the row, and gone from the file below
    try:
        g = im.getexif().get_ifd(0x8825)
        dms = lambda v: float(v[0]) + float(v[1]) / 60 + float(v[2]) / 3600  # noqa: E731
        if g.get(2) and g.get(4):
            plat = dms(g[2]) * (-1 if str(g.get(1, "N")).upper().startswith("S") else 1)
            plon = dms(g[4]) * (-1 if str(g.get(3, "E")).upper().startswith("W") else 1)
            if -90 <= plat <= 90 and -180 <= plon <= 180 and (plat, plon) != (0.0, 0.0):
                point = (plat, plon)
    except Exception:  # noqa: BLE001 — a broken GPS block is no point, not a refused picture
        point = None
    im = ImageOps.exif_transpose(im)  # the orientation is metadata too: apply it, then let it go with the rest
    out = io.BytesIO()
    if fmt0 in ("JPEG", "MPO", "HEIF", "HEIC", "AVIF"):  # an MPO keeps its first frame, the picture
        im.convert("RGB").save(out, "JPEG", quality=90)
        mime = "image/jpeg"
    elif fmt0 == "PNG":
        im.save(out, "PNG")
        mime = "image/png"
    else:
        im.save(out, "WEBP", quality=90)
        mime = "image/webp"
    return out.getvalue(), mime, taken, point


@router.post("/captures")
async def capture_post(request: Request, authorization: str = Header(""),
                       photo: "UploadFile" = File(...), kind: str = Form("phone"),
                       lat: float | None = Form(None), lon: float | None = Form(None),
                       cell: str | None = Form(None), note: str = Form(""),
                       taken_at: str = Form(""), actor: str = Form(""), describe: str = Form("")):
    """A household adds a picture: multipart, one image, `kind`, `lat`+`lon` OR a res-10 `cell` OR neither (the
    node's own cell, which is what a phone with no location permission means), optional `note`, `taken_at` and
    `actor` (the name the phone keeps), and `describe=1` to have the image model describe it after the upload answers
    (the upload form's checkbox). The exact point is kept — a tree or a dump is worth it — and only the
    file is cleaned. A duplicate sha256 answers the existing row instead of keeping the same picture twice."""
    import hashlib  # noqa: PLC0415
    import h3  # noqa: PLC0415
    _captures_auth(request, authorization)
    if kind not in CAPTURE_KINDS:
        raise HTTPException(422, f"kind must be one of {', '.join(CAPTURE_KINDS)}")
    raw = await photo.read()
    if not raw:
        raise HTTPException(422, "no picture arrived")
    if len(raw) > 40 * 1024 * 1024:
        raise HTTPException(413, "a capture is a picture, not a film: 40 MB is the most this node takes")
    sha = hashlib.sha256(raw).hexdigest()
    dup = _db.q("SELECT * FROM captures WHERE sha256 = %s", sha)
    if dup:
        return {"ok": True, "duplicate": True, "capture": dup[0]}
    try:
        cleaned, mime, exif_taken, exif_point = _clean_picture(raw)
    except ValueError as e:
        raise HTTPException(415, str(e)) from None
    if (lat is None) != (lon is None):
        raise HTTPException(422, "lat and lon together, or neither")
    if lat is not None and not (-90 <= lat <= 90 and -180 <= lon <= 180):
        raise HTTPException(422, "lat must be -90..90 and lon -180..180")
    if exif_point and not cell:
        lat, lon = exif_point   # the picture's own GPS: where it was taken beats where the phone is now (a gallery pick)
    seven, home10 = _node_cells()
    if lat is not None:
        cap_cell = h3.latlng_to_cell(lat, lon, 10)
    elif cell:
        if not h3.is_valid_cell(cell):
            raise HTTPException(422, f"{cell!r} is not an H3 cell")
        if h3.get_resolution(cell) != 10:
            raise HTTPException(422, "cell must be res 10, the room; send lat and lon instead if you have them")
        cap_cell = cell
    else:
        cap_cell = home10   # no point given: the picture was taken here, at the node, as far as this node knows
    outside = h3.cell_to_parent(cap_cell, 8) not in seven
    at_home = cap_cell == home10
    ts = taken_at.strip() or exif_taken
    if ts:
        try:
            ts = datetime.fromisoformat(ts.replace("Z", "+00:00")).isoformat()
        except ValueError:
            raise HTTPException(422, "taken_at must be an ISO date-time") from None
    folder = _captures_dir()
    name = f"{sha}.{mime.split('/')[1].replace('jpeg', 'jpg')}"
    with open(os.path.join(folder, name), "wb") as f:
        f.write(cleaned)
    with _db.db() as con, con.cursor() as cur:
        cur.execute("""INSERT INTO captures (ts, kind, cell, lat, lon, outside, at_home, actor, note, file, sha256, bytes, mime)
                       VALUES (COALESCE(%s::timestamptz, now()), %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                       RETURNING *""",
                    (ts, kind, cap_cell, lat, lon, outside, at_home, str(actor or "")[:80], str(note or "")[:500],
                     name, sha, len(cleaned), mime))
        row = {k: (v.isoformat() if isinstance(v, datetime) else v) for k, v in cur.fetchone().items()}
    describing = describe.strip().lower() in ("1", "on", "true") and _describe_later(row["id"])
    return {"ok": True, "capture": row, "describing": bool(describing)}


@router.get("/captures")
def captures_list(request: Request, authorization: str = Header(""), cell: str | None = None,
                  kind: str | None = None, limit: int = Query(50, ge=1, le=500)):
    """The visual database, newest first. `?cell=` takes a cell at any resolution and answers the captures inside
    it — which is how the walk asks for a street's or a ring's pictures from the res-10 cells it keeps."""
    _captures_auth(request, authorization)
    if kind is not None and kind not in CAPTURE_KINDS:
        raise HTTPException(422, f"kind must be one of {', '.join(CAPTURE_KINDS)}")
    # ponytail: a ?cell= reads every row and filters in Python (no H3 in Postgres here); fine to tens of thousands
    rows = _db.q("SELECT * FROM captures" + (" WHERE kind = %s" if kind else "") + " ORDER BY id DESC"
             + ("" if cell else " LIMIT %s" % limit), *([kind] if kind else []))
    if cell:
        import h3  # noqa: PLC0415
        if not h3.is_valid_cell(cell):
            raise HTTPException(422, f"{cell!r} is not an H3 cell")
        res = h3.get_resolution(cell)
        rows = [r for r in rows if h3.cell_to_parent(r["cell"], min(res, 10)) == cell] if res <= 10 else []
    import h3  # noqa: PLC0415
    # `at` is where a map draws it: the exact point, else its cell's centre (the node computes, the page draws)
    return [{**r, "at": [r["lat"], r["lon"]] if r.get("lat") is not None else list(h3.cell_to_latlng(r["cell"]))}
            for r in rows[:limit]]


@router.get("/species")
def species(request: Request, authorization: str = Header(""), cell: str | None = None):
    """The species a person here has confirmed (SPEC_species §4), per taxon: how many, in how many images, and what
    GRIIS and others' records say. `?cell=` at any resolution answers inside that cell. Only confirmed findings count:
    a model's guess is not a sighting. Read from the images, behind the images' own token, because where a picture was
    taken is the household's; these are not readings, so nothing here reaches the export or a parent."""
    _captures_auth(request, authorization)
    import h3  # noqa: PLC0415
    if cell and not h3.is_valid_cell(cell):
        raise HTTPException(422, f"{cell!r} is not an H3 cell")
    res = h3.get_resolution(cell) if cell else None
    out: dict = {}
    for r in _db.q("SELECT id, cell, analysis FROM captures WHERE analysis->>'confirmed_by' IS NOT NULL"):
        if cell and (res > 10 or h3.cell_to_parent(r["cell"], res) != cell):
            continue
        for f in (r["analysis"] or {}).get("findings") or []:
            t, sci = f.get("taxon") or {}, f.get("scientific")
            if f.get("class") not in TAXON_KINGDOM or not (t or sci):
                continue
            k = t.get("key") or sci   # a name typed without GBIF still counts here, by its words
            row = out.setdefault(k, {"key": t.get("key"), "name": t.get("name") or sci, "rank": t.get("rank"),
                                     "class": f["class"], "count": 0, "images": set(), "cells": set()})
            row["count"] += f.get("count") or 1
            row["images"].add(r["id"]); row["cells"].add(r["cell"])
            row.update({k2: t[k2] for k2 in ("introduced", "where", "others") if k2 in t})
    rows = sorted(out.values(), key=lambda x: (-x["count"], x["name"]))
    return {"cell": cell, "species": [{**x, "images": len(x["images"]), "cells": len(x["cells"])} for x in rows]}


@router.patch("/captures/{cid}")
def capture_patch(cid: int, body: dict, request: Request, authorization: str = Header("")):
    """The household edits an image's words: `note`, `kind`, and `meta` (an object of short strings, replaced whole).
    The point, the cell, the time and the file are facts of arrival and are not edited here."""
    _captures_auth(request, authorization)
    sets, vals = [], []
    if "note" in body:
        sets.append("note = %s"); vals.append(str(body["note"] or "")[:500])
    if "kind" in body:
        if body["kind"] not in CAPTURE_KINDS:
            raise HTTPException(422, f"kind must be one of {', '.join(CAPTURE_KINDS)}")
        sets.append("kind = %s"); vals.append(body["kind"])
    if "meta" in body:
        m = body["meta"]
        if not isinstance(m, dict) or len(m) > 40:
            raise HTTPException(422, "meta is an object of at most 40 keys")
        sets.append("meta = %s"); vals.append(Jsonb({str(k)[:60]: str(v)[:500] for k, v in m.items()}))
    if body.get("confirm") or "findings" in body:
        was = (_db.q("SELECT analysis FROM captures WHERE id = %s", cid) or [{}])[0].get("analysis") or {}
        if not was.get("model"):
            raise HTTPException(409, "nothing to confirm: this image has not been described yet")
        # a person here says the model's findings are right: from now on they are the household's, with its name
        # (an edited list is confirmed by the edit: what is left is what a person says is there)
        who = str(body.get("actor") or "someone here")[:80]
        mine = {"by": "person", "confirmed_by": who, "confirmed_at": datetime.now(timezone.utc).isoformat()}
        if "findings" in body:
            if not isinstance(body["findings"], list) or len(body["findings"]) > 30:
                raise HTTPException(422, "findings is a list of at most 30")
            mine["findings"] = _taxa(_findings(body["findings"]),   # an unchanged name keeps its taxon, unasked
                                     {f["scientific"]: f["taxon"] for f in was.get("findings") or [] if f.get("scientific") and f.get("taxon")})
        sets.append("analysis = analysis || %s"); vals.append(Jsonb(mine))
    if not sets:
        raise HTTPException(422, "nothing to change: note, kind, meta, findings or confirm")
    with _db.db() as con, con.cursor() as cur:
        cur.execute(f"UPDATE captures SET {', '.join(sets)} WHERE id = %s RETURNING *", (*vals, cid))
        row = cur.fetchone()
    if not row:
        raise HTTPException(404, "no such capture")
    return {"ok": True, "capture": {k: (v.isoformat() if isinstance(v, datetime) else v) for k, v in row.items()}}


@router.delete("/captures/{cid}")
def capture_delete(cid: int, request: Request, authorization: str = Header("")):
    """Delete an image: the row and its file. The admin token (or this machine) only: the act token may add an
    image and edit its words, never destroy one."""
    if not _is_local(request):
        _admin(authorization)
    with _db.db() as con, con.cursor() as cur:
        cur.execute("DELETE FROM captures WHERE id = %s RETURNING file", (cid,))
        row = cur.fetchone()
        if row:   # a thing added from this photo stays, without a link to a picture that is gone
            cur.execute("UPDATE things SET capture_id = NULL WHERE capture_id = %s", (cid,))
    if not row:
        raise HTTPException(404, "no such capture")
    path = os.path.join(CAPTURES_DIR, os.path.basename(row["file"]))
    if os.path.isfile(path):
        os.remove(path)
    return {"ok": True, "deleted": cid}


@router.get("/captures/{cid}/file")
def capture_file(cid: int, request: Request, authorization: str = Header(""), w: int = Query(0, ge=0, le=1024)):
    """The picture itself. Token only, like the row; the name is this node's own, never a client's path. `?w=` makes a
    JPEG at most that many pixels a side, for a table's thumbnail: a drone picture is 11 MB."""
    _captures_auth(request, authorization)
    from fastapi.responses import FileResponse, Response  # noqa: PLC0415
    rows = _db.q("SELECT file, mime FROM captures WHERE id = %s", cid)
    if not rows:
        raise HTTPException(404, "no such capture")
    path = os.path.join(CAPTURES_DIR, os.path.basename(rows[0]["file"]))
    if not os.path.isfile(path):
        raise HTTPException(404, "the row is here but the file is gone from the captures folder")
    if w:
        import io  # noqa: PLC0415
        from PIL import Image  # noqa: PLC0415
        # ponytail: resized on every ask; a thumbnail cache beside the file when a table of hundreds feels slow
        im = Image.open(path).convert("RGB")
        im.thumbnail((w, w))
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=80)
        return Response(buf.getvalue(), media_type="image/jpeg", headers={"Cache-Control": "private, max-age=86400"})
    return FileResponse(path, media_type=rows[0]["mime"])


# ---------------------------------------------------------------- the image model (SPEC_eyes step 2)
# A local vision model describes an image and lists what it sees, each finding filed under a class of the Fab City
# flows profile, so a tree in a picture and a tree logged as planted are the same word. Only the physical classes:
# a picture cannot see a design file or an hour of work. The picture goes to this machine's Ollama and nowhere else.
FLOWS_VOCAB = "https://planetai.fab.city/vocab/flows/1.0/"
# ponytail: copied from packs/flows/resources.yml (branch flows-pack-2026-09-28); read that file once the pack merges
EYES_CLASSES = ("plant", "animal", "habitat", "food", "water", "compost", "waste_residual", "plastic_waste",
                "packaging", "wood", "metal", "textile", "electronics", "filament", "fuel", "electricity", "part",
                "filter", "furniture", "tool", "appliance", "garment", "micromobility", "vehicle", "goods", "other")
# Two asks, because a 7B vision model asked for JSON straight from the picture invents (node #1, 12 Oct: dogs, cats
# and a reef on a drone shot of roofs, looping until cut off). Looking first, in words, and filing those words second
# keeps every finding to something the description said.
EYES_LOOK = ("A household took this picture of its own place ({kind}, near {city}){note}. Describe what is in it in a "
             "short paragraph: the living things (plants and trees, with the species when you can tell, and animals), "
             "what is built or made, and anything that is a problem for the place, such as rubbish, smoke, a spill or "
             "damage. Say only what you can actually see. Do not describe people.")
EYES_FILE = ("Here is a description of a picture:\n\n{summary}\n\nList each kind of thing the description says is "
             "there, once, as a finding, and leave out anything it says is absent. class: plant is any living plant or "
             "tree, animal any animal, habitat is ground made living, waste_residual and plastic_waste are rubbish, a "
             "made thing goes under its own class or goods, a car, motorbike or truck is vehicle, and other is "
             "buildings, roads and anything else. "
             "name: as specific as the description is. count: only when the description gives a number, else null. "
             "issue: true only when the description says it is a problem. scientific: for a plant or animal only, its "
             "scientific name at the rank you are sure of (a species such as Cocos nucifera, a genus such as Plumeria, "
             "or a family such as Arecaceae), else null. Never people.")
_EYES_TASKS: set = set()   # strong refs, so an automatic description is not collected half way


async def _describe(cid: int, model: str) -> dict:
    """Ask the local vision model about one capture and keep what it says, marked as the model's. Raises with a
    sentence a person can act on when the model or the file is not there."""
    import asyncio, base64, io  # noqa: E401, PLC0415
    from PIL import Image  # noqa: PLC0415
    rows = _db.q("SELECT file, kind, note FROM captures WHERE id = %s", cid)
    if not rows:
        raise HTTPException(404, "no such capture")
    path = os.path.join(CAPTURES_DIR, os.path.basename(rows[0]["file"]))
    if not os.path.isfile(path):
        raise HTTPException(404, "the file is gone from the captures folder")
    im = Image.open(path).convert("RGB")
    im.thumbnail((1024, 1024))   # what a 7B vision model can use; a drone's 20 MP would only cost minutes
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=85)
    note = (rows[0]["note"] or "").strip()
    look = EYES_LOOK.format(kind=rows[0]["kind"], city=os.getenv("NODE_CITY", "") or NODE,
                            note=f"; the household wrote: {note[:200]}" if note else "")
    schema = {"type": "object", "required": ["findings"], "properties": {
        "findings": {"type": "array", "maxItems": 12, "items": {"type": "object", "required": ["class", "name"], "properties": {
            "class": {"type": "string", "enum": list(EYES_CLASSES)}, "name": {"type": "string"},
            "count": {"type": ["integer", "null"]}, "issue": {"type": "boolean"},
            "scientific": {"type": ["string", "null"]}}}}}}
    url = os.getenv("OLLAMA_URL", "http://host.docker.internal:11434")

    async def ask(hc, msg, num, fmt=None):
        r = await hc.post(url + "/api/chat", json={"model": model, "stream": False, "messages": [msg],
                                                   "options": {"temperature": 0, "num_predict": num},
                                                   **({"format": fmt} if fmt else {})})
        # The detail reaches the Data door, so it is said in the household's words; the admin's is the log's.
        if r.status_code == 404:
            log.warning("eyes: %s is not pulled on this machine (ollama pull %s)", model, model)
            raise HTTPException(503, "No image reader is set up on this node yet.")
        if r.status_code >= 400:
            log.warning("eyes: %s answered %s: %s", model, r.status_code, r.text[:200])
            raise HTTPException(502, "The image reader did not answer; try again later.")
        return r.json()["message"]["content"]
    try:
        async with httpx.AsyncClient(timeout=600) as hc:
            summary = (await ask(hc, {"role": "user", "content": look,
                                      "images": [base64.b64encode(buf.getvalue()).decode()]}, 500)).strip()
            filed = EYES_FILE.format(summary=summary)
            out = json.loads(await ask(hc, {"role": "user", "content": filed}, 900, schema))
    except httpx.HTTPError as e:
        log.warning("eyes: Ollama is not answering at %s (%s)", url, type(e).__name__)
        raise HTTPException(503, "The image reader did not answer; try again later.") from None
    except (KeyError, ValueError, TypeError) as e:
        log.warning("eyes: %s answered something that is not the shape asked for (%s)", model, type(e).__name__)
        raise HTTPException(502, "The image reader did not answer; try again later.") from None
    findings = await asyncio.to_thread(_taxa, _findings(out.get("findings") or []))
    analysis = {"model": model, "where": "local", "vocab": FLOWS_VOCAB, "asked": [look, EYES_FILE],
                "at": datetime.now(timezone.utc).isoformat(), "summary": summary[:1500],
                "findings": findings, "by": "model", "confirmed_by": None}
    with _db.db() as con, con.cursor() as cur:
        cur.execute("UPDATE captures SET analysis = %s WHERE id = %s", (Jsonb(analysis), cid))
    return analysis


def _findings(raw: list) -> list:
    """A list of findings as the node keeps them, whoever wrote it: a known class or other, a name, a count or none."""
    out = []
    for f in raw[:30]:
        if not isinstance(f, dict) or str(f.get("name") or "").strip().lower() in ("", "none", "null", "n/a", "nothing"):
            continue   # a small model walks the class list and files "none" under each
        cnt = f.get("count")
        row = {"class": f.get("class") if f.get("class") in EYES_CLASSES else "other",
               "name": str(f["name"]).strip()[:120],
               "count": cnt if isinstance(cnt, int) and not isinstance(cnt, bool) and cnt >= 0 else None,
               "issue": f.get("issue") is True}
        sci = " ".join(str(f.get("scientific") or "").split())[:120]
        if row["class"] in TAXON_KINGDOM and sci.lower() not in ("", "none", "null", "n/a", "unknown"):
            row["scientific"] = sci   # only a living thing has a species; a taxon is the node's, never taken from a body
        out.append(row)
    return out


# SPEC_species step 1: a plant or animal finding's scientific name, matched to the GBIF Backbone (CC BY 4.0) when the
# household said yes to SPECIES_MATCH. The name goes, nothing else. strict=true, because a fuzzy match turns a typo
# into some other living thing; and a match in the wrong kingdom (a plant named like a beetle) is no match.
TAXON_KINGDOM = {"plant": "Plantae", "animal": "Animalia"}
GBIF_MATCH = "https://api.gbif.org/v1/species/match"


def _taxa(findings: list, known: dict | None = None) -> list:
    """Give each living finding with a scientific name its taxon: carried over from `known` (scientific -> taxon, the
    row's earlier findings) when the name is unchanged, else asked of GBIF when the household allows it. The rank is
    what GBIF matched, never what the model claimed: "Arecaceae" stays a family. No yes, no answer or no match, and
    the finding keeps its typed name with no taxon."""
    from main import state  # noqa: PLC0415 — main imports packs: its timers' state and http client
    known = known or {}
    ask = settings.get("SPECIES_MATCH", "off") == "on"
    for f in findings:
        sci = f.get("scientific")
        if not sci:
            continue
        if sci in known:
            f["taxon"] = known[sci]
            continue
        if not ask:
            continue
        try:
            m = httpx.get(GBIF_MATCH, params={"name": sci, "strict": "true"}, timeout=10).json()
        except (httpx.HTTPError, ValueError) as e:
            log.warning("species: GBIF did not answer (%s)", type(e).__name__)
            ask = False   # one failure is enough for this list; the rest keep their typed names
            continue
        if m.get("matchType") in (None, "NONE") or not m.get("usageKey") or m.get("kingdom") != TAXON_KINGDOM[f["class"]]:
            continue
        f["taxon"] = {"key": m["usageKey"], "name": m.get("scientificName") or sci, "rank": str(m.get("rank") or "").lower(),
                      "match": str(m["matchType"]).lower(), "source": "gbif",
                      **({"accepted": m["acceptedUsageKey"]} if m.get("acceptedUsageKey") else {})}
    g, o = state.get("griis"), (state.get("others") or {}).get("cells")
    for f in findings:   # every pass, so a saved finding takes up a checklist read since it was matched
        t = f.get("taxon")
        if t and o is not None:   # what others recorded in the seven cells, under this name or the one it stands for
            t["others"] = sum(c.get(t.get("key")) or c.get(t.get("accepted")) or 0 for c in o.values())
        if not t or not g:
            continue
        t.pop("introduced", None), t.pop("where", None)
        if "marks" in g:   # a synonym is looked up under the name it stands for, too
            mark = g["marks"].get(t.get("key")) or g["marks"].get(t.get("accepted"))
            t.update({"introduced": mark, "where": g["name"]} if mark else {})
        elif g.get("why"):
            t["introduced"], t["where"] = None, g["why"]
    return findings


def _eyes_model() -> str:
    return settings.get("EYES_MODEL", "").strip()


def _describe_later(cid: int) -> bool:
    """The upload's checkbox: describe a new image after its upload has answered, so the phone is not kept waiting.
    False when no image model is set, so the page can say so."""
    import asyncio  # noqa: PLC0415
    model = _eyes_model()
    if not model:
        return False

    async def run():
        try:
            await _describe(cid, model)
        except Exception as e:  # noqa: BLE001 — a failed description leaves the image undescribed, never lost
            log.warning("eyes: capture %s not described: %s", cid, getattr(e, "detail", e))
    t = asyncio.get_running_loop().create_task(run())
    _EYES_TASKS.add(t)
    t.add_done_callback(_EYES_TASKS.discard)
    return True


@router.post("/captures/{cid}/describe")
async def capture_describe(cid: int, request: Request, authorization: str = Header("")):
    """Describe one image with the image model in Set up (EYES_MODEL), now, and answer what it found. A second
    press (a new model, say) replaces the earlier description, and with it any confirmation or edit of that one."""
    _captures_auth(request, authorization)
    model = _eyes_model()
    if not model:
        raise HTTPException(409, "No image reader is set up on this node yet.")
    return {"ok": True, "analysis": await _describe(cid, model)}
