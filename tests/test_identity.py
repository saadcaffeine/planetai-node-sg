"""A node is a key, not a string (docs/SPEC_identity.md): the ID, the signature on a push, and the parent's pin.

The child's push is app/main.py::_post_parent lifted whole by AST (importing main starts a second MQTT client), posting
into a stub httpx; what it posted goes into app/identity.py::admit on a cursor that keeps the children table in a dict.
So the bytes the parent checks are the bytes the child signed, not a copy typed in here.

    PYTHONPATH=app python3 tests/test_identity.py
"""
import ast
import base64
import hashlib
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "app"))
from fastapi import HTTPException  # noqa: E402

import identity  # noqa: E402

A, B, C, D, E = "11" * 32, "22" * 32, "33" * 32, "44" * 32, "55" * 32


def as_node(seed):
    os.environ["NODE_KEY"] = seed
    identity._private.cache_clear()


def refused(fn, code, *words):
    try:
        fn()
    except HTTPException as e:
        assert e.status_code == code, (e.status_code, e.detail)
        for w in words:
            assert w in e.detail, (w, e.detail)
        return e.detail
    raise AssertionError(f"not refused, expected {code}")


# 1 · the ID: 16 base32 characters of sha256(public key), the same with the standard library alone
as_node(A)
key, nid = identity.public_key(), identity.node_id()
assert len(base64.b64decode(key)) == 32
assert nid == base64.b32encode(hashlib.sha256(base64.b64decode(key)).digest()).decode().lower()[:16]
assert len(nid) == 16 and set(nid) <= set("abcdefghijklmnopqrstuvwxyz234567"), nid
as_node(B)
assert identity.node_id() != nid, "two keys, two IDs"
as_node("")
assert identity.node_id() is None and identity.headers("/aggregates", b"{}") == {}, "no NODE_KEY: no ID, unsigned"
as_node("not hex")
assert identity.node_id() is None, "a malformed NODE_KEY is no key, not a crash"
print("  ok  the ID is a short hash of the key, and a node without NODE_KEY pushes unsigned")


# 2 · sign and verify
def signed(seed, route, body, ts=None):
    as_node(seed)
    real = time.time
    if ts is not None:
        identity.time.time = lambda: ts
    try:
        return {k.lower(): v for k, v in identity.headers(route, body).items()}
    finally:
        identity.time.time = real


body = b'{"schema": "aggregates-v0", "node": "mahon1", "rows": []}'
h = signed(A, "/aggregates", body)
as_node("")                                  # the parent's own key plays no part in checking a child's
assert identity.verify("/aggregates", body, h) == (nid, key)
assert identity.verify("/aggregates", body, {}) is None, "no headers: an unsigned push, for admit to decide"
refused(lambda: identity.verify("/aggregates", body[:-1] + b" }", h), 401, "does not verify")
refused(lambda: identity.verify("/events", body, h), 401, "does not verify")
other = signed(B, "/aggregates", body)
refused(lambda: identity.verify("/aggregates", body, {**h, "x-node-signature": other["x-node-signature"]}), 401)
refused(lambda: identity.verify("/aggregates", body, {**other, "x-node-id": nid}), 401, "does not verify")
refused(lambda: identity.verify("/aggregates", body, {**h, "x-node-signature": "%%%"}), 401)
refused(lambda: identity.verify("/aggregates", body, signed(A, "/aggregates", body, time.time() - 660)), 401, "clock")
refused(lambda: identity.verify("/aggregates", body, signed(A, "/aggregates", body, time.time() + 660)), 401, "clock")
identity.verify("/aggregates", body, signed(A, "/aggregates", body, time.time() - 540))
print("  ok  a changed byte, another route, another key, a forged ID and a clock 11 minutes out are refused")


# 3 · the pin, on a cursor that keeps the children table in a dict
class Cursor:
    def __init__(self): self.rows, self.out, self.rowcount = {}, [], 0

    def execute(self, sql, args=()):
        sql = " ".join(sql.split())
        if sql.startswith("SELECT name, node_id, public_key, first_seen FROM children WHERE name = %s OR node_id = %s"):
            self.out = [dict(r) for r in self.rows.values() if r["name"] == args[0] or (args[1] and r["node_id"] == args[1])]
        elif sql.startswith("INSERT INTO children (name) VALUES (%s) ON CONFLICT (name) DO UPDATE SET last_seen = now()"):
            self.rows.setdefault(args[0], {"name": args[0], "node_id": None, "public_key": None,
                                           "first_seen": datetime(2026, 11, 1, tzinfo=timezone.utc)})
        elif sql.startswith("INSERT INTO children (name, node_id, public_key) VALUES (%s, %s, %s) ON CONFLICT (name) DO UPDATE"):
            assert "WHERE children.node_id IS NULL OR children.public_key = EXCLUDED.public_key" in sql
            r = self.rows.get(args[0])
            self.rowcount = 0 if r and r["node_id"] and r["public_key"] != args[2] else 1
            if self.rowcount:
                first = r["first_seen"] if r else datetime(2026, 11, 5, tzinfo=timezone.utc)
                self.rows[args[0]] = {"name": args[0], "node_id": args[1], "public_key": args[2], "first_seen": first}
        else:
            raise AssertionError("admit ran SQL this fake does not know: " + sql)

    def fetchall(self): return self.out


cur = Cursor()
admit = lambda name, h, listed=None, b=body: identity.admit(cur, name, "/aggregates", b, h, listed)  # noqa: E731

