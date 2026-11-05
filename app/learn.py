"""What worked here (docs/SPEC_learn.md step 1): the household's own evidence, from the actions ledger.

For every act-level alert on one sensor that somebody acted on, or that nobody answered at all, the node takes the
metric the rule watches on that sensor in the hour before (the act, or the alert when unanswered) and its mean over a
window after, and the same two numbers on the street (every outdoor sensor). Per rule it keeps the medians as one row
of `learnings`, with its cases, so the page can show the proof.

WHAT IT DOES NOT CLAIM, AND THE ROW SAYS SO: a cause. GET /effect already warns that air clearing at 03:00 may be the
window or the night. Here the street's change is beside the house's, and the unanswered alerts beside the acted ones,
which is more than a before and after; it is still not an experiment.

Hourly, because readings_1h is what a node keeps for every sensor; the hour before the act ends up to 59 minutes
before it. Code proves, a model only words (SPEC_learn §2): the statement is a template over the numbers.
"""
from __future__ import annotations

import math
import statistics
import time
from datetime import datetime, timedelta, timezone



def _owned() -> dict:
    """{pack id: the issue it ships} (app/issues/__init__.py::owners). What used to be PACK_METRIC and ISSUE_PACK here:
    a rule is judged on its issue's `metric` when its own `watch` names none (inside_worse_ventilate fires on a relation,
    inside worse than outside, and has no line, but what it asks you to change is still PM2.5), and the event engine's
    episodes of an issue are counted under `<its pack>/events`."""
    import issues                    # noqa: PLC0415 — issues imports packs, which a pure test of this module never needs
    return issues.owners()


def _metric(pack: str) -> str | None:
    return (_owned().get(pack) or {}).get("metric")


def _issue_packs() -> dict:
    """{issue: the pack that ships it}."""
    return {d["key"]: p for p, d in _owned().items()}
# Hours after the act that make "after": air changes within the hour, a room's heat over several.
AFTER = {"pm25": (1, 2), "apparent": (3, 6), "temp": (3, 6)}
UNIT = {"pm25": "µg/m³", "apparent": "°C", "temp": "°C"}
WORDS = {"pm25": "PM2.5", "apparent": "the feels-like temperature", "temp": "the temperature"}
EARLY = 5          # fewer acted cases than this and the row says "too early to say", with its count


def apparent(t: float, rh: float) -> float:
    """The node's own Steadman form, as packs/heat/rules.yml and usual_by_hour write it."""
    return t + 0.33 * (rh / 100.0 * 6.105 * math.exp(17.27 * t / (237.7 + t))) - 4.0


def series(rows: list[dict]) -> dict:
    """Hourly means as {(sensor_id, metric): {bucket: value}}, with `apparent` derived where temp and humidity meet."""
    out: dict = {}
    for r in rows:
        out.setdefault((r["sensor_id"], r["metric"]), {})[r["bucket"]] = r["mean"]
    for (sid, m), temps in list(out.items()):
        if m == "temp" and (sid, "humidity") in out:
            hum = out[(sid, "humidity")]
            out[(sid, "apparent")] = {b: apparent(t, hum[b]) for b, t in temps.items() if b in hum}
    return out


def _mean(s: dict, start: datetime, hours: range):
    vals = [s[start + timedelta(hours=h)] for h in hours if start + timedelta(hours=h) in s]
    return sum(vals) / len(vals) if vals else None


def case(s: dict, outdoor: list[dict], h: datetime, after: tuple[int, int]) -> dict | None:
    """One alert's numbers: before and after on its own sensor, and on the street. None when the house has no reading
    on either side; the street may be missing, and then only the house's change is kept."""
    before, aft = _mean(s, h, range(-1, 0)), _mean(s, h, range(after[0], after[1] + 1))
    if before is None or aft is None:
        return None
    ob = [x for x in (_mean(o, h, range(-1, 0)) for o in outdoor) if x is not None]
    oa = [x for x in (_mean(o, h, range(after[0], after[1] + 1)) for o in outdoor) if x is not None]
    street = (sum(oa) / len(oa) - sum(ob) / len(ob)) if ob and oa else None
    return {"at": h.isoformat(), "before": round(before, 1), "after": round(aft, 1),
            "change": round(aft - before, 1), "street": None if street is None else round(street, 1)}


def _med(xs):
    xs = [x for x in xs if x is not None]
    return round(statistics.median(xs), 1) if xs else None


# The verdict (design review, 14 Oct): node #1's air row read HOLDING while acting had left the air worse than not
# answering. `holding` says the learning holds; the verdict says what it holds. It compares the two groups' changes
# inside, each net of the street's: acting helps when its net change is lower (cleaner, cooler) than not answering by
# more than the metric's noise, which is the report's TREND step read across. With nobody unanswered yet, not
# answering counts as no change. Words lead the sentence; the numbers follow it, so code proves and the words only say.
# The values are the ones the diary split's pages read (helps, no_clear_difference, too_early, gone), plus `worse`.
NOISE = {"pm25": 3.0, "apparent": 0.5, "temp": 0.5}
VERDICT_WORDS = {"helps": "acting on it helps",
                 "no_clear_difference": "no clear difference between acting on it and leaving it",
                 "worse": "acting on it seemed to make it worse than leaving it",
                 "too_early": "too few to be sure whether acting on it helps",
                 "gone": "this alert no longer rings here; what it showed is kept"}
