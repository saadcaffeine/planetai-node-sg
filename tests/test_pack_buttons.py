"""app/buttons.py is the contract for the buttons a pack's rule can declare. A pack is not trusted: its `buttons`
column is checked here once, so run_rules, /actions, the bot and the dashboard all read the same clean rows, and a bad
column costs the alert its buttons, never the alert. Pure module, stdlib only. Run: PYTHONPATH=app python3 tests/test_pack_buttons.py
"""
import logging
from datetime import datetime, timedelta, timezone

import buttons

RAW = '[[{"text":"Uluwatu 👍","value":"uluwatu:good"}]]'
b = buttons.normalize(RAW)
assert b[0][0] == {"text": {"en": "Uluwatu 👍"}, "value": "uluwatu:good", "stage": "acted", "ask": None}, b
assert buttons.normalize(RAW.replace('"value"', '"stage":"acknowledged","ask":{"en":"how was it?"},"value"'))[0][0] \
    ["ask"] == {"en": "how was it?"}
assert buttons.normalize([[{"text": {"en": "a", "es": "b"}, "value": "v"}]])[0][0]["text"] == {"en": "a", "es": "b"}
assert buttons.normalize(None) is None
print("  normalize: a good column becomes clean rows")

# every way a column can be wrong gives None, and one warning each (the alert still goes, without buttons)
BAD = {
    "not json": "not json",
    "bad value": [[{"text": "x", "value": "Bad Value"}]],
    "newline in value": [[{"text": "x", "value": "good\n"}]],
    "value too long": [[{"text": "x", "value": "a" * 41}]],
    "nine rows": [[{"text": "x", "value": "v"}]] * 9,
    "five buttons": [[{"text": "x", "value": f"v{i}"} for i in range(5)]],
    "stage dismissed": [[{"text": "x", "value": "v", "stage": "dismissed"}]],
    "no text": [[{"value": "v"}]],
    "empty text": [[{"text": "", "value": "v"}]],
    "text of the wrong type": [[{"text": 5, "value": "v"}]],
    "empty row": [[]],
    "not rows": {"text": "x", "value": "v"},
    "a button that is not an object": [["x"]],
    "ask of the wrong type": [[{"text": "x", "value": "v", "ask": 3}]],
}
records = []


class Grab(logging.Handler):
    def emit(self, record):
        records.append(record)


buttons.log.addHandler(Grab())
for name, raw in BAD.items():
    records.clear()
    assert buttons.normalize(raw) is None, name
    assert len(records) == 1 and records[0].levelno == logging.WARNING, (name, records)
records.clear()
assert buttons.normalize([[{"text": "x", "value": "a" * 40}]] * 8) is not None, "8 rows of 1, 40-char values are the limit"
assert buttons.normalize([[{"text": "x", "value": f"v{i}"} for i in range(4)]]) is not None, "4 in a row is allowed"
assert not records
print("  normalize: every way to be wrong, one warning each, never an exception")

# Review Focus 1: a text with no entry for the node's locale never shows a dict
assert buttons.pick({"en": "a", "es": "b"}, "es") == "b"
assert buttons.pick({"en": "a"}, "id") == "a"
assert buttons.pick({"es": "b"}, "id") == "b"
print("  pick: locale, then en, then the first")

assert buttons.telegram_rows(b, 812, "en") == [[{"text": "Uluwatu 👍", "callback_data": "al:812:uluwatu:good"}]]
long = buttons.normalize([[{"text": "x", "value": "a" * 40}]])
for row in buttons.telegram_rows(long, 123456789012, "en"):
    for btn in row:
        assert len(btn["callback_data"].encode()) <= 64, btn
print("  telegram_rows: callback data stays inside Telegram's 64 bytes")

t = datetime(2026, 11, 3, 6, 0, tzinfo=timezone.utc)
assert buttons.find(b, "uluwatu:good") is b[0][0] and buttons.find(b, "nope") is None
assert buttons.find(None, "x") is None
assert buttons.check_answer(b, "uluwatu:good", t, t + timedelta(hours=71))["stage"] == "acted"
for value, now, exc, msg in (("nope", t, ValueError, "that answer was not offered"),
                             ("uluwatu:good", t + timedelta(hours=73), TimeoutError, "this question has closed")):
    try:
        buttons.check_answer(b, value, t, now)
    except exc as e:
        assert str(e) == msg, e
    else:
        raise AssertionError(f"{value} at {now} should raise {exc.__name__}")
try:
    buttons.check_answer(None, "x", t, t)
except ValueError:
    pass
else:
    raise AssertionError("an alert without buttons offered nothing")
print("  check_answer: offered, and not older than 72 h")

# the same (alert, actor, choice) is one row; a later note replaces it, silence keeps it
assert buttons.merge(None, "") is None and buttons.merge("x", "") is None
assert buttons.merge("", "head high") == "head high" and buttons.merge("x", "y") == "y"
print("  merge: a note replaces the row's note, silence writes nothing")
print("test_pack_buttons: all checks passed")
