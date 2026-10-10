"""Runtime settings: the database overlays the environment.

  get(key, default)   the DB value if the GUI set one, else the environment, else default. Cached 20 s.
  set(key, value)     write; the next get() sees it within 20 s. No restart for anything in RUNTIME, or for a key an
                      installed pack declares, which is also put into the environment the pack reads.
  describe()          what the GUI shows: every editable key with its group, label, whether it is a secret,
                      whether it needs a restart, and its current (masked) value.

Two classes of key, and the distinction is the whole design:
  RUNTIME   read through get() by the code, so a change takes effect on the next poll or rule pass.
  BOOTSTRAP read once by Docker or the process at start (ports, database, compose profiles). The GUI shows
            them read-only with the instruction to edit .env and run `planetai restart`.
"""
from __future__ import annotations

import logging
import os
import time

DB = os.getenv("DATABASE_URL", "postgresql://planetai:planetai@db:5432/planetai")
log = logging.getLogger("planetai.settings")
_cache: dict = {"at": 0.0, "rows": {}}
TTL = 20

# key -> (group, label, secret?, restart?, help)
#
# THE ORDER OF THIS DICT IS THE ORDER OF THE SETTINGS UI, on every surface. `planetai config`'s
# walk, `planetai config list` and the dashboard's Set up tabs all take their groups from
# describe(), first-seen, so there is one order and it is declared here. Keep each group's keys
# together: all three surfaces print a heading when the group changes, and a key that strays into
# another group's block prints a second heading for a group that already had one.
#
# The groups are the tasks of the person setting a node up, not the modules of the code (28 Sep 2026: Set up had
# nine tabs in the code's own order, and a keeper looking for "the tokens" found them in three of them). `basics`
# is first and NODE_ISSUES leads it, because it is the one setting that says what this place is for. Every secret
# is in `keys`, everything that leaves the machine in `sharing`, and the numbers nobody needs on day one in
# `system`.
RUNTIME = {
    # basics — what this place is, what it watches, and how its page opens. What matters here is decided by the people who live here.
    "NODE_ISSUES":        ("basics", "What this place watches, in order", False, False,
                           "The issues this node reports, most important first: air, heat, land, coast. The first "
                           "one is where the page starts, and the one with something to say takes the top of it. A "
                           "name nothing declares is ignored with a line in the log; blank means every issue there "
                           "is, in the packs' own order. Your preset guessed for this place \u2014 change it: what "
                           "matters here is decided by the people who live here, not by which pack was written first."),
    "NODE_KIND":          ("basics", "Kind", False, False, "home | business | community | district."),
    "ALERT_LOCALE":       ("basics", "Alert language", False, False, "en, id or es. The alert rules, the reports, the test alert and the bot's own replies; the dashboard and the terminal stay in English. Anything else falls back to English."),
    "UI_MODE":            ("basics", "How much of the page is shown", False, False,
                           "simple = one sentence per stage, written by this node, and nothing else: for a phone, "
                           "a visitor, or anybody who wants the answer rather than the working. advanced (default) = "
                           "every section. learn = the advanced page with a question mark at each part, which opens "
                           "the node's own documentation for it. This is what the page opens as; anyone reading it "
                           "can switch from the header, and their choice is remembered by their browser and changes "
                           "nothing for anybody else."),
    # sources — sensors and data: what the node reads. Sources that come as packs keep their settings in their pack's card.
    "SC_USER":            ("sources", "Smart Citizen username", False, False, "Every kit on the account is read as yours, indoor or outdoor from each kit's own setting."),
    "SC_DEVICES":         ("sources", "Smart Citizen kit ids", False, False, "Comma-separated. Always treated as yours, at this address."),
    "SC_EXCLUDE":         ("sources", "Smart Citizen kits to leave out", False, False, "Comma-separated ids of account kits that belong to another site."),
    "AIRGRADIENT_HOSTS":  ("sources", "AirGradient hosts", False, False, "Hostnames or IPs on your WiFi, comma-separated. Read directly, no cloud."),
    "PURPLEAIR_HOSTS":    ("sources", "PurpleAir hosts", False, False, "IP addresses on your WiFi."),
    "SENSOR_INDOOR":      ("sources", "LAN sensors are indoors", False, False, "1 if the AirGradient/PurpleAir units are inside."),
    "MESH_INDOOR_NODES":  ("sources", "Indoor mesh radios", False, False, "Meshtastic node ids that are inside, e.g. !8f491db0,!64e0bfd1."),
    "BAD_ENABLED":        ("sources", "Bali Air Dispatch", False, False, "Bali only: the island's public stations as outdoor reference. 1 or 0."),
    "BAD_EXCLUDE":        ("sources", "Stations to leave out", False, False, "Comma-separated station ids that are ours and the identity and distance rules missed."),
    "BAD_INCLUDE_INDOOR": ("sources", "Keep indoor stations", False, False, "1 to keep stations the archive suspects are indoors. Off by default: they are not the ring."),
    "OPENMETEO_ENABLED":  ("sources", "Global models (Open-Meteo, CAMS)", False, False, "Free, key-free, anywhere. 1 or 0."),
    "CKAN_PORTALS":       ("sources", "Open-data portals", False, False, "slug=url pairs, comma-separated. Feeds Governance|City."),
    # alerts — alerts and reports: when the node speaks, what interrupts, and how a loop is closed.
    "TELEGRAM_CHAT_IDS":  ("alerts", "Telegram chat ids", False, False, "Comma-separated. planetai telegram finds yours."),
    "TELEGRAM_BUTTONS":   ("alerts", "Event buttons in Telegram", False, False, "1 = event messages carry Done / Not now / Doesn't fit. The bot sets this on startup so the buttons ride only while somebody answers them; leave it alone."),
    "REPORT_EVERY":       ("alerts", "Report every", False, False, "Hours between reports: 3, 4, 6, 8, 12 or 24. Default 6, which is four a day."),
    "REPORT_ANCHOR":      ("alerts", "First report of the day", False, False, "The local hour the rhythm starts from, 0-23. Default 6: with a 6-hour interval that is 06, 12, 18 and 00."),
    "REPORT_DEPTH":       ("alerts", "How much the report says", False, False, "auto, brief, standard or deep. auto lets the strongest model the node can reach decide. Until a model is in the path every report is the node's own, and this changes nothing."),
    "ALERT_LEVEL":        ("alerts", "Interrupt me for", False, False, "act = only when something needs doing (default) · warn = also when something changed · info = everything. Everything is recorded, on the dashboard, and in the next report."),
    "QUIET_HOURS":        ("alerts", "Quiet hours", False, False, "1 = between the hours below, only act-level alerts are sent; the rest wait for the morning report."),
    "QUIET_FROM":         ("alerts", "Quiet from", False, False, "Local hour, default 22."),
    "QUIET_TO":           ("alerts", "Quiet until", False, False, "Local hour, default 6."),
    "ALERT_ENGINE":       ("alerts", "Alert engine", False, False,
                           "rules = every rule sends on its own, as before (default). shadow = the event engine "
                           "(docs/SPEC_alerts.md) decides what it would send and records it, and sends nothing; "
                           "the rules keep sending. events = the event engine sends the heat and air messages, one "
                           "per event (no buttons yet), and the old heat and air rules are recorded but not sent; "
                           "every other alert and the reports are unchanged."),
    "ALERT_MAX_PER_DAY":  ("alerts", "Most messages a day", False, False,
                           "With the event engine: pushes a day outside danger, default 4. Beyond it an event "
                           "is still recorded and waits for the next report. Danger is never held."),
    "HOME_HAS":           ("alerts", "What this home has", False, False,
                           "Comma-separated: purifier, ac, fan, windows (windows that open). The event engine "
                           "only suggests what is here to use."),
    "MESH_ALERTS":        ("alerts", "Alerts over the LoRa mesh", False, False, "1 to send act-level alerts through the gateway radio."),
    "MESH_GATEWAY_NODE_NUM": ("alerts", "Gateway node number", False, False, "Decimal, for mesh downlink."),
    # Off by default, and a community's switch rather than the software's. A node in a house records
    # an act whether or not anybody deliberated first -- somebody smells smoke and opens a window,
    # and a node that refused to record that would be asserting a deliberation that did not happen.
    # A node that acts for more than one household is a different case, and this is where that
    # community says so. See docs/SPEC_decide.md section 10.
    "DECISION_REQUIRED":  ("alerts", "An act needs a decision first", False, False,
                           "0 (default) records an act whenever somebody says they did something. 1 refuses "
                           "one unless a decision was recorded against the same alert first, which is what a "
                           "node acting for a street rather than a house usually wants. It applies to every "
                           "way in -- the dashboard, Telegram, the radio and the terminal -- so turn it on "
                           "only where everybody answering has a screen to decide on."),
    # model — ask and model: which model answers, on the dashboard's ask pane and on Telegram alike.
    "AGENT_PREFER":       ("model", "Model preference", False, True,
                           "private \u2014 nothing leaves your network, and it is what this node does until somebody "
                           "here chooses otherwise. fallback \u2014 your own remote model, then online, then the "
                           "small local one. strongest \u2014 online first, so every question goes to the online "
                           "model whenever a key is set. It decides for the Telegram bot and the dashboard's ask "
                           "pane alike. With fallback or strongest, what somebody asks, and the page's own "
                           "sentences and numbers (never a position, a sensor's name or its id), go to the online "
                           "model's provider, and that is a choice to give up this house's sovereignty over them."),
    "AGENT_REMOTE_URL":   ("model", "Remote model URL", False, True, "A bigger model on another machine of yours, on this network or your tailnet, OpenAI-compatible. Ollama on a laptop: http://<laptop>.local:11434/v1, with Ollama listening beyond the laptop (OLLAMA_HOST=0.0.0.0). exo: http://<host>:8082/v1. Nothing leaves your network."),
    "AGENT_REMOTE_MODEL": ("model", "Remote model", False, True, "e.g. gpt-oss-120b or qwen3:8b"),
    "AGENT_ONLINE_URL":   ("model", "Online model URL", False, True, "https://api.anthropic.com/v1 or https://api.openai.com/v1"),
    "AGENT_ONLINE_MODEL": ("model", "Online model", False, True, "e.g. claude-sonnet-4-6"),
    "UI_ASK":             ("model", "Ask the node, on the dashboard", False, False,
                           "on (default) = a toggle on the dashboard opens a pane that asks this node's own model, on "
                           "this machine, about what the page shows. It reads and never changes anything; a change "
                           "it suggests is a card somebody presses. Nothing anybody types is kept. off = no toggle "
                           "and no pane."),
    # packs — which load, and each pack's own settings, which describe() adds after these from every pack.yaml.
    "PACKS_ENABLED":      ("packs", "Enabled packs", False, False, "Empty = every pack in packs/. Or a comma-separated list of ids."),
    "PACKS_ALLOW_CODE":   ("packs", "Allow code packs", False, False, "1 lets packs with adapter.py run. Read them first."),
    "EE_PROJECT":         ("packs", "Earth Engine project", False, False, "Project id, not the service account number. Blank reads it from the key file."),
    "EE_KEY_FILE":        ("packs", "Earth Engine key file", False, False, "Path inside the container; the file goes in config/."),
    "COAST_MAX_KM":       ("packs", "Coast: max distance to sea, km", False, False, ""),
    # keys — every secret in one place. Each is masked once saved and never shown again.
    "TELEGRAM_BOT_TOKEN": ("keys", "Telegram bot token", True, False, "From @BotFather. Never shown again once saved."),
    "AGENT_REMOTE_KEY":   ("keys", "Remote model key", True, True, "If that server asks for one."),
    "AGENT_ONLINE_KEY":   ("keys", "Online model key", True, True, "The only thing that lets household data leave your network. Your choice."),
    "AGGREGATE_TOKEN":    ("keys", "Token children must present", True, False, "Set this before pointing another node at this one."),
    "BACKUP_TOKEN":       ("keys", "Token for collecting backups", True, False, "Read-only: lets a NAS fetch /backups. Separate from the admin token."),
    "PARENT_TOKEN":       ("keys", "Token for the parent", True, False, ""),
    "ACT_TOKEN":          ("keys", "Token for closing a loop", True, False,
                           "Lets someone in the house record that they acted on an alert (POST /actions) without holding the admin token: it cannot read a secret or change a setting. `planetai ui` prints it."),
    # sharing — sharing and network: who may read this node, and everything it sends or announces beyond this machine.
    "SHARE_LEVEL":        ("sharing", "What a reader without a token may see", False, False,
                           "off (default) = the dashboard shell, /health with the position rounded, the daily export and the layout, and nothing else. "
                           "open = the whole read API to anyone on your network, so a wall screen or a phone works with no token; writes still need one. "
                           "cell and means are reserved and refused today: cell will answer the neighbouring H3 cells that ask, means will hand hourly means to a parent node. "
                           "This never changes what a request carrying a token may read, from anywhere \u2014 the NAS, Home Assistant and the agent are unaffected at every level."),
    "MAP_TILES":          ("sharing", "Live map tiles", False, False, "Satellite and street view tiles from the internet. Each tile request tells a tile server which square of the planet this house is looking at. off (default) = tiles from the node's local copy of OpenStreetMap; on = live tiles. A keeper turns this on in Set up."),
    "UPDATE_CHECK":       ("sharing", "Tell me when a new version is out", False, False,
                           "on (default) = once a day the node asks planetai.fab.city which version is current, with a plain "
                           "request that carries nothing about this house. It does show Fab City's host this house's internet "
                           "address and that a PLANETAI node lives there. When a newer version is out, the page's header says so, "
                           "`planetai doctor` says so, and Telegram says so once per version. Nothing is installed: "
                           "`planetai update` stays yours to run. off = the node never asks."),
    # Presence: the node saying "I am here" on Reticulum, and nothing else. Off by default, because
    # SHARE_LEVEL governs what this node ANSWERS when asked and this is the node speaking unprompted.
    "RETICULUM_PRESENCE":  ("sharing", "Announce this node on Reticulum", False, False,
                            "1 announces the node's name and a COARSE map cell every half hour, so other "
                            "PLANETAI nodes can see that it exists and how far away it is. No readings, no "
                            "address, nothing else — and nothing at all while this is 0."),
    "RETICULUM_PRESENCE_RES": ("sharing", "How exactly the announce places this node", False, False,
                               "The H3 resolution the announced cell is rounded to, and the whole of the "
                               "privacy decision. 3 is about 60 km across and says the island; 4 is about "
                               "22 km; 5 about 8 km; 8 is this street. Default 3. Anything finer than 6 is "
                               "refused, because a node announcing its street to an open radio network is "
                               "not a thing to do by typing a number."),
    "RETICULUM_ALERT_DESTINATIONS": ("sharing", "Reticulum alert addresses", False, False, "LXMF hashes, comma-separated."),
    "HA_DISCOVERY":       ("sharing", "Home Assistant", False, False, "1 publishes sensors and alerts as HA entities over MQTT (needs the broker)."),
    "SC_FORWARD":         ("sharing", "Forward to Smart Citizen", True, False,
                           "Device tokens, comma-separated, of the kits and DIY nodes that publish to this node's broker "
                           "(`planetai broker`) and whose messages this node passes on to smartcitizen.me unchanged, so the "
                           "device keeps its page there and the campaign dashboards keep reading it. Blank = nothing is "
                           "forwarded. A token is a credential: it is masked here and never appears in a sensor id."),
    "PARENT_API_URL":     ("sharing", "Parent node", False, False, "http://<district>:8080 — hourly means go here. Empty = none."),
    # system — tuning numbers, and the layout Arrange mode writes. Not "advanced": that is a page mode, and the header has its switch.
    "LOCAL_RADIUS_M":     ("system", "Local radius, m", False, False, "how far from the node a sensor can be and still count as this node's own, in metres"),
    "BAD_RADIUS_KM":      ("system", "Bali Air Dispatch radius, km", False, False, "How far out the ring of other people's stations reaches."),
    "BAD_MIN_SEPARATION_M": ("system", "Nearest a station may be, m", False, False, "A station closer than this to the node is assumed to be our own hardware, not a neighbour."),
    "STATIONS_SHOWN":     ("system", "Other people's stations listed", False, False,
                           "How many of the neighbourhood's stations the dashboard lists, nearest first. Default 3; "
                           "0 lists every one. This node's own hardware is always listed and is never counted here \u2014 "
                           "a house hiding its own sensors behind a press would be absurd. Nothing is discarded or "
                           "stopped: the page says how many it is not listing and one press lists them all. To collect "
                           "fewer stations in the first place, turn the Bali Air Dispatch radius down instead."),
    "UI_GROUND":          ("system", "How the ground is drawn", False, False,
                           "svg (default) = the drawing this page has always made. map = MapLibre and deck.gl draw it "
                           "in this browser, so it pans and zooms; it needs WebGL2 and falls back to svg, saying why, "
                           "without it. Neither one changes what leaves the house: MAP_TILES still decides that."),
    "UI_LAYOUT":          ("system", "Dashboard layout", False, False, "Order and visibility of the dashboard's cards, as JSON. Managed by the dashboard's Arrange mode; blank restores the default."),
}
# What an anonymous reader on the LAN may see the value of. Everything else shows as "•••• set" until the admin token is
# presented (the dashboard's Set up view sends it once unlocked). Chat ids, sensor hosts, account names and remote URLs
# are not secrets, but they are the household's, and GET /settings answers anyone on the WiFi (found 6 Sep 2026).
PUBLIC = {"REPORT_EVERY", "REPORT_ANCHOR", "REPORT_DEPTH", "ALERT_LEVEL", "QUIET_HOURS", "QUIET_FROM", "QUIET_TO", "ALERT_LOCALE",
          "MESH_ALERTS", "HA_DISCOVERY", "PACKS_ENABLED", "PACKS_ALLOW_CODE", "OPENMETEO_ENABLED", "BAD_ENABLED", "BAD_RADIUS_KM",
          "BAD_MIN_SEPARATION_M", "BAD_EXCLUDE", "BAD_INCLUDE_INDOOR",
          "LOCAL_RADIUS_M", "SENSOR_INDOOR", "COAST_MAX_KM", "AGENT_PREFER", "AGENT_REMOTE_MODEL", "AGENT_ONLINE_MODEL", "UI_LAYOUT", "UI_MODE", "UI_ASK", "UI_GROUND", "MAP_TILES", "UPDATE_CHECK", "STATIONS_SHOWN", "NODE_KIND", "SHARE_LEVEL", "NODE_ISSUES",
          "RETICULUM_PRESENCE", "RETICULUM_PRESENCE_RES"}
