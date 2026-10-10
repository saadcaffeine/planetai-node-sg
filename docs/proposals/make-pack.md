# make — the pack that knows what can be made, and who nearby can make it

**Status:** proposal, v0.47. Nothing here is implemented. The decision to sign is
[`docs/decisions/2026-09-10-make-pack.md`](../decisions/2026-09-10-make-pack.md).

Today an act alert ends at *shut the kitchen windows*. That is the whole response layer: a door, closed by hand.
The node knows the air is bad and it knows what the person should do in the next ten minutes. It does not know
that a box fan and four MERV-13 filters would fix the room in an hour, and it does not know that there is a fab
lab 3.9 km away with a laser cutter and a 3D printer in it. Nothing in the node knows what can be made or who
nearby can make it, because nothing in the node has ever been told.

The Open Hardware Manager knows. It holds **OKH manifests** (a structured description of an open hardware design:
what it is, how to build it, what files exist) and **OKW facilities** (a structured description of a workshop's
capabilities: what processes it can perform, at what quality, and where it is), and **matching** produces a
**supply tree** — a ranked list of the facilities that can build a given design. Its own words, from `CONTEXT.md`;
this proposal uses them and does not invent synonyms.

OHM never runs on a home node. It is FastAPI + Next.js + spaCy in four containers with Redis behind them; the node
is Python 3.9 standard library in two. The pack is a client, over HTTP, to an instance somewhere else. That is a
decision, not debt.

---

## §1 · What the pack does

**In the household's words.** When the node tells you to shut the windows, it can now also tell you what would
actually clear the room, and where the nearest workshop is that could build it. Not a shop and not a price — a
design somebody has already published and tested, and a place with the tools. One extra sentence at the end of
the report: *"A Corsi-Rosenthal Cube would clear this room; Fab Lab Bali, 3.9 km away, has the tools."* You decide
whether to do anything about it. The node will not ask again, it will not chase you, and it does not know whether
you built it.

**At a community node.** The same sentence, at the scale where somebody can act on it. PM2.5 over the threshold
for an hour across the nodes a lab aggregates, and the alert that reaches the lab carries a bilingual advisory
*and* a shortlist of fabricable filters, ranked by which of them the lab's own equipment can actually produce. The
lab approves, or does not. That is the paper's Agent-1 workflow with the missing half filled in: the advisory was
always writable from the readings; the shortlist needed somewhere that knows what a laser cutter is. **The
shortlist is material for stage 2 — the advisory the body reads and approves. It is never stage 3 evidence.**
Nothing was made because the node listed it.

---

## §2 · The rule key

A rule may carry `fabricable:` — a list of OKH ids, or of content hashes, for designs that address the condition
that rule fires on. It is metadata on the rule and it changes nothing about when the rule fires, what it says, or
who it reaches.

On `packs/air-quality/rules.yml`, the act rule where a filter is the actual remedy:

```yaml
- id: indoor_pm25_high
  level: act
  cooldown_minutes: 120
  fabricable:
    # Corsi-Rosenthal_Cube — CC-BY-SA-4.0, Philip Neustrom, encycla.com/Corsi-Rosenthal_Cube.
    # Read from openhardwaremanager.org on 12 September 2026; it is a real record, not a placeholder.
    - 0e42a8e3-e6c7-4017-b8a3-f8117b69c839
    # Portable-Air-Filter-Frame — 3DP frame, PC fans, MERV13, USB power. Same read, same day.
    - 3265e69d-4f7b-4db4-a102-4040937c3a7b
  sql: |
    SELECT sensor_id, name, mean_15m FROM stats
    WHERE local AND indoor AND metric = 'pm25' AND mean_15m > 35.5
  message:
    en: "..."   # unchanged. The shortlist is not in the alert. See §5.
```

