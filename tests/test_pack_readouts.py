"""A pack adds readouts to an issue (docs/decisions/2026-10-01-packs.md, point 4), and never replaces anything.

pack_readouts() on its own first, then issues.load() reading a real packs folder written here, with PACKS_ENABLED on
and off, then the engine turning a merged readout into a number only when its sensor has a row. Last, the guarantee
that matters for every node that exists today: no shipped pack declares readouts, so load() is exactly the files.
Run: PYTHONPATH=app python3 tests/test_pack_readouts.py
"""
import copy
import logging
import os
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
tmp = Path(tempfile.mkdtemp())
os.environ["PACKS_DIR"] = str(tmp / "packs")                         # packs.py reads it at import
os.environ.setdefault("DATABASE_URL", "postgresql://x:x@127.0.0.1:1/x")  # settings falls back to the environment
os.environ.pop("PACKS_ENABLED", None)

import issues as I                 # noqa: E402
from issues import engine          # noqa: E402

logs = []
logging.getLogger("planetai.issues").addHandler(type("H", (logging.Handler,), {"emit": lambda self, r: logs.append(r.getMessage())})())
logging.getLogger("planetai.issues").setLevel(logging.WARNING)

# The files alone: since 23 Oct 2026 each issue ships in its pack (packs/<id>/issue.yml), so the four shipped ones
# are copied into one directory here, as load(<a directory>) reads them.
import shutil  # noqa: E402
ISSUES = tmp / "issues"; ISSUES.mkdir()
for _f in sorted((ROOT / "packs").glob("*/issue.yml")):
    shutil.copy(_f, ISSUES / f"{_f.parent.name}.yml")
FILES = I.load(ISSUES)
assert set(FILES) == {"air", "heat", "coast", "land", "water"}, set(FILES)
LABEL = {"en": "NEA PSI", "id": "PSI NEA", "es": "PSI de NEA"}


def ro(metric="psi", sensor="nea-psi", **kw):
    r = {"metric": metric, "sensor_id": sensor, "unit": "PSI", "dp": 0, "label": dict(LABEL)}
    r.update(kw)
    return {k: v for k, v in r.items() if v is not None}


def merged(*manifests):
    logs.clear(); I._said.clear()     # each case starts with a process that has said nothing yet
    return I.pack_readouts(copy.deepcopy(FILES), list(manifests))


def metrics(decl, key):
    return [(r["metric"], r["sensor_id"]) for r in decl[key].get("readouts") or []]


# ---------------------------------------------------------------- the merge
own = metrics(FILES, "coast")
d = merged({"id": "zeta", "readouts": {"coast": [ro("beach_band", "nea-beach-changi", unit="of 3")]}},
           {"id": "alpha", "readouts": {"coast": [ro("beach_band", "nea-beach-east-coast", unit="of 3")]}})
assert metrics(d, "coast") == own + [("beach_band", "nea-beach-east-coast"), ("beach_band", "nea-beach-changi")], metrics(d, "coast")
print("  a pack's readouts follow the issue's own, in the order of the packs' ids")

assert metrics(merged({"id": "p", "readouts": {"air": [ro()]}}), "air") == [("psi", "nea-psi")]
print("  an issue with no readouts of its own (air) takes a pack's")

# `noise`, not `water`: water is a real issue since the terrain pack (23 Oct 2026).
d = merged({"id": "p", "readouts": {"noise": [ro()]}})
assert d == FILES and any("'noise'" in m and "no issue on this node" in m for m in logs), logs
print("  a readout for an issue nobody declared is left out, and the log says which")

for bad, why in ((ro(label={"en": "PSI"}), "label in every locale"), (ro(unit=None), "needs a unit"),
                 (ro(dp="0"), "whole number"), (ro(sensor=None), "metric and a sensor_id"), ("psi", "metric and a sensor_id")):
    d = merged({"id": "p", "readouts": {"air": [bad, ro("pm10_24h")]}})
    assert metrics(d, "air") == [("pm10_24h", "nea-psi")], (why, metrics(d, "air"))
    assert any(why in m for m in logs), (why, logs)
print("  a malformed readout is left out alone; the pack's other readouts and the issue stand")

first = FILES["coast"]["readouts"][0]
d = merged({"id": "p", "readouts": {"coast": [ro(first["metric"], first["sensor_id"], unit="m")]}})
assert metrics(d, "coast") == own and any("already shown" in m for m in logs), logs
d = merged({"id": "a", "readouts": {"air": [ro()]}}, {"id": "b", "readouts": {"air": [ro()]}})
assert metrics(d, "air") == [("psi", "nea-psi")]
print("  the same sensor and metric is never shown twice, from the issue or from another pack")

