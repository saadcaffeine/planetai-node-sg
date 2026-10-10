"""The ask pane: what the model is told, what it may do, and what is kept. No model, no database, no network.

  · privacy: the context built on node #1's 21 Sep capture carries none of the node's position to three
    decimals, no sensor or station name, no sensor id and no `meta`; and a tool result is scrubbed the same way
  · a request to turn MAP_TILES on is a `proposal` card and no setting changes
  · nothing is stored: after a request the log holds no word that was asked or answered, and the database was
    never opened
  · /ask/status is 404 with no loop set up, and says `running: false` with the tag when Ollama is down
  · /docs/search answers from the build's copy of docs/site, with no model
  · the three routes follow SHARE_LEVEL like every other read

Run: PACKS_DIR=packs PYTHONPATH=app python3 tests/test_ask.py
"""
import asyncio
import io
import json
import logging
import os
import sys
import time
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.chdir(ROOT)
os.environ.setdefault("PACKS_DIR", "packs")
sys.path.insert(0, str(ROOT / "app"))

try:
    from fastapi.testclient import TestClient
except ImportError:
    print("ask: skipped (pip install -r app/requirements.txt)")
    raise SystemExit(0)

logging.disable(logging.WARNING)
os.environ.update(ADMIN_TOKEN="admin-tok", NODE_NAME="bayu-2", DATABASE_URL="postgresql://unused/never-connected",
                  COMPOSE_PROFILES="mqtt,agent", OLLAMA_URL="http://127.0.0.1:9", AGENT_MODEL="qwen3.5:4b")
import settings                                     # noqa: E402
settings._cache = {"at": time.time() + 1e9, "rows": {}}
import main                                         # noqa: E402
import ask                                          # noqa: E402
import agent_loop                                   # noqa: E402
REAL_CHAT = agent_loop.chat                          # the fakes below replace it; the thinking checks need the real one
import issues as I                                  # noqa: E402
from issues import engine                           # noqa: E402
from issues import api as issues_api                # noqa: E402

fails = []


def check(ok, msg):
    if not ok:
        fails.append(msg)


class S(dict):
    def get(self, k, d=""):
        return super().get(k, d)

    def num(self, k, d):
        return d


FIX = json.loads((ROOT / "app/issues/fixtures/node1-2026-09-21d.json").read_text())
DOC = engine.replay(FIX, S(NODE_ISSUES="air,heat,land,coast"), I.load())
LAT, LON = FIX["health"]["lat"], FIX["health"]["lon"]
NAMES = sorted({s["name"] for s in FIX["sensors"] if s.get("name")} | {s["name"] for s in DOC["stations"] if s.get("name")})
IDS = sorted({s["sensor_id"] for s in FIX["sensors"]})
check(NAMES and IDS and any(n.lower() in json.dumps(DOC, ensure_ascii=False).lower() for n in NAMES),
      "the capture has no sensor name in its bundle, so the privacy test below would prove nothing")


def leaks(text: str) -> list[str]:
    found = [f"{v:.3f}" for v in (LAT, LON) if f"{v:.3f}" in text]
    found += [n for n in NAMES if len(n) >= 3 and n.lower() in text.lower()]
    found += [i for i in IDS if i in text]
    found += [f'"{k}"' for k in ("meta", "lat", "lon", "sensor_id") if f'"{k}"' in text]
    return found


# ---------------------------------------------------------------- privacy
learn = json.loads((ROOT / "app/static/learn.json").read_text())
scrub = ask.scrub_for(DOC, [s.get("name") for s in FIX["sensors"]], LAT, LON)
ctx = json.dumps(scrub.value(ask.context(DOC, "en", "now", "advanced", "lead", learn, "v0.73")), ensure_ascii=False)
check(not leaks(ctx), f"the pane's context carries {leaks(ctx)}")
check("focus" in ctx and "The first thing on Now" in ctx, "the context lost the learn entry for the part in focus")
check(json.loads(ctx)["open_alerts"], "the context lost the open alerts, so the privacy test is scrubbing nothing")
for name in ("sensors", "stations"):
    raw = json.dumps(FIX["sensors"] if name == "sensors" else DOC["stations"], ensure_ascii=False)
    check(leaks(raw) and not leaks(scrub(raw)), f"a {name} tool result reaches the model with {leaks(scrub(raw))}")
