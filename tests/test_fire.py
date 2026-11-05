"""packs/fire: rings, directions, upwind, polite polling, and rules that speak at the right level.

The fixtures are REAL rows from NASA FIRMS's public VIIRS files, read 14 Oct 2026 at about 17:15 UTC (CC0, NASA
FIRMS): NOAA-20 and NOAA-21 SouthEast_Asia 24 h, every row within 150 km of (-8.8, 115.1) on Bali's Bukit and ten
from 150 to 400 km, and NOAA-20 Europe 24 h within 600 km of (39.9, 4.1) on Menorca. Each also keeps one row from
far outside any ring. The numbers asserted below are what those rows say; nothing here touches the network or a
database. The rules' SQL is checked against init.sql by tools/check_rules.py in `make lint`.
"""
import csv
import importlib.util
import io
import os
import re
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
FIX = ROOT / "packs/fire/tests/fixtures"
os.environ.update(NODE_LAT="-8.8", NODE_LON="115.1", PACK_OUT=tempfile.mkdtemp())
spec = importlib.util.spec_from_file_location("fire_adapter", ROOT / "packs/fire/adapter.py")
A = importlib.util.module_from_spec(spec)
spec.loader.exec_module(A)

fails = []


def check(label, cond, detail=""):
    if not cond:
        fails.append(f"{label}{': ' + str(detail) if detail else ''}")


BALI, MENORCA = (-8.8, 115.1), (39.9, 4.1)
AT = datetime(2026, 10, 14, 17, 16, tzinfo=timezone.utc)      # when the fixtures were read

# ---------------------------------------------------------------- ring math and directions
check("one degree of latitude is 111.2 km", abs(A.km(0, 0, 1, 0) - 111.2) < 0.1, A.km(0, 0, 1, 0))
check("bearings: N E S W", [round(A.bearing(0, 0, *p)) for p in ((1, 0), (0, 1), (-1, 0), (0, -1))] == [0, 90, 180, 270])
check("upwind is ±45° of where the wind comes from", A.upwind(80, 45) and A.upwind(10, 45) and not A.upwind(91, 45))
check("upwind wraps through north", A.upwind(350, 20) and A.upwind(20, 350) and not A.upwind(300, 20))
check("Bali at 150 km reads South East Asia", A.region(*BALI, 150) == "SouthEast_Asia")
check("Bali at 500 km runs past that file's box: Global", A.region(*BALI, 500) == "Global")
check("Singapore at 500 km fits South East Asia", A.region(1.317, 103.885, 500) == "SouthEast_Asia")
check("Menorca reads Europe", A.region(*MENORCA, 500) == "Europe")
check("nowhere in a box reads Global", A.region(-33.4, -70.6, 150) == "Global")

# ---------------------------------------------------------------- parsing the real files
j1 = (FIX / "J1_VIIRS_C2_SouthEast_Asia_24h_bali.csv").read_text()
j2 = (FIX / "J2_VIIRS_C2_SouthEast_Asia_24h_bali.csv").read_text()
rows = list(csv.DictReader(io.StringIO(j1)))
within = [r for r in rows if A.km(*BALI, float(r["latitude"]), float(r["longitude"])) <= 150]
low = sum(1 for r in within if r["confidence"] == "low")
s1, s2 = A.parse(j1, *BALI, 150), A.parse(j2, *BALI, 150)
check("NOAA-20: 35 detections in 150 km once the low-confidence ones go", len(s1) == 35, len(s1))
check("the public file spells confidence `low`, and those go", low > 0 and len(s1) + low == len(within), (low, len(within)))
check("NOAA-21: 34 detections", len(s2) == 34, len(s2))
check("the row from far away is not kept", all(A.km(*BALI, s[1], s[2]) <= 150 for s in s1 + s2))
check("the API's `l` is low too", A.parse("latitude,longitude,acq_date,acq_time,confidence,frp\n-8.8,115.1,2026-10-14,0100,l,3\n", *BALI, 25) == [])
try:
    A.parse("Invalid MAP_KEY", *BALI, 25)
    check("a table that is not a table must raise", False)
