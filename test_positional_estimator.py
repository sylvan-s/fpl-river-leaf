#!/usr/bin/env python3
"""Offline tests for the TEST `positional` estimator (17 Nov 2026).

build_squad._apply_positional() picks a shrinkage target per position, from
the by-position GW10 backtest (TEAM_CHANGE_LOG.md proposal 5):
  DEF  xg90/xa90/xgi90 -> team x position mean; xgc90 -> own-last-season
       blend; cbit90 -> 2025/26 prior untouched
  MID  sparse (< 2 current 90s) -> team x position; regulars -> own blend
  FWD / GKP -> own blend (same as `shrunk`)
Synthetic rows only - no network, no pulp.

Run:  python3 test_positional_estimator.py
"""
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


import build_squad as bs  # noqa: E402
import scoring  # noqa: E402

METRICS = tuple(scoring.PRIORS_DISPERSION)
K = {m: 10.0 for m in METRICS}


def row(name, pos, team, prior, cur, n90):
    r = dict(name=name, pos=pos, team=team)
    r.update({m: prior for m in METRICS})
    c = {m: cur for m in METRICS}
    c["n90"] = n90
    r["_cur"] = c
    return r


def build():
    return [
        # Two data-rich ARS defenders set the ARS DEF baseline: mean live 0.20
        row("DefA", "DEF", "ARS", prior=0.05, cur=0.10, n90=9.0),
        row("DefB", "DEF", "ARS", prior=0.05, cur=0.30, n90=9.0),
        # A thin-sample LIV defender: no LIV DEF baseline -> position-wide mean
        row("DefC", "DEF", "LIV", prior=0.40, cur=0.00, n90=1.0),
        # MID baseline at MUN: one regular, live 0.50
        row("MidReg", "MID", "MUN", prior=0.30, cur=0.50, n90=9.0),
        row("MidSparse", "MID", "MUN", prior=0.10, cur=0.90, n90=1.0),
        row("Fwd", "FWD", "LEE", prior=0.40, cur=0.60, n90=9.0),
        row("Gk", "GKP", "ARS", prior=1.0, cur=2.0, n90=9.0),
    ]


rows = build()
counts = bs._apply_positional(rows, K)
by = {r["name"]: r for r in rows}

print("== popped and tagged ==")
check("every row has _cur popped", all("_cur" not in r for r in rows))
check("every row tagged with pos_method", all("pos_method" in r for r in rows))
check("counts total = rows", sum(counts.values()) == len(rows), counts)

print("\n== DEF ==")
# DefA xg90: team target (ARS DEF mean 0.20), n90 9, k 10 -> (9*0.10 + 10*0.20)/19
exp = (9 * 0.10 + 10 * 0.20) / 19
check("DEF xg90 shrinks to the team x position mean, not own last season",
      abs(by["DefA"]["xg90"] - exp) < 1e-9, by["DefA"]["xg90"])
check("DEF xa90 and xgi90 use the same team target",
      abs(by["DefA"]["xa90"] - exp) < 1e-9 and abs(by["DefA"]["xgi90"] - exp) < 1e-9)
own = scoring.shrink_rate(0.10, 9.0, 0.05, 10.0)
check("DEF xgc90 stays on the own-last-season blend", abs(by["DefA"]["xgc90"] - own) < 1e-9)
check("DEF cbit90 stays on the 2025/26 prior, live data ignored", by["DefA"]["cbit90"] == 0.05)
# DefC: LIV has no DEF with >=5 n90 -> position-wide DEF mean = 0.20 too
exp_c = (1.0 * 0.0 + 10 * 0.20) / 11
check("no team baseline -> falls back to the position-wide mean",
      abs(by["DefC"]["xg90"] - exp_c) < 1e-9, by["DefC"]["xg90"])

print("\n== MID ==")
check("regular MID uses own-last-season blend on every metric",
      all(abs(by["MidReg"][m] - scoring.shrink_rate(0.50, 9.0, 0.30, 10.0)) < 1e-9 for m in METRICS))
check("regular MID tagged 'MID regular own'", by["MidReg"]["pos_method"] == "MID regular own")
exp_s = (1.0 * 0.90 + 10 * 0.50) / 11
check("sparse MID shrinks to the team x position mean",
      abs(by["MidSparse"]["xg90"] - exp_s) < 1e-9, by["MidSparse"]["xg90"])
check("sparse MID tagged 'MID sparse team'", by["MidSparse"]["pos_method"] == "MID sparse team")

print("\n== FWD / GKP unchanged from shrunk ==")
check("FWD = own-last-season blend",
      abs(by["Fwd"]["xg90"] - scoring.shrink_rate(0.60, 9.0, 0.40, 10.0)) < 1e-9)
check("GKP = own-last-season blend",
      abs(by["Gk"]["sv90"] - scoring.shrink_rate(2.0, 9.0, 1.0, 10.0)) < 1e-9)

print("\n== no live data ==")
r = [row("Nobody", "DEF", "ARS", prior=0.07, cur=0.0, n90=0.0)]
bs._apply_positional(r, K)
check("n90 = 0 keeps the prior (shrink_rate's no-data branch)", r[0]["xg90"] == 0.07, r[0]["xg90"])

print("\n== wiring ==")
check("'positional' is a valid estimator", "positional" in bs.ESTIMATOR_CHOICES)
check("weekly default is NOT positional", bs.ESTIMATOR_DEFAULT != "positional")

print(f"\n{'ALL PASS' if not FAILS else f'{len(FAILS)} FAILED'}")
sys.exit(1 if FAILS else 0)
