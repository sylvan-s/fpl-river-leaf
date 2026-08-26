#!/usr/bin/env python3
"""Offline tests for scoring.py's actual_points_breakdown() - no network
required. expected_points()/expected_points_scaled_breakdown() have been
exercised indirectly for months via build_squad.py/fixture_adjust.py's own
usage and the squad page's route-reconciliation assert; this file covers the
newer actual-results side specifically (added 26 Aug 2026 for the squad
page's Expected/Actual toggle).

Run:  python3 test_scoring.py
"""
import sys

import scoring as s

FAILS = []


def check(label, cond, detail=""):
    if cond:
        print(f"  PASS  {label}")
    else:
        print(f"  FAIL  {label}  {detail}")
        FAILS.append(label)


print("== actual_points_breakdown: reconciles against a REAL result ==")
# GW1 2026/27, a real player_gw-shaped row (goalkeeper, clean sheet, one
# save) - total_points=6 is the actual FPL-awarded total for this match.
raya_gw1 = {
    "minutes": 90, "goals_scored": 0, "assists": 0, "clean_sheets": 1,
    "goals_conceded": 0, "saves": 1, "bonus": 0,
    "clearances_blocks_interceptions": 1, "tackles": 0, "recoveries": 8,
    "yellow_cards": 0, "red_cards": 0, "own_goals": 0, "penalties_missed": 0,
}
pos_, ded_ = s.actual_points_breakdown(raya_gw1, "GKP")
check("appearance: 90 mins -> 2", pos_["appearance"] == 2.0)
check("clean sheet: GKP CS=4", pos_["clean_sheets"] == 4.0)
check("saves: 1 save, floor(1/3)=0", pos_["saves"] == 0.0)
check("GKP defensive contribution below the 99 threshold -> 0",
      pos_["defensive_contribution"] == 0.0)
check("no deductions this match", sum(ded_.values()) == 0.0, str(ded_))
check("sum matches the real total_points (6)",
      sum(pos_.values()) + sum(ded_.values()) == 6.0,
      f"{sum(pos_.values()) + sum(ded_.values())}")

print("\n== defender: goal involvement, clean sheet, DC threshold, a card ==")
def_row = {
    "minutes": 90, "goals_scored": 0, "assists": 1, "clean_sheets": 1,
    "goals_conceded": 1, "saves": 0, "bonus": 2,
    "clearances_blocks_interceptions": 6, "tackles": 5, "recoveries": 3,
    "yellow_cards": 1, "red_cards": 0, "own_goals": 0, "penalties_missed": 0,
}
pos_, ded_ = s.actual_points_breakdown(def_row, "DEF")
check("assist: ASSIST=3", pos_["goal_involvement"] == 3.0)
check("clean sheet: DEF CS=4", pos_["clean_sheets"] == 4.0)
check("DC: CBI+tackles=11 clears the 10 DEF threshold -> 2pts (discrete, not a probability)",
      pos_["defensive_contribution"] == 2.0)
check("DC uses CBI+tackles for DEF, NOT +recoveries (would be 14, still clears here - "
      "use a case where it matters instead)", True)  # see next block for the recoveries case
check("bonus carried through as-is", pos_["bonus"] == 2.0)
check("1 goal conceded (below the 2-per-minus threshold) costs nothing yet",
      ded_["goals_conceded"] == 0.0)
check("one yellow card costs exactly YELLOW_CARD", ded_["yellow_cards"] == s.YELLOW_CARD == -1)
check("total reconciles", sum(pos_.values()) + sum(ded_.values())
      == 2.0 + 3.0 + 4.0 + 2.0 + 0.0 + 2.0 - 1.0)

print("\n== DC metric differs by position: DEF excludes recoveries, others include it ==")
# 6 CBI + 3 tackles = 9, clears nothing for DEF (threshold 10) on CBI+tackles alone,
# but 9 + 5 recoveries = 14 clears the MID/FWD threshold (12) once recoveries count.
row = {"minutes": 90, "clearances_blocks_interceptions": 6, "tackles": 3, "recoveries": 5,
       "goals_scored": 0, "assists": 0, "clean_sheets": 0, "goals_conceded": 0, "saves": 0,
       "bonus": 0, "yellow_cards": 0, "red_cards": 0, "own_goals": 0, "penalties_missed": 0}
pdef, _ = s.actual_points_breakdown(row, "DEF")
pmid, _ = s.actual_points_breakdown(row, "MID")
check("DEF: CBI+tackles=9 misses the 10-line (recoveries not counted for DEF)",
      pdef["defensive_contribution"] == 0.0)
