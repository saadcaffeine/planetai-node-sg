# Networking
<!-- checked: v0.80.10 -->

Three layers, each doing one thing.

| layer | for | command |
|---|---|---|
| Tailscale | reaching the node from anywhere; nodes reaching each other | `planetai mesh` |
| Meshtastic (LoRa) | sensors and alerts where there is no WiFi | `planetai meshtastic` |
| Reticulum (LXMF) | encrypted messages when the internet is gone; later, node-to-node data | `planetai reticulum` |

## Tailscale

`planetai mesh` installs the client and joins the tailnet under the node's name. No open ports; the node is reachable
as `<name>.<tailnet>.ts.net` from any of your devices. `PARENT_API_URL` becomes a tailnet hostname when a district node exists.
Tailscale SSH is Linux-only. On a Mac, ordinary `ssh` over the tailnet, with Remote Login on.

Headscale, self-hosted, is the recorded exit if a partner's governance forbids a third-party coordinator. Swap the login
server; nothing else changes.

## Meshtastic

The ground layer. One gateway radio with WiFi uplinks the mesh to a broker on the node; field radios carry sensors on
batteries; a shelf radio paired to a phone receives alerts with no internet. Everything about the radios is in
[`MESHTASTIC.md`](MESHTASTIC.md).

A LoRa frame is about 200 bytes, a few a minute. Telemetry and one-line alerts, not data between nodes.

## Reticulum

The bridge container gives the node an LXMF address. Inbox: `act <id>` from Sideband records an action. Outbox: alerts
to `RETICULUM_ALERT_DESTINATIONS`. Presence, only with `RETICULUM_PRESENCE=1`: every half hour it announces the node's
name and its H3 cell rounded up to `RETICULUM_PRESENCE_RES` (3 by default, never finer than 6). TCP today; an RNode LoRa interface is a commented block in
`config/reticulum/config.tpl`.
Node-to-node data over Reticulum returns when a district and a community node have no internet between them (SPEC §6).

## What connects to what

```
sensors (WiFi)  ──HTTP──▶ node ◀──MQTT── gateway radio ◀──LoRa── field radios, shelf radio
                          │
                          ├──Telegram──▶ phones          (internet)
                          ├──LoRa (via gateway)──▶ shelf radio    (no internet needed)
                          ├──LXMF──▶ Sideband           (no internet needed)
                          ├──MQTT discovery──▶ Home Assistant
                          └──Tailscale──▶ you, other nodes, a district
```

Raw readings never leave the house on any of these. Home Assistant, on your own network, gets each sensor's latest
value; hourly means go up to a parent; alerts go out; that is all.
