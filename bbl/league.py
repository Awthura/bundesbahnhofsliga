"""Table engine: weekly seasons (calendar weeks, Mon..Sun), live tables after every matchday,
promotion/relegation after Sunday.

Pyramid like German football: 1., 2., 3. BL are national (18 each), below them Regionalbahnhofsligen by region.
Between two national leagues: 17th and 18th go down, 1st and 2nd of the league below go up, and 16th (above)
meets 3rd (below) in a playoff decided by punctuality on the week's last day.
Between the 3. BL (20 stations) and the Regionalbahnhofsligen: places 17-20 go down into their own region, and the
best 4 of the 5 regional champions (by weekly Schnitt) go up. No regional rotation, no playoff.

Input: daily rows {day, eva, station, points, plays, arrivals?, punctual?}. Pure Python, no I/O.
"""
from __future__ import annotations

import datetime as dt
import math
import statistics
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

    def members(self, week_start: dt.date, current: set[str] | None = None):
        """Members for the week starting week_start. Newcomers need at least MIN_ARRIVALS on every day
        of the window (MIN_DAY_SHARE); stations in `current` (last week's members) only need it on
        STAY_DAY_SHARE of the days. Both need a typical (median) day of MIN_MEDIAN_ARRIVALS or more."""
        days = self.complete_days(self.window(week_start, config.MEMBERSHIP_WINDOW_DAYS))
        if len(days) < config.SEED_MIN_DAYS:
            return None, {}
        played = defaultdict(list)
        for d in days:
            for eva, r in self.by_day[d].items():
                if r["plays"]:
                    played[eva].append(r["points"])
        current = current or set()

        def typical_day(eva):   # median ICE/IC arrivals over the window (days without trains count as 0)
            return statistics.median(self.by_day[d].get(eva, {}).get("arrivals", 0) for d in days)

        mem = {eva for eva, p in played.items()
               if len(p) >= (config.STAY_DAY_SHARE if eva in current else config.MIN_DAY_SHARE) * len(days)
               and typical_day(eva) >= config.MIN_MEDIAN_ARRIVALS}
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
            "arrivals": sum(p["arrivals"] for p in pts if p),   # traffic this week so far (national tie-break)
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


def final_through(data: Data) -> dt.date | None:
    """Last day whose data is complete. The newest day in the data may still be running (it is
    collected through the day, and late updates arrive with the next day's files), so a day only
    counts as finished once data for a later day exists."""
    return data.days[-1] - dt.timedelta(days=1) if data.days else None


