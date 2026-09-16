#!/usr/bin/env python3
"""Offline tests for start-rate shrinkage (roadmap A0.2 activation, 16 Sep 2026).

The frozen last-16 start rate was the worst of prior / raw / shrunk on
2026/27 GW2-4 (RMSE 0.492 vs 0.397 shrunk), so --stp-estimator shrunk blends
it with live starts per TEAM match. These cover the estimator itself, and
load() end to end with bootstrap-static and /fixtures/ stubbed from the
committed snapshot - no network.

Run:  python3 test_stp_shrinkage.py
"""
import contextlib
import importlib.util
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
FAILS = []


def check(label, cond, detail=""):
    if cond:
        print(f"  PASS  {label}")
    else:
        print(f"  FAIL  {label}  {detail}")
        FAILS.append(label)


import scoring  # noqa: E402

print("== scoring.shrink_start ==")
s, raw = scoring.shrink_start(2, 4, 0.9, 2.0)
check("blend: (4*0.5 + 2*0.9) / 6 = 0.633, raw 0.5", abs(s - 0.6333) < 1e-3 and raw == 0.5, (s, raw))
check("no team matches -> prior unchanged, raw None", scoring.shrink_start(3, 0, 0.8, 2.0) == (0.8, None))
check("no live starts -> prior unchanged", scoring.shrink_start(None, 4, 0.8, 2.0) == (0.8, None))
check("a deadline-day mover's starts over his new club's games cap at 1.0",
      scoring.shrink_start(5, 4, 0.5, 1.0)[1] == 1.0)
check("large k stays near the prior; k=1 leans on four matches",
      abs(scoring.shrink_start(0, 4, 1.0, 30.0)[0] - 30 / 34) < 1e-9
      and abs(scoring.shrink_start(0, 4, 1.0, 1.0)[0] - 0.2) < 1e-9)

print("\n== scoring.estimate_k_start ==")
k, note = scoring.estimate_k_start([(1.0, 4, 0.9)] * 5)
check("under MIN_START_POOL -> fallback", note == "fallback" and k == scoring.START_K_FALLBACK)
k, note = scoring.estimate_k_start([(1.0, 1, 0.5)] * 40)
check("one match each (GW2) -> fallback, n>=2 required", note == "fallback")
# prior exactly right on average: raw scatters only by binomial noise -> trust the prior
calm = []
for i in range(40):
    p = 0.5
    calm += [(0.5, 4, p), (0.5, 4, p)]
k, note = scoring.estimate_k_start(calm)
check("prior explains everything -> k clamped at the max (lean on prior)",
      k == scoring.START_K_MAX and note == "clamped", (k, note))
wild = [(1.0, 4, 0.1)] * 20 + [(0.0, 4, 0.9)] * 20
k, note = scoring.estimate_k_start(wild)
check("prior badly wrong -> k clamped at 1 (lean on live data)", k == 1.0 and note == "clamped", (k, note))
# residual +/-0.5 at n=4: E[r^2]=0.25, noise 0.25/4=0.0625, prior error 0.1875,
# k = 0.25/0.1875 = 1.33 - derived, not clamped
mid = [(1.0, 4, 0.5)] * 20 + [(0.0, 4, 0.5)] * 20
k, note = scoring.estimate_k_start(mid)
check("moderate prior error -> derived k = 1.33, note None",
      abs(k - 4 / 3) < 1e-9 and note is None, (k, note))


def _load_module(name, filename):
    spec = importlib.util.spec_from_file_location(name, os.path.join(HERE, filename))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


bs = _load_module("bs", "build_squad.py")
snap = json.load(open(bs.SNAP, encoding="utf-8"))
teams = {int(k): v for k, v in snap["teams"].items()}


def pid_of(name, team):
    return next(pid for pid, p in snap["players"].items()
                if p["web_name"] == name and teams.get(p["team"]) == team)


RICE, SAKA, TIMBER = pid_of("Rice", "ARS"), pid_of("Saka", "ARS"), pid_of("Gabriel", "ARS")


