"""What worked here (docs/SPEC_learn.md step 1): app/learn.py's arithmetic on hours made by hand, its status rules, and
GET /learned's guards. The database is stubbed; the numbers are worked out here so a wrong window shows.

Run: PYTHONPATH=app python3 tests/test_learned.py
"""
import logging
import os
import re
import time
from datetime import datetime, timedelta, timezone

import learn

SQL = open("init.sql").read()
SRC = open("app/main.py").read()

# ---------------------------------------------------------------- the table, kept home
m = re.search(r"CREATE TABLE IF NOT EXISTS learnings \((.*?)\n\);", SQL, re.S)
assert m and "PRIMARY KEY (kind, key)" in m.group(1), "one row per learning, replaced, never duplicated"
assert "'too_early','holding','weakening','gone'" in m.group(1), "a learning is marked, never deleted"
assert "REVOKE ALL ON learnings FROM planetai_ro" in SQL, "pack SQL never reads what the house learned"
for road in ("def export", "def push_aggregates", "def aggregates"):
    body = SRC[SRC.index(road):SRC.index("\n\n\n", SRC.index(road))]
    assert "learnings" not in body, f"{road} must never name the learnings table"
assert "DELETE FROM learnings" not in SRC, "nothing deletes a learning"
print("schema: learnings kept home, marked and never deleted")

# ---------------------------------------------------------------- the arithmetic
assert abs(learn.apparent(30, 70) - (30 + 0.33 * (0.7 * 6.105 * 2.718281828 ** (17.27 * 30 / 267.7)) - 4)) < 1e-6, \
    "the Steadman form the heat rules use"
T0 = datetime(2026, 10, 1, 20, tzinfo=timezone.utc)
H = lambda k: T0 + timedelta(hours=k)  # noqa: E731
inside = {H(-1): 40.0, H(1): 20.0, H(2): 10.0}            # before 40, after mean(20, 10) = 15: -25
street = [{H(-1): 30.0, H(1): 25.0, H(2): 25.0}, {H(-1): 10.0, H(1): 15.0, H(2): 15.0}]   # street 20 -> 20: 0
c = learn.case(inside, street, T0, learn.AFTER["pm25"])
assert c == {"at": T0.isoformat(), "before": 40.0, "after": 15.0, "change": -25.0, "street": 0.0}, c
assert learn.case({H(1): 5.0}, street, T0, (1, 2)) is None, "no hour before, no case"
assert learn.case(inside, [], T0, (1, 2))["street"] is None, "no street, only the house's change"
heat = learn.series([{"bucket": H(0), "sensor_id": "k", "metric": "temp", "mean": 30.0},
                     {"bucket": H(0), "sensor_id": "k", "metric": "humidity", "mean": 70.0}])
assert abs(heat[("k", "apparent")][H(0)] - learn.apparent(30, 70)) < 1e-9, "apparent where temp and humidity meet"
print("arithmetic: the hour before, the window after, the street beside, apparent as the rules compute it")

# ---------------------------------------------------------------- the row and its statement
cs = [{"change": -25.0, "street": 0.0}] * 6
row = learn.summarise("air-quality/indoor_pm25_high", "pm25", cs, [{"change": -2.0, "street": -1.0}] * 3, None, True)
assert row["status"] == "holding" and row["n"] == 6 and row["numbers"]["acted"]["change"] == -25.0
assert row["statement"] == ("After unhealthy air inside, 9 times so far: acting on it helps. "
                            "Acted on 6 times: PM2.5 inside changed -25.0 µg/m³ in the 1–2 h after, while on the street "
                            "it changed +0.0 µg/m³. Left unanswered 3 times: PM2.5 inside changed -2.0 µg/m³ in the "
                            "1–2 h after, while on the street it changed -1.0 µg/m³."), row["statement"]
assert row["numbers"]["verdict"] == "helps"
assert all(str(x) in row["statement"] for x in ("6", "-25.0", "3", "-2.0")), "every number in the sentence is a row number"
early = learn.summarise("heat/heat_stress_now", "apparent", cs[:4], [], None, True)
assert early["status"] == "too_early" and early["statement"] == (
    "After heat inside, 4 times so far: too few to be sure whether acting on it helps. Acted on 4 times."), \
    "under five, a count and no percentage"
assert early["numbers"]["verdict"] == "too_early"
flip = learn.summarise("air-quality/indoor_pm25_high", "pm25", [{"change": 3.0, "street": 0.0}] * 6, [], row, True)
assert flip["status"] == "weakening", "it held, and now it goes the other way"
old = learn.summarise("x/old", "pm25", cs, [], row, False)
assert old["status"] == "gone" and old["numbers"]["verdict"] == "gone", "a rule that cannot fire is gone, kept"
assert old["statement"].startswith("After x/old, 6 times so far: this alert no longer rings here") and "-25.0" in old["statement"]
# The verdict (design review, 14 Oct). node #1's air row read HOLDING while acting had made it worse: acted +2.5 against
# unanswered -0.8. Holding says the learning holds; the verdict says what it holds, from the row's own numbers, first.
n1 = learn.summarise("air-quality/events", "pm25", [{"change": 2.5, "street": 0.3}] * 5, [{"change": -0.8, "street": 0.1}] * 4, None, True)
assert n1["status"] == "holding" and n1["numbers"]["verdict"] == "worse", n1["numbers"]
assert n1["statement"].startswith("After an air alert, 9 times so far: acting on it seemed to make it worse than leaving it. "
                                  "Acted on 5 times: PM2.5 inside changed +2.5 µg/m³"), n1["statement"]
