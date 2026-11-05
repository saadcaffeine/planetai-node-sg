#!/usr/bin/env python3
"""planetai radio — provision Meshtastic radios for a node, run the node as their gateway, federate nodes over MQTT.

    planetai radio init      [--region SG_923] [--slot N]     one fleet per node: channel keys, region, frequency slot
    planetai radio url                                        the fleet's channel URL / QR (what the phone app imports)
    planetai radio render    <role> "<long name>" <SHORT>     print the device profile that `provision` would apply
    planetai radio provision <role> "<long name>" <SHORT> --port /dev/cu.usbmodem1101 [--wifi SSID:PSK] [--fixed LAT,LON]
    planetai radio gateway   --port /dev/cu.usbmodem1101     the radio on this USB port becomes the node's gateway
    planetai radio federate  [--write]                        render (and install) the broker's bridge blocks to peer nodes
    planetai radio list                                       the fleet file and, with --port, what the radio sees
    planetai radio doctor    [--port ...]                     the usual reasons nothing arrives, checked one by one

Roles: sensor · relay · shelf · gateway-wifi (ESP32 uplinks over WiFi) · gateway-host (any board on this node's USB).

Everything a radio needs is in one DeviceProfile (`render` prints it). `provision` writes it with the stock CLI, one
settings section per call, reboots the radio and reads it back over a new connection. The fleet file holds the keys,
so it is a credential: config/radio/fleet.yaml, gitignored, next to mosquitto/passwd. Python 3.9, needs
`python3 -m pip install --user meshtastic paho-mqtt` on the host
(not in the container: a USB port does not reach a container on macOS, and node #1 is a Mac mini).
"""
from __future__ import annotations

import argparse
import base64
import json
import logging
import os
import re
import secrets
import shutil
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

log = logging.getLogger("planetai.radio")
# Apple's Python 3.9 is built on LibreSSL, so urllib3 2.x warns on every run. The radio talks over USB and the LAN, and
# the warning only taught people to doubt the output under it.
import warnings  # noqa: E402
warnings.filterwarnings("ignore", message=r"urllib3 v2 only supports OpenSSL")

ROOT = Path(os.getenv("PLANETAI_ROOT", Path(__file__).resolve().parent.parent))
FLEET_PATH = ROOT / "config" / "radio" / "fleet.yaml"
PROFILES_DIR = ROOT / "tools" / "radio_profiles"
MOSQ_DIR = ROOT / "config" / "mosquitto"

# ---------------------------------------------------------------- regions and the frequency slot
# Meshtastic's region table (docs/configuration/radio/lora, read 16 Oct 2026). Only the regions a Fab City node has
# asked for so far; add a line, nothing else changes. There is no Indonesia preset. Indonesia allocates 920–923 MHz
# (the AS923-2 plan), and SG_923 spans 917–925, so a slot chosen by hashing the channel name can land outside the
# allocation. `init` pins the slot inside it instead (see slot_for). KR is 920–923 exactly but carries Korean
# duty-cycle rules; staying on SG_923 with a pinned slot keeps the fleet Bali already runs.
REGIONS: Dict[str, Tuple[float, float]] = {
    "US": (902.0, 928.0), "EU_868": (869.4, 869.65), "EU_433": (433.0, 434.0), "ANZ": (915.0, 928.0),
    "SG_923": (917.0, 925.0), "TH": (920.0, 925.0), "KR": (920.0, 923.0), "MY_919": (919.0, 924.0),
    "JP": (920.5, 923.5), "IN": (865.0, 867.0), "BR_902": (902.0, 907.5), "LORA_24": (2400.0, 2483.5),
}
# What the law allows where a node lives, when it is narrower than the preset. Only entries somebody checked.
ALLOCATION: Dict[str, Tuple[float, float]] = {
    "bali": (920.0, 923.0),      # Indonesia, AS923-2. Check the Kominfo text before relying on the edges.
}
PRESET_BW_KHZ = {"LONG_FAST": 250, "LONG_SLOW": 125, "LONG_MODERATE": 125, "MEDIUM_FAST": 250, "MEDIUM_SLOW": 250,
                 "SHORT_FAST": 250, "SHORT_SLOW": 250, "SHORT_TURBO": 500, "LONG_TURBO": 500, "MEDIUM_TURBO": 500}
CITY_REGION = {"bali": "SG_923", "menorca": "EU_868", "barcelona": "EU_868", "boston": "US", "santiago": "ANZ"}


def num_slots(region: str, preset: str = "LONG_FAST") -> int:
    lo, hi = REGIONS[region]
    return int((hi - lo) / (PRESET_BW_KHZ[preset] / 1000.0))


def slot_freq(region: str, slot: int, preset: str = "LONG_FAST") -> float:
    """Centre frequency of a 1-based slot, the firmware's formula: start + bw/2 + bw*(slot-1).
    Verify against what the radio logs at boot ("freq=") the first time a region is used; this is arithmetic, not a measurement."""
    lo, _ = REGIONS[region]
    bw = PRESET_BW_KHZ[preset] / 1000.0
    return round(lo + bw / 2 + bw * (slot - 1), 4)


def slots_inside(region: str, band: Tuple[float, float], preset: str = "LONG_FAST") -> List[int]:
    """Slots whose whole bandwidth sits inside `band`."""
    bw = PRESET_BW_KHZ[preset] / 1000.0
    out = []
    for s in range(1, num_slots(region, preset) + 1):
        f = slot_freq(region, s, preset)
        if f - bw / 2 >= band[0] - 1e-9 and f + bw / 2 <= band[1] + 1e-9:
            out.append(s)
    return out


