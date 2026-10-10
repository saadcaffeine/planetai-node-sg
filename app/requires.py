"""Which node versions a pack works with: its pack.yaml's `requires: { node: ">=0.40.0" }`, held against this node.

Standard library only, and Python 3.9: the app imports it, and so does the CLI (`planetai packs`), which runs on
the node's own Python and has no YAML. One rule in one place, so the loader that refuses a pack and the command that
says why cannot disagree (docs/decisions/2026-10-01-packs.md, point 6).
"""
from __future__ import annotations

import re

_CLAUSE = re.compile(r"^\s*(>=|<=|==|>|<)\s*v?(\d+)\.(\d+)(?:\.(\d+))?\s*$")


def release_of(v: str) -> tuple | None:
    """The release a version string is at: `v0.75.7`, and `v0.75.7-14-gafc298a` from a git checkout ahead of it,
    are both (0, 75, 7). A checkout that is ahead of a release is still at that release: node #1 tracks main, and
    on v0.75.7-14 it has not got v0.75.8. None for anything that names no release (a bare sha, `dev`, `?`)."""
    m = re.match(r"v(\d+)\.(\d+)(?:\.(\d+))?(?=$|-)", v or "")
    return tuple(int(x or 0) for x in m.groups()) if m else None


def check(spec, here: str) -> str | None:
    """None when a node at version `here` may load a pack that requires `spec` (">=0.40.0", or clauses joined by
    commas: ">=0.40.0, <0.90.0"). Otherwise the reason, as one sentence a person can act on.

    A node that cannot say which release it is at (`dev`, a bare sha, unset) loads the pack: refusing every pack on a
    developer's checkout would be worse than the rare pack that needs a newer node. A spec that is not a version
    range is refused, because nobody can tell which nodes it was written for."""
    if spec is None or str(spec).strip() == "":
        return None
    clauses = [_CLAUSE.match(c) for c in str(spec).split(",")]
    if not all(clauses):
        return f"its requires: node is {str(spec)!r}, which is not a version range like >=0.40.0"
    mine = release_of(here)
    if mine is None:
        return None
    for m in clauses:
        op, want = m.group(1), tuple(int(x or 0) for x in m.groups()[1:])
        ok = {">=": mine >= want, ">": mine > want, "<=": mine <= want, "<": mine < want, "==": mine == want}[op]
        if not ok:
            return (f"it needs a node {str(spec).strip()} and this node is {here}"
                    + ("; planetai update first" if mine < want else ""))
    return None