same = learn.summarise("heat/events", "apparent", [{"change": -1.0, "street": -0.5}] * 5, [{"change": -0.8, "street": -0.5}] * 5, None, True)
assert same["numbers"]["verdict"] == "no_clear_difference", "0.2 °C apart is inside half a degree of noise"
assert "no clear difference between acting on it and leaving it" in same["statement"]
alone = learn.summarise("heat/events", "apparent", [{"change": -2.0, "street": 0.0}] * 5, [], None, True)
assert alone["numbers"]["verdict"] == "helps", "nobody unanswered yet: leaving it counts as no change"
street = learn.summarise("air-quality/events", "pm25", [{"change": -6.0, "street": -6.0}] * 5, [{"change": 0.0, "street": 0.0}] * 5, None, True)
assert street["numbers"]["verdict"] == "no_clear_difference", "the street cleared as much: acting did not do it"
# the diary split's pages read these values (Now's "Did it work", Node's table): the same five, never a sixth
assert set(learn.VERDICT_WORDS) == {"helps", "no_clear_difference", "worse", "too_early", "gone"}
for r in (row, early, n1, same, alone, street):
    assert r["statement"].index(learn.VERDICT_WORDS[r["numbers"]["verdict"]]) < 60, "the plain meaning leads"
assert learn.alert_name("air-quality/some_new_rule") == "an air alert" and learn.alert_name("nearby/x") == "nearby/x"
# The names and the pack of each issue come from the packs since 23 Oct 2026: a rule's `name:`, its issue's `alert:`,
# the pack that ships the issue. The core keeps no map naming air-quality or heat.
assert learn.alert_name("air-quality/indoor_pm25_high") == "unhealthy air inside" and learn.alert_name("heat/events") == "a heat alert"
assert learn._issue_packs() == {"air": "air-quality", "heat": "heat", "coast": "coast", "land": "earth", "water": "terrain"}, learn._issue_packs()
assert learn._metric("air-quality") == "pm25" and learn._metric("heat") == "apparent" and learn._metric("nearby") is None
import events_pg as _epg, report as _rep  # noqa: E402
for _mod, _gone in ((learn, ("PACK_METRIC", "ISSUE_PACK", "ALERT_NAMES")), (_epg, ("PACK_ISSUE",)), (_rep, ("THRESHOLDS",))):
    assert not any(hasattr(_mod, g) for g in _gone), f"{_mod.__name__} keeps a hard-coded pack map again"
ranked = sorted(learn.rank([n1, {"kind": "usual", "key": "indoor-heat", "issue": "heat", "numbers": {}}], {}), key=lambda r: r["kind"] != "worked")
assert ranked[0]["name"] == "an air alert" and ranked[0]["verdict"] == learn.VERDICT_WORDS["worse"], ranked[0]
assert ranked[1]["name"] == "the feels-like temperature inside" and ranked[1]["verdict"] is None
# /learned in the bot: the alert as the household calls it and the verdict first, the status in words, no rule id
import ast  # noqa: E402
_tree = ast.parse(open("app/agent_loop.py").read())
_ns = {}
for _n in _tree.body:
    if (isinstance(_n, ast.FunctionDef) and _n.name == "_learned_head") or (
            isinstance(_n, ast.Assign) and any(getattr(t, "id", None) == "LEARNED_STATUS" for t in _n.targets)):
        exec(compile(ast.Module([_n], []), "agent_loop.py", "exec"), _ns)
assert _ns["_learned_head"](ranked[0]) == "An air alert: acting on it seemed to make it worse than leaving it (the finding holds)", \
    _ns["_learned_head"](ranked[0])
assert "x['key']" not in open("app/agent_loop.py").read().split('if text.startswith("/learned")')[1][:3000], "no rule id"
print("rows: holding, too early under five, weakening when it turns, gone when the rule is retired; the sentence is the numbers")
print("verdicts: helps, no clear difference, worse than leaving it, too early; led in words, named as the household names it")

# ---------------------------------------------------------------- the cases from the ledger
now = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
t = now - timedelta(days=1)
ALERTS = [
    {"id": 1, "ts": t, "rule_id": "air-quality/indoor_pm25_high", "sensor_id": "in", "acted_at": t + timedelta(minutes=20), "answered": True, "note": "closed the windows"},
    {"id": 2, "ts": t, "rule_id": "air-quality/indoor_pm25_high", "sensor_id": "in", "acted_at": None, "answered": False, "note": None},
    {"id": 3, "ts": t, "rule_id": "air-quality/indoor_pm25_high", "sensor_id": "in", "acted_at": None, "answered": True, "note": None},
    {"id": 4, "ts": now, "rule_id": "air-quality/indoor_pm25_high", "sensor_id": "in", "acted_at": now, "answered": True, "note": ""},
    {"id": 5, "ts": t, "rule_id": "air-quality/retired_rule", "sensor_id": "in", "acted_at": t, "answered": True, "note": "opened"},
    {"id": 6, "ts": t, "rule_id": "nearby/only_here", "sensor_id": "out", "acted_at": t, "answered": True, "note": ""},
    {"id": 7, "ts": t, "rule_id": "indoor_pm25_high", "sensor_id": "in", "acted_at": t, "answered": True, "note": ""}]
