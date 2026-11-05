"""Bali Air Dispatch: the island's public air stations, as the ring of other people's sensors around this node.

Public, key-free, edge-cached 5-60 min, aggregating eight networks. We take /latest, decide which stations are this
node's NEIGHBOURS rather than its own kit read twice, and store pm25 (as published) + pm25_raw when present so the
correction stays auditable. Every station is stored `local=False`, whatever its coordinates say.

Attribution required: "Bali Air Dispatch, baliairdispatch.com" + the row's source network. See README.md.

This lived in app/sources.py until the release after v0.82.3; the sensor ids (`bad-<station>`), the source name
(`baliairdispatch`) and the settings (BAD_*) are unchanged, so a node's history carries on.

Contract: fetch(hc) -> (sensors, readings), like everything in app/sources.py. `verdicts()` and `audit()` are also
read by packs/nearby and by GET /nearby?audit=1, so the audit can never drift from what is stored.
"""
from __future__ import annotations

import sys

sys.path.insert(0, "/app")
import settings  # noqa: E402
import sources  # noqa: E402

LATEST = "https://baliairdispatch.com/api/v1/latest"
STATIONS = "https://baliairdispatch.com/api/v1/stations"
SOURCE = "baliairdispatch"
ATTRIBUTION = "Bali Air Dispatch, baliairdispatch.com"
# Aggregators re-publish other networks' devices under their own ids. Measured 7 Sep 2026: 23 of the 87 stations
# are an AirGradient unit and its OpenAQ mirror at identical coordinates with an identical name, and one is an
# IQAir station mirrored by AQICN. The archive dedupes OpenAQ against some networks but not against AirGradient,
# so the ring has to. These prefixes lose a tie: the network that owns the device is kept, the mirror is dropped.
MIRROR_PREFIXES = ("oq-", "oaq-", "aq-")


def _ids(key: str) -> set[str]:
    return {x for x in settings.get(key, "").replace(" ", "").split(",") if x}


def cfg() -> dict:
    """The pack's own settings, read the way the node reads them (a Set up row wins over .env)."""
    return {"on": settings.get("BAD_ENABLED", "0") == "1",
            "radius_km": float(settings.get("BAD_RADIUS_KM", "15") or 15),
            "min_separation_m": float(settings.get("BAD_MIN_SEPARATION_M", "150") or 150),
            "exclude": _ids("BAD_EXCLUDE"),
            "include_indoor": settings.get("BAD_INCLUDE_INDOOR", "0") == "1"}


def own_ids(hc, account: bool = True) -> set[str]:
    """The station ids this node already reads directly: Smart Citizen kits by id (the archive republishes them as
    `sc-<kit>`), AirGradient units by serial. `account=False` skips the call to smartcitizen.me."""
    ids = {int(x) for x in _ids("SC_DEVICES")}
    if account and settings.get("SC_USER", "").strip():
        try:
            ids |= set(sources.smartcitizen_account(hc, settings.get("SC_USER").strip(),
                                                    exclude={int(x) for x in _ids("SC_EXCLUDE")}))
        except Exception as e:  # noqa: BLE001 — the ring still works, identity just catches less
            import logging; logging.getLogger("planetai").warning("smartcitizen account discovery failed: %s", e)
    own = {f"sc-{i}" for i in ids}
    own |= {f"ag-{h.replace('.local', '').replace('airgradient_', '')}" for h in _ids("AIRGRADIENT_HOSTS")}
    return own