# What the household calls an alert, for a learning's lead and the bot's /learned. A rule without a name of its own is
# named by its issue ("an air alert"), never by its id.
# A rule says its own name (`name:` in its pack's rules.yml); an issue what its alerts are called (`alert:` in its
# issue.yml), which names the event engine's episodes and any rule of that pack without a name of its own.
_NAMES: dict = {"at": 0.0, "map": {}}


def _rule_names() -> dict:
    if time.time() - _NAMES["at"] > 60:
        import packs                 # noqa: PLC0415
        _NAMES.update(at=time.time(), map={r["id"]: r["name"] for r in packs.load_rules()
                                           if isinstance(r, dict) and isinstance(r.get("name"), str)})
    return _NAMES["map"]


def alert_name(key: str) -> str:
    pack, _, rule = (key or "").partition("/")
    alert = (_owned().get(pack) or {}).get("alert")
    if rule == "events":
        return alert or key
    return _rule_names().get(key) or GROUP_WORDS.get(key) or alert or key


def verdict(metric: str, status: str, a: dict, u: dict) -> str:
    """helps · no_clear_difference · worse · too_early · gone, from the row's status and the two groups' medians
    (summarise's `a` and `u`). `helps` also needs the house's own net change to be a fall, as the pages expect."""
    if status in ("too_early", "gone"):
        return status
    net = a["change"] - (a["street"] or 0)
    base = (u["change"] - (u["street"] or 0)) if u["n"] and u["change"] is not None else 0.0
    d, step = net - base, NOISE.get(metric, 0.5)
    return "helps" if net < 0 and d <= -step else "worse" if d >= step else "no_clear_difference"


def summarise(rule: str, metric: str, acted: list[dict], unanswered: list[dict], was: dict | None, live: bool) -> dict:
    """One learning row from the cases, with the statement written from its own numbers: the verdict in words first,
    then the numbers it came from."""
    a = {"n": len(acted), "change": _med(c["change"] for c in acted), "street": _med(c["street"] for c in acted)}
    u = {"n": len(unanswered), "change": _med(c["change"] for c in unanswered),
         "street": _med(c["street"] for c in unanswered)}
    w, unit, lo, hi = WORDS[metric], UNIT[metric], *AFTER[metric]
    if not live:
        status = "gone"
    elif a["n"] < EARLY:
        status = "too_early"
    else:
        net = a["change"] - (a["street"] or 0)
        old = ((was or {}).get("numbers") or {}).get("acted") or {}
        old_net = (old.get("change") or 0) - (old.get("street") or 0) if old.get("n", 0) >= EARLY else None
        status = "weakening" if old_net is not None and (old_net < 0) != (net < 0) else "holding"
    v = verdict(metric, status, a, u)

    def says(x, who):
        street = f", while on the street it changed {x['street']:+.1f} {unit}" if x["street"] is not None else ""
        return f"{who} {x['n']} times: {w} inside changed {x['change']:+.1f} {unit} in the {lo}–{hi} h after{street}."
    text = f"After {alert_name(rule)}, {a['n'] + u['n']} times so far: {VERDICT_WORDS[v]}."
    if v == "too_early":
        text += f" Acted on {a['n']} times."
    else:
        text += " " + (says(a, "Acted on") if a["n"] else "Nobody has acted on it yet.")
        if u["n"]:
            text += " " + says(u, "Left unanswered")
    return {"kind": "worked", "key": rule, "issue": rule.split("/")[0], "metric": metric, "status": status,
            "statement": text, "n": a["n"], "scope": "house",
            "numbers": {"acted": a, "unanswered": u, "after_hours": [lo, hi], "unit": unit, "verdict": v,
                        "cases": {"acted": acted[-30:], "unanswered": unanswered[-30:]}}}


# ON A NODE WHOSE EVENT ENGINE SPEAKS (ALERT_ENGINE=events), the packs it replaced still write `alerts` rows that are
# never sent. Counting those as "left unanswered" counted alerts nobody received (node #1, 14 Oct: 58 silent heat rows
# against 4 heat messages since the switch). So a row of a replaced pack after the switch is silent and left out, and
# the engine's own episodes that were sent stand in for them, under `<pack>/events` (_issue_packs()).


def replaced(rules: list, mode: str) -> set:
    """The packs the event engine speaks for on this node: those with kinded rules, on ALERT_ENGINE=events only."""
    if mode != "events":
        return set()
    return {r["id"].split("/", 1)[0] for r in rules if isinstance(r, dict) and r.get("kind") and r.get("id")}


def silent(rule_id: str, ts, replaced: set, since) -> bool:
    return bool(since) and rule_id.split("/")[0] in replaced and _aware(ts) >= _aware(since)


