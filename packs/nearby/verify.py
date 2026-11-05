"""Check the ring on this node: exclusions fire, nothing external is local, the numbers recompute.  planetai run nearby verify

Exits 1 naming the line that failed. An exclusion rule that cannot be shown to fire is the whole pack's premise
unproven, so it is a failure here, not a warning.
"""
import os
import sys

import httpx
import psycopg
from psycopg.rows import dict_row

sys.path.insert(0, "/app")
import packs  # noqa: E402
import sources  # noqa: E402

archive = packs.module("bali-air-dispatch")   # the archive's adapter: its endpoints and the one function that decides the ring
if archive is None:
    sys.exit("nearby: the bali-air-dispatch pack is not on this node; the ring reads what it stores")

LAT, LON = float(os.environ["NODE_LAT"]), float(os.environ["NODE_LON"])
SEP = float(os.getenv("BAD_MIN_SEPARATION_M", "150"))
bad = []


def step(n, ok, msg):
    print(f"  {'ok  ' if ok else 'FAIL'} {n}. {msg}")
    if not ok:
        bad.append(n)


# ---- 1. every exclusion rule fires. Ownership rules are checked against a case built from this node's own
# coordinates, so the check works on a node whose ring happens to be clean today.
here = {"station_id": "sc-000", "name": "a kit on this wall", "source": "Smart Citizen",
        "latitude": LAT, "longitude": LON, "observed_at": "2026-01-01T00:00:00Z", "stale": False, "pm25": 9.0}
away = dict(here, station_id="sc-999", name="a neighbour", latitude=LAT + 0.05, longitude=LON)
cases = [
    ("identity", [dict(away, station_id="sc-111")], {"sc-111"}, set(), "identity"),
    ("proximity", [here], set(), set(), "proximity"),
    ("by hand", [dict(away, station_id="sc-222")], set(), {"sc-222"}, "by hand"),
    ("beyond the radius", [dict(away, latitude=LAT + 5)], set(), set(), "beyond the radius"),
    ("suspected_indoor", [dict(away, suspected_indoor=True)], set(), set(), "suspected_indoor"),
    ("suspected_malfunctioning", [dict(away, suspected_malfunctioning=True)], set(), set(), "suspected_malfunctioning"),
    ("stale", [dict(away, stale=True, age_hours=99)], set(), set(), "stale"),
    ("one device, two networks", [dict(away, station_id="ag-1"), dict(away, station_id="oq-1")], set(), set(), "same device"),
]
for label, rows, own, byhand, want in cases:
    got = [v for _, v in archive.verdicts(rows, LAT, LON, 15.0, own, byhand, SEP)]
    step(f"exclusion: {label}", any(want in v for v in got), f"{want} — got {got}")

# and a plain neighbour is not excluded by any of them
step("a neighbour survives", [v for _, v in archive.verdicts([away], LAT, LON, 15.0, set(), set(), SEP)] == ["included"],
     "a station 5.5 km away with nothing wrong with it is in the ring")

# ---- 2. the archive is reachable and this node's own hardware is out of its own ring
try:
    hc = httpx.Client(timeout=60, headers={"user-agent": "planetai-node"})
    latest = hc.get(archive.LATEST).json().get("readings", [])
    own = {f"sc-{i}" for i in sources.smartcitizen_account(hc, os.getenv("SC_USER", "").strip())} if os.getenv("SC_USER", "").strip() else set()
    own |= {f"sc-{x}" for x in os.getenv("SC_DEVICES", "").replace(" ", "").split(",") if x}
    byhand = {x for x in os.getenv("BAD_EXCLUDE", "").replace(" ", "").split(",") if x}
    v = archive.verdicts(latest, LAT, LON, float(os.getenv("BAD_RADIUS_KM", "15")), own, byhand, SEP)
    inc = [r for r, w in v if w == "included"]
    step("the archive answers", True, f"{len(latest)} stations, {len(inc)} in this node's ring")
    tooclose = [r["station_id"] for r in inc
                if sources.metres(LAT, LON, r["latitude"], r["longitude"]) <= SEP]
    step("no station of ours in the ring", not tooclose, f"nothing inside {SEP:g} m survived — {tooclose or 'none'}")
    if len(inc) < 2:
        print(f"  note  the ring is {len(inc)} station(s). only_here and everywhere cannot fire; alone will.")
except Exception as e:  # noqa: BLE001
    step("the archive answers", False, f"{type(e).__name__}: {str(e)[:120]}")

# ---- 3. what is stored: never local, never in the node's own ambient pool, and the ring recomputes
try:
    with psycopg.connect(os.environ["DATABASE_URL"], row_factory=dict_row) as con, con.cursor() as cur:
        cur.execute("SELECT count(*) AS n FROM sensors WHERE source = 'baliairdispatch' AND local")
        step("external is never local", cur.fetchone()["n"] == 0, "no stored station claims to be this node's own")

        cur.execute("""SELECT count(*) AS n FROM sensors s JOIN channel_roles c ON c.source = s.source
                       WHERE s.source = 'baliairdispatch' AND c.role = 'ambient' AND s.local""")
        step("out of the ambient pool", cur.fetchone()["n"] == 0,
             "the node's ambient average is joined on `local`, and no station is local")

        cur.execute("""
            SELECT count(*) AS n,
                   round(percentile_cont(0.5) WITHIN GROUP (ORDER BY st.mean_1h)::numeric, 1) AS med,
                   round((percentile_cont(0.75) WITHIN GROUP (ORDER BY st.mean_1h)
                        - percentile_cont(0.25) WITHIN GROUP (ORDER BY st.mean_1h))::numeric, 1) AS spread
            FROM stats st JOIN sensors sn USING (sensor_id)
            WHERE sn.source = 'baliairdispatch' AND NOT st.local AND NOT st.indoor AND st.kind = 'sensor'
              AND st.metric = 'pm25' AND st.mean_1h IS NOT NULL AND st.silent_minutes < 120""")
        r = cur.fetchone()
        step("the ring recomputes", r["n"] == 0 or r["med"] is not None,
             f"{r['n']} reporting, middle {r['med']} ug/m3, spread {r['spread']}")
except Exception as e:  # noqa: BLE001
    step("the database answers", False, f"{type(e).__name__}: {str(e)[:120]}")

print()
if bad:
    sys.exit(f"nearby: {len(bad)} check(s) failed — {', '.join(bad)}")
print("nearby: the ring is other people's stations, and this node's own kit is not in it.")
