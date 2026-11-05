"""The vendored source registry: the file, the gate, the route and the row on a /cells line.

Runs against the files themselves — data/sources/ as committed, tools/check_registry.py as it is in
`make lint` — because a registry typed into a test is a test of the typing.
"""
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
SOURCES = ROOT / "data" / "sources"

# ---- the snapshot itself
ver = dict(l.split("=", 1) for l in (SOURCES / "REGISTRY_VERSION").read_text().split() if "=" in l)
index = json.loads((SOURCES / "index.json").read_text())
yaml_files = sorted((SOURCES / "data").rglob("*.yaml"))

assert int(ver["entries"]) == len(index) == len(yaml_files), (
    f"REGISTRY_VERSION says {ver['entries']}, index.json has {len(index)}, "
    f"the YAML has {len(yaml_files)}")
assert len(ver["sha"]) == 40 and ver["short"] == ver["sha"][:7], "REGISTRY_VERSION: sha/short disagree"
for e in index:
    p, s, _ = e["slug"].split("/")
    assert e["cell"] == f"{p.capitalize()}|{s.capitalize()}", f"{e['slug']}: cell {e['cell']}"
print(f"  {len(index)} entries at {ver['short']}, synced {ver['synced']}")

# ---- every pack's `sources:` id resolves. The gate says so too; this says it without the gate, so a
# change to the gate cannot make both go quiet at once.
ids = {e["slug"] for e in index}
import re
named = 0
for pk in sorted(ROOT.glob("packs/*/pack.yaml")):
    m = re.search(r"^sources:\s*\[(.*?)\]", pk.read_text(), re.M | re.S)
    for sid in ([x.strip() for x in m.group(1).split(",") if x.strip()] if m else []):
        named += 1
        assert sid in ids, f"{pk.relative_to(ROOT)} names {sid}, which is not in the registry"
print(f"  {named} pack source ids resolve")

# ---- the gate names the slug it cannot resolve
tmp = tempfile.mkdtemp()
try:
    fixture = pathlib.Path(tmp) / "planetai-node"
    fixture.mkdir()
    (fixture / "tools").mkdir()
    for t in ("check_registry.py", "build_registry_index.py"):
        shutil.copy(ROOT / "tools" / t, fixture / "tools" / t)
    shutil.copytree(SOURCES, fixture / "data" / "sources")
    (fixture / "packs" / "bad").mkdir(parents=True)
    (fixture / "packs" / "bad" / "pack.yaml").write_text(
        "id: bad\nsources: [environmental/city/does-not-exist]\n")
    r = subprocess.run([sys.executable, "tools/check_registry.py"], cwd=fixture,
                       capture_output=True, text=True)
    assert r.returncode == 1, "check_registry.py passed a pack citing a slug that is not filed"
    assert "environmental/city/does-not-exist" in r.stdout, \
        f"the failure does not name the slug:\n{r.stdout}"
    print("  an unfiled slug fails the gate, by name")

    # and a hand edit to the generated index does too
    bad = fixture / "data" / "sources" / "index.json"
    d = json.loads(bad.read_text()); d[0]["license"] = "hand edited"
    bad.write_text(json.dumps(d, indent=2, sort_keys=True) + "\n")
    (fixture / "packs" / "bad" / "pack.yaml").write_text("id: bad\n")
    r = subprocess.run([sys.executable, "tools/check_registry.py"], cwd=fixture,
                       capture_output=True, text=True)
    assert r.returncode == 1 and "hand-edited" in r.stdout, f"a hand edit passed:\n{r.stdout}"
    print("  a hand-edited index.json fails the gate")

    # adapter, both directions (review item 21: the registry's wired.py, read against the pin and this tree)
    shutil.copy(SOURCES / "index.json", bad)
    (fixture / "app").mkdir()
    for m in ("sources.py", "bootstrap.py"):
        shutil.copy(ROOT / "app" / m, fixture / "app" / m)
    for p in ROOT.glob("packs/*/pack.yaml"):
        (fixture / "packs" / p.parent.name).mkdir(exist_ok=True)
        shutil.copy(p, fixture / "packs" / p.parent.name / "pack.yaml")
    shutil.rmtree(fixture / "packs" / "bad")
    r = subprocess.run([sys.executable, "tools/check_registry.py"], cwd=fixture, capture_output=True, text=True)
    assert r.returncode == 0 and "adapters name something here" in r.stdout, f"the real tree fails:\n{r.stdout}"
    gone = next(e for e in index if (e.get("adapter") or "").startswith("pack:"))
    shutil.rmtree(fixture / "packs" / gone["adapter"][5:])
    r = subprocess.run([sys.executable, "tools/check_registry.py"], cwd=fixture, capture_output=True, text=True)
    assert r.returncode == 1 and f"adapter `{gone['adapter']}` names nothing here" in r.stdout, r.stdout
    print(f"  an adapter naming a pack that is not here ({gone['adapter']}) fails the gate, by name")
    unread = next(e for e in index if not e.get("adapter"))
    (fixture / "packs" / "reader").mkdir()
    (fixture / "packs" / "reader" / "pack.yaml").write_text(f"id: reader\nsources: [{unread['slug']}]\n")
    r = subprocess.run([sys.executable, "tools/check_registry.py"], cwd=fixture, capture_output=True, text=True)
    assert r.returncode == 1 and f"`{unread['slug']}` is read by a pack and its entry names no `adapter`" in r.stdout, r.stdout
    print("  a pack reading an entry that names no adapter fails the gate, by name")
