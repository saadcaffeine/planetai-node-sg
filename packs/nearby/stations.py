"""Every station in the archive, its distance, and whether it is in this node's ring or why not.  planetai run nearby stations

Read it once by eye. It is the proof that this node's own kit is not sitting in its own ring arguing with itself:
identity, proximity and BAD_EXCLUDE each name the station they caught. The verdicts come from the same function the
adapter uses, so this list cannot drift from what the node actually stores.
"""
import os
import sys

import httpx

sys.path.insert(0, "/app")
import packs  # noqa: E402
import sources  # noqa: E402

archive = packs.module("bali-air-dispatch")   # the archive's adapter: its endpoints and the one function that decides the ring
if archive is None:
    sys.exit("nearby: the bali-air-dispatch pack is not on this node; the ring reads what it stores")

LAT, LON = float(os.environ["NODE_LAT"]), float(os.environ["NODE_LON"])
RADIUS = float(os.getenv("BAD_RADIUS_KM", "15"))
SEP = float(os.getenv("BAD_MIN_SEPARATION_M", "150"))
BYHAND = {x for x in os.getenv("BAD_EXCLUDE", "").replace(" ", "").split(",") if x}
INDOOR = os.getenv("BAD_INCLUDE_INDOOR", "0") == "1"

hc = httpx.Client(timeout=60, headers={"user-agent": "planetai-node"})
latest = {r["station_id"]: r for r in hc.get(archive.LATEST).json().get("readings", [])}
# /stations carries the three the archive has no current reading for, so the audit is the whole archive, not
# only the part that answered today.
rows = []
for s in hc.get(archive.STATIONS).json().get("stations", []):
    rows.append({**s, **latest.get(s["station_id"], {})})

# the station ids this node reads directly, built the same way the pack's adapter builds them
own = {f"sc-{i}" for i in sources.smartcitizen_account(hc, os.getenv("SC_USER", "").strip())} if os.getenv("SC_USER", "").strip() else set()
own |= {f"sc-{x}" for x in os.getenv("SC_DEVICES", "").replace(" ", "").split(",") if x}
own |= {f"ag-{h.replace('.local', '').replace('airgradient_', '')}"
        for h in os.getenv("AIRGRADIENT_HOSTS", "").replace(" ", "").split(",") if h}

verdicts = archive.verdicts(rows, LAT, LON, RADIUS, own, BYHAND, SEP, INDOOR)
verdicts.sort(key=lambda rv: sources.km(LAT, LON, rv[0]["latitude"], rv[0]["longitude"])
              if rv[0].get("latitude") is not None else 9e9)

print(f"\nThe ring around {os.getenv('NODE_NAME', 'this node')} at {LAT}, {LON}")
print(f"radius {RADIUS:g} km · own hardware within {SEP:g} m · {len(own)} device id(s) read directly"
      + (f" · {len(BYHAND)} excluded by hand" if BYHAND else ""))
print(f"\n{'km':>7}  {'station':<24} {'network':<14} verdict")
print("-" * 100)
for row, verdict in verdicts:
    d = ("    n/a" if row.get("latitude") is None
         else f"{sources.km(LAT, LON, row['latitude'], row['longitude']):7.2f}")
    print(f"{d}  {str(row['station_id']):<24} {str(row.get('source'))[:14]:<14} {verdict}")

inc = [r for r, v in verdicts if v == "included"]
print("-" * 100)
print(f"{len(inc)} of {len(verdicts)} stations are this node's ring.")
for r, v in verdicts:
    if v != "included" and not v.startswith(("excluded: beyond", "excluded: stale")):
        print(f"  {r['station_id']:<24} {v}")
if len(inc) < 2:
    print("\nFewer than two neighbours. This node's readings speak for this address and nothing else:\n"
          "nothing here can tell a fire in the lane from a haze over the island.")
print("\nBali Air Dispatch, baliairdispatch.com, and the network named in each row.")
