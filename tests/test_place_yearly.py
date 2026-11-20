"""The place pack's yearly building count (packs/place/satellite.py yearly, packs/place/adapter.py satellite_refresh).

Open Buildings Temporal keeps `building_fractional_count` as a fraction of a building on each 0.5 m pixel, and Earth
Engine's pyramid for it is the mean. Google's own example, "How to compute building count for a given AOI", sums at a
coarser scale and multiplies by (scale × 2)² "to recover sum at original 50cm resolution". Until 18 Nov 2026 yearly()
summed at 4 m and multiplied by nothing: node #1 read 128 buildings in the circle where the footprints count 5994.

The Earth Engine below is a town spread evenly over the ground, reduced the way Earth Engine reduces: a pixel carries
the mean of the 0.5 m pixels under it, and a sum adds one value for each pixel. A mosaic is reduced in EPSG:4326, so
at a scale of s metres a pixel is s metres tall and s × cos(latitude) wide. Nothing here reaches Earth Engine or a
database."""
import contextlib
import io
import math
import os
import runpy
import sys
import types
from datetime import datetime, timezone

sys.path.insert(0, "packs/place")
import adapter as place          # noqa: E402
import satellite as S            # noqa: E402

RADIUS = 1000
AREA = math.pi * RADIUS ** 2
TOWN = {2016: (5530.0, 4.1), 2019: (6820.0, 4.4), 2023: (8172.0, 4.8)}      # year: (buildings in the circle, mean height)
EPOCH = {int(datetime(y, 6, 30, 7, tzinfo=timezone.utc).timestamp()): y for y in TOWN}


class Image:
    """`at(a)` is what one pixel holds when it covers a square metres of ground."""
    def __init__(self, at): self.at = at
    def select(self, band): return Image(lambda a: {band: self.at(a)[band]})
    def _with(self, other, op):
        f = other.at if isinstance(other, Image) else (lambda a: {None: other})
        return Image(lambda a: {k: op(v, next(iter(f(a).values()))) for k, v in self.at(a).items()})
    def multiply(self, other): return self._with(other, lambda a, b: a * b)
    def divide(self, other): return self._with(other, lambda a, b: a / b)
    def gt(self, x): return self._with(x, lambda a, b: float(a > b))
    def updateMask(self, mask): return self                    # the town is built everywhere it is counted
    def reduceRegion(self, reducer, geometry, scale, maxPixels=None):
        a = scale ** 2 * math.cos(math.radians(geometry.lat))
        return Info({k: v * geometry.area / a if reducer == "sum" else v for k, v in self.at(a).items()})


class Info:
    def __init__(self, v): self.v = v
    def getInfo(self): return self.v
    def distinct(self): return self


class Collection:
    def __init__(self, epoch=None): self.epoch = epoch
    def filterBounds(self, g): return self
    def filter(self, epoch): return Collection(epoch)
    def aggregate_array(self, prop): return Info(list(EPOCH))
    def mosaic(self):
        n, h = TOWN[EPOCH[self.epoch]]
        per_pixel = n * 0.25 / AREA                             # the band: a building's share on one 0.5 m pixel
        return Image(lambda a: {"building_fractional_count": per_pixel, "building_height": h, "building_presence": 0.9})


ee = types.SimpleNamespace(
    Geometry=types.SimpleNamespace(Point=lambda xy: types.SimpleNamespace(buffer=lambda r: types.SimpleNamespace(area=math.pi * r ** 2, lat=xy[1]))),
    ImageCollection=lambda _id: Collection(),
    Filter=types.SimpleNamespace(eq=lambda prop, v: v),
    Reducer=types.SimpleNamespace(sum=lambda: "sum", mean=lambda: "mean"),
    Image=types.SimpleNamespace(pixelArea=lambda: Image(lambda a: {"area": a})))

# near the equator a 4 m pixel is almost square; at Cape Town it is a sixth narrower, and a flat 64 reads a fifth high
for lat, lon in ((-8.82, 115.16), (-33.98, 18.60)):
    got = S.yearly(ee, lat, lon, RADIUS)
    assert [y for y, _, _ in got] == [2016, 2019, 2023], got
    for (year, count, height), (n, h) in zip(got, TOWN.values()):
        assert abs(count - n) < 1, f"{year} at {lat}: the town has {n:.0f} buildings in the circle and yearly() counted {count:.1f} ({n / count:.2f} times off)"
        assert height == h, (year, height)
print("  yearly: the count is the buildings in the circle, not a sixty-fourth of them, at either latitude")

# A recount has to reach the readings. The node keeps the first value it files (app/store.py overwrites only a
# forecast still to come), and the series is dated 1 July of each year, so the low rows of a node that ran before the
# fix would outlive every refresh. And `planetai run place refresh` is another process: a poll that read the old count
# just before it must not be able to file the old rows back, so the recount writes its rows itself, over what stands.
ran = []


class Cur:
    def __enter__(self): return self
    def __exit__(self, *a): return False
    def execute(self, sql, params=None): ran.append((" ".join(sql.split()), params))