print("  privacy: the context and a tool result carry no position, name, id or meta")

# ---------------------------------------------------------------- the stubs every request below uses
LOG = io.StringIO()
logging.disable(logging.NOTSET)
handler = logging.StreamHandler(LOG)
logging.getLogger().addHandler(handler)
logging.getLogger().setLevel(logging.DEBUG)

opened = []
main.db = lambda: opened.append("db") or (_ for _ in ()).throw(RuntimeError("no database in this test"))
main.q = lambda sql, *a: [{"name": s.get("name")} for s in FIX["sensors"]] if "FROM sensors" in sql else []
issues_api.issues_now = lambda: DOC
written = []
settings.set = lambda *a, **k: written.append(("settings.set", a, k))

ASKED = "Could you please turn the satellite map on for me"
ANSWER = "I have put the satellite map on a card for you to press"


class Tool:
    def __init__(self, name):
        self.name, self.description, self.inputSchema = name, name, {"type": "object", "properties": {}}


class Session:
    def __init__(self):
        self.called = []

    async def call_tool(self, name, args):
        self.called.append(name)
        return type("R", (), {"content": [type("C", (), {"text": json.dumps(FIX["sensors"])})()]})()


SESSION = Session()


@asynccontextmanager
async def fake_session(hc, url=None, keep=None):
    listed = [Tool(n) for n in ("status", "sensors", "settings_get", "settings_set", "act", "run_pack_script")]
    yield SESSION, keep(listed)


SCRIPT = []


async def fake_chat(hc, rung, messages, tools, final=False, system=None):
    SCRIPT.append({"tools": [t["function"]["name"] for t in tools or []], "system": system,
                   "seen": json.dumps([m.get("content") for m in messages if m.get("role") == "tool"], ensure_ascii=False)})
    if len(SCRIPT) == 1:
        return {"role": "assistant", "content": "", "tool_calls": [
            {"id": "a", "function": {"name": "sensors", "arguments": "{}"}},
            {"id": "b", "function": {"name": "settings_set", "arguments": json.dumps({"changes": {"MAP_TILES": "on"}})}},
            {"id": "c", "function": {"name": "act", "arguments": json.dumps({"alert_id": 367, "note": "I opened the windows"})}}]}
    return {"role": "assistant", "content": ANSWER}


agent_loop.node_session = fake_session
agent_loop.chat = fake_chat
lan = TestClient(main.app)
local = TestClient(main.app, client=("127.0.0.1", 51000))


def events(body: str) -> list[tuple[str, dict]]:
    out = []
    for block in body.strip().split("\n\n"):
        lines = dict(l.split(": ", 1) for l in block.split("\n") if ": " in l)
        if "event" in lines:
            out.append((lines["event"], json.loads(lines["data"])))
    return out


# ---------------------------------------------------------------- a request that asks for a change
settings._cache["rows"]["MAP_TILES"] = "off"
r = local.post("/ask", json={"messages": [{"role": "user", "content": ASKED}], "view": "now", "mode": "simple"})
check(r.status_code == 200 and r.headers["content-type"].startswith("text/event-stream"), f"/ask answered {r.status_code}")
ev = events(r.text)
kinds = [e for e, _ in ev]
prop = next((d for e, d in ev if e == "proposal"), None)
check(ask._proposal({"tool": "settings_set", "args": {"changes": {"MAP_TILES": "1"}}}, "en")["proposed"] is None,
      "a value the key would refuse must not be proposed")
check(prop and prop["setting"] == "MAP_TILES" and prop["current"] == "off" and prop["proposed"] == "on",
      f"MAP_TILES did not become a proposal card: {prop}")
check(prop and "tile server" in prop["leaves"]["en"] and "Set up" in prop["undo"]["en"],
      f"the card does not say what leaves and how to undo it: {prop}")
