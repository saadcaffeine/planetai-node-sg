"""The Telegram buttons contract (SPEC_alerts §7): the keyboard the app writes under an event message and the
parser the bot answers it with are two ends of one promise — ev:<event_id>:<stage> — and the Doesn't-fit
follow-up keeps a note without ever eating a command or a stale chat line.

No imports of main or agent_loop (importing either starts side effects): the functions are lifted whole by AST,
the way tests/test_run_rules_modes.py lifts run_rules."""

import ast
import asyncio
import logging
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "app"))
import actions  # noqa: E402 — the wire's own button words


def _lift(path, names, ns):
    tree = ast.parse((ROOT / "app" / path).read_text())
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in names:
            exec(compile(ast.Module([node], []), str(path), "exec"), ns)
        if isinstance(node, ast.Assign) and any(getattr(t, "id", None) in names for t in node.targets):
            exec(compile(ast.Module([node], []), str(path), "exec"), ns)
    return ns


_m = _lift("main.py", {"_event_keyboard"}, {"_act": actions})
keyboard = _m["_event_keyboard"]

_b = _lift("agent_loop.py", {"parse_callback", "note_pending", "NOTE_WINDOW", "node_url"}, {"re": re})
parse_callback, note_pending, NOTE_WINDOW = _b["parse_callback"], _b["note_pending"], _b["NOTE_WINDOW"]

# The audit's caveat, pinned: the actions URL never depends on the letters "/mcp" being present in MCP_URL.
for mcp, want in (("http://app:8080/mcp", "http://app:8080/actions"),
                  ("http://app:8080", "http://app:8080/actions"),
                  ("http://app:8080/", "http://app:8080/actions")):
    fn = _lift("agent_loop.py", {"node_url"}, {"MCP_URL": mcp})["node_url"]
    assert fn("/actions") == want, f"MCP_URL={mcp!r}: {fn('/actions')}"


# The keyboard is the wire's three words, one row, in every locale the wire speaks.
for loc, words in (("en", ("Done", "Not now", "Doesn't fit")),
                   ("id", ("Selesai", "Nanti dulu", "Tidak cocok")),
                   ("es", ("Hecho", "Ahora no", "No encaja"))):
    kb = keyboard(12, loc)
    assert len(kb) == 1 and len(kb[0]) == 3, f"one row of three buttons: {kb}"
    assert tuple(b["text"] for b in kb[0]) == words, f"{loc}: {kb[0]}"
    for b in kb[0]:
        assert "callback_data" in b and "url" not in b, "a button carries callback_data, never a link"
        assert parse_callback(b["callback_data"]) is not None, \
            f"every button the app writes must parse at the bot's end: {b}"
# An unknown locale falls back to English, as the wire does.
assert tuple(b["text"] for b in keyboard(12, "fr")[0]) == ("Done", "Not now", "Doesn't fit")

# The round trip: what the app writes, the bot reads back as (event, stage), and only those three stages.
assert [(parse_callback(b["callback_data"])) for b in keyboard(12, "en")[0]] == \
    [(12, "acted"), (12, "acknowledged"), (12, "dismissed")]
for bad in (None, "", "ev:12", "ev:x:acted", "ev:12:decided", "EV:12:acted", "ev:12:acted:extra", "12:acted"):
    assert parse_callback(bad) is None, f"the parser refuses {bad!r}: the page's stages are ack/acted/decided, and an event's are not"

# The Doesn't-fit follow-up: one free-text line inside the window becomes the note, once.
pending = {"1": (12, 100.0)}
assert note_pending(pending, "2", "opened the window", 120.0) is None, "another chat's line is never the note"
assert note_pending(pending, "1", "/stack", 120.0) is None and "1" in pending, "a command is never a note, and the ask stays open"
assert note_pending(pending, "1", "opened the window", 120.0) == 12, "the first free-text line is the note"
assert "1" not in pending and note_pending(pending, "1", "again", 130.0) is None, "the ask is answered once"
pending = {"1": (12, 100.0)}
assert note_pending(pending, "1", "too late", 100.0 + NOTE_WINDOW + 1) is None and "1" not in pending, \
    "a stale ask is forgotten, not answered"

