"""A model runs the node, over Telegram. Which model: the strongest one reachable, from a ladder you configure.

  online   Anthropic or OpenAI, with a key. The most capable. The only rung that sends anything off your network.
  remote   a bigger local model elsewhere on your tailnet: a laptop's Ollama, an exo cluster. Private, no key.
  local    Ollama on this machine, qwen3:4b. Always there.

AGENT_PREFER=private never uses online at all, and is what a node does when nobody has chosen: the household's own
sentences stay on the machine that recorded them until somebody says otherwise. =fallback tries your own remote model
first, then online, then local — online above local because a rung is skipped only when it *fails*, and a 4B model
never fails, it answers badly. =strongest tries online, remote, local in that order. A rung that is unreachable,
unauthorised or erroring is skipped for five minutes. `/model` in Telegram shows the ladder and which
rung answered; `/model local` pins one for the conversation.

All three speak the OpenAI-compatible chat protocol with tools, which Ollama, exo, OpenAI and Anthropic all serve.
The node's own MCP tools are the model's hands; every write records X-Agent=<AGENT_NAME>/<rung>.

This container has no clock. It answers when someone writes; it sends nothing on a schedule. The node keeps one
schedule, in the app container, and writes the report itself (REPORT_EVERY / REPORT_ANCHOR): a second clock here
sent a 07:00 copy of a report the household had already read at 06:00, and from v0.30 to v0.35 sent nothing at
all — it handed Telegram a tuple and logged a 400 every morning.

Alerts do not pass through the model. The node sends them; the model answers questions about them.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import time

import httpx
import re
from contextlib import asynccontextmanager
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("agent")
for noisy in ("httpx", "mcp"):
    logging.getLogger(noisy).setLevel(logging.WARNING)

MCP_URL = os.getenv("MCP_URL", "http://app:8080/mcp")


def node_url(path: str) -> str:
    """A plain HTTP endpoint on the app, derived from the MCP endpoint. The Cowork audit (10 Oct) flagged the
    old `MCP_URL.replace("/mcp", path)`: it munges a URL that merely contains those letters and breaks
    silently on one that lacks them. Strip the suffix only if it is a suffix, then add the path."""
    return MCP_URL.removesuffix("/mcp").rstrip("/") + path
TOKEN = os.getenv("ADMIN_TOKEN", "")
NAME = os.getenv("AGENT_NAME", "local-model")
NODE = os.getenv("NODE_NAME", "node")
# Telegram and locale come from the node's settings (the dashboard may hold them, not .env); env is the fallback.
CFG: dict = {}
def cfg(k, d=""): return (CFG.get(k) or os.getenv(k) or d)
def TG_TOKEN(): return cfg("TELEGRAM_BOT_TOKEN")
def CHATS(): return {c.strip() for c in cfg("TELEGRAM_CHAT_IDS").replace(" ", "").split(",") if c.strip()}
LOCALE = os.getenv("ALERT_LOCALE", "en")


LANG_NAME = {"id": "Bahasa Indonesia", "es": "Spanish"}.get(LOCALE, "English")


def T(en: str, **other: str) -> str:
    """The bot's own few sentences, in the node's language. Bahasa falls back to English here until a native reader
    has been through the set; the model itself answers in whatever ALERT_LOCALE says."""
    return other.get(LOCALE, en)
MAX_ROUNDS = 8
SKIP_FOR = 300


class Rung:
    def __init__(self, name, url, model, key="", small=False):
        self.name, self.url, self.model, self.key, self.small = name, url.rstrip("/"), model, key, small
        self.skip_until = 0.0

    def headers(self):
        h = {"content-type": "application/json"}
        if self.key:
            h["Authorization"] = f"Bearer {self.key}"
            if "anthropic.com" in self.url:
                h["x-api-key"] = self.key
        return h


RUNGS: list[Rung] = []
_SKIPS: dict[str, float] = {}


def ladder(cfg: dict) -> list[Rung]:
    """Build the ladder from settings (the dashboard's Model page) with the environment as fallback."""
    g = lambda k, d="": (cfg.get(k) or os.getenv(k) or d)  # noqa: E731

    def url_ok(name, u):
        """A URL that is not one is not a rung. Node #1 held the literal text of .env.example's comment —
        '# https://api.anthropic.com/v1 or ...' — in AGENT_ONLINE_URL, pasted in through the Model page. With no key
        set it was harmless and invisible; the moment a key arrived it would have been a rung that could only fail."""
        if u.startswith("http://") or u.startswith("https://"):
            return True
        log.warning("%s rung ignored: %s is not a URL (%r). Set it on the dashboard's Model page.",
                    name, f"AGENT_{name.upper()}_URL", u[:60])
        return False

    rungs = []
    if g("AGENT_ONLINE_URL") and g("AGENT_ONLINE_KEY") and url_ok("online", g("AGENT_ONLINE_URL")):
        rungs.append(Rung("online", g("AGENT_ONLINE_URL"), g("AGENT_ONLINE_MODEL", "claude-sonnet-4-6"), g("AGENT_ONLINE_KEY")))
    if g("AGENT_REMOTE_URL") and url_ok("remote", g("AGENT_REMOTE_URL")):
        rungs.append(Rung("remote", g("AGENT_REMOTE_URL"), g("AGENT_REMOTE_MODEL", "gpt-oss-120b"), g("AGENT_REMOTE_KEY")))
    rungs.append(Rung("local", os.getenv("OLLAMA_URL", "http://host.docker.internal:11434") + "/v1", os.getenv("MODEL", "qwen3:4b"), small=True))
    prefer = g("AGENT_PREFER", "private")
    if prefer == "private":
        rungs = [r for r in rungs if r.name != "online"]
    elif prefer == "fallback":
        # Your own big model, then the online one, then the small local model last.
        #
        # Online has to sit ABOVE local, not below it. A rung is skipped only when it *fails*, and qwen3:4b never
        # fails — it answers, weakly. Putting online last therefore meant that the moment the tailnet box was
        # asleep the household got 4B answers and the paid model it had configured was never once reached. Local
        # stays on the bottom as the floor that works with no internet at all.
        rank = {"remote": 0, "online": 1, "local": 2}
        rungs.sort(key=lambda r: rank[r.name])
    for r in rungs:                        # keep the skip clocks across rebuilds
        r.skip_until = _SKIPS.get(r.name, 0.0)
    return rungs


async def refresh_ladder(hc: httpx.AsyncClient) -> None:
    """Every minute: re-read the runtime settings so a change in the dashboard reaches the bot without a restart."""
    global RUNGS
    while True:
        try:
            r = await hc.get(node_url("/settings/raw"))
            cfg = r.json() if r.status_code == 200 else {}
            if r.status_code != 200:
                log.warning("settings/raw -> %s (is ADMIN_TOKEN the same as the app's?)", r.status_code)
        except Exception as e:  # noqa: BLE001
            log.warning("settings/raw unreachable at %s: %s", MCP_URL, type(e).__name__)
            cfg = {}
        CFG.clear(); CFG.update(cfg)
        for r_ in RUNGS:
            _SKIPS[r_.name] = r_.skip_until
        new = ladder(CFG)
        if [(x.name, x.model, x.url) for x in new] != [(x.name, x.model, x.url) for x in RUNGS]:
            log.info("ladder: %s", [f"{x.name}:{x.model}" for x in new])
        RUNGS = new
        await asyncio.sleep(60)

SYSTEM = f"""You run PLANETAI node '{NODE}', a small computer that connects everything measuring one place, from sensors on
the wall to satellites overhead, and tells the people there what to do about the air, the heat, the sea and the land. You have tools that read the node and act on it. You are talking to the people who live
or work here, on Telegram.
- Use tools to answer; never guess numbers. For "how is it" questions call health_check and status. For the sea, swell, surf, wind, rain, UV or the land, call `context`. For a sensor's history, `readings`.
- Answer in {LANG_NAME}. Explain, do not just report: say what is happening, what it means for them, and what to do.
- Start with an emoji that fits (🏠 inside, 🌳 outside, 🛰️ satellites, 🌊 sea, 🥵 heat, 📡 a sensor, ✅ fine, ⚠️ watch, 🚨 act). Use a few more where they help the eye. Short paragraphs, not lists.
- Avoid statistics. No means, peaks, correlations, percentages or counts unless the person asks for numbers. One number is fine when it drives the advice (a PM2.5 level, a temperature).
- Speak in layers: what is happening, in words, first; the one number when it drives the advice; what a term means only when the person asks.
- No lecture voice: no "it is important to", no signposting, no reassurance kickers, no rhetorical questions. Advice is physical, specific, and keeps its reason.
- When a person says they did something about an alert, record it with `act` as their note, and thank them. It is their note on what happened, not the node's measurement: the node measures that itself, from the sensors.
- Never reveal tokens or values that look like secrets.
- Tasks that need the node's shell (update, backup, restart): give the exact command from `maintenance` and say it runs on the node.
- Plain text only: Telegram shows it raw. No asterisks, no backticks, no headings. Line breaks and emojis are your formatting.
- Under 100 words unless the person asks for detail. One message, not a report.
- If you do not know, say so. Reply with the answer only; do not narrate what you did."""


def clean(text: str) -> str:
    """Strip thinking blocks and Markdown: Telegram gets plain text, and a model reaches for ** and ``` anyway."""
    import re
    t = re.sub(r"<think>.*?</think>", "", text or "", flags=re.S)
    t = re.sub(r"```[a-z]*\n?", "", t)
    t = re.sub(r"(\*\*|__|`)", "", t)
    t = re.sub(r"^#{1,6}\s*", "", t, flags=re.M)
    return re.sub(r"\n{3,}", "\n\n", t).strip()


# The local model is a CLIENT of this node, not a component of it. It may read the node and it may record
# that a human acted; it may not change a setting, run a pack's code, or make the node speak to the
# household unprompted. `app/agent.py::TOOL_CLASS` is the authority and this is the subset — imported
# rather than retyped, so a tool added there cannot quietly appear in a model's menu here.
#
# NOTHING IS REMOVED FROM THE MCP SURFACE. A person operating an agent over the tailnet still has all
# twenty. This is only what the model running unattended on the box is handed.
from tool_classes import TOOL_CLASS  # noqa: E402 — a table and nothing else; see that module's docstring

LOCAL_CLASSES = ("read", "act")
LOCAL_TOOLS = frozenset(n for n, c in TOOL_CLASS.items() if c in LOCAL_CLASSES)


def to_openai_tools(tools) -> list[dict]:
    kept, dropped = [], []
    for t in tools:
        (kept if t.name in LOCAL_TOOLS else dropped).append(t)
    if dropped:
        log.info("tools withheld from the local model (%s): %s",
                 ", ".join(sorted({TOOL_CLASS.get(t.name, "?") for t in dropped})),
                 ", ".join(sorted(t.name for t in dropped)))
    return [{"type": "function", "function": {"name": t.name, "description": t.description or "",
                                              "parameters": getattr(t, "input_schema", None) or getattr(t, "inputSchema", None) or {"type": "object", "properties": {}}}} for t in kept]


TOOL_CAP = 8000
NO_EFFORT: set = set()      # (url, model) of the servers that answered `reasoning_effort` with a 400


def cap(text: str) -> str:
    """A tool result, cut to TOOL_CAP characters, saying so when it was. Cut silently it was half a list the model
    took for all of it: asked how many alerts there were in a day, it counted the ~16 that fit and answered 17
    with 18 in the table."""
    if len(text) <= TOOL_CAP:
        return text
    return text[:TOOL_CAP] + (f"\n[cut: this result is {len(text)} characters and only the first {TOOL_CAP} are "
                              "shown. It is incomplete; ask for less, or for a count.]")


async def chat(hc: httpx.AsyncClient, rung: Rung, messages: list, tools: list | None, final: bool = False,
               system: str | None = None) -> dict:
    body = {"model": rung.model, "messages": messages, "temperature": 0.2}
    if tools and not final:
        body["tools"] = tools
    if final and rung.small:            # a small model narrates its reasoning as prose; a schema stops that
        body["response_format"] = {"type": "json_schema", "json_schema": {"name": "answer", "schema": {"type": "object", "properties": {"answer": {"type": "string"}}, "required": ["answer"]}}}
    if rung.small:
        messages[0] = {"role": "system", "content": (system or SYSTEM) + "\n/no_think"}
    # After a tool result, answer without thinking. The thinking is what chooses a tool, and it is short; after
    # the result it was a model counting a list in hidden text: on node #1, gemma4:31b wrote 1,162 to 1,871
    # tokens of it at 9 to 16 a second for a 42-character sentence, and the pane waited one to three minutes.
    # Off for that round, it wrote 19. A server that does not take the field says so with a 400, once.
    elif messages[-1].get("role") == "tool" and (rung.url, rung.model) not in NO_EFFORT:
        body["reasoning_effort"] = "none"
    r = await hc.post(f"{rung.url}/chat/completions", json=body, headers=rung.headers())
    if r.status_code == 400 and body.pop("reasoning_effort", None):
        NO_EFFORT.add((rung.url, rung.model))   # module-level: the pane builds its rungs again for every question
        r = await hc.post(f"{rung.url}/chat/completions", json=body, headers=rung.headers())
    r.raise_for_status()
    return r.json()["choices"][0]["message"]


def _tool_json(res) -> dict:
    """An MCP tool result's payload. The server returns text content holding JSON."""
    for c in getattr(res, "content", []) or []:
        text = getattr(c, "text", None)
        if text:
            try:
                return json.loads(text)
            except ValueError:
                continue
    return {}


def stack_text(data: dict, one: str = "") -> str:
    """`/stack` and `/stack <issue>`, written from the node's own sentences and nothing else.

    The sentence, the state and the four distances are all computed on the node (app/issues/), so
    this function only lays them out. It picks the locale from ALERT_LOCALE, the same setting the
    alerts and the report use, so the house is answered in one language.
    """
    if data.get("error"):
        known = ", ".join(data.get("declares") or []) or "nothing yet"
        return f"I do not watch that here. This node watches: {known}."   # the only line here that is not the node's
    if one:
        rows = [(one, data)]
        head = None
    else:
        issues, head = data.get("issues") or {}, data.get("headline")
        rows = [(k, issues[k]) for k in (data.get("order") or []) if k in issues]
    if not rows:
        return "No issues are declared on this node yet. Set NODE_ISSUES under Set up → Basics."
    out = []
    for key, iss in rows:
        name = (iss.get("name") or {}).get(LOCALE) or key
        mark = " ←" if head == key else ""
        out.append(f"{name.upper()} · {iss.get('state', '?')}{mark}")
        out.append(iss.get("sentence", {}).get(LOCALE) or "")
        labels = (data.get("labels") or {}).get(LOCALE, {})
        cols = []
        for dist in (data.get("distances") or ("room", "yard", "ring", "region")):
            cell = (iss.get("stack") or {}).get(dist)
            if not cell or cell.get("value") is None:
                continue
            cols.append(f"{labels.get(dist, dist)} {cell['value']:.{iss.get('dp', 0)}f} "
                        f"({cell.get('provenance', '?')})")
        if cols:
            out.append("  " + " · ".join(cols) + f" {iss.get('unit', '')}")
        for ask in (iss.get("open_asks") or [])[:2]:
            says = (ask.get("says") or {}).get(LOCALE, "")
            how = (ask.get("how") or {}).get(LOCALE, "")
            out.append(f"  #{ask.get('id')} — {says}. {how}".rstrip())
        out.append("")
    return "\n".join(out).strip()


@asynccontextmanager
async def node_session(hc: httpx.AsyncClient, url: str | None = None, keep=None):
    """One MCP session per question, not one per process. Yields (session, tools).

    A session held open for the life of the container dies with the first network blip or server-side expiry, and
    every POST /mcp after that comes back 404 'session not found'. Nothing crashes and nothing is logged, because
    call_tool's exception is written into the tool result: the model reads "tool error", and answers "I am unable
    to reach the node" — to every question, forever, until someone restarts the container. That was this node on
    9 September: the session opened at 15:39, three questions at 22:16, 22:17 and 22:28 sent twelve calls, the app
    answered 404 to all twelve, and the agent log showed only the calls going out.

    The handshake is four requests to a container on the same bridge, and questions arrive minutes apart, so paying
    it per question costs nothing anyone can feel. Reconnect logic would be more code and still lose the first call
    after a drop.
    """
    async with streamable_http_client(url or MCP_URL, http_client=hc) as (r, w, *_):
        async with ClientSession(r, w) as session:
            await session.initialize()
            listed = (await session.list_tools()).tools
            yield session, (keep(listed) if keep else to_openai_tools(listed))


async def ask(session: ClientSession, tools: list[dict], user: str, history: list[dict] | None = None, pin: str | None = None) -> tuple[str, str]:
    """Returns (answer, rung name). Walks the ladder; a rung that fails is skipped for five minutes."""
    now = time.time()
    order = [r for r in RUNGS if (pin is None or r.name == pin) and r.skip_until < now] or [r for r in RUNGS if pin is None or r.name == pin]
    last_err = None
    async with httpx.AsyncClient(timeout=240) as hc:
        for rung in order:
            messages = [{"role": "system", "content": SYSTEM}, *(history or []), {"role": "user", "content": user}]
            try:
                for _ in range(MAX_ROUNDS):
                    msg = await chat(hc, rung, messages, tools)
                    messages.append(msg)
                    calls = msg.get("tool_calls") or []
                    if not calls:
                        if rung.small:
                            messages.append({"role": "user", "content": "Give the final answer for the person now: a short explanation with an emoji or two, what it means, what to do. No statistics unless they asked."})
                            fin = await chat(hc, rung, messages, None, final=True)
                            try:
                                return clean(json.loads(fin.get("content") or "{}").get("answer", "")) or clean(msg.get("content")), rung.name
                            except Exception:  # noqa: BLE001
                                return clean(msg.get("content")) or "(no answer)", rung.name
                        return clean(msg.get("content")) or "(no answer)", rung.name
                    for c in calls:
                        fn = c["function"]["name"]
                        args = c["function"].get("arguments") or {}
                        if isinstance(args, str):
                            try: args = json.loads(args)
                            except Exception: args = {}
                        spec = next((t for t in tools if t["function"]["name"] == fn), {}).get("function", {}).get("parameters", {}).get("properties", {})
                        if "agent" in spec:
                            args.setdefault("agent", f"{NAME}/{rung.name}")
                        shown = {k: ("****" if ("KEY" in k or "TOKEN" in k or "PASS" in k) else v) for k, v in args.items()} if fn != "settings_set" else {"changes": sorted((args.get("changes") or {}).keys())}
                        log.info("[%s] tool %s %s", rung.name, fn, json.dumps(shown)[:160])   # never the values of settings_set: a Telegram token or an AI key would land in the container log
                        try:
                            res = await session.call_tool(fn, args)
                            text = cap("\n".join(getattr(x, "text", "") for x in res.content))
                        except Exception as e:  # noqa: BLE001
                            # Log it as well as handing it to the model. A tool error the model turns into "I cannot
                            # reach the node" is invisible otherwise: the line above logs the call, and nothing logs
                            # that it failed.
                            log.warning("[%s] tool %s failed: %s: %s", rung.name, fn, type(e).__name__, str(e)[:200])
                            text = f"tool error: {type(e).__name__}: {e}"
                        messages.append({"role": "tool", "tool_call_id": c.get("id", fn), "content": text})
                return T("I ran out of steps. Ask something narrower.", es="Me quedé sin pasos. Pregunta algo más concreto."), rung.name
            except (httpx.HTTPError, KeyError, ValueError) as e:
                last_err = e
                rung.skip_until = time.time() + SKIP_FOR
                log.warning("[%s] unavailable (%s: %s); trying the next rung", rung.name, type(e).__name__, str(e)[:100])
    why = type(last_err).__name__ if last_err else 'none configured'
    return T(f"No model answered ({why}). On the node: `ollama list`, and check AGENT_* in .env.",
             es=f"Ningún modelo respondió ({why}). En el nodo: `ollama list`, y revisa AGENT_* en .env."), "none"


# ---------------------------------------------------------------------------------------- the dashboard's pane
#
# The same local rung, asked from the dashboard instead of Telegram, with a narrower contract: it reads, and
# everything else it would do is a PROPOSAL the person presses. `app/ask.py` serves it at POST /ask.
#
#   read   executed, and each result is scrubbed of positions, names and ids before the model sees it
#   act    not executed: a proposal. The person presses it and the page writes the ledger row exactly as its
#          own I-did-this button does, with the person's own words. A model recording an act is a model
#          putting words in a household's mouth; the pane does not.
#   admin  not executed: a proposal, with the setting, its current and proposed value, what would leave
#          the house and how to undo it. The person presses it with the token the page holds for Set up.
#
# Withheld even from `read`: settings_get (chat ids, hostnames), report_bundle and export_day. The pane can be
# open on a wall at SHARE_LEVEL=open, and the one who types is not always the one who set the node up.
PANE_WITHHELD = frozenset({"settings_get", "report_bundle", "export_day"})
PANE_RUNS = frozenset(n for n, c in TOOL_CLASS.items() if c == "read") - PANE_WITHHELD
PANE_PROPOSES = frozenset(n for n, c in TOOL_CLASS.items() if c in ("act", "admin"))
PANE_TOOLS = PANE_RUNS | PANE_PROPOSES
AUDIT_PANE = "dashboard-chat"

PANE_SYSTEM = """You are PLANETAI node '{node}', answering a person reading this node's own dashboard. The page's
context is below: what the page is showing right now. Use it first; call a tool
only when the question needs more.
- You may read. You may not change anything. To change a setting, call settings_set with
  {{"changes": {{"KEY": "value"}}}}; nothing changes, the person is shown a card and decides. Say that is what you did.
- Call act only when the person says they did something about an alert, and only with the alert's id. The
  person writes what they did on the card, in their own words; never write it for them.
- Never guess a number. Say what you know and what you do not.
- Answer in {lang}. Plain sentences, no Markdown, under 90 words unless asked for more. One number
  only when it drives the advice.
- Speak in layers: what is happening, in words, first; the one number when it helps; what a term
  means only when the person asks. The page context carries the node's own sentences for this.
- No lecture voice: no "it is important to", no signposting, no reassurance kickers, no rhetorical
  questions. Advice is physical, specific, and keeps its reason.

The page's context:
{context}"""


# WALL_SYSTEM: the node's "thinking aloud" voice for the wall screen (docs/SPEC_language.md §The prompts).
# Verbatim from app/static/doors-wall.js:73, with NARR_ANGLES rotation handled node-side.
WALL_ANGLES = ['what is happening right now', 'what has changed over the last few hours', 'how warm it feels inside the home',
  'how inside the home compares with the street and the neighbourhood', 'how today compares with the last few days']
WALL_SYSTEM = """You are the voice of this home's sensor node, speaking on a screen in the living room to people who know nothing about air science, units or maps. Like a calm neighbour telling a short story, say what is happening around their home: the air, and the heat if your context has it. Plain everyday words only. Never write units or symbols such as µg/m³, °C, PM2.5, AQI, ppm, percent or km. Say 'inside your home', 'your street', 'the neighbourhood', 'the wider area' instead of room, yard, ring or region. Instead of numbers, compare: 'clean', 'a little hazy', 'well under the safe limit', 'warmer than usual for this hour'. At most two numbers. Go in this order: what is happening inside the home; how that compares with the street and the neighbourhood; what it suggests for an ordinary day, such as windows, cooking, sleep or children outside, never telling people that anything is safe, fine or without risk, only what the readings show; and last, what the next few hours may bring, from the forecast or the usual pattern for this hour if your context has it, or that the node will keep watching if it does not. Use only the figures in your context. Six to eight sentences, one paragraph, no lists, no greeting, no questions."""


def pane_tools(listed) -> list[dict]:
    """The pane's menu: the reads it runs and the writes it may only propose, in the OpenAI shape."""
    return [{"type": "function", "function": {
        "name": t.name,
        "description": (t.description or "") + (" (PROPOSAL ONLY: nothing is changed; the person is shown a card)"
                                                if t.name in PANE_PROPOSES else ""),
        "parameters": getattr(t, "input_schema", None) or getattr(t, "inputSchema", None)
        or {"type": "object", "properties": {}}}} for t in listed if t.name in PANE_TOOLS]


def local_rung() -> Rung:
    """The rung on this machine and no other. The pane says `runs on this machine`, so it may not fall
    through to a tailnet box or an online key the way the Telegram ladder does."""
    return Rung("local", os.getenv("OLLAMA_URL", "http://host.docker.internal:11434") + "/v1",
                os.getenv("AGENT_MODEL") or os.getenv("MODEL") or "qwen3:4b", small=True)


def _text_call(content) -> list[dict]:
    """A tool call a small model wrote as its answer: `{"name": "issues", "arguments": {...}}` as plain text.

    qwen2.5-coder does this on Ollama's OpenAI endpoint instead of filling `tool_calls`, and the pane then
    printed the JSON to the person as its answer. Read as a call only when the name is a tool it was offered."""
    try:
        j = json.loads(clean(content or ""))
    except ValueError:
        return []
    if isinstance(j, dict) and j.get("name") in PANE_TOOLS:
        return [{"id": "text-call", "function": {"name": j["name"], "arguments": j.get("arguments") or {}}}]
    return []


def recommend() -> dict:
    """The tag `planetai agent local` recommends for this machine's memory, and its size on disk.

    The same two rows as bin/planetai::cmd_agent_local, measured against the registry on 20 September 2026.
    Inside a container /proc/meminfo is the machine the container runs on, which under Colima is the VM and
    not the Mac, so this errs small, never large."""
    try:
        kb = next(int(l.split()[1]) for l in open("/proc/meminfo") if l.startswith("MemTotal"))
        gb = kb // 1048576
    except (OSError, StopIteration, ValueError):
        gb = 0
    tag, size = ("qwen3.5:9b", "6.6 GB") if gb >= 16 else ("qwen3.5:4b", "3.4 GB")
    return {"tag": tag, "size": size, "memory_gb": gb or None, "pull": f"planetai agent local pull {tag}"}


def where_of(rung: Rung) -> dict:
    """Where a rung runs, in the words the pane prints: this machine, your network, or online.

    `online` is the one that leaves the house: the pane says so in its header and on every answer it gives."""
    from urllib.parse import urlparse
    host = urlparse(rung.url).hostname or rung.url
    return {"rung": rung.name, "model": rung.model, "host": host,
            "where": {"local": "this machine", "remote": "your network"}.get(rung.name, "online")}


def pane_rungs(cfg: dict, with_local: bool = True) -> list[Rung]:
    """The ladder the pane walks: the same settings and the same AGENT_PREFER as the Telegram bot, so one
    choice under Set up → Model governs both. `private` (the default) never includes the online rung.
    `with_local` is False when no loop was set up here, so no Ollama is assumed on this machine."""
    rungs = []
    for r in ladder(cfg):
        if r.name == "local":
            if not with_local:
                continue
            r = local_rung()
            r.skip_until = _SKIPS.get("local", 0.0)
        rungs.append(r)
    return rungs


async def pane(messages: list[dict], system: str, tools: list[dict], call, scrub, chat_fn=None,
               rungs: list[Rung] | None = None):
    """One answer for the dashboard's pane, as a stream of (event, data).

    `call(name, args)` runs a read tool and returns its text; `scrub(text)` is what every result passes through
    before the model sees it. Events: `tools` per read (name and ms), `proposal` per write the model reached for
    (tool and args; app/ask.py adds the setting's words), `token` for the answer, `done` with where the answer
    was produced, or `error`.

    The rungs are tried in order, and a rung that fails is skipped for five minutes, as on Telegram. A
    proposal from a failed attempt is dropped, not streamed: it must not sit on the page beside the same
    proposal from the rung that answered. A `tools` event goes out the moment its read is done, because
    while a model works it is the only news the pane has; if that rung then fails, `retry` tells the pane
    to forget the reads it was shown before the next rung starts.

    NOTHING IS LOGGED BUT THE TOOL'S NAME, ITS TIME AND WHICH RUNG ANSWERED. Not the question, not the answer,
    not the arguments: the pane keeps no transcript anywhere, and a log line is a transcript by another name.
    """
    chat_fn = chat_fn or chat
    rungs = rungs if rungs is not None else [local_rung()]
    now = time.time()
    order = [r for r in rungs if r.skip_until < now] or list(rungs)
    last = None
    async with httpx.AsyncClient(timeout=240) as hc:
        for rung in order:
            convo = [{"role": "system", "content": system}, *messages]
            events: list[tuple[str, dict]] = []
            read = False
            try:
                for _ in range(MAX_ROUNDS):
                    msg = await chat_fn(hc, rung, convo, tools, system=system)
                    convo.append(msg)
                    calls = msg.get("tool_calls") or _text_call(msg.get("content"))
                    if not calls:
                        text = clean(msg.get("content"))
                        if rung.small and not text:
                            fin = await chat_fn(hc, rung, convo, None, final=True, system=system)
                            try:
                                text = clean(json.loads(fin.get("content") or "{}").get("answer", ""))
                            except ValueError:
                                text = clean(fin.get("content"))
                        for e in events:
                            yield e
                        for word in (text or "(no answer)").split(" "):
                            yield "token", {"text": word + " "}
                        log.info("[pane] answered by %s", rung.name)
                        yield "done", where_of(rung)
                        return
                    for c in calls:
                        fn = c["function"]["name"]
                        args = c["function"].get("arguments") or {}
                        if isinstance(args, str):
                            try:
                                args = json.loads(args)
                            except ValueError:
                                args = {}
                        if fn in PANE_PROPOSES:
                            events.append(("proposal", {"tool": fn, "args": args}))
                            text = "Nothing was changed. It is on a card in front of the person, who decides."
                        elif fn in PANE_RUNS:
                            t0 = time.time()
                            try:
                                text = cap(scrub(await call(fn, args)))
                            except Exception as e:  # noqa: BLE001
                                text = f"tool error: {type(e).__name__}"
                            ms = round((time.time() - t0) * 1000)
                            log.info("[pane] tool %s %d ms", fn, ms)
                            read = True
                            yield "tools", {"tool": fn, "ms": ms}
                        else:
                            text = "That tool is not offered here."
                        convo.append({"role": "tool", "tool_call_id": c.get("id", fn), "content": text})
                for e in events:
                    yield e
                yield "error", {"message": "ran out of steps; ask something narrower"}
                return
            except (httpx.HTTPError, KeyError, ValueError) as e:
                last = e
                rung.skip_until = time.time() + SKIP_FOR
                _SKIPS[rung.name] = rung.skip_until
                log.warning("[pane] %s did not answer (%s); trying the next rung", rung.name, type(e).__name__)
                if read:
                    yield "retry", {"rung": rung.name}
    w = ", ".join(f"{where_of(r)['model']} ({where_of(r)['where']})" for r in order) or "none set up"
    yield "error", {"message": f"no model answered ({type(last).__name__ if last else 'none'}): tried {w}"}


class TelegramError(Exception):
    """Carries the status code only. Never the response, never the URL: both contain the bot token."""


async def telegram(method: str, **params):
    async with httpx.AsyncClient(timeout=40) as hc:
        try:
            r = await hc.post(f"https://api.telegram.org/bot{TG_TOKEN()}/{method}", json=params)
        except httpx.HTTPError as e:
            raise TelegramError(f"{type(e).__name__}") from None
        if r.status_code == 401:
            raise TelegramError("401: Telegram rejects this bot token. Run `planetai telegram` on the node to set the current one.")
        if r.status_code == 409:
            raise TelegramError("409: something else is polling this bot (a second agent, or a webhook). Only one may.")
        if r.status_code >= 400:
            raise TelegramError(f"{r.status_code}")
        return r.json()


# ----------------------------------------------------------- event buttons (SPEC_alerts §7)
NOTE_WINDOW = 600          # seconds to answer "what did you do instead?" after Doesn't fit


def parse_callback(data) -> tuple[int, str] | None:
    """ev:<event_id>:<stage> — the contract main.py's _event_keyboard writes under every event message."""
    m = re.fullmatch(r"ev:(\d+):(acted|acknowledged|dismissed)", str(data or ""))
    return (int(m.group(1)), m.group(2)) if m else None


def note_pending(pending: dict, chat: str, text: str, now: float) -> int | None:
    """The Doesn't-fit follow-up. The dismissal was already recorded at the press; a free-text line within
    NOTE_WINDOW becomes its note — a second actions row, which is allowed on purpose ("two people who both acted
    are both recording something true"), and the wire keeps the latest answer, which is the one carrying the note.
    A command is never a note and leaves the ask open; a stale ask is forgotten. Returns the event id to
    annotate, or None."""
    p = pending.get(chat)
    if not p:
        return None
    if now - p[1] > NOTE_WINDOW:
        pending.pop(chat, None)
        return None
    if text.startswith("/"):
        return None
    pending.pop(chat, None)
    return p[0]


def _name_of(user: dict) -> str:
    return ((user.get("first_name") or "") or (user.get("username") or "") or "someone").strip()[:80] or "someone"


async def _post_answer(hc, event_id: int, stage: str, actor: str, note: str = "") -> None:
    r = await hc.post(node_url("/actions"), timeout=15,
                      json={"event_id": event_id, "stage": stage, "actor": actor, "note": note})
    r.raise_for_status()


async def handle_callback(hc, cq: dict, pending: dict) -> None:
    """One button press on an event message: record the answer on the node (the same POST /actions the dashboard
    makes — page and phone write the same row), lift the keyboard, and say in chat who pressed, so the chat
    itself carries the record. Doesn't fit asks the one optional question and keeps the reply as the note."""
    qid = cq.get("id")
    msg = cq.get("message") or {}
    chat = str((msg.get("chat") or {}).get("id", ""))
    actor = _name_of(cq.get("from") or {})
    parsed = parse_callback(cq.get("data"))
    if chat not in CHATS():
        log.info("callback from chat %s ignored: not in TELEGRAM_CHAT_IDS", chat)
        if qid:
            await telegram("answerCallbackQuery", callback_query_id=qid)
        return
    if not parsed:
        if qid:
            await telegram("answerCallbackQuery", callback_query_id=qid,
                           text=T("This button is from another time; the event it belonged to is no longer mine.",
                                  es="Este botón es de otro momento; el evento al que pertenecía ya no es mío."))
        return
    eid, stage = parsed
    try:
        await _post_answer(hc, eid, stage, actor)
    except Exception as e:  # noqa: BLE001
        log.warning("answer on event #%s failed: %s: %s", eid, type(e).__name__, str(e)[:200])
        if qid:
            await telegram("answerCallbackQuery", callback_query_id=qid,
                           text=T("⚠️ I could not record that on the node. Nothing was written; press again in a moment.",
                                  es="⚠️ No pude anotarlo en el nodo. No se escribió nada; pulsa de nuevo en un momento."))
        return
    if qid:
        await telegram("answerCallbackQuery", callback_query_id=qid)
    word = {"acted": T("Done", es="Hecho"), "acknowledged": T("Not now", es="Ahora no"),
            "dismissed": T("Doesn't fit", es="No encaja")}[stage]
    try:
        await telegram("editMessageReplyMarkup", chat_id=chat, message_id=msg.get("message_id"),
                       reply_markup={"inline_keyboard": []})
        await telegram("sendMessage", chat_id=chat, text=f"{word} · {actor}")
    except Exception as e:  # noqa: BLE001
        log.warning("callback follow-up failed: %s", type(e).__name__)
    if stage == "dismissed":
        pending[chat] = (eid, time.monotonic())
        await telegram("sendMessage", chat_id=chat,
                       text=T("What did you do instead? One line, or ignore me.",
                              es="¿Qué hiciste en su lugar? Una línea, o ignórame."))


async def announce_buttons(hc) -> None:
    """The bot's signature on the node: TELEGRAM_BUTTONS=1 tells the app its event messages may carry the three
    buttons. A node without the agent container never gets the setting and sends the same message bare
    (SPEC_alerts §7). Best-effort: a failure here costs the buttons, never the messages."""
    try:
        async with node_session(hc) as (session, _t):
            await session.call_tool("settings_set", {"changes": {"TELEGRAM_BUTTONS": "1"}, "agent": f"{NAME}/telegram"})
        log.info("event buttons on (TELEGRAM_BUTTONS=1)")
    except Exception as e:  # noqa: BLE001
        log.warning("could not turn the event buttons on (%s: %s): messages go without buttons",
                    type(e).__name__, str(e)[:120])


def ladder_text(pins: dict, chat: str) -> str:
    now = time.time()
    lines = [f"{'→' if pins.get(chat) == r.name else ' '} {r.name:7} {r.model} @ {r.url.replace('http://','').replace('https://','')[:40]}" + ("  (skipped, retry soon)" if r.skip_until > now else "") for r in RUNGS]
    # cfg(), not os.getenv(): the Model page writes AGENT_PREFER to the database, and reading only the environment
    # told every household that changed it there that it was still on 'strongest'.
    prefer = cfg("AGENT_PREFER", "private")
    order = {"private": "the node's own machines only, nothing leaves the network",
             "fallback": "your remote model first, then online, then the small local one as the offline floor",
             "strongest": "strongest first, so online answers whenever it is configured"}
    return "Model ladder, tried top to bottom:\n" + "\n".join(lines) + \
        f"\nPrefer: {prefer} — {order.get(prefer, 'unknown value; treated as strongest')}." + \
        "\nPin one: /model local | remote | online. Unpin: /model auto"


async def main():
    if not TOKEN:
        raise SystemExit("ADMIN_TOKEN is required")
    hc = httpx.AsyncClient(headers={"Authorization": f"Bearer {TOKEN}", "X-Agent": NAME}, timeout=120)
    for i in range(30):                    # the app may still be starting; its settings are the source of truth, not .env
        try:
            if (await hc.get(node_url("/health"), timeout=5)).status_code == 200:
                break
        except Exception:  # noqa: BLE001
            pass
        if i == 0: log.info("waiting for the node at %s", MCP_URL)
        await asyncio.sleep(2)
    asyncio.create_task(refresh_ladder(hc))
    await asyncio.sleep(2)
    log.info("%s: ladder %s", NODE, [f"{r.name}:{r.model}" for r in RUNGS])
    log.info("telegram: %s", f"bot set, answering {len(CHATS())} chat(s): {sorted(CHATS())}" if TG_TOKEN() and CHATS() else "NOT configured (no TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_IDS in settings or .env) — the bot will not answer anyone")
    try:                                   # once, so the log says the node answered and how many tools it offers
        async with node_session(hc) as (_s, tools):
            log.info("%d tools", len(tools))
    except Exception as e:  # noqa: BLE001
        log.warning("could not reach the node's tools at startup (%s: %s); each question opens its own session anyway",
                    type(e).__name__, str(e)[:120])
    if TG_TOKEN() and CHATS():
        await announce_buttons(hc)
    offset, history, pins, pending = 0, {}, {}, {}
    while True:
        if not TG_TOKEN():
            await asyncio.sleep(30); continue
        try:
            upd = await telegram("getUpdates", offset=offset, timeout=25, allowed_updates=["message", "callback_query"])
        except TelegramError as e:
            msg = e.args[0] if e.args else "error"      # TelegramError carries a status code and advice, never the URL
            log.warning("telegram: %s", msg); await asyncio.sleep(30 if msg[:3] in ("401", "409") else 10); continue
        except Exception as e:  # noqa: BLE001
            log.warning("telegram: %s", type(e).__name__); await asyncio.sleep(10); continue
        for u in upd.get("result", []):
            offset = u["update_id"] + 1
            cq = u.get("callback_query")
            if cq:
                try:
                    await handle_callback(hc, cq, pending)
                except Exception as e:  # noqa: BLE001
                    log.warning("callback failed: %s: %s", type(e).__name__, str(e)[:200])
                continue
            m = u.get("message") or {}
            chat = str((m.get("chat") or {}).get("id", "")); text = (m.get("text") or "").strip()
            if not text:
                continue
            if chat not in CHATS():
                log.info("message from chat %s ignored: not in TELEGRAM_CHAT_IDS %s", chat, sorted(CHATS()))
                continue
            note_eid = note_pending(pending, chat, text, time.monotonic())
            if note_eid is not None:
                try:
                    await _post_answer(hc, note_eid, "dismissed", _name_of(m.get("from") or {}), note=text)
                    said = T(f"Kept as the note for event #{note_eid}.",
                             es=f"Anotado como la nota del evento #{note_eid}.")
                except Exception as e:  # noqa: BLE001
                    log.warning("note on event #%s failed: %s: %s", note_eid, type(e).__name__, str(e)[:200])
                    said = T("⚠️ I could not keep that note on the node. The Doesn't fit stands; the note is lost.",
                             es="⚠️ No pude guardar esa nota en el nodo. El No encaja queda; la nota se pierde.")
                await telegram("sendMessage", chat_id=chat, text=said)
                continue
            if text.startswith("/act"):
                parts = text.split(maxsplit=2)
                if len(parts) >= 2 and parts[1].isdigit() and len(parts) < 3:
                    # No words, no row. `act` used to substitute "acted" here, which put a placeholder
                    # where the person's own sentence belongs — and rho is built out of those sentences.
                    # Asking costs one message and gets something true.
                    await telegram("sendMessage", chat_id=chat,
                                   text=T(f"What did you do about #{parts[1]}? Send it as:  /act {parts[1]} <what you did>",
                                          es=f"¿Qué hiciste con la #{parts[1]}? Envíalo así:  /act {parts[1]} <lo que hiciste>"))
                    continue
                if len(parts) >= 3 and parts[1].isdigit():
                    try:
                        async with node_session(hc) as (session, _t):
                            await session.call_tool("act", {"alert_id": int(parts[1]), "note": parts[2], "agent": f"{NAME}/telegram"})
                        said = T(f"Recorded: you acted on #{parts[1]}.", es=f"Anotado: actuaste sobre #{parts[1]}.")
                    except Exception as e:  # noqa: BLE001
                        log.warning("act on #%s failed: %s: %s", parts[1], type(e).__name__, str(e)[:200])
                        said = T(f"⚠️ I could not record that on the node ({type(e).__name__}). Nothing was written; try again in a moment.",
                                 es=f"⚠️ No pude anotarlo en el nodo ({type(e).__name__}). No se escribió nada; inténtalo de nuevo en un momento.")
                    await telegram("sendMessage", chat_id=chat, text=said)
                    continue
            if text.startswith("/stack"):
                # No model, ever. /stack is a read of the node's own arithmetic printed through a
                # template, so it answers on a node with no agent rung reachable at all — which is
                # the same promise the report and the alerts already make. It sits above ask() so a
                # model never gets the chance to paraphrase a number.
                arg = text.split(maxsplit=1)[1].strip().lower() if " " in text else ""
                try:
                    async with node_session(hc) as (session, _t):
                        res = await session.call_tool("issues", {"issue": arg} if arg else {})
                    said = stack_text(_tool_json(res), arg)
                except Exception as e:  # noqa: BLE001
                    log.warning("/stack failed: %s: %s", type(e).__name__, str(e)[:200])
                    said = T(f"⚠️ I could not read the node ({type(e).__name__}). Nothing is wrong with your air; this is me.",
                             es=f"⚠️ No pude leer el nodo ({type(e).__name__}). Tu aire está bien; el problema soy yo.")
                await telegram("sendMessage", chat_id=chat, text=said)
                continue
            if text.startswith("/model"):
                arg = text.split(maxsplit=1)[1].strip().lower() if " " in text else ""
                if arg in {r.name for r in RUNGS}: pins[chat] = arg
                elif arg == "auto": pins.pop(chat, None)
                await telegram("sendMessage", chat_id=chat, text=ladder_text(pins, chat))
                continue
            t0 = time.time()
            try:
                async with node_session(hc) as (session, tools):
                    answer, rung = await ask(session, tools, text, history.get(chat, [])[-6:], pins.get(chat))
            except Exception as e:  # noqa: BLE001
                # The node itself, not a model: say so plainly rather than letting a model guess at it.
                log.warning("no session to the node for chat %s: %s: %s", chat, type(e).__name__, str(e)[:200])
                answer, rung = f"⚠️ I could not open a session to the node just now ({type(e).__name__}). It may be restarting — try again in a moment.", "none"
            history.setdefault(chat, []).extend([{"role": "user", "content": text}, {"role": "assistant", "content": answer}])
            log.info("chat %s via %s: %.1fs", chat, rung, time.time() - t0)
            await telegram("sendMessage", chat_id=chat, text=answer[:4000])


if __name__ == "__main__":
    asyncio.run(main())
