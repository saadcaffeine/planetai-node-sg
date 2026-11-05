"""The dashboard's ask pane: `GET /ask/status`, `POST /ask`, `GET /docs/search`.

A person reading the page asks the node's own model, on this machine, about what the page shows. The loop is
`agent_loop.pane`: it reads, and anything else it reaches for comes back as a proposal the person presses.

THREE PROMISES, EACH HELD BY A TEST IN tests/test_ask.py:

  · The context carries no coordinate, no room or sensor name, no sensor id and no `meta`. It is built here from
    the /issues bundle the page already has, and every tool result passes through the same `scrub` before the
    model reads it. A local model is on the machine those facts describe; the rule holds anyway, because a pane
    open on a wall is read by whoever walks past, and what the model is never told it cannot repeat.
  · Nothing is stored. No transcript on disk, no row, no log line with a word anybody typed. The thread lives in
    the browser tab and dies with it.
  · Nothing is changed. An `act` or an admin tool is a `proposal` event; the page presses it with its own token.

`/docs/search` needs no model: a case-insensitive substring over learn.json and data/docs_site.json, which
`make learn` cuts out of docs/site at build time, because the container never sees docs/.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import math
import re
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import httpx
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

import agent_loop
import learn
import packs
import settings
from tool_classes import TOOL_CLASS

log = logging.getLogger("planetai.ask")
router = APIRouter(tags=["ask"])
HERE = Path(__file__).resolve().parent
LEARN = HERE / "static" / "learn.json"
# `./data` is mounted at /app/data in the container, and sits beside app/ in a checkout.
DOCS_COPY = next((p for p in (HERE / "data" / "docs_site.json", HERE.parent / "data" / "docs_site.json")
                  if p.exists()), HERE / "data" / "docs_site.json")
LOCALES = ("en", "id", "es")

# Wall narration rotation state (module-level counter, matching the client-side NARR_TURN behavior)
WALL_NARR_TURN = 0

# Keys that name a place, a device or a household's own words about its kit. Dropped wherever they occur.
DROP = frozenset({"lat", "lon", "latitude", "longitude", "centroid", "center", "position", "sensor_id", "sensor_ids",
                  "sensors", "name", "source", "meta", "stations", "geometry", "host", "hostname", "mesh_node",
                  "gateway", "topic", "root_topic", "actor", "note", "provenance", "series", "buckets"})


class Scrub:
    """What the model may never be told: this node's position and the names and ids of the things in it.

    Built once per request from what the node knows about itself, so a sensor renamed this morning is
    scrubbed this afternoon. Keys in DROP are removed at any depth; in every string left, each known name and
    id becomes "a sensor", and the node's own coordinates, to two decimals or finer, become "here".
    """

    def __init__(self, names=(), lat=None, lon=None):
        pats = sorted({str(n).strip() for n in names if n and len(str(n).strip()) >= 3}, key=len, reverse=True)
        self.names = re.compile("|".join(re.escape(n) for n in pats), re.I) if pats else None
        coords = []
        for v in (lat, lon):
            if v:
                # rounded and cut: -8.8190516 rounds to -8.82, and "-8.8190" in a text starts -8.81
                for head in {f"{float(v):.2f}", f"{int(float(v) * 100) / 100:.2f}"}:
                    coords.append(re.escape(head) + r"\d*")
        self.coords = re.compile("|".join(coords)) if coords else None

    def text(self, s: str) -> str:
        if self.names:
            s = self.names.sub("a sensor", s)
        if self.coords:
            s = self.coords.sub("here", s)
        return s

    def value(self, v):
        if isinstance(v, dict):
            # keys too: the Wall's facts are labelled by a pack's own words, and a label can carry a room
            return {self.text(k) if isinstance(k, str) else k: self.value(x) for k, x in v.items() if k not in DROP}
        if isinstance(v, list):
            return [self.value(x) for x in v]
        if isinstance(v, str):
            return self.text(v)
        return v

    def __call__(self, text: str) -> str:
        """A tool's result, which arrives as JSON text; anything that is not JSON is scrubbed as a string."""
        try:
            return json.dumps(self.value(json.loads(text)), ensure_ascii=False)
        except (TypeError, ValueError):
            return self.text(str(text))


