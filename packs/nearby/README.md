# nearby

**What it adds** — the ring: other people's air sensors around this node, and the one question a single kit can
never answer. When the air is bad, the thing that changes what a person does is whether it is *them* or
*everywhere*. A fire in the lane means go and look. A haze over the island means close up and wait. The same
reading, two different afternoons.

Three rules. `only_here` (act) when this address is well above a ring that agrees with itself — go outside, use
your nose, and if something is burning, report it. `everywhere` (info) when the ring is high too — there is
nothing nearby to find. `alone` contributes to the report and is never sent: it is the line that says this
reading speaks for this address and nothing else.

**Where it was learned** — Kuta Selatan, Bali, September 2026, against Bali Air Dispatch's 87 stations.

## This node's own kit is not in its own ring

Bali Air Dispatch ingests the Smart Citizen public API, and node #1 polls Smart Citizen directly. The same
physical kit can therefore enter the node twice — once with a week of its own history, once as a station — and
every comparison the ring makes would be the node arguing with itself. On 7 September the archive carried
`sc-19835` "Bayu Kit" at node #1's exact coordinates and `sc-19236` "Ungasan Kit" 1.3 km away. The node calls its
own kits "BAYU NEW ENCLOSURE" and "Ungasan Kit - TEST". Name matching was never an option.

Four rules do it, in `app/sources.py`, and each one catches something the others miss:

| | catches | proved by |
|---|---|---|
| identity | a device this node polls, at any distance | `sc-19236`, 1.3 km away — no distance rule would reach it |
| proximity | anything within `BAD_MIN_SEPARATION_M` of the node | `sc-19835`, 10 m away and **not** on the account this node polls, so identity misses it entirely |
| by hand | `BAD_EXCLUDE`, what the first three missed | — |
| one device, two networks | the same unit republished under a second network's id | 23 AirGradient units mirrored by OpenAQ, one IQAir station mirrored by AQICN |

Ownership is **not** the test. A kit of the operator's at Serangan or Seminyak is a legitimate neighbour. The
test is only whether this node already measures that device.

The fourth rule is about the archive rather than about us. It does not dedupe OpenAQ against AirGradient: 23 of
the 87 stations arrive twice, identical coordinates, identical name. A ring median over those rows weights half
the ring double. Same name *and* within the separation radius is the discriminator — every mirror pair shares a
name, and the three Smart Citizen kits 25 m apart at Kios Utak Atik do not, so collapsing on distance alone would
have deleted real sensors.

`planetai run nearby stations` prints every station in the archive with its distance and one of `included` or
`excluded: <reason>`. Read it once by eye. It comes from the same function the adapter uses, so the audit cannot
drift from what the node stores.

Also dropped by default: `suspected_indoor` (`BAD_INCLUDE_INDOOR=1` keeps them), `suspected_malfunctioning`, and
anything stale. Gaps stay gaps and are never filled.

## The ring at node #1 is thin, and the pack says so

Measured 7 September 2026, after exclusions, from −8.8271 / 115.15709:

| radius | stations | mirrors collapsed |
|---|---|---|
| 5 km | **1** | 0 |
| 10 km | 3 | 1 |
| **15 km (default)** | **6** | 1 |
| 25 km | 19 | 8 |

The nearest neighbour is 3.81 km away. At 5 km there is no ring at all. 15 km is the default because it is the
tightest radius that clears the two-station floor with room to spare and still plausibly describes this address:
25 km reaches Canggu and Pererenan, which is a different airshed and would be this node claiming a scale it did
not measure. When fewer than two stations report, or the nearest is beyond 10 km, `alone` puts that in the report
instead of letting a comparison imply coverage that is not there.

## What it would have said last week

Replayed over node #1's own readings for 2–7 September against its six real neighbours' hourly PM2.5 for the same
days, sampled every sixth hour: **none of the three fired**. The air was clean — the ring's median sat near
8 µg/m³ all week and the node's own outdoor kits between 7 and 9. That is the right answer, and it is pinned in
`tests/test_nearby.py` alongside a case for each rule proving it still fires when the thing it exists for happens.

One threshold was wrong on the first pass and the replay caught it. `only_here` first asked that the ring "agree
with itself" — a p25–p75 spread under 5 µg/m³. Node #1's six neighbours, in clean air, are **9.3 µg/m³** apart
between p25 and p75, because they sit 4 to 15 km apart across the Bukit and south Denpasar and that is what the
air does here. Any fixed gate tight enough to mean agreement would have made the rule dead. It now measures
against the ring's 75th percentile instead: the node has to clear the *top* of the ring by the 10 µg/m³ floor. A
wide ring demands a bigger excursion, a tight one fires sooner, and there is one fewer number to justify.

## What it does not claim

**No cell, deliberately.** `live` means measured here, and the ring is measured by other people through a
third-party aggregation. `Environmental|City` already exists in `packs/air-quality/cells.yml` as `partial`, over
exactly these stations; a second number for the same thing with different provenance is the duplication this pack
exists to refuse. If a cell is wanted later it is a decision for the node's operator, and it lands with the
`Environmental|City` question resolved, not before.

**No channels.yml.** The pack adds no metric. Bali Air Dispatch's channels are declared by the
`bali-air-dispatch` pack, and their roles are right as they stand: `pm25`, `pm10`, `pm1`, `temp` and `humidity` are
`ambient` because that is what they *are* — the air at a place — and `aqi` is `index` because it is a vendor's
composite. The role is not what keeps a neighbour's PM out of this node's ambient pool; `local` is, and every
query that pools ambient joins on it. `verify` checks that no station is ever stored as `local`.

**No adapter.** The fetch is the `bali-air-dispatch` pack's (in `app/sources.py` from v0.11 until the release
after v0.82.3), and this pack's scripts call its `verdicts()`. Adding a second fetch would put every station in the
node twice, which is the same disease as the duplicate kit, one layer up.

## What it assumes

At least two public outdoor stations within `BAD_RADIUS_KM`, and — for `only_here` — a local **outdoor** sensor.
A node whose only kits are indoors has nothing for the ring to be compared against, and `only_here` stays silent
rather than comparing a kitchen to a street.

**Fork it.** The archive is Bali's. Elsewhere the same three rules want an OpenAQ v3 backend behind the same
shape. In Bali, keep using the archive: it applies the EPA/Barkjohn humidity correction to Plantower-class
sensors before publishing, which OpenAQ does not.

## Attribution

Every stored row carries its `source`. Credit both the archive and the network named in the row:
**Bali Air Dispatch, baliairdispatch.com**, and Nafas / IQAir / PurpleAir / AQICN / OpenAQ / AirGradient /
Smart Citizen / Airly as applicable. The archive's code is MIT; the data is not the archive's to licence, and each
row stays under its own network's terms.

## Scripts

```bash
planetai run nearby stations      # every station, its distance, and why it is in or out
planetai run nearby status        # the ring now: who is reporting, how far, how long ago
planetai run nearby verify        # every exclusion fires; nothing external is local; the ring recomputes
planetai run nearby backfill 7    # each station's hourly PM2.5 history. Off by default; asked for, not scheduled.
```
