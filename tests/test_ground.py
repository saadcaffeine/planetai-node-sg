"""The hero's ground is this node's own cell, and it is drawn the way the design kit draws it.

Two things can go wrong here and neither raises. The drawing can drift from planetai-design, which
computes the same geometry in JavaScript with d3-geo — two languages, one picture, and no build step
between them. And the caption can outlive the geometry: it names a cell and says the node stands in
it, which was false on every node but #1 for the whole of v0.36.

The first is held by redrawing node #1's coordinates and comparing against app/static/node-ground.svg,
which is the design kit's own d3-geo output, vertex for vertex. If the projection, the fit or the
winding moves here, this fails.

What it does not hold: the sibling repo is not on a node and cannot be imported, so this pins the
drawing to the kit as it stood on 7 September 2026, not to the kit as it is now. A change to
planetai-geo's nodeGround() needs that file copied over again, and then this test says whether the
Python followed.
"""
import re
import sys

sys.path.insert(0, "app")
import math

try:
    import h3                                     # noqa: F401
except ImportError:
    print("  - ground check skipped (pip install -r app/requirements.txt)")
    sys.exit(0)
import ground

BALI = (-8.8271, 115.15709)          # node #1, Kuta Selatan
BARCELONA = (41.3874, 2.1686)
paths = lambda svg: re.findall(r' d="([^"]+)"', svg)

shipped = open("app/static/node-ground.svg").read()
drawn = ground.svg(*BALI)

# 1. the same picture the design kit computes, to the last vertex
assert paths(drawn) == paths(shipped), (
    "the ground has drifted from planetai-design's node-ground.svg. Compare against "
    "planetai-geo/index.mjs nodeGround() before changing anything here")
assert len(paths(drawn)) == 14, f"6 neighbours + 7 children + the cell, not {len(paths(drawn))}"
print("  node #1's ground redraws to the design kit's geometry, all 14 paths")

# 2. the caption is true, because it is this node's cell. It is page text rather than a stamp in the
#    drawing: the hero scales the ground with object-fit:cover, and a stamp at the foot of the frame
#    loses its cell id to the crop at 390 and the whole line at 1440.
here = ground.svg(*BARCELONA)
bali_id, bcn_id = h3.latlng_to_cell(*BALI, 8), h3.latlng_to_cell(*BARCELONA, 8)
assert bali_id != bcn_id
for svg, (lat, lon), cell in ((drawn, BALI, bali_id), (here, BARCELONA, bcn_id)):
    line = ground.facts(lat, lon)["caption"]
    assert line.startswith(f"{cell} · RES 8 · ") and line.endswith(" · THE CELL THIS NODE STANDS IN"), line
    assert line in svg[:svg.index("</title>")], "the file says what it is on its own, in <title>"
    assert "<text" not in svg, "the caption is the page's; a stamp in the frame gets cropped"
# The page is a renderer since v0.45: the two stamps are one `stamp` component, listed in the hero's
# anatomy and the wall's, and the caption reaches it through the band's data from /health. Asserting
# the anatomy is the guarantee the two ids used to give — an id can exist while nothing writes to it.
# (tests/test_shipped.py holds the same three facts; this suite skipped on every machine without h3,
# which is how the old literal survived here after it was gone from the page.)
import re as _re
def _haversine(a, b):
    p = math.pi / 180
    x = 0.5 - math.cos((b[0] - a[0]) * p) / 2 + math.cos(a[0] * p) * math.cos(b[0] * p) * (1 - math.cos((b[1] - a[1]) * p)) / 2
    return 12742 * math.asin(math.sqrt(x))


# ---- presence: how much a coarse cell actually gives away -----------------------------------------
# The announced cell is the node's own res-8 cell rounded up to a parent, and the resolution IS the
# privacy control. These are the numbers that choice is made on, measured rather than asserted.
_here8 = h3.latlng_to_cell(*BALI, 8)
_blur = {}
for _r in (3, 4, 5, 6):
    _c = h3.cell_to_parent(_here8, _r)
    _lat, _lon = h3.cell_to_latlng(_c)
    _blur[_r] = ground.km(BALI[0], BALI[1], _lat, _lon) if hasattr(ground, "km") else _haversine(BALI, (_lat, _lon))