# Which Set up tab shows each bootstrap key, read-only. The place itself is Basics; the machinery is System.
BOOTSTRAP_GROUP = {k: "basics" for k in ("NODE_NAME", "NODE_CITY", "NODE_LAT", "NODE_LON", "NODE_TZ", "NODE_SCALE")}

BOOTSTRAP = {
    "NODE_NAME": "Name", "NODE_CITY": "City key", "NODE_LAT": "Latitude", "NODE_LON": "Longitude", "NODE_TZ": "Time zone",
    "NODE_SCALE": "Scale", "APP_PORT": "Port", "COMPOSE_PROFILES": "Extra containers", "MQTT_HOST": "Broker",
    "BACKUP_DIR": "Backups", "BACKUP_REMOTE": "Off-machine copy", "BACKUP_KEEP": "Days of backups kept", "DATA_DIR": "Database location", "EXPORT_ENABLED": "Daily export", "IPFS_PUBLISH": "IPFS", "POLL_SECONDS": "Poll interval",
}

# Values a key refuses. Most settings are free text on purpose — a node has to keep running through a typo — but a
# report interval the scheduler cannot honour would make the node silent instead of wrong, which is worse. The help
# text above is where the accepted values are written; the refusal quotes it rather than keeping a second copy.
CHOICES = {
    "REPORT_EVERY":  ("3", "4", "6", "8", "12", "24"),      # each divides 24, so the rhythm does not walk round the clock
    "REPORT_ANCHOR": tuple(str(h) for h in range(24)),
    "REPORT_DEPTH":  ("auto", "brief", "standard", "deep"),
    "ALERT_ENGINE":  ("rules", "shadow", "events"),
    "UI_MODE":       ("simple", "advanced", "learn"),
    # private first because it is the default and because the order is what every surface offers: `describe()`
    # publishes this tuple and the dashboard's select and `planetai config` both walk it as given.
    "AGENT_PREFER":  ("private", "fallback", "strongest"),   # a typo here would fail open: not-"private" sends household data off the network
    "SHARE_LEVEL":   ("off", "open"),                        # cell and means are named in the help and refused here, so a node cannot sit at a level that does nothing
    "UI_ASK":        ("on", "off"),
    "UI_GROUND":     ("svg", "map"),
    "MAP_TILES":     ("off", "on"),                          # live tiles leave the house; off by default, a keeper turns them on in Set up
    "UPDATE_CHECK":  ("on", "off"),                          # a daily request to planetai.fab.city; on by default (Tomas, 30 Sep 2026)
}

