# From a change to a release

How work moves here, written down on 5 October 2026 so that improving things on the spot does not turn into a release
nobody can describe. Four places hold the state, and each has one job:

| where | what it holds |
|---|---|
| a pull request | one change, with its CHANGELOG line, its milestone and its testing label |
| `main` | everything merged: the upcoming release, already running on node #1 |
| the release milestone on GitHub (now `v0.77`) | the list of what the next release carries, and what is still untested |
| `CHANGELOG.md`, `## Unreleased` | the release notes a tester reads, one line per change |

`docs/NEXT_RELEASE.md` stays what it is: the larger work that is owed and the rules for staging it.

## 1. Make the change

A branch in your own worktree, never the checkout that holds `main` (`skills/preflight/SKILL.md`). When it is ready,
open a pull request and give it three things:

- **A line under `## Unreleased` in `CHANGELOG.md`**, written for the person running a node: what changed for them.
  CI fails a pull request that changes what a node runs (`app/`, `bin/`, `packs/`, `config/`, `presets/`,
  `init.sql`, the installers, `docker-compose.yml`) without one. A change that truly needs none carries the label
  `no changelog`.
- **The release milestone**: `gh pr edit <n> --milestone v0.77`. Assign it when the pull request opens, not when the
  release is cut. That is the moment to see whether the release is getting too big or breaks one of
  `docs/NEXT_RELEASE.md`'s rules (one large change per release; the page and the packs in separate releases). Moving
  a pull request to the next milestone before it merges is easy; splitting a release after is not.
- **`needs testing`** if it changes what a node does. Documentation and tooling need no label.

Then `make lint && make test`, and merge with a squash.

## 2. Prove it on a node

Two nodes track `main` and get a merge on their next update. They are the test nodes:

| node | where | how to reach it | update |
|---|---|---|---|
| #1 `bayu-ungasan` | Fab Lab Bali, Mac mini, port 8081 | `ssh mini` | `planetai update` |
| #3 `dieznode` | Tomas's Omarchy laptop, port 8080 (tailnet `omarchy-gmail`) | `ssh omarchy-gmail` | `planetai update` |

```bash
ssh mini 'export PATH="/opt/homebrew/bin:/usr/local/bin:$HOME/.local/bin:$PATH"; cd ~/planetai/planetai-node && planetai update'
ssh omarchy-gmail 'cd ~/planetai && planetai update'
```

Node #3 was a release-tarball install until 5 October 2026; it became a git checkout of `main` that day. Update the
test nodes the day you merge, not on a Friday. A change is **tested** when it has gone through one real cycle of the
thing it changes (an alert, a report, an update, a setting saved) on a node, and the log shows no errors. Then swap
the label to `tested: node 1` or `tested: node 3` (or both), and leave one comment saying what you saw. Node #1 has
sensors in three rooms and Telegram; node #3 has two Xiaomi purifiers and models, no Telegram; a change to a
household message is proven on #1.

## 3. Plan the release

Open the milestone. Cut the release when there is enough in it to be worth a tester's update, or when one change is
needed out there now, and when every pull request in it that changes a node is labelled `tested`. Anything still
`needs testing` either gets tested or moves to the next milestone.

## 4. Cut it

The steps are in `docs/site/developing.md` (Releasing) and `skills/release-docs/SKILL.md`. In order:

1. Sync the registry (`docs/NEXT_RELEASE.md`, rule 4).
2. The release pull request renames `## Unreleased` to `## vX.Y — date — title`. From that commit `make lint` fails
   until every page of the documentation site has been read again for vX.Y and its stamp moved.
3. Merge it, tag, push the tag, wait for CI, then ship with the signing key. Deploying the site is `make deploy` in
   the site repository, and it is Tomas's.
4. Close the milestone and open the next one.

The nodes that take releases, Menorca and any household node, update to it from then on.