assert _blur[3] > 20, f"res 3 must not land near the house: it is {_blur[3]:.1f} km away"
assert _blur[3] > _blur[5], "a coarser cell has to blur further, or the setting means nothing"
assert h3.cell_to_parent(_here8, 3) != _here8, "the announced cell is never the node's own cell"
# and the distance between two nodes is two cell centres, so it is symmetric and carries no address
_men = h3.cell_to_parent(h3.latlng_to_cell(39.9496, 4.1100, 8), 3)
_a, _b = h3.cell_to_latlng(h3.cell_to_parent(_here8, 3)), h3.cell_to_latlng(_men)
_d = _haversine(_a, _b)
assert 11500 < _d < 13500, f"Bali to Menorca from two coarse cells is {_d:.0f} km, which is not the right planet"
print(f"  the announced cell blurs this node by {_blur[3]:.0f} km at res 3, and Menorca reads {_d:.0f} km away")

gui = open("app/static/dashboard.js").read()
# Rewritten 15 September 2026 with the modular page, which has no ANATOMY object: the shell draws the
# lead and wall.js draws the wall, and there is no band table between them. Each of the three findings
# below is the one the ANATOMY assertions carried, re-expressed against the code that draws today —
# and each still goes red if what it protects stops being true.
#
#   1  the stamp is a component a gate can find      — unchanged
#   2  it is drawn on BOTH surfaces, from one piece  — was ANATOMY.hero/.wall; now the two call sites
#   3  the caption is /health's own, never derived   — was the old renderer's names; now stamp()'s
assert 'data-component="stamp"' in gui, "the cell stamp is a component"
# 2 — one stamp(), called from the lead and from the wall's foot. Delete either call and this is red;
# it is the same guarantee the two anatomy entries gave, read off the call sites instead of a table.
# The two used to be asserted as one adjacent string. They are not adjacent since
# 21 September 2026: the lead's stamp line carries the open-ask reference between them,
# because the ask strip moved to Act and T1 still wants an ask on the first screen. What
# this guards is that the LEAD draws the stamp at all — one stamp(), called from here and
# from the wall — not the order of the line it sits in.
assert "${window.K.stamp()}" in gui, "the lead no longer draws the cell stamp"
assert "${asof()}" in gui, "the lead no longer draws its as-of"
assert "${K.asof()}${K.stamp()}" in gui, "the wall no longer draws the cell stamp, and it has no header"
# 3 — the caption is the cell's own, off /health, and a node with no cell prints nothing rather than
# a caption the page made up. Change either half and this is red.
assert "const c = (S.health || {}).cell;" in gui and "const said = c ? c.caption : '';" in gui, (
    "the stamp no longer takes its caption from /health's own cell")
_main_src = open("app/main.py").read()
assert '"cell": _cell()' in _main_src, "/health carries the cell"

# `_cell()` returns ground.facts(): {"id", "res", "edge_m", "caption"}. TWO places read a cell out of
# it — /presence, which coarsens before announcing, and poll_reticulum, which measures the distance to a
# peer — and BOTH read `here["cell"]`, a key facts() has never had. Both guards were therefore always
# false: every node announced cell: null (#59) and every peer showed km: null. The `except` in each sits
# inside the dead branch, so neither ever logged. Checked on node #1: /presence answered "cell": null,
# and after #59 fixed only the first site the Network tab still showed km: None beside a good cell.
#
# So this scans the WHOLE file rather than one function. #59's version looked only inside /presence's
# body and could not see the sibling two hundred lines up, which is how the second site shipped.
_facts_keys = set(ground.facts(*BALI))
# both readers are in app/presence.py since 24 Oct 2026, where _node_cell() is main's _cell()
_pres_src = open("app/presence.py").read()
_reads = set(_re.findall(r'here(?:\.get\(|\[)["\'](\w+)["\']', _main_src + _pres_src))
assert _reads, "nothing reads ground.facts() any more — did the cell stop being announced?"
assert _reads <= _facts_keys, (
    f"app/main.py reads {sorted(_reads - _facts_keys)} off _cell(), which returns {sorted(_facts_keys)}. "
    f"A node would announce cell: null, or show km: null for every peer.")
