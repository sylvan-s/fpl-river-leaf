#!/usr/bin/env python3
"""Roadmap A4 — empirical per-match DC hit rates, replacing p_threshold().

    python3 fetch_gw_history.py     # must run first
    python3 build_dc_rates.py       # writes dc_hit_rates.json

WHY. `build_squad.py` converted an average CBIT/CBIRT into expected DC points
through a four-band step function on the season mean. Measured against 2025/26
per-match counts that was wrong in three ways: the 0.80-1.00x band assumed 0.20
against an actual 0.41 (0.42 xP/90, ~16 pts/season, over 39 of 160 qualifying
players); the top 1.30x band was unreachable and never fired; and everyone above
the line scored an identical 0.55 while real hit rates inside that band ran from
52% to 70%.

The award is a per-match THRESHOLD, so the honest estimator is the per-match hit
rate — which needs no distributional assumption at all. The mean cannot recover
it because the counts are overdispersed (variance/mean about 1.38), so a fat
right tail rescues near-miss players far more often than any tight distribution
allows. That is precisely the band the step function got most wrong.

CONDITIONING. Rates are computed over appearances of 60+ minutes. xP is a per-90
quantity, so the question being asked is "given he plays, does he clear the
line?" — a 20-minute cameo is a different population and would drag the rate down
for reasons the minutes model already handles.

SHRINKAGE. A player with six appearances should not be trusted at his raw rate.
Each is shrunk toward the positional mean by empirical Bayes, with the strength
k estimated FROM THE DATA by method of moments rather than chosen. This is the
same machinery A0.2 will use for start rates.

CONTAMINATION IS NOT SOLVED HERE. A player who changed clubs has a hit rate
earned at the old one — exactly as his mean was. See the `contaminated` fence in
ROLE_INTEL.md; this file flags them but does not adjust them, because there is
no honest basis on which to.
"""
import csv, io, json, os, re, unicodedata, statistics as st
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, ".cache_merged_gw.csv")
OUT = os.path.join(HERE, "dc_hit_rates.json")
SNAP = os.path.join(HERE, "fpl_priors_2025_26_v2.json")
THRESH = {"DEF": 10, "MID": 12, "FWD": 12}
MIN_MINUTES = 60          # a cameo is a different population
MIN_APPS_FOR_PRIOR = 20   # players used to estimate the positional prior