Both ids were read from the hosted instance's public `GET /v1/api/okh` listing, which carries 163 manifests; the
first resolves to `Corsi-Rosenthal_Cube`, *"peer-reviewed and fully documented design for air cleaning and
ventilation, which incorporates a box fan with MERV-13 furnace filters"*. No id here is invented and none is a
placeholder.

**Ids or content hashes.** OHM's glossary calls the **content hash** — a SHA-256 of the canonical JSON of an OKH
manifest — the stable, globally unique identity of a design across systems, and that is the right thing for a
`fabricable:` list to carry, because a UUID belongs to one instance and a hash belongs to the design. Today the
hosted instance returns content hashes only on its federation and catalog surfaces (`/api/federation/records/{content_hash}`,
`CatalogRecord`, `Attestation`); a plain `GET /api/okh/{id}` does not carry one. So the key accepts both, the
implementation sends whichever it is given, and a list of UUIDs is what is actually writable in September 2026.
When OHM exposes the hash on the ordinary read, the lists migrate and the key does not change.

**What `tools/check_rules.py` should assert.** It reads every `packs/*/rules.yml` already and today ignores any
key it does not know, so `fabricable:` would pass in silence and typo itself into uselessness. Five assertions,
each of which should be broken on purpose once before it is trusted:

1. **`fabricable:` only on `level: act`.** A shortlist is an errand. On an `info` or `warn` rule it is a suggestion
   nobody asked for, attached to a line that exists to be read and forgotten.
2. **Never together with `contributes:`.** A contributor is never sent (`app/packs.py::alerts`), so a shortlist on
   one reaches nobody — the same failure the existing message/contributes check exists for.
3. **A non-empty list of strings**, each either a UUID in canonical 8-4-4-4-12 hex form or a hex string of 16
   characters or more. Refuse a URL, a title, a bare word, a bare integer. `fabricable: []` is a rule claiming a
   shortlist it does not have.
4. **No duplicates within one rule**, and the key never appears in a `cells.yml` — a cell is a number, and a
   design is not one (§6).
5. **No message template references `{fabricable}`.** The existing placeholder check walks the message for
   `{name}`-shaped holes and asserts the SQL returns each; `fabricable` comes from the rule, not the SQL, so a
   template that reaches for it would fail that check with a confusing error. Refuse it by name, with the reason.

---

## §3 · The setting

```
OHM_URL=        # empty by default
```

Empty means the pack is idle: no outbound request, no stored row, and **the report says nothing** — not "no
workshops found", not "OHM unavailable", nothing. The part-4 clause is simply not appended, which is how `report.py`
already handles a part with nothing to say, and how `nearby` handles a missing ring: its `alone` rule has no
message and is never sent, and `nearby status` prints *"No stations stored yet"* to the operator who asked, not to
the household. An absent source is not news.

| key | group | secret | restart | PUBLIC | default |
|---|---|---|---|---|---|
| `OHM_URL` | `keys` | no | no | **no** | empty |
| `OHM_TOKEN` | `keys` | **yes** | no | no | empty |
| `OHM_COUNTRY` | `keys` | no | no | no | empty |

`OHM_URL` is a `RUNTIME` key in the `keys` group, beside `EE_PROJECT` and `COAST_MAX_KM` — the group for what a
pack needs in order to reach something. It is **not** in `PUBLIC`. It is not a secret, but it names the
organisation whose instance this household is asking, which is the household's business and not a stranger's on
the WiFi; the same reasoning that kept `AGENT_REMOTE_URL` and `TELEGRAM_CHAT_IDS` out of that set on 6 September.

**A token only if the instance asks.** The hosted instance declares an `APIKeyHeader` security scheme on `/api/match`
in its OpenAPI document, and an unauthenticated `POST /v1/api/match` against it on 12 September 2026 **succeeded**
— 200, five ranked solutions. Its private surfaces (`/api/okh/inventory`, `/api/okw/inventory`) answer
`401 {"detail": "Missing authentication token. Expected 'Authorization: Bearer <token>' header"}`. So `OHM_TOKEN`
exists and defaults to empty; when set, the pack sends `Authorization: Bearer <token>` and nothing else changes.
The nearest token pattern in the tree is `AGENT_REMOTE_KEY` / `PARENT_TOKEN`: secret, no restart, no `.env`
echo, never printed by any script, never in a log line. Reuse it exactly.