check("settings_set" not in SESSION.called and "sensors" in SESSION.called,
      f"the loop ran {SESSION.called}: an admin tool was executed, or a read was not")
check(not written and settings._cache["rows"]["MAP_TILES"] == "off", f"a setting changed: {written}")
actp = next((d for e, d in ev if e == "proposal" and d["tool"] == "act"), None)
check(actp and actp["args"] == {"alert_id": 367} and "opened the windows" not in r.text,
      f"an act card must carry the alert and never the model's words for what the person did: {actp}")
check("act" not in SESSION.called, "the loop ran act")
check(kinds[-1] == "done" and "tools" in kinds and "token" in kinds, f"the stream was {kinds}")
check("".join(d["text"] for e, d in ev if e == "token").strip() == ANSWER, "the answer did not arrive as tokens")
menu = SCRIPT[0]["tools"]
check("settings_get" not in menu and "status" in menu and "settings_set" in menu and "act" in menu,
      f"the pane's menu is {menu}")
check(not leaks(SCRIPT[0]["system"]), f"the system prompt carries {leaks(SCRIPT[0]['system'])}")
check(len(SCRIPT) > 1 and "sensor" in SCRIPT[1]["seen"] and not leaks(SCRIPT[1]["seen"]),
      f"the sensors result reached the model carrying {leaks(SCRIPT[-1]['seen'])}")
print("  proposal: MAP_TILES on is a card with its current value, what leaves and the way back; nothing changed")

# ---------------------------------------------------------------- the wall asks for its prompt by name
# WALL_SYSTEM lives on the node (docs/SPEC_language.md §The prompts): the page sends prompt:'wall' and the
# node composes the voice, the rotating angle, and — the part a missing line once cost — the figures.
before = len(SCRIPT)
r = local.post("/ask", json={"messages": [{"role": "user", "content": "speak"}], "view": "wall",
                             "mode": "advanced", "prompt": "wall"})
check(r.status_code == 200, f"/ask wall answered {r.status_code}")
wall = SCRIPT[before]["system"]
check("voice of this home's sensor node" in wall and "This time, start from" in wall,
      "the wall did not get WALL_SYSTEM with its rotating angle")
check("The page's context:" in wall and not leaks(wall),
      f"the wall's system prompt lost the scrubbed context, or carries {leaks(wall)}")
r = local.post("/ask", json={"messages": [{"role": "user", "content": "speak"}], "view": "wall",
                             "mode": "advanced", "prompt": "wall"})
check(r.status_code == 200 and SCRIPT[-1]["system"] != wall, "the wall's angle did not rotate between narrations")
print("  wall: the page asks by name; the voice, the figures and a fresh angle ride in the system prompt")

# ---------------------------------------------------------------- the shape a live node hands it
# A capture's timestamps are strings; the live engine's are datetimes straight from Postgres. v0.75 was
# tested on captures only and answered every question on node #1 with a 500 (datetime is not JSON
# serializable). The same request, on the live shape.
import copy                                          # noqa: E402
LIVE = copy.deepcopy(DOC)
for _v in LIVE["issues"].values():
    for _a in _v.get("open_asks") or []:
        _a["ts"] = datetime.fromisoformat(_a["ts"])
check(any(isinstance(a["ts"], datetime) for v in LIVE["issues"].values() for a in v.get("open_asks") or []),
      "the live-shaped bundle has no datetime in it, so this proves nothing")
issues_api.issues_now = lambda: LIVE
SCRIPT.clear()
r2 = local.post("/ask", json={"messages": [{"role": "user", "content": "how is it"}]})
check(r2.status_code == 200 and [e for e, _ in events(r2.text)][-1] == "done",
      f"on a live node's bundle /ask answered {r2.status_code}: {r2.text[:200]}")
issues_api.issues_now = lambda: DOC
print("  live shape: datetimes from Postgres reach the model as ISO strings, not a 500")

