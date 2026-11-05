"""Where an alert goes: Telegram, the LoRa mesh and the Reticulum bridge (LXMF).

Moved out of app/main.py unchanged (22 Oct 2026). `notify()` is the one call a rule, the report or a route makes; the
mesh and Reticulum get act-level alerts only, Telegram gets everything. `mesh_state` is written by the MQTT thread in
main, the same dict, because a downlink needs the root topic an uplink taught it. Home Assistant is a pack since 22 Oct
2026 (packs/home-assistant): it hears every alert and every stored reading through packs.emit.
"""
import logging
import os
import time
import unicodedata

import httpx

import settings
import sources

log = logging.getLogger("planetai")

NODE = os.getenv("NODE_NAME", "node")
MQTT_HOST = os.getenv("MQTT_HOST", "").strip()
MQTT_USER, MQTT_PASS = os.getenv("MQTT_USER", ""), os.getenv("MQTT_PASS", "")
RETICULUM_URL = os.getenv("RETICULUM_URL", "").strip()


def TG():
    """Token and chat ids, read at send time so the GUI can change them without a restart."""
    return settings.get("TELEGRAM_BOT_TOKEN", "").strip(), [c for c in settings.get("TELEGRAM_CHAT_IDS", "").replace(" ", "").split(",") if c]
def MESH_ALERTS():
    return settings.get("MESH_ALERTS", "0") == "1"
def MESH_GATEWAY_NUM():
    return int(settings.get("MESH_GATEWAY_NODE_NUM", "0") or 0)
mesh_state = {"root_topic": None, "gateway": None, "packets": 0, "last": None}

# Whether the last message to Telegram went through, for GET /health/sources. Kept apart from `state`, which /health
# once spread to every reader at every share level: whether this house's alerts reach it is not theirs to read.
tg_state: dict = {"ok": None, "at": None}


def mesh_send(text: str) -> None:
    """Send `text` over the LoRa mesh via the gateway's MQTT downlink. Needs a root topic learned from an uplink."""
    if not (MQTT_HOST and MESH_ALERTS() and mesh_state["root_topic"]):
        return
    try:
        import paho.mqtt.publish as publish
        topic, payload = sources.meshtastic_downlink(mesh_state["root_topic"], MESH_GATEWAY_NUM(), text)
        publish.single(topic, payload, hostname=MQTT_HOST, auth={"username": MQTT_USER, "password": MQTT_PASS} if MQTT_USER else None)
        log.info("mesh -> sent %d bytes on %s", len(payload), topic)
    except Exception as e:  # noqa: BLE001
        log.warning("mesh send failed: %s", type(e).__name__)


def notify(level: str, text: str, keyboard: list | None = None, home: str = "", home_before_last: bool = False) -> None:
    """Send an alert. `home` is a line for the household's own Telegram only (who in this house it matters to,
    learn.alert_line; the report's morning memory): never the mesh, Reticulum or the log, which other people and
    machines can read. It goes at the end, or above the last paragraph with `home_before_last` (the report's
    invitation stays its last line)."""
    # One sign per message (design review, 14 Oct): a text that opens with its own (📈, ✅, the report's 🌡️) is not
    # given the level's as well; node #1 sent "ℹ️ 🌡️ It is hot inside".
    icon = "" if text[:1] and unicodedata.category(text[0]) == "So" else {"info": "ℹ️", "warn": "⚠️", "act": "🔴"}.get(level, "")
    log.info("ALERT [%s] %s", level, text)
    if level == "act":
        mesh_send(text.split("\n")[0])            # the mesh gets the first line only: LoRa frames are small
        if RETICULUM_URL:
            try:
                httpx.post(f"{RETICULUM_URL}/send", json={"text": text}, timeout=10)
            except Exception as e:  # noqa: BLE001
                log.warning("reticulum send failed: %s", type(e).__name__)
    tok, chats = TG()
    if not tok or not chats:
        return
    for chat in chats:
        try:
            said = f"{icon} {text}".strip()
            head, sep, last = said.rpartition("\n\n") if home and home_before_last else ("", "", said)
            body = {"chat_id": chat, "text": f"{head}\n\n{home}\n\n{last}" if sep else said + (f"\n\n{home}" if home else "")}
            if keyboard:
                body["reply_markup"] = {"inline_keyboard": keyboard}
            url = f"https://api.telegram.org/bot{tok}/sendMessage"
            r = httpx.post(url, json=body, timeout=15)
            if r.status_code == 400 and "reply_markup" in body:
                # the message is never lost over its buttons (SPEC_alerts §7): a keyboard Telegram refuses is dropped once
                log.warning("telegram -> %s refused the keyboard; sending the message without its buttons", chat)
                body.pop("reply_markup")
                r = httpx.post(url, json=body, timeout=15)
            r.raise_for_status()
            log.info("telegram -> %s ok", chat)
            tg_state.update(ok=True, at=time.time())
        except Exception as e:  # noqa: BLE001
            # never interpolate the exception's URL: httpx puts the token in it
            log.warning("telegram -> %s failed: %s", chat, type(e).__name__)
            tg_state.update(ok=False, at=time.time())