except RuntimeError as e:
    check("an answer that is not a table says what came back", "not a fire table" in str(e))

# ---------------------------------------------------------------- one place per cell, whoever saw it
twice = [[1.0, -8.5, 115.5, 3.0], [2.0, -8.5001, 115.5001, 7.0]]       # NOAA-20, then NOAA-21 ~50 min later
check("one fire seen by two satellites is one place", len(A.places(twice)) == 1 and A.places(twice)[0][3] == 7.0)
check("NOAA-20 and NOAA-21 together: 57 places from 69 detections", len(A.places(s1 + s2)) == 57, len(A.places(s1 + s2)))


def m(readings):
    return {k: v for _, _, k, v in readings}


# ---------------------------------------------------------------- Bali, 14 Oct 2026, the numbers
calm = m(A.summarise(s1 + s2, AT, *BALI, 25, 150, None))
check("Bali: nothing in the local 25 km ring", calm["fires_local_24h"] == 0 and calm["frp_local_mw"] == 0, calm)
check("Bali: 51 burning places within 150 km in the last 24 h", calm["fires_region_24h"] == 51, calm)
check("Bali: the nearest is 75 km north-west (East Java)", calm["fires_nearest_km"] == 75.1 and calm["fires_nearest_bearing"] == 309, calm)
check("no wind, no upwind numbers", not any("upwind" in k or "wind_from" in k for k in calm), calm)
se = m(A.summarise(s1 + s2, AT, *BALI, 25, 150, 135.0))
check("a south-east wind puts 3 upwind", se["fires_region_upwind"] == 3 and se["fires_local_upwind"] == 0, se)
nw = m(A.summarise(s1 + s2, AT, *BALI, 25, 150, 315.0))
check("a north-west wind puts 47 upwind, the nearest the 75 km one", nw["fires_region_upwind"] == 47 and nw["fires_upwind_km"] == 75.1, nw)
wide = m(A.summarise(s1 + s2, AT, *BALI, 100, 150, 315.0))
check("a 100 km local ring reaches 2, both upwind of a north-west wind", wide["fires_local_24h"] == 2 and wide["fires_local_upwind"] == 2, wide)
check("a day later the ring is empty, and no nearest is invented",
      "fires_nearest_km" not in m(A.summarise(s1 + s2, AT + timedelta(days=2), *BALI, 25, 150, 315.0)))
menorca = m(A.summarise(A.parse((FIX / "J1_VIIRS_C2_Europe_24h_menorca.csv").read_text(), *MENORCA, 500), AT, *MENORCA, 25, 500, None))
check("Menorca: 33 places within 500 km, the nearest 249 km north-west", menorca["fires_region_24h"] == 33
      and menorca["fires_nearest_km"] == 248.8 and menorca["fires_nearest_bearing"] == 315, menorca)


# ---------------------------------------------------------------- polling: off, first start, paced, unchanged, changed
def table(hours_ago):
    """Fixture rows moved so the newest is `hours_ago` old: fetch() reads the real clock."""
    now = datetime.now(timezone.utc)
    out = io.StringIO()
    w = None
    for r in csv.DictReader(io.StringIO(j1)):
        t = datetime.strptime(f"{r['acq_date']} {r['acq_time']}", "%Y-%m-%d %H%M").replace(tzinfo=timezone.utc)
        t = now - timedelta(hours=hours_ago) - (AT - t)
        r.update(acq_date=f"{t:%Y-%m-%d}", acq_time=f"{t:%H%M}")
        if w is None:
            w = csv.DictWriter(out, fieldnames=list(r)); w.writeheader()
        w.writerow(r)
    return out.getvalue()


class R:
    def __init__(self, code=200, text="", etag=None, url=""):
        self.status_code, self.text, self.url = code, text, url
        self.headers = {"etag": etag, "last-modified": "Wed, 14 Oct 2026 16:43:00 GMT"} if etag else {}

    def raise_for_status(self):
        if self.status_code >= 400:
            e = Exception(f"Client error '{self.status_code}' for url '{self.url}'")
            e.response = self
            raise e


