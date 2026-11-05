"""The report the node writes itself, and the bundle it writes it from.

The fixture below is a real bundle, taken from a node seeded with eight days shaped like node #1: a kitchen that
cooks at six, a porch, a public reference down the road, a radio that stopped talking four days ago, and the
three model points. It is the ruler for everything downstream — the model's rewrite is checked against these
numbers and nothing else — so it is written out here in full rather than generated, and it is read by eye.
"""
import json, os, sys

os.environ.setdefault("DATABASE_URL", "postgresql://x/x")
os.environ.setdefault("NODE_TZ", "Asia/Makassar")
os.environ.setdefault("NODE_NAME", "bayu-2")
sys.path.insert(0, "app")

import report

# ---------------------------------------------------------------- the fixture: a pot on the stove, an hour ago
FIXTURE = {
    "meta": {"node": "bayu-2", "locale": "en", "tz": "Asia/Makassar", "local_time": "18:00",
             "local_date": "2026-09-07", "local_weekday": "Monday", "local_hour": 18,
             "window_hours": 6, "held_hours": 0, "folds_a_held_report": False, "truncated": 0},
    "series": [
        {"sensor_id": "sc-kitchen", "metric": "pm25", "name": "Bayu 2 - Kitchen", "local": True, "indoor": True,
         "kind": "sensor", "start": "2026-09-07T13:00:00+08:00", "end": "2026-09-07T17:00:00+08:00",
         "min": 5.4, "max": 206.3, "mean": 60.1, "n": 20, "trend": "falling", "notability": 12.4,
         "usual": 5.7, "baseline_days": 7},
        {"sensor_id": "sc-kitchen", "metric": "temp", "name": "Bayu 2 - Kitchen", "local": True, "indoor": True,
         "kind": "sensor", "start": "2026-09-07T13:00:00+08:00", "end": "2026-09-07T17:00:00+08:00",
         "min": 29.5, "max": 32.2, "mean": 30.9, "n": 20, "trend": "falling", "notability": -2.37,
         "usual": 31.0, "baseline_days": 7},
        {"sensor_id": "sc-porch", "metric": "pm25", "name": "Bayu 2 - Porch", "local": True, "indoor": False,
         "kind": "sensor", "start": "2026-09-07T13:00:00+08:00", "end": "2026-09-07T17:00:00+08:00",
         "min": 4.5, "max": 7.5, "mean": 5.8, "n": 20, "trend": "steady", "notability": -0.92,
         "usual": 6.0, "baseline_days": 7},
        {"sensor_id": "cams-point", "metric": "pm25_model", "name": "CAMS model point", "local": False,
         "indoor": False, "kind": "model", "start": "2026-09-07T15:00:00+08:00", "end": "2026-09-07T15:00:00+08:00",
         "min": 11.5, "max": 11.5, "mean": 11.5, "n": 1, "trend": "steady", "notability": -0.64,
         "usual": 12.2, "baseline_days": 7},
    ],
    "now": [
        {"sensor_id": "sc-kitchen", "name": "Bayu 2 - Kitchen", "metric": "pm25", "indoor": True, "local": True,
         "kind": "sensor", "last": 16.49, "mean_15m": 17.2, "mean_1h": 17.21, "silent_minutes": 2},
        {"sensor_id": "sc-kitchen", "name": "Bayu 2 - Kitchen", "metric": "temp", "indoor": True, "local": True,
         "kind": "sensor", "last": 29.53, "mean_15m": 29.6, "mean_1h": 29.77, "silent_minutes": 2},
        {"sensor_id": "sc-kitchen", "name": "Bayu 2 - Kitchen", "metric": "humidity", "indoor": True, "local": True,
         "kind": "sensor", "last": 66.12, "mean_15m": 66.4, "mean_1h": 67.91, "silent_minutes": 2},
        {"sensor_id": "sc-porch", "name": "Bayu 2 - Porch", "metric": "pm25", "indoor": False, "local": True,
         "kind": "sensor", "last": 7.27, "mean_15m": 7.1, "mean_1h": 6.45, "silent_minutes": 2},
        {"sensor_id": "bad-pa-1", "name": "Jimbaran PA", "metric": "pm25", "indoor": False, "local": False,
         "kind": "sensor", "last": 8.84, "mean_15m": 8.8, "mean_1h": 8.91, "silent_minutes": 2},
    ],
    "observations": [
        {"group": "satellite_air", "sensor_id": "cams-point", "metric": "pm25_model",
         "means": "PM2.5 the model estimates for the district, µg/m³", "value": 11.46, "day_ago": 12.13,
         "at": "2026-09-07T15:00:00+08:00"},
        {"group": "satellite_air", "sensor_id": "cams-point", "metric": "uv_index", "means": "UV index",
         "value": 7.78, "day_ago": 0.0, "at": "2026-09-07T15:00:00+08:00"},
        {"group": "sea", "sensor_id": "marine-point", "metric": "swell_height_m", "means": "swell height, m",
         "value": 1.87, "day_ago": 2.1, "at": "2026-09-07T15:00:00+08:00"},
        {"group": "weather", "sensor_id": "om-point", "metric": "precipitation", "means": "rain this hour, mm",
         "value": 0.0, "day_ago": 2.4, "at": "2026-09-07T15:00:00+08:00"},
    ],
    "alerts": [
        {"id": 1, "at": "2026-09-07T15:00:00+08:00", "rule": "air-quality/indoor_pm25_high",
         "sensor_id": "sc-kitchen", "level": "act",
         "line": "🏠😷 The air inside at Bayu 2 - Kitchen is unhealthy right now.", "acted": False},
        {"id": 2, "at": "2026-09-07T15:00:00+08:00", "rule": "air-quality/indoor_spike",
         "sensor_id": "sc-kitchen", "level": "warn",
         "line": "📈🏠 Something just changed the air at Bayu 2 - Kitchen.", "acted": False},
    ],
    "open_act": [{"id": 1, "at": "2026-09-07T15:00:00+08:00", "rule": "air-quality/indoor_pm25_high",
                  "sensor_id": "sc-kitchen",
                  "line": "🏠😷 The air inside at Bayu 2 - Kitchen is unhealthy right now."}],
    "sensors_quiet": [{"sensor_id": "msh-quiet", "name": "Garden radio", "silent_minutes": 5821}],
    "rho": {"now": {"window_days": 30, "days_ago": 0, "alerts_act": 2, "acted": 1, "rho": 0.5, "median_minutes": 60},
            "week_ago": {"window_days": 30, "days_ago": 7, "alerts_act": 0, "acted": 0, "rho": None,
                         "median_minutes": None}},
    "previous": None,
    "cells": [{"id": "Governance|Community", "value": 0.5,
               "unit": "rho — share of act-level alerts answered within 24h (30d)", "provenance": "partial",
               "changed": None}],
    "health": {"ok": True, "checks": [{"check": "polled in the last 15 min", "ok": True, "fix": None}]},
}

