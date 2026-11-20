"""The dashboard hero's ground: this node's own H3 cell, drawn from NODE_LAT / NODE_LON.

Until v0.37 every node shipped the same file, `static/node-ground.svg`, which is node #1's cell in
Kuta Selatan. On a Barcelona node it was geometry that looked like the node's own cell and was not,
so the caption naming the cell was stripped and the drawing claimed nothing. This draws the real
one, and the caption goes back because it is now true wherever the node stands.

The drawing is planetai-design's `planetai-geo/index.mjs` nodeGround(), in Python, because the node
has no Node.js and a household LAN may have no route out: the ground has to be computable here.
Same geometry, same projection, same numbers — `tests/test_ground.py` holds the two together by
redrawing node #1's cell and comparing it to the design kit's own output, vertex for vertex.

Projection: Lambert azimuthal equal-area centred on the node, which is d3.geoAzimuthalEqualArea()
.rotate([-lon, -lat]) and is on the design kit's allow-list for this drawing with its reason
recorded (design-log, 7 Sep): the cell is about half a kilometre across, and Equal Earth squashes
east-west by 25% at node #1's latitude. Every vertex is projected and written straight into the
path. d3's adaptive resampling is float noise at this scale and drops vertices from small polygons
without erroring; there is nothing to resample in a hexagon anyway.
"""
from __future__ import annotations

import math
from functools import lru_cache

try:
    import h3
except ImportError:      # the image was built before h3 was a dependency; main.py serves the file
    h3 = None

D = math.pi / 180
SIZE = (900, 600)
BLEED = 0.10             # the disk is fitted 10% outside the frame, so neighbours' edges leave it


def _num(v: float) -> str:
    """Three decimals, trailing zeros dropped — the same string d3-geo's path writes."""
    return f"{v:.3f}".rstrip("0").rstrip(".")


def _projector(lat: float, lon: float):
    """Rotate the sphere so the node is at the origin, then project equal-area about it."""
    cd, sd = math.cos(-lat * D), math.sin(-lat * D)

    def raw(lng: float, la: float) -> tuple[float, float]:
        lo, la = (lng - lon) * D, la * D
        cp = math.cos(la)
        x, y, z = math.cos(lo) * cp, math.sin(lo) * cp, math.sin(la)
        # d3-geo rotation(deltaLambda, deltaPhi), gamma 0
        rl = math.atan2(y, x * cd - z * sd)
        rp = math.asin(max(-1.0, min(1.0, z * cd + x * sd)))
        k = math.sqrt(2 / (1 + math.cos(rl) * math.cos(rp)))
        return k * math.cos(rp) * math.sin(rl), k * math.sin(rp)

    return raw


def _ring(cell: str) -> list[tuple[float, float]]:
    """h3 hands back (lat, lng) counter-clockwise; d3-geo reads an exterior ring clockwise. The
    winding does not change what a single-ring path paints, but it keeps this output comparable to
    the design kit's, which is how the two are held together."""
    b = [(lng, lat) for lat, lng in h3.cell_to_boundary(cell)]
    return [b[0]] + b[:0:-1]


def _edge_m(cell: str) -> int:
    """This cell's own mean edge, in metres. Cells are never regular hexagons and the length varies
    with latitude, so it is measured rather than quoted from a table.

    The measuring moved to `issues.geometry.edge_m` on 21 September 2026, when the grain table, the
    plates and the radio row stopped quoting the global average beside a specific cell's area. This
    is the same number it always was; there is now one function producing it instead of this one
    being right and three other rows being wrong.

    Imported inside the call, not at module scope: `issues.geometry` imports h3 unconditionally and
    this file must stay importable on a machine without it — `facts()` above is what checks, and it
    raises a sentence rather than failing at import and taking `app/main.py` down with it."""
    from issues.geometry import edge_m       # noqa: PLC0415 — see the paragraph above
    return edge_m(cell)


@lru_cache(maxsize=4)
def facts(lat: float, lon: float) -> dict:
    """The cell this node stands in, and the one line that says so.

    The design kit stamps that line inside the drawing, at the foot of a 900x600 frame. The
    dashboard cannot: the hero scales the ground with `object-fit: cover`, so at 1440 the foot of
    the frame is cropped away and at 390 the left of it is, taking the cell id with it and leaving
    "· 525 M EDGE · THE CELL THIS NODE STANDS IN" under a cell it no longer names. The line belongs
    to the page, which sets it from /health, and the SVG keeps it in <title> so the file still says
    what it is on its own."""
    if h3 is None:
        raise RuntimeError("h3 is not installed in this image")
    cell = h3.latlng_to_cell(lat, lon, 8)
    edge = _edge_m(cell)
    return {"id": cell, "res": 8, "edge_m": edge,
            "caption": f"{cell} · RES 8 · {edge} M EDGE · THE CELL THIS NODE STANDS IN"}


