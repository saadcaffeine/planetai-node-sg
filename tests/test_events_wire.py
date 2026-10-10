"""The events block of GET /issues, without a database (docs/SPEC_dashboard_events.md §3.1).
The same rows as a live node hands them over (datetimes) and as a capture holds them (ISO strings) must give one block.
Run: PACKS_DIR=packs PYTHONPATH=app python3 tests/test_events_wire.py
"""
import datetime as dt
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.chdir(ROOT)
os.environ.setdefault("PACKS_DIR", "packs")
os.environ.setdefault("DATABASE_URL", "postgresql://x:x@127.0.0.1:1/x")
sys.path.insert(0, str(ROOT / "app"))
import events_wire as W  # noqa: E402

UTC = dt.timezone.utc
BALI = dt.timezone(dt.timedelta(hours=8))
NOW = dt.datetime(2026, 10, 5, 7, 0, tzinfo=UTC)            # 15:00 in Bali
DECL = {"heat": {"metric": "apparent", "line": {"value": 35.0}}, "air": {"metric": "pm25", "line": {"value": 15.0}}}
H = dt.timedelta(hours=1)


def ev(i, issue, kind, opened, cleared=None, action_id=None):
    return {"id": i, "issue": issue, "kind": kind, "level": "act", "opened_at": opened, "last_seen_at": opened,
            "cleared_at": cleared, "peak": 35.8, "rooms": ["L ROOM", "K ROOM"], "places": ["inside"],
            "action_id": action_id}


EVENTS = [ev(1, "heat", "sustained", NOW - 2 * H, action_id="heat/open_up"),
          ev(2, "air", "danger", NOW - H),
          ev(3, "heat", "unusual", NOW - 3 * H),
          ev(4, "air", "spike", NOW - 20 * H, cleared=NOW - 19 * H),          # 20:00 Bali yesterday: not today
          ev(5, "heat", "sustained", NOW - 8 * H, cleared=NOW - 5 * H),       # 10:00 Bali today
          ev(6, "air", "spike", NOW - 9 * 24 * H, cleared=NOW - 8 * 24 * H),  # older than 7 days: dropped
          ev(7, "air", "spike", NOW - 10 * H, cleared=NOW - 4 * H),           # opened before 5, cleared after: reveals sort by clear
          ev(8, "heat", "sustained", NOW - 12 * H, cleared=NOW - 8 * H)]      # 23:00 UTC on the 4th, 07:00 Bali on the 5th
MESSAGES = [{"event_id": 1, "ts": NOW - 2 * H, "text": "Hot inside.\n\n👉 Open up now: outside is 29.1 °C.",
             "sent": True, "action_id": "heat/open_up"},
            {"event_id": 1, "ts": NOW - H, "text": "Still hot inside.\n\n👉 Open up now: outside is 28.0 °C.",
             "sent": False, "action_id": "heat/open_up"},
            {"event_id": 5, "ts": NOW - 5 * H, "text": "Cooler now.", "sent": True, "action_id": None}]
ANSWERS = [{"event_id": 1, "ts": NOW - 90 * dt.timedelta(minutes=1), "stage": "acknowledged", "actor": "tomas"},
           {"event_id": 2, "ts": NOW - 30 * dt.timedelta(minutes=1), "stage": "acknowledged", "actor": "ana"},
           {"event_id": 5, "ts": NOW - 6 * H, "stage": "acted", "actor": "tomas", "note": "opened the west side"}]
COVERED = {1: [578, 571], 2: [], 3: [], 4: [], 5: [500], 7: [520], 8: []}
CONTEXTS = {1: {"inside_temp": 35.8, "outside_temp": 29.1, "outside_pm25": 12.0, "outside_source": "outside",
                "usual": 33.4},
            2: {"inside_pm25": 140.0, "outside_pm25": 12.0, "outside_source": "the forecast model", "usual": 9.0},
            3: {"usual": None}}


def iso(rows):
    return [{k: (v.isoformat() if isinstance(v, dt.datetime) else v) for k, v in r.items()} for r in rows]


live = W.build("events", EVENTS, MESSAGES, ANSWERS, COVERED, CONTEXTS, DECL, "en", NOW, BALI)
captured = W.build("events", iso(EVENTS), iso(MESSAGES), iso(ANSWERS), COVERED, CONTEXTS, DECL, "en", NOW, BALI)
assert json.dumps(live, sort_keys=True) == json.dumps(captured, sort_keys=True), "live and captured rows differ"
json.dumps(live)                                            # every value is JSON: no datetime, no set
print("  a live row (datetimes) and a captured row (ISO strings) give one block, and it is all JSON")

