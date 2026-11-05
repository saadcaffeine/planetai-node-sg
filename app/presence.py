"""Presence on Reticulum: GET /presence, what the bridge reads to announce "I am here", and the thread that asks the
bridge who it is and whom it has heard (poll_reticulum).

A module of its own since 24 Oct 2026, moved unchanged out of app/main.py (review item 15). The announced cell is a
coarse parent of the node's own, never finer than PRESENCE_RES_FLOOR, whatever a settings box says. /presence is on
the `off` list because the bridge is another container with no token, and it says nothing until presence is on.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter

import settings
import sources

log = logging.getLogger("planetai")
NODE = os.getenv("NODE_NAME", "node")
RETICULUM_URL = os.getenv("RETICULUM_URL", "").strip()       # the reticulum bridge, e.g. http://reticulum:4243

# What the Reticulum bridge says about itself, refreshed on its own thread. /health is called every
# twenty seconds by every screen in the house, so it must never make an outbound request of its own:
# a bridge that is down would turn the node's own health check into a timeout.
reticulum_state = {"ok": False, "address": None, "destinations": 0, "announce_s": None,
                   "announcing": False, "peers": [], "last": None}

router = APIRouter()


def poll_reticulum() -> None:
    """Ask the bridge who it is. It announces itself on Reticulum every RETICULUM_ANNOUNCE_S — an
    "I am here, I am planetai <node>" with no data attached — and this is the node's only window
    onto whether that is actually happening."""
    if not RETICULUM_URL:
        return
    r = httpx.get(f"{RETICULUM_URL}/health", timeout=5).json()
    peers = []
    try:
        peers = httpx.get(f"{RETICULUM_URL}/peers", timeout=5).json().get("peers", [])
    except Exception as e:  # noqa: BLE001 — an older bridge has no /peers, which is not an error
        log.debug("reticulum: no peers from the bridge (%s)", e)
    reticulum_state.update({"ok": bool(r.get("ok")), "address": r.get("address"),
                            "destinations": r.get("destinations", 0),
                            "announce_s": int(os.getenv("RETICULUM_ANNOUNCE_S", "1800")),
                            "announcing": bool(r.get("announcing")),
                            "peers": _with_distance(peers),
                            "last": datetime.now(timezone.utc).isoformat()})


def _with_distance(peers: list[dict]) -> list[dict]:
    """How far each heard node is, from its coarse cell to ours. Neither end published a position.

    The distance is between two cell CENTRES, so it carries the coarseness of whichever cell is
    blunter — at res 3 two nodes in the same cell read 0 km and are somewhere within sixty. That is
    the point of it, and `res` travels with the answer so the page can say so.
    """
    here = _node_cell()
    out = []
    for p in peers or []:
        row = {k: p.get(k) for k in ("node", "cell", "res", "version", "kind", "first", "last", "hash")}
        row["km"] = None
        try:
            import h3  # noqa: PLC0415
            if here and here.get("id") and p.get("cell"):
                a = h3.cell_to_latlng(h3.cell_to_parent(here["id"], int(p["res"])))
                b = h3.cell_to_latlng(p["cell"])
                row["km"] = round(sources.km(a[0], a[1], b[0], b[1]))
        except Exception as e:  # noqa: BLE001 — a malformed cell from a stranger must not break the poll
            log.debug("reticulum: no distance for %s (%s)", p.get("node"), e)
        out.append(row)
    return sorted(out, key=lambda r: (r["km"] is None, r["km"] or 0))


# Nothing finer than this may be announced. res 6 is roughly 3 km across; below that a node is
# telling an open radio network which neighbourhood it is in, and that is not a thing anyone should
# be able to do by typing a number into a settings box.
PRESENCE_RES_FLOOR = 6


def _presence_res() -> int:
    try:
        r = int(settings.get("RETICULUM_PRESENCE_RES", "3") or 3)
    except ValueError:
        return 3
    return max(0, min(r, PRESENCE_RES_FLOOR))


@router.get("/presence")
def presence():
    """What this node is willing to announce about itself, and whether it is announcing at all.

    The Reticulum bridge asks this — it has no h3 and no settings of its own — and announces exactly
    what comes back, or nothing when `enabled` is false. Open on purpose at every share level: when
    presence is on, this is the same handful of facts the node is already broadcasting to any radio
    within reach, and when it is off it answers with nothing but that.

    The cell is the node's own res-8 cell rounded UP to a coarse parent: at the default res 3 that is
    an area about sixty kilometres across, which names an island and not an address. Distance between
    two nodes is then two cell centres, and neither of them ever published a position.
    """
    on = settings.get("RETICULUM_PRESENCE", "0") == "1"
    if not on:
        return {"enabled": False}
    here = _node_cell()
    res = _presence_res()
    cell = None
    if here and here.get("id"):
        try:
            import h3  # noqa: PLC0415 — only this path needs it
            cell = h3.cell_to_parent(here["id"], res)
        except Exception as e:  # noqa: BLE001
            log.warning("presence: could not coarsen %s to res %d (%s)", here.get("id"), res, e)
    return {"enabled": True, "node": NODE, "cell": cell, "res": res,
            "version": os.getenv("NODE_VERSION", "?"), "kind": os.getenv("NODE_KIND", "") or None}


def _node_cell() -> dict | None:
    """This node's own cell, as /health names it (app/main.py::_cell, which /health and the export share)."""
    from main import _cell           # noqa: PLC0415 — main imports this module
    return _cell()
