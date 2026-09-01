#!/usr/bin/env python3
"""One-off historical validation: replay the LIVE walk-forward shrinkage
methodology (build_prediction_tracker.py) across the ENTIRE completed 2025/26
season, GW2-38, using 2024/25 as the prior season - rather than the toy
2-gameweek sample the live tracker has to work with on the season actually
being played right now.

WHY THIS EXISTS. The retired build_priors_backtest.py already validated the
shrinkage MECHANISM once (see "Shrinkage backtest - 2025/26 GW1-8 vs GW9-38"
in METHODOLOGY_ALTERNATIVES.md), but with two shortcuts this script removes:
it used a POSITIONAL pool mean as its only "baseline" (never a player's own
prior-season rate), and it split ONE season in half rather than walking
forward week by week with a genuine prior SEASON behind it. This script
reuses the real hierarchical baseline (own last-season rate, falling back to
position mean) and calls build_prediction_tracker.py's own walk_forward()
directly, so the backtest is judged by the EXACT same code path the live
tracker runs every Tuesday, not a re-implementation that could quietly drift.

DATA SOURCE. Both seasons come from vaastav/Fantasy-Premier-League (see
fetch_gw_history.py's own caveat: a community archive mirroring the official
API, not the official API itself). 2025/26 reuses the already-cached
.cache_merged_gw.csv; 2024/25 is fetched fresh into its own cache file.

SCOPE LIMIT, CONFIRMED AGAINST THE ARCHIVE ITSELF: 2024/25's merged_gw.csv has
no clearances_blocks_interceptions / tackles / recoveries columns - FPL's
"defensive contribution" scoring category did not exist before 2025/26. There
is no historical prior to build CBIT90/CBIRT90 baselines from, so this script
only backtests the five metrics that DO have a real 2024/25 prior: xG90, xA90,
xGC90, saves90, start rate. walk_forward() still computes cbit90/cbirt90
buckets internally (it always iterates every metric); this script's build()
appends a CBIT_NOTE and callers should ignore those two keys in the output.

Run:  python3 historical_backtest_2025_26.py
Writes docs/data/historical_backtest_2025_26.json (trajectory across GW2-38
for raw/prior/shrunk, the five valid metrics) and prints a summary.
"""
import csv, io, json, os, re, sys, unicodedata, urllib.request
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import build_prediction_tracker as bpt

CURRENT_CSV = os.path.join(HERE, ".cache_merged_gw.csv")          # 2025/26, already cached
PRIOR_SEASON = "2024-25"
PRIOR_URL = f"https://raw.githubusercontent.com/vaastav/Fantasy-Premier-League/master/data/{PRIOR_SEASON}/gws/merged_gw.csv"
PRIOR_CACHE = os.path.join(HERE, f".cache_merged_gw_{PRIOR_SEASON}.csv")
OUT = os.path.join(HERE, "historical_backtest_2025_26.json")

POS_MAP = {"GK": "GKP", "GKP": "GKP", "DEF": "DEF", "MID": "MID", "FWD": "FWD"}
ELEMENT_TYPE = {"GKP": 1, "DEF": 2, "MID": 3, "FWD": 4}

CBIT_NOTE = (
    "cbit90 and cbirt90 are NOT valid in this backtest - 2024/25's archive has "
    "no clearances_blocks_interceptions/tackles/recoveries columns (FPL's "
    "defensive contribution category launched with 2025/26), so there is no "
    "real prior-season baseline for them. Excluded from the trajectory below."
)


def norm(s):
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    return tuple(t for t in re.sub(r"[^a-z ]", " ", s.lower()).split() if t)


def fetch_csv(url, cache_path):
    if os.path.exists(cache_path):
        print(f"  using local cache: {os.path.basename(cache_path)} "
              f"({os.path.getsize(cache_path)/1e6:.1f} MB)")
        return open(cache_path, encoding="utf-8", errors="replace").read()
    print(f"  GET {url}")
    try:
        with urllib.request.urlopen(url, timeout=120) as r:
            raw = r.read().decode("utf-8", errors="replace")
    except Exception as e:
        raise SystemExit(f"FETCH FAILED: {e}")
    open(cache_path, "w", encoding="utf-8").write(raw)
    print(f"  {len(raw)/1e6:.1f} MB cached to {os.path.basename(cache_path)}")
    return raw


