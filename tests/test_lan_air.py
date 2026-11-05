"""packs/airgradient and packs/purpleair: the household's own monitors on the WiFi, read again.

Both readers were core adapters until v0.16 (5 Sep 2026) dropped them from the poll by accident, while the settings and
the installer's flags stayed: a node that set AIRGRADIENT_HOSTS read nothing. They are packs since 22 Oct 2026, on
whenever their hosts are set, so nobody needs a new key, and update.sh adds them where a node lists its packs.
The readers' payloads are checked in tests/test_sources.py. They borrow the EPA 2021 correction from packs/air-quality,
which since 24 Oct 2026 also carries the CAMS model the core used to poll (section 2b).

    PACKS_DIR=packs PYTHONPATH=app python3 tests/test_lan_air.py
"""
import os
import subprocess
import sys
import tempfile
import time

os.environ.update(PACKS_DIR="packs", NODE_LAT="-8.65", NODE_LON="115.22", PACKS_ALLOW_CODE="0")
sys.path.insert(0, "app")
import settings  # noqa: E402
import packs     # noqa: E402
import sources   # noqa: E402

ROWS = {"PACKS_ENABLED": "", "OPENMETEO_ENABLED": "0", "PACKS_ALLOW_CODE": "0"}
settings._cache = {"at": time.time() + 1e9, "rows": ROWS}

AG = {"serialno": "84fce612a5b4", "rco2": 612, "pm01": 4, "pm02": 9, "pm10": 11, "atmp": 29.4, "rhum": 61, "model": "I-9PSL"}
PA = {"SensorId": "84:f3:eb:12:34:56", "pm2_5_cf_1": 47.8, "pm2_5_cf_1_b": 46.9, "current_humidity": 62}


class R:
    def __init__(s, j): s.j = j
    def json(s): return s.j


class HC:
    """The LAN: an AirGradient answers /measures/current, a PurpleAir /json."""
    def __init__(s): s.urls = []
    def get(s, url, timeout=None):
        s.urls.append(url)
        return R(AG if "/measures/current" in url else PA)


# ---- 1. off with no host, on with one, with no PACKS_ALLOW_CODE
for pack, key in (("airgradient", "AIRGRADIENT_HOSTS"), ("purpleair", "PURPLEAIR_HOSTS")):
    d = packs.PACKS_DIR / pack
    ROWS[key] = ""
    assert not packs._official_on(d), pack
    ROWS[key] = "192.168.1.60"
    assert packs._official_on(d), pack
    ROWS[key] = ""
print("lan air: each pack is on whenever its hosts are set, with no PACKS_ALLOW_CODE")

# ---- 2. the poll reads them again, through the same sources.enabled() the core polls with
names = [n for n, _ in sources.enabled(HC())]
assert "airgradient" not in names and "purpleair" not in names, names
ROWS.update(AIRGRADIENT_HOSTS="airgradient_84fce6.local, 192.168.1.52", PURPLEAIR_HOSTS="192.168.1.60", SENSOR_INDOOR="1")
hc = HC()
got = dict(sources.enabled(hc))
s, r = got["airgradient"]()
assert [x["sensor_id"] for x in s] == ["ag-84fce612a5b4"] * 2 and all(x["indoor"] and x["local"] for x in s), s
assert s[0]["lat"] == -8.65 and s[0]["meta"]["host"] == "airgradient_84fce6.local", "the node's coordinates, the host as listed"
assert {m for _, _, m, _ in r} >= {"pm25", "pm25_raw", "co2", "temp", "humidity"}, r
s, r = got["purpleair"]()
assert s[0]["sensor_id"] == "pa-84f3eb123456" and s[0]["indoor"] and {m for _, _, m, _ in r} == {"pm25", "pm25_raw", "humidity"}
assert hc.urls == ["http://airgradient_84fce6.local/measures/current", "http://192.168.1.52/measures/current",
                   "http://192.168.1.60/json?live=true"], hc.urls
assert not hasattr(sources, "airgradient") and not hasattr(sources, "purpleair"), "one copy, in the packs"
ROWS["PACKS_ENABLED"] = "air-quality,heat"
assert not {"airgradient", "purpleair"} & {n for n, _ in sources.enabled(HC())}, "a node that lists its packs without them reads none"
ROWS.update(PACKS_ENABLED="", AIRGRADIENT_HOSTS="", PURPLEAIR_HOSTS="", SENSOR_INDOOR="")
print("lan air: the poll reads every listed host, indoors from SENSOR_INDOOR, and nothing with no host")

# ---- 2b. CAMS is packs/air-quality's, on with Global models as it was in the core, and its correction is borrowed
class AQ:
    """Open-Meteo's air-quality API, now and hourly."""
    def get(s, url, params=None, timeout=None):
        assert url == "https://air-quality-api.open-meteo.com/v1/air-quality", url
        if "hourly" in params:
            return R({"hourly": {"time": ["2026-10-23T00:00", "2026-10-23T01:00"], "pm2_5": [12.0, None], "pm10": [20.0, 21.0]}})
        return R({"current": {"time": "2026-10-24T03:00", "pm2_5": 18.4, "pm10": 30.1, "uv_index": 9.0}})
    def raise_for_status(s): pass