# A node at minute five: the schema is there, the first poll has not landed, and there is nothing to say.
EMPTY = {
    "meta": {"node": "casa-providencia", "locale": "es", "tz": "America/Santiago", "local_time": "06:03",
             "local_date": "2026-09-07", "local_weekday": "Monday", "local_hour": 6, "window_hours": 6,
             "held_hours": 0, "folds_a_held_report": False, "truncated": 0},
    "series": [], "now": [], "observations": [], "alerts": [], "open_act": [], "sensors_quiet": [],
    "rho": {"now": {"window_days": 30, "days_ago": 0, "alerts_act": 0, "acted": 0, "rho": None,
                    "median_minutes": None},
            "week_ago": {"window_days": 30, "days_ago": 7, "alerts_act": 0, "acted": 0, "rho": None,
                         "median_minutes": None}},
    "previous": None, "cells": [], "health": {"ok": True, "checks": []},
}

# ---------------------------------------------------------------- rising, falling, steady
def tr(metric, first, last, lo=0.0, hi=10.0):
    return report._trend({"metric": metric, "mean_first": first, "mean_last": last, "lo": lo, "hi": hi})

assert tr("pm25", 7, 40) == "rising" and tr("pm25", 40, 7) == "falling"
assert tr("pm25", 7, 9) == "steady", "PM2.5 moves by 3 or it has not moved; the digest has used that since v0.24"
assert tr("pm25", 7, 10.5) == "rising"
assert tr("temp", 29.0, 29.3) == "steady" and tr("temp", 29.0, 29.8) == "rising", "half a degree indoors is a change"
assert tr("humidity", 60, 62) == "steady" and tr("humidity", 60, 64) == "rising"
# a metric with no line of its own gets five per cent of its own range, which at least scales
assert tr("gas_resistance", 100, 100.4, lo=100, hi=110) == "steady"
assert tr("gas_resistance", 100, 101, lo=100, hi=110) == "rising"
# one reading in the window has no halves, and a flat line has no range: neither may divide by zero
assert tr("pm25", None, 12) == "steady" and tr("gas_resistance", 5, 5, lo=5, hi=5) == "steady"
print("a metric moved when it moved further than that metric's own noise")

