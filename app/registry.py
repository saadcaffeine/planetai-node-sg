"""The network's source registry, as the node carries it. Domain-blind.

    load()    -> (entries, version)   the vendored snapshot of awesome-fabcity-data
    find()    -> entries, filtered

`data/sources/` is a pinned copy of the registry (tools/sync_registry.sh), mounted read-only. It is
what the network has decided can be measured at each pillar and scale — 209 rows at the time of
writing, against the fourteen sources a node actually reads.

That gap is the point. `index.cells()` can only emit rows this node can compute, so the cell nobody
has an adapter for is simply absent from `/cells`, and until now absent meant unanswerable. The
registry answers it: `GET /sources?cell=Social|City` says what is filed for that cell, and each
entry's `adapter` — `core:ckan`, `pack:coast` — says which of it anything here reads yet.

This module names no metric, no source and no pillar. It loads, filters and serves; every word of
vocabulary in it came out of the registry's own schema. Adding a source is still a PR upstream and a
re-pin (docs/SOURCES.md), never a change here.

Reads index.json, not the YAML beside it: the same one file `bin/planetai` reads, with the standard
library, because a node's Python has no PyYAML.
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path

log = logging.getLogger("planetai.registry")
SOURCES_DIR = Path(os.getenv("SOURCES_DIR", "/app/data/sources"))

_cache: dict = {"mtime": None, "entries": [], "version": {}}


def load() -> tuple[list[dict], dict]:
    """(entries, version). Cached on index.json's mtime, so a re-pin applied by `planetai update`
    is picked up without a restart and a hot path does not re-read 209 entries every request."""
    index = SOURCES_DIR / "index.json"
    if not index.is_file():
        return [], {}
    mtime = index.stat().st_mtime
    if _cache["mtime"] != mtime:
        try:
            entries = json.loads(index.read_text())
            ver = {}
            vp = SOURCES_DIR / "REGISTRY_VERSION"
            if vp.is_file():
                ver = dict(l.split("=", 1) for l in vp.read_text().split() if "=" in l)
            ver["entries"] = len(entries)
            _cache.update(mtime=mtime, entries=entries, version=ver)
        except Exception as e:  # noqa: BLE001
            log.warning("source registry at %s did not load: %s", index, e)
            return [], {}
    return _cache["entries"], _cache["version"]


def find(pillar: str = "", scale: str = "", pilot: str = "", cell: str = "",
         wired: bool | None = None, status: str = "") -> list[dict]:
    """Every filter is AND, and an empty one matches everything.

    `wired` keeps its name on the wire — nothing that worked yesterday stops working — but reads the
    registry's `adapter`, a string naming the code, rather than the `wired_in_planetai` boolean that
    is deprecated upstream. Same question, asked of something that can be checked.

    `status` is the registry's own word — live, candidate, stale, deprecated, paywalled, planned —
    and filtering on it is how a reader asks for the half of the list a node could actually call.

    `pilot` is the exception worth knowing: an entry relevant to `global` is relevant to every pilot,
    so asking for Bali returns Bali's sources AND the planet-wide ones. A node asking what it could
    measure wants both, and the registry's own `pilot_relevance` is where that word comes from."""
    entries, _ = load()
    out = []
    for e in entries:
        if pillar and e.get("pillar") != pillar:
            continue
        if scale and e.get("scale") != scale:
            continue
        if cell and e.get("cell") != cell:
            continue
        if status and e.get("status") != status:
            continue
        if wired is not None and bool(e.get("adapter")) is not wired:
            continue
        if pilot:
            rel = e.get("pilot_relevance") or []
            if pilot not in rel and "global" not in rel:
                continue
        out.append(e)
    return out


def one(slug: str) -> dict | None:
    entries, _ = load()
    return next((e for e in entries if e.get("slug") == slug), None)


# The verdicts that back a `live` status upstream. Named here once because two functions ask it and
# because it is the registry's word, not this repo's: schema/review.schema.json.
USABLE = ("usable", "usable-with-caveats")


def cell_counts() -> dict[str, dict[str, int]]:
    """{cell: {"capable", "reviewed", "candidate"}} — three honest numbers per cell.

    This replaces counts_by_cell(), which answered a question nobody was asking. Two changes.

    **What a cell is counted FROM.** An entry is counted against every cell in its `feeds_cells` —
    the cells a node can actually fill from it — and only against its own path-derived `cell` when
    `feeds_cells` is ABSENT, so nothing vanishes from the numbers merely because nobody has
    backfilled it yet. Present-but-empty is left empty on purpose: the registry's CONTRIBUTING §2b
    says `[]` states something absence does not — code reads this and no Index cell comes out of it
    — and six vendored entries say exactly that. Filed-under and feeds are different questions and
    this is the second one; `bali-air-dispatch` is filed Environmental|Community and feeds
    Environmental|City.

    **What counts at all.** Only two statuses count anywhere. `deprecated`, `stale`, `paywalled` and
    `planned` count nowhere, because a number that includes a source no node can call is the kind of
    number the Index was criticised for. Sixteen of today's 225 entries are in that group.

        capable    status `live` AND an `adapter` — code here reads it
        reviewed   status `live` AND (an `adapter` OR a review whose verdict is in USABLE).
                   That OR is not a shortcut: it mirrors the registry's own join rule exactly
                   (scripts/validate.py, "N live entries carry neither a review nor an adapter"),
                   so this node and the list it carries agree on what backs the word `live`.
        candidate  status `candidate` — verified, and nobody has read it for a real territory

    capable is therefore a subset of reviewed. A cell whose entries are all deprecated still gets a
    key, with three zeros: "registered and nothing usable" is an answer, and a missing key is not."""
    out: dict[str, dict[str, int]] = {}
    entries, _ = load()
    for e in entries:
        cells = e["feeds_cells"] if "feeds_cells" in e else [e.get("cell", "")]
        status, adapter = e.get("status"), bool(e.get("adapter"))
        backed = adapter or any(r.get("verdict") in USABLE for r in (e.get("reviews") or []))
        for c in cells:
            if not c:
                continue
            row = out.setdefault(c, {"capable": 0, "reviewed": 0, "candidate": 0})
            if status == "live" and adapter:
                row["capable"] += 1
            if status == "live" and backed:
                row["reviewed"] += 1
            if status == "candidate":
                row["candidate"] += 1
    return out


def counts_by_cell() -> dict[str, tuple[int, bool]]:
    """DEPRECATED, and removed one release after the one that introduces cell_counts(). Kept for
    exactly one release so this commit does not break index.py's `_row()`, which the next one
    rewires.

    It answers "how many entries are FILED under this cell, and does anything read any of them",
    counting deprecated, stale and paywalled entries as though a node could call them. Use
    cell_counts().

    {cell: (how many registered, does anything read any of them)} — what index.py puts on a row.

    `adapter` is a string naming the code that reads the entry — `core:ckan`, `pack:coast` —
    and its presence is the answer. It replaced `wired_in_planetai`, a boolean typed upstream by hand
    about this repository, which is why sixteen of thirty-two were once ticked including a paywalled
    source no node can call. The string is checked against this repo in the registry's own CI; the
    boolean never could be, and is deprecated there."""
    out: dict[str, tuple[int, bool]] = {}
    entries, _ = load()
    for e in entries:
        n, read = out.get(e.get("cell", ""), (0, False))
        out[e.get("cell", "")] = (n + 1, read or bool(e.get("adapter")))
    return out
