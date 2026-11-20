"""Daily measured generation mix from REE REData (`generacion/estructura-generacion`) for the Balearic system."""
from __future__ import annotations

import calendar
import json
import os
from datetime import date
from pathlib import Path

import grids

URL = "https://apidatos.ree.es/es/datos/generacion/estructura-generacion"
LINK_URL = "https://apidatos.ree.es/es/datos/intercambios/enlace-baleares"


def _state_file() -> Path:
    return Path(os.getenv("PACK_OUT", "/app/out")) / "energy" / "ree.json"


def _load() -> dict:
    try:
        return json.loads(_state_file().read_text())
    except (OSError, ValueError):
        return {}


def _save(st: dict) -> None:
    try:
        f = _state_file()
        f.parent.mkdir(parents=True, exist_ok=True)
        tmp = f.with_suffix(".part")
        tmp.write_text(json.dumps(st))
        tmp.replace(f)
    except OSError:
        pass


def parse(doc: dict) -> list[tuple[date, float, float]]:
    """Return `(day, fossil_mwh, total_mwh)`, one row per day, sorted by day.

    Fossil is every series REE types as non-renewable, minus storage consumption if REE reports it as negative.
    """
    fossil: dict[date, float] = {}
    ren: dict[date, float] = {}
    neg: dict[date, float] = {}
    totals: dict[date, float] = {}
    days: set[date] = set()

    for item in (doc or {}).get("included") or []:
        attr = item.get("attributes") or {}
        kind = (attr.get("type") or "").strip().lower()
        for pt in attr.get("values") or []:
            dt = str(pt.get("datetime") or "")
            if len(dt) < 10:
                continue
            try:
                d = date.fromisoformat(dt[:10])
                v = float(pt.get("value") or 0.0)
            except (TypeError, ValueError):
                continue
            days.add(d)
            if kind == "total":
                totals[d] = totals.get(d, 0.0) + v
            elif kind == "no-renovable":
                fossil[d] = fossil.get(d, 0.0) + v
            elif kind == "renovable":
                if v >= 0:
                    ren[d] = ren.get(d, 0.0) + v
                else:
                    neg[d] = neg.get(d, 0.0) + v
            elif v < 0:
                neg[d] = neg.get(d, 0.0) + v

    out: list[tuple[date, float, float]] = []
    for d in sorted(days):
        f = max(0.0, fossil.get(d, 0.0) + neg.get(d, 0.0))
        t = totals[d] if d in totals else (f + max(0.0, ren.get(d, 0.0)))
        if t > 0:
            out.append((d, min(f, t), t))
    return out


def share(rows) -> float | None:
    """Fossil MWh divided by total MWh across `rows` (`(day_or_share, fossil_mwh, total_mwh)`), or None when empty."""
    f_sum = 0.0
    t_sum = 0.0
    for _, f, t in rows or []:
        if f is not None and t is not None and t > 0:
            f_sum += float(f)
            t_sum += float(t)
    if t_sum <= 0:
        return None
    return f_sum / t_sum


def imports(doc: dict) -> dict[date, float]:
    """MWh a day that came from the peninsula, from `enlace-baleares` read for the Balearic system (positive = in)."""
    out: dict[date, float] = {}
    for item in (doc or {}).get("included") or []:
        for pt in (item.get("attributes") or {}).get("values") or []:
            try:
                d, v = date.fromisoformat(str(pt.get("datetime"))[:10]), float(pt.get("value"))
            except (TypeError, ValueError):
                continue
            if v > 0:
                out[d] = out.get(d, 0.0) + v
    return out


def with_link(
    bal_rows: list[tuple[date, float, float]],
    pen_rows: list[tuple[date, float, float]],
    imports_mwh: dict[date, float] | None = None,
) -> list[tuple[date, float, float]]:
    """Add each day's peninsular link imports (`imports_mwh[day] > 0`) valued at that day's peninsular fossil share."""
    if not imports_mwh:
        return list(bal_rows)
    pen_by_day = {d: f / t for d, f, t in (pen_rows or []) if t > 0}
    out: list[tuple[date, float, float]] = []
    for d, f, t in bal_rows or []:
        imp = float(imports_mwh.get(d) or 0.0)
        if imp > 0 and d in pen_by_day:
            f += imp * pen_by_day[d]
            t += imp
        out.append((d, min(max(0.0, f), t), t))
    return out


def ring_split(sources: list[dict], g: dict, beyond_share: float = 0.0) -> dict:
    """Split Menorca (`city`) vs rest of Balearics (`region`) by OSM plant MW inside each ring, plus `beyond` link."""
    poly = g.get("polygon") or []
    city_mw = 0.0
    region_mw = 0.0
    for s in sources or []:
        if s.get("kind") != "plant":
            continue
        cap = s.get("mw")
        lat, lon = s.get("lat"), s.get("lon")
        if cap is None or cap <= 0 or lat is None or lon is None or not grids.inside(lat, lon, poly):
            continue
        if grids.ring_for(lat, lon, g) == "city":
            city_mw += float(cap)
        else:
            region_mw += float(cap)
    beyond = max(0.0, min(1.0, float(beyond_share or 0.0)))
    island_mw = city_mw + region_mw
    if island_mw <= 0:
        return {"city": None, "region": None, "beyond": beyond, "kind": "estimated"}
    rem = 1.0 - beyond
    return {
        "city": (city_mw / island_mw) * rem,
        "region": (region_mw / island_mw) * rem,
        "beyond": beyond,
        "kind": "estimated",
    }