def sent_events(q, days: int | None = None) -> list[dict]:
    """The event engine's episodes that reached someone (an open or an escalation sent in events mode)."""
    return q("""SELECT e.id, e.issue, e.opened_at, e.rooms, CAST(extract(hour FROM e.opened_at) AS INTEGER) AS hour,
                       (SELECT min(x.ts) FROM actions x WHERE x.event_id = e.id AND x.stage = 'acted') AS acted_at,
                       EXISTS (SELECT 1 FROM actions x WHERE x.event_id = e.id AND x.stage = 'acted') AS acted,
                       EXISTS (SELECT 1 FROM actions x WHERE x.event_id = e.id AND x.stage = 'dismissed') AS dismissed,
                       EXISTS (SELECT 1 FROM actions x WHERE x.event_id = e.id) AS answered,
                       (SELECT string_agg(x.note, ' · ') FROM actions x
                         WHERE x.event_id = e.id AND x.stage = 'acted' AND coalesce(x.note, '') <> '') AS note
                FROM alert_events e
                WHERE EXISTS (SELECT 1 FROM event_messages m WHERE m.event_id = e.id AND m.sent AND m.mode = 'events'
                                AND m.reason IN ('open', 'escalate'))
                  AND (%s::int IS NULL OR e.opened_at > now() - make_interval(days => %s::int))
                ORDER BY e.opened_at""", days, days)


def learn_worked(q, rules: list[dict], live: set, was: dict, replaced: set = frozenset(), since=None) -> list[dict]:
    """Every rule's row, for each rule with at least one case. `q` reads the database (main.q), `rules` are
    packs.load_rules(), `live` the rules that can still fire, `was` the previous rows by key (for `weakening`). A rule
    no longer loaded still gets its row, marked `gone`, from its alerts: retiring a rule does not unlearn it."""
    watch = {r["id"]: (r.get("watch") or {}).get("metric") for r in rules if isinstance(r, dict) and r.get("id")}
    alerts = q("""SELECT l.id, l.ts, l.rule_id, l.sensor_id,
                         (SELECT min(x.ts) FROM actions x WHERE x.alert_id = l.id AND x.stage = 'acted') AS acted_at,
                         EXISTS (SELECT 1 FROM actions x WHERE x.alert_id = l.id) AS answered,
                         (SELECT string_agg(x.note, ' · ') FROM actions x
                           WHERE x.alert_id = l.id AND x.stage = 'acted' AND coalesce(x.note, '') <> '') AS note
                  FROM alerts l
                  WHERE l.level = 'act' AND l.sensor_id IS NOT NULL
                  ORDER BY l.ts""")
    alerts = [a for a in alerts if not silent(a["rule_id"], a["ts"], replaced, since)]
    events = sent_events(q) if since else []
    names = {r["name"]: r["sensor_id"] for r in q("SELECT sensor_id, name FROM sensors WHERE name IS NOT NULL")} if events else {}
    owner = _issue_packs()
    for e in events:   # an episode is a case on its first room's sensor, like an alert on its sensor
        sid = next((names[r] for r in (e["rooms"] or []) if r in names), None)
        if sid and e["issue"] in owner:
            key = f"{owner[e['issue']]}/events"
            alerts.append({"id": None, "ts": e["opened_at"], "rule_id": key, "sensor_id": sid,
                           "acted_at": e["acted_at"], "answered": e["answered"], "note": e["note"]})
            watch.setdefault(key, _metric(owner[e["issue"]]))
            live = live | {key}
    if not alerts:
        return []
    want = {}
    for rid in dict.fromkeys(a["rule_id"] for a in alerts):
        metric = watch.get(rid) or (_metric(rid.split("/")[0]) if "/" in rid else None)
        if metric in AFTER:
            want[rid] = metric
    if not want:
        return []
    start = min(_aware(a["ts"]) for a in alerts) - timedelta(hours=2)
    rows = q("""SELECT date_trunc('hour', r.ts) AS bucket, r.sensor_id, r.metric, avg(r.value) AS mean, bool_or(s.indoor) AS indoor
                FROM readings r JOIN sensors s USING (sensor_id)
                WHERE s.kind = 'sensor' AND r.metric IN ('pm25', 'temp', 'humidity') AND r.ts >= %s AND r.ts <= now()
                GROUP BY 1, 2, 3""", start)
    for r in rows:
        r["bucket"] = _aware(r["bucket"])
    s = series(rows)
    indoor = {r["sensor_id"]: r["indoor"] for r in rows}
    now = datetime.now(timezone.utc)
    out = []
    for rule, metric in want.items():
        street = [v for (sid, m), v in s.items() if m == metric and indoor.get(sid) is False]
        acted, unanswered = [], []
        for a in (x for x in alerts if x["rule_id"] == rule):
            h = _aware(a["acted_at"] or a["ts"]).replace(minute=0, second=0, microsecond=0)
            if a["acted_at"] is None and a["answered"]:
                continue                     # seen or dismissed, but not acted on: neither group
            if now < h + timedelta(hours=AFTER[metric][1] + 1):
                continue                     # its after-window has not passed yet
            c = case(s.get((a["sensor_id"], metric), {}), street, h, AFTER[metric])
            if c:
                (acted if a["acted_at"] else unanswered).append({**c, "note": a["note"] or ""} if a["acted_at"] else c)
        if acted or unanswered:
            out.append(summarise(rule, metric, acted, unanswered, was.get(rule), rule in live))
    return out




