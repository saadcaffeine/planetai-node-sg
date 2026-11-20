"""Compare two cached years, pixel by pixel, and write the map and the numbers.  planetai run earth change [A B | --all]

With no years, the two most recent consecutive cached years. With `--all`, every consecutive pair plus the
span from the oldest cached year to the newest — the whole history in one command, which is the order worth
reading it in: the span is where persistent change stands out from the year-to-year background, and the
yearly steps say when each thing happened. Already-computed pairs are skipped unless `--force`; a pair computed
before the Wall's image existed (no `wall` key in its JSON), whose Wall image is missing, or whose crop was cut round
another res-8 cell than the house's now, is computed again.

Writes change_<A>_<B>.png (north up, a grey ramp, the node ringed) and change_<A>_<B>.json (mean, median,
p95, the share and the hectares above the threshold, the bounds, the source objects) into out/earth/<node>/,
and change_<A>_<B>_wall.png, the Wall's image (changed pixels in the community's cells only), whose crop the
JSON keeps under `wall`.
"""
import json
import os
import sys
import time
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(__file__))
import adapter as A                                                              # noqa: E402

# Where "changed" starts. Not a physical constant: it is the one number in this pack chosen rather than
# measured, and it is calibrated on one 10 km square of Bali. For the two consecutive-year pairs at node #1
# it sits at the 99th percentile, so about 1% of a normal year's square is flagged (2023→2024: 0.96%,
# 2024→2025: 1.19%); over the two-year gap 2023→2025 it flags 4.9%. Lower it and a quiet year looks busy:
# 0.05, the threshold the earth-engine pack uses on a different quantity, flags a third of this square.
CHANGED = 0.15

A.require("numpy", "h3")

import numpy as np                                                               # noqa: E402

USAGE = "usage: planetai run earth change [A B | --all] [--force]"
# Anything unrecognised is an error. `planetai run earth change --all` used to fall through to the default
# pair and print a perfectly ordinary result for a comparison nobody asked for (7 Sep 2026): a flag this
# script did not have was not a digit, so it was dropped, and the empty argument list meant "the latest pair".
flags = {x for x in sys.argv[1:] if x.startswith("-")}
years = [x for x in sys.argv[1:] if not x.startswith("-")]
unknown = sorted(flags - {"--all", "--force"}) + [y for y in years if not (y.isdigit() and len(y) == 4)]
if unknown or len(years) not in (0, 2):
    print(f"earth: {'do not know ' + ', '.join(unknown) if unknown else 'give two years or none'}\n{USAGE}")
    sys.exit(1)
do_all, force = "--all" in flags, "--force" in flags
cached = A.cached_years()

if do_all:
    if len(cached) < 2:
        print(f"earth: fewer than two years cached (have: {', '.join(map(str, cached)) or 'none'}). "
              f"planetai run earth fetch"); sys.exit(1)
    pairs = [(x, y) for x, y in zip(cached, cached[1:]) if y - x == 1]
    span = (cached[0], cached[-1])
    if span not in pairs:
        pairs.append(span)
elif len(years) == 2:
    pairs = [tuple(sorted(int(y) for y in years))]
else:
    pair = A.latest_pair()
    if not pair:
        print(f"earth: no two consecutive years are cached (have: {', '.join(map(str, cached)) or 'none'}). "
              f"planetai run earth fetch"); sys.exit(1)
    pairs = [pair]

missing = sorted({y for p in pairs for y in p} - set(cached))
if missing:
    print(f"earth: {', '.join(map(str, missing))} not cached. planetai run earth fetch {' '.join(map(str, missing))}")
    sys.exit(1)

