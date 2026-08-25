#!/usr/bin/env python3
"""Pure-stdlib statistical tests — no numpy/scipy dependency.

WHY THIS EXISTS. The build_*.py pipeline that publish_dashboard.sh runs is
stdlib-only everywhere else in this repo (grep confirms no numpy/scipy import
anywhere else) - the one exception, pulp in optimise_squad.py, isn't part of
the publish path. Adding a scipy import to a page-build script would make
`publish_dashboard.sh` fail on any machine where scipy isn't already
installed, and the skill's own rule is that a broken build must never go
live silently. So the tests actually used on the "Statistical relationships"
page (Kruskal-Wallis, Mann-Whitney U, two-sample KS) are reimplemented here
in plain Python, validated against scipy's output on the exact data they're
used for (25 Aug 2026 - see the __main__ block, and the numbers quoted in
that chat session): all three matched scipy to at least 3 decimal places
except the KS asymptotic p-value on one pair, which used a marginally
different series approximation and differed in the 3rd decimal (0.212 vs
0.209) - well within what "asymptotic" already concedes, and it doesn't
change any significance conclusion.

Kruskal-Wallis' p-value uses a closed form rather than a general chi-square
CDF: with exactly 3 groups, df = 2, and chi-square(df=2) IS Exponential(rate
0.5) exactly, so P(H > h) = exp(-h/2) with no incomplete-gamma machinery
needed. This only covers the 3-group case used here - _chi2_sf_generic
raises for anything else rather than silently returning a wrong number for
df != 1, 2.
"""
import math
from collections import Counter
import bisect


def _norm_sf(z):
    """Standard normal survival function, exact via math.erfc (stdlib)."""
    return 0.5 * math.erfc(z / math.sqrt(2))


def _rank(values):
    """Average (mid-)ranks, 1-based, ties handled - the standard scheme
    every rank-based test below assumes."""
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        avg_rank = (i + 1 + j + 1) / 2.0
        for k in range(i, j + 1):
            ranks[order[k]] = avg_rank
        i = j + 1
    return ranks


def _chi2_sf_generic(x, df):
    if df == 1:
        return 2 * _norm_sf(math.sqrt(x))
    raise NotImplementedError(
        f"chi2 survival function only implemented for df in (1, 2) - got df={df}. "
        "Add a general incomplete-gamma implementation before using this for "
        "anything other than a 2- or 3-group Kruskal-Wallis test.")


def kruskal_wallis(groups):
    """groups: list of lists of numbers (2+ groups). Tie-corrected H and its
    p-value under chi2(df=len(groups)-1)."""
    all_vals = []
    for g in groups:
        all_vals.extend(g)
    N = len(all_vals)
    ranks = _rank(all_vals)
    idx, R = 0, []
    for g in groups:
        n = len(g)
        R.append(sum(ranks[idx:idx + n]))
        idx += n
    H = 12.0 / (N * (N + 1)) * sum(r * r / len(g) for r, g in zip(R, groups)) - 3 * (N + 1)
    tie_sum = sum(t ** 3 - t for t in Counter(all_vals).values())
    denom = 1 - tie_sum / float(N ** 3 - N)
    H_corr = H / denom if denom > 0 else H
    df = len(groups) - 1
    p = math.exp(-H_corr / 2.0) if df == 2 else _chi2_sf_generic(H_corr, df)
    return H_corr, p


def mannwhitney_u(a, b):
    """Two-sided Mann-Whitney U, normal approximation with tie correction
    and continuity correction. Returns (U1, p)."""
    n1, n2 = len(a), len(b)
    N = n1 + n2
    combined = list(a) + list(b)
    ranks = _rank(combined)
    R1 = sum(ranks[:n1])
    U1 = R1 - n1 * (n1 + 1) / 2.0
    mean_U = n1 * n2 / 2.0
    tie_sum = sum(t ** 3 - t for t in Counter(combined).values())
    sigma2 = (n1 * n2 / 12.0) * ((N + 1) - tie_sum / float(N * (N - 1)))
    if sigma2 <= 0:
        return U1, 1.0
    sigma = math.sqrt(sigma2)
    z = U1 - mean_U
    z += -0.5 if z > 0 else (0.5 if z < 0 else 0.0)
    z /= sigma
    return U1, min(2 * _norm_sf(abs(z)), 1.0)


def ks_2samp(a, b):
    """Two-sample Kolmogorov-Smirnov: max gap between empirical CDFs, plus
    the asymptotic (Stephens-approximation) p-value."""
    n1, n2 = len(a), len(b)
    a_sorted, b_sorted = sorted(a), sorted(b)
    all_vals = sorted(set(a_sorted + b_sorted))
    D = 0.0
    for v in all_vals:
        cdf_a = bisect.bisect_right(a_sorted, v) / n1
        cdf_b = bisect.bisect_right(b_sorted, v) / n2
        D = max(D, abs(cdf_a - cdf_b))
    en = math.sqrt(n1 * n2 / float(n1 + n2))
    lam = (en + 0.12 + 0.11 / en) * D
    p = 0.0
    for k in range(1, 101):
        term = ((-1) ** (k - 1)) * math.exp(-2 * k * k * lam * lam)
        p += term
        if abs(term) < 1e-10:
            break
    return D, max(0.0, min(1.0, 2 * p))


def bonferroni(pvals):
    n = len(pvals)
    return [min(p * n, 1.0) for p in pvals]


if __name__ == "__main__":
    # Validated against scipy 25 Aug 2026 on the DEF/MID/FWD 2025/26 pooled
    # gameweek-points data (150+ season point qualifiers) - see the chat
    # session for the scipy-side numbers this was checked against.
    raw = {
        'DEF': {'-1': 2, '0': 39, '1': 50, '2': 56, '3': 39, '4': 36, '5': 12, '6': 39,
                '7': 10, '8': 25, '9': 16, '10': 5, '11': 17, '12': 3, '13': 5, '14': 6,
                '15': 6, '17': 3},
        'MID': {'-1': 1, '0': 37, '1': 40, '2': 98, '3': 56, '4': 45, '5': 34, '6': 27,
                '7': 14, '8': 18, '9': 17, '10': 19, '11': 10, '12': 8, '13': 13, '14': 4,
                '15': 4, '16': 2, '17': 1, '18': 2, '20': 1},
        'FWD': {'0': 6, '1': 14, '2': 63, '4': 3, '5': 8, '6': 8, '7': 5, '8': 8, '9': 7,
                '10': 2, '11': 2, '12': 3, '13': 12, '14': 1, '15': 2, '16': 3, '17': 1,
                '19': 1},
    }
    groups = {pos: [int(k) for k, v in d.items() for _ in range(v)] for pos, d in raw.items()}
    H, p = kruskal_wallis([groups['DEF'], groups['MID'], groups['FWD']])
    print(f"KW H={H:.4f} p={p:.4f}  (expect H=0.386 p=0.8243)")
    for a, b in [('DEF', 'MID'), ('DEF', 'FWD'), ('MID', 'FWD')]:
        U, p = mannwhitney_u(groups[a], groups[b])
        print(f"MWU {a} vs {b}: U={U:.1f} p={p:.4f}")
    for a, b in [('DEF', 'MID'), ('DEF', 'FWD'), ('MID', 'FWD')]:
        D, p = ks_2samp(groups[a], groups[b])
        print(f"KS  {a} vs {b}: D={D:.4f} p={p:.4f}")