def _aware(t) -> datetime:
    t = datetime.fromisoformat(t) if isinstance(t, str) else t
    return t if t.tzinfo else t.replace(tzinfo=timezone.utc)


# ---------------------------------------------------------------- what is usual here (SPEC_learn §5, step 2)
# Per group of this house's own sensors: when in the day it is usually highest and lowest, weekdays against weekends,
# this week against the three before, and, once there are 60 days, a slow trend. One row per group. The house's
# indoor rooms are `house`; its own outdoor sensors are `place`, the kind of learning a community would want.
GROUPS = {"indoor-pm25": ("pm25", True), "outdoor-pm25": ("pm25", False), "indoor-heat": ("apparent", True)}
GROUP_WORDS = {"indoor-pm25": "PM2.5 inside", "outdoor-pm25": "PM2.5 outside", "indoor-heat": "the feels-like temperature inside"}
USUAL_DAYS = 28        # the window the day's shape and the week's comparison read
USUAL_MIN = 14         # fewer days than this and the row says too early
TREND_MIN = 60         # a slope needs at least this many days


def theil_sen(ys: list[float]) -> float:
    """The median of every pairwise slope, per step: a trend a few odd days cannot drag. O(n²); a year is 66k pairs."""
    s = [(ys[j] - ys[i]) / (j - i) for i in range(len(ys)) for j in range(i + 1, len(ys))]
    return statistics.median(s) if s else 0.0


def usual_row(group: str, hourly: dict, today) -> dict | None:
    """One group's row from its hourly means {aware local datetime: value}. None when the house has no such sensor."""
    if not hourly:
        return None
    metric, inside = GROUPS[group]
    unit, words = UNIT[metric], GROUP_WORDS[group]
    days = sorted({b.date() for b in hourly})
    recent = {b: v for b, v in hourly.items() if (today - b.date()).days < USUAL_DAYS}
    base = {"kind": "usual", "key": group, "issue": "air" if metric == "pm25" else "heat", "metric": metric,
            "n": len({b.date() for b in recent}), "scope": "house" if inside else "place"}
    if base["n"] < USUAL_MIN:
        return {**base, "status": "too_early", "numbers": {"days": base["n"]},
                "statement": f"{base['n']} days of {words} so far: too early to say what is usual."}
    by_hour = {h: statistics.median([v for b, v in recent.items() if b.hour == h]) for h in {b.hour for b in recent}}
    hi, lo = max(by_hour, key=by_hour.get), min(by_hour, key=by_hour.get)
    wk = [v for b, v in recent.items() if b.isoweekday() < 6]
    we = [v for b, v in recent.items() if b.isoweekday() >= 6]
    daily = {d: statistics.median([v for b, v in hourly.items() if b.date() == d]) for d in days}
    this = [daily[d] for d in days if (today - d).days < 7]
    before = [daily[d] for d in days if 7 <= (today - d).days < USUAL_DAYS]
    n = {"days": base["n"], "high_hour": hi, "high": round(by_hour[hi], 1), "low_hour": lo, "low": round(by_hour[lo], 1),
         "weekday": round(statistics.median(wk), 1) if wk else None, "weekend": round(statistics.median(we), 1) if we else None,
         "by_hour": {h: round(v, 1) for h, v in sorted(by_hour.items())}, "unit": unit}
    text = (f"Over the last {base['n']} days, {words} is usually highest around {hi:02d}:00 ({n['high']} {unit}) "
            f"and lowest around {lo:02d}:00 ({n['low']}).")
    if n["weekday"] is not None and n["weekend"] is not None:
        d = round(n["weekend"] - n["weekday"], 1)
        text += f" Weekends run {abs(d)} {unit} {'higher' if d > 0 else 'lower'} than weekdays." if d else " Weekends and weekdays are the same."
    if len(this) >= 3 and len(before) >= 7:
        q1, _, q3 = statistics.quantiles(before, n=4)
        now_, usual = statistics.median(this), statistics.median(before)
        n.update(this_week=round(now_, 1), usual_week=round(usual, 1), spread=[round(q1, 1), round(q3, 1)])
        where = "above" if now_ > q3 else "below" if now_ < q1 else None
        text += (f" This week it was {round(now_, 1)} {unit} a day, {where} the three weeks before ({round(q1, 1)}–{round(q3, 1)})."
                 if where else f" This week ({round(now_, 1)} {unit} a day) was within the three weeks before.")
    if len(days) >= TREND_MIN:
        slope = theil_sen([daily[d] for d in days]) * 30
        n["trend_per_30_days"] = round(slope, 2)
        text += f" Over {len(days)} days it has moved {slope:+.1f} {unit} every 30 days."
    return {**base, "status": "holding", "numbers": n, "statement": text}


def learn_usual(q, today=None) -> list[dict]:
    """The three groups from this house's own sensors, up to a year back."""
    rows = q("""SELECT date_trunc('hour', r.ts) AS bucket, r.sensor_id, r.metric, avg(r.value) AS mean, bool_or(s.indoor) AS indoor
                FROM readings r JOIN sensors s USING (sensor_id)
                WHERE s.kind = 'sensor' AND s.local AND r.metric IN ('pm25', 'temp', 'humidity')
                  AND r.ts > now() - interval '365 days' AND r.ts <= now()
                GROUP BY 1, 2, 3""")
    g = group_hourly(rows)
    today = today or (max(r["bucket"] for r in rows).date() if rows else None)
    return [r for r in (usual_row(k, g.get(k, {}), today) for k in GROUPS) if r]


