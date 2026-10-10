# Developing and contributing
<!-- checked: v0.80.10 -->

This page is for the person who changes the node itself: a new adapter, a rule, a pack, a fix. A change
here reaches every household the next time it runs `planetai update`, and, in the repo's words, "a
household updates by running `planetai update` and cannot review what arrives." So the path from a
commit to a node is gated, signed and published twice, and this page walks it in order.

Short version: run a node, report what broke, send the fix. The repository is
[`fabcity/planetai-node`](https://github.com/fabcity/planetai-node), Apache-2.0 for the code today,
AGPL-3.0-or-later once every contributor has consented ([the decision](../../docs/decisions/2026-09-25-licence.md)),
and CC BY 4.0 for the documentation. By opening a pull request you agree to those terms.

## Two machines

The dev machine has git and pushes. A node runs `planetai update` and never commits. Node #1 is a Mac mini;
its Python is Apple's 3.9 with no third-party libraries, and that is the Python the CLI must run on.
Nothing runs pip on a node's host; what the app needs is in its image.

## Three ways to help

**Run a node and report.** The most useful contribution is [Install](install.md) failing on your machine.
Open an issue with the "Node problem" template. It asks for the output of `make health; docker compose ps;
docker compose logs app | tail -50`. Never `.env`.

**Add a sensor or a source.** An adapter is one function returning `(sensors, readings)`;
[the contract](sensors.md). Test it against a saved payload from the real device before opening a PR. Set
`local` and `indoor` to what is true; every rule depends on them.

**Write a rule, a cell, a pack.** [Packs](packs.md). For one place it is a wild pack in its own repository, listed at
[fabcity/planetai-wild-packs](https://github.com/fabcity/planetai-wild-packs), not a pull request here; the 17 in
`packs/` are core, and a pack joins them by promotion. (v0.76 shipped 18: `xiaomi-air` left core in v0.77 and is now a
wild pack.) Copy `packs/heat`; say in the README where the thresholds came from and which
place you wrote for. A rule should end in something a person does.

## What will not be merged

Anything that makes a node depend on a cloud service to *function*: reference data from public APIs is
fine, control planes are not. A third container without a trigger written in [`SPEC.md`](spec.md) §6. Raw
readings leaving the node: hourly means, cells and model updates may go, raw never. Rules that fire on
indoor sensors as if they were ambient: `NOT s.indoor` is not decoration.

## Starting and ending a session

Most of what has gone wrong on this repository went wrong between two trees, not inside one: a branch
nobody pushed, two branches moving the same count, CI red on main for a day. `make lint` looks at one tree
and cannot see any of that, so a session has two ends of its own:

```bash
tools/session.sh preflight   # before touching anything: read-only, under a minute
tools/session.sh land        # before closing the laptop: runs make lint and make test in full
```

`preflight` says which worktree holds `main`, how far your branch is from `origin/main`, whether
`tests/all` lists as many suites as it asserts, every open PR, whether CI is green on main, whether the site
is behind main, and where the sibling checkouts (`planetai-design`, `awesome-fabcity-data`) stand. `land`
stops on uncommitted changes, unpushed commits, landing from `main`, a suite count that does not match, no
PR for the branch, and a red `make lint` or `make test`. A red `x` from either is a stop. The checklists
behind them are [skills/preflight/SKILL.md](../../skills/preflight/SKILL.md) and
[skills/land/SKILL.md](../../skills/land/SKILL.md).

## Before every commit

```bash
cp tools/hooks/pre-commit .git/hooks/   # once
make lint
make test
git commit -s
```

The hook refuses a commit that stages `.env`, anything under `.git/`, `backups/` or a `*.before-update`
file; a diff that carries a Telegram bot URL, a `…TOKEN=` or `…API_KEY=` value, or a database password
other than the placeholder; and `.DS_Store`, `__pycache__` or `.pyc` files. Then it runs `make lint` and
`make test`, both.

`-s` adds the `Signed-off-by:` line of the Developer Certificate of Origin: a person saying they wrote the
change or have the right to contribute it. Most changes need one maintainer. `init.sql`, the contracts in
`SPEC.md`, `install`, `install.sh`, `update.sh` and `bin/planetai` need two, because those are what a
household runs without reading. `GOVERNANCE.md` says who merges what.

`make lint` is cheap on purpose and runs every gate that exists because something once shipped broken:

| gate | the bug it exists for |
|---|---|
| `bash -n` on every script | shell syntax |
| `check_floors.py`, `gen_floors.py --check`, `render_platforms.py --check` | a platform floor older than 180 days; the Platforms page drifting from `data/platform_floors.yml` |
| `gen_defaults.py --check` | the defaults `GET /settings` reports drifting from `.env.example` |
| `extract_strings.py --check` | the installer's and the preflight's human-readable sentences out of step with `data/strings/en.yml` |
| `check_sql.py` | a comment ate a closing bracket; a missing config Docker replaced with an empty directory; `.DS_Store` committed; `\| grep -q` under pipefail failing a good dump |
| `check_cli_python.py` | f-strings that crashed on Python 3.9; PyYAML the node does not have; a `for` after a semicolon |
| `check_docs.py` | "two containers, five rules" when there were nine adapters and eight packs; links to files that had moved. It reads the root pages, `docs/*.md`, `docs/site/*.md`, pack READMEs and skills. `docs/site/` joined the list after v0.72.1: until then the site could describe v0.57 while the node was at v0.72 and every gate stayed green |
| `check_registry.py` | a pack naming `environmental/city/alphaearth` after the registry filed it as `alphaearth-satellite-embedding`, and a `social/community/openstreetmap` twin that was never filed. Also a hand-edited `data/sources/index.json`, and a pin that stopped half-way through a sync |
| `check_ui.py` | an element id the script referenced that was not in the markup; a network `url()` in a stylesheet; Fab Blue in the dark register; a page that imports h3-js or calls an H3 function, computing a cell the node did not send |
| `build_docs.py --check` | the same fifteen releases, seen as a site: a NAV entry whose source is gone, a page in `docs/site/` that NAV never lists, a link to no page, an `#anchor` to a heading the page does not have. Renders every page and writes nothing. Needs `markdown`; without it the gate says it skipped, and CI installs it so it never skips there |
| `check_site.py` | the programme page eight releases behind the node while every gate in both repos was green. Holds its release, pack and page counts, languages and ρ to this repository, holds the purpose and the lead sentence to `introduction.md`, and fails on a retired word in `docs/site/`. Skipped with a warning where the site repo is not checked out |
| `build_learn.py --check` | a docs edit that moved one of the spans the dashboard's learn mode quotes, so `app/static/learn.json` would quote prose that is gone |
| `check_wire.py` | a top-level key added to or dropped from one of the six wire documents in a commit about something else. The key lists are frozen in `tests/data/wire/` |
| `check_theme.py` | the copy of the design repo's theme drifting on this side, where nothing would say what moved. Holds the three frozen files to the sha256s in `data/frozen_layer.txt`, including in CI, where `planetai-design` is not checked out |
| `shasum -a 256 -c data/vendor.sha256` | a vendored drawing library (`app/static/plot.umd.min.js`, `app/static/d3.min.js`) replaced without anybody deciding to; replacing one means rewriting its line |
| `check_requirements.sh` | `uvicorn` pinned against `mcp`; the image failed to build on the node |
| `check_rules.py` (needs sqlglot) | a 69-day cooldown that made `test-alert` report a dead node; message placeholders the SQL never returned; a cell without a `value` |
| `py_compile`, pyflakes, the import check | `PARENT.startswith()` on a function, at import, so uvicorn never listened |
| only `app` and `agent` get `env_file: .env` | a container that speaks to a public radio mesh holding every secret the node has |
| `.env.example` comment placement; every pack HTTP client has a timeout | a comment after a blank key becoming its value; a client that hangs forever |

`tools/sweep.py` is not a lint gate. It runs once a day in CI and files what it finds into one pinned
issue: six releases tagged with no CHANGELOG heading, the site at v0.59 while main was at v0.60.

`make test` runs `tests/all`: 67 offline suites, one line each with a count at the end, and a non-zero exit
when a suite fails, when a check skipped that nobody declared, or when the list and the count disagree.
Adapters against saved payloads, Meshtastic parsing, cell provenance and custody, code packs, settings,
the issues engine and its geometry, the report templates and schedule, the packs, the registry, the wire
formats, the dashboard and its ask pane, the shell scripts (`preflight`, `remove`, `diagnose`, `sudo` prompting, release
consistency).

Two habits. **Test the file, not a copy typed into the test**: three times a test retyped the code it was
checking, and the retyping hid the bug. **Break something on purpose before trusting a new gate**: a check
that has never failed has not been tested.

## Looking at the page

`python3 tools/shots.py` renders every fixture in Now, on the wall and in Network at four widths into
`docs/design/shots/`, with every request fulfilled from disk, and fails on a page error, a component that
drew its guard box, a page that scrolls sideways or a request the fixture path should not have made. It
needs Chromium from the sibling `planetai-design` checkout (`PLANETAI_DESIGN_REPO`) and is not a gate. The
dashboard's frozen visual language and the checks against it are in `docs/design/LANGUAGE_GAP.md`.

## What goes in one release

How a change gets into a release (a CHANGELOG line, the release milestone, a test on a node that tracks `main`) is
[docs/WORKFLOW.md](../../docs/WORKFLOW.md); CI fails a pull request that changes what a node runs without a line under
`## Unreleased`. [docs/NEXT_RELEASE.md](../../docs/NEXT_RELEASE.md) collects what is owed and holds four rules for the
queue:

1. Only one branch at a time may change the suite count in `tests/all`. Git merges two bumps of that
   number without a conflict and keeps one.
2. `app/static/*` and `packs/*` are merged in separate releases, never the same one, so "was it the page
   or the data" has one answer when a node comes back wrong.
3. One large change per release: the interface or new data sources, not both. Two large changes in one
   hop cannot be bisected by the person who has to report it.
4. Sync the registry, then tag, in that order, every release.

The registry is `data/sources/`, a pinned snapshot of `awesome-fabcity-data`. At v0.80 it is `851b8db`,
269 entries, synced 2026-10-06 (`data/sources/REGISTRY_VERSION`). The script takes a commit sha and
refuses a branch or a tag:

```bash
git -C ../awesome-fabcity-data fetch -q origin
tools/sync_registry.sh "$(git -C ../awesome-fabcity-data rev-parse origin/main)"
```

Commit the diff with a CHANGELOG line, then tag. `check_registry.py` asks whether the snapshot is
consistent, not whether it is current; nothing checks the pin against upstream except a person, and the
doctor's amber row after 180 days.

## Releasing

A merge is not a release, and nothing reaches a tester without one. `install.sh` and `bin/planetai` reach
a node inside the tarball, and the tarball changes only when somebody builds, signs and publishes it.
`tools/release.sh` does all of that in one run.

1. **Write the CHANGELOG section, commit, push, and wait for CI.** `release.sh` refuses a dirty tree, a
   `CHANGELOG.md` with no `## v<version>` section, and a tag that already exists. Push `main` and let the
   `lint` and `install-smoke` workflows finish green before the next step; the Careful note below says
   why. Renaming `## Unreleased` to `## v<version>` makes `make lint` fail on every docs page until each
   has been read again against the code and its `<!-- checked: v<version> -->` stamp moved:
   `skills/release-docs/SKILL.md` is the procedure, and the pages go in the same pull request.

2. **Run the release with the signing key.**

   ```bash
   PLANETAI_SIGNING_KEY=~/.planetai/release_key tools/release.sh 0.72.2
   ```

   Before it tags anything it asks `tools/ship.sh --check-key`, which refuses a key that is missing,
   inside the repository, or not the one `tools/allowed_signers` publishes, and prints `signing key
   present, and it matches tools/allowed_signers` when it is right. Then `tools/ship.sh --check-docs`,
   which refuses a machine where no `python3` has the `markdown` package (`the docs site can be built
   here` when one does). It refuses a site repo (`PLANETAI_SITE_REPO`, default `../planetai`) with
   uncommitted work outside `node0/get` and `docs/`, and refuses to tag while the programme page in it describes another
   release. Then it runs
   `make lint` and `make test`, tags `v0.72.2`, and pushes `main --tags`.

3. **Watch `ship.sh` publish it.** `release.sh` calls `tools/ship.sh` itself. It refuses a commit CI has
   not vouched for, builds the tarball, signs it with `ssh-keygen -Y sign -n planetai-node`, verifies the
   signature against `tools/allowed_signers` as principal `fabcity` (`signed, and the signature verifies
   against tools/allowed_signers`), rebuilds the docs site from the same commit (`docs site rebuilt at
   v0.72.2`), commits both into the site repo in one commit, `node0/get + docs: tester tarball and docs
   site at v0.72.2`, publishes the same
   files as a GitHub Release when `gh` is present (`publishing the GitHub Release v0.72.2`), and deploys
   the site. `release.sh` then checks that `planetai-node.tar.gz`, `SHA256` and the `.sig` are not
   empty, and ends:

   ```
   >> released v0.72.2, signed. Nodes update with:  ./update.sh
   ```

   That is the release. A `make ship` afterwards is redundant.

4. **Check what a tester gets.** `make released` compares `main` with the `VERSION` the site serves and
   prints `a tester gets what is on main`, or exits 1 when the site is behind. `VERSION` is served with
   `max-age=300`, so it reads again for up to 40 seconds before calling the site behind.

> **Careful.** `ship.sh` refuses when no CI run has started for the commit, when a run is still going,
> and when one is red, unless `SHIP_WITHOUT_CI=1`. `release.sh` has already tagged and pushed by then,
> and both workflows run on every push, so the tag's own push can start runs. If the commit was not
> pushed and green before step 2, the script stops with the tag public and nothing published. Wait for
> CI, then run `make ship`: it builds from the tag and publishes it.

The key is the Foundation's and lives outside the repository; [docs/SIGNING.md](../../docs/SIGNING.md)
has where, the command that made it, and the rotation. A passphrase-protected key goes into the agent
first with `ssh-add`. `PLANETAI_UNSIGNED=1` builds a tarball nobody signed, which a node installs only when it is given
`PLANETAI_UNSIGNED=1` too; it is for a throwaway build. `make ship` on its own publishes whatever `main`
is at under its `git describe` name, signed; only a commit that is exactly a tag also gets a GitHub
Release.

What a node checks is on [Sharing and security](sharing.md#signed-updates). The committed `install` stub
fetches `VERSION` only for the line under its logo, downloads the tarball from `PLANETAI_GET` (default
`planetai.fab.city/node0/get`), and checks the checksum and the signature. `PLANETAI_GET` pointed at the
GitHub Release installs from the mirror. The preflight it runs first comes from `raw.githubusercontent.com`
at `PLANETAI_REF`, which defaults to `main`.

Schema changes go in `init.sql` additively. One dated line in `CHANGELOG.md` per change, saying why.

## This documentation

The pages under `docs/site/` and the pages of `docs/` and the root that the sidebar lists are rendered by
`tools/build_docs.py` into `planetai.fab.city/docs`:

```bash
pip install markdown                                   # on the dev machine only
python3 tools/build_docs.py --check                    # what make lint runs: the map, every link, every anchor
make docs                                              # build_learn.py, then build_docs.py --out ../planetai/docs
python3 tools/build_docs.py --single /tmp/docs.html    # everything on one page, for review
make -C ../planetai deploy
```

A release does this on its own: `tools/ship.sh` rebuilds the site from the commit it ships and puts it
in the same site-repo commit as the tarball, so the docs a tester reads describe the node a tester
downloads. `SHIP_WITHOUT_DOCS=1` skips it, deliberately, for an urgent fix on a machine without
`markdown`; `make docs` and a site deploy catch up afterwards.

`make docs` regenerates `app/static/learn.json` before it renders, because `make lint` fails when the
learn marks and the pages disagree. Move a span on purpose and update `MARKS` in `tools/build_learn.py` in
the same change; `make learn` rewrites the file on its own.

`docs/site/STYLE.md` is how the pages are written: plain words, say what to do, only what the code says,
and the conventions the renderer understands. The version and commit in every page's footer are read from
git at build time, which says when the page was built and not what it was read against. What `make
lint` checks is mechanical, in both directions: the commands, settings, paths and endpoints a page names
exist, and every command, MCP tool, route, setting and `pack.yaml` field the code has is on its page
(`check_docs.py`); every link and anchor lands (`build_docs.py --check`); and the learn spans are still spans.
Whether a sentence is still true is not mechanical. So every page carries `<!-- checked: vX -->`, the
release it was last read against, and lint holds that to the newest release in `CHANGELOG.md`: a release
cannot pass lint until every page has been read for it. A change that alters what a page describes changes
the page in the same commit.

## Layout of the repository

```
app/          main.py (api, loops, notify) · sources.py (adapters) · index.py (cells, ρ) · packs.py · settings.py
              registry.py (the source registry) · report.py · agent.py (MCP) · tool_classes.py · agent_loop.py (the bot)
              events.py · events_pg.py · events_wire.py · actions.py (the alert-event engine, its store, its /issues block and
              the action it chooses)
              requires.py (which node a pack needs)
              ask.py (the dashboard's ask pane) · bootstrap.py · ground.py · reticulum_bridge.py · issues/ · static/ (the dashboard)
bin/planetai  the operator CLI
packs/        seventeen core packs; see Packs
config/       rules.yml (two domain-blind rules) · channels.yml · mosquitto · reticulum
data/         sources/ (the pinned registry) · strings/ · env_defaults.yml · frozen_layer.txt · platform_floors.yml · mac_ceilings.yml
skills/       setup-node · troubleshoot-node · connect-agent · publish-to-index · preflight · land · write-a-pack
              · release-docs
tools/        the gates, hooks, bundle, ship and release scripts, session.sh, sweep.py, sync_registry.sh, build_docs.py
tests/        offline suites
docs/         the pages; docs/site/ the ones written for this site; design/ the visual language and its reviews
presets/      bali · barcelona · boston · santiago · delhi · menorca
```

A tarball node carries none of `tests/`, `.github/`, `docs/design/`, the `tools/check_*` gates, or the
bundle and release scripts: `tools/bundle.sh` leaves them out.

## Where this leads

The parts a contributor most often adds are [a sensor](sensors.md) and [a pack](packs.md). What a change
may send off the machine is on [Sharing and security](sharing.md).