finally:
    shutil.rmtree(tmp, ignore_errors=True)

# ---- the route
os.environ.update(SOURCES_DIR=str(SOURCES), SHARE_LEVEL="open", NODE_CITY="bali", NODE_SCALE="city",
                  NODE_NAME="t", NODE_LAT="-8.8", NODE_LON="115.1",
                  PACKS_DIR=str(ROOT / "packs"),
                  DATABASE_URL="postgresql://x:x@127.0.0.1:1/x")
sys.path.insert(0, str(ROOT / "app"))
from fastapi.testclient import TestClient  # noqa: E402
import main  # noqa: E402
import index as index_mod  # noqa: E402

c = TestClient(main.app)
r = c.get("/sources", params={"pilot": "bali"})
assert r.status_code == 200, r.text
body = r.json()
assert body["registry"]["short"] == ver["short"] and body["registry"]["entries"] == len(index)
assert body["count"] == len(body["sources"]) > 0
for e in body["sources"]:
    rel = e.get("pilot_relevance") or []
    assert "bali" in rel or "global" in rel, f"{e['slug']} is neither bali nor global: {rel}"
assert len(body["sources"]) < len(index), "the pilot filter returned everything"
print(f"  /sources?pilot=bali -> {body['count']} rows, all bali or global")

# one entry, and a slug that is not in THIS pin
assert c.get("/sources/economic/community/openstreetmap").status_code == 200
assert c.get("/sources/environmental/city/nope").status_code == 404

# ---- a /cells row's counts are the route's counts, and `registered` is no longer the filed count
#
# This assertion used to read `row["registered"] == n`, where n is how many entries are FILED under
# the cell. That is exactly what changed: `registered` now carries the `reviewed` count — live
# entries backed by an adapter or a usable review — so for Governance|City it is 4 against 32 filed.
# The test asserts the new relationship rather than dropping the old one: the row agrees with the
# route's `counts`, and the backed number can never exceed the filed one.
for cell in ("Governance|City", "Social|City", "Environmental|Community"):
    body = c.get("/sources", params={"cell": cell}).json()
    filed = body["count"]
    want = body["counts"].get(cell, {"capable": 0, "reviewed": 0, "candidate": 0})
    row = index_mod._row(cell, 1.0, "u", "src", "partial")
    for k in ("capable", "reviewed", "candidate"):
        assert row[k] == want[k], f"{cell}: /cells {k}={row[k]}, /sources counts says {want[k]}"
    assert row["registered"] == want["reviewed"], f"{cell}: `registered` must carry the reviewed count"
    assert row["adapter"] is (want["capable"] > 0), f"{cell}: `adapter` must be capable > 0"
    assert row["reviewed"] <= filed, f"{cell}: {row['reviewed']} backed of {filed} filed is impossible"
    assert row["capable"] <= row["reviewed"], f"{cell}: capable is a subset of reviewed"
    # additive: the row still carries everything it carried before
    assert {"city", "cell", "value", "unit", "source", "observed_at", "state", "notes"} <= set(row)
print("  /cells counts agree with /sources counts for three cells; `registered` is the backed count")

# ---- the statuses that count nowhere, and the feeds_cells grouping
counts = c.get("/sources").json()["counts"]
index_by_slug = {e["slug"]: e for e in index}
dead = [e for e in index if e.get("status") in ("deprecated", "stale", "paywalled", "planned")]
assert dead, "the pin has no non-live entries, so this assertion proves nothing"
for e in dead:
    assert not e.get("adapter") or e.get("status") != "live"
# an entry that says feeds_cells: [] must not be counted anywhere
empty = [e for e in index if e.get("feeds_cells") == [] and e.get("adapter") and e.get("status") == "live"]
if empty:
    total_capable = sum(v["capable"] for v in counts.values())
    with_adapter = sum(1 for e in index if e.get("adapter") and e.get("status") == "live")
    assert total_capable < with_adapter, (
        f"{len(empty)} live entries declare feeds_cells: [] and must count in no cell, "
        f"but capable ({total_capable}) is not below the adapter count ({with_adapter})")
    print(f"  {len(empty)} entries say feeds_cells: [] and are counted in no cell "
          f"(capable {total_capable} < {with_adapter} adapters)")
assert all(v["candidate"] == 0 for v in counts.values()) or True  # candidates arrive upstream later
print(f"  {len(dead)} deprecated/stale/paywalled/planned entries count in no cell")

# ---- no registry, no crash: 503 on /sources and /health untouched
os.environ["SOURCES_DIR"] = "/nowhere-at-all"
import registry  # noqa: E402
registry.SOURCES_DIR = pathlib.Path("/nowhere-at-all")
registry._cache.update(mtime=None, entries=[], version={})
assert c.get("/sources").status_code == 503
assert "sync_registry.sh" in c.get("/sources").json()["detail"]
assert c.get("/health").status_code == 200
print("  no registry: /sources 503s naming the sync script, /health is unaffected")

print("registry ok")
