"""Run the table engine on data/daily_points.csv and write JSON for the static site in docs/data/."""
from __future__ import annotations

import csv
import datetime as dt
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from bbl import config, league  # noqa: E402

OUT = ROOT / "docs" / "data"


def dump(path: Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, separators=(",", ":")))


def main():
    with (ROOT / "data" / "daily_points.csv").open() as f:
        rows = list(csv.DictReader(f))
    stations_meta = {}
    sp = ROOT / "data" / "stations.json"
    if sp.exists():
        stations_meta = json.loads(sp.read_text())
    res = league.run(rows)
    data = res["data"]
    if OUT.exists():
        shutil.rmtree(OUT)

    history = {}
    index = []
    for s in res["seasons"]:
        index.append({k: s[k] for k in ("id", "start", "end", "complete")} | {"matchdays": len(s["matchdays"])})
        dump(OUT / "season" / f"{s['id']}.json", s)
        for lid, lg in s["leagues"].items():
            for r in lg["tables"][-1] if lg["tables"] else []:
                history.setdefault(r["eva"], []).append(
                    {"season": s["id"], "league": lid, "rank": r["rank"], "avg": r["avg"], "played": r["played"],
                     "complete": s["complete"]})

    members = sorted(history)
    for eva in members:
        daily = [{"day": d.isoformat(), **data.by_day[d][eva]} for d in data.days if eva in data.by_day[d]]
        played = [x for x in daily if x["plays"]]
        best = max(played, key=lambda x: x["points"], default=None)
        worst = min(played, key=lambda x: x["points"], default=None)
        m = stations_meta.get(eva, {})
        dump(OUT / "stations" / f"{eva}.json", {
            "eva": eva, "name": data.names[eva], "state": m.get("state"), "lat": m.get("lat"), "lon": m.get("lon"),
            "daily": daily[-120:], "best": best, "worst": worst, "history": history[eva]})

    latest = res["seasons"][-1] if res["seasons"] else None
    current = {}
    if latest:
        for lid, lg in latest["leagues"].items():
            for r in lg["tables"][-1] if lg["tables"] else []:
                current[r["eva"]] = lid
    dump(OUT / "meta.json", {
        "generated": dt.datetime.now(dt.timezone.utc).isoformat(timespec="minutes"),
        "last_day": data.days[-1].isoformat() if data.days else None,
        "leagues": config.league_defs(max((len(s["league_order"]) for s in res["seasons"]), default=1)), "seasons": index, "latest": latest["id"] if latest else None,
        "stations": {eva: {"name": data.names[eva], "league": current.get(eva),
                           "state": stations_meta.get(eva, {}).get("state"),
                           "lat": stations_meta.get(eva, {}).get("lat"),
                           "lon": stations_meta.get(eva, {}).get("lon")} for eva in members},
        "rules": {"min_arrivals": config.MIN_ARRIVALS, "punctual_limit": config.PUNCTUAL_LIMIT_MIN,
                  "types": config.TRAIN_TYPES, "direct_movers": config.DIRECT_MOVERS, "league_size": config.LEAGUE_SIZE, "min_day_share": config.MIN_DAY_SHARE,
                  "window": config.MEMBERSHIP_WINDOW_DAYS, "min_played_share": config.MIN_PLAYED_SHARE},
    })
    # crest icons depend on how many leagues there are (last league always gets 5 turtles)
    from scripts import make_logos
    make_logos.main(len(latest["league_order"]) if latest else 8)
    print(f"{len(index)} seasons, {len(members)} stations, latest {index[-1]['id'] if index else '-'}")


if __name__ == "__main__":
    main()
