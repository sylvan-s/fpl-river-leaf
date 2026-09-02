#!/usr/bin/env python3
"""Shared data engine for the methodology-diagnostic pages — computes the
whole player/team pool ONCE and exposes it as module-level globals (`rows`,
`D`/`M`/`F_`/`G`, `stats`, `kpanel`, `FIXTURES`, `club_xgc_cs`, `payload`, ...)
for its three consumers to slice as they need:

    build_player_benchmarking.py   docs/player-benchmarking.html
    build_team_benchmarking.py     docs/team-benchmarking.html
    build_relationships_page.py    docs/relationships.html

THIS FILE WRITES NO PAGE ITSELF. Until 2 Sep 2026 it emitted a single
"Player & Club Metric Benchmarking" page (analysis.html) directly; that page
was split into the two above because its panels answered two different
questions (which PLAYER to pick vs. whose fixtures are kind) with only the
first needing the global start% filter the four player-level panels shared.
Splitting the OUTPUT without splitting the DATA PIPELINE would have meant two
independently-computed player pools drifting apart the moment either changed
- exactly the failure class this project keeps a standing warning about (see
squad.json's provenance note, and build_relationships_page.py's own docstring
for the same "single pipeline, N consumers" pattern, established first).

Each of the three consumers imports this file as a module (the same
side-effect-import pattern build_relationships_page.py already used before
the split) and reads `payload` — or the narrower globals directly — rather
than recomputing any of it.

Regenerate all three pages:
    python3 build_player_benchmarking.py
    python3 build_team_benchmarking.py
    python3 build_relationships_page.py

VERIFY AFTER EVERY CHANGE (each page has its own deep verify — see
publish_dashboard.sh for the full extract+check+verify sequence):
    node verify_player_benchmarking.js
    node verify_team_benchmarking.js

A syntax error anywhere in either page's inline script kills the WHOLE page
silently - the HTML still looks complete, the file size looks right, and
nothing renders. That happened once: an over-escaped apostrophe terminated a
string early. Checking that strings are PRESENT in the file does not check
that they PARSE - both verify scripts execute their page's script against a
stubbed DOM and assert every panel builds with non-empty data.
"""
import importlib.util, json, math, os, sys, datetime as dt

import scoring

HERE = os.path.dirname(os.path.abspath(__file__))
SNAP = os.environ.get("FPL_SNAPSHOT") or os.path.join(HERE, "fpl_priors_2025_26_v2.json")
LAST16_PATH = os.path.join(HERE, "last16_starts.json")


def load_last16():
    """{(web_name, team): (starts, games)} — mirrors build_squad._load_last16.

    Kept as a SEPARATE loader rather than an import so this file still runs
    if build_squad.py's interface ever changes; the two must stay in step by
    convention (same last16_starts.json), not by code sharing.
    """
    try:
        payload = json.load(open(LAST16_PATH, encoding="utf-8"))
    except Exception:
        return {}, {}
    out = {}
    for key, v in payload.get("matched", {}).items():
        name, team = key.rsplit("|", 1)
        out[(name, team)] = (v["starts"], v["games"])
    return out, payload

POS = {1: "GKP", 2: "DEF", 3: "MID", 4: "FWD"}
CBIT_THRESH, CBIRT_THRESH = 10.0, 12.0
NEAR = 0.8                      # "near" = within 20% of the line
MIN_MINS = 450

# From squad.json via squad_state.py — the single source of truth. Was a
# hardcoded set here until 9 Aug 2026. Unlike the last16 loader below, this is
# DELIBERATELY coupled: there must be exactly one squad, so a private copy that
# survives an interface change is a bug, not resilience.
_sq_spec = importlib.util.spec_from_file_location(
    "squad_state", os.path.join(HERE, "squad_state.py"))
_squad_state = importlib.util.module_from_spec(_sq_spec)
_sq_spec.loader.exec_module(_squad_state)
SQUAD = _squad_state.load().name_set

FIXTURE_WINDOW_PATH = os.path.join(HERE, "fixture_window.json")


