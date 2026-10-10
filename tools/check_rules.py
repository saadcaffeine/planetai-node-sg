"""Validate every rule and Index cell against the schema in init.sql, without a database.

Catches the failures that are silent at runtime:
  · SQL referencing a column a view does not have  -> the rule is logged as failed and skipped, forever
  · a message placeholder the SQL never returns    -> main.py falls back to printing the raw template with braces
  · a cell whose SQL has no `value` column         -> the cell is silently never emitted
  · a rule with a cooldown so long it can only fire once  -> looks like "nothing works" (this bit test-alert)

Needs sqlglot (dev only; CI installs it). Run: python3 tools/check_rules.py
"""
import glob
import re
import sys

import sqlglot
import yaml
from sqlglot import exp
from sqlglot.errors import ErrorLevel

SQL = open("init.sql").read()
errs, checked = [], 0


def schema() -> dict[str, set[str]]:
    """Table and view columns, from init.sql.

    ErrorLevel.IGNORE, because sqlglot 27 reads `GENERATED ALWAYS AS (expr) STORED` in an ALTER as GENERATED
    AS IDENTITY and raises on it — Postgres has accepted that form since 12. Raising took the whole checker
    down, and the Makefile's fallback then printed "rule check skipped", so a gate that had crashed looked
    like a gate that had not run on purpose. IGNORE parses what it cannot read as an opaque Command, exactly
    as it already did for this file's DO block and its GRANTs, and the ALTER regex below picks up the columns.
    A genuinely malformed CREATE TABLE still fails loudly: the table drops out of the schema and every rule
    that names it is reported."""
    out: dict[str, set[str]] = {}
    # sqlglot reads CREATE MATERIALIZED VIEW ... WITH NO DATA as an opaque Command, which left usual_by_hour out of
    # the schema; as a plain view it is the same select list.
    sql = SQL.replace("CREATE MATERIALIZED VIEW", "CREATE VIEW").replace("WITH NO DATA", "")
    for st in sqlglot.parse(sql, read="postgres", error_level=ErrorLevel.IGNORE):
        if not isinstance(st, exp.Create):
            continue
        name = getattr(getattr(st.this, "this", None), "name", None)
        if not name:
            continue
        if st.kind == "TABLE":
            out[name] = {c.name for c in st.find_all(exp.ColumnDef)}
        elif st.kind == "VIEW":
            # a view ending in UNION ALL (recent_15m) names its columns by its first SELECT
            body = st.expression
            while isinstance(body, exp.Union):
                body = body.this
            out[name] = {e.alias_or_name for e in getattr(body, "expressions", [])}
    for m in re.finditer(r"ALTER TABLE (\w+) ADD COLUMN IF NOT EXISTS (\w+)", SQL):
        out.setdefault(m.group(1), set()).add(m.group(2))
    return out


S = schema()
# columns Postgres provides that are not in any table
FREE = {"now", "current_setting", "value", "count", "avg", "sum", "min", "max", "round", "extract"}


def check_sql(where: str, query: str) -> set[str]:
    """Returns the query's output column names. Appends any unknown-column errors."""
    try:
        tree = sqlglot.parse_one(query, read="postgres")
    except Exception as e:  # noqa: BLE001
        errs.append(f"{where}: SQL does not parse ({e})")
        return set()

    # which real tables/views this query reads, and the aliases pointing at them
    alias_of: dict[str, str] = {}
    used: set[str] = set()
    for t in tree.find_all(exp.Table):
        if t.name in S:
            used.add(t.name)
            alias_of[t.alias or t.name] = t.name
        elif t.name not in {c.alias for c in tree.find_all(exp.CTE)}:
            errs.append(f"{where}: reads unknown table/view `{t.name}`")

    known = set().union(*(S[t] for t in used)) if used else set()
    # a CTE body can be a UNION, whose own .expressions is not the select list — walk to the first SELECT
    # every SELECT inside a CTE contributes aliases (UNION branches, nested subqueries included)
    cte_cols = set()
    for c in tree.find_all(exp.CTE):
        for sel in c.this.find_all(exp.Select):
            cte_cols |= {a.alias_or_name for a in sel.expressions}
        if isinstance(c.this, exp.Select):
            cte_cols |= {a.alias_or_name for a in c.this.expressions}
    for col in tree.find_all(exp.Column):
        if col.table and col.table in alias_of:
            if col.name not in S[alias_of[col.table]]:
                errs.append(f"{where}: `{col.table}.{col.name}` is not a column of `{alias_of[col.table]}`")
        elif col.name not in known and col.name not in cte_cols and col.name not in FREE:
            errs.append(f"{where}: column `{col.name}` is in none of {sorted(used) or ['(no table)']}")

    top = tree.find(exp.Select)
    return {e.alias_or_name for e in top.expressions} if top else set()


