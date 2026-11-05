"""The order of the model ladder, which decides whether household data leaves the network.

`strongest` sends every question to the online API when one is configured. `fallback` keeps it as the net under
this machine and the tailnet, used only when neither answers — what you want from a backup model. `private` drops
it entirely. A typo in AGENT_PREFER must not quietly behave like `strongest`, which is why settings.CHOICES pins
the three values; this test covers the ordering itself.
"""
import sys
import types

# agent_loop imports httpx and mcp for the parts this test does not touch. Stub them; the Makefile already does the
# same for httpx in the other suites.
for name, attrs in (("httpx", {"AsyncClient": object, "HTTPError": type("HTTPError", (Exception,), {})}),
                    ("mcp", {"ClientSession": object}),
                    ("mcp.client", {}),
                    ("mcp.client.streamable_http", {"streamable_http_client": lambda *a, **k: None})):
    mod = types.ModuleType(name)
    for k, v in attrs.items():
        setattr(mod, k, v)
    sys.modules.setdefault(name, mod)

sys.path.insert(0, "app")
import agent_loop as A  # noqa: E402

BOTH = {"AGENT_ONLINE_URL": "https://generativelanguage.googleapis.com/v1beta/openai",
        "AGENT_ONLINE_KEY": "k", "AGENT_REMOTE_URL": "http://100.64.0.1:8082/v1"}


def names(**over):
    return [r.name for r in A.ladder({**BOTH, **over})]


assert names(AGENT_PREFER="strongest") == ["online", "remote", "local"], names(AGENT_PREFER="strongest")
# online ABOVE local: a rung is skipped only when it fails, and the 4B local model never fails, it answers
# badly — so online last meant a configured paid model was never reached while the tailnet box slept.
assert names(AGENT_PREFER="fallback") == ["remote", "online", "local"], names(AGENT_PREFER="fallback")
assert names(AGENT_PREFER="private") == ["remote", "local"], names(AGENT_PREFER="private")

# The key absent from .env AND from the settings table is the case this whole file is about. Until v0.63 the two
# call sites defaulted to "strongest", so a household that pasted an API key into the Model page and never opened
# the preference sent its 64 kB report bundle — its numbers, its room names, its own sentences — to somebody
# else's API first and to the model on the box last. BOTH is fully configured here and online must still be absent.
assert names() == ["remote", "local"], names()
# and the value, wherever it was set, still decides
assert names(AGENT_PREFER="strongest") == ["online", "remote", "local"], "an explicit choice is not overridden"

# The second default: what /model prints. It reads through cfg(), which is CFG then os.environ then the default —
# so with neither, the household is told the truth about where its sentences go.
A.CFG = {}
os = __import__("os"); os.environ.pop("AGENT_PREFER", None)
assert "Prefer: private" in A.ladder_text({}, "chat"), A.ladder_text({}, "chat")

# fallback with nothing online configured is just the local ladder, not an empty one
assert names(AGENT_PREFER="fallback", AGENT_ONLINE_KEY="") == ["remote", "local"]
# local is always last-resort present, even with nothing else set at all
assert [r.name for r in A.ladder({"AGENT_PREFER": "fallback"})] == ["local"]

# a URL that is not a URL is not a rung — node #1 held the text of .env.example's own comment here
assert "online" not in names(AGENT_PREFER="fallback", AGENT_ONLINE_URL="# https://api.anthropic.com/v1 or ..."), \
    "a non-URL must not become a rung that can only fail"
assert "remote" not in names(AGENT_PREFER="fallback", AGENT_REMOTE_URL="100.64.0.1:8082"), \
    "a host with no scheme is not a URL"

# the one setting where a typo must be refused rather than tolerated: not-"private" sends data off the network
sys.path.insert(0, "app")
import settings as S  # noqa: E402
# private first: describe() publishes this tuple and every surface offers the values in the order it gives them.
assert S.CHOICES["AGENT_PREFER"] == ("private", "fallback", "strongest"), S.CHOICES.get("AGENT_PREFER")
assert set(S.CHOICES["AGENT_PREFER"]) == {"private", "fallback", "strongest"}, "the three values themselves do not change"

