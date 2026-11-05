"""A node says when a newer PLANETAI is out, once, and never installs it (Tomas, 30 Sep 2026).

check_release() asks planetai.fab.city/node0/get/VERSION every hour, puts what it found in /health (the header
and `planetai doctor` read it there), and sends Telegram one message per version. UPDATE_CHECK=off asks nothing.

    PYTHONPATH=app python3 tests/test_release_check.py
"""
import logging
import os
import time
from contextlib import contextmanager

os.environ.update(ADMIN_TOKEN="admin-tok", NODE_NAME="node-1", NODE_VERSION="v0.75.7-14-gafc298a",
                  DATABASE_URL="postgresql://unused/never-connected")

try:
    from fastapi.testclient import TestClient
except ImportError:
    print("release: skipped (pip install -r app/requirements.txt)")
    raise SystemExit(0)

logging.disable(logging.CRITICAL)
import settings  # noqa: E402
settings._cache = {"at": time.time() + 1e9, "rows": {}}
import main  # noqa: E402

fails = []
def check(ok, why):
    if not ok:
        fails.append(why)

# ---------------------------------------------------------------- which release a version string is at
R = main.release_of
check(R("v0.75.7") == (0, 75, 7) and R("v0.75") == (0, 75, 0), "a tag is its own release")
check(R("v0.75.7-14-gafc298a") == (0, 75, 7), "a checkout ahead of a tag is still at that tag's release")
check(R("v0.75.10") > R("v0.75.9"), "releases compare as numbers, not as text")
check(all(R(v) is None for v in ("", "?", "dev", "afc298a", "0.75.7", "v0.75.7x")), "a string that names no release is None")

# ---------------------------------------------------------------- the check, with the site, the database and Telegram faked
class Answer:
    def __init__(self, text, status=200):
        self.text, self.status_code = text, status
    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"{self.status_code}")

ASKED, TOLD, ROWS = [], [], set()
SITE = ["v0.75.8"]
class Site:
    def get(self, url, timeout=None):
        ASKED.append(url)
        return Answer(SITE[0])

class Cur:
    def execute(self, sql, args):
        self.got = None if args[0] in ROWS else (args[0],)
        ROWS.add(args[0])
    def fetchone(self):
        return self.got
class Con:
    def cursor(self):
        return self
    def __enter__(self):
        return Cur()
    def __exit__(self, *a):
        return False

@contextmanager
def fake_db():
    yield Con()

QUIET = [False]
main.hc, main.db = Site(), fake_db
main.notify = lambda level, text: TOLD.append((level, text))
main._quiet = lambda level: QUIET[0]
def fresh():
    main.state.pop("release", None)
    ASKED.clear(); TOLD.clear(); ROWS.clear()
    main.state.get("errors", {}).pop("check_release", None)

# Newer: said in state, told once, and asked once in RELEASE_EVERY however often the loop runs.
fresh()
main.check_release(); main.check_release(); main.check_release()
rel = main.state.get("release") or {}
check(rel.get("latest") == "v0.75.8" and rel.get("current") == "v0.75.7-14-gafc298a" and rel.get("newer") is True,
      f"v0.75.8 against v0.75.7-14 should be newer: {rel}")
check(ASKED == [main.RELEASE_URL], f"three hourly runs should ask the site once, asked {len(ASKED)}")
check(len(TOLD) == 1 and TOLD[0][0] == "info" and "v0.75.8" in TOLD[0][1] and "planetai update" in TOLD[0][1],
      f"the household should be told once, with the command: {TOLD}")

# A restart forgets the state but not the row: asked again, and still told only once.
main.state.pop("release", None)
main.check_release()
check(len(ASKED) == 2 and len(TOLD) == 1, f"after a restart the same version was told again: {TOLD}")

# Quiet hours hold the message; the next run after them sends it.
fresh(); QUIET[0] = True
main.check_release()
check(main.state["release"]["newer"] and not TOLD and not ROWS, "a release message went out in quiet hours")
QUIET[0] = False
main.check_release()
check(len(TOLD) == 1 and len(ASKED) == 1, "the held message did not go out once quiet hours were over, or the site was asked twice")

# The node is on that release, or ahead of it: nothing to say.
for here in ("v0.75.8", "v0.75.8-3-gabc1234", "v0.76"):
    fresh(); os.environ["NODE_VERSION"] = here
    main.check_release()
    check(main.state["release"]["newer"] is False and not TOLD, f"{here} was told v0.75.8 is newer")
# A node that cannot say which release it is on is never told it is behind.
fresh(); os.environ["NODE_VERSION"] = "?"
main.check_release()
check(main.state["release"]["newer"] is False and not TOLD, "a node with no version was told it is behind")
os.environ["NODE_VERSION"] = "v0.75.7-14-gafc298a"

# A site that answers with a page, or not at all: nothing said, nothing in the loops' errors (the agent's health
# check reads those as a broken source), and asked again in an hour rather than in a day.
for text, status in (("<!doctype html><title>PLANETAI</title>", 200), ("", 503)):
    fresh(); SITE[0] = text
    main.check_release() if status == 200 else None
    if status != 200:
        main.hc = type("Down", (), {"get": lambda self, url, timeout=None: Answer("", 503)})()
        main.check_release()
        main.hc = Site()
    rel = main.state.get("release") or {}
    check(not rel.get("newer") and rel.get("error") and not TOLD, f"a bad answer ({status}) became a release: {rel}")
    check("check_release" not in main.state.get("errors", {}), "a failed check reached the loops' errors")
    check(0 < main.RELEASE_EVERY - (time.time() - rel.get("asked", 0)) <= 3600 + 5,
          "after a failed check the site should be asked again in about an hour")
SITE[0] = "v0.75.8"

# Off: the site is never asked, and what the node knew is forgotten, so the header stops saying it.
fresh(); main.check_release()
settings._cache["rows"]["UPDATE_CHECK"] = "off"
ASKED.clear(); main.state["release"]["asked"] = 0
main.check_release()
check(not ASKED and "release" not in main.state, "UPDATE_CHECK=off still asked the site, or kept its answer")
settings._cache["rows"].pop("UPDATE_CHECK")

# ---------------------------------------------------------------- where it is said, and how it is declared
fresh(); main.check_release()
h = TestClient(main.app).get("/health").json()
check((h.get("release") or {}).get("latest") == "v0.75.8" and h["release"]["newer"] is True,
      f"/health does not carry the release the page and doctor read: {h.get('release')}")
check(settings.RUNTIME["UPDATE_CHECK"][0] == "sharing" and "UPDATE_CHECK" in settings.OUTWARD
      and settings.CHOICES["UPDATE_CHECK"][0] == "on" and "UPDATE_CHECK" in settings.PUBLIC,
      "UPDATE_CHECK should be a sharing setting, declared outward, on by default, readable without a token")
check("UPDATE_CHECK=on" in open(".env.example").read(), ".env.example does not ship UPDATE_CHECK=on")
js = open("app/static/dashboard.js").read()
check("function releaseBar(h)" in js and "${releaseBar(health)}</header>" in js, "the header does not draw the release line")
check("is out (this node runs" in open("bin/planetai").read(), "planetai doctor does not say a release is out")
check("CREATE TABLE IF NOT EXISTS release_notices" in open("init.sql").read(), "init.sql has no release_notices table")

print("\n".join(f"  x {f}" for f in fails) or "  release: asked every hour, told once per version, off asks nothing")
raise SystemExit(1 if fails else 0)
