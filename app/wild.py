"""Every pack a node could run, and installing a wild one from the page (docs/decisions/2026-10-27-pack-install-from-the-page.md).

GET /packs/all        every pack folder here and every pack on the wild list, each installed or not, on or not
GET /packs/preview    what a wild pack is before it is fetched: author, repository, commit, pip: lines (admin token)
POST /packs/install   ask the host to install one (admin token); GET /packs/install says how it is going

The app never writes packs/: it is mounted read-only. It writes one request into out/requests/, and the host's
crontab line runs `planetai packs pending`, which reads the wild list again by itself, checks the commit, and runs
the same `packs add` a terminal runs. Only an id on the list and the commit that was shown cross that line.
"""
from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path

import yaml
from fastapi import APIRouter, Header, HTTPException

import packs
import requires
import settings
from auth import _admin
from db import db

WILD_INDEX = "https://raw.githubusercontent.com/fabcity/planetai-wild-packs/main/packs.json"   # as bin/planetai's
WILD_EVERY = 3600
REQUESTS = Path(os.getenv("PACK_OUT", "/app/out")) / "requests"
REQUEST, STATUS = REQUESTS / "pack-add.json", REQUESTS / "pack-add.status"
STUCK_S = 180          # a request older than this was not picked up: the crontab line is missing
SHA = re.compile(r"^[0-9a-f]{40}$")
SOURCE = re.compile(r"^([A-Za-z0-9._-]+)/([A-Za-z0-9._-]+)((?:/[A-Za-z0-9._-]+)*)$")

router = APIRouter()
_LIST: dict = {"at": 0.0, "rows": None, "error": None}


def _client():
    import httpx
    return httpx.Client(timeout=20, headers={"User-Agent": "planetai-node"}, follow_redirects=True)


def listed(max_age: float = WILD_EVERY) -> list[dict] | None:
    """The wild list, read at most once in `max_age` seconds. None when it has never been read; a failed read keeps
    the last good list and says why in `_LIST["error"]`."""
    if time.time() - _LIST["at"] >= max_age:
        _LIST["at"] = time.time()
        try:
            with _client() as c:
                r = c.get(WILD_INDEX)
                r.raise_for_status()
                d = r.json()
            if not isinstance(d, list):
                raise ValueError("the wild list is not a list")
            _LIST.update(rows=[e for e in d if isinstance(e, dict) and isinstance(e.get("id"), str)], error=None)
        except Exception as e:  # noqa: BLE001 — a node with no route out still lists what is on its disk
            _LIST["error"] = type(e).__name__
    return _LIST["rows"]


def _wild_meta(d: Path) -> dict:
    """`.wild` beside a pack `packs add` fetched: where it came from and at which commit."""
    out = {}
    for line in (d / ".wild").read_text().splitlines():
        k, _, v = line.partition("=")
        out[k] = v
    return out


def _code(d: Path) -> bool:
    return (d / "adapter.py").is_file() or (d / "hooks.py").is_file()


