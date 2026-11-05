# season

**What it adds** — the other half of `nearby`. That pack asks where the bad air is coming from, right now,
across space: is it this address or the whole area? This one asks across time: is this week worse than the
weeks before it, or is this simply what the air here does? One rule that can reach a household (`turning`),
one that only ever reaches the report (`record`).

A **data pack**: two SQL rules and a script. It fetches nothing. The ring is already in this node's database,
stored every poll by the `bali-air-dispatch` pack (in `app/sources.py` from v0.11 until the release after
v0.82.3), and this reads it back.

## Paired, always

The comparison is per station — each ring station's last 7 days against its own preceding 60 — and the rules
report the median of those differences. Never one island median minus another.

The archive's own growth is why. Measured 16 September 2026 over `/api/v1/measurements?interval=daily`:

| month | stations with usable daily rows |
|---|---|
| Jan 2025 | 2 |
| Jan 2026 | 5 |
| May 2026 | 17 |
| Aug 2026 | 52 |
| Sep 2026 | 79 |

An unpaired comparison over that record measures which networks joined Bali Air Dispatch, not what the air
did. Pairing costs stations — only those present in both windows count — and buys the only difference that is
about the air.

## Where the thresholds came from

Replayed over the archive's daily record, January 2025 to 16 September 2026, on the 177 days where three or
more stations paired:

| | all Bali | within 15 km of node #1 |
|---|---|---|
| paired step, median | +0.6 | +0.6 |
| p90 | +8.2 | +6.3 |
| range | −15.2 … +10.5 | −3.7 … +9.4 |

So **+8 µg/m³** is the top of what that record calls an ordinary week, not a round number. The week itself
must also reach **20 µg/m³**: a step of 8 from 6 to 14 is clean air getting less clean and changes nobody's
afternoon. **Three paired stations** is the floor for saying anything at all.

With those numbers the rule fires on 19 of 177 days all-Bali — some eight episodes, late July 2025, late
April and early June 2026. Replayed day by day over this ring's whole 2026 record in `tests/test_season.py`,
it fires on four days: 31 May to 3 June, when the ring sat above 20 µg/m³ against a baseline near 12. One
episode, and the three-day cooldown makes it one alert. That is what a seasonal rule should cost a household.

**These are Bali's numbers.** They were measured on an island whose dry-season burning is the thing the rule
exists to catch. Somewhere with a heating season, a harvest, or a Saharan dust event will want its own step,
measured the same way against its own record.

## It needs 68 days, and says so when it has not got them

Both rules read 68 days of ring history out of this node. A node installed last month holds less, nothing
pairs, and `record` returns no row rather than a number built on four days. The archive can supply the depth
once:

```bash
planetai run nearby backfill 90     # the ring's hourly history, from baliairdispatch.com
planetai run season window          # every paired station, its week, its baseline, the step
```

`window` prints the table the rules reduce to one number, and runs the `record` rule itself for the summary
line, so the audit cannot drift from the report.

## What it does not claim

**No cell.** Same reason as `nearby`: `live` means measured here, and this is other people's stations through
a third-party archive. `Environmental|City` already exists in `packs/air-quality/cells.yml` as `partial` over
exactly these stations, and a second number for one idea with different provenance is the duplication both
packs exist to refuse.

**No adapter, no new metric, no channels.yml.** It reads `pm25` on sensors the node already stores, so there
is nothing new to declare. A second fetch of the same archive would put every station in the node twice.

**Not a climatology.** "The same days last year" is the comparison a household would ask for first, and the
archive cannot support it: on this window in 2025 it held two stations, one of which still reports. Year over
year needs a record that does not exist yet. The preceding sixty days is what the data can actually carry, and
the rules say "its own last two months", never "normal for this time of year".

**Indoor and malfunctioning stations are already out** — dropped by `app/sources.py` before anything is
stored — and gaps stay gaps: a station with no rows for a week simply has fewer days in its window, and drops
out of the pairing if it falls under 4 in the week or 20 in the baseline.

## Attribution

**Bali Air Dispatch, baliairdispatch.com**, and the network named in each row's `source` — Nafas, IQAir,
PurpleAir, AQICN, OpenAQ, AirGradient, Smart Citizen, Airly. The archive's code is MIT; the measurements stay
under their own networks' terms.

## Scripts

```bash
planetai run season window        # every paired station, its week, its baseline and the step
```
