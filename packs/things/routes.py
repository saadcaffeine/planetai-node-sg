"""The things a home keeps, and the ones it offers: GET/POST /things, PATCH/DELETE /things/{id}, GET /offers.

A pack since 24 Oct 2026; until then app/main.py, moved unchanged (docs/decisions/2026-10-21-core-and-packs.md: things
and offers are a category a node watches, like air or heat). The node mounts these routes from here
(app/packs.py::routers) and answers 404 while this pack is off. The `things` table stays in init.sql, and the private
role on the counts stays the core's (app/main.py THING_CLASSES, load_channel_roles), so a node that switches this pack
off keeps its readings private. `offers_now()` is also what the daily export carries (main._offers).
"""
from __future__ import annotations

import logging
import os
import time
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, Header, HTTPException

import db as _db                 # through the module, so a test can stub the database (db.q, db.db)
from auth import _admin

log = logging.getLogger("planetai")
NODE = os.getenv("NODE_NAME", "node")

router = APIRouter()


def _classes() -> tuple[tuple, tuple]:
    """THING_CLASSES and THING_COUNTS: the core's, because the private role on every count is declared from them at
    every start, whether this pack is on or not."""
    from main import THING_CLASSES, THING_COUNTS  # noqa: PLC0415 — main imports packs
    return THING_CLASSES, THING_COUNTS


# ---------------------------------------------------------------- the things a home keeps (docs/SPEC_inventory.md)
# One row per thing, kept as captures are, and three private counts per class written as readings whenever one
# changes, so readouts, rules and cells can use them and nothing sends them (packs.public_sql). The admin token only.
THING_CHOICES = {"used": ("weekly", "monthly", "yearly", "never"), "condition": ("works", "needs_repair", "broken"),
                 "offer": ("no", "lend", "give")}


def _thing_fields(body: dict, partial: bool) -> dict:
    """A thing as the table keeps it, or a 422 a person can act on."""
    out = {}
    if "class" in body or not partial:
        if body.get("class") not in _classes()[0]:
            raise HTTPException(422, f"class must be one of {', '.join(_classes()[0])}")
        out["class"] = body["class"]
    if "name" in body or not partial:
        name = " ".join(str(body.get("name") or "").split())[:120]
        if not name:
            raise HTTPException(422, "a thing needs a name")
        out["name"] = name
    if "count" in body:
        c = body["count"]
        if not isinstance(c, int) or isinstance(c, bool) or not 1 <= c <= 10000:
            raise HTTPException(422, "count is a whole number from 1")
        out["count"] = c
    for k, ok in THING_CHOICES.items():
        if k in body:
            if body[k] not in ok:
                raise HTTPException(422, f"{k} must be one of {', '.join(ok)}")
            out[k] = body[k]
    if "note" in body:
        out["note"] = str(body["note"] or "")[:500]
    if "capture_id" in body:
        out["capture_id"] = body["capture_id"] if isinstance(body["capture_id"], int) and not isinstance(body["capture_id"], bool) else None
    return out


def _thing_counts(cur, classes) -> None:
    """Rewrite the three private counts of each class touched, now, on the node's own survey sensor."""
    sid, now = f"things:{NODE}", datetime.now(timezone.utc)
    cur.execute("""INSERT INTO sensors (sensor_id, source, name, kind, local, indoor, cadence)
                   VALUES (%s, 'things', 'The things this home keeps', 'survey', TRUE, TRUE, 'P1D')
                   ON CONFLICT (sensor_id) DO NOTHING""", (sid,))
    for c in sorted({c for c in classes if c}):
        cur.execute("""SELECT coalesce(sum(count), 0) AS stock,
                              coalesce(sum(count) FILTER (WHERE used IN ('yearly', 'never')), 0) AS idle,
                              coalesce(sum(count) FILTER (WHERE condition <> 'works'), 0) AS repair
                       FROM things WHERE class = %s""", (c,))
        n = cur.fetchone()
        cur.executemany("""INSERT INTO readings (ts, sensor_id, metric, value) VALUES (%s, %s, %s, %s)
                           ON CONFLICT (sensor_id, metric, ts) DO UPDATE SET value = EXCLUDED.value""",
                        [(now, sid, f"{k}.{c}", float(n[k])) for k in _classes()[1]])


def _thing_out(r: dict) -> dict:
    return {k: (v.isoformat() if isinstance(v, datetime) else v) for k, v in r.items()}


