---
name: write-a-pack
description: Write a pack for somebody's place (a rule, a threshold, an Index cell, a new source), test it on their node, and share it as a wild pack, without forking this repository.
---

# Writing a pack with somebody

A pack is a folder: `pack.yaml`, and any of `rules.yml`, `cells.yml`, `channels.yml`, `adapter.py`, `README.md`.
`docs/PACKS.md` is the contract and the authority; this skill is the order to do it in. The person is the author.
They answer for the thresholds, and the pack stays theirs.

## 1. Decide where it lives before writing a line

A pack for one place is **wild**: it lives in the person's own repository (the repository *is* the pack folder), or
hosted in `fabcity/planetai-wild-packs`, and never as a folder in this repository's `packs/`. Do not fork this
repository to write one. Only a pack useful beyond its place, openly licensed, with offline tests and a maintainer
here who will keep it, comes into `packs/`, and that is a promotion (`docs/decisions/2026-10-01-packs.md`, point 3).

## 2. Start from a core pack of the same kind

A data pack (YAML and SQL only): copy `packs/heat`. A pack that fetches a new source has an `adapter.py` and is a
code pack: start from the core pack whose source looks most like theirs, and read `docs/sensors.md §1`. Then:

- `id:` in `pack.yaml` equals the folder name, and is not the name of a core pack (`ls packs/`).
- `requires: { node: ">=0.76" }` if it uses `readouts:` or `sections:`; an older node ignores both silently.
- A token or key goes in `env:` blank and its name under `secrets:`. Never a value, anywhere.
- A script an agent should be able to run (a `verify`, a `status`) is named under `agent_scripts:`; a wild pack's
  other scripts reach only the node's own terminal.
- Every source it reads is an entry in the registry (`fabcity/awesome-fabcity-data`) and named in `sources:`.
  No entry yet: that repository's `AGENTS.md` says how to file one, as a `candidate`.
- The README says where each threshold came from, which place it was written for, what it does not know, and its
  licence. Thresholds for Kuta Selatan are not thresholds for Barcelona.

## 3. Test it on their node

Put the folder at `packs/<id>` on the node (a git clone there, while developing), then from the node's folder:

```bash
python3 tools/check_rules.py              # rules and cells against the schema, with every other pack
python3 packs/<id>/tests/test_x.py        # its own offline tests, if it has any
planetai restart && planetai packs        # it loads, or says why under "not loaded"
```

A code pack runs only with `PACKS_ALLOW_CODE=1`; ask the person before you set it, because the adapter then runs with
the node's privileges. Watch one pass of the loop (`planetai logs`) before calling it done.

## 4. Share it

Push their repository and take the full 40-character commit. Then follow `fabcity/planetai-wild-packs`'s
`AGENTS.md`: one entry in `packs.json`, `status: listed`, `tested_with` the release you ran it on, and its checks run
locally before the pull request. Another node then installs it with `planetai packs add <owner>/<repo>`. The pull
request comes from the person's account, not yours.

## Never

- Never edit a core pack in `packs/` to suit one place. Write a wild pack beside it.
- Never change a gate to make a pack pass. If a gate is wrong, that is its own pull request here.
- Never mark a pack `reviewed`. A maintainer does, after reading it.