# ---------------------------------------------------------------- 64 kB, and what goes first
big = json.loads(json.dumps(FIXTURE))
big["series"] = [dict(FIXTURE["series"][0], sensor_id=f"s{i}", notability=round(20 - i * 0.01, 2)) for i in range(400)]
fitted = report._fit(big)
assert len(json.dumps(fitted, default=str).encode()) <= report.MAX_BYTES, "the document must fit what a small rung holds"
assert fitted["meta"]["truncated"] > 0 and fitted["series"], "it drops series, not the whole document"
assert fitted["series"][0]["sensor_id"] == "s0", "the most notable series is the one that stays"
assert len(fitted["series"]) + fitted["meta"]["truncated"] == 400, "truncated must count what actually went"
small = report._fit(json.loads(json.dumps(FIXTURE)))
assert small["meta"]["truncated"] == 0 and len(small["series"]) == len(FIXTURE["series"])
print("a bundle over 64 kB drops its least notable series and says how many")

# ---------------------------------------------------------------- the queries, and the one copy of LABELS
SQL = {k: v for k, v in vars(report).items() if k.endswith("_SQL")}
assert set(SQL) >= {"SERIES_SQL", "NOW_SQL", "OBS_SQL", "ALERTS_SQL", "OPEN_ACT_SQL", "QUIET_SQL"}, sorted(SQL)
for name, sql in SQL.items():
    head = sql.strip().split()[0].upper()
    assert head in ("SELECT", "WITH"), f"{name} starts with {head}"
    for w in ("INSERT", "UPDATE", "DELETE", "CREATE", "DROP", "GRANT"):
        assert w not in sql.upper(), f"{name} contains {w}; these run as planetai_ro and read only"
    assert "settings" not in sql.lower(), f"{name} reads settings; planetai_ro cannot, and a report must not"
assert set(report.POINTS) == set(report.LABELS), "POINTS is the LABELS keys, not a second list"
_agent = open("app/agent.py").read()
assert "from report import LABELS" in _agent and "LABELS = {" not in _agent, "one copy of LABELS, in report.py"
for sid, (group, labels) in report.LABELS.items():
    assert group and labels, sid
print("every query reads, none of them can see settings, and LABELS has one home")

# ---------------------------------------------------------------- the sheet, in every language
import copy, re, unicodedata, yaml

RULES = {}
for _f in sorted(__import__("glob").glob("packs/*/rules.yml")):
    pack = _f.split("/")[1]
    for _r in yaml.safe_load(open(_f).read()) or []:
        RULES[f"{pack}/{_r['id']}"] = _r

