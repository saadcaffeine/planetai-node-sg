#!/usr/bin/env python3
"""Replay a node's month through today's rules and through the event engine (docs/SPEC_alerts.md §9).

    python3 tools/replay_alerts.py --data DIR [--days 30] [--step 5] [--quiet 22,6] [--max-per-day 4]
                                   [--alert-level warn] [--home-has ac,fan] [--lat -8.82 --lon 115.16]

DIR holds readings.tsv (ts, sensor_id, metric, value) and sensors.tsv (sensor_id, source, name, lat, lon, indoor,
local, kind), read-only from the node: household data, never committed. Rules run in DuckDB exactly as they ship,
with now() set to the replayed instant (tests/trustdb.py), and the node holds no reading later than that instant:
each step loads the readings its clock has passed. The old engine is app/main.py's run_rules: a cooldown per rule
and sensor, ALERT_LEVEL, quiet hours holding all but act. The new engine is app/events.py itself, and each message
chooses its action from what DuckDB says about inside and outside at that instant.

It counts exactly --days whole local days, ending with the last day the data completes, after a one-hour warm-up
that is replayed and not counted. Prints the §9 numbers and writes DIR/old.txt, DIR/new.txt (held messages marked)
and DIR/summary.json.
Needs duckdb (dev only).
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import statistics
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / "app"), str(ROOT / "tests")]
import trustdb as T          # noqa: E402
import events as E           # noqa: E402
import events_pg as P        # noqa: E402
import actions as A          # noqa: E402
import yaml                  # noqa: E402

PACKS = ("heat", "air-quality")
FLOOR = {"info": 0, "warn": 1, "act": 2}                # app/main.py run_rules
LOCAL = dt.timezone(dt.timedelta(hours=8))             # node #1, Asia/Makassar: +08, no DST
HOUR = dt.timedelta(hours=1)
BURST = ("A push is in a burst when it and at least two other pushes fall within one 60-minute span (first to last "
         "under 60 min); a burst is a maximal run of such pushes, each under 60 min after the one before.")
SCOPE = "old side: packs heat and air-quality only (node #1 also runs core sensor_silent and other packs)"


def _pack_rules(pack):
    rs = yaml.safe_load((ROOT / "packs" / pack / "rules.yml").read_text()) or []
    return [dict(r, id=f"{pack}/{r['id']}") for r in rs if not r.get("contributes")]


def old_rules():
    return [r for p in PACKS for r in _pack_rules(p) if not r.get("kind")]


def new_rules():
    return [r for p in PACKS for r in _pack_rules(p) if r.get("kind")]


def _fill(rule, row):
    """The old message as app/main.py fills it: the rule's template, None as an em dash."""
    msg = rule.get("message")
    tmpl = (msg.get("en") or "") if isinstance(msg, dict) else str(msg)
    try:
        return tmpl.format(**{k: ("—" if v is None else v) for k, v in row.items()})
    except (KeyError, ValueError, TypeError):
        return tmpl


def _either(a, b):
    return a if a is not None else b


def context(node, event, t, home_has):
    """What events_pg.context() reads on a node, from DuckDB at `t`: means over the last hour of recent_15m. Inside is
    the event's own indoor rooms (by name or sensor_id), else every local indoor kit; outside is local kits that are
    not indoor. A temperature channel whose declared role is not 'ambient' is left out, as on the node."""
    kits = {sid: (name, indoor, src) for sid, name, indoor, src in
            node.con.execute("SELECT sensor_id, name, indoor, source FROM sensors WHERE local").fetchall()}
    odd = set(node.con.execute("SELECT source, metric FROM channel_roles WHERE role <> 'ambient'").fetchall())
    hour = [(sid, m, v) for b, sid, m, v in node.recent(t)
            if b > t - HOUR and sid in kits and v is not None and (m != "temp" or (kits[sid][2], m) not in odd)]

    def mean(metric, keep):
        vs = [v for sid, m, v in hour if m == metric and keep(sid, *kits[sid][:2])]
        return round(sum(vs) / len(vs), 1) if vs else None

    def room(sid, name, indoor):
        return indoor and (name in event.rooms or sid in event.rooms)

    def inside(sid, name, indoor):
        return indoor

    def outside(sid, name, indoor):
        return not indoor

    local = t.astimezone(LOCAL)
    return {"inside_temp": _either(mean("temp", room), mean("temp", inside)),
            "inside_pm25": _either(mean("pm25", room), mean("pm25", inside)),
            "outside_temp": mean("temp", outside), "outside_pm25": mean("pm25", outside),
            "outside_source": "outside", "hour": local.hour, "where": set(event.where), "kind": event.kind,
            "home_has": set(home_has)}


