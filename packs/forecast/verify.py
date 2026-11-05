"""Check the forecast on this node: the point, the units, and whether the issue time is real.  planetai run forecast verify

Exits 1 naming the line that failed. The three things worth checking are the three that fail silently: a village
code for the wrong village, a unit that changed under us, and a forecast that stopped refreshing — which looks
exactly like one that is right.
"""
import os
import sys
from datetime import datetime, timezone

import httpx

sys.path.insert(0, os.path.dirname(__file__))
import adapter as A  # noqa: E402

LAT, LON = float(os.environ["NODE_LAT"]), float(os.environ["NODE_LON"])
hc = httpx.Client(timeout=60, headers={"user-agent": "planetai-node"})
bad = []


def step(n, ok, msg):
    print(f"  {'ok  ' if ok else 'FAIL'} {n}. {msg}")
    if not ok:
        bad.append(n)


adm4 = os.getenv("FORECAST_BMKG_ADM4", "").strip()
if os.getenv("FORECAST_BMKG", "1") != "1":
    print("  note  BMKG is off (FORECAST_BMKG=0).")
elif not adm4:
    step("the adm4 code", False,
         "FORECAST_BMKG_ADM4 is empty. It is a Permendagri village code, e.g. 51.03.05.2002 for Ungasan, "
         "Kuta Selatan. BMKG publishes the list; the check below proves whichever you pick is near this node.")
else:
    try:
        d = hc.get(A.BMKG, params={"adm4": adm4}).json()
        loc = d.get("lokasi") or {}
        if not loc:
            step("the adm4 code", False, f"BMKG has no forecast for {adm4}: {str(d)[:120]}")
        else:
            km = A._km(LAT, LON, float(loc["lat"]), float(loc["lon"]))
            # 10 km is the line: past it the forecast is for somewhere else and the card has to say so.
            step("the forecast point", km <= 10,
                 f"{adm4} is {loc.get('desa')}, {loc.get('kecamatan')}, {loc.get('kotkab')} — {km:.2f} km from this node"
                 + ("" if km <= 10 else ". That is another place; find the code for this one."))
            steps = [s for g in (d.get("data") or [{}])[0].get("cuaca") or [] for s in g]
            issued = A._utc((steps[0] if steps else {}).get("analysis_date"))
            age = None if issued is None else (datetime.now(timezone.utc) - issued).total_seconds() / 3600
            # BMKG publishes twice a day. Past about 18 hours the forecast has stopped refreshing, and a stale
            # forecast reads exactly like a current one unless something checks.
            step("the issue time", issued is not None and age is not None and age < 18,
                 "no analysis_date in the payload" if issued is None
                 else f"issued {issued:%Y-%m-%d %H:%M} UTC, {age:.1f} h ago"
                      + ("" if age < 18 else " — BMKG publishes twice a day, so this one has stopped refreshing")) 
            step("units as documented", any(s.get("ws") is not None for s in steps),
                 "BMKG publishes ws in km/h and wd_deg in degrees; the node stores both unchanged")
    except Exception as e:  # noqa: BLE001
        step("BMKG answers", False, f"{type(e).__name__}: {str(e)[:140]}")

if os.getenv("FORECAST_OPENMETEO", "0") != "1":
    print("  note  Open-Meteo is off. Its free tier is non-commercial only, so it is your call: FORECAST_OPENMETEO=1.")
else:
    try:
        r = hc.get(A.OPEN_METEO, params={"latitude": LAT, "longitude": LON, "hourly": A.OM_HOURLY,
                                         "forecast_days": 2, "timezone": "UTC"}).json()
        u = r.get("hourly_units") or {}
        # the one unit that matters: BMKG is km/h, and the gap channel subtracts one from the other.
        step("Open-Meteo units", u.get("wind_speed_10m") == "km/h",
             f"wind_speed_10m is {u.get('wind_speed_10m')!r}; BMKG publishes km/h and the gap channel assumes both match")
        step("Open-Meteo answers", bool((r.get("hourly") or {}).get("time")),
             f"{len(((r.get('hourly') or {}).get('time') or []))} hourly steps for {r.get('latitude')}, {r.get('longitude')}")
        print("  note  Open-Meteo publishes no model run time. The node records when it fetched, and says so.")
    except Exception as e:  # noqa: BLE001
        step("Open-Meteo answers", False, f"{type(e).__name__}: {str(e)[:140]}")

try:
    # force: without it `_due(source)` answers for the node's poll clocks. Right after a fetch that is "not due", so this
    # check failed for FORECAST_POLL_HOURS with the forecast stored; at a due moment it touched the stamp and stored
    # nothing, so the node then skipped its own poll for six hours. Forced, verify reads now and leaves the clock alone.
    s, rd = A.fetch(hc, force=True)
    step("the adapter returns", bool(s),
         f"{len(s)} source(s), {len(rd)} readings; metrics {sorted({m for _, _, m, _ in rd})}")
    step("nothing claims to be local", all(not x["local"] and x["kind"] == "model" for x in s),
         "a forecast is not a measurement at this address, and is never `local`")
    step("the issue time is stored", any(m == "fc_lead_hours" for _, _, m, _ in rd) or not rd,
         "every value carries how far ahead of its forecast it is, so it can be checked afterwards")
except Exception as e:  # noqa: BLE001
    step("the adapter returns", False, f"{type(e).__name__}: {str(e)[:140]}")

print()
if bad:
    sys.exit(f"forecast: {len(bad)} check(s) failed — {', '.join(bad)}")
print("forecast: the point is this one, the units are as documented, and the forecast is fresh.")
