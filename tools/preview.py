#!/usr/bin/env python3
"""The dashboard, browsable, from a committed fixture and no database.

    python3 tools/preview.py [fixture] [--port 8123]
    open http://127.0.0.1:8123/?fixture=<name>

WHY THIS EXISTS. Reviewing the page meant one of two things: static renders from
`tests/visual/measure.mjs`, which nobody can click, or a whole node with Postgres and Docker behind
it. This is the third: a real browser on the real page, with a real capture of a real node, and
nothing to install. Every number on it is node #1's.

IT SERVES WHAT THE NODE SERVES AND NOT ONE PATH MORE. `COMPANIONS` is imported from `app/main.py`
rather than reimplemented, and `/static/<name>` takes a NAME — no slashes, no traversal, no falling
through to the directory layout. The measuring rig once fell through to the layout, served
`/static/fonts/x.woff2`, and so hid for weeks that the mono had never loaded on a node. A preview
that is more generous than the thing it previews reports a page that does not exist.

The routes are the snapshot's own keys under the paths the node answers them at, which is what
`serveNodeAPI()` in the rig does for the same reason. `/issues` is REPLAYED through the engine rather
than served from the file, so what you read is what this checkout's code makes of that data — which
is the point of previewing a branch.
"""
import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "app"))
os.environ.setdefault("PACKS_DIR", str(ROOT / "packs"))
os.environ.setdefault("RULES_PATH", str(ROOT / "config" / "rules.yml"))
# Same shape as PACKS_DIR: the default is the container path /app/data/sources, so a checkout
# loads an empty registry and /sources answers 503 with nothing saying why.
os.environ.setdefault("SOURCES_DIR", str(ROOT / "data" / "sources"))
# main.py builds a connection string at import and never connects here. Without this it raises on
# DATABASE_URL, the COMPANIONS import below falls back, and the fallback is MORE PERMISSIVE than the
# node — which is the whole thing this file's docstring says it must not be.
os.environ.setdefault("DATABASE_URL", "postgresql://preview@127.0.0.1:1/preview")

# Extra library search paths on developer macOS machines (e.g. h3)
for extra in ("/opt/homebrew/Caskroom/miniconda/base/lib/python3.14/site-packages",):
    if Path(extra).is_dir() and extra not in sys.path:
        sys.path.append(extra)

# Stub psycopg if the native libpq is absent: preview.py never queries the database
if "psycopg" not in sys.modules:
    try:
        import psycopg  # noqa: F401
    except Exception:
        import types
        stub_pg = types.ModuleType("psycopg")
        stub_pg.connect = lambda *a, **kw: None
        stub_pg_rows = types.ModuleType("psycopg.rows")
        stub_pg_rows.dict_row = None
        stub_pg_types = types.ModuleType("psycopg.types.json")
        stub_pg_types.Jsonb = lambda x: x
        sys.modules["psycopg"] = stub_pg
        sys.modules["psycopg.rows"] = stub_pg_rows
        sys.modules["psycopg.types"] = types.ModuleType("psycopg.types")
        sys.modules["psycopg.types.json"] = stub_pg_types

import settings                                   # noqa: E402
from issues import engine, load                   # noqa: E402

FIXTURES = ROOT / "app" / "issues" / "fixtures"
# The design repo's plan, which this repository does not carry. Absent is a supported state: the
# ground draws the grid and says it has no plan, exactly as a node without the place pack does.
PLAN = Path(os.environ.get("PLANETAI_DESIGN_REPO", ROOT.parent / "planetai-design")) / "data" / "place.geojson"

# Snapshot key -> the path the node answers it at. Anything not here is a 404, as it would be.
FROM_SNAPSHOT = {
    "/health": "health", "/sensors": "sensors", "/cells": "cells", "/trust": "trust",
    "/forecast": "forecast", "/stats": "stats", "/rho": "rho", "/reach": "reach",
    "/alerts": "alerts", "/observations": "observations",
    "/nearby": "nearby", "/report/latest": "report_latest", "/earth": "earth",
    # Captures taken before `planetai snapshot` learned to fetch it carry no `shape`, and the 404
    # below is then the right answer: the section's own absent line is one of its two real states,
    # and inventing a shape here would be the preview describing a pattern no node has seen.
    "/shape": "shape", "/effect": "effect",
}