def scrub_for(doc: dict, sensor_names=(), lat=None, lon=None) -> Scrub:
    names = list(sensor_names)
    ids = []
    for s in doc.get("stations") or []:
        names.append(s.get("name")); ids.append(s.get("sensor_id"))
    for iss in (doc.get("issues") or {}).values():
        for cell in (iss.get("stack") or {}).values():
            if cell:
                ids += cell.get("sensors") or []
                if cell.get("source") and not re.fullmatch(r"\d+ sensors", str(cell["source"])):
                    names.append(cell["source"])
    return Scrub(names + ids, lat, lon)


def context(doc: dict, loc: str, view: str, mode: str, focus: str | None = None, learn: dict | None = None,
            version: str = "") -> dict:
    """What the model is told the page shows. Everything is the node's own words and figures from /issues."""
    loc = loc if loc in LOCALES else "en"

    def L(d):
        return (d.get(loc) or d.get("en") or "") if isinstance(d, dict) else (d or "")
    iss = doc.get("issues") or {}
    lead = (doc.get("lead") or {}).get("issue")
    h = (iss.get(lead) or {}).get("hero") or {}
    out = {
        "view": view, "mode": mode, "node_version": version,
        "lead": {"issue": lead, "picked_by": (doc.get("lead") or {}).get("by"),
                 "value": h.get("value"), "unit": h.get("unit"), "stamp": L(h.get("stamp")),
                 "sentence": L(h.get("sentence")), "plain": L(h.get("plain")),
                 "about": L((iss.get(lead) or {}).get("about") or {})},
        "digest": {k: L(v) for k, v in (doc.get("digest") or {}).items()},
        "issues": [{"issue": k, "name": L(v.get("name")), "state": v.get("state"), "why": L(v.get("reason_text")),
                    "unit": v.get("unit"), "line": (v.get("line") or {}).get("value"),
                    "about": L(v.get("about") or {}),
                    "at": {d: c.get("value") for d, c in (v.get("stack") or {}).items() if c}}
                   for k, v in iss.items() if v.get("watched") is not False],
        "open_alerts": [{"id": a.get("id"), "issue": k, "at": a.get("ts"), "says": str(a.get("text") or "").split("\n")[0]}
                        for k, v in iss.items() for a in (v.get("open_asks") or [])][:12],
    }
    if focus and learn:
        m = (learn.get("marks") or {}).get(focus)
        if m:
            out["focus"] = {"part": m.get("title"), "quote": m.get("quote"), "more": m.get("more"),
                            "from": f"{m.get('page_title')} · {m.get('section') or ''}".strip(" ·")}
    return out


# ---------------------------------------------------------------- the Wall's facts
# The Wall is read by whoever walks past, so its context is a whitelist, not the pane's context cut down: short
# labelled facts, each with its unit and where it comes from (live, model, satellite), and nothing else. What the
# house learned, its digests, its things, who answered and the alerts' own words (which name rooms) never enter it.
# A pack's public figures reach it without code here: every watched issue's readouts, and every section a pack
# declares `wall: true`. A readout on a channel any pack declares `private` is left out.
WALL_WHERE = {"room": "inside the home", "yard": "street", "ring": "neighbourhood", "region": "wider area"}
# ponytail: provenance by the source's words; a pack whose source names none of these reads as its own provenance
SATELLITE = re.compile(r"satellite|earth engine|alphaearth|sentinel|landsat|modis|viirs|firms", re.I)
COMPASS = ("north", "north-east", "east", "south-east", "south", "south-west", "west", "north-west")
WALL_FORECAST_HOURS = 6


def _prov(x: dict) -> str:
    if SATELLITE.search(str(x.get("source") or "")):
        return "satellite"
    p = x.get("provenance") or "live"
    return "live" if p == "partial" else p


def _fig(v, dp, unit) -> str:
    return f"{float(v):.{int(dp or 0)}f} {unit or ''}".strip()