def group_hourly(rows: list[dict]) -> dict:
    """{group: {aware local bucket: mean over that group's sensors}} from hourly rows of the house's own sensors."""
    for r in rows:
        r["bucket"] = _aware(r["bucket"])
    s = series(rows)
    indoor = {r["sensor_id"]: r["indoor"] for r in rows}
    out = {}
    for group, (metric, inside) in GROUPS.items():
        merged: dict = {}
        for (sid, m), vals in s.items():
            if m == metric and indoor.get(sid) is inside:
                for b, v in vals.items():
                    merged.setdefault(b, []).append(v)
        if merged:
            out[group] = {b: sum(v) / len(v) for b, v in merged.items()}
    return out


# ---------------------------------------------------------------- asks that do not fit (SPEC_learn §5)
# An alert that is mostly dismissed or left unanswered is a learning about the alert, not the house. The node says so
# and names what would change it; it changes nothing itself. The lines live in the packs' rules, so the suggestion is
# addressed to whoever keeps them, and quiet hours hold only lesser alerts, never an act-level one.
ASKS_DAYS = 30
ASKS_MIN = 5
NIGHT = set(range(22, 24)) | set(range(0, 6))


def asks_row(rule: str, alerts: list[dict], live: bool) -> dict | None:
    """One rule's row from its last 30 days of act-level alerts: [{hour, acted, dismissed, answered}]."""
    n = len(alerts)
    if n < ASKS_MIN:
        return None
    acted = sum(a["acted"] for a in alerts)
    dismissed = sum(a["dismissed"] and not a["acted"] for a in alerts)
    ignored = [a for a in alerts if not a["answered"]]
    night = sum(a["hour"] in NIGHT for a in ignored)
    share = (len(ignored) + dismissed) / n
    nums = {"days": ASKS_DAYS, "raised": n, "acted": acted, "dismissed": dismissed, "unanswered": len(ignored),
            "unanswered_at_night": night}
    text = (f"In the last {ASKS_DAYS} days this alert was raised {n} times: acted on {acted}, "
            f"dismissed {dismissed}, left unanswered {len(ignored)}.")
    per_day = n / ASKS_DAYS
    peak = statistics.mode(a["hour"] for a in ignored) if ignored else None
    nums.update(per_day=round(per_day, 1), unanswered_peak_hour=peak)
    suggest = None
    if share >= 0.7:
        if ignored and night / len(ignored) >= 0.5:
            suggest = (f"{night} of the {len(ignored)} unanswered came between 22:00 and 06:00. Quiet hours do not hold "
                       "an act-level alert, so this one still rings at night; a night line or a lower level for it is "
                       "a change to its rule.")
        elif per_day >= 3:
            suggest = (f"It rings about {round(per_day)} times a day, most often around {peak:02d}:00, and an alert that "
                       "often becomes background. A longer pause between repeats, or a higher line, is a change to its rule.")
        else:
            suggest = (f"Most of the time it is not answered (most often around {peak:02d}:00). Its line, or the action "
                       "it asks for, may not fit this house; that is a change to its rule.")
        text += " " + suggest
    return {"kind": "asks", "key": rule, "issue": rule.split("/")[0], "metric": None, "n": n, "scope": "house",
            "status": "gone" if not live else "holding", "statement": text,
            "numbers": {**nums, "suggest": suggest}}


def learn_asks(q, live: set, replaced: set = frozenset(), since=None) -> list[dict]:
    rows = q("""SELECT l.rule_id, CAST(extract(hour FROM l.ts) AS INTEGER) AS hour,
                       EXISTS (SELECT 1 FROM actions x WHERE x.alert_id = l.id AND x.stage = 'acted') AS acted,
                       EXISTS (SELECT 1 FROM actions x WHERE (x.alert_id = l.id OR (l.event_id IS NOT NULL AND x.event_id = l.event_id))
                                 AND x.stage = 'dismissed') AS dismissed,
                       EXISTS (SELECT 1 FROM actions x WHERE x.alert_id = l.id OR (l.event_id IS NOT NULL AND x.event_id = l.event_id)) AS answered
                       , l.ts
                FROM alerts l WHERE l.level = 'act' AND l.ts > now() - make_interval(days => %s)""", ASKS_DAYS)
    by: dict = {}
    hushed = set()
    for r in rows:
        if silent(r["rule_id"], r["ts"], replaced, since):
            hushed.add(r["rule_id"])
            continue
        by.setdefault(r["rule_id"], []).append(r)
    out = [x for x in (asks_row(k, v, k in live) for k, v in by.items() if k not in hushed) if x]
    day = _aware(since).date().isoformat() if since else ""
    for k in sorted(hushed):   # its old row said how often it rang; it no longer rings here
        out.append({"kind": "asks", "key": k, "issue": k.split("/")[0], "metric": None, "n": 0, "scope": "house",
                    "status": "gone", "numbers": {"replaced_since": day},
                    "statement": f"This alert no longer sends here: since {day} the event engine speaks for this issue, "
                                 f"once per episode (see {k.split('/')[0]}/events). It still records, silently."})
    ev = sent_events(q, ASKS_DAYS) if since else []
    for issue, pack in _issue_packs().items():
        mine = [{"hour": e["hour"], "acted": e["acted"], "dismissed": e["dismissed"], "answered": e["answered"]}
                for e in ev if e["issue"] == issue]
        r = asks_row(f"{pack}/events", mine, True)
        if r:
            out.append(r)
    return out