READ = [{"bucket": t + timedelta(hours=k), "sensor_id": sid, "metric": "pm25", "mean": v, "indoor": ind}
        for sid, ind, vals in (("in", True, {-1: 40, 1: 20, 2: 10}), ("out", False, {-1: 20, 1: 20, 2: 20}))
        for k, v in vals.items()]
q = lambda sql, *a: ALERTS if "FROM alerts" in sql else [dict(r) for r in READ]  # noqa: E731
rules = [{"id": "air-quality/indoor_pm25_high", "level": "act", "watch": {"metric": "pm25", "over": 35.5}},
         {"id": "heat/heat_stress_now", "level": "act", "watch": {"metric": "apparent", "over": 35}},
         {"id": "nearby/only_here", "level": "act"}, {"id": "air-quality/warn_only", "level": "warn"}]
out = {r["key"]: r for r in learn.learn_worked(q, rules, {"air-quality/indoor_pm25_high", "heat/heat_stress_now"}, {})}
assert set(out) == {"air-quality/indoor_pm25_high", "air-quality/retired_rule"}, \
    f"rules with cases and a metric; a rule with no alerts has no row; no metric, no row: {set(out)}"
aq = out["air-quality/indoor_pm25_high"]["numbers"]
assert aq["acted"]["n"] == 1 and aq["unanswered"]["n"] == 1, "seen-but-not-acted is neither; an open window waits"
assert aq["cases"]["acted"][0]["note"] == "closed the windows" and aq["cases"]["acted"][0]["change"] == -25.0
gone = out["air-quality/retired_rule"]
assert gone["status"] == "gone" and gone["numbers"]["acted"]["n"] == 1 and gone["metric"] == "pm25", \
    "a retired rule keeps what it taught, by its pack's metric"
print("ledger: acted and unanswered from the alerts, an unfinished window waits, notes kept, a retired rule kept as gone")

# ---------------------------------------------------------------- an events node: silent rows are not alerts anyone got
SINCE = now - timedelta(hours=12)
assert learn.silent("heat/heat_stress_now", now, {"heat"}, SINCE) and not learn.silent("heat/heat_stress_now", now - timedelta(days=9), {"heat"}, SINCE)
assert not learn.silent("nearby/only_here", now, {"heat"}, SINCE) and not learn.silent("heat/x", now, {"heat"}, None)
EVENTS = [{"id": i, "issue": "air", "opened_at": t + timedelta(minutes=i), "rooms": ["Kitchen"], "hour": 13, "acted_at": None,
           "acted": False, "dismissed": False, "answered": False, "note": None} for i in range(6)]
EVENTS[0].update(acted_at=t, acted=True, answered=True, note="closed the door")
ARows = [{"rule_id": "air-quality/indoor_pm25_high", "hour": 13, "acted": False, "dismissed": False, "answered": False, "ts": now - timedelta(hours=k)} for k in range(9)] \
      + [{"rule_id": "nearby/only_here", "hour": 8, "acted": False, "dismissed": False, "answered": False, "ts": now - timedelta(hours=k)} for k in range(6)]
def qe(sql, *a):
    if "FROM alert_events" in sql:
        return [dict(e) for e in EVENTS]
    if "FROM sensors WHERE name" in sql:
        return [{"sensor_id": "in", "name": "Kitchen"}]
    if "FROM alerts" in sql and "hour FROM l.ts" in sql:
        return ARows
    if "FROM alerts" in sql:
        return [a for a in ALERTS if a["rule_id"] == "air-quality/indoor_pm25_high"] + \
               [{**ALERTS[1], "id": 9, "ts": now - timedelta(hours=3), "acted_at": None, "answered": False}]
    return [dict(r) for r in READ]
ak = {r["key"]: r for r in learn.learn_asks(qe, {"air-quality/indoor_pm25_high", "nearby/only_here"}, {"air-quality"}, SINCE)}
assert ak["air-quality/indoor_pm25_high"]["status"] == "gone" and "no longer sends here" in ak["air-quality/indoor_pm25_high"]["statement"], \
    "a replaced rule says it no longer rings, not how often it rang"
assert ak["nearby/only_here"]["n"] == 6, "a pack the engine does not replace is counted as before"
assert ak["air-quality/events"]["n"] == 6 and ak["air-quality/events"]["numbers"]["acted"] == 1, "the engine's sent episodes are the alerts here"
wk = {r["key"]: r for r in learn.learn_worked(qe, rules, {"air-quality/indoor_pm25_high"}, {}, {"air-quality"}, SINCE)}
assert wk["air-quality/indoor_pm25_high"]["numbers"]["unanswered"]["n"] == 1, "the silent row after the switch is not an unanswered alert"
ev = wk["air-quality/events"]["numbers"]
assert ev["acted"]["n"] == 1 and ev["cases"]["acted"][0]["note"] == "closed the door", "an episode is a case on its room's sensor"
print("events node: silent rows left out, a replaced rule says so, the engine's sent episodes counted in both learnings")

# ---------------------------------------------------------------- the route
logging.disable(logging.WARNING)
os.environ.update(ADMIN_TOKEN="admin-tok", ACT_TOKEN="act-tok", NODE_LAT="-8.6478291", NODE_LON="115.1385412",
                  DATABASE_URL="postgresql://unused/never-connected")