m = A.meta()
def compare(a, b):
    """One pair: the arithmetic, the map and the JSON. Returns its stats, or None if this pair cannot be done
    (which is not fatal when --all is walking a history that has a gap in it)."""
    wa, wb = (m.get("windows", {}).get(str(y), {}) for y in (a, b))
    if wa.get("px") and wb.get("px") and wa["px"] != wb["px"]:
        print(f"earth: {a} is {wa['px']} px and {b} is {wb['px']} px — re-fetch both with --force"); return None
    # meta.json records a window per year for the square the pack currently describes. A year with a file but no window
    # was read around a different point, and comparing it with one from here would report the difference between two
    # places as change over time.
    orphan = [y for y, w in ((a, wa), (b, wb)) if not w.get("bounds")]
    if orphan:
        print(f"earth: {', '.join(map(str, orphan))} on disk but not in meta.json for this square — read around another "
              f"point, or fetched by an older version. planetai run earth fetch {' '.join(map(str, orphan))} --force")
        return None
    # Two years read over different ground (a move inside fetch's tolerance re-reads only the years it fetches) have
    # the same size and other origins: subtracting them pixel by pixel reports a shift as change.
    if wa["bounds"] != wb["bounds"] or wa.get("crs") != wb.get("crs"):
        print(f"earth: {a} and {b} were read over different ground ({wa.get('crs')} {wa['bounds']} against "
              f"{wb.get('crs')} {wb['bounds']}). planetai run earth fetch {a} {b} --force")
        return None

    t0 = time.time()
    X = np.load(A.year_file(a), mmap_mode="r")
    Y = np.load(A.year_file(b), mmap_mode="r")
    dist, masked = A.cosine_distance(X, Y)
    numbers = A.change_stats(dist, masked, CHANGED)
    if not numbers:
        print("earth: every pixel is masked in one of the two years"); return None

    stats = {
        "node": A.node(), "year_a": a, "year_b": b, **numbers,
        "metres_per_pixel": 10,
        "crs": wb.get("crs") or wa.get("crs"),
        "bounds": wb.get("bounds") or wa.get("bounds"),
        "lat": m.get("lat"), "lon": m.get("lon"), "radius_m": m.get("radius_m"),
        "clipped": bool(wa.get("clipped") or wb.get("clipped")),
        "tiles": [w.get("object") for w in (wa, wb) if w.get("object")],
        "dataset": A.DATASET, "attribution": A.ATTRIBUTION,
        "computed_at": datetime.now(timezone.utc).isoformat(),
        "png": A.change_file(a, b, "png").name,
    }

    ix = A.ramp_indices(dist, masked)
    rc = (wb.get("node_rc") or wa.get("node_rc"))                                    # recorded north-up by fetch.py
    A.draw_marks(ix, (int(rc[0]), int(rc[1])) if rc else None)
    stats["node_rc"] = rc
    png_bytes = A.write_png(A.change_file(a, b, "png"), ix, {
        "Title": f"Land change {a}-{b}, {A.node()}",
        "Description": f"1 - cosine similarity of annual AlphaEarth embeddings, {a} to {b}. "
                       f"North up, 10 m per pixel, grey ramp 0 to {A.RAMP_CEILING}. Black is no data.",
        "Copyright": A.ATTRIBUTION,
    })
    # The Wall's own image (adapter.py::wall_image): no ring, no scale bar, nothing that moves with the house.
    # Placed from NODE_LAT/NODE_LON, the point /wall reads; without them there is no cell to crop by.
    wall, home = None, A.wall_cell()
    if stats["bounds"] and stats["crs"] and home:
        wall = A.wall_image(dist, masked, stats["bounds"], stats["crs"], home,
                            stats["radius_m"] or A.aoi()[2], CHANGED, stats["clipped"])
    wall_png = wall_file(a, b)
    if wall:
        part = wall_png.with_name(wall_png.name + ".part")     # the served image is replaced whole, never truncated
        A.write_png(part, wall[0], {
            "Title": f"Land changed {a}-{b}",
            "Description": f"Pixels over {CHANGED} in 1 - cosine similarity of annual AlphaEarth embeddings, inside "
                           f"the community's H3 cells. North up, 10 m per pixel.",
            "Copyright": A.ATTRIBUTION,
        }, palette=A.WALL_PALETTE, trns=b"\x00")
        os.replace(part, wall_png)
    else:
        wall_png.unlink(missing_ok=True)           # an earlier crop must not answer for this run's null
    # null, not absent: "tried, nothing the Wall may show", so the next plain run does not try again. Either way bound
    # to the house's cell, so a move into another cell computes it again (computed()).
    stats["wall"] = {**wall[1], "cell": home} if wall else None
    if not wall:
        stats["wall_cell"] = home
    A.change_file(a, b, "json").write_text(json.dumps(stats, indent=1))

    print(f"earth: {a} → {b} over {stats['px'][0] * 10 / 1000:.1f} x {stats['px'][1] * 10 / 1000:.1f} km, "
          f"{time.time() - t0:.0f}s")
    print(f"  mean {stats['mean']:.4f}  median {stats['median']:.4f}  p95 {stats['p95']:.4f}  max {stats['max']:.4f}")
    print(f"  above {CHANGED}: {stats['share_over_threshold'] * 100:.2f}% of the square, "
          f"{stats['hectares_over_threshold']:.0f} ha")
    print(f"  {A.change_file(a, b, 'png').name} ({png_bytes / 1000:.0f} kB)  {A.change_file(a, b, 'json').name}")
    return stats


def wall_file(a, b):
    return A.change_file(a, b, "png").with_name(f"change_{a}_{b}_wall.png")


def computed(a, b) -> bool:
    """Whether the pair is done: its JSON exists and has `wall` (null counts), cut round the house's cell now, and a
    crop has its image on disk. A pair computed before the Wall's image existed has no `wall` key, one whose image
    was lost has a crop and no file, and one cut before the house moved into another cell names that cell: the next
    plain run computes each again so the Wall gets one. A null `wall` for this cell is an answer, and stays."""
    try:
        st = json.loads(A.change_file(a, b, "json").read_text())
    except (OSError, ValueError):
        return False
    if "wall" not in st:
        return False
    w = st["wall"]
    if (w.get("cell") if w else st.get("wall_cell")) != A.wall_cell():
        return False
    return not w or wall_file(a, b).is_file()


done, skipped = [], []
for a, b in pairs:
    if not force and computed(a, b):
        skipped.append((a, b)); continue
    st = compare(a, b)
    if st:
        done.append(st)

if skipped:
    print(f"earth: already computed, skipping {', '.join(f'{a}→{b}' for a, b in skipped)} (--force to redo)")
if do_all:
    have = sorted((json.loads(A.change_file(a, b, "json").read_text()) for a, b in pairs
                   if A.change_file(a, b, "json").is_file()), key=lambda d: (d["year_b"] - d["year_a"], d["year_a"]))
    if have:
        print(f"\n  {'pair':13} {'mean':>7} {'median':>7} {'p95':>7} {'over ' + str(CHANGED):>9} {'hectares':>9}")
        for d in have:
            mark = "  the span" if d["year_b"] - d["year_a"] > 1 else ""
            print(f"  {d['year_a']}→{d['year_b']:<8} {d['mean']:>7.4f} {d['median']:>7.4f} {d['p95']:>7.4f} "
                  f"{d['share_over_threshold'] * 100:>8.2f}% {d['hectares_over_threshold']:>9.0f}{mark}")
        print("\n  The span is the cleaner picture of what was built: over years, change that stays accumulates\n"
              "  and the year-to-year background does not. The yearly rows say when each thing happened.")
print(A.ATTRIBUTION)