# Keys that change what leaves this machine, as opposed to what it does with what it keeps.
#
# Every surface renders these in the same box as COAST_MAX_KM today, so the setting that decides
# whether the whole read API answers a stranger on the WiFi looks exactly like the one that says how
# far the sea is. A household deciding what to share should be able to see which decisions those are.
# The node declares the set because the node is the one that acts on it; a surface can mark them or
# not, but it should not have to guess which they are.
OUTWARD = {
    "SHARE_LEVEL",          # what a reader with no token may read from this node
    "PARENT_API_URL",       # where hourly means are posted
    "CKAN_PORTALS",         # open-data portals this node reads from and publishes cells for
    "RETICULUM_PRESENCE",   # the node announcing its existence and a coarse cell over radio
    "RETICULUM_PRESENCE_RES",  # how precisely it does so
    "RETICULUM_ALERT_DESTINATIONS",  # where act-level alerts are sent
    "MESH_ALERTS",          # alerts over the LoRa mesh, which is not this household's network
    "HA_DISCOVERY",         # sensors and alerts published to the MQTT broker
    "SC_FORWARD",           # a device's own readings passed on to smartcitizen.me
    "AGENT_ONLINE_URL", "AGENT_ONLINE_MODEL", "AGENT_ONLINE_KEY",  # the one path off the network
    "AGENT_PREFER",         # which decides whether the online path is used at all
    "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_IDS",  # where the node speaks
    "UPDATE_CHECK",         # a daily request to planetai.fab.city for the current version
}

