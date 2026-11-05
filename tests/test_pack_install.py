"""Every pack listed, and a wild pack installed from the page (app/wild.py; docs/decisions/2026-10-27-pack-install-from-the-page.md).

GET /packs/all says, for every pack on disk and every pack on the wild list, whether it is installed, on and loaded,
and why not. GET /packs/preview and POST /packs/install answer the admin token only, at every share level. The
request the page writes holds an id and a commit and nothing else. A new pack on the list is said once, and the
node's first read of the list says nothing. The host's side (`packs pending`) is tests/test_packs_add.sh.

    PYTHONPATH=app python3 tests/test_pack_install.py
"""
import json
import os
import tempfile
import time
from pathlib import Path

T = Path(tempfile.mkdtemp())
os.environ.update(PACKS_DIR=str(T / "packs"), PACK_OUT=str(T / "out"), ADMIN_TOKEN="admin-tok", NODE_VERSION="v0.90.0",
                  NODE_LAT="-8.8", NODE_LON="115.1", DATABASE_URL="postgresql://unused/never-connected")

try:
    from fastapi.testclient import TestClient
except ImportError:
    print("pack install: request checks skipped (pip install -r app/requirements.txt)")
    raise SystemExit(0)


def pack(pid, yaml_text="", files=(), wild=None):
    d = T / "packs" / pid
    d.mkdir(parents=True)
    (d / "pack.yaml").write_text(f"id: {pid}\nname: {pid.title()}\n{yaml_text}")
    for f in files:
        (d / f).write_text("def fetch(hc): return [], []\n")
    if wild:
        (d / ".wild").write_text(f"source={wild}\ncommit={'a' * 40}\nadded=2026-10-27\n")


pack("heat")
pack("coder", files=["adapter.py"])                                  # a core code pack with no switch of its own
pack("tide", wild="fabcity/planetai-wild-packs/packs/tide")
pack("wcode", files=["hooks.py"], wild="someone/wcode")
pack("future", 'requires: { node: ">=99.0.0" }\n')

import settings  # noqa: E402
ROWS = {"PACKS_ENABLED": "heat,tide,wcode,future", "SHARE_LEVEL": "off", "PACKS_ALLOW_CODE": "0", "UPDATE_CHECK": "on"}
settings._cache = {"at": time.time() + 1e9, "rows": ROWS}

import main  # noqa: E402
import wild  # noqa: E402

SHA = "b" * 40
LIST = [{"id": "tide", "source": "fabcity/planetai-wild-packs/packs/tide", "status": "listed", "author": "Lucas"},
        {"id": "posi", "name": "Posidonia", "source": "fabcity/planetai-wild-packs/packs/posi", "author": "Lucas",
         "reads": "Sea temperature", "kind": "data", "status": "listed", "licence": "Apache-2.0", "tested_with": "v0.80"},
        {"id": "pinned", "source": "someone/pinned", "commit": "c" * 40, "status": "reviewed"},
        {"id": "heat", "source": "someone/heatclone", "status": "listed"}]
wild._LIST.update(at=time.time(), rows=LIST, error=None)


class Cur:
    told: set = set()

    def __enter__(self): return self
    def __exit__(self, *a): return False

    def execute(self, sql, args=()):
        self.last = None
        if "INSERT INTO release_notices" in sql:
            self.last = None if args[0] in Cur.told else (args[0],)
            Cur.told.add(args[0])
        elif "SELECT 1 FROM release_notices" in sql:
            self.last = (1,) if any(t.startswith("pack:") for t in Cur.told) else None
        elif "INSERT INTO actions" in sql:
            Cur.actions.append(args)

    actions: list = []
    def fetchone(self): return self.last
    def fetchall(self): return []


class Con:
    def __enter__(self): return self
    def __exit__(self, *a): return False
    def cursor(self): return Cur()


main.db = wild.db = lambda: Con()
c = TestClient(main.app)
H = {"Authorization": "Bearer admin-tok"}

