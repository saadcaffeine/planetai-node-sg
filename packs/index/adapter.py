"""Reads this node's Fab City Index place, and the registry, once a day.

Two reads, both plain GETs of public files, neither carrying anything about the house:
  place     INDEX_URL/api/v0/places/<INDEX_PLACE>.json   what the Index says about the place (format fci-api-v0)
  registry  the commit sha of awesome-fabcity-data's main from GitHub, then that commit's index.json, converted to
            the entry shape app/registry.py reads. The body is fetched only when the sha has moved.

Each lands in one row of index_reads (what, sha, fetched_at, ok, error, body). On the `place` row `sha` holds the slug
the row was read for, on success and on failure; on the `registry` row it is the commit. A read that fails or is not
what was asked for never replaces the body: it keeps the last good one and says why in `error`, so a stale file reads
as stale instead of as empty. It keeps it only for the same slug: another place's file is dropped, and a row read for
another slug is not skipped as fresh, so changing INDEX_PLACE is read at the next poll, not a day later. The pack
stores and serves; it computes no score. fetch() returns no readings.
"""
from __future__ import annotations

import contextlib
import datetime as dt
import json
import logging
import os
import re
import sys

sys.path.insert(0, os.path.dirname(__file__))
import place as PL  # noqa: E402

log = logging.getLogger("planetai.index")

REPO = "fabcity/awesome-fabcity-data"
MAX_BYTES = 8 * 1024 * 1024          # a place file is ~50 KB and the registry ~0.7 MB: past 8 MB it is not either

DDL = """
CREATE TABLE IF NOT EXISTS index_reads (
  what       TEXT PRIMARY KEY,         -- place | registry
  sha        TEXT,
  fetched_at TIMESTAMPTZ,
  ok         BOOLEAN,
  error      TEXT,
  body       JSONB
)
"""


def ensure(cur):
    cur.execute(DDL)


def convert(upstream: dict) -> list:
    """index.json (a dict, entries under `entries`, each with `id`, `pillar`, `scale`) → the node's entry shape:
    slug is the id, cell is "<Pillar>|<Scale>" capitalised, every other key stays, reviews default to []."""
    out = []
    for e in upstream["entries"]:
        o = dict(e)
        o["slug"] = e["id"]
        o["cell"] = e["pillar"].capitalize() + "|" + e["scale"].capitalize()
        o.setdefault("reviews", [])
        out.append(o)
    return out


def _get(hc, url: str, headers=None):
    """GET one https URL and return its parsed JSON, refusing anything over MAX_BYTES. The cap protects parsing and
    storage, not the download: the body has already arrived when the header and the length are checked."""
    assert url.startswith("https://"), url
    r = hc.get(url, headers=headers or {}, timeout=20)
    r.raise_for_status()
    if int(r.headers.get("content-length") or 0) > MAX_BYTES or len(r.content) > MAX_BYTES:
        raise ValueError("the answer is over 8 MB")
    return r.json()


def _put(cur, what, now, ok, error, sha=None, body=None, keep=lambda body: True):
    """Upsert one row. A failed read passes no body, and the row keeps the one it had unless keep(body) says that body is
    not this read's to keep (a place file for a place the node is no longer configured for). It keeps its old sha too
    unless a sha is passed: the place row passes its slug on failure as well, the registry row passes none."""
    cur.execute("SELECT sha, fetched_at, ok, error, body FROM index_reads WHERE what = %s", (what,))
    prev = cur.fetchone() or (None, None, None, None, None)
    sha = sha if ok or sha is not None else prev[0]
    body = body if ok else prev[4] if prev[4] is not None and keep(prev[4]) else None
    cur.execute("INSERT INTO index_reads (what, sha, fetched_at, ok, error, body) VALUES (%s, %s, %s, %s, %s, %s::jsonb) "
                "ON CONFLICT (what) DO UPDATE SET sha = EXCLUDED.sha, fetched_at = EXCLUDED.fetched_at, "
                "ok = EXCLUDED.ok, error = EXCLUDED.error, body = EXCLUDED.body",
                (what, sha, now, ok, error, None if body is None else json.dumps(body)))


def _prev(cur, what):
    cur.execute("SELECT sha, fetched_at, ok, error, body FROM index_reads WHERE what = %s", (what,))
    return cur.fetchone()


def _is(body, slug) -> bool:
    p = body.get("place") if isinstance(body, dict) else None
    return isinstance(p, dict) and p.get("slug") == slug


def _place(hc, cur, slug, now) -> bool:
    try:
        base = (os.getenv("INDEX_URL") or "https://index.fab.city").rstrip("/")
        body = _get(hc, f"{base}/api/v0/places/{slug}.json")
        if body.get("format") != "fci-api-v0":
            raise ValueError(f"not the Index's format: format is {body.get('format')!r}, not 'fci-api-v0'")
    except Exception as e:  # noqa: BLE001
        _put(cur, "place", now, False, str(e), sha=slug, keep=lambda b: _is(b, slug))
        return False
    _put(cur, "place", now, True, None, sha=slug, body=body)
    return True


def _registry(hc, cur, now) -> bool:
    try:
        sha = _get(hc, f"https://api.github.com/repos/{REPO}/commits/main",
                   {"Accept": "application/vnd.github+json"})["sha"]
        if not isinstance(sha, str) or not re.fullmatch(r"[0-9a-f]{40}", sha):
            raise ValueError(f"not a commit sha: {str(sha)[:40]!r}")
        prev = _prev(cur, "registry")
        if prev and prev[0] == sha and prev[2] and prev[4] is not None:
            body = prev[4]              # same commit, same file: touch the row, fetch nothing
        else:
            body = convert(_get(hc, f"https://raw.githubusercontent.com/{REPO}/{sha}/index.json"))
    except Exception as e:  # noqa: BLE001
        _put(cur, "registry", now, False, str(e))
        return False
    _put(cur, "registry", now, True, None, sha=sha, body=body)
    return True


def read(hc, cur, slug, now) -> dict:
    """At most the two reads. A slug the Index does not track is said in the place row and nothing is requested,
    the registry included: a node pointed at a typo has nothing to ask for until it is fixed."""
    ensure(cur)
    if not PL.known(slug, PL.load()):
        _put(cur, "place", now, False, f"not an Index place: {slug}", sha=slug, keep=lambda b: _is(b, slug))
        return {"place": False, "registry": False}
    return {"place": _place(hc, cur, slug, now), "registry": _registry(hc, cur, now)}


@contextlib.contextmanager
def _cursor():
    import psycopg
    with psycopg.connect(os.environ["DATABASE_URL"], autocommit=True) as con:
        with con.cursor() as cur:
            yield cur


def _now():
    return dt.datetime.now(dt.timezone.utc)


def fetch(hc):
    """The node's poll calls this often; it reads when the last `place` row is older than INDEX_REFRESH_HOURS, or was
    read for another slug. A failed read is dated too, so a host that is down is asked once a day, not at every poll."""
    slug = os.getenv("INDEX_PLACE", "").strip()
    if not slug:
        return [], []
    hours = float((os.getenv("INDEX_REFRESH_HOURS") or "").strip() or "24")
    now = _now()
    with _cursor() as cur:
        ensure(cur)
        last = _prev(cur, "place")
        if last and last[0] == slug and last[1] and now - last[1] < dt.timedelta(hours=hours):
            return [], []
        r = read(hc, cur, slug, now)
    if not all(r.values()):
        log.warning("index pack: %s", {k: "ok" if v else "failed" for k, v in r.items()})
    return [], []