# ---------------------------------------------------------------------------------------------------
# The model is a client of this node, not a component of it.
#
# Stage 1's trigger has not fired, the 9 September benchmark memo retired "local AI over your own data"
# as a claim, and the agent surface is twenty-one tools including settings_set and run_pack_script. What the
# unattended model on the box may reach is therefore a decision, and this is where it is held.
import types  # noqa: E402 — already imported above; named again because this block stands on its own
import tool_classes as TC  # noqa: E402

ADMIN = {n for n, c in TC.TOOL_CLASS.items() if c == "admin"}
assert ADMIN == {"settings_set", "run_pack_script", "maintenance", "report_now"}, ADMIN

# 1. the allow-list is derived, not retyped: a tool added to TOOL_CLASS as admin cannot appear here
assert A.LOCAL_TOOLS == {n for n, c in TC.TOOL_CLASS.items() if c in ("read", "act")}
assert not (A.LOCAL_TOOLS & ADMIN), "an admin tool is in the local model's allow-list"

# 2. and the filter actually drops them. to_openai_tools is the ONE place the model's menu is built,
#    so this is the whole mechanism: hand it every tool the server has and see what comes back.
Tool = type("Tool", (), {})
def _t(name):
    t = Tool(); t.name = name; t.description = ""; t.inputSchema = {}; return t
menu = {f["function"]["name"] for f in A.to_openai_tools([_t(n) for n in TC.TOOL_CLASS])}
assert menu == A.LOCAL_TOOLS, sorted(menu ^ A.LOCAL_TOOLS)
for bad in ADMIN:
    assert bad not in menu, f"{bad} reached the local model's menu"
assert "act" in menu and "issues" in menu, "read and act must still be there; this is a subset, not a lockout"

# 3. nothing was removed from the MCP surface. A keeper in Claude Desktop over the tailnet still has all
#    twenty-one, which is the case the surface was built for.
assert len(TC.TOOL_CLASS) == 21, len(TC.TOOL_CLASS)

# 4. rho is built out of what people said, so a model may not write a row without it. The placeholders
#    are the strings this repository itself used where a human's sentence belongs.
assert {"acted", "acted (via reticulum)"} <= TC.PLACEHOLDER_NOTES
assert "/act" in open("app/agent_loop.py").read()
src = open("app/agent_loop.py").read()
assert '"note": parts[2] if len(parts) > 2 else "acted"' not in src, \
    "the Telegram handler is substituting a placeholder for the person's own words again"
assert "What did you do about it?" in src, "it must ask for the words instead of inventing them"

# 5. `planetai agent` prints the class, and the two cannot drift. The CLI is Bash and cannot import the
#    table, so this is the gate instead of a shared file.
import re  # noqa: E402
CLI = open("bin/planetai").read()
block = CLI[CLI.index('echo "    read   '):CLI.index('echo "  A person driving an agent')]
for name in TC.TOOL_CLASS:
    assert re.search(rf"(?<![\w-]){re.escape(name)}(?![\w-])", block), \
        f"`planetai agent` does not list {name}; a tool nobody is told about is a tool nobody audits"
admin_line = next(l for l in block.splitlines() if '"    admin' in l)
for name in ADMIN:
    assert re.search(rf"(?<![\w-]){re.escape(name)}(?![\w-])", admin_line), f"{name} is not on the CLI's admin line"
for name in A.LOCAL_TOOLS:
    if name != "act":                       # `act` appears on its own line, by name, with its rule
        assert not re.search(rf"(?<![\w-]){re.escape(name)}(?![\w-])", admin_line), \
            f"{name} is listed as admin in the CLI and is {TC.TOOL_CLASS[name]} in the table"

print("the local model gets read and act; settings_set, run_pack_script, maintenance and report_now are withheld")
print("the ladder: strongest online-first, fallback remote-online-local, private online-never, and a non-URL is not a rung")

# A key that ships blank must not carry a trailing comment. Compose's env_file strips an inline comment only when the
# key has a value: `KEY=    # note` hands the container "# note". Node #1 ran for weeks with the text of
# .env.example's own comment in AGENT_ONLINE_URL, and AGENT_REMOTE_URL shipped the same trap — a blank remote URL
# became a rung pointing at "# a bigger local model on your tailnet".
import re as _re
_env = open(".env.example").read()
_bad = _re.findall(r"^([A-Z_][A-Z0-9_]*)=[ \t]+#.*$", _env, _re.M)
assert not _bad, f"put the comment on its own line above these keys, not after them: {_bad}"