def slot_for(region: str, city: str = "", preset: str = "LONG_FAST") -> Optional[int]:
    """A slot to pin: the middle of the legal band when one is listed for the city, else None (let the name hash it)."""
    band = ALLOCATION.get(city)
    if not band:
        return None
    ok = slots_inside(region, band, preset)
    return ok[len(ok) // 2] if ok else None


# ---------------------------------------------------------------- the fleet file
def _yaml():
    import yaml  # ships with the meshtastic package; the CLI's own Python has no yaml, which is why this file is separate
    return yaml


def new_fleet(node: str, region: str, city: str = "", preset: str = "LONG_FAST", slot: Optional[int] = None) -> dict:
    if region not in REGIONS:
        raise SystemExit(f"unknown region {region!r}; one of {', '.join(sorted(REGIONS))}")
    slot = slot if slot is not None else slot_for(region, city, preset)
    return {
        "node": node, "region": region, "preset": preset, "slot": slot, "created": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        # channel 0, PRIMARY: telemetry and position travel here and only here. The key is this node's own. Full
        # position (32 bits): it is the household's channel (Tomas, 19 Oct); 0 would send no position at all.
        "primary": {"name": "planetai", "psk": base64.b64encode(secrets.token_bytes(32)).decode(), "position_precision": 32},
        # channel 1, SECONDARY: what crosses to other nodes (text, alerts). Its own key too; federation re-sends as
        # text through the bridge, so two nodes never need to share a key. Position on it is capped coarse.
        "fabcity": {"name": "fabcity", "psk": base64.b64encode(secrets.token_bytes(32)).decode(), "position_precision": 13},
        "radios": [],
    }


def load_fleet(path: Path = FLEET_PATH) -> dict:
    if not path.exists():
        raise SystemExit(f"no fleet yet: run  planetai radio init  (looked at {path})")
    return _yaml().safe_load(path.read_text())


def save_fleet(fleet: dict, path: Path = FLEET_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_yaml().safe_dump(fleet, sort_keys=False))
    os.chmod(path, 0o600)


# ---------------------------------------------------------------- the channel URL
def channel_url(fleet: dict, gateway: bool = False) -> str:
    """One URL carrying both channels and the LoRa config (region, preset, pinned slot), the thing the phone app
    imports and `provision` writes with `--seturl`. Uplink/downlink flags ride inside it, so a gateway's URL differs from a
    sensor's by those two bits only."""
    from meshtastic.protobuf import apponly_pb2, channel_pb2, config_pb2
    cs = apponly_pb2.ChannelSet()
    for key, up, down in (("primary", gateway, gateway), ("fabcity", gateway, gateway)):
        ch = fleet[key]
        s = channel_pb2.ChannelSettings()
        s.name = ch["name"]
        s.psk = base64.b64decode(ch["psk"])
        s.uplink_enabled, s.downlink_enabled = up, down
        if ch.get("position_precision") is not None:
            s.module_settings.position_precision = int(ch["position_precision"])
        cs.settings.append(s)
    lora = cs.lora_config
    lora.region = config_pb2.Config.LoRaConfig.RegionCode.Value(fleet["region"])
    lora.use_preset = True
    lora.modem_preset = config_pb2.Config.LoRaConfig.ModemPreset.Value(fleet.get("preset", "LONG_FAST"))
    lora.hop_limit = 3
    lora.tx_enabled = True
    if fleet.get("slot"):
        lora.channel_num = int(fleet["slot"])
    b = base64.urlsafe_b64encode(cs.SerializeToString()).decode("ascii").rstrip("=")
    return f"https://meshtastic.org/e/#{b}"


def decode_url(url: str) -> dict:
    from meshtastic.protobuf import apponly_pb2, config_pb2
    b = url.split("/#", 1)[1]
    b += "=" * (-len(b) % 4)
    cs = apponly_pb2.ChannelSet()
    cs.ParseFromString(base64.urlsafe_b64decode(b))
    return {
        "channels": [{"name": s.name, "psk_len": len(s.psk), "uplink": s.uplink_enabled, "downlink": s.downlink_enabled,
                      "position_precision": s.module_settings.position_precision} for s in cs.settings],
        "region": config_pb2.Config.LoRaConfig.RegionCode.Name(cs.lora_config.region),
        "preset": config_pb2.Config.LoRaConfig.ModemPreset.Name(cs.lora_config.modem_preset),
        "slot": cs.lora_config.channel_num,
    }


# ---------------------------------------------------------------- roles → device profile
def load_profiles(d: Path = PROFILES_DIR) -> Dict[str, dict]:
    out = {}
    for p in sorted(d.glob("*.yaml")):
        out[p.stem] = _yaml().safe_load(p.read_text()) or {}
    return out


def _deep_merge(a: dict, b: dict) -> dict:
    out = dict(a)
    for k, v in b.items():
        out[k] = _deep_merge(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else v
    return out


def render_profile(role: str, long_name: str, short_name: str, fleet: dict, profiles: Dict[str, dict],
                   mqtt: Optional[dict] = None, wifi: Optional[Tuple[str, str]] = None,
                   fixed: Optional[Tuple[float, float, float]] = None) -> dict:
    """The DeviceProfile (meshtastic's camelCase YAML) for one radio. Pure: no radio, no network.
    `fixed` = (lat, lon, alt_m) pins the radio's position: a XIAO ESP32-S3 sensor node has no GPS, and a reading
    without a place never becomes `local` on the node. Broadcast on the primary channel only (the household's);
    the fabcity channel's precision cap still applies to anything that crosses."""
    if role not in profiles:
        raise SystemExit(f"unknown role {role!r}; one of {', '.join(sorted(profiles))}")
    if not (1 <= len(short_name) <= 4):
        raise SystemExit("short name is 1–4 characters (it is what the radio shows on screens with no room)")
    base = profiles.get("_base", {})
    spec = _deep_merge(base, {k: v for k, v in profiles[role].items() if not k.startswith("_")})
    is_gw = bool(profiles[role].get("_gateway"))
    prof: dict = {"owner": long_name, "owner_short": short_name, "channel_url": channel_url(fleet, gateway=is_gw)}
    prof["config"] = spec.get("config", {})
    prof["module_config"] = spec.get("module_config", {})
    # The URL already carries the LoRa config, but on firmware 2.7.26 a write that rides along with others can be lost
    # (node #1, 19 Oct), and verify compares section by section. So the lora section says it all again, explicitly.
    prof["config"]["lora"] = {"region": fleet["region"], "usePreset": True, "modemPreset": fleet.get("preset", "LONG_FAST"),
                              "channelNum": int(fleet.get("slot") or 0), "hopLimit": 3, "txEnabled": True}
    if fixed:
        lat, lon, alt = fixed
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            raise SystemExit(f"--fixed {lat},{lon}: not a coordinate")
        prof["location"] = {"lat": lat, "lon": lon, "alt": int(alt)}   # the CLI reads `location:` and writes DeviceProfile.fixed_position
        prof["config"].setdefault("position", {}).update({"fixedPosition": True, "gpsMode": "NOT_PRESENT"})
    if is_gw and profiles[role].get("_uplink") == "wifi":
        if not mqtt:
            raise SystemExit("gateway-wifi needs the broker: --mqtt host:1883 user pass (planetai radio doctor prints it)")
        prof["module_config"]["mqtt"] = {
            "enabled": True, "address": mqtt["address"], "username": mqtt["username"], "password": mqtt["password"],
            "encryptionEnabled": False,   # the broker is the node's; an encrypted uplink hides readings from it
            "jsonEnabled": True,          # the node reads JSON. ESP32 only: nRF52 has no JSON, use gateway-host there
            "root": "msh",
        }
        if wifi:
            prof["config"]["network"] = {"wifiEnabled": True, "wifiSsid": wifi[0], "wifiPsk": wifi[1]}
    return prof


# ---------------------------------------------------------------- talking to a radio (thin: the meshtastic CLI does the work)
def meshtastic_cli() -> List[str]:
    """The meshtastic CLI as the module of the very python3 running this file. A `--user` install puts the
    `meshtastic` script in ~/Library/Python/3.9/bin on a Mac, which is on nobody's PATH: looking for the script once
    reported a radio that "did not come back after a reboot" when no command had reached it (node #1, 18 Oct)."""
    import importlib.util
    if importlib.util.find_spec("meshtastic") is None:
        raise SystemExit(f"the meshtastic package is not installed for {sys.executable}:  python3 -m pip install --user meshtastic")
    return [sys.executable, "-m", "meshtastic"]


# Firmware 2.7.26 (node #1, 19 Oct) keeps a write only when it travels alone: `--configure`, a settings transaction
# through the API, `write_channels` with a 2 s wait all lost sections or channel 1, on two XIAOs, and the readback said
# they were there. What held on both: one stock CLI call per settings section, 25 s apart, then a reboot.
SETTLE_S = 25


def shown(args: List[str]) -> str:
    """A CLI call as it may be printed: keys, passwords and the channel URL (which carries both keys) are dots."""
    return " ".join("…" if i and re.search(r"psk|password|seturl", args[i - 1], re.I) else a for i, a in enumerate(args))


def run_cli(port: str, *args: str, timeout: int = 120) -> str:
    r = subprocess.run([*meshtastic_cli(), "--port", port, *args], capture_output=True, text=True, timeout=timeout)
    if r.returncode != 0:
        out = r.stdout + r.stderr
        for i, a in enumerate(args):   # the CLI echoes "Set wifi_psk to <value>" before a write fails
            if i and re.search(r"psk|password|seturl", args[i - 1], re.I):
                out = out.replace(a.split(":", 1)[-1] if a.startswith("base64:") else a, "…")
        raise SystemExit(f"meshtastic {shown(list(args))} failed:\n{out.strip()[-800:]}")
    return r.stdout


def wait_ready(port: str, tries: int = 30) -> None:
    """Every settings write reboots the radio; an ESP32 takes longer than an nRF52 to come back. Poll, don't sleep."""
    meshtastic_cli()   # a missing package is said as such, not retried as a radio that is slow to come back
    for _ in range(tries):
        try:
            run_cli(port, "--info", timeout=40)
            return
        except (SystemExit, subprocess.TimeoutExpired):
            time.sleep(2)
    raise SystemExit(f"radio on {port} did not come back after a reboot")


def _cli_value(v: Any) -> str:
    return ("true" if v else "false") if isinstance(v, bool) else str(v)


def provision_steps(prof: dict, fleet: dict, gateway: bool) -> List[List[str]]:
    """The CLI calls that write `prof`, in order, each a single write: the owner, the URL (both channels and the LoRa
    config), one `--set` call per config and module section, the fixed position, then each channel again by its index:
    2.7.26 lost channel 1 from the URL, and channel 0's position precision (node #1's Tracker, 19 Oct). Pure, so it is
    tested without a radio. `provision` adds the reboot."""
    steps = [["--set-owner", prof["owner"], "--set-owner-short", prof["owner_short"]], ["--seturl", prof["channel_url"]]]
    for group in ("config", "module_config"):
        for section, fields in prof.get(group, {}).items():
            step = [x for k, v in fields.items() for x in ("--set", f"{section}.{k}", _cli_value(v))]
            if step:
                steps.append(step)
    loc = prof.get("location")
    if loc:   # after the position section: `=` because a south latitude starts with a minus
        steps.append([f"--setlat={loc['lat']}", f"--setlon={loc['lon']}", f"--setalt={loc['alt']}"])
    for idx, key in ((0, "primary"), (1, "fabcity")):
        c = fleet[key]
        ch = ["--ch-index", str(idx), "--ch-set", "name", c["name"], "--ch-set", "psk", "base64:" + c["psk"],
              "--ch-set", "uplink_enabled", _cli_value(gateway), "--ch-set", "downlink_enabled", _cli_value(gateway)]
        if c.get("position_precision") is not None:
            ch += ["--ch-set", "module_settings.position_precision", str(int(c["position_precision"]))]
        steps.append(ch)
    return steps


def channel_hash(name: str, psk: bytes) -> int:
    """The firmware's one-byte channel hash: name bytes XOR key bytes. It is what a packet carries and what can be
    printed; the fleet's are planetai 0xfe, fabcity 0xe7 on node #1."""
    h = 0
    for b in name.encode() + psk:
        h ^= b
    return h


def read_radio(port: str) -> dict:
    """The radio as it is now, over a NEW connection. Within one connection the Python API answers from what it read
    at connect (localConfig, and deviceMetrics uptime too), so a readback after a write shows the write, not the radio:
    node #1's gateway "had" slot 19 and the fleet key for a day while it ran slot 20 and its old key (19 Oct)."""
    import meshtastic.serial_interface
    from google.protobuf import json_format
    from meshtastic.protobuf import channel_pb2

    def d(m: Any) -> dict:
        try:
            return json_format.MessageToDict(m, always_print_fields_with_no_presence=True)
        except TypeError:   # protobuf older than 5.26
            return json_format.MessageToDict(m, including_default_value_fields=True)
    iface = meshtastic.serial_interface.SerialInterface(port, timeout=60)
    try:
        n, me = iface.localNode, iface.getMyUser() or {}
        pos = (iface.getMyNodeInfo() or {}).get("position") or {}
        return {"id": me.get("id"), "lat_i": pos.get("latitudeI"), "lon_i": pos.get("longitudeI"), "alt": pos.get("altitude", 0), "owner": me.get("longName"), "owner_short": me.get("shortName"),
                "reboot_count": iface.myInfo.reboot_count, "config": d(n.localConfig), "module_config": d(n.moduleConfig),
                "channels": {c.index: {"role": channel_pb2.Channel.Role.Name(c.role), "name": c.settings.name,
                                       "psk": bytes(c.settings.psk), "uplink": c.settings.uplink_enabled,
                                       "downlink": c.settings.downlink_enabled,
                                       "position_precision": c.settings.module_settings.position_precision}
                             for c in (n.channels or [])}}
    finally:
        iface.close()


def wait_rebooted(port: str, before: int, tries: int = 24) -> dict:
    """read_radio once the radio has rebooted on what was written. Proof is its boot count rising (an ESP32, whose USB
    port stays up through a soft reboot), or its USB port going away and coming back (an nRF52: the Tracker L1's
    reboot_count stays 0, node #1, 19 Oct). The CLI's --reboot waits 10 s before the radio goes."""
    gone = False
    for _ in range(160):   # 40 s
        if not os.path.exists(port):
            gone = True
            break
        time.sleep(0.25)
    for _ in range(tries):
        time.sleep(5)
        try:
            snap = read_radio(port)
        except (Exception, SystemExit):  # noqa: BLE001  (a booting radio stalls the port or drops it)
            continue
        if gone or snap["reboot_count"] > before:
            return snap
    raise SystemExit(f"the radio on {port} did not reboot (boot count stayed {before}, its USB port never dropped); "
                     "it may still be on its old frequency")


def differences(prof: dict, fleet: dict, snap: dict, gateway: bool) -> List[str]:
    """What the radio (read_radio) holds that `prof` does not, as sentences (empty = good). Keys are compared, only
    their hashes are said; a WiFi or broker password is not compared (the firmware need not return it)."""
    problems = []
    for k in ("owner", "owner_short"):
        if snap.get(k) != prof[k]:
            problems.append(f"{k} is {snap.get(k)!r}, wants {prof[k]!r}")
    for group in ("config", "module_config"):
        for section, fields in prof.get(group, {}).items():
            got = snap.get(group, {}).get(section, {})
            for k, want in fields.items():
                if re.search(r"psk|password", k, re.I):
                    continue
                if _cli_value(want).lower() != _cli_value(got.get(k)).lower():   # enums by name, int64 as text
                    hint = " (a radio with no region never transmits)" if k == "region" else ""
                    problems.append(f"{section}.{k} is {got.get(k)}, wants {want}{hint}")
    loc = prof.get("location")
    if loc:   # the firmware stores 1e-7 degrees and whole metres; a lost --setlat leaves fixedPosition on and no place
        got = (snap.get("lat_i"), snap.get("lon_i"), snap.get("alt") or 0)
        want = (round(loc["lat"] * 1e7), round(loc["lon"] * 1e7), int(loc["alt"]))
        if None in got or abs(got[0] - want[0]) > 1 or abs(got[1] - want[1]) > 1 or got[2] != want[2]:
            def deg(v: Optional[int]) -> str:
                return "none" if v is None else f"{v / 1e7:.7f}".rstrip("0")
            problems.append(f"position.pin is {deg(got[0])},{deg(got[1])},{got[2]} m, wants {loc['lat']},{loc['lon']},{want[2]} m")
    for idx, key, role in ((0, "primary", "PRIMARY"), (1, "fabcity", "SECONDARY")):
        c, ch = fleet[key], snap.get("channels", {}).get(idx) or {}
        psk = base64.b64decode(c["psk"])
        if ch.get("role") != role or ch.get("name") != c["name"] or ch.get("psk") != psk:
            got = f"{ch.get('name')!r} hash {channel_hash(ch.get('name', ''), ch.get('psk', b'')):#04x}" if ch else "missing"
            problems.append(f"channel {idx} is {got} ({ch.get('role', 'no role')}), wants {c['name']!r} hash "
                            f"{channel_hash(c['name'], psk):#04x} ({role})")
        elif ch.get("uplink") != gateway or ch.get("downlink") != gateway:
            problems.append(f"channel {idx} uplink/downlink is {ch.get('uplink')}/{ch.get('downlink')}, wants {gateway}")
        elif c.get("position_precision") is not None and ch.get("position_precision") != int(c["position_precision"]):
            problems.append(f"channel {idx} position precision is {ch.get('position_precision')}, wants {c['position_precision']}")
    return problems


def step_key(step: List[str]) -> str:
    """What a provision step writes, in the words problem_key gives a difference: owner, a section, ch0, ch1."""
    if step[0] == "--set":
        return step[1].split(".")[0]
    if step[0].startswith("--setlat"):
        return "position"
    if step[0] == "--ch-index":
        return "ch" + step[1]
    return {"--set-owner": "owner"}.get(step[0], step[0])


def problem_key(problem: str) -> str:
    """The step that would fix a sentence from differences(): 'channel 1 is …' → ch1, 'lora.region is …' → lora."""
    m = re.match(r"channel (\d)|(owner)|(\w+)\.", problem)
    return ("ch" + m.group(1)) if m and m.group(1) else (m.group(2) or m.group(3)) if m else ""


def write_and_reboot(port: str, steps: List[List[str]]) -> dict:
    """Each step alone, SETTLE_S apart, then a reboot proven by wait_rebooted; returns the radio read afterwards."""
    for i, args in enumerate(steps, 1):
        print(f"   {i}/{len(steps) + 1}  {shown(args)}")
        out = run_cli(port, *args)
        for _ in range(2):
            if args[0] != "--set" or out.count("\nSet ") + out.startswith("Set ") >= args.count("--set"):
                break
            # a --set that lands in the radio's reboot window prints no "Set" line and writes nothing (19 Oct)
            wait_ready(port)
            out = run_cli(port, *args)
        else:   # verify cannot read a password back, so an unconfirmed write stops here
            raise SystemExit(f"the radio did not take  {shown(args)}  (no \"Set\" line, twice): run provision again")
        time.sleep(SETTLE_S)   # 2.7.26 drops a write when the port closes too soon after it
        wait_ready(port)
    # commitSettingsTransaction does not reboot 2.7.26, and a radio keeps its old frequency until it does. The count of
    # boots, read before and after over new connections, is the proof; uptime is cached by the API.
    before = read_radio(port)["reboot_count"]
    print(f"   {len(steps) + 1}/{len(steps) + 1}  --reboot  (boot count {before})")
    run_cli(port, "--reboot")
    return wait_rebooted(port, before)


def provision(port: str, role: str, long_name: str, short_name: str, fleet: dict, profiles: Dict[str, dict],
              mqtt: Optional[dict] = None, wifi: Optional[Tuple[str, str]] = None,
              fixed: Optional[Tuple[float, float, float]] = None) -> List[str]:
    """Write the role's profile, reboot, and read it back from a new connection. Returns the problems found."""
    prof = render_profile(role, long_name, short_name, fleet, profiles, mqtt, wifi, fixed)
    gw = bool(profiles[role].get("_gateway"))
    steps = provision_steps(prof, fleet, gw)
    wait_ready(port)
    print(f">> {role}: '{long_name}' ({short_name}), region {fleet['region']}, slot {fleet.get('slot') or 'by name'}; "
          f"{len(steps) + 1} steps, one write each, about {(len(steps) * (SETTLE_S + 15) + 60) // 60} minutes")
    snap = write_and_reboot(port, steps)
    problems = differences(prof, fleet, snap, gw)
    # 2.7.26 can still drop a write, or take one with another: a channel 0 write emptied channel 1 on a XIAO while the
    # same write kept it on the gateway and the Tracker (19 Oct). Write again only what did not hold, at most twice.
    for _ in range(2):
        redo = [st for st in steps if step_key(st) in {problem_key(p) for p in problems}]
        if not redo:
            break
        print("   did not hold: " + "; ".join(problems) + "\n   writing those again")
        snap = write_and_reboot(port, redo)
        problems = differences(prof, fleet, snap, gw)
    node_id = snap.get("id")
    # provisioning a radio again replaces its entry: the fleet lists each radio once
    fleet["radios"] = [r for r in fleet.get("radios", []) if not (node_id and r.get("id") == node_id)]
    fleet["radios"].append({"id": node_id, "role": role, "name": long_name, "short": short_name, "verified": not problems,
                                          "provisioned": datetime.now(timezone.utc).isoformat(timespec="seconds")})
    save_fleet(fleet)
    if problems:
        print("!! the radio, read back after its reboot, is not what was written:\n   " + "\n   ".join(problems)
              + "\n   Written three times and still not held: write that one setting with python3 -m meshtastic, then --reboot.")
    else:
        h = {k: channel_hash(fleet[k]["name"], base64.b64decode(fleet[k]["psk"])) for k in ("primary", "fabcity")}
        print(f">> ok. {node_id or 'radio'} rebooted on it and was read back over a new connection: every setting, "
              f"channels planetai {h['primary']:#04x} and fabcity {h['fabcity']:#04x}. In {FLEET_PATH}")
        print("   Next step:  planetai radio")
    return problems


# ---------------------------------------------------------------- the host gateway: packets → the same JSON an ESP32 gateway publishes
_SNAKE = re.compile(r"(?<!^)(?=[A-Z])")


def snake(d: Any) -> Any:
    """MessageToDict gives camelCase; the firmware's MQTT JSON (what app/sources.py parses) is snake_case."""
    if isinstance(d, dict):
        return {_SNAKE.sub("_", k).lower(): snake(v) for k, v in d.items()}
    if isinstance(d, list):
        return [snake(x) for x in d]
    return d


def envelope(packet: dict, gateway_id: str) -> Optional[Tuple[str, dict]]:
    """One decoded packet from the Python API → (type, payload) in the firmware's JSON shape, or None if the node
    has no use for it. Pure, so it is tested without a radio. Field names follow firmware 2.x JSON output."""
    dec = packet.get("decoded") or {}
    port = dec.get("portnum")
    if port == "TELEMETRY_APP":
        t = dec.get("telemetry") or {}
        # the block travels with the fields: `voltage` is the battery in deviceMetrics and an INA's bus in
        # environmentMetrics, and app/sources.py files them apart. healthMetrics (an MLX90614's object) is not uplinked.
        for block, name in (("deviceMetrics", "device"), ("environmentMetrics", "environment"),
                            ("airQualityMetrics", "air_quality"), ("powerMetrics", "power")):
            if block in t:
                return "telemetry", {**snake(t[block]), "block": name}
        return None
    if port == "POSITION_APP":
        p = dec.get("position") or {}
        out = {"latitude_i": p.get("latitudeI"), "longitude_i": p.get("longitudeI")}
        if p.get("altitude") is not None:
            out["altitude"] = p["altitude"]
        if p.get("time"):
            out["time"] = p["time"]
        return "position", out
    if port == "NODEINFO_APP":
        u = dec.get("user") or {}
        return "nodeinfo", {"id": u.get("id"), "longname": u.get("longName"), "shortname": u.get("shortName"), "hardware": u.get("hwModel")}
    if port == "TEXT_MESSAGE_APP":
        return "text", {"text": dec.get("text", "")}
    return None


def to_mqtt(packet: dict, gateway_id: str, region: str, channel_name: str, root: str = "msh") -> Optional[Tuple[str, bytes]]:
    """(topic, payload) exactly as an ESP32 gateway with JSON on would publish, so app/main.py's MQTT thread needs no change."""
    e = envelope(packet, gateway_id)
    if not e:
        return None
    kind, payload = e
    sender = packet.get("fromId") or f"!{packet['from']:08x}"
    msg = {"channel": packet.get("channel", 0), "from": packet.get("from"), "id": packet.get("id"), "payload": payload,
           "sender": sender, "timestamp": int(packet.get("rxTime") or time.time()), "to": packet.get("to", -1), "type": kind}
    return f"{root}/{region}/2/json/{channel_name}/{gateway_id}", json.dumps(msg, separators=(",", ":")).encode()


# ---------------------------------------------------------------- federation: what may cross to another node
class Federation:
    """Decides what leaves this node for the fabcity/ topics and what comes in from them.
    Out: text on the fabcity channel, the node's alerts, a presence line. Never a reading, never a position finer
    than the channel's cap (and the cap is set so nothing finer than a resolution-8 cell leaves: the site rule).
    In: text from other nodes, re-sent on the local fabcity channel, deduplicated and rate-limited: LoRa airtime is
    the scarce thing, and a broker can deliver a thousand lines a second."""

    def __init__(self, node: str, fabcity_index: int = 1, max_per_minute: int = 6):
        self.node, self.idx, self.max_per_minute = node, fabcity_index, max_per_minute
        self.seen: Dict[str, float] = {}
        self.sent_times: List[float] = []

    def outbound(self, packet: dict) -> Optional[Tuple[str, bytes]]:
        if packet.get("channel", 0) != self.idx:
            return None                                     # channel 0 is the household's; it stays home
        e = envelope(packet, "")
        if not e or e[0] != "text":
            return None                                     # positions, telemetry: never
        text = e[1]["text"].strip()
        if not text:
            return None
        body = {"node": self.node, "from": packet.get("fromId"), "id": packet.get("id"), "text": text[:200],
                "ts": int(packet.get("rxTime") or time.time())}
        return f"fabcity/{self.node}/text", json.dumps(body, separators=(",", ":")).encode()

    def presence(self, radios: int, cell_r3: Optional[str]) -> Tuple[str, bytes]:
        body = {"node": self.node, "radios": radios, "cell": cell_r3, "ts": int(time.time())}
        return f"fabcity/{self.node}/presence", json.dumps(body, separators=(",", ":")).encode()

    def inbound(self, topic: str, payload: bytes, now: Optional[float] = None) -> Optional[str]:
        """The text to send on the local fabcity channel, or None (own echo, duplicate, rate limit, not text)."""
        now = now or time.time()
        parts = topic.split("/")
        if len(parts) != 3 or parts[0] != "fabcity" or parts[2] not in ("text", "alerts"):
            return None
        if parts[1] == self.node:
            return None
        try:
            m = json.loads(payload)
        except Exception:  # noqa: BLE001
            return None
        key = f"{parts[1]}/{m.get('id')}"
        if key in self.seen:
            return None
        self.seen = {k: v for k, v in self.seen.items() if now - v < 3600}
        self.seen[key] = now
        self.sent_times = [t for t in self.sent_times if now - t < 60]
        if len(self.sent_times) >= self.max_per_minute:
            log.warning("federation: dropping %s, more than %d lines a minute", key, self.max_per_minute)
            return None
        self.sent_times.append(now)
        text = str(m.get("text", "")).strip()
        if not text:
            return None
        return f"[{parts[1]}] {text}"[:200]


def mosquitto_bridges(node: str, peers: Dict[str, dict], user: str) -> str:
    """Bridge blocks for config/mosquitto/bridges/peers.conf. Each peer is a node on the tailnet; the connection goes
    over Tailscale, so no TLS and no open port, and a peer's password is the one `planetai radio federate` on
    that node printed. Only fabcity/ crosses. msh/ never does."""
    lines = ["# written by planetai radio federate; peers come from RADIO_PEERS in .env. Only fabcity/ crosses."]
    for name, p in sorted(peers.items()):
        u = p.get("username", user)
        lines += [
            f"connection fabcity-{name}",
            f"address {p['address']}",
            *([f"remote_username {u}", f"remote_password {p['password']}"] if u else []),   # mosquitto refuses an empty value
            f"remote_clientid planetai-{node}-to-{name}",
            "cleansession false",
            "try_private true",
            "notifications false",
            f"topic {node}/# out 0 fabcity/ fabcity/",      # mine go out
            f"topic {name}/# in 0 fabcity/ fabcity/",       # theirs come in; nothing else
            "",
        ]
    return "\n".join(lines) + "\n"


def parse_peers(s: str) -> Dict[str, dict]:
    """RADIO_PEERS=menorca=lucas-node.tailnet.ts.net:1883:<password>,boston=…"""
    out = {}
    for item in (x.strip() for x in s.split(",") if x.strip()):
        name, _, rest = item.partition("=")
        host, _, rest = rest.partition(":")
        port, _, password = rest.partition(":")
        if not (name and host and port and password):
            raise SystemExit(f"RADIO_PEERS entry {item!r} is not name=host:port:password")
        out[name.strip()] = {"address": f"{host}:{port}", "password": password}
    return out


# ---------------------------------------------------------------- the gateway process
def lan_ip() -> str:
    """The address other machines on the LAN reach this one at: the source of the route out. No packet is sent."""
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("192.0.2.1", 9))      # TEST-NET-1: never routed, but connect() picks the interface
        ip = s.getsockname()[0]; s.close()
        return "" if ip.startswith("127.") else ip
    except OSError:
        return ""


def envget(key: str, default: str = "") -> str:
    env = ROOT / ".env"
    if not env.exists():
        return os.getenv(key, default)
    for line in env.read_text().splitlines():
        if line.startswith(key + "="):
            v = line.split("=", 1)[1].strip()
            if v and v[0] in "\"'":                       # quoted: the value is what the quotes hold, # and all
                return v[1:].split(v[0], 1)[0]
            return re.split(r"\s+#", v, maxsplit=1)[0].strip()   # unquoted: ` # …` is a comment, as docker compose reads it
    return os.getenv(key, default)


def gateway(port: str, fleet: dict, broker: str = "127.0.0.1:1883", once: bool = False) -> None:
    """This radio, on this node's USB, is the gateway: packets go to the broker as JSON; downlink text comes back;
    the fabcity channel is federated. Runs until killed. `planetai radio gateway --install` makes it a service."""
    import paho.mqtt.client as mqtt
    from pubsub import pub
    import meshtastic.serial_interface

    user, password = envget("MQTT_USER", "planetai"), envget("MQTT_PASS")
    node = envget("NODE_NAME", fleet.get("node", "node"))
    host, _, bport = broker.partition(":")
    region, primary, fab = fleet["region"], fleet["primary"]["name"], fleet["fabcity"]["name"]
    iface = meshtastic.serial_interface.SerialInterface(port)
    me = iface.getMyNodeInfo() or {}
    gw_id = (me.get("user") or {}).get("id") or f"!{me.get('num', 0):08x}"
    root_topic = f"msh/{region}"
    # the radio's channel table decides which index is which; a phone import can land fabcity anywhere
    names = {0: primary, 1: fab}
    try:
        names = {c.index: c.settings.name for c in iface.localNode.channels if c.settings.name} or names
    except Exception:  # noqa: BLE001
        pass
    fab_idx = next((i for i, n in names.items() if n == fab), 1)
    fed = Federation(node, fabcity_index=fab_idx)
    log.info("gateway %s on %s, broker %s, node %s, fabcity is channel %d", gw_id, port, broker, node, fab_idx)

    c = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"planetai-radio-{node}")
    if user:
        c.username_pw_set(user, password)
    counts = {"up": 0, "down": 0, "fed_out": 0, "fed_in": 0}

    def on_radio(packet, interface):  # noqa: ARG001
        ch = packet.get("channel", 0)
        tp = to_mqtt(packet, gw_id, region, names.get(ch, primary))
        if tp:
            c.publish(tp[0], tp[1]); counts["up"] += 1
        fo = fed.outbound(packet)
        if fo:
            c.publish(fo[0], fo[1]); counts["fed_out"] += 1

    def on_mqtt(client, userdata, msg):  # noqa: ARG001
        if msg.topic == f"{root_topic}/2/json/mqtt/":          # app/main.py mesh_send(): the node's own alerts
            try:
                m = json.loads(msg.payload)
                if m.get("type") == "sendtext":
                    iface.sendText(str(m.get("payload", ""))[:200], channelIndex=int(m.get("channel", 0)))
                    counts["down"] += 1
                    c.publish(f"fabcity/{node}/alerts", json.dumps({"node": node, "id": int(time.time()), "text": m.get("payload", "")}).encode())
            except Exception as e:  # noqa: BLE001
                log.warning("downlink ignored: %s", e)
            return
        text = fed.inbound(msg.topic, msg.payload)
        if text:
            iface.sendText(text, channelIndex=fab_idx); counts["fed_in"] += 1

    c.on_message = on_mqtt
    c.connect(host, int(bport or 1883), keepalive=60)
    c.subscribe([(f"{root_topic}/2/json/mqtt/", 0), ("fabcity/+/text", 0), ("fabcity/+/alerts", 0)])
    c.loop_start()
    # Names: the gateway's own nodeinfo never comes up its USB, and a sensor's comes every three hours. So say the
    # names this radio already holds for itself and the fleet's radios, once, at start (node #1, 20 Oct 2026).
    ours = {gw_id} | {r.get("id") for r in fleet.get("radios", [])}
    for n in list((getattr(iface, "nodes", None) or {}).values()):
        u = n.get("user") or {}
        tp = to_mqtt({"from": n.get("num"), "fromId": u.get("id"), "decoded": {"portnum": "NODEINFO_APP", "user": u}},
                     gw_id, region, primary) if u.get("id") in ours and isinstance(n.get("num"), int) else None
        if tp:
            c.publish(tp[0], tp[1])
    pub.subscribe(on_radio, "meshtastic.receive")
    # an unplugged radio leaves the port dead and this process alive, so the service never restarts it (20 Oct 2026)
    lost = threading.Event()

    def on_lost(interface):  # noqa: ARG001
        lost.set()
    pub.subscribe(on_lost, "meshtastic.connection.lost")

    def heartbeat():
        while True:
            t, p = fed.presence(len(fleet.get("radios", [])), None)
            c.publish(t, p, retain=True)
            log.info("up %d · down %d · federated out %d in %d", counts["up"], counts["down"], counts["fed_out"], counts["fed_in"])
            time.sleep(1800)
    threading.Thread(target=heartbeat, daemon=True).start()
    try:
        if once:
            time.sleep(5)
        else:
            lost.wait()
            log.warning("the radio on %s went away; exiting so the service starts the gateway again", port)
            raise SystemExit(1)
    finally:
        iface.close(); c.loop_stop()


