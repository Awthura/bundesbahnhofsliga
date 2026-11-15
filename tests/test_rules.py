import datetime as dt

import duckdb

from bbl import audit, config, forecast, ingest, league, points, stats


def stops_con(rows):
    con = duckdb.connect()
    con.execute(f"CREATE TABLE s ({ingest.STOPS_COLUMNS})")
    con.executemany("INSERT INTO s VALUES (?, ?, ?, ?, ?, ?, ?, ?)", rows)
    return con


def stop(i, delay=0, canceled=False, eva="1", day="2026-11-09 10:00"):
    return [str(i), eva, "Teststadt Hbf", "ICE", str(i), dt.datetime.fromisoformat(day), delay, canceled]


# --- daily points -----------------------------------------------------------

def test_points_are_share_between_0_and_1_and_rounded():
    assert points.score_day(3, 2) == (0.67, False)
    assert points.score_day(5, 3) == (0.6, True)
    assert points.score_day(7, 7) == (1.0, True)
    assert points.score_day(7, 0) == (0.0, True)


def test_at_least_five_arrivals_needed_to_be_scored():
    assert points.score_day(4, 4)[1] is False
    assert points.score_day(5, 5)[1] is True


def test_cancelled_counts_as_not_punctual_and_six_minutes_is_late():
    rows = [stop(1, 0), stop(2, 5), stop(3, 6), stop(4, 0, canceled=True), stop(5, 2), stop(6, 30)]
    (r,) = points.daily_counts(stops_con(rows), "s")
    assert (r["arrivals"], r["punctual"], r["canceled"]) == (6, 3, 1)
    assert r["points"] == 0.5 and r["plays"]


def test_duplicate_stop_ids_counted_once():
    rows = [stop(1, 0), stop(1, 0), stop(2, 0)]
    (r,) = points.daily_counts(stops_con(rows), "s")
    assert r["arrivals"] == 2


# --- raw API parsing ---------------------------------------------------------

PLAN = """<timetable station='Halle(Saale)Hbf'>
<s id="a-1"><tl c="ICE" n="1"/><ar pt="2611091000"/><dp pt="2611091002"/></s>
<s id="a-2"><tl c="ICE" n="2"/><dp pt="2611091100"/></s>
<s id="a-3"><tl c="RE" n="3"/><ar pt="2611091200"/></s>
<s id="a-4"><tl c="IC" n="4"/><ar pt="2611091300"/></s>
<s id="a-5"><tl c="ECE" n="5"/><ar pt="2611091400"/></s>
</timetable>"""
FCHG_OLD = '<timetable><s id="a-1"><ar ct="2611091020"/></s></timetable>'
FCHG_NEW = '<timetable><s id="a-1"><ar ct="2611091004"/></s><s id="a-4"><ar cs="c"/></s></timetable>'


def test_raw_plan_and_latest_change_win():
    acc = ingest.RawAccumulator()
    url = "https://x/timetables/v1/plan/08010159/261109/10"
    acc.add(dt.datetime(2026, 11, 9, 8), url, "timetables/v1/plan", PLAN)
    acc.add(dt.datetime(2026, 11, 9, 11), "", "timetables/v1/fchg", FCHG_NEW)
    acc.add(dt.datetime(2026, 11, 9, 9), "", "timetables/v1/fchg", FCHG_OLD)  # older, arrives late
    s = {r["id"]: r for r in acc.stops()}
    assert set(s) == {"a-1", "a-4", "a-5"}    # first stop (no <ar>) and RE ignored; EC/ECE count
    assert s["a-1"]["delay_in_min"] == 4 and s["a-1"]["eva"] == "08010159"
    assert s["a-4"]["canceled"]


# --- league engine -----------------------------------------------------------

def make_rows(n_stations, days, score):
    out = []
    for d in days:
        for i in range(n_stations):
            out.append({"day": d, "eva": f"{i:03d}", "station": f"S{i:03d}", "points": score(i, d), "plays": True,
                        "arrivals": 20})
    return out


def small_pyramid(monkeypatch, tiers=2, size=6, promoted=2, relegated=2, regions=None):
    monkeypatch.setattr(config, "LEAGUE_SIZE", size)
    monkeypatch.setattr(config, "LEAGUE_SIZES", {})
    monkeypatch.setattr(config, "NATIONAL_TIERS", tiers)
    monkeypatch.setattr(config, "REGIONS", regions or {"N": ("Nord", ["Hamburg"]), "S": ("Süd", ["Bayern"])})
    monkeypatch.setattr(config, "RL_PROMOTED", promoted)
    monkeypatch.setattr(config, "RL_RELEGATED", relegated)


