"""app/issues/schema.py's CONTRACT names real columns, and the two row classifiers behave.

The point of the first half is that `app/issues/` never guesses. A column renamed or a view whose
SELECT list changed is caught here rather than as an empty stack on somebody's wall screen.

    python3 tests/test_issues_schema.py
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "app"))

from issues.schema import CONTRACT, DISTANCES, is_open, is_seen, place_of, stage_of  # noqa: E402

SQL = "\n".join(re.sub(r"--.*$", "", line) for line in (ROOT / "init.sql").read_text().splitlines())
fails = []


def columns_of(name: str) -> set[str]:
    """Every column init.sql gives this table or view.

    A view's columns are the items of its SELECT list, named by their `AS alias` where they have one
    and by their last identifier where they do not — `sensor_id, metric` in `readings_1h` are bare,
    and an extractor that only reads aliases silently accepts a CONTRACT naming columns that moved.
    A table's are the first word of each line inside its parentheses, plus every ALTER that adds one.
    """
    m = re.search(rf"CREATE VIEW {name} AS(.*?);", SQL, re.S)
    if m:
        sel = m.group(1)
        # the view's own SELECT is the first one at depth 0: a WITH's SELECTs sit inside its parentheses
        depth, at = 0, None
        for i, ch in enumerate(sel):
            depth += (ch == "(") - (ch == ")")
            if depth == 0 and sel.startswith("SELECT", i):
                at = i
                break
        sel = sel[at + 6:]
        sel = re.sub(r"^\s*DISTINCT ON \([^)]*\)", "", sel)
        # Split the SELECT list on commas at depth 0 and stop at the FROM that is also at depth 0.
        # Both matter: `avg(value) AS mean` holds its own comma-free parens, and stats' own
        # `extract(epoch FROM now() - max(r.ts))` carries a FROM three levels down.
        items, depth, buf = [], 0, ""
        for ch in sel:
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
            if depth == 0 and re.search(r"(^|\W)FROM\s*$", buf):
                buf = buf[: buf.upper().rindex("FROM")]
                break
            if ch == "," and depth == 0:
                items.append(buf); buf = ""
            else:
                buf += ch
        items.append(buf)
        out = set()
        for it in items:
            words = re.findall(r"\w+", it)
            if not words:
                continue
            out.add(re.search(r"\bAS (\w+)", it).group(1) if re.search(r"\bAS (\w+)", it) else words[-1])
        return out
    m = re.search(rf"CREATE TABLE IF NOT EXISTS {name} \((.*?)\n\);", SQL, re.S)
    if not m:
        return set()
    cols = {ln.strip().split()[0] for ln in m.group(1).splitlines() if ln.strip() and not
            ln.strip().upper().startswith(("UNIQUE", "PRIMARY", "CHECK", "FOREIGN", "CONSTRAINT"))}
    cols |= set(re.findall(rf"ALTER TABLE {name} ADD COLUMN IF NOT EXISTS (\w+)", SQL))
    return cols


for table, fields in CONTRACT.items():
    have = columns_of(table)
    if not have:
        fails.append(f"CONTRACT names {table}, which init.sql does not define")
        continue
    for f in fields:
        if f not in have:
            fails.append(f"CONTRACT says {table}.{f}, which is not a column of {table} in init.sql")

# --- place_of: the one function the custody spec changes -------------------------------------------
CASES = [
    ({"kind": "sensor", "local": True, "indoor": True}, "room"),
    ({"kind": "sensor", "local": True, "indoor": False}, "yard"),
    ({"kind": "sensor", "local": False, "indoor": False}, "ring"),
    ({"kind": "sensor", "local": False, "indoor": True}, "ring"),   # somebody else's, indoors: still theirs
    ({"kind": "model", "local": False, "indoor": False}, "region"),
    ({"kind": "portal", "local": True, "indoor": False}, "region"),  # a city statistic is not our yard
    ({"kind": "survey", "local": True, "indoor": True}, "region"),
    ({"kind": "child", "local": False, "indoor": False}, "child"),
    ({"local": True, "indoor": True}, "room"),                       # no kind: init.sql defaults to sensor
]
for row, want in CASES:
    got = place_of(row)
    if got != want:
        fails.append(f"place_of({row}) is {got!r}, expected {want!r}")

if set(DISTANCES) != {"room", "yard", "ring", "region"}:
    fails.append(f"DISTANCES is {DISTANCES}; the four distances are room, yard, ring, region")
if "child" in DISTANCES:
    fails.append("child is a place, not a distance — it must not be a column of a stack")

# --- stage_of / is_open: acknowledged is not acted ------------------------------------------------
A = {"id": 65}
OTHER = [{"alert_id": 53, "stage": "acted"}]                       # a different alert entirely
for actions, want_stage, want_open, want_seen in [
    ([], None, True, False),
    (OTHER, None, True, False),
    ([{"alert_id": 65, "stage": "acknowledged"}], "acknowledged", True, True),
    ([{"alert_id": 65, "stage": "acted"}], "acted", False, False),
    ([{"alert_id": 65, "stage": "measured"}], "measured", False, False),
    # order must not matter: over Telegram "I did it" often arrives before "I saw it"
    ([{"alert_id": 65, "stage": "acted"}, {"alert_id": 65, "stage": "acknowledged"}], "acted", False, False),
    ([{"alert_id": 65, "stage": "acknowledged"}, {"alert_id": 65, "stage": "measured"}], "measured", False, False),
    # 'settings' rows share the table and carry alert_id NULL; rho ignores them and so must this
    ([{"alert_id": None, "stage": "settings"}], None, True, False),
]:
    if stage_of(A, actions) != want_stage:
        fails.append(f"stage_of on {actions} is {stage_of(A, actions)!r}, expected {want_stage!r}")
    if is_open(A, actions) != want_open:
        fails.append(f"is_open on {actions} is {is_open(A, actions)}, expected {want_open}")
    if is_seen(A, actions) != want_seen:
        fails.append(f"is_seen on {actions} is {is_seen(A, actions)}, expected {want_seen}")

if stage_of({"id": None}, [{"alert_id": None, "stage": "acted"}]) is not None:
    fails.append("an alert with no id must match no action row, or every settings row closes it")

print("\n".join(f"  x {f}" for f in fails) or
      f"  issues/schema: {sum(len(v) for v in CONTRACT.values())} contract fields exist in init.sql; "
      f"place_of sorts {len(CASES)} rows; acknowledged is not acted")
sys.exit(1 if fails else 0)
