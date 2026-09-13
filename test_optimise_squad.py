#!/usr/bin/env python3
"""Offline tests for optimise_squad.py — no network required.

Covers _sell_price() (the FPL half-profit-on-a-rise rule) and its wiring
into optimise_transfers()'s budget constraint. squad_state.load() reads the
real squad.json at import time (local disk only, no network), so this
imports fine offline; the integration test below builds its own fully
synthetic 15-man pool rather than depending on the live squad's shape.

Run:  python3 test_optimise_squad.py   (needs the `pulp` package — it lives
in the base conda env on this Mac, not the fpl-mcp env test_fpl_mcp.py uses)
"""
import optimise_squad as opt

FAILS = []


def check(label, cond, detail=""):
    if cond:
        print(f"  PASS  {label}")
    else:
        print(f"  FAIL  {label}  {detail}")
        FAILS.append(label)


print("== _sell_price ==")
check("a fall passes through in full", opt._sell_price(5.0, 4.8) == 4.8)
check("flat price sells at cost", opt._sell_price(5.0, 5.0) == 5.0)
check("even rise: half banked exactly (5.0->5.4, +0.4 -> sells 5.2)",
      opt._sell_price(5.0, 5.4) == 5.2)
check("odd rise: half rounds DOWN (5.0->5.3, +0.3 -> sells 5.1, not 5.15)",
      opt._sell_price(5.0, 5.3) == 5.1)
check("float-drift guard: 5.5->5.7 (raw float diff is 0.19999999999999973)",
      opt._sell_price(5.5, 5.7) == 5.6)
check("bigger rise: 4.0->4.9, +0.9 -> floor(9/2)=4 tenths -> sells 4.4",
      opt._sell_price(4.0, 4.9) == 4.4)
check("a bought_for above current price never returns MORE than current",
      opt._sell_price(6.0, 5.0) == 5.0)


print("\n== optimise_transfers: sell price feeds the budget constraint ==")


def _row(name, pos, team, price, score, stp=0.95, ok=True):
    return {"name": name, "pos": pos, "team": team, "price": price,
            "score": score, "stp": stp, "ok": ok}


# A fully synthetic, legal 15-man squad (2 GKP / 5 DEF / 5 MID / 3 FWD,
# every player on a distinct club so MAX_CLUB=3 can never bind and the test
# is purely about the budget constraint). XI is 1-4-4-2 (11 starters),
# matching FORMATION's allowed ranges for every position.
OWNED = [
    _row("G1", "GKP", "T1", 4.5, 3.0),
    _row("G2", "GKP", "T2", 4.0, 2.5),
    _row("D1", "DEF", "T3", 4.5, 3.5),
    _row("D2", "DEF", "T4", 4.5, 3.4),
    _row("D3", "DEF", "T5", 4.0, 3.3),
    _row("D4", "DEF", "T6", 4.0, 3.2),
    _row("D5", "DEF", "T7", 4.0, 1.9),
    _row("M1", "MID", "T8", 6.0, 4.5),
    _row("M2", "MID", "T9", 6.0, 4.4),
    _row("M3", "MID", "T10", 5.5, 4.3),
    _row("M4", "MID", "T11", 5.5, 4.2),
    _row("M5", "MID", "T12", 4.5, 1.5),
    # F1 is the RISER: bought at 5.0, now worth 5.4 (+0.4m). True sell
    # proceeds are 5.2 (half the rise, rounded down) — not the 5.4 the old
    # code (pre-fix) would have credited.
    _row("F1", "FWD", "T13", 5.4, 4.0),
    _row("F2", "FWD", "T14", 5.0, 3.5),
    _row("F3", "FWD", "T15", 4.5, 1.0),
]
OWNED_NAMES = {r["name"] for r in OWNED}

# The only transfer candidate in the pool: a better FWD than F1, priced so
# that whether the swap is affordable hinges EXACTLY on which sell price F1
# is credited at.
#   real sell proceeds  5.2  -> 5.3 is NOT affordable (bank 0)         -> HOLD
#   old-bug sell price  5.4  -> 5.3 WOULD have been affordable          -> BUY
CANDIDATE = _row("RiserTarget", "FWD", "T16", 5.3, 4.5)
POOL = OWNED + [CANDIDATE]

BANK = 0.0


def _swapped_in(res):
    xi, bench, hits = res
    return {r["name"] for r in xi + bench} - OWNED_NAMES


# Correct bought_for: F1 really did rise from 5.0 to 5.4.
bf_real = {r["name"]: r["price"] for r in OWNED}
bf_real["F1"] = 5.0

res_real = opt.optimise_transfers(POOL, OWNED_NAMES, BANK, 1, allow_haaland=True,
                                   max_att_per_club=None, bought_for=bf_real)
check("feasible squad returned (real sell price)", res_real is not None)
if res_real:
    check("with the REAL sell price (5.2), the 5.3 upgrade is unaffordable -> HOLD",
          "RiserTarget" not in _swapped_in(res_real),
          f"bought in: {_swapped_in(res_real)}")

# Same scenario, but bought_for says F1 has NOT moved (bought_for == current
# price) — this is what every owned player looked like under the pre-fix
# code, which always used current price as sell proceeds. Same pool, same
# bank, same candidate: only the sell-price input changes, and it should
# flip the answer, proving the constraint is actually driven by bought_for
# rather than being coincidentally right either way.
bf_flat = {r["name"]: r["price"] for r in OWNED}  # F1: bought_for == 5.4
res_flat = opt.optimise_transfers(POOL, OWNED_NAMES, BANK, 1, allow_haaland=True,
                                   max_att_per_club=None, bought_for=bf_flat)
check("feasible squad returned (flat/no-rise bought_for)", res_flat is not None)
if res_flat:
    check("if F1 hadn't actually risen, full current price WOULD cover the "
          "5.3 upgrade -> BUY (proves the outcome genuinely depends on "
          "bought_for, not a fluke)",
          "RiserTarget" in _swapped_in(res_flat),
          f"bought in: {_swapped_in(res_flat)}")

# A kept (non-transferred) player's own bought_for must never matter — the
# sell-price/current-price choice cancels out algebraically for anyone who
# stays. Regression-proofs that _coef()'s branch on idx_owned_set doesn't
# accidentally constrain players who were never going to move.
bf_missing = {}  # no entries at all -> every owned player falls back to
                  # "current price" (assumed flat) per the documented default
res_default = opt.optimise_transfers(POOL, OWNED_NAMES, BANK, 0, allow_haaland=True,
                                      max_att_per_club=None, bought_for=bf_missing)
check("0-transfer hold is feasible even with an empty bought_for map "
      "(missing entries fall back to current price, not a crash)",
      res_default is not None)

print("\n" + ("ALL TESTS PASSED" if not FAILS else f"{len(FAILS)} FAILURE(S): {FAILS}"))
import sys
sys.exit(1 if FAILS else 0)