def _trailing_window(today: date) -> list[str]:
    ym = today.year * 12 + (today.month - 1)
    out: list[str] = []
    for k in range(11, -1, -1):
        y, m0 = divmod(ym - k, 12)
        out.append(f"{y:04d}-{m0 + 1:02d}")
    return out


def months_to_fetch(have: set[str], today: date) -> list[str]:
    """Return the `YYYY-MM` keys of the trailing 12 months not yet held in `have`, oldest first."""
    held = set(have or ())
    return [m for m in _trailing_window(today) if m not in held]


def _ree_cfg(g: dict | None = None) -> tuple[tuple[str, int], tuple[str, int]]:
    """(geo_limit, geo_id) for the grid itself and for the peninsula behind its link, from grids.yml."""
    if not g:
        g = next((e for e in grids.load() if (e.get("mix") or {}).get("source") == "ree"), {})
    mix = g.get("mix") or {}
    pen = next((lk.get("mix_from") or {} for lk in g.get("links") or [] if lk.get("mix_from")), {})
    return ((str(mix.get("geo_limit") or "baleares"), int(mix.get("geo_id") or 8743)),
            (str(pen.get("geo_limit") or "peninsular"), int(pen.get("geo_id") or 8741)))


def _month_bounds(ym: str, today: date) -> tuple[str, str] | None:
    """The month's full days; the current month ends yesterday, and has none on the 1st."""
    y_s, m_s = ym.split("-")
    y, m = int(y_s), int(m_s)
    last_day = calendar.monthrange(y, m)[1]
    if (y, m) == (today.year, today.month):
        last_day = min(last_day, today.day - 1)
    if last_day < 1:
        return None
    return f"{ym}-01T00:00", f"{ym}-{last_day:02d}T23:59"


def _get(hc, url: str, start: str, end: str, geo: tuple[str, int]) -> dict:
    r = hc.get(url, params={"start_date": start, "end_date": end, "time_trunc": "day",
                            "geo_limit": geo[0], "geo_ids": str(geo[1])}, timeout=30)
    if hasattr(r, "raise_for_status"):
        r.raise_for_status()
    return r.json() if hasattr(r, "json") else r


def fetch(hc, state: dict, today: date, g: dict | None = None) -> dict:
    """Update `state['months']` (at most 3 months per call) and return the trailing-year measured share.

    Each month is three requests: the Balearic mix, the peninsula's mix, and the link, so imports count at the
    peninsula's share that day. The current month goes first, so "yesterday" is never a day from the backfill.
    """
    months: dict = state.setdefault("months", {})
    imported: dict = state.setdefault("imports", {})
    last: dict = state.get("last") or {}
    geo, pen_geo = _ree_cfg(g)

    cur = f"{today.year:04d}-{today.month:02d}"
    todo = [m for m in months_to_fetch(set(months.keys()), today) if m != cur]
    batch = [cur] + todo[:2]

    stale = False
    latest_day_share: float | None = last.get("now")
    as_of: str | None = last.get("as_of")

    for ym in batch:
        bounds = _month_bounds(ym, today)
        if bounds is None:
            continue
        try:
            doc = _get(hc, URL, *bounds, geo)
            imp = imports(_get(hc, LINK_URL, *bounds, geo))
            rows = with_link(parse(doc), parse(_get(hc, URL, *bounds, pen_geo)), imp)
            if not rows:
                raise RuntimeError(f"REE returned no daily rows for {ym}")
            months[ym] = [share(rows), sum(f for _, f, _ in rows), sum(t for _, _, t in rows)]
            imported[ym] = sum(imp.get(d, 0.0) for d, _, _ in rows)
            if ym == cur:
                _, lf, lt = rows[-1]
                latest_day_share = lf / lt
                upd = ((doc or {}).get("data") or {}).get("attributes") or {}
                as_of = upd.get("last-update") or rows[-1][0].isoformat()
        except Exception:
            stale = True
            break

    window = _trailing_window(today)
    held_rows = [months[m] for m in window if m in months]
    n_months = len(held_rows)
    t_held = sum(months[m][2] for m in window if m in months)
    beyond = sum(imported.get(m, 0.0) for m in window if m in months) / t_held if t_held > 0 else None
    val = share(held_rows)
    if val is None:
        val = last.get("value")
    elif stale and last.get("value") is not None:
        val = last["value"]

    if not stale and val is not None:
        state["last"] = {"value": val, "now": latest_day_share, "as_of": as_of}
    if os.getenv("PACK_OUT"):
        _save(state)

    return {
        "value": val,
        "now": latest_day_share,
        "months": n_months,
        "beyond": beyond,
        "as_of": as_of,
        "stale": stale,
        "kind": "measured",
    }
