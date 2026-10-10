"""The event engine (docs/SPEC_alerts.md §4): one event per issue per house; open, escalate, match, clear; quiet
hours send only danger; a daily ceiling outside danger. Pure: no database, a clock passed in.
Run: PYTHONPATH=app python3 tests/test_events.py
"""
import datetime as dt

import events as E

T0 = dt.datetime(2026, 9, 25, 9, 0, tzinfo=dt.timezone(dt.timedelta(hours=8)))
POL = E.Policy(quiet=(22, 6), max_per_day=4, alert_level="act")


def c(room, kind="sustained", value=36.0, over=True, issue="heat", sensor=None, line=35.0):
    return E.Candidate(rule_id=f"heat/heat_{kind}", issue=issue, kind=kind, level="act",
                       sensor_id=sensor or f"sc-{room}", room=room, value=value, line=line, over=over)


def at(minutes):
    return T0 + dt.timedelta(minutes=minutes)


# one story for three rooms
s = E.MemoryStore()
m = E.step(at(0), [c("K"), c("L"), c("S")], s, POL)
assert [x.reason for x in m] == ["open"] and m[0].send, m
assert m[0].event.rooms == {"K", "L", "S"}, m[0].event.rooms
print("  three rooms at once open one heat event and send one message")

# the same condition a minute later updates silently
assert E.step(at(1), [c("K"), c("L")], s, POL) == []
print("  rows that match an open event send nothing")

# a rule row below the line (over=False) keeps the event alive but never opens one
s2 = E.MemoryStore()
assert E.step(at(0), [c("K", over=False, value=34.5)], s2, POL) == [] and s2.open_events() == []
print("  a margin row (over=False) does not open an event")

# escalation: a climb in kind, not sooner than ESCALATE_GAP, except danger
m = E.step(at(30), [c("K", kind="unusual")], s, POL)
assert m == [], "unusual (rank 1) is below the open sustained (rank 2): no climb"
m = E.step(at(60), [c("K", kind="danger", value=40.5)], s, POL)
assert [x.reason for x in m] == ["escalate"] and m[0].send, "danger always escalates, inside the gap"
print("  a climb to danger sends at once; other climbs wait ESCALATE_GAP")

# clearing: no candidate for CLEAR_AFTER closes the event, with one all-clear because it had been sent
assert E.step(at(60 + 29), [], s, POL) == []          # last seen at minute 60: 29 minutes is not yet 30
m = E.step(at(60 + 30), [], s, POL)
assert [x.reason for x in m] == ["clear"] and m[0].send and s.open_events() == [], m
print("  thirty minutes without a row clears it, with one all-clear")

# a margin row holds an open event open
s3 = E.MemoryStore()
E.step(at(0), [c("K")], s3, POL)
E.step(at(40), [c("K", over=False, value=34.6)], s3, POL)
assert s3.open_events(), "a row inside the margin keeps the event open"
print("  the margin is hysteresis: inside it an open event stays open")

# quiet hours: only danger sends; others are held for the morning
night = T0.replace(hour=2)
q = E.MemoryStore()
m = E.step(night, [c("K")], q, POL)
assert m[0].send is False and m[0].held == "quiet", m
m = E.step(night, [c("X", kind="danger", value=41, issue="air", sensor="sc-x")], q, POL)
assert m[0].send is True, "danger sends in quiet hours"
print("  at 02:00 a sustained event is held for the morning; danger is sent")

# the daily ceiling counts sends outside danger, per local day
d = E.MemoryStore()
sent = 0
for i, issue in enumerate(["heat", "air", "land", "coast", "water"]):
    for x in E.step(at(i * 5), [c("K", issue=issue, sensor=f"s{i}")], d, POL):
        sent += x.send
        if i == 4:
            assert not x.send and x.held == "ceiling", x
assert sent == 4, sent
print("  the fifth non-danger push of the day is held: ceiling")

# ALERT_LEVEL: a warn event is recorded, and sent only when ALERT_LEVEL allows warn
w = E.MemoryStore()
m = E.step(at(0), [E.Candidate("air-quality/air_spike", "air", "spike", "warn", "s", "K", 40, 12, True)], w, POL)
assert m[0].send is False and m[0].held == "level", m
print("events: one story per issue, silent matches, hysteresis, quiet hours, a ceiling, ALERT_LEVEL")

