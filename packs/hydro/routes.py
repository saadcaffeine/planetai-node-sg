"""GET /hydro: what the hydro pack kept for this node's square, for the Place map's water rows.

**On no SHARE_LEVEL allowlist** (pack.yaml has no `share:`), like /place/geojson: the nearest river's distance and the
basin that holds the node, drawn, give away the point /health rounds on purpose. This machine or a token.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

from fastapi import APIRouter

router = APIRouter()

_spec = importlib.util.spec_from_file_location("planetai_pack_hydro_adapter_for_routes", Path(__file__).with_name("adapter.py"))
pack = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pack)  # type: ignore[union-attr]


@router.get("/hydro")
def hydro():
    """The rivers and level-12 basins in the square, the nearest and largest river with their sentences, and the
    node's basin at levels 12 and 4. Empty, with the command that fills it, until `planetai run hydro fetch`."""
    r = pack.result()
    if not r:
        return {"node": pack.node(), "rivers": None, "basins": None, "hint": "nothing kept yet: planetai run hydro fetch",
                "attribution": pack.ATTRIBUTION}
    return {**r, "node": pack.node(),
            "sentence": pack.sentence(r["nearest"]) if r.get("nearest") else None,
            "largest_sentence": pack.sentence(r["largest"]) if r.get("largest") else None}
