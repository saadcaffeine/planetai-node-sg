"""Tests for the shipped code packs' logic, without their services.
  · coast: the inland refusal and the metric mapping, against a saved Marine API payload
  · earth-engine: compute() against a fake `ee` that returns known numbers; fetch() stays idle without credentials
    (land change is no longer here: it moved to the `earth` pack in v0.33.1, tests/test_earth.py)
Run: PYTHONPATH=/tmp/stub:app python3 tests/test_packs.py"""
import importlib.util
import os
import sys
import types

import yaml

def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m

# ---------------------------------------------------------------- coast
coast = load("packs/coast/adapter.py", "coast")
class R:
    def __init__(s, j): s.j = j
    def raise_for_status(s): pass
    def json(s): return s.j
class HC:
    def __init__(s, j): s.j = j
    def get(s, url, params=None): return R(s.j)
marine = {"latitude": -8.791664, "longitude": 115.125015, "current_units": {"wave_height": "m"},
          "current": {"time": "2026-09-05T03:45", "wave_height": 1.72, "wave_direction": 203, "wave_period": 11.75,
                      "swell_wave_height": 1.58, "swell_wave_period": 11.1, "sea_surface_temperature": 27.4}}
os.environ.update(NODE_LAT="-8.8271", NODE_LON="115.15709")
s, r = coast.fetch(HC(marine))
m = {k: v for _, _, k, v in r}
assert s[0]["kind"] == "model" and s[0]["scale"] == "bioregion" and not s[0]["local"]
assert m["wave_height_m"] == 1.72 and m["sea_surface_temp"] == 27.4 and m["swell_period_s"] == 11.1
assert 4 < s[0]["meta"]["distance_km"] < 6, "the node is ~5 km from that ocean cell"
os.environ.update(NODE_LAT="-8.5069", NODE_LON="115.2625", COAST_MAX_KM="10")     # Ubud
try:
    coast.fetch(HC(marine)); raise AssertionError("an inland node must be refused")
except RuntimeError:
    pass
os.environ.update(NODE_LAT="-8.8271", NODE_LON="115.15709"); os.environ.pop("COAST_MAX_KM", None)

# ---------------------------------------------------------------- earth-engine, with a fake ee
eepack = load("packs/earth-engine/adapter.py", "eepack")

class FakeVal:
    def __init__(s, v): s.v = v
    def getInfo(s): return s.v
class FakeImage:
    def __init__(s, data): s.data = data
    def select(s, *a): return s
    def updateMask(s, *a): return s
    def rename(s, *a): return s
    def normalizedDifference(s, *a): return s
    def neq(s, *a): return s
    def And(s, *a): return s
    def reduceRegion(s, **kw): return FakeDict(s.data)
class FakeDict:
    def __init__(s, d): s.d = d
    def get(s, k): return FakeVal(s.d.get(k))
    def getInfo(s): return s.d
class FakeIC:
    def __init__(s, cid): s.cid = cid
    def filterBounds(s, *a): return s
    def filterDate(s, a, b): s.year = int(a[:4]); return s
    def select(s, *a): return s
    def sort(s, *a): return s
    def map(s, fn): return s
    def mode(s): return FakeImage({"label": {"1": 60, "6": 30, "4": 10}})                      # 60% trees, 30% built, 10% crops
    def median(s): return FakeImage({"ndvi": 0.42})
    def first(s):
        return FakeImage({"avg_rad": 3.7})
class FakeReducer:
    @staticmethod
    def frequencyHistogram(): return "hist"
    @staticmethod
    def mean(): return "mean"
class FakeGeom:
    @staticmethod
    def Point(c):
        class P:
            def buffer(s, m): return "aoi"
        return P()
fake_ee = types.SimpleNamespace(ImageCollection=FakeIC, Reducer=FakeReducer, Geometry=FakeGeom)