for f in sorted(glob.glob("config/rules.yml") + glob.glob("packs/*/rules.yml")):
    for r in yaml.safe_load(open(f)) or []:
        checked += 1
        where = f"{f}:{r.get('id')}"
        outs = check_sql(where, r["sql"])
        cd = r.get("cooldown_minutes", 60)
        if cd > 20160 and not r.get("long_cooldown_ok"):      # a fortnight
            errs.append(f"{where}: cooldown {cd} min is over a fortnight — it can fire about once. If deliberate, add `long_cooldown_ok: true`")
        msg = r.get("message")
        # `contributes:` (app/packs.py CONTRIBUTES) makes a rule part of something the node builds rather than
        # something it sends. Either it has a message or it contributes; a rule with neither reaches nobody, and a
        # rule with both looks like an alert and is never sent.
        con = r.get("contributes")
        if con and con not in ("report",):
            errs.append(f"{where}: `contributes: {con}` is not something a rule can contribute to")
        if con and msg:
            errs.append(f"{where}: `contributes: {con}` and a message — a contributor is never sent, so the message is dead")
        if not con and not msg:
            errs.append(f"{where}: no message and no `contributes:` — this rule can fire and reach nobody")
        # `watch:` names the indicator and the line this rule is about, so GET /effect can say how long an
        # action took to work. The rule's SQL is the truth and this is a second copy of one number out of it:
        # the guard is that the number must still appear in that SQL. Two places holding one threshold is
        # exactly how they come to disagree, and a disagreement here would be a measurement that lies.
        w = r.get("watch")
        if w is not None:
            if not isinstance(w, dict) or "metric" not in w or "over" not in w:
                errs.append(f"{where}: `watch:` needs a metric and an `over` threshold, or leave it out")
            else:
                sql_txt = str(r.get("sql") or "")
                if f"'{w['metric']}'" not in sql_txt:
                    errs.append(f"{where}: watch.metric is {w['metric']!r} and the SQL never mentions it")
                over = str(w["over"])
                if over not in sql_txt and over.rstrip("0").rstrip(".") not in sql_txt:
                    errs.append(f"{where}: watch.over is {over} and the SQL does not use that number — "
                                "one of the two has moved, and the effect measurement would be against the wrong line")
        # Whose line (docs/SPEC_language.md rule 10): an act or warn alert with a static threshold
        # names whose line it is, through the {line} clause — main.py fills {line} from watch.over.
        # A {line} with no watch to fill it would render braces to somebody's phone, so both
        # directions fail here. Kinded rules are the event engine's: their SQL returns `line` as a
        # column (checked by the placeholder loop below) and their issue's events: templates speak.
        msg_en = str(msg.get("en", "")) if isinstance(msg, dict) else str(msg or "")
        over_v = w.get("over") if isinstance(w, dict) else None
        has_watch = over_v is not None
        if not r.get("kind") and r.get("level") in ("act", "warn"):
            if has_watch and "{line}" not in msg_en:
                errs.append(f"{where}: {r.get('level')} rule has a line (watch.over is {over_v}) but the message never "
                            "names whose line it is — add the {line} clause (docs/SPEC_language.md rule 10)")
            if not has_watch and "{line}" in msg_en:
                errs.append(f"{where}: message uses {{line}} but the rule has no watch.over to fill it from")
        for lang, tmpl in (msg.items() if isinstance(msg, dict) else [("", msg)]):
            for ph in re.findall(r"\{(\w+)", str(tmpl)):
                if ph not in outs:
                    if ph == "line" and not r.get("kind") and has_watch:
                        continue          # engine-filled from watch.over in main.py, not a SQL column
                    errs.append(f"{where} [{lang}]: message wants {{{ph}}} but the SQL returns {sorted(outs)}")

for f in sorted(glob.glob("packs/*/cells.yml")):
    for c in yaml.safe_load(open(f)) or []:
        checked += 1
        where = f"{f}:{c.get('cell')}"
        outs = check_sql(where, c["sql"])
        if "value" not in outs:
            errs.append(f"{where}: SQL must return a column named `value`, returns {sorted(outs)}")

print("\n".join(f"  x {e}" for e in errs) or f"  {checked} rules and cells check out against init.sql")
sys.exit(1 if errs else 0)