# Fix round 1: level climbing
# test a: warn spike opens (held 'level' with ALERT_LEVEL=act), later a danger row at act → message sent, event level 'act'
warn_store = E.MemoryStore()
m = E.step(at(0), [E.Candidate("air-quality/air_spike", "air", "spike", "warn", "s", "K", 40, 12, True)], warn_store, POL)
assert m[0].send is False and m[0].held == "level" and warn_store.open_events()[0].level == "warn", m
m = E.step(at(10), [E.Candidate("air-quality/air_danger", "air", "danger", "act", "s", "K", 130, 125, True)], warn_store, POL)
assert [x.reason for x in m] == ["escalate"] and m[0].send and m[0].event.level == "act", m
assert warn_store.open_events()[0].level == "act", "event level raised to act"
print("  warn spike opens (held), danger row escalates and raises event level to act")

# test b: unusual opens and sends at minute 0; a sustained row at minute 60 → no message; the same sustained row at minute 0+180 (ESCALATE_GAP) → one 'escalate' sent
unusual_store = E.MemoryStore()
m = E.step(at(0), [c("K", kind="unusual", value=33.0)], unusual_store, POL)
assert [x.reason for x in m] == ["open"] and m[0].send, "unusual opens and sends"
m = E.step(at(60), [c("K", kind="sustained", value=35.5)], unusual_store, POL)
assert m == [], "sustained at minute 60: inside ESCALATE_GAP, no escalate"
m = E.step(at(180), [c("K", kind="sustained", value=35.5)], unusual_store, POL)
assert [x.reason for x in m] == ["escalate"] and m[0].send, "sustained at minute 180: outside ESCALATE_GAP, escalate sent"
print("  unusual opens; sustained inside gap → no msg; sustained at gap boundary → escalate")

# test c: heat opens at 36 and sends; 38.5 at minute 60 → none (inside ESCALATE_GAP); still 38.5 at minute 180 → 'escalate' (worse by ≥2 vs told_peak 36)
value_store = E.MemoryStore()
m = E.step(at(0), [c("K", value=36.0)], value_store, POL)
assert [x.reason for x in m] == ["open"] and m[0].send, "heat opens at 36"
m = E.step(at(60), [c("K", value=38.5)], value_store, POL)
assert m == [], "38.5 at minute 60: 2.5 delta but inside gap, no escalate"
m = E.step(at(180), [c("K", value=38.5)], value_store, POL)
assert [x.reason for x in m] == ["escalate"] and m[0].send, "38.5 at minute 180: ≥2 delta and outside gap, escalate"
print("  heat opens at 36; value climbs to 38.5: inside gap → no msg; at gap boundary → escalate")

# test d: sustained event sent by day, clearing at 02:00 → reason 'clear', send False, held 'quiet'; danger event clearing at 02:00 → also held 'quiet'
clear_store = E.MemoryStore()
m = E.step(at(0), [c("K")], clear_store, POL)
assert m[0].send, "heat opens and sends at 09:00"
# clear at next day 02:00 + CLEAR_AFTER (no candidates for 30 min)
night_clear = T0.replace(day=26, hour=2) + dt.timedelta(minutes=30)  # next day 02:30
m = E.step(night_clear, [], clear_store, POL)
assert [x.reason for x in m] == ["clear"] and m[0].send is False and m[0].held == "quiet", m
# danger at 02:00 clearing
danger_store = E.MemoryStore()
m = E.step(at(0), [c("K", kind="danger", value=41)], danger_store, POL)
assert m[0].send, "danger opens and sends"
m = E.step(night_clear, [], danger_store, POL)
assert m[0].reason == "clear" and m[0].send is False and m[0].held == "quiet", "danger all-clear held in quiet hours"
print("  all-clear at 02:00 held 'quiet', regardless of kind")

# test e: after four sends today (ceiling reached), an all-clear for one of them is still sent
ceiling_store = E.MemoryStore()
for i, issue in enumerate(["heat", "air", "land", "coast"]):
    m = E.step(at(i * 5), [c("K", issue=issue, sensor=f"s{i}")], ceiling_store, POL)
    assert m[0].send, f"send {i+1} of 4 allowed"
