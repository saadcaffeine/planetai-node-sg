# Reports and messages — handoff

Written 7 September 2026, at the end of Release 1 of three. The design this implements is
`PLANETAI_Reports_and_Messages_Proposal_2026-09-07.md` and the analysis
`PLANETAI_rho_observed_analysis_node1_2026-09-07.md`, both in the PLANETAI project — **neither is on this machine**;
everything below was built from the brief's own summary of them, which was self-sufficient.

## Where it stands

**Release 1 — one clock, the node writes the report: code complete, gates green, NOT TAGGED.**
Branch `reports-and-messages`, in the worktree `../planetai-node-reports`, 18 commits on top of v0.36.
`make lint && make test` green. The one thing missing is §1.12: the clean-VM proof. Do not tag before it.

**Release 2 — the model rewrites under a guardrail: not started.**
**Release 3 — the response layer measured: not started.**

The release is **v0.37**, not v0.36. v0.36 was taken by the dashboard-colours release while this work was in
progress; the code comments and the changelog were corrected, and Release 2 is v0.38, Release 3 v0.39.

## Read this first: three sessions share one repo

While this ran, two other Claude Code sessions were writing the same repository. Between the first read of
`app/main.py` and the second, its working tree went from one modified file to four modified and four untracked, and
`main.py` grew by 21 lines. **This work is in its own git worktree for that reason** — two sessions editing
`app/main.py` would have corrupted both. `main` moved four commits during Release 1 and was merged in (dfeb208).

Before continuing: `git -C ../planetai-node log --oneline -3` and `git merge main` first. Expect conflicts in
`app/main.py`, `bin/planetai`, `Makefile` and `CHANGELOG.md`; the Makefile's `test:` line is the one that always
conflicts, and the resolution is to keep both sessions' test files.

All five `pai-clean*` Lima VMs were in use by those sessions (one was populated 12 minutes before this was written).
Make a new one rather than borrowing theirs.

## What was proven, and how

Everything except §1.12 was proven against something real, not asserted:

- **The scheduler**, against a throwaway Postgres 14 seeded with eight days shaped like node #1 (a kitchen that
  cooks at six, a porch, a public reference, a radio silent for four days, three model points). Seven behaviours:
  not a due hour writes nothing · four calls inside one window write one row · the same hour after a restart writes
  none · quiet hours write-and-hold · the held window folds · two held in a row fold once each, not twice · a node
  off for a week reports 48 hours, not 168. The scripts are in the session scratchpad, not committed — the seed is
  20 lines and `tests/test_report_schedule.py` covers the arithmetic offline.
- **The bundle**, against the same database. JSON-clean end to end (Postgres `numeric` arrives as `Decimal`, which
  is not JSON and stringifies as `Decimal('17')` — `report._num` handles it).
- **The sheet**, offline, in three languages across ten states, with a gate that fails if a phrase exists in one
  language and not another, and one that fails if a phrase is never rendered by any case.
- **The dashboard**, against a live app on the seeded database, at 375 / 768 / 1440. No horizontal overflow at any
  width. Clicking the Report now button found two bugs that reading the code did not: `/report/latest` ordered by
  `due_local`, which is null for a report written on request, so the page went on showing the previous one; and a
  forced report during quiet hours did not end the held stretch, so the night was folded in twice.
- **The update path**, against `update.sh`'s own merge loop on a synthetic v0.33.7 `.env` with `BRIEF_MORNING=7`.
- **Every new gate, broken on purpose once**, including two that passed when broken and had to be rewritten: a
  threshold check satisfied by `"35" in "35.5"`, and a skipped-part check no case could reach.

### What is NOT proven — §1.12, before any tag

```bash
limactl start --name=pai-reports template://ubuntu-24.04    # the other pai-clean* VMs are in use
limactl shell pai-reports
# in the VM, with the Santiago preset and a clock that is not America/Santiago:
#   1. install from this branch, NODE_TZ=America/Santiago, no agent profile
#   2. temporarily set REPORT_ANCHOR to the next local hour; see one report
#   3. docker compose up -d --force-recreate app  inside the same 20 minutes; see no second report
#   4. repeat with COMPOSE_PROFILES=agent and grep every log for a 7 o'clock message: there must be none
#   5. on a second VM at v0.33.7 with BRIEF_MORNING=7: planetai update, then confirm
#      REPORT_EVERY=12 and REPORT_ANCHOR=7 appear once in the log and in `settings`
```

Steps 2, 3 and 5 have equivalents proven at the function level against a real database and against `update.sh`'s
own code; what the VM adds is the container lifecycle and the real `planetai update`.

## Open items

1. **§1.12 and the tag.** Above.
2. **`ALERT_LEVEL` does not move on an updating node.** `update.sh` adds keys a `.env` is missing and never
   overwrites one it has, so the new `act` default reaches fresh installs only. This is correct — nothing a
   household chose changes underneath it — but it means node #1's 13 warn-level messages in 48 hours keep arriving
   until someone runs `planetai report level act`. The changelog, the tester guide and a startup log line all say
   so. If the decision is to move it anyway, that is a one-line addition to `settings.brief_migration`, and it
   should be argued out loud because it contradicts what the same migration promises about BRIEF_*.
