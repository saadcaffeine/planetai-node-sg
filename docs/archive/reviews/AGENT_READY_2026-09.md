# Agent-ready: the six live repositories and the Index instruments

**Date:** 2026-09-09
**Scope agreed:** the six live repos (`planetai-node`, `awesome-fabcity-data`, `planetai-coordination`, `city-site-template`, `website-guide`, `things-that-work`) plus the Index surfaces (`index.fab.city`, the Airtable spine, `planetai.fab.city`); archive the eleven dead ones. Reference implementation on `planetai-node`.
**Method:** read all six repos at HEAD; read the current vendor specs (agents.md, llmstxt.org, MCP 2026-07-28, agentskills.io, Cloudflare AI Crawl Control, GitHub PR-limit settings); built and lint-tested the reference.

---

## 1. What we actually have

Better than most. `planetai-node` already has the thing most projects lack: an `AGENTS.md` written with conviction, an MCP server with nineteen tools and an audit header, `--json` on every diagnostic, a `check_docs.py` that fails the build when a doc names a command that does not exist. `awesome-fabcity-data` has a JSON schema, a validator in CI and a generated README. The site repos are plain static HTML with no build step. Nothing here is hostile to an agent.

What is missing is narrower than "agent-readiness": **every agent-facing word we have is written for an agent that is already inside a running node.** The four people who actually show up with an agent are somewhere else:

- the person with no node yet, asking Claude to walk them through the install;
- the person whose sensor went quiet at 9pm, pasting a log into Codex;
- the person who wants their own agent to have the node's tools;
- the pilot partner who wants their cells on the Index and does not know the tier contract.

Their agents open the repo, find nineteen tool names and a set of invariants, and improvise. We have already seen the result: the `contrib/awesome-fabcity-data/bali-air-dispatch.yaml` proposal that cannot merge because it uses Airtable column names instead of the schema. That is what an agent does when the repo tells it *what not to break* but not *where to start*.

The second gap is on the web side. `planetai.fab.city`, `index.fab.city`, `coord.planetai.fab.city`, `ttw.fab.city` and the city subdomains have no `robots.txt` policy toward AI crawlers and no `llms.txt`. Everything is open to training crawlers and nothing is indexed for a person's agent. That is exactly backwards from what you asked for.

## 2. The thesis: one pattern, three roles, and the lint keeps it honest

You want two things that sound opposed: keep bots out, let people's agents in. They are not opposed once you name the distinction the vendors themselves now make. Every major vendor runs **two kinds of fetcher**: a training crawler (`GPTBot`, `ClaudeBot`, `Google-Extended`, `CCBot`, `Bytespider`) and a **user-triggered agent** (`ChatGPT-User`, `Claude-User`, `Google-Agent`, `Perplexity-User`) that fetches one page because a person asked. The first kind honours `robots.txt`; the second kind, by the vendors' own documentation, mostly does not — and that is fine, because the second kind *is* the person. So the policy is simple to state: **block training, welcome the person's agent, and make every write go through an identified human or node.**

On the repo side, the pattern is three files and a folder, and it is the same in every repo:

**`AGENTS.md` is the front door and it routes.** One file, read natively by Codex, Cursor, Copilot and (with a setting) Gemini; `CLAUDE.md` and `GEMINI.md` are one-line pointers to it, since Claude reads only `CLAUDE.md` and Gemini defaults to `GEMINI.md`. Its first section is a table: *the person says X → read this skill → then do this.* Everything the operator-agent needed stays below it.

**`skills/<task>/SKILL.md` are the entry points.** The agentskills.io shape — a folder, frontmatter with `name` and `description`, then instructions — is now read by Claude, Codex, Gemini CLI, Cursor, Copilot and a dozen others. Each skill answers one situation: what to read, what to run, what never to do. They do not duplicate the docs; they order them. A skill that restates `START_HERE.md` will drift from it within a month.

**`llms.txt` is the index for an agent arriving from outside.** One page, every document with one line of description and a raw URL. Be clear-eyed about it: Ahrefs found 97% of `llms.txt` files receive zero requests, Google has said it does not read them, and no vendor fetches them unprompted. They work in exactly one case — when a person points their agent at the repo or domain — which is the case we care about. Cheap to write, cheap to lint, worth it, no more than that.

