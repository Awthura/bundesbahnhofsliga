"""Table engine: weekly seasons (calendar weeks, Mon..Sun), live tables after every matchday,
promotion/relegation after Sunday.

Pyramid like German football: 1., 2., 3. BBL are national (18 each), below them Regionalbahnhofsligen by region.
Between two national leagues: 17th and 18th go down, 1st and 2nd of the league below go up, and 16th (above)
meets 3rd (below) in a playoff decided by punctuality on the week's last day.
Between the 3. BBL and the Regionalbahnhofsligen: 17th and 18th go down into their own region; the regional champions
are ranked by Schnitt, the best 2 go up, the 3rd best plays the 16th of the 3. BBL (same Sunday playoff).

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


def _sort_by(evas, score, names):
    return sorted(evas, key=lambda e: (-score.get(e, -1), names.get(e, e)))


def run(rows, states: dict[str, str] | None = None) -> dict:
    """states: eva -> Bundesland, used to place stations in their Regionalbahnhofsliga."""
    data = Data(rows)
    states = states or {}
    if not data.days:
        return {"seasons": [], "names": {}, "data": data, "leagues": {}}
    size, nat = config.LEAGUE_SIZE, config.NATIONAL_TIERS
    nat_ids = [str(t) for t in range(1, nat + 1)]
    reg_ids = [config.regional_league(r)["id"] for r in config.REGIONS]
    defs = {str(t): config.national_league(t) for t in range(1, nat + 1)}
    defs.update({config.regional_league(r)["id"]: config.regional_league(r) for r in config.REGIONS})

    def region(e):
        st = config.STATE_OVERRIDES.get(e) or states.get(e)
        return config.region_of(st) or config.DEFAULT_REGION

    def rl(e):
        return f"RL-{region(e)}"

    seasons, lists, score = [], None, {}   # lists: league id -> ordered evas; score: last known Schnitt
    week = monday(data.days[0]) + dt.timedelta(days=7)
    last = data.days[-1]
    while week <= last:
        mem, win_avg = data.members(week)
        days = [week + dt.timedelta(days=i) for i in range(7) if week + dt.timedelta(days=i) in data.by_day]
        if mem is None or not days:
            week += dt.timedelta(days=7)
            continue
        status = {}
        if lists is None:   # season 1 seeding: rank by average of the history window
            score = dict(win_avg)
            order = _sort_by(mem, score, data.names)
            lists = {l: [] for l in nat_ids + reg_ids}
            for i, e in enumerate(order):
                lists[nat_ids[i // size] if i < size * nat else rl(e)].append(e)
            status = {e: "seeded" for e in order}
        else:
            for l in lists:   # drop stations that no longer qualify
                lists[l] = [e for e in lists[l] if e in mem]
            known = {e for l in lists.values() for e in l}
            for e in _sort_by(mem - known, win_avg, data.names):   # newcomers start in their Regionalbahnhofsliga
                score.setdefault(e, win_avg[e])
                lists[rl(e)].append(e)
                status[e] = "new"
            for i, l in enumerate(nat_ids):   # fill gaps in national leagues from below
                while len(lists[l]) < size:
                    if i + 1 < len(nat_ids):
                        if not lists[nat_ids[i + 1]]:
                            break
                        lists[l].append(lists[nat_ids[i + 1]].pop(0))
                    else:
                        tops = [lists[r][0] for r in reg_ids if lists[r]]
                        if not tops:
                            break
                        e = _sort_by(tops, score, data.names)[0]
                        lists[rl(e)].remove(e)
                        lists[l].append(e)
        sunday = week + dt.timedelta(days=6)
        complete = sunday in data.by_day
        active = [l for l in nat_ids + reg_ids if lists[l]]
        season = {"id": season_id(week), "start": week.isoformat(), "end": sunday.isoformat(),
                  "complete": complete, "matchdays": [d.isoformat() for d in days], "leagues": {},
                  "league_order": active, "zones": {}, "moves": [], "playoffs": [], "promotion_round": []}
        finals = {}
        for l in active:
            md_tables, prev = [], None
            for k in range(1, len(days) + 1):
                t = table(lists[l], data, days[:k], prev)
                prev = {r["eva"]: r["rank"] for r in t}
                md_tables.append(t)
            finals[l] = md_tables[-1]
            season["leagues"][l] = {**defs[l], "tables": md_tables,
                                    "status": {e: status[e] for e in lists[l] if e in status}}
            season["zones"][l] = {"up": 0, "down": 0, "po_up": False, "po_down": False}
            for r in finals[l]:
                score[r["eva"]] = r["avg"] if r["ranked"] else -1
        fin = {l: [r["eva"] for r in finals[l]] for l in active}
        new = {l: list(v) for l, v in fin.items()}

        def move(e, a, b):
            new[a].remove(e)
            new[b].append(e)
            season["moves"].append({"eva": e, "from": a, "to": b})

        def playoff(upper_l, upper_e, lower_l, lower_e):
            w = playoff_winner(data, sunday, upper_e, lower_e)
            season["playoffs"].append({"upper": upper_l, "lower": lower_l, "upper_eva": upper_e, "lower_eva": lower_e,
                                       "winner": w, "day": sunday.isoformat(),
                                       "upper_share": data.by_day[sunday].get(upper_e, {}).get("share"),
                                       "lower_share": data.by_day[sunday].get(lower_e, {}).get("share")})
            return w

        nat_active = [l for l in nat_ids if l in fin]
        for a, b in zip(nat_active, nat_active[1:]):   # national pairs
            direct, po = zones(len(fin[a]), len(fin[b]))
            season["zones"][a].update(down=direct, po_down=po)
            season["zones"][b].update(up=direct, po_up=po)
            if complete and direct:
                downs, ups = fin[a][-direct:], fin[b][:direct]
                if po and playoff(a, fin[a][-direct - 1], b, fin[b][direct]) == fin[b][direct]:
                    downs, ups = downs + [fin[a][-direct - 1]], ups + [fin[b][direct]]
                for e in downs:
                    move(e, a, b)
                for e in ups:
                    move(e, b, a)

        regs = [l for l in reg_ids if l in fin]
        bottom = nat_active[-1] if nat_active else None
        if bottom and regs:   # 3. BBL <-> Regionalbahnhofsligen: promotion round of the regional champions
            champs = [finals[r][0] for r in regs if finals[r][0]["ranked"]]
            champs.sort(key=lambda r: (-r["avg"], -r["points"], r["station"]))
            direct = min(config.DIRECT_MOVERS, len(fin[bottom]) // 3, len(champs))
            po = config.PLAYOFF and len(champs) > direct and len(fin[bottom]) >= direct + 2
            season["zones"][bottom].update(down=direct, po_down=po)
            for r in regs:
                season["zones"][r].update(po_up=True)   # the champion is in the promotion round
            season["promotion_round"] = [{"eva": c["eva"], "league": rl(c["eva"]), "avg": c["avg"],
                                          "result": "up" if i < direct else ("playoff" if po and i == direct else "stays")}
                                         for i, c in enumerate(champs)]
            if complete and direct:
                downs, ups = fin[bottom][-direct:], [c["eva"] for c in champs[:direct]]
                if po:
                    ue, le = fin[bottom][-direct - 1], champs[direct]["eva"]
                    if playoff(bottom, ue, rl(le), le) == le:
                        downs, ups = downs + [ue], ups + [le]
                for e in downs:
                    move(e, bottom, rl(e))
                for e in ups:
                    move(e, rl(e), bottom)

        if complete:   # keep lists in last week's ranking order (used to fill gaps)
            lists = {l: _sort_by(new.get(l, []), score, data.names) for l in lists}
        seasons.append(season)
        week += dt.timedelta(days=7)
    return {"seasons": seasons, "names": data.names, "data": data, "leagues": defs}