def load_fixture_window():
    """Read the SAME file fixture_adjust.py consults, so this panel can never
    quietly drift out of step with it. Found 9 Aug 2026: this file used to
    carry its own hardcoded "GW1-5" snapshot, independent of
    fixture_window.json's live "GW1-4" window — close enough in magnitude
    that the mismatch went unnoticed, exactly the class of cross-file sync
    bug this project has been bitten by before (see TEAM_CHANGE_LOG.md's
    fixture_adjust.py SQ note). Returns ({team: (att_x, def_x, games)}, stamp).
    """
    try:
        w = json.load(open(FIXTURE_WINDOW_PATH, encoding="utf-8"))
        return {k: tuple(v) for k, v in w["teams"].items()}, w
    except Exception:
        return None, None

FIXTURE_MAP, FIXTURE_STAMP = load_fixture_window()
if not FIXTURE_MAP:
    # Identical to fixture_adjust.py's own built-in fallback, so if both are
    # stale at once they are at least stale with the SAME wrong numbers.
    FIXTURE_MAP = {
        "TOT": (1.08, 0.99, 4), "BRE": (1.07, 0.99, 4), "ARS": (1.05, 1.03, 4),
        "LIV": (1.05, 0.69, 4), "BHA": (1.05, 1.19, 4), "NFO": (1.05, 0.99, 4),
        "LEE": (1.05, 0.96, 4), "BOU": (1.04, 1.20, 4), "EVE": (1.04, 1.10, 4),
        "HUL": (1.03, 1.22, 4), "NEW": (1.03, 1.05, 4), "CRY": (1.02, 0.88, 4),
        "MCI": (1.02, 1.14, 4), "FUL": (1.01, 1.11, 4), "MUN": (1.01, 1.00, 4),
        "IPS": (1.00, 1.07, 4), "CHE": (0.91, 0.93, 4), "SUN": (0.90, 0.85, 4),
        "AVL": (0.90, 0.99, 4), "COV": (0.88, 1.23, 4),
    }
# sorted for panel 5's chart labelling; games dropped, kept in FIXTURE_MAP for xp4_adj
FIXTURES = sorted(([t, v[0], v[1]] for t, v in FIXTURE_MAP.items()), key=lambda x: -x[1])
SCALE_WORKLOAD = True   # tougher opponent -> more defensive contributions & saves

def f(x):
    try: return float(x)
    except (TypeError, ValueError): return 0.0

def corr(a, b):
    if len(a) < 3: return 0.0
    ma, mb = sum(a)/len(a), sum(b)/len(b)
    num = sum((x-ma)*(y-mb) for x, y in zip(a, b))
    den = math.sqrt(sum((x-ma)**2 for x in a) * sum((y-mb)**2 for y in b))
    return num/den if den else 0.0

def estimate_k(samples, dispersion=1.0):
    """Mirrors fpl_research_mcp._estimate_k so the panel shows the REAL values."""
    pts = [(r, n) for r, n in samples if n >= 3 and r >= 0]
    if len(pts) < 20: return 10.0, None
    rates = [r for r, _ in pts]
    m = sum(rates)/len(rates)
    if m <= 0: return 10.0, None
    tot = sum((r-m)**2 for r in rates)/(len(rates)-1)
    samp = dispersion * (sum(r/n for r, n in pts)/len(pts))
    bet = tot - samp
    if bet <= 1e-9: return 40.0, (m, tot, samp, bet)
    return max(1.0, min(m/bet, 60.0)), (m, tot, samp, bet)

def degenerate(k):
    return any(abs(k-v) < 1e-9 for v in (10.0, 40.0, 60.0))

# ---------------------------------------------------------------- load
try:
    snap = json.load(open(SNAP, encoding="utf-8"))
except FileNotFoundError:
    sys.exit(f"Snapshot not found: {SNAP}\nRun --snapshot-priors first.")

