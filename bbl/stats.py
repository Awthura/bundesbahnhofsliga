"""Extra statistics for station pages: records and streaks, weekday profile, national rank, volume."""
from __future__ import annotations

import datetime as dt
from collections import defaultdict

from . import config

STREAK_LEVEL = config.FORECAST_THRESHOLD   # a "good day" for streaks: the same bar as the forecast (0.60)


def overall_average(daily: list[dict]) -> float | None:
    """Average daily points over all scored days (the same measure as the weekly Schnitt)."""
    pts = [d["points"] for d in daily if d["plays"]]
    return round(sum(pts) / len(pts), 3) if pts else None


def streaks(daily: list[dict], level: float = STREAK_LEVEL) -> dict:
    """Longest and current run of scored days at or above `level`. A day that is not scored breaks a run."""
    best = cur = 0
    best_end = None
    for d in daily:
        if d["plays"] and d["points"] is not None and d["points"] >= level:
            cur += 1
            if cur > best:
                best, best_end = cur, d["day"]
        else:
            cur = 0
    best_start = None
    if best_end:
        i = next(i for i, d in enumerate(daily) if d["day"] == best_end)
        best_start = daily[i - best + 1]["day"]
    return {"level": level, "longest": best, "longest_from": best_start, "longest_to": best_end, "current": cur}


def weekday_profile(daily: list[dict]) -> list[dict]:
    """Average points per weekday, Monday first."""
    by = defaultdict(list)
    for d in daily:
        if d["plays"]:
            by[dt.date.fromisoformat(d["day"]).weekday()].append(d["points"])
    return [{"weekday": w, "avg": round(sum(by[w]) / len(by[w]), 3) if by[w] else None, "days": len(by[w])}
            for w in range(7)]


def records(history: list[dict]) -> dict:
    done = [h for h in history if h["complete"]]
    best = max(done, key=lambda h: h["avg"], default=None)
    worst = min(done, key=lambda h: h["avg"], default=None)
    top = min(history, key=lambda h: (h["tier"], h["rank"]), default=None)
    pick = lambda h: {k: h[k] for k in ("season", "league", "short", "rank", "avg")} if h else None   # noqa: E731
    return {"best_week": pick(best), "worst_week": pick(worst), "highest": pick(top),
            "titles": sum(1 for h in done if h["rank"] == 1),
            "promotions": sum(1 for h in history if h.get("move") == "up"),
            "relegations": sum(1 for h in history if h.get("move") == "down")}


def volume(daily: list[dict]) -> dict:
    days = [d for d in daily if d.get("arrivals")]
    if not days:
        return {"avg_per_day": None, "busiest": None}
    busiest = max(days, key=lambda d: d["arrivals"])
    return {"avg_per_day": round(sum(d["arrivals"] for d in days) / len(days), 1),
            "busiest": {"day": busiest["day"], "arrivals": busiest["arrivals"]}}


def national_ranks(averages: dict[str, float | None], states: dict[str, str | None]) -> dict[str, dict]:
    """Rank of every current member by overall average, nationally and within its Bundesland."""
    ranked = sorted((e for e, a in averages.items() if a is not None), key=lambda e: -averages[e])
    out, per_state = {}, defaultdict(list)
    for i, e in enumerate(ranked, 1):
        per_state[states.get(e)].append(e)
        out[e] = {"rank": i, "of": len(ranked)}
    for st, evas in per_state.items():
        for i, e in enumerate(evas, 1):
            out[e].update(state=st, state_rank=i, state_of=len(evas))
    return out


def week_ranks(season: dict, states: dict[str, str | None]) -> dict[str, dict]:
    """National ranking of one week: all leagues' final tables in one list, ranked like a league table
    (ranked stations first, then Schnitt, then points, then name). Same order as the ranking page."""
    rows = [r for lg in season["leagues"].values() for r in (lg["tables"][-1] if lg["tables"] else [])]
    rows.sort(key=lambda r: (not r["ranked"], -r["avg"], -r["points"], r["station"]))
    out, per_state = {}, defaultdict(list)
    for i, r in enumerate(rows, 1):
        per_state[states.get(r["eva"])].append(r["eva"])
        out[r["eva"]] = {"season": season["id"], "rank": i, "of": len(rows), "avg": r["avg"]}
    for st, evas in per_state.items():
        for i, e in enumerate(evas, 1):
            out[e].update(state=st, state_rank=i, state_of=len(evas))
    return out
