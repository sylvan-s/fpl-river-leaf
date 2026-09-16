#!/usr/bin/env python3
"""Best predictor per position x metric, for the season BEING PLAYED.

    python3 season_predictors.py     # writes docs/data/season_predictors.json

WHY. The relationships page's panel 5 summarised historical_backtest_2025_26.json:
a frozen replay of the COMPLETED 2025/26 season. It never updated and named no
gameweek, so a reader could not tell it described last season, not this one.
This answers the same question on 2026/27 as it accrues, and stamps the
gameweeks it scored.

HOW, per metric family:

  per-90 rates (xg90, xa90, xgc90, sv90, cbit90, cbirt90) - exactly
      build_prediction_tracker.walk_forward(), run once per position with the
      INPUT restricted to that position (historical_backtest_2025_26.
      filter_by_position - exact, since walk_forward already derives k per
      position). Prior = 2025/26. CBIT/CBIRT now have a real prior: defensive
      contributions existed in 2025/26, unlike the 2024/25 archive the frozen
      backtest had to use.

  start rate - the definition SELECTION uses since 16 Sep 2026 (roadmap A0.2),
      not the tracker's: starts per TEAM MATCH (an unused-sub match is a
      non-start), prior = build_squad's 2025/26 last-16 rate, k from
      scoring.estimate_k_start. Scored walk-forward on every player in the
      900-minute pool still in the league, whether or not he appeared.

Winner = lowest mean per-gameweek RMSE over the scored gameweeks (GW2 onward;
GW1 has no live history to predict from). Early in the season these rest on
very few gameweeks: the JSON carries the count and the margin to the runner-up
so the page can say so.

DATA. Live API first (bootstrap-static, event/{gw}/live, fixtures). The local
SQLite cache is a fallback only - it is warmed weekly and on 16 Sep 2026 sat
one gameweek behind the live season.
"""
import importlib.util
import json
import math
import os
import statistics as st
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
OUT = os.path.join(HERE, "docs", "data", "season_predictors.json")

import build_prediction_tracker as bpt  # noqa: E402
import scoring  # noqa: E402

POSITIONS = ("GKP", "DEF", "MID", "FWD")
RATE_METRICS = {m["key"]: m["positions"] for m in bpt.METRICS + bpt.DC_METRICS}
NAMES = ("raw", "prior", "shrunk")


def _load(name, filename):
    spec = importlib.util.spec_from_file_location(name, os.path.join(HERE, filename))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def season_data():
    """(boot, cache, finished, source). Live API unless unreachable; then the
    SQLite cache. Raises if neither has a finished gameweek."""
    try:
        boot = bpt._bootstrap()
        finished = sorted(e["id"] for e in boot["events"] if e.get("finished"))
        cache = {str(gw): bpt._fetch_live(gw) for gw in finished}
        return boot, cache, finished, "live API"
    except Exception as exc:
        cache, finished = bpt._cache_from_sqlite()
        if not cache:
            raise RuntimeError(f"live API failed ({exc}) and no SQLite cache") from exc
        return bpt._boot_from_priors_snapshot(), cache, finished, f"SQLite cache (live API failed: {exc})"


def team_games_by_gw(boot):
    """{gw: {team_short: fixtures that gameweek}} from /fixtures/, finished only."""
    codes = {t["id"]: t["short_name"] for t in boot.get("teams", [])}
    out = defaultdict(lambda: defaultdict(int))
    for fx in bpt._http_get("https://fantasy.premierleague.com/api/fixtures/"):
        if fx.get("finished") and fx.get("event"):
            for side in ("team_h", "team_a"):
                if codes.get(fx.get(side)):
                    out[fx["event"]][codes[fx[side]]] += 1
    return out


def rate_results(boot, cache, finished, baselines):
    """{pos: {metric: {"raw": [...per-GW RMSE], "prior": [...], "shrunk": [...], "gws": [...]}}}"""
    hb = _load("hb", "historical_backtest_2025_26.py")
    out = {}
    for pos in POSITIONS:
        fboot, fcache = hb.filter_by_position(boot, cache, {pos})
        weeks, _cum = bpt.walk_forward(fboot, fcache, finished, baselines)
        per = {}
        for metric, positions in RATE_METRICS.items():
            if pos not in positions:
                continue
            t = {"raw": [], "prior": [], "shrunk": [], "gws": [], "n": []}
            for gw in finished:
                w = (weeks.get(gw) or weeks.get(str(gw)) or {}).get(metric) or {}
                vals = (w.get("rmse_raw"), w.get("rmse_base"), w.get("rmse_shrunk"))
                if None in vals or not w.get("n"):
                    continue
                for name, v in zip(NAMES, vals):
                    t[name].append(v)
                t["gws"].append(gw)
                t["n"].append(w["n"])
            per[metric] = t
        out[pos] = per
    return out


