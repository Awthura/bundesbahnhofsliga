"""Next-day forecast per station: "Will it score at least THRESHOLD tomorrow?"

A deliberately simple, transparent model, no machine learning:
  * look at the station's played days in the last WINDOW days,
  * weight each day by recency (half-life HALF_LIFE days) and double it if it is the same weekday
    as the day being forecast (weekends are clearly more punctual than Thursdays and Fridays),
  * P(yes) = weighted share of days at or above the threshold, with a Beta(1, 1) prior so a
    station with little history stays near 50 %,
  * expected score and an 80 % range come from the same weighted history.
The history of past forecasts (each made only with data available before that day) is kept to
show how the probability moved and how well it did (Brier score; a coin flip scores 0.25).
"""
from __future__ import annotations

import datetime as dt

from . import config


def _weights(history: list[tuple[dt.date, float]], target: dt.date):
    out = []
    for day, pts in history:
        age = (target - day).days
        if 0 < age <= config.FORECAST_WINDOW_DAYS:
            w = 0.5 ** (age / config.FORECAST_HALF_LIFE_DAYS)
            if day.weekday() == target.weekday():
                w *= config.FORECAST_SAME_WEEKDAY_WEIGHT
            out.append((w, pts))
    return out


def _quantile(wp: list[tuple[float, float]], q: float) -> float:
    wp = sorted(wp, key=lambda x: x[1])
    total, acc = sum(w for w, _ in wp), 0.0
    for w, p in wp:
        acc += w
        if acc >= q * total:
            return p
    return wp[-1][1]


def predict(history: list[tuple[dt.date, float]], target: dt.date, threshold: float | None = None) -> dict | None:
    """history: (day, points) for played days only. Uses only days before target."""
    thr = config.FORECAST_THRESHOLD if threshold is None else threshold
    wp = _weights(history, target)
    if len(wp) < config.FORECAST_MIN_DAYS:
        return None
    total = sum(w for w, _ in wp)
    yes = sum(w for w, p in wp if p >= thr)
    return {
        "p_yes": round((yes + 1) / (total + 2), 3),
        "expected": round(sum(w * p for w, p in wp) / total, 3),
        "low": round(_quantile(wp, 0.1), 2),
        "high": round(_quantile(wp, 0.9), 2),
    }


def station_forecast(daily: list[dict], next_day: dt.date, history_days: int = 45) -> dict | None:
    """daily: [{day, points, plays}] of one station. Returns tomorrow's forecast plus past forecasts."""
    played = [(dt.date.fromisoformat(d["day"]), d["points"]) for d in daily if d["plays"] and d["points"] is not None]
    if not played or (next_day - played[-1][0]).days > config.FORECAST_MAX_GAP_DAYS:
        return {"day": next_day.isoformat(), "no_service": True}   # e.g. line closed for construction
    now = predict(played, next_day)
    if now is None:
        return None
    outcome = {day: pts for day, pts in played}
    past, briers = [], []
    for i in range(history_days, 0, -1):
        day = next_day - dt.timedelta(days=i)
        f = predict(played, day)
        if f is None:
            continue
        res = None
        if day in outcome:
            res = outcome[day] >= config.FORECAST_THRESHOLD
            briers.append((f["p_yes"] - (1.0 if res else 0.0)) ** 2)
        past.append({"day": day.isoformat(), "p": f["p_yes"], "yes": res})
    return {"day": next_day.isoformat(), "threshold": config.FORECAST_THRESHOLD, **now, "history": past,
            "brier": round(sum(briers) / len(briers), 3) if briers else None, "resolved": len(briers)}
