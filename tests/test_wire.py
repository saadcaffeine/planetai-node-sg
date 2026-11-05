"""Every wire format says which format it is, and no receiver ever refuses one it does not know.

ARCHITECTURE.md §3 names the contracts that must not change casually. One of them was versioned
(`fci-cells-v0`); the nightly export — pinned to IPFS forever — carried a licence and no schema
version, `GET /issues` is the one document a client draws and had none, and the two pushes travel
between nodes on different releases with none. This asserts the five keys and, more importantly, the
rule that makes them safe to add: **a receiver logs and processes, it never refuses.**

That rule is not decoration. A parent one release behind has to keep accepting a child one release
ahead, or the first operator to update their own node silently stops the district's numbers — and
nobody would find out, because a push that 400s is a line in a log on a machine in a cupboard.

    PYTHONPATH=app python3 tests/test_wire.py
"""
import logging
import os
import time

os.environ.update(ADMIN_TOKEN="admin-tok", AGGREGATE_TOKEN="agg-tok", NODE_NAME="parent-1",
                  DATABASE_URL="postgresql://unused/never-connected")

try:
    from fastapi.testclient import TestClient
except ImportError:
    print("wire: request checks skipped (pip install -r app/requirements.txt)")
    raise SystemExit(0)

logging.disable(logging.NOTSET)
import settings  # noqa: E402
settings._cache = {"at": time.time() + 1e9, "rows": {"AGGREGATE_TOKEN": "agg-tok"}}
import main  # noqa: E402
import threading  # noqa: E402

# Importing main starts nothing: the loops, the MQTT client and the bootstrap run from the app's lifespan (main.start).
# A second import used to run a second node inside the first, and its MQTT client knocked node #1 off the broker.
_started = sorted(t.name for t in threading.enumerate() if t.name in ("poll_sources", "run_rules", "mqtt", "sc-forward"))
assert not _started and main._STARTED is False, f"importing main started {_started}"
import db  # noqa: E402
assert main.db is db.db and db._pool is None, "importing main opened the connection pool; it opens on first use"

# ---------------------------------------------------------------- the emitters
# The five constants exist and are the strings the documents carry. Read off the module rather than
# retyped, so a rename here fails rather than quietly producing a second vocabulary.
assert (main.ISSUES_V0, main.EXPORT_V0, main.AGGREGATES_V0, main.EVENTS_V0, main.REPORT_V0) == \
    ("issues-v0", "export-v0", "aggregates-v0", "events-v0", "report-v0")

SRC = open("app/main.py").read()
for const in ("AGGREGATES_V0", "EVENTS_V0"):
    assert f'json={{"schema": {const}' in SRC, f"the push body must lead with schema: {const}"
assert '"schema": EXPORT_V0' in SRC, "/export carries its version"
assert '"schema": REPORT_V0' in SRC, "/report/latest carries its version"
assert '"schema": "issues-v0"' in open("app/issues/engine.py").read(), "the issues document carries its version"
print("all five documents carry a schema key")

# ---------------------------------------------------------------- the receivers
# A parent with no database: every push below reaches the auth check and the schema check, and dies
# at the first cursor. What is under test is what happens BEFORE that, and a 500 from the database is
# proof the request was accepted — a refusal on the version would be a 4xx and would never get there.
main.db = lambda: (_ for _ in ()).throw(RuntimeError("no database in this test"))
c = TestClient(main.app, raise_server_exceptions=False)
AUTH = {"Authorization": "Bearer agg-tok"}
ROWS = {"aggregates": [{"bucket": "2026-09-19T10:00:00+00:00", "sensor_id": "ag-1", "metric": "pm25",
                        "mean": 12.0, "min": 9.0, "max": 15.0, "n": 12}],
        "events": [{"alert_id": "1", "rule": "air-quality/pm25", "level": "act",
                    "raised_at": "2026-09-19T10:00:00+00:00"}]}


def push(path, body):
    return c.post(path, json=body, headers=AUTH)


def accepted(r, why):
    """Accepted = it got past auth and the version check. 401/403/422 mean it did not."""
    assert r.status_code not in (400, 401, 403, 415, 422), f"{why}: refused with {r.status_code} {r.text[:120]}"


for path, key in (("/aggregates", "aggregates"), ("/events", "events")):
    rows = ROWS[key]
    # 1. the version this release sends
    accepted(push(path, {"schema": f"{key}-v0", "node": "child-1", "rows": rows}), f"{path} current")
    # 2. NO schema at all — every node on v0.62 and earlier, and node #1 and Menorca today
    accepted(push(path, {"node": "child-1", "rows": rows}), f"{path} legacy, no schema")
    # 3. a version from the future. A child two releases ahead must not be turned away by a parent
    #    that has not been updated: it is the same household's data and the rows it recognises are
    #    still right.
    accepted(push(path, {"schema": f"{key}-v9", "node": "child-1", "rows": rows}), f"{path} unknown version")
    # 4. rubbish in the field, which is what a bug upstream looks like
    accepted(push(path, {"schema": {"not": "a string"}, "node": "child-1", "rows": rows}), f"{path} non-string")
    accepted(push(path, {"schema": "x" * 4000, "node": "child-1", "rows": rows}), f"{path} absurd length")
print("both receivers accept: current, legacy, a future version, a non-string and an absurd one")

# ---------------------------------------------------------------- the log, and its bound
# The value arrives from a child over the network, so the set that makes the log once-per-value is a
# set keyed on a stranger's string. Capped, or a child looping with a random schema is a slow leak.
main._wire_said.clear()
for i in range(500):
    main._wire_in({"schema": f"made-up-{i}"}, main.EVENTS_V0)
assert len(main._wire_said) <= 64, f"the seen-versions set is unbounded: {len(main._wire_said)}"

# and the return value is what the node will read it as, never the stranger's string
assert main._wire_in({}, main.EVENTS_V0) == "events-v0", "no schema reads as -v0"
assert main._wire_in({"schema": "events-v0"}, main.EVENTS_V0) == "events-v0"
assert main._wire_in({"schema": "events-v9"}, main.EVENTS_V0) == "events-v9", "it reports what was said"
print("the seen-versions set is bounded and _wire_in reports what it read")

# ---------------------------------------------------------------- /report/latest has ONE shape
# Until v0.63 the empty case answered five keys and the populated case ten, so a client reading
# `sent` had to know which case it was in. That is the implicitness this release is about, and it
# would have been invisible without a fixture to compare against.
main.q = lambda sql, *a: []
# SHARE_LEVEL is off and TestClient is a stranger on the WiFi, so the read needs the token.
body = c.get("/report/latest", headers={"Authorization": "Bearer admin-tok"}).json()
assert body["schema"] == "report-v0"
for k in ("id", "ts", "due_local", "window_hours", "depth", "rung", "text", "sent",
          "held_quiet", "fallback_reason"):
    assert k in body, f"/report/latest with no report must still carry {k}"
assert body["note"], "and it says why they are all null"
print("/report/latest answers one shape whether or not a report exists")

print("all wire tests pass")