3. **`reports.cells`.** §1.3 asks whether each Index cell moved since the previous report, and nothing else on the
   node stores what a cell was six hours ago. That needed one column beyond the schema §1.1 lists:
   `ALTER TABLE reports ADD COLUMN IF NOT EXISTS cells JSONB`, schema 0.23. Additive, idempotent, no secrets.
4. **The `es` and `id` report templates are assistant-written and no native reader has been through them.** They
   are in `report.T` in `app/report.py`, about twenty phrases each. `es` is the first Spanish anything on the node,
   so Vivanco is the reader for it; `id` should go past someone in Bali. `docs/BETA_TESTER_GUIDE.md` says this in
   its Language paragraph and the changelog repeats it. Do not let a release claim otherwise.
5. **`todo_health` embeds an English string in a Spanish sentence.** Part five of the sheet can carry a failing
   health check's `fix`, and those are written for an operator in English (`app/agent.py::health_check`). In `id`
   and `es` the sentence around it is translated and the fix is not. Unavoidable without translating the checks.
6. **The 13:03 event on 7 September is still six alerts.** One pot, three sensors in one room, six act alerts in
   five minutes. Release 3 §3.3. The readings are in the NAS dump.
7. **The NAS dump is not on the dev laptop.** Release 3 §3.8 requires a a one-off backfill script (not written yet) to reproduce the
   analysis doc's table against `bayu-2-2026-09-07.sql.gz`, which lives at
   `/volume2/docker_1/agentic-os/backups/planetai/bayu-2/` on tx-nas-bali. The `nas` MCP server can read it in
   place but cannot move a 1 MB binary onto the laptop; move it by hand before starting §3.8. It is Tomas's own
   house's data and is public-safe, but **do not commit it**.
8. **The pre-commit hook's installed copy is stale.** `tools/hooks/pre-commit` now runs `make test` as well as
   `make lint`. `.git/hooks/` is shared across all worktrees and was left alone so as not to disturb the other
   sessions: `cp tools/hooks/pre-commit .git/hooks/` when they are done.
9. **Node #1 has no shell from this laptop.** Tailscale SSH rejects the user and there is no key. The node is
   readable at `http://100.90.223.47:8081` (it runs on `fabalabbali`, 192.168.4.190 — not on the tailnet machine
   called `bayu-2`, which is the node's *name*). Container logs are therefore unreadable from here; the 48-hour
   send count in the changelog was reconstructed from the node's own `alerts` table plus `run_rules`'s send rule,
   and that is stated in the changelog rather than dressed up as a log count.
10. **`app/__pycache__` will lie to you.** A stale `.pyc` made a deliberately-broken gate appear to pass twice
    during this work. `rm -rf app/__pycache__` before trusting a gate you have just broken on purpose.

## For the heat-pack session

Nothing in `packs/heat/` was touched. Two things concern it:

- Release 3 §3.1 adds `kind: condition` to `heat_stress_now` and `heat_danger` and **nothing else** — no
  `recovery:` key, no threshold change, no cell change. `packs/heat/rules.yml` will gain one line per rule.
- `heat_stress_now` is deliberately absent from `report.THRESHOLDS`, the table the report's part four uses to say
  whether a value came back under its rule's line. It watches an apparent temperature that no column holds, and
  recomputing Steadman in `report.py` would put a copy of the heat pack's maths outside the heat pack. The rule
  therefore gets no sentence in the report rather than a guessed one, until §3.4 gives conditions a real outcome
  (crossing, then a reminder at 30 minutes and at 2 hours, then nothing until the next report).
- `report.THRESHOLDS` carries four air-quality numbers and `tests/test_report_templates.py` refuses any that is not
  in that rule's own SQL — the same check `make lint` gained for pack READMEs in v0.35. If a threshold moves in a
  pack, that gate fails and tells you.

## Do not touch

- `packs/heat/` SQL, thresholds or cells. One key in Release 3, nothing more.
- ρ beyond Release 3 §3.5, the FCI formula, provenance rules.
- `app/static/index.html` and `tools/check_ui.py` beyond what a report needs: the visual-language gates there were
  written by another session from six violations found in front of real households. All of them pass. The Here band
  was added inside them: no hexagon, no gradient, no website-palette hue, no radius of its own, and the report text
  is ink, because a tint would be the page having an opinion about the node's own sentences.
- The per-alert **I did this** buttons in the Act band. The hero's button and the "waiting" state are gone, but
  these are the only remaining door into the actions ledger until §3.6 asks for a note after the evidence. Taking
  them out first would leave `rho_reported` with nothing to record.
- Node #1. Read-only. Every behaviour goes to a VM first, and `planetai update` on the node is Tomas's.

## The next session's first five minutes

```bash
cd "/Users/tomasdiez/Documents/Claude/Projects/FAB CITY/planetai-node-reports"
git log --oneline -1                      # 5039fc4, or later
git merge main                            # the other sessions have moved
make lint && make test                    # both, always
rm -rf app/__pycache__                    # before trusting any gate
```

Release 2 starts at §2.1. Its shape is already in place: `reports.depth` and `reports.rung` are columns,
`REPORT_DEPTH` is a declared setting the dashboard already shows, `report.sheet()` is the fallback and the ruler,
and `bundle()` is capped at 64 kB because that is what the smallest rung can hold. What Release 2 adds is
`POST /render` on the agent container, the per-depth prompts, and `check_numbers()`.