`OHM_COUNTRY` is an ISO-3166 alpha-2 code for the `network_filter`. Empty means every country, which is honest and
slow; `ID` at node #1.

---

## §4 · The query

### The endpoint

`POST {OHM_URL}/v1/api/match` — *Enhanced Requirements Matching (Domain-Aware)*, from the instance's own
`/v1/docs`. The manufacturing domain is auto-detected from an OKH input; the node does not pass `domain`.
It is the only call the pack makes. `/api/match/facility` is the reverse question (what can this workshop make)
and belongs to a lab, not a node. `/api/okw/spaces` is not needed: the match response already carries each
facility's coordinates.

### What the node sends

```json
{
  "okh_id": "0e42a8e3-e6c7-4017-b8a3-f8117b69c839",
  "location_coords": {"lat": -8.827, "lon": 115.157},
  "max_results": 10,
  "min_confidence": 0.5,
  "network_filter": {"include_mom": true, "country": "ID"}
}
```

**The coordinates are the only thing about this house that leaves, and they leave rounded.** Either the H3
resolution-8 cell centroid this node already computes (`app/ground.py::facts`, `h3.latlng_to_cell(lat, lon, 8)`,
mean edge ≈ 500 m), or `round(lat, 3)` / `round(lon, 3)`, which is 110 m. Not the address, ever. This is the rule
F13 named — *"the node's name and its exact coordinates leave with every outbound request"* — and
`sources.py::openmeteo` is where it was answered: `params={"latitude": round(lat, 3), "longitude": round(lon, 3)}`,
with a `planetai-node` User-Agent that does not carry the node's name. Copy those two lines and that header
verbatim. `/health` rounds to three for the same reason and says so in a comment.

Nothing else about the household is in the request. No readings, no sensor ids, no alert text, no node name, no
`client_info`, no `request_id` that could carry one. `use_llm` stays false (§6).

### What comes back, and the finding that changes the design

Verified against the hosted instance, OHM 0.12.2, 12 September 2026, with the request above:

```
data.solutions[].facility.name                        "Fab Lab Bali"
data.solutions[].facility.location.coordinates        {"lat": -8.7931195, "lon": 115.1501316}
data.solutions[].facility.manufacturing_processes     ["3d_printing", "cnc_machining", ...]
data.solutions[].tree.metadata.okh_title              "Corsi-Rosenthal_Cube"
data.solutions[].confidence, .rank, .score
data.coverage_gaps                                    ["Assembly"]
```

**`location_coords` and `max_distance_km` are accepted and not applied.** The response came back with
`applied_filters: {}` and the list ranked Fablab Jogja, Fastlab UTY, Fab Lab Bali, Fablab Bandung, HONFablab — in
that order, all at confidence 1.0, with the nearest one third in the list and Bandung (≈950 km) fourth. The
server does not sort by distance today. **So the node sorts.** It has `sources.km` already; the facility
coordinates are in the response; the nearest is the one the report names. This is one line of Python and it means
the pack does not depend on a server-side filter that is currently inert.

Two more things that response says out loud and the pack should not paper over: `coverage_gaps: ["Assembly"]` with
`coverage_ratio: 0.0`, and `equipment_count: 0` on every facility. The Maps of Making records carry processes but
no equipment, so the match is a process-level claim, not a proven capability. **The pack stores the confidence and
the coverage ratio and the report never says "can build it" — it says the design, the place, and the distance.**

### What is stored

**One `sensors` row per design, `kind = 'external'`, with no readings at all.** Not a new table.