def _forecast(fc: dict | None, now) -> str | None:
    """The next few hours from one forecast source (BMKG first, the official one, else Open-Meteo). Only hours
    still to come: readings hold the forecast's rows up to 72 h ahead, timestamped in the future."""
    end = now + timedelta(hours=WALL_FORECAST_HOURS)
    hours = [h for h in (fc or {}).get("hours") or [] if now < learn._aware(h["ts"]) <= end]
    src = next((s for s in ("forecast-bmkg", "forecast-om") if any(h.get("source") == s for h in hours)), None)
    hours = [h for h in hours if h.get("source") == src]
    if not hours:
        return None
    temps = [h["fc_temp"] for h in hours if h.get("fc_temp") is not None]
    rain = sum(h.get("fc_rain") or 0 for h in hours)
    wind = next((h for h in hours if h.get("fc_wind_speed") is not None and h.get("fc_wind_direction") is not None), None)
    parts = [f"next {WALL_FORECAST_HOURS} hours"]
    if temps:
        parts.append(f"{min(temps):.0f} to {max(temps):.0f} °C")
    parts.append(f"rain about {rain:.1f} mm" if rain >= 0.2 else "dry")
    if wind:
        parts.append(f"wind from the {COMPASS[round(wind['fc_wind_direction'] / 45) % 8]} at {wind['fc_wind_speed']:.0f} km/h")
    return ", ".join(parts + ["model"])


def wall_context(doc: dict, loc: str = "en", usual=(), forecast: dict | None = None, private=frozenset(),
                 now=None) -> dict:
    """What the Wall's model is told. `usual` is learnings rows (only kind usual, scope place, holding are read);
    `forecast` is GET /forecast's body; `private` the metrics any channel declares private."""
    loc = loc if loc in LOCALES else "en"

    def L(d):
        return (d.get(loc) or d.get("en") or "") if isinstance(d, dict) else (d or "")
    now = learn._aware(now or doc.get("as_of") or datetime.now(timezone.utc))
    tz = os.getenv("NODE_TZ", "").strip()
    try:
        here = now.astimezone(ZoneInfo(tz)) if tz else now
    except (ZoneInfoNotFoundError, ValueError):
        here = now
    out: dict = {"time": here.strftime("%A %H:%M")}

    def readouts(rows) -> dict:
        return {L(r.get("label")) or r["metric"]: f"{_fig(r['value'], r.get('dp'), r.get('unit'))}, {_prov(r)}"
                for r in rows or [] if r.get("value") is not None and r.get("metric") not in private}
    iss = doc.get("issues") or {}
    for k, v in iss.items():
        if v.get("watched") is False:
            continue
        f = {"today": L(v.get("title")), "so far": L(v.get("tagline"))}
        if v.get("state") != "context":            # land and the sea say themselves in their readouts
            for d, c in (v.get("stack") or {}).items():
                if c and c.get("value") is not None:
                    f[WALL_WHERE.get(d, d)] = f"{_fig(c['value'], v.get('dp'), v.get('unit'))}, {_prov(c)}"
            line = v.get("line") or {}
            if line.get("value") is not None:
                f["line"] = (f"{_fig(line['value'], 0, line.get('unit') or v.get('unit'))}, "
                             + ("the WHO guideline" if "WHO" in str(line.get("source")) else "this place's own line"))
            f["trend"] = v.get("trend")
        f.update(readouts(v.get("readouts")))
        f = {a: b for a, b in f.items() if b}
        if f:
            out[k] = f
    for sec in doc.get("sections") or []:
        if sec.get("wall") and readouts(sec.get("readouts")):
            out[L(sec.get("title")) or sec.get("id")] = readouts(sec.get("readouts"))

    air_line = ((iss.get("air") or {}).get("line") or {}).get("value")
    pm = [(s.get("km"), r["value"]) for s in doc.get("stations") or [] if not s.get("local") and not s.get("indoor")
          for r in [(s.get("read") or {}).get("pm25") or {}]
          if r.get("value") is not None and (r.get("silent_minutes") or 0) < 120]
    if pm:
        st = f"{len(pm)} public stations nearby read fine dust, {min(v for _, v in pm):.0f} to {max(v for _, v in pm):.0f} µg/m³"
        if air_line is not None:
            st += f", {sum(v > air_line for _, v in pm)} of them over the WHO line"
        kms = [km for km, _ in pm if km is not None]
        out["stations nearby"] = st + (f", the nearest {min(kms):.0f} km away" if kms else "") + ", live"

    seen = []
    for r in usual or []:
        n = r.get("numbers") or {}
        if r.get("kind") != "usual" or r.get("scope") != "place" or r.get("status") != "holding" or "high_hour" not in n:
            continue
        s = (f"{learn.GROUP_WORDS.get(r.get('key'), r.get('key'))} over the last {n.get('days')} days: usually highest "
             f"around {n['high_hour']:02d}:00 and lowest around {n['low_hour']:02d}:00")
        at = (n.get("by_hour") or {})
        at = at.get(here.hour, at.get(str(here.hour)))
        if at is not None:
            s += f", usually {at} {n.get('unit', '')} at this hour"
        if n.get("this_week") is not None:
            s += f", this week {n['this_week']} a day against {n.get('usual_week')} the three weeks before"
        seen.append(s + ", live")
    if seen:
        out["usual for this place"] = seen
    fc = _forecast(forecast, now)
    if fc:
        out["forecast"] = fc
    return out


