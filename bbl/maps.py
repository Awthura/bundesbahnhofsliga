"""Data for the map page: arrivals and punctual arrivals per Bundesland and per day, from ALL ICE/IC/EC
stops (not only league members), plus per-day numbers for the league stations shown as dots.

A state's score for any period is pooled: sum of punctual arrivals / sum of arrivals, so every train
counts once. The page computes day, week and 4-week values from these daily sums.
"""
from __future__ import annotations

from collections import defaultdict

from . import config

BINS = ("d6_15", "d16_30", "d31_60", "d61_120", "d121p")


def state_of(eva: str, stations_meta: dict) -> str | None:
    return config.STATE_OVERRIDES.get(eva) or (stations_meta.get(eva) or {}).get("state")


def map_data(rows: list[dict], stations_meta: dict, members: dict[str, dict]) -> dict:
    """rows: daily_points rows. members: eva -> {name, lat, lon, league} for the station dots."""
    days = sorted({r["day"] for r in rows})
    idx = {d: i for i, d in enumerate(days)}
    # per day: [arrivals, punctual, cancelled, late 6-15, 16-30, 31-60, 61-120, >120 min]
    blank = lambda: [[0] * 8 for _ in days]   # noqa: E731
    states, national, unassigned = defaultdict(blank), blank(), blank()
    dots = {e: {**m, "d": [0] * len(days)} for e, m in members.items() if m.get("lat") is not None}
    for r in rows:
        a, p, c = int(r["arrivals"]), int(r["punctual"]), int(r.get("canceled") or 0)
        bins = [int(r.get(k) or 0) for k in BINS]
        i = idx[r["day"]]
        target = states[state_of(r["eva"], stations_meta)] if state_of(r["eva"], stations_meta) else unassigned
        for t in (target, national):
            for k, v in enumerate([a, p, c, *bins]):
                t[i][k] += v
        if r["eva"] in dots and a:
            dots[r["eva"]]["d"][i] = [a, p, c, *bins]
    return {"days": days, "states": dict(sorted(states.items())), "national": national,
            "unassigned": unassigned, "stations": dots}


def check(m: dict) -> list[str]:
    """States plus unassigned must add up exactly to the national total, every day."""
    errors = []
    for i, day in enumerate(m["days"]):
        for k in range(8):
            s = sum(v[i][k] for v in m["states"].values()) + m["unassigned"][i][k]
            if s != m["national"][i][k]:
                errors.append(f"{day}: states add up to {s}, national is {m['national'][i][k]}")
    return errors