@lru_cache(maxsize=4)
def centre(lat: float, lon: float) -> tuple[float, float, float]:
    """The centre of the res-8 cell (lat, lon) stands in, and the farthest any point of that cell can be from it (its
    farthest vertex), in metres. What a reader without a token is measured from (R25, main._published_position): a
    distance from here, or a cut round here narrowed or widened by that last number, comes out the same wherever in
    the cell the house stands."""
    if h3 is None:
        raise RuntimeError("h3 is not installed in this image")
    cell = h3.latlng_to_cell(lat, lon, 8)
    c = h3.cell_to_latlng(cell)
    return c[0], c[1], max(h3.great_circle_distance(c, v, unit="m") for v in h3.cell_to_boundary(cell))


@lru_cache(maxsize=4)
def svg(lat: float, lon: float, variant: str = "dark") -> str:
    """The ground for one point. Cached: NODE_LAT and NODE_LON are bootstrap keys, so a node changes
    them by editing .env and restarting, and the drawing takes about a millisecond either way."""
    w, h = SIZE
    cell = facts(lat, lon)["id"]
    disk = h3.grid_disk(cell, 1)
    kids = h3.cell_to_children(cell, 9)
    raw = _projector(lat, lon)

    # fitExtent, as d3 computes it: bounds at scale 150 and no translation, then the scale and
    # offset that put those bounds in the extent.
    pts = [raw(*p) for c in disk for p in _ring(c)]
    xs = [150 * x for x, _ in pts]
    ys = [-150 * y for _, y in pts]
    ex, ey = -w * BLEED, -h * BLEED
    fw, fh = w * (1 + 2 * BLEED), h * (1 + 2 * BLEED)
    k = min(fw / (max(xs) - min(xs)), fh / (max(ys) - min(ys)))
    tx = ex + (fw - k * (max(xs) + min(xs))) / 2
    ty = ey + (fh - k * (max(ys) + min(ys))) / 2

    def path(c: str) -> str:
        d = ""
        for i, (lng, la) in enumerate(_ring(c)):
            x, y = raw(lng, la)
            d += f"{'M' if i == 0 else 'L'}{_num(tx + 150 * k * x)},{_num(ty - 150 * k * y)}"
        return d + "Z"

    body = "\n".join([
        '<g id="neighbours">',
        *[f'  <path class="hair" d="{path(c)}" stroke-width="1" stroke-opacity="0.10"/>'
          for c in disk if c != cell],
        '</g>',
        '<g id="children">',
        *[f'  <path class="hair" d="{path(c)}" stroke-width="0.75" stroke-opacity="0.07"/>'
          for c in kids],
        '</g>',
        '<g id="cell">',
        f'  <path class="lit" d="{path(cell)}" fill-opacity="0.05" stroke-width="1.5" stroke-opacity="0.20"/>',
        '</g>',
    ])
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}" role="img" data-variant="{variant}">
<title>{facts(lat, lon)["caption"]} — with its neighbours and its seven resolution-9 children.</title>
<style>{_CSS}</style>
{body}
</svg>
"""


# Every element carries a class that binds its colour to a variant token, and the only paper and ink
# literals in the file are in these two blocks. A literal on an element would not flip in the dark
# register; that bug shipped three times in the design kit and test/variant.test.js now holds it.
_CSS = """
  :root {
    --ground: #F9F5F2;
    --land:   #171717;
    --land-opacity: 0.12;
    --cells:  #20388D;
    --rings:  #00A057;
    --ink:    #171717;
  }
  svg[data-variant="dark"], .variant-dark {
    --ground: #171717;
    --land:   #F9F5F2;
    --land-opacity: 0.18;
    --cells:  #7FA5E8;
    --rings:  #00A057;
    --ink:    #F9F5F2;
  }
  .ground { fill: var(--ground); }
  .land   { fill: var(--land); fill-opacity: var(--land-opacity); }
  .cell   { fill: none; stroke: var(--cells); }
  .chain  { fill: var(--cells); stroke: var(--cells); }   /* the next frame's cell: data, opacity via attribute */
  .lit    { fill: var(--cells); stroke: var(--cells); }   /* a node's lit cell: same */
  .ring   { fill: none; stroke: var(--rings); }
  .hair   { fill: none; stroke: var(--ink); }
  .fig    { fill: var(--ink); }
  .label  { fill: var(--ink); font-family: 'JetBrains Mono', ui-monospace, monospace; }
"""
