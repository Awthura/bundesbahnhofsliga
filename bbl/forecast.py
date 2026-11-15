"""Forecast per station: "Will at least THRESHOLD of the long-distance trains arrive on time on this day?"

Two layers, both deliberately simple and transparent:

1. Before the day (prior). From the station's own history: each past scored day is weighted by recency
   (half-life) and doubled-ish if it is the same weekday. P(yes) = weighted share of days at or above the
   threshold, with a Beta(1, 1) prior. The three settings (window, half-life, weekday weight) are not fixed:
   `tune()` tries a small grid on all past days, where every forecast only uses data from before its day,
   and keeps the combination with the lowest Brier score. As history grows, the settings re-tune themselves.

2. During the day (live). Once trains of the running day are due, the day's own results update the
   forecast: the station's punctuality rate gets a Beta prior from its history and is updated with
   "k of m on time so far"; the remaining scheduled trains follow a beta-binomial. That live probability is
   blended with the prior by the share of the day already observed, and it becomes 0 or 1 as soon as the
   outcome is decided (enough trains already on time, or too many already late).
"""
from __future__ import annotations

import datetime as dt
import itertools
import math

from . import config

GRID = {"window": (28, 56, 84), "half_life": (7, 14, 28, 56), "weekday_weight": (1.0, 2.0, 3.0)}


def default_params() -> dict:
    return {"window": config.FORECAST_WINDOW_DAYS, "half_life": config.FORECAST_HALF_LIFE_DAYS,
            "weekday_weight": config.FORECAST_SAME_WEEKDAY_WEIGHT}


def _weights(history, target, p):
    out = []
    for day, pts in history:
        age = (target - day).days
        if 0 < age <= p["window"]:
            w = 0.5 ** (age / p["half_life"])
            if day.weekday() == target.weekday():
                w *= p["weekday_weight"]
            out.append((w, pts))
    return out


def _quantile(wp, q):
    wp = sorted(wp, key=lambda x: x[1])
    total, acc = sum(w for w, _ in wp), 0.0
    for w, v in wp:
        acc += w
        if acc >= q * total:
            return v
    return wp[-1][1]


def predict(history: list[tuple[dt.date, float]], target: dt.date, threshold: float | None = None,
            params: dict | None = None) -> dict | None:
    """Prior forecast for `target` from played days before it."""
    thr = config.FORECAST_THRESHOLD if threshold is None else threshold
    wp = _weights(history, target, params or default_params())
    if len(wp) < config.FORECAST_MIN_DAYS:
        return None
    total = sum(w for w, _ in wp)
    yes = sum(w for w, v in wp if v >= thr)
    return {"p_yes": round((yes + 1) / (total + 2), 3), "expected": round(sum(w * v for w, v in wp) / total, 3),
            "low": round(_quantile(wp, 0.1), 2), "high": round(_quantile(wp, 0.9), 2)}


def tune(histories: list[list[tuple[dt.date, float]]], min_forecasts: int = 500) -> dict:
    """Pick the grid settings with the lowest out-of-sample Brier score over all stations' past days."""
    thr = config.FORECAST_THRESHOLD
    best, results = None, []
    for window, half_life, wk in itertools.product(*GRID.values()):
        p = {"window": window, "half_life": half_life, "weekday_weight": wk}
        se, n = 0.0, 0
        for hist in histories:
            for day, pts in hist:
                f = predict(hist, day, params=p)
                if f:
                    se += (f["p_yes"] - (1.0 if pts >= thr else 0.0)) ** 2
                    n += 1
        if n >= min_forecasts:
            results.append((se / n, n, p))
    if not results:
        return {"params": default_params(), "brier": None, "forecasts": 0, "tuned": False}
    brier, n, p = min(results, key=lambda r: r[0])
    return {"params": p, "brier": round(brier, 4), "forecasts": n, "tuned": True}


def _beta_binomial_tail(r: int, need: int, a: float, b: float) -> float:
    """P(X >= need) for X ~ BetaBinomial(r, a, b)."""
    if need <= 0:
        return 1.0
    if need > r:
        return 0.0
    lbeta = lambda x, y: math.lgamma(x) + math.lgamma(y) - math.lgamma(x + y)   # noqa: E731
    base = lbeta(a, b)
    total = 0.0
    for x in range(need, r + 1):
        total += math.exp(math.lgamma(r + 1) - math.lgamma(x + 1) - math.lgamma(r - x + 1)
                          + lbeta(x + a, r - x + b) - base)
    return min(max(total, 0.0), 1.0)


