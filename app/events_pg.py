"""The event engine against Postgres: candidates from kinded rules, a Policy from settings, and a store.
docs/SPEC_alerts.md §4. The decisions are app/events.py's; this file only reads and writes.
The table is alert_events: `events` is the parent's ledger of what its children pushed (init.sql, v0.50)."""
from __future__ import annotations

import datetime as dt
import logging

import actions as A
import events as E
import issues
import settings

log = logging.getLogger("planetai")
# a pack's domain is its issue unless a rule says otherwise
PACK_ISSUE = {"air-quality": "air", "heat": "heat"}
HOME_ITEMS = ("purifier", "ac", "fan", "windows")


def candidates(rule: dict, rows: list[dict]) -> list[E.Candidate]:
    kind = rule.get("kind")
    if not kind:
        return []                                     # report-only: never interrupts (SPEC_alerts §3)
    pack = rule["id"].split("/", 1)[0]
    issue = rule.get("issue") or PACK_ISSUE.get(pack, pack)
    out = []
    for r in rows:
        if r.get("value") is None or r.get("line") is None:
            continue
        out.append(E.Candidate(rule_id=rule["id"], issue=issue, kind=kind, level=rule.get("level", "info"),
                               sensor_id=str(r.get("sensor_id", "node")), room=str(r.get("name") or r.get("sensor_id")),
                               value=float(r["value"]), line=float(r["line"]), over=bool(r.get("over", True)),
                               where=str(r.get("where") or "inside")))
    return out


def policy() -> E.Policy:
    quiet = (settings.num("QUIET_FROM", 22), settings.num("QUIET_TO", 6)) if settings.get("QUIET_HOURS", "1") == "1" else None
    return E.Policy(quiet=quiet, max_per_day=settings.num("ALERT_MAX_PER_DAY", 4),
                    alert_level=settings.get("ALERT_LEVEL", "act") or "act")


def home_has() -> set[str]:
    return {x.strip() for x in (settings.get("HOME_HAS", "") or "").split(",") if x.strip() in HOME_ITEMS}


# Event fields <-> alert_events columns; `where` is the column `places` (WHERE is a keyword), sets are TEXT[].
COLS = ("issue", "kind", "level", "opened_at", "last_seen_at", "last_sent_at", "cleared_at", "peak", "rooms", "places",
        "ever_sent", "action_id", "told_kind", "told_peak", "told_level", "told_held", "last_emitted_at")


class PgStore:
    """MemoryStore's four methods, kept in `alert_events` and `event_messages`."""

    def __init__(self, cur):
        self.cur = cur
        self._pending: dict[dt.date, int] = {}        # sends decided in this step, not yet in event_messages

    def open_events(self) -> list[E.Event]:
        self.cur.execute("SELECT * FROM alert_events WHERE cleared_at IS NULL")
        return [E.Event(**{k: r[k] for k in COLS if k not in ("rooms", "places")}, rooms=set(r["rooms"]),
                        where=set(r["places"]), id=r["id"]) for r in self.cur.fetchall()]

    def save(self, e: E.Event) -> E.Event:
        vals = [sorted(e.rooms) if c == "rooms" else sorted(e.where) if c == "places" else getattr(e, c) for c in COLS]
        if e.id is None:
            self.cur.execute(f"INSERT INTO alert_events ({', '.join(COLS)}) VALUES ({', '.join(['%s'] * len(COLS))}) RETURNING id", vals)
            e.id = self.cur.fetchone()["id"]
        else:
            self.cur.execute(f"UPDATE alert_events SET {', '.join(c + '=%s' for c in COLS)} WHERE id=%s", (*vals, e.id))
        return e

    def sends_on(self, day: dt.date) -> int:
        self.cur.execute("""SELECT count(*) AS n FROM event_messages m
                            WHERE m.sent AND m.reason <> 'clear' AND m.kind <> 'danger'
                              AND (m.ts AT TIME ZONE current_setting('TimeZone'))::date = %s""", (day,))
        return self.cur.fetchone()["n"] + self._pending.get(day, 0)

    def count_send(self, day: dt.date) -> None:
        self._pending[day] = self._pending.get(day, 0) + 1   # run() writes the row; this covers the rest of the step


