#!/usr/bin/env python3
"""Exact squad optimisation — integer linear programming over expected points.

WHY THIS EXISTS. build_squad.py is GREEDY: it fills each slot with the best
available player and hopes the budget works out. Greedy is provably suboptimal
here, because the choice at one slot changes what is affordable at every later
one. This solves the same problem exactly.

    pip install pulp          # bundled CBC solver, no other dependency

    python3 optimise_squad.py                  # best 15 from scratch (wildcard / rebuild)
    python3 optimise_squad.py --transfers 1    # best swap FROM the current squad  <-- weekly
    python3 optimise_squad.py --transfers 2 --hits
    python3 optimise_squad.py --haaland --gate 0.70
    python3 optimise_squad.py --fixtures               # score on xP_adj (GW1-4)
    python3 optimise_squad.py --fixtures --transfers 1

EXOGENOUS PREFERENCES. Two standing choices are applied as ILP constraints,
ON by default, each overridable per run - see "THE FORMULATION" below for
why constraints (not a hardcoded pool filter) is the right mechanism, and
"PRICE OF THE PREFERENCE" for why every one of them reports its own cost.

    python3 optimise_squad.py --haaland                      # relax: allow Haaland
    python3 optimise_squad.py --max-attackers-per-club 3      # relax: allow 3
    python3 optimise_squad.py --no-max-attackers-per-club     # disable: fall back
                                                                # to the blanket
                                                                # 3-per-club rule only

A request to RUN the optimiser (from Sylvan, or a scheduled skill) should
open with a dialogue stating the active defaults and asking whether to
proceed or clear/adjust one - see docs/agents/optimiser.md. This file only
implements the constraints; the dialogue is the calling agent's job.

ROLE_INTEL.md adjustments are ON BY DEFAULT since 13 Aug 2026 (see
build_squad.py USE_INTEL) - every run above already applies the `set stp` /
`mult` fence entries. This was flipped after finding the weekly brief's
documented command never passed --intel, so transferred/new-signing players
were scored on ROLE_INTEL-blind numbers in the actual weekly run, not just in
explicit comparisons. Pass --no-intel to see the raw, unadjusted numbers:

    python3 optimise_squad.py --no-intel                # ROLE_INTEL.md adjustments OFF
    python3 optimise_squad.py --no-intel --transfers 1
    python3 optimise_squad.py --compare-intel           # WITH vs WITHOUT, one run
    python3 optimise_squad.py --compare-intel --transfers 1

PLAYER PERFORMANCE ESTIMATOR (roadmap A0.2, revised 31 Aug 2026, extended with
`raw` 2 Sep 2026) - `--estimator {prior,raw,shrunk}`, default `prior`, unlike
intel above. Governs how xg90/xa90/xgi90/xgc90/cbit90/cbirt90/sv90 are
derived (NOT stp - see METHODOLOGY_ALTERNATIVES.md A0.2 "Phase 2" for why
start rate stays out of this):

    prior  - 2025/26 prior season only. No live fetch. The long-standing default.
    raw    - live 2026/27 per-90 rates only, no blending toward the prior at
             all. Gated per-player at scoring.MIN_N90_RAW - below that a raw
             rate is noise (see that constant's comment), so the prior is
             used for that player/metric instead.
    shrunk - Bayesian blend of the two, weighted by how much live evidence
             exists (heavy on the prior early, shifts toward raw as the
             season accrues minutes).

`raw` and `shrunk` both need live network for build_squad.load()'s
current-season fetch; both degrade to prior-only with a warning if
unreachable (e.g. this session's sandbox). `shrunk` is compare-only until
the GW3 sanity check looks sane, then flips to default-on before GW4:

    python3 optimise_squad.py --estimator raw --fixtures --transfers 1
    python3 optimise_squad.py --estimator shrunk --fixtures --transfers 1
    python3 optimise_squad.py --compare-estimators --fixtures --transfers 1   # prior vs raw vs shrunk, one run

(`--shrunk-priors` and `--compare-shrink` still work as legacy aliases for
`--estimator shrunk` and a prior-vs-shrunk-only compare.)

TWO MODES, AND THE WEEKLY ONE IS THE SECOND.

Rebuild mode answers "what is the best 15 for £100m?" - the wildcard question,
asked maybe three times a season. Transfer mode answers "given the squad I own,
£X in the bank and N free transfers, what is the best move?" - which is the
question every single week.

They are different problems. Rebuild has the whole budget free; transfer has
almost none, and the squad is a constraint rather than an output.

THE FORMULATION

  decision variables, per player i
      x_i = 1 if i is in the STARTING XI
      b_i = 1 if i is on the BENCH
      (x_i + b_i <= 1  - a player is in the XI, on the bench, or not owned)

  objective                MAXIMISE  sum( xP_i * x_i )
      Only the XI scores. The bench is a cost, not a benefit - which is exactly
      why the problem is interesting: every pound spent on fodder is a pound not
      spent on the XI. A naive "maximise over all 15" would buy a luxury bench.

  subject to
      budget      sum( price_i * (x_i + b_i) )  <= 100.0     all 15 are bought
      squad       sum( x_i + b_i )              == 15
      per pos     GKP 2 · DEF 5 · MID 5 · FWD 3               across XI + bench
      XI size     sum( x_i )                    == 11
      formation   1 GKP · 3-5 DEF · 2-5 MID · 1-3 FWD in the XI
      club        sum over club( x_i + b_i )    <= 3
      concentr.   sum over club, pos in {MID,FWD}( x_i + b_i )  <= 2   (default)
                  a PREFERENCE, not an FPL rule - the 3-per-club line above is
                  the real rule and never changes. This one caps how many of
                  those 3 may be attacking-returns sources from the same
                  fixture, because correlated returns (three players who all
                  score or all blank together) are a risk the flat objective
                  cannot see - it only sums expectations, never covariance.
                  Overridable/clearable per run - see EXOGENOUS PREFERENCES.
      gates       applied as a pre-filter, so an ineligible player has no variable

WHAT THIS BUYS OVER GREEDY - measured, not asserted.

At the FULL £100.0m budget the two agree exactly: 49.54 xP, identical XI. The
budget is slack enough that taking the best player at each slot happens to fit.
So on THIS instance the optimiser wins nothing, and saying otherwise would be
overselling it.

The difference appears the moment money is tight:

    budget   ILP xP   greedy
    100.0     49.54    49.54    identical
     95.0     48.77    NO FEASIBLE SQUAD
     90.0     47.79    NO FEASIBLE SQUAD
     85.0     45.85    NO FEASIBLE SQUAD

Greedy does not degrade - it FAILS. The reason is structural: it never consults
the budget while choosing. It takes the best available at each slot and checks
the total only at the end, so it works only when the unconstrained-best squad
happens to be affordable.

THIS MATTERS BECAUSE THE TIGHT CASE IS THE NORMAL CASE. A pre-season rebuild with
the whole £100m free is the one situation greedy handles. Every mid-season
transfer is made with £0.5m in the bank and a squad already fixed - precisely
where greedy has nothing to say.

Bench order is not optimised: autosub priority is a separate, much smaller
decision, and the model has no view on which starter is likeliest to be dropped.
"""
import importlib.util, json, math, os, sys