```
sensor_id   ohm-0e42a8e3-e6c7-4017-b8a3-f8117b69c839
source      ohm
name        Corsi-Rosenthal_Cube
kind        external
local       false
indoor      false
lat / lon   the facility's, not the node's
meta        {okh_id, okh_title, licence, facility_name, facility_id, facility_km,
             facility_processes, confidence, coverage_ratio, ohm_url, fetched_at, attribution}
```

Why this and not a table: the diff is **one comment line in `init.sql`** — `kind` is a free-text column with a
comment listing `sensor | portal | model | survey | child`, and `external` joins that list the way `peer` is
joining it in the custody work. A new table is a `CREATE TABLE`, an idempotency gate, a migration, a place for
`app/main.py` to expose it, and a second thing to back up. And the row is the cache: `sensors` is upserted by the
existing adapter contract `fetch(hc) -> (sensors, readings)`, it survives a restart, and it survives the internet
going away, which is the whole requirement. `meta.fetched_at` is the TTL clock and the report prints nothing
newer-sounding than it.

It reaches nothing else, and that is checkable rather than hoped for: `stats` selects `WHERE s.kind = 'sensor'`,
so the row is not in any rolling mean; the `observations` view joins `readings`, and this row has none, so it is
not an observation either; it is never `local`, so no ambient pool and no cell can see it. `nearby`'s verify has
the same assertion for its stations — *nothing external is local* — and this pack's verify should copy it.

**The honest objection**, recorded rather than argued away: the table is called `sensors` and a design is not a
sensor. It already holds portals and models, which are not sensors either — the column says how a number was
produced, and this row produces no number. If that reads wrong to Tomas in review, a `fabricable` table is four
columns and half a day, and nothing above §4 changes.

### Cache, TTL, cadence

```
OHM_POLL_HOURS=24      # a workshop does not move
OHM_TTL_HOURS=168      # a week; after that the row is stale, not wrong
```

The pack polls once a day, per distinct OKH id across every enabled rule's `fabricable:` list — at node #1 that is
two ids, so two requests a day. On any failure it logs once and returns nothing, and the previous row stands: a
pack that needs a service must never take the node down (`docs/PACKS.md`). Past `OHM_TTL_HOURS` the row is kept
and the report stops quoting it, because a filter that was near you last week probably still is, but the node
should not assert it as current. That is the same shape as `forecast`'s `FORECAST_POLL_HOURS=6` against a source
that publishes twice a day: do not ask a cache the same question.

---

## §5 · The report line and the dashboard

**The report.** Part 4 of `report.sheet()` is *what happened after this window's alerts*. It walks the act-level
alerts in the bundle and, for each one whose rule is in `report.THRESHOLDS`, says whether the value came back
under its line. It gains **one clause, on an act alert whose rule carries `fabricable:`, and only when a fresh
match row exists**:

> Inside at the kitchen is back under 35. A Corsi-Rosenthal Cube would clear it faster; Fab Lab Bali, 3.9 km, has
> the tools.

One clause, one design, one facility — the nearest by the node's own arithmetic. Never a list: the report is
under a hundred words in three languages and a shortlist in it is a catalogue. If two act alerts both carry
`fabricable:`, the same cap that already stops part 4 at two outcomes applies, and the clause is appended once.
It is not in the alert. An alert is what to do in the next ten minutes and building a box fan filter is not that.

**The dashboard.** Beside the ring, in the card row that already holds *"You against your neighbours."* — the
nearby pack's card, whose provenance pill reads `external` today, ink only, no colour, `<span class="prov">` with
the ring glyph. The make card takes the same pill and the same word, because it is the same kind of claim: an
outside source informing what the node says, never becoming the node's own measurement. Design name, facility
name, distance, and the fetch date. Nothing coloured, no verdict, no hexagon of its own — `tools/check_ui.py`
refuses a provenance pill that carries a role colour, and it is right to.