# ---- the list: every pack, its state, and why
r = c.get("/packs/all", headers=H)
assert r.status_code == 200, r.text
P = {p["id"]: p for p in r.json()["packs"]}
assert set(P) == {"heat", "coder", "tide", "wcode", "future", "posi", "pinned"}, sorted(P)
assert P["heat"]["installed"] and P["heat"]["on"] and P["heat"]["loaded"] and P["heat"]["tier"] == "core", P["heat"]
assert P["coder"]["installed"] and not P["coder"]["on"] and P["coder"]["why"] == "switched off", P["coder"]
assert P["tide"]["tier"] == "wild" and P["tide"]["commit"] == "a" * 40 and P["tide"]["status"] == "listed", P["tide"]
assert P["wcode"]["on"] and not P["wcode"]["loaded"] and P["wcode"]["why"] == "a code pack, waiting for Allow code packs", P["wcode"]
assert P["wcode"]["status"] == "not on the list", P["wcode"]
assert P["future"]["on"] and not P["future"]["loaded"] and ">=99.0.0" in P["future"]["why"], P["future"]
assert not P["posi"]["installed"] and not P["posi"]["on"] and P["posi"]["reads"] == "Sea temperature", P["posi"]
assert "heat" in P and P["heat"]["tier"] == "core", "a list entry naming a core pack's id does not hide the core pack"
ROWS["PACKS_ALLOW_CODE"] = "1"
assert {p["id"]: p for p in c.get("/packs/all", headers=H).json()["packs"]}["wcode"]["loaded"], "Allow code packs runs it"
ROWS["PACKS_ALLOW_CODE"] = "0"
print("  /packs/all lists core, wild and listed packs, with installed, on, loaded and why")

ROWS["PACKS_ENABLED"] = ""
assert {p["id"]: p for p in c.get("/packs/all", headers=H).json()["packs"]}["coder"]["on"], "an empty list is every pack"
ROWS["PACKS_ENABLED"] = "heat,tide,wcode,future"

# the list unread: what is on disk, and it says so
wild._LIST.update(rows=None, error="ConnectError")
j = c.get("/packs/all", headers=H).json()
assert j["list"] == {"url": wild.WILD_INDEX, "read": False, "error": "ConnectError"} and "posi" not in {p["id"] for p in j["packs"]}, j["list"]
wild._LIST.update(rows=LIST, error=None)
print("  with the wild list unread, the disk's packs and a line saying so")

# ---- who may read and who may press
assert c.get("/packs/all").status_code == 403, "SHARE_LEVEL=off refuses the list to a screen with no token"
ROWS["SHARE_LEVEL"] = "open"
assert c.get("/packs/all").status_code == 200, "open lets the network read the list, as it reads /packs"
for method, path, body in (("get", "/packs/preview?id=posi", None), ("post", "/packs/install", {"id": "posi", "commit": SHA}),
                           ("get", "/packs/install", None)):
    r = getattr(c, method)(path, **({"json": body} if body else {}))
    assert r.status_code in (401, 403), (path, r.status_code, "a screen at SHARE_LEVEL=open without the token")
    r = getattr(c, method)(path, headers={"Authorization": "Bearer wrong"}, **({"json": body} if body else {}))
    assert r.status_code in (401, 403), (path, r.status_code, "a wrong token")
ROWS["SHARE_LEVEL"] = "off"
r = c.post("/packs/install", json={"id": "posi", "commit": SHA}, headers={**H, "X-Agent": "claude"})
assert r.status_code == 403 and "a person installs" in r.json()["detail"], r.text
assert not (T / "out" / "requests" / "pack-add.json").exists()
print("  preview and install answer the admin token only, at off and open alike, and never an agent")

# ---- the preview: read at the commit it would install, from pack.yaml, writing nothing
class Resp:
    def __init__(self, text): self.text = text
    def raise_for_status(self): pass


class Fake:
    urls: list = []
    def __enter__(self): return self
    def __exit__(self, *a): return False

    def get(self, url, headers=None):
        Fake.urls.append(url)
        if url == "https://api.github.com/repos/fabcity/planetai-wild-packs/commits/HEAD":
            return Resp(SHA)
        if url == f"https://raw.githubusercontent.com/fabcity/planetai-wild-packs/{SHA}/packs/posi/pack.yaml":
            return Resp('id: posi\nname: Posidonia\nauthor: Lucas Marangoni\nkind: code\nmetrics: [sst]\n'
                        'needs: An outbound connection to Copernicus.\npip: ["numpy==2.*"]\n'
                        'env:\n  - "# posi: the bay"\n  - "POSI_BAY="\nrequires: { node: ">=0.76" }\n')
        if url == f"https://raw.githubusercontent.com/someone/pinned/{'c' * 40}/pack.yaml":
            return Resp("id: pinned\n")
        raise AssertionError("unexpected fetch " + url)


