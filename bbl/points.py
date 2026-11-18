"""Daily points per station from the stops table."""
from __future__ import annotations

from . import config


def score_day(arrivals: int, punctual: int) -> tuple[float | None, bool]:
    """Return (points, plays). Points are the punctual share, 0.00 .. 1.00.
    A day is scored only with AT LEAST MIN_ARRIVALS arrivals; otherwise it is not scored ("plays" = scored)."""
    plays = arrivals >= config.MIN_ARRIVALS
    if arrivals == 0:
        return None, False
    return round(punctual / arrivals, config.POINTS_DECIMALS), plays


DELAY_BINS = ("d6_15", "d16_30", "d31_60", "d61_120", "d121p")   # minutes late: 6-15, 16-30, 31-60, 61-120, >120


def daily_counts(con, stops_sql: str) -> list[dict]:
    """stops_sql: any relation with the stops schema (see ingest.py). Deduplicated on id."""
    rows = con.sql(f"""
        WITH s AS (
            SELECT id, any_value(eva) AS eva, any_value(station) AS station,
                   CAST(any_value(planned) AS DATE) AS day,
                   max(delay_in_min) AS delay, bool_or(canceled) AS canceled,
                   bool_and(coalesce(due, true)) AS due
            FROM {stops_sql} GROUP BY id
        )
        SELECT eva, any_value(station) AS station, day,
               count(*) FILTER (WHERE due) AS arrivals,
               count(*) FILTER (WHERE due AND NOT canceled AND delay < {config.PUNCTUAL_LIMIT_MIN}) AS punctual,
               count(*) FILTER (WHERE due AND canceled) AS canceled,
               count(*) AS scheduled,
               -- late arrivals by delay (whole minutes), not cancelled; together they make up all late arrivals
               count(*) FILTER (WHERE due AND NOT canceled AND delay BETWEEN 6 AND 15) AS d6_15,
               count(*) FILTER (WHERE due AND NOT canceled AND delay BETWEEN 16 AND 30) AS d16_30,
               count(*) FILTER (WHERE due AND NOT canceled AND delay BETWEEN 31 AND 60) AS d31_60,
               count(*) FILTER (WHERE due AND NOT canceled AND delay BETWEEN 61 AND 120) AS d61_120,
               count(*) FILTER (WHERE due AND NOT canceled AND delay > 120) AS d121p
        FROM s GROUP BY eva, day ORDER BY day, eva
    """).fetchall()
    out = []
    for eva, station, day, arrivals, punctual, canceled, scheduled, *bins in rows:
        pts, plays = score_day(arrivals, punctual)
        out.append({"eva": eva, "station": station, "day": day.isoformat(), "arrivals": arrivals,
                    "punctual": punctual, "canceled": canceled, "points": pts, "plays": plays,
                    "scheduled": scheduled, **dict(zip(DELAY_BINS, bins))})
    return out
