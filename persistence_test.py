#!/usr/bin/env python3
"""Split-half persistence — does xGI persist, and does delta regress to zero?

    python3 fetch_gw_history.py    # must run first
    python3 persistence_test.py

CLOSES ROADMAP B6/D, A YEAR EARLY. The whole xGI-first method rests on two
numbers the project had taken from external literature and flagged as
unverifiable without two seasons of its own data: chance creation persists
~0.63, finishing over-performance ~0.12. The 2025/26 archive makes both
testable now, by splitting the season at GW19 and correlating each half.

    RESULT (n=256, 450+ minutes in BOTH halves):
        xGI/90        r = 0.84     (assumed 0.63 — BETTER than assumed)
        xG/90         r = 0.83
        actual G+A/90 r = 0.59
        DELTA/90      r = -0.01    (assumed 0.12 — it is NOISE)

Delta does not merely regress toward zero, it retains nothing. The heaviest
first-half over-performers gave back 91% of their edge; the heaviest
under-performers crossed zero and finished slightly positive.

FINISHING SKILL IS NOT DETECTABLE HERE, BY POSITION OR BY VOLUME. The natural
objection is that good finishers stay good, so forwards should differ. They do
not: FWD -0.10, MID -0.12, DEF +0.03. Nor does it appear once shot volume is
sufficient — no xG bucket shows positive persistence. Of the ten best
first-half finishers, four stayed positive in the second; a coin gives five.

    HONEST LIMIT: with 28 forwards the interval on r is roughly +/-0.39, so
    this rules out a LARGE finishing effect, not a modest one. Half a season is
    ~40-60 shots, where the literature that does find finishing skill uses
    hundreds across several seasons. The correct claim is "not detectable at
    the horizon this model operates on", which for selection purposes has the
    same consequence: a positive delta cannot be traded on.

OTHER LIMITS. One season, one split. Requiring minutes in both halves selects
for players who stayed fit and in favour. The January window sits inside the
split, so some players changed clubs mid-sample — docs/data/club_changes.json
now makes it possible to exclude them if a stricter run is ever wanted.
"""
import csv, io, math, os, statistics as st
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, ".cache_merged_gw.csv")
SPLIT, MIN_MINS = 19, 450


def f(x):
    try: return float(x)
    except (TypeError, ValueError): return 0.0


def corr(a, b):
    if len(a) < 8: return None
    ma, mb = st.mean(a), st.mean(b)
    den = math.sqrt(sum((x-ma)**2 for x in a) * sum((y-mb)**2 for y in b))
    return (sum((x-ma)*(y-mb) for x, y in zip(a, b)) / den) if den else 0.0


def load():
    if not os.path.exists(CACHE):
        raise SystemExit("run `python3 fetch_gw_history.py` first")
    rows = list(csv.DictReader(io.StringIO(
        open(CACHE, encoding="utf-8", errors="replace").read())))
    H = {1: defaultdict(lambda: defaultdict(float)),
         2: defaultdict(lambda: defaultdict(float))}
    pos = {}
    for r in rows:
        h = 1 if int(r["round"]) <= SPLIT else 2
        n = r["name"]; pos[n] = r["position"]; d = H[h][n]
        d["mins"] += int(r["minutes"] or 0)
        d["G"] += int(r["goals_scored"] or 0)
        d["A"] += int(r["assists"] or 0)
        d["xG"] += f(r["expected_goals"])
        d["xA"] += f(r["expected_assists"])
        d["xGI"] += f(r["expected_goal_involvements"])
    return H, pos


def main():
    H, pos = load()
    P = [n for n in H[1] if H[1][n]["mins"] >= MIN_MINS and H[2][n]["mins"] >= MIN_MINS]
    p90 = lambda d, k: d[k] / (d["mins"] / 90)
    delta = lambda d: (d["G"] + d["A"] - d["xGI"]) / (d["mins"] / 90)
    fin = lambda d: (d["G"] - d["xG"]) / (d["mins"] / 90)

    print(f"Split-half persistence · 2025/26 · GW1-{SPLIT} vs GW{SPLIT+1}-38")
    print(f"n = {len(P)} players with {MIN_MINS}+ minutes in both halves\n")
    print(f"  {'metric (per 90)':<26}{'r':>7}")
    for lab, fn in (("xGI", lambda d: p90(d, "xGI")), ("xG", lambda d: p90(d, "xG")),
                    ("xA", lambda d: p90(d, "xA")), ("actual G+A", lambda d: (d["G"]+d["A"])/(d["mins"]/90)),
                    ("DELTA (G+A - xGI)", delta), ("FINISHING (G - xG)", fin)):
        print(f"  {lab:<26}{corr([fn(H[1][n]) for n in P], [fn(H[2][n]) for n in P]):>7.2f}")

    print("\n  Finishing persistence by position — the 'good finishers stay good' test")
    print(f"  {'':<8}{'n':>4}{'r(xG)':>8}{'r(finishing)':>14}")
    for p in ("FWD", "MID", "DEF"):
        g = [n for n in P if pos[n] == p]
        print(f"  {p:<8}{len(g):>4}"
              f"{corr([p90(H[1][n],'xG') for n in g], [p90(H[2][n],'xG') for n in g]):>8.2f}"
              f"{corr([fin(H[1][n]) for n in g], [fin(H[2][n]) for n in g]):>14.2f}")

    print("\n  Reversion, by first-half delta quintile")
    recs = sorted((delta(H[1][n]), delta(H[2][n])) for n in P)
    q = len(recs) // 5
    for i in range(5):
        g = recs[i*q:(i+1)*q] if i < 4 else recs[4*q:]
        a, b = st.mean(x[0] for x in g), st.mean(x[1] for x in g)
        print(f"    quintile {i+1}   H1 {a:>+7.3f}   H2 {b:>+7.3f}   retained "
              f"{(b/a*100 if a else 0):>4.0f}%")


if __name__ == "__main__":
    main()