teams = {int(k): v for k, v in (snap.get("teams") or {}).items()}
LAST16, LAST16_META = load_last16()
# xbonus90 (architecture review candidate #1). This pool didn't compute bonus
# at all before — expected_points()/expected_points_adj() below were two of
# the four independently-drifted copies of the scoring formula, and both had
# silently dropped the xbonus90 term because there was no bonus data on
# these rows to add. scoring.bonus_shrinkage() is the same computation
# build_squad.py's load() does; MIN_MINS here (450) is this page's own,
# broader gate, not build_squad's 900.
XBONUS_MAP, _XBONUS_K = scoring.bonus_shrinkage(snap.get("players") or {}, teams,
                                                 min_minutes=MIN_MINS)
rows = []
for pid, p in (snap.get("players") or {}).items():
    mins = p.get("minutes", 0) or 0
    if mins < MIN_MINS: continue
    n90 = mins/90.0
    cbi = p.get("clearances_blocks_interceptions", 0) or 0
    tk  = p.get("tackles", 0) or 0
    rec = p.get("recoveries", 0) or 0
    xgi = f(p.get("expected_goal_involvements"))
    ga  = (p.get("goals_scored", 0) or 0) + (p.get("assists", 0) or 0)
    name = p.get("web_name", "")
    team = teams.get(p.get("team"), "?")
    stp_season = (p.get("starts", 0) or 0) / 38.0
    hit = LAST16.get((name, team))
    if hit:
        starts16, games16 = hit
        stp, stp_src = starts16 / games16, "last16"
    else:
        stp, stp_src = stp_season, "season_fallback"
    rows.append(dict(
        id=int(pid), name=name, pos=POS.get(p["element_type"], "?"),
        team=team, n90=n90, mins=mins,
        starts=p.get("starts", 0) or 0, stp=stp, stp_season=stp_season,
        stp_src=stp_src,
        price=(p.get("now_cost") or 0)/10.0,
        xgi90=xgi/n90, delta=ga-xgi,
        xg90=f(p.get("expected_goals"))/n90, xa90=f(p.get("expected_assists"))/n90,
        cbit90=(cbi+tk)/n90, cbirt90=(cbi+tk+rec)/n90,
        xgc90=f(p.get("expected_goals_conceded"))/n90,
        cs=p.get("clean_sheets", 0) or 0,
        bps90=(p.get("bps") or 0)/n90,
        sv90=(p.get("saves") or 0)/n90,
        yellows=p.get("yellow_cards") or 0,
        own=f(p.get("selected_by_percent")),
        squad=name in SQUAD,
        xbonus90=XBONUS_MAP.get(pid, 0.0),
    ))

CBIT_HIT_THRESH = 10          # fixed across ALL positions, deliberately - see loader docstring
CACHE_CSV = os.path.join(HERE, ".cache_merged_gw.csv")
MIN_APPS_FOR_HIT = 5          # thinner samples are left unmatched, not misleadingly shown