def all_packs(new_since: dict | None = None) -> dict:
    """Every pack folder on disk and every wild-list entry not on disk. `on` is the Set up switch (in PACKS_ENABLED,
    or that list is empty); `loaded` is whether the node runs it now; `why` says why an installed pack is not."""
    only = {p for p in settings.get("PACKS_ENABLED", "").replace(" ", "").split(",") if p}
    here, allow = os.getenv("NODE_VERSION", ""), packs._allow_code()
    rows, entries = [], {e["id"]: e for e in (listed() or [])}
    for d in sorted(packs.PACKS_DIR.iterdir()) if packs.PACKS_DIR.is_dir() else []:
        if not (d / "pack.yaml").is_file():
            continue
        m = packs._manifest(d)
        wild = (d / ".wild").is_file()
        on = not only or d.name in only
        why = requires.check((m.get("requires") or {}).get("node"), here)
        if not why and not on:
            why = "switched off"
        if not why and _code(d) and not (allow or packs._official_on(d)):
            why = "a code pack, waiting for Allow code packs" if wild else "a code pack, waiting for its switch or Allow code packs"
        e = entries.get(d.name, {})
        rows.append({"id": d.name, "name": m.get("name") or d.name, "description": m.get("description") or "",
                     "author": m.get("author") or e.get("author") or "", "version": m.get("version") or "",
                     "kind": "code" if any(d.glob("*.py")) else "data", "domain": m.get("domain") or "",
                     "tier": "wild" if wild else "core", "installed": True, "on": on, "loaded": not why, "why": why,
                     **({"source": e.get("source") or _wild_meta(d).get("source"), "commit": _wild_meta(d).get("commit"),
                         "added": _wild_meta(d).get("added"), "status": e.get("status") or "not on the list",
                         "reads": e.get("reads") or ""} if wild else {})})
    have = {r["id"] for r in rows}
    for e in entries.values():
        if e["id"] in have:
            continue
        rows.append({"id": e["id"], "name": e.get("name") or e["id"], "description": e.get("reads") or "",
                     "author": e.get("author") or "", "kind": e.get("kind") or "", "tier": "wild", "installed": False,
                     "on": False, "loaded": False, "why": "not installed", "source": e.get("source") or "",
                     "status": e.get("status") or "listed", "reads": e.get("reads") or "", "licence": e.get("licence") or "",
                     "tested_with": e.get("tested_with") or "", "new": e["id"] in (new_since or {})})
    return {"packs": rows, "list": {"url": WILD_INDEX, "read": _LIST["rows"] is not None, "error": _LIST["error"]}}


@router.get("/packs/all")
def packs_all():
    """Every pack this node could run: core and wild, installed or not, on or not, and why one is not loaded."""
    try:   # the packs said new in the last fortnight (check_wild in app/main.py), for the Packs section's mark
        with db() as con, con.cursor() as cur:
            cur.execute("SELECT substr(version, 6) FROM release_notices WHERE version LIKE 'pack:%%' "
                        "AND told_at > now() - interval '14 days'")
            new = {r[0]: True for r in cur.fetchall()}
    except Exception:  # noqa: BLE001 — the list does not need the database to be drawn
        new = {}
    return all_packs(new)


def _entry(pid: str) -> dict:
    e = next((x for x in (listed() or []) if x.get("id") == pid), None)
    if not e:
        raise HTTPException(404, f"{pid} is not on the wild list" + ("" if _LIST["rows"] is not None else
                                                                     ", which this node could not read"))
    if not SOURCE.match(str(e.get("source", ""))) or "/../" in f"/{e['source']}/":
        raise HTTPException(502, f"the wild list gives {pid} a source that is not owner/repo[/folder]")
    return e


def resolve(e: dict, c) -> str:
    """The commit a listed pack is installed at: the entry's pinned `commit`, else the head of its repository now.
    `planetai packs pending` resolves it the same way and refuses a request naming any other."""
    if SHA.match(str(e.get("commit") or "")):
        return e["commit"]
    owner, repo, _ = SOURCE.match(e["source"]).groups()
    r = c.get(f"https://api.github.com/repos/{owner}/{repo}/commits/HEAD", headers={"Accept": "application/vnd.github.sha"})
    r.raise_for_status()
    if not SHA.match(r.text.strip()):
        raise ValueError("GitHub did not answer with a commit")
    return r.text.strip()


def _lines(v) -> list[str]:
    return [str(x) for x in v] if isinstance(v, list) else [str(v)] if v else []


