# Channels
<!-- checked: v0.80.10 -->

A channel is how an alert leaves the node and reaches the people it is for. The repo's own description of a node
ends with it: it "sends the people at that address one plain message when something should change". This page
connects four ways of doing that. Two of them (Telegram and Reticulum) also carry the answer back, which is how
an alert becomes a row in `actions` and, from there, part of [ρ](rho.md).

| channel | receives | needs internet | answers back | set up with |
|---|---|---|---|---|
| Telegram | every alert that reaches the floor; every report; the bot's replies | yes | `/act <id> <words>`, when the bot runs | `planetai telegram` |
| Meshtastic (LoRa mesh) | `act` alerts, first line only | no | no | `planetai meshtastic`, then `MESH_ALERTS=1` |
| Reticulum (LXMF) | `act` alerts, full text | no | `act <id> [note]` | `planetai reticulum` |
| Home Assistant | every alert, sent or not, and every report sent, as entity state | no (LAN) | no | `planetai homeassistant` |

Telegram, the mesh and Reticulum are reached from `notify()` in `app/main.py` (the mesh through `mesh_send()`,
Reticulum by a post to the bridge container). Home Assistant is a separate call, `ha_alert()`, made after
`notify()` and also for the alerts `notify()` does not send. A separate notifier service is a retired piece in
[`SPEC.md`](spec.md) §6; its trigger is a second channel with its own auth lifecycle (WhatsApp Business), not a
count of channels.