assert [e["id"] for e in live["open"]] == [2, 1, 3], "danger first, then sustained, then unusual"
assert [e["id"] for e in live["recent"]] == [7, 5, 8, 4], "cleared in 7 days, newest clear first; older dropped"
print("  open: danger > sustained > unusual; recent: 7 days, newest clear first")

one = live["open"][1]
assert one["action"] == {"id": "heat/open_up", "text": "Open up now: outside is 28.0 °C."}, one["action"]
assert one["message"]["text"].startswith("Still hot") and one["message"]["sent"] is False, one["message"]
assert one["line"] == 35.0 and one["rooms"] == ["K ROOM", "L ROOM"] and one["alerts"] == [571, 578]
assert one["context"] == {"usual": 33.4, "outside": 29.1, "outside_metric": "temp", "outside_from": "outside"}
assert live["open"][0]["context"]["outside"] == 12.0 and live["open"][0]["context"]["outside_metric"] == "pm25"
assert live["open"][0]["context"]["outside_from"] == "outside", "outside PM2.5 always came from a sensor, whatever outside_source says"
assert live["open"][2]["context"]["outside"] is None and live["open"][2]["context"]["outside_from"] is None
assert live["open"][2]["action"] is None and live["open"][2]["message"] is None
print("  the action is the line as sent; the message is the latest; heat's outside is the air temperature")

held = (NOW - 90 * dt.timedelta(minutes=1) + 3 * H).isoformat()
assert one["answer"] == {"stage": "acknowledged", "actor": "tomas", "ts": (NOW - 90 * dt.timedelta(minutes=1)).isoformat(),
                         "held_until": held, "note": None}, one["answer"]
assert live["open"][0]["answer"]["held_until"] is None, "Not now never holds a danger event"
assert live["recent"][1]["answer"]["note"] == "opened the west side", \
    "the household's own words ride the answer to the card"
assert live["recent"][1]["cleared_after_min"] == 60, live["recent"][1]
assert "context" not in live["recent"][1]
print("  Not now holds for 3 h except at danger; a Done followed by a clear says how long it took")

assert live["cleared_today"] == 3 and live["last_cleared"] == {"issue": "air", "ts": (NOW - 4 * H).isoformat()}
utc = W.build("events", EVENTS, MESSAGES, ANSWERS, COVERED, CONTEXTS, DECL, "en", NOW, UTC)
assert utc["cleared_today"] == 2, "event 8 cleared on the 4th in UTC: the local day is what counts"
print("  cleared today counts the node's local day, not UTC's")

assert live["buttons"] == {"done": "Done", "not_now": "Not now", "doesnt_fit": "Doesn't fit"}
assert W.build("events", [], [], [], {}, {}, DECL, "xx", NOW)["buttons"]["done"] == "Done", "unknown locale: en"
rules = W.build("rules", EVENTS, MESSAGES, ANSWERS, COVERED, CONTEXTS, DECL, "en", NOW, BALI)
assert rules["open"] == [] and rules["engine"] == "rules" and len(rules["recent"]) == 4
assert W.engine_of("shadow") == "shadow" and W.engine_of("typo") == "rules" and W.engine_of(None) == "rules"
print("  on rules nothing is open (the engine is not running); a typo behaves as rules")

import contextlib  # noqa: E402

class FakeCur:
    """Answers live()'s reads in the order it makes them; `fail` names a statement that raises, as an unpopulated
    usual_by_hour does after a restart."""
    def __init__(self, fail=""):
        self.sql, self.fail, self.last = [], fail, ""
        self.connection = type("C", (), {"transaction": lambda s: contextlib.nullcontext()})()

    def execute(self, sql, args=()):
        self.sql.append(sql)
        self.last = sql
        if self.fail and self.fail in sql:
            raise RuntimeError("materialized view usual_by_hour has not been populated")

    def fetchone(self):
        if "current_setting" in self.last:
            return {"tz": "Asia/Makassar", "hour": 15}
        if "usual_by_hour" in self.last:
            return {"usual": 33.44}
        return {"inside_temp": 35.8, "inside_pm25": None, "outside_temp": 29.1, "outside_pm25": None,
                "outside_source": "outside"}

    def fetchall(self):
        if "FROM alert_events" in self.last:
            return [ev(1, "heat", "sustained", NOW - 2 * H, action_id="heat/open_up")]
        if "FROM alerts" in self.last:
            return [{"id": 578}]
        return []

