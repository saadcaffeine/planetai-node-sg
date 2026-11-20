"""The message is never lost over its buttons (SPEC_alerts §7): when Telegram refuses a message that carries an inline
keyboard (HTTP 400, a bad button), notify() sends it once more without the keyboard and says so in the log. Any other
refusal is not retried. A connection that never opened is tried twice more (6 Nov 2026); a read timeout is not, so an
alert is never sent twice. channels.httpx.post is a fake. Run: PYTHONPATH=app python3 tests/test_notify_keyboard.py
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
        assert timeout.connect == 5 and timeout.read == 15, timeout      # keeps three tries x four chats under 180 s
        a = next(answers)
        if isinstance(a, Exception):
            raise a
        return httpx.Response(a, request=httpx.Request("POST", url))

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
slept = []
channels.time.sleep = slept.append
down = httpx.ConnectError("no route")

run([down, 200])
assert len(sent) == 2 and channels.tg_state["ok"] is True and slept == [3], (sent, slept)
assert any("trying again in 3 s" in w for w in warned) and not any("tok" in w for w in warned), warned
print("  a dropped connection is tried again and the alert arrives")

slept.clear()
run([down, httpx.ConnectTimeout("slow"), down])
assert len(sent) == 3 and channels.tg_state["ok"] is False and slept == [3, 10], (sent, slept)
print("  three tries at most, then it gives up as before")

slept.clear()
channels.TG = lambda: ("tok", ["1", "2"])
run([down, down, down, 200])
assert [m["chat_id"] for m in sent] == ["1", "1", "1", "2"] and channels.tg_state["ok"] is True, sent
assert slept == [3, 10], "the next chat gets one try once the line is known to be down, not three"
print("  after one chat gives up, the next still gets its alert, in one try")

slept.clear()
run([down, down, down, down])
assert len(sent) == 4 and slept == [3, 10] and channels.tg_state["ok"] is False, (sent, slept)
print("  with the line down, a second chat costs one try, not three (POST /report/now stays under 180 s)")
channels.TG = lambda: ("tok", ["1"])

slept.clear()
run([httpx.ReadTimeout("late")])
assert len(sent) == 1 and channels.tg_state["ok"] is False and slept == [], "a read timeout may have arrived: no second copy"
print("  a read timeout is never retried")

slept.clear()
run([down, 400, 200])
assert len(sent) == 3 and "reply_markup" not in sent[2] and channels.tg_state["ok"] is True, sent
print("  the keyboard fallback still works after a drop")
import pathlib
route = (pathlib.Path(__file__).resolve().parent.parent / "app/main.py").read_text().split("def report_now(")[1].split("\n@app.")[0]
assert "threading.Thread(target=notify" in route and "\n    notify(" not in route, "POST /report/now waits on Telegram again"
print("  POST /report/now hands the send to a thread, so a down line never holds the request")
print("test_notify_keyboard: all checks passed")