def test_weekly_promotion_relegation_and_playoff(monkeypatch):
    small_pyramid(monkeypatch, tiers=2, size=6)
    start = dt.date(2026, 11, 2)
    seed = [start - dt.timedelta(days=i) for i in range(1, 8)]
    week1 = [start + dt.timedelta(days=i) for i in range(7)]
    week2 = [start + dt.timedelta(days=7 + i) for i in range(2)]
    # 12 stations fill the two national leagues. Seeding: station i better than i+1.
    # Week 1: reversed, so the lowest become the best.
    rows = make_rows(12, seed, lambda i, d: 1 - i / 20)
    rows += make_rows(12, week1 + week2, lambda i, d: i / 20)
    res = league.run(rows, {})
    s1, s2 = res["seasons"]
    assert s1["id"] == "2026-KW45" and s1["complete"] and not s2["complete"]
    assert s1["leagues"]["1"]["tables"][0][0]["eva"] == "005"
    moves = {(m["eva"], m["from"], m["to"]) for m in s1["moves"]}
    # 2 direct each way, plus playoff: 002 (4th of 6 above) vs 009 (3rd below), 009 better on Sunday
    assert moves == {("011", "2", "1"), ("010", "2", "1"), ("009", "2", "1"),
                     ("000", "1", "2"), ("001", "1", "2"), ("002", "1", "2")}
    (po,) = s1["playoffs"]
    assert (po["upper_eva"], po["lower_eva"], po["winner"]) == ("002", "009", "009")
    assert {r["eva"] for r in s2["leagues"]["1"]["tables"][-1]} == {"003", "004", "005", "009", "010", "011"}
    assert len(s2["leagues"]["1"]["tables"]) == 2  # live table after each matchday


def test_regionalligen_and_promotion_round(monkeypatch):
    small_pyramid(monkeypatch, tiers=1, size=6)
    start = dt.date(2026, 11, 2)
    seed = [start - dt.timedelta(days=i) for i in range(1, 8)]
    week1 = [start + dt.timedelta(days=i) for i in range(7)]
    # 6 national + 6 regional: odd stations in Hamburg (Nord), even in Bayern (Süd)
    states = {f"{i:03d}": ("Hamburg" if i % 2 else "Bayern") for i in range(12)}
    rows = make_rows(12, seed, lambda i, d: 1 - i / 20)
    rows += make_rows(12, week1, lambda i, d: i / 20)   # reversed again
    rows += make_rows(12, [week1[-1] + dt.timedelta(days=1)], lambda i, d: 0.5)   # Monday: Sunday is complete
    s1 = league.run(rows, states)["seasons"][0]
    assert s1["league_order"] == ["1", "RL-N", "RL-S"]
    assert sorted(e["eva"] for e in s1["leagues"]["RL-N"]["tables"][0]) == ["007", "009", "011"]
    assert sorted(e["eva"] for e in s1["leagues"]["RL-S"]["tables"][0]) == ["006", "008", "010"]
    # both champions are among the best 2: 011 (Nord) and 010 (Süd) go up
    assert {c["eva"]: c["result"] for c in s1["promotion_round"]} == {"011": "up", "010": "up"}
    moves = {(m["eva"], m["from"], m["to"]) for m in s1["moves"]}
    # 000 (Bayern) and 001 (Hamburg) drop into their own region
    assert moves == {("011", "RL-N", "1"), ("010", "RL-S", "1"), ("000", "1", "RL-S"), ("001", "1", "RL-N")}


def test_playoff_tie_and_called_off():
    sun = dt.date(2026, 11, 8)
    data = league.Data([
        {"day": sun, "eva": "u", "station": "U", "points": 0.5, "plays": True, "arrivals": 10, "punctual": 5},
        {"day": sun, "eva": "l", "station": "L", "points": 0.5, "plays": True, "arrivals": 20, "punctual": 10},
        {"day": sun, "eva": "x", "station": "X", "points": 1.0, "plays": False, "arrivals": 3, "punctual": 3},
        {"day": sun, "eva": "y", "station": "Y", "points": 0.67, "plays": True, "arrivals": 6, "punctual": 4},
    ])
    assert league.playoff_winner(data, sun, "u", "l") == "u"   # tie: upper stays
    assert league.playoff_winner(data, sun, "u", "x") == "u"   # lower did not play Sunday
    assert league.playoff_winner(data, sun, "x", "y") == "y"   # upper did not play Sunday