os.environ["ALERT_ENGINE"] = "shadow"
got = W.live(FakeCur(), DECL, "en", NOW)
assert got["engine"] == "shadow" and [e["id"] for e in got["open"]] == [1], got
assert got["open"][0]["alerts"] == [578] and got["open"][0]["context"]["usual"] == 33.4, got["open"][0]
cold = W.live(FakeCur(fail="usual_by_hour"), DECL, "en", NOW)
assert cold["open"][0]["context"]["usual"] is None and cold["open"][0]["context"]["outside"] == 29.1, cold
print("  live: one read per table, alerts matched per event, a usual_by_hour that fails is null and costs nothing else")
import issues as I                # noqa: E402
from issues import engine          # noqa: E402


class Settings:
    def get(self, key, default=""):
        return default

    def num(self, key, default):
        return default


SNAP = json.loads((ROOT / "app/issues/fixtures/node1-2026-09-21d.json").read_text())
DECLS = I.load()
plain = engine.replay(json.loads(json.dumps(SNAP)), Settings(), DECLS)
assert plain["events"] is None, "a fixture from before v0.77 replays with no events block: the older-node state"
heroes = [k for k in plain["order"] if plain["issues"][k].get("hero")]
other = next(k for k in heroes if k != plain["headline"])          # an issue that does not lead on its own
asks = [a["id"] for v in plain["issues"].values() for a in (v.get("open_asks") or []) if a.get("id") is not None]
assert asks, "the 21d fixture has open asks; pick another fixture if it ever stops having them"
rule_of = {a["id"]: a["rule_id"] for v in plain["issues"].values() for a in (v.get("open_asks") or [])}
# Inject an event covering a non-owned ask to test that covered exclusion works on the events engine
non_owned = [a for a in asks if rule_of.get(a, "").split("/", 1)[0] not in ("heat", "air-quality")]
snap = json.loads(json.dumps(SNAP))
snap["issues"]["events"] = {"engine": "events", "buttons": {}, "recent": [], "cleared_today": 0, "last_cleared": None,
                            "open": [{"id": 9, "issue": other, "kind": "sustained", "opened_at": "2026-09-21T10:00:00+08:00",
                                      "alerts": non_owned[:1]}]}
led = engine.replay(snap, Settings(), DECLS)
assert led["headline"] == other and led["lead"] == {"issue": other, "by": "event"}, led["lead"]
# Events engine: uncovered_asks excludes covered asks AND the packs the engine replaced
expected_events = [a for a in asks if rule_of.get(a, "").split("/", 1)[0] not in ("heat", "air-quality") and a not in non_owned[:1]]
assert led["events"]["uncovered_asks"] == expected_events, (led["events"]["uncovered_asks"], expected_events)
assert led["headline_rule"]["en"].startswith("An open event leads")
# Rules engine: uncovered_asks excludes only covered asks, not owned packs (original behavior)
snap["issues"]["events"]["engine"] = "rules"
led_rules = engine.replay(snap, Settings(), DECLS)
expected_rules = [a for a in asks if a not in non_owned[:1]]
assert sorted(led_rules["events"]["uncovered_asks"]) == sorted(expected_rules), (sorted(led_rules["events"]["uncovered_asks"]), sorted(expected_rules))
print("  replay: a captured block leads the headline with its event; on events, uncovered_asks excludes covered and replaced-pack alerts; on rules, only covered")

out = {"air": {"hero": {"sign": "a"}, "state": "act", "moved": 0.9}, "heat": {"hero": {"sign": "h"}, "state": "quiet", "moved": 0.0}}
assert engine._lead(out, ["air", "heat"], {"open": [{"issue": "heat"}]}) == {"issue": "heat", "by": "event"}
assert engine._lead(out, ["air", "heat"], {"open": []})["by"] == "state", "nothing open: today's rule"
assert engine._lead(out, ["air", "heat"], {"open": [{"issue": "coast"}]})["issue"] == "air", "no hero: cannot lead"
print("  _lead: an open event's issue leads; with none open, or none that can lead, today's rule stands")

snap2 = json.loads(json.dumps(SNAP))
snap2["issues"]["events"] = {"engine": "events", "buttons": {}, "open": [], "recent": [], "cleared_today": 0,
                             "last_cleared": None}
ev = engine.replay(snap2, Settings(), DECLS)
owned = ("heat/", "air-quality/")
assert not [i for i in ev["events"]["uncovered_asks"] if rule_of[i].startswith(owned)], ev["events"]["uncovered_asks"]
snap2["issues"]["events"]["engine"] = "rules"
assert sorted(engine.replay(snap2, Settings(), DECLS)["events"]["uncovered_asks"]) == sorted(rule_of), "rules: all"
print("  uncovered_asks: on shadow and events, the replaced packs' old alerts are not asks; on rules they are")

