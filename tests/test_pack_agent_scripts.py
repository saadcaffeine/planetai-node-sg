"""A wild pack's scripts reach an agent only when its pack.yaml lists them under `agent_scripts:` (#168).

`run_pack_script` ran any pack's top-level script for an admin-tier agent and handed back its output. A wild camera
pack keeps motion off the readings on purpose, and its `events` script printed a year of it to whoever asked. Core
packs keep every script reachable, as before; a wild pack (`.wild` beside pack.yaml) offers only what it lists.
Run: PYTHONPATH=app python3 tests/test_pack_agent_scripts.py
"""
import os
import tempfile
from pathlib import Path

d = Path(tempfile.mkdtemp())
os.environ.update(PACKS_DIR=str(d), DATABASE_URL="postgresql://x:x@127.0.0.1:1/x")

import time  # noqa: E402
import settings  # noqa: E402
ROWS = {"PACKS_ENABLED": ""}
settings._cache = {"at": time.time() + 1e9, "rows": ROWS}
import agent  # noqa: E402
import packs  # noqa: E402


def pack(name, yaml_, scripts, wild=False):
    (d / name).mkdir()
    (d / name / "pack.yaml").write_text(yaml_)
    for s in scripts:
        (d / name / f"{s}.py").write_text(f"print('{name} {s} ran')\n")
    if wild:
        (d / name / ".wild").write_text("source=someone/cam\ncommit=abc\nadded=2026-10-03\n")


pack("heat", "id: heat\n", ["verify", "adapter", "routes"])   # routes.py is mounted, never run (24 Oct 2026)
pack("cam", "id: cam\nagent_scripts: [status]\n", ["status", "events", "snapshot", "adapter"], wild=True)
pack("rain", "id: rain\n", ["verify"], wild=True)
pack("odd", "id: odd\nagent_scripts: verify\n", ["verify"], wild=True)
pack("broken", "id: [broken\n", ["verify"], wild=True)

got = packs.agent_scripts()
assert got == ["cam/status", "heat/verify"], got
print("  core scripts are all reachable; a wild pack offers only what it lists, and an adapter or routes.py never")

r = agent.run_pack_script("heat", "verify")
assert r["exit"] == 0 and r["stdout"].strip() == "heat verify ran", r
r = agent.run_pack_script("cam", "status")
assert r["exit"] == 0 and r["stdout"].strip() == "cam status ran", r
print("  a core script and a listed wild script run as before")

for p, s in (("cam", "events"), ("cam", "snapshot"), ("rain", "verify"), ("odd", "verify"), ("broken", "verify")):
    r = agent.run_pack_script(p, s)
    assert "exit" not in r and "stdout" not in r, (p, s, r)
    assert r["error"].startswith(f"{p}/{s} is in a wild pack") and f"planetai run {p} {s}" in r["error"], r
    assert r["available"] == got, r
print("  an unlisted wild script is refused with where it does run, and nothing is run; a list that is not a list,"
      " or a pack.yaml that does not parse, lists nothing")

r = agent.run_pack_script("cam", "../heat/verify")
assert r["error"] == "no such script: cam/verify" and "exit" not in r, r
r = agent.run_pack_script("nope", "x")
assert r["error"] == "no such script: nope/x" and r["available"] == got, r
r = agent.run_pack_script("heat", "adapter")
assert r["error"] == "no such script: heat/adapter", r
print("  a path cannot climb out of a pack, a missing script says so, and an adapter is not a script")

# ---- a pack this node does not load runs nothing (review 21 Oct, loader fixes)
# agent_scripts() and module() globbed PACKS_DIR, so a pack left out of PACKS_ENABLED, or refused by its
# `requires:`, still had scripts an agent could run and a module the report imported.
pack("later", "id: later\nrequires: { node: \">=99.0.0\" }\n", ["verify", "adapter"])
(d / "heat" / "adapter.py").write_text("def fetch(hc): return [], []\nX = 1\n")
os.environ["NODE_VERSION"] = "v0.83.0"          # requires: is checked against the running node's version
assert "later/verify" not in packs.agent_scripts() and packs.module("later") is None, "requires: refused it"
r = agent.run_pack_script("later", "verify")
assert "exit" not in r and "not loaded on this node" in r["error"], r
ROWS["PACKS_ENABLED"] = "cam"
assert packs.agent_scripts() == ["cam/status"], packs.agent_scripts()
assert packs.module("heat") is None and packs.module("cam", "status") is not None
r = agent.run_pack_script("heat", "verify")
assert "exit" not in r and r["error"].startswith("heat is not loaded on this node"), r
ROWS["PACKS_ENABLED"] = ""
assert packs.module("heat").X == 1, "loaded again when the list is empty"
print("  a pack left out of PACKS_ENABLED, or refused by requires:, offers no script and no module")

# kind: code whenever the pack ships Python, as nearby and season do with scripts and no adapter
kinds = {m["id"]: m["kind"] for m in packs.manifests()}
assert kinds["rain"] == "code" and kinds["heat"] == "code", kinds
pack("words", "id: words\n", [])
assert {m["id"]: m["kind"] for m in packs.manifests()}["words"] == "data"
print("  a pack is code when it ships any Python, data when it ships none")
