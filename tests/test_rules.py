import datetime as dt

import duckdb

from bbl import config, ingest, league, points


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
    assert points.score_day(7, 7) == (1.0, True)
    assert points.score_day(7, 0) == (0.0, True)


def test_more_than_five_arrivals_needed_to_play():
    assert points.score_day(5, 5)[1] is False
    assert points.score_day(6, 5)[1] is True


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
    assert set(s) == {"a-1", "a-4"}           # first stop (no <ar>) and RE ignored
    assert s["a-1"]["delay_in_min"] == 4 and s["a-1"]["eva"] == "08010159"
    assert s["a-4"]["canceled"]


# --- league engine -----------------------------------------------------------

def make_rows(n_stations, days, score):
    out = []
    for d in days:
        for i in range(n_stations):
            out.append({"day": d, "eva": f"{i:03d}", "station": f"S{i:03d}", "points": score(i, d), "plays": True})
    return out


def test_weekly_promotion_relegation_and_playoff(monkeypatch):
    monkeypatch.setattr(config, "LEAGUES", [
        {"id": "1", "name": "A", "short": "A", "size": 6},
        {"id": "2", "name": "B", "short": "B", "size": 6}])
    start = dt.date(2026, 11, 2)
    seed = [start - dt.timedelta(days=i) for i in range(1, 8)]
    week1 = [start + dt.timedelta(days=i) for i in range(7)]
    week2 = [start + dt.timedelta(days=7 + i) for i in range(2)]
    # seeding: station i better than i+1. week 1: reversed, so the lowest become the best
    rows = make_rows(12, seed, lambda i, d: 1 - i / 20)
    rows += make_rows(12, week1 + week2, lambda i, d: i / 20)
    res = league.run(rows)
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


def test_leagues_of_18_last_takes_rest():
    split = league.split_leagues([str(i) for i in range(40)])
    assert [len(e) for _, e in split] == [18, 18, 4]


def test_ranking_by_average_and_min_played():
    data = league.Data([
        {"day": "2026-11-09", "eva": "a", "station": "A", "points": 0.9, "plays": True},
        {"day": "2026-11-10", "eva": "a", "station": "A", "points": 0.9, "plays": True},
        {"day": "2026-11-09", "eva": "b", "station": "B", "points": 0.5, "plays": True},
        {"day": "2026-11-10", "eva": "b", "station": "B", "points": 0.7, "plays": True},
        {"day": "2026-11-09", "eva": "c", "station": "C", "points": 1.0, "plays": True},
        {"day": "2026-11-10", "eva": "c", "station": "C", "points": 0.2, "plays": False},
    ])
    days = data.days + [dt.date(2026, 11, 11)]
    data.by_day[days[-1]] = {"a": {"points": 0.1, "plays": True}, "b": {"points": 0.9, "plays": True}}
    t = league.table(["a", "b", "c"], data, days, None)
    assert [r["eva"] for r in t] == ["b", "a", "c"]   # c played only 1 of 3: needs 2 to be ranked
    assert t[1]["points"] == 1.9 and t[1]["avg"] == round(1.9 / 3, 3)
    assert t[2]["form"] == [1.0, None, None]


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


def test_membership_needs_more_than_5_arrivals_every_day():
    start = dt.date(2026, 11, 9)
    rows = []
    for i in range(1, 15):
        d = start - dt.timedelta(days=i)
        rows.append({"day": d, "eva": "a", "station": "A", "points": 0.9, "plays": True})
        rows.append({"day": d, "eva": "b", "station": "B", "points": 0.9, "plays": i != 3})  # one thin day
    mem, _ = league.Data(rows).members(start)
    assert mem == {"a"}


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
