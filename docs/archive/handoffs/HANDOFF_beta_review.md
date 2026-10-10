# Handoff: beta-readiness review, 6 September 2026 (second pass)

For a fresh session that continues this work. The full findings, scores and evidence are in
`docs/archive/reviews/BETA_READINESS_2026-09.md` (statuses updated in this pass); the tester-facing path is
`docs/BETA_TESTER_GUIDE.md`; what changed is the `v0.32` section of `CHANGELOG.md`.

## State

- `fabcity/planetai-node` is **public**; `fabcity/planetai` (the site) is **private**. `main` is the beta channel by
  decision: `/install` fetches it, `planetai update` follows it.
- v0.31 was the review's release. **v0.32** (this pass) closes the review's open items after Tomas decided the three
  questions; **v0.32.1** adds the reinstall guard found while rehearsing it: `git log v0.31..v0.32.1 --oneline`, one
  fix per commit, gates green (`make lint && make test`, run with
  every check enabled on the laptop's miniconda Python: fastapi, sqlglot, pyflakes present).
- The second pass was run from a Cowork session that cannot push to GitHub or reach planetai.fab.city; every commit
  was authored in that session, carried to the laptop checkout (`~/Documents/Claude/Projects/FAB CITY/planetai-node`)
  as a patch (`../_patches/`, disposable), gated there in full, and pushed from the laptop. Behaviour was verified on
  the Lima node `pai-clean` (`~/planetai` inside the VM) by `planetai update` v0.31 → v0.32, not by reading.
- **Spanish** is on branch `es-messages`, PR #1: 23 templates, briefing, test alert, bot lines, presets. Assistant-
  written; waits for Tomas to read it as a native speaker. Not tagged, not on `main`.
- Node #1: ssh `fablabbali@bayu-2` (tailscale name; `tailscale status` on the laptop lists it), node folder
  `~/planetai/planetai-node`, **APP_PORT 8081** (caddy has 8080), Docker via Colima, **v0.30**, schema 0.20,
  **no backup crontab**. Read-only throughout both passes; not updated. `planetai update` there is Tomas's call; the
  v0.32 update recreates the `db` container once (log cap) and applies schema 0.21 (the read-only role).
- Site: mechanical diffs from review §9 applied in the laptop's site checkout and committed with the v0.32 tarball
  (`node0/get/`), **not deployed**: `make deploy` in that repo is a publish and is Tomas's. Narrative changes (cell
  count, ρ 0.67, the legacy agents/hardware block, version stamp, alpha on the front page) are proposed in the
  review's §9, not made.
- Test VMs (Lima, `limactl list`): `pai-clean` (Santiago-shaped node, updated v0.31 → v0.32 → v0.32.1 in this
  pass), `pai-clean2` (restore target), `pai-clean4`–`pai-clean6` (release rehearsals; `pai-clean6` ran the v0.32
  fresh install from the site line in 38 s and the reinstall-over-a-volume refusal). `limactl delete <name>` removes them.

## Decisions made on 6 September, and why

- Release channel: `main`. No tag-following code was written; the tarball at `/node0/get/` is rebuilt by
  `tools/release.sh` and its VERSION must equal the tag.
- Raspberry Pi: dropped for the beta. No arm64 PostGIS image; switching images is a dependency change and node #1
  would need a fresh volume. The site stops promising it.
- LAN and dumps: token on `POST /readings`; `settings` rows out of dumps (dashboard settings do not survive a
  restore; `.env` does); read-only role `planetai_ro` for pack SQL (schema 0.21). `POST /actions` stays open so the
  household's *I did this* works from any phone.
- Spanish: drafted for review rather than left out or handed to Vivanco; presets for Santiago and Barcelona switch
  to `es` in that branch.
- Only what the review found was fixed. One behaviour split (`planetai packs` list vs `packs install`) because the
  listing rebuilt the image; the CLI's own `storage` / `storage set` shape was followed.

## Open findings (not fixed)

Decisions for Tomas
- Cell count to state publicly (6 distinct / 8 rows / "seven" / "4 of 20"); `daily_pulse` still in
  `config/rules.yml`; the heat pack's Social cell reporting 0.0 hours with no indoor sensor (cell SQL).
- Site narrative (review §9.3–9.7, 9.12): legacy agents/hardware block, ρ 0.67, alpha wording on the front page,
  version under the screenshots, `now.jpg` alt text. Proposed as exact diffs there.
- The digest's `{trend}` word comes from SQL in English (rising/falling/steady) in every language; ↑ ↓ → would fix
  all three at once but changes the English text.
- PR #1 (Spanish): merge after reading; then `es` reaches testers on their next `planetai update`.

Serious, code, not done
- Containers run as root; the `reticulum` container receives the whole `.env`.
- Briefings and the dashboard test alert are English-only under `ALERT_LOCALE=id` (the `es` branch gives them a
  locale switch; an `id` set for them needs the lab's native reader, item 1.14 in the tracker).

Polish, not done
- Doctor: log-size and time-sync checks. Contrast and text-only provenance pills on the dashboard (design calls).
  `info@fab.city` not in the Now view's visible text. Open-Meteo requests carry full-precision coordinates and the
  node name in the User-Agent.

## Do not touch

- Node #1: no `update`, `restore`, migrations, `docker compose down`, no writes, until Tomas decides to move it.
- The FCI formula, ρ's definition, cell weights, provenance rules, the data model. Schema 0.21 added a role and
  grants only; no table changed.
- Secrets: never print `.env` values; the VMs' tokens are throwaway and were not pasted anywhere.
- Deletions: `daily_pulse`, unreferenced site screenshots, `_patches/` on the laptop (Tomas's to remove).

## If you continue

1. Ask Tomas to read PR #1 (Spanish); merge; the gate in `tests/test_packs.py` keeps future rules trilingual.
2. If node #1 moves to v0.32: `planetai update` there, then `planetai doctor` shows the missing cron line to add;
   `planetai storage` still shows the read-only backup token the NAS uses (unchanged).
3. Site: `make deploy` in the site checkout publishes the committed footer/alpha/Pi changes and the v0.32.1 tarball;
   then check `https://planetai.fab.city/node0/get/VERSION` reads `v0.32.1`.
4. The narrative diffs in review §9 and the cell-count decision, once Tomas words them.