**Nothing at wall mode in v0.** The wall is the kiosk view: one number across a room, one verdict sentence, three
stats, read by whoever walks past. A fabricable clause there is an errand addressed to nobody in particular, on a
screen with no way to act on it, in a view that exists to say how the place is right now. When the wall has a
reason to carry an errand it will be because somebody asked for one; it has not.

---

## §6 · What it never does

- **No cell.** Not `Economic|Community`, not anything. The ring refused a cell for exactly this reason and wrote
  it down: a second number for an idea that already has one, with different provenance, is duplication. A count of
  nearby workshops is a fact about Maps of Making's coverage, not a measurement of this place. **No second
  Economic cell source without a registry row** — the Index's Economic column has one source of record and a pack
  does not get to add a second by arriving with an API.
- **No `deployed_at`.** At household tier the pack advises and stops. Whether anything was made is not something
  the node can see, and a field it cannot fill honestly is a field that fills itself with guesses. At community
  tier, stage 3 of the funnel is written **by the body** — the lab, the banjar, the school — with an OHM RFQ or
  asset id as `evidence_ref`. That is v0.48 and it is not this pack. What this pack produces is stage 2 material:
  a shortlist attached to an advisory, which is a thing to approve, not a thing that happened.
- **No LLM call from the node to OHM's generation endpoint.** `/api/okh/generate-from-url` and `use_llm: true` on
  `/api/match` both run a language model on somebody's account, for money, on text the node supplies. The node's
  own rule is that exactly one setting lets household data leave the network and the person chooses it
  (`AGENT_ONLINE_KEY`). The pack sends `use_llm` false, or omits it, and never touches the generation endpoints.
- **No OKW export from the node.** The node is not a facility. It has no equipment, no processes, no opening
  hours and no staff, and publishing an OKW record for a house would put a household's address in a directory of
  workshops. `/api/okw/create` and `/api/okw/upload` are not in this pack's vocabulary. A lab may publish itself
  (§7); a node never publishes anything about itself here.
- **No peer or external row in a cell, ever.** Already an invariant; restated because this pack adds the first
  external rows that are about people rather than about air.

---

## §7 · Fab Lab Bali, first facility and first host

Fab Lab Bali is **already in the network surface OHM matches against**, via Maps of Making:

```
GET /v1/api/okw/spaces?include_mom=true&country=ID
  id        urn:mak:space/fab-lab-bali-badung
  name      Fab Lab Bali
  lat/lon   -8.7931195, 115.1501316          → 3.86 km from node #1
  city      Badung        country  ID        source  mom
  processes 3d_printing, cnc_machining, electronics_assembly,
            laser_cutting, vinyl_cutting, cnc_milling
  url       https://fablabbali.com/
```

It is also in the `/api/match` result for the Corsi-Rosenthal Cube, at confidence 1.0 — third in the server's
order, first once the node sorts by distance. So the pack has a real answer at node #1 on day one, before anybody
writes a single record.

### What an OKW record for it contains

From the instance's own `GET /v1/api/okw/template`, filled with what the fablabs.io entry (lab `2755`, slug
`fablabbali`) and Maps of Making actually hold. Nothing below is invented:

| OKW field | value | from |
|---|---|---|
| `name` | Fab Lab Bali | fablabs.io |
| `location.address` | J-Loft 2C, Jimbaran HUB, Jl. Karang Mas, Jimbaran, Kuta Selatan · Badung · Bali · 80361 · ID | fablabs.io |
| `location.gps_coordinates` | −8.7931195, 115.1501316 | fablabs.io / MoM |
| `facility_status` | Active | fablabs.io `activity_status: active` |
| `contact.email` / `.mobile` | fablabbali@gmail.com · +628119119066 | fablabs.io |
| `owner` / `affiliations` | Meaningful Design Group; Jimbaran Hijau; Fab City Foundation | fablabs.io description |
| `description` | the fablabs.io blurb, verbatim | fablabs.io |
| `manufacturing_processes` | 3D printing · CNC milling · circuit production · laser · precision milling · vinyl cutting | fablabs.io `capabilities` |
| `innovation_space.services` | — | not recorded anywhere |

