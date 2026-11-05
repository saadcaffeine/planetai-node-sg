"""What the house learned and who lives in it: GET /learned, /learned/place, /learned/search, GET and PUT /household.

A module of its own since 24 Oct 2026, moved unchanged out of app/main.py (review item 15). The admin token reads the
house's own learnings and people; an agent only while every model this node uses stays on the house's network
(_models_home). /learned/place is the place's, never the house's, and is on the `open` list.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone

from fastapi import APIRouter, Header, HTTPException, Query, Request
from psycopg.types.json import Jsonb

import learn
import settings
from auth import _admin
from db import db, q

router = APIRouter()


def _models_home() -> bool:
    """Every model this node may use is on this house's own network (agent_loop.models_stay_home): AGENT_PREFER is
    private and no rung's address leaves. The gate on what the house learned and who lives in it."""
    import agent_loop
    return agent_loop.models_stay_home(settings)


@router.get("/learned")
def learned(request: Request, authorization: str = Header("")):
    """What this node has learned (docs/SPEC_learn.md), newest checks first, each with its numbers and cases. The
    admin token only: the cases carry the household's own notes. An agent reads it only while every model this node
    may use is on this house's own network (_models_home); otherwise it is told why not."""
    _admin(authorization)
    if request.headers.get("x-agent") and not _models_home():
        raise HTTPException(403, "what this house learned stays with its own machines: AGENT_PREFER is not private, "
                                 "or a model is set up outside this house's network. Read it on the page, Node, "
                                 "What it remembers.")
    rows = q("SELECT * FROM learnings ORDER BY kind, CASE status WHEN 'holding' THEN 0 WHEN 'weakening' THEN 1 "
             "WHEN 'too_early' THEN 2 ELSE 3 END, n DESC")
    # how many diary entries the node keeps, by scale: Node's "What it remembers" counts them
    kept = {r["scale"]: r["n"] for r in q("SELECT scale, count(*)::int AS n FROM digests GROUP BY scale")}
    return {"learnings": learn.rank(rows, _people()), "digests": kept, "checked": _checked()}


def _checked() -> str | None:
    """When the learning last ran: main's state, which refresh_learned stamps."""
    import main                      # noqa: PLC0415 — main imports this module
    at = main.state.get("learned_at")
    return at and datetime.fromtimestamp(at, timezone.utc).isoformat(timespec="seconds")


def _people() -> dict:
    r = q("SELECT people FROM household WHERE id = 1")
    return (r[0].get("people") or {}) if r else {}


@router.get("/household")
def household(request: Request, authorization: str = Header("")):
    """Who is in the house, as the household said (SPEC_learn §8): yes or no for each of `choices`. Guarded as
    GET /learned: the admin token, and an agent only while every model stays home."""
    _admin(authorization)
    if request.headers.get("x-agent") and not _models_home():
        raise HTTPException(403, "who is in this house stays with its own machines: AGENT_PREFER is not private, "
                                 "or a model is set up outside this house's network")
    return {"people": _people(), "choices": learn.PEOPLE}


@router.put("/household")
def household_set(body: dict, request: Request, authorization: str = Header("")):
    """Replace the answers: {"people": {"older": true, ...}}. Only the keys in `choices`, only true or false; the rest
    is refused, so nothing but these answers is ever kept. An agent may not write them."""
    _admin(authorization)
    if request.headers.get("x-agent"):
        raise HTTPException(403, "who lives here is the household's to say, on the page")
    p = body.get("people")
    if not isinstance(p, dict) or any(k not in learn.PEOPLE or not isinstance(v, bool) for k, v in p.items()):
        raise HTTPException(422, f"people is an object of true or false for {', '.join(learn.PEOPLE)}")
    with db() as con, con.cursor() as cur:
        cur.execute("""INSERT INTO household (id, people, updated_at) VALUES (1, %s, now())
                       ON CONFLICT (id) DO UPDATE SET people = EXCLUDED.people, updated_at = now()""", (Jsonb(p),))
    return {"ok": True, "people": p}


@router.get("/learned/place")
def learned_place():
    """What this node learned about the place around it, never about the house (SPEC_learn §3): the holding `usual`
    learnings of scope place, the outdoor sensors' hours, which the Wall draws and its narration already reads
    (ask.wall_reads). On the `open` list: the rows are outdoor public stations' numbers, with nothing of the house in
    them. The house's own learnings, what worked, the asks and the digests stay behind GET /learned."""
    return {"learnings": q("SELECT key, issue, metric, statement, numbers, n, checked_at FROM learnings "
                           "WHERE kind = 'usual' AND scope = 'place' AND status = 'holding' ORDER BY key")}


@router.get("/learned/search")
def learned_search(request: Request, q_: str = Query("", alias="q", max_length=200), scale: str = "",
                   limit: int = Query(12, ge=1, le=50), authorization: str = Header("")):
    """Search what this house learned and its digests (SPEC_learn §6): any of the words, ranked, newest first among
    equals. No words lists the newest digests, of one `scale` if given. Postgres full-text search, 'simple' so English,
    Indonesian and Spanish words all match as written. Guarded as GET /learned."""
    _admin(authorization)
    if request.headers.get("x-agent") and not _models_home():
        raise HTTPException(403, "what this house learned stays with its own machines: AGENT_PREFER is not private, "
                                 "or a model is set up outside this house's network")
    if scale and scale not in learn.SCALES:
        raise HTTPException(422, f"scale is one of {', '.join(learn.SCALES)}")
    terms = learn.search_terms(q_)
    if not terms:
        return {"q": q_, "results": q("""SELECT 'digest' AS source, scale, period_start, label, text, numbers FROM digests
                                         WHERE (%s = '' OR scale = %s) ORDER BY period_start DESC, scale LIMIT %s""",
                                      scale, scale, limit)}
    return {"q": q_, "results": q("""
        WITH t AS (SELECT to_tsquery('simple', %s) AS query)
        SELECT * FROM (
          SELECT 'digest' AS source, scale, period_start, label, text, numbers, ts_rank(tsv, t.query) AS rank
            FROM digests, t WHERE tsv @@ t.query AND (%s = '' OR scale = %s)
          UNION ALL
          SELECT 'learning', kind, NULL, key, statement, numbers, ts_rank(to_tsvector('simple', key || ' ' || statement), t.query)
            FROM learnings, t WHERE %s = '' AND to_tsvector('simple', key || ' ' || statement) @@ t.query) x
        ORDER BY rank DESC, period_start DESC NULLS LAST LIMIT %s""", terms, scale, scale, scale, limit)}