def load_cbit_hitrates(pool):
    """Per-player 2025/26 per-match CBIT (clearances_blocks_interceptions +
    tackles) hit-rate against a FIXED 10+ line, for EVERY position - not the
    position-specific `defensive_contribution` rule dc_hit_rates.json uses
    (10 for DEF, 12 for MID/FWD, and recoveries included for the latter).
    Panel 2 is asking a narrower question - "if held to the DEFENDER'S own
    bar, who actually clears it reliably" - so the threshold does not move
    with position here.

    Kept as a SEPARATE loader rather than sharing build_dc_rates.py's, for the
    same reason load_last16() above is separate: this file must still run if
    that script's matching internals change. The name+team matching ladder
    (token-subset, then position, then club, then minutes) mirrors it exactly
    so the two never quietly disagree about who is who.

    Returns {(web_name, team_short): {"rate": pct, "apps": N, "hits": H}}.
    Tolerant of a missing archive (returns {}) - the panel just shows fewer
    points rather than failing the whole build.
    """
    import csv, io, re, unicodedata
    from collections import defaultdict
    try:
        csv_rows = list(csv.DictReader(io.StringIO(
            open(CACHE_CSV, encoding="utf-8", errors="replace").read())))
    except FileNotFoundError:
        return {}

    apps, pos_of, mins_by_team = defaultdict(list), {}, defaultdict(lambda: defaultdict(int))
    for r in csv_rows:
        m = int(r.get("minutes") or 0)
        if m < 60:
            continue                        # a cameo is a different population
        cbi = int(r.get("clearances_blocks_interceptions") or 0)
        tk = int(r.get("tackles") or 0)
        name = r["name"]
        apps[name].append(cbi + tk)
        pos_of[name] = {"GK": "GKP"}.get(r.get("position"), r.get("position"))
        mins_by_team[name][r.get("team")] += m

    def norm(s):
        s = unicodedata.normalize("NFKD", s)
        s = "".join(c for c in s if not unicodedata.combining(c))
        return [t for t in re.sub(r"[^a-z ]", " ", s.lower()).split() if t]

    FULL2CODE = {'Arsenal': 'ARS', 'Aston Villa': 'AVL', 'Bournemouth': 'BOU', 'Brentford': 'BRE',
     'Brighton': 'BHA', 'Burnley': 'BUR', 'Chelsea': 'CHE', 'Crystal Palace': 'CRY', 'Everton': 'EVE',
     'Fulham': 'FUL', 'Leeds': 'LEE', 'Liverpool': 'LIV', 'Man City': 'MCI', 'Man Utd': 'MUN',
     'Newcastle': 'NEW', "Nott'm Forest": 'NFO', 'Spurs': 'TOT', 'Sunderland': 'SUN',
     'West Ham': 'WHU', 'Wolves': 'WOL'}
    arch = [{"n": n, "tok": set(norm(n)), "pos": pos_of[n], "v": v,
             "club": FULL2CODE.get(max(mins_by_team[n], key=mins_by_team[n].get)) if mins_by_team[n] else None,
             "mins": sum(mins_by_team[n].values())}
            for n, v in apps.items()]

    out = {}
    for pl in pool:
        want = {t for t in norm(pl["name"]) if len(t) > 1}
        cands = [a for a in arch if want and want <= a["tok"]]
        if len(cands) > 1:
            cands = [a for a in cands if a["pos"] == pl["pos"]] or cands
        if len(cands) > 1:
            byteam = [a for a in cands if a["club"] == pl["team"]]
            cands = byteam if len(byteam) == 1 else sorted(cands, key=lambda a: -a["mins"])[:1]
        if len(cands) != 1:
            continue
        a = cands[0]
        v, N = a["v"], len(a["v"])
        if N < MIN_APPS_FOR_HIT:
            continue
        hits = sum(1 for x in v if x >= CBIT_HIT_THRESH)
        out[(pl["name"], pl["team"])] = {"rate": round(100.0 * hits / N, 1), "apps": N, "hits": hits}
    return out


_CBIT_HITS = load_cbit_hitrates(rows)
for r in rows:
    hit = _CBIT_HITS.get((r["name"], r["team"]))
    r["cbit_hit10"] = hit["rate"] if hit else None
    r["cbit_hit10_apps"] = hit["apps"] if hit else 0

D = [r for r in rows if r["pos"] == "DEF"]
M = [r for r in rows if r["pos"] == "MID"]
F_ = [r for r in rows if r["pos"] == "FWD"]
G = [r for r in rows if r["pos"] == "GKP"]


def blank_risk(r):
    """P(<=2 points), same definition captaincy_odds uses.

    Two disjoint routes to a blank:
      * does not start                      -> 0-1 pts
      * starts but no CS, no DC, no return  -> exactly 2 pts
    Clean sheet is exp(-xGC/90) and returns are Poisson on xGI/90, matching the
    rest of the system. The DC term is a threshold, not a rate - a defender who
    averages 10+ CBIT still misses it in low-volume matches, so it uses the
    player's OBSERVED per-match hit rate (roadmap A4), not a flat assumption.
    """
    import math
    p_start = min(max(r["stp"], 0.0), 0.98)
    p_cs = math.exp(-max(r["xgc90"], 0.05)) if r["pos"] in ("DEF", "GKP") else 0.0
    p_dc = scoring.p_threshold(r["cbit90"], CBIT_THRESH, key=f'{r["name"]}|{r["team"]}')
    p_ret = 1.0 - math.exp(-max(r["xgi90"], 0.0))
    played_blank = (1 - p_cs) * (1 - p_dc) * (1 - p_ret)
    return round(100.0 * ((1 - p_start) + p_start * played_blank), 1)