**Empty, and staying empty until somebody at the lab fills them in:** `equipment` (make, model, serial, per
machine — the field that would turn a process claim into a capability claim, and the reason `equipment_count: 0`
appears in every match today), `typical_materials`, `typical_batch_size`, `typical_products`, `opening_hours`,
`access_type`, `human_capacity.headcount`, `floor_size`, `storage_capacity`, `certifications`,
`circular_economy`, `wheelchair_accessibility`, `date_founded`, `maintenance_schedule`, `partners_funders`.
The fablabs.io `capabilities` list is six coarse words; an OKW `equipment` array is the specific machines.
Do not synthesise the second from the first.

### The two steps

**One — the hosted instance.** `OHM_URL=https://www.openhardwaremanager.org` on node #1, pointed at the public
catalog, matching against Maps of Making. No hosting, no token today, no operational cost, and the first real
report clause at node #1 within a day. This is the step that proves the sentence is worth having before anyone
runs a container for it.

**Two — the lab's own instance, on the tailnet.** Fab Lab Bali runs OHM itself, on one machine: four containers
(`ohm-frontend`, `ohm-api`, `ohm-worker`, `redis`), `docker compose up`, images published for `linux/arm64` as
well as amd64, so a Pi-class or Apple-silicon box is enough. In `production` mode it refuses to start without
`OHM_ENCRYPTION_SALT` and `OHM_ENCRYPTION_PASSWORD`. **`OHM_FEDERATION_ENABLED` stays false** — the default; a
fresh instance talks to nobody, follows nobody and syncs from nobody, and that is the correct posture for an
instance holding a lab's real equipment list. The nodes reach it over Tailscale at `http://<lab-host>:8080`,
never a port forward, the same answer `connect-agent` gives. Then the lab's own OKW record is the one being
matched against, with its equipment in it, and the confidence scores start meaning something.

---

## §8 · things-that-work

Things That Work is a library of responses. Its masthead counts 1,524 open-hardware designs inside 1,594 entries,
and it has never answered the question that follows every one of them: who near me can actually make this. The
mechanism is one field. **A TTW entry carries an `okh` key holding an OKH id or content hash** — the same identity
the `fabricable:` rule key carries, pointing at the same record in the same instance. For the entries that already
cite OSHWA or Field Ready, this is transcription, not authorship; for the rest it is the per-entry normalisation
work the OHM evaluation already named as the real cost. It is a field on a record, not a schema change to the
site: entries without it behave exactly as they do now, and the ~70 entries that are techniques rather than
manufacturable things — the zeer pot, bleach dosing — never get one, and should not.

With that field in place, the TTW query skill from the agent-ready plan stops being a separate thing to design.
That plan says things-that-work is a crisis-response surface whose right agent interface is a *query* skill rather
than a contributor one; the query it needs to answer is *what should I make, and who near me can make it*. The
first half TTW already answers. The second half is `POST /v1/api/match` with the entry's OKH id and the asker's
coordinates — the identical call this pack makes, from a Worker proxy instead of a node container, with the key
held server-side because a bearer token cannot live in a browser. So the skill is a skin over this query, and the
node pack is the same skin over the same query with a different face on it: one record, one identity, one
endpoint, two surfaces. Whichever of the two is built first, the second is configuration.

---

## §9 · The gate for v0.47

One test. A rule carrying `fabricable:`, `OHM_URL` pointed at a stub that returns a fixture match — the real
12 September response for the Corsi-Rosenthal Cube against `country=ID`, trimmed and saved to
`tests/fixtures/ohm_match.json` — and the node run against it end to end. Do not write the test file here; these
are its assertions.

**The report clause appears.**
1. `report.sheet(bundle)` contains the design's title *and* the facility's name *and* a distance, in one sentence
   in part 4, for an act alert whose rule carries `fabricable:`.