def test_fchg_cancellation_time_counts_and_empty_snapshots_are_ignored():
    acc = ingest.RawAccumulator()
    acc.add(dt.datetime(2026, 11, 9, 8), "https://x/timetables/v1/plan/08010159/261109/10", "timetables/v1/plan", PLAN)
    acc.add(dt.datetime(2026, 11, 9, 9), "", "timetables/v1/fchg",
            '<timetable><s id="a-1"><ar ct="2611091012"/></s><s id="a-4"><ar clt="2611090900"/></s></timetable>')
    acc.add(dt.datetime(2026, 11, 9, 10), "", "timetables/v1/fchg",
            '<timetable><s id="a-1"><ar l="10"/></s></timetable>')   # no arrival info: keep the earlier change
    s = {r["id"]: r for r in acc.stops()}
    assert s["a-1"]["delay_in_min"] == 12
    assert s["a-4"]["canceled"]


def test_membership_needs_at_least_5_arrivals_every_day():
    start = dt.date(2026, 11, 9)
    rows = []
    for i in range(1, 15):
        d = start - dt.timedelta(days=i)
        rows.append({"day": d, "eva": "hub", "station": "Hub", "points": 0.5, "plays": True, "arrivals": 300})
        rows.append({"day": d, "eva": "a", "station": "A", "points": 0.9, "plays": True, "arrivals": 20})
        rows.append({"day": d, "eva": "b", "station": "B", "points": 0.9, "plays": i != 3,
                     "arrivals": 20 if i != 3 else 3})   # one thin day
    mem, _ = league.Data(rows).members(start)
    assert mem == {"hub", "a"}


def test_data_gap_day_does_not_cost_membership():
    start = dt.date(2026, 11, 9)
    rows = []
    for i in range(1, 15):
        d = start - dt.timedelta(days=i)
        gap = i == 5   # collection outage: everyone has few arrivals that day
        for e in ("a", "b", "c"):
            rows.append({"day": d, "eva": e, "station": e, "points": 0.9, "plays": not gap,
                         "arrivals": 3 if gap else 20})
    mem, _ = league.Data(rows).members(start)
    assert mem == {"a", "b", "c"}


def test_best_4_of_5_champions_go_up(monkeypatch):
    regions = {r: (r, [f"S{r}"]) for r in ("A", "B", "C", "D", "E")}
    small_pyramid(monkeypatch, tiers=1, size=12, promoted=4, relegated=4, regions=regions)
    start = dt.date(2026, 11, 2)
    seed = [start - dt.timedelta(days=i) for i in range(1, 8)]
    week1 = [start + dt.timedelta(days=i) for i in range(7)]
    n = 22                                     # 12 national + 2 per region
    states = {f"{i:03d}": f"S{'ABCDE'[i % 5]}" for i in range(n)}
    rows = make_rows(n, seed, lambda i, d: 1 - i / 40)
    rows += make_rows(n, week1, lambda i, d: 0.2 + i / 40)   # reversed: higher number = better this week
    rows += make_rows(n, [week1[-1] + dt.timedelta(days=1)], lambda i, d: 0.5)   # Monday: Sunday is complete
    s1 = league.run(rows, states)["seasons"][0]
    rnd = s1["promotion_round"]
    assert len(rnd) == 5 and [c["result"] for c in rnd] == ["up", "up", "up", "up", "stays"]
    assert [c["avg"] for c in rnd] == sorted((c["avg"] for c in rnd), reverse=True)
    ups = {m["eva"] for m in s1["moves"] if m["to"] == "1"}
    downs = [m for m in s1["moves"] if m["from"] == "1"]
    assert ups == {c["eva"] for c in rnd[:4]} and len(downs) == 4
    assert not s1["playoffs"]


def test_forecast_probability_and_weekday_weight():
    target = dt.date(2026, 11, 15)                           # a Sunday
    hist = []
    for i in range(1, 29):
        d = target - dt.timedelta(days=i)
        hist.append((d, 0.9 if d.weekday() == 6 else 0.4))   # great on Sundays, poor otherwise
    f = forecast.predict(hist, target)
    g = forecast.predict(hist, target + dt.timedelta(days=1))   # Monday
    assert 0 < g["p_yes"] < f["p_yes"] < 1                   # Sunday forecast clearly higher
    assert f["low"] == 0.4 and f["high"] == 0.9
    assert forecast.predict(hist[:3], target) is None        # too little history
    assert forecast.predict([(target, 1.0)] * 10, target) is None   # never uses the target day itself