class HC:
    def __init__(self, etag="a", code=200, text=None):
        self.etag, self.code, self.text, self.calls = etag, code, text or table(1), []

    def head(self, url, timeout=0):
        self.calls.append(("HEAD", url, {}))
        return R(200, "", self.etag, url)

    def get(self, url, headers=None, timeout=0):
        self.calls.append(("GET", url, headers or {}))
        if self.code == 304:
            return R(304, "", self.etag, url)
        return R(self.code, self.text, self.etag, url)


A.wind = lambda: 315.0          # a stub wind: the database is not here
for k in ("FIRE_LOCAL_KM", "FIRE_REGION_KM", "FIRE_POLL_HOURS", "FIRE_SATELLITES", "FIRMS_MAP_KEY"):
    os.environ.pop(k, None)

os.environ["FIRE_ENABLED"] = "0"
hc = HC()
check("off by default: nothing asked, nothing stored", A.fetch(hc) == ([], []) and hc.calls == [])

os.environ["FIRE_ENABLED"] = "1"
hc = HC()
sensors, readings = A.fetch(hc)
check("first start takes the 7-day file, once per satellite",
      [c[1].rsplit("/", 1)[1] for c in hc.calls] == ["J1_VIIRS_C2_SouthEast_Asia_7d.csv", "J2_VIIRS_C2_SouthEast_Asia_7d.csv"], hc.calls)
check("the sensor is a model, not local, and not at the house", sensors[0]["kind"] == "model" and sensors[0]["local"] is False
      and sensors[0]["lat"] is None and sensors[0]["sensor_id"] == "firms-fires", sensors)
check("its name gives both rings, so 'nearby' under it is not read as 150 km (4 Nov: it said only 150 km)",
      sensors[0]["name"] == "NASA FIRMS, VIIRS satellites: nearby is within 25 km, the region 150 km", sensors[0]["name"])
check("first start also writes the six days before, without upwind",
      sum(1 for r in readings if r[2] == "fires_region_24h") == 7 and sum(1 for r in readings if r[2] == "fires_region_upwind") == 1)
now_set = {r[2]: r[3] for r in readings if r[0] == max(x[0] for x in readings)}
check("today's set carries the upwind count by the stub wind", now_set.get("fire_wind_from_deg") == 315 and "fires_region_upwind" in now_set, now_set)

hc = HC()
check("asked again at once: paced, nothing asked", A.fetch(hc) == ([], []) and hc.calls == [])

st = A._load()
st["checked"] -= 4 * 3600
A._save(st)
hc = HC(etag="a")
check("unchanged ETag on HEAD: no download, no new rows", A.fetch(hc) == ([], []) and [c[0] for c in hc.calls] == ["HEAD", "HEAD"], hc.calls)

st = A._load(); st["checked"] -= 4 * 3600; A._save(st)
hc = HC(etag="b", code=304)
got = A.fetch(hc)
check("a 304 is no new rows", got == ([], []), got)
check("the GET carries If-None-Match and If-Modified-Since",
      any(c[0] == "GET" and c[2].get("If-None-Match") == "a" and "If-Modified-Since" in c[2] for c in hc.calls), hc.calls)

st = A._load(); st["checked"] -= 4 * 3600; A._save(st)
hc = HC(etag="c", text=table(2))
sensors, readings = A.fetch(hc)
check("a changed file is read: the 24 h file now, and one set of rows",
      any(c[1].endswith("J1_VIIRS_C2_SouthEast_Asia_24h.csv") for c in hc.calls)
      and sum(1 for r in readings if r[2] == "fires_region_24h") == 1, hc.calls)

# the key rides in the URL path, so no error may carry a URL
os.environ.update(FIRMS_MAP_KEY="KEY-THAT-MUST-NOT-LEAK", FIRE_SATELLITES="noaa-20")
st = A._load(); st["checked"] -= 4 * 3600; A._save(st)
hc = HC(code=403)
try:
    A.fetch(hc)
    check("every satellite failing must raise", False)
except RuntimeError as e:
    check("the key is not in the error", "KEY-THAT-MUST-NOT-LEAK" not in str(e) and "403" in str(e), str(e))