assert _pres_src.count("here = _node_cell()") == 2 and "here = _cell()" not in _main_src, (
    f"{_pres_src.count('here = _node_cell()')} places read _cell() — this guard assumes `here` is always "
    "its result. If that changed, the scan above may be reading someone else's variable.")
print(f"  both _cell() readers use {sorted(_reads)}; facts() returns {sorted(_facts_keys)}")
assert "THE CELL THIS NODE STANDS IN" not in shipped, (
    "app/static/node-ground.svg is the fallback for a node with no coordinates yet. It is node #1's "
    "cell and must claim nothing")
print(f"  the caption names the node's own cell: {bali_id} in Bali, {bcn_id} in Barcelona")

# 3. the edge is measured, not quoted. H3 publishes 531 m as the res-8 average; node #1's cell is
#    smaller than average and its six edges run 471-518 m. A table value printed beside a drawn cell
#    is the same small untruth as node #1's geometry on someone else's node.
b = h3.cell_to_boundary(bali_id)
edges = [round(h3.great_circle_distance(b[i], b[(i + 1) % 6], unit="m")) for i in range(6)]
assert len(set(edges)) > 1, "an H3 cell is never a regular hexagon; equal edges mean something drew one"
assert f" {round(sum(edges) / 6)} M EDGE " in ground.facts(*BALI)["caption"], f"the stamp should carry this cell's mean edge, {edges}"
print(f"  the stamp measures this cell: edges {min(edges)}-{max(edges)} m, mean {round(sum(edges) / 6)}")

# 4. the dark register. A paper or ink literal on an element does not flip, which is the bug
#    planetai-design's test/variant.test.js exists to stop; here every element must carry a class.
BINDS = {"ground", "land", "cell", "chain", "lit", "ring", "hair", "fig", "label"}
body = re.sub(r"<style>.*?</style>", "", here, flags=re.S)
for tag in re.findall(r"<(?:rect|path|line|circle|polygon|text|ellipse)\s[^>]*>", body):
    lit = re.search(r'(?:fill|stroke)="(#F9F5F2|#171717)"', tag, re.I)
    assert not lit, f"{lit.group(0)} on an element with no binding class: it will not flip"
    assert BINDS & set(re.search(r'class="([^"]*)"', tag).group(1).split()), tag
assert 'data-variant="dark"' in here and "#7FA5E8" in here and "#20388D" in here
print("  every element binds its colour to a variant token; the dark register's blue is #7FA5E8")

# 5. Barcelona is not Bali. Nothing about the drawing is a constant.
assert not set(paths(here)) & set(paths(drawn)), "no path survives a change of place"
assert ground.svg(*BARCELONA) is here, "one point is drawn once and kept"
print("  a different node draws a different ground")

# 6. the ground follows the page's register. It is an <img>, so it is a document of its own and no
#    CSS on the page reaches it: without this it drew #7FA5E8 on the paper hero at 2.29:1, which is
#    the one thing planetai-design's guards say may never happen. The page asks in the URL instead.
paper = ground.svg(*BALI, "paper")
assert 'data-variant="paper"' in paper, "?variant=paper must reach the root attribute"
assert 'data-variant="dark"' in drawn, "the default is still the dark register"
assert paths(paper) == paths(drawn), "the register changes the palette, never the geometry"

_main = open("app/main.py").read()
# The variant is interpolated into data-variant="..." inside the SVG, so the route may never pass a
# caller's string through. Two literals, chosen by comparison — that is what makes it uninjectable.
assert '_ground_svg("paper" if variant == "paper" else "dark")' in _main, (
    "the route must coerce ?variant= to one of two literals, not validate-and-forward it")
assert 'src="static/node-ground.svg?variant=${ctx.register}"' in open("app/static/dashboard.js").read(), (
    "the renderer must ask for the register it is in")

# The shipped fallback is drawn dark, so a node with no coordinates yet needs the attribute swapped
# or it puts the lifted blue on the paper hero — the same bug, one branch over.
assert 'data-variant="dark"' in shipped, "the shipped file is the dark register"
assert 'data-variant="paper"' in shipped.replace('data-variant="dark"', 'data-variant="paper"', 1)
assert "#20388D" in shipped and "#7FA5E8" in shipped, (
    "the fallback carries both registers in its own <style>, or swapping the attribute changes nothing")
print("  the ground follows the register: paper on the page, dark on the wall, geometry unchanged")
