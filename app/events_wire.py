"""The alert events as GET /issues carries them (docs/SPEC_dashboard_events.md §3.1).

`build` is pure, so a live node (datetimes) and a capture (ISO strings) go through the same code and are tested apart.
`live` (Task 3) is the reads, on the cursor the /issues route already has open. The page computes nothing from this
block: every number and sentence the event card draws is here.
"""
from __future__ import annotations

import datetime as dt
import logging
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import actions as A
import settings

log = logging.getLogger("planetai")

ENGINES = ("rules", "shadow", "events")
ORDER = ("danger", "sustained", "unusual", "spike", "ahead")   # which open event leads (§3.1)
HOLD = dt.timedelta(hours=3)                                   # Not now: docs/SPEC_alerts.md §7
RECENT = dt.timedelta(days=7)                                  # Act's record (§4.3)
OUTSIDE = {"apparent": "temp", "temp": "temp", "pm25": "pm25"}  # an issue's metric -> events_pg.context's outside_*
SENT_ACTION = "\n"              # how actions.render puts the action under the story, since 14 Oct (one sign per message)
SENT_ACTION_OLD = "\n\n👉 "     # how it did before: messages already sent keep it, and their cards still find the action


def _action_of(said: str):
    """The action line of a sent message: under the story, in the old shape or the new one; None when there is none."""
    for sep in (SENT_ACTION_OLD, SENT_ACTION):
        if sep in said:
            return said.split(sep, 1)[1]
    return None


def engine_of(value) -> str:
    """run_rules' own reading of ALERT_ENGINE: anything else behaves as rules."""
    return value if value in ENGINES else "rules"


def _t(v):
    if v is None or isinstance(v, dt.datetime):
        return v
    return dt.datetime.fromisoformat(str(v).replace("Z", "+00:00"))


def _iso(v):
    v = _t(v)
    return v.isoformat() if v else None


def _latest(rows: list[dict]) -> dict:
    out = {}
    for r in rows:
        k = r["event_id"]
        if k not in out or _t(r["ts"]) > _t(out[k]["ts"]):
            out[k] = r
    return out


def rank(row: dict) -> tuple:
    """Lower sorts first: the most serious kind, then the one open longest."""
    k = row["kind"]
    return (ORDER.index(k) if k in ORDER else len(ORDER), _t(row["opened_at"]))


def _answer(a: dict | None, kind: str) -> dict | None:
    if not a:
        return None
    held = _t(a["ts"]) + HOLD if a["stage"] == "acknowledged" and kind != "danger" else None
    # The note is the household's own words ("what did you do instead?"): recorded at the press or ridden in on a
    # second row, and shown on the card — an answer without it is a vote, an answer with it is a story.
    return {"stage": a["stage"], "actor": a.get("actor"), "ts": _iso(a["ts"]), "held_until": _iso(held),
            "note": a.get("note") or None}


