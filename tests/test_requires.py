"""A pack's `requires: { node: ... }` is enforced (docs/decisions/2026-10-01-packs.md, point 6).

The rule in app/requires.py, then the loader in app/packs.py refusing a pack whole and saying so once, then two
guards: app/requires.py stays Python 3.9 (the CLI runs it on the node's own Python), and no shipped pack asks for a
node newer than the latest release in CHANGELOG.md, which would make a release refuse its own pack.
Run: PYTHONPATH=app python3 tests/test_requires.py
"""
import ast
import logging
import os
import re
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
tmp = Path(tempfile.mkdtemp())
os.environ["PACKS_DIR"] = str(tmp / "packs")
os.environ.setdefault("DATABASE_URL", "postgresql://x:x@127.0.0.1:1/x")
os.environ.pop("PACKS_ENABLED", None)

import requires as Q  # noqa: E402
import packs          # noqa: E402

# ---------------------------------------------------------------- the rule
assert Q.release_of("v0.75.8") == (0, 75, 8) and Q.release_of("v0.75.8-14-gafc298a") == (0, 75, 8)
assert Q.release_of("v0.76") == (0, 76, 0) and Q.release_of("dev") is None and Q.release_of("") is None
assert Q.check(">=0.40.0", "v0.75.8") is None
assert Q.check(">=0.75.8", "v0.75.8") is None and Q.check("==0.75.8", "v0.75.8-3-gabc") is None
assert Q.check(">=0.40.0, <0.90.0", "v0.75.8") is None and Q.check("> v0.75.7", "v0.75.8") is None
why = Q.check(">=0.80.0", "v0.75.8")
assert why == "it needs a node >=0.80.0 and this node is v0.75.8; planetai update first", why
assert "update" not in Q.check("<0.70.0", "v0.75.8"), "a node that is too new is not told to update"
assert "update" not in Q.check("==0.70.0", "v0.75.8") and "update" in Q.check("==0.80.0", "v0.75.8")
assert Q.check(">=0.40.0, <0.70.0", "v0.75.8") is not None
print("  >= > <= < == and comma-joined clauses; a checkout ahead of a release is at that release")
for unknown in ("dev", "", "?", "afc298a"):
    assert Q.check(">=99.0.0", unknown) is None
print("  a node that cannot say its release loads the pack rather than refusing everything")
assert Q.check(None, "v0.75.8") is None and Q.check("", "v0.75.8") is None
for bad in ("0.40.0", ">=forty", "latest", ">=0.40.0,"):
    assert "not a version range" in (Q.check(bad, "v0.75.8") or ""), bad
print("  no requirement is no requirement; a spec that is not a range is refused, and says why")

# ---------------------------------------------------------------- the loader
logs = []
logging.getLogger("planetai.packs").addHandler(type("H", (logging.Handler,), {"emit": lambda self, r: logs.append(r.getMessage())})())
for pid, spec, rule in (("old-ok", ">=0.40.0", "ok_rule"), ("too-new", ">=99.0.0", "future_rule"), ("no-spec", None, "plain_rule")):
    d = tmp / "packs" / pid
    d.mkdir(parents=True)
    (d / "pack.yaml").write_text(f"id: {pid}\nname: {pid}\ndomain: air\n" + (f'requires: {{ node: "{spec}" }}\n' if spec else ""))
    (d / "rules.yml").write_text(f"- id: {rule}\n  level: info\n  sql: SELECT 1 AS x\n  message: {{ en: x, id: x, es: x }}\n")

os.environ["NODE_VERSION"] = "v0.75.8"
ids = [m["id"] for m in packs.manifests()]
assert ids == ["no-spec", "old-ok"], ids
assert "too-new" in packs.REFUSED and "planetai update first" in packs.REFUSED["too-new"], packs.REFUSED
assert not [r for r in packs.alerts() if r["id"].startswith("too-new/")], "a refused pack's rules must not run"
assert [r["id"] for r in packs.alerts() if r["id"].startswith("old-ok/")] == ["old-ok/ok_rule"]
print("  a pack for a newer node is refused whole: not in /packs, and its rules do not run")
n = sum("too-new" in m for m in logs)
packs.manifests(); packs.alerts()
assert n == 1 and sum("too-new" in m for m in logs) == 1, logs
print("  the log says it once, not on every poll")
os.environ["NODE_VERSION"] = "v99.1.0"
assert [m["id"] for m in packs.manifests()] == ["no-spec", "old-ok", "too-new"] and "too-new" not in packs.REFUSED
os.environ["NODE_VERSION"] = "dev"
assert len(packs.manifests()) == 3
print("  after an update it loads, and a dev checkout loads everything")

# ---------------------------------------------------------------- guards
ast.parse((ROOT / "app" / "requires.py").read_text(), feature_version=(3, 9))
print("  app/requires.py parses as Python 3.9, so the CLI can run it on a node")
latest = re.search(r"^## (v\d+\.\d+\.\d+)", (ROOT / "CHANGELOG.md").read_text(), re.M).group(1)
import yaml  # noqa: E402
late = {}
for f in sorted((ROOT / "packs").glob("*/pack.yaml")):
    spec = ((yaml.safe_load(f.read_text()) or {}).get("requires") or {}).get("node")
    why = Q.check(spec, latest)
    if why:
        late[f.parent.name] = why
assert not late, f"shipped packs the latest release ({latest}) would refuse: {late}"
print(f"requires: enforced at load, said once, refused whole; every shipped pack loads on {latest}")