def _run(node, rule, t, failed, lat, lon):
    """A rule's rows at `t`, or [] when DuckDB cannot run it (its first error is kept, once)."""
    try:
        return node.run(rule, t, lat, lon)
    except Exception as e:  # noqa: BLE001
        failed.setdefault(rule["id"], (str(e).strip().splitlines() or ["?"])[0])
        return []


def _bursts(times):
    """(bursts, pushes in them), as BURST says."""
    ts = sorted(times)
    hit = set()
    for i in range(len(ts)):                          # every 60-minute span that opens on a push
        span = [j for j in range(i, len(ts)) if ts[j] - ts[i] < HOUR]
        if len(span) >= 3:
            hit.update(span)
    marked = [ts[i] for i in sorted(hit)]
    runs = sum(1 for k, t in enumerate(marked) if k == 0 or t - marked[k - 1] >= HOUR)
    return runs, len(marked)


def _side(pushes, days, night):
    per_day = {d: 0 for d in days}
    for p in pushes:
        per_day[p["ts"].date()] += 1
    bursts, in_bursts = _bursts([p["ts"] for p in pushes])
    clears = sum(1 for p in pushes if p["reason"] == "clear")
    return {"pushes": pushes, "per_day": per_day, "night": sum(1 for p in pushes if night(p)),
            "opens_escalates": len(pushes) - clears, "clears": clears,
            "median_per_day": statistics.median(per_day.values()) if per_day else 0,
            "max_per_day": max(per_day.values(), default=0), "bursts": bursts, "in_bursts": in_bursts}


def window(data_end, days):
    """[start, end) in UTC: exactly `days` whole local days, ending with the last one complete before data_end."""
    last = data_end.astimezone(LOCAL).date() - dt.timedelta(days=1)
    first = last - dt.timedelta(days=days - 1)
    midnight = dt.time(tzinfo=LOCAL)
    return (dt.datetime.combine(first, midnight).astimezone(dt.timezone.utc),
            dt.datetime.combine(last + dt.timedelta(days=1), midnight).astimezone(dt.timezone.utc))


def _at_night(ts):
    return ts.hour >= 22 or ts.hour < 6


def _stage(node, rows):
    """Every reading into a staging table the rules never read. One bulk read_csv: executemany costs ~0.3 ms a row,
    minutes for a month of a real node; this is a fraction of a second."""
    node.con.execute("CREATE OR REPLACE TEMP TABLE pending (ts TIMESTAMPTZ, sensor_id TEXT, metric TEXT, value DOUBLE)")
    if not rows:
        return                                          # read_csv cannot sniff an empty file
    with tempfile.TemporaryDirectory() as d:
        f = Path(d) / "readings.tsv"
        f.write_text("".join(f"{ts.isoformat()}\t{sid}\t{m}\t{v!r}\n" for ts, sid, m, v in rows))
        node.con.execute("INSERT INTO pending SELECT * FROM read_csv(?, delim='\t', header=false, quote='', "
                         "columns={'ts': 'TIMESTAMPTZ', 'sensor_id': 'TEXT', 'metric': 'TEXT', 'value': 'DOUBLE'})",
                         [str(f)])


def _load(node, after, upto):
    """The staged readings the clock has just passed, after < ts <= upto (everything up to `upto` when after is None)."""
    lo = f"ts > TIMESTAMPTZ '{after.isoformat()}' AND " if after else ""
    node.con.execute("INSERT INTO readings (ts, sensor_id, metric, value) SELECT DISTINCT ON (ts, sensor_id, metric) "
                     f"ts, sensor_id, metric, value FROM pending WHERE {lo}ts <= TIMESTAMPTZ '{upto.isoformat()}'")


