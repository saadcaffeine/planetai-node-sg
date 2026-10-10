# Journeys: the node's second loop

How an event becomes a capability. This document designs the explore tier — the loop from a reading to something made nearby — and is the authority for `explore:` blocks in the issue files, the household capability inventory, and the offer contract that governs how often the node may suggest. It builds on `docs/SPEC_language.md`: every string here obeys the voice rules and speaks in the three layers.

The node today runs one loop: a reading, an event, a protective action, a measured result — close the windows, run the purifier, ρ counts it. The learn content already names what is missing: the loop from a reading to something made nearby. This document gives the node the second loop: the same event, offered afterwards as a possibility. **[changed: "afterwards"; see When an offer is made]**

**The principle that shapes everything below: the journey belongs to the household, never to a person.** A person depends on a roof, water, energy, food, waste and communications; the house is the unit that connects to the place, and the place is what the node reads. No streaks, no badges, no levels, no "you did it!". **[changed]** The household is identified the way `docs/SPEC_rho.md` §3 identifies it: a `principal` stable enough to count and never enough to name.

**[new] The second loop never touches the first.** Protection is measured by ρ; curiosity is not. An explore answer is never an action, never enters ρ, and never shares a message with an open protective ask.

## The capability inventory: the house's limbs

**[changed]** `HOME_HAS` today is a comma-separated setting filtered against the four-item `HOME_ITEMS` tuple (`app/events_pg.py:17`); anything else is silently dropped. `HOME_ITEMS` becomes the inventory below, grouped by need so Set up reads like a metabolism, not a shopping list.

| need | limbs |
| --- | --- |
| roof | windows, fan, purifier, ac, dehumidifier, mosquito_net, insulation, plastic_sheeting |
| energy | solar, battery, inverter, generator, induction_stove |
| water | water_filter, rainwater, greywater, well, pump, stored_water |
| food | garden, greenhouse, fruit_trees, chickens, aquaponics, fermentation |
| waste | compost, biodigester, recycling_station, black_soldier_fly |
| comms | meshtastic_radio, community_mesh, crank_radio |
| sensing | outdoor_sensor, weather_station, drone, camera, microscope |
| making | hand_tools, power_tools, 3d_printer, laser_cutter, sewing_machine, soldering_iron, workbench |
| mobility | bicycle, e_bike |
| care | first_aid_kit, medications, n95_masks, fire_extinguisher, power_bank |

**[changed]** `windows` and `fan` keep their place in roof: they are in `HOME_ITEMS` today and the setting's help text names them, so houses may already have declared them. The care row (first aid kit, medications, masks, extinguisher, power bank) stays in the vocabulary by Tomas's decision (9 October 2026), but as declared-only limbs: no action or offer reads them yet, they live behind "more" in Set up, and medications is health information the node has no reason to hold until an offer needs it.

**Sources.** Roof and the thermal rows draw on the WHO Housing and Health Guidelines (2018) and on the Global Heat Health Information Network's At Home guidance (2023). The links: [WHO Housing and Health Guidelines, 2018](https://www.who.int/publications/i/item/9789241550376); [Global Heat Health Information Network, At Home](https://heathealth.info/at-home). `plastic_sheeting` is the Red Cross shelter-in-place item. `camera` sits in sensing because the official Fab Lab inventory lists documentation (camera + accessories) as a machine of the lab. Compost sits in waste: it processes the one and feeds the other.

**[changed] Set up shows what is used.** The Set up section lists only the limbs some action or offer names (`when: home_has` or `needs:`), grouped by need, plus today's four items, with the full vocabulary behind "more". The list grows as content is written, not as the vocabulary does. Packs may extend the vocabulary.

**[new] Words.** "Limb", "rung", "journey", "offer" and "explore" are this document's words, not the household's. Set up keeps the label it has today, "What this home has" (`app/settings.py:86`), and every surface uses one household word for an offer (open decision).

## The Fab City Lab inventory

