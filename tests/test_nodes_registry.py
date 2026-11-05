"""The nodes the programme lists (docs/SPEC_hello.md step 1): the node reads registry.json on main, keeps only what a
page may see, and serves it at /nodes, open at every share level. UPDATE_CHECK=off reads nothing.

No import of main (it starts a second MQTT client): the functions are lifted whole by AST, as test_agent_buttons does.

    python3 tests/test_nodes_registry.py
"""
import ast
import json
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NAMES = {"REGISTRY_URL", "REGISTRY_EVERY", "REGISTRY_FIELDS", "listed_nodes", "check_registry", "nodes", "_SHARE_OFF"}


class Settings:
    v = {}
    def get(self, k, d=None): return self.v.get(k, d)


class Answer:
    def __init__(self, body, code=200): self.body, self.code = body, code
    def raise_for_status(self):
        if self.code >= 400: raise RuntimeError(self.code)
    def json(self): return json.loads(self.body)


class Client:
    def __init__(self): self.asked, self.answer = 0, None
    def get(self, url, timeout=None):
        self.asked += 1
        if isinstance(self.answer, Exception): raise self.answer
        return self.answer


class App:
    def get(self, *a, **k): return lambda f: f


ns = {"settings": Settings(), "state": {}, "hc": Client(), "time": time, "datetime": datetime, "timezone": timezone,
      "app": App(),
      "_packs": type("P", (), {"shared": staticmethod(lambda level="open": set())})()}   # auth.py adds the packs' paths
tree = ast.parse((ROOT / "app" / "main.py").read_text() + (ROOT / "app" / "auth.py").read_text())   # _SHARE_OFF is in auth.py
for node in tree.body:
    named = node.name if isinstance(node, ast.FunctionDef) else \
        next((t.id for t in getattr(node, "targets", []) if isinstance(t, ast.Name)), None)
    if named in NAMES:
        exec(compile(ast.Module([node], []), "main.py", "exec"), ns)
missing = NAMES - set(ns)
assert not missing, f"main.py no longer defines {missing}"

# the repo's own registry.json is what a node will read: it parses and every entry keeps its name
mine = ns["listed_nodes"](json.loads((ROOT / "registry.json").read_text()))
assert mine and all(n["name"] for n in mine), "registry.json lists at least one node"

raw = {"nodes": [
    {"name": "bayu-ungasan", "place": "Ungasan", "cell": "8895a4c843fffff", "lat": -8.816, "lon": 115.164,
     "contact": "someone@example.org", "sources": ["smartcitizen:1"], "scale": "community", "since": "2026-09"},
    {"name": "no-point", "place": "Somewhere"},
    "not a node", {"place": "no name"}]}
rows = ns["listed_nodes"](raw)
assert [r["name"] for r in rows] == ["bayu-ungasan", "no-point"], "a malformed entry is skipped, the rest kept"
assert rows[0]["ll"] == [115.2, -8.8], "another node's point is given to one decimal"
assert rows[1]["ll"] is None, "an entry with no point has none, not 0,0"
assert not any(k in r for r in rows for k in ("contact", "sources", "lat", "lon")), "contact and sources never reach a page"
assert ns["listed_nodes"]("[]") == [] and ns["listed_nodes"]({}) == [], "a file that is not the registry lists nothing"

hc, state, settings = ns["hc"], ns["state"], ns["settings"]
assert ns["nodes"]() == {"read": None, "from": ns["REGISTRY_URL"], "nodes": []}, "nothing read yet says so"

hc.answer = Answer(json.dumps(raw))
ns["check_registry"]()
first = ns["nodes"]()
assert hc.asked == 1 and first["read"] and len(first["nodes"]) == 2 and "error" not in first, "the first check reads"
ns["check_registry"]()
assert hc.asked == 1, "a second check inside REGISTRY_EVERY asks nothing"

# the second time is a different case: a failed read keeps the last good list and says why
state["registry"]["asked"] -= ns["REGISTRY_EVERY"]
hc.answer = ConnectionError("offline")
ns["check_registry"]()
after = ns["nodes"]()
assert hc.asked == 2 and after["nodes"] == first["nodes"] and after["read"] == first["read"], "a failed read keeps the list"
assert after["error"] == "ConnectionError", "and says why"
ns["check_registry"]()
assert hc.asked == 2, "after a failure it waits an hour, not a minute"

settings.v["UPDATE_CHECK"] = "off"
ns["check_registry"]()
assert hc.asked == 2 and ns["nodes"]()["nodes"] == [], "UPDATE_CHECK=off asks nothing and forgets the list"

assert "/nodes" in ns["_SHARE_OFF"][0], "/nodes is open at every share level"
print("nodes: registry.json read, trimmed to what a page may see, kept through a failed read, off with UPDATE_CHECK")
