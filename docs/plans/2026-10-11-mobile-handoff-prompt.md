# Hand-off prompt: the phone page, v1 (for Hermes)

Paste everything below the line into a new Hermes session.

---

You are building v1 of the PLANETAI node's phone page: one scrollable page with Now, Place and Node, served when the
dashboard is opened on a phone. The spec is `docs/SPEC_mobile.md` in `planetai-node`. Build §4 to §8 and nothing
from §9 beyond v1. The repo, its `AGENTS.md` and the spec win over this prompt where they disagree.

## Before you touch anything

1. Read `~/Obsidian/Hermes/coordination/planetai/README.md` (the shared protocol) and `STATE.md`, then the newest
   file in `handoffs/`. If someone already holds this work, stop and ask Tomas.
2. **Wait for PR #204.** `gh pr view 204 --repo fabcity/planetai-node --json state,mergeCommit`. Until it is
   `MERGED` and its merge commit is an ancestor of `origin/main` (`git merge-base --is-ancestor <sha> origin/main`;
   a badge that says merged can mean merged into a dead branch), do not start. The phone's Decide card depends on
   its `asking` field.
3. **Claim it** with one line under "In flight" in `STATE.md`:
   `hermes · phone page v1 (docs/SPEC_mobile.md) · mobile-2026-10-11 · planetai-node-mobile · scope: app/static/{mobile.html,mobile.js,doors-load.js,doors.html}, app/main.py (ui() and COMPANIONS only), tests/test_doors.py, tests/visual/{measure.mjs,gate.sh}, docs/site/dashboard.md, CHANGELOG.md · <date>`
4. Make the worktree from the checkout holding `main`, never working in it:
   ```bash
   cd ~/Documents/Claude/Projects/FAB\ CITY/planetai-node-main
   git fetch -q origin
   git worktree add ../planetai-node-mobile -b mobile-2026-10-11 origin/main
   cd ../planetai-node-mobile && tools/session.sh preflight
   ```
5. Read, in the worktree: `AGENTS.md`, `docs/WORKFLOW.md`, `docs/NEXT_RELEASE.md` rules 1 to 4,
   `docs/SPEC_language.md`, `docs/decisions/2026-10-07-doors.md`, `docs/SPEC_mobile.md`, then
   `app/static/doors-load.js`, `doors-now.js` (`readout`, `decision`, the click handler), `doors-core.js` (the boot
   overlay and `refused()`), `doors-place.js`, `doors-node.js`, and `app/main.py` around `_SHARE_OFF` and `ui()`.

## Build

v1 as the spec has it: the rule and the redirect in `doors.html`'s head, `?layout=mobile` in `ui()`, `mobile.html`
and `mobile.js`, `loadD(routes)` in `doors-load.js`, the tests in `tests/test_doors.py` and the `mobile` command in
the visual gate. Outside your scope, write what you find in the handoff's "Found, not touched"; do not fix it.

Traps this repo has already paid for:

- **The page writes no household sentence.** Title, tagline, `plain`, the action and the button labels are the
  wire's, character for character. The page compares nothing against the line and counts nothing.
- **`/settings` is rows** (`describe()`), never a flat map. Read it through `buildD()`'s `setting()`.
- **A check below `sys.exit()` never runs.** `tests/test_doors.py` exits early when `node` is missing. Put the
  shell-route checks above that line, then break one on purpose and watch it fail.
- **The rig must not be kinder than the node.** `measure.mjs` must serve only the names `COMPANIONS` serves, and
  must honour `?layout=` as `ui()` does.
- **The fixture is not node #1.** A capture carries strings where the live node carries other shapes. Node #1 is
  the proof, not the gate.
- **`UI_LAYOUT` is Arrange's JSON.** It does not choose a page; leave it alone.
- **No `packs/` file in this PR** (rule 2), and no change to the suite count in `tests/all` (rule 1).

## Prove it

