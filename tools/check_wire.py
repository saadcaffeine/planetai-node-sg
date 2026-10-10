"""The six wire formats' top-level keys are a committed file, and changing one is a deliberate act.

ARCHITECTURE.md §3 names the contracts that must not change casually. "Casually" is the operative
word: nothing stopped a key being added to `/export` — pinned to IPFS forever — or dropped from
`GET /issues` in a commit about something else. Now `tests/data/wire/<format>.json` holds the top-level
key list of each document, and this fails when the source and the fixture disagree. Updating a wire
format means editing two files in the same commit, one of which is a reviewer's eye.

It does NOT check values, types, or anything nested. Those change every hour; the top level is the
contract, and a contract that tried to pin the readings would be updated by a cron and assert nothing.

Read statically, with `ast`, for two reasons: `make lint` runs on a node with no database and in CI
with no Postgres, and a regex over a dict literal that spans forty lines and nests four deep is the
flimsier algorithm for the same effort.

`**expr` at the top level of a wire document is REFUSED rather than resolved. A splat is how a key
gets into a document without appearing in it, which is precisely what this gate exists to stop.

Run: python3 tools/check_wire.py          Update:  python3 tools/check_wire.py --update
"""
import ast
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "tests" / "data" / "wire"

# format -> (file, how to find the dict literal)
#   ("func", name)  the dict this function returns
#   ("post", name)  the `json=` keyword of the httpx.post inside this function
FORMATS = {
    "issues-v0":     ("app/issues/engine.py", ("func", "compute")),
    "export-v0":     ("app/main.py", ("func", "export")),
    "report-v0":     ("app/main.py", ("func", "report_latest")),
    "aggregates-v0": ("app/main.py", ("post", "push_aggregates")),
    "events-v0":     ("app/main.py", ("post", "push_events")),
    "days-v0":       ("app/issues/engine.py", ("func", "days")),
}

errs: list[str] = []


def _keys(node: ast.Dict, where: str) -> list[str]:
    out = []
    for k in node.keys:
        if k is None:
            errs.append(f"{where}: a `**` at the top level of a wire document. A key that does not "
                        f"appear in the literal cannot be reviewed; write the keys out.")
            continue
        if not isinstance(k, ast.Constant) or not isinstance(k.value, str):
            errs.append(f"{where}: a computed top-level key. Wire keys are literal strings.")
            continue
        out.append(k.value)
    return out


def _find(path: str, how: tuple[str, str]) -> list[str] | None:
    kind, name = how
    tree = ast.parse((ROOT / path).read_text())
    fn = next((n for n in ast.walk(tree)
               if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == name), None)
    if fn is None:
        errs.append(f"{path}: no function {name}() — this gate is pointed at code that moved")
        return None
    where = f"{path}::{name}"
    if kind == "func":
        # the LAST `return {...}` in the function: the early returns are guards, the final one is the
        # document. A function whose last return is not a dict literal is one this gate cannot read,
        # and saying so is better than reading the wrong thing.
        dicts = [n.value for n in ast.walk(fn) if isinstance(n, ast.Return) and isinstance(n.value, ast.Dict)]
        if dicts:
            return _keys(dicts[-1], where)
        # `out = {...}` … `return out`, which is what a handler looks like once it has a branch in it.
        # Follow the name to its last dict-literal assignment. Anything else — a comprehension, a call,
        # a merge — is a shape this gate cannot read, and it says so rather than guessing.
        ret = [n.value for n in ast.walk(fn) if isinstance(n, ast.Return) and isinstance(n.value, ast.Name)]
        if ret:
            target = ret[-1].id
            asg = [n.value for n in ast.walk(fn) if isinstance(n, ast.Assign) and isinstance(n.value, ast.Dict)
                   and any(isinstance(t, ast.Name) and t.id == target for t in n.targets)]
            if asg:
                keys = _keys(asg[-1], where)
                # A key added later by subscript — `out["note"] = …` — is a key of the document that is
                # not in the literal. Same objection as `**`: write it into the literal, as None if it
                # is conditional, so the shape is one thing a reader can see.
                extra = sorted({n.slice.value for n in ast.walk(fn)
                                if isinstance(n, ast.Subscript) and isinstance(n.ctx, ast.Store)
                                and isinstance(n.value, ast.Name) and n.value.id == target
                                and isinstance(n.slice, ast.Constant) and isinstance(n.slice.value, str)}
                               - set(keys))
                if extra:
                    errs.append(f"{where}: {', '.join(extra)} added to the document by subscript after the "
                                f"literal. Put every key in the literal — None when it is conditional — so "
                                f"the shape is one thing a reader can see.")
                return keys
        errs.append(f"{where}: returns no dict literal, so its wire shape cannot be read here")
        return None
    for call in (n for n in ast.walk(fn) if isinstance(n, ast.Call)):
        for kw in call.keywords:
            if kw.arg == "json" and isinstance(kw.value, ast.Dict):
                return _keys(kw.value, where)
    errs.append(f"{where}: no `json={{...}}` literal in the post — the push body cannot be read here")
    return None


update = "--update" in sys.argv
FIXTURES.mkdir(parents=True, exist_ok=True)
checked = 0

for fmt, (path, how) in sorted(FORMATS.items()):
    found = _find(path, how)
    if found is None:
        continue
    if "schema" not in found:
        errs.append(f"{path}::{how[1]} builds the {fmt} document and its top-level keys do not include "
                    f"`schema`. Every wire document says which document it is.")
    fx = FIXTURES / f"{fmt}.json"
    want = {"schema": fmt, "source": f"{path}::{how[1]}", "keys": sorted(found)}
    if update:
        fx.write_text(json.dumps(want, indent=2) + "\n")
        print(f"  wrote {fx.relative_to(ROOT)}  ({len(found)} keys)")
        continue
    if not fx.exists():
        errs.append(f"{fmt}: no fixture at {fx.relative_to(ROOT)}. Run: python3 tools/check_wire.py --update")
        continue
    have = json.loads(fx.read_text())
    gained = sorted(set(want["keys"]) - set(have.get("keys", [])))
    lost = sorted(set(have.get("keys", [])) - set(want["keys"]))
    if gained or lost:
        errs.append(
            f"{fmt} changed shape and {fx.relative_to(ROOT)} did not."
            + (f"\n      gained: {', '.join(gained)}" if gained else "")
            + (f"\n      lost:   {', '.join(lost)}" if lost else "")
            + "\n      A wire format is a contract. If the change is intended, run"
              " `python3 tools/check_wire.py --update` and commit the fixture WITH the change."
            + ("\n      A LOST key is a breaking change: ARCHITECTURE.md §3 says the version bumps and"
               " the bump is a docs/decisions/ entry." if lost else ""))
        continue
    if have.get("source") != want["source"]:
        errs.append(f"{fmt}: the fixture says it was read from {have.get('source')!r}, this gate read "
                    f"{want['source']!r}. Re-run with --update.")
        continue
    checked += 1

if errs:
    for e in errs:
        print(f"  x {e}")
    sys.exit(1)
print(f"  {checked} wire format(s) match their fixtures in tests/data/wire/")