# ---------------------------------------------------------------- nothing is stored
logged = LOG.getvalue()
check(ASKED not in logged and ANSWER not in logged and "satellite map" not in logged,
      "a word somebody asked or the model answered is in the log")
check("[pane] tool sensors" in logged, "the log should still say which tool ran and how long it took")
check(not opened, "the pane opened the database")
check(not list((ROOT / "out").glob("*ask*")) if (ROOT / "out").exists() else True, "the pane wrote a file under out/")
print("  nothing kept: the log names the tool and its time, never a word; no database, no file")
logging.getLogger().removeHandler(handler)
logging.disable(logging.WARNING)

# ---------------------------------------------------------------- status
os.environ["COMPOSE_PROFILES"] = "mqtt"
_nf = local.get("/ask/status")
check(_nf.status_code == 404 and _nf.json()["detail"]["recommend"]["pull"].startswith("planetai agent local pull ")
      and _nf.json()["detail"]["mcp"] == "/mcp", f"the 404 must carry what to pull and the other way in: {_nf.text}")
check(local.post("/ask", json={"messages": [{"role": "user", "content": "hi"}]}).status_code == 404,
      "with no agent profile /ask must be 404")
os.environ["COMPOSE_PROFILES"] = "mqtt,agent"
st = local.get("/ask/status").json()
check(st["running"] is False and st["model"] == "qwen3.5:4b" and st["stored"] is False and "not answering" in st["why"],
      f"Ollama down should read running:false with the tag: {st}")
check({t["class"] for t in st["tools"]} == {"read", "act", "admin"} and "settings_get" not in {t["name"] for t in st["tools"]},
      f"/ask/status lists {st['tools']}")
print("  status: 404 with no loop, running:false with the tag when Ollama is down")

# ---------------------------------------------------------------- which model, and where it runs
# The pane follows Set up → Model and AGENT_PREFER, the same settings as the Telegram bot. What it must never
# do is reach an online model at `private`, or answer from one without saying so.
ROWS = settings._cache["rows"]
ROWS.update(AGENT_REMOTE_URL="http://macbook.local:11434/v1", AGENT_REMOTE_MODEL="qwen3:14b",
            AGENT_ONLINE_URL="https://api.anthropic.com/v1", AGENT_ONLINE_MODEL="claude-x", AGENT_ONLINE_KEY="k")
_probe_was, ask._probe = ask._probe, (lambda r: (True, ""))      # no network: macbook.local is not in this test
for prefer, want, leaves_, first_where in (
        ("private", ["remote", "local"], False, "your network"),
        ("fallback", ["remote", "online", "local"], True, "your network"),
        ("strongest", ["online", "remote", "local"], True, "online")):
    ROWS["AGENT_PREFER"] = prefer
    st = local.get("/ask/status").json()
    got = [r["rung"] for r in st["rungs"]]
    check(got == want, f"{prefer}: the pane would ask {got}, not {want}")
    check(st["leaves"] is leaves_ and st["where"] == first_where, f"{prefer}: status says {st['where']}, leaves={st['leaves']}")
    check(prefer != "private" or all(r["where"] != "online" for r in st["rungs"]), "private reached the online model")
st = local.get("/ask/status").json()
check(st["host"] == "api.anthropic.com" and st["model"] == "claude-x", f"strongest names {st['host']} {st['model']}")
ROWS["AGENT_PREFER"] = "private"
os.environ["COMPOSE_PROFILES"] = "mqtt"
st = local.get("/ask/status")
check(st.status_code == 200 and [r["rung"] for r in st.json()["rungs"]] == ["remote"]
      and st.json()["host"] == "macbook.local", f"a remote model with no loop on this node: {st.text[:200]}")
os.environ["COMPOSE_PROFILES"] = "mqtt,agent"
ask._probe = _probe_was

# A model that fails hands over to the next, and nothing from the failed attempt reaches the page: a card it
# proposed before falling over must not stand beside the card from the model that answered.
import httpx                                          # noqa: E402
async def flaky_chat(hc, rung, messages, tools, final=False, system=None):
    if rung.name == "remote":
        if not any(m.get("role") == "tool" for m in messages):
            return {"role": "assistant", "content": "", "tool_calls": [
                {"id": "p", "function": {"name": "settings_set", "arguments": json.dumps({"changes": {"UI_ASK": "off"}})}}]}
        raise httpx.ConnectError("macbook asleep")
    return {"role": "assistant", "content": "The local model answered."}