# The thresholds the report quotes are the rules' own. A number here that is not in that rule's SQL is a second
# copy waiting to drift, which is exactly what the pack-README gate exists for.
LINES = report.thresholds()
assert set(LINES) == {"air-quality/indoor_pm25_high", "air-quality/outside_worse_keep_shut", "air-quality/outdoor_pm25_high",
                      "air-quality/inside_worse_ventilate"}, sorted(LINES)
for rule, (metric, line, owner) in LINES.items():
    assert all(owner in report.T[loc] for loc in report.T), f"{rule}: no words for whose line {owner} is"
    assert rule in RULES, f"{rule} has a report line but no pack ships it"
    sql = RULES[rule]["sql"]
    # the whole number, not a prefix of it: plain `"35" in sql` is satisfied by the 35.5 it is meant to catch
    assert re.search(rf"(?<![\d.]){re.escape(report._n(line))}(?![\d.])", sql), \
        f"{rule}: the report says {line}, its SQL does not"
    assert metric in sql, f"{rule}: the report watches {metric}, its SQL does not mention it"
for rule in report.BEYOND:
    assert rule in RULES, f"{rule} is in BEYOND but no pack ships it"
assert not any(r.startswith("heat/") for r in LINES), \
    "heat_stress_now watches an apparent temperature no column holds; it gets an outcome in v0.39, not a guess here"
# the heat line the report names is the issue's own, the one the page and the alerts name
assert report.HEAT_LINE == float(yaml.safe_load(open("packs/heat/issue.yml"))["line"]["value"]), "two heat lines"
print("every threshold the report quotes is the rule's own")

# Every language carries every phrase. A key in one dict and not another is a report with a hole in it.
assert set(report.T) == {"en", "id", "es"}, sorted(report.T)
for loc, d in report.T.items():
    assert set(d) == set(report.T["en"]), f"{loc} differs: {sorted(set(d) ^ set(report.T['en']))}"
    # The report's whole placeholder vocabulary. A phrase may only ask for something the code fills,
    # so a typo like {palce} fails here rather than reaching a person as a literal brace. Growing this
    # tuple is how the vocabulary grows — {where} arrived with packs/make.
    PLACEHOLDERS = ("{place}", "{n}", "{where}", "{at}", "{line}", "{rooms}")
    for k, v in d.items():
        bare = v
        for ph in PLACEHOLDERS:
            bare = bare.replace(ph, "")
        assert v.strip() and "{" not in bare, f"{loc}/{k}: {v}"
# every placeholder the code fills has a phrase to fill, in every language
for m in re.findall(r"""t\[["']([a-z_]+)["']\]""", open("app/report.py").read()):
    for loc in report.T:
        assert m in report.T[loc], f"{loc} has no phrase for {m}"
for metric in ("pm25", "temp", "humidity"):
    for loc in report.T:
        assert f"high_{metric}" in report.T[loc] and f"low_{metric}" in report.T[loc], f"{loc}: {metric}"
print("every phrase exists in English, Bahasa Indonesia and Spanish")


def _b(**over):
    b = copy.deepcopy(FIXTURE)
    b["rules"] = ["air-quality/indoor_pm25_high", "air-quality/inside_worse_ventilate", "coast/heavy_swell"]
    for k, v in over.items():
        b[k] = v
    return b


def _indoor(b, v):
    for r in b["now"]:
        if r["metric"] == "pm25" and r["indoor"]:
            r["mean_15m"] = r["mean_1h"] = r["last"] = v
    return b


CASES = {}
CASES["a pot still on the stove"] = _indoor(_b(), 48.0)
CASES["the room came back down"] = _b()
CASES["a clean afternoon"] = _indoor(_b(series=[], alerts=[], open_act=[], sensors_quiet=[]), 6.0)
# "Dangerously hot" is said only at real danger (heat/heat_danger, feels like 40 °C or more). heat_stress_now's 35 is
# node #1's ordinary afternoon: the report said "dangerously hot inside" on 14 of 14 ordinary days (SPEC_alerts §1).
CASES["dangerous heat"] = _b(open_act=[{"id": 9, "at": "2026-09-07T15:00:00+08:00", "rule": "heat/heat_danger",
                                        "sensor_id": "sc-kitchen", "line": "🚨🥵 DANGER"}])