# Keys the reports release retired. Rows for them are left in `settings` and in .env, and nothing reads them: a
# household that updates does not have a value it chose deleted out from under it. BRIEF_HOUR was the agent
# container's own third clock and is gone from the compose file.
RETIRED = ("BRIEFINGS", "BRIEF_MORNING", "BRIEF_EVENING", "BRIEF_HOUR")


def _rows() -> dict:
    if time.time() - _cache["at"] < TTL:
        return _cache["rows"]
    try:
        import psycopg
        from psycopg.rows import dict_row
        with psycopg.connect(DB, row_factory=dict_row, autocommit=True) as con, con.cursor() as cur:
            cur.execute("SELECT key, value FROM settings")
            _cache["rows"] = {r["key"]: r["value"] for r in cur.fetchall()}
        _overlay_packs(_cache["rows"])
    except Exception:  # noqa: BLE001 — before the table exists, or db down: fall through to the environment
        pass
    _cache["at"] = time.time()
    return _cache["rows"]


# A pack key's environment value from before a GUI row overrode it; None = it was unset.
_env_before: dict = {}


def _overlay_packs(rows: dict) -> None:
    """Put the GUI's value of every pack-declared key into the process environment, and take it back out when the row
    is deleted. Packs read their keys with os.getenv — that is the pack contract, and their verify and refresh scripts
    run outside the app where this module is not importable — so a row in `settings` that stopped here reached no pack:
    Set up saved MAKE_ENABLED=1 and the make pack went on reading the 0 in .env. A key the GUI never touched is left
    exactly as the environment has it."""
    declared = {r["key"] for r in pack_settings()}
    for k in declared & rows.keys():
        _env_before.setdefault(k, os.environ.get(k))
        os.environ[k] = rows[k]
    for k in _env_before.keys() - rows.keys():
        v = _env_before.pop(k)
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v


