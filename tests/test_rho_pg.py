"""rho on a real database: only what was sent is asked (node #1, 20 Oct 2026).

On ALERT_ENGINE=events the engine speaks for the packs it replaced, and those packs' `alerts` rows are written and
never sent. rho once counted them: node #1 read 289 asks in 30 days for 9 messages that went out, rho 0.028, which
the programme page was about to publish. Needs a Postgres with init.sql applied, at RHO_PG_URL (CI's lint job
starts one); without it the suite skips.
Run: RHO_PG_URL=postgresql://planetai:x@127.0.0.1:5432/planetai PYTHONPATH=app PACKS_DIR=packs python3 tests/test_rho_pg.py
"""
import os
import sys

url = os.getenv("RHO_PG_URL")
if not url:
    print("  - rho on a real database skipped (set RHO_PG_URL to a Postgres with init.sql applied)")
    sys.exit(0)
os.environ.setdefault("DATABASE_URL", url)
os.environ["ALERT_ENGINE"] = "events"
import psycopg  # noqa: E402
from psycopg.rows import dict_row  # noqa: E402
import index  # noqa: E402

con = psycopg.connect(url, row_factory=dict_row)          # one transaction, rolled back: nothing stays
cur = con.cursor()
q = lambda sql, *a: cur.execute(sql, a)                  # noqa: E731
q("DELETE FROM actions"); q("DELETE FROM event_messages"); q("DELETE FROM alerts"); q("DELETE FROM alert_events")

def alert(rule, hours_ago, level="act"):
    cur.execute("INSERT INTO alerts (ts, rule_id, sensor_id, level, text) VALUES (now() - make_interval(hours => %s), %s, 'sc-1', %s, 'x') RETURNING id",
                (hours_ago, rule, level))
    return cur.fetchone()["id"]

def event(level, hours_ago, sent):
    cur.execute("INSERT INTO alert_events (issue, kind, level, opened_at, last_seen_at) VALUES ('heat', 'sustained', %s, "
                "now() - make_interval(hours => %s), now()) RETURNING id", (level, hours_ago))
    eid = cur.fetchone()["id"]
    q("INSERT INTO event_messages (ts, event_id, reason, kind, sent, held, mode, text) VALUES "
      "(now() - make_interval(hours => %s), %s, 'open', 'sustained', %s, false, 'events', 'x')", hours_ago, eid, sent)
    return eid

# the switch: the event engine's first sent message, 200 h ago
switch = event("act", 200, True)                                  # sent, at act: asked once
for h in (190, 150, 100, 50, 10):
    alert("heat/heat_stress_now", h)                              # heat is replaced: written after the switch, never sent
before = alert("heat/heat_stress_now", 300)                       # before the switch it was sent: asked
near1, near2 = alert("nearby/only_here", 120), alert("nearby/only_here", 40)   # not replaced: sent by rules, asked
event("act", 30, False)                                           # an act event never sent: not asked
event("warn", 20, True)                                           # sent, but not act: not asked
q("INSERT INTO actions (ts, alert_id, stage, actor) VALUES (now() - make_interval(hours => 119), %s, 'acted', 't')", near1)
q("INSERT INTO actions (ts, event_id, stage, actor) VALUES (now() - make_interval(hours => 199), %s, 'acknowledged', 't')", switch)

r = index.rho(cur)
assert (r["alerts_act"], r["acted"]) == (4, 2), f"asked 4 (one pre-switch heat row, two nearby rows, one sent act event), answered 2: {r}"
assert r["rho"] == 0.5, r
st = r["funnel"]["stages"]
assert st["asked"] == 4 and st["acknowledged"] == 1 and st["acted"] == 1, f"the funnel asks what rho asks: {st}"
print("  rho on an events node asks only what was sent: rows of replaced packs after the switch are left out, sent act events count")

os.environ["ALERT_ENGINE"] = "rules"
r2 = index.rho(cur)
assert r2["alerts_act"] == 9 and r2["acted"] == 1 + 1, f"on a rules node every act row is asked, and sent events still count: {r2}"
print("  on a rules node every act-level row is asked, as before")
con.rollback()