# ---------------------------------------------------------------- digests (SPEC_learn §6, step 3)
# One per completed day, week (Monday to Sunday), month and year, in the house's own time zone: what each group of its
# sensors did, the alerts and what was done about them in the household's own words, and the change since the
# digest before at the same scale. Written by the node from its numbers; searched by the pane and the bot.
# ponytail: English dates and words, as the report's sheet; a locale per digest when a node asks for one
SHORT = {"indoor-pm25": "PM2.5 inside", "outdoor-pm25": "PM2.5 outside", "indoor-heat": "feels-like inside"}
SCALES = ("day", "week", "month", "year")
BACKFILL_DAYS = 400
# A digest written by an older version of this file is written again, once: v2 counts what was sent on an events
# node (node #1's 13 Oct digest said "15 alerts, 0 acted on" when those rows were never sent); v3 leaves out test
# alerts (`_test/hello-<epoch>`, and `gui/test` from POST /test-alert), which node #1's 5 and 6 Oct entries counted as alerts.
DIGEST_V = 3


def periods(first, today) -> list[tuple[str, object, object]]:
    """Every completed (scale, start, end) from the first day with data to yesterday; `end` is exclusive."""
    from datetime import date  # noqa: PLC0415
    out, first = [], max(first, today - timedelta(days=BACKFILL_DAYS))
    d = first
    while d < today:
        out.append(("day", d, d + timedelta(days=1)))
        d += timedelta(days=1)
    w = first - timedelta(days=first.weekday())
    while w + timedelta(days=7) <= today:
        out.append(("week", w, w + timedelta(days=7)))
        w += timedelta(days=7)
    m = first.replace(day=1)
    while True:
        nxt = (m.replace(day=28) + timedelta(days=4)).replace(day=1)
        if nxt > today:
            break
        out.append(("month", m, nxt))
        m = nxt
    y = date(first.year, 1, 1)
    while date(y.year + 1, 1, 1) <= today:
        out.append(("year", y, date(y.year + 1, 1, 1)))
        y = date(y.year + 1, 1, 1)
    return out


def label(scale: str, start) -> str:
    return {"day": start.strftime("%A %-d %B %Y"), "week": f"Week of {start.strftime('%-d %B %Y')}",
            "month": start.strftime("%B %Y"), "year": start.strftime("%Y")}[scale]


def digest(scale: str, start, end, groups: dict, alerts: list[dict], notes: list[dict], prev: dict | None) -> dict:
    """One digest from the period's hourly groups, its act-level alerts [{rule_id, acted}] and acted notes
    [{note}]. `prev` is the digest before at the same scale, for the change."""
    nums, parts = {}, []
    for g in GROUPS:
        v = {b: x for b, x in (groups.get(g) or {}).items() if start <= b.date() < end}
        if not v:
            continue
        top = max(v, key=v.get)
        unit = UNIT[GROUPS[g][0]]
        nums[g] = {"mean": round(sum(v.values()) / len(v), 1), "max": round(v[top], 1), "max_at": top.isoformat(), "hours": len(v)}
        when = f"{top.hour:02d}:00" if scale == "day" else f"{top.strftime('%-d %b')} at {top.hour:02d}:00"
        parts.append(f"{SHORT[g]} averaged {nums[g]['mean']} {unit}, highest {nums[g]['max']} {unit} ({when})")
    text = label(scale, start) + ". " + ("; ".join(parts) + "." if parts else "No readings from this house's own sensors.")
    by_rule: dict = {}
    for a in alerts:
        r = by_rule.setdefault(a.get("name") or a["rule_id"].split("/")[-1], [0, 0])
        r[0] += 1
        r[1] += 1 if a["acted"] else 0
    nums["alerts"] = {k: {"raised": v[0], "acted": v[1]} for k, v in by_rule.items()}
    if by_rule:
        raised, acted = sum(v[0] for v in by_rule.values()), sum(v[1] for v in by_rule.values())
        top3 = ", ".join(f"{k} {v[0]}" for k, v in sorted(by_rule.items(), key=lambda kv: -kv[1][0])[:3])
        text += f" {raised} alert{'s' if raised != 1 else ''} ({top3}), {acted} acted on."
    words = [n["note"].strip() for n in notes if (n.get("note") or "").strip()]
    nums["notes"] = len(words)
    if words:   # the household's words as written, each once, with how many times
        seen = {}
        for w in words:
            seen[w[:120]] = seen.get(w[:120], 0) + 1
        text += " What was done: " + "; ".join(f"\u201c{w}\u201d" + (f" \u00d7{k}" if k > 1 else "")
                                              for w, k in list(seen.items())[:8]) + "."
    if prev:
        moved = [f"{SHORT[g]} {nums[g]['mean'] - prev[g]['mean']:+.1f}" for g in GROUPS
                 if g in nums and isinstance(prev.get(g), dict) and abs(nums[g]["mean"] - prev[g]["mean"]) >= 0.1]
        if moved:
            text += f" Against the {scale} before: " + ", ".join(moved) + "."
    nums["v"] = DIGEST_V
    return {"scale": scale, "period_start": start.isoformat(), "label": label(scale, start), "text": text, "numbers": nums}


