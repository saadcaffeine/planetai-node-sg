"""One action per event, chosen from what is happening (docs/SPEC_alerts.md §5), and the message around it.

An issue file lists candidate actions in order; the first whose `when:` holds is the one sent. `when:` is a closed
vocabulary evaluated here, never eval'd: a pack can add actions to an issue, and a pack is not trusted to run code
in this path. A context value the node does not know is None, and a condition on None does not hold, so an action
that needs the outside temperature is never chosen on a node that has none.
"""
from __future__ import annotations

# The three answers to an event (docs/SPEC_alerts.md §7), in the household's language. One table, so the dashboard's
# buttons and the bot's say the same words: the page holds no copy (docs/SPEC_dashboard_events.md §4.4).
BUTTONS = {
    "en": {"done": "Done", "not_now": "Not now", "doesnt_fit": "Doesn't fit"},
    "id": {"done": "Selesai", "not_now": "Nanti dulu", "doesnt_fit": "Tidak cocok"},
    "es": {"done": "Hecho", "not_now": "Ahora no", "doesnt_fit": "No encaja"},
}


def _in_window(h, a, b) -> bool:
    return (a <= h or h < b) if a > b else (a <= h < b)


def _num(x) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def holds(when: dict, ctx: dict) -> bool:
    """Every condition must hold. A condition that is malformed (wrong type, a half hour window, an unknown key) does
    not hold: a typo can narrow an action to never, it cannot widen it to always."""
    when = when or {}
    if not isinstance(when, dict):
        return False
    it, ot = ctx.get("inside_temp"), ctx.get("outside_temp")
    ip, op = ctx.get("inside_pm25"), ctx.get("outside_pm25")
    if "hour_to" in when and "hour_from" not in when:
        return False                                   # a half window is a typo
    if "hour_from" in when:
        a, b, h = when["hour_from"], when.get("hour_to", 24), ctx.get("hour")
        if not (_num(a) and _num(b) and _num(h) and _in_window(h, a, b)):
            return False
    for k, want in when.items():
        if k == "kind":
            ok = isinstance(want, (list, tuple)) and ctx.get("kind") in want
        elif k == "where":
            ok = isinstance(want, str) and want in (ctx.get("where") or set())
        elif k == "home_has":
            ok = isinstance(want, str) and want in (ctx.get("home_has") or set())
        elif k in ("hour_from", "hour_to"):
            continue                                   # checked as a pair above
        elif k == "outside_cooler_by":
            ok = _num(want) and _num(it) and _num(ot) and it - ot >= want
        elif k == "outside_hotter":
            ok = _num(it) and _num(ot) and (ot > it) == bool(want)
        elif k == "outside_pm25_below":
            ok = _num(want) and _num(op) and op < want
        elif k == "outside_worse":
            ok = _num(ip) and _num(op) and (op > ip) == bool(want)
        else:
            return False                               # an unknown key never holds
        if not ok:
            return False
    return True


def choose(actions: list[dict], ctx: dict) -> dict | None:
    for a in actions or []:
        if a.get("id") and holds(a.get("when") or {}, ctx):
            return a
    return None


def _say(block, locale):
    return (block or {}).get(locale) or (block or {}).get("en") or ""


def _fill(block, fields, locale) -> str:
    raw = _say(block, locale)
    try:
        return raw.format(**fields)
    except (KeyError, ValueError, IndexError):
        return raw


# How a message joins the rooms of one event: "Kids and Living Room", not "Kids, Living Room". The engine keeps rooms as
# a sorted set, so the message never claims which came first.
AND = {"en": " and ", "id": " dan ", "es": " y "}


def rooms_said(rooms, locale: str) -> str:
    r = sorted(rooms or [])
    return ", ".join(r[:-1]) + (AND.get(locale) or AND["en"]) + r[-1] if len(r) > 1 else "".join(r)


def _fields(issue: dict, rooms: str, peak, ctx: dict) -> dict:
    """The figures a message or an action may name, in the issue's own dp and with their units. The peak and the line
    carry the issue's unit too (Tomas, 14 Oct: one line per issue, always with its unit), so a template never says a
    bare "15" and never types a unit of its own."""
    dp = int(issue.get("dp", 1))
    unit = issue.get("unit") or ""
    line_v = (issue.get("line") or {}).get("value")

    def fmt(k, v):
        """A figure for a message: the issue's own dp, and the unit the string no longer carries
        (docs/SPEC_language.md — the reading layer names its units, the words don't)."""
        if v is None:
            return "—"
        if k == "peak":
            return f"{float(v):.{dp}f} {unit}".strip()
        if k.endswith("pm25"):
            return f"{float(v):.0f} µg/m³"
        if k.endswith("temp"):
            return f"{float(v):.1f} °C"
        return v

    fields = {"rooms": rooms, "peak": peak,
              "outside_temp": ctx.get("outside_temp"), "inside_temp": ctx.get("inside_temp"),
              "outside_pm25": ctx.get("outside_pm25"), "inside_pm25": ctx.get("inside_pm25"),
              "outside_source": ctx.get("outside_source") or "outside",
              "line": f"{float(line_v):g} {unit}".strip() if line_v is not None else "—",
              "unhealthy": f"{float(issue['unhealthy']):g} {unit}".strip() if issue.get("unhealthy") is not None else "—"}
    return {k: (v if k in ("rooms", "outside_source", "line", "unhealthy") else fmt(k, v)) for k, v in fields.items()}


def render(issue: dict, msg, ctx: dict, locale: str) -> tuple[str, str | None]:
    e = msg.event
    tpl = (issue.get("events") or {}).get(msg.reason if msg.reason == "clear" else e.kind) or {}
    rooms = rooms_said(e.rooms, locale)
    fields = _fields(issue, rooms, e.peak, ctx)
    # no template for this kind: say which issue and where, so a message never starts with an empty line
    text = _fill(tpl, fields, locale) or f"{_say(issue.get('name'), locale) or issue.get('key') or e.issue}: {rooms}"
    if msg.reason == "clear":
        return text, None
    a = choose(issue.get("actions") or [], ctx)
    line = _fill(a.get("say"), fields, locale) if a else ""
    if not line:
        return text, None
    # one sign per message, the story's own: the action is the line under it (events_wire.SENT_ACTION)
    return f"{text}\n{line}", a["id"]


def now_say(issue: dict, ctx: dict, locale: str, rooms, peak) -> dict | None:
    """The action an open event's card shows: chosen again from the context as it is now, by the same rules that
    chose the sent message's. The sent message stays what it was (it is history); the card is the present, so it
    never tells a house to open up on the strength of last night's outside reading."""
    a = choose(issue.get("actions") or [], ctx)
    text = _fill(a.get("say"), _fields(issue, rooms_said(rooms, locale), peak, ctx), locale) if a else ""
    return {"id": a["id"], "text": text} if text else None