out = eepack.compute(fake_ee, -8.8271, 115.15709, 2025)
assert abs(out["tree_frac"] - 0.6) < 1e-9 and abs(out["built_frac"] - 0.3) < 1e-9 and abs(out["crop_frac"] - 0.1) < 1e-9
assert out["water_frac"] == 0.0, "an absent class is 0, not missing"
assert out["ndvi_median"] == 0.42 and out["night_lights"] == 3.7
# land change is the earth pack's now. One number for one thing: this pack must not publish a second.
assert "land_change_score" not in out, "land_change_score moved to the earth pack in v0.33.1"
assert not any("land_change" in m for m in yaml.safe_load(open("packs/earth-engine/pack.yaml"))["metrics"])
assert "land_change" not in open("packs/earth-engine/cells.yml").read()
assert "land_change" not in open("packs/earth-engine/adapter.py").read()

# without credentials the pack must stay idle, not raise, and must not retry every poll
for k in ("EE_PROJECT", "EE_SERVICE_ACCOUNT", "EE_KEY_FILE"): os.environ.pop(k, None)
sys.modules["ee"] = types.ModuleType("ee")     # importable, but _init will fail on missing config
eepack._state["last"] = 0
assert eepack.fetch(None) == ([], []) and eepack._state["warned"]

# verify.py, run end to end against a fake ee. Its step 6 named adapter.EMB for a year after the AlphaEarth score
# left the adapter, so the one script a tester runs to check their setup died with AttributeError on a good setup.
import contextlib, io, json, tempfile   # noqa: E401,E402
class _Q:                                # every call chains; getInfo() is the only answer
    def __getattr__(s, name): return lambda *a, **k: s
    def getInfo(s): return {"elevation": 42}
_seen = []
_vee = types.ModuleType("ee")
_vee.Initialize = _vee.ServiceAccountCredentials = lambda *a, **k: None
_vee.Image = lambda cid: _Q(); _vee.ImageCollection = lambda cid: (_seen.append(cid), _Q())[1]
_vee.Reducer = _vee.Geometry = _Q()
with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as _kf:
    json.dump({"project_id": "p", "client_email": "sa@p"}, _kf)
os.environ.update(EE_PROJECT="p", EE_SERVICE_ACCOUNT="sa@p", EE_KEY_FILE=_kf.name)
sys.modules["ee"] = _vee; sys.modules.pop("adapter", None)
_out = io.StringIO()
with contextlib.redirect_stdout(_out):
    load("packs/earth-engine/verify.py", "ee_verify")     # an AttributeError here is the bug
os.unlink(_kf.name); sys.modules.pop("adapter", None); [os.environ.pop(k) for k in ("EE_PROJECT", "EE_SERVICE_ACCOUNT", "EE_KEY_FILE")]
assert "Setup is good" in _out.getvalue(), _out.getvalue()
assert _seen == [eepack.DW, eepack.S2, eepack.VIIRS], f"verify.py checks {_seen}, the adapter reads DW, S2, VIIRS"
print("earth-engine verify.py runs all six steps and checks only the datasets the adapter reads")

print("all pack tests pass")

# ---------------------------------------------------------------- place: a node that moved
# Everything the place pack stores is a circle around one point, and the staleness test used to look only at the
# radius and the age. Change NODE_LAT/NODE_LON in .env and the node kept the previous neighbourhood's geometry for
# up to PLACE_REFRESH_DAYS while computing "nearest clinic" from the new point to the old features.
_pg = types.ModuleType("psycopg"); _pg.connect = lambda *a, **k: None
_pgj = types.ModuleType("psycopg.types.json"); _pgj.Jsonb = dict
_pgt = types.ModuleType("psycopg.types"); _pgt.json = _pgj; _pg.types = _pgt
sys.modules.setdefault("psycopg", _pg); sys.modules.setdefault("psycopg.types", _pgt); sys.modules.setdefault("psycopg.types.json", _pgj)
place = load("packs/place/adapter.py", "place_adapter")

BALI = (-8.8271, 115.15709)
assert round(place.metres(*BALI, BALI[0] + 0.001, BALI[1])) == 111, "one thousandth of a degree of latitude is 111 m"
assert round(place.metres(41.4036, 2.2033, 41.4036, 2.2043)) == 83, "longitude shrinks with the cosine of latitude"
assert place.metres(*BALI, *BALI) == 0.0