def write_digests(q, have: set, prev_numbers: dict, today=None, replaced: set = frozenset(), since=None) -> list[dict]:
    """The digests not yet written, oldest first, so each finds the one before it. `have` is {(scale, start iso)};
    `prev_numbers` {(scale, start iso): numbers} of those already kept. `replaced` and `since` as learn_worked: on an
    events node a replaced pack's rows are left out and the episodes that were sent are counted, by issue."""
    first = q("""SELECT min(r.ts) AS t FROM readings r JOIN sensors s USING (sensor_id)
                 WHERE s.kind = 'sensor' AND s.local AND r.ts <= now()""")
    if not first or not first[0]["t"]:
        return []
    first_day = _aware(first[0]["t"]).date()
    now_local = _aware(q("SELECT now() AS t")[0]["t"])
    today = today or now_local.date()
    todo = [p for p in periods(first_day, today) if (p[0], p[1].isoformat()) not in have]
    if not todo:
        return []
    begin = min(p[1] for p in todo)
    rows = q("""SELECT date_trunc('hour', r.ts) AS bucket, r.sensor_id, r.metric, avg(r.value) AS mean, bool_or(s.indoor) AS indoor
                FROM readings r JOIN sensors s USING (sensor_id)
                WHERE s.kind = 'sensor' AND s.local AND r.metric IN ('pm25', 'temp', 'humidity')
                  AND r.ts >= %s::date AND r.ts < %s::date GROUP BY 1, 2, 3""", begin.isoformat(), today.isoformat())
    groups = group_hourly(rows)
    alerts = q("""SELECT l.rule_id, l.ts, l.ts::date AS d,
                         EXISTS (SELECT 1 FROM actions x WHERE x.alert_id = l.id AND x.stage = 'acted') AS acted
                  FROM alerts l WHERE l.level = 'act' AND l.rule_id NOT LIKE '\\_test/%%' AND l.rule_id <> 'gui/test'
                    AND l.ts >= %s::date AND l.ts < %s::date""", begin.isoformat(), today.isoformat())
    alerts = [a for a in alerts if not silent(a["rule_id"], a["ts"], replaced, since)]
    if replaced:
        owner = _issue_packs()
        alerts += [{"rule_id": f"{owner.get(e['issue'], e['issue'])}/events", "name": e["issue"],
                    "d": _aware(e["opened_at"]).date(), "acted": e["acted"]}
                   for e in sent_events(q) if begin <= _aware(e["opened_at"]).date() < today]
    notes = q("""SELECT ts::date AS d, note FROM actions
                 WHERE stage = 'acted' AND coalesce(note, '') <> '' AND ts >= %s::date AND ts < %s::date ORDER BY ts""",
              begin.isoformat(), today.isoformat())
    day = lambda r: r["d"] if not isinstance(r["d"], str) else datetime.fromisoformat(r["d"]).date()  # noqa: E731
    out, last = [], {}
    for scale, start, end in sorted(todo, key=lambda p: (SCALES.index(p[0]), p[1])):
        before = last.get(scale) or prev_numbers.get((scale, _previous(scale, start).isoformat()))
        d = digest(scale, start, end, groups, [a for a in alerts if start <= day(a) < end],
                   [n for n in notes if start <= day(n) < end], before)
        last[scale] = d["numbers"]
        out.append(d)
    return out


def _previous(scale: str, start):
    if scale == "day":
        return start - timedelta(days=1)
    if scale == "week":
        return start - timedelta(days=7)
    if scale == "month":
        return (start - timedelta(days=1)).replace(day=1)
    return start.replace(year=start.year - 1)


def search_terms(text: str) -> str:
    """A tsquery any of whose words may match: words of three letters or more, OR'd. Built from word characters
    only, so nothing a person or a model types reaches to_tsquery's own syntax."""
    import re  # noqa: PLC0415
    return " | ".join(dict.fromkeys(w.lower() for w in re.findall(r"\w{3,}", text or "")))



# ---------------------------------------------------------------- the morning (SPEC_learn §6; Tomas, 14 Oct: on by default)
# The first report the household gets each day carries the house's memory, on Telegram only: yesterday's digest, last
# week's on a Monday, last month's on the 1st, last year's on 1 January, then the learnings whose status changed today.
# One message, not four: more messages is what the household already said no to (#235).
MORNING_HEAD = {"en": "What the node learned, changed today:", "id": "Yang dipelajari node, berubah hari ini:",
                "es": "Lo que aprendió el nodo, cambiado hoy:"}