def wall_angles(ctx: dict) -> list[str]:
    """The angles whose facts this context has: an angle with nothing to say from is skipped, never apologised for."""
    keys = " ".join(list(ctx) + [k for v in ctx.values() if isinstance(v, dict) for k in v])
    return [a for a, need in agent_loop.WALL_ANGLES if re.search(need, keys, re.I)]


def wall_reads() -> tuple[list, dict | None]:
    """The two reads the Wall makes beyond /issues. A read that fails leaves its fact out."""
    import main                                    # noqa: PLC0415
    try:
        usual = main.q("SELECT kind, key, scope, status, numbers FROM learnings "
                       "WHERE kind = 'usual' AND scope = 'place' AND status = 'holding'")
    except Exception:  # noqa: BLE001
        usual = []
    try:
        fc = _read_forecast(WALL_FORECAST_HOURS)
    except Exception:  # noqa: BLE001
        fc = None
    return usual, fc


def _read_forecast(hours: int) -> dict | None:
    """GET /forecast's own answer, from the forecast pack (packs/forecast/routes.py), or None while it is off."""
    mod = packs.module("forecast", "routes")
    return mod.forecast(hours) if mod else None


AGENT_KEYS = ("AGENT_PREFER", "AGENT_REMOTE_URL", "AGENT_REMOTE_MODEL", "AGENT_REMOTE_KEY",
              "AGENT_ONLINE_URL", "AGENT_ONLINE_MODEL", "AGENT_ONLINE_KEY")


def configured() -> bool:
    """A loop on this machine is set up when the agent profile is on: `planetai agent local` adds it."""
    return "agent" in (os.getenv("COMPOSE_PROFILES") or "").replace(" ", "").split(",")


def rungs() -> list:
    """The models the pane may ask, in order: the same Set up → Model settings and AGENT_PREFER the Telegram
    bot reads, so one choice governs both. The local rung only when a loop is set up on this machine; a
    remote model on the network works without one, and an online one only when AGENT_PREFER allows it."""
    return agent_loop.pane_rungs({k: settings.get(k, "") for k in AGENT_KEYS}, with_local=configured())


def _probe(rung) -> tuple[bool, str]:
    """Whether a rung would answer now. Local asks Ollama for its tags; a remote server is asked for its
    models, the OpenAI-compatible way; an online one is not probed, because a key that is set is a choice
    somebody made, and a request to check it would be a request off the network nobody asked for."""
    if rung.name == "online":
        return True, ""
    if rung.name == "remote":
        try:
            ok = httpx.get(rung.url + "/models", headers=rung.headers(), timeout=3).status_code < 400
        except httpx.HTTPError:
            ok = False
        return (True, "") if ok else (False, f"{agent_loop.where_of(rung)['host']} is not answering")
    url = os.getenv("OLLAMA_URL", "http://host.docker.internal:11434")
    try:
        tags = httpx.get(url + "/api/tags", timeout=3).json().get("models") or []
    except (httpx.HTTPError, ValueError):
        return False, "Ollama is installed and not answering"
    names = {t.get("name") for t in tags} | {str(t.get("name", "")).removesuffix(":latest") for t in tags}
    return (True, "") if rung.model in names else (False, f"{rung.model} is not on this machine yet")