def test_forecast_history_is_out_of_sample():
    daily = [{"day": (dt.date(2026, 10, 1) + dt.timedelta(days=i)).isoformat(), "points": 0.7, "plays": True}
             for i in range(40)]
    fc = forecast.station_forecast(daily, dt.date(2026, 11, 10))
    assert fc["p_yes"] > 0.9 and fc["brier"] is not None and fc["resolved"] > 0
    assert all(h["day"] < "2026-11-10" for h in fc["history"])


def _three_tier_history(monkeypatch):
    regions = {"N": ("Nord", ["SN"]), "S": ("Süd", ["SS"])}
    small_pyramid(monkeypatch, tiers=2, size=6, promoted=2, relegated=2, regions=regions)
    monkeypatch.setattr(config, "LEAGUE_SIZES", {})
    start = dt.date(2026, 11, 2)
    seed = [start - dt.timedelta(days=i) for i in range(1, 8)]
    weeks = [start + dt.timedelta(days=i) for i in range(16)]
    n = 18
    states = {f"{i:03d}": ("SN" if i % 2 else "SS") for i in range(n)}
    rows = make_rows(n, seed, lambda i, d: 1 - i / 40)
    rows += make_rows(n, weeks, lambda i, d: 0.2 + ((i * 7 + d.toordinal()) % 17) / 25)
    for r in rows:
        r["arrivals"], r["punctual"], r["canceled"] = 20, round(r["points"] * 20), 0
        r["points"] = round(r["punctual"] / 20, 2)
    return league.run(rows, states), rows, states


def test_audit_passes_on_engine_output(monkeypatch):
    res, rows, states = _three_tier_history(monkeypatch)
    assert len(res["seasons"]) >= 2
    assert audit.audit(res, rows, states) == []


def test_audit_catches_tampering(monkeypatch):
    res, rows, states = _three_tier_history(monkeypatch)
    s1, s2 = res["seasons"][0], res["seasons"][1]
    # a station silently jumps from the bottom league to the top
    low = s2["leagues"]["RL-N"]["tables"][-1][0]
    s2["leagues"]["1"]["tables"][-1].append(dict(low))
    errs = audit.audit(res, rows, states)
    assert any("jumped" in e or "is in" in e for e in errs)
    # wrong daily points
    res2, rows2, states2 = _three_tier_history(monkeypatch)
    rows2[0]["points"] = 0.99
    assert any("points" in e for e in audit.audit(res2, rows2, states2))
    # a promotion that the rules don't allow
    res3, rows3, states3 = _three_tier_history(monkeypatch)
    res3["seasons"][0]["moves"].append({"eva": res3["seasons"][0]["leagues"]["2"]["tables"][-1][3]["eva"], "from": "2", "to": "1"})
    assert any("moves differ" in e for e in audit.audit(res3, rows3, states3))


def test_audit_real_history():
    """The committed history must pass the audit with the current rules."""
    import csv
    import json
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent
    rows = list(csv.DictReader((root / "data" / "daily_points.csv").open()))
    st = json.loads((root / "data" / "stations.json").read_text())
    states = {e: v.get("state") for e, v in st.items()}
    assert audit.audit(league.run(rows, states), rows, states) == []


def test_membership_hard_to_join_easy_to_stay():
    start = dt.date(2026, 11, 9)
    rows = []
    for i in range(1, 29):
        d = start - dt.timedelta(days=i)
        rows.append({"day": d, "eva": "a", "station": "A", "points": 0.9, "plays": i not in (3, 4),
                     "arrivals": 20 if i not in (3, 4) else 0})                                   # 2 thin days
        rows.append({"day": d, "eva": "b", "station": "B", "points": 0.9, "plays": i <= 10,
                     "arrivals": 20 if i <= 10 else 0})                                           # 18 thin days
        rows.append({"day": d, "eva": "c", "station": "C", "points": 0.9, "plays": True, "arrivals": 20})
    data = league.Data(rows)
    assert data.members(start)[0] == {"c"}                          # newcomers: every day
    assert data.members(start, {"a", "b", "c"})[0] == {"a", "c"}    # members: at least half of the days


def test_typical_day_needs_10_arrivals():
    start = dt.date(2026, 11, 9)
    rows = []
    for i in range(1, 29):
        d = start - dt.timedelta(days=i)
        rows.append({"day": d, "eva": "busy", "station": "Busy", "points": 0.7, "plays": True, "arrivals": 40})
        rows.append({"day": d, "eva": "quiet", "station": "Quiet", "points": 0.9, "plays": True, "arrivals": 7})
        rows.append({"day": d, "eva": "mixed", "station": "Mixed", "points": 0.8, "plays": True,
                     "arrivals": 12 if i % 2 else 6})   # median 9: not enough
    data = league.Data(rows)
    assert data.members(start)[0] == {"busy"}
    assert data.members(start, {"busy", "quiet", "mixed"})[0] == {"busy"}   # staying needs it too