import constants

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("bs", os.path.join(HERE, "build_squad.py"))
bs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bs)          # reuse the gates and the xP model verbatim

try:
    import pulp
except ImportError:
    sys.exit("PuLP not installed.  pip install pulp")

# Squad shape (architecture review candidate #4) — was hand-duplicated here
# with string position keys and again in build_squad.py with int keys. One
# representation now, in constants.py.
BUDGET, SQUAD, XI_SIZE, MAX_CLUB = (
    constants.BUDGET, constants.SQUAD_SHAPE, constants.XI_SIZE, constants.MAX_PER_CLUB)
FORMATION = constants.FORMATION
HIT_COST = 4                     # points per transfer beyond the free allowance

# --- Exogenous preferences --------------------------------------------------
# NOT FPL rules - those are constants.py (budget, squad shape, 3-per-club) and
# never change. These are Sylvan's standing choices, held as constraints so
# their cost is measurable (see PRICE OF THE PREFERENCE) rather than baked in
# silently. allow_haaland follows the same pattern via its own bool param.
MAX_ATT_PER_CLUB_DEFAULT = 2     # cap on MID+FWD owned from one club; None = off


def _max_attackers_from_one_club(rows):
    """(club, count) for whichever club has the most MID+FWD players in
    `rows`, or (None, 0) if there are none."""
    from collections import Counter
    c = Counter(r["team"] for r in rows if r["pos"] in ("MID", "FWD"))
    if not c:
        return None, 0
    return c.most_common(1)[0]

# The live squad, from squad.json via squad_state.py - the SINGLE source of
# truth. These were hardcoded here, in build_dashboard.py and in
# fixture_adjust.py until 9 Aug 2026; keeping three copies in step was a
# standing instruction that still failed silently. Do not reintroduce a literal.
_spec = importlib.util.spec_from_file_location("squad_state",
                                               os.path.join(HERE, "squad_state.py"))
squad_state = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(squad_state)
_STATE = squad_state.load()

CURRENT_SQUAD = _STATE.names
BANK = _STATE.bank