2. The distance the clause prints equals `sources.km(node_lat, node_lon, facility_lat, facility_lon)` rounded to
   one decimal — computed by the node, not taken from the response, which carries no distance.
3. The facility named is the **nearest** of the fixture's five, not the first: the fixture's server order puts
   Fab Lab Bali third. This assertion is the one that fails if anybody later trusts the server's ranking.
4. The same bundle with `OHM_URL` empty renders a report with **no** part-4 clause, byte-identical to the report
   before the pack existed — and with `OHM_URL` set but the stub returning 500, likewise, plus exactly one log line.
5. A row older than `OHM_TTL_HOURS` produces no clause and is not deleted.

**The hero shows it as external.**
6. The card's provenance element renders the literal word `external` and no other provenance word.
7. `tools/check_ui.py` passes: the pill carries no `#hex`, no `rgb(`, and none of `--red --green --blue --orange`,
   inline or in a rule.
8. The wall view's markup contains no design name, no facility name and no `fabricable` string.

**No cell changed.**
9. `GET /cells` before and after the poll are equal, key for key and `state` for `state`.
10. No `cells.yml` in the tree contains the string `fabricable`, and no cell SQL reads a row where `kind = 'external'`.
11. The stored row has `local = false` and `indoor = false`, and `SELECT count(*) FROM stats WHERE sensor_id LIKE 'ohm-%'`
    is 0 — it is not in any rolling mean.

**No `deployed_at` written.**
12. The string `deployed_at` appears nowhere in the pack, and the `actions` ledger row count is unchanged across
    the whole run. The pack writes no action and closes no loop.

**The outgoing request is clean.**
13. The captured request body's `location_coords.lat` and `.lon` each have **at most 3 decimal places** — asserted
    on the serialised JSON, not on the float, because `round(-8.8271, 3)` serialises as `-8.827` and a formatting
    slip is exactly how five decimals come back.
14. The body contains no sensor id, no reading, no alert text, no `NODE_NAME`, and `use_llm` is absent or false.
15. The `User-Agent` header is `planetai-node` with no version and no node name — the F13 fix, asserted here so
    the pack cannot reintroduce what `sources.py` had to have removed.

---

## Sources read

`AGENTS.md` · `packs/nearby/` in full · `app/sources.py::openmeteo` and `::_adapters` · `app/report.py::sheet` ·
`app/settings.py` · `app/ground.py` · `app/packs.py` · `tools/check_rules.py` · `tools/check_ui.py` ·
`docs/PACKS.md` · `docs/archive/reviews/CODE_REVIEW_2026-09.md` §F13 · `docs/archive/reviews/CODE_REVIEW_2026-09-10_second_pass.md`
§A12 · `skills/publish-to-index/SKILL.md` (the tier contract) · `PRODUCT.md` (the tier table) ·
`docs/archive/reviews/AGENT_READY_2026-09.md` (the TTW query skill) · `ttw-redesign/OHM_API_Integration_Eval.md`.

OHM, read live on 12 September 2026: `README.md`, `CONTEXT.md`, `docs-site/docs/guides/run-your-own-node.md`,
`/v1/openapi.json` and `/v1/docs` on the hosted instance (version 0.12.2), `GET /v1/api/okh`,
`GET /v1/api/okw/template`, `GET /v1/api/okw/spaces`, and one live `POST /v1/api/match`.

**Two documents this proposal could not read**, named here rather than guessed at: the funnel briefing (its stage 3
row and tier table) and decision 11. Neither is on this machine — `HANDOFF_reports.md` records the same absence for
`PLANETAI_Reports_and_Messages_Proposal_2026-09-07.md`, which is where Release 3 and ρ live. The funnel's stages
are used here as the brief states them (a shortlist is stage 2 material, stage 3 is written by the body with an
`evidence_ref`), and the tier contract is taken from `skills/publish-to-index/SKILL.md`, which is in the tree and
is authoritative. If either document says something different, it wins and this file has a bug.