def build_current_season():
    """boot/cache for 2025/26, keyed on the archive's own `element` id - no
    cross-season identity problem here, it is the SAME archive throughout."""
    rows = list(csv.DictReader(io.StringIO(
        open(CURRENT_CSV, encoding="utf-8", errors="replace").read())))
    elements, cache = {}, defaultdict(dict)
    for r in rows:
        pid = r.get("element")
        if not pid:
            continue
        pos = POS_MAP.get(r.get("position"), r.get("position"))
        if pos not in ELEMENT_TYPE:
            continue
        elements.setdefault(pid, dict(id=int(pid), element_type=ELEMENT_TYPE[pos],
                                       web_name=r["name"]))
        gw = r.get("round")
        if not gw or not gw.isdigit():
            continue
        cache[gw][pid] = {
            "minutes": r.get("minutes") or 0,
            "starts": r.get("starts") or 0,
            "expected_goals": r.get("expected_goals") or 0,
            "expected_assists": r.get("expected_assists") or 0,
            "expected_goals_conceded": r.get("expected_goals_conceded") or 0,
            "saves": r.get("saves") or 0,
            "clearances_blocks_interceptions": 0,
            "tackles": 0,
            "recoveries": 0,
        }
    finished = sorted((int(g) for g in cache), key=int)
    boot = {"elements": list(elements.values())}
    print(f"  2025/26: {len(elements)} players, GW{finished[0]}-{finished[-1]} "
          f"({len(finished)} rounds)")
    return boot, cache, finished


def build_prior_baselines(boot):
    """Hierarchical prior exactly like build_prediction_tracker.build_baselines(),
    sourced from 2024/25's archive instead of a frozen snapshot JSON. own-rate
    tier needs cross-season name matching (element ids are NOT stable between
    seasons); position-mean tier needs no matching at all."""
    raw = fetch_csv(PRIOR_URL, PRIOR_CACHE)
    rows = list(csv.DictReader(io.StringIO(raw)))
    totals = defaultdict(lambda: dict(mins=0.0, xg=0.0, xa=0.0, xgc=0.0, sv=0.0,
                                       starts=0, apps=0, pos=None))
    for r in rows:
        key = norm(r["name"])
        if not key:
            continue
        t = totals[key]
        m = float(r.get("minutes") or 0)
        t["mins"] += m
        t["xg"] += float(r.get("expected_goals") or 0)
        t["xa"] += float(r.get("expected_assists") or 0)
        t["xgc"] += float(r.get("expected_goals_conceded") or 0)
        t["sv"] += float(r.get("saves") or 0)
        t["starts"] += float(r.get("starts") or 0)
        t["apps"] += 1
        t["pos"] = POS_MAP.get(r.get("position"), t["pos"])

    own_rate, pool_by_pos = {}, defaultdict(list)
    for key, t in totals.items():
        if t["mins"] <= 0 or t["pos"] not in ELEMENT_TYPE:
            continue
        n90 = t["mins"] / 90.0
        r = dict(xg=t["xg"]/n90, xa=t["xa"]/n90, xgc=t["xgc"]/n90, sv=t["sv"]/n90,
                 cbit=0.0, cbirt=0.0)
        stp = t["starts"] / t["apps"] if t["apps"] else None
        if t["mins"] >= bpt.MIN_MINS_PRIOR:
            own_rate[key] = (r, t["pos"], stp)
            pool_by_pos[t["pos"]].append(r)

    pos_mean = {}
    for pos, rs in pool_by_pos.items():
        pos_mean[pos] = {k: sum(x[k] for x in rs)/len(rs) for k in ("xg","xa","xgc","sv","cbit","cbirt")}

    baselines, matched, unmatched = {}, 0, 0
    for el in boot["elements"]:
        pid, pos = str(el["id"]), bpt.POS.get(el["element_type"])
        key = norm(el["web_name"])
        hit = own_rate.get(key)
        if hit:
            r, hit_pos, stp = hit
            baselines[pid] = dict(rates=r, source="own", pos=pos, stp=stp if stp is not None else 0.3)
            matched += 1
        elif pos in pos_mean:
            baselines[pid] = dict(rates=pos_mean[pos], source="pos", pos=pos, stp=None)
            unmatched += 1
        else:
            baselines[pid] = dict(rates={k: 0.0 for k in ("xg","xa","xgc","sv","cbit","cbirt")},
                                   source="pos", pos=pos, stp=None)
            unmatched += 1

    stp_pos_mean = {}
    for pos in ("GKP", "DEF", "MID", "FWD"):
        vals = [b["stp"] for b in baselines.values() if b["pos"] == pos and b["stp"] is not None]
        stp_pos_mean[pos] = sum(vals)/len(vals) if vals else 0.3
    for b in baselines.values():
        if b["stp"] is None:
            b["stp"] = stp_pos_mean.get(b["pos"], 0.3)

    print(f"  2024/25 prior: {matched} players matched to their own last-season "
          f"rate (900+ mins), {unmatched} fell back to a positional mean")
    return baselines