print(".env.example: no blank key carries a trailing comment compose would read as its value")

# Where a rung runs is read off its address, never its name (agent_loop.stays_home). A city's GPU server typed into
# AGENT_REMOTE_URL leaves the house, and until 21 Oct 2026 the node called it "your network" and handed it what the
# house learned. Each pair: the URL, and whether a model there stays home.
for url, home in (("http://host.docker.internal:11434/v1", True), ("http://localhost:11434/v1", True),
                  ("http://192.168.4.44:11434/v1", True), ("http://macbook.local:11434/v1", True),
                  ("http://100.64.0.1:8082/v1", True), ("http://gpu.tail1234.ts.net/v1", True),
                  ("http://ollama:11434/v1", True), ("http://[::1]:8080/v1", True),
                  ("https://api.anthropic.com/v1", False), ("https://vllm.city.example.org/v1", False),
                  ("http://8.8.8.8/v1", False), ("http://100.128.0.1/v1", False)):
    assert A.stays_home(url) is home, f"{url}: stays_home says {A.stays_home(url)}"
# Under private a rung at a public address is not used at all (Tomas, 21 Oct 2026): private means nothing leaves.
city = {"AGENT_REMOTE_URL": "https://vllm.city.example.org/v1", "AGENT_PREFER": "private"}
assert [r.name for r in A.ladder(city)] == ["local"], "private used a remote model at a public address"
assert A.models_stay_home(city), "private with a public remote: it is not used, so nothing leaves"
assert [r.name for r in A.ladder({**city, "AGENT_REMOTE_URL": "http://192.168.4.44:11434/v1"})] == ["remote", "local"], \
    "private dropped a remote model on the house's own network"
city_fb = {**city, "AGENT_PREFER": "fallback"}
assert [A.where_of(r)["where"] for r in A.ladder(city_fb)] == ["online", "this machine"], "fallback: a public remote is online"
assert not A.models_stay_home(city_fb), "fallback with a public remote: the house's learnings would leave"
assert A.models_stay_home({**BOTH, "AGENT_PREFER": "private"}), "private, tailnet remote, local: everything stays home"
assert not A.models_stay_home({**BOTH, "AGENT_PREFER": "fallback"}), "fallback may reach the online rung"

# And the Telegram bot hands a rung that leaves what the pane hands any rung: no settings, no report bundle, no day's
# export. A tool the rung was not offered is refused, not run, even when the model names it anyway.
import asyncio as _aio


class _HC:
    def __init__(self, *a, **k): pass
    async def __aenter__(self): return self
    async def __aexit__(self, *a): return False


class _Session:
    def __init__(self): self.called = []
    async def call_tool(self, name, args):
        self.called.append(name)
        return types.SimpleNamespace(content=[types.SimpleNamespace(text="{}")])


_menus = []


async def _chat(hc, rung, messages, tools, final=False):
    _menus.append(sorted(t["function"]["name"] for t in tools or []))
    if len(_menus) == 1:        # the model asks for a withheld tool by name, as a model off its menu does
        return {"role": "assistant", "content": "", "tool_calls": [{"id": "1", "function": {"name": "settings_get", "arguments": {}}}]}
    return {"role": "assistant", "content": "done"}


_tools = [{"type": "function", "function": {"name": n, "parameters": {}}} for n in ("status", "settings_get", "report_bundle", "export_day")]
A.httpx.AsyncClient, A.chat = _HC, _chat
for rungs, offered, ran in (([A.Rung("remote", "https://vllm.city.example.org/v1", "m")], ["status"], []),
                            ([A.Rung("remote", "http://100.64.0.1:8082/v1", "m")], sorted(t["function"]["name"] for t in _tools), ["settings_get"])):
    _menus.clear(); A.RUNGS = rungs; s = _Session()
    _aio.run(A.ask(s, _tools, "hi"))
    assert _menus[0] == offered, f"{rungs[0].url}: offered {_menus[0]}"
    assert s.called == ran, f"{rungs[0].url}: ran {s.called}"
print("a rung is home or online by its address; one that leaves gets no settings, bundle or export, and the house's learnings stay")
