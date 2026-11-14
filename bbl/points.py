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


def daily_counts(con, stops_sql: str) -> list[dict]:
    """stops_sql: any relation with the stops schema (see ingest.py). Deduplicated on id."""
    rows = con.sql(f"""
        WITH s AS (
            SELECT id, any_value(eva) AS eva, any_value(station) AS station,
                   CAST(any_value(planned) AS DATE) AS day,
                   max(delay_in_min) AS delay, bool_or(canceled) AS canceled
            FROM {stops_sql} GROUP BY id
        )
        SELECT eva, any_value(station) AS station, day, count(*) AS arrivals,
               count(*) FILTER (WHERE NOT canceled AND delay < {config.PUNCTUAL_LIMIT_MIN}) AS punctual,
               count(*) FILTER (WHERE canceled) AS canceled
        FROM s GROUP BY eva, day ORDER BY day, eva
    """).fetchall()
    out = []
    for eva, station, day, arrivals, punctual, canceled in rows:
        pts, plays = score_day(arrivals, punctual)
        out.append({"eva": eva, "station": station, "day": day.isoformat(), "arrivals": arrivals,
                    "punctual": punctual, "canceled": canceled, "points": pts, "plays": plays})
    return out
