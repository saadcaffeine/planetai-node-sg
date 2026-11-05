"""Who may read and write what: the node's tokens, the SHARE_LEVEL allowlists, and the checks the routes call.

Moved out of app/main.py unchanged (22 Oct 2026), so a router in its own module can check a token without importing
main. The two middlewares that apply SHARE_LEVEL and guard /mcp stay in main, beside the app they are registered on.
"""
import os
import secrets

from fastapi import HTTPException, Request

import settings


def AGG_TOKEN():
    return settings.get("AGGREGATE_TOKEN", "").strip()
def SHARE_LEVEL():
    return (settings.get("SHARE_LEVEL", "off") or "off").strip().lower()
def ACT_TOKEN():
    return settings.get("ACT_TOKEN", "").strip()


# What a request carrying no token may read at each SHARE_LEVEL: exact paths, plus the prefixes for the two routes that
# carry a wildcard. Anything not named here is refused — /place/geojson, /settings/raw, /backups, /aggregates and every
# write — so a route added next release is private until someone puts it on this list on purpose. That is the opposite
# of the SELECT * in /sensors, which published every new column the day it landed (A7).
#
# The `off` list is the dashboard's shell and the two reads that keep the node's own machinery running: /export, which
# backup.sh fetches over the published port to write the daily CC-BY file (already rounded to 3 dp and public by
# design), and /settings, reduced to UI_LAYOUT and SHARE_LEVEL by the route itself.
#
# The `open` list is what a wall screen on the house WiFi needs: the twenty-one paths the dashboard fetches
# (`grep -oE "(api|fetch)\('/[a-z0-9/._{}-]+" app/static/index.html`), less the three writes and /place/geojson, plus
# the two <img> routes that grep does not see (/earth/year.png at index.html:904, /earth/change.png from /earth's
# png_url) and the other-consumer reads /readings, /exports and /export.
# /sources is on the `open` list and named on purpose rather than left to default-private: it is a
# byte-identical copy of a public registry of public datasets, the same 209 rows on every node in a
# release. It says nothing about this house — not a sensor, not a reading, not a coordinate. /packs,
# already here, describes this node's own configuration and is more revealing than it is.
# /presence is here and not on the `open` list because the RETICULUM BRIDGE reads it, and the bridge
# is another container with no token: on the default SHARE_LEVEL=off it would be refused and presence
# would silently never announce. It is safe at every level by construction — it answers `{"enabled":
# false}` until a household turns announcing on, and after that it returns the same handful of facts
# the node is already broadcasting to every radio in reach.
# /nodes is here because it is the programme's public registry.json, the same on every node: it says which nodes
# exist and nothing about this house.
# /ground/* is on `open` because every layer under it is a public dataset (OpenStreetMap, OpenAerialMap, Sentinel-2,
# Open-Meteo) cut around the node, and its centre is no closer than the point /health already rounds. /geo/cell is
# there too, but the route drops what it says relative to the node (is_node, cells_from_node, *_polar) for a
# caller without a token: asked at res 15 cell by cell, those would find the house. The phone's walk needs both
# (Tomas, 12 Oct 2026: one phone mode, no token, for the person running the node).
_SHARE_OFF = (frozenset({"/", "/ui", "/workbench", "/tester", "/health", "/llms.txt", "/settings", "/export", "/presence", "/nodes"}), ("/static/",))
_SHARE_OPEN = (_SHARE_OFF[0] | frozenset({
    "/stats", "/sensors", "/observations", "/alerts", "/series", "/sparks", "/rho", "/cells", "/packs", "/packs/all", "/trust",
    "/report/latest", "/readings", "/reach", "/shape", "/effect",
    "/history", "/exports", "/sources",
    # The ask pane. Its context and every tool result are scrubbed of positions, names and ids (app/ask.py), so
    # it tells a reader nothing /issues does not; it is here, and not on `off`, because it spends this machine's
    # CPU on whoever asks, and `open` is the household saying the WiFi may.
    "/ask", "/ask/status", "/docs/search", "/geo/cell",
    # What the node learned about the place (outdoor stations' usual hours), never the house's: the Wall reads it.
    "/learned/place",
}), ("/static/", "/exports/", "/issues", "/sources/", "/ground/"))
# A pack's own routes add themselves (pack.yaml `share:`, packs.shared_open()), the forecast and nearby packs first.
import packs as _packs  # noqa: E402
_SHARE_OFF = (_SHARE_OFF[0] | frozenset(_packs.shared("off")), _SHARE_OFF[1])     # /offers: the things pack
_SHARE_OPEN = (_SHARE_OPEN[0] | frozenset(_packs.shared("open")), _SHARE_OPEN[1])
_SHARE = {"off": _SHARE_OFF, "open": _SHARE_OPEN}


