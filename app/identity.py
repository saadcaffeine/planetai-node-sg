"""Who this node is, and who is pushing to it: an Ed25519 key, its ID, and the signature on every up-link push.

    node_id()                   this node's ID: the first 16 base32 characters of sha256(public key). None without NODE_KEY.
    public_key()                its public key, base64. Both are public: /health publishes them.
    headers(route, body)        the four X-Node-* headers that sign `body` for the parent's `route`. {} without a key.
    post(parent, route, payload, token)
                                every push upstream: serialises `payload` once, signs those bytes, posts them.
    admit(cur, name, route, body, headers, listed)
                                parent side: verify the signature, pin the child's key on first contact, refuse a
                                changed one. Raises HTTPException with a sentence.

docs/SPEC_identity.md is the argument. The private key is NODE_KEY in .env, 32 random bytes as hex, written by
install.sh and update.sh; it is never printed, logged or returned by anything here.
"""
from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import time
from functools import lru_cache

import httpx
from fastapi import HTTPException

log = logging.getLogger("planetai.identity")
VERSION = "planetai-node-v1"
SKEW = 600          # seconds either way; the whole replay defence, because every signed route is an idempotent upsert
LISTED: list = []   # registry.json's nodes, as main.check_registry last read them: a listed name pins only to its id


def id_of(key_b64: str) -> str:
    """The ID a public key hashes to. Standard library only, so bin/planetai and the tests derive the same thing."""
    raw = base64.b64decode(key_b64)
    return base64.b32encode(hashlib.sha256(raw).digest()).decode().lower()[:16]


@lru_cache(maxsize=1)
def _private():
    seed = os.getenv("NODE_KEY", "").strip()
    try:
        raw = bytes.fromhex(seed)
    except ValueError:
        raw = b""
    if len(raw) != 32:
        if seed:
            log.warning("NODE_KEY in .env is not 64 hex characters; this node pushes unsigned until it is")
        return None
    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    except ImportError:       # an image built before app/requirements.txt named it; `planetai update` rebuilds it
        log.warning("NODE_KEY is set but this image has no cryptography; this node pushes unsigned until it is rebuilt")
        return None
    return Ed25519PrivateKey.from_private_bytes(raw)


def public_key() -> str | None:
    k = _private()
    if not k:
        return None           # before the import: /health answers on a node whose image has no cryptography yet
    from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
    return base64.b64encode(k.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)).decode()


def node_id() -> str | None:
    key = public_key()
    return id_of(key) if key else None


def _message(route: str, ts: str, body: bytes) -> bytes:
    return f"{VERSION}\n{route}\n{ts}\n{hashlib.sha256(body).hexdigest()}".encode()


def headers(route: str, body: bytes) -> dict:
    k = _private()
    if not k:
        return {}
    ts = str(int(time.time()))
    return {"X-Node-Id": node_id(), "X-Node-Key": public_key(), "X-Node-Ts": ts,
            "X-Node-Signature": base64.b64encode(k.sign(_message(route, ts, body))).decode()}


def post(parent: str, route: str, payload: dict, token: str = "") -> httpx.Response:
    """POST `payload` to `parent` + `route`, signed. The bytes signed are the bytes sent, so the body is serialised
    here and posted as content, never json=: json= would serialise it again after signing. Raises httpx.HTTPError when
    the parent cannot be reached; a refusal comes back as the response, for the caller to say."""
    body = json.dumps(payload).encode()
    h = {"Content-Type": "application/json", **headers(route, body)}
    if token:
        h["Authorization"] = f"Bearer {token}"
    return httpx.post(f"{parent}{route}", content=body, headers=h, timeout=30)


def refusal(r: httpx.Response) -> str:
    """The sentence a parent refused with, or "" when it gave none (a proxy's HTML error page)."""
    try:
        why = r.json().get("detail")
    except Exception:  # noqa: BLE001
        why = None
    return why if isinstance(why, str) else ""