1. `make lint && make test` before every commit, without `--no-verify`.
2. `bash tests/visual/gate.sh` (about five minutes, Playwright from `../planetai-design`). Green, including the new
   `mobile` command.
3. Open the pull request with a line under `## Unreleased` in `CHANGELOG.md`, the open release milestone
   (`gh api repos/fabcity/planetai-node/milestones --jq '.[].title'`; take the one that is open), and the label
   `needs testing`. Say in the body which release it should ride: one with no pack change, and no other large page
   change.
4. **Node #1 runs the branch before merge** (Tomas's standing rule). Once CI is green: `ssh mini`, switch
   `~/planetai/planetai-node` to `mobile-2026-10-11`, `planetai update` with the brew `PATH` exported
   (`docs/WORKFLOW.md` §2). Then:
   - open node #1 on a real phone, locked and then unlocked with the act token; screenshot Now, Place and Node at
     the phone's own width, in paper and in dark;
   - press one real answer on a live event if one is asking, and check the row in `/actions` and the card's answer
     line;
   - open `/#setup` on the phone and confirm it stays on the doors; press "Full dashboard" and "Phone view";
   - read `planetai logs` for errors.
   Label the PR `tested: node 1` and leave one comment with what you saw and the screenshots. Node #1 goes back to
   `main` after the merge.
5. **Ask Tomas on Telegram before** any merge, tag, release, ship or site deploy. The standing rule covers updating
   node #1 for this PR and nothing else.

## When you stop

`tools/session.sh land`. Write `~/Obsidian/Hermes/coordination/planetai/handoffs/<date>-hermes-phone-page-v1.md`
from `_TEMPLATE.md`, update your line in `STATE.md`, and send Tomas three lines on Telegram: what changed, what he
must decide, and the handoff's path. The spec's three questions go to "Waiting on Tomas" if he has not answered them.
Until he does, build to the spec's defaults: no Telegram link, phones only, the act-token field.

## Acceptance

- [ ] PR #204 is in `origin/main` before the branch was cut; the work is claimed in `STATE.md` with its scope.
- [ ] A phone (coarse pointer, short side under 600 px) opening `/` lands on `/?layout=mobile`; a desk and a tablet
      stay on the doors; `/#setup`, `/#data` and `/#wall` stay on the doors on a phone.
- [ ] "Full dashboard" and "Phone view" switch, and the choice holds on the next visit to `/` in that browser.
- [ ] `?fixture=` and the hash survive the redirect.
- [ ] Now shows the lead issue's title, tagline, numeral with unit and provenance, `plain`, the four distances and
      the other issues as rows; every word and number is a field of the wire.
- [ ] The Decide card shows the live action; its buttons appear only while `asking` is true and the phone holds a
      token; a press posts the same body as `doors-now.js`, with the person's name, and the card then shows the
      wire's answer.
- [ ] Without a token the card says where to answer (Telegram when `message.sent`, or unlock this phone).
- [ ] At `SHARE_LEVEL=off` with no token, Node draws from `/health`, and Now shows the node's 403 sentence and the
      act-token field. Nothing offers the admin token, and nothing writes `/settings`.
- [ ] Place draws the cell, the ground, how far back, one lazy satellite frame, and a link to the map; no request to
      MapLibre, deck.gl, d3, Plot, `/ground/*`, `/geo/*` or `/aggregates`.
- [ ] No horizontal overflow at 320, 360 and 390 px in both registers; every target at least 44 × 44 px; reduced
      motion moves nothing; the boot face paints before any script.
- [ ] The budget in the spec's §7.1 holds in the gate.
- [ ] `make lint && make test` and `tests/visual/gate.sh` green; CI green.
- [ ] CHANGELOG line, milestone, `needs testing`, then `tested: node 1` with phone screenshots in a PR comment.
- [ ] Handoff written, `STATE.md` updated, Tomas told. No merge, release or deploy without his word.