@router.get("/packs/preview")
def preview(id: str, authorization: str = Header("")):
    """What installing `id` would bring, read from its pack.yaml at the commit it would be installed at. Writes
    nothing. The commit returned is the one POST /packs/install must carry."""
    _admin(authorization)
    e = _entry(id)
    owner, repo, folder = SOURCE.match(e["source"]).groups()
    try:
        with _client() as c:
            sha = resolve(e, c)
            r = c.get(f"https://raw.githubusercontent.com/{owner}/{repo}/{sha}{folder}/pack.yaml")
            r.raise_for_status()
            m = yaml.safe_load(r.text) or {}
    except Exception as ex:  # noqa: BLE001
        raise HTTPException(502, f"could not read {id}'s pack.yaml from GitHub ({type(ex).__name__})") from None
    d = packs.PACKS_DIR / id
    clash = d.is_dir() and not (d / ".wild").is_file()
    return {"id": id, "name": m.get("name") or e.get("name") or id, "author": m.get("author") or e.get("author") or "",
            "status": e.get("status") or "listed", "reads": e.get("reads") or "", "licence": e.get("licence") or "",
            "source": e["source"], "commit": sha, "code_url": f"https://github.com/{owner}/{repo}/tree/{sha}{folder}",
            "kind": m.get("kind") or e.get("kind") or "", "description": m.get("description") or "",
            "metrics": _lines(m.get("metrics")), "needs": m.get("needs") or "", "pip": _lines(m.get("pip")),
            "settings": [s.split("=")[0].strip() for s in _lines(m.get("env")) if s.strip() and not s.lstrip().startswith("#")],
            "loads_here": requires.check((m.get("requires") or {}).get("node"), os.getenv("NODE_VERSION", "")),
            "installed_at": _wild_meta(d).get("commit") if (d / ".wild").is_file() else None,
            "refused": f"packs/{id} is a core pack here; a wild pack never replaces it" if clash else None}


def _read(f: Path) -> dict | None:
    try:
        return json.loads(f.read_text())
    except (OSError, ValueError):
        return None


@router.get("/packs/install")
def install_status(authorization: str = Header("")):
    """How the last install is going: waiting (the host has not picked it up), running, done or failed."""
    _admin(authorization)
    req = _read(REQUEST)
    if req:
        age = time.time() - REQUEST.stat().st_mtime
        return {**req, "state": "waiting", "waited_s": int(age), "stuck": age > STUCK_S}
    return _read(STATUS) or {"state": "idle"}


@router.post("/packs/install")
def install(body: dict, authorization: str = Header(""), x_agent: str = Header("")):
    """{"id": "bmkg-synop", "commit": "<the 40 hex /packs/preview returned>"}. Writes the request the host picks up
    within a minute. A person installs a pack: a call that says it is an agent is refused, and no MCP tool calls this."""
    _admin(authorization)
    if x_agent:
        raise HTTPException(403, "a person installs a pack, from Set up › Packs; an agent does not")
    pid, sha = str(body.get("id", "")), str(body.get("commit", ""))
    _entry(pid)
    if not SHA.match(sha):
        raise HTTPException(400, "commit must be the 40-character commit /packs/preview returned")
    d = packs.PACKS_DIR / pid
    if d.is_dir():
        raise HTTPException(409, f"packs/{pid} is a core pack here; a wild pack never replaces it" if not (d / ".wild").is_file()
                            else f"{pid} is installed already. To update it, on the node: planetai packs add {pid}")
    now = install_status(authorization)
    if now["state"] == "waiting" or (now["state"] == "running" and time.time() - now.get("t", 0) < 1800):
        raise HTTPException(409, f"{now.get('id')} is being installed: {now.get('line') or now['state']}")
    REQUESTS.mkdir(parents=True, exist_ok=True)
    tmp = REQUEST.with_suffix(".tmp")
    tmp.write_text(json.dumps({"id": pid, "commit": sha, "at": int(time.time())}))
    tmp.replace(REQUEST)
    with db() as con, con.cursor() as cur:
        cur.execute("INSERT INTO actions (alert_id, stage, actor, note) VALUES (NULL, 'settings', 'gui', %s)",
                    (f"pack install asked: {pid} at {sha[:12]}",))
    return {"state": "waiting", "id": pid, "commit": sha}