m = E.step(at(20), [c("K", issue="heat", sensor="s0")], ceiling_store, POL)
assert m == [], "heat row matches open, silent"
m = E.step(at(50 + 30), [], ceiling_store, POL)  # CLEAR_AFTER after the last seen
heat_clears = [x for x in m if x.event.issue == "heat"]
assert heat_clears[0].send is True and heat_clears[0].held is None, "all-clear sent despite ceiling"
print("  all-clear sends even when ceiling is reached")

# test f: after an event clears, a new over row for the same issue opens a NEW event (new id) with an 'open' message
reopen_store = E.MemoryStore()
m = E.step(at(0), [c("K")], reopen_store, POL)
first_id = m[0].event.id
m = E.step(at(60 + 30), [], reopen_store, POL)
assert m[0].event.id == first_id and m[0].event.cleared_at is not None, "first event clears"
m = E.step(at(100), [c("K")], reopen_store, POL)
assert [x.reason for x in m] == ["open"] and m[0].event.id != first_id, "new open creates new id"
print("  after clear, new over row opens NEW event with different id")

# Fix round 2: level rise is escalation; told_held gates the gap
# test: air spike warn opens (held 'level') at minute 0; act unusual air at minute 5 → escalate sent, level act
level_esc_store = E.MemoryStore()
m = E.step(at(0), [E.Candidate("air-quality/air_spike", "air", "spike", "warn", "s", "K", 40, 12, True)], level_esc_store, POL)
assert [x.reason for x in m] == ["open"] and m[0].send is False and m[0].held == "level", "spike warn opens, held"
assert level_esc_store.open_events()[0].told_held == "level", "told_held tracks the held message"
m = E.step(at(5), [E.Candidate("air-quality/air_unusual", "air", "unusual", "act", "s", "K", 37, 30, True)], level_esc_store, POL)
assert [x.reason for x in m] == ["escalate"] and m[0].send is True, "level rise escalates immediately (held 'level' doesn't start gap)"
assert m[0].event.level == "act", "level is raised to act"
print("  held 'level' doesn't start gap; level rise (warn→act) escalates at minute 5, sent")

# test: spike warn at 60 and spike act at 50 in one step → level is act
multi_level_store = E.MemoryStore()
m = E.step(at(0), [
    E.Candidate("air-quality/air_spike", "air", "spike", "warn", "s1", "K", 40, 12, True),
    E.Candidate("air-quality/air_spike", "air", "spike", "act", "s2", "L", 50, 12, True)
], multi_level_store, POL)
assert [x.reason for x in m] == ["open"] and m[0].event.level == "act", "level climbs to highest of all over-candidates"
print("  one step: spike/warn + spike/act → level is act (not just top)")

# Air danger re-sends only when its value doubles since the last message, and never within DANGER_REPEAT_GAP. A
# cooking peak climbing 131 -> 1033 re-sent every five minutes on node #1's replay: 9 extra pushes in a month.
d = E.MemoryStore()
air_d = lambda v: E.Candidate("air-quality/air_extreme", "air", "danger", "act", "s", "K", v, 125.5, True)
assert [x.reason for x in E.step(at(0), [air_d(131)], d, POL)] == ["open"]
assert E.step(at(5), [air_d(250)], d, POL) == [], "not doubled: no re-send"
assert E.step(at(10), [air_d(300)], d, POL) == [], "doubled, but inside the 30-min floor"
m = E.step(at(31), [air_d(300)], d, POL)
assert [x.reason for x in m] == ["escalate"] and m[0].send, m
assert E.step(at(40), [air_d(1033)], d, POL) == [], "doubled again, inside the floor"
assert [x.reason for x in E.step(at(62), [air_d(1033)], d, POL)] == ["escalate"]
print("  air danger re-sends only when its value doubles, never within 30 min")
# heat danger keeps its +2 °C step, behind the same floor; climbing INTO danger stays immediate (tested above)
hd = E.MemoryStore()
E.step(at(0), [c("K", kind="danger", value=40.5)], hd, POL)
assert E.step(at(5), [c("K", kind="danger", value=43.0)], hd, POL) == [], "heat danger +2.5 inside the floor"
assert [x.reason for x in E.step(at(31), [c("K", kind="danger", value=43.0)], hd, POL)] == ["escalate"]
print("  heat danger keeps its +2 °C step behind the same 30-min floor")