agent_loop.chat = flaky_chat
r3 = local.post("/ask", json={"messages": [{"role": "user", "content": "anything"}]})
ev3 = events(r3.text)
done = next((d for e, d in ev3 if e == "done"), {})
check(done.get("rung") == "local" and done.get("where") == "this machine",
      f"after the remote model failed, the answer should come from this machine: {done}")
check(not any(e == "proposal" for e, _ in ev3), "a proposal from the model that failed reached the page")
check("".join(d["text"] for e, d in ev3 if e == "token").strip() == "The local model answered.", "the answer is not the local one's")
agent_loop._SKIPS.clear()

# A model that READ something before falling over: its read went to the page as it happened, so the page is
# told to forget it (`retry`) before the next model starts, and the answer's reads are only the next one's.
async def reads_then_fails(hc, rung, messages, tools, final=False, system=None):
    if rung.name == "remote":
        if not any(m.get("role") == "tool" for m in messages):
            return {"role": "assistant", "content": "", "tool_calls": [{"id": "s", "function": {"name": "sensors", "arguments": "{}"}}]}
        raise httpx.ConnectError("macbook asleep")
    return {"role": "assistant", "content": "The local model answered."}
agent_loop.chat = reads_then_fails
ev4 = [e for e, _ in events(local.post("/ask", json={"messages": [{"role": "user", "content": "anything"}]}).text)]
check("tools" in ev4 and "retry" in ev4 and ev4.index("tools") < ev4.index("retry") < ev4.index("token"),
      f"a failed model's read should be followed by retry before the answer: {ev4}")
check("retry" not in [e for e, _ in ev], f"one model that answered sent a retry: {[e for e, _ in ev]}")
agent_loop.chat = fake_chat
agent_loop._SKIPS.clear()

# A read is news the moment it is done: the pane hears `tools` BEFORE the model is asked again, not with the
# answer at the end. Driven through pane() itself, because an HTTP test client hands back the whole body at once.
async def _live():
    calls = []
    async def chat2(hc, rung, messages, tools, final=False, system=None):
        calls.append(1)
        if len(calls) == 1:
            return {"role": "assistant", "content": "", "tool_calls": [{"id": "s", "function": {"name": "sensors", "arguments": "{}"}}]}
        return {"role": "assistant", "content": "Done."}
    async def call(name, args):
        return "[]"
    async for e, _ in agent_loop.pane([{"role": "user", "content": "x"}], "system", [], call, lambda t: t,
                                      chat_fn=chat2, rungs=[agent_loop.Rung("remote", "http://x/v1", "m")]):
        if e == "tools":
            return len(calls)
    return None
check(asyncio.run(_live()) == 1, "the read reached the page only after the model had been asked again")
for k in ("AGENT_REMOTE_URL", "AGENT_REMOTE_MODEL", "AGENT_ONLINE_URL", "AGENT_ONLINE_MODEL", "AGENT_ONLINE_KEY", "AGENT_PREFER"):
    ROWS.pop(k, None)
print("  ladder: private never goes online, strongest says it does, a failed model hands over and leaves nothing behind")

# ---------------------------------------------------------------- docs search, and the share level
hits = local.get("/docs/search", params={"q": "map_tiles"}).json()
check(hits and all({"page", "anchor", "title", "snippet"} <= set(h) for h in hits)
      and any("MAP_TILES" in h["snippet"] for h in hits), f"/docs/search found {hits[:2]}")
check(local.get("/docs/search", params={"q": "x"}).status_code == 422, "a one-letter search should be refused")
settings._cache["rows"]["SHARE_LEVEL"] = "off"
check(all(lan.get(p, params={"q": "air"}).status_code == 403 for p in ("/ask/status", "/docs/search")),
      "at SHARE_LEVEL=off the pane's routes must need a token from the WiFi")