check("with a key it asks the area API for the ring's box, and no HEAD",
      hc.calls and hc.calls[0][0] == "GET" and "/api/area/csv/" in hc.calls[0][1] and "VIIRS_NOAA20_NRT" in hc.calls[0][1], hc.calls)
check("a failure still records the ask, so a server that is down is not asked every five minutes",
      A.fetch(HC()) == ([], []))
os.environ.pop("FIRMS_MAP_KEY")
os.environ.pop("FIRE_SATELLITES")

# ---------------------------------------------------------------- the rules: levels, wording, roles
rules = {r["id"]: r for r in yaml.safe_load((ROOT / "packs/fire/rules.yml").read_text())}
check("three rules, one at each level", {k: r["level"] for k, r in rules.items()}
      == {"fire_near": "info", "fire_upwind_near": "warn", "smoke_arriving": "act"}, rules.keys())
check("none is kinded: the event engine's kinds are about rooms", not any(r.get("kind") for r in rules.values()))
check("cooldowns are long, half a day or more", all(r["cooldown_minutes"] >= 720 for r in rules.values()))
act = rules["smoke_arriving"]["sql"]
check("act needs the fires AND the air: upwind count, the WHO line, and a rise",
      "fires_region_upwind" in act and ">= 25" in act and "a.recent >= 15" in act and "1.5 * a.before" in act)
check("act reads outdoor air only, and never a peer", "NOT s.indoor" in act and "s.kind = 'sensor'" in act)
check("act names the WHO line with its unit", all("15 µg/m³" in t for t in rules["smoke_arriving"]["message"].values()))
check("info and warn never page: neither is act", rules["fire_near"]["level"] != "act" and rules["fire_upwind_near"]["level"] != "act")
row = {"sensor_id": "firms-fires", "fires": 3, "km": 12, "ring": 25, "pm25": 30,
       "dir": {"en": "north-east", "id": "timur laut", "es": "noreste"}}       # `dir` arrives as a JSON object
for rid, r in rules.items():
    for loc, t in r["message"].items():
        text = t.format(**row)
        check(f"{rid}/{loc} renders", "{" not in text and row["dir"][loc] in text and "12 km" in text, text)
        check(f"{rid}/{loc} has one sign", sum(1 for ch in text if ord(ch) > 0x2600 and not ch.isalpha()) == 1, text)
        check(f"{rid}/{loc} never says a coordinate", not re.search(r"-?\d+\.\d{2,}", text), text)

pack = yaml.safe_load((ROOT / "packs/fire/pack.yaml").read_text())
roles = {d["metric"]: d for d in yaml.safe_load((ROOT / "packs/fire/channels.yml").read_text())}
check("every metric has a declared role", set(pack["metrics"]) == set(roles), set(pack["metrics"]) ^ set(roles))
check("all derived, none comparable, none private", all(d["role"] == "derived" and not d["comparable"] for d in roles.values()))
produced = {k for k in (m(A.summarise(s1 + s2, AT, *BALI, 100, 150, 315.0)))}
check("the adapter produces every declared metric", produced == set(roles), produced ^ set(roles))
check("the map key is a secret", pack.get("secrets") == ["FIRMS_MAP_KEY"])
check("off until somebody says yes", "FIRE_ENABLED=0" in pack["env"])
sec = pack["sections"][0]
check("one public section on the Wall, from the pack's own metrics", sec["wall"] is True and len(pack["sections"]) == 1
      and {r["metric"] for r in sec["readouts"]} <= set(roles) and all(r["sensor_id"] == "firms-fires" for r in sec["readouts"]))
check("the sensor's name says FIRMS and VIIRS, so the Wall labels it satellite",
      "FIRMS" in sensors[0]["name"] and "VIIRS" in sensors[0]["name"], sensors[0]["name"])

print("\n".join(f"  x {f}" for f in fails) or "  fire: rings, directions and upwind hold on real FIRMS rows; "
      "it asks politely, keeps no key in an error, and speaks at info, warn and act")
sys.exit(1 if fails else 0)