SERVICE_MAC = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>city.fab.planetai.radio</string>
  <key>ProgramArguments</key><array><string>{python}</string><string>{script}</string><string>gateway</string><string>--port</string><string>{port}</string></array>
  <key>WorkingDirectory</key><string>{root}</string>
  <key>RunAtLoad</key><true/><key>KeepAlive</key><true/>
  <key>StandardOutPath</key><string>{root}/out/radio.log</string><key>StandardErrorPath</key><string>{root}/out/radio.log</string>
</dict></plist>
"""
SERVICE_LINUX = """[Unit]
Description=PLANETAI radio gateway
After=network.target docker.service
[Service]
WorkingDirectory={root}
ExecStart={python} {script} gateway --port {port}
Restart=always
RestartSec=10
[Install]
WantedBy=default.target
"""


def install_service(port: str) -> None:
    py, script, root = sys.executable, str(Path(__file__).resolve()), str(ROOT)
    if sys.platform == "darwin":
        p = Path.home() / "Library" / "LaunchAgents" / "city.fab.planetai.radio.plist"
        p.write_text(SERVICE_MAC.format(python=py, script=script, port=port, root=root))
        subprocess.run(["launchctl", "unload", str(p)], capture_output=True)   # a fresh load picks up a changed port
        r = subprocess.run(["launchctl", "load", str(p)], capture_output=True, text=True)
        print(f">> the gateway runs as a service now, and again after every restart ({p})" if r.returncode == 0 else
              f"!! wrote {p}, but launchctl did not load it: {(r.stderr or r.stdout).strip()}\n   by hand:  launchctl load {p}")
    else:
        p = Path.home() / ".config" / "systemd" / "user" / "planetai-radio.service"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(SERVICE_LINUX.format(python=py, script=script, port=port, root=root))
        ok = all(subprocess.run(c, capture_output=True).returncode == 0 for c in
                 (["systemctl", "--user", "daemon-reload"], ["systemctl", "--user", "enable", "--now", "planetai-radio"]))
        print(f">> the gateway runs as a service now ({p}). So it also runs while nobody is logged in:  loginctl enable-linger $USER"
              if ok else f"!! wrote {p}, but systemctl did not start it.\n   by hand:  systemctl --user daemon-reload && systemctl --user enable --now planetai-radio")


# ---------------------------------------------------------------- doctor
def doctor(port: Optional[str]) -> int:
    bad = 0

    def chk(ok: bool, what: str, fix: str) -> None:
        nonlocal bad
        print(("  ok  " if ok else "  !!  ") + what + ("" if ok else f"\n        {fix}"))
        bad += 0 if ok else 1

    import importlib.util
    chk(importlib.util.find_spec("meshtastic") is not None, f"meshtastic for {sys.executable}", "python3 -m pip install --user meshtastic")
    try:
        from importlib.metadata import version
        v = tuple(int(x) for x in version("meshtastic").split(".")[:3])
        # 2.7.11 is the CLI provision was proven with on firmware 2.7.26 (node #1, 19 Oct): one `--set` per section,
        # `--ch-index 1 --ch-set psk base64:…`, `--setlat=` for a south latitude.
        chk(v >= (2, 7, 11), f"meshtastic package {'.'.join(map(str, v))} (2.7.11 or newer: what provision is proven with)", "python3 -m pip install --user -U meshtastic")
    except Exception:  # noqa: BLE001
        chk(False, "meshtastic package version readable", "python3 -m pip install --user -U meshtastic")
    try:
        import paho.mqtt  # noqa: F401
        chk(True, "paho-mqtt on the host", "")
    except ImportError:
        chk(False, "paho-mqtt on the host", "python3 -m pip install --user paho-mqtt")
    chk(FLEET_PATH.exists(), f"fleet file {FLEET_PATH.relative_to(ROOT)}", "planetai radio init")
    chk(bool(envget("MQTT_PASS")), "broker credentials in .env", "planetai meshtastic  (creates the broker and its user)")
    chk("mqtt" in envget("COMPOSE_PROFILES"), "mqtt compose profile on", "planetai meshtastic")
    if FLEET_PATH.exists():
        f = load_fleet()
        city = envget("NODE_CITY")
        band = ALLOCATION.get(city)
        if band:
            slot = f.get("slot")
            chk(bool(slot) and slot in slots_inside(f["region"], band, f.get("preset", "LONG_FAST")),
                f"frequency slot inside {city}'s allocation {band[0]}–{band[1]} MHz",
                "planetai radio init --slot N   (then re-provision every radio: the URL changed)")
    if port:
        try:
            info = run_cli(port, "--info", timeout=60)
            chk('"region": "UNSET"' not in info and "region: 0" not in info, "radio has a region", "a radio with region unset never transmits and nothing tells you")
            chk('"name": "planetai"' in info, "radio is on the planetai channel", "planetai radio provision …")
        except SystemExit as e:
            chk(False, f"radio answers on {port}", str(e).splitlines()[-1] if str(e) else "")
    print(f"\n{bad} problem(s)" if bad else "\nnothing wrong that this can see")
    return 1 if bad else 0


# ---------------------------------------------------------------- the guide
def usb_radios() -> List[Tuple[str, str]]:
    """Serial ports with a USB vendor id: what is plugged in now. macOS lists every radio twice (cu. and tty.); cu. is
    the one to use. Empty when pyserial is missing, so the guide still runs."""
    try:
        from serial.tools import list_ports
    except ImportError:
        return []
    out = []
    for p in list_ports.comports():
        if p.vid is None or "/dev/tty." in p.device:
            continue
        out.append((p.device, (p.description or "").strip() if p.description and p.description != "n/a" else "USB serial"))
    return out


def gateway_port() -> Optional[str]:
    """The USB port the installed gateway service holds, read back from its own service file."""
    p = (Path.home() / "Library" / "LaunchAgents" / "city.fab.planetai.radio.plist") if sys.platform == "darwin" \
        else (Path.home() / ".config" / "systemd" / "user" / "planetai-radio.service")
    m = re.search(r"(/dev/[\w.\-]+)", p.read_text()) if p.exists() else None
    return m.group(1) if m else None


def service_installed() -> bool:
    if sys.platform == "darwin":
        return (Path.home() / "Library" / "LaunchAgents" / "city.fab.planetai.radio.plist").exists()
    return (Path.home() / ".config" / "systemd" / "user" / "planetai-radio.service").exists()


def guide() -> int:
    """`planetai radio` on its own: where this node is in setting up its radios, step by step, and the one command
    that comes next. Read-only: it looks at .env, the fleet file and the USB ports, and never talks to a radio."""
    ports = usb_radios()
    gw_port = gateway_port()
    free = [d for d, _ in ports if d != gw_port]   # the gateway's port is taken: never offer it for another radio
    port = free[0] if len(free) == 1 else "/dev/cu.usbmodem…"
    try:
        fleet = load_fleet() if FLEET_PATH.exists() else None
    except ImportError:   # yaml arrives with the packages; the fleet is there, its details wait for step 1
        fleet = {"region": "?", "radios": []}
    # a radio whose readback failed is listed, and not counted as done (entries from before 19 Oct have no flag)
    radios = [r for r in (fleet or {}).get("radios", []) if r.get("verified", True)]
    gateways = [r for r in radios if str(r.get("role", "")).startswith("gateway")]
    others = [r for r in radios if not str(r.get("role", "")).startswith("gateway")]
    steps = []   # (done, title, detail, next command when not done)
    try:
        import meshtastic  # noqa: F401
        import paho.mqtt  # noqa: F401
        pkgs = True
    except ImportError:
        pkgs = False
    pins = ('"pyobjc-core<12" "pyobjc-framework-Cocoa<12" "pyobjc-framework-CoreBluetooth<12" "pyobjc-framework-libdispatch<12" '
            if sys.platform == "darwin" and sys.version_info < (3, 10) else "")   # 12.0 does not build on Apple's 3.9
    steps.append((pkgs, "The packages", f"meshtastic and paho-mqtt for {sys.executable}",
                  f"python3 -m pip install --user {pins}meshtastic paho-mqtt"))
    broker = bool(envget("MQTT_PASS")) and "mqtt" in envget("COMPOSE_PROFILES")
    steps.append((broker, "The broker", "the node's MQTT broker, where the gateway delivers what the radios hear",
                  "planetai meshtastic"))
    if fleet:
        f = fleet
        where = f"region {f['region']}, slot {f.get('slot') or 'by channel name'}" + (
            f" ({slot_freq(f['region'], f['slot'], f.get('preset', 'LONG_FAST'))} MHz)" if f.get("slot") else "")
        steps.append((True, "The fleet", f"{where}; the household's channel keys, in {FLEET_PATH.relative_to(ROOT)}", ""))
    else:
        steps.append((False, "The fleet", "one set of channel keys, region and frequency for every radio of this node",
                      "planetai radio init"))
    steps.append((bool(gateways), "The gateway radio",
                  "one radio on this machine's USB that carries the mesh to the node" + (f": {gateways[0]['name']}" if gateways else ""),
                  f'planetai radio provision gateway-host "{envget("NODE_NAME", "node")} gateway" GATE --port {port}'))
    if gateways:
        steps.append((service_installed(), "The gateway, always on", "a service that keeps the gateway running after a restart",
                      f"planetai radio gateway --port {port} --install"))
    steps.append((bool(others), "Sensor and shelf radios",
                  (f"{len(others)} provisioned: " + ", ".join(r["name"] for r in others[:4]) + ("…" if len(others) > 4 else "")) if others
                  else "field sensors, relays, and shelf radios that receive alerts when the internet is down",
                  f'planetai radio provision sensor "<the place it stands>" ABC --port {port}'))
    print("Radios for this node, step by step\n")
    for i, (done, title, detail, _) in enumerate(steps, 1):
        print(f"  {'✓' if done else '·'} {i}. {title}: {detail}")
    print("\n  On USB now: " + ("; ".join(f"{d} ({desc})" + (" — the gateway, keep it plugged in" if d == gw_port else "") for d, desc in ports) if ports
          else "no radio. Plug one in by USB (antenna on first), then run this again.\n"
          "    Plugged in and still nothing? The usual four, most likely first: a charge-only cable (try the one that came\n"
          "    with the radio); a Tracker's power switch is off; a XIAO needs BOOT held while it is plugged in; a hub or\n"
          "    dock in between (plug straight into this machine)."))
    todo = [st for st in steps if not st[0]]
    if todo:
        print(f"\nNext: {todo[0][3]}")
        if "/dev/cu.usbmodem…" in todo[0][3]:
            print("      (plug the radio in by USB first; this command then names its port)" if not free and not (ports and gw_port) else
                  "      (plug the next radio into another USB port; the gateway stays where it is)" if not free else
                  "      (more than one radio is plugged in: pick its port from the list above)")
    else:
        print("\nEvery step is done. Phones join with  planetai radio url ; check a radio with  planetai radio doctor --port <port>")
    print("Step by step, with what you should see: docs/MESHTASTIC.md")
    return 0


# ---------------------------------------------------------------- CLI
def main(argv: Optional[List[str]] = None) -> int:
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"), format="%(asctime)s %(levelname)s %(message)s")
    logging.getLogger("meshtastic").setLevel(logging.WARNING)   # its "Telling node to commit…" lines are not for people
    ap = argparse.ArgumentParser(prog="planetai radio", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd")
    s = sub.add_parser("init"); s.add_argument("--region"); s.add_argument("--slot", type=int); s.add_argument("--preset", default="LONG_FAST"); s.add_argument("--force", action="store_true")
    s = sub.add_parser("url"); s.add_argument("--json", action="store_true", help="the decoded settings, for a script")
    for name in ("render", "provision"):
        s = sub.add_parser(name); s.add_argument("role"); s.add_argument("long_name"); s.add_argument("short_name")
        s.add_argument("--port"); s.add_argument("--mqtt", help="host:1883 user pass, for gateway-wifi", nargs=3, metavar=("ADDR", "USER", "PASS"))
        s.add_argument("--wifi", help="SSID:PSK, gateway-wifi only")
        s.add_argument("--fixed", help="LAT,LON[,ALT_M]: pin the position of a radio with no GPS (a XIAO sensor node); "
                                       "a south latitude as it is: --fixed -8.8,115.1")
    s = sub.add_parser("gateway"); s.add_argument("--port", required=True); s.add_argument("--broker", default="127.0.0.1:1883"); s.add_argument("--install", action="store_true"); s.add_argument("--once", action="store_true")
    s = sub.add_parser("federate"); s.add_argument("--write", action="store_true")
    s = sub.add_parser("list"); s.add_argument("--port")
    s = sub.add_parser("doctor"); s.add_argument("--port")
    argv = list(sys.argv[1:] if argv is None else argv)
    # `--fixed -8.8,115.1`: argparse takes a value that starts with a minus, and is not a bare number, for an option, so
    # every radio south of the equator stopped at "expected one argument" (Bali, 19 Oct). Join it to its flag.
    for i in range(len(argv) - 1):
        if argv[i] == "--fixed" and argv[i + 1].startswith("-"):
            argv[i:i + 2] = ["--fixed=" + argv[i + 1]]
            break
    a = ap.parse_args(argv)
    if not a.cmd:
        return guide()

    if a.cmd == "init":
        if FLEET_PATH.exists() and not a.force:
            raise SystemExit(f"{FLEET_PATH} exists. --force makes a new one, and every radio must then be re-provisioned (new keys).")
        city = envget("NODE_CITY")
        region = a.region or CITY_REGION.get(city)
        if not region:   # never guess: a radio on another country's band is illegal there (node #1 got EU_868 in Bali)
            raise SystemExit(f"no radio region for NODE_CITY={city!r}. Say which, e.g.  planetai radio init --region SG_923\n"
                             f"   one of {', '.join(sorted(REGIONS))}")
        f = new_fleet(envget("NODE_NAME", "node"), region, city, a.preset, a.slot)
        save_fleet(f)
        print(f">> fleet for {f['node']}: region {region}, preset {a.preset}, slot {f['slot'] or 'by channel name'}"
              + (f" ({slot_freq(region, f['slot'], a.preset)} MHz)" if f["slot"] else ""))
        print(f"   keys in {FLEET_PATH} (mode 600, gitignored). Next step:  planetai radio")
        return 0
    if a.cmd == "url":
        f = load_fleet(); u = channel_url(f)
        if a.json:
            print(json.dumps({"url": u, **decode_url(u)}, indent=1)); return 0
        print(f"This node's radio channels: region {f['region']}, slot {f.get('slot') or 'by channel name'}; "
              "two channels, planetai (the household's) and fabcity (what other nodes see).\n")
        print("To put a phone on the mesh:")
        print("  1. Install the Meshtastic app (iPhone or Android).")
        print("  2. Pair it with any radio over Bluetooth: the PIN is on the radio's screen, or 123456 on one without a screen.")
        qr = shutil.which("qrencode")
        print(f"  3. Open this link on the phone{', or scan the QR below' if qr else ''}, and accept replacing the channels:\n")
        print(f"     {u}\n")
        if qr:
            subprocess.run(["qrencode", "-t", "ansiutf8", u], check=False)
        else:
            print("     (for a QR here:  brew install qrencode  or  apt install qrencode)")
        print("Radios provisioned with  planetai radio provision  already have these channels; this link is for phones.")
        return 0
    if a.cmd in ("render", "provision"):
        f, profiles = load_fleet(), load_profiles()
        mqtt = {"address": a.mqtt[0], "username": a.mqtt[1], "password": a.mqtt[2]} if a.mqtt else None
        if a.role == "gateway-wifi" and not mqtt:
            mqtt = {"address": f"{lan_ip() or '<node LAN ip>'}:1883", "username": envget("MQTT_USER", "planetai"), "password": envget("MQTT_PASS")}
        wifi = tuple(a.wifi.split(":", 1)) if a.wifi else None
        fixed = None
        if a.fixed:
            try:
                xs = [float(x) for x in a.fixed.split(",")]
                fixed = (xs[0], xs[1], xs[2] if len(xs) > 2 else 0.0)
            except (ValueError, IndexError):
                raise SystemExit("--fixed wants LAT,LON or LAT,LON,ALT_M, e.g. --fixed -8.80045,115.17664")
        if a.cmd == "render":
            print(_yaml().safe_dump(render_profile(a.role, a.long_name, a.short_name, f, profiles, mqtt, wifi, fixed), sort_keys=False)); return 0
        if not a.port:
            seen = usb_radios()
            raise SystemExit("--port is needed to provision. " + (
                "On USB now: " + ", ".join(d for d, _ in seen) if seen else "No radio is on USB now: plug one in (antenna on first).")
                + "\n   render shows the profile without a radio.")
        return 1 if provision(a.port, a.role, a.long_name, a.short_name, f, profiles, mqtt, wifi, fixed=fixed) else 0
    if a.cmd == "gateway":
        if a.install:
            install_service(a.port); print("   Next step:  planetai radio"); return 0
        gateway(a.port, load_fleet(), a.broker, once=a.once); return 0
    if a.cmd == "federate":
        peers = parse_peers(envget("RADIO_PEERS"))
        node = envget("NODE_NAME", "node")
        if not peers:
            print("no peers. In .env:  RADIO_PEERS=menorca=<their tailnet host>:1883:<their MQTT_PASS>,…")
            print(f"what a peer puts in theirs for this node:  {node}=<this node's tailnet host>:1883:{envget('MQTT_PASS') or '<MQTT_PASS>'}")
            return 0
        conf = mosquitto_bridges(node, peers, envget("MQTT_USER", "planetai"))
        if a.write:
            # a subdirectory, because include_dir takes every *.conf in it and mosquitto.conf must not include itself
            d = MOSQ_DIR / "bridges"; d.mkdir(parents=True, exist_ok=True)
            (d / "peers.conf").write_text(conf)
            main_conf = MOSQ_DIR / "mosquitto.conf"
            if main_conf.exists() and "include_dir" not in main_conf.read_text():
                main_conf.write_text(main_conf.read_text().rstrip("\n") + "\ninclude_dir /mosquitto/config/bridges\n")
            print(f">> wrote {d / 'peers.conf'} (a credential: gitignore config/mosquitto/bridges/); restart the broker:  planetai restart")
        else:
            print(conf)
        return 0
    if a.cmd == "list":
        f = load_fleet()
        print(f"{f['node']}: region {f['region']}, slot {f.get('slot') or 'by name'}, {len(f.get('radios', []))} radio(s) provisioned")
        for r in f.get("radios", []):
            print(f"  {r.get('id') or '?':10} {r['role']:13} {r['short']:4} {r['name']}  ({r['provisioned'][:10]})")
        if a.port:
            print(run_cli(a.port, "--nodes"))
        return 0
    if a.cmd == "doctor":
        return doctor(a.port)
    return 0


if __name__ == "__main__":
    sys.exit(main())
