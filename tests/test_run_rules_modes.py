"""run_rules in ALERT_ENGINE=rules, shadow and events, without importing app main (importing it starts a second MQTT
client). Parses app/main.py, takes run_rules' source, execs it against fakes. A typo must behave as rules.
Run: python3 tests/test_run_rules_modes.py
"""
import ast
import contextlib
import pathlib

src = pathlib.Path(__file__).resolve().parent.parent / "app" / "main.py"
tree = ast.parse(src.read_text())
fns = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in ("run_rules", "_event_keyboard")]
code = compile(ast.Module(body=fns, type_ignores=[]), "run_rules", "exec")

import sys  # noqa: E402
sys.path.insert(0, str(src.parent))
import actions  # noqa: E402 — _event_keyboard reads the wire's own button words

# heat/old is replaced by the engine (its pack has a kinded rule); trust/other is not, and keeps sending in events mode
OLD = {"id": "heat/old", "sql": "OLD_SQL", "message": "old {x}", "level": "act"}
OTHER = {"id": "trust/other", "sql": "OTHER_SQL", "message": "other {x}", "level": "act"}
KINDED = {"id": "heat/kinded", "sql": "KINDED_SQL", "message": "k", "level": "act", "kind": "sustained"}


class Msg:
    def __init__(self, send, level="act"):
        self.send = send
        self.event = type("E", (), {"level": level, "id": 7})()


def run(mode, buttons=False):
    sqls, notified, ran, kbs = [], [], [], []

    class Cur:
        def execute(self, sql, *a):
            sqls.append(sql)

        def fetchone(self):
            return {"id": 1} if sqls[-1].startswith("INSERT") else None

    class Con:
        def cursor(self):
            return contextlib.nullcontext(Cur())

    @contextlib.contextmanager
    def db():
        yield Con()

    class NS:
        pass

    packs, index, events_pg, settings, log = NS(), NS(), NS(), NS(), NS()
    packs.load_rules = lambda: [OLD, OTHER, KINDED]
    index.run_ro = lambda cur, sql: (sqls.append(sql), [{"sensor_id": "s", "x": 1}])[1]
    events_pg.candidates = lambda rule, rows: ["cand"]
    events_pg.run = lambda cur, cands, m, now: (ran.append((cands, m)),
                                                [(Msg(True), "engine says"), (Msg(False), "held one"), (Msg(True), None)])[1]
    settings.get = lambda k, d=None: mode if k == "ALERT_ENGINE" else d
    settings.num = lambda k, d=0: 1 if (k == "TELEGRAM_BUTTONS" and buttons) else d
    log.warning = log.info = lambda *a: None
    sent_levels = []
    g = dict(packs=packs, index=index, events_pg=events_pg, settings=settings, log=log, db=db, _act=actions,
             notify=lambda lvl, text, keyboard=None: (notified.append(text), sent_levels.append(lvl), kbs.append(keyboard)),
             ha_alert=lambda *a: None,
             run_report=lambda cur: None, _quiet=lambda lvl: False, LOCALE=lambda: "en", _local_now=lambda: "now")
    exec(code, g)
    g["run_rules"]()
    return sqls, notified, ran, kbs


for mode in ("rules", "typo", "", None):
    sqls, notified, ran, kbs = run(mode)
    assert "KINDED_SQL" not in sqls, (mode, "a kinded rule's SQL ran")
    assert not ran, (mode, "event engine ran")
    assert notified == ["old 1", "other 1"], (mode, notified)
print("  rules (and a typo, empty): kinded rules never run their SQL, no event engine, every old rule sent")

sqls, notified, ran, kbs = run("shadow")
assert "KINDED_SQL" in sqls and "OLD_SQL" in sqls
assert notified == ["old 1", "other 1"], notified
assert sum(s.startswith("INSERT") for s in sqls) == 2, "only the old rules write alerts rows"
assert ran == [(["cand"], "shadow")], ran
print("  shadow: kinded rule runs, writes no alerts row, sends nothing; engine called once in shadow; old rule still sent")

sqls, notified, ran, kbs = run("events")
assert "KINDED_SQL" in sqls and "OLD_SQL" in sqls and "OTHER_SQL" in sqls
assert ran == [(["cand"], "events")], ran
assert sum(s.startswith("INSERT") for s in sqls) == 2, "both old rules still record an alerts row"
assert "old 1" not in notified, "an old rule of a pack the engine replaces is recorded, not sent"
assert notified == ["other 1", "engine says"], notified
assert kbs == [None, None], "no bot, no buttons: TELEGRAM_BUTTONS=0 sends every message bare (SPEC_alerts §7)"
print("  events: the engine's sent messages go out (held and text-less ones do not); old heat/air rules are recorded,")
print("          not sent; rules of packs the engine does not replace send as before")

sqls, notified, ran, kbs = run("events", buttons=True)
assert notified == ["other 1", "engine says"], notified
assert kbs[0] is None, "the buttons are for event messages, not for a pack rule the engine does not replace"
assert [[(b["text"], b["callback_data"]) for b in row] for row in kbs[1]] == \
    [[("Done", "ev:7:acted"), ("Not now", "ev:7:acknowledged"), ("Doesn't fit", "ev:7:dismissed")]], \
    f"the event's message carries the wire's three words and the bot's contract: {kbs[1]}"
print("  events + bot: the engine's message rides the three buttons, the rule's own message goes bare")