import settings                                    # noqa: E402
settings._cache = {"at": time.time() + 1e9, "rows": {"SHARE_LEVEL": "open"}}
import main                                       # noqa: E402
from fastapi.testclient import TestClient         # noqa: E402

main.q = main.household.q = lambda sql, *a: [{"scale": "day", "n": 40}] if "FROM digests" in sql else [{"kind": "worked", "key": "k", "status": "holding", "statement": "s", "numbers": {}}]
c = TestClient(main.app)
ADMIN = {"Authorization": "Bearer admin-tok"}
assert c.get("/learned").status_code in (401, 403) and c.get("/learned", headers={"Authorization": "Bearer act-tok"}).status_code == 401
assert c.get("/learned", headers=ADMIN).json()["learnings"][0]["statement"] == "s"
assert c.get("/learned", headers=ADMIN).json()["digests"] == {"day": 40}, "Node counts the diary entries kept, by scale"
settings._cache["rows"]["AGENT_PREFER"] = "private"
assert c.get("/learned", headers={**ADMIN, "X-Agent": "agent"}).status_code == 200, "an agent, models at home: yes"
settings._cache["rows"]["AGENT_PREFER"] = "fallback"
r = c.get("/learned", headers={**ADMIN, "X-Agent": "agent"})
assert r.status_code == 403 and "AGENT_PREFER" in r.json()["detail"], "an agent that may be online: no, and why"
assert c.get("/learned", headers=ADMIN).status_code == 200, "the page is not an agent"
# a city's server in the remote box: under private it is not used at all, so the learnings stay readable at home;
# under fallback it is used, and the agent is told why it may not read them
settings._cache["rows"].update(AGENT_PREFER="private", AGENT_REMOTE_URL="https://vllm.city.example.org/v1")
assert c.get("/learned", headers={**ADMIN, "X-Agent": "agent"}).status_code == 200, "private never uses a public remote"
settings._cache["rows"]["AGENT_PREFER"] = "fallback"
r = c.get("/learned", headers={**ADMIN, "X-Agent": "agent"})
assert r.status_code == 403 and "outside this house" in r.json()["detail"], "fallback, a public remote: no, and why"
assert c.get("/household", headers={**ADMIN, "X-Agent": "agent"}).status_code == 403
assert c.get("/learned/search?q=smoke", headers={**ADMIN, "X-Agent": "agent"}).status_code == 403
settings._cache["rows"].update(AGENT_PREFER="private", AGENT_REMOTE_URL="http://192.168.4.44:11434/v1")
assert c.get("/learned", headers={**ADMIN, "X-Agent": "agent"}).status_code == 200, "private, a LAN remote: yes"
settings._cache["rows"]["AGENT_REMOTE_URL"] = ""
print("route: admin only; an agent only while every model stays home, told why otherwise")
# GET /learned/place: the place's usual hours for a screen with no token (the Wall), and nothing of the house
_sql = []
main.q = main.household.q = lambda sql, *a: _sql.append(sql) or [{"key": "outdoor-pm25", "issue": "air", "metric": "pm25", "statement": "s", "numbers": {"high_hour": 18}}]
r = c.get("/learned/place")
assert r.status_code == 200 and r.json()["learnings"][0]["key"] == "outdoor-pm25", r.text
assert "kind = 'usual'" in _sql[0] and "scope = 'place'" in _sql[0] and "status = 'holding'" in _sql[0] and "cases" not in _sql[0], _sql
settings._cache["rows"]["SHARE_LEVEL"] = "off"
assert c.get("/learned/place").status_code == 403, "at SHARE_LEVEL=off a screen with no token reads nothing of it"
settings._cache["rows"]["SHARE_LEVEL"] = "open"
assert "/learned/place" in main._SHARE_OPEN[0] and "/learned" not in main._SHARE_OPEN[0] and "/learned/search" not in main._SHARE_OPEN[0]
print("route: /learned/place answers the place's usual hours on the open list; /learned and its search stay the house's")

# ---------------------------------------------------------------- what is usual (step 2)
from datetime import date  # noqa: E402
assert learn.theil_sen([1, 2, 3, 100, 5]) == 1.0, "a slope one odd day cannot drag"
WIB = timezone(timedelta(hours=8))
start = datetime(2026, 9, 1, tzinfo=WIB)
hourly = {}
for d in range(28):
    for h in range(24):
        b = start + timedelta(days=d, hours=h)
        hourly[b] = (20.0 if h == 7 else 5.0 if h == 0 else 10.0) + (3.0 if b.isoweekday() >= 6 else 0) + (8.0 if d >= 21 else 0)
today = (start + timedelta(days=27)).date()
u = learn.usual_row("indoor-pm25", hourly, today)
assert u["status"] == "holding" and u["scope"] == "house" and u["numbers"]["high_hour"] == 7 and u["numbers"]["low_hour"] == 0, u["numbers"]
assert "highest around 07:00" in u["statement"] and "lowest around 00:00" in u["statement"], "the hours are the house's local ones"
assert "Weekends run" in u["statement"] and "higher than weekdays" in u["statement"]
assert "above the three weeks before" in u["statement"], "this week is 8 over a steady three weeks"
assert "every 30 days" not in u["statement"], "no trend before 60 days"
assert learn.usual_row("outdoor-pm25", {b: v for b, v in hourly.items() if (today - b.date()).days < 10}, today)["status"] == "too_early"
assert learn.usual_row("indoor-heat", {}, today) is None, "no sensor of that kind, no row"
long = {start + timedelta(days=d, hours=12): 10.0 + d * 0.1 for d in range(90)}
lu = learn.usual_row("outdoor-pm25", long, (start + timedelta(days=89)).date())
assert lu["scope"] == "place" and lu["numbers"]["trend_per_30_days"] == 3.0, lu["numbers"]
rows = [{"bucket": b, "sensor_id": sid, "metric": "pm25", "mean": v, "indoor": ind}
        for b, v in list(hourly.items())[:400] for sid, ind in (("in", True), ("out", False))]