def optimise(pool, allow_haaland=False, max_att_per_club=MAX_ATT_PER_CLUB_DEFAULT,
             verbose=True):
    P = [r for r in pool if r["ok"]]
    if not allow_haaland:
        P = [r for r in P if r["name"] != "Haaland"]
    # Gate 2 differs for XI and bench, so it is expressed on the variables:
    # a player below GATE_XI may still be bought as fodder, but cannot start.
    P = [r for r in P if r["stp"] >= bs.GATE_BENCH]

    prob = pulp.LpProblem("fpl_squad", pulp.LpMaximize)
    x = {i: pulp.LpVariable(f"x{i}", cat="Binary") for i in range(len(P))}
    b = {i: pulp.LpVariable(f"b{i}", cat="Binary") for i in range(len(P))}

    # Primary objective: XI expected points.
    # Secondary, epsilon-weighted: among bench players the model is otherwise
    # indifferent to (bench xP contributes NOTHING), prefer the one who actually
    # plays. Without this the solver picks arbitrarily among equal-priced fodder
    # and can land on a 61%-starter, which is worthless for autosub and Bench
    # Boost. EPS is small enough that it can never alter an XI decision.
    EPS = 1e-4
    prob += (pulp.lpSum(P[i]["score"] * x[i] for i in range(len(P)))
             + EPS * pulp.lpSum(P[i]["stp"] * b[i] for i in range(len(P))))

    for i in range(len(P)):
        prob += x[i] + b[i] <= 1
        if P[i]["stp"] < bs.GATE_XI:
            prob += x[i] == 0                      # fodder-only: may not start

    prob += pulp.lpSum(P[i]["price"] * (x[i] + b[i]) for i in range(len(P))) <= BUDGET
    prob += pulp.lpSum(x[i] + b[i] for i in range(len(P))) == 15
    prob += pulp.lpSum(x[i] for i in range(len(P))) == XI_SIZE

    for pos, n in SQUAD.items():
        idx = [i for i in range(len(P)) if P[i]["pos"] == pos]
        prob += pulp.lpSum(x[i] + b[i] for i in idx) == n
        lo, hi = FORMATION[pos]
        prob += pulp.lpSum(x[i] for i in idx) >= lo
        prob += pulp.lpSum(x[i] for i in idx) <= hi

    for club in {r["team"] for r in P}:
        idx = [i for i in range(len(P)) if P[i]["team"] == club]
        prob += pulp.lpSum(x[i] + b[i] for i in idx) <= MAX_CLUB
        if max_att_per_club is not None:
            idx_att = [i for i in idx if P[i]["pos"] in ("MID", "FWD")]
            prob += pulp.lpSum(x[i] + b[i] for i in idx_att) <= max_att_per_club

    prob.solve(pulp.PULP_CBC_CMD(msg=0))
    if pulp.LpStatus[prob.status] != "Optimal":
        sys.exit(f"solver returned {pulp.LpStatus[prob.status]}")

    xi = [P[i] for i in range(len(P)) if x[i].value() > 0.5]
    bench = [P[i] for i in range(len(P)) if b[i].value() > 0.5]
    return xi, bench, pulp.value(prob.objective)


