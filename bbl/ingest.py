"""Turn source data into one compact "stops" table: one row per ICE/IC arrival.

Two sources feed it:
  * Hugging Face monthly processed parquet (complete past months)
  * raw DB Timetables API responses (plan + fchg XML), either from the Hugging Face
    raw_data folder (piebro collects hourly) or from our own collector. Same format.

Output schema (data/stops/<day>.parquet):
  id, eva, station, train_type, train_number, planned (TIMESTAMP), delay_in_min (INT), canceled (BOOL)
"""
from __future__ import annotations

import datetime as dt
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path

import duckdb

from . import config

STOPS_COLUMNS = "id VARCHAR, eva VARCHAR, station VARCHAR, train_type VARCHAR, train_number VARCHAR, " \
                "planned TIMESTAMP, delay_in_min INTEGER, canceled BOOLEAN"


def parse_db_time(s: str | None) -> dt.datetime | None:
    """DB Timetables time format YYMMddHHmm, local German time."""
    if not s or len(s) != 10:
        return None
    return dt.datetime.strptime(s, "%y%m%d%H%M")


def _eva_from_url(url: str) -> str | None:
    m = re.search(r"/(?:plan|fchg|rchg)/(\d+)", url)
    return m.group(1).zfill(8) if m else None


def parse_plan(xml: str, eva: str, types=config.TRAIN_TYPES) -> list[dict]:
    """Planned arrivals of the wanted train types. Stops without <ar> (first stop) are skipped."""
    out = []
    root = ET.fromstring(xml)
    station = root.get("station")
    for s in root.findall("s"):
        tl, ar = s.find("tl"), s.find("ar")
        if tl is None or ar is None or tl.get("c") not in types:
            continue
        planned = parse_db_time(ar.get("pt"))
        if planned is None:
            continue
        out.append({"id": s.get("id"), "eva": eva, "station": station, "train_type": tl.get("c"),
                    "train_number": tl.get("n"), "planned": planned})
    return out


def parse_fchg(xml: str) -> list[dict]:
    """Arrival changes: changed time (ct) and cancellation status (cs='c')."""
    out = []
    root = ET.fromstring(xml)
    for s in root.findall("s"):
        ar = s.find("ar")
        if ar is None:
            continue
        ct = parse_db_time(ar.get("ct"))
        canceled = ar.get("cs") == "c" or ar.get("clt") is not None
        if ct is None and not canceled and ar.get("cs") is None:
            continue   # no arrival information in this snapshot (same rule as piebro's processing)
        out.append({"id": s.get("id"), "ct": ct, "pt": parse_db_time(ar.get("pt")), "canceled": canceled})
    return out


class RawAccumulator:
    """Feed raw API responses in chronological order, then call stops()."""

    def __init__(self):
        self.plans: dict[str, dict] = {}
        self.changes: dict[str, tuple[dt.datetime, dict]] = {}   # id -> (fetched_at, change)
        self.stations: dict[str, dict] = {}

    def add(self, fetched_at: dt.datetime, url: str, api_name: str, body: str | None):
        if not body:
            return
        try:
            if api_name == "timetables/v1/plan":
                eva = _eva_from_url(url)
                if 'c="IC' not in body:          # cheap pre-filter, matches ICE and IC
                    return
                for p in parse_plan(body, eva):
                    self.plans.setdefault(p["id"], p)
            elif api_name == "timetables/v1/fchg":
                for c in parse_fchg(body):
                    prev = self.changes.get(c["id"])
                    if prev is None or fetched_at >= prev[0]:
                        self.changes[c["id"]] = (fetched_at, c)
            elif api_name == "station-data/v2/stations":
                for st in json.loads(body).get("result", []):
                    for e in st.get("evaNumbers", []):
                        if e.get("isMain"):
                            coords = (e.get("geographicCoordinates") or {}).get("coordinates") or [None, None]
                            self.stations[str(e["number"]).zfill(8)] = {
                                "name": st.get("name"), "state": st.get("federalState"),
                                "lon": coords[0], "lat": coords[1], "category": st.get("category")}
        except ET.ParseError:
            pass

    def stops(self) -> list[dict]:
        rows = []
        for sid, p in self.plans.items():
            ch = self.changes.get(sid, (None, {}))[1]
            canceled = bool(ch.get("canceled"))
            delay = 0
            if ch.get("ct") is not None:
                delay = int((ch["ct"] - p["planned"]).total_seconds() // 60)
            rows.append({**p, "delay_in_min": delay, "canceled": canceled})
        return rows


def ingest_raw_files(paths: list[str]) -> RawAccumulator:
    """Read raw parquet files (columns timestamp, url, api_name, response_data, status_code)."""
    acc = RawAccumulator()
    con = duckdb.connect()
    files = ", ".join(f"'{p}'" for p in sorted(paths))
    cur = con.execute(f"""
        SELECT timestamp, url, api_name, response_data FROM read_parquet([{files}])
        WHERE status_code = '200' AND api_name IN ('timetables/v1/plan', 'timetables/v1/fchg', 'station-data/v2/stations')
        ORDER BY timestamp
    """)
    while batch := cur.fetchmany(5000):
        for ts, url, api, body in batch:
            acc.add(ts, url, api, body)
    return acc


def stops_from_monthly(con: duckdb.DuckDBPyConnection, path: str, month: str):
    """Relation of stops from a HF monthly processed parquet, limited to days of that month."""
    start = dt.date.fromisoformat(month + "-01")
    end = (start.replace(day=28) + dt.timedelta(days=4)).replace(day=1)
    types = ", ".join(f"'{t}'" for t in config.TRAIN_TYPES)
    return con.sql(f"""
        SELECT id, any_value(eva) AS eva, any_value(station_name) AS station,
               any_value(train_type) AS train_type, any_value(train_number) AS train_number,
               CAST(any_value(arrival_planned_time) AS TIMESTAMP) AS planned,
               -- arrival delay; the dataset's delay_in_min prefers the departure delay, so don't use it
               max(coalesce(date_diff('minute', arrival_planned_time, arrival_change_time), 0)) AS delay_in_min,
               bool_or(coalesce(arrival_is_canceled, false)) AS canceled
        FROM read_parquet('{path}')
        WHERE train_type IN ({types}) AND arrival_planned_time IS NOT NULL AND has_plan_record
          AND arrival_planned_time >= DATE '{start}' AND arrival_planned_time < DATE '{end}'
        GROUP BY id
    """)


def write_stops(rows: list[dict], out_dir: Path) -> list[str]:
    """Write stops rows to one parquet per planned day. Returns written days."""
    out_dir.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    con.execute(f"CREATE TABLE s ({STOPS_COLUMNS})")
    cols = ["id", "eva", "station", "train_type", "train_number", "planned", "delay_in_min", "canceled"]
    con.executemany("INSERT INTO s VALUES (?, ?, ?, ?, ?, ?, ?, ?)", [[r[c] for c in cols] for r in rows])
    return write_stops_relation(con, "s", out_dir)


def write_stops_relation(con, rel_sql: str, out_dir: Path) -> list[str]:
    out_dir.mkdir(parents=True, exist_ok=True)
    days = [str(d[0]) for d in con.sql(f"SELECT DISTINCT CAST(planned AS DATE) FROM {rel_sql} ORDER BY 1").fetchall()]
    for d in days:
        con.sql(f"COPY (SELECT * FROM {rel_sql} WHERE CAST(planned AS DATE) = DATE '{d}' ORDER BY id) "
                f"TO '{out_dir / (d + '.parquet')}' (FORMAT parquet)")
    return days