got = {r["key"]: r for r in learn.learn_usual(lambda sql, *a: [dict(r) for r in rows], today)}
assert set(got) == {"indoor-pm25", "outdoor-pm25"} and got["outdoor-pm25"]["scope"] == "place", set(got)
print("usual: the day's highest and lowest hour, weekends, this week against three, a trend after 60 days; inside is house, outside is place")

# ---------------------------------------------------------------- asks that do not fit
mk = lambda n, hour, acted=False, answered=False: [{"hour": hour, "acted": acted, "dismissed": False, "answered": answered or acted}] * n  # noqa: E731
assert learn.asks_row("heat/x", mk(4, 13), True) is None, "under five, nothing to say"
night = learn.asks_row("heat/x", mk(8, 23) + mk(2, 13, acted=True), True)
assert night["numbers"]["unanswered_at_night"] == 8 and "between 22:00 and 06:00" in night["statement"], night["statement"]
assert "Quiet hours do not hold an act-level alert" in night["statement"], "says why quiet hours would not help"
often = learn.asks_row("heat/y", mk(170, 13) + mk(2, 9, acted=True), True)
assert "about 6 times a day" in often["statement"] and "around 13:00" in often["statement"], often["statement"]
fine = learn.asks_row("air/z", mk(6, 13, acted=True) + mk(1, 2), True)
assert fine["numbers"]["suggest"] is None and "change to its rule" not in fine["statement"], "mostly answered: no suggestion"
assert learn.asks_row("air/old", mk(6, 13), False)["status"] == "gone"
SRC2 = open("app/learn.py").read()
assert "UPDATE" not in SRC2 and "INSERT" not in SRC2 and "settings.set" not in SRC2, "learning changes no rule and no setting"
print("asks: a count, the hours, and what would change it, said and never done; nothing under five")
# ---------------------------------------------------------------- digests and search (step 3)
from datetime import date  # noqa: E402,F811
m = re.search(r"CREATE TABLE IF NOT EXISTS digests \((.*?)\n\);", SQL, re.S)
assert m and "PRIMARY KEY (scale, period_start)" in m.group(1) and "to_tsvector('simple'" in m.group(1)
assert "REVOKE ALL ON digests FROM planetai_ro" in SQL and "DELETE FROM digests" not in SRC
for road in ("def export", "def push_aggregates", "def aggregates"):
    body = SRC[SRC.index(road):SRC.index("\n\n\n", SRC.index(road))]
    assert "digests" not in body, f"{road} must never name the digests"
ps = learn.periods(date(2026, 9, 29), date(2026, 10, 14))
by = {k: [p[1] for p in ps if p[0] == k] for k in learn.SCALES}
assert len(by["day"]) == 15 and by["day"][-1] == date(2026, 10, 13), "every completed day, never today"
assert by["week"] == [date(2026, 9, 28), date(2026, 10, 5)], "Monday to Sunday, only finished weeks"
assert by["month"] == [date(2026, 9, 1)] and by["year"] == [], "September is done, October is not"
assert learn.label("day", date(2026, 10, 13)) == "Tuesday 13 October 2026" and learn.label("week", date(2026, 10, 5)) == "Week of 5 October 2026"
B = lambda d, h: datetime(2026, 10, d, h, tzinfo=WIB)  # noqa: E731
G = {"indoor-pm25": {B(13, 7): 30.0, B(13, 8): 10.0}, "outdoor-pm25": {B(13, 6): 40.0, B(12, 6): 99.0}}
dg = learn.digest("day", date(2026, 10, 13), date(2026, 10, 14), G,
                  [{"rule_id": "heat/heat_stress_now", "acted": True}, {"rule_id": "heat/heat_stress_now", "acted": False}],
                  [{"note": "closed the windows"}, {"note": "closed the windows"}, {"note": "purifier on"}],
                  {"indoor-pm25": {"mean": 15.0}, "outdoor-pm25": {"mean": 40.0}})
t = dg["text"]
assert t.startswith("Tuesday 13 October 2026. PM2.5 inside averaged 20.0 µg/m³, highest 30.0 µg/m³ (07:00)"), t
assert "PM2.5 outside averaged 40.0" in t and "99" not in t, "only the period's own hours"
assert "2 alerts (heat_stress_now 2), 1 acted on." in t
assert "\u201cclosed the windows\u201d \u00d72; \u201cpurifier on\u201d" in t, "each note once, with how many times"
assert "Against the day before: PM2.5 inside +5.0." in t, "a change under 0.1 is not said"
assert "feels-like" not in t, "a group with no readings is not invented"
assert dg["numbers"]["v"] == learn.DIGEST_V, "a digest says which version wrote it, so an older one is written again"
# an events node: the replaced pack's rows were never sent; the episodes that were are counted, by issue
D13 = lambda h: datetime(2026, 10, 13, h, tzinfo=WIB)  # noqa: E731
def qd(sql, *a):
    if "min(r.ts)" in sql:
        return [{"t": datetime(2026, 10, 12, 1, tzinfo=WIB)}]
    if "SELECT now()" in sql:
        return [{"t": D13(9)}]
    if "FROM alert_events" in sql:
        return [{"issue": "heat", "opened_at": D13(14), "acted": True}, {"issue": "heat", "opened_at": D13(14) - timedelta(days=9), "acted": False}]
    if "FROM alerts" in sql:
        return [{"rule_id": "heat/heat_stress_now", "ts": D13(h), "d": date(2026, 10, 13), "acted": False} for h in range(7)] \
             + [{"rule_id": "nearby/only_here", "ts": D13(8), "d": date(2026, 10, 13), "acted": False}]
    return []
