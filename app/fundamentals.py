"""The sources every node needs for its basic job, and how to tell each one is running.

One list, here. GET /health/sources reads it; `planetai doctor`, install.sh and update.sh (through the doctor), the
Set up page and an agent read that route — so the fix a household is given is written once, in this file.

The order is the order of "To finish setting up": most important first. A node with no sensor of its own measures
nothing here; a node nobody hears from is a log file; the rest are what it compares against and how it keeps its past.

States, one per source:
  ok        a reading inside its window (`fresh_minutes`), or a backup that young
  missing   not set up. `fix` says how.
  quiet     set up, and nothing inside its window. `fix_quiet` says what to look at.
  waiting   set up, nothing yet, and the node has not finished a poll since it started: after an install or an update
            the first reading is minutes away, and calling that a fault would put a cross on every new node.
  na        does not apply here (public stations where no installed pack reads a network yet)
  elsewhere the backups are kept outside this container (BACKUP_DIR); the doctor on the machine judges them
The map is fetched once, not read: ok with the day it was fetched, or missing.
`ok` is true, false or null (waiting, na, elsewhere): only false asks somebody to do something.
"""
from __future__ import annotations

import calendar
import json
import os
import time
from pathlib import Path

HOUR = 60

FUNDAMENTALS = [
    {"id": "own-sensors", "name": "Your own sensors", "fresh_minutes": HOUR,
     "why": "The air in this home, measured here. Everything else is somebody else's number or a model.",
     "settings": ["SC_DEVICES", "SC_USER", "AIRGRADIENT_HOSTS", "PURPLEAIR_HOSTS"], "setup": "sources", "command": None,
     "fix": "Add your sensor in Set up › Sources: a Smart Citizen kit number, or the address of an AirGradient or "
            "PurpleAir on your WiFi. Or in the terminal: planetai config --section sources",
     "fix_quiet": "Your sensor is set up but has not reported in the last hour. Check it has power and WiFi; "
                  "planetai sensors shows when each one last spoke."},
    {"id": "alerts", "name": "Alerts on your phone (Telegram)", "fresh_minutes": None,
     "why": "How the node tells you to do something. Until it is connected, alerts only reach the log.",
     "settings": ["TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_IDS"], "setup": "keys", "command": "planetai telegram",
     "fix": "Connect Telegram, two minutes: planetai telegram",
     "fix_quiet": "Telegram refused the last message: the bot's token may have been revoked. Run planetai telegram again."},
    # Whose stations is a pack's (pack.yaml `stations:`, packs.stations()); {name} and {switch} are that pack's.
    {"id": "nearby-stations", "name": "Air stations nearby", "fresh_minutes": 3 * HOUR,
     "why": "The street around you, from other people's stations, so one kit can tell a fire in the lane from haze over the island.",
     "settings": [], "setup": "packs", "command": None,
     "fix": "Turn on {name} in Set up › Packs. Or: planetai config set {switch} 1",
     "fix_quiet": "{name} has not answered in three hours. Is the internet up? planetai logs names the error."},
    {"id": "weather", "name": "Weather (Open-Meteo)", "fresh_minutes": 3 * HOUR,
     "why": "Temperature, humidity, wind and rain at this point from a global model, free and anywhere.",
     "settings": ["OPENMETEO_ENABLED"], "setup": "sources", "command": None,
     "fix": "Turn on Global models in Set up › Sources. Or: planetai config set OPENMETEO_ENABLED 1",
     "fix_quiet": "Open-Meteo has not answered in three hours. Is the internet up? Its free service also stops "
                  "answering an address that asks too often in a day; planetai logs names the error."},
    {"id": "satellite-air", "name": "Satellite air (CAMS)", "fresh_minutes": 3 * HOUR,
     "why": "Modelled PM2.5 at this point from satellites: what your own sensor is compared against.",
     "settings": ["OPENMETEO_ENABLED"], "setup": "sources", "command": None,
     "fix": "Turn on Global models in Set up › Sources. Or: planetai config set OPENMETEO_ENABLED 1",
     "fix_quiet": "CAMS (through Open-Meteo) has not answered in three hours. Is the internet up? planetai logs names the error."},
    {"id": "backup", "name": "Nightly backup", "fresh_minutes": 2 * 24 * HOUR,
     "why": "The only copy of this home's record that survives the disk.",
     "settings": [], "setup": None, "command": "planetai backup",
     "fix": "No backup yet. One runs every night at 03:17; to have one now: planetai backup",
     "fix_quiet": "No backup in two days. Make one now: planetai backup, then check the nightly one: crontab -l | grep backup"},
    # Tomas, 19 Oct 2026: "how to add the open street maps tiles? I dont find how to set it up, it should be one of the
    # basic setup steps." Fetched once (packs/place/basemap.py), so it is there or it is not: never quiet, never waiting.
    {"id": "map", "name": "The map of this place", "fresh_minutes": None,
     "why": "Streets, buildings and their names round the node, kept on its own disk, so the Place door and the Wall "
            "draw where things are and ask nobody for a tile.",
     "settings": [], "setup": None, "command": "planetai run place basemap",
     "fix": "No map yet. Fetch it once, a few minutes: planetai run place basemap. build.protomaps.com and "
            "OpenAerialMap learn roughly where this node is (the square fetched); after that nothing is sent.",
     "fix_quiet": None},
]