# ---- pack buttons: al:<alert_id>:<value> (the event path above is untouched) ----
import buttons  # noqa: E402

TG = []            # every telegram() call the bot made, in order


class _Resp:
    def __init__(self, code, body):
        self.status_code, self._body = code, body

    def json(self):
        return self._body

    def raise_for_status(self):
        if self.status_code >= 400:
            e = RuntimeError(str(self.status_code))
            e.response = self
            raise e


class _Node:
    """The node, as the bot sees it: GET /alerts, and POST /actions with the three answers B3 gives."""
    def __init__(self, alerts, offered=("good", "didnt-go"), age_ok=True, refuse=None):
        self.alerts, self.offered, self.age_ok, self.refuse, self.posts, self.seen = alerts, offered, age_ok, refuse, [], set()

    async def get(self, url, **kw):
        # an open question older than the newest 200 alerts must still be found (the node serves up to 1000)
        assert url.endswith("/alerts") and kw["params"] == {"since_hours": 72, "limit": 1000}, (url, kw)
        return _Resp(200, self.alerts)

    async def post(self, url, json, **kw):
        assert url.endswith("/actions")
        a = next((x for x in self.alerts if x["id"] == json["alert_id"]), None)
        if a is None:
            return _Resp(404, {})
        if json["choice"] not in self.offered:
            return _Resp(400, {})
        if not self.age_ok:
            return _Resp(409, {"detail": "this question has closed"})
        if self.refuse:
            return _Resp(409, {"detail": self.refuse})
        key = (json["alert_id"], json["actor"], json["choice"])
        if key in self.seen and not json["note"]:
            return _Resp(200, {"ok": True, "kept": True})
        self.seen.add(key)
        self.posts.append(json)
        return _Resp(200, {"ok": True})


async def _telegram(method, **kw):
    TG.append((method, kw))
    return {}


_quiet = logging.getLogger("quiet")      # the refusals log a warning each; the test's output stays clean
_quiet.addHandler(logging.NullHandler())
_quiet.propagate = False
_ns = {"re": re, "time": __import__("time"), "log": _quiet, "telegram": _telegram, "pick": buttons.pick,
       "CHATS": lambda: {"1", "2"}, "LOCALE": "en", "MCP_URL": "http://app:8080/mcp"}
_ns = _lift("agent_loop.py", {"parse_callback", "parse_alert_callback", "lift", "node_url", "_name_of", "T",
                              "_post_answer", "_handle_alert_tap", "handle_callback", "note_pending",
                              "NOTE_WINDOW", "_keep_alert_note"}, _ns)
parse_alert_callback, lift, handle_callback, _post_answer = (_ns[k] for k in
                                                              ("parse_alert_callback", "lift", "handle_callback", "_post_answer"))

assert parse_alert_callback("al:1212:uluwatu:good") == (1212, "uluwatu:good")
assert parse_alert_callback("al:1212:Bad") is None and parse_alert_callback("al:x:a") is None
assert parse_alert_callback("al:1:" + "a" * 41) is None and parse_alert_callback(None) is None
assert parse_callback("al:1212:x") is None, "events are unchanged: an alert tap is not an event tap"
assert parse_alert_callback("ev:12:acted") is None

kb = [[{"text": "A", "callback_data": "al:1:a:good"}, {"text": "B", "callback_data": "al:1:a:bad"}],
      [{"text": "Skip", "callback_data": "al:1:didnt-go"}]]
assert lift(kb, "al:1:a:good", False) == [kb[1]], "only the row holding the tap goes"
assert lift(kb, "al:1:didnt-go", True) == [], "an acknowledged answer lifts every row"

