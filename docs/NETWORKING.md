# Networking
<!-- checked: v0.91.0 -->

Three layers connect a node, each with one job.

| layer | for | command |
|---|---|---|
| Tailscale | reaching the node from anywhere; nodes reaching each other | `planetai mesh` |
| Meshtastic (LoRa) | sensors and alerts where there is no WiFi | `planetai meshtastic` |
| Reticulum (LXMF) | encrypted messages when the internet is gone | `planetai reticulum` |

## Tailscale

`planetai mesh` installs the client (with Homebrew on a Mac) and joins the tailnet under the node's name, asking
you once to approve it in a browser. The node then answers as `<name>.<tailnet>.ts.net` from any of your devices,
with no port open on any router. `planetai mesh status` shows the tailnet; `planetai mesh down` leaves it. When a
district node exists, `PARENT_API_URL` is its tailnet hostname.

On Linux it turns on Tailscale SSH, so `ssh <name>` needs no keys; on a Mac it is ordinary `ssh` over the tailnet,
with Remote Login on. Where a third-party coordinator is ruled out, self-hosted Headscale replaces only the login
server.

## Meshtastic

One gateway radio with WiFi uplinks the mesh to a broker on the node, field radios carry sensors on batteries, and a
shelf radio paired to a phone receives alerts with no internet. A LoRa frame is about 200 bytes, a few a minute,
enough for telemetry and one-line alerts. Everything about the radios is on [Radios](MESHTASTIC.md).

## Reticulum

The bridge container gives the node an LXMF address. It lives in its own repository, [`fabcity/planetai-reticulum`](https://github.com/fabcity/planetai-reticulum), which
`planetai reticulum` fetches at a pinned commit and builds on the node. `act <id>` sent from Sideband records an action, and alerts go
to `RETICULUM_ALERT_DESTINATIONS`. With `RETICULUM_PRESENCE=1` it also announces, every half hour, the node's name
and its H3 cell rounded to `RETICULUM_PRESENCE_RES` (3 by default, never finer than 6). It runs over TCP; an RNode
LoRa interface is a commented block in its `config.tpl`, which becomes `config/reticulum/config`. `rns` and `lxmf` are pinned and are under the Reticulum License,
which is not an open licence: [docs/decisions/2026-10-23-reticulum-licence.md](decisions/2026-10-23-reticulum-licence.md).

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
value, a parent gets hourly means, and alerts go to the people who act on them.