CASES["a hot afternoon"] = _b(open_act=[{"id": 9, "at": "2026-09-07T15:00:00+08:00", "rule": "heat/heat_stress_now",
                                         "sensor_id": "sc-kitchen", "line": "🥵 It is dangerously hot"}])
CASES["no sensor indoors"] = _b(now=[r for r in FIXTURE["now"] if not r["indoor"]], series=[], alerts=[], open_act=[])
_swell = _b()
for _o in _swell["observations"]:
    if _o["metric"] == "swell_height_m":
        _o["value"] = 3.1
_swell["observations"].append({"group": "sea", "sensor_id": "marine-point", "metric": "swell_period_s",
                               "means": "swell period, s", "value": 14.0, "day_ago": 11.0, "at": "x"})
CASES["a swell arriving"] = _swell
_sat = _b()
for _o in _sat["observations"]:
    if _o["metric"] == "pm25_model":
        _o["value"] = 61.0
CASES["the satellite sees the district over the line"] = _sat
CASES["a report folded out of quiet hours"] = _b(meta=dict(FIXTURE["meta"], folds_a_held_report=True,
                                                           held_hours=6, window_hours=12))
CASES["the node itself is unwell"] = _b(
    sensors_quiet=[], alerts=[], open_act=[],
    health={"ok": False, "checks": [{"check": "a backup in the last 2 days", "ok": False,
                                     "fix": "run `planetai backup` on the node; check `crontab -l`"}]})
CASES["a node at minute five"] = copy.deepcopy(EMPTY)
for _case, _c in (("the node stopped polling", {"check": "polled in the last 15 min", "fix": "check `planetai logs`"}),
                  ("a radio went quiet", {"check": "LoRa radios heard in the last hour", "fix": "radio(s) msh-a1 silent",
                                          "who": ["Bayu - Garden"]}),
                  ("a radio with no name went quiet", {"check": "LoRa radios heard in the last hour", "fix": "radio(s) msh-a1"}),
                  ("a check the report has no words for", {"check": "something new", "fix": "`planetai doctor`"})):
    CASES[_case] = _b(sensors_quiet=[], alerts=[], open_act=[], health={"ok": False, "checks": [dict(_c, ok=False)]})

seen_keys = set()
for name, b in CASES.items():
    for loc in ("en", "id", "es"):
        s = report.sheet(b, loc)
        assert s and s.strip(), f"{name}/{loc}: empty"
        assert "{" not in s and "}" not in s, f"{name}/{loc}: unfilled placeholder\n{s}"
        assert "None" not in s, f"{name}/{loc}: a None reached a household\n{s}"
        assert "—" not in s, f"{name}/{loc}: a dash where the sentence should have been skipped\n{s}"
        assert "  " not in s and not re.search(r"[ ]\n|\n[ ]", s), f"{name}/{loc}: loose whitespace\n{s!r}"
        assert len(s.split()) <= 100, f"{name}/{loc}: {len(s.split())} words\n{s}"
        assert s.split("\n\n")[-1] == report.T[loc]["ask"], f"{name}/{loc}: the invitation must be last"
        assert s.strip()[0] not in "0123456789", f"{name}/{loc}: it opens with an emoji, not a number"
        # one sign per report (design review, 14 Oct): the headline's, and no 👉 under it
        assert sum(unicodedata.category(ch) == "So" and ch != "°" for ch in s) <= 1, f"{name}/{loc}: more than one sign\n{s}"
        # a line is never a bare number: every figure carries its unit, and a time is a time
        bare = re.findall(r"(?<![\d:.])\d+(?:\.\d+)?(?!\d|[:.]\d|\s*(?:µg/m³|°C|km))", s)
        assert not bare, f"{name}/{loc}: a number with no unit {bare}\n{s}"
        seen_keys |= {k for k, v in report.T[loc].items() if "{" not in v and v in s}
    # the same bundle in three languages must be the same report, part for part
    assert len({len(report.sheet(b, loc).split("\n\n")) for loc in ("en", "id", "es")}) == 1, f"{name}: shapes differ"