assert admit("old-home", {}) is None and cur.rows["old-home"]["node_id"] is None, "an old child is recorded, unsigned"
c = signed(C, "/aggregates", body)
assert admit("old-home", c) == c["x-node-id"] and cur.rows["old-home"]["node_id"] == c["x-node-id"], "it updates: pinned"
refused(lambda: admit("old-home", {}), 401, "old-home signs its pushes here since 2026-11-01")

assert admit("mahon1", h) == nid and cur.rows["mahon1"]["node_id"] == nid, "first contact pins"
assert admit("mahon1", h) == nid, "the same key again is accepted"
msg = refused(lambda: admit("mahon1", signed(B, "/aggregates", body)), 409, "mahon1 is pinned here to node " + nid,
              "planetai children forget mahon1")
assert identity.id_of(other["x-node-key"]) in msg, "the sentence names both IDs"
refused(lambda: admit("mahon1", {}), 401, "unsigned push under its name is refused")
refused(lambda: admit("mahon2", h), 409, f"node {nid} is pinned here as mahon1", "calls itself mahon2")

cur.rows.pop("mahon1")                       # planetai children forget mahon1
assert admit("mahon1", signed(B, "/aggregates", body)), "after forget, the next push pins its new key"

listed = [{"name": "bayu", "id": nid}]
refused(lambda: admit("bayu", signed(E, "/aggregates", body), listed), 409, "registry.json lists bayu as node " + nid,
        "planetai hello")
assert admit("bayu", signed(A, "/aggregates", body), listed) == nid, "the listed key pins"
print("  ok  trust on first use: pinned, a changed key and a renamed key refused with a sentence, the registry outranks it")


# 4 · the child posts the bytes it signed: _post_parent lifted from main.py, into a stub httpx, through admit
class Posted:
    status_code = 200


class Httpx:
    HTTPError = OSError
    sent = []

    def post(self, url, content=None, headers=None, timeout=None, json=None):
        assert json is None, "a signed push posts content=, never json=: json= re-serialises after signing"
        self.sent.append((url, content, headers))
        return Posted()


tree = ast.parse((ROOT / "app" / "main.py").read_text())
fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "_post_parent")
identity.httpx = Httpx()                     # identity.post is the one place a push is posted
ns = {"identity": identity, "httpx": identity.httpx, "PARENT": lambda: "http://parent:8080",
      "PARENT_TOKEN": lambda: "tok", "log": None}
exec(compile(ast.Module([fn], []), "main.py", "exec"), ns)
as_node(D)
assert ns["_post_parent"]("/events", {"schema": "events-v0", "node": "walk", "rows": [{"alert_id": "1"}]}).status_code == 200
url, sent, hdrs = Httpx.sent[-1]
assert url == "http://parent:8080/events" and hdrs["Authorization"] == "Bearer tok" and hdrs["X-Node-Id"]
as_node("")
assert identity.admit(cur, "walk", "/events", sent, {k.lower(): v for k, v in hdrs.items()}) == hdrs["X-Node-Id"]
for name in ("receive_aggregates", "receive_events"):
    src = ast.get_source_segment((ROOT / "app" / "main.py").read_text(),
                                 next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name))
    route = "/aggregates" if name == "receive_aggregates" else "/events"
    assert f'_admit(cur, body, "{route}", raw, request)' in src and "Depends(_raw_body)" in src, name
    assert src.index("_bearer_ok(authorization, AGG_TOKEN())") < src.index("_admit("), f"{name}: the token is checked first"
    assert 'body.get("node"' not in src, f"{name} reads the child's name only through _admit"
print("  ok  the child signs the bytes it posts, and both receive routes admit before they write")


# 5 · a shared map (app/maps.py): pushed through identity.post, admitted before it is written, owned by the node's ID
os.environ.setdefault("DATABASE_URL", "postgresql://unused/never-connected")   # db.py opens nothing at import
import maps  # noqa: E402

msrc = (ROOT / "app" / "maps.py").read_text()
mtree = ast.parse(msrc)
seg = lambda name: ast.get_source_segment(msrc, next(n for n in mtree.body if isinstance(n, ast.FunctionDef) and n.name == name))  # noqa: E731
assert 'identity.post(PARENT(), "/place/maps/received"' in seg("push_maps") and "httpx.post" not in seg("push_maps")
rcv = seg("map_received")
assert "Depends(_raw_body)" in rcv and rcv.index("_bearer_ok(authorization, AGG_TOKEN())") < rcv.index("identity.admit(cur, child,")
assert rcv.index("identity.admit(") < rcv.index("DELETE FROM place_maps"), "a delete is admitted too"
as_node(A)
assert maps.feature_collection({"name": "m", "owner": "Ana"}, [], "bayu", upstream=True)["owner"] == nid
assert maps.feature_collection({"name": "m", "owner": "Ana"}, [], "bayu")["owner"] == "Ana", "at home, the household's"
as_node("")
assert maps.feature_collection({"name": "m"}, [], "bayu", upstream=True)["owner"] == "bayu", "no key: the node's name"
identity.LISTED = [{"name": "listed-one", "id": nid}]
refused(lambda: identity.admit(Cursor(), "listed-one", "/place/maps/received", body,
                               signed(E, "/place/maps/received", body)), 409, "registry.json lists listed-one")
identity.LISTED = []
print("  ok  a shared map is signed, admitted before it is written or deleted, owned by the node's ID; the registry holds")


# 6 · every registry.json entry that carries a key carries the ID that key hashes to
for n in json.loads((ROOT / "registry.json").read_text())["nodes"]:
    if n.get("key") or n.get("id"):
        assert n.get("key") and identity.id_of(n["key"]) == n.get("id"), f"registry.json: {n['name']}'s id is not its key's"
print("  ok  registry.json: every listed id is its key's hash")
sys.exit(0)
