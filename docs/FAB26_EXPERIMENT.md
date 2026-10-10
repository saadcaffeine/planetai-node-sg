# The FAB26 node experiment

October to December 2026. What we ask, what we measure, how to reach us.

You built or received a PLANETAI node at the sensors workshop in July. Between now and December we want to learn,
with you, three things: **does it stay alive**, **can a normal human use it**, and **what do people build on it**.
This page is the whole experiment. If anything here is unclear, that is a bug — tell us.

## The timeline

- **Kickoff all-hands, week of 6 October.** A live call; we install together, one screen at a time. Bring the
  machine your node will live on. Nobody leaves without seeing their own dashboard and one alert on Telegram.
- **October and November: live with it.** Keep the machine on. That is most of what we ask. Every two weeks the
  experiment bot asks you three questions, two minutes from your phone.
- **Any time, optional: build something.** A pack for a sensor we do not support, or something that talks to the
  node's API. The strangest idea in the room is probably the one we need most.
- **Wrap-up all-hands, first week of December.** What held, what broke, what people made. The findings write-up
  goes to everyone after.

## Install

```bash
curl -fsSL planetai.fab.city/install | bash
```

Four questions, two minutes. Then `planetai telegram` for the alerts and `planetai ui` for the dashboard.
Best machine: an old laptop or mini PC with Linux that stays on. A Mac works; Windows through WSL2. The full
walk-through is [START_HERE.md](START_HERE.md).

**Confirm you are in:** open **@planetai_exp_bot** on Telegram and send it your name, city and node name. That
first message is our census, and it proves your channel works.

## If you have the workshop sensor kit

Some participants left FAB26 with a kit: a Seeed XIAO ESP32-S3 with the Wio-SX1262 LoRa module, a Grove shield,
a BME680 (temperature, humidity, pressure, gas) and a Seeed HM3001 (PM). If that is not you, skip this section —
a node with no sensor still knows your weather, the satellite air model over your district, and forty years of
climate for your coordinates.

Your kit left the workshop flashed with firmware that reads both sensors and publishes to the node. You do not
need to reflash anything: power it within reach of your node setup and its readings join the picture. The radio
side of the path — gateway radio, channels, regions, provisioning — is documented in
[MESHTASTIC.md](MESHTASTIC.md).

The 3D-printed enclosure from **Making Sense Bali** fits this exact assembly. Files:
[github.com/Meaningful-Design-Group/makingsensebali](https://github.com/Meaningful-Design-Group/makingsensebali/tree/main/hardware/diy-node/enclosure/node-v3.2).

One caveat, so nobody loses data by being tidy: stock Meshtastic firmware reads the BME680 but not the HM3001.
If you ever reflash the kit with stock firmware, particulate readings stop until the custom path is restored.
Update the node, not the radio.

## The biweekly check-in

Every two weeks, **@planetai_exp_bot** pings you with three questions:

1. **Did your node stay up?** (yes / died and I restarted it / still down)
2. **Did an alert make you do anything?** Open a window, close one, move something, look outside — anything,
   in your own words. "Nothing, again" is data too.
3. **One thing that surprised you.** Good or bad. A sentence is enough.

Answer however is natural: type it, send a voice note, photograph your dashboard. The second question is not
idle curiosity. The node's own measure of itself is ρ, the share of alerts that led to an action, and your
honest answers are the dataset.

**Between check-ins the bot is the drop box.** An idea at midnight, a screenshot of something weird, a voice
note from the street — send it any time and it reaches the team, filed under your name.

## The build track (optional)

Two doors in:

- **Write a pack.** A pack is a folder: a small adapter that reads a thing, channels that name what it measures,
  rules that say when to speak. Start from [PACKS.md](PACKS.md); copy `packs/heat`. Keep it in a repository of your
  own, install it on any node with `planetai packs add <you>/<repo>`, and list it at
  [fabcity/planetai-wild-packs](https://github.com/fabcity/planetai-wild-packs) so other nodes can find it. The Xiaomi air purifier pack,
  `xiaomi-air`, written for two real living rooms, is listed there.
- **Use the API.** The node exposes readings, alerts and reports over MCP and plain HTTP on your network;
  `planetai agent` shows the URL and token. Feed your own dashboard, your Home Assistant, your spreadsheet habit.

Tell us what you built, however rough. A screenshot and three sentences is a perfect report.

## How to report

- **The bot first:** @planetai_exp_bot. Check-ins, ideas, screenshots, voice notes. If you use only one channel,
  use this one.
- **Bugs and confusion:** tell the bot, or open an issue here titled starting with `[fab26]`. We file bot
  reports as issues ourselves when they are bugs.
- **Catch-all, always:** info@fab.city

What you report decides what gets fixed first. That is not a courtesy line; it is how the alpha has worked since
node #1 went up in Bali in September.

## The deal

Your readings never leave your machine. What flows upward is a daily summary, and only if you point the node
somewhere. The experiment collects your check-in answers, your issue reports, and whatever you choose to show
from the build track. Nothing else.