def run(rows, states: dict[str, str] | None = None) -> dict:
    """states: eva -> Bundesland, used to place stations in their Regionalbahnhofsliga."""
    data = Data(rows)
    states = states or {}
    if not data.days:
        return {"seasons": [], "names": {}, "data": data, "leagues": {}}
    done_through = final_through(data)
    nat = config.NATIONAL_TIERS
    sizes = {str(t): config.league_size(t) for t in range(1, nat + 1)}
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
    last_rank: dict[str, tuple[str, int]] = {}   # eva -> (league, final place) of the last finished week
    went_down: dict[str, str] = {}               # relegated last week: eva -> league it left
    week = monday(data.days[0]) + dt.timedelta(days=7)
    last = data.days[-1]
    while week <= last:
        current = {e for l in lists.values() for e in l} if lists else None
        mem, win_avg = data.members(week, current)
        days = [week + dt.timedelta(days=i) for i in range(7) if week + dt.timedelta(days=i) in data.by_day]
        if mem is None or not days:
            week += dt.timedelta(days=7)
            continue
        status, fills, dropped = {}, [], []
        if lists is None:   # season 1 seeding: rank by average of the history window
            score = dict(win_avg)
            order = _sort_by(mem, score, data.names)
            lists = {l: [] for l in nat_ids + reg_ids}
            slots = [l for l in nat_ids for _ in range(sizes[l])]   # national places, top to bottom
            for i, e in enumerate(order):
                lists[slots[i] if i < len(slots) else rl(e)].append(e)
            status = {e: "seeded" for e in order}
        else:
            for l in lists:   # drop stations that no longer qualify
                dropped += [{"eva": e, "league": l} for e in lists[l] if e not in mem]
                lists[l] = [e for e in lists[l] if e in mem]
            known = {e for l in lists.values() for e in l}
            for e in _sort_by(mem - known, win_avg, data.names):   # newcomers start in their Regionalbahnhofsliga
                score.setdefault(e, win_avg[e])
                lists[rl(e)].append(e)
                status[e] = "new"
            # Fill gaps in national leagues, like football does when a club withdraws:
            # 1) spare the best-placed station that was just relegated from that league;
            # 2) otherwise the best-placed station of the league below that was already there last week
            #    (never a station that was just promoted into it, so nobody can jump two tiers).
            for i, l in enumerate(nat_ids):
                below = nat_ids[i + 1:i + 2] or reg_ids
                while len(lists[l]) < sizes[l]:
                    spared = [e for e, frm in went_down.items() if frm == l and any(e in lists[b] for b in below)]
                    if spared:
                        e, reason = min(spared, key=lambda x: last_rank[x][1]), "spared"
                    else:
                        cands = [e for b in below for e in lists[b] if last_rank.get(e, ("", 0))[0] == b]
                        if not cands:
                            break
                        e = min(cands, key=lambda x: (last_rank[x][1], -score.get(x, -1), data.names.get(x, x)))
                        reason = "next_best"
                    frm = next(b for b in below if e in lists[b])
                    lists[frm].remove(e)
                    lists[l].append(e)
                    went_down.pop(e, None)
                    fills.append({"eva": e, "from": frm, "to": l, "reason": reason})
        sunday = week + dt.timedelta(days=6)
        # the week is final only when Sunday is completely collected; never decide on a partial Sunday
        complete = sunday in data.by_day and sunday <= done_through
        active = [l for l in nat_ids + reg_ids if lists[l]]
        season = {"id": season_id(week), "start": week.isoformat(), "end": sunday.isoformat(),
                  "complete": complete, "matchdays": [d.isoformat() for d in days], "leagues": {},
                  "league_order": active, "zones": {}, "moves": [], "playoffs": [], "promotion_round": [],
                  "fills": fills, "dropped": dropped}
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

        def playoff(upper_l, upper_e, lower_l, lower_e, kind="relegation"):
            w = playoff_winner(data, sunday, upper_e, lower_e)
            season["playoffs"].append({"upper": upper_l, "lower": lower_l, "upper_eva": upper_e, "lower_eva": lower_e,
                                       "winner": w, "day": sunday.isoformat(), "kind": kind,
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
        if bottom and regs:   # 3. BL <-> Regionalbahnhofsligen: best 4 champions up, places 17-20 down
            champs = sorted((finals[r][0] for r in regs if finals[r][0]["ranked"]),
                            key=lambda r: (-r["avg"], -r["points"], r["station"]))
            n_down = min(config.RL_RELEGATED, config.RL_PROMOTED, len(champs), len(fin[bottom]) // 3)
            ups = [c["eva"] for c in champs[:n_down]]
            season["zones"][bottom].update(down=n_down)
            for e in ups:
                season["zones"][rl(e)].update(up=1)   # live: currently among the best champions
            season["promotion_round"] = [{"eva": c["eva"], "league": rl(c["eva"]), "avg": c["avg"],
                                          "result": "up" if c["eva"] in ups else "stays"} for c in champs]
            if complete and n_down:
                for e in fin[bottom][-n_down:]:
                    move(e, bottom, rl(e))
                for e in ups:
                    move(e, rl(e), bottom)

        if complete:   # apply the moves; remember final places for next week's gap filling
            last_rank = {r["eva"]: (l, r["rank"]) for l in active for r in finals[l]}
            tier = {l: defs[l]["tier"] for l in defs}
            went_down = {m["eva"]: m["from"] for m in season["moves"] if tier[m["to"]] > tier[m["from"]]}
            lists = {l: _sort_by(new.get(l, []), score, data.names) for l in lists}
        seasons.append(season)
        week += dt.timedelta(days=7)
    return {"seasons": seasons, "names": data.names, "data": data, "leagues": defs}