def optimise_transfers(pool, owned_names, bank, n_transfers, allow_haaland=False,
                       max_att_per_club=MAX_ATT_PER_CLUB_DEFAULT,
                       free_transfers=1, force=False):
    """Best n_transfers FROM the current squad. The weekly question.

    Differs from rebuild mode in three ways that matter:
      * the squad is a CONSTRAINT, not an output - at most n players may change
      * the budget is the sale proceeds plus the bank, which is usually tiny
      * transfers beyond the free allowance cost 4 points each

    force=False (default): AT MOST n_transfers may change - if holding is
    genuinely optimal, the solver returns the current squad unchanged. This is
    the right question for "should I make a transfer" (transfer_mode() below).

    force=True: EXACTLY n_transfers must change - the solver is not permitted
    to hand back the current squad, so it returns the next-best forced move
    even if its impact is small or negative. Answers a different question,
    "if I had to move exactly one player, which one" - useful for showing the
    next-best alternative alongside a hold recommendation, not for deciding
    whether to hold. See build_squad_page.py's Alternative 2 panel, which
    calls this with force=True and applies its own MIN_GAIN threshold to the
    result to decide what to recommend.

    SELL PRICE CAVEAT: this uses current price. FPL actually pays purchase price
    plus half any rise, so mid-season the true proceeds can be lower. Pre-season
    the two are identical. Do not trust a marginal call to 0.1m mid-season.
    """
    P = [r for r in pool if r["ok"] or r["name"] in owned_names]
    if not allow_haaland:
        P = [r for r in P if r["name"] != "Haaland"]
    P = [r for r in P if r["stp"] >= bs.GATE_BENCH or r["name"] in owned_names]
    idx_owned = [i for i, r in enumerate(P) if r["name"] in owned_names]
    missing = set(owned_names) - {P[i]["name"] for i in idx_owned}
    if missing:
        print(f"  WARNING: owned players not found in the pool: {sorted(missing)}")

    prob = pulp.LpProblem("fpl_transfer", pulp.LpMaximize)
    x = {i: pulp.LpVariable(f"x{i}", cat="Binary") for i in range(len(P))}
    b = {i: pulp.LpVariable(f"b{i}", cat="Binary") for i in range(len(P))}
    own = {i: x[i] + b[i] for i in range(len(P))}

    hits = max(0, n_transfers - free_transfers) * HIT_COST
    EPS = 1e-4
    prob += (pulp.lpSum(P[i]["score"] * x[i] for i in range(len(P)))
             + EPS * pulp.lpSum(P[i]["stp"] * b[i] for i in range(len(P))))

    for i in range(len(P)):
        prob += x[i] + b[i] <= 1
        if P[i]["stp"] < bs.GATE_XI:
            prob += x[i] == 0

    # Budget: what you can spend is what you already own plus the bank.
    owned_value = sum(P[i]["price"] for i in idx_owned)
    prob += pulp.lpSum(P[i]["price"] * own[i] for i in range(len(P))) <= owned_value + bank

    # At most n_transfers players may LEAVE (exactly, if force=True) - so at
    # least (15 - n) must be kept, or precisely (15 - n) if forced.
    kept = pulp.lpSum(own[i] for i in idx_owned)
    if force:
        prob += kept == 15 - n_transfers
    else:
        prob += kept >= 15 - n_transfers

    prob += pulp.lpSum(own[i] for i in range(len(P))) == 15
    prob += pulp.lpSum(x[i] for i in range(len(P))) == XI_SIZE
    for pos, n in SQUAD.items():
        ii = [i for i in range(len(P)) if P[i]["pos"] == pos]
        prob += pulp.lpSum(own[i] for i in ii) == n
        lo, hi = FORMATION[pos]
        prob += pulp.lpSum(x[i] for i in ii) >= lo
        prob += pulp.lpSum(x[i] for i in ii) <= hi
    for club in {r["team"] for r in P}:
        ii = [i for i in range(len(P)) if P[i]["team"] == club]
        prob += pulp.lpSum(own[i] for i in ii) <= MAX_CLUB
        if max_att_per_club is not None:
            ii_att = [i for i in ii if P[i]["pos"] in ("MID", "FWD")]
            prob += pulp.lpSum(own[i] for i in ii_att) <= max_att_per_club

    prob.solve(pulp.PULP_CBC_CMD(msg=0))
    if pulp.LpStatus[prob.status] != "Optimal":
        return None
    xi = [P[i] for i in range(len(P)) if x[i].value() > 0.5]
    bench = [P[i] for i in range(len(P)) if b[i].value() > 0.5]
    return xi, bench, hits


def show(xi, bench, obj):
    order = ["GKP", "DEF", "MID", "FWD"]
    form = "-".join(str(sum(1 for r in xi if r["pos"] == p)) for p in order[1:])
    spend_xi = sum(r["price"] for r in xi)
    spend = spend_xi + sum(r["price"] for r in bench)
    xp_xi = sum(r["score"] for r in xi)
    print(f"formation {form}   XI £{spend_xi:.1f}m   squad £{spend:.1f}m   "
          f"bank £{BUDGET-spend:.1f}m   XI xP/90 {xp_xi:.2f}   "
          f"bench avg starts {sum(r['stp'] for r in bench)/len(bench)*100:.0f}%\n")
    for r in sorted(xi, key=lambda r: (order.index(r["pos"]), -r["score"])):
        print(f"  {r['name'][:14]:<15}{r['pos']:<5}{r['team']:<5}£{r['price']:<5.1f}"
              f"{r['stp']*100:>4.0f}%   xP {r['score']:>5.2f}")
    print("  --- bench ---")
    for r in sorted(bench, key=lambda r: order.index(r["pos"])):
        print(f"  {r['name'][:14]:<15}{r['pos']:<5}{r['team']:<5}£{r['price']:<5.1f}"
              f"{r['stp']*100:>4.0f}%   xP {r['score']:>5.2f}")


