"""Alerts become events (docs/SPEC_alerts.md §4). Pure: candidates and a clock in, messages out.

A kinded rule's row is a Candidate. Every candidate is folded into the one open Event for its issue (heat, air…)
at this house. An event opens on the first candidate that is `over` its line, escalates when its kind climbs or its
value clearly passes its peak, and clears when no candidate (over or inside the margin) has been seen for
CLEAR_AFTER. A margin row — `over` False — keeps an open event open and never opens one: that is the hysteresis.

Whether a message is sent: quiet hours send only `danger`; outside `danger`, at most Policy.max_per_day pushes a
local day; ALERT_LEVEL decides whether a warn event interrupts at all. A held message is still returned, with the
reason, because the report carries it. The same function runs in the app (events_pg.py) and in the replay
(tools/replay_alerts.py), so what is replayed is what ships.
"""
from __future__ import annotations

import datetime as dt
import itertools
from dataclasses import dataclass, field

# Starting values (docs/SPEC_alerts.md §3–§4), set by the replay of node #1's month, not by this file.
KIND_RANK = {"ahead": 0, "unusual": 1, "spike": 1, "sustained": 2, "danger": 3}
ESCALATE_GAP = dt.timedelta(hours=3)            # never two messages for one event closer than this, unless danger
CLEAR_AFTER = dt.timedelta(minutes=30)          # no candidate for this long and the event clears
# Once danger has been said, it is said again only when clearly worse and never sooner than this. Air must double
# (cooking smoke climbing 131 -> 1033 µg/m³ re-sent every five minutes on node #1); other issues keep ESCALATE_STEP.
DANGER_REPEAT_GAP = dt.timedelta(minutes=30)
DANGER_REPEAT_RATIO = {"air": 2.0}
ESCALATE_STEP = {"heat": 2.0, "air": 25.0}      # a value this far past the peak is "clearly worse"; issues without an entry never escalate on value, only on kind
LEVELS = {"info": 0, "warn": 1, "act": 2}


@dataclass(frozen=True)
class Candidate:
    rule_id: str
    issue: str
    kind: str
    level: str
    sensor_id: str
    room: str
    value: float
    line: float
    over: bool
    where: str = "inside"


@dataclass
class Event:
    issue: str
    kind: str
    level: str
    opened_at: dt.datetime
    last_seen_at: dt.datetime
    peak: float
    rooms: set = field(default_factory=set)
    where: set = field(default_factory=set)
    last_sent_at: dt.datetime | None = None
    cleared_at: dt.datetime | None = None
    ever_sent: bool = False
    id: int | None = None
    action_id: str | None = None
    told_kind: str | None = None
    told_peak: float | None = None
    told_level: str | None = None
    told_held: str | None = None
    last_emitted_at: dt.datetime | None = None


@dataclass
class Message:
    event: Event
    reason: str                 # open | escalate | clear
    send: bool
    held: str | None            # quiet | ceiling | level | None


@dataclass(frozen=True)
class Policy:
    quiet: tuple[int, int] | None     # (from_hour, to_hour) local, or None when quiet hours are off
    max_per_day: int
    alert_level: str


class MemoryStore:
    """The store the tests and the replay use. events_pg.PgStore has the same four methods."""

    def __init__(self):
        self._events: list[Event] = []
        self._sends: dict[dt.date, int] = {}
        self._ids = itertools.count(1)

    def open_events(self) -> list[Event]:
        return [e for e in self._events if e.cleared_at is None]

    def save(self, e: Event) -> Event:
        if e.id is None:
            e.id = next(self._ids)
            self._events.append(e)
        return e

    def sends_on(self, day: dt.date) -> int:
        return self._sends.get(day, 0)

    def count_send(self, day: dt.date) -> None:
        self._sends[day] = self._sends.get(day, 0) + 1


def _quiet(now: dt.datetime, quiet: tuple[int, int] | None) -> bool:
    if not quiet:
        return False
    a, b = quiet
    return (a <= now.hour or now.hour < b) if a > b else (a <= now.hour < b)


def _decide(now: dt.datetime, e: Event, store, policy: Policy) -> tuple[bool, str | None]:
    if e.kind == "danger":
        return True, None
    if LEVELS.get(e.level, 0) < LEVELS.get(policy.alert_level, 2):
        return False, "level"
    if _quiet(now, policy.quiet):
        return False, "quiet"
    if store.sends_on(now.date()) >= policy.max_per_day:
        return False, "ceiling"
    return True, None


