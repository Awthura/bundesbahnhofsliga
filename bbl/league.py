"""Table engine: weekly seasons (calendar weeks, Mon..Sun), live tables after every matchday,
promotion/relegation after Sunday.

Between two neighbouring leagues: 17th and 18th go down, 1st and 2nd of the league below go up,
and 16th (above) meets 3rd (below) in a playoff decided by punctuality on the week's last day.

Input: daily rows {day, eva, station, points, plays, arrivals?, punctual?}. Pure Python, no I/O.
"""
from __future__ import annotations

import datetime as dt
import math
from collections import defaultdict

from . import config


def monday(d: dt.date) -> dt.date:
    return d - dt.timedelta(days=d.weekday())


def season_id(start: dt.date) -> str:
    y, w, _ = start.isocalendar()
    return f"{y}-KW{w:02d}"


class Data:
    def __init__(self, rows):
        self.by_day: dict[dt.date, dict[str, dict]] = defaultdict(dict)
        self.names: dict[str, str] = {}
        for r in rows:
            day = r["day"] if isinstance(r["day"], dt.date) else dt.date.fromisoformat(r["day"])
            plays = r["plays"] in (True, "True", "true", 1, "1")
            pts = r["points"]
            pts = float(pts) if pts not in (None, "") else None
            arr = int(r.get("arrivals") or 0)
            pun = r.get("punctual")
            share = (int(pun) / arr) if pun not in (None, "") and arr else pts   # exact share for playoffs
            self.by_day[day][r["eva"]] = {"points": pts, "plays": plays, "arrivals": arr, "share": share}
            self.names[r["eva"]] = r["station"]
        self.days = sorted(self.by_day)

    def window(self, end: dt.date, n: int):
        start = end - dt.timedelta(days=n)
        return [d for d in self.days if start <= d < end]

    def complete_days(self, days):
        """Drop days where the data source itself has a gap (total arrivals far below the usual level),
        so a collection outage can't throw stations out of the league."""
        totals = sorted(sum(r["arrivals"] for r in self.by_day[d].values()) for d in days)
        if not totals or not totals[-1]:
            return days
        median = totals[len(totals) // 2]
        return [d for d in days if sum(r["arrivals"] for r in self.by_day[d].values()) >= config.DATA_GAP_SHARE * median]

    def members(self, week_start: dt.date):
        days = self.complete_days(self.window(week_start, config.MEMBERSHIP_WINDOW_DAYS))
        if len(days) < config.SEED_MIN_DAYS:
            return None, {}
        played = defaultdict(list)
        for d in days:
            for eva, r in self.by_day[d].items():
                if r["plays"]:
                    played[eva].append(r["points"])
        need = config.MIN_DAY_SHARE * len(days)
        mem = {eva for eva, p in played.items() if len(p) >= need}
        avg = {eva: sum(played[eva]) / len(played[eva]) for eva in mem}
        return mem, avg


def split_leagues(order: list[str]) -> list[tuple[dict, list[str]]]:
    """Chunks of LEAGUE_SIZE; the last league takes the remainder."""
    defs = config.LEAGUES
    out, i = [], 0
    for k, lg in enumerate(defs):
        if i >= len(order):
            break
        last = k == len(defs) - 1
        n = len(order) - i if last or lg.get("size") is None else lg["size"]
        out.append((lg, order[i:i + n]))
        i += n
    return out


def table(evas: list[str], data: Data, days: list[dt.date], prev_ranks: dict[str, int] | None):
    """Table after the given matchdays. Rank by Schnitt (average per played day)."""
    k = len(days)
    need = math.ceil(config.MIN_PLAYED_SHARE * k)
    rows = []
    for eva in evas:
        pts = [data.by_day[d].get(eva) for d in days]
        played = [p["points"] for p in pts if p and p["plays"]]
        total = round(sum(played), 2)
        rows.append({
            "eva": eva, "station": data.names.get(eva, eva), "played": len(played), "points": total,
            "avg": round(total / len(played), 3) if played else 0.0,
            "ranked": len(played) >= need,
            "form": [(p["points"] if p and p["plays"] else None) for p in pts][-5:],
        })
    rows.sort(key=lambda r: (not r["ranked"], -r["avg"], -r["points"], r["station"]))
    for i, r in enumerate(rows, 1):
        r["rank"] = i
        r["trend"] = (prev_ranks[r["eva"]] - i) if prev_ranks and r["eva"] in prev_ranks else None
    return rows


def zones(n_upper: int, n_lower: int):
    """How many go directly, and whether a playoff happens, between two neighbouring leagues."""
    direct = min(config.DIRECT_MOVERS, n_upper // 3, n_lower // 3)
    playoff = config.PLAYOFF and direct > 0 and n_upper >= direct + 2 and n_lower >= direct + 1
    return direct, playoff


def playoff_winner(data: Data, day: dt.date, upper: str, lower: str) -> str:
    """Higher punctuality on the last day wins. A station that did not play that day cannot win.
    A tie keeps the upper league's station up."""
    def score(e):
        r = data.by_day.get(day, {}).get(e)
        return r["share"] if r and r["plays"] else None
    su, sl = score(upper), score(lower)
    if sl is not None and (su is None or sl > su):
        return lower
    return upper


def run(rows) -> dict:
    data = Data(rows)
    if not data.days:
        return {"seasons": [], "names": {}, "data": data}
    seasons, order = [], None
    week = monday(data.days[0]) + dt.timedelta(days=7)
    last = data.days[-1]
    while week <= last:
        mem, win_avg = data.members(week)
        if mem is None:
            week += dt.timedelta(days=7)
            continue
        status = {}
        if order is None:   # season 1 seeding: rank by average of the history window
            order = sorted(mem, key=lambda e: (-win_avg[e], data.names.get(e, e)))
            status = {e: "seeded" for e in order}
        else:
            new = sorted(mem - set(order), key=lambda e: (-win_avg[e], data.names.get(e, e)))
            order = [e for e in order if e in mem] + new
            status.update({e: "new" for e in new})
        split = split_leagues(order)
        days = [week + dt.timedelta(days=i) for i in range(7) if week + dt.timedelta(days=i) in data.by_day]
        sunday = week + dt.timedelta(days=6)
        complete = sunday in data.by_day
        if not days:  # data gap: no matchday this week, nothing changes
            week += dt.timedelta(days=7)
            continue

        season = {"id": season_id(week), "start": week.isoformat(), "end": sunday.isoformat(),
                  "complete": complete, "matchdays": [d.isoformat() for d in days], "leagues": {},
                  "league_order": [lg["id"] for lg, _ in split], "zones": {}, "moves": [], "playoffs": []}
        finals = []
        for lg, evas in split:
            md_tables, prev = [], None
            for k in range(1, len(days) + 1):
                t = table(evas, data, days[:k], prev)
                prev = {r["eva"]: r["rank"] for r in t}
                md_tables.append(t)
            finals.append([r["eva"] for r in md_tables[-1]] if md_tables else list(evas))
            season["leagues"][lg["id"]] = {"name": lg["name"], "short": lg["short"], "tables": md_tables,
                                           "status": {e: status[e] for e in evas if e in status}}
            season["zones"][lg["id"]] = {"up": 0, "down": 0, "po_up": False, "po_down": False}

        # zones are shown live; moves and playoffs are applied only once Sunday is played
        new_lists = [list(f) for f in finals]
        for i in range(len(split) - 1):
            a, b = split[i][0]["id"], split[i + 1][0]["id"]
            fa, fb = finals[i], finals[i + 1]
            direct, po = zones(len(fa), len(fb))
            season["zones"][a].update(down=direct, po_down=po)
            season["zones"][b].update(up=direct, po_up=po)
            if not complete or not direct:
                continue
            down, up = fa[-direct:], fb[:direct]
            if po:
                pu, pl = fa[-direct - 1], fb[direct]
                w = playoff_winner(data, sunday, pu, pl)
                season["playoffs"].append({"upper": a, "lower": b, "upper_eva": pu, "lower_eva": pl, "winner": w,
                                           "day": sunday.isoformat(),
                                           "upper_share": data.by_day[sunday].get(pu, {}).get("share"),
                                           "lower_share": data.by_day[sunday].get(pl, {}).get("share")})
                if w == pl:
                    down, up = down + [pu], up + [pl]
            for e in down:
                new_lists[i].remove(e)
                new_lists[i + 1].insert(0, e)
                season["moves"].append({"eva": e, "from": a, "to": b})
            for e in up:
                new_lists[i + 1].remove(e)
                new_lists[i].append(e)
                season["moves"].append({"eva": e, "from": b, "to": a})
        if complete:
            order = [e for lst in new_lists for e in lst]
        seasons.append(season)
        week += dt.timedelta(days=7)
    return {"seasons": seasons, "names": data.names, "data": data}