settings._cache["rows"]["SHARE_LEVEL"] = "open"
check(lan.get("/docs/search", params={"q": "air"}).status_code == 200, "at open the WiFi may search the docs")
print("  docs: searched with no model; the routes follow SHARE_LEVEL")

# ---------------------------------------------------------------- the answer after a tool: no thinking, nothing cut silently
# Node #1, 28 Sep: "how many alerts in the last 24 hours" took 165 s. The tool took 73 ms; gemma4:31b then wrote
# 1,162 to 1,871 tokens of hidden thinking to count a list that had been cut at 8,000 characters, and got it wrong.
import httpx                                                       # noqa: E402
SEEN = []
def _server(refuse):
    def handle(req):
        b = json.loads(req.content)
        SEEN.append(b.get("reasoning_effort"))
        if refuse and "reasoning_effort" in b:
            return httpx.Response(400, json={"error": "Unrecognized request argument supplied: reasoning_effort"})
        return httpx.Response(200, json={"choices": [{"message": {"role": "assistant", "content": "ok"}}]})
    return httpx.AsyncClient(transport=httpx.MockTransport(handle))
_q = [{"role": "system", "content": "s"}, {"role": "user", "content": "how many alerts today?"}]
_t = _q + [{"role": "assistant", "content": "", "tool_calls": []}, {"role": "tool", "content": "[]"}]
async def _thinking():
    big = agent_loop.Rung("remote", "http://m.test/v1", "gemma4:31b")
    await REAL_CHAT(_server(False), big, list(_q), [{"type": "function"}])
    await REAL_CHAT(_server(False), big, list(_t), [{"type": "function"}])
    picky = agent_loop.Rung("online", "http://o.test/v1", "picky")
    got = await REAL_CHAT(_server(True), picky, list(_t), [{"type": "function"}])
    await REAL_CHAT(_server(True), picky, list(_t), [{"type": "function"}])
    small = agent_loop.Rung("local", "http://l.test/v1", "qwen3:4b", small=True)
    await REAL_CHAT(_server(False), small, list(_t), [{"type": "function"}])
    return got
_got = asyncio.run(_thinking())
check(SEEN[:2] == [None, "none"], f"thinking must choose the tool and be off after its result: {SEEN[:2]}")
check(SEEN[2:5] == ["none", None, None] and _got.get("content") == "ok",
      f"a server that refuses reasoning_effort must be asked again without it, and not sent it next time: {SEEN[2:5]}")
check(SEEN[5:] == [None], f"a small model has /no_think already and must not be sent reasoning_effort: {SEEN[5:]}")
check(agent_loop.cap("x" * 10) == "x" * 10, "a tool result under the cap must reach the model unchanged")
_c = agent_loop.cap("y" * 9000)
check(_c.startswith("y" * agent_loop.TOOL_CAP) and "[cut: this result is 9000 characters" in _c and "incomplete" in _c,
      "a tool result over the cap must say it was cut, or the model takes half a list for all of it")

import agent                                                       # noqa: E402
_URLS = []
_ROWS = [{"id": i, "ts": "2026-09-28T07:00:00Z", "rule_id": "heat/act", "level": "act", "text": "t" * 400,
          "acted_at": None} for i in range(18)]
agent._get = lambda path: (_URLS.append(path), _ROWS)[1]
_a = agent.alerts(since_hours=24)
check(_URLS[-1] == "/alerts?since_hours=24&limit=1000", f"since_hours must ask the node for the whole window: {_URLS[-1]}")
check(_a["count"] == 18 and len(_a["alerts"]) == 10 and all(len(r["text"]) <= 160 for r in _a["alerts"]),
      f"since_hours must count every alert in the window and send the newest ten, shortened: "
      f"{_a['count']}, {len(_a['alerts'])}")