BTNS = [[{"text": {"en": "Uluwatu is good", "es": "Uluwatu bien"}, "value": "good", "stage": "acted",
          "ask": {"en": "How was it?", "es": "¿Cómo fue?"}}],
        [{"text": {"en": "Didn't go"}, "value": "didnt-go", "stage": "acknowledged", "ask": None}]]
ALERT = {"id": 7, "buttons": BTNS}
KB7 = [[{"text": "Uluwatu is good", "callback_data": "al:7:good"}],
       [{"text": "Didn't go", "callback_data": "al:7:didnt-go"}]]


IDS = {"Ana": 101, "Ben": 202, "Eve": 303}   # Telegram's from.id: the name is only what is shown


def tap(node, chat, who, value, pending, qid="q"):
    TG.clear()
    cq = {"id": qid, "from": {"first_name": who, "id": IDS[who]}, "data": f"al:7:{value}",
          "message": {"message_id": 5, "chat": {"id": chat}, "reply_markup": {"inline_keyboard": KB7}}}
    asyncio.run(handle_callback(node, cq, pending))
    return [(m, kw) for m, kw in TG]


# A first tap: written, callback answered, its row lifted, one line, then the pack's question, and a pending note.
node, pending = _Node([ALERT]), {}
calls = tap(node, 1, "Ana", "good", pending)
assert [m for m, _ in calls] == ["answerCallbackQuery", "editMessageReplyMarkup", "sendMessage", "sendMessage"], calls
assert calls[1][1]["reply_markup"] == {"inline_keyboard": [KB7[1]]}
assert calls[2][1]["text"] == "Uluwatu is good · Ana" and calls[3][1]["text"] == "How was it?"
assert node.posts == [{"alert_id": 7, "choice": "good", "actor": "Ana", "note": ""}]
assert pending["1"][0] == ("al", 7, "good", "Ana", 101), "the ask remembers who pressed, by Telegram id"
assert note_pending(pending, "1", "waves were clean", pending["1"][1] + 1, 101) == ("al", 7, "good", "Ana", 101)

# Review Focus 5: a second chat taps the same alert: a different actor, so it is written, and its keyboard loses the row.
calls = tap(node, 2, "Ben", "good", {})
assert len(node.posts) == 2 and node.posts[1]["actor"] == "Ben"
assert calls[1][1]["reply_markup"] == {"inline_keyboard": [KB7[1]]}
# The same actor again: nothing new is written, the callback is still answered, no second line, no second question.
pending = {}
calls = tap(node, 1, "Ana", "good", pending)
assert len(node.posts) == 2, "a repeat tap writes nothing new"
assert [m for m, _ in calls] == ["answerCallbackQuery", "editMessageReplyMarkup"] and not pending, calls

# An acknowledged button lifts the whole keyboard and asks nothing.
calls = tap(node, 1, "Ana", "didnt-go", pending := {})
assert calls[1][1]["reply_markup"] == {"inline_keyboard": []} and not pending
assert calls[2][1]["text"] == "Didn't go · Ana" and len(calls) == 3

# Refusals write nothing and lift nothing: closed (409), not offered (400), no such alert (404 / not in the page).
for n, want in ((_Node([ALERT], age_ok=False), "This question has closed."),
                (_Node([ALERT], offered=("didnt-go",)), "That answer is not open any more.")):
    calls = tap(n, 1, "Ana", "good", pending := {})
    assert [m for m, _ in calls] == ["answerCallbackQuery"] and calls[0][1]["text"] == want, calls
    assert not n.posts and not pending
calls = tap(_Node([{"id": 8, "buttons": BTNS}]), 1, "Ana", "good", {})
assert [m for m, _ in calls] == ["answerCallbackQuery"] and calls[0][1]["text"] == "This question has closed."
calls = tap(_Node([{"id": 7, "buttons": None}]), 1, "Ana", "good", {})
assert calls[0][1]["text"] == "This question has closed." and len(calls) == 1, "no buttons on the alert: closed"
calls = tap(_Node([ALERT]), 1, "Ana", "nope", {})
assert calls[0][1]["text"] == "This question has closed.", "a value the alert does not carry writes nothing"