def main():
    if not os.path.exists(CACHE):
        raise SystemExit(
            f"{os.path.basename(CACHE)} not found — run `python3 fetch_gw_history.py`\n"
            f"first. This script does not invent rates for data it does not have.")

    rows = list(csv.DictReader(io.StringIO(
        open(CACHE, encoding="utf-8", errors="replace").read())))
    apps = defaultdict(list)
    pos, clubs = {}, defaultdict(set)
    for r in rows:
        if int(r["minutes"] or 0) >= MIN_MINUTES:
            k = r["name"]
            apps[k].append(int(r["defensive_contribution"] or 0))
            pos[k] = r["position"]
            clubs[k].add(r["team"])

    # --- positional priors, by method of moments on the beta-binomial ------
    priors = {}
    for p, thr in THRESH.items():
        rates = [sum(1 for x in v if x >= thr) / len(v)
                 for n, v in apps.items()
                 if pos[n] == p and len(v) >= MIN_APPS_FOR_PRIOR]
        if len(rates) < 5:
            priors[p] = (0.5, 5.0)
            continue
        m, var = st.mean(rates), st.variance(rates)
        # k = m(1-m)/var - 1 ; clamp to keep shrinkage sane on thin evidence
        k = max(2.0, min(30.0, (m * (1 - m) / var - 1) if var > 0 else 20.0))
        priors[p] = (m, k)

    # --- key the result on OUR pool's name|team ---------------------------
    # Same token-subset match as fetch_gw_history.py: web_name is often a
    # nickname, so every token of the short name must appear in the archive's
    # full name. Reads the snapshot directly rather than importing build_squad,
    # which would be circular once build_squad consumes this file.
    def norm(s):
        s = unicodedata.normalize("NFKD", s)
        s = "".join(c for c in s if not unicodedata.combining(c))
        return [t for t in re.sub(r"[^a-z ]", " ", s.lower()).split() if t]

    snap = json.load(open(SNAP, encoding="utf-8"))
    teams = {int(k): v for k, v in snap["teams"].items()}
    POSN = {1: "GKP", 2: "DEF", 3: "MID", 4: "FWD"}
    FULL2CODE = {'Arsenal':'ARS','Aston Villa':'AVL','Bournemouth':'BOU','Brentford':'BRE',
     'Brighton':'BHA','Burnley':'BUR','Chelsea':'CHE','Crystal Palace':'CRY','Everton':'EVE',
     'Fulham':'FUL','Leeds':'LEE','Liverpool':'LIV','Man City':'MCI','Man Utd':'MUN',
     'Newcastle':'NEW',"Nott'm Forest":'NFO','Spurs':'TOT','Sunderland':'SUN',
     'West Ham':'WHU','Wolves':'WOL'}
    mins = defaultdict(Counter)
    for r in rows:
        m = int(r["minutes"] or 0)
        if m:
            mins[r["name"]][r["team"]] += m
    arch = [{"n": n, "tok": set(norm(n)), "pos": pos[n], "v": v,
             "club": FULL2CODE.get(mins[n].most_common(1)[0][0]) if mins[n] else None,
             "mins": sum(mins[n].values())}
            for n, v in apps.items()]

    out, unmatched = {}, []
    for pl in snap["players"].values():
        if (pl.get("minutes", 0) or 0) < 900:
            continue
        ppos = POSN[pl["element_type"]]
        if ppos not in THRESH:
            continue
        key = f'{pl["web_name"]}|{teams[pl["team"]]}'
        want = {t for t in norm(pl["web_name"]) if len(t) > 1}
        c = [a for a in arch if want and want <= a["tok"]]
        if len(c) > 1:
            c = [a for a in c if a["pos"] == ppos] or c
        if len(c) > 1:
            # Club, then minutes — same ladder as fetch_gw_history.py. Club is
            # last because it is the unreliable field for anyone who moved.
            byteam = [a for a in c if a["club"] == teams[pl["team"]]]
            c = byteam if len(byteam) == 1 else sorted(c, key=lambda a: -a["mins"])[:1]
        if len(c) != 1:
            unmatched.append(key)
            continue
        a = c[0]
        thr = THRESH[a["pos"]]
        v = a["v"]
        hits, N = sum(1 for x in v if x >= thr), len(v)
        m, k = priors[a["pos"]]
        out[key] = {"counts": sorted(v),   # full per-match distribution, so the
                    #   rate can be re-evaluated at a FIXTURE-SCALED threshold:
                    #   a tougher opponent means more defensive work, which the
                    #   old mean-based path modelled by scaling the metric. A
                    #   fixed rate cannot respond to the opponent at all, so the
                    #   distribution is kept and P(X >= thresh/def_x) computed.
                    "pos": a["pos"], "apps": N, "hits": hits,
                    "raw": round(hits / N, 4),
                    "rate": round((hits + m * k) / (N + k), 4),
                    "mean_dc": round(st.mean(v), 2),
                    "archive_name": a["n"],
                    "clubs": sorted(clubs[a["n"]])}

    json.dump({
        "_comment": ("Empirical per-match DC hit rate. Roadmap A4. Replaces the "
                     "p_threshold() step function in build_squad.py. 'rate' is "
                     "shrunk toward the positional prior; 'raw' is unshrunk."),
        "source": "vaastav/Fantasy-Premier-League 2025-26, via .cache_merged_gw.csv",
        "caveat": ("Community archive, not the official API. A player who changed "
                   "clubs has a rate earned at the OLD club — see the contaminated "
                   "fence in ROLE_INTEL.md."),
        "conditioning": f"appearances of {MIN_MINUTES}+ minutes",
        "thresholds": THRESH,
        "priors": {p: {"mean": round(m, 4), "k_pseudo_matches": round(k, 1)}
                   for p, (m, k) in priors.items()},
        "unmatched": sorted(unmatched),
        "players": out,
    }, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    print(f"written: {OUT}  ({len(out)} matched, {len(unmatched)} unmatched)")
    if unmatched:
        print("  unmatched (will fall back to the step function): "
              + ", ".join(sorted(unmatched)))
    for p, (m, k) in priors.items():
        print(f"  {p}: prior mean {m:.3f}, shrinkage k = {k:.1f} pseudo-matches")


if __name__ == "__main__":
    main()
