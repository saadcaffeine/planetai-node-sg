"""The buttons a pack's rule can declare, and the one place they are checked (docs/SPEC_alerts.md).

A rule's `buttons` column is a JSON array of rows of buttons. A pack is not trusted, so run_rules, /actions, the bot
and the dashboard all read what `normalize` returns and nothing raw. A column that fails costs the alert its buttons,
never the alert: `normalize` logs one warning and returns None. Stdlib only, no database, no clock of its own.
"""
from __future__ import annotations

import json
import logging
import re
from datetime import datetime

log = logging.getLogger("planetai.buttons")

MAX_AGE_H = 72                      # an answer to a question this old is refused: the moment has gone
MAX_ROWS, MAX_PER_ROW = 8, 4
STAGES = ("acted", "acknowledged")
_VALUE = re.compile(r"[a-z0-9:_-]{1,40}")   # fullmatch, not `$` (it accepts a trailing newline). al:<id>:<value> must fit Telegram's 64 bytes of callback data


def _words(x) -> dict | None:
    """A str is English; a dict maps locale to a non-empty str. Anything else is not words."""
    if isinstance(x, str):
        x = {"en": x}
    if isinstance(x, dict) and x and all(isinstance(k, str) and isinstance(v, str) and v for k, v in x.items()):
        return dict(x)
    return None


def _button(raw) -> dict:
    if not isinstance(raw, dict):
        raise ValueError("a button is not an object")
    text = _words(raw.get("text"))
    if text is None:
        raise ValueError("a button needs text")
    value = raw.get("value")
    if not (isinstance(value, str) and _VALUE.fullmatch(value)):
        raise ValueError(f"bad value {value!r}")
    stage = raw.get("stage", "acted")
    if stage not in STAGES:
        raise ValueError(f"bad stage {stage!r}")
    ask = raw.get("ask")
    if ask is not None and (ask := _words(ask)) is None:
        raise ValueError("ask must be text")
    return {"text": text, "value": value, "stage": stage, "ask": ask}


def normalize(raw) -> list[list[dict]] | None:
    """The validated rows, or None when there are none or they are not valid (one warning)."""
    if not raw:
        return None
    try:
        rows = json.loads(raw) if isinstance(raw, (str, bytes)) else raw
        if not isinstance(rows, list) or not rows:
            raise ValueError("buttons must be a list of rows")
        if len(rows) > MAX_ROWS:
            raise ValueError(f"more than {MAX_ROWS} rows")
        out = []
        for row in rows:
            if not isinstance(row, list) or not row:
                raise ValueError("a row must be a list of buttons")
            if len(row) > MAX_PER_ROW:
                raise ValueError(f"more than {MAX_PER_ROW} buttons in a row")
            out.append([_button(b) for b in row])
        return out
    except ValueError as e:                  # json.JSONDecodeError is one
        log.warning("buttons: %s", e)
        return None


def pick(words: dict, locale: str) -> str:
    """The node's locale, then English, then whatever the pack wrote: never a dict on a button."""
    return words.get(locale) or words.get("en") or next(iter(words.values()), "")


def telegram_rows(buttons, alert_id: int, locale: str) -> list[list[dict]]:
    return [[{"text": pick(b["text"], locale), "callback_data": f"al:{alert_id}:{b['value']}"} for b in row]
            for row in buttons or []]


def find(buttons, value: str) -> dict | None:
    return next((b for row in buttons or [] for b in row if b["value"] == value), None)


def check_answer(buttons, value: str, alert_ts: datetime, now: datetime) -> dict:
    """The button an answer names. ValueError if it was never offered (a 400), TimeoutError if the alert is older
    than MAX_AGE_H (a 409). Both datetimes are timezone-aware."""
    b = find(buttons, value)
    if b is None:
        raise ValueError("that answer was not offered")
    if (now - alert_ts).total_seconds() > MAX_AGE_H * 3600:
        raise TimeoutError("this question has closed")
    return b


def merge(existing_note: str | None, note: str) -> str | None:
    """The note to write on an answer the same actor already gave, or None for no write: a later note replaces the row,
    a repeat tap with no words changes nothing."""
    return note or None