d13 = {d["period_start"]: d for d in learn.write_digests(qd, set(), {}, date(2026, 10, 14), {"heat"}, D13(0) - timedelta(days=8))}
assert "2 alerts (only_here 1, heat 1), 1 acted on." in d13["2026-10-13"]["text"], d13["2026-10-13"]["text"]
rules_node = {d["period_start"]: d for d in learn.write_digests(qd, set(), {}, date(2026, 10, 14))}
assert "8 alerts (heat_stress_now 7, only_here 1), 0 acted on." in rules_node["2026-10-13"]["text"], "a rules node counts its rows, as before"
assert "rule_id NOT LIKE '\\\\_test/%%' AND l.rule_id <> 'gui/test'" in open("app/learn.py").read(), "a test alert is not an alert in the diary"
CL = SRC[SRC.index("def check_learn"):SRC.index("\n\n\n", SRC.index("def check_learn"))]
assert 'get("v") == learn.DIGEST_V' in CL and "DO UPDATE SET label = EXCLUDED.label" in CL, "an older digest is written again"
assert 'state.get("learned_on") == today' in CL and "SELECT current_date" in CL, "once a local day, so the morning finds yesterday"
empty = learn.digest("week", date(2026, 9, 28), date(2026, 10, 5), {}, [], [], None)
assert empty["text"] == "Week of 28 September 2026. No readings from this house's own sensors."
assert learn.search_terms("was this October smokier?") == "was | this | october | smokier"
assert learn.search_terms("a & b | c:* !! ') ;") == "", "nothing of tsquery's own syntax gets through"
assert learn.search_terms("asap ok") == "asap", "words of three letters or more"
LOG = []
main.q = main.household.q = lambda sql, *a: (LOG.append((sql, a)), [])[1]
settings._cache["rows"]["AGENT_PREFER"] = "private"
assert c.get("/learned/search?q=smoke", headers=ADMIN).status_code == 200
assert "to_tsquery('simple', %s)" in LOG[-1][0] and LOG[-1][1][0] == "smoke", "the words go as a parameter"
c.get("/learned/search?scale=month", headers=ADMIN)
assert "ORDER BY period_start DESC" in LOG[-1][0] and "to_tsquery" not in LOG[-1][0], "no words: the newest entries"
assert all("numbers" in sql for sql, _ in LOG[-2:]), "every entry carries its numbers, which Node's diary table reads"
assert c.get("/learned/search?scale=decade", headers=ADMIN).status_code == 422
assert c.get("/learned/search?q=x").status_code in (401, 403)
settings._cache["rows"]["AGENT_PREFER"] = "fallback"
assert c.get("/learned/search?q=smoke", headers={**ADMIN, "X-Agent": "agent"}).status_code == 403
print("digests: completed days, weeks, months and years only; the period's own hours; notes once with a count; search by words as a parameter, guarded")
# ---------------------------------------------------------------- who is in the house (step 4)
m = re.search(r"CREATE TABLE IF NOT EXISTS household \((.*?)\n\);", SQL, re.S)
assert m and "CHECK (id = 1)" in m.group(1) and "REVOKE ALL ON household FROM planetai_ro" in SQL, "one private row"
for road in ("def export", "def push_aggregates", "def aggregates"):
    body = SRC[SRC.index(road):SRC.index("\n\n\n", SRC.index(road))]
    assert "household" not in body, f"{road} must never name the household"
assert learn.for_whom("heat", {"older": True, "lungs": True}) == ["someone over 65"], "heat weighs on the old, not on lungs"
assert learn.for_whom("air-quality", {"older": True, "lungs": True}) == ["someone with asthma or another lung condition", "someone over 65"]
assert learn.for_whom("nearby", {"older": True}) == [] and learn.for_whom(None, {"older": True}) == []
assert learn.for_whom("heat", {"older": "yes"}) == [], "only a true is a yes"
ranked = learn.rank([{"kind": "worked", "issue": "air-quality", "key": "a"}, {"kind": "worked", "issue": "heat", "key": "h"},
                     {"kind": "usual", "issue": "air", "key": "u"}], {"under5": True, "pregnant": False})
assert [r["key"] for r in ranked] == ["u", "a", "h"] and ranked[1]["for_whom"] == ["a child under five"], ranked
assert [r["key"] for r in learn.rank([{"kind": "worked", "issue": "heat", "key": "h"}, {"kind": "worked", "issue": "air", "key": "a"}], {"lungs": True})] == ["a", "h"], \
    "within a kind, what matters here first"
KEPT = []
class HCur:
    def __enter__(self): return self
    def __exit__(self, *a): return False
    def execute(self, sql, params=()): KEPT.append(params[0].obj)