@router.get("/things")
def things_list(authorization: str = Header("")):
    """Every thing, newest first, and the sums the Now door says in one line: how many, how many idle (used yearly or
    never), how many waiting for a repair, how many offered."""
    _admin(authorization)
    rows = [_thing_out(r) for r in _db.q("SELECT * FROM things ORDER BY id DESC")]
    return {"things": rows, "classes": list(_classes()[0]), "choices": THING_CHOICES, "summary": {
        "things": sum(r["count"] for r in rows),
        "idle": sum(r["count"] for r in rows if r["used"] in ("yearly", "never")),
        "repair": sum(r["count"] for r in rows if r["condition"] != "works"),
        "offered": sum(r["count"] for r in rows if r["offer"] != "no")}}


@router.post("/things")
def thing_add(body: dict, authorization: str = Header("")):
    _admin(authorization)
    f = _thing_fields(body, partial=False)
    with _db.db() as con, con.cursor() as cur:
        cur.execute(f"INSERT INTO things ({', '.join(f)}) VALUES ({', '.join(['%s'] * len(f))}) RETURNING *", tuple(f.values()))
        row = cur.fetchone()
        _thing_counts(cur, [row["class"]])
    return {"ok": True, "thing": _thing_out(row)}


@router.patch("/things/{tid}")
def thing_edit(tid: int, body: dict, authorization: str = Header("")):
    _admin(authorization)
    f = _thing_fields(body, partial=True)
    if not f:
        raise HTTPException(422, "nothing to change: class, name, count, used, condition, offer, note")
    with _db.db() as con, con.cursor() as cur:
        cur.execute("SELECT class FROM things WHERE id = %s", (tid,))
        was = cur.fetchone()
        if not was:
            raise HTTPException(404, "no such thing")
        cur.execute(f"UPDATE things SET {', '.join(k + ' = %s' for k in f)} WHERE id = %s RETURNING *", (*f.values(), tid))
        row = cur.fetchone()
        _thing_counts(cur, [was["class"], row["class"]])   # a thing moved between classes changes both
    return {"ok": True, "thing": _thing_out(row)}


@router.delete("/things/{tid}")
def thing_delete(tid: int, authorization: str = Header("")):
    _admin(authorization)
    with _db.db() as con, con.cursor() as cur:
        cur.execute("DELETE FROM things WHERE id = %s RETURNING class", (tid,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(404, "no such thing")
        _thing_counts(cur, [row["class"]])
    return {"ok": True}


# ---------------------------------------------------------------- offers (docs/SPEC_inventory.md step 4)
# A thing the household marks `lend` or `give` becomes a public line: its class, name, condition and count, at the
# node's own res-8 cell, the one /health already names. Never the household, a point, a photo or a note. Whoever
# wants it writes to the node's Telegram bot, which passes the message on (agent_loop.relay_offer); the household's
# chat ids never show. Tomas, 13 Oct 2026: "option 1, the Telegram bot".
BOT_EVERY = 86400


def _bot_username() -> str | None:
    """The bot's @name, asked of Telegram once a day with the token the node already holds. None without a bot."""
    from channels import TG          # noqa: PLC0415 — the bot token, read where the channels read it
    tok, chats = TG()
    if not tok or not chats:
        return None
    from main import state           # noqa: PLC0415 — main imports packs; the bot's @name is cached in its state
    known = state.get("bot") or {}
    if time.time() - known.get("asked", 0) < BOT_EVERY:
        return known.get("username")
    try:
        r = httpx.get(f"https://api.telegram.org/bot{tok}/getMe", timeout=10)
        name = (r.json().get("result") or {}).get("username") if r.status_code == 200 else None
    except Exception as e:  # noqa: BLE001 — the URL holds the token: log the kind of failure, never the error text
        log.warning("telegram getMe: %s", type(e).__name__)
        name = None
    state["bot"] = {"username": name or known.get("username"), "asked": time.time() if name else time.time() - BOT_EVERY + 3600}
    return state["bot"]["username"]


def offers_now() -> dict:
    import h3  # noqa: PLC0415
    lat, lon = float(os.getenv("NODE_LAT", 0) or 0), float(os.getenv("NODE_LON", 0) or 0)
    bot = _bot_username()
    rows = _db.q("SELECT id, class, name, condition, offer, count FROM things WHERE offer <> 'no' ORDER BY id")
    return {"node": NODE, "cell": h3.latlng_to_cell(lat, lon, 8) if (lat or lon) else None,
            "contact": f"https://t.me/{bot}" if bot else None,
            "offers": [{**r, "ask": f"https://t.me/{bot}?start=offer-{r['id']}" if bot else None} for r in rows]}


@router.get("/offers")
def offers():
    """What this home would lend or give, as it chose to publish it: open at every SHARE_LEVEL, and in the daily
    export. `ask` opens the node's Telegram bot on that offer; null when the node has no bot."""
    return offers_now()