def build(engine, events, messages, answers, covered, contexts, decl, locale, now, tz=None) -> dict:
    tz = tz or now.tzinfo or dt.timezone.utc
    last_msg = _latest(messages)
    last_act = _latest([m for m in messages if m.get("action_id")])
    last_ans = _latest(answers)
    opened, recent, cleared_today, last = [], [], 0, None
    for e in events:
        eid, cleared = e["id"], _t(e.get("cleared_at"))
        if cleared is not None and now - cleared > RECENT:
            continue
        if cleared is None and engine == "rules":
            continue                     # the engine is not running: an event a shadow spell left open is not open
        issue = decl.get(e["issue"]) or {}
        m, am, a = last_msg.get(eid), last_act.get(eid), last_ans.get(eid)
        said = (am.get("text") or "") if am else ""
        row = {"id": eid, "issue": e["issue"], "kind": e["kind"], "level": e["level"],
               "opened_at": _iso(e["opened_at"]), "last_seen_at": _iso(e["last_seen_at"]), "cleared_at": _iso(cleared),
               "peak": e.get("peak"), "line": (issue.get("line") or {}).get("value"),
               "rooms": sorted(e.get("rooms") or []), "places": sorted(e.get("places") or []),
               "action": ({"id": am["action_id"], "text": _action_of(said)}
                          if am else None),
               "message": {"text": m.get("text"), "ts": _iso(m["ts"]), "sent": bool(m.get("sent"))} if m else None,
               "alerts": sorted(covered.get(eid) or []),
               "answer": _answer(a, e["kind"])}
        # Whether the card still asks: until somebody answers, and again once a Not now's hold has run out (the node
        # asks again then). Every page draws its buttons from this, so an answered card never offers them twice.
        held = (row["answer"] or {}).get("held_until")
        row["asking"] = cleared is None and (a is None or (a["stage"] == "acknowledged" and held is not None
                                                            and _t(held) <= now))
        if cleared is None:
            ctx, key = contexts.get(eid) or {}, OUTSIDE.get(issue.get("metric"))
            # The card is the present: its action is chosen again from the context as it is now. The message that
            # was sent keeps its words, as history.
            if ctx:
                row["action"] = A.now_say(issue, ctx, locale, e.get("rooms"), e.get("peak")) or row["action"]
            outside = ctx.get(f"outside_{key}") if key else None
            # outside_source only describes the temperature; an outside PM2.5 always came from an outdoor sensor
            came = None if outside is None else "outside" if key == "pm25" else ctx.get("outside_source")
            row["context"] = {"usual": ctx.get("usual"), "outside": outside, "outside_metric": key, "outside_from": came}
            opened.append(row)
            continue
        if a and a["stage"] == "acted" and cleared > _t(a["ts"]):
            row["cleared_after_min"] = round((cleared - _t(a["ts"])).total_seconds() / 60)
        recent.append(row)
        if cleared.astimezone(tz).date() == now.astimezone(tz).date():
            cleared_today += 1
            if last is None or cleared > _t(last["ts"]):
                last = {"issue": e["issue"], "ts": cleared.isoformat()}
    opened.sort(key=rank)
    recent.sort(key=lambda r: _t(r["cleared_at"]), reverse=True)
    return {"engine": engine, "buttons": A.BUTTONS.get(locale) or A.BUTTONS["en"],
            "open": opened, "recent": recent, "cleared_today": cleared_today, "last_cleared": last}


USUAL_SQL = """SELECT avg(u.median) AS usual FROM usual_by_hour u JOIN sensors s USING (sensor_id)
               WHERE u.metric = %s AND u.hour = %s AND (s.name = ANY(%s) OR s.sensor_id = ANY(%s))"""


def _context(cur, P, e: dict, metric: str | None, hour: int, now) -> dict:
    """Inside and outside from the resolver that chose the action, and this room's usual for this local hour. Each is a
    savepoint of its own: usual_by_hour is empty from a start until the app's first refresh, and a context that cannot
    be read is null on the card, not a failed /issues."""
    ctx: dict = {}
    rooms = sorted(e.get("rooms") or [])
    try:
        with cur.connection.transaction():
            ctx = dict(P.context(cur, SimpleNamespace(rooms=set(rooms), where=set(e.get("places") or []),
                                                      kind=e["kind"]), now))
    except Exception as ex:  # noqa: BLE001
        log.warning("event %s: no context (%s)", e["id"], type(ex).__name__)
    ctx["usual"] = None
    try:
        with cur.connection.transaction():
            cur.execute(USUAL_SQL, (metric, hour, rooms, rooms))
            u = (cur.fetchone() or {}).get("usual")
            ctx["usual"] = None if u is None else round(float(u), 1)
    except Exception as ex:  # noqa: BLE001
        log.info("event %s: no usual for this hour (%s)", e["id"], type(ex).__name__)
    return ctx