check("MID: CBI+tackles+recoveries=14 clears the 12-line", pmid["defensive_contribution"] == 2.0)

print("\n== two-per-minus goals-conceded deduction, and MID/FWD are exempt ==")
gc_row = {"minutes": 90, "goals_conceded": 3, "goals_scored": 0, "assists": 0,
          "clean_sheets": 0, "saves": 0, "bonus": 0,
          "clearances_blocks_interceptions": 0, "tackles": 0, "recoveries": 0,
          "yellow_cards": 0, "red_cards": 0, "own_goals": 0, "penalties_missed": 0}
_, ded_gkp = s.actual_points_breakdown(gc_row, "GKP")
_, ded_def = s.actual_points_breakdown(gc_row, "DEF")
_, ded_mid = s.actual_points_breakdown(gc_row, "MID")
_, ded_fwd = s.actual_points_breakdown(gc_row, "FWD")
check("GKP: floor(3/2)=1 conceded-goal deduction", ded_gkp["goals_conceded"] == -1.0)
check("DEF: same rule applies", ded_def["goals_conceded"] == -1.0)
check("MID exempt from the goals-conceded penalty", ded_mid["goals_conceded"] == 0.0)
check("FWD exempt from the goals-conceded penalty", ded_fwd["goals_conceded"] == 0.0)

print("\n== red card, own goal, penalty miss all apply their own constant ==")
bad_row = {"minutes": 90, "goals_scored": 0, "assists": 0, "clean_sheets": 0,
           "goals_conceded": 0, "saves": 0, "bonus": 0,
           "clearances_blocks_interceptions": 0, "tackles": 0, "recoveries": 0,
           "yellow_cards": 0, "red_cards": 1, "own_goals": 1, "penalties_missed": 1}
_, ded_bad = s.actual_points_breakdown(bad_row, "FWD")
check("red card", ded_bad["red_cards"] == s.RED_CARD == -3)
check("own goal", ded_bad["own_goals"] == s.OWN_GOAL == -2)
check("penalty miss", ded_bad["penalties_missed"] == s.PENALTY_MISS == -2)
check("all three stack", sum(ded_bad.values()) == -7.0)

print("\n== missing fields default to zero rather than raising ==")
try:
    pos_, ded_ = s.actual_points_breakdown({"minutes": 90}, "MID")
    check("no KeyError on a sparse row", True)
    check("unset counts read as zero", sum(pos_.values()) == 2.0  # appearance only
          and sum(ded_.values()) == 0.0)
except KeyError as e:
    check("no KeyError on a sparse row", False, str(e))

print("\n== every category present for every position (fixed six-key shape) ==")
for pos in ("GKP", "DEF", "MID", "FWD"):
    pos_, ded_ = s.actual_points_breakdown(raya_gw1, pos)
    check(f"{pos}: six positive keys",
          set(pos_) == {"appearance", "goal_involvement", "clean_sheets",
                        "defensive_contribution", "saves", "bonus"})
    check(f"{pos}: five deduction keys",
          set(ded_) == {"goals_conceded", "yellow_cards", "red_cards",
                        "own_goals", "penalties_missed"})

print("\n== expected_gc_penalty: un-netting helper for the deductions bar ==")
defr = {"pos": "DEF", "xgc90": 1.2}
gkr = {"pos": "GKP", "xgc90": 1.2}
midr = {"pos": "MID", "xgc90": 1.2}
check("DEF: matches the netted formula's own gc term",
      s.expected_gc_penalty(defr, 1.0) == -(1.2 * 1.0 / s.GC_PER_MINUS))
check("fixture scaling (def_x) is applied",
      s.expected_gc_penalty(defr, 2.0) == -2 * (1.2 * 1.0 / s.GC_PER_MINUS))
check("GKP also carries the penalty", s.expected_gc_penalty(gkr, 1.0) < 0)
check("MID/FWD exempt", s.expected_gc_penalty(midr, 1.0) == 0.0)
_breakdown = s.expected_points_scaled_breakdown(
    {**defr, "xg90": 0.1, "xa90": 0.1, "cbit90": 8, "cbirt90": 8, "sv90": 0,
     "name": "Test", "team": "TST"}, att_x=1.0, def_x=1.5, empirical=False)
_pen = s.expected_gc_penalty({**defr}, 1.5)
check("un-netting recovers a non-negative pure DC figure",
      _breakdown["defensive_contribution"] - _pen >= 0,
      f"dc={_breakdown['defensive_contribution']} pen={_pen}")

print("\n" + ("ALL TESTS PASSED" if not FAILS else f"{len(FAILS)} FAILURE(S): {FAILS}"))
sys.exit(1 if FAILS else 0)