**The lint gate is what makes this a system instead of a pile of prompts.** `planetai-node` already refuses to build when a document names a command that does not exist. The reference PR extends that to the skills and to `llms.txt`: every skill folder has a well-formed `SKILL.md` whose name is its folder; `AGENTS.md` routes to every skill; every command and path a skill mentions exists; every file `llms.txt` links to exists. Each of those gates was broken on purpose before being trusted, which is the repo's own habit. This is the part to copy first into the other repos — a prompt nobody lints is a doc that rots faster than the docs.

The **PR template** closes the write side: a person is responsible for every pull request, whatever wrote the code; one written with an agent says which, and that the person read every line. An agent-opened PR with nobody behind it is closed unread. Not as a rule about tools — a node runs in somebody's home.

## 3. What was built: the `planetai-node` reference

`AGENTS.md` opens with the routing table. Four skills: **`setup-node`** (preflight → the one line → the four questions → Telegram → `planetai doctor`, with the exit codes read correctly and "never talk them into a machine the preflight refused"); **`troubleshoot-node`** (ask for `planetai doctor --json`, `status --json`, twenty lines of logs — never `.env`, and if a Telegram token appears in a paste, tell them to revoke it; the known-failures table; what an agent may and may not touch, including "a node that is quiet because you raised its threshold is lying"); **`connect-agent`** (the three facts from `planetai agent`, the `claude mcp add` line, the client shapes, `health_check` first, and "the answer is Tailscale, not a port forward"); **`publish-to-index`** (the `fci-cells-v0` row, the tier contract — one node per pilot writes, a home node never does — the dry run, and the honest fact that the writer and the token live with the Index's code and are issued per pilot by you).

Then `llms.txt`, `GEMINI.md`, `.mcp.json` (project-scoped, Claude Code reads it from a clone; URL, token and agent name come from the shell so nothing secret is in the file), a *Bring your own agent* README section with the one paragraph a person pastes to their agent, the PR template, the `check_docs.py` extension, and a `v0.42` changelog entry saying why.

What the reference deliberately does not do: it does not add a `.well-known/mcp` file (the MCP server-card proposal is still a draft, not spec — what clients actually discover is the OAuth resource metadata), it does not register on the MCP registry (a node's endpoint is on a LAN or tailnet; there is nothing public to register), and it does not add a "write a pack" skill yet — `docs/PACKS.md` is good and the pack contributor is the least-frequent of the five arrivals. That is the fifth skill when someone actually asks.

## 4. The Index instruments

The Index has one real ingestion surface and it must stay that way. `index.fab.city/api/cells/{city}.json` is read-only, served by the `cells-worker`, from the Airtable Observations table; the only write path is `cells-ingest`, which refuses to run unless the publisher flag is set and holds a per-pilot write token. That is already the right architecture for "avoid bots, welcome agents": a person's agent can *read* every pilot's cells with a `curl`, and the only thing that can *write* is a City-tier node whose operator you issued a token to. What is missing is that nothing tells an agent this. The `publish-to-index` skill now does, from the node side.

On the Index side, three things, none large. First, an `llms.txt` and a plain `API.md` on `index.fab.city` stating the read contract (`fci-cells-v0`, the four pilot keys, newest-per-cell, CC-BY-4.0, "please cache an hour") — the methodology pages explain the Index to a human; nothing explains the endpoint to an agent. Second, a rate limit on `cells-worker`: the Workers rate-limit binding is one `wrangler.toml` block and the worker is on the free tier's 100k requests/day, which one looping agent could exhaust by lunchtime. Third, move the personal staging fallback out of shipped public code before any agent-facing doc points at that file.

`awesome-fabcity-data` is where agent-written contributions already arrive and already fail. It needs one skill, **`add-source`**: the three-of-three fit test from `CONTRIBUTING.md` restated as questions the agent must ask the person before writing a line (open licence? one pillar × one scale without contortion? who in the network has used or audited it?), the YAML template, the validator as the gate, the README builder, the PR title convention, and the two schema facts that broke the Bali proposal. Plus `AGENTS.md` with the routing table, `CLAUDE.md`/`GEMINI.md` pointers and `llms.txt`. CI is already the lint gate; extend it with the same skill-shape check.

The Airtable spine itself gets no agent surface. Ever. It is production, one hand-edited row is the whole of Barcelona's live data, and the right agent access to it is the worker in front of it.

## 5. Bot policy: three threats, three instruments

**Training crawlers on the fab.city surfaces.** `robots.txt` on every zone we serve, disallowing the training agents by name and adding Cloudflare's Content-Signal line so the policy is machine-readable: index us, let a person's agent read us, do not train on us. It is a request, not a wall — the vendors that matter honour it for training and ignore it for user-triggered fetches, which is the split we want. The wall, where we want one, is Cloudflare's **AI Crawl Control** on the fab.city zone, which categorises Search, Agent and Training traffic and blocks per category; we should set Training to block and Agent to allow explicitly rather than inherit a default.

**Unattended writes.** Three write paths exist and each already has, or now gets, an identity requirement. The Index: the publisher flag plus a per-pilot token you issue by hand — keep it by hand. GitHub PRs: the template's "who wrote this" section, plus the two PR-limit settings GitHub shipped this year. Do **not** restrict issue creation to collaborators: the *Node problem* issue from a stranger's agent is the most valuable input the project gets. The node registry (`registry.json`): a PR, hence a person. Web Bot Auth — HTTP message signatures that let a site verify *which* agent is calling — is now an IETF working group with a first WG draft; watch it, do not build on it yet.

**Load on nodes and Workers.** Nodes: the MCP endpoint is behind the admin token and on a LAN or tailnet; `connect-agent` says so and refuses the port-forward conversation. Workers: the rate-limit binding above on `cells-worker`, and the same on anything else public. The open daily export on a node is a static file; nothing to protect.

## 6. Rollout, with names

Order by where agents already arrive, not by repo importance.

**Week of 9 September — `planetai-node`.** Tomas lands this layer on the dev machine, reads the four skills as if he were Lars, pushes, ships with `make ship` (a merge is not a release). Then the real test: **Lars**, installing node #4, is asked to do it with Claude Code and the README paragraph, and to report where the agent went wrong. That report is the first lessons entry for the skills. Owner: Tomas. Blocking: nothing.

**Week of 16 September — `awesome-fabcity-data` and the Index read side.** Lucas lands `AGENTS.md`, `add-source`, `llms.txt` and the CI extension in `awesome-fabcity-data`; Tomas adds `API.md` + `llms.txt` to `index.fab.city` and the rate-limit binding to `cells-worker`, and removes the staging fallback. `robots.txt` with the Content-Signal line goes on every zone the same day, and AI Crawl Control gets set explicitly. Owner: Lucas (repo), Tomas (Cloudflare, private repos).

**Before Santiago publishes — `publish-to-index` gets its first outside user.** When Vivanco's node reaches City tier, the skill is the onboarding: he runs it with his own agent, and what it fails to tell him becomes the next revision. Owner: Tomas issues the token; Vivanco reports.

**October — the site repos.** `city-site-template` gets the smallest version: an `AGENTS.md` whose one skill is "help a city fill in its city.json and pass the validator". Add `robots.txt` to the template so every forked city site inherits the policy. `website-guide` and `planetai-coordination` get `llms.txt` and the two pointer files only; they are read, not operated. `things-that-work` is the one to think about separately — it is a crisis-response surface and the right agent interface there is a *query* skill rather than a contributor one. Owner: Lucas.

**Same afternoon, any week — archive the eleven.** An agent that finds a 2017 event site and a 2026 node in the same org cannot tell which is current; archiving is how we tell it. Owner: Tomas (org admin).

## 7. Honest risks

The skills will drift. The lint catches commands and paths that stop existing; it cannot catch a fix in the *When it breaks* table that the skill's own table no longer matches. Mitigation is structural: the skills point at the tables instead of copying them where they can, and the one table `troubleshoot-node` does carry is short. When a doc and a skill disagree, `AGENTS.md` says the doc wins and the skill has a bug.

`llms.txt` will be mostly unread. Stated above; do not measure success by its request count.

`publish-to-index` depends on a script in a private repo. Right now that is a feature — the write path stays gated — but it means the skill can only *describe* the last mile. When there are three pilots publishing, the ingest script should probably live in `planetai-node` under `tools/`, still refusing to run without the publisher flag and token. Not yet.

The `.mcp.json` env-expansion default is Claude Code's documented behaviour; Cursor reads its own config file and may not expand defaults the same way. The `connect-agent` skill tells Cursor users to use the snippet `planetai agent` prints instead. If you want one file for every client, drop the defaults and require all three variables.

## 8. First move

Land the layer, then hand Lars the README paragraph and nothing else, and watch what his agent does with it. Everything above is a hypothesis until one stranger's agent has installed a node from it.