# the tolerance: 1% of the radius, never under 25 m, so a hand-typed decimal is not a refetch
assert not place.moved(BALI[0] + 0.0002, BALI[1], *BALI, 1000), "22 m is a typed correction, not a move"
assert place.moved(BALI[0] + 0.0005, BALI[1], *BALI, 1000), "56 m at a 1 km radius is a move"
assert not place.moved(BALI[0] + 0.0005, BALI[1], *BALI, 10000), "56 m of a 10 km circle is not"
assert place.moved(BALI[0] + 0.002, BALI[1], *BALI, 10000), "222 m of a 10 km circle is"
assert place.moved(41.4036, 2.2033, *BALI, 1000), "Bali to Poblenou is a move by any measure"
# a run recorded before v0.33.4 has no point; fetch() treats that as stale rather than guessing
assert not place.moved(*BALI, None, None, 1000)
assert place.MOVE_MIN_M == 25.0 and place.MOVE_FRAC == 0.01
# the reason a refresh happened has to reach the log, and the satellite caches have to be cleared on a move
_src = open("packs/place/adapter.py").read()
assert "place_runs (run_at, radius_m, n_features, source, lat, lon)" in _src, "the run must record its point"
assert 'ALTER TABLE place_runs ADD COLUMN IF NOT EXISTS lat' in _src, "additive for nodes that ran before"
assert 'for t in ("place_buildings_sat", "place_yearly")' in _src, "a move invalidates the satellite caches too"
assert "SELECT run_at, radius_m, lat, lon FROM place_runs" in _src, "staleness must read the stored point"
print("place move tests pass")


# ---------------------------------------------------------------- a rule that contributes is not an alert
os.environ.setdefault("DATABASE_URL", "postgresql://x/x")
os.environ["PACKS_DIR"] = "packs"          # the repo's own packs, not the container's /app/packs
_packs = load("app/packs.py", "packs_under_test")

assert _packs.CONTRIBUTES == ("report",), "tools/check_rules.py carries this list too; keep them together"
_all = {r["id"] for r in _packs.rules()}
_alerts = {r["id"] for r in _packs.alerts()}
_contrib = {r["id"] for r in _packs.contributors("report")}
assert _contrib == _all - _alerts, "every rule is either sent or contributed, never both and never neither"
assert "insight/digest" in _contrib, "the digest is part of the report now, not a message every three hours"
for r in _packs.alerts():
    assert r.get("message"), f"{r['id']} is loaded as an alert with no message; it would print its own braces"
for r in _packs.contributors("report"):
    assert not r.get("message") and not r.get("level"), f"{r['id']} contributes; it has nothing to send"
print("a rule either says something or contributes something, and the loader knows which")
# ---------------------------------------------------------------- channel role registry
# The channel role registry. Integrity rules read roles, not metric names.
# CORE_CHANNELS defaults to /app/config/channels.yml (the container mount); point it at the repo's own copy so
# this test exercises the real, shipped file without needing a container.
os.environ.setdefault("CHANNELS_PATH", "config/channels.yml")
import packs as _packs
_ch = _packs.channels()
_by = {(c["source"], c["metric"]): c for c in _ch}
assert _by[("smartcitizen", "pm25")]["role"] == "ambient" and _by[("smartcitizen", "pm25")]["comparable"] is True
assert _by[("smartcitizen", "bme_iaq")]["role"] == "index", "a vendor index is never pooled"
assert _by[("meshtastic", "temp")]["role"] == "enclosure", "a radio in a sealed case reports its own box"
assert _by[("meshtastic", "battery_pct")]["role"] == "device_health"
assert _by[("smartcitizen", "pm25")]["declared_by"] == "core"
assert all(c["role"] in ("ambient", "enclosure", "device_health", "derived", "index", "private") for c in _ch)
assert len({(c["source"], c["metric"]) for c in _ch}) == len(_ch), "one declaration per source and metric"
print(f"{len(_ch)} channel roles declared")