def writable(key: str) -> bool:
    """RUNTIME, or a key an installed pack's pack.yaml declares: the same rows describe() publishes as editable. Every
    installed pack, not only the enabled ones, because a pack's own switch (MAKE_ENABLED) is a key of a pack that is
    off, and refusing it would leave the page offering a field the node will not take."""
    return key in RUNTIME or key in {r["key"] for r in pack_settings()}


def get(key: str, default: str = "") -> str:
    v = _rows().get(key)
    if v is not None:
        return v
    return os.getenv(key, default)


def set(key: str, value: str) -> None:  # noqa: A001
    if not writable(key):
        raise KeyError(f"{key} is not a runtime setting, and no installed pack declares it")
    if value and key in CHOICES and value not in CHOICES[key]:
        raise ValueError(f"{value!r} is not a value {key} accepts. {RUNTIME[key][4]}")
    import psycopg
    from psycopg.rows import dict_row
    with psycopg.connect(DB, row_factory=dict_row, autocommit=True) as con, con.cursor() as cur:
        if value == "":
            cur.execute("DELETE FROM settings WHERE key = %s", (key,))       # blank = back to the environment
        else:
            cur.execute("INSERT INTO settings (key, value) VALUES (%s, %s) ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = now()", (key, value))
    _cache["at"] = 0.0