R.raise_for_status = lambda s: None
assert not hasattr(sources, "openmeteo_air") and not hasattr(sources, "epa_2021_correct"), "one copy, in the pack"
assert "air-quality" not in {n for n, _ in sources.enabled(AQ())}, "OPENMETEO_ENABLED=0: no CAMS, as in the core"
ROWS["OPENMETEO_ENABLED"] = "1"
got = dict(sources.enabled(AQ()))
s, r = got["air-quality"]()
assert s[0]["sensor_id"] == "cams-point" and s[0]["source"] == "open-meteo-cams" and s[0]["kind"] == "model", s
assert {m: v for _, _, m, v in r} == {"pm25_model": 18.4, "pm10_model": 30.1, "uv_index": 9.0}, r
assert r[0][0].isoformat() == "2026-10-24T03:00:00+00:00", "Open-Meteo's UTC time without a zone, read as UTC"
air = packs.module("air-quality")
s, r = air.history(AQ(), -8.65, 115.22)
assert [(t.hour, m, v) for t, _, m, v in r] == [(0, "pm25_model", 12.0), (0, "pm10_model", 20.0), (1, "pm10_model", 21.0)], r
ROWS["PACKS_ENABLED"] = "heat"
assert packs.module("air-quality") is None and "air-quality" not in {n for n, _ in sources.enabled(AQ())}
ag = packs.module("air-quality", on_only=False)
assert ag and round(ag.epa_2021_correct(28, 65), 1) == 14.8, "a node with the air pack off still corrects a Plantower"
ROWS.update(PACKS_ENABLED="", OPENMETEO_ENABLED="0")
src = open("app/bootstrap.py").read()
assert 'packs.module("air-quality")' in src and "air.history(hc, lat, lon)" in src, "the first start takes its 92 days from the pack"
print("lan air: CAMS polls from packs/air-quality under OPENMETEO_ENABLED, and its EPA correction is there with the pack off")

# ---- 3. update.sh step 5b: added where hosts are set and the node lists its packs, once
src = open("update.sh").read()
block = src[src.index("# 5b."):src.index("# 6. rebuild and restart")]
STUB = r'''
docker() {   # docker compose exec -T db psql -U planetai -tAc "<sql>" planetai, against a key=value file
  local sql=""; for a in "$@"; do case "$a" in SELECT*|UPDATE*) sql="$a";; esac; done
  if [[ "$sql" == SELECT* ]]; then k="$(sed -E "s/.*key = '([A-Z_]+)'.*/\1/" <<< "$sql")"; sed -n "s/^${k}=//p" "$DB"
  else add="$(sed -E "s/.*\|\| ',([a-z-]+)'.*/\1/" <<< "$sql")"; sed -i.bak -E "s/^(PACKS_ENABLED=.+)$/\1,${add}/" "$DB"; rm -f "$DB.bak"; fi
}
'''


def run(db: str, env: str) -> tuple[str, str]:
    with tempfile.TemporaryDirectory() as t:
        open(os.path.join(t, "db"), "w").write(db); open(os.path.join(t, ".env"), "w").write(env)
        subprocess.run(["bash", "-c", STUB + block], cwd=t, env={**os.environ, "DB": os.path.join(t, "db")},
                       capture_output=True, text=True, check=True)
        return open(os.path.join(t, "db")).read(), open(os.path.join(t, ".env")).read()


LIST = "PACKS_ENABLED=air-quality,heat\n"
db, _ = run("AIRGRADIENT_HOSTS=airgradient_84fce6.local\n" + LIST, "")
assert "PACKS_ENABLED=air-quality,heat,airgradient" in db and "purpleair" not in db, db
assert run(db, "")[0] == db, "a second update changed the list again"
_, env = run("", "PURPLEAIR_HOSTS=192.168.1.60\n" + LIST)
assert "PACKS_ENABLED=air-quality,heat,purpleair" in env and "airgradient" not in env, env
db, env = run(LIST, LIST)
assert "airgradient" not in db + env and "purpleair" not in db + env, "added with no host"
ISS = "NODE_ISSUES=heat\n"                      # 5d would add air-quality for the air issue; 5b must stand alone
db, _ = run("OPENMETEO_ENABLED=1\nPACKS_ENABLED=heat\n" + ISS, "")
assert "PACKS_ENABLED=heat,air-quality" in db, db
db, env = run("PACKS_ENABLED=heat\n" + ISS, "OPENMETEO_ENABLED=0\nPACKS_ENABLED=heat\n" + ISS)
assert "air-quality" not in db + env, "Global models off: CAMS was off, so nothing to keep"
print("update.sh 5b: air-quality added where Global models is on and the node lists its packs")
print("update.sh 5b: airgradient and purpleair added where their hosts are set and the node lists its packs, once")
print("lan air: every check passed")