# which source's rows judge a fundamental, and which adapter (sources.enabled) names its last error: the core's adapter is
# named for its source, a pack's adapter by the pack's id (CAMS is packs/air-quality's since 24 Oct 2026)
SOURCE = {"weather": "open-meteo", "satellite-air": "open-meteo-cams"}
ADAPTER = {"weather": "open-meteo", "satellite-air": "air-quality"}


def _age(minutes):
    if minutes is None:
        return "no reading in two days"
    m = int(round(minutes))
    if m < 2:
        return "just now"
    if m < 120:
        return f"{m} min ago"
    return f"{m // 60} h ago" if m < 48 * 60 else f"{m // 1440} days ago"


def _errors(last_error: str | None) -> dict:
    """poll_once joins failures as 'name: message | name: message'."""
    out = {}
    for part in (last_error or "").split(" | "):
        name, sep, msg = part.partition(": ")
        if sep:
            out[name.strip()] = msg.strip()
    return out


def assess(cfg: dict, seen: list[dict], polled: bool, last_error: str | None = None,
           telegram_ok: bool | None = None, backup_minutes: float | None = None, backup_here: bool = True,
           own_known: bool = False, stations: list[dict] | None = None, map_at: float | None = None) -> list[dict]:
    """Pure: the state of every fundamental source.

    cfg            the effective settings this needs (settings.get), plus NODE_LAT/NODE_LON and MQTT_HOST
    seen           rows {source, own, indoor, minutes}: the youngest reading in two days, per source and kind
    polled         the node has finished at least one poll since it started
    telegram_ok    the last message to Telegram went through (True), was refused (False), or none was sent yet (None)
    backup_minutes the age of the newest dump the app can see, None when there is none
    backup_here    False when BACKUP_DIR points outside ./backups, which is the only folder this container sees
    own_known      the node has ever stored a sensor of this household's own (a kit on MQTT needs no setting)
    stations       packs.stations(): the enabled packs that read public stations, each with `box`, `switch`, `on`
    map_at         when the street map's fetch finished (epoch seconds, map_fetched), None when the node has no map
    """
    on = lambda k: (cfg.get(k) or "").strip() not in ("", "0")  # noqa: E731
    errs = _errors(last_error)

    def youngest(pred):
        ages = [r["minutes"] for r in seen if pred(r) and r.get("minutes") is not None]
        return min(ages) if ages else None

    out = []
    for f in FUNDAMENTALS:
        fid, fresh = f["id"], f["fresh_minutes"]
        minutes, detail, configured, applies, adapter, words = None, "", True, True, ADAPTER.get(fid, ""), {}
        if fid == "own-sensors":
            configured = any(on(k) for k in f["settings"]) or on("MQTT_HOST") or own_known
            minutes = youngest(lambda r: r["own"])
            inside, outside = youngest(lambda r: r["own"] and r["indoor"]), youngest(lambda r: r["own"] and not r["indoor"])
            detail = ("inside and outside" if inside is not None and outside is not None else
                      "inside only; one outside would tell the house from the street" if inside is not None else
                      "outside only; one inside would say what you breathe" if outside is not None else "")
        elif fid == "alerts":
            configured = on("TELEGRAM_BOT_TOKEN") and on("TELEGRAM_CHAT_IDS")
        elif fid == "nearby-stations":
            try:
                lat, lon = float(cfg.get("NODE_LAT") or "nan"), float(cfg.get("NODE_LON") or "nan")
            except ValueError:
                lat = lon = float("nan")
            inside = lambda b: isinstance(b, list) and len(b) == 4 and b[0] < lat < b[1] and b[2] < lon < b[3]  # noqa: E731
            here = [s for s in stations or [] if s.get("on") or inside(s.get("box"))]
            on = [s for s in here if s.get("on")]
            applies, configured = bool(here), bool(on)
            mine = {s["source"] for s in on}
            minutes = youngest(lambda r: r["source"] in mine)
            first = (on or here or [{}])[0]
            adapter, words = first.get("pack", ""), {"name": first.get("name", ""), "switch": first.get("switch", "")}
        elif fid in ("weather", "satellite-air"):
            configured = (cfg.get("OPENMETEO_ENABLED") or "1") == "1"
            minutes = youngest(lambda r: r["source"] == SOURCE[fid])
        elif fid == "backup":
            minutes, configured = backup_minutes, backup_minutes is not None
        elif fid == "map":
            configured = map_at is not None
            if configured:
                t = time.localtime(map_at)
                detail = f"fetched {t.tm_mday} {time.strftime('%b %Y', t)}"

        if not applies:
            state, ok = "na", None
            detail = "no public station network this node can read here yet; the satellite model is the outdoor reference"
        elif fid == "backup" and not backup_here:
            state, ok, detail = "elsewhere", None, "kept outside this container (BACKUP_DIR); planetai doctor checks it on the machine"
        elif not configured:
            state, ok, detail = "missing", False, "not set up"
        elif fid == "map":
            state, ok = "ok", True
        elif fid == "alerts":
            state, ok = ("quiet", False) if telegram_ok is False else ("ok", True)
            detail = {True: "the last message went through", False: "", None: "set up; nothing sent since the node started"}[telegram_ok]
        elif minutes is not None and minutes <= fresh:
            state, ok = "ok", True
        elif not polled and fid != "backup":
            state, ok, detail = "waiting", None, "set up; the first reading arrives after the node's first poll, within a few minutes"
        else:
            state, ok = "quiet", False
        err = errs.get(adapter, "")
        if state == "quiet" and err:
            detail = f"last error: {err}"
        out.append({"id": fid, "name": f["name"], "state": state, "ok": ok,
                    "minutes": None if minutes is None else round(minutes, 1),
                    "age": _age(minutes) if state in ("ok", "quiet") and fid not in ("alerts", "map") else None,
                    "detail": detail or None,
                    "fix": None if ok is not False else (f["fix"] if state == "missing" else f["fix_quiet"]).format(**words),
                    "setup": f"#setup/{f['setup']}" if f["setup"] else None, "command": f["command"], "why": f["why"]})
    return out


def backup_age(folder: str = "/app/backups") -> float | None:
    """Minutes since the newest dump in the folder this container can see, or None."""
    p = Path(folder)
    dumps = [x.stat().st_mtime for x in p.glob("*.sql.gz")] if p.is_dir() else []
    return (time.time() - max(dumps)) / 60 if dumps else None


def map_fetched(folder: str = "/app/out/ground") -> float | None:
    """When the street map's fetch finished, or None: no map, or a fetch that stopped half way. packs/place/basemap.py
    writes meta.json's vector.fetched last, after the tiles and the label fonts, so the tiles alone are not a map."""
    p = Path(folder)
    try:
        at = json.loads((p / "meta.json").read_text())["vector"]["fetched"]
        return calendar.timegm(time.strptime(at, "%Y-%m-%dT%H:%M:%SZ")) if (p / "vector.mbtiles").is_file() else None
    except (OSError, ValueError, KeyError, TypeError):
        return None


def backup_is_here() -> bool:
    """docker-compose.yml mounts ./backups at /app/backups and nothing else: a BACKUP_DIR elsewhere is invisible here."""
    d = (os.getenv("BACKUP_DIR") or "./backups").strip().rstrip("/")
    return d in ("./backups", "backups")