wild._client = lambda: Fake()
v = c.get("/packs/preview?id=posi", headers=H).json()
assert v["commit"] == SHA and v["author"] == "Lucas Marangoni" and v["kind"] == "code" and v["pip"] == ["numpy==2.*"], v
assert v["settings"] == ["POSI_BAY"] and v["metrics"] == ["sst"] and "Copernicus" in v["needs"] and v["loads_here"] is None, v
assert v["code_url"] == f"https://github.com/fabcity/planetai-wild-packs/tree/{SHA}/packs/posi", v["code_url"]
assert v["source"] == "fabcity/planetai-wild-packs/packs/posi" and v["refused"] is None, v
Fake.urls.clear()
assert c.get("/packs/preview?id=pinned", headers=H).json()["commit"] == "c" * 40
assert not any("api.github.com" in u for u in Fake.urls), "a pinned commit is used as listed, with no lookup"
assert c.get("/packs/preview?id=nosuch", headers=H).status_code == 404
assert not (T / "out" / "requests").exists() or not any((T / "out" / "requests").iterdir()), "the preview wrote something"
print("  the preview reads pack.yaml at the commit it would install and writes nothing")

# ---- install: refused cases write nothing
for body, code, words in (({"id": "nosuch", "commit": SHA}, 404, "not on the wild list"),
                          ({"id": "posi", "commit": "HEAD"}, 400, "40-character"),
                          ({"id": "tide", "commit": SHA}, 409, "installed already"),
                          ({"id": "heat", "commit": SHA}, 409, "core pack")):
    r = c.post("/packs/install", json=body, headers=H)
    assert r.status_code == code and words in r.json()["detail"], (body, r.status_code, r.text)
assert not (T / "out" / "requests" / "pack-add.json").exists()
print("  an id off the list, a commit that is not one, a pack already here and a core id are refused, and nothing is written")

# ---- install: the request is an id and a commit, one at a time
assert c.get("/packs/install", headers=H).json() == {"state": "idle"}
r = c.post("/packs/install", json={"id": "posi", "commit": SHA, "extra": "rm -rf /"}, headers=H)
assert r.status_code == 200 and r.json() == {"state": "waiting", "id": "posi", "commit": SHA}, r.text
req = json.loads((T / "out" / "requests" / "pack-add.json").read_text())
assert set(req) == {"id", "commit", "at"} and req["id"] == "posi" and req["commit"] == SHA, req
assert Cur.actions and "posi" in Cur.actions[-1][0], "the install is not in the settings history"
s = c.get("/packs/install", headers=H).json()
assert s["state"] == "waiting" and s["id"] == "posi" and not s["stuck"], s
r = c.post("/packs/install", json={"id": "posi", "commit": SHA}, headers=H)
assert r.status_code == 409 and "being installed" in r.json()["detail"], r.text
old = time.time() - 600
os.utime(T / "out" / "requests" / "pack-add.json", (old, old))
assert c.get("/packs/install", headers=H).json()["stuck"], "a request nobody picked up in ten minutes is said to be stuck"
# the host took it, and is building
(T / "out" / "requests" / "pack-add.json").unlink()
(T / "out" / "requests" / "pack-add.status").write_text(json.dumps({"state": "running", "id": "posi", "commit": SHA,
                                                                     "line": "fetching posi", "t": int(time.time())}))
assert c.get("/packs/install", headers=H).json()["line"] == "fetching posi"
assert c.post("/packs/install", json={"id": "pinned", "commit": "c" * 40}, headers=H).status_code == 409, "one at a time"
(T / "out" / "requests" / "pack-add.status").write_text(json.dumps({"state": "failed", "id": "posi", "line": "x", "t": 1}))
assert c.post("/packs/install", json={"id": "pinned", "commit": "c" * 40}, headers=H).status_code == 200, "after a failure, another"
print("  the request holds an id and a commit only, says waiting, then stuck, and one install runs at a time")

# ---- a new pack on the list is said once; the first read says nothing
said = []
main.notify = lambda level, text, **k: said.append((level, text))
main._quiet = lambda level: False
main.check_wild()
assert said == [] and {"pack:tide", "pack:posi", "pack:pinned", "pack:heat"} <= Cur.told, (said, Cur.told)
LIST.append({"id": "kelp", "name": "Kelp", "author": "Ana", "reads": "Kelp cover from Sentinel-2.", "source": "a/kelp"})
main.check_wild()
main.check_wild()
assert said == [("info", "A new pack is on the PLANETAI list: Kelp, by Ana. It reads kelp cover from Sentinel-2. "
                         "To look at it and install it: Set up › Packs on this node's page.")], said
ROWS["UPDATE_CHECK"] = "off"
LIST.append({"id": "reef", "source": "a/reef"})
main.check_wild()
assert len(said) == 1 and "pack:reef" not in Cur.told, "UPDATE_CHECK=off asks nothing, as the release check"
print("  a pack new on the list is said once, the first read is silent, and UPDATE_CHECK=off stops it")

print("pack install: every pack listed with its state; preview and install for the admin token only; one request, an id and a commit")