VALID_METRICS = ["xg90", "xa90", "xgc90", "sv90", "stp"]


def main():
    print("Building 2025/26 season (own-progression source)...")
    boot, cache, finished = build_current_season()
    print("\nBuilding 2024/25 prior baselines...")
    baselines = build_prior_baselines(boot)
    print("\nWalking forward through GW2-38 (build_prediction_tracker.walk_forward, unmodified)...")
    weeks, _cum = bpt.walk_forward(boot, cache, finished, baselines)

    trajectory = {k: {"gw": [], "raw": [], "prior": [], "shrunk": []} for k in VALID_METRICS}
    for k in VALID_METRICS:
        nr = nb = ns = 0
        sr = sb = ss = 0.0
        for gw in finished:
            w = weeks[str(gw)][k]
            if not w["n"]:
                continue
            if w["rmse_raw"] is not None:
                sr += w["rmse_raw"]**2 * w["n"]; nr += w["n"]
            if w["rmse_base"] is not None:
                sb += w["rmse_base"]**2 * w["n"]; nb += w["n"]
            if w["rmse_shrunk"] is not None:
                ss += w["rmse_shrunk"]**2 * w["n"]; ns += w["n"]
            trajectory[k]["gw"].append(gw)
            trajectory[k]["raw"].append((sr/nr)**0.5 if nr else None)
            trajectory[k]["prior"].append((sb/nb)**0.5 if nb else None)
            trajectory[k]["shrunk"].append((ss/ns)**0.5 if ns else None)

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(dict(season="2025-26", prior_season=PRIOR_SEASON,
                   metric_labels={k: v["label"] for k, v in
                                  {m["key"]: m for m in bpt.METRICS}.items()},
                   caveat=CBIT_NOTE, trajectory=trajectory),
              open(OUT, "w", encoding="utf-8"), indent=1)

    print(f"\nwritten: {os.path.relpath(OUT, HERE)}")
    print(f"\n{CBIT_NOTE}\n")
    for k in VALID_METRICS:
        t = trajectory[k]
        raw_end = t["raw"][-1]
        base_end, shrunk_end = t["prior"][-1], t["shrunk"][-1]
        cross_gw = None
        for i, gw in enumerate(t["gw"]):
            if t["shrunk"][i] is not None and t["prior"][i] is not None and t["shrunk"][i] < t["prior"][i]:
                cross_gw = gw
                break
        label = k
        print(f"  {label:8s} final cumulative RMSE (GW38): raw {raw_end:.3f}  "
              f"prior {base_end:.3f}  shrunk {shrunk_end:.3f}"
              + (f"  -> shrunk overtook prior at GW{cross_gw}" if cross_gw else "  -> shrunk never beat prior"))


if __name__ == "__main__":
    main()