With `ALERT_ENGINE=events` (v0.77; the default, `rules`, is unchanged) the heat and air-quality rules still record their
alerts, and Home Assistant still gets them, but they are not sent. The event engine sends one message per event
through the same `notify()`, so an `act` event reaches the mesh and Reticulum as well as Telegram. In quiet hours it
sends only danger, and outside danger at most `ALERT_MAX_PER_DAY` pushes a day (default 4). On Telegram, event messages
carry three buttons (Done / Not now / Doesn't fit) when the bot has announced itself (`TELEGRAM_BUTTONS=1`); the button
press posts `POST /actions` with `event_id`, `stage`, `actor`, `note`. `/act` still answers alerts, not events.

## Telegram

The default channel, and the one the report uses. Everything it sends is plain text prefixed with the level's
icon: ℹ️ for a report or an info alert, ⚠️ for warn, 🔴 for act.

1. **Run `planetai telegram`.** It prints `1. In Telegram, message @BotFather and send:  /newbot`. Do that, give
   the bot any name and a username ending in `bot`, and copy the token BotFather replies with.
2. **Paste the token.** The node checks it with Telegram and prints `● token works. Your bot is @<name>`. A
   wrong token stops here with "Telegram rejected that token. Copy it again from @BotFather."
3. **Send the bot any message** (or add it to a group and make it an admin). The terminal waits up to two
   minutes, then prints `● found your chat: <id>`. It writes `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_IDS` to
   `.env` and to the running node's settings, so the terminal and the dashboard agree about which bot this node
   talks to. `TELEGRAM_CHAT_IDS` is a comma list; several people can receive.
4. **Read the hello.** The chat receives `<NODE_NAME> is connected. Alerts will arrive here.`, or `<NODE_NAME>
   está conectado. Los avisos llegarán aquí.` when `ALERT_LOCALE=es`. The terminal ends with
   `● the node is restarting with Telegram on. Try:  planetai test-alert`.
5. **Run `planetai test-alert`.** A 🔴 message arrives. The whole path works: a rule fired, the node wrote a
   message, and it reached a person.

With the token blank the node logs alerts and sends nothing. The node never logs the Telegram URL, because the
token is in it; `planetai logs` containing `api.telegram.org/bot` would be a leak.

Answering on Telegram is the [bot](bot.md), which runs in the separate `agent` container. `/act 12 closed the
windows` records an `acted` row with the actor `<AGENT_NAME>/telegram` (`local-model/telegram` by default) and replies "Recorded: you acted on
#12." `/act 12` with no words is not recorded: the bot asks "What did you do about #12? Send it as:  /act 12
<what you did>". `/stack` answers from the node's own arithmetic, with no model.

## Meshtastic, the LoRa mesh

For sensors and alerts where there is no WiFi. One gateway radio with WiFi uplinks the mesh to an MQTT broker on
the node; field radios carry a sensor on a battery; a shelf radio paired to a phone receives alerts when the
internet is down.

1. **Run `planetai meshtastic`.** It creates a broker user, starts the broker as the compose profile `mqtt`, and
   prints *Now the gateway radio (the ESP32 one), in the Meshtastic app* with every value to type: the LoRa
   region for your preset (`EU_868` by default, `SG_923` for Bali), MQTT on at `<this machine's LAN IP>:1883`
   with the username `planetai` and a generated password, encryption off, **JSON output on** (without it the
   node cannot read the packets), root topic `msh`, and uplink and downlink on for your channel. The node
   now has its own broker on the LAN, waiting for the mesh; nothing arrives until the gateway radio carries
   these values.
2. **Set the gateway and wait.** The terminal prints `Waiting for the first packet from the mesh (up to 3
   minutes)`, then `● packets arriving. Sensors seen so far:` and the mesh sensors it has. Radio telemetry on
   `msh/#` now becomes readings. A radio's own temperature and pressure are its enclosure, not the street.
3. **Turn on alerts back to the mesh.** Set `MESH_ALERTS=1` and `MESH_GATEWAY_NODE_NUM=<the gateway's node
   number, decimal>` in `.env`, then `planetai restart`. An `act` alert's first line is then published through
   the gateway, once the node has learned the mesh's root topic from an uplink. `planetai logs` shows
   `mesh -> sent <n> bytes on <topic>`.

If step 2 prints nothing, the usual reasons are printed with it: JSON output off on the gateway, the wrong
address, a gateway on another WiFi, or a firewall on 1883. A LoRa frame is about 200 bytes, a few a minute:
telemetry and one-line alerts, never data between nodes. Everything about the boards, the firmware and the
channel key is on [Radios](radios.md).

## Reticulum, LXMF

The bridge container (compose profile `reticulum`) gives the node an LXMF address that Sideband can message. It
posts answers to `POST /actions` with `ACT_TOKEN`, and it reads that token when its container is created, so run
`planetai ui` first if the node has no `ACT_TOKEN` yet: it creates one.

1. **Run `planetai reticulum`.** It builds and starts the bridge and prints
   `● this node's LXMF address:  <address>`, then what to do in Sideband: add a TCP Client interface to this machine's LAN address on port
   4242, and start a conversation with the address above. The node now has an address a phone can reach
   over Reticulum with no internet in between, and the next step uses it to answer.
2. **Answer an alert.** Send `act 3 opened the windows`. The bridge records an `acted` row on alert #3 with the
   actor `lxmf:<your hash>` and replies `recorded: you acted on #3`. Sent as `act 3` alone, the note is recorded
   as `acted (via reticulum)`: this path does not ask for words.
3. **Receive alerts.** Copy your own LXMF address from Sideband's settings into `.env` as
   `RETICULUM_ALERT_DESTINATIONS=<hash>[,<hash>]`, then run `planetai reticulum` again. The bridge reads the
   list when its container is created, and `planetai restart` (which the terminal suggests) recreates only
   the app. `planetai logs reticulum` then shows `bridge up: http :4243, announcing every 1800s, 1 alert
   destination(s), …` with your count. Every `act` alert is delivered, full text, to each address. To check, run `planetai test-alert`: Sideband shows a message from the node's
   address titled `planetai <NODE_NAME>`, carrying the whole test alert. If nothing arrives, `planetai logs
   reticulum` says `no path to <hash> yet; is that client announced and reachable?`. The alert now reaches a
   person with no internet in the house, and step 2 carries the answer back.

The bridge does not read `.env`. It receives exactly eight variables from `docker-compose.yml`: `LOG_LEVEL`,
`NODE_NAME`, `NODE_API_URL`, `RETICULUM_CONFIGDIR`, `RETICULUM_DATA`, `RETICULUM_ALERT_DESTINATIONS`,
`RETICULUM_ANNOUNCE_S` and `ACT_TOKEN`. The Telegram token, the admin token and the database password stay out
of a process whose job is to speak to a radio mesh. TCP transport today; an RNode LoRa interface is a commented
block in `config/reticulum/config.tpl`.

Presence is separate and off by default: with `RETICULUM_PRESENCE=1` the bridge announces the node's name and a
coarse H3 cell every half hour, at `RETICULUM_PRESENCE_RES` (3) and never finer than resolution 6, whatever the
setting says, so an exact place never leaves. `GET /presence` is what the bridge reads to do it, and it answers
at every sharing level for that reason.

Node-to-node data over Reticulum (a district and a community node with no internet between them) is a retired
piece with its trigger written in [`SPEC.md`](spec.md) §6.

## Home Assistant

1. **Run `planetai homeassistant`.** With no broker yet it says `● no broker yet: setting one up (this is the
   same broker the Meshtastic gateway uses)`. It sets `HA_DISCOVERY=1`, restarts the node, and prints
   `● publishing. Entities appear in HA within one poll (5 min).` followed by the broker address, port 1883,
   username and password. The node's sensors and alerts are now on a broker on the house's own network,
   where Home Assistant can act on them; the node itself still switches nothing.
2. **Add them in Home Assistant**: Settings → Devices & services → Add integration → MQTT. Discovery does the
   rest: a device per sensor, and a *latest alert* text sensor on the node itself.

What is published: each metric of each local sensor, and of the model and portal points, as a discovery entity
grouped under a device per sensor with a suggested area of Indoor or Outdoor. Other people's reference stations
are not published. States are retained at `planetai/<node>/<sensor>/<metric>` and expire after an hour of
silence. The *latest alert* sensor carries the first line of the latest alert or report, with `level`,
`alert_id` and `ts` as attributes: every alert, whatever its level and whatever quiet hours say, and every
report that is sent. If Home Assistant already runs a broker, point `MQTT_HOST`, `MQTT_USER` and `MQTT_PASS` at it instead.

The node switches nothing on or off. Build the automations there: purifier on above 35 for ten minutes; a
window reminder at the cleanest hour; a phone notification when the alert level is `act`.

## Languages

Since v0.63 Spanish runs through every channel: with `ALERT_LOCALE=es` the Telegram hello, the bot's own
replies, the test alert, every alert and every report are in Spanish. With `id` the alerts and the report are in
Bahasa Indonesia, and the bot's few fixed lines and the Telegram hello stay in English. The terminal is in
English.

## What a house with no internet still gets

A shelf radio paired to a phone receives the first line of every `act` alert over LoRa. Sideband receives the
whole alert over LXMF and can answer `act <id>`. Home Assistant on the LAN keeps every entity current. The
dashboard on a wall screen keeps drawing. The node keeps polling its LAN sensors, running its rules and writing
its reports; only Telegram waits for the internet to come back.

## Where this leads

The node can now ask, and hear the answer. [ρ](rho.md) is what it makes of the answers: the share of its alerts
that somebody acted on, and whether the condition stopped afterwards. The [report](report.md) is the one
message it sends on a schedule rather than on a line being crossed.
