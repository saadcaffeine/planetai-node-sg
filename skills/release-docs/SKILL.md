---
name: release-docs
description: Bring planetai.fab.city/docs up to the release being cut. Re-read every page of the docs site against the code, fix what changed, and move each page's checked stamp, so the release pull request passes make lint.
---

# The docs site, at every release

`planetai.fab.city/docs` is built from this repository by `tools/ship.sh`, from the same commit as the tarball. So
the site is exactly as current as the pages are. `make lint` holds them to that:

- every page of the site carries one line `<!-- checked: vX -->`, and every `**Gap in vX.**` note names a release;
- both must equal the newest release in `CHANGELOG.md`, its first `## vX` heading.

The release pull request turns `## Unreleased` into `## vX — date — title`. From that commit on, lint fails and
names every page until each has been read again. That is this skill. The pages are `docs/site/*.md` (except
`STYLE.md`) and the `docs/` pages the site's sidebar takes as they are (`tools/build_docs.py` NAV), CHANGELOG aside.

## 1. Know what changed

Read the CHANGELOG entry being released, and `git log --first-parent vPREV..HEAD` for anything it left out. Each
change has a page a reader would look for it on: a pack field on `packs.md`, a command on `cli.md`, a setting on
`configuration.md`, a route on `api.md`, a tool on `mcp.md`. `make lint` already fails when one of those is missing
entirely; it cannot tell when a sentence about it went wrong.

## 2. Read every page against the code

Every page, including the ones nothing in the changelog touches: a page goes stale through changes nobody connected
to it. For each factual claim (commands and flags, settings and defaults, endpoints, counts, thresholds, paths,
version numbers, what a gap note says is missing), open the code that decides it and check. Then:

- a claim that is wrong: fix it, with the smallest edit that makes it true;
- a `**Gap in vPREV.**` note: if the gap is fixed, delete the note; if it is still there, relabel it `vX`;
- a feature on `main` that the release does not carry: it is now in the release, so remove "not in vPREV" notes;
- registry numbers: re-read `data/sources/REGISTRY_VERSION` and recount with `bin/planetai sources`, never by hand.

Then move the page's stamp to `<!-- checked: vX -->`. The stamp says somebody read the page against vX; moving it
without reading is the one way to make the gate lie. The pages are independent, so several agents can take one group
each, as long as each edits only its own files and nobody runs `tools/build_learn.py` until all are done.

## 3. Rebuild and check

```bash
python3 tools/build_learn.py          # the search index and the learn marks are cut from the pages
make lint && make test
```

`build_docs.py --check` in lint fails on a broken link or anchor. Commit the pages, the stamps and
`data/docs_site.json` with the release pull request, before the tag, so the tag holds the docs it ships.
