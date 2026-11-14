"""Our own collector for the DB Timetables API (optional backup to the Hugging Face archive).

Fetches, for every league station: the planned timetable for this hour and the next, and the full
change list (fchg). Writes the raw responses in the same format as the Hugging Face raw dumps, so
scripts/update_data.py can read both.

Credentials come from the environment only (GitHub Actions secrets), never from files in the repo:
  DB_CLIENT_ID, DB_API_KEY     from https://developers.deutschebahn.com/ (Timetables, free plan)

python -m scripts.collect   -> data/collector/<YYYY-MM-DD>_<HHMM>.parquet
"""
from __future__ import annotations

import datetime as dt
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from zoneinfo import ZoneInfo

import duckdb

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from bbl import config  # noqa: E402

BERLIN = ZoneInfo("Europe/Berlin")


def fetch(url, headers):
    t0 = time.time()
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=30) as r:
            return r.read().decode("utf-8"), str(r.status), None, (time.time() - t0) * 1000
    except urllib.error.HTTPError as e:
        return None, str(e.code), str(e), (time.time() - t0) * 1000
    except Exception as e:  # network errors: log and continue
        return None, None, str(e), (time.time() - t0) * 1000


def main():
    cid, key = os.environ.get("DB_CLIENT_ID"), os.environ.get("DB_API_KEY")
    if not cid or not key:
        print("DB_CLIENT_ID / DB_API_KEY not set, skipping collection")
        return
    headers = {"DB-Client-Id": cid, "DB-Api-Key": key, "accept": "application/xml"}
    meta = json.loads((ROOT / "docs" / "data" / "meta.json").read_text())
    evas = sorted(meta["stations"])
    now = dt.datetime.now(BERLIN)
    hours = [now, now + dt.timedelta(hours=1)]
    jobs = []
    for eva in evas:
        e = eva.lstrip("0")
        for h in hours:
            jobs.append(("timetables/v1/plan", f"{config.DB_TIMETABLES_BASE}/plan/{e}/{h:%y%m%d}/{h:%H}"))
        jobs.append(("timetables/v1/fchg", f"{config.DB_TIMETABLES_BASE}/fchg/{e}"))

    pause = 60 / config.DB_REQUESTS_PER_MIN
    rows = []
    for api, url in jobs:
        body, status, err, ms = fetch(url, headers)
        rows.append((dt.datetime.now(BERLIN).replace(tzinfo=None), url, api, None, body, status, err, ms))
        if status == "429":
            time.sleep(30)
        time.sleep(pause)

    out = ROOT / "data" / "collector"
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"{now:%Y-%m-%d_%H%M}.parquet"
    con = duckdb.connect()
    con.execute("CREATE TABLE r (timestamp TIMESTAMP, url VARCHAR, api_name VARCHAR, query_params VARCHAR, "
                "response_data VARCHAR, status_code VARCHAR, error VARCHAR, duration_ms DOUBLE)")
    con.executemany("INSERT INTO r VALUES (?, ?, ?, ?, ?, ?, ?, ?)", rows)
    con.execute(f"COPY r TO '{path}' (FORMAT parquet, COMPRESSION zstd)")
    ok = sum(1 for r in rows if r[5] == "200")
    print(f"{ok}/{len(rows)} requests ok -> {path.name}")


if __name__ == "__main__":
    main()
