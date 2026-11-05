# Pack design: what a pack must answer before it is built

**Question.** The `wyze-camera` wild pack was built on 3 October 2026 as a test of the whole path a pack takes:
design, implementation, listing, and how it shows on a node. It works. It logs a room's motion on node #1. And nobody
can see that motion anywhere on the node, nothing can alert on it, and it serves none of the node's issues. What
should a pack answer before it is built? And does the node need something it lacks, so that a pack that keeps its
data private can still be useful?

## What Tomas has said

On 3 October 2026, after the live check on node #1:

- Keep the camera pack at motion only for now.
- It is not clear where motion shows on the dashboard, whether anything alerts on it, or what to do with the data.
- The pack was a test of a new pack's design, its implementation and how it shows in the node, and it should be
  useful later.
- It should inform how packs are designed.

## What the test found

The pack is `packs/wyze-camera` in fabcity/planetai-wild-packs: listed in #5, spec and plan beside it. It reads
docker-wyze-bridge, a separate service that exposes Wyze cameras on the local network.

**1. Private became invisible.** The daily export publishes hourly means for every sensor and every metric, and the
upstream aggregates push every hourly row. Motion stored as readings would publish when a home is occupied. So the
pack returns no sensors and no readings, and writes `out/wyze-camera/motion.jsonl` instead. But every path a pack has
to the page or to the household starts in the database:

| a pack can | it reads |
|---|---|
| add readouts to an issue | a sensor's latest row |
| declare a dashboard section | readout cards, filled the same way |
| raise an alert (`rules.yml`) | SQL over the database |
| fill an Index cell (`cells.yml`) | SQL over the database |

A pack that keeps its data out of the database has none of them. Its data reaches only the pack's own scripts, run
from the node's terminal. The node has no word for data that it keeps, shows and acts on locally but never exports.
Channel roles (`ambient`, `enclosure`, `device_health`, `derived`, `index`) say what a metric *is*, not where it may go.

**2. The pack served no decision.** The node's purpose is clean air, water and soil for the people around it, and ρ
is the share of act-level alerts somebody answered. Motion, on its own, says nothing about either. A version that
would serve them: occupancy combined with the indoor air it already measures, as in "the office is occupied and CO₂
is 1,200 ppm: open a window". The spec answered what stays private in detail. It never asked which issue the data
informs, where it appears, or what it can trigger.

**3. The outside service was most of the work.** On the way to the first live motion event:

- a Wyze account that signs in with Google cannot be used, so the cameras had to be shared to a second account;
- a `$` in a password was eaten by Docker Compose's `.env` parsing;
- macOS's AirPlay Receiver holds port 5000;
- the bridge's defaults derive its API key and web password from the Wyze email, so they are guessable on the LAN;
- Colima's network on a Mac cannot reach the camera's stream, so snapshots do not work there.

Trying to fix the last one took node #1 and four other services on the Mac mini down for about five minutes.

**4. The fakes passed and the live bridge differed.** The bridge reports an unknown camera in a different shape than
its source suggested, and waits up to 15 s for a still where the pack gave up at 10. Both were found only against the
real bridge.

**5. It found two gaps in the core.** A pack's secrets were shown in Set up (#167). Any pack's script could be run by
an admin agent (#168, #169). A wild pack that holds something sensitive is a good probe of the node's trust edges.

## Recommendation

**1. Every pack answers five questions first**, in its README and, where the node can read it, in `pack.yaml`:

| question | the camera pack's answer | where it goes |
|---|---|---|
| Which issue or decision does it inform? | none | README; later a `serves:` field naming issue ids |
| Where does it show on the page? | nowhere | `readouts:`, `sections:` |
| What can alert, and at which level? | nothing | `rules.yml` |
| What stays on this machine, and why? | all of it: occupancy | `secrets:`, the answer to 2 below |
| What outside service does it need, and how is that set up and checked? | docker-wyze-bridge | README, a `status` script |

A pack that answers "none" to the first three may still be listed, but as a tool, not as part of the node's loop,
and its README says so. `docs/PACKS.md` gets the table, and the wild list's pull request template asks it.

**2. The node gets a local-only class of reading.** Three ways, recommended first:

- **(A) A channel role, `private`**, declared in `channels.yml` like the other five. Rows land in `readings` as any
  others do, so readouts, sections, rules and cells work unchanged. They are left out of the daily export, the
  aggregates pushed upstream, `/readings` and `/series` beyond the admin token, the ask pane's context, and the
  agent's read tools. One predicate, written once, as custody is (`2026-09-10-custody.md`). A test asserts that a
  private row never appears in any of those.
- **(B) Pack-owned files plus a local panel.** The pack keeps its own files, as `wyze-camera` does, and the page
  gets a way to draw what a pack's script returns. Nothing enters the database. But every pack invents its own
  storage, and rules and cells cannot see it.
- **(C) Nothing.** A private pack stays a log read from the terminal. That is the honest state today.

(A) is recommended because it reuses everything a pack already has, and it puts the privacy rule in one place the
core tests, not in each pack's discipline. It touches the export, the aggregate push, `/readings`, `/series`,
`app/ask.py` and `app/agent.py`.

**3. A live check is part of listing.** The wild list's `reviewed` status means a maintainer read the pack. It should
also mean the pack ran against its real outside service, on a named node release. The pull request says where and
when, as #5 did.

**4. The core camera feature waits for 2.** The Frigate and CCTV feature (decided core, not designed) has the same
problem in a larger form: events and images from inside homes. It is designed after point 2 is settled, so it
starts with somewhere to put its data.

## What gets harder

- **A private role is a promise the core keeps everywhere.** Every new route, export or tool that reads `readings`
  must honour it. The predicate and its test are what make that checkable. Without them it is a promise nobody can
  check.
- **More pack fields.** `serves:` and `private` are two more things a pack author learns. The table in point 1 is the
  argument that they are the questions a pack author should be asking anyway.
- **Motion in the database is still motion on the disk.** A backup now carries it; today `out/` is not backed up.
  The backup is the household's own, but it should say so.

## What this record does not do

It changes no code. It does not add `serves:`, the `private` role or the live-check rule, and it does not change the
camera pack, which stays at motion only on node #1. It does not design the core camera feature.

Decided: point 2 as (A), the `private` role, by Tomas on 13 October 2026. Its first user is not the camera but the
household inventory (`docs/SPEC_inventory.md`, idle things first), whose rows must never leave the home. Built 13 October 2026 as `role: private` and `packs.public_sql` (see `docs/site/sensors.md`). Points 1, 3
and 4 are not yet decided.
