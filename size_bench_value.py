#!/usr/bin/env python3
"""Size the prize: is autosub bench value worth modelling at all?

The current optimiser treats the bench as pure cost (optimise_squad.py:35-38).
Before building a Poisson-binomial autosub term into the objective, establish
whether the quantity it would add is large enough to change a decision.

    python3 size_bench_value.py            # flat xP
    python3 size_bench_value.py --fixtures # xP_adj over the window  <-- use this

THE MODEL, first-order and deliberately an UPPER BOUND
------------------------------------------------------
A bench player scores only if (a) enough starters blank to reach his slot, and
(b) he himself played.

    E[outfield bench] = sum_k  P(>= k blanks among the 10 outfield starters)
                               * s_k * xP_k          k = 1..3, best-first
    E[GK bench]       = (1 - s_gk_start) * s_gk_bench * xP_gk_bench

P(>= k blanks) is the Poisson-binomial over the starters' (1 - s_i), computed
exactly by DP under an independence assumption.

WHY THIS IS AN UPPER BOUND, so a small answer here is decisive:
  * formation validity is ignored — a real autosub only fires if the resulting
    shape is legal, which can only ever SUPPRESS a substitution, never add one
  * bench order is taken as optimal (best expected autosub first)
  * blanks are assumed independent; in reality they cluster (one team rotating,
    a postponed fixture), and clustering concentrates blanks rather than
    spreading them across slots, which lowers the chance of reaching slot 2-3
  * a 20-minute cameo is scored as a full start here, when in reality it scores
    ~1 point AND BLOCKS the autosub entirely — the single most optimistic
    assumption in the list

If the upper bound is below the noise floor, the exact model cannot rescue it.

THE UNIT TRAP — read this before quoting any total
--------------------------------------------------
The bench term below is expected points PER GAMEWEEK: it is already multiplied
by start probability. `optimise_squad.py`'s XI objective is expected points
PER 90: it is not. **Adding the two is invalid**, and it fails in a specific,
seductive direction.

Worked example, the live GW1 squad, Tavernier -> Anderson:

                                    before    after   change
    XI, xP per 90 (current model)    49.94    50.31    +0.37
    XI, xP per GW (start-weighted)   44.28    45.40    +1.12
    bench autosub                     3.72     3.13    -0.59
    per-90 XI + bench   (INVALID)    53.66    53.44    -0.21   <- reversal
    per-GW XI + bench   (correct)    48.00    48.53    +0.54   <- no reversal

Anderson (94% starts) replacing Joao Pedro (75%) in the XI makes the XI more
reliable, so fewer blanks, so the bench is needed less often. Bench slots 2
and 3 hold the SAME players before and after, and still lose 0.318 between
them — that fall is the transfer's benefit appearing with a minus sign. The
per-90 XI column cannot see the gain, but the bench column charges the
knock-on in full, so the transfer looks like a loss when it is a clear win.

CONSEQUENCE FOR THE BUILD ORDER: an autosub term cannot be added to the
current objective. It would systematically penalise every upgrade in XI
reliability — precisely the transfers worth making. Start-weighting the XI is
a PRECONDITION for the bench term, not a parallel option.
"""
import importlib.util, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))


def _load(mod, fn):
    spec = importlib.util.spec_from_file_location(mod, os.path.join(HERE, fn))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


bs = _load("bs", "build_squad.py")
opt = _load("opt", "optimise_squad.py")

try:
    import pulp
except ImportError:
    sys.exit("PuLP not installed.  pip install pulp")


def blank_distribution(start_probs):
    """P(exactly j blanks) for j = 0..n, by exact DP (Poisson-binomial)."""
    dist = [1.0]
    for s in start_probs:
        q = 1.0 - s                       # P(this player blanks)
        nxt = [0.0] * (len(dist) + 1)
        for j, p in enumerate(dist):
            nxt[j] += p * (1 - q)
            nxt[j + 1] += p * q
        dist = nxt
    return dist


def at_least(dist, k):
    return sum(dist[k:]) if k < len(dist) else 0.0