def verify(route: str, body: bytes, h) -> tuple[str, str] | None:
    """(node_id, public_key) for a good signature, None for an unsigned push. Raises 401 for anything else."""
    nid, key, ts, sig = (h.get(f"x-node-{k}", "") for k in ("id", "key", "ts", "signature"))
    if not (nid or key or ts or sig):
        return None
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    try:
        if id_of(key) != nid:
            raise ValueError("id")
        if abs(time.time() - int(ts)) > SKEW:
            raise HTTPException(401, f"this push was signed at {ts}, more than {SKEW // 60} minutes from this "
                                     "parent's clock; check the clock on both machines")
        Ed25519PublicKey.from_public_bytes(base64.b64decode(key)).verify(base64.b64decode(sig), _message(route, ts, body))
    except HTTPException:
        raise
    except (ValueError, TypeError, InvalidSignature):
        raise HTTPException(401, f"the signature on this push does not verify for node {nid or '?'}; it is refused") from None
    return nid, key


def admit(cur, name: str, route: str, body: bytes, h, listed: list | None = None) -> str | None:
    """Parent side, after the token. Returns the child's node_id, or None for an unsigned child not yet pinned.

    One row per name, one name per key (init.sql 0.63, docs/SPEC_identity.md §5). A name is pinned to the first key
    that signs under it, unless registry.json lists that name with another ID."""
    signed = verify(route, body, h)
    cur.execute("SELECT name, node_id, public_key, first_seen FROM children WHERE name = %s OR node_id = %s",
                (name, signed[0] if signed else None))
    rows = cur.fetchall()
    mine = next((r for r in rows if r["name"] == name), None)
    since = mine and mine["first_seen"].date().isoformat()
    if not signed:
        if mine and mine["node_id"]:
            raise HTTPException(401, f"{name} signs its pushes here since {since}; an unsigned push under its name "
                                     "is refused")
        cur.execute("INSERT INTO children (name) VALUES (%s) ON CONFLICT (name) DO UPDATE SET last_seen = now()", (name,))
        log.info("unsigned push from %s: it signs once it updates", name)
        return None
    nid, key = signed
    if mine and mine["node_id"] and mine["public_key"] != key:
        raise HTTPException(409, f"{name} is pinned here to node {mine['node_id']} since {since}, and this push is "
                                 f"signed by node {nid}. If {name} lost its key, the keeper of this parent runs "
                                 f"`planetai children forget {name}` and its next push is pinned.")
    other = next((r for r in rows if r["node_id"] == nid and r["name"] != name), None)
    if other:
        raise HTTPException(409, f"node {nid} is pinned here as {other['name']}, and now calls itself {name}. Set its "
                                 f"NODE_NAME back to {other['name']}, or run `planetai children forget {other['name']}` "
                                 "on this parent.")
    if not (mine and mine["node_id"]):
        listed_id = next((n.get("id") for n in (LISTED if listed is None else listed) if n.get("name") == name and n.get("id")), None)
        if listed_id and listed_id != nid:
            raise HTTPException(409, f"registry.json lists {name} as node {listed_id}, and this push is signed by node "
                                     f"{nid}. If {name} has a new key, its keeper runs `planetai hello` to list it.")
        log.info("pinned %s to node %s", name, nid)
    cur.execute("""INSERT INTO children (name, node_id, public_key) VALUES (%s, %s, %s)
                   ON CONFLICT (name) DO UPDATE SET node_id = EXCLUDED.node_id, public_key = EXCLUDED.public_key,
                                                    last_seen = now()
                   WHERE children.node_id IS NULL OR children.public_key = EXCLUDED.public_key""", (name, nid, key))
    if cur.rowcount == 0:      # another key pinned this name between the SELECT and here
        raise HTTPException(409, f"{name} was pinned to another node a moment ago; this push is refused")
    return nid