# expected_points / expected_points_adj / p_threshold used to be a THIRD and
# FOURTH hand-written copy of the scoring formula here (architecture review
# candidate #1) — both missing the xbonus90 term added to build_squad.py on
# 12 Aug, so this page's xP silently disagreed with squad.html's. Delegating
# to scoring.py fixes that structurally: one implementation, both terms.


def archetype_att(r, med_xgi):
    """Same two axes as midfielders. Forwards share the 12+ CBIRT threshold."""
    clears = r["cbirt90"] >= CBIRT_THRESH
    near = r["cbirt90"] >= CBIRT_THRESH * NEAR
    ceiling = r["xgi90"] > med_xgi
    if clears and ceiling: return "box-to-box"
    if clears:             return "holder"
    if ceiling:            return "attacker"
    if near:               return "borderline"
    return "limited"


def archetype_def(r, med_xgc):
    clears = r["cbit90"] >= CBIT_THRESH
    solid  = r["xgc90"] < med_xgc
    if clears and solid: return "BOTH"
    if clears:           return "workhorse"
    if solid:            return "cleansheet"
    if r["cbit90"] >= CBIT_THRESH*NEAR: return "borderline"
    return "avoid"

def archetype_mid(r, med_xgi):
    """Mirrors fpl_research_mcp.midfielder_screen exactly.

    Defensive axis is judged against the REAL 12+ CBIRT threshold; the attacking
    axis against the group median, because xGI has no absolute cut-off. Strict
    inequality on the median - an earlier `>=` misclassified players sitting
    exactly on it.
    """
    clears = r["cbirt90"] >= CBIRT_THRESH
    near = r["cbirt90"] >= CBIRT_THRESH * NEAR
    ceiling = r["xgi90"] > med_xgi
    if clears and ceiling: return "box-to-box"
    if clears:             return "holder"
    if ceiling:            return "attacker"
    if near:               return "borderline"
    return "limited"

