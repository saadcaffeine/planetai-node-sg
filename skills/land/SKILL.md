---
name: land
description: How a working session on this repository ends — nothing exists only on this machine, the gates are green for real, and a reviewer can find it. Run before closing the laptop, every time.
---

# Land: before the session ends

A session that ends with work in a working tree, on an unpushed branch, or with a green that was
assumed rather than run, has not ended — it has been left. Four PRs sat unmerged for two weeks in
September; thirty-nine commits of the redesign sat on one laptop. This is the checklist that stops
that, and `tools/session.sh land` runs the mechanical half of it.

## Run it

```bash
tools/session.sh land
```

It stops on: uncommitted changes; a branch with no upstream or with unpushed commits; landing from
`main`; the suite count in `tests/all` not matching the list; this branch moving that count while
another open PR moves it too; no PR for the branch; `make lint` or `make test` failing — it runs both,
in full, because that is the point. It warns on: being behind `origin/main`; code changed with no
`CHANGELOG.md` line.

A red `x` is not a suggestion. Fix it and run it again.

## Then, by hand

1. **Merge `origin/main` in if you are behind, and run `land` again.** The PR merges against main as
   it is, not as it was when you branched. A test you ran on Tuesday's main proves nothing about
   Friday's.
2. **The PR body answers the template's questions.** Who wrote it and whether you read every line;
   `make lint` and `make test` on your machine; if you added a gate, that you broke something first
   and watched it fail; how you know it works — what you *ran*, not what should happen. A PR that
   says "it should work" is closed unread.
3. **The CHANGELOG line is for the tester, not for you.** A dated bullet at the top for unreleased
   work; a `## vX.Y — date — title` section when it becomes a release. Six releases went out in
   September without one. `tools/sweep.py` now names them daily.
   Put the PR in the upcoming release's milestone (`gh pr edit <n> --milestone v0.77`), and label it `needs
   testing` if it changes what a node does; `docs/WORKFLOW.md` says what happens after the merge.
4. **If you moved the suite count, say so in the PR**, and say which other PRs must not merge in the
   same hour. Git merges two bumps of that number without a conflict and keeps one.
5. **Write down what you did not finish.** In `docs/NEXT_RELEASE.md` if it is owed, in the PR body
   under "Not fixed here" if it is adjacent. A half-done thing nobody knows about is a thing that will
   be done twice.

## What land does not do

It does not merge. Merging is a decision, and after CI has run — `gh pr checks <n>` — a person
makes it, in the worktree that holds `main`, with `gh pr merge <n> --merge`. If GitHub will not
re-attach a PR to a branch (it happened once, after a branch was deleted and restored), merge locally
into `main` and push; GitHub sees the head commit arrive and marks the PR merged itself.

And it does not ship. `make released` says whether the site is behind; `make ship` fixes it, from the
worktree that holds `main`, after a tag, with the release key. That is a separate decision, and
`docs/NEXT_RELEASE.md` says which changes ship alone.