@router.get("/ask/status")
def ask_status():
    """Which model the pane asks first, where it runs, whether it answers, and what it may do. 404 when no model
    is set up at all: none on this machine, none on the network, and no online one AGENT_PREFER allows."""
    order = rungs()
    if not order:
        # The page draws its no-model state from this body: what to pull for this machine, and the
        # other way in, a person's own agent over MCP.
        raise HTTPException(404, {"error": "no model is set up on this node; `planetai agent local` sets one up",
                                  "recommend": agent_loop.recommend(), "mcp": "/mcp",
                                  "token_hint": "planetai agent"})
    first = order[0]
    running, why = _probe(first)
    here = agent_loop.where_of(first)
    return {"model": first.model, "rung": first.name, "where": here["where"], "host": here["host"],
            "running": running, "why": why or None,
            "rungs": [agent_loop.where_of(r) for r in order],
            # True when the question and the page's context may leave the house: an online rung is in the
            # order, which only AGENT_PREFER fallback or strongest allows.
            "leaves": any(r.leaves for r in order),
            "tools": [{"name": n, "class": TOOL_CLASS[n]} for n in sorted(agent_loop.PANE_TOOLS)],
            "stored": False}


class Msg(BaseModel):
    role: str = Field(pattern="^(user|assistant)$")
    content: str = Field(max_length=4000)


class AskBody(BaseModel):
    messages: list[Msg] = Field(min_length=1, max_length=24)
    view: str = Field("now", max_length=20)
    mode: str = Field("advanced", max_length=20)
    focus: str | None = Field(None, max_length=40)
    prompt: str | None = Field(None, max_length=50)  # optional: 'wall' for wall narration


def _proposal(p: dict, loc: str) -> dict:
    """Add a setting's own words to a proposal: its current value, what would leave, how to undo it."""
    out = dict(p, setting=None, current=None, proposed=None, choices=None, group=None, leaves=None, undo=None)
    if p.get("tool") == "act":
        # The id only. A note is the person's own sentence about what they did; a model's draft of it on the card
        # would be words put in their mouth, and ρ is built out of those sentences. The card asks them to write it.
        out["args"] = {"alert_id": (p.get("args") or {}).get("alert_id")}
    if p.get("tool") == "settings_set":
        changes = (p.get("args") or {}).get("changes") or {}
        key = next(iter(changes), None)
        row = next((r for r in settings.describe()["runtime"] if r["key"] == key), None)
        if row:
            proposed = str(changes[key])
            # A value the key would refuse is not proposed; the card offers the values it takes instead. A small
            # model asked to "turn on" MAP_TILES proposed "1", which PUT /settings refuses.
            if row.get("choices") and proposed not in row["choices"]:
                proposed = None
            out.update(setting=key, proposed=proposed, choices=row.get("choices"), current=row["value"],
                       group=row["group"],
                       leaves={l: row["help"] for l in LOCALES},
                       undo={l: UNDO[l].format(key=key, value=row["value"] or "blank", group=row["group"])
                             for l in LOCALES})
    return out


# A proposal's way back, in the household's language. The id and es strings want a native reader.
UNDO = {"en": "Set {key} back to {value} under Set up → {group}.",
        "id": "Kembalikan {key} ke {value} di Set up → {group}.",
        "es": "Vuelve a poner {key} en {value} en Set up → {group}."}


def _json(v) -> str:
    """JSON for the model and the stream. On a live node an alert's `ts` is a datetime from Postgres, where a
    capture carries a string; v0.75 met the first on node #1 and answered every question with a 500."""
    return json.dumps(v, ensure_ascii=False, default=lambda o: o.isoformat() if hasattr(o, "isoformat") else str(o))


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {_json(data)}\n\n"


# What the house learned (SPEC_learn §7) stays with the house: the pane offers the `learned` tool only to a caller
# carrying the household's own token (admin or act) or this machine itself, and never to the Wall, which is read by
# whoever walks past. /ask is on the SHARE_LEVEL=open allowlist, so without this a stranger on the network could ask
# the pane what the household did and when.
HOUSE_TOOLS = frozenset({"learned"})


def _house(request: Request) -> bool:
    given = (request.headers.get("authorization") or "").replace("Bearer ", "", 1).strip().encode()
    ok = False
    for t in (os.getenv("ADMIN_TOKEN", "").strip(), (settings.get("ACT_TOKEN", "") or "").strip()):
        if t and secrets.compare_digest(given, t.encode()):
            ok = True
    return ok or (getattr(request.client, "host", "") or "") in ("127.0.0.1", "::1", "localhost")