class HCon:
    def __enter__(self): return self
    def __exit__(self, *a): return False
    def cursor(self): return HCur()
main.db = main.household.db = lambda: HCon()
main.q = main.household.q = lambda sql, *a: [{"people": {"older": True}}] if "FROM household" in sql else []
settings._cache["rows"]["AGENT_PREFER"] = "private"
assert c.get("/household").status_code in (401, 403) and c.get("/household", headers={"Authorization": "Bearer act-tok"}).status_code == 401
h = c.get("/household", headers=ADMIN).json()
assert h["people"] == {"older": True} and set(h["choices"]) == set(learn.PEOPLE)
assert c.put("/household", json={"people": {"older": True, "lungs": False}}, headers=ADMIN).status_code == 200 and KEPT[-1] == {"older": True, "lungs": False}
for bad in ({"people": {"name": "Ana"}}, {"people": {"older": "yes"}}, {"people": {"older": 2}}, {"people": []}, {}):
    assert c.put("/household", json=bad, headers=ADMIN).status_code == 422, bad
assert c.put("/household", json={"people": {"older": True}}, headers={**ADMIN, "X-Agent": "agent"}).status_code == 403, "an agent never writes it"
settings._cache["rows"]["AGENT_PREFER"] = "fallback"
assert c.get("/household", headers={**ADMIN, "X-Agent": "agent"}).status_code == 403
settings._cache["rows"]["AGENT_PREFER"] = "private"
main.q = main.household.q = lambda sql, *a: [{"people": {"lungs": True}}] if "FROM household" in sql else [] if "FROM digests" in sql else [{"kind": "worked", "key": "air-quality/x", "issue": "air-quality", "status": "holding", "statement": "s"}]
assert c.get("/learned", headers=ADMIN).json()["learnings"][0]["for_whom"] == ["someone with asthma or another lung condition"]
print("household: yes or no for five, one private row, admin only, never written by an agent; learnings say who they matter to")
# ---------------------------------------------------------------- who, in the alert (Tomas: "yes, add it to the alerts")
# no sign of its own: the alert above it has one (one per message, 14 Oct)
assert learn.alert_line("heat", {"under5": True, "lungs": True}) == "This matters more here: you said there is a child under five."
assert learn.alert_line("air", {"lungs": True}, "id") == "Ini lebih penting di sini: Anda mengatakan ada seseorang dengan asma atau penyakit paru lain."
assert learn.alert_line("air-quality/indoor_pm25_high", {"older": True}, "es") == "Aquí importa más: dijiste que hay alguien mayor de 65 años."
assert learn.alert_line("heat", {"lungs": True}) == "" and learn.alert_line("nearby/x", {"older": True}) == "", "nobody at more risk, no line"
assert learn.alert_line("heat", {"older": True}, "fr").startswith("This matters"), "an unknown locale speaks English"
SENT = []
import channels  # noqa: E402 — notify and its channels live there since 22 Oct
channels.mesh_send = lambda text: SENT.append(("mesh", text))
channels.RETICULUM_URL = "http://reticulum"
channels.TG = lambda: ("123:abc", ["109"])
class P:
    def raise_for_status(self): return None
main.httpx.post = lambda url, json=None, timeout=None: (SENT.append(("tg" if "telegram" in url else "ret", json)), P())[1]
main.notify("act", "It is too hot.\nDrink water.", home="This matters more here: you said there is a child under five.")
tg = [j for k, j in SENT if k == "tg"][0]["text"]
assert tg == "🔴 It is too hot.\nDrink water.\n\nThis matters more here: you said there is a child under five.", tg
# one sign per message: a text with its own is not given the level's too (node #1 sent "ℹ️ 🌡️ It is hot inside")
SENT.clear()
main.notify("act", "📈 Smoke or dust in Kids.\nOpen the windows.")
assert [j for k, j in SENT if k == "tg"][0]["text"] == "📈 Smoke or dust in Kids.\nOpen the windows.", SENT
# the report's memory goes above its invitation, so the sign-off is the last thing read
SENT.clear()
main.notify("info", "🌡️ It is hot inside.\n\nNothing needs doing.\n\nAsk me anything.", home="📔 Yesterday.", home_before_last=True)
assert [j for k, j in SENT if k == "tg"][0]["text"] == "🌡️ It is hot inside.\n\nNothing needs doing.\n\n📔 Yesterday.\n\nAsk me anything.", SENT
SENT.clear()
assert not any("child" in str(x) for k, x in SENT if k != "tg"), "never the mesh or Reticulum"
main.q = main.household.q = lambda sql, *a: (_ for _ in ()).throw(RuntimeError("no table"))
assert main._alert_home("heat") == "", "a profile that cannot be read never stops an alert"
rr = SRC[SRC.index("def run_rules"):SRC.index("def _alert_home")]
assert 'home=_alert_home(rule["id"]) if level == "act" else ""' in rr and 'home=_alert_home(m.event.issue) if m.event.level == "act" else ""' in rr, \
    "both engines, act level only"
assert "INSERT INTO alerts (rule_id, sensor_id, level, text, buttons) VALUES (%s,%s,%s,%s,%s)" in rr and "_alert_home" not in rr.split("INSERT INTO alerts")[0][-400:], \
    "the stored alert text, which /alerts serves, never carries it"