def _block(engine_name, open_=(), recent=()):
    return {"engine": engine_name, "buttons": {"done": "Done", "not_now": "Not now", "doesnt_fit": "Doesn't fit"},
            "open": list(open_), "recent": list(recent), "cleared_today": 0, "last_cleared": None}


def _replay(block):
    s = json.loads(json.dumps(SNAP))
    s["issues"]["events"] = block
    return engine.replay(s, Settings(), DECLS)


OWNED = ("heat/", "air-quality/")
base = engine.replay(json.loads(json.dumps(SNAP)), Settings(), DECLS)
all_asks = {k: [a["rule_id"] for a in (v.get("open_asks") or [])] for k, v in base["issues"].items()}
assert any(r.startswith(OWNED) for rs in all_asks.values() for r in rs), "21d has old heat/air asks to filter"
for eng in ("events", "shadow"):
    got = _replay(_block(eng))
    kept = [a["rule_id"] for v in got["issues"].values() for a in (v.get("open_asks") or [])]
    assert not [r for r in kept if r.startswith(OWNED)], (eng, kept)
    assert sorted(kept) == sorted(r for rs in all_asks.values() for r in rs if not r.startswith(OWNED)), eng
ruled = _replay(_block("rules"))
assert {k: [a["rule_id"] for a in (v.get("open_asks") or [])] for k, v in ruled["issues"].items()} == all_asks, \
    "on rules, open_asks is exactly today's"
err = _replay({**_block("events"), "error": "x"})
assert {k: [a["rule_id"] for a in (v.get("open_asks") or [])] for k, v in err["issues"].items()} == all_asks, \
    "an unreadable events block falls back to the alert cards: every ask stays"
print("  open_asks: on shadow and events the replaced packs' alerts are not asks; on rules and with no block, unchanged")

AS_OF = dt.datetime.fromisoformat(SNAP["as_of"])
iso = lambda d: (AS_OF - d).isoformat()            # noqa: E731


def ev(kind="sustained", level="act", answer=None, opened=dt.timedelta(hours=1)):
    return {"id": 9, "issue": "heat", "kind": kind, "level": level, "opened_at": iso(opened), "cleared_at": None,
            "alerts": [], "answer": answer}


def heat(block):
    v = _replay(block)["issues"]["heat"]
    return v["state"], v["reason"]["code"], v["reason_text"]["en"]


st, code, _ = heat(_block("events", [ev()]))
assert (st, code) == ("act", "event_open"), (st, code)
ack = {"stage": "acknowledged", "actor": "Tomas Diez", "ts": iso(dt.timedelta(minutes=10)), "held_until": None}
st, code, said = heat(_block("events", [ev(answer=ack)]))
assert (st, code) == ("notable", "event_answered") and "Tomas Diez" in said and "Not now" in said, (st, code, said)
st, code, _ = heat(_block("events", [ev(kind="danger", answer=ack)]))
assert (st, code) == ("act", "event_open"), "an answered danger event stays act"
st, code, _ = heat(_block("events", [ev(kind="spike", level="warn")]))
assert (st, code) == ("notable", "event_open"), "the warn-level spike is notable"
gone = dict(ev(), cleared_at=iso(dt.timedelta(hours=3)))
st, code, said = heat(_block("events", recent=[gone]))
assert (st, code) == ("notable", "event_cleared") and said, (st, code)
old = dict(ev(), cleared_at=iso(dt.timedelta(hours=30)))
assert heat(_block("events", recent=[old]))[1] != "event_cleared", "a clear older than 24 h is not notable"
assert _replay(_block("rules", [ev()]))["issues"]["heat"]["reason"]["code"] != "event_open", "rules: today's state"
led = _replay(_block("events", [ev(answer=ack)]))
assert led["lead"] == {"issue": "heat", "by": "event"}, "an answered open event still leads"
for loc in ("en", "id", "es"):
    assert "{" not in _replay(_block("events", [ev(answer=ack)]))["issues"]["heat"]["reason_text"][loc], loc
naive = dict(ev(), cleared_at=(AS_OF.replace(tzinfo=None) - dt.timedelta(hours=3)).isoformat())
st, code, _ = heat(_block("events", recent=[naive]))
assert (st, code) == ("notable", "event_cleared"), "a naive cleared_at (no offset) counts as UTC and does not raise"
print("  state: an open act event is act until answered (danger stays act); answered or a spike is notable; "
      "a clear within a day is notable; rules unchanged")

print("events_wire: the open events, their actions as sent, answers and holds, the local day")