def transfer_mode(pool, n, allow_haaland, max_att_per_club=MAX_ATT_PER_CLUB_DEFAULT):
    owned = set(CURRENT_SQUAD)
    base = [r for r in pool if r["name"] in owned]
    # Baseline: best XI from the squad already owned, AS OWNED - never run
    # through max_att_per_club. That preference governs what gets BOUGHT; a
    # squad assembled before the preference existed (or under FPL's own
    # weaker 3-per-club rule) can already breach a stricter, later-added one.
    # Forcing k=0 through the same cap would make "make no changes" itself
    # infeasible and hide the real answer - whether a transfer is worth it.
    res0 = optimise_transfers(pool, owned, BANK, 0, allow_haaland, max_att_per_club=None)
    if not res0:
        sys.exit("current squad is infeasible under the base constraints — check CURRENT_SQUAD")
    xi0 = sum(r["score"] for r in res0[0])
    print(f"current squad   XI xP/90 {xi0:.2f}   bank £{BANK:.1f}m\n")

    if max_att_per_club is not None:
        club_b, breach = _max_attackers_from_one_club(res0[0] + res0[1])
        if breach > max_att_per_club:
            print(f"  NOTE: current squad already holds {breach} attackers from "
                  f"{club_b} - over the {max_att_per_club}/club preference. Options "
                  f"below still enforce the cap on the resulting squad, so clearing "
                  f"the breach may be forced into whichever move is shown, or may "
                  f"need more transfers than are free this week.\n")

    for k in range(1, n + 1):
        res = optimise_transfers(pool, owned, BANK, k, allow_haaland, max_att_per_club)
        if not res:
            print(f"  {k} transfer(s): infeasible"
                  + (f" — {max_att_per_club}/club cap cannot be met in {k} move(s)"
                     if max_att_per_club is not None else "")); continue
        xi, bench, hits = res
        gain = sum(r["score"] for r in xi) - xi0
        out = sorted(owned - {r["name"] for r in xi + bench})
        inn = sorted({r["name"] for r in xi + bench} - owned)

        # MIN_GAIN guards against the epsilon bench tiebreak surfacing as a
        # "transfer". A swap worth 0.00 xP is not a recommendation - it is the
        # solver breaking a tie, and reporting it as a move would be noise.
        MIN_GAIN = 0.01
        if gain < MIN_GAIN or not inn:
            print(f"  {k} transfer(s): no gain above {MIN_GAIN} xP/90 — HOLD")
            if inn:
                print(f"      (solver is indifferent between {out} and {inn};"
                      f" a tie, not an upgrade)")
            continue

        print(f"  {k} transfer(s): +{gain:.2f} xP/90"
              + (f"  (hit −{hits})" if hits else "  (free)"))
        print(f"      OUT {out}  ->  IN {inn}")
        if hits:
            be = hits / gain
            print(f"      breakeven after {be:.1f} gameweeks held — "
                  f"{'worth it' if be <= 5 else 'NOT worth the hit on a normal hold'}")
        print(f"      over a 5-GW hold: {gain*5 - hits:+.1f} pts net")


def _fixture_scale(pool):
    """Apply fixture_adjust and swap the objective to xP_adj. Mutates pool."""
    import importlib.util as _il
    _sp = _il.spec_from_file_location("fa", os.path.join(HERE, "fixture_adjust.py"))
    fa = _il.module_from_spec(_sp); _sp.loader.exec_module(fa)
    fa.adjust(pool)
    for r in pool:
        r["score"] = r["xp_adj"]
    return fa


def compare_intel(allow_haaland, season_starts, use_fixtures, n_transfers,
                   max_att_per_club=MAX_ATT_PER_CLUB_DEFAULT):
    """WITH vs WITHOUT ROLE_INTEL.md adjustments, in one run.

    Mirrors the "PRICE OF THE PREFERENCE" pattern already used for the
    no-Haaland preference below - report the cost/gain of a choice rather than
    silently baking it in. Two independent pools are built (bs.load(intel=...)
    takes an explicit override for exactly this) so nothing here duplicates
    the adjustment logic itself - that stays in intel_adjust.py, single source.
    """
    print("=== INTEL COMPARISON — WITH vs WITHOUT ROLE_INTEL.md adjustments ===\n")
    pool_off = bs.load(season_starts=season_starts, intel=False)
    pool_on = bs.load(season_starts=season_starts, intel=True)
    if use_fixtures:
        _fixture_scale(pool_off)
        _fixture_scale(pool_on)
        print(f"objective: xP_adj (opponent-adjusted, GW1-4)\n")

    if n_transfers is not None:
        print("--- WITHOUT intel ---")
        transfer_mode(pool_off, n_transfers, allow_haaland, max_att_per_club)
        print("\n--- WITH intel ---")
        transfer_mode(pool_on, n_transfers, allow_haaland, max_att_per_club)
        return

    xi_off, bench_off, _ = optimise(pool_off, allow_haaland, max_att_per_club)
    xi_on, bench_on, _ = optimise(pool_on, allow_haaland, max_att_per_club)
    xp_off = sum(r["score"] for r in xi_off)
    xp_on = sum(r["score"] for r in xi_on)
    out = sorted({r["name"] for r in xi_off + bench_off}
                 - {r["name"] for r in xi_on + bench_on})
    inn = sorted({r["name"] for r in xi_on + bench_on}
                 - {r["name"] for r in xi_off + bench_off})
    print(f"XI xP/90 WITHOUT intel: {xp_off:.2f}")
    print(f"XI xP/90 WITH intel:    {xp_on:.2f}   ({xp_on - xp_off:+.2f})")
    if out or inn:
        print(f"  OUT (without -> with): {out}")
        print(f"  IN  (without -> with): {inn}")
    else:
        print("  Same 15 players either way — intel moved rates but not who "
              "gets picked at this budget.")