print("alerts: act-level heat and air say who here they matter to, in the household's language, on Telegram only")
# ---------------------------------------------------------------- the house's counts stay with the house
# A readout (/stats) answers `private` rows to the household's own tokens or this machine, never to anyone the page
# answers at SHARE_LEVEL=open, nor to a parent's or a backup's token.
SQLS = []
main.q = main.household.q = lambda sql, *a: (SQLS.append(sql), [])[1]
settings._cache["rows"].update(SHARE_LEVEL="open", ACT_TOKEN="act-tok", AGG_TOKEN="agg-tok")
for hdr, private in (({}, False), ({"Authorization": "Bearer agg-tok"}, False), ({"Authorization": "Bearer act-tok"}, True), (ADMIN, True)):
    SQLS.clear()
    assert c.get("/stats", headers=hdr).status_code == 200, hdr
    assert ("role = 'private'" not in SQLS[0]) == private, (hdr, SQLS[0])
SQLS.clear()
assert c.get("/stats", headers={**ADMIN, "X-Agent": "agent"}).status_code == 200 and "role = 'private'" in SQLS[0], "never an agent"
print("readouts: the house's private counts to its own tokens and this machine, not to the network, a parent or an agent")
# ---------------------------------------------------------------- the morning (Tomas, 14 Oct: on by default)
mp = lambda d, push="all": [(sc, st.isoformat()) for sc, st in learn.morning_periods(d, push)]  # noqa: E731
assert mp(date(2026, 10, 15)) == [("day", "2026-10-14")], "an ordinary day: yesterday"
assert mp(date(2026, 10, 19)) == [("day", "2026-10-18"), ("week", "2026-10-12")], "a Monday: yesterday and last week"
assert mp(date(2027, 1, 1)) == [("day", "2026-12-31"), ("month", "2026-12-01"), ("year", "2026-01-01")], "1 January: the year too"
assert mp(date(2026, 10, 15), "week") == [] and mp(date(2026, 10, 19), "week") == [("week", "2026-10-12")]
assert mp(date(2027, 1, 1), "off") == [], "off is off"
txt = learn.morning(["Wednesday 14 October 2026. PM2.5 inside averaged 20.0."], [{"statement": "Acted on 6 times: …", "status": "holding"},
                    {"statement": "This alert no longer sends here.", "status": "gone"}])
assert txt == ("📔 Wednesday 14 October 2026. PM2.5 inside averaged 20.0.\n\nWhat the node learned, changed today:\n"
               "• Acted on 6 times: …\n• This alert no longer sends here. (gone)"), txt
assert learn.morning([], []) == "", "nothing to say, nothing said"
cut = learn.morning(["a" * 300, "b" * 300], [], "es", room=400)
assert cut.startswith("📔 aaa") and "bbb" not in cut and cut.endswith("… el resto con /learned") and len(cut) <= 400, "what does not fit is left for /learned"


class Cur:
    def __init__(self, sent_today=False, have_yesterday=True):
        self.sent, self.have, self.sql = sent_today, have_yesterday, []
    def execute(self, sql, args=()):
        self.sql.append((sql, args))
    def fetchone(self):
        return {"?": 1} if self.sent and "FROM reports" in self.sql[-1][0] else None
    def fetchall(self):
        last = self.sql[-1][0]
        if "FROM digests" in last:
            return [{"scale": "day", "period_start": date(2026, 10, 18), "text": "Sunday 18 October 2026. Calm."},
                    {"scale": "week", "period_start": date(2026, 10, 12), "text": "Week of 12 October 2026. Smoky."}][0 if self.have else 1:]
        return [{"kind": "worked", "key": "heat/events", "issue": "heat", "status": "holding", "statement": "Acted on 5 times: cooler."}]


main.q = main.household.q = lambda sql, *a: [{"people": {}}]
settings._cache["rows"]["LEARN_PUSH"] = "all"
MON = datetime(2026, 10, 19, 6)
m = main._morning(Cur(), MON, 900)
assert m.startswith("📔 Sunday 18 October 2026. Calm.\n\n📔 Week of 12 October 2026. Smoky.\n\nWhat the node learned") and "cooler" in m, m
assert main._morning(Cur(sent_today=True), MON, 900) == "", "one report a day carries it, whatever restarts"
assert main._morning(Cur(have_yesterday=False), MON, 900) == "", "yesterday not written yet: the next report carries it"
settings._cache["rows"]["LEARN_PUSH"] = "off"
assert main._morning(Cur(), MON, 900) == ""
settings._cache["rows"]["LEARN_PUSH"] = "all"
RR = SRC[SRC.index("def run_report"):SRC.index("def _morning")]
assert 'notify("info", text, home=memory, home_before_last=True)' in RR and 'packs.emit("on_alert", "info", text, None)' in RR, "Telegram alone carries the memory"
assert "text, text, not quiet" in RR and "bool(memory)" in RR, "the stored report is the report; it only says it carried the memory"
assert 'memory = "" if quiet else _morning(' in RR, "a held report carries nothing; the next one sent does"
assert "status_since = CASE WHEN learnings.status IS DISTINCT FROM EXCLUDED.status THEN current_date" in SRC
BOT = open("app/agent_loop.py").read()
assert '{"scale": scale} if scale else' in BOT, "/learned week asks for the newest of that size, no model"
print("morning: yesterday, Monday's week, the 1st's month, 1 January's year, what changed; once a day, Telegram only, on by default")
print("learned: every check passed")
