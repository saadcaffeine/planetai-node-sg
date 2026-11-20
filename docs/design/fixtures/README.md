# Fixtures

The fixtures a design round renders against live in **`app/issues/fixtures/`**, not here.

They have to be inside `app/`, because `docker-compose.yml` builds the app image with `build: ./app`
— the build context is that directory, so a `COPY` cannot reach up into `docs/`, and `docs/` is not
one of the five paths the compose file mounts either (`config`, `packs`, `out`, `backups`,
`exports`). A fixture under `docs/` would be readable on a dev laptop and absent on every node,
which is the opposite of what a fixture is for.

They are served by the issues router at `/issues/fixtures/<name>`, and the dashboard reads that
route with `?fixture=<name>`. Deliberately not from `/static/`: that prefix is on the
`SHARE_LEVEL=off` allowlist, and a snapshot carries alert texts and sensor names.

Two kinds of file, in two places, and they are not interchangeable.

**A render fixture lives in `app/issues/fixtures/`** and must replay. `engine.Replay` answers the engine's
five queries from five tables — `stats`, `observations`, `alerts`, `actions`, `readings_1h` — and a fixture
missing any of them is refused out loud since v0.67. `tests/test_issues_engine.py` checks every file in that
directory carries all five, so a fixture that cannot render cannot be committed there.

Two of them:

`node1-2026-09-06.json` — node #1 on 6 September 2026 at 14:08 UTC. Hand-assembled: its own `provenance`
block says which parts were read from the API verbatim, which were transcribed off the capture's
screenshot, and which had to be reconstructed. **It is still what the visual gate measures against**,
because `tests/visual/gate.sh`'s `HEIGHT_SHIPPED` and `EMPTY_SHIPPED` numbers were measured from it and a
baseline compared against a different node is not a baseline. Prompt 7 re-measures and moves them.

`node1-2026-09-21.json` — node #1 on 21 September 2026 at 13:56 WITA, running v0.67, and **the first
snapshot `planetai snapshot` has ever produced that replays**. Fourteen endpoints, all five tables the
engine reads: 96 stats, 51 observations, 200 alerts, 31 actions, 2,548 hourly buckets. It replays with a
full act ledger and a real day of series, which is exactly what every snapshot between these two dates
could not do.

**A wire-shape fixture lives beside this README**, in `docs/design/fixtures/`. It is evidence of what the node
answered on a day, read by people and by design sessions on a laptop; it is never served and never rendered,
so it does not need to be inside the build context.

Today: `node1-2026-09-20.json` — node #1 at v0.66, 20 September 2026 at 23:21 WITA. It is the record of the
v0.66 wire: `/sources` at registry pin `85a194c`, the `kind='facility'` row the `make` pack writes, and the
`/settings` row grammar. It was taken before the snapshot tool was fixed, so it carries no `actions` and no
`readings_1h` and cannot replay — which is the reason it is here and not there.

## Making one

`planetai snapshot --out <file>`, on the node. Since v0.67 that fetches fourteen paths and the result replays:
`/actions` was added as a read route, and `readings_1h` is stitched from `/aggregates?hours=24` with `indoor`,
`local` and `kind` joined in from `/sensors`, the same three columns `engine._read` joins from the sensors
table. `/alerts` is asked for 200 rows rather than 50, because that is what the engine itself reads.

Before v0.67 it fetched twelve paths, neither `actions` nor `readings_1h` was among them, and a missing table
read as an empty one — so every snapshot taken between the 06 fixture and v0.67 replayed with no act ledger,
no stages, no series and no barcode, and said nothing about it. That was gap J in
`planetai-design/node-docs/design/PICK_2026-09-20.md`. If you are holding a snapshot from that window, it is a wire-shape fixture
whether or not it was meant to be one.
