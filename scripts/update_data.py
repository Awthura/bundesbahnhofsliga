"""Fetch new data and update data/daily_points.csv (the small source of truth kept in git).

  python -m scripts.update_data                    # auto: missing complete months + last raw days
  python -m scripts.update_data --months 2026-10   # specific monthly files
  python -m scripts.update_data --days 2026-11-09 2026-11-14

Complete months come from the Hugging Face monthly parquet. Days of the running month come from
the Hugging Face raw API dumps (hourly DB Timetables responses). Optionally also from our own
collector output in data/collector/ (same raw format), see scripts/collect.py.
Intermediate per-day stops go to data/stops/ (not in git, synced to the server if configured).
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import glob
import json


import subprocess
import sys
from pathlib import Path

import duckdb

from bbl import config, ingest, points

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
STOPS = DATA / "stops"
CACHE = DATA / "raw"
POINTS_CSV = DATA / "daily_points.csv"
SOURCES = DATA / "sources.json"
STATIONS = DATA / "stations.json"
HF_API = "https://huggingface.co/api/datasets/piebro/deutsche-bahn-data/tree/main"
HF_RESOLVE = "https://huggingface.co/datasets/piebro/deutsche-bahn-data/resolve/main"
UA = {"User-Agent": "bundesbahnhofsliga-bot"}


def _get_json(url):
    # curl instead of urllib: urllib stalled for minutes on some networks
    out = subprocess.run(["curl", "-sSL", "--fail", "--retry", "3", "-m", "60", "-A", UA["User-Agent"], url],
                         check=True, capture_output=True).stdout
    return json.loads(out)


def _download(url, dest: Path):
    if dest.exists() and dest.stat().st_size > 0:
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(".part")
    subprocess.run(["curl", "-sSL", "--fail", "--retry", "3", "-o", str(tmp), url], check=True)
    tmp.rename(dest)
    return dest


def load_sources():
    return json.loads(SOURCES.read_text()) if SOURCES.exists() else {"months": [], "days": {}}


def available_months():
    files = _get_json(f"{HF_API}/monthly_processed_data")
    months = sorted(f["path"].split("data-")[1][:7] for f in files if f["path"].endswith(".parquet"))
    return [m for m in months if m >= config.HF_FIRST_MONTH]


def raw_day_files(day: dt.date):
    try:
        files = _get_json(f"{HF_API}/raw_data/year={day.year}/month={day.month}/day={day.day}")
    except Exception:
        return []
    return [f["path"] for f in files if f["path"].endswith(".parquet")]


def do_month(month: str, keep_raw: bool):
    path = _download(f"{HF_RESOLVE}/monthly_processed_data/data-{month}.parquet", CACHE / f"data-{month}.parquet")
    con = duckdb.connect()
    con.register("m", ingest.stops_from_monthly(con, str(path), month))
    days = ingest.write_stops_relation(con, "m", STOPS)
    if not keep_raw:
        path.unlink()
    print(f"month {month}: {len(days)} days")
    return days


def do_raw_day(day: dt.date, keep_raw: bool):
    """Stops for one day need that day's dump and the next one (late changes after midnight)."""
    paths = []
    for d in (day, day + dt.timedelta(days=1)):
        for p in raw_day_files(d):
            paths.append(_download(f"{HF_RESOLVE}/{p}", CACHE / "daily" / Path(p).name))
        paths += [Path(p) for p in glob.glob(str(DATA / "collector" / f"{d}_*.parquet"))]
    if not paths:
        print(f"day {day}: no raw data")
        return False
    acc = ingest.ingest_raw_files([str(p) for p in paths])
    rows = [r for r in acc.stops() if r["planned"].date() == day]
    ingest.write_stops(rows, STOPS)
    due = sum(1 for r in rows if r["due"])
    if acc.stations:
        known = json.loads(STATIONS.read_text()) if STATIONS.exists() else {}
        known.update(acc.stations)
        STATIONS.write_text(json.dumps(known, ensure_ascii=False, indent=0, sort_keys=True))
    if not keep_raw:  # keep tomorrow's files, they are needed for the next day too
        for p in CACHE.glob("daily/date_*.parquet"):
            if p.name < f"date_{day}":
                p.unlink()
    print(f"day {day}: {due} of {len(rows)} scheduled long-distance arrivals due so far, from {len(paths)} raw files")
    return True


def rebuild_points():
    files = sorted(STOPS.glob("*.parquet"))
    if not files:
        return
    con = duckdb.connect()
    lst = ", ".join(f"'{f}'" for f in files)
    new = points.daily_counts(con, f"read_parquet([{lst}], union_by_name=true)")
    new_days = {r["day"] for r in new}
    old = []
    if POINTS_CSV.exists():  # keep days whose stops are no longer on disk (CSV is the archive)
        with POINTS_CSV.open() as f:
            old = [r for r in csv.DictReader(f) if r["day"] not in new_days]
    rows = old + new
    rows.sort(key=lambda r: (r["day"], r["eva"]))
    with POINTS_CSV.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["day", "eva", "station", "arrivals", "punctual", "canceled", "points", "plays",
                                          "scheduled"])
        w.writeheader()
        for r in rows:
            r.setdefault("scheduled", r["arrivals"])   # finished days: everything scheduled is due
            if r["scheduled"] in (None, ""):
                r["scheduled"] = r["arrivals"]
            w.writerow({k: r[k] for k in w.fieldnames})
    print(f"daily_points.csv: {len(rows)} rows, {len({r['day'] for r in rows})} days")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--months", nargs="*")
    ap.add_argument("--days", nargs="*", help="ISO dates, or two dates for a range")
    ap.add_argument("--keep-raw", action="store_true")
    ap.add_argument("--max-months", type=int, default=99)
    a = ap.parse_args(argv)
    src = load_sources()
    today = dt.date.today()

    if a.months is None and a.days is None:   # auto mode
        avail = available_months()
        a.months = [m for m in avail if m not in src["months"]][: a.max_months]
        last_month = max(avail + src["months"]) if (avail or src["months"]) else None
        first_raw = dt.date.fromisoformat(last_month + "-01") if last_month else today
        first_raw = (first_raw.replace(day=28) + dt.timedelta(days=4)).replace(day=1)
        done = {d for d, final in src["days"].items() if final}
        a.days = [str(first_raw + dt.timedelta(days=i)) for i in range((today - first_raw).days + 1)
                  if str(first_raw + dt.timedelta(days=i)) not in done]
    elif a.days and len(a.days) == 2:
        s, e = map(dt.date.fromisoformat, a.days)
        a.days = [str(s + dt.timedelta(days=i)) for i in range((e - s).days + 1)]

    for m in a.months or []:
        do_month(m, a.keep_raw)
        src["months"] = sorted(set(src["months"]) | {m})
        SOURCES.write_text(json.dumps(src, indent=1))
    for d in a.days or []:
        day = dt.date.fromisoformat(d)
        if do_raw_day(day, a.keep_raw):
            # a day is final once the next day's dump exists in full (2 days later to be safe)
            src["days"][d] = day <= today - dt.timedelta(days=2)
            SOURCES.write_text(json.dumps(src, indent=1))
    rebuild_points()


if __name__ == "__main__":
    sys.path.insert(0, str(ROOT))
    main()
