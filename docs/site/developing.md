# Developing and contributing
<!-- checked: v0.91.0 -->

This page is for the person who changes the node itself: a new adapter, a rule, a pack, a fix. A household updates
by running `planetai update` and cannot review what arrives, so every change here passes the gates, a review and CI
before it merges, and a release is signed before any node gets it.

The repository is [`fabcity/planetai-node`](https://github.com/fabcity/planetai-node). The code is Apache-2.0 today
and moves to AGPL-3.0-or-later once every contributor has consented
([the decision](../../docs/decisions/2026-09-25-licence.md)); the documentation is CC BY 4.0. By opening a pull
request you agree to those terms.

## Ways to help

Run a node and report. The most useful contribution is [Install](install.md) failing on your machine. Open an issue
with the "Node problem" template, which asks for the output of `make health; docker compose ps; docker compose logs
app | tail -50`. Never paste `.env`.

Add a sensor or a source. An adapter is one function returning `(sensors, readings)`, and the contract is on
[Sensors](sensors.md). Test it against a saved payload from the real device before you open a pull request, and set
`local` and `indoor` to what is true, because every rule depends on them.

Write a rule, a cell or a pack: [Packs](packs.md). A pack for one place is a wild pack in its own repository, listed
at [fabcity/planetai-wild-packs](https://github.com/fabcity/planetai-wild-packs), and does not come here as a pull
request. The 25 packs in `packs/` are core, and a wild pack joins them by promotion. Start from a core pack of the
same kind, say in the README where the thresholds come from and which place you wrote for, and make the rule end in
something a person does.

## What will not be merged

Anything that makes a node depend on a cloud service to function: reference data from public APIs is fine, a control
plane is not. A third container without a trigger written in [`SPEC.md`](spec.md) §6. Raw readings leaving the node:
hourly means, cells and model updates may go, raw never. Rules that fire on indoor sensors as if they were ambient,
which is what `NOT s.indoor` in a rule is there to prevent.

## Run a node from your clone

Develop on a machine with git, and keep the node you test on separate from the one a household relies on. The CLI
runs on Apple's Python 3.9 with the standard library only, and nothing runs pip on a node's host; what the app needs
is in its image.

```bash
git clone https://github.com/fabcity/planetai-node && cd planetai-node
./install.sh --name dev --lat -8.8 --lon 115.1     # your own coordinates; no sensor needed
make health
```

The installer runs in the checkout and builds the app image from `app/`. With no sensor the node still fills itself
with 92 days of free global data for its coordinates, so there is something to read as soon as `make health`
answers. After you change the
code, rebuild and restart the app with `docker compose up -d --build app`, and watch it with `make logs`.

## Before you commit

```bash
cp tools/hooks/pre-commit .git/hooks/   # once
make lint
make test
git commit -s
```

The hook refuses a commit that stages `.env`, anything under `.git/`, `backups/` or a `*.before-update` file, a diff
that carries a Telegram bot URL, a `…TOKEN=` or `…API_KEY=` value or a real database password, and `.DS_Store`,
`__pycache__` or `.pyc` files. Then it runs `make lint` and `make test`.

`make lint` runs every gate this repository has: shell syntax, SQL, the CLI's Python 3.9 compatibility, the docs
against the code, the registry, the dashboard, the wire formats, the theme, the vendored libraries, the rules, and an
import of the app. [docs/DEVELOPING.md](../../docs/DEVELOPING.md) says what each gate exists for. Some gates need
extra packages on the dev machine (`pyyaml`; `sqlglot` for the rules; `markdown` for the docs site; the app's
`requirements.txt` for the import check), and a gate whose package is missing says it skipped. CI installs them all,
so nothing skips there.

`make test` runs `tests/all`: 105 offline suites, one line each with a count at the end. It exits non-zero when a
suite fails, when a check skipped that nobody declared, or when the list and the count disagree. A new suite needs
its own line in `tests/all` and the count raised, or it never runs.

`-s` adds the `Signed-off-by:` line of the Developer Certificate of Origin: you are saying you wrote the change or
have the right to contribute it. If an agent writes your commits, tell it to use `-s` too.

Two habits help. Test the file itself, never a copy of the code typed into the test, because the copy hides the bug.
And before you trust a new gate, break something on purpose and watch it fail.

## Open a pull request

Work on your own branch, and in a worktree of your own if you keep several. `tools/session.sh preflight` before you
start tells you where `main` is, how far your branch is from `origin/main`, the open pull requests and whether CI is
green on main. `tools/session.sh land` before you stop runs `make lint` and `make test` in full and stops on
uncommitted or unpushed work.

Give the pull request a line under `## Unreleased` in `CHANGELOG.md`, written for the person running a node: what
changed for them. A pull request that changes what a node runs (`app/`, `bin/`, `packs/`, `config/`, `presets/`,
`init.sql`, the installers, `docker-compose.yml`) fails CI without one; a change that truly needs none carries the
label `no changelog`. Schema changes go in `init.sql` additively, so a node updates in place. A new feature, setting
or command also needs a place a household would look (a Set up row, a line on the page that uses it) and a page or
section here; say in the pull request where both are (AGENTS.md, "Anything new is visible").

Most changes need one maintainer's review. `init.sql`, the contracts in `SPEC.md`, `install`, `install.sh`,
`update.sh` and `bin/planetai` need two, because those are what a household runs without reading. `GOVERNANCE.md`
says who merges what. How a merged change is tested on a node and gathered into a release is in
[docs/WORKFLOW.md](../../docs/WORKFLOW.md).

## What CI checks

| workflow | when | what it runs |
|---|---|---|
| `lint` | every push and pull request | `make lint` and `make test` on Ubuntu with Python 3.12, and the visual gate on macOS (a pull request from a fork gets no secrets, so the visual gate does not run there) |
| `install smoke` | every push and pull request | the install a stranger runs, from a tarball built from this commit: no terminal, no prompt, no `sudo` and no `brew`, and `make health` answers. Then a second run, a removal and a fresh install, on Ubuntu 22.04, Linux Mint, Arch and Debian on arm64 |
| `changelog` | every pull request | a change to what a node runs carries a line under `## Unreleased`, or the `no changelog` label |
| `sweep` | once a day | `tools/sweep.py`, which files what it finds (a release with no CHANGELOG heading, a site behind main) into one pinned issue |

## Looking at the page

`python3 tools/shots.py` renders every fixture in Now, on the Wall and in Network at four widths into
`docs/design/shots/`, with every request answered from disk. It fails on a page error, a component that drew its
guard box, a page that scrolls sideways or a request the fixture should not have made. It needs Chromium from a
sibling `planetai-design` checkout (`PLANETAI_DESIGN_REPO`) and is not a gate. The dashboard's frozen visual language
and the checks against it are in `docs/design/LANGUAGE_GAP.md`.

## This documentation

The pages under `docs/site/`, and the pages of `docs/` and the root that the sidebar lists, are rendered by
`tools/build_docs.py` into `planetai.fab.city/docs`:

```bash
pip install markdown                                   # on the dev machine only
python3 tools/build_docs.py --check                    # what make lint runs: the map, every link, every anchor
make docs                                              # build_learn.py, then build_docs.py --out ../planetai/docs
python3 tools/build_docs.py --single /tmp/docs.html    # everything on one page, for review
```

`docs/site/STYLE.md` is how the pages are written. `make lint` checks what can be checked mechanically: the
commands, settings, paths and endpoints a page names exist, every command, MCP tool, route, setting and `pack.yaml`
field the code has is on its page (`check_docs.py`), every link and anchor lands (`build_docs.py --check`), and the
learn spans are still there.

Whether a sentence is still true is not mechanical. Every page carries `<!-- checked: vX -->`, the release it was
last read against, and lint holds that to the newest release in `CHANGELOG.md`, so a release cannot pass lint until
every page has been read for it (`skills/release-docs/SKILL.md`). A change that alters what a page describes changes
the page in the same commit.

The dashboard's learn mode quotes short spans of some pages, through `app/static/learn.json`. If you move one on
purpose, update `MARKS` in `tools/build_learn.py` in the same change and run `make learn`; `make lint` fails until
the marks and the pages agree.

## Releases

A merge is not a release: a node gets a change only in a signed tarball. Maintainers cut releases with
`tools/release.sh <version>` and the Foundation's signing key (`PLANETAI_SIGNING_KEY`), after the CHANGELOG section is
written, pushed and green in CI. It runs `make lint` and `make test`, tags, pushes, and then `tools/ship.sh` builds
the tarball, signs it with `ssh-keygen -Y sign -n planetai-node`, verifies it against `tools/allowed_signers`,
rebuilds the docs site from the same commit and publishes both. `make released` afterwards says whether the site
serves what is on `main`.

The steps in order are in [docs/WORKFLOW.md](../../docs/WORKFLOW.md), the key and its rotation in
[docs/SIGNING.md](../../docs/SIGNING.md), and what a node checks before it installs an update on
[Sharing and security](sharing.md#signed-updates).

## Layout of the repository

```
app/          main.py (api, loops) · db.py (the pool, q()) · auth.py (tokens, share levels) · channels.py (notify)
              basemap.py · geo.py · machine.py · household.py · presence.py (route groups moved out of main.py)
              sources.py (adapters) · index.py (cells, ρ) · packs.py · settings.py
              registry.py (the source registry) · report.py · agent.py (MCP) · tool_classes.py · agent_loop.py (the bot)
              events.py · events_pg.py · events_wire.py · actions.py (the alert-event engine, its store, its /issues block and
              the action it chooses)
              requires.py (which node a pack needs) · fundamentals.py (the sources every node needs) · learn.py (what it learns)
              ask.py (the dashboard's ask pane) · bootstrap.py · ground.py · issues/ · static/ (the dashboard)
              store.py (how a reading is written) · buttons.py (a rule's buttons) · wild.py (wild packs on Set up)
              firmware.py (the firmware the workbench flashes)
bin/planetai  the operator CLI
packs/        the twenty-five core packs, some with their own routes.py; see Packs
config/       rules.yml (two domain-blind rules, trust's three) · channels.yml · mosquitto · grafana
data/         sources/ (the pinned registry) · strings/ · env_defaults.yml · frozen_layer.txt · platform_floors.yml · mac_ceilings.yml
skills/       setup-node · troubleshoot-node · connect-agent · publish-to-index · preflight · land · write-a-pack
              · release-docs
tools/        the gates, hooks, bundle, ship and release scripts, session.sh, sweep.py, sync_registry.sh, build_docs.py
tests/        offline suites
docs/         the pages; docs/site/ the ones written for this site; design/ the visual language and its reviews
presets/      bali · barcelona · boston · santiago · delhi · menorca
```

A tarball node carries none of `tests/`, `.github/`, `docs/design/`, the `tools/check_*` gates, or the bundle and
release scripts; `tools/bundle.sh` leaves them out.

## Where this leads

The parts a contributor most often adds are [a sensor](sensors.md) and [a pack](packs.md). What a change may send off
the machine is on [Sharing and security](sharing.md).
