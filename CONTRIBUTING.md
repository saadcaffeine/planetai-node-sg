# Contributing

Short version: run a node, tell us what broke, send the fix.

## Ways to help

**Run a node and report.** The most useful contribution is `docs/START_HERE.md` failing on your machine. Open an issue
with the "Node problem" template — it asks for the exact three commands we need.

**Write a pack for your place.** A rule, a threshold, an Index cell or a new source is a pack, and a pack for your
place does not come to this repository. Keep it in a repository of your own (the repository *is* the pack folder),
develop it in `packs/<id>` on your node, and list it at
[fabcity/planetai-wild-packs](https://github.com/fabcity/planetai-wild-packs) by pull request so other nodes can add
it with `planetai packs add`. You maintain it. `docs/PACKS.md` is the contract, and
`docs/decisions/2026-10-01-packs.md` is why packs are core or wild. A rule should end in something a person does.

**Change the node itself.** A fix, a core adapter in `app/sources.py` (the contract is at the top of that file and in
`docs/sensors.md §1`), a column `stats` does not have, a scripted dashboard section, or promoting a wild pack into
`packs/` (a pack useful beyond its place, openly licensed, with offline tests in `tests/all` and a maintainer who
keeps it). These are pull requests here. Test a source against a saved payload from the real device, and set `local`
and `indoor` honestly — every rule depends on them.

**Use an agent.** Point Claude Code, Codex, Gemini or Cursor at this repository and it reads `AGENTS.md`
(`CLAUDE.md` and `GEMINI.md` point there). Its routing table sends the agent to the skill for what you are doing,
and `skills/preflight/` and `skills/land/` hold it to the same gates as you. You are still the contributor: the pull
request comes from your account, signed off by you (below), and you answer for what is in it.

## What we won't merge

- Anything that makes a node depend on a cloud service to *function*. Reference data (public APIs) is fine; control planes are not.
- A third container without a trigger written in `SPEC.md §6`. The list of retired pieces exists for a reason.
- Raw readings leaving the node. Hourly means, cells, model updates — yes. Raw — never.
- Rules that fire on indoor sensors as if they were ambient. `NOT s.indoor` is not decoration.

## Before your first commit

```bash
cp tools/hooks/pre-commit .git/hooks/
```

Installs the pre-commit hook: blocks `.env`, credentials and `.git` contents, and runs `make lint` and `make test`. See
[`docs/DEVELOPING.md`](docs/DEVELOPING.md).

## Conventions

- `make lint` must pass. It runs every gate that exists because something once shipped broken — SQL, docs,
  dashboard, wire shapes, registry, pyflakes, the app import — and `docs/DEVELOPING.md` says what each one caught.
- Schema changes go in `init.sql` additively (`IF NOT EXISTS`, and `DROP VIEW IF EXISTS` before every `CREATE VIEW`). A v0.1 node must update in place.
- One dated line in `CHANGELOG.md` per change, saying why.
- Code Apache 2.0, docs CC-BY 4.0. By opening a PR you agree to those terms.
- **Sign off your commits.** `git commit -s` adds one line (tell your agent to use `-s` too):

  ```
  Signed-off-by: Your Name <your@email>
  ```

  That is the [Developer Certificate of Origin](https://developercertificate.org/) — you are saying you
  wrote the change or have the right to contribute it, under the licences above. Not a CLA: nothing is
  assigned to anybody, and there is no form. It exists because this repository already merges code
  three quarters of which carries a `Co-Authored-By` trailer for a model, and the line that says a
  *person* stands behind a commit is worth having written down rather than assumed.

## Who decides

`GOVERNANCE.md` says who merges what and how that list changes; `MAINTAINERS.md` is the list. Most
changes need one maintainer. `init.sql`, `SPEC.md`'s contracts, `install`, `install.sh`, `update.sh`
and `bin/planetai` need two, for one reason: a household updates by running `planetai update` and
cannot review what arrives.

## Voice

Docs are written for the person installing at 9pm with a sensor that just went quiet. Plain words. Say what to do.
No emoji, no hype, no "simply".