med_xgc = sorted(r["xgc90"] for r in D)[len(D)//2]
for r in D: r["arch"] = archetype_def(r, med_xgc)
med_xgi_m = sorted(r["xgi90"] for r in M)[len(M)//2]
for r in M: r["arch"] = archetype_mid(r, med_xgi_m)
med_xgi_f = sorted(r["xgi90"] for r in F_)[len(F_)//2] if F_ else 0.0
for r in F_: r["arch"] = archetype_att(r, med_xgi_f)
# GOALKEEPERS HAVE NO ARCHETYPE. A2 on the roadmap is still undefined, and
# inventing one here to fill a column would be worse than an honest blank.
for r in G: r["arch"] = "—"
for r in rows: r["xp"] = round(scoring.expected_points(r), 2)
for r in rows: r["blank"] = blank_risk(r)
for r in rows:
    att_x, def_x, games = FIXTURE_MAP.get(r["team"], (1.0, 1.0, 4))
    r["xp4_adj"] = round(scoring.expected_points_scaled(
        r, att_x, def_x, scale_workload=SCALE_WORKLOAD) * games, 2)

# ---------------------------------------------------------------- stats
stats = {
    "def_n": len(D),
    "def_clear": sum(1 for r in D if r["cbit90"] >= CBIT_THRESH),
    "def_near": sum(1 for r in D if CBIT_THRESH*NEAR <= r["cbit90"] < CBIT_THRESH),
    "mid_n": len(M),
    "mid_clear": sum(1 for r in M if r["cbirt90"] >= CBIRT_THRESH),
    "mid_near": sum(1 for r in M if CBIRT_THRESH*NEAR <= r["cbirt90"] < CBIRT_THRESH),
    "corr_cbit_cs":  corr([r["cbit90"] for r in D], [float(r["cs"]) for r in D]),
    "corr_cbit_xgc": corr([r["cbit90"] for r in D], [r["xgc90"] for r in D]),
}
Gk = [r for r in G if r["mins"] >= 900]
stats["corr_saves_cs"] = corr([r["sv90"] for r in Gk], [float(r["cs"]) for r in Gk])
stats["gk_n"] = len(Gk)

# shrinkage diagnostics - before and after the dispersion fix
DISP_XG = 0.11
kpanel = []
for label, pool, metric, disp in (
        ("MID xGI",  M,  "xgi90",  DISP_XG),
        ("FWD xGI",  F_, "xgi90",  DISP_XG),
        ("DEF CBIT", D,  "cbit90", 1.0),
        ("GKP xGI",  G,  "xgi90",  DISP_XG)):
    S = [(r[metric], r["n90"]) for r in pool]
    kb, _ = estimate_k(S, 1.0)
    ka, parts = estimate_k(S, disp)
    kpanel.append(dict(label=label, n=len(S), k_before=kb, k_after=ka,
                       deg_before=degenerate(kb), deg_after=degenerate(ka),
                       mean=parts[0] if parts else 0, total=parts[1] if parts else 0,
                       samp=parts[2] if parts else 0, between=parts[3] if parts else 0,
                       disp=disp))

med_xgi_mid = sorted(r["xgi90"] for r in M)[len(M)//2]
for r in rows:
    for k in ("n90","stp","stp_season","xgi90","xg90","xa90","delta","cbit90","cbirt90","xgc90","bps90","sv90","own","price"):
        r[k] = round(r[k], 3)

n_last16 = sum(1 for r in rows if r["stp_src"] == "last16")
last16_info = dict(
    n_matched=n_last16, n_total=len(rows),
    window=f"GW{LAST16_META.get('window_gws', [23,38])[0]}-{LAST16_META.get('window_gws', [23,38])[1]}"
           if LAST16_META else "n/a",
    season=LAST16_META.get("season", "2025-26") if LAST16_META else "n/a",
    source=LAST16_META.get("source", "") if LAST16_META else "last16_starts.json not found",
)
fixture_info = dict(
    generated_for_gw=FIXTURE_STAMP.get("generated_for_gw") if FIXTURE_STAMP else None,
    horizon=(FIXTURE_STAMP.get("horizon", 4) if FIXTURE_STAMP else 4),
    source="fixture_window.json" if FIXTURE_STAMP else "built-in fallback (stale if this shows)",
)

# ------------------------------------------------------- CBIT avg vs hit-rate
# Panel 2, replaced 10 Aug 2026. Used to histogram the POINTS a season average
# converts to (via p_threshold); now plots the average directly against the
# REAL per-match 10+ CBIT hit-rate (roadmap A4 data), by position, so the gap
# between "averages above the line" and "reliably earns the line" is the shape
# of the scatter itself rather than a bucketed summary of it.
for _pos in ("DEF", "MID", "FWD"):
    _matched = [r for r in rows if r["pos"] == _pos and r["cbit_hit10"] is not None]
    stats[f"cbit_hit_n_{_pos.lower()}"] = len(_matched)
    stats[f"cbit_hit_corr_{_pos.lower()}"] = round(
        corr([r["cbit90"] for r in _matched], [r["cbit_hit10"] for r in _matched]), 3)
    # A correlation coefficient is undefined once one side has ~zero variance
    # (corr() returns 0.0 in that case, indistinguishable from "no relationship"
    # unless the max is checked too) - true for FWD, who essentially never
    # clear a DEFENDER'S 10+ CBIT line at all.
    stats[f"cbit_hit_max_{_pos.lower()}"] = round(
        max((r["cbit_hit10"] for r in _matched), default=0.0), 1)

# ------------------------------------------------ club-level xGC vs clean sheets
# Panel 8 (Player analysis). Team-level, not player-level: xGC/90 averaged across
# each club's GKP+DEF pool (the population that actually faces the shots),
# clean sheets taken from the primary goalkeeper (most minutes) as the club's
# season total — a keeper's clean sheet IS the team's, so this avoids double
# counting across five defenders who share one result.
club_xgc = {}
club_cs = {}
club_cs_mins = {}
for r in rows:
    if r["pos"] in ("GKP", "DEF"):
        club_xgc.setdefault(r["team"], []).append(r["xgc90"])
    if r["pos"] == "GKP":
        if r["team"] not in club_cs_mins or r["mins"] > club_cs_mins[r["team"]]:
            club_cs_mins[r["team"]] = r["mins"]
            club_cs[r["team"]] = r["cs"]
club_xgc_cs = sorted(
    ([team, round(sum(vals) / len(vals), 3), club_cs[team]]
     for team, vals in club_xgc.items() if team in club_cs),
    key=lambda x: x[1])

# ---- PLAYER BENCHMARKING'S DATA-SOURCE SELECTOR (prior/raw/shrunk) ---------
# `rows` above is the PRIOR variant only (2025/26 season, frozen snapshot).
# Same three estimators as optimise_squad.py's --estimator flag and the same
# scope (scoring.PRIORS_DISPERSION: xg90/xa90/xgi90/xgc90/cbit90/cbirt90/sv90,
# NOT stp/xbonus90 — see that constant's comment for why), computed here
# independently rather than imported from build_squad.py, for the same
# "separate hand-maintained copy" reason scoring.py's own docstring gives:
# build_squad.py pulls in its own gates/pool (900-min, contaminated-prior
# filter, ROLE_INTEL) that don't apply to this page's broader 450-min pool.
_current_cache = None


def _fetch_current_season():
    global _current_cache
    if _current_cache is not None:
        return _current_cache
    import urllib.request
    try:
        req = urllib.request.Request(
            "https://fantasy.premierleague.com/api/bootstrap-static/",
            headers={"User-Agent": "fpl-build-dashboard/1.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        _current_cache = {str(e["id"]): e for e in data.get("elements", [])}
    except Exception as exc:
        print(f"  ESTIMATOR: live bootstrap-static fetch failed ({exc}) - "
              f"raw/shrunk both fall back to prior-only values for every "
              f"player this run.", file=sys.stderr)
        _current_cache = {}
    return _current_cache


def _current_rates(el):
    """Current-season per-90 rates (plus raw goals+assists, for `delta`) from
    a LIVE bootstrap element. `el` may be {} (not found, or the fetch itself
    failed) - returns all-zero/n90=0, which shrink_rate() then treats as "no
    current data, keep the baseline" rather than a divide."""
    m = el.get("minutes", 0) or 0
    n90 = m / 90.0
    if n90 <= 0:
        return dict(n90=0.0, ga=0, xg90=0.0, xa90=0.0, xgi90=0.0, xgc90=0.0,
                    cbit90=0.0, cbirt90=0.0, sv90=0.0)
    cbi = el.get("clearances_blocks_interceptions", 0) or 0
    tk, rec = el.get("tackles", 0) or 0, el.get("recoveries", 0) or 0
    return dict(
        n90=n90, ga=(el.get("goals_scored", 0) or 0) + (el.get("assists", 0) or 0),
        xg90=f(el.get("expected_goals")) / n90, xa90=f(el.get("expected_assists")) / n90,
        xgi90=f(el.get("expected_goal_involvements")) / n90,
        xgc90=f(el.get("expected_goals_conceded")) / n90,
        cbit90=(cbi + tk) / n90, cbirt90=(cbi + tk + rec) / n90,
        sv90=(el.get("saves") or 0) / n90,
    )


_current = _fetch_current_season()
_current_by_id = {r["id"]: _current_rates(_current.get(str(r["id"]), {})) for r in rows}

# One k per metric, pool-wide (same scope decision build_squad.py's load()
# makes for this first activation — see METHODOLOGY_ALTERNATIVES.md A0.2
# "Phase 2" for what a later review should reconsider if this looks wrong).
_shrunk_ks = {}
for _metric, _disp in scoring.PRIORS_DISPERSION.items():
    _samples = [(_current_by_id[r["id"]][_metric], _current_by_id[r["id"]]["n90"]) for r in rows]
    _shrunk_ks[_metric] = scoring.estimate_k_priors(_samples, dispersion=_disp)


def _build_estimator_variant(estimator):
    """Recompute the estimator-sensitive fields for every row, then re-derive
    everything downstream of them in the SAME ORDER the prior computation
    above used (archetype, xP, xP4_adj) - so raw/shrunk can never silently
    disagree with prior about how those are derived, only about the inputs.
    `estimator` is "raw" or "shrunk"; prior needs no variant, see below.
    """
    vrows = [dict(r) for r in rows]
    for rv in vrows:
        cur = _current_by_id[rv["id"]]
        if estimator == "shrunk":
            for metric in scoring.PRIORS_DISPERSION:
                rv[metric] = scoring.shrink_rate(cur[metric], cur["n90"], rv[metric], _shrunk_ks[metric])
            rv["delta"] = cur["ga"] - rv["xgi90"] * cur["n90"]
        else:  # raw - ungated, a near-zero-minutes rate is unusable, see
               # scoring.MIN_N90_RAW's comment. Below the gate, keep prior.
            if cur["n90"] >= scoring.MIN_N90_RAW:
                for metric in scoring.PRIORS_DISPERSION:
                    rv[metric] = cur[metric]
                rv["delta"] = cur["ga"] - rv["xgi90"] * cur["n90"]

    Dv = [r for r in vrows if r["pos"] == "DEF"]
    Mv = [r for r in vrows if r["pos"] == "MID"]
    Fv = [r for r in vrows if r["pos"] == "FWD"]
    med_xgc_v = sorted(r["xgc90"] for r in Dv)[len(Dv) // 2]
    for r in Dv: r["arch"] = archetype_def(r, med_xgc_v)
    med_xgi_m_v = sorted(r["xgi90"] for r in Mv)[len(Mv) // 2]
    for r in Mv: r["arch"] = archetype_mid(r, med_xgi_m_v)
    med_xgi_f_v = sorted(r["xgi90"] for r in Fv)[len(Fv) // 2] if Fv else 0.0
    for r in Fv: r["arch"] = archetype_att(r, med_xgi_f_v)
    for r in vrows:
        r["xp"] = round(scoring.expected_points(r), 2)
        att_x, def_x, games = FIXTURE_MAP.get(r["team"], (1.0, 1.0, 4))
        r["xp4_adj"] = round(scoring.expected_points_scaled(
            r, att_x, def_x, scale_workload=SCALE_WORKLOAD) * games, 2)
    for r in vrows:
        for k in ("xgi90", "xg90", "xa90", "delta", "cbit90", "cbirt90", "xgc90", "sv90"):
            r[k] = round(r[k], 3)
    return dict(rows=vrows, med_xgc=round(med_xgc_v, 4), med_xgi_m=round(med_xgi_m_v, 4),
                stats=dict(mid_n=len(Mv), mid_clear=sum(1 for r in Mv if r["cbirt90"] >= CBIRT_THRESH)))


estimators = {
    "prior": dict(rows=rows, med_xgc=round(med_xgc, 4), med_xgi_m=round(med_xgi_m, 4),
                  stats=dict(mid_n=stats["mid_n"], mid_clear=stats["mid_clear"])),
    "raw": _build_estimator_variant("raw"),
    "shrunk": _build_estimator_variant("shrunk"),
}
estimator_live = bool(_current)   # False -> raw/shrunk silently equal prior; UI should say so

# The full union of what any consumer needs — build_player_benchmarking.py
# and build_team_benchmarking.py each pick their own subset of keys out of
# this before writing their page (see either file); build_relationships_page.py
# reads it directly, as it already did before the split.
payload = dict(rows=rows, med_xgi_m=round(med_xgi_m,4), fixtures=FIXTURES, stats=stats, kpanel=kpanel,
               club_xgc_cs=club_xgc_cs,
               med_xgc=med_xgc, med_xgi_mid=med_xgi_mid,
               captured=snap.get("captured_utc", "")[:19],
               season=snap.get("season_described", "?"),
               generated=dt.datetime.now().strftime("%Y-%m-%d %H:%M"),
               last16=last16_info, fixture_info=fixture_info,
               estimators=estimators, estimator_live=estimator_live)

