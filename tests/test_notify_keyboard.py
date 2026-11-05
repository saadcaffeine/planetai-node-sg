"""The message is never lost over its buttons (SPEC_alerts §7): when Telegram refuses a message that carries an inline
keyboard (HTTP 400, a bad button), notify() sends it once more without the keyboard and says so in the log. Any other
refusal is not retried. channels.httpx.post is a fake. Run: PYTHONPATH=app python3 tests/test_notify_keyboard.py
"""
import logging

import httpx

import channels

KB = [[{"text": "Uluwatu", "callback_data": "al:7:good"}]]
sent, warned = [], []


class Grab(logging.Handler):
    def emit(self, record):
        warned.append(record.getMessage())


channels.log.addHandler(Grab())
channels.log.propagate = False           # the warnings are asserted below, not printed
channels.TG = lambda: ("tok", ["1"])
channels.RETICULUM_URL = ""


def run(statuses, keyboard=KB):
    """notify() against a Telegram that answers `statuses` in turn."""
    sent.clear()
    warned.clear()
    answers = iter(statuses)

    def post(url, json, timeout):
        sent.append(dict(json))      # a copy: notify() edits its body between the two sends
        return httpx.Response(next(answers), request=httpx.Request("POST", url))

    channels.httpx.post = post
    channels.tg_state.update(ok=None, at=None)
    channels.notify("info", "hello", keyboard=keyboard)


run([200])
assert len(sent) == 1 and sent[0]["reply_markup"] == {"inline_keyboard": KB} and channels.tg_state["ok"], sent
print("  an accepted keyboard goes once")

run([400, 200])
assert len(sent) == 2 and "reply_markup" in sent[0] and "reply_markup" not in sent[1], sent
assert sent[1]["text"] == sent[0]["text"] and channels.tg_state["ok"] is True, "the same words, no keyboard, delivered"
assert any("without its buttons" in w for w in warned) and not any("tok" in w for w in warned), warned
print("  a 400 on a keyboard retries once without it, and warns")

run([400, 400])
assert len(sent) == 2 and channels.tg_state["ok"] is False, "the retry is one, not a loop"

run([500])
assert len(sent) == 1 and channels.tg_state["ok"] is False, "only a 400 is retried"

run([400], keyboard=None)
assert len(sent) == 1 and channels.tg_state["ok"] is False, "a 400 on a message with no keyboard has nothing to drop"
print("test_notify_keyboard: all checks passed")
