# Handoff — `nearby` and `forecast`, v0.40

Written 7–8 September 2026. What was measured, what was decided against the brief, and what is left for Tomas.

## The ring at node #1 is thin, and thinner than we thought

Bali Air Dispatch, 87 stations, measured 7 September from −8.8271 / 115.15709 with every exclusion applied:

| radius | neighbours | mirrors collapsed |
|---|---|---|
| 5 km | **1** | 0 |
| 10 km | 3 | 1 |
| **15 km (shipped default)** | **6** | 1 |
| 25 km | 19 | 8 |

The nearest neighbour is **`sc-19760` "Bayu Sensor by Fab Lab Bali", 3.81 km**. At 5 km there is no ring at all.

`BAD_RADIUS_KM` moved 8 → 15: the tightest radius that clears the two-station floor with room, and still
plausibly this address. 25 km reaches Canggu and Pererenan, a different airshed, and would be the node claiming a
scale it did not measure.

The brief guessed the nearest non-own stations were ~4 km and ~6 km. The real nearest **non-own** station is
`oaq-balangan` at 2.85 km (no current reading, so not in the ring). `sc-*` count is 12, not 7; `ag-*` is 23, not 24.

## The exclusion audit, as it stood on 7 September

Every rule fires on a real station. None needed a crafted case.

```
proximity  1   sc-19835 "Bayu Kit", 10 m from the node   (the brief said 50 m)
identity   2   sc-19236 (1.3 km), sc-19898 (7.1 km) — both polled directly
stale     20
indoor     3   iqs-jimbaran-s, pa-36601, nafas-…
malfunct.  1   iq-kopernik
no /latest 3   oaq-balangan, oaq-kopernik, oaq-ubud_rozendal
mirrors    8 at 25 km, 20 at 50 km
```

**The brief's identity/proximity reasoning is inverted, and both rules are still needed.** `sc-19835` is *not* on
the Smart Citizen account this node polls (`tomasdiez`, 16 kits, none of them 19835), so identity misses it
entirely — proximity catches it at 10 m. Conversely `sc-19236` is 1.3 km away, which no distance rule reaches, and
identity catches it because the node polls it. Keep both.

**The archive does not dedupe OpenAQ.** 23 of the 87 stations are an AirGradient unit and its OpenAQ mirror at
identical coordinates under an identical name, and one is an IQAir station mirrored by AQICN. A ring median over
those rows weights half the ring double. The discriminator is *same name **and** within the separation radius* —
measured, not guessed: every mirror pair shares a name, and the three Smart Citizen kits 25 m apart at Kios Utak
Atik do not, so collapsing on distance alone would have deleted real sensors. **This is worth fixing upstream in
the archive**, and if it is, the node's rule becomes a harmless no-op rather than a wrong one.

## What the rules would have fired last week

Replayed over node #1's own readings for 2–7 September against its six real neighbours' hourly PM2.5 for the same
days, sampled every sixth hour, past-only at each instant:

| rule | matched | would have sent |
|---|---|---|
| `only_here` | 0 / 22 | 0 |
| `everywhere` | 0 / 22 | 0 |
| `alone` | 0 / 22 | — contributes to the report |

Clean air all week: the ring's median sat near 8 µg/m³ and node #1's outdoor kits between 7 and 9. Each rule has a
case proving it still fires when the thing it exists for happens. Both are in `tests/test_nearby.py`.

**One threshold was wrong and the replay caught it.** `only_here` first asked the ring to "agree with itself" — a
p25–p75 spread under 5 µg/m³. Node #1's six neighbours, in clean air with a median of 8.8, are **9.3 µg/m³** apart
between p25 and p75, because they sit 4 to 15 km apart across the Bukit and south Denpasar. Any fixed gate tight
enough to mean agreement would have made the rule dead. It measures against the ring's **p75** instead: clear the
top of the box by the 10 µg/m³ floor, not the middle. A wide ring demands a bigger excursion, a tight one fires
sooner, and there is one fewer number to defend.

## Decisions taken against the brief

**`nearby` ships as a data pack, not a code pack, and has no adapter.** The fetch already existed in
`app/sources.py` since v0.11 — radius, stale-drop, `local: False`, attribution, and the `sc-*` identity dedup —
and `BAD_ENABLED=1` by default. A second adapter would have put every station in the node twice: `bad-sc-19618`
*and* `nearby-sc-19618`, two fetches, two entries in air-quality's `Environmental|City` mean. That is the same
disease as the duplicate kit, one layer up. Tomas chose this shape on 7 September. The missing exclusions went
into the core adapter; the pack is rules, scripts and cards.

Consequence: **there is no `nearby-ring` derived sensor.** A pack adapter gets `fetch(hc)` and no database handle
(`app/packs.py:135`), so it cannot compute a ring from stored rows. The ring numbers are computed on read, in
`/nearby` and in the rules' SQL. Nothing to keep consistent, which is better.

Env names stayed in the `BAD_*` family rather than becoming `NEARBY_*`: one switch per thing. `BAD_MIN_SEPARATION_M`,
`BAD_EXCLUDE`, `BAD_INCLUDE_INDOOR` are new.

**No `origin` column, and no trust commit.** The brief authorised one additive column and a conditional trust fix.
Neither was needed: all three trust rules already gate on `s.local` inside the `seasoned` join, so an external
station cannot reach them whatever its history. `seasoned` landed in `ab65201`. **Backfill is therefore safe** and
`planetai run nearby backfill 7` works; it is off by default only because it is a large fetch against someone
else's server.