def companions():
    """The node's own static allowlist, imported from main.py. No fallback, on purpose.

    main.py starts its pollers and its MQTT thread at import, and here they would hammer a database
    that is not there. So `Thread.start` is a no-op for the duration of the import: the module is
    wanted for one dict, not for its behaviour.

    A failure is FATAL rather than a flat mirror of app/static. The first version of this function
    fell back, and the fallback served OFL-Figtree.txt and every file under fonts/ — a preview more
    generous than the node, which is the one thing the docstring above says it must never be."""
    import threading                              # noqa: PLC0415
    started = threading.Thread.start
    threading.Thread.start = lambda self: None
    try:
        import main                               # noqa: PLC0415
        return main.COMPANIONS
    except Exception as e:                        # noqa: BLE001
        sys.exit(f"app/main.py did not import, so the node's own static allowlist is unavailable "
                 f"and this preview will not guess at it: {e}")
    finally:
        threading.Thread.start = started


TYPES = {".css": "text/css", ".js": "text/javascript", ".svg": "image/svg+xml",
         ".json": "application/json", ".html": "text/html", ".ttf": "font/ttf",
         ".woff2": "font/woff2", ".txt": "text/plain"}
COMPANIONS = companions()
_cache: dict[str, dict] = {}


def snapshot(name: str) -> dict:
    """The fixture with its issues replayed by THIS checkout, cached per name."""
    if name not in _cache:
        snap = json.loads((FIXTURES / f"{name}.json").read_text())
        snap["issues"] = engine.replay(snap, settings, load())
        _cache[name] = snap
    return _cache[name]


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):                    # one line per request, not three
        pass

    def send(self, code, body, ctype="application/json"):
        raw = body if isinstance(body, bytes) else json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-cache, must-revalidate")
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):                             # noqa: N802
        u = urlparse(self.path)
        q = parse_qs(u.query)
        fx = (q.get("fixture") or [DEFAULT])[0]
        p = u.path

        if p in ("/", "/ui", "/index.html"):
            # The page reads ?fixture= from its own location, and a preview with no fixture asks a
            # node that is not there. So a bare / redirects to one rather than rendering the
            # refusal: this server exists to show a capture, and which capture is its business.
            if "fixture" not in q:
                self.send_response(302)
                self.send_header("Location", f"{p}?fixture={DEFAULT}")
                self.end_headers()
                return None
            page = "index.html" if (q.get("layout") or [""])[0] == "classic" else "doors.html"   # app/main.py::ui
            return self.send(200, (ROOT / "app" / "static" / page).read_bytes(), "text/html")

        if p.startswith("/static/"):
            name = p[len("/static/"):]
            # A NAME, not a path — the node's own rule. This is the line the rig lost.
            hit = COMPANIONS.get(name) if "/" not in name else None
            if not hit or not Path(hit[0]).is_file():
                return self.send(404, {"detail": "no such asset"})
            ctype = hit[1] or TYPES.get(Path(hit[0]).suffix, "application/octet-stream")
            return self.send(200, Path(hit[0]).read_bytes(), ctype)

        if p.startswith("/issues/fixtures/"):
            name = p.rsplit("/", 1)[-1]
            if not (FIXTURES / f"{name}.json").is_file():
                return self.send(404, {"detail": f"no such fixture: {name}"})
            return self.send(200, snapshot(name))

        if p == "/issues":
            return self.send(200, snapshot(fx)["issues"])

        if p == "/sources":
            # The registry is a pinned file this repository carries (data/sources), not something a
            # capture of one node has: registry.load() is what app/main.py::sources_ reads too.
            import registry                       # noqa: PLC0415
            entries, ver = registry.load()
            if not entries:
                return self.send(503, {"detail": "no source registry in this checkout"})
            rows = registry.find()
            return self.send(200, {"registry": {k: ver.get(k) for k in
                                                ("sha", "short", "synced", "entries")},
                                   "count": len(rows), "sources": rows})

        if p == "/settings":
            return self.send(200, settings.describe(unlocked=False, public=settings.PUBLIC))

        if p == "/place/geojson":
            if not PLAN.is_file():
                return self.send(404, {"detail": "no place plan in this checkout"})
            return self.send(200, PLAN.read_bytes(), "application/geo+json")

        if p == "/actions":
            # THE NODE REFUSES THIS WITHOUT A TOKEN, AT EVERY SHARE LEVEL, and so does this. It is on
            # neither allowlist in app/main.py because `actor` and `note` are the household's own
            # words about what it did in its own house. Serving them here because they happen to be
            # in the file would make the preview more generous than the thing it previews — the one
            # rule this server has — and it would have shown a page that no reader of a real node
            # can see. Pass ?token= to read them, which is the preview's stand-in for holding one.
            if not (q.get("token") or self.headers.get("authorization")):
                return self.send(403, {"error": "this node is set to SHARE_LEVEL=off, so /actions "
                                                "answers only this machine or a request carrying a "
                                                "token."})
            body = snapshot(fx).get("actions")
            if body is None:
                return self.send(404, {"detail": "this snapshot carries no actions"})
            return self.send(200, body)

        if p in FROM_SNAPSHOT:
            body = snapshot(fx).get(FROM_SNAPSHOT[p])
            # A key the capture does not carry is a 404, as a node with that route off would answer —
            # never an empty list, which would be this file claiming the node looked and found none.
            if body is None:
                return self.send(404, {"detail": f"this snapshot carries no {FROM_SNAPSHOT[p]}"})
            return self.send(200, body)

        return self.send(404, {"detail": f"this preview does not serve {p}"})


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    DEFAULT = args[0] if args else "node1-2026-09-21d"
    port = 8123
    if "--port" in sys.argv:
        port = int(sys.argv[sys.argv.index("--port") + 1])
    if not (FIXTURES / f"{DEFAULT}.json").is_file():
        have = ", ".join(sorted(p.stem for p in FIXTURES.glob("*.json")))
        sys.exit(f"no fixture {DEFAULT}. This checkout has: {have}")
    # REFUSE A PORT SOMEBODY ELSE HOLDS. This bound 127.0.0.1 while another session already had a
    # `python3 -m http.server` on the same port over IPv6, and both stayed up: curl reached this one
    # over 127.0.0.1 and the browser reached theirs over localhost, which resolves to ::1 first. The
    # page then half-worked — real data from here, 404s for every font from there — and the 404s
    # looked like bugs in this file. Checking both families makes that state impossible to be in.
    import socket                                 # noqa: PLC0415
    for fam, host in ((socket.AF_INET, "127.0.0.1"), (socket.AF_INET6, "::1")):
        probe = socket.socket(fam, socket.SOCK_STREAM)
        probe.settimeout(0.4)
        taken = probe.connect_ex((host, port)) == 0
        probe.close()
        if taken:
            sys.exit(f"something is already listening on {host}:{port} — probably another session.\n"
                     f"  Pick another: python3 tools/preview.py {DEFAULT} --port {port + 1}\n"
                     f"  (a server on the other address family is the confusing case: the browser\n"
                     f"   resolves localhost to ::1 first, so it would reach theirs and not this.)")
    snapshot(DEFAULT)                             # replay once up front, so a failure is loud here
    print(f"  the page, from {DEFAULT}, on http://127.0.0.1:{port}/?fixture={DEFAULT}")
    print(f"  views: #now  #historical  #network  #wall  #arrange  #setup")
    ThreadingHTTPServer(("127.0.0.1", port), H).serve_forever()