def live(cur, decl: dict, locale: str, now: dt.datetime) -> dict:
    """The block, read on the /issues route's cursor. The session runs in NODE_TZ (app/main.py), so the hour and the
    zone come from Postgres, the same clock usual_by_hour was bucketed on."""
    import events_pg as P            # noqa: PLC0415 — events_pg imports issues, whose route imports this module
    engine = engine_of(settings.get("ALERT_ENGINE", "rules"))
    cur.execute("SELECT current_setting('TimeZone') AS tz, extract(hour FROM now())::int AS hour")
    r = cur.fetchone()
    try:
        tz = ZoneInfo(r["tz"])
    except Exception:  # noqa: BLE001 — an offset Postgres names that zoneinfo does not: fall back to now's own zone
        tz = None
    cur.execute("SELECT id, issue, kind, level, opened_at, last_seen_at, cleared_at, peak, rooms, places, action_id "
                "FROM alert_events WHERE cleared_at IS NULL OR cleared_at > %s", (now - RECENT,))
    events = [dict(x) for x in cur.fetchall()]
    ids = [e["id"] for e in events]
    cur.execute("SELECT event_id, ts, text, sent, action_id FROM event_messages WHERE event_id = ANY(%s)", (ids,))
    messages = [dict(x) for x in cur.fetchall()]
    cur.execute("SELECT event_id, ts, stage, actor, note FROM actions WHERE event_id = ANY(%s)", (ids,))
    answers = [dict(x) for x in cur.fetchall()]
    covered, contexts = {}, {}
    for e in events:
        # Until Plan 2 writes alerts.event_id, an event covers its issue's pack's rows inside its own window.
        packs = [(decl.get(e["issue"]) or {}).get("pack") or e["issue"]]      # the pack that ships the issue
        cur.execute("SELECT id FROM alerts WHERE event_id = %s OR (split_part(rule_id, '/', 1) = ANY(%s) "
                    "AND ts >= %s AND ts <= %s)", (e["id"], packs, e["opened_at"], e["cleared_at"] or now))
        covered[e["id"]] = [x["id"] for x in cur.fetchall()]
        if e["cleared_at"] is None and engine != "rules":
            contexts[e["id"]] = _context(cur, P, e, (decl.get(e["issue"]) or {}).get("metric"), r["hour"], now)
    out = build(engine, events, messages, answers, covered, contexts, decl, locale, now, tz)
    out["sent_24h"] = _sent(cur, engine, now)
    return out


LEVELS = {"act": 2, "warn": 1, "info": 0}


def _sent(cur, engine: str, now: dt.datetime) -> int:
    """What reached a phone in the last 24 hours, for the Node door's "Alerts, to a phone". An alerts row is written
    whether or not it was sent, so this counts what run_rules sends (app/main.py): a row at ALERT_LEVEL or above, never
    one of a pack the event engine speaks for once it has spoken (learn.silent), and the engine's own sent messages.
    Counting every row said 30 on node #1 when the engine had sent a handful.
    ponytail: quiet hours leave no trace in the table, so a warn they held still counts; a `sent` column if it matters."""
    import learn                     # noqa: PLC0415
    import packs                     # noqa: PLC0415
    floor = LEVELS.get(settings.get("ALERT_LEVEL", "act"), LEVELS["act"])
    replaced = {r["id"].split("/", 1)[0] for r in packs.load_rules() if r.get("kind")} if engine == "events" else set()
    cur.execute("SELECT min(ts) AS since FROM event_messages WHERE mode = 'events'")
    since = (cur.fetchone() or {}).get("since")
    cur.execute("SELECT rule_id, level, ts FROM alerts WHERE ts > %s", (now - dt.timedelta(hours=24),))
    rows = [x for x in cur.fetchall() if LEVELS.get(x.get("level"), 0) >= floor
            and not learn.silent(x.get("rule_id") or "", x.get("ts"), replaced, since)]
    cur.execute("SELECT count(*) AS n FROM event_messages WHERE sent AND mode = 'events' AND ts > %s",
                (now - dt.timedelta(hours=24),))
    return len(rows) + int((cur.fetchone() or {}).get("n") or 0)
