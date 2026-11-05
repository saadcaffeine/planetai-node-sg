"""The points a forecast is asked for at the node's scale. Pure: no env, no network.

home is the node alone; community is its res-7 H3 cell and the ring round it (7 points); city is res 6 with two rings
(19); region is res 5 with two rings (19). The node's own point comes first and keeps the node's lat/lon, its id is the
bare `base`; the others are cell centres, sorted, with the id `<base>-<cell>`. An unknown scale is community, the
node's own default.
"""
import h3

SCALES = {"community": (7, 1), "city": (6, 2), "region": (5, 2)}


def points(scale: str, lat: float, lon: float, base: str) -> list[dict]:
    if scale == "home":
        return [{"sid": base, "cell": h3.latlng_to_cell(lat, lon, 7), "lat": lat, "lon": lon}]
    res, k = SCALES.get(scale, SCALES["community"])
    own = h3.latlng_to_cell(lat, lon, res)
    return [{"sid": base, "cell": own, "lat": lat, "lon": lon}] + [
        {"sid": f"{base}-{c}", "cell": c, **dict(zip(("lat", "lon"), h3.cell_to_latlng(c)))}
        for c in sorted(set(h3.grid_disk(own, k)) - {own})]