def run_load(starts, games, stp_estimator="shrunk", intel=False):
    """Everyone listed live on his snapshot club with 4 starts in 4 games
    unless `starts` says otherwise; /fixtures/ stubbed as `games`."""
    elements = {pid: {"id": int(pid), "status": "a", "news": "", "now_cost": p.get("now_cost"),
                      "starts": starts.get(pid, 4)} for pid, p in snap["players"].items()}
    clubs = {pid: teams.get(p.get("team"), "?") for pid, p in snap["players"].items()}
    real_fetch, real_games = bs._fetch_current_season, bs._fetch_team_games
    bs._fetch_current_season = lambda: elements
    bs._fetch_team_games = lambda: games
    bs._current_cache, bs._live_clubs_cache = elements, clubs
    err = io.StringIO()
    try:
        with contextlib.redirect_stderr(err):
            pool = bs.load(intel=intel, stp_estimator=stp_estimator)
    finally:
        bs._fetch_current_season, bs._fetch_team_games = real_fetch, real_games
        bs._current_cache = bs._live_clubs_cache = None
    return {r["name"]: r for r in pool if r["team"] == "ARS"}, err.getvalue()


four = {code: 4 for code in set(teams.values())}

print("\n== load(): default is unchanged ==")
by, err = run_load({RICE: 0}, four, stp_estimator="prior")
check("default/prior: stp is the last-16 prior, no stp_prior field, no STP lines",
      "stp_prior" not in by["Rice"] and "STP" not in err)
check("STP_ESTIMATOR_DEFAULT is still prior (flip is a separate, dated decision)",
      bs.STP_ESTIMATOR_DEFAULT == "prior")
try:
    bs.load(stp_estimator="vibes")
    check("bad stp_estimator is refused", False)
except ValueError:
    check("bad stp_estimator is refused", True)

print("\n== load(): shrunk moves stp toward live starts ==")
prior_by, _ = run_load({}, four, stp_estimator="prior")
by, err = run_load({RICE: 0, SAKA: 2}, four)
r = by["Rice"]
check("Rice: 0 starts in 4 -> stp falls below his prior, raw 0.0, n 4",
      r["stp"] < prior_by["Rice"]["stp"] and r["stp_raw"] == 0.0 and r["stp_n"] == 4, r.get("stp"))
check("stp_prior keeps the old value", abs(r["stp_prior"] - prior_by["Rice"]["stp"]) < 1e-12)
check("stp_src is marked +live", r["stp_src"].endswith("+live"), r["stp_src"])
check("Saka: 2 of 4 -> raw 0.5", by["Saka"]["stp_raw"] == 0.5)
check("xP is unchanged by start rate (A0.5 is not built)",
      abs(r["score"] - prior_by["Rice"]["score"]) < 1e-12)
check("STP SHRUNK line reports k per position", "STP SHRUNK" in err and "DEF" in err, err[-400:])
if prior_by["Rice"]["stp"] >= bs.GATE_XI > r["stp"]:
    check("a player pushed under the XI gate is named in 'now below it'",
          "now below it" in err and "Rice (ARS)" in err, err[-600:])

print("\n== load(): no team match counts -> prior kept, loudly ==")
by, err = run_load({RICE: 0}, {})
check("fixtures fetch failed: stp stays the prior", abs(by["Rice"]["stp"] - prior_by["Rice"]["stp"]) < 1e-12)
check("...and says so", "STP: shrunk requested but no team match counts" in err, err[-300:])

print("\n== load(): ROLE_INTEL `set stp` still wins over shrinkage ==")
gw = bs.ia._current_gw()
setrow = next((e for e in bs.ia.load_adjustments() if e["field"] == "stp" and e["op"] == "set"
               and e["team"] == "ARS"), None)
if setrow:
    by, _ = run_load({pid_of(setrow["player"], "ARS"): 0}, four, intel=True)
    row = by.get(setrow["player"])
    applied = row and any(e["field"] == "stp" for e in row.get("intel_applied", []))
    if applied:
        check(f"{setrow['player']}: fence `set stp {setrow['value']}` beats shrunk "
              f"(0 live starts)", abs(row["stp"] - setrow["value"]) < 1e-9 and row["stp_raw"] == 0.0,
              (row["stp"], row.get("stp_raw")))
    else:
        print(f"  SKIP  {setrow['player']}'s fence row is out of window for GW{gw}")
else:
    print("  SKIP  no ARS `set stp` row in ROLE_INTEL.md to test against")

print("\n" + ("ALL TESTS PASSED" if not FAILS else f"{len(FAILS)} FAILURE(S): {FAILS}"))
sys.exit(1 if FAILS else 0)