# Only the whole sentences can be looked for by their text: "air" and "heat" are words that appear inside other
# phrases, so finding them proves nothing. Every one of those must have been rendered by one of the cases above.
_phrases = {k for k, v in report.T["en"].items() if "{" not in v and v.endswith((".", "?"))}
assert _phrases <= seen_keys, f"never rendered, so never checked: {sorted(_phrases - seen_keys)}"

# The room sentences, each one asked for on purpose: a bundle where that metric is the notable one. Plain words about
# the room ("Kitchen was more humid than usual"), never "Kitchen: the damp ran higher than usual" (node #1, 14 Oct).
for _metric, _hi, _lo in (("pm25", "The air in Kitchen was dirtier", "The air in Kitchen was cleaner"),
                          ("temp", "Kitchen was warmer", "Kitchen was cooler"),
                          ("humidity", "Kitchen was more humid", "Kitchen was drier")):
    _one = _b(series=[dict(FIXTURE["series"][0], metric=_metric, notability=4.0)], alerts=[], open_act=[])
    _low = _b(series=[dict(FIXTURE["series"][0], metric=_metric, notability=-4.0)], alerts=[], open_act=[])
    for _loc in ("en", "id", "es"):
        assert report.T[_loc][f"high_{_metric}"].format(place="Kitchen") in report.sheet(_one, _loc), (_loc, _metric)
        assert report.T[_loc][f"low_{_metric}"].format(place="Kitchen") in report.sheet(_low, _loc), (_loc, _metric)
    assert f"{_hi} than usual." in report.sheet(_one, "en") and f"{_lo} than usual." in report.sheet(_low, "en"), _metric
    assert "ran higher" not in report.sheet(_one, "en") and "What changed" not in report.sheet(_one, "en")
# a part with nothing to say is left out of the report, not printed empty or as a dash
_clean = report.sheet(CASES["a clean afternoon"], "en").split("\n\n")
assert len(_clean) == 3 and all(p.strip() for p in _clean), _clean
assert not any("than usual" in p or "went past" in p for p in _clean), "nothing happened, so no sentence says it did"
# headline, what happened (per room, with its local time and the line named with its unit), the one thing, the invitation
_busy = report.sheet(CASES["a pot still on the stove"], "en").split("\n\n")
assert len(_busy) == 4, _busy
assert _busy[1].startswith("Kitchen went past the US EPA's unhealthy level, 35.5 µg/m³, at 15:00, and is still past it."), _busy[1]
assert "The air in Kitchen was dirtier than usual." in _busy[1] and _busy[2].startswith("Kitchen is the one to deal with"), _busy
assert "35.5 µg/m³, at 15:00; it is back under now." in report.sheet(CASES["the room came back down"], "en")
assert _busy[0] == "😷 The air inside is unhealthy right now.", "the headline is the state in words, no number"
# heat, per room and with its time: the old rule's sensor, and the engine's episode by its rooms, joined in words
_hot = report.sheet(CASES["a hot afternoon"], "en").split("\n\n")
assert _hot[0] == "🌡️ It is hot inside." and _hot[1].startswith(
    "In Kitchen it has felt past this house's heat line, 35 °C feels-like, since 15:00."), _hot
_kids = report.sheet(_b(open_act=[], alerts=[], series=[], open_events=[{"issue": "heat", "kind": "sustained", "at": "2026-10-14T06:47:00+00:00",
                                                                        "rooms": ["Living Room", "Kids"]}]), "en")
