"""Run the table engine on data/daily_points.csv and write JSON for the static site in docs/data/."""
from __future__ import annotations

import csv
import datetime as dt
import json
import shutil
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from bbl import audit, config, forecast, league, stats  # noqa: E402

OUT = ROOT / "docs" / "data"


def version_assets():
    """Cache-busting: reference app.js/style.css as ...?v=<content hash> in every page, so a browser
    never combines a new page with a cached old script (GitHub Pages caches assets for 10 minutes)."""
    import hashlib
    import re
    docs = ROOT / "docs"
    for name in ("app.js", "style.css"):
        h = hashlib.sha256((docs / "assets" / name).read_bytes()).hexdigest()[:10]
        for page in docs.glob("*.html"):
            txt = page.read_text()
            new = re.sub(rf"assets/{re.escape(name)}(\?v=[0-9a-f]+)?", f"assets/{name}?v={h}", txt)
            if new != txt:
                page.write_text(new)


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
    states = {e: v.get("state") for e, v in stations_meta.items()}
    res = league.run(rows, states)
    problems = audit.audit(res, rows, states)
    if problems:   # never publish a history that breaks the rules
        print(f"AUDIT FAILED: {len(problems)} violations", file=sys.stderr)
        for p in problems[:50]:
            print(" -", p, file=sys.stderr)
        sys.exit(1)
    print("audit: 0 violations")
    data = res["data"]
    if OUT.exists():
        shutil.rmtree(OUT)

    history = {}
    index = []
    for s in res["seasons"]:
        tier_of = {lid: lg["tier"] for lid, lg in s["leagues"].items()}
        tier_of.update({l["id"]: l["tier"] for l in res["leagues"].values()})
        moved = {m["eva"]: ("up" if tier_of[m["to"]] < tier_of[m["from"]] else "down") for m in s["moves"]}
        filled = {f["eva"]: f["reason"] for f in s.get("fills", [])}
        index.append({k: s[k] for k in ("id", "start", "end", "complete")} | {"matchdays": len(s["matchdays"])})
        dump(OUT / "season" / f"{s['id']}.json", s)
        for lid, lg in s["leagues"].items():
            for r in lg["tables"][-1] if lg["tables"] else []:
                history.setdefault(r["eva"], []).append(
                    {"season": s["id"], "league": lid, "short": lg["short"], "tier": lg["tier"], "rank": r["rank"],
                     "size": len(lg["tables"][-1]), "avg": r["avg"], "played": r["played"],
                     "complete": s["complete"], "move": moved.get(r["eva"]), "filled": filled.get(r["eva"])})

    # champions history per league: winner (and runner-up) of every finished week
    champions = {lid: {**lg, "seasons": []} for lid, lg in res["leagues"].items()}
    for s in res["seasons"]:
        for lid, lg in s["leagues"].items():
            t = lg["tables"][-1] if lg["tables"] else []
            if not t:
                continue
            entry = {"season": s["id"], "start": s["start"], "end": s["end"], "complete": s["complete"],
                     "champion": {k: t[0][k] for k in ("eva", "station", "avg", "points", "played")},
                     "runner_up": {k: t[1][k] for k in ("eva", "station", "avg")} if len(t) > 1 else None,
                     "promoted": any(m["eva"] == t[0]["eva"] and m["from"] == lid for m in s["moves"])}
            champions[lid]["seasons"].append(entry)
    for lid, c in champions.items():
        done = [x for x in c["seasons"] if x["complete"]]
        tally = {}
        for x in done:
            e = x["champion"]["eva"]
            tally.setdefault(e, {"eva": e, "station": x["champion"]["station"], "titles": 0, "last": None})
            tally[e]["titles"] += 1
            tally[e]["last"] = x["season"]
        c["record"] = sorted(tally.values(), key=lambda r: (-r["titles"], r["last"]), reverse=False)
        c["seasons"].reverse()   # newest first
    dump(OUT / "champions.json", {"order": [l for l in res["leagues"]], "leagues": champions})

    members = sorted(history)
    full_daily = {eva: [{"day": d.isoformat(), **data.by_day[d][eva]} for d in data.days if eva in data.by_day[d]]
                  for eva in members}
    latest_members = {r["eva"] for lg in res["seasons"][-1]["leagues"].values() for r in lg["tables"][-1]} \
        if res["seasons"] else set()
    state_of = {e: config.STATE_OVERRIDES.get(e) or stations_meta.get(e, {}).get("state") for e in members}
    # national rank cards: place in the national ranking of the last finished week, and the week before
    done = [s for s in res["seasons"] if s["complete"]]
    ranks = stats.week_ranks(done[-1], state_of) if done else {}
    prev_ranks = stats.week_ranks(done[-2], state_of) if len(done) > 1 else {}
    for e, r in ranks.items():
        if e in prev_ranks:
            r["change"] = prev_ranks[e]["rank"] - r["rank"]          # positive = moved up
            r["state_change"] = prev_ranks[e]["state_rank"] - r["state_rank"] if prev_ranks[e].get("state") == r.get("state") else None
    # forecast settings re-tuned on all past days (every forecast only uses data before its day)
    running = data.days[-1]
    fc_model = forecast.tune([[(dt.date.fromisoformat(d["day"]), d["points"]) for d in full_daily[e]
                               if d["plays"] and d["points"] is not None and d["day"] < running.isoformat()]
                              for e in members])
    print(f"forecast model: {fc_model}")
    for eva in members:
        daily = full_daily[eva]
        played = [x for x in daily if x["plays"]]
        best = max(played, key=lambda x: x["points"], default=None)
        worst = min(played, key=lambda x: x["points"], default=None)
        m = stations_meta.get(eva, {})
        fc = forecast.station_forecast(daily, data.days[-1], params=fc_model["params"])
        dump(OUT / "stations" / f"{eva}.json", {
            "forecast": fc,
            "eva": eva, "name": data.names[eva], "state": config.STATE_OVERRIDES.get(eva) or m.get("state"), "lat": m.get("lat"), "lon": m.get("lon"),
            "daily": daily[-120:], "best": best, "worst": worst, "history": history[eva],
            "stats": {"overall_avg": stats.overall_average(daily), "national": ranks.get(eva),
                      "streaks": stats.streaks([d for d in daily if d["day"] < running.isoformat()]),   # running day still open "weekdays": stats.weekday_profile(daily),
                      "records": stats.records(history[eva]), "volume": stats.volume(daily)}})

    # typical day (median ICE/IC/EC arrivals over the last 28 days), for the frequency filter on the ranking page
    recent = data.days[-config.MEMBERSHIP_WINDOW_DAYS:]
    typical_day = {e: statistics.median(data.by_day[d].get(e, {}).get("arrivals", 0) for d in recent)
                   for e in members} if recent else {}

    latest = res["seasons"][-1] if res["seasons"] else None
    current = {}
    if latest:
        for lid, lg in latest["leagues"].items():
            for r in lg["tables"][-1] if lg["tables"] else []:
                current[r["eva"]] = lid
    dump(OUT / "meta.json", {
        "generated": dt.datetime.now(dt.timezone.utc).isoformat(timespec="minutes"),
        "last_day": data.days[-1].isoformat() if data.days else None,
        "leagues": list(res["leagues"].values()), "seasons": index, "latest": latest["id"] if latest else None,
        "stations": {eva: {"name": data.names[eva], "league": current.get(eva),
                           "state": config.STATE_OVERRIDES.get(eva) or stations_meta.get(eva, {}).get("state"),
                           "lat": stations_meta.get(eva, {}).get("lat"),
                           "lon": stations_meta.get(eva, {}).get("lon"),
                           "per_day": typical_day.get(eva)} for eva in members},
        "forecast_model": fc_model,
        "rules": {"min_arrivals": config.MIN_ARRIVALS, "punctual_limit": config.PUNCTUAL_LIMIT_MIN,
                  "types": config.TRAIN_TYPES, "direct_movers": config.DIRECT_MOVERS, "league_sizes": config.LEAGUE_SIZES, "rl_relegated": config.RL_RELEGATED, "min_day_share": config.MIN_DAY_SHARE, "stay_day_share": config.STAY_DAY_SHARE, "min_median_arrivals": config.MIN_MEDIAN_ARRIVALS,
                  "window": config.MEMBERSHIP_WINDOW_DAYS, "min_played_share": config.MIN_PLAYED_SHARE},
    })
    # crests are generated from bbl/config.py (regions)
    from scripts import make_logos
    make_logos.main()
    version_assets()
    print(f"{len(index)} seasons, {len(members)} stations, latest {index[-1]['id'] if index else '-'}")


if __name__ == "__main__":
    main()
