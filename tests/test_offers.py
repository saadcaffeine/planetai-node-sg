"""Offers (docs/SPEC_inventory.md step 4): a thing marked lend or give becomes a public line, and a stranger asks
through the node's Telegram bot, which passes the message to the household.

Node half drives /offers and reads /export with the database stubbed. Bot half lifts relay_offer out of agent_loop by
AST (importing agent_loop starts the bot), with Telegram and the node faked.

Run: PYTHONPATH=app python3 tests/test_offers.py
"""
import ast
import asyncio
import logging
import os
import re
import time
from pathlib import Path

SRC = open("app/main.py").read() + open("app/auth.py").read()   # auth.py: the allowlists, since 22 Oct
assert '"off": [/offers]' in open("packs/things/pack.yaml").read(), "/offers is open at every SHARE_LEVEL: each line was chosen to be public"
exp = SRC[SRC.index("def export("):SRC.index("import geo  # noqa: E402")]   # /place/geojson followed it until app/geo.py
assert '"offers": _offers()' in exp and 'packs.module("things", "routes")' in SRC, "the daily export carries the offers, from the things pack"

# ---------------------------------------------------------------- the node: only what the household chose, at its cell
logging.disable(logging.WARNING)
os.environ.update(ADMIN_TOKEN="admin-tok", NODE_NAME="bayu-2", NODE_LAT="-8.6478291", NODE_LON="115.1385412",
                  DATABASE_URL="postgresql://unused/never-connected")
import settings                                    # noqa: E402
settings._cache = {"at": time.time() + 1e9, "rows": {"SHARE_LEVEL": "off"}}
import main                                       # noqa: E402
import h3                                         # noqa: E402
from fastapi.testclient import TestClient         # noqa: E402

import auth                                       # noqa: E402
import db                                         # noqa: E402 — the things pack's routes read through db (packs/things)
import packs                                      # noqa: E402
assert "/offers" in auth._SHARE_OFF[0], "the pack's share: off puts /offers on every level"
SQL = []
db.q = main.q = lambda sql, *a: (SQL.append(sql), [{"id": 4, "class": "tool", "name": "cordless drill", "condition": "works",
                                             "offer": "lend", "count": 1}])[1]
main.state["bot"] = {"username": "bayu_planetai_bot", "asked": time.time()}
settings._cache["rows"].update(TELEGRAM_BOT_TOKEN="123:abc", TELEGRAM_CHAT_IDS="109")
r = TestClient(main.app).get("/offers")
assert r.status_code == 200, "a stranger reads offers at SHARE_LEVEL=off"
o = r.json()
assert "WHERE offer <> 'no'" in SQL[-1], "only what the household marked lend or give"
assert re.search(r"SELECT id, class, name, condition, offer, count FROM things", SQL[-1]), "never a note, a photo or how often it is used"
assert o["cell"] == h3.latlng_to_cell(-8.6478291, 115.1385412, 8), "the node's own res-8 cell, the one /health names"
assert "lat" not in str(o) and "capture" not in str(o), "no point, no photo"
assert o["offers"][0]["ask"] == "https://t.me/bayu_planetai_bot?start=offer-4" and o["contact"] == "https://t.me/bayu_planetai_bot"
settings._cache["rows"].update(TELEGRAM_BOT_TOKEN="")
assert packs.module("things", "routes").offers_now()["offers"][0]["ask"] is None, "no bot, no link: the offer still stands"
print("node: /offers open, only lend or give, only class, name, condition and count, at the node's cell, with the bot's link")

# ---------------------------------------------------------------- the bot: one message passed on, with a name to answer
ROOT = Path(__file__).resolve().parent.parent
SENT = []


async def telegram(method, **p):
    SENT.append((method, p))


class Resp:
    status_code = 200
    def json(self): return {"offers": [{"id": 4, "name": "cordless drill", "offer": "lend"}]}


class HC:
    async def get(self, url, timeout=None):
        assert url.endswith("/offers"); return Resp()


ns = {"re": re, "telegram": telegram, "T": lambda en, **o: en, "NODE": "bayu-2", "CHATS": lambda: {"109", "110"},
      "node_url": lambda p: "http://app:8080" + p}
for node in ast.parse((ROOT / "app" / "agent_loop.py").read_text()).body:
    targets = getattr(node, "targets", None) or [getattr(node, "target", None)]   # x = … and x: dict = …
    names = {getattr(t, "id", None) for t in targets} | {getattr(node, "name", None)}
    if names & {"relay_offer", "_name_of", "OFFER_WINDOW", "OFFER_GAP", "OFFER_ASKING", "OFFER_SENT"}:
        exec(compile(ast.Module([node], []), "agent_loop.py", "exec"), ns)
relay = lambda m, chat, text, now: asyncio.run(ns["relay_offer"](HC(), m, chat, text, now))  # noqa: E731
who = {"from": {"first_name": "Wayan", "username": "wayan_b"}}

assert relay(who, "555", "hello", 0) is False, "a stranger's message about nothing is still ignored"
assert relay(who, "555", "/start offer-9", 0) is True and "not here any more" in SENT[-1][1]["text"], "an offer gone says so"
assert relay(who, "555", "/start offer-4", 0) is True and "cordless drill" in SENT[-1][1]["text"]
assert SENT[-1][1]["chat_id"] == "555", "the stranger is answered, nobody else yet"
SENT.clear()
assert relay(who, "555", "Could I borrow it on Saturday?", 10) is True
to_house = [p for m, p in SENT if p["chat_id"] in ("109", "110")]
assert len(to_house) == 2 and all("Could I borrow it on Saturday?" in p["text"] and "@wayan_b" in p["text"] and "#4" in p["text"]
                                  for p in to_house), "every household chat gets the message, the offer and a name to answer"
assert SENT[-1][1]["chat_id"] == "555" and "Passed on" in SENT[-1][1]["text"]
assert not any("109" in p["text"] or "110" in p["text"] for m, p in SENT if p["chat_id"] == "555"), "the household's ids never show"
SENT.clear()
assert relay(who, "555", "and Sunday?", 20) is False, "one message per opening: the next is ignored like any stranger's"
assert relay(who, "555", "/start offer-4", 30) is True and relay(who, "555", "again", 40) is True
assert "already wrote" in SENT[-1][1]["text"] and not any(p["chat_id"] == "109" for m, p in SENT), "one an hour per chat"
SENT.clear()
anon = {"from": {"first_name": "Ketut"}}
relay(anon, "777", "/start offer-4", 0)
relay(anon, "777", "I need a drill", 5)
assert any("no Telegram username" in p["text"] for m, p in SENT if p["chat_id"] == "109"), "the household is told it cannot answer"
assert "no Telegram username" in SENT[-1][1]["text"], "and so is the sender"
SENT.clear()
relay(who, "888", "/start offer-4", 0)
assert relay(who, "888", "late", ns["OFFER_WINDOW"] + 1) is False, "an opening goes stale"
print("bot: an offer's link opens one message, passed to every household chat with a name to answer; one an hour; stale ignored")
print("offers: every check passed")