check(len(json.dumps(_a)) < agent_loop.TOOL_CAP, "a day's alerts must fit in one tool result, uncut")
check(agent.alerts() == _ROWS and _URLS[-1] == "/alerts?limit=10", "without since_hours, alerts must be as it was")
_sql = []
main.q = lambda sql, *a: (_sql.append((sql, a)), [])[1]
local.get("/alerts", params={"since_hours": 24})
check(_sql and "make_interval(hours => %s)" in _sql[-1][0] and _sql[-1][1] == (24, 24, 50),
      f"/alerts?since_hours must bound the query by hours: {_sql[-1:] and _sql[-1][1]}")
print("  after a tool: no thinking, a cut result says so, alerts counts a window")

# ---------------------------------------------------------------- the pane's thread: how long it lasts, what is sent
# Tomas, 28 Sep: the pane got busy and never cleared. The thread lived in sessionStorage with no way to end it, and
# every question sent the last 24 messages back to the model. The thread's own functions are lifted out of the page
# and run in node against a fake sessionStorage and a clock this test moves.
import re, shutil, subprocess                                     # noqa: E401,E402
_js = open("app/static/dashboard.js").read()
_pane = re.search(r"const OPEN = 'planetai_ask_open'.*?\nconst recent = t => \{.*?\n\};", _js, re.S)
check(_pane, "the ask pane's thread functions (OPEN .. recent) are no longer together in dashboard.js")
check("messages: recent(t)" in _js, "send() must post recent(t), not the whole thread")
check("data-ask-new" in _js and "forget(); draw();" in _js, "the pane has no working new-conversation button")
if _pane and shutil.which("node"):
    _prog = """
const store = {}; let now = 1e12;
globalThis.sessionStorage = { getItem: k => (k in store ? store[k] : null), setItem: (k, v) => { store[k] = String(v); } };
Date.now = () => now;
""" + _pane.group(0) + """
const out = {};
const t = [{ role: 'card', key: 'air' }];
for (let i = 0; i < 12; i++) t.push({ role: 'user', content: 'q' + i }, { role: 'assistant', content: 'a' + i });
t.push({ role: 'user', content: 'now' }, { role: 'assistant', content: '' });
out.sent = recent(t).map(m => m.content);
out.firstRole = recent(t)[0].role;
out.afterError = recent([{ role: 'assistant', content: 'a' }, { role: 'user', content: 'q' }]).map(m => m.role);
keep(t); out.kept = thread().length;
now += 29 * 60 * 1000; out.at29 = thread().length;
keep(thread()); now += 31 * 60 * 1000; out.at31 = thread().length;
keep([{ role: 'user', content: 'x' }]); forget(); out.forgotten = thread().length;
store[THREAD] = JSON.stringify([{ role: 'user', content: 'old tab' }]); store[AT] = '';
now += 99 * 60 * 1000; out.legacy = thread().length;
console.log(JSON.stringify(out));
"""
    _r = subprocess.run(["node"], input=_prog, capture_output=True, text=True)
    check(_r.returncode == 0, f"the pane's thread functions did not run in node: {_r.stderr[-400:]}")
    if _r.returncode == 0:
        _o = json.loads(_r.stdout)
        check(_o["sent"] == ["q9", "a9", "q10", "a10", "q11", "a11", "now"],
              f"a question must go with the last three exchanges and nothing older: {_o['sent']}")
        check(_o["firstRole"] == "user" and _o["afterError"] == ["user"],
              f"what is sent must start at a question of the person's: {_o['firstRole']}, {_o['afterError']}")
        check(_o["kept"] == 27, f"the thread must keep what was said, the learn card included: {_o['kept']}")
        check(_o["at29"] == 27, "a thread 29 minutes old must still be there")
        check(_o["at31"] == 0, "a thread nobody added to for 31 minutes must be over")
        check(_o["forgotten"] == 0, "new conversation must leave nothing behind")
        check(_o["legacy"] == 1, "a thread from before this change has no clock, and must not vanish on load")
    print("  pane: new conversation, over after 30 idle minutes, three exchanges sent")

print("\n".join(f"  x {f}" for f in fails) or "  ask: private context, proposals not changes, nothing kept")
sys.exit(1 if fails else 0)