def _emit(now, e, reason, store, policy) -> Message:
    send, held = _decide(now, e, store, policy)
    # all-clear in quiet hours waits for the morning, regardless of kind
    if reason == "clear" and _quiet(now, policy.quiet):
        send, held = False, "quiet"
    elif reason == "clear" and held == "ceiling":
        send, held = True, None             # an all-clear closes a loop already opened; it does not spend the ceiling
    if send:
        e.last_sent_at, e.ever_sent = now, True
        if e.kind != "danger" and reason != "clear":
            store.count_send(now.date())
    # track what was told in this message (sent or held)
    e.told_kind, e.told_peak, e.told_level, e.told_held, e.last_emitted_at = e.kind, e.peak, e.level, held, now
    store.save(e)
    return Message(e, reason, send, held)


def step(now: dt.datetime, cands: list[Candidate], store, policy: Policy) -> list[Message]:
    """Fold candidates into messages. `now` must be the node's local time (NODE_TZ); quiet hours and the daily
    ceiling read now.hour and now.date()."""
    out: list[Message] = []
    by_issue: dict[str, list[Candidate]] = {}
    for c in cands:
        by_issue.setdefault(c.issue, []).append(c)
    open_by_issue = {e.issue: e for e in store.open_events()}

    for issue, cs in sorted(by_issue.items()):
        over = [c for c in cs if c.over]
        e = open_by_issue.get(issue)
        if e is None:
            if not over:
                continue
            top = max(over, key=lambda c: (KIND_RANK.get(c.kind, 0), c.value))
            e = Event(issue=issue, kind=top.kind, level=max((c.level for c in over), key=lambda l: LEVELS.get(l, 0)),
                      opened_at=now, last_seen_at=now, peak=max(c.value for c in over),
                      rooms={c.room for c in over}, where={c.where for c in over})
            out.append(_emit(now, e, "open", store, policy))
            continue
        e.last_seen_at = now
        e.rooms |= {c.room for c in over}
        e.where |= {c.where for c in over}
        if not over:
            store.save(e)
            continue
        top = max(over, key=lambda c: (KIND_RANK.get(c.kind, 0), c.value))
        # raise level to the highest seen (all over-candidates, not just top)
        e.level = max([e.level, *(c.level for c in over)], key=lambda l: LEVELS.get(l, 0))
        # check escalation against what was told, not current state
        climbed = KIND_RANK.get(top.kind, 0) > KIND_RANK.get(e.told_kind or e.kind, 0)
        level_rise = LEVELS.get(e.level, 0) > LEVELS.get(e.told_level or e.level, 0)
        told_danger = e.told_kind == "danger"
        base = e.told_peak if e.told_peak is not None else e.peak
        if told_danger and issue in DANGER_REPEAT_RATIO:
            worse = top.value >= base * DANGER_REPEAT_RATIO[issue]
        else:
            worse = top.value >= base + ESCALATE_STEP.get(issue, float("inf"))
        # track truth: kind and peak are highest seen
        if KIND_RANK.get(top.kind, 0) > KIND_RANK.get(e.kind, 0):
            e.kind = top.kind
        e.peak = max(e.peak, top.value)
        # escalate if climbed, level rise, or worse, respecting gap from last emitted (not last sent)
        # a message held for 'level' didn't tell anybody, so it doesn't start the gap
        # climbing INTO danger is due at once; danger already said waits DANGER_REPEAT_GAP like any other repeat
        gap = DANGER_REPEAT_GAP if told_danger else ESCALATE_GAP
        due = ((e.kind == "danger" and not told_danger) or e.last_emitted_at is None or e.told_held == "level"
               or now - e.last_emitted_at >= gap)
        if (climbed or level_rise or worse) and due:
            out.append(_emit(now, e, "escalate", store, policy))
        else:
            store.save(e)

    for e in store.open_events():
        if e.issue in by_issue:
            continue
        if now - e.last_seen_at >= CLEAR_AFTER:
            e.cleared_at = now
            if e.ever_sent:
                out.append(_emit(now, e, "clear", store, policy))
            else:
                store.save(e)
    return out