# 409 is two things: a closed question, and (DECISION_REQUIRED) an act that needs a decision first. Each is told as it is.
n = _Node([ALERT], refuse="this node is set to DECISION_REQUIRED, so an act needs a decision first.")
calls = tap(n, 1, "Ana", "good", pending := {})
assert [m for m, _ in calls] == ["answerCallbackQuery"] and not n.posts and not pending
assert calls[0][1]["text"] == "this node is set to DECISION_REQUIRED, so an act needs a decision first.", calls
assert tap(_Node([ALERT], age_ok=False), 1, "Ana", "good", {})[0][1]["text"] == "This question has closed.", \
    "the closed detail still reads as closed"

# The node down: the same message the event path uses, and the keyboard stays.
class _Down(_Node):
    async def get(self, url, **kw):
        raise ConnectionError("down")
calls = tap(_Down([ALERT]), 1, "Ana", "good", {})
assert [m for m, _ in calls] == ["answerCallbackQuery"] and "could not record" in calls[0][1]["text"]

# A chat that is not the household's is ignored, as for events.
n = _Node([ALERT])
calls = tap(n, 9, "Eve", "good", {})
assert [m for m, _ in calls] == ["answerCallbackQuery"] and not n.posts

# The note goes to the same /actions with the alert id and choice.
n = _Node([ALERT])
r = asyncio.run(_post_answer(n, None, "", "Ana", note="clean", alert_id=7, choice="good"))
assert n.posts == [{"alert_id": 7, "choice": "good", "actor": "Ana", "note": "clean"}] and r.json()["ok"]

# A note belongs to the person who pressed. In a household group Ben's next line is not Ana's note (review, 3 Nov).
ASK = ("al", 7, "good", "Ana", 101)
p = {"1": (ASK, 100.0)}
assert note_pending(p, "1", "my own words", 120.0, 202) is None and p["1"][0] == ASK, \
    "another person's line is not the note, and the ask stays open for the presser"
assert note_pending(p, "1", "my own words", 120.0) is None and "1" in p, "a line with no sender is nobody's note"
assert note_pending(p, "1", "/stack", 120.0, 101) is None and "1" in p, "a command is never a note"
assert note_pending(p, "1", "my own words", 120.0, 101) == ASK and "1" not in p


def line(who, text):
    return {"from": {"first_name": who, "id": IDS[who]}, "text": text}


def keep(node, p, who, text, now=120.0):
    TG.clear()
    return asyncio.run(_ns["_keep_alert_note"](node, p, "1", line(who, text), text, now)), [(m, kw) for m, kw in TG]


n = _Node([ALERT])
n.seen.add((7, "Ana", "good"))       # Ana's tap was written; a note is the UPDATE of that row, not a new answer
p = {"1": (ASK, 100.0)}
handled, said = keep(n, p, "Ben", "waves were clean")
assert not handled and not n.posts and not said and p["1"][0] == ASK, "Ben writes nothing and the ask stays Ana's"
handled, said = keep(n, p, "Ana", "/stack")
assert not handled and not n.posts and "1" in p, "a command is never a note"
handled, said = keep(n, p, "Ana", "waves were clean")
assert handled and "1" not in p and n.posts == [{"alert_id": 7, "choice": "good", "actor": "Ana", "note": "waves were clean"}], n.posts
assert said[0][1]["text"] == "Note kept with that answer."
handled, said = keep(n, {"1": (12, 100.0)}, "Ana", "an event's ask")
assert not handled and not n.posts[1:], "an event's ask is left to the event path"

# The event path still posts what it always did.
class _Ev:
    async def post(self, url, json, **kw):
        self.json = json
        return _Resp(200, {})
e = _Ev()
asyncio.run(_post_answer(e, 12, "dismissed", "Ana", note="x"))
assert e.json == {"event_id": 12, "stage": "dismissed", "actor": "Ana", "note": "x"}

print("the buttons the app writes are the buttons the bot answers, and the note goes where the question was asked")