def replay(node, rows, rules_old, rules_new, start, end, step_min, policy, home_has=(), lat=None, lon=None,
           warmup=HOUR):
    """Both engines over [start - warmup, end) (UTC-aware) every `step_min` minutes; only [start, end) is counted, so
    cooldowns and open events are warm when counting begins. `node` holds sensors and no readings; `rows` are
    (ts_utc, sensor_id, metric, value) and are loaded as the clock passes them, never ahead of it.

    Returns {"old": side, "new": side, "not_replayed": {rule_id: first error line}, "coords": {lat, lon, from}};
    a side is {pushes, per_day, night, opens_escalates, clears, median_per_day, max_per_day, bursts, in_bursts}, a
    push {ts (local), what, text, kind, reason, held, action}. `new` also has `held` (every held message) and
    `held_by` {reason: n}. Night counts every old push 22:00–06:00 (act ignores quiet hours) and every new
    non-danger SENT push in that window. Every old push is an open (reason "open"): it has no all-clear."""
    naive = next((r for r in rows if r[0].tzinfo is None), None)
    if naive or start.tzinfo is None or end.tzinfo is None:
        raise ValueError(f"replay needs time-zone-aware timestamps (readings are UTC); got {naive or (start, end)}")
    issues = {k: yaml.safe_load((ROOT / "app/issues" / f"{k}.yml").read_text()) for k in ("heat", "air")}
    coords = {"lat": lat, "lon": lon, "from": "--lat/--lon"}
    if lat is None:
        # the node's coordinates are a setting a rule reads (planetai.lat/lon); stand in its local kits' centre
        lat, lon = node.con.execute("SELECT avg(lat), avg(lon) FROM sensors WHERE local AND (lat <> 0 OR lon <> 0)").fetchone()
        coords = {"lat": lat, "lon": lon, "from": "local kits' centre"}
    _stage(node, rows)
    prev = None
    failed, last, store = {}, {}, E.MemoryStore()
    old, new, held = [], [], []
    refreshed, t = None, start - warmup
    while t < end:
        counted = t >= start
        _load(node, prev, t)
        prev = t
        if refreshed is None or t - refreshed >= HOUR:
            node.refresh_usual(t)
            refreshed = t
        local = t.astimezone(LOCAL)
        for r in rules_old:
            for row in _run(node, r, t, failed, lat, lon):
                key = (r["id"], str(row.get("sensor_id", "node")))
                cool = dt.timedelta(minutes=int(r.get("cooldown_minutes", 60)))
                if key in last and t - last[key] < cool:
                    continue
                last[key] = t                          # the alerts row is written whether or not it is sent
                lvl = r.get("level", "info")
                if counted and FLOOR.get(lvl, 0) >= FLOOR.get(policy.alert_level, 2) and not (
                        lvl != "act" and E._quiet(local, policy.quiet)):
                    old.append({"ts": local, "what": r["id"], "text": _fill(r, row), "kind": None, "reason": "open",
                                "held": None, "action": None})
        cands = []
        for r in rules_new:
            cands += P.candidates(r, _run(node, r, t, failed, lat, lon))
        for m in E.step(local, cands, store, policy):
            text, aid = None, None
            if not counted:
                continue
            if m.event.issue in issues:
                try:
                    text, aid = A.render(issues[m.event.issue], m, context(node, m.event, t, home_has), "en")
                except Exception as e:  # noqa: BLE001
                    text = f"(could not render: {e})"
            p = {"ts": local, "what": m.event.issue, "text": text or f"{m.event.issue} {m.reason}",
                 "kind": m.event.kind, "reason": m.reason, "held": m.held, "action": aid}
            (new if m.send else held).append(p)
        t += dt.timedelta(minutes=step_min)

    a, b = start.astimezone(LOCAL).date(), (end - dt.timedelta(microseconds=1)).astimezone(LOCAL).date()
    days = [a + dt.timedelta(days=k) for k in range((b - a).days + 1)]
    out_new = _side(new, days, lambda p: p["kind"] != "danger" and _at_night(p["ts"]))
    out_new["held"] = held
    out_new["held_by"] = {k: sum(1 for p in held if p["held"] == k) for k in ("quiet", "ceiling", "level")}
    return {"old": _side(old, days, lambda p: _at_night(p["ts"])), "new": out_new, "not_replayed": failed,
            "coords": coords}


