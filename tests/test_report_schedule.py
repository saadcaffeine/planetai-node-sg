"""When the node writes a report.

The bug this file exists for: three schedules sending messages from two containers, none of them aware of the
others. Node #1's household got the 06:00 report from the app, nothing at all from the agent's 07:00 attempt
(it passed a tuple to Telegram and logged a 400 every morning since v0.30), and a digest every three hours that
only reached the phone at ALERT_LEVEL=info. Everything here runs offline, against the files themselves.
"""
import os, sys

os.environ.setdefault("DATABASE_URL", "postgresql://x/x")
sys.path.insert(0, "app")

import report
import settings as st

# ---------------------------------------------------------------- the settings themselves
for k in ("REPORT_EVERY", "REPORT_ANCHOR", "REPORT_DEPTH"):
    assert k in st.RUNTIME and st.RUNTIME[k][0] == "alerts", f"{k} belongs to the alerts group"
    assert k in st.PUBLIC, f"{k} is the household's own rhythm; the dashboard shows it without the token"
    assert k in st.CHOICES, f"{k} must refuse a value the scheduler cannot honour"
for k in st.RETIRED:
    assert k not in st.RUNTIME, f"{k} is retired: no control for a key nothing reads"
assert all(24 % int(h) == 0 for h in st.CHOICES["REPORT_EVERY"]), "an interval that does not divide 24 walks round the clock"
assert st.RUNTIME["ALERT_LEVEL"][4].startswith("act = only when something needs doing (default)"), "the help text must say which is the default"

# The refusal names the accepted values, by quoting the help text rather than keeping a second copy of it.
for bad in ("5", "0", "seven", "24h"):
    try:
        st.set("REPORT_EVERY", bad)
    except ValueError as e:
        assert "3, 4, 6, 8, 12 or 24" in str(e), f"the refusal must name what is accepted: {e}"
    else:
        raise AssertionError(f"REPORT_EVERY accepted {bad!r}")
try:
    st.set("REPORT_DEPTH", "verbose")
except ValueError as e:
    assert "auto, brief, standard or deep" in str(e), e
else:
    raise AssertionError("REPORT_DEPTH accepted 'verbose'")
print("a report interval the scheduler cannot honour is refused, and the refusal says what it takes")

# ---------------------------------------------------------------- the default survives an empty key
os.environ["REPORT_EVERY"] = ""          # what update.sh writes into an updating node's .env
assert st.num("REPORT_EVERY", 6) == 6, "a key that is present but empty must not beat the default"
os.environ["REPORT_EVERY"] = "12"
st._cache["at"] = 0.0
assert st.num("REPORT_EVERY", 6) == 12
os.environ["REPORT_EVERY"] = "nonsense"
assert st.num("REPORT_EVERY", 6) == 6, "and neither must a value that is not a number"
del os.environ["REPORT_EVERY"]
print("the report settings hold their defaults through an empty .env key")

# ---------------------------------------------------------------- the agent container has no clock
import yaml

_loop = open("app/agent_loop.py").read()
_compose = yaml.safe_load(open("docker-compose.yml"))
assert "BRIEF_HOUR" not in _loop, "the agent's own report hour is gone; one schedule, in the app container"
assert "BRIEF_HOUR" not in yaml.dump(_compose), "docker-compose.yml still hands the agent a report hour"
# A wall-clock read in this file is what a second schedule is made of: the 07:00 copy came from `datetime.now()`
# next to a BRIEF_HOUR. time.time() is the model ladder's five-minute skip clock and stays.
assert "datetime" not in _loop, "the agent container reads no wall clock: that is how the second schedule started"
assert "daily_report" not in _loop, "a scheduled report is not something the bot asks the model for"
print("the agent container answers when written to and sends nothing on a schedule")


# ---------------------------------------------------------------- the due hours, every interval, across midnight
import datetime as dt

assert report.due_hours(6, 6) == [0, 6, 12, 18], "the default: four a day from six in the morning"
assert report.due_hours(6, 0) == [0, 6, 12, 18]
assert report.due_hours(6, 23) == [5, 11, 17, 23], "an anchor near midnight wraps and stays four hours apart"
assert report.due_hours(24, 7) == [7], "once a day is one hour, the anchor's"
assert report.due_hours(12, 7) == [7, 19]
assert report.due_hours(3, 6) == [0, 3, 6, 9, 12, 15, 18, 21]
assert report.due_hours(4, 23) == [3, 7, 11, 15, 19, 23]
assert report.due_hours(8, 0) == [0, 8, 16]
for every in (int(e) for e in st.CHOICES["REPORT_EVERY"]):
    for anchor in range(24):
        hrs = report.due_hours(every, anchor)
        assert len(hrs) == 24 // every, (every, anchor, hrs)
        assert anchor % 24 in hrs, "the anchor is always one of its own due hours"
        assert len(set(hrs)) == len(hrs), "no hour is due twice"
        gaps = [(b - a) % 24 or 24 for a, b in zip(hrs, hrs[1:] + hrs[:1])]   # once a day wraps to 24, not 0
        assert set(gaps) == {every}, f"every gap is the interval, midnight included: {every}/{anchor} -> {gaps}"
# an interval that does not divide 24 would walk round the clock; .env is edited by hand, so the scheduler catches it
for bad in (0, 5, 7, 25, -6, None):
    assert report.due_hours(bad, 6) == [0, 6, 12, 18], f"{bad} must fall back to six"
print("the due hours are the anchor's, one interval apart, wrapping at midnight")

# ---------------------------------------------------------------- the window a folded report covers
H = dt.datetime(2026, 9, 8, 6, 0, tzinfo=dt.timezone.utc)
assert report.held_hours(None, H, 6) == 0, "the first report ever covers its own interval and no more"
assert report.held_hours(H - dt.timedelta(hours=6), H, 6) == 0, "nothing was held; nothing to fold"
assert report.held_hours(H - dt.timedelta(hours=12), H, 6) == 6, "one report held: the night joins the morning"
assert report.held_hours(H - dt.timedelta(hours=9), H, 3) == 6, "two held at three-hour intervals"
# the bug this function replaced: summing the held reports' own windows counted the same night three times
assert report.held_hours(H - dt.timedelta(hours=9), H, 3) != 3 + 6
# a node that was off for a week reports two days, not a hundred and sixty-eight hours
assert report.held_hours(H - dt.timedelta(days=7), H, 6) == report.MAX_WINDOW - 6
assert report.held_hours(H - dt.timedelta(days=7), H, 6) + 6 == 48
# and a clock that went backwards must not produce a negative window
assert report.held_hours(H + dt.timedelta(hours=3), H, 6) == 0
print("a folded report covers every unreported hour, once, and never more than two days")
