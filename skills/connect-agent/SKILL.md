---
name: connect-agent
description: Give a person's own agent the node's twenty-one MCP tools, over their tailnet, without opening a port to the internet.
---

# Connecting an agent to a node

The node is an MCP server. Any client that speaks MCP can hold its tools.

## Get the three facts from the node itself, not from this file

```bash
planetai agent
```

It prints, for this node: the **URL** (localhost, and the tailnet address if there is one), the
**`Authorization: Bearer` header** with the node's real `ADMIN_TOKEN`, and a ready-made JSON snippet with
the node's own name in it. Those three facts are the whole configuration. Never guess a token; never write
one into a file you will commit.

Read `AGENTS.md` before the first call. It is the operating manual for whatever you connect, and it lists
the twenty-one tools.

## The answer is Tailscale, not a port forward

A node lives in somebody's home. Its MCP endpoint is behind an admin token, on a LAN or a tailnet, and
that is the design — not a limitation to route around.

If the person asks how to reach it from outside, the answer is `planetai mesh` and `docs/NETWORKING.md`:
Tailscale puts the node on their private network and the same URL works from anywhere they are. **Do not
suggest a router port forward, ngrok, a public tunnel, or a reverse proxy on a public hostname**, and do
not help configure one. An admin token on the open internet is one credential away from a stranger with
`settings_set` on somebody's house.

## Wiring it up

**Claude Code, from a clone of this repository.** `.mcp.json` in the repo root is project-scoped and
already correct. Set the three variables in the shell first — the file holds no secret:

```bash
export PLANETAI_MCP_URL="http://<node>:8080/mcp"
export PLANETAI_ADMIN_TOKEN="…"     # from `planetai agent`
export PLANETAI_AGENT_NAME="your-name"
```

**Claude Code, anywhere else.**

```bash
claude mcp add --transport http planetai "$PLANETAI_MCP_URL" \
  --header "Authorization: Bearer $PLANETAI_ADMIN_TOKEN" \
  --header "X-Agent: $PLANETAI_AGENT_NAME"
```

**Claude Desktop, Codex, a local model with an MCP client.** Use the JSON snippet `planetai agent` prints.

**Cursor.** Cursor reads its own `.cursor/mcp.json` and does not expand `${VAR:-default}` the way Claude
Code does, so `.mcp.json` here will not work for it. Use the snippet `planetai agent` prints, with the
values already filled in.

## Name yourself in every write

Every write — `act`, `settings_set`, `report_now`, `run_pack_script` — takes an `agent` argument, and that
is how a name reaches the audit trail: `act` writes it as the action's `actor`, and `settings_set` passes it
on to the node's API as `X-Agent`; `report_now` and `run_pack_script` record no name. The default is
`agent`, which tells nobody anything. Pass your own name in that argument on every write (the `X-Agent`
header you send on `/mcp` itself is not read by the tools in this version). A node may have a local model on
it already, appearing as `local-model/<rung>`; without a name of your own, the trail cannot tell you apart.
Pick a name a person would recognise a month from now.

## Call health_check first

`health_check` before anything else, every session. Every failing check names its own fix, its `sources`
says which of the node's fundamental sources is not running yet, and it tells you what this node can
honestly answer before you ask it something it cannot. Then `status`, then the
tool you came for.

What the tools never hand you: a reading a pack declared `private`, and, unless every model this node may
use runs on the house's own machines, what the house learned (`learned` says why instead).

`act` and `settings_set` write. Read the invariants in `AGENTS.md` before either, and read
`troubleshoot-node` before you change a threshold.

## When a doc and this file disagree

The doc wins and this file has a bug. Say so, and open an issue.