# ---------------------------------------------------------------- every alert template speaks every language the node offers
# A Santiago or Menorca tester read English until v0.32. A rule added with only `en` would silently fall back for
# everyone else, so the set is checked as a set: same keys, same placeholders, in every rules.yml.
import glob, re, yaml
LOCALES = {"en", "id", "es"}
for f in ["config/rules.yml"] + sorted(glob.glob("packs/*/rules.yml")):
    for r in yaml.safe_load(open(f)) or []:
        m = r.get("message")
        if not isinstance(m, dict):
            continue
        assert set(m) == LOCALES, f"{f} {r['id']}: message has {sorted(m)}, needs {sorted(LOCALES)}"
        ph = {k: set(re.findall(r"\{(\w+)", v)) for k, v in m.items()}
        assert len(set(map(frozenset, ph.values()))) == 1, f"{f} {r['id']}: placeholders differ between languages: {ph}"
        for k, v in m.items():
            assert v.strip() and len(v) < 700, f"{f} {r['id']}.{k}: empty or too long for a phone"
assert "es" in open("app/settings.py").read().split('"ALERT_LOCALE"')[1].split("\n")[0], "settings.py: ALERT_LOCALE help must name es"
# the language select is built in the dashboard's own script, not typed into index.html, since v0.54
assert "'es', 'Espa\u00f1ol'" in open("app/static/dashboard.js").read(), "dashboard: language select needs Espa\u00f1ol"
for pre in ("santiago", "barcelona", "menorca"):
    assert "ALERT_LOCALE=es" in open(f"presets/{pre}.env").read(), f"presets/{pre}.env: Spanish-first pilots speak Spanish"
print("every template speaks en, id and es")

# packs.module() is the one place that knows where a node keeps its packs. Two callers used to
# insert "../packs/<name>" on sys.path and import bare — engine._where_to_go and report.sheet — and
# "../packs" is not where the image keeps them (/app/packs is, and PACKS_DIR is unset there), so
# both imports failed on every real node. Both swallow the failure by design, so nothing said so:
# `asks.where` was null with the make pack on and a lab 3.3 km away, and the report's `make` line
# never appeared once. This asserts the loader finds a real pack's adapter, and that neither caller
# has gone back to building the path itself.
import pathlib as _pl
_m = _packs.module("make")
assert _m is not None, f"packs.module('make') found nothing under {_packs.PACKS_DIR}"
assert hasattr(_m, "ask_line"), "packs/make/adapter.py no longer exposes ask_line"
assert _packs.module("no-such-pack") is None, "a pack that is not here must be None, never a raise"
assert _packs.module("make", "no-such-module") is None, "a missing module must be None"
for _f in ("app/issues/engine.py", "app/report.py"):
    # The CODE, not the prose: both files explain the old bug in a comment that names the path, and
    # matching the string flagged the explanation as the offence.
    _src = "\n".join(l.split("#")[0] for l in _pl.Path(_f).read_text().split("\n"))
    assert 'getenv("PACKS_DIR"' not in _src, \
        f"{_f} resolves PACKS_DIR itself again; packs.py holds that default (/app/packs on a node)"
    assert "path.insert" not in _src, \
        f"{_f} is putting a pack on sys.path again; packs.module() imports it by file"
print("packs.module finds a pack's adapter, and neither caller builds the path itself")

# packs.read_yaml: parsed once per change of the file (GET /issues parsed every pack.yaml 223 times a request), and a
# copy each time, because every caller sets keys on what it gets
import tempfile  # noqa: E402
import time  # noqa: E402
sys.path.insert(0, "app")
import packs as _packs  # noqa: E402
with tempfile.TemporaryDirectory() as _d:
    _f = __import__("pathlib").Path(_d) / "pack.yaml"
    _f.write_text("id: one\nmetrics: [pm25]\n")
    _a = _packs.read_yaml(_f); _a["metrics"].append("changed"); _a["id"] = "changed"
    assert _packs.read_yaml(_f) == {"id": "one", "metrics": ["pm25"]}, "read_yaml handed out the cached object itself"
    time.sleep(0.01)
    _f.write_text("id: two\n")
    assert _packs.read_yaml(_f) == {"id": "two"}, "read_yaml served the old parse of a file that changed"
    _f.unlink()
    try:
        _packs.read_yaml(_f)
        raise AssertionError("read_yaml served a deleted file from its cache")
    except FileNotFoundError:
        pass
    _f.write_text("id: [unclosed\n")
    try:
        _packs.read_yaml(_f)
        raise AssertionError("read_yaml parsed a broken file")
    except __import__("yaml").YAMLError:
        pass
print("packs.read_yaml: one parse per change of the file, a copy each time, missing and broken files raise")

