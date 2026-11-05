"""Actions are chosen from what is happening, one per event (docs/SPEC_alerts.md §5).
Run: PYTHONPATH=app python3 tests/test_actions.py
"""
import datetime as dt
import re
from pathlib import Path

import yaml

import actions as A
import events as E

ROOT = Path(__file__).resolve().parent.parent
heat = yaml.safe_load((ROOT / "packs/heat/issue.yml").read_text())
air = yaml.safe_load((ROOT / "packs/air-quality/issue.yml").read_text())

night = dict(inside_temp=29.3, outside_temp=24.9, outside_pm25=10, inside_pm25=8, hour=20, home_has=set(),
             where={"inside"}, kind="sustained")
assert A.choose(heat["actions"], night)["id"] == "heat/open_up", "outside 4.4 °C cooler and clean: open up"
noon = dict(night, outside_temp=32.3, inside_temp=30.2, hour=13)
assert A.choose(heat["actions"], noon)["id"] == "heat/keep_shut_shaded", "outside hotter: keep it shut"
smoky = dict(night, outside_pm25=60)
assert A.choose(heat["actions"], smoky)["id"] != "heat/open_up", "never open up into smoke"
print("  heat: open up when outside is cooler and clean, keep shut when it is hotter, never into smoke")

cook = dict(where={"inside"}, inside_pm25=59, outside_pm25=12, home_has={"purifier"}, kind="spike", hour=12)
assert A.choose(air["actions"], cook)["id"] == "air/ventilate_and_purify"
# an outdoor event has no indoor rooms of its own: events_pg.context() fills inside_* from the house-wide indoor
# mean, so production hands over inside_pm25 here (proven against Postgres in the Task 4 fix report)
bad_out = dict(cook, where={"outside"}, outside_pm25=80, inside_pm25=20)
assert A.choose(air["actions"], bad_out)["id"] == "air/keep_shut_purify"
none = dict(bad_out, home_has=set())
assert A.choose(air["actions"], none)["id"] == "air/keep_shut", "no purifier: do not suggest one"
print("  air: ventilate a kitchen spike, keep shut when outside is worse, never a purifier the home has not got")

assert not A.holds({"outside_cooler_by": 2}, dict(night, outside_temp=None)), "unknown context does not hold"
assert A.holds({"hour_from": 17, "hour_to": 8}, dict(night, hour=2)) and not A.holds({"hour_from": 17, "hour_to": 8}, dict(night, hour=12))
print("  when: an unknown value never holds; hour windows wrap midnight")

for bad in ({"hour_to": 8}, {"kind": "danger"}, {"where": ["inside"]}, {"outside_cooler_by": "2"}, {"outside_pm25_below": "35"},
            {"hour_from": "17", "hour_to": 8}, {"nonsense": 1}):
    assert not A.holds(bad, night), f"a malformed condition must not hold: {bad}"
assert A.choose([{"when": {}, "say": {"en": "x"}}], night) is None, "an action with no id is skipped"
print("  when: a half hour window, a wrong type, a string threshold and an unknown key never hold")

t0 = dt.datetime(2026, 9, 25, 20, 0)
e = E.Event(issue="heat", kind="sustained", level="act", opened_at=t0, last_seen_at=t0, peak=36.7, rooms={"K ROOM"})
text, aid = A.render(heat, E.Message(e, "open", True, None), night, "en")
assert "K ROOM" in text and text.count("\n") == 1 and aid == "heat/open_up", text
assert text == ("🥵 Hot for hours in K ROOM, longer than usual: it feels like 36.7 °C; this house's heat line is 35 °C feels-like."
                "\nOpen up now: outside is 24.9 °C and inside is 29.3 °C."), text
