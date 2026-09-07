#!/usr/bin/env python3
"""Offline tests for the 7 Sep 2026 stale-club fixes - no network required.

Two bugs, both found while running the GW4 brief, both about a club code
that had gone stale without anything saying so:

  1. build_squad.load() read every club from the frozen 8 Aug 2026 snapshot,
     so a deadline-day mover (Konsa, AVL->ARS) was scored on his OLD club's
     fixture run. load() now reads the club live, and keeps the snapshot club
     as `team_prior` because prior-season lookups are still keyed by it.
     Those lookups are what this file guards: getting the live club right is
     worthless if it silently breaks the prior-season data it addresses.
  2. optimise_squad.py printed "GW1-{HORIZON}" for a window stamped GW4,
     training the operator to abort a run that was correct.

load() itself needs bootstrap-static, so it is not tested here - these cover
the two pure functions the fixes turn on.

Run:  python3 test_club_hygiene.py
"""
import importlib.util
import os
import sys

import scoring as s

HERE = os.path.dirname(os.path.abspath(__file__))
FAILS = []


def check(label, cond, detail=""):
    if cond:
        print(f"  PASS  {label}")
    else:
        print(f"  FAIL  {label}  {detail}")
        FAILS.append(label)


print("== scoring.dc_key: prior-season data keeps its prior-season club ==")
# dc_hit_rates.json is keyed on web_name|<8 Aug snapshot club> by
# build_dc_rates.py, because the per-match counts in it ARE a 2025/26
# record. Keying it on the live club would miss every mover and drop him
# from the empirical hit rate to the parametric fallback without a word.
mover = {"name": "Konsa", "team": "ARS", "team_prior": "AVL"}
stayer = {"name": "Gabriel", "team": "ARS", "team_prior": "ARS"}
check("mover keys on the PRIOR club, not the live one",
      s.dc_key(mover) == "Konsa|AVL", s.dc_key(mover))
check("non-mover is unaffected", s.dc_key(stayer) == "Gabriel|ARS")
check("row without team_prior falls back to team (build_dashboard.py's pool)",
      s.dc_key({"name": "Raya", "team": "ARS"}) == "Raya|ARS")
check("empty team_prior falls back too, rather than keying on ''",
      s.dc_key({"name": "Raya", "team": "ARS", "team_prior": ""}) == "Raya|ARS")

# The real regression: a mover must still find his row in dc_hit_rates.json.
rates = s._dc_rates()
if rates:
    check("Konsa|AVL is present in dc_hit_rates.json (the key dc_key builds)",
          s.dc_key(mover) in rates)
    check("Konsa|ARS is NOT - which is what the old key would have looked up",
          "Konsa|ARS" not in rates)
else:
    print("  SKIP  dc_hit_rates.json not present - run build_dc_rates.py")

print("\n== fixture_adjust.window_label: the start GW is read, not assumed ==")
_spec = importlib.util.spec_from_file_location(
    "fa", os.path.join(HERE, "fixture_adjust.py"))
fa = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fa)

_real_active = fa.active_window
try:
    fa.active_window = lambda: ({}, "stub", {"generated_for_gw": 4, "horizon": 4})
    check("a window stamped GW4 with horizon 4 reads GW4-7",
          fa.window_label() == "GW4-7", fa.window_label())
    check("window_gws returns the stamp, not the module constant",
          fa.window_gws() == (4, 4), str(fa.window_gws()))

    fa.active_window = lambda: ({}, "stub", {"generated_for_gw": 1, "horizon": 4})
    check("GW1 still reads GW1-4 (the old hardcoded label, when true)",
          fa.window_label() == "GW1-4", fa.window_label())

    fa.active_window = lambda: ({}, "stub", {"generated_for_gw": 12, "horizon": 6})
    check("horizon comes from the stamp too, not fa.HORIZON",
          fa.window_label() == "GW12-17", fa.window_label())

    fa.active_window = lambda: ({}, "stub", None)
    check("no stamp -> says so rather than inventing a start gameweek",
          fa.window_label().startswith("GW?-")
          and "fixture_window.json" in fa.window_label(),
          fa.window_label())
finally:
    fa.active_window = _real_active

check("the committed fixture_window.json still parses",
      fa.window_gws()[0] is not None, "no stamp found")

print("\n" + ("ALL TESTS PASSED" if not FAILS else f"{len(FAILS)} FAILURE(S): {FAILS}"))
sys.exit(1 if FAILS else 0)