def bench_value(xi, bench):
    """E[points from the bench via autosub], per gameweek. Upper bound."""
    xi_out = [r for r in xi if r["pos"] != "GKP"]
    xi_gk = [r for r in xi if r["pos"] == "GKP"]
    bn_out = [r for r in bench if r["pos"] != "GKP"]
    bn_gk = [r for r in bench if r["pos"] == "GKP"]

    dist = blank_distribution([r["stp"] for r in xi_out])
    # Optimal bench order: best expected autosub contribution first.
    bn_out = sorted(bn_out, key=lambda r: -(r["stp"] * r["score"]))

    rows, total = [], 0.0
    for k, r in enumerate(bn_out[:3], start=1):
        p = at_least(dist, k)
        v = p * r["stp"] * r["score"]
        total += v
        rows.append((f"OUT slot {k}", r["name"], p, r["stp"], r["score"], v))

    if xi_gk and bn_gk:
        g, bg = xi_gk[0], bn_gk[0]
        p = 1.0 - g["stp"]
        v = p * bg["stp"] * bg["score"]
        total += v
        rows.append(("GK slot", bg["name"], p, bg["stp"], bg["score"], v))

    return total, rows, dist


def best_bench_at_spend(pool, xi, spend, clubs_used):
    """Best achievable bench for a given total spend, respecting composition.

    Answers 'what is the most autosub value this money could buy?' — the other
    end of the range the optimiser would be trading within.
    """
    need = {"GKP": 2, "DEF": 5, "MID": 5, "FWD": 3}
    for r in xi:
        need[r["pos"]] -= 1
    xi_names = {r["name"] for r in xi}
    P = [r for r in pool if r["name"] not in xi_names and r["stp"] >= bs.GATE_BENCH]

    prob = pulp.LpProblem("bench", pulp.LpMaximize)
    b = {i: pulp.LpVariable(f"b{i}", cat="Binary") for i in range(len(P))}
    # Maximise raw autosub potential (stp * xP); slot probabilities are a
    # common factor across candidates so they do not change the ranking.
    prob += pulp.lpSum(P[i]["stp"] * P[i]["score"] * b[i] for i in range(len(P)))
    prob += pulp.lpSum(P[i]["price"] * b[i] for i in range(len(P))) <= spend + 1e-6
    for pos, n in need.items():
        idx = [i for i in range(len(P)) if P[i]["pos"] == pos]
        prob += pulp.lpSum(b[i] for i in idx) == n
    for club, used in clubs_used.items():
        idx = [i for i in range(len(P)) if P[i]["team"] == club]
        prob += pulp.lpSum(b[i] for i in idx) <= max(0, 3 - used)
    prob.solve(pulp.PULP_CBC_CMD(msg=0))
    if pulp.LpStatus[prob.status] != "Optimal":
        return None
    return [P[i] for i in range(len(P)) if b[i].value() > 0.5]


