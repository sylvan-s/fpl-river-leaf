#!/usr/bin/env python3
"""Generate the FPL methodology diagnostic dashboard.

Reads the frozen prior-season snapshot and emits ONE self-contained HTML file.
Every panel exists to test a claim in the methodology - not to re-display a
table. If a panel cannot change a decision or expose an error, it should be cut.

Regenerate:  python3 build_dashboard.py

VERIFY AFTER EVERY CHANGE:
    python3 -c "h=open('FPL_DIAGNOSTICS.html').read(); \
open('dash.js','w').write('const DATA'+h.split(chr(60)+'script'+chr(62)+chr(10)+'const DATA',1)[1].split(chr(60)+'/script'+chr(62))[0])"
    node --check dash.js && node verify_dashboard.js

The extract MUST go to ./dash.js, not /tmp — verify_dashboard.js does
`require('./dash.js')`. Writing the fresh extract to /tmp meant `node --check`
validated the new build while verify_dashboard.js silently re-verified whatever
stale ./dash.js was left over from an earlier run. Fixed 9 Aug 2026; the bug
was invisible until a clean clone had no stale dash.js to fall back on.

A syntax error anywhere in the inline script kills the WHOLE page silently -
the HTML still looks complete, the file size looks right, and nothing renders.
That happened once: an over-escaped apostrophe terminated a string early.
Checking that strings are PRESENT in the file does not check that they PARSE.
verify_dashboard.js executes the script against a stubbed DOM and asserts all
five panels build with non-empty data.
"""
import importlib.util, json, math, os, sys, datetime as dt

HERE = os.path.dirname(os.path.abspath(__file__))
SNAP = os.environ.get("FPL_SNAPSHOT") or os.path.join(HERE, "fpl_priors_2025_26_v2.json")
OUT  = os.environ.get("FPL_DASH_OUT") or os.path.join(HERE, "FPL_DIAGNOSTICS.html")
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

_bs_spec = importlib.util.spec_from_file_location(
    "bs_for_dash", os.path.join(HERE, "build_squad.py"))
_bs = importlib.util.module_from_spec(_bs_spec)
_bs_spec.loader.exec_module(_bs)

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
        saves90=(p.get("saves") or 0)/n90,
        yellows=p.get("yellow_cards") or 0,
        own=f(p.get("selected_by_percent")),
        squad=name in SQUAD,
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
    p_dc = p_threshold(r["cbit90"], CBIT_THRESH, key=f'{r["name"]}|{r["team"]}')
    p_ret = 1.0 - math.exp(-max(r["xgi90"], 0.0))
    played_blank = (1 - p_cs) * (1 - p_dc) * (1 - p_ret)
    return round(100.0 * ((1 - p_start) + p_start * played_blank), 1)



# ---- expected points, identical to build_squad.expected_points ---------------
GOAL_PTS = {"GKP": 10, "DEF": 6, "MID": 5, "FWD": 4}
ASSIST_PTS = 3
CS_PTS = {"GKP": 4, "DEF": 4, "MID": 1, "FWD": 0}
DC_PTS = 2
DC_THRESH_POS = {"GKP": 99.0, "DEF": 10.0, "MID": 12.0, "FWD": 12.0}


# Roadmap A4. This file used to hold a FOURTH copy of the step function, so the
# published dashboard kept showing the superseded estimator after build_squad.py
# had moved on. Delegate instead — one implementation, no drift.
def p_threshold(mean, thresh, key=None):
    return _bs.p_threshold(mean, thresh, key=key)


def expected_points(r):
    pos = r["pos"]
    dc = r["cbit90"] if pos == "DEF" else r["cbirt90"]
    p_cs = math.exp(-max(r["xgc90"], 0.05)) if CS_PTS[pos] else 0.0
    xp = 2 + GOAL_PTS[pos]*r["xg90"] + ASSIST_PTS*r["xa90"] + CS_PTS[pos]*p_cs
    xp += DC_PTS * p_threshold(dc, DC_THRESH_POS[pos],
                               key=f'{r["name"]}|{r["team"]}')
    if pos in ("GKP", "DEF"): xp -= r["xgc90"]/2
    if pos == "GKP":          xp += r["saves90"]/3
    return round(xp, 2)


def expected_points_adj(r, att_x, def_x):
    """Same scoring table as expected_points(), inputs scaled by opponent
    strength. Mirrors fixture_adjust.adjust() term-for-term so the two files
    can never quietly disagree about what "fixture-adjusted" means."""
    pos = r["pos"]
    xg = r["xg90"] * att_x
    xa = r["xa90"] * att_x
    xgc = r["xgc90"] * def_x
    p_cs = math.exp(-max(xgc, 0.05)) if CS_PTS[pos] else 0.0
    dc = r["cbit90"] if pos == "DEF" else r["cbirt90"]
    saves = r["saves90"]
    if SCALE_WORKLOAD:
        dc *= def_x
        saves *= def_x
    xp = 2 + GOAL_PTS[pos]*xg + ASSIST_PTS*xa + CS_PTS[pos]*p_cs
    xp += DC_PTS * p_threshold(dc, DC_THRESH_POS[pos],
                               key=f'{r["name"]}|{r["team"]}')
    if pos in ("GKP", "DEF"): xp -= xgc/2
    if pos == "GKP":          xp += saves/3
    return xp


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
for r in rows: r["xp"] = expected_points(r)
for r in rows: r["blank"] = blank_risk(r)
for r in rows:
    att_x, def_x, games = FIXTURE_MAP.get(r["team"], (1.0, 1.0, 4))
    r["xp4_adj"] = round(expected_points_adj(r, att_x, def_x) * games, 2)

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
stats["corr_saves_cs"] = corr([r["saves90"] for r in Gk], [float(r["cs"]) for r in Gk])
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
    for k in ("n90","stp","stp_season","xgi90","xg90","xa90","delta","cbit90","cbirt90","xgc90","bps90","saves90","own","price"):
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

payload = dict(rows=rows, med_xgi_m=round(med_xgi_m,4), fixtures=FIXTURES, stats=stats, kpanel=kpanel,
               med_xgc=med_xgc, med_xgi_mid=med_xgi_mid,
               captured=snap.get("captured_utc", "")[:19],
               season=snap.get("season_described", "?"),
               generated=dt.datetime.now().strftime("%Y-%m-%d %H:%M"),
               last16=last16_info, fixture_info=fixture_info)

HTML = open(os.path.join(HERE, "template.html"), encoding="utf-8").read()
# Shared chrome, inlined so the output stays a single self-contained file.
_ps_spec = importlib.util.spec_from_file_location(
    "page_shell", os.path.join(HERE, "page_shell.py"))
_page_shell = importlib.util.module_from_spec(_ps_spec)
_ps_spec.loader.exec_module(_page_shell)
HTML = (HTML.replace("/*__CSS__*/", _page_shell.css())
            .replace("<!--__NAV__-->", _page_shell.nav("analysis")))
with open(OUT, "w", encoding="utf-8") as fh:
    fh.write(HTML.replace("/*__DATA__*/null", json.dumps(payload)))
print(f"written: {OUT}  ({os.path.getsize(OUT)/1024:.0f} KB)")
print(f"  players {len(rows)} | DEF {len(D)} MID {len(M)} FWD {len(F_)} GKP {len(G)}")