def num(key: str, default: int) -> int:
    """A setting that has to be a number, where the default survives a key that is present but empty. `update.sh`
    merges new keys from `.env.example` with whatever value they carry there, and the REPORT_* keys ship blank so
    that an updating node keeps the rhythm it had instead of silently taking the new default."""
    v = (get(key, "") or "").strip()
    return int(v) if v.isdigit() else default


def brief_migration(current: dict) -> dict:
    """What a node on the old two-briefings schedule should be set to when it updates: the REPORT_* rows to write,
    or nothing at all. Pure, so the test can run this function rather than a copy of its rule.

    A node with BRIEF_MORNING=7 keeps seven o'clock and keeps speaking twice a day; it does not start speaking four
    times a day because someone ran an update. A fresh install has none of the old keys, gets nothing written here,
    and takes 6 and 6 from the defaults."""
    if any((current.get(k) or "").strip() in CHOICES[k] for k in ("REPORT_EVERY", "REPORT_ANCHOR")):
        return {}
    if not any((current.get(k) or "").strip() for k in RETIRED[:3]):
        return {}
    anchor = (current.get("BRIEF_MORNING") or "").strip()
    return {"REPORT_EVERY": "12", "REPORT_ANCHOR": anchor if anchor in CHOICES["REPORT_ANCHOR"] else "6"}