assert "In Kids and Living Room it has felt past this house's heat line, 35 °C feels-like, since 14:47." in _kids, _kids
_warm = report.sheet(_b(open_act=[], alerts=[], series=[], open_events=[{"issue": "heat", "kind": "unusual", "at": "2026-10-14T06:47:00+00:00",
                                                                        "rooms": ["Studio"]}]), "es")
assert "En Studio hace más calor de lo habitual desde las 14:47." in _warm, "an unusual episode is not said to be past the line"
assert report.sheet(CASES["a node at minute five"], "es").startswith("🛰️"), "a node with no readings still speaks"
assert "dangerously" not in report.sheet(CASES["a hot afternoon"], "en"), "an ordinary hot afternoon is not danger"
assert report.T["en"]["state_heat"] in report.sheet(CASES["a hot afternoon"], "en")
assert report.T["en"]["state_hot"] in report.sheet(CASES["dangerous heat"], "en")
# ---------------------------------------------------------------- what was sent, and only that (14 Oct)
# On ALERT_ENGINE=events a replaced pack's rules record rows nobody received. node #1's 19:00 report opened "It is hot
# inside" from one of those while the page said bearable: the bundle leaves them out, and the engine's open, sent
# episodes stand in for them.
import learn                                                        # noqa: E402
assert learn.replaced([{"id": "heat/heat_stress_now", "kind": "sustained"}, {"id": "nearby/x"}], "events") == {"heat"}
assert learn.replaced([{"id": "heat/heat_stress_now", "kind": "sustained"}], "rules") == set(), "a rules node replaces nothing"
_src = open("app/report.py").read()
_bun = _src[_src.index("def bundle"):_src.index("\ndef ", _src.index("def bundle") + 10)]
assert _bun.count("if told(r)]") == 2 and "learn.silent(" in _bun, "both alert lists leave silent rows out"
assert "WHERE cleared_at IS NULL AND ever_sent AND level = 'act'" in _bun, "the engine's open episodes, only those it told"
# and bundle() itself, run: node #1 showed a check by reading alone is not enough. A local `import packs` lower in
# bundle() made `packs` local to all of it, the rule set could not be read, and every silent row went through.
from datetime import datetime as _dt, timedelta as _td, timezone as _tz          # noqa: E402
_now = _dt.now(_tz.utc)
_rows = {"ALERTS_SQL": [{"id": 1, "ts": _now - _td(hours=2), "rule_id": "heat/heat_stress_now", "sensor_id": "k", "level": "act", "line": "hot", "acted": False},
                        {"id": 2, "ts": _now - _td(hours=1), "rule_id": "nearby/only_here", "sensor_id": "k", "level": "act", "line": "x", "acted": False}],
         "OPEN_ACT_SQL": [{"id": 1, "ts": _now - _td(hours=2), "rule_id": "heat/heat_stress_now", "sensor_id": "k", "line": "hot"}]}
class _Cur:
    def __init__(self): self.last = ""
    def execute(self, sql, *a): self.last = sql
    def fetchone(self): return {"t": _now - _td(days=9)} if "event_messages" in self.last else None
    def fetchall(self): return [{"issue": "heat", "kind": "sustained", "opened_at": _now - _td(hours=2)}] if "alert_events" in self.last else []