**There is no `day` band.** The dashboard's bands are `report · room · street · plan · region · act`; `day` is a
card inside `street`. The forecast card sits beside it there, which also matches the brief's own "home layer" intent.

**`forecast` has three sensors, not one.** `forecast-bmkg`, `forecast-om` and `forecast-gap`. Two sources both on
would collide on `(sensor_id, metric, ts)` under a single `forecast-point`.

## Two bugs found by looking at the rendered page

**`NOT local` is not the ring.** Node #1's own kits sit 1.1 km from its coordinates, so at `LOCAL_RADIUS_M=500`
they are the operator's but not this node's and `local` is FALSE on both. Every ring query scoped by `NOT local`
alone counted them as neighbours — the node comparing itself against its own hardware, the duplicate this pack
exists to refuse, one layer down in the SQL. The ring is now the archive by name. `tests/test_nearby.py` fails
without it, checked by removing it.

**The station card said "5 of 5 reporting" while the numbers said 3**, because the list counted stations the
archive suspects are indoors and the numbers did not.

Neither was reachable from the SQL alone, and `check_ui.py` caught neither — nor `drawRing` being defined inside
`drawDay`'s body, because a function in the wrong scope still parses.

## Gate bugs fixed in passing

Two places extracted a view from `init.sql` with a non-greedy match to the first `;` — and
`-- rolling stats are for sensors only;` sits **inside** the `stats` view. `tests/trustdb.py` got a truncated view
that would not bind; `tools/check_ui.py` would have silently rejected any stats column added below that line. Both
strip line comments first now.

`tools/check_docs.py` read only `app/sources.py` when checking channel declarations, so a pack could never declare
its own channels even though `docs/PACKS.md` tells it to. It reads pack adapters now.

## Left with Tomas

**`Environmental|City`.** It is in `packs/air-quality/cells.yml` (not `earth`, as the brief said), `state: partial`,
computed as `avg(pm25) WHERE NOT s.local` — which has the same flaw the ring had: it averages *any* non-local
sensor, so the operator's own kits beyond `LOCAL_RADIUS_M` are counted as the city. It also averages across
mirrored devices. `nearby` deliberately ships no cell. Two things to decide: whether that cell should be scoped to
the archive the way the ring now is, and whether a ring cell should exist at all. Neither is mine to take.

**Node #1 was unreachable all session** (`100.107.139.69`, a sleeping Mac). Nothing was written to it and nothing
was verified on it. Everything live was verified on `pai-clean5` ("tanjung", −8.8005 / 115.1766, 3 km from node #1).
Node #1 has no local *outdoor* sensor inside `LOCAL_RADIUS_M=500` — its three kits at the address are all indoor,
and the two outdoor ones are 1.1 km away and therefore not `local`. **`only_here` cannot fire on node #1 as
configured.** Either raise `LOCAL_RADIUS_M` to ~1500 or move a kit outside at the address.

**`suspected_malfunctioning` appears in `/latest`** as well as `/stations`, which the brief did not say. Good: the
exclusion works from one call.

## What a node in Barcelona or Santiago needs

`nearby` is Bali-only today because the archive is. The same three rules want an **OpenAQ v3 backend behind the
same shape**: a function returning `(row, verdict)` pairs, and `bad_verdicts()` is already that shape — it takes
rows and returns verdicts, and nothing in it is Bali-specific except the mirror prefixes.

**Bali should keep using the archive rather than OpenAQ directly.** The archive already dedupes OpenAQ against
seven other networks and applies the EPA/Barkjohn humidity correction to Plantower-class sensors before
publishing; OpenAQ does neither. Going direct would lose both and gain nothing.

`forecast` is already portable: BMKG covers Indonesia, Open-Meteo covers everywhere, and the pack idles cleanly
with neither configured. Barcelona and Santiago need `FORECAST_BMKG=0` and `FORECAST_OPENMETEO=1` — and the
non-commercial clause on Open-Meteo's free tier read before that is turned on for anything that earns money.

## The release, and the one step that is yours

It shipped as **v0.41**, not v0.40. `v0.40` was already tagged on 7 September for the trust-pack fix — but the
site was still serving **v0.39**, so that tag had never been pushed and no tester ever received the trust fix.
Both tags are pushed now, and v0.41's tarball carries both.

Done: tag `v0.41` pushed to `main`; `tools/bundle.sh` rebuilt the tarball into `../planetai/node0/get/`; the
tarball, `VERSION` and `SHA256` are committed and pushed in the site repo — the step that was missed last time.

**Not done, because it is yours: `make deploy`.** `https://planetai.fab.city/node0/get/VERSION` still answers
`v0.39`, and `update.sh` downloads from there, so **`planetai update` on a node still fetches v0.39 until you
deploy.** The end-to-end update path is therefore the one thing in this work that has not been run.

What was run instead: the built tarball was unpacked onto a node and started. Schema advanced to 0.23, thirteen
packs load including both new ones, `/nearby` and `/forecast` both answer 200. Its checksum matches `SHA256`.

`tools/bundle.sh` was not executable and `tools/release.sh` calls it directly, so the release stopped after
tagging. Fixed and committed.

## AccuWeather

Not added, and not because of tooling. Its developer terms forbid redistributing the data, cap caching at two
weeks, and require AccuWeather branding wherever it appears. The node exports what it stores and ships its data
with the node. Those cannot both be true. Nothing in either pack needed it.
