"""The Telegram buttons contract (SPEC_alerts §7): the keyboard the app writes under an event message and the
parser the bot answers it with are two ends of one promise — ev:<event_id>:<stage> — and the Doesn't-fit
follow-up keeps a note without ever eating a command or a stale chat line.

No imports of main or agent_loop (importing either starts side effects): the functions are lifted whole by AST,
the way tests/test_run_rules_modes.py lifts run_rules."""

import ast
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

print("the buttons the app writes are the buttons the bot answers, and the note goes where the question was asked")