MORE = {"en": "… the rest with /learned", "id": "… selebihnya dengan /learned", "es": "… el resto con /learned"}
STATUS_WORDS = {"holding": "", "weakening": " (weakening)", "gone": " (gone)"}


def morning_periods(today, push: str = "all") -> list[tuple[str, object]]:
    """[(scale, period_start)] the morning of `today` carries: `push` is LEARN_PUSH, all (default), week or off."""
    from datetime import date  # noqa: PLC0415
    if push == "off":
        return []
    out = [("day", today - timedelta(days=1))] if push != "week" else []
    if today.weekday() == 0:
        out.append(("week", today - timedelta(days=7)))
    if today.day == 1:
        out.append(("month", (today - timedelta(days=1)).replace(day=1)))
        if today.month == 1:
            out.append(("year", date(today.year - 1, 1, 1)))
    return out


def morning(digests: list[str], changed: list[dict], locale: str = "en", room: int = 3000) -> str:
    """The memory's text: each digest as written, then each changed learning's own statement. Parts that do not fit in
    `room` characters are left for /learned, and it says so. "" when there is nothing to say."""
    parts = [f"📔 {t}" for t in digests]
    if changed:
        parts.append(MORNING_HEAD.get(locale, MORNING_HEAD["en"]) + "\n" + "\n".join(
            f"• {r['statement']}{STATUS_WORDS.get(r['status'], '')}" for r in changed))
    out, more = "", MORE.get(locale, MORE["en"])
    for p in parts:
        if len(out) + len(p) + 2 > room - len(more) - 2:
            return (out + "\n\n" + more).strip()
        out = (out + "\n\n" + p).strip()
    return out


# ---------------------------------------------------------------- who is in the house (SPEC_learn §8, step 4)
# Yes/no answers, never a name or an age. They rank what the node learned and let it say why a learning matters here;
# they change no threshold. Who each issue weighs on most: heat on the old, the very young, pregnancy and outdoor work
# (WHO heat-health guidance); fine particles on lungs, the very young, the old and pregnancy (WHO air quality
# guidelines 2021).
PEOPLE = {"older": "someone over 65", "under5": "a child under five", "lungs": "someone with asthma or another lung condition",
          "pregnant": "someone pregnant", "outdoor": "someone who works outdoors"}
AT_RISK = {"heat": ("older", "under5", "pregnant", "outdoor"), "air": ("lungs", "under5", "older", "pregnant")}


def who(issue: str | None, people: dict) -> list[str]:
    """The keys of the people in this house `issue` weighs on most, in AT_RISK's order."""
    kind = "air" if (issue or "").startswith("air") else "heat" if (issue or "").startswith("heat") else None
    return [k for k in AT_RISK.get(kind, ()) if people.get(k) is True]


def for_whom(issue: str | None, people: dict) -> list[str]:
    """The people in this house a learning about `issue` matters most to, in the household's terms."""
    return [PEOPLE[k] for k in who(issue, people)]


# The line an act-level heat or air alert carries to the household's own Telegram when the profile says someone here
# is at more risk (Tomas, 14 Oct 2026: "yes, add it to the alerts"). People ignore alerts mostly because they do not
# feel at risk; this says who is. No sign of its own: the alert above it has one (one per message, 14 Oct). It rides
# the Telegram message only: never the mesh, Reticulum, Home Assistant or
# the stored alert text, which /alerts serves.
PEOPLE_WORDS = {
    "en": PEOPLE,
    "id": {"older": "seseorang berusia di atas 65 tahun", "under5": "anak di bawah lima tahun",
           "lungs": "seseorang dengan asma atau penyakit paru lain", "pregnant": "seseorang yang sedang hamil",
           "outdoor": "seseorang yang bekerja di luar ruangan"},
    "es": {"older": "alguien mayor de 65 años", "under5": "un niño o una niña menor de cinco años",
           "lungs": "alguien con asma u otra enfermedad pulmonar", "pregnant": "alguien embarazada",
           "outdoor": "alguien que trabaja al aire libre"}}
MATTERS = {"en": "This matters more here: you said there is {who}.",
           "id": "Ini lebih penting di sini: Anda mengatakan ada {who}.",
           "es": "Aquí importa más: dijiste que hay {who}."}


def alert_line(issue: str | None, people: dict, locale: str = "en") -> str:
    """The Telegram line for an alert about `issue`, or "" when nobody listed here is at more risk from it."""
    keys = who(issue, people)
    if not keys:
        return ""
    words = PEOPLE_WORDS.get(locale) or PEOPLE_WORDS["en"]
    return (MATTERS.get(locale) or MATTERS["en"]).format(who=", ".join(words[k] for k in keys))


def rank(rows: list[dict], people: dict) -> list[dict]:
    """Each learning with its `for_whom`; within each kind, the ones that matter to someone here first, the order
    otherwise kept."""
    out = [{**r, "for_whom": for_whom(r.get("issue"), people), "name": alert_name(r.get("key")),
            "verdict": VERDICT_WORDS.get(((r.get("numbers") or {}) if isinstance(r.get("numbers"), dict) else {}).get("verdict"))}
           for r in rows]
    return sorted(out, key=lambda r: (r["kind"], not r["for_whom"]))