def menu(listed, house: bool) -> list[dict]:
    return [t for t in agent_loop.pane_tools(listed) if house or t["function"]["name"] not in HOUSE_TOOLS]


@router.post("/ask")
async def ask(body: AskBody, request: Request):
    """One answer, streamed as server-sent events: token · tools · retry · proposal · done · error. Nothing is kept."""
    order = rungs()
    if not order:
        raise HTTPException(404, "no model is set up on this node; `planetai agent local` sets one up")
    import main                                    # noqa: PLC0415 — main includes this router at the bottom of itself
    from issues import api as issues_api           # noqa: PLC0415
    doc = await asyncio.to_thread(issues_api.issues_now)
    try:
        # a room is the sensor's name (init.sql 0.61); the room and the platform's own name are looked for too
        names = [v for r in await asyncio.to_thread(main.q, "SELECT name, room, source_name FROM sensors")
                 for v in (r.get("name"), r.get("room"), r.get("source_name")) if v]
    except Exception:  # noqa: BLE001 — a read failing must not put names back in; it only means fewer to look for
        names = []
    scrub = scrub_for(doc, names, os.getenv("NODE_LAT"), os.getenv("NODE_LON"))
    loc = settings.get("ALERT_LOCALE", "en") or "en"
    learn = json.loads(LEARN.read_text()) if body.focus and LEARN.exists() else None

    # Compose system prompt: wall narration uses WALL_SYSTEM with an angle its facts can carry; otherwise PANE_SYSTEM.
    # Either way the scrubbed context rides in the system prompt — the wall's voice lives on its figures.
    if body.prompt == "wall":
        global WALL_NARR_TURN
        usual, fc = await asyncio.to_thread(wall_reads)
        private = {c["metric"] for c in packs.channels() if c.get("role") == "private"}
        ctx = scrub.value(wall_context(doc, loc, usual, fc, private))
        angles = wall_angles(ctx)
        angle = angles[WALL_NARR_TURN % len(angles)]
        WALL_NARR_TURN += 1
        system = (agent_loop.WALL_SYSTEM + f" This time, start from {angle}."
                  + f"\n\nThe page's context:\n{_json(ctx)}")
    else:
        ctx = scrub.value(context(doc, loc, body.view, body.mode, body.focus, learn, os.getenv("NODE_VERSION", "")))
        system = agent_loop.PANE_SYSTEM.format(node=os.getenv("NODE_NAME", "node"),
                                               lang=agent_loop.LANG_NAME, context=_json(ctx))
    house = _house(request) and body.prompt != "wall"
    hc = httpx.AsyncClient(headers={"Authorization": f"Bearer {os.getenv('ADMIN_TOKEN', '')}",
                                    "X-Agent": agent_loop.AUDIT_PANE}, timeout=60)
    url = f"http://127.0.0.1:{os.getenv('PORT', '8080')}/mcp"

    async def stream():
        try:
            async with agent_loop.node_session(hc, url, keep=lambda listed: menu(listed, house)) as (session, tools):
                async def call(name, args):
                    res = await session.call_tool(name, args)
                    return "\n".join(getattr(x, "text", "") for x in res.content)
                # The Wall tells its story from the facts in its prompt ("use only the facts in your context"), so it
                # is offered no tools, and with none to choose the model answers without thinking (agent_loop.chat).
                async for event, data in agent_loop.pane([m.model_dump() for m in body.messages], system,
                                                         [] if body.prompt == "wall" else tools,
                                                         call, scrub, rungs=order):
                    yield _sse(event, _proposal(data, loc) if event == "proposal" else data)
        except Exception as e:  # noqa: BLE001
            log.warning("ask: %s", type(e).__name__)                  # the kind of failure, never the words
            yield _sse("error", {"message": f"the node could not answer ({type(e).__name__})"})
        finally:
            await hc.aclose()
    return StreamingResponse(stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"})


def _docs() -> list[dict]:
    rows = []
    try:
        rows += json.loads(DOCS_COPY.read_text())
    except (OSError, ValueError):
        pass
    try:
        for m in (json.loads(LEARN.read_text()).get("marks") or {}).values():
            rows.append({"page": m.get("page"), "anchor": m.get("anchor"), "title": m.get("title"),
                         "text": f"{m.get('quote', '')} {m.get('more', '')}"})
    except (OSError, ValueError):
        pass
    return rows


# Words a question carries that say nothing about what it asks, in the three languages the node speaks.
_STOP = set("""the and for are was what how does can could should would will with this that from have has had you your
our there their them they its into about when where which who why not but any all also just like more most some than
then too very get got make made use used need want know tell show give here does did doing being been were
apa yang dan untuk dari dengan ini itu ada bisa saya kami bagaimana kenapa mengapa kapan dimana siapa tidak
que qué los las del por para con una uno como cómo cuál cuando dónde quién está son hay puedo debo este esta eso""".split())
# A word a person uses, and the one the docs use for it.
_SAYS = {"rho": ("ρ",), "location": ("position",), "address": ("position",)}
_WORD = re.compile(r"[^\W_]+", re.U)


def _terms(q: str) -> list[str]:
    """The words of a question worth looking for: three letters or more, not a stop word, a plural's s dropped."""
    out = []
    for w in _WORD.findall(q.lower()):
        if len(w) < 3 or w in _STOP:
            continue
        w = w[:-1] if len(w) > 4 and w.endswith("s") else w
        if w not in out:
            out.append(w)
    return out


def _plain(text: str) -> str:
    """A section's words as a person reads them: no code blocks or tables, a link reduced to its words, no markdown marks."""
    t = re.sub(r"```.*?```", " ", text, flags=re.S)
    t = re.sub(r"(?:\|[^|]*){3,}\|?", " ", t)                     # a table, flattened onto one line
    t = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", t)
    t = re.sub(r"[`*#>]+|(?<!\w)-{2,}(?!\w)", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def _snippet(plain: str, words: list[str]) -> str:
    """The sentence holding the first word found, and what follows it, cut at a word: about 220 characters."""
    low = plain.lower()
    at = min((low.find(w) for w in words if w and w in low), default=0)
    start = plain.rfind(". ", 0, at) + 2 if plain.rfind(". ", 0, at) >= 0 else 0
    cut = plain[start: start + 240]
    return cut if len(plain) <= start + 240 else cut[: cut.rfind(" ")]


@router.get("/docs/search")
def docs_search(q: str = Query(..., min_length=2, max_length=200)):
    """This node's documentation, searched without a model, so the ask box is a docs search where no model is
    set up. The whole query as a phrase ranks first; otherwise each section is scored by the question's words it
    holds, a word in its title counting three times, and a section needs most of them. Twenty hits at most, the
    authors' style guide left out."""
    needle, terms = q.lower().strip(), _terms(q)
    ways = {w: (w, *_SAYS.get(w, ())) for w in terms}       # each word, and the docs' own words for it
    rows = [r for r in _docs() if r.get("page") != "STYLE.md"]
    # A word on every page ("node") says less than a rare one ("update"): weight each by how few sections hold it.
    hay = [(str(r.get("title") or "") + " " + str(r.get("text") or "")).lower() for r in rows]
    idf = {v: math.log((len(rows) + 1) / (1 + sum(v in h for h in hay))) for vs in ways.values() for v in vs}
    scored = []
    for r in rows:
        title, page = str(r.get("title") or "").lower(), str(r.get("page") or "").lower()
        raw = str(r.get("text") or "")
        text = _plain(raw) or re.sub(r"\s+", " ", re.sub(r"[|`*#>]+|-{2,}", " ", raw)).strip()   # a section that is all table
        low = text.lower()
        if needle in title or needle in low:
            score = 1000
        elif terms:
            found = [v for w in terms for v in ways[w] if v in title or v in low]
            asked = [w for w in terms if any(v in title or v in low for v in ways[w])]
            if len(asked) * 2 < len(terms) + (len(terms) > 2):     # most of the question's words, not one of them
                continue
            score = sum(idf[v] * (5 * (v in page) + 3 * (v in title) + (v in low)) for v in found)
        else:
            continue
        snippet = _snippet(text, [needle] + [v for vs in ways.values() for v in vs])
        scored.append((score, {"page": r.get("page"), "anchor": r.get("anchor"), "title": r.get("title"), "snippet": snippet}))
    scored.sort(key=lambda x: -x[0])
    hits = []
    for _, h in scored:
        if any(h["page"] == x["page"] and h["anchor"] == x["anchor"] for x in hits):
            continue
        hits.append(h)
        if len(hits) >= 20:
            break
    return hits