def test_station_stats():
    days = [{"day": f"2026-11-{i:02d}", "points": p, "plays": pl, "arrivals": a} for i, (p, pl, a) in enumerate([
        (0.9, True, 20), (0.85, True, 22), (0.5, True, 20), (0.8, True, 18), (0.95, True, 30),
        (0.9, True, 25), (None, False, 2), (0.82, True, 20)], start=2)]   # Nov 2 is a Monday
    s = stats.streaks(days, level=0.8)
    assert (s["longest"], s["longest_from"], s["longest_to"], s["current"]) == (3, "2026-11-05", "2026-11-07", 1)
    wk = stats.weekday_profile(days)
    assert wk[0]["avg"] == round((0.9 + 0.82) / 2, 3) and wk[6]["days"] == 0   # Sunday Nov 8 not scored
    v = stats.volume(days)
    assert v["busiest"] == {"day": "2026-11-06", "arrivals": 30}
    r = stats.national_ranks({"a": 0.7, "b": 0.6, "c": 0.8, "d": None}, {"a": "X", "b": "Y", "c": "X"})
    assert r["c"]["rank"] == 1 and r["a"]["state_rank"] == 2 and r["b"]["state_rank"] == 1 and r["a"]["of"] == 3
    hist = [{"season": "KW1", "league": "2", "short": "2. BBL", "tier": 2, "rank": 1, "avg": 0.8, "complete": True, "move": "up"},
            {"season": "KW2", "league": "1", "short": "BBL", "tier": 1, "rank": 17, "avg": 0.6, "complete": True, "move": "down"},
            {"season": "KW3", "league": "2", "short": "2. BBL", "tier": 2, "rank": 3, "avg": 0.9, "complete": False, "move": None}]
    rec = stats.records(hist)
    assert rec["best_week"]["season"] == "KW1" and rec["highest"]["short"] == "BBL"
    assert (rec["titles"], rec["promotions"], rec["relegations"]) == (1, 1, 1)


def test_week_ranks_follow_the_ranking_page_order():
    def row(e, avg, ranked=True, pts=1.0):
        return {"eva": e, "station": e.upper(), "avg": avg, "points": pts, "ranked": ranked}
    season = {"id": "2026-KW45", "leagues": {
        "1": {"tables": [[row("a", 0.70), row("b", 0.60)]]},
        "RL-N": {"tables": [[row("c", 0.80), row("d", 0.95, ranked=False)]]}}}
    r = stats.week_ranks(season, {"a": "X", "b": "Y", "c": "X", "d": "X"})
    assert [r[e]["rank"] for e in "cabd"] == [1, 2, 3, 4]      # unranked last, even with the best average
    assert (r["a"]["state_rank"], r["a"]["state_of"], r["a"]["season"]) == (2, 3, "2026-KW45")


def test_week_is_not_closed_on_a_partial_sunday(monkeypatch):
    small_pyramid(monkeypatch, tiers=2, size=6)
    start = dt.date(2026, 11, 2)
    seed = [start - dt.timedelta(days=i) for i in range(1, 8)]
    week = [start + dt.timedelta(days=i) for i in range(7)]          # ends on Sunday Nov 8
    rows = make_rows(12, seed, lambda i, d: 1 - i / 20) + make_rows(12, week, lambda i, d: i / 20)
    s = league.run(rows, {})["seasons"][0]
    assert not s["complete"] and not s["moves"] and not s["playoffs"]   # Sunday may still be running
    rows += make_rows(12, [start + dt.timedelta(days=7)], lambda i, d: 0.5)   # Monday data arrives
    s = league.run(rows, {})["seasons"][0]
    assert s["complete"] and s["moves"]


def test_national_tie_goes_to_more_traffic():
    def row(e, avg, arr):
        return {"eva": e, "station": e.upper(), "avg": avg, "points": 3.0, "ranked": True, "arrivals": arr}
    season = {"id": "2026-KW45", "leagues": {"1": {"tables": [[row("small", 0.7, 80)]]},
                                             "2": {"tables": [[row("hub", 0.7, 900)]]}}}
    r = stats.week_ranks(season, {})
    assert r["hub"]["rank"] == 1 and r["small"]["rank"] == 2