# What the node knows about inside and outside, for choosing the action (actions.py: a None never holds).
# `t` is the local sensors' rolling stats, minus any temperature channel whose declared role is not 'ambient' (a
# Meshtastic box's enclosure temp is not the room's air). A (source, metric) with no declared role is kept.
# inside_*: the event's own indoor rooms (matched by name or sensor_id, as candidates() falls back to the id), else the
# mean of every local indoor sensor: an outdoor event has no indoor rooms, and the house still has an inside.
# om-point's `temp_model` is the Open-Meteo current-hour sample: a fallback for outside_temp, never older than 2 h.
CTX_SQL = """
WITH t AS (
  SELECT st.sensor_id, st.name, st.indoor, st.metric, st.mean_15m, st.mean_1h
  FROM stats st JOIN sensors s USING (sensor_id)
  WHERE st.local AND (st.metric <> 'temp' OR NOT EXISTS (
          SELECT 1 FROM channel_roles c WHERE c.source = s.source AND c.metric = st.metric AND c.role <> 'ambient'))
)
SELECT
  coalesce((SELECT avg(mean_15m) FROM t WHERE indoor AND metric = 'temp' AND (name = ANY(%(rooms)s) OR sensor_id = ANY(%(rooms)s))),
           (SELECT avg(mean_15m) FROM t WHERE indoor AND metric = 'temp')) AS inside_temp,
  coalesce((SELECT avg(mean_15m) FROM t WHERE indoor AND metric = 'pm25' AND (name = ANY(%(rooms)s) OR sensor_id = ANY(%(rooms)s))),
           (SELECT avg(mean_15m) FROM t WHERE indoor AND metric = 'pm25')) AS inside_pm25,
  coalesce((SELECT avg(mean_1h) FROM t WHERE NOT indoor AND metric = 'temp'),
           (SELECT value FROM observations WHERE sensor_id = 'om-point' AND metric = 'temp_model'
              AND ts <= now() AND ts > now() - INTERVAL '2 hours')) AS outside_temp,
  (SELECT avg(mean_1h) FROM t WHERE NOT indoor AND metric = 'pm25') AS outside_pm25,
  CASE WHEN EXISTS (SELECT 1 FROM t WHERE NOT indoor AND metric = 'temp' AND mean_1h IS NOT NULL)
       THEN 'outside'::text ELSE 'the forecast model'::text END AS outside_source  -- ::text, or psycopg hands back bytes
"""


def context(cur, e: E.Event, now: dt.datetime) -> dict:
    cur.execute(CTX_SQL, {"rooms": sorted(e.rooms)})
    ctx = dict(cur.fetchone())
    for k in ("inside_temp", "inside_pm25", "outside_temp", "outside_pm25"):
        if ctx[k] is not None:
            ctx[k] = round(float(ctx[k]), 1)
    ctx.update(hour=now.hour, home_has=home_has(), where=set(e.where), kind=e.kind)
    return ctx


def run(cur, cands: list[E.Candidate], mode: str, now: dt.datetime) -> list[tuple[E.Message, str | None]]:
    """One engine step. Every decided message is recorded; in shadow, `sent` records what WOULD have gone out.
    One transaction (a block of its own on the app's autocommit connection): no event row without its message.
    Returns each decided message with its rendered text, so the caller can send after the transaction commits."""
    out = []
    with cur.connection.transaction():
        msgs = E.step(now, cands, PgStore(cur), policy())
        decl = issues.load() if msgs else {}
        for m in msgs:
            text, aid = None, None
            if m.event.issue in decl:
                try:
                    # a savepoint of its own: a bad template or a failed query costs this message its text, not the step
                    with cur.connection.transaction():
                        text, aid = A.render(decl[m.event.issue], m, context(cur, m.event, now),
                                             settings.get("ALERT_LOCALE", "en") or "en")
                except Exception as ex:  # noqa: BLE001
                    log.warning("event %s: could not render (%s)", m.event.id, ex)
                    text, aid = None, None
            if aid:
                m.event.action_id = aid
                cur.execute("UPDATE alert_events SET action_id = %s WHERE id = %s", (aid, m.event.id))
            cur.execute("INSERT INTO event_messages (ts, event_id, reason, kind, sent, held, mode, text, action_id) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                        (now, m.event.id, m.reason, m.event.kind, m.send, m.held, mode, text, aid))
            out.append((m, text))
    return out


# The three buttons (docs/SPEC_alerts.md §7): Not now, Done, Doesn't fit. `decided` is not one: the buttons are the
# decision, and DECISION_REQUIRED applies to alert-based acts only (docs/SPEC_dashboard_events.md §3.2).
EVENT_STAGES = ("acknowledged", "acted", "dismissed")


def answer(cur, event_id, stage, actor, note) -> None:
    """A button pressed on an event, from the dashboard or (Plan 2) the bot: one actions row with event_id and no
    alert_id. Every ρ, funnel and effect query joins actions to alerts on alert_id, so this row changes no published
    number until Plan 2's decision record says how events count."""
    if stage not in EVENT_STAGES:
        raise ValueError("an event's stage must be acknowledged, acted or dismissed")
    if isinstance(event_id, bool) or isinstance(event_id, float):
        raise ValueError("event_id must be a whole number")
    try:
        eid = int(event_id)
    except (TypeError, ValueError):
        raise ValueError("event_id must be a whole number") from None
    cur.execute("SELECT 1 FROM alert_events WHERE id = %s", (eid,))
    if not cur.fetchone():
        raise LookupError("no such event")
    cur.execute("INSERT INTO actions (event_id, stage, actor, note) VALUES (%s,%s,%s,%s)",
                (eid, stage, str(actor or "")[:80], str(note or "")[:500]))
