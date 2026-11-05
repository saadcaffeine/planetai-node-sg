# SPEC: the node brokers the house's sensors, and a pack knows the brands

*Asked, 15 October 2026, by Tomas, answering the pre-launch audit: "we should put as core the node being the broker of
sensors at the household, and have smart citizen, purple air, and air gradient as a air quality sensor pack,
independently."*

**Status: decided 15 October 2026 (Tomas: "A yes, B air-sensors, C yes"). Nothing built.** Each step below is its own pull request, run on node #1 before it merges.

## 1 · What is there today

The core does two jobs at once. It brokers, and it also knows three makes of sensor by name.

- **Broker.** The `mosquitto` container. `app/main.py` subscribes to two wire formats on it:
  - Meshtastic radios, through `sources.meshtastic_message`.
  - Smart Citizen kits publishing their own MQTT format to the node, through `sources.smartcitizen_mqtt`. Their
    copies are forwarded to smartcitizen.me when `SC_FORWARD` names them.
- **Brands, polled over HTTP.** `app/sources.py` holds:
  - `smartcitizen` (the platform's API, `SC_DEVICES` / `SC_USER`)
  - `airgradient` (the device's local API, `AIRGRADIENT_HOSTS`)
  - `purpleair` (the local API, `PURPLEAIR_HOSTS`)

  `sources.enabled()` turns on only `smartcitizen`. The AirGradient and PurpleAir adapters exist, but nothing calls
  them; `AIRGRADIENT_HOSTS` is only read to keep those units out of Bali Air Dispatch.
- **The installer offers all three** (`bin/planetai`, question 4). Picking AirGradient or PurpleAir writes a host that
  is never read. The node gets no reading and no first alert, and nothing tells the operator why (audit item 9).

## 2 · The split

**Core: the broker, and one wire format of its own.** The node is where the house's devices report. It keeps:

- `mosquitto`
- the subscribe loop
- custody and rooms (`sensors.local`, `indoor`, `room`)
- one PLANETAI topic that any device or bridge can publish to, with no brand code: `planetai/<sensor_id>/<metric>`,
  carrying `{"v": <number>, "ts": <ISO 8601, optional>, "unit": <optional>}`, plus a retained
  `planetai/<sensor_id>/meta` holding `{"name", "indoor", "lat", "lon"}`
- the hook packs use to read their own topics (§3)

An ESPHome, Tasmota or DIY board can report to the node with no pack at all.

**Pack `air-sensors` (core, official): the brands.** It holds:

- Smart Citizen: the API poll, the MQTT wire format and the forward to smartcitizen.me
- AirGradient: the local API
- PurpleAir: the local API

Each adapter writes the same `sensor_id`s as today (`sc-<kit>`, `ag-<serial>`, `pa-<id>`), so a node's history
continues across the move. Each reads the same settings keys as today, so no `.env` changes. `packs/air-quality` stays
what it is, rules and Index cells. The new pack is only where readings come from.

Meshtastic stays in the core for now. It is the house's radio mesh, and alerts go out over it (`MESH_ALERTS`), not
just readings in. Whether it is a broker transport or a brand is open question C.

## 3 · What the core needs that it does not have

1. **A topic hook for packs.** `packs.adapters()` only polls (`fetch(hc)`). A pack also needs to say "these MQTT
   topics are mine, here is the parser". That means a `topics()` function in `adapter.py`, returning
   `{pattern: parse(topic, payload) -> (sensors, readings)}`. The core subscribes and routes.
2. **Official packs run code by default.** Today every `adapter.py` waits for `PACKS_ALLOW_CODE=1` (open question A).
   Moving Smart Citizen into a pack under that rule would switch it off on every default install.
3. **The installer reads its sensor menu from the pack.** Question 4 lists what `air-sensors` declares it can read,
   so the menu can never offer a sensor the node does not read again.

## 4 · Steps

1. **The PLANETAI topic and the topic hook** (core). Tests cover a reading on `planetai/<id>/pm25` arriving as a row,
   and a pack's topic reaching its parser. The installer stops offering AirGradient and PurpleAir until step 3; that
   part ships with audit PR 4.
2. **Smart Citizen moves into `air-sensors`.** The code moves; it is not rewritten. On node #1 the seven SC kits
   keep their ids, their history and their forwarding.
3. **AirGradient and PurpleAir are wired for the first time**, in the pack, each tested against a real unit before it
   is offered. Node #1 has neither today, so this step waits for a unit in a house.
4. **The installer's question 4 reads the pack.**

## 5 · Decided (Tomas, 15 October 2026)

- **A. Code in official packs: yes.** The packs shipped in this repository, signed with the release, run their
  `adapter.py` without `PACKS_ALLOW_CODE=1`. The flag now means "wild packs may run code".
- **B. The pack's name: `air-sensors`.**
- **C. Meshtastic stays in the core**, as the house's radio. Alerts go out over it.