def main():
    pool = bs.load()
    label = "flat xP/90"
    if "--fixtures" in sys.argv:
        fa = _load("fa", "fixture_adjust.py")
        fa.adjust(pool)
        for r in pool:
            r["score"] = r["xp_adj"]
        label = f"xP_adj over GW1-{fa.HORIZON}"

    owned = set(opt.CURRENT_SQUAD)
    res = opt.optimise_transfers(pool, owned, opt.BANK, 0, allow_haaland=False)
    if not res:
        sys.exit("current squad infeasible — check CURRENT_SQUAD")
    xi, bench, _ = res

    print(f"SIZING THE BENCH PRIZE   objective: {label}")
    print("=" * 74)
    xi_p90 = sum(r["score"] for r in xi)
    xi_pgw = sum(r["stp"] * r["score"] for r in xi)
    print(f"\ncurrent XI, xP per 90            {xi_p90:6.2f}   <- optimise_squad.py's objective")
    print(f"current XI, xP per GW            {xi_pgw:6.2f}   <- start-weighted, comparable to the bench")
    print(f"availability haircut             {xi_p90-xi_pgw:6.2f}   "
          f"({(1-xi_pgw/xi_p90)*100:.0f}% of the per-90 figure is never played)")
    print("\nDO NOT ADD the bench total below to the per-90 line. See THE UNIT TRAP\n"
          "in the module docstring — it manufactures false reversals.")

    cur, rows, dist = bench_value(xi, bench)
    print(f"\nBlank distribution across the 10 outfield starters:")
    for j in range(min(5, len(dist))):
        print(f"   P(exactly {j} blank) {dist[j]:6.3f}      P(>= {j}) {at_least(dist,j):6.3f}")
    print(f"   expected blanks        {sum(j*p for j,p in enumerate(dist)):.3f}")

    print(f"\nCurrent bench, autosub value per gameweek:")
    print(f"   {'slot':<12}{'player':<15}{'P(used)':>9}{'start%':>9}{'xP':>8}{'E[pts]':>9}")
    for slot, name, p, s, xp, v in rows:
        print(f"   {slot:<12}{name[:14]:<15}{p:>9.3f}{s*100:>8.0f}%{xp:>8.2f}{v:>9.3f}")
    print(f"   {'':<12}{'TOTAL':<15}{'':<9}{'':<9}{'':<8}{cur:>9.3f}")

    bench_spend = sum(r["price"] for r in bench)
    clubs = {}
    for r in xi:
        clubs[r["team"]] = clubs.get(r["team"], 0) + 1

    print(f"\nRange the optimiser could trade within (bench spend held at "
          f"£{bench_spend:.1f}m):")
    best = best_bench_at_spend(pool, xi, bench_spend, clubs)
    if best:
        bv, _r, _d = bench_value(xi, best)
        print(f"   current bench          {cur:6.3f} pts/GW   "
              f"({', '.join(r['name'] for r in bench)})")
        print(f"   best bench, same money {bv:6.3f} pts/GW   "
              f"({', '.join(r['name'] for r in best)})")
        print(f"   HEADROOM               {bv-cur:+6.3f} pts/GW   "
              f"= {(bv-cur)*38:+.1f} pts/season")
    else:
        print("   (no feasible alternative bench at that spend)")

    print(f"\nWhat the same money buys in the XI — the opportunity cost:")
    print(f"   {'extra £m to bench':>18}{'best bench':>12}{'XI xP lost':>12}{'net':>9}")
    for extra in (0.5, 1.0, 2.0, 3.0):
        alt = best_bench_at_spend(pool, xi, bench_spend + extra, clubs)
        if not alt:
            continue
        av, _r, _d = bench_value(xi, alt)
        # XI cost of that money: re-solve the XI with a budget reduced by `extra`.
        lost = xi_marginal(pool, xi, extra)
        gain = av - cur
        print(f"   {extra:>18.1f}{av:>12.3f}{lost:>12.3f}{gain-lost:>+9.3f}")

    print(f"\nNoise floor for reference: the weekly brief treats anything under")
    print(f"0.10 xP/90 (~4 pts/season) as noise and refuses to act on it.")


def best_xi_at_spend(pool, spend):
    """Best XI buyable for `spend`, from the whole pool. Used for the exchange rate."""
    P = [r for r in pool if r["stp"] >= bs.GATE_XI]
    prob = pulp.LpProblem("xi", pulp.LpMaximize)
    x = {i: pulp.LpVariable(f"x{i}", cat="Binary") for i in range(len(P))}
    prob += pulp.lpSum(P[i]["score"] * x[i] for i in range(len(P)))
    prob += pulp.lpSum(P[i]["price"] * x[i] for i in range(len(P))) <= spend + 1e-6
    prob += pulp.lpSum(x[i] for i in range(len(P))) == 11
    for pos, (lo, hi) in opt.FORMATION.items():
        idx = [i for i in range(len(P)) if P[i]["pos"] == pos]
        prob += pulp.lpSum(x[i] for i in idx) >= lo
        prob += pulp.lpSum(x[i] for i in idx) <= hi
    for club in {r["team"] for r in P}:
        idx = [i for i in range(len(P)) if P[i]["team"] == club]
        prob += pulp.lpSum(x[i] for i in idx) <= 3
    prob.solve(pulp.PULP_CBC_CMD(msg=0))
    if pulp.LpStatus[prob.status] != "Optimal":
        return float("nan")
    return pulp.value(prob.objective)


def xi_marginal(pool, xi, give_up, _cache={}):
    """xP the XI gives up when `give_up` £m is moved to the bench.

    BOTH ends of this comparison must come from the same construction, or the
    answer is meaningless. Comparing the OWNED XI against a freshly optimised
    one measures 'how suboptimal is my squad', not 'what does a pound buy' —
    and returns a negative cost, which is how the bug announced itself.
    """
    xi_spend = sum(r["price"] for r in xi)
    if "base" not in _cache:
        _cache["base"] = best_xi_at_spend(pool, xi_spend)
    return _cache["base"] - best_xi_at_spend(pool, xi_spend - give_up)


if __name__ == "__main__":
    main()
