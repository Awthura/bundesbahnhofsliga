"""Independent audit of the whole league history. Returns a list of violations (empty = all good).

It re-derives every number and every league change from the daily data and the rules, and compares
them with what the engine produced. scripts/build_site.py refuses to publish if anything is off.
"""
from __future__ import annotations

import datetime as dt
import math

from . import config, league


def audit(res: dict, rows: list[dict], states: dict[str, str]) -> list[str]:
    errors: list[str] = []
    err = errors.append
    data: league.Data = res["data"]
    defs = res["leagues"]
    tier = {l: d["tier"] for l, d in defs.items()}
    name = lambda e: f"{data.names.get(e, e)} ({e})"   # noqa: E731

    def region_league(e):
        st = config.STATE_OVERRIDES.get(e) or states.get(e)
        return f"RL-{config.region_of(st) or config.DEFAULT_REGION}"

    # A. daily points follow from the arrival counts
    for r in rows:
        a, p = int(r["arrivals"]), int(r["punctual"])
        c = int(r.get("canceled") or 0)
        plays = r["plays"] in (True, "True")
        if not (0 <= p <= a and 0 <= c <= a - p):
            err(f"{r['day']} {name(r['eva'])}: impossible counts arrivals={a} punctual={p} canceled={c}")
        if a and abs(float(r["points"]) - round(p / a, config.POINTS_DECIMALS)) > 1e-9:
            err(f"{r['day']} {name(r['eva'])}: points {r['points']} != {p}/{a}")
        if plays != (a >= config.MIN_ARRIVALS):
            err(f"{r['day']} {name(r['eva'])}: plays={plays} but arrivals={a}")

    prev = None
    for s in res["seasons"]:
        sid = s["id"]
        week = dt.date.fromisoformat(s["start"])
        days = [dt.date.fromisoformat(d) for d in s["matchdays"]]
        where = {}
        for l, lg in s["leagues"].items():
            final = lg["tables"][-1]
            for r in final:
                if r["eva"] in where:
                    err(f"{sid}: {name(r['eva'])} is in {where[r['eva']]} and {l}")
                where[r["eva"]] = l
            # B. tables: recompute every matchday table from the daily data
            for k, t in enumerate(lg["tables"], 1):
                need = math.ceil(config.MIN_PLAYED_SHARE * k)
                for r in t:
                    pts = [data.by_day[d].get(r["eva"]) for d in days[:k]]
                    played = [p["points"] for p in pts if p and p["plays"]]
                    if r["played"] != len(played) or abs(r["points"] - round(sum(played), 2)) > 1e-9:
                        err(f"{sid} {l} matchday {k}: {name(r['eva'])} played/points mismatch")
                    exp_avg = round(round(sum(played), 2) / len(played), 3) if played else 0.0
                    if abs(r["avg"] - exp_avg) > 1e-9 or r["ranked"] != (len(played) >= need):
                        err(f"{sid} {l} matchday {k}: {name(r['eva'])} avg/ranked mismatch")
                keys = [(not r["ranked"], -r["avg"], -r["points"], r["station"]) for r in t]
                if keys != sorted(keys) or [r["rank"] for r in t] != list(range(1, len(t) + 1)):
                    err(f"{sid} {l} matchday {k}: table not sorted correctly")
            # sizes and regions
            if tier[l] <= config.NATIONAL_TIERS:
                size = config.league_size(tier[l])
                if len(final) > size:
                    err(f"{sid} {l}: {len(final)} stations, more than {size}")
                if len(final) < size and any(s["leagues"].get(r) for r in s["leagues"] if tier[r] > tier[l]):
                    err(f"{sid} {l}: only {len(final)} of {size} places filled although stations are below")
            else:
                for r in final:
                    if region_league(r["eva"]) != l:
                        err(f"{sid} {l}: {name(r['eva'])} belongs to {region_league(r['eva'])}")

        # C. membership, recomputed here: newcomers need >= MIN_ARRIVALS on every day of the window,
        #    last week's members on at least STAY_DAY_SHARE of the days (data-gap days ignored)
        window = data.window(week, config.MEMBERSHIP_WINDOW_DAYS)
        totals = sorted(sum(r["arrivals"] for r in data.by_day[d].values()) for d in window)
        median = totals[len(totals) // 2] if totals else 0
        window = [d for d in window if sum(r["arrivals"] for r in data.by_day[d].values()) >= config.DATA_GAP_SHARE * median]
        before_members = {r["eva"] for lg in prev["leagues"].values() for r in lg["tables"][-1]} if prev else set()
        mem = set()
        for e in {e for d in window for e in data.by_day[d]}:
            good = sum(1 for d in window if data.by_day[d].get(e, {}).get("plays"))
            share = config.STAY_DAY_SHARE if e in before_members else config.MIN_DAY_SHARE
            if window and good >= share * len(window):
                mem.add(e)
        if set(where) != mem:
            extra, missing = set(where) - mem, mem - set(where)
            err(f"{sid}: membership mismatch, extra {sorted(map(name, extra))[:5]}, missing {sorted(map(name, missing))[:5]}")

        # D. moves of this season follow the zones and playoffs
        if s["complete"]:
            check_moves(s, tier, data, err)

        # E. every change from last week is explained, and nobody jumps two tiers
        if prev is not None and prev["complete"]:
            before = {r["eva"]: l for l, lg in prev["leagues"].items() for r in lg["tables"][-1]}
            expect = dict(before)
            for m in prev["moves"]:
                if expect.get(m["eva"]) != m["from"]:
                    err(f"{prev['id']}: move of {name(m['eva'])} from {m['from']} but it was in {expect.get(m['eva'])}")
                expect[m["eva"]] = m["to"]
            for d in s["dropped"]:
                expect.pop(d["eva"], None)
            for f in s["fills"]:
                if expect.get(f["eva"]) != f["from"] or tier[f["to"]] != tier[f["from"]] - 1:
                    err(f"{sid}: bad gap fill {name(f['eva'])} {f['from']} -> {f['to']}")
                if f["reason"] == "next_best" and before.get(f["eva"]) != f["from"]:
                    err(f"{sid}: gap fill {name(f['eva'])} was not in {f['from']} last week")
                expect[f["eva"]] = f["to"]
            for e, l in where.items():
                if e in expect:
                    if expect[e] != l:
                        err(f"{sid}: {name(e)} is in {l}, expected {expect[e]} (unexplained change)")
                elif l != region_league(e):
                    err(f"{sid}: newcomer {name(e)} in {l}, not in its own Regionalbahnhofsliga")
                if e in before and abs(tier[l] - tier[before[e]]) > 1:
                    err(f"{sid}: {name(e)} jumped from {before[e]} to {l}")
        prev = s
    return errors


def check_moves(s, tier, data, err):
    sid = s["id"]
    finals = {l: [r["eva"] for r in lg["tables"][-1]] for l, lg in s["leagues"].items()}
    tables = {l: lg["tables"][-1] for l, lg in s["leagues"].items()}
    sunday = dt.date.fromisoformat(s["end"])
    moves = {(m["eva"], m["from"], m["to"]) for m in s["moves"]}
    po = {(p["upper"], p["lower"]): p for p in s["playoffs"]}
    expected = set()
    nat = [l for l in finals if tier[l] <= config.NATIONAL_TIERS]
    nat.sort(key=lambda l: tier[l])
    for a, b in zip(nat, nat[1:]):
        direct, has_po = league.zones(len(finals[a]), len(finals[b]))
        downs, ups = finals[a][-direct:] if direct else [], finals[b][:direct]
        if has_po and direct:
            ue, le = finals[a][-direct - 1], finals[b][direct]
            p = po.get((a, b))
            w = league.playoff_winner(data, sunday, ue, le)
            if not p or p["upper_eva"] != ue or p["lower_eva"] != le or p["winner"] != w:
                err(f"{sid}: playoff {a}/{b} wrong (expected {ue} vs {le}, winner {w})")
            if w == le:
                downs, ups = downs + [ue], ups + [le]
        expected |= {(e, a, b) for e in downs} | {(e, b, a) for e in ups}
    regs = [l for l in finals if tier[l] > config.NATIONAL_TIERS]
    if nat and regs:
        bottom = nat[-1]
        champs = sorted((tables[r][0] for r in regs if tables[r][0]["ranked"]),
                        key=lambda r: (-r["avg"], -r["points"], r["station"]))
        n = min(config.RL_RELEGATED, config.RL_PROMOTED, len(champs), len(finals[bottom]) // 3)
        reg_of = {e: l for l in regs for e in finals[l]}
        for e in finals[bottom][-n:] if n else []:
            region = next((x["to"] for x in s["moves"] if x["eva"] == e), None)
            expected.add((e, bottom, region))
        expected |= {(c["eva"], reg_of[c["eva"]], bottom) for c in champs[:n]}
    if moves != expected:
        err(f"{sid}: moves differ from the rules: unexpected {sorted(moves - expected)[:4]}, missing {sorted(expected - moves)[:4]}")
    ups = sum(1 for m in s["moves"] if tier[m["to"]] < tier[m["from"]])
    downs = sum(1 for m in s["moves"] if tier[m["to"]] > tier[m["from"]])
    if ups != downs:
        err(f"{sid}: {ups} promotions but {downs} relegations")