def _node_tokens() -> list[str]:
    """Every token this node trusts as the household. A request carrying one is not what SHARE_LEVEL is about: it is
    the NAS pulling /backups, the agent, Home Assistant or someone in the house, and it reads exactly what it read
    before, from anywhere — which is the whole reason the setting can default to `off` without breaking a node on
    update. Each endpoint still checks its own token after this, so BACKUP_TOKEN getting past here does not unmask
    the Telegram token at /settings/raw.

    AGGREGATE_TOKEN is not one of them: every child node holds it, and a child is another household. Until 15 Oct
    2026 it was, and a child read its parent's sensor rooms, point and building as if it lived there. Its two
    writes pass the middleware by path (_CHILD_WRITES) and check the token themselves."""
    return [t for t in (os.getenv("ADMIN_TOKEN", "").strip(), settings.get("BACKUP_TOKEN", "").strip(),
                        ACT_TOKEN()) if t]


# What a child node sends its parent. Each route checks AGGREGATE_TOKEN itself and refuses without it, so letting
# them past SHARE_LEVEL opens nothing to a request with no token.
_CHILD_WRITES = frozenset({("POST", "/aggregates"), ("POST", "/events")})


def _is_local(request: Request) -> bool:
    """The socket's own peer address, never a header: X-Forwarded-For would make this a one-line bypass, and uvicorn
    runs without --proxy-headers (app/Dockerfile:19) so nothing populates it here anyway.

    Inside Docker this is true for the app's own MCP tools (agent.py talks to 127.0.0.1) and for a shell in the
    container, and false for the browser on the machine hosting it, which arrives as the bridge gateway. That is
    deliberate rather than an oversight: on a node whose Docker forwards through a VM — Colima, Lima — a LAN client
    arrives as the gateway too, so trusting the bridge would trust the whole WiFi and this setting would do nothing.
    Fail closed and let the household set `open`, or carry a token."""
    return (getattr(request.client, "host", "") or "") in ("127.0.0.1", "::1", "localhost")


def _bearer_ok(authorization: str, *tokens: str) -> bool:
    """True when the Authorization header carries one of `tokens`. Compared in constant time: `!=` returns at the first
    differing byte, which lets a caller on the LAN measure its way to a token one character at a time."""
    given = authorization.replace("Bearer ", "", 1).strip().encode()
    ok = False
    for t in tokens:
        if t and secrets.compare_digest(given, t.encode()):
            ok = True          # no early return: the time taken must not say which token matched
    return ok


def _pull_ok(authorization: str) -> None:
    """A read-only token for whoever collects backups (a NAS), separate from the admin token. Either works."""
    tokens = [t for t in (os.getenv("ADMIN_TOKEN", "").strip(), settings.get("BACKUP_TOKEN", "").strip()) if t]
    if not tokens:
        raise HTTPException(403, "no BACKUP_TOKEN or ADMIN_TOKEN set on this node")
    if not _bearer_ok(authorization, *tokens):
        raise HTTPException(401, "bad or missing token")


def _shows_private(request: Request, authorization: str = "", raw: bool = True) -> bool:
    """Whether this read may include `private` readings (packs.public_sql). Never for an agent, which says so with
    X-Agent on every call (app/agent.py), whatever token it carries: what a model reads can go to a provider. A raw
    route (rows, series) answers them to the admin token only; a readout (`raw=False`) to the household's own tokens
    (admin, act) or this machine. Until 14 Oct a readout went to anyone the page answered, which at SHARE_LEVEL=open is
    anyone on the network, and a parent's or a backup's token: the house's counts on a screen nobody in it owns."""
    if request.headers.get("x-agent"):
        return False
    if not raw:
        return _bearer_ok(authorization, os.getenv("ADMIN_TOKEN", "").strip(), ACT_TOKEN()) or _is_local(request)
    return _bearer_ok(authorization, os.getenv("ADMIN_TOKEN", "").strip())


def _admin(authorization: str) -> None:
    tok = os.getenv("ADMIN_TOKEN", "").strip()
    if not tok:
        raise HTTPException(403, "ADMIN_TOKEN is not set in .env; run `planetai ui` to create one")
    if not _bearer_ok(authorization, tok):
        raise HTTPException(401, "bad or missing admin token")