def migrate_briefings() -> dict:
    """Run brief_migration against this node and write what it says. Returns what was written, for the log."""
    current = {k: get(k, "") for k in (*RETIRED, "REPORT_EVERY", "REPORT_ANCHOR")}
    writes = brief_migration(current)
    for k, v in writes.items():
        set(k, v)
    return writes


def _mask(v: str) -> str:
    return ("•••• set" if v else "") if v is not None else ""


# What a fresh node gets, generated from `.env.example` into `data/`, which IS mounted into the
# image — the app is built from `app/`, so a COPY cannot reach the repo root and the container has
# never been able to say what a default IS. tools/gen_defaults.py writes it and `make lint` fails
# when the two disagree, the same arrangement the platform floors have.
_defaults_cache: dict = {}


def defaults() -> dict:
    """`{KEY: {default, help}}`, read once. A node whose image predates this file gets {} and every
    row simply has no `default` — the page says nothing rather than guessing one."""
    if not _defaults_cache:
        # Read at call time, not at import: a path frozen when the module loads cannot be pointed
        # anywhere else afterwards, which is fine in a container and wrong everywhere else.
        path = os.getenv("ENV_DEFAULTS", "/app/data/env_defaults.yml")
        try:
            import yaml                              # noqa: PLC0415
            with open(path) as fh:
                _defaults_cache.update(yaml.safe_load(fh.read()) or {})
        except Exception:                            # noqa: BLE001 — no defaults is not an outage
            _defaults_cache["_"] = {}
    return _defaults_cache


def _env_lines(lines) -> list[tuple[str, str, str]]:
    """`[(KEY, default, help)]` from a block of `# comment` and `KEY=value` lines.

    This is the shape both `.env.example` and a pack.yaml `env:` list are already written in —
    comments above the key they describe, which `make lint` enforces for the first of them. So the
    help text and the default a pack publishes are read from the pack rather than copied into this
    file, where they would be a second version of the same sentence with nothing holding them level.
    """
    out, note, started = [], [], False
    for raw in lines:
        s = str(raw).strip()
        if s.startswith("#"):
            if started:                              # a new block after a key ends the last one
                note, started = [], False
            note.append(s.lstrip("#").strip())
            continue
        if "=" not in s:
            note, started = [], False
            continue
        k, _, v = s.partition("=")
        k = k.strip()
        if k and k.replace("_", "").isalnum() and k.isupper():
            out.append((k, v.strip(), " ".join(n for n in note if n)))
            started = True
        # The block is NOT cleared here. These files are written with one comment covering a run of
        # related keys — "radius around the node, and how often to re-fetch" sits above both
        # PLACE_RADIUS_M and PLACE_REFRESH_DAYS — so clearing after the first of them sends the
        # second to Set up with nothing said about it. A blank line ends a block; the next comment
        # starts a new one.
    return out


def pack_settings() -> list[dict]:
    """Every key the installed packs declare, whether or not the pack is switched on.

    A PACK'S KEYS NEVER REACHED /settings AT ALL, so the Set up page could not show them and nobody
    could turn a pack on from the dashboard — including the switch whose entire job is to turn the
    pack on. Node #1 had MAKE_ENABLED=1 in its .env and the string MAKE appeared nowhere in its
    settings body. Found 21 September 2026.

    EVERY installed pack, not the enabled ones. `packs.manifests()` filters by PACKS_ENABLED and
    PACKS_ALLOW_CODE, which is right for loading code and exactly wrong here: a keeper cannot enable
    what the page will not show them, and a pack that is off is the one they most need to see.

    Read straight off disk rather than through the loader, so this cannot be the reason /settings
    fails: a pack with a broken pack.yaml costs its own rows and nothing else.
    """
    import glob                                     # noqa: PLC0415
    root = os.getenv("PACKS_DIR", "/app/packs")
    rows = []
    for path in sorted(glob.glob(os.path.join(root, "*", "pack.yaml"))):
        name = os.path.basename(os.path.dirname(path))
        try:
            import yaml                             # noqa: PLC0415
            m = yaml.safe_load(open(path).read()) or {}
        except Exception as e:                      # noqa: BLE001 — one bad pack, not a 500
            # Silently is the wrong kind of tolerant: a pack.yaml that will not parse loses every
            # key it declares from Set up, and the keeper's only symptom is a pack that is not
            # there. Caught while writing this — an invalid escape in a double-quoted YAML scalar
            # dropped the whole forecast pack and nothing said so.
            log.warning("settings: %s has a pack.yaml that will not parse (%s), so none of its "
                        "keys reach Set up", name, e)
            continue
        # A pack names the keys that are secrets (`secrets: [CAMERA_WYZE_BRIDGE_TOKEN]`), and they are treated like the
        # node's own tokens: masked once saved, even to the admin token and the agent's settings tool. Every pack key
        # used to be published as plain text to anyone holding the admin token, a FIRMS key or a bridge token included.
        # frozenset and a list, not set(): this module defines its own set(key, value), which shadows the builtin.
        secrets = frozenset(k for k in m.get("secrets") if isinstance(k, str)) if isinstance(m.get("secrets"), list) else frozenset()
        declared = []
        for key, default, help_ in _env_lines(m.get("env") or []):
            declared.append(key)
            rows.append({"key": key, "pack": name, "default": default, "help": help_, "secret": key in secrets})
        for key in sorted(k for k in secrets if k not in declared):
            log.warning("settings: %s lists %s under secrets: but declares no such key under env:", name, key)
    return rows