def verdicts(rows: list[dict], node_lat: float, node_lon: float, radius_km: float,
             own_ids: set[str] | None = None, exclude_ids: set[str] | None = None,
             min_separation_m: float = 150.0, include_indoor: bool = False) -> list[tuple[dict, str]]:
    """Which archive stations are this node's neighbours, and for the rest, why not.

    Pure: rows in, (row, verdict) out, no network. The adapter keeps the `included` ones; `planetai run nearby
    stations` prints the whole list so a person can read the dedup by eye. One function, so the audit cannot
    drift from what the adapter actually does.

    Three ways a station can be this node's own kit rather than a neighbour, and all three are needed:
      identity   the node polls this device directly. Catches `sc-19236` (Ungasan Kit, 1.3 km away) which no
                 distance rule would.
      proximity  within min_separation_m of the node. Catches `sc-19835` ("Bayu Kit", 10 m away), which is NOT on
                 the account this node polls and which identity therefore misses. Also catches a re-registered
                 device and a second sensor on the same wall.
      hand       BAD_EXCLUDE, for what the operator knows is theirs and the first two missed.
    Ownership is not the test: a kit of the operator's at another address is a legitimate neighbour. The test is
    whether this node already measures that device.

    Distance from the node stands in for distance from each local sensor: every local sensor is inside
    LOCAL_RADIUS_M (500 m) of it by definition. A local sensor near the edge of that radius with a station 150 m
    beyond it on the far side would be missed; BAD_EXCLUDE is the answer if that ever happens.
    """
    own, byhand = own_ids or set(), exclude_ids or set()
    out: list[tuple[dict, str]] = []
    for row in rows:
        sid = str(row.get("station_id"))
        if row.get("latitude") is None or row.get("longitude") is None:
            out.append((row, "excluded: no coordinates")); continue
        d_m = sources.metres(node_lat, node_lon, float(row["latitude"]), float(row["longitude"]))
        if sid in own:
            out.append((row, "excluded: identity (this node polls it)"))
        elif d_m <= min_separation_m:
            out.append((row, f"excluded: proximity ({d_m:.0f} m from this node)"))
        elif sid in byhand:
            out.append((row, "excluded: by hand (BAD_EXCLUDE)"))
        elif sources.km(node_lat, node_lon, row["latitude"], row["longitude"]) > radius_km:
            out.append((row, "excluded: beyond the radius"))
        elif row.get("suspected_indoor") and not include_indoor:
            out.append((row, "excluded: suspected_indoor"))
        elif row.get("suspected_malfunctioning"):
            out.append((row, "excluded: suspected_malfunctioning"))
        elif row.get("stale"):
            out.append((row, f"excluded: stale ({row.get('age_hours')} h)"))
        elif sources._iso(row.get("observed_at")) is None:
            out.append((row, "excluded: no usable timestamp"))
        else:
            out.append((row, "included"))
    # Second pass: one device, one row. Same name AND within min_separation_m is the discriminator — measured, not
    # guessed. All 23 AirGradient/OpenAQ mirror pairs share a name; the three Smart Citizen kits 25 m apart at Kios
    # Utak Atik do not, and collapsing those would delete real sensors. Keep the direct network over the mirror,
    # then the fresher row, then the lower id, so the choice is stable between polls.
    for i, (row, verdict) in enumerate(out):
        if verdict != "included":
            continue
        rank = (str(row["station_id"]).startswith(MIRROR_PREFIXES), float(row.get("age_hours") or 0), str(row["station_id"]))
        for other, ov in out:
            if ov != "included" or other is row or other.get("name") != row.get("name"):
                continue
            if sources.metres(float(row["latitude"]), float(row["longitude"]), float(other["latitude"]), float(other["longitude"])) > min_separation_m:
                continue
            orank = (str(other["station_id"]).startswith(MIRROR_PREFIXES), float(other.get("age_hours") or 0), str(other["station_id"]))
            if orank < rank:
                out[i] = (row, f"excluded: same device as {other['station_id']}")
                break
    return out


def ring(hc, node_lat: float, node_lon: float, radius_km: float,
         skip_station_ids: set[str] | None = None, exclude_ids: set[str] | None = None,
         min_separation_m: float = 150.0, include_indoor: bool = False):
    """The ring: other people's stations around this node. Never `local` — at any distance, whatever the
    coordinates say. See verdicts() for which stations are dropped and why."""
    sensors, readings = [], []
    r = hc.get(LATEST)
    r.raise_for_status()
    for row, verdict in verdicts(r.json().get("readings", []), node_lat, node_lon, radius_km,
                                 skip_station_ids, exclude_ids, min_separation_m, include_indoor):
        if verdict != "included":
            continue
        ts = sources._iso(row.get("observed_at"))
        sid = f"bad-{row['station_id']}"
        sensors.append({
            "sensor_id": sid, "source": SOURCE, "name": f"{row.get('name')} ({row.get('source')})",
            "lat": row["latitude"], "lon": row["longitude"],
            "indoor": bool(row.get("suspected_indoor")), "local": False,
            "meta": {"network": row.get("source"), "corrected": row.get("pm25_corrected"),
                     "km": round(sources.km(node_lat, node_lon, row["latitude"], row["longitude"]), 2),
                     "attribution": ATTRIBUTION},
        })
        for k, metric in (("pm25", "pm25"), ("pm25_raw", "pm25_raw"), ("pm10", "pm10"), ("pm1", "pm1"),
                          ("temperature", "temp"), ("humidity", "humidity"), ("aqi", "aqi")):
            if row.get(k) is not None:
                readings.append((ts, sid, metric, float(row[k])))
    return sensors, readings


def _here() -> tuple[float, float] | None:
    lat, lon = settings.get("NODE_LAT", ""), settings.get("NODE_LON", "")
    return (float(lat), float(lon)) if lat and lon else None


def fetch(hc):
    """Off unless BAD_ENABLED=1 and the node knows where it is."""
    c, here = cfg(), _here()
    if not c["on"] or not here:
        return [], []
    return ring(hc, *here, c["radius_km"], own_ids(hc), c["exclude"], c["min_separation_m"], c["include_indoor"])


def audit(hc) -> list[dict]:
    """A verdict for every station the archive lists right now: GET /nearby?audit=1."""
    c, here = cfg(), _here()
    if not here:
        return []
    rows = hc.get(LATEST).json().get("readings", [])
    return [{"station_id": r["station_id"], "name": r.get("name"), "network": r.get("source"),
             "km": None if r.get("latitude") is None else round(sources.km(*here, r["latitude"], r["longitude"]), 2),
             "verdict": v}
            for r, v in verdicts(rows, *here, c["radius_km"], own_ids(hc), c["exclude"], c["min_separation_m"],
                                 c["include_indoor"])]