_by = {getattr(report, k): k for k in ("ALERTS_SQL", "OPEN_ACT_SQL")}
_saved = (report.index.run_ro, report.index.rho, report.index.cells, report.packs.load_rules, report.packs.rules, report.packs.contributors)
report.index.run_ro = lambda cur, sql, *a: [dict(r) for r in _rows.get(_by.get(sql), [])]
report.index.rho = lambda cur, **k: None
report.index.cells = lambda cur: []
report.packs.load_rules = lambda: [{"id": "heat/heat_stress_now", "kind": "sustained"}, {"id": "nearby/only_here"}]
report.packs.rules = lambda: []
report.packs.contributors = lambda kind: []
_sg = report.settings.get
report.settings.get = lambda k, d=None: "events" if k == "ALERT_ENGINE" else _sg(k, d)
_bundle = report.bundle(_Cur(), 6)
report.settings.get = _sg
(report.index.run_ro, report.index.rho, report.index.cells, report.packs.load_rules, report.packs.rules, report.packs.contributors) = _saved
assert [a["rule"] for a in _bundle["alerts"]] == ["nearby/only_here"] and _bundle["open_act"] == [], _bundle["alerts"]
assert _bundle["open_events"] and _bundle["open_events"][0]["issue"] == "heat", "the engine's open sent episode stands in"
_ev = lambda kind: _b(open_act=[], open_events=[{"issue": "heat", "kind": kind, "at": "2026-10-14T14:47:00+08:00"}])  # noqa: E731
assert report.T["en"]["state_heat"] in report.sheet(_ev("sustained"), "en"), "an open heat episode that was sent is said"
assert report.T["en"]["state_hot"] in report.sheet(_ev("danger"), "en")
assert report.T["en"]["state_heat"] not in report.sheet(_b(open_act=[], open_events=[]), "en"), "nothing open, no heat line"
# the inventory is a survey sensor written when it is edited: it never "stopped sending"
assert "s.local AND s.kind = 'sensor'" in report.QUIET_SQL
# a metric with no household word is never named (node #1: "BAYU HOLES: the bme_iaq ran higher than usual")
_iaq = report.sheet(_b(series=[dict(FIXTURE["series"][0], metric="bme_iaq", notability=4.0)], alerts=[], open_act=[]), "en")
assert "bme_iaq" not in _iaq and "What changed" not in _iaq, _iaq
print("the report tells what was sent; the inventory never stops sending; a metric without a word is not named")
_src_err = _b(alerts=[], open_act=[], sensors_quiet=[], health={"ok": False, "checks": [{"check": "no source errors", "ok": False,
              "fix": "errors: open-meteo: Client error '429 Too Many Requests' for url 'https://api.open-meteo.com/v1/forecast"}]})
_se = report.sheet(_src_err, "en")
assert "429" not in _se and "http" not in _se and report.T["en"]["todo_none"] in _se, "a refusing source is the keeper's, not the house's to-do"
# 15 Oct: a failing health check reached the morning as its admin `fix` ("run `planetai backup`", "radio(s) msh-…
# silent"). The house gets its own line per check, names a sensor by its room, and never the id or a command.
_FIX = {"polled in the last 15 min": "the poll loop is stuck or the node just started; check `planetai logs`",
        "a backup in the last 2 days": "run `planetai backup` on the node and check `crontab -l | grep backup`",
        "LoRa radios heard in the last hour": "radio(s) msh-a1b2 have been silent for hours. `planetai logs mosquitto`",
        "no local sensor's ambient channel is frozen": "Bayu - Kitchen has a channel stuck",
        "something new": "`planetai doctor`"}
for _chk, _fix in _FIX.items():
    for _who in ([], ["Bayu - Kitchen"]):
        _c = {"check": _chk, "ok": False, "fix": _fix, **({"who": _who} if _who else {})}
        for _loc in ("en", "id", "es"):
            _s = report.sheet(_b(alerts=[], open_act=[], sensors_quiet=[], health={"ok": False, "checks": [_c]}), _loc)
            assert not re.search(r"planetai|crontab|msh-|`|\{|poll loop", _s), (_chk, _loc, _s)
            _todo = _s.split("\n\n")[-2]
            assert "Bayu" not in _todo and ("Kitchen" in _todo) == bool(
                _who and _chk in ("LoRa radios heard in the last hour", "no local sensor's ambient channel is frozen")), (_chk, _loc, _todo)
print("a failing health check reaches the morning in the household's words, by room, never as its admin fix")
print(f"the sheet renders in three languages across {len(CASES)} states, under 100 words, with nothing unfilled")