def _write(path, pushes):
    with open(path, "w") as f:
        for p in sorted(pushes, key=lambda p: p["ts"]):
            mark = f" (held: {p['held']})" if p["held"] else ""
            f.write(f"--- {p['ts']:%Y-%m-%d %H:%M} {p['what']}{mark}\n{p['text']}\n\n")


def main():
    t0 = time.monotonic()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", required=True, help="directory holding readings.tsv and sensors.tsv")
    ap.add_argument("--days", type=int, default=30, help="whole local days counted, ending the day before the data does")
    ap.add_argument("--step", type=int, default=5, help="minutes between replayed instants")
    ap.add_argument("--quiet", default="22,6", help="FROM,TO local hours, or 'off'")
    ap.add_argument("--max-per-day", type=int, default=4)
    ap.add_argument("--alert-level", default="warn", choices=sorted(FLOOR))
    ap.add_argument("--home-has", default="", help="comma list: purifier,ac,fan,windows")
    ap.add_argument("--lat", type=float, help="the node's latitude (planetai.lat); default: its local kits' centre")
    ap.add_argument("--lon", type=float, help="the node's longitude (planetai.lon)")
    a = ap.parse_args()
    if (a.lat is None) != (a.lon is None):
        ap.error("--lat and --lon go together")
    d = Path(a.data)
    rows = T.readings_from(d / "readings.tsv")
    node = T.Node([], who=T.sensors_from(d / "sensors.tsv"))
    start, end = window(max(r[0] for r in rows), a.days)
    quiet = None if a.quiet == "off" else tuple(int(x) for x in a.quiet.split(","))
    pol = E.Policy(quiet=quiet, max_per_day=a.max_per_day, alert_level=a.alert_level)
    home = {x.strip() for x in a.home_has.split(",") if x.strip()}
    res = replay(node, rows, old_rules(), new_rules(), start, end, a.step, pol, home, a.lat, a.lon)

    news = {r["id"] for r in new_rules()}
    for rid, err in sorted(res["not_replayed"].items()):
        print(f"{'NEW RULE ' if rid in news else ''}not replayed: {rid}: {err}")
    print(f"scope: {SCOPE}")
    print(f"counted: {start.astimezone(LOCAL):%Y-%m-%d %H:%M} to {end.astimezone(LOCAL):%Y-%m-%d %H:%M} local "
          f"({a.days} whole days, after a one-hour warm-up); coordinates from {res['coords']['from']}")
    print(f"{'':4} {'pushes':>7} {'opens':>6} {'clears':>7} {'median/day':>11} {'max/day':>8} {'night':>6} "
          f"{'bursts':>7} {'in bursts':>10}")
    summary = {"days": a.days, "step": a.step, "start": start.isoformat(), "end": end.isoformat(),
               "policy": {"quiet": quiet, "max_per_day": a.max_per_day, "alert_level": a.alert_level},
               "home_has": sorted(home), "coords": res["coords"], "scope": SCOPE, "burst_definition": BURST,
               "not_replayed": res["not_replayed"]}
    for side in ("old", "new"):
        s = res[side]
        print(f"{side:4} {len(s['pushes']):7} {s['opens_escalates']:6} {s['clears']:7} {s['median_per_day']:11} "
              f"{s['max_per_day']:8} {s['night']:6} {s['bursts']:7} {s['in_bursts']:10}")
        summary[side] = {"pushes": len(s["pushes"]), **{k: s[k] for k in (
            "opens_escalates", "clears", "median_per_day", "max_per_day", "night", "bursts", "in_bursts")},
            "per_day": {str(k): v for k, v in s["per_day"].items()}}
    summary["new"]["held_by"] = res["new"]["held_by"]
    print(f"new held: {res['new']['held_by']}   (night: old counts every push 22-06, new its non-danger sends)")
    _write(d / "old.txt", res["old"]["pushes"])
    _write(d / "new.txt", res["new"]["pushes"] + res["new"]["held"])
    summary["runtime_seconds"] = round(time.monotonic() - t0, 1)
    (d / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(f"messages: {d / 'old.txt'} and {d / 'new.txt'}; numbers: {d / 'summary.json'} "
          f"({summary['runtime_seconds']} s)")


if __name__ == "__main__":
    main()