The make rung's other half: what a lab offers a house that does not own the machine. The Fab Foundation's official inventory is the baseline — laser cutter and filtration, CNC milling, the benchtop precision mill, 3D printers, vinyl cutter, electronics workbench, molding and casting, large-format printing, silk screening, documentation camera. The Fab City Lab inventory extends it with plastic recycling (Precious Plastic's shredder, extruder, injection and sheet press), a sensor and IoT bench, and composting equipment.

**[changed] Directories.** fablabs.io names where the labs are, read through the `make` pack. That pack is **off by default** (`MAKE_ENABLED=0`): the directory is not openly licensed, and Fab City Foundation's decision to read it covers the Foundation, not each operator. The Precious Plastic community map would name recycling workspaces and their machines. It is read only after it has a `data/sources` file and a licence answer, like every other source.

**[new] The standard already exists.** A lab declaring its machines is what Open Know-Where (OKW) is for: a published schema in which a facility lists its `equipment`. The make-pack decision record (`docs/decisions/2026-09-10-make-pack.md`) proposed exactly that, through Open Hardware Manager, with Open Know-How (OKH) ids for designs and a `fabricable:` key on rules. It was never decided, and the shipped pack reads fablabs.io instead. So:

- The Fab City Lab inventory is written as OKW equipment terms, extended only where OKW has no term (plastic recycling, the sensor bench), and those extensions are proposed upstream.
- A make offer may carry `fabricable:` OKH ids, as rules were meant to, so "the lab could make this" names a design and not a sentence.
- **Prerequisite:** the make-pack decision is settled (fablabs.io, OHM/OKW, or both) before the make rung is built.

## Two kinds of making **[new]**

The Act layer already makes things. `ARCHITECTURE.md` puts a `fabricate` stage between decide and act "when the action is a part", and names the first fabrication ticket: a printed enclosure, an air-filter frame. That making is **protective**. It answers an ask, it is timestamped in `actions`, and it belongs to ρ.

The making in this document is **exploratory**. It answers no ask, it is recorded in `explore_answers`, and it never enters ρ.

The test is the question the thing answers. A filter frame printed because the kitchen keeps filling with smoke is protective, even if an offer first suggested it; once the household decides to make it for that reason, it is a fabrication ticket on that event. A shade design drawn because the house was curious about the west wall is exploratory. One object never sits in both ledgers.

## The explore tier

A second list beside `actions:` in each sensed issue file, using the same `when:` machinery, with two new keys. **[changed]**

- `rung` — the step of the journey: **search → learn → design → prototype → make**.
- `needs` — the limb the offer uses, if any. **It is not a condition.** `when:` decides whether an offer is possible; `needs` decides how it is ranked and, at prototype and make, whether the lab sentence is added.

```yaml
explore:
  - id: air/where_it_comes_from
    rung: search
    when: {kind: [spike, unusual], where: outside}
    say:
      en: "That smoke came from outside. The map shows the stations around the house; the one that
           rose first is closest to where it started."
  - id: air/map_the_plume
    rung: prototype
    needs: drone
    when: {kind: [spike], where: outside}
    say:
      en: "Next time smoke comes from outside, a drone flight would show where it starts.
           Drop the flight's GeoTIFF into the node and it joins the map."
```

**[changed]** The example says only what the node knows. An outdoor spike is not proof of a plume overhead, and the flight lands on this node's own map, not the ring's. It also presumes an outside reading: a house whose air issue only ever reads indoors never sees the offer fire, and that is correct, not a bug.

Every chain starts at search or learn, which need no equipment, so a house with nothing but windows still has a journey. The pitch obeys the three layers: what the house could do, why now, what it unlocks.

At prototype and make, a house without the `needs` limb gets one more sentence:

- `make` enabled and a lab within `MAKE_RADIUS_KM`: the nearest lab, by name and distance, from the directory.
- **[new]** otherwise: "A fab lab or makerspace near you may have one." It names no lab. Labs come from the directory or not at all.

**[changed]** "Fab Lab Bali prints it" is fixed at its source, `docs/site/sensors.md:173`, and `learn.json` is rebuilt with `tools/build_learn.py`.

**[new] Packs.** A pack may add `explore:` entries to an existing issue, under the same rules as `actions:` (`SPEC_alerts.md` §8), and may extend the limb vocabulary. A pack for one place is a wild pack in its own repository. Offers are worded as possibilities from the node's content, never as findings (`SPEC_decide.md` §14).

## When an offer is made **[new]**

An event message carries one action and one set of buttons (`SPEC_alerts.md` §4, §7). Protection first: an offer never appears beside an *unanswered* protective ask. One exception, decided 9 October 2026: on an outdoor `spike` or `unusual` event, once the house has answered the protective ask, the offer may join — the plume is there while the smoke is, not after it clears. Everywhere else, offers go in two places:

1. **The all-clear.** When an event clears, its all-clear may carry one offer. The all-clear already carries no action, is already held past quiet hours, and is not counted in `ALERT_MAX_PER_DAY`. The offer adds no push.
2. **The next report** (`REPORT_EVERY` hours from `REPORT_ANCHOR`, the node's one scheduled message), for offers that are good all season (a shade design), and later for context issues, which have no events. An event that cleared in quiet hours carries its offer in the first report after them, as its all-clear already does. **[changed: there is no fixed morning report]**

This also settles the original's open question about expiry: an offer is said once, at clear or in the report, and is not carried forward.

- At most **one** offer per all-clear, and one per report.
- After a `danger` event, an offer may come at its all-clear, a day later (decided 9 October 2026).
- Coast and land have no events in v1; their offers wait for the report slot.
- **[new]** The `EXPLORE` setting gates all offers (see Phasing).

**[new] On the page.** Decide holds open asks and nothing else (`SPEC_dashboard_events.md` §4.1), so an offer is never drawn there. It is drawn in **Act**, beside the answered event it followed and beside the nearest place to make or fix something, which Act already shows when the node knows one (`docs/GUI.md`). The page holds no copy: the offer's words and its three button labels come from `/issues`, in a new `explore` key. `/issues` is `issues-v0`, so `tests/data/wire/issues-v0.json` is edited on purpose in the same PR. Adding a key is not a breaking change and needs no version bump.

## Answers and the done-set **[changed]**

An offer has its own buttons, with the same three words as an event (`BUTTONS` in `app/actions.py`), written to a new table that no ρ query reads:

```sql
CREATE TABLE IF NOT EXISTS explore_answers (
  id         BIGSERIAL PRIMARY KEY,
  ts         TIMESTAMPTZ NOT NULL DEFAULT now(),
  offer_id   TEXT NOT NULL,           -- air/map_the_plume
  issue      TEXT NOT NULL,
  rung       TEXT NOT NULL,
  event_id   BIGINT,                  -- the event whose all-clear carried it, if any
  stage      TEXT NOT NULL,           -- acted | later | dismissed
  principal  TEXT,                    -- SPEC_rho §3
  note       TEXT                     -- the household's own words, never a model's
);
```

- **Done** → `acted`. The offer is done for this house.
- **Not now** → `later`. Nothing is muted.
- **Doesn't fit** → `dismissed`. Two dismissals mute that offer for 180 days (decided 9 October 2026). Adding the limb it `needs` lifts the mute at once: the house has changed.

**[new] What an answer never does.**

- It never touches the issue's state or `open_asks`. Since `SPEC_event_led_state.md`, an answer to an open event makes its issue `notable`; an explore answer is not an answer to an event.
- It never travels. `push_events` joins `actions` on `alert_id` (`app/main.py:541`), so this table is not pushed, and its notes are a household's own sentences, which stay on the machine that recorded them (`AGENTS.md`). It is not in the daily export.
- A model never writes one without the household's words, the same note rule as `act` (`SPEC_rho.md` §3).

A separate table is the choice, decided 9 October 2026. The alternative was a new `actions.stage` value with `alert_id` NULL, which `SPEC_decide.md` §6 shows every consumer ignores (as `settings` is ignored today); it would still have needed an `offer_id` column.

**Selection is deterministic.** A rung is done for an issue when any of its offers is `acted`. Among the offers whose `when:` holds and that are not done or muted, the selector takes the lowest rung that is not done, and within it prefers offers whose `needs` the house has. A rung with no written offers is skipped, not a dead end.

Wording speaks of the house, never of a person: "this house has never mapped smoke", never "Lucas hasn't".

## The drone lands somewhere: NEXT_RELEASE §3

The offer "fly the drone" is only half a loop without somewhere for the flight to land. NEXT_RELEASE.md §3 already owes it: providers beyond OpenAerialMap, including a household's or a lab's own flight — a GeoTIFF dropped into the node, tiled locally. Fly, drop the GeoTIFF, and the flight becomes a ground layer on the node's own map, credited like any mosaic.

**[changed]** That map is the node's own: `/ground/*` needs a token at every share level (`SPEC.md` §4). A household flight also shows the neighbours' roofs. Whether and how it ever leaves the node is a `docs/SPEC_custody.md` decision, not this document's.

## Phasing **[changed]**

Under NEXT_RELEASE rules 2–3, v1 ships as three releases, in this order:

1. **The node** (`app/issues`, `app/actions.py`, `app/events_pg.py`, `app/issues/engine.py`, `init.sql`, tests). `HOME_ITEMS` becomes the inventory; `explore:` with `rung` and `needs`; the selector; `explore_answers`; the `EXPLORE` setting (default `1`; it exists to switch offers off, not to hide them); the `explore` key on `/issues` with its wire fixture; offers in Telegram as "When an offer is made" sets out. `HOME_HAS` is already editable as a setting, so this works before the page changes.
2. **The page** (`app/static`). The Set up section "What this home has", in the classic dashboard's Set up, which the doors link to and do not yet port; the offer in Act, on the classic dashboard and the doors, with the doors in English until they gain locales.
3. **The make pack** (`packs/make`), after the make-pack decision is settled. The nearest-lab sentence and `fabricable:` ids for prototype and make offers.

**First content [changed]: equipment-free first.** Air: `where_it_comes_from` (search) and one learn entry. Heat: a shade design (search → design) and one learn entry. `air/map_the_plume` does **not** ship in v1 (decided 9 October 2026): it waits for NEXT_RELEASE §3's own-flight GeoTIFF route, so the offer never asks for a flight the node cannot yet receive. Content written around node #1's drone before the landing strip exists would repeat the Fab Lab Bali mistake.

**[new] FAB26.** The experiment runs October to December 2026 and asks three things: does the node stay alive, can a normal person use it, and what do people build on it (`docs/FAB26_EXPERIMENT.md`). Its second check-in question, "Did an alert make you do anything?", is the ρ dataset. Offers arriving mid-experiment would change the messages participants are judging, so:

- `EXPLORE` ships as `1` and is on for every FAB26 node at once, announced in a check-in, so the experiment measures the real message stream rather than a quiet one (decided 9 October 2026).
- The check-in gains a fourth question: "Did the node suggest something to try, and did you?" Without it, a season of fab26 data about offers will not exist.
- Journeys is a natural fit for FAB26's third question. The build track (packs, the API) is where a participant would first write an explore entry.

**Mid-term.** The bot may reword an offer the selector already chose, with the yml text as the fallback (`SPEC_alerts.md` §8). It never chooses an offer and never speaks unprompted (`app/agent_loop.py`). The data stays the brain; the model is only the voice.

**Long-term.** A richer journey engine — sequencing, cross-issue paths — only if a season of fab26 data shows the done-set is not enough. Design it then, with the data in hand.

## Decisions (Tomas, 9 October 2026)

1. An offer may join an **open** outdoor `spike`/`unusual` event once the house has answered the protective ask — the plume is there while the smoke is.
2. Two dismissals mute an offer for **180 days**, lifted at once when the house adds the limb it needs.
3. After a `danger` event, an offer may come at its all-clear, a day later.
4. The care row ships as declared-only vocabulary, hidden in Set up until an offer uses it.
5. `air/map_the_plume` does not ship in v1; it waits for NEXT_RELEASE §3's own-flight GeoTIFF route.
6. Explore answers live in a separate `explore_answers` table that no ρ query reads.
7. The make-pack decision (fablabs.io, OHM/OKW, or both) is settled before the make rung is built; the lab inventory uses OKW terms either way.
8. `EXPLORE` ships as `1`: on for every FAB26 node at once, announced in a check-in, with a fourth check-in question ("Did the node suggest something to try, and did you?").
9. The household's word for an offer stays **open** — every surface will use one word, chosen before the page release.