for shape in (["psi"], "psi", {"air": "psi"}):
    d = merged({"id": "p", "readouts": shape})
    assert d == FILES, shape
assert merged({"id": "p"}, {"id": "q", "readouts": None}) == FILES
print("  readouts that are not a mapping of lists are ignored, and a pack without them changes nothing")

bad = {"id": "p", "readouts": {"noise": [ro()]}}
merged(bad); I.pack_readouts(copy.deepcopy(FILES), [bad]); I.pack_readouts(copy.deepcopy(FILES), [bad])
assert sum("'noise'" in m for m in logs) == 1, logs
print("  a pack's mistake is logged once, not on every /issues request")

# ---------------------------------------------------------------- load(), from a real packs folder
owner = tmp / "packs" / "air-owner"                                   # the pack that ships the air issue
owner.mkdir(parents=True)
(owner / "pack.yaml").write_text("id: air-owner\nname: air\ndomain: air\n")
shutil.copy(ROOT / "packs" / "air-quality" / "issue.yml", owner / "issue.yml")
pk = tmp / "packs" / "sg-test"
pk.mkdir(parents=True)
(pk / "pack.yaml").write_text("id: sg-test\nname: test\ndomain: air\nreadouts:\n  air:\n"
                              "    - { metric: psi, sensor_id: nea-psi, unit: PSI, dp: 0, label: { en: NEA PSI, id: PSI NEA, es: PSI de NEA } }\n")
assert metrics(I.load(), "air") == [("psi", "nea-psi")], metrics(I.load(), "air")
print("  load() merges what an enabled pack's pack.yaml declares")
os.environ["PACKS_ENABLED"] = "air-owner"
assert "readouts" not in I.load()["air"]
os.environ["PACKS_ENABLED"] = "some-other-pack"
assert "air" not in I.load(), "an issue is its pack's: with the pack off, the node has no such issue"
os.environ.pop("PACKS_ENABLED")
print("  and a pack PACKS_ENABLED leaves out adds nothing; the issue goes with the pack that ships it")
assert "readouts" not in I.load(ISSUES)["air"]
print("  load(<a directory>) is the files alone, for validators and tests")

# ---------------------------------------------------------------- the engine: a number only when the row exists
decl = I.load()["air"]
row = {"sensor_id": "nea-psi", "metric": "psi", "value": 61.4, "name": "NEA PSI (east region)", "kind": "model",
       "ts": "2026-10-02T06:00:00+00:00"}
out = engine._readouts(decl, [row])
assert len(out) == 1 and out[0]["value"] == 61 and out[0]["provenance"] == "model" and out[0]["source"] == row["name"], out
assert out[0]["_text"]["en"] == "NEA PSI 61 PSI", out[0]["_text"]
assert engine._readouts(decl, []) == []
print("  the engine shows it with the node's own row, and shows nothing without one")

# ---------------------------------------------------------------- today's nodes: nothing changes
os.environ["PACKS_DIR"] = str(ROOT / "packs")
import importlib  # noqa: E402
import packs      # noqa: E402
importlib.reload(packs)
# One shipped pack declares readouts since 15 Oct 2026: surface-heat, on heat, from its own satellite sensors. Every
# other issue is exactly its file, and heat gains only rows that show nothing until that pack has written a pass,
# which a node without PACKS_ALLOW_CODE=1 never does. A second pack declaring readouts must be added here on purpose.
assert [m["id"] for m in packs.manifests() if m.get("readouts")] == ["surface-heat"], "a new shipped pack declares readouts"
shipped = I.load()
assert all(shipped[k].pop("pack") for k in shipped), "a pack's issue knows the pack that ships it (issues.owners)"
assert {k: v for k, v in shipped.items() if k != "heat"} == {k: v for k, v in FILES.items() if k != "heat"}
own = FILES["heat"].get("readouts") or []
added = shipped["heat"]["readouts"][len(own):]
assert shipped["heat"]["readouts"][:len(own)] == own and {r["sensor_id"] for r in added} == {"surface-cell", "surface-modis"}
assert engine._readouts({"readouts": added}, []) == [], "no pass written, nothing shown"
print("pack readouts: added after the issue's own, refused when malformed, never twice, never invented; only surface-heat adds any")