def stp_results(boot, cache, finished):
    """Start rate on selection's definition, walk-forward. Same shape as rate_results."""
    bs = _load("bs_sp", "build_squad.py")
    snap = json.load(open(bs.SNAP, encoding="utf-8"))
    teams = {int(k): v for k, v in snap["teams"].items()}
    last16 = bs._load_last16()
    live = {str(e["id"]): e for e in boot.get("elements", [])}
    codes = {t["id"]: t["short_name"] for t in boot.get("teams", [])}
    games = team_games_by_gw(boot)
    players = {}
    for pid, p in snap["players"].items():
        if (p.get("minutes") or 0) < bs.MIN_MINUTES or pid not in live:
            continue
        if live[pid].get("status") in ("u", "n"):       # left the league / loaned out
            continue
        hit = last16.get((p["web_name"], teams.get(p.get("team"))))
        prior = hit[0] / hit[1] if hit else (p.get("starts") or 0) / 38
        players[pid] = (prior, bs.POS[p["element_type"]], codes.get(live[pid].get("team")))
    out = {pos: {"stp": {"raw": [], "prior": [], "shrunk": [], "gws": [], "n": [], "k": []}}
           for pos in POSITIONS}
    for gi, gw in enumerate(finished):
        if gi == 0:
            continue
        hist = finished[:gi]
        state = {}
        for pid, (prior, pos, team) in players.items():
            n = sum(games[h].get(team, 0) for h in hist)
            played_now = games[gw].get(team, 0)
            if not n or not played_now:                  # no history yet, or a blank now
                continue
            starts = sum(1 for h in hist if ((cache.get(str(h)) or {}).get(pid) or {}).get("starts"))
            state[pid] = (min(1.0, starts / n), n, prior, pos)
        for pos in POSITIONS:
            rows = [(pid, v) for pid, v in state.items() if v[3] == pos]
            if not rows:
                continue
            k, _note = scoring.estimate_k_start([(r, n, pr) for _, (r, n, pr, _) in rows])
            err = {name: [] for name in NAMES}
            for pid, (raw, n, prior, _) in rows:
                actual = 1.0 if ((cache.get(str(gw)) or {}).get(pid) or {}).get("starts") else 0.0
                shrunk = (n * raw + k * prior) / (n + k)
                for name, v in zip(NAMES, (raw, prior, shrunk)):
                    err[name].append((v - actual) ** 2)
            t = out[pos]["stp"]
            for name in NAMES:
                t[name].append(math.sqrt(st.mean(err[name])))
            t["gws"].append(gw)
            t["n"].append(len(rows))
            t["k"].append(round(k, 2))
    return out


def summarise(t):
    """Winner by mean per-GW RMSE; margin = runner-up's mean over the winner's, minus 1."""
    if not t["gws"]:
        return None
    means = {name: st.mean(t[name]) for name in NAMES}
    rank = {"shrunk": 0, "prior": 1, "raw": 2}
    order = sorted(NAMES, key=lambda nm: (means[nm], rank[nm]))
    best, second = order[0], order[1]
    margin = means[second] / means[best] - 1 if means[best] > 0 else 0.0
    return {"best": best, "runner_up": second, "margin": round(margin, 4),
            "mean_rmse": {nm: round(means[nm], 4) for nm in NAMES},
            "scored_gws": t["gws"], "n_players": max(t["n"]) if t["n"] else 0,
            **({"k": t["k"]} if "k" in t else {})}


def build():
    boot, cache, finished, source = season_data()
    if len(finished) < 2:
        payload = {"season": "2026-27", "through_gw": finished[-1] if finished else None,
                   "scored_gws": [], "source": source, "cells": {},
                   "note": "fewer than two finished gameweeks - nothing to score yet"}
    else:
        baselines = bpt.build_baselines()
        rates = rate_results(boot, cache, finished, baselines)
        stp = stp_results(boot, cache, finished)
        cells = {}
        for pos in POSITIONS:
            cells[pos] = {m: summarise(t) for m, t in rates[pos].items()}
            cells[pos]["stp"] = summarise(stp[pos]["stp"])
        scored = sorted({gw for pos in cells.values() for c in pos.values() if c
                         for gw in c["scored_gws"]})
        payload = {"season": "2026-27", "prior_season": "2025-26",
                   "through_gw": finished[-1], "scored_gws": scored, "source": source,
                   "cells": cells,
                   "definitions": {
                       "rates": "build_prediction_tracker.walk_forward, per position; 60+ minute appearances scored",
                       "stp": "starts per team match vs build_squad last-16 prior, k = scoring.estimate_k_start (selection's definition since 16 Sep 2026)"}}
    import datetime as dt
    payload["updated_utc"] = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=1)
    return payload


if __name__ == "__main__":
    p = build()
    print(f"season_predictors: through GW{p['through_gw']}, scored {p['scored_gws']}, source {p['source']}")
    for pos, row in p.get("cells", {}).items():
        print(f"  {pos}: " + ", ".join(f"{m} {c['best']} (+{c['margin']:.0%})" if c else f"{m} -"
                                      for m, c in row.items()))
