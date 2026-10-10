# Developing

## Two machines

The dev machine has git and pushes. A node runs `planetai update` and never commits. Node #1 is a Mac mini at Fab Lab
Bali; its Python is Apple's 3.9 with no third-party libraries, and that is the Python the CLI must run on.

## Before every commit

```bash
make lint      # shell syntax, SQL idempotency, compose mounts, CLI snippets as Python 3.9 with stdlib only,
               # rules and cells against init.sql, docs against the code, the GUI, pyflakes, the app imports
make test      # the 56 offline suites in tests/all, one line each and a count at the end
```

The pre-commit hook runs lint and refuses `.env`, credentials, `.DS_Store`, and anything under `.git`. Install it once:
`cp tools/hooks/pre-commit .git/hooks/`.

## What each gate exists for

Every gate is a bug that shipped.

| gate | the bug |
|---|---|
| `check_sql.py` | a comment ate a closing bracket; a missing config Docker replaced with an empty directory; `.DS_Store` committed; `\| grep -q` under pipefail failing a good dump |
| `check_cli_python.py` | f-strings that crashed on Python 3.9; PyYAML the node does not have; a `for` after a semicolon |
| `check_rules.py` | a 69-day cooldown that made `test-alert` report a dead node; message placeholders the SQL never returned |
| `check_docs.py` | "two containers, five rules" when there were nine adapters and eight packs; links to files that had moved. Reads `docs/site/` too since v0.72.1, when the site was found fifteen releases behind |
| `build_docs.py --check` | the docs site as a site: a NAV source that is gone, a page NAV never lists, a link to no page, an anchor to no heading |
| `check_ui.py` | an element id the script referenced that was not in the markup |
| `check_theme.py` | the copy of the design repo's theme drifting on this side, where nothing would say what moved. Holds the three frozen files to the sha256s in `data/frozen_layer.txt` on every lint — including CI and a node, where planetai-design is not checked out and the byte comparison cannot run |
| `check_registry.py` | a pack naming `environmental/city/alphaearth` after the registry filed it as `alphaearth-satellite-embedding`, and a `social/community/openstreetmap` twin that was never filed. Also a hand-edited `data/sources/index.json`, and a pin that stopped half-way through a sync |
| `tools/session.sh preflight` / `land` | not a lint gate — the two ends of a session. Four PRs unmerged for two weeks; the redesign on one laptop; two branches moving the suite count and git keeping one; CI red on main for a day. `skills/preflight/` and `skills/land/` |
| `tools/sweep.py` | the same, once a day, into one pinned issue: six releases tagged with no CHANGELOG heading, the site at v0.59 while main was at v0.60 |
| import check | `PARENT.startswith()` on a function, at import, so uvicorn never listened |
| `check_requirements.sh` | `uvicorn==0.30.*` pinned against `mcp`, which needs 0.31; the image failed to build on the node |

## Looking at the page

```bash
python3 tools/shots.py                 # docs/design/shots/<fixture>-<view>-<width>.jpg
```

Not a gate and not in `make test`: it needs Chromium, which a node does not have and a household
should never be asked to install. It renders every fixture this node ships, in the Now view and on
the wall, at four widths, and fails on a page error, a component that drew its guard box, a page
that scrolls sideways, or a request the fixture path should not have made. Playwright comes from the
sibling `planetai-design` checkout — `PLANETAI_DESIGN_REPO` points it elsewhere.

There is no node and no database behind it: the fixture is computed exactly as
`GET /issues/fixtures/{name}` computes it, and every request is fulfilled from disk. That includes
the refusals — `/static/{name}` takes a name, so the mono's nested path 404s here as it does on a
node.

## Two habits

**Test the file, not a copy typed into the test.** Three times a test retyped the code it was checking, and the
retyping hid the bug.

**Break something on purpose before trusting a new gate.** A check that has never failed has not been tested.

## Releasing

```bash
PLANETAI_SIGNING_KEY=~/.planetai/release_key tools/release.sh 0.73
# lint + test, tag v0.73, push, then tools/ship.sh: the signed tarball AND the docs site, from the
# same commit, into the site repo, and deploy. Needs a `## v0.73` section in CHANGELOG.md.
```

## Agents

`AGENTS.md` at the root is the operating manual for an AI agent (Claude, Codex, a local model): the MCP surface at
`/mcp`, the `--json` commands, the invariants, the gates. `planetai agent` prints the endpoint, the token and a config
snippet. The MCP server is `app/agent.py`, twenty tools over the existing API; host operations are handed back as
commands because the container has no Docker or git. `app/agent_loop.py` is a local model (Ollama, `qwen3.5:4b` on 8 GB) using
those tools, talking to the household over Telegram; `planetai agent local` sets it up. A bigger model on a laptop or workstation becomes the `remote` rung with
`tools/remote-model.sh gptoss` (llama.cpp, `--jinja` for tool calls, an API key, the tailnet address printed for the
node's `.env`). Tested: gpt-oss-120b answers in about two seconds with correct tool use; the node falls back to its
local model when the laptop is away. The final answer is requested
as constrained JSON because a 4B model narrates its reasoning as prose otherwise.

## Layout

```
app/          main.py (api, loops, notify) · sources.py (adapters) · index.py (cells, ρ) · packs.py · settings.py ·
              bootstrap.py · ask.py (the ask pane) · static/ (the dashboard)
bin/planetai  the operator CLI
packs/        seventeen packs; see PACKS.md
config/       rules.yml (two domain-blind rules), mosquitto, reticulum
tools/        gates, hooks, bundle, release, mesh-provision.sh, nas/ (the NAS puller)
tests/        offline suites
docs/         you are here
```