def _concentration(daily: list[dict], mean: float) -> float:
    """How strongly a station's punctuality rate sticks to its usual level (Beta 'kappa'),
    from the spread of its daily scores minus pure binomial noise."""
    days = [d for d in daily if d["plays"] and d.get("arrivals")]
    if len(days) < 7:
        return 20.0
    shares = [d["share"] if d.get("share") is not None else d["points"] for d in days]
    m = sum(shares) / len(shares)
    var = sum((s - m) ** 2 for s in shares) / len(shares)
    noise = sum(mean * (1 - mean) / d["arrivals"] for d in days) / len(days)
    between = max(var - noise, 1e-4)
    return min(max(mean * (1 - mean) / between - 1, 2.0), 200.0)


def live_update(prior: dict, daily_hist: list[dict], due: int, punctual: int, scheduled: int,
                threshold: float | None = None) -> dict:
    """Update the prior with the running day's results so far."""
    thr = config.FORECAST_THRESHOLD if threshold is None else threshold
    need = math.ceil(thr * scheduled - 1e-9)          # punctual arrivals needed at the end of the day
    remaining = max(scheduled - due, 0)
    if punctual >= need:
        return {"p_yes": 1.0, "decided": "yes"}
    if punctual + remaining < need:
        return {"p_yes": 0.0, "decided": "no"}
    mean = min(max(prior["expected"], 0.02), 0.98)
    kappa = _concentration(daily_hist, mean)
    a, b = mean * kappa + punctual, (1 - mean) * kappa + (due - punctual)
    p_live = _beta_binomial_tail(remaining, need - punctual, a, b)
    w = due / scheduled if scheduled else 0.0           # how much of the day has been seen
    return {"p_yes": round(w * p_live + (1 - w) * prior["p_yes"], 3), "decided": None}


def station_forecast(daily: list[dict], running_day: dt.date, params: dict | None = None,
                     history_days: int = 45) -> dict | None:
    """daily: [{day, points, plays, arrivals, punctual, scheduled}] of one station. The forecast is about the
    running day (the newest day in the data), updated live with its trains so far."""
    p = params or default_params()
    played = [(dt.date.fromisoformat(d["day"]), d["points"]) for d in daily
              if d["plays"] and d["points"] is not None and dt.date.fromisoformat(d["day"]) < running_day]
    today = next((d for d in daily if d["day"] == running_day.isoformat()), None)
    scheduled = int((today or {}).get("scheduled") or (today or {}).get("arrivals") or 0)
    # the archive fetches each hour's timetable shortly before that hour, so early in the day only part of
    # the day's trains are known: use the station's usual number for this weekday when that is larger
    same_wd = sorted(int(d.get("arrivals") or 0) for d in daily
                     if d["day"] < running_day.isoformat() and d.get("arrivals")
                     and dt.date.fromisoformat(d["day"]).weekday() == running_day.weekday()
                     and (running_day - dt.date.fromisoformat(d["day"])).days <= 28)
    usual = same_wd[len(same_wd) // 2] if same_wd else 0
    expected_total = max(scheduled, usual)
    if not played or ((running_day - played[-1][0]).days > config.FORECAST_MAX_GAP_DAYS and not scheduled):
        return {"day": running_day.isoformat(), "no_service": True}
    prior = predict(played, running_day, params=p)
    if prior is None:
        return None
    out = {"day": running_day.isoformat(), "threshold": config.FORECAST_THRESHOLD, **prior, "prior_p_yes": prior["p_yes"]}
    due = int((today or {}).get("arrivals") or 0)
    punctual = int((today or {}).get("punctual") or 0)
    if today and due and expected_total >= config.MIN_ARRIVALS:
        hist_rows = [d for d in daily if d["day"] < running_day.isoformat()]
        lv = live_update(prior, hist_rows, due, punctual, expected_total)
        out.update(p_yes=lv["p_yes"], live={"due": due, "punctual": punctual, "expected_total": expected_total,
                                            "decided": lv["decided"]})
    # past forecasts (each made only with data available before that day) and how they turned out
    outcome = {day: pts for day, pts in played}
    past, briers = [], []
    for i in range(history_days, 0, -1):
        day = running_day - dt.timedelta(days=i)
        f = predict(played, day, params=p)
        if f is None:
            continue
        res = None
        if day in outcome:
            res = outcome[day] >= config.FORECAST_THRESHOLD
            briers.append((f["p_yes"] - (1.0 if res else 0.0)) ** 2)
        past.append({"day": day.isoformat(), "p": f["p_yes"], "yes": res})
    out.update(history=past, brier=round(sum(briers) / len(briers), 3) if briers else None, resolved=len(briers))
    return out