def compare_estimators(allow_haaland, season_starts, use_fixtures, n_transfers,
                        max_att_per_club=MAX_ATT_PER_CLUB_DEFAULT,
                        estimators=("prior", "raw", "shrunk")):
    """prior vs raw vs shrunk (or any subset/order of them), in one run.

    Generalises compare_intel()'s WITH/WITHOUT pattern to three options
    instead of two - one independent pool per estimator (bs.load(estimator=...)
    takes an explicit override for exactly this), diffed against the first
    named estimator as baseline. This is the sanity-check tool for the GW3
    dry run and the GW5 review (see METHODOLOGY_ALTERNATIVES.md A0.2
    "Phase 2"). If the live bootstrap-static fetch fails (no network - true
    in this session's sandbox), raw/shrunk both fall back to prior-only and
    this will correctly report no difference from prior; that is
    build_squad.load()'s designed degrade-safe behaviour, not a bug in the
    comparison.
    """
    print(f"=== ESTIMATOR COMPARISON — {' vs '.join(estimators)} ===\n")
    pools = {e: bs.load(season_starts=season_starts, estimator=e) for e in estimators}
    if use_fixtures:
        for p in pools.values():
            _fixture_scale(p)
        print(f"objective: xP_adj (opponent-adjusted, GW1-4)\n")

    if n_transfers is not None:
        for e in estimators:
            print(f"--- {e} ---")
            transfer_mode(pools[e], n_transfers, allow_haaland, max_att_per_club)
            print()
        return

    picks = {}
    for e in estimators:
        xi, bench, _ = optimise(pools[e], allow_haaland, max_att_per_club)
        picks[e] = (xi, bench)
        print(f"XI xP/90 [{e:>6}]: {sum(r['score'] for r in xi):.2f}")

    base = estimators[0]
    base_names = {r["name"] for r in picks[base][0] + picks[base][1]}
    for e in estimators[1:]:
        names = {r["name"] for r in picks[e][0] + picks[e][1]}
        out, inn = sorted(base_names - names), sorted(names - base_names)
        if out or inn:
            print(f"\n{base} -> {e}:")
            print(f"  OUT: {out}")
            print(f"  IN:  {inn}")
        else:
            print(f"\n{base} -> {e}: same 15 players — the estimator moved "
                  f"rates but not who gets picked at this budget (or the "
                  f"live fetch found nothing to move - check for a "
                  f"fetch-failed warning above).")


def compare_shrink(allow_haaland, season_starts, use_fixtures, n_transfers,
                    max_att_per_club=MAX_ATT_PER_CLUB_DEFAULT):
    """Legacy alias for compare_estimators(estimators=("prior", "shrunk")) -
    kept so the --compare-shrink flag documented in METHODOLOGY_ALTERNATIVES.md
    keeps working unchanged."""
    compare_estimators(allow_haaland, season_starts, use_fixtures, n_transfers,
                        max_att_per_club, estimators=("prior", "shrunk"))