def describe(unlocked: bool = False, public: frozenset | set = PUBLIC) -> dict:
    """unlocked=False is what an anonymous GET /settings gets: secrets masked, and every value outside PUBLIC masked too.
    unlocked=True (admin token presented, or an MCP call, which is behind the token already) shows all but the secrets.

    `public` narrows that set without narrowing the rows: at SHARE_LEVEL=off a caller who is neither on this machine
    nor carrying a token gets UI_LAYOUT and SHARE_LEVEL only — the layout because every screen in the house reads it,
    SHARE_LEVEL because a screen being refused needs to be able to name what is refusing it."""
    db = _rows()
    out = {"unlocked": unlocked, "runtime": [], "bootstrap": []}
    for k, (group, label, secret, restart, help_) in RUNTIME.items():
        v = get(k, "")
        hide = secret or (not unlocked and k not in public)
        out["runtime"].append({"key": k, "group": group, "label": label, "secret": secret, "restart": restart, "help": help_,
                               "value": _mask(v) if hide else v, "set": bool(v), "source": "gui" if k in db else ("env" if os.getenv(k) else "default"),
                               # What this key will accept, so a surface can offer the values instead of letting
                               # somebody type one it will refuse. CHOICES is already the authority for the refusal;
                               # publishing it means the dashboard's widget and the node's validation cannot disagree.
                               "choices": list(CHOICES[k]) if k in CHOICES else None,
                               # None when the image has no defaults file, never a guess.
                               "default": (defaults().get(k) or {}).get("default"),
                               "outward": k in OUTWARD})
    # The packs' own keys, after the node's. They carry a `default` because pack.yaml states one
    # beside every key; the node's own rows do not, which is the other half of this gap and needs
    # somewhere in the image to read them from — `.env.example` is at the repo root and the app
    # image is built from `app/`, so the container cannot see it.
    # `db` is already the dict of gui-set rows and `set` is this module's own setter, so the
    # obvious `set(db)` calls it with one argument and raises.
    by_key = {r["key"]: r for r in out["runtime"]}
    for r in pack_settings():
        k = r["key"]
        if k in by_key:
            # EE_PROJECT, EE_KEY_FILE and COAST_MAX_KM are RUNTIME keys a pack also declares. They were drawn twice,
            # once in the node's own group and once in the pack's; now once, in the pack's card, with the pack's
            # words where the node has none.
            by_key[k].update(pack=r["pack"], help=by_key[k]["help"] or r["help"],
                             default=by_key[k]["default"] if by_key[k]["default"] is not None else r["default"])
            if r.get("secret") and not by_key[k]["secret"]:
                by_key[k].update(secret=True, value=_mask(get(k, "")))
            continue
        v = get(k, "")
        secret = bool(r.get("secret"))
        hide = secret or (not unlocked and k not in public)
        out["runtime"].append({
            # restart False: _overlay_packs puts a GUI value into the environment the pack reads, so it is in
            # force at the pack's next run, within 20 s, like any RUNTIME key.
            "key": k, "group": "packs", "label": k, "secret": secret, "restart": False,
            "help": r["help"], "value": _mask(v) if hide else v, "set": bool(v),
            "source": "gui" if k in db else ("env" if os.getenv(k) else "default"),
            "choices": None, "outward": k in OUTWARD,
            "default": r["default"], "pack": r["pack"]})
    for k, label in BOOTSTRAP.items():
        out["bootstrap"].append({"key": k, "label": label, "value": os.getenv(k, ""),
                                 "group": BOOTSTRAP_GROUP.get(k, "system")})
    return out