text_id, _ = A.render(heat, E.Message(e, "open", True, None), night, "id")
assert text_id != text, "id has its own sentence"
clear, aid2 = A.render(heat, E.Message(e, "clear", True, None), night, "en")
assert "\n" not in clear and aid2 is None, "an all-clear carries no action"
bare = E.Event(issue="heat", kind="unusual", level="info", opened_at=t0, last_seen_at=t0, peak=31.0, rooms={"K ROOM"})
no_tpl, aid3 = A.render({"name": heat["name"], "events": {}, "actions": []}, E.Message(bare, "open", True, None), night, "en")
assert no_tpl.startswith(heat["name"]["en"]) and "K ROOM" in no_tpl and not no_tpl.startswith("\n") and aid3 is None, no_tpl
print("  render: no template for the kind gives one line naming the issue and the rooms")

# The voice (design review of node #1, 14 Oct). Before: "📈 The air jumped in K ROOM - BAYU HOLES, L ROOM - Ai1 - SEEED
# OPEN: 48 µg/m³ PM2.5 — the WHO line is 15. Outside reads 11 µg/m³.\n\n👉 Open the side where it started and run the
# purifier for 30 min: outside is cleaner (11 µg/m³)." Words first, one reading, the line with its owner and unit, the
# outside said once, as the action's reason, and nothing about where it started (rooms are a sorted set).
import unicodedata                                                  # noqa: E402
kids = E.Event(issue="air", kind="spike", level="warn", opened_at=t0, last_seen_at=t0, peak=48.2, rooms={"Living Room", "Kids"})
said, _ = A.render(air, E.Message(kids, "open", True, None), dict(cook, outside_pm25=11), "en")
assert said == ("📈 Smoke or dust in Kids and Living Room: 48 µg/m³; the WHO line is 15 µg/m³."
                "\nOpen the windows and run the purifier for 30 minutes. Outside is cleaner, at 11 µg/m³."), said
# Urgent air names the EPA's 35.5, everyday air the WHO's 15 (Tomas, 14 Oct; audit, 15 Oct)
for kind in ("sustained", "danger"):
    for loc in ("en", "id", "es"):
        u, _ = A.render(air, E.Message(E.Event(issue="air", kind=kind, level="act", opened_at=t0, last_seen_at=t0,
                                               peak=48.2, rooms={"Kids"}), "open", True, None), cook, loc)
        assert "35.5 µg/m³" in u and "WHO" not in u and "OMS" not in u, (kind, loc, u)
for loc in ("en", "id", "es"):
    for key, issue, ctx in (("air", air, dict(cook, outside_pm25=11)), ("heat", heat, night)):
        for kind in issue["events"]:
            ev = E.Event(issue=key, kind=kind if kind != "clear" else "sustained", level="act", opened_at=t0,
                         last_seen_at=t0, peak=40.0, rooms={"Kids", "Studio"})
            m, _ = A.render(issue, E.Message(ev, "clear" if kind == "clear" else "open", True, None), ctx, loc)
            signs = [ch for ch in m if unicodedata.category(ch) == "So" and ch != "°"]
            assert len(signs) == 1 and m.startswith(signs[0]), f"{loc}/{key}/{kind}: one sign, first: {m}"
            assert "{" not in m and "—" not in m and "side where" not in m and "👉" not in m, (loc, kind, m)
            assert m.count(str(ctx["outside_pm25"]) + " µg/m³") <= 1, f"the outside is said once: {m}"
            assert not re.search(r"(?<![\d.])\d+(?:\.\d+)?(?!\d|[.:]\d|\s*(?:µg/m³|°C|minutes|menit|minutos|min\b))", m), f"a bare number: {m}"
            assert ("Kids" in m) and ("Studio" in m) and ("Kids, Studio" not in m), f"rooms joined in words: {m}"
print("  voice: words first, one reading with its unit, the line named with its unit, one sign, the outside said once")

for loc in ("en", "id", "es"):
    b = A.BUTTONS[loc]
    assert set(b) == {"done", "not_now", "doesnt_fit"} and all(isinstance(v, str) and v for v in b.values()), (loc, b)
assert A.BUTTONS["en"] == {"done": "Done", "not_now": "Not now", "doesnt_fit": "Doesn't fit"}
print("  buttons: Done / Not now / Doesn't fit in en, id and es, one table for the bot and the page")
print("actions: one action per event, chosen from the context; messages in three languages")