class Con:
    commits = 0
    def cursor(self): return Cur()
    def commit(self): Con.commits += 1


sys.modules["satellite"] = types.SimpleNamespace(init_ee=lambda: ee, footprints=lambda ee, con, lat, lon, r: ran.append(("footprints", r)) or (5994, 0.8),
                                                yearly=lambda ee, lat, lon, r: [(2016, 5530.0, 4.1), (2023, 8172.0, None)])
assert place.satellite_refresh(Con(), -8.82, 115.16, RADIUS) == 2
sql = [s for s, _ in ran]
assert sql[0] == "footprints", "the footprints first: the series is read against them"
ups = [(s, p) for s, p in ran if s.startswith("INSERT INTO place_yearly")]
assert [p for _, p in ups] == [(2016, 5530.0, 4.1), (2023, 8172.0, None)] and all("ON CONFLICT (year) DO UPDATE SET buildings=EXCLUDED.buildings" in s for s, _ in ups), ups
gone = [i for i, s in enumerate(sql) if s.startswith("DELETE FROM readings")]
assert len(gone) == 1 and "sensor_id='place-point'" in sql[gone[0]] and ran[gone[0]][1] == (["sat_buildings_yearly", "sat_height_m_yearly"],), gone
filed = [(i, s, p) for i, (s, p) in enumerate(ran) if s.startswith("INSERT INTO readings")]
JULY = lambda y: datetime(y, 7, 1, tzinfo=timezone.utc)   # noqa: E731
assert [p for _, _, p in filed] == [(JULY(2016), "place-point", "sat_buildings_yearly", 5530.0), (JULY(2016), "place-point", "sat_height_m_yearly", 4.1),
                                    (JULY(2023), "place-point", "sat_buildings_yearly", 8172.0)], filed
assert all(i > gone[0] and "ON CONFLICT (sensor_id, metric, ts) DO UPDATE SET value = EXCLUDED.value" in s for i, s, _ in filed), "the recount is written over whatever stands, after the old rows go"
assert all("WHERE EXISTS (SELECT 1 FROM sensors WHERE sensor_id='place-point')" in s for _, s, _ in filed), "a node that has not filed its sensor yet has nothing to correct, and a reading without its sensor is refused"
assert Con.commits == 1, "the old rows go and the new count lands in one commit"
assert place.yearly_readings([(2016, 5530.0, 4.1), (2023, 8172.0, None)]) == [p for _, _, p in filed], "the poll files the same rows the recount wrote"
print("  recount: place_yearly is rewritten by year, and the readings are replaced in the same commit")

# every way a count is fetched goes through that one function: the monthly poll and `planetai run place refresh`
_adapter, _refresh = open("packs/place/adapter.py").read(), open("packs/place/refresh.py").read()
assert "satellite_refresh(con, lat, lon, radius)" in _adapter.split("def fetch(hc):")[1], "the poll does not run the satellite half"
assert "A.satellite_refresh(con, lat, lon, radius)" in _refresh, "`planetai run place refresh` does not run the satellite half"
assert _adapter.count("S.yearly(") == 1, "one place fetches the series"
assert "readings + yearly_readings(yearly)" in _adapter.split("def fetch(hc):")[1], "the poll files the series from place_yearly"


# the command itself, with no database and no network: whatever stops the satellite half, the map's result is said
class Db:
    def __enter__(self): return self
    def __exit__(self, *a): return False
    def cursor(self): return Cur()
    def commit(self): pass


def refresh_says(satellite_refresh):
    fakes = {"psycopg": types.SimpleNamespace(connect=lambda url: Db()), "httpx": types.SimpleNamespace(Client=lambda timeout: None),
             "adapter": types.SimpleNamespace(DDL="", refresh=lambda con, hc, lat, lon, r: 3510, satellite_refresh=satellite_refresh)}
    kept, out = {k: sys.modules.get(k) for k in fakes}, io.StringIO()
    os.environ.update(DATABASE_URL="postgresql://nowhere", NODE_LAT="-8.82", NODE_LON="115.16")
    sys.modules.update(fakes)
    try:
        with contextlib.redirect_stdout(out):
            runpy.run_path("packs/place/refresh.py")
    finally:
        sys.modules.update({k: v for k, v in kept.items() if v is not None})
    return out.getvalue()


def stops(e):
    def f(con, lat, lon, r): raise e
    return f


assert "3510 features stored, 8 years of Open Buildings recounted." in refresh_says(lambda con, lat, lon, r: 8)
assert "3510 features stored, Open Buildings skipped (TimeoutError: )." in refresh_says(stops(TimeoutError())), "an exception with no message"
assert "3510 features stored, Open Buildings skipped (SystemExit: place: the satellite half needs earthengine-api)." in refresh_says(stops(SystemExit("place: the satellite half needs earthengine-api\n      planetai packs install")))
print("  refresh: the poll and `planetai run place refresh` both recount, and the command says what it did when Earth Engine stops it")
print("place yearly tests pass")