def main():
    global BUDGET
    allow_haaland = "--haaland" in sys.argv
    if "--gate" in sys.argv:
        bs.GATE_XI = float(sys.argv[sys.argv.index("--gate") + 1])

    # Concentration preference: same treatment as --haaland above - overridable
    # (--max-attackers-per-club N) or clearable (--no-max-attackers-per-club),
    # never silently different from what gets printed and reported below.
    if "--no-max-attackers-per-club" in sys.argv:
        max_att_per_club = None
    elif "--max-attackers-per-club" in sys.argv:
        max_att_per_club = int(sys.argv[sys.argv.index("--max-attackers-per-club") + 1])
    else:
        max_att_per_club = MAX_ATT_PER_CLUB_DEFAULT

    if "--compare-intel" in sys.argv:
        n_transfers = (int(sys.argv[sys.argv.index("--transfers") + 1])
                       if "--transfers" in sys.argv else None)
        compare_intel(allow_haaland, "--season-starts" in sys.argv,
                      "--fixtures" in sys.argv, n_transfers, max_att_per_club)
        return

    if "--compare-shrink" in sys.argv:
        n_transfers = (int(sys.argv[sys.argv.index("--transfers") + 1])
                       if "--transfers" in sys.argv else None)
        compare_shrink(allow_haaland, "--season-starts" in sys.argv,
                       "--fixtures" in sys.argv, n_transfers, max_att_per_club)
        return

    if "--compare-estimators" in sys.argv:
        n_transfers = (int(sys.argv[sys.argv.index("--transfers") + 1])
                       if "--transfers" in sys.argv else None)
        compare_estimators(allow_haaland, "--season-starts" in sys.argv,
                            "--fixtures" in sys.argv, n_transfers, max_att_per_club)
        return

    # Parses its own argv now (architecture review candidate #3) rather than
    # relying on build_squad's ambient USE_INTEL default — this file IS the
    # entry point, so this was already correct in practice, but an explicit
    # local variable is the real fix, not a coincidence of shared argv.
    use_intel = "--no-intel" not in sys.argv
    # --estimator {prior,raw,shrunk} is the primary interface; --shrunk-priors
    # kept as a legacy alias for --estimator shrunk (see the module docstring).
    if "--estimator" in sys.argv:
        estimator = sys.argv[sys.argv.index("--estimator") + 1]
    elif "--shrunk-priors" in sys.argv:
        estimator = "shrunk"
    else:
        estimator = "prior"                       # default - see A0.2 "Phase 2"
    if estimator not in bs.ESTIMATOR_CHOICES:
        sys.exit(f"--estimator must be one of {bs.ESTIMATOR_CHOICES}, got {estimator!r}")
    pool = bs.load(season_starts="--season-starts" in sys.argv, intel=use_intel,
                   estimator=estimator)
    if use_intel:
        print("INTEL: ROLE_INTEL.md `adjustments` fence is ACTIVE (default since "
              "13 Aug 2026 - pass --no-intel to disable)\n")
    else:
        print("INTEL: DISABLED (--no-intel) - stp/xg90/etc. are the raw, "
              "ROLE_INTEL-blind numbers\n")
    est_note = {
        "prior": "PRIOR — 2025/26 season only (default). "
                 "Pass --estimator raw or --estimator shrunk to use live 2026/27 data.",
        "raw": f"RAW — live 2026/27 per-90 rates only, gated at "
               f"{bs.scoring.MIN_N90_RAW:.1f} n90, no blending (--estimator raw).",
        "shrunk": "SHRUNK — Bayesian blend of the 2025/26 prior and live "
                  "2026/27 rates (--estimator shrunk). See METHODOLOGY_ALTERNATIVES.md "
                  "A0.2 'Phase 2'.",
    }[estimator]
    print(f"ESTIMATOR: {est_note}\n")
    if "--fixtures" in sys.argv:
        # Swap the objective from flat xP to opponent-adjusted xP over the
        # window. Everything else - gates, constraints, bench rule - is
        # unchanged, so any difference in the squad is attributable to fixtures
        # and nothing else.
        import importlib.util as _il
        _sp = _il.spec_from_file_location("fa", os.path.join(HERE, "fixture_adjust.py"))
        fa = _il.module_from_spec(_sp); _sp.loader.exec_module(fa)
        fa.adjust(pool)
        for r in pool:
            r["score"] = r["xp_adj"]
        print(f"OBJECTIVE: xP_adj over GW1-{fa.HORIZON} "
              f"(opponent-adjusted; workload scaling "
              f"{'on' if fa.SCALE_WORKLOAD else 'off'})")
    att_note = ("" if max_att_per_club is None
                else f" · max {max_att_per_club} attackers/club")
    print(f"pool {len(pool)} players · gates: {bs.MIN_MINUTES}+ mins · "
          f"starts >={bs.GATE_XI:.0%} XI / {bs.GATE_BENCH:.0%} bench"
          + ("" if allow_haaland else " · no Haaland") + att_note + "\n")

    if "--transfers" in sys.argv:
        n = int(sys.argv[sys.argv.index("--transfers") + 1])
        print("=== TRANSFER MODE — best moves from the CURRENT squad ===")
        transfer_mode(pool, n, allow_haaland, max_att_per_club)
        return

    xi, bench, obj = optimise(pool, allow_haaland, max_att_per_club)
    print("=== OPTIMAL (ILP)" + ("" if allow_haaland else " — WITH THE NO-HAALAND PREFERENCE APPLIED") + " ===")
    show(xi, bench, obj)

    # PRICE THE PREFERENCE. Excluding Haaland is a Tier 5 preference under
    # SELECTION_FRAMEWORK.md, not a finding. A preference is entirely legitimate
    # to hold - but it must never be silently baked into something labelled
    # "optimal". Always report what it costs.
    if not allow_haaland:
        # Relax ONLY this preference - hold max_att_per_club fixed at its
        # current value - so the cost reported is this preference's alone,
        # not conflated with the concentration cap.
        fxi, fbench, _ = optimise(pool, allow_haaland=True, max_att_per_club=max_att_per_club)
        free = sum(r["score"] for r in fxi)
        held = sum(r["score"] for r in xi)
        cost = free - held
        print(f"\n--- PRICE OF THE PREFERENCE (no Haaland) ---")
        print(f"  unconstrained optimum : {free:.2f} xP/90"
              + ("  (includes Haaland)" if any(r["name"] == "Haaland" for r in fxi) else ""))
        print(f"  with no-Haaland held  : {held:.2f} xP/90")
        print(f"  COST OF THE PREFERENCE: {cost:.2f} xP/90  (~{cost*38:.0f} pts/season)")
        if cost < 0.30:
            print(f"  -> Small enough to be inside model error. The preference is"
                  f" effectively free.")
        else:
            print(f"  -> Material. This preference is costing real points; revisit it.")
        gone = {r["name"] for r in fxi} - {r["name"] for r in xi}
        gained = {r["name"] for r in xi} - {r["name"] for r in fxi}
        if gone:
            print(f"  holding it gives up : {sorted(gone)}")
            print(f"  and starts instead  : {sorted(gained)}")

    if max_att_per_club is not None:
        # Same treatment, other axis: relax the concentration cap only, hold
        # allow_haaland fixed at its current value.
        rxi, rbench, _ = optimise(pool, allow_haaland, max_att_per_club=None)
        relaxed = sum(r["score"] for r in rxi)
        held2 = sum(r["score"] for r in xi)
        cost2 = relaxed - held2
        club_m, m = _max_attackers_from_one_club(rxi + rbench)
        print(f"\n--- PRICE OF THE CONCENTRATION PREFERENCE "
              f"(max {max_att_per_club} attackers/club) ---")
        print(f"  unconstrained on this axis : {relaxed:.2f} xP/90"
              + (f"  (uses {m} attackers from one club — {club_m})"
                 if m > max_att_per_club else ""))
        print(f"  with the cap held          : {held2:.2f} xP/90")
        print(f"  COST OF THE PREFERENCE     : {cost2:.2f} xP/90  (~{cost2*38:.0f} pts/season)")
        if cost2 < 0.30:
            print(f"  -> Small enough to be inside model error. The preference is"
                  f" effectively free.")
        else:
            print(f"  -> Material. This preference is costing real points; revisit it.")
        gone2 = {r["name"] for r in rxi} - {r["name"] for r in xi}
        gained2 = {r["name"] for r in xi} - {r["name"] for r in rxi}
        if gone2:
            print(f"  holding it gives up : {sorted(gone2)}")
            print(f"  and starts instead  : {sorted(gained2)}")

    if max_att_per_club is not None:
        print(f"\n(NOTE: greedy below is blind to the max-{max_att_per_club}-"
              f"attackers-per-club preference — build_squad.py never applies it, "
              f"so any gap it shows against the ILP is not purely a methodology "
              f"gap; some of it may be the ILP paying for a constraint greedy "
              f"never had to satisfy.)")

    # Same gates, same xP, greedy slot-filling - the difference is the method.
    best = None
    for form in ((3,4,3),(3,5,2),(4,4,2),(4,3,3),(5,3,2),(4,5,1),(5,4,1)):
        ok, gxi, gsq, gxs, gtot = bs.build(pool, form, allow_haaland, bs.GATE_XI)
        if ok and gtot <= BUDGET:
            m = sum(r["score"] for r in gxi)
            if best is None or m > best[0]:
                best = (m, gxi, gsq, gxs, gtot)
    if best:
        gm, gxi, gsq, gxs, gtot = best
        print(f"\n=== GREEDY (build_squad.py) ===  XI xP/90 {gm:.2f}   squad £{gtot:.1f}m")
        gap = sum(r["score"] for r in xi) - gm
        same = {r["name"] for r in xi} & {r["name"] for r in gxi}
        diff = {r["name"] for r in xi} - {r["name"] for r in gxi}
        if abs(gap) < 1e-6:
            print(f"\n  Identical XI ({len(same)}/11). At the full budget greedy IS optimal —")
            print(f"  the constraint is slack, so slot-by-slot picking happens to fit.")
        else:
            print(f"\n  Greedy leaves {gap:.2f} xP/90 on the table "
                  f"(~{gap*38:.0f} pts/season). XI overlap {len(same)}/11.")
            if diff:
                print(f"  optimiser starts instead: {sorted(diff)}")
    else:
        print("\n=== GREEDY (build_squad.py) ===  NO FEASIBLE SQUAD at this budget.")
        print("  Greedy never consults the budget while choosing — it takes the best")
        print("  at each slot and checks the total afterwards. The optimiser still")
        print(f"  finds a squad worth {sum(r['score'] for r in xi):.2f} xP/90.")

    print("\nBudget sensitivity — where the method starts to matter:")
    print(f"  {'budget':>7}{'ILP xP':>9}   greedy")
    for B in (100.0, 95.0, 90.0, 85.0):
        keep, BUDGET = BUDGET, B
        try:
            oxi, _ob, _oo = optimise(pool, allow_haaland)
            oil = f"{sum(r['score'] for r in oxi):.2f}"
        except SystemExit:
            oil = "infeasible"
        gok = any(bs.build(pool, f_, allow_haaland, bs.GATE_XI)[0]
                  and bs.build(pool, f_, allow_haaland, bs.GATE_XI)[4] <= B
                  for f_ in ((3,4,3),(3,5,2),(4,4,2),(4,3,3),(5,3,2),(4,5,1),(5,4,1)))
        BUDGET = keep
        print(f"  {B:>7.1f}{oil:>9}   {'ok' if gok else 'NO FEASIBLE SQUAD'}")


if __name__ == "__main__":
    main()
