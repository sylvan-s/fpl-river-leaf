#!/usr/bin/env python3
"""Canonical expected-points scoring — the single source of truth for
expected_points(), the DC-threshold estimator, and the bonus-points
shrinkage that produces xbonus90.

EXTRACTED 14 Aug 2026 (architecture review candidate #1). Before this, the
formula existed as four independently-written copies:

  - build_squad.py:expected_points()        (had xbonus90)
  - build_dashboard.py:expected_points()     (did NOT have xbonus90 — bug)
  - build_dashboard.py:expected_points_adj() (did NOT have xbonus90 — bug)
  - fixture_adjust.py:adjust()               (had xbonus90, delegated to
                                               build_squad for constants/
                                               p_threshold, but re-assembled
                                               the formula itself)

build_dashboard.py's own comment on the p_threshold delegation ("this file
used to hold a FOURTH copy of the step function, so the published dashboard
kept showing the superseded estimator") shows this exact class of bug
recurring. This module ends the copies: build_squad.py, build_dashboard.py
and fixture_adjust.py all import it now.

Pure functions only, plus one small piece of reference-data I/O
(dc_hit_rates.json, a static table checked into the repo) that every one of
the four copies was already doing independently. No sys.argv reads — every
behaviour switch (`empirical`) is an explicit parameter. Defaults match the
pipeline's long-standing defaults (empirical DC ON).

Deliberately NOT unified with fpl_research_mcp.py's `_estimate_k` — that one
is a more general Poisson-Gamma estimator (takes an `empirical_var`
override) shared by five live screen tools (xgi, cbit, goals...). The
bonus-specific estimator here solves a narrower problem and was already a
hand-maintained "local copy... because importing [the MCP module] would pull
in its whole server/tool surface for ~15 lines of arithmetic" — see
build_squad.py's prior docstring. Left fpl_research_mcp.py alone: unifying
it wasn't needed to fix the drift bug this extraction targets, and touching
a 3000-line live MCP server mid-season is a real behavioural risk for a
theoretical win. See the architecture review for the full reasoning.
"""
import json, math, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))

POS = {1: "GKP", 2: "DEF", 3: "MID", 4: "FWD"}

# ---- scoring table (SELECTION_FRAMEWORK.md) ---------------------------------
GOAL   = {"GKP": 10, "DEF": 6, "MID": 5, "FWD": 4}
ASSIST = 3
CS     = {"GKP": 4, "DEF": 4, "MID": 1, "FWD": 0}
DC_PTS = 2
DC_THRESH_POS = {"GKP": 99.0, "DEF": 10.0, "MID": 12.0, "FWD": 12.0}
APPEARANCE = 2                   # 60+ minutes
SAVES_PER_POINT = 3
GC_PER_MINUS = 2                 # -1 per 2 goals conceded (GKP and DEF only)

# ---- bonus (roadmap A1, added 12 Aug 2026) -----------------------------------
BONUS_DISPERSION = 1.0
CBI_HEAVY_THRESH = 6.0           # CBI(not CBIT)/90 above which a defender counts as "CBI-heavy"
CBI_HAIRCUT = 0.95               # UNSOURCED magnitude, bounded — see build_squad.py's prior note
TACKLE_BUMP = 1.05               # UNSOURCED magnitude, bounded — 2026/27 BPS change

# The three values estimate_k_bonus() returns when it could NOT fit k from
# variance (too few points, non-positive between-player variance, or a ratio
# outside [1,60]) rather than deriving it. Named once here so the "treat as
# unvalidated" check below and any downstream consumer (the squad page's
# scoring-route composition chart, ADR 0001) test the same three numbers
# instead of a second hand-copied tuple silently drifting from this one.
BONUS_FALLBACK_KS = (10.0, 40.0, 60.0)

# ---- empirical defensive-contribution hit rate (roadmap A4) -----------------
_DC_PATH = os.path.join(HERE, "dc_hit_rates.json")
_DC_RATES, _DC_DOC, _DC_WARNED = None, None, False
_PRIOR_CACHE = {}


def _dc_rates():
    global _DC_RATES, _DC_DOC
    if _DC_RATES is None:
        try:
            _DC_DOC = json.load(open(_DC_PATH, encoding="utf-8"))
            _DC_RATES = _DC_DOC["players"]
        except Exception:
            _DC_DOC, _DC_RATES = {}, {}
    return _DC_RATES


def _prior_at(pos, eff):
    """Positional mean hit rate AT this effective threshold, and shrinkage k.

    Recomputed per threshold because a fixture-scaled line moves the whole
    population, not just one player — shrinking toward a fixed prior would
    drag every scaled estimate back toward the unscaled world.
    """
    ck = (pos, round(eff, 3))
    if ck not in _PRIOR_CACHE:
        rs = [sum(1 for x in r["counts"] if x >= eff) / len(r["counts"])
              for r in _dc_rates().values()
              if r["pos"] == pos and r["apps"] >= 20]
        k = (_DC_DOC.get("priors", {}).get(pos, {}) or {}).get("k_pseudo_matches", 5.0)
        _PRIOR_CACHE[ck] = ((sum(rs) / len(rs)) if rs else 0.3, k)
    return _PRIOR_CACHE[ck]


def p_threshold_legacy(mean, thresh):
    """SUPERSEDED by the empirical hit rate. Kept for the GW10 comparison and
    for callers that explicitly pass empirical=False (what --legacy-dc now
    maps to, explicitly, rather than via an ambient sys.argv read).

    Measured against 2025/26 per-match counts this was wrong three ways: the
    0.80-1.00x band assumed 0.20 against an actual 0.41; the 1.30x band was
    unreachable and never fired; everyone above the line scored an identical
    0.55 while real hit rates inside that band ran 52%-70%. See
    METHODOLOGY_ALTERNATIVES.md A4.
    """
    if mean >= thresh * 1.30: return 0.75
    if mean >= thresh:        return 0.55
    if mean >= thresh * 0.80: return 0.20
    return 0.05


def p_threshold(mean, thresh, key=None, empirical=True):
    """P(clearing the DC line in a given match).

    empirical=True (the pipeline default): prefers the player's OBSERVED
    per-match hit rate, shrunk toward the positional prior — the award is a
    per-match threshold, so the hit rate is the quantity itself rather than
    an estimate of it. Falls back to the step function only where the player
    is absent from the archive, or where empirical=False is passed explicitly.
    """
    global _DC_WARNED
    if not empirical:
        return p_threshold_legacy(mean, thresh)
    rec = _dc_rates().get(key or "")
    if rec:
        # `mean` arrives already fixture-scaled by the caller, so recover the
        # scale and move the THRESHOLD by the inverse: P(X >= thresh/scale).
        scale = (mean / rec["mean_dc"]) if rec.get("mean_dc") else 1.0
        scale = min(max(scale, 0.5), 2.0)          # guard against a bad ratio
        eff = thresh / scale
        m, k = _prior_at(rec["pos"], eff)
        hits = sum(1 for x in rec["counts"] if x >= eff)
        return (hits + m * k) / (rec["apps"] + k)
    if not _DC_WARNED and not _dc_rates():
        _DC_WARNED = True
        print("  NOTE: dc_hit_rates.json not found — using the superseded "
              "p_threshold step function. Run build_dc_rates.py.", file=sys.stderr)
    return p_threshold_legacy(mean, thresh)


def estimate_k_bonus(samples):
    """Poisson-Gamma method of moments, for bonus-point shrinkage specifically.

    NOT the same function as fpl_research_mcp._estimate_k — see this module's
    docstring for why that one was left alone.
    """
    pts = [(r, n) for r, n in samples if n >= 3 and r >= 0]
    if len(pts) < 20:
        return 10.0
    rates = [r for r, _ in pts]
    m = sum(rates) / len(rates)
    if m <= 0:
        return 10.0
    total_var = sum((r - m) ** 2 for r in rates) / (len(rates) - 1)
    sampling_var = BONUS_DISPERSION * (sum(r / n for r, n in pts) / len(pts))
    between_var = total_var - sampling_var
    if between_var <= 1e-9:
        return 40.0
    return max(1.0, min(m / between_var, 60.0))


def bonus_shrinkage(players, teams, min_minutes=900):
    """{pid: xbonus90} for every min_minutes+ player, plus the estimated k.

    shrunk = (n90*raw + k*baseline) / (n90+k), baseline = team x position
    mean bonus90, falling back to position mean where the team+pos group is
    thin (<3 players).
    """
    rows = []
    for pid, p in players.items():
        m = p.get("minutes", 0) or 0
        if m < min_minutes:
            continue
        n90 = m / 90.0
        cbi = p.get("clearances_blocks_interceptions", 0) or 0
        rows.append(dict(
            pid=pid, pos=POS[p["element_type"]], team=teams.get(p.get("team"), "?"),
            n90=n90, raw=(p.get("bonus", 0) or 0) / n90, cbi90=cbi / n90))

    k = estimate_k_bonus([(r["raw"], r["n90"]) for r in rows])
    if k in BONUS_FALLBACK_KS:
        print(f"  NOTE: xbonus90 shrinkage k={k:.1f} is a fallback/clamp, not "
              f"derived from variance — treat xbonus90 as unvalidated until "
              f"this is investigated.", file=sys.stderr)

    def _mean(sel):
        vals = [x["raw"] for x in sel]
        return sum(vals) / len(vals) if vals else None

    out = {}
    for r in rows:
        same_team_pos = [x for x in rows if x["pos"] == r["pos"] and x["team"] == r["team"]]
        base = _mean(same_team_pos) if len(same_team_pos) >= 3 else None
        if base is None:
            base = _mean([x for x in rows if x["pos"] == r["pos"]]) or 0.0
        shrunk = (r["n90"] * r["raw"] + k * base) / (r["n90"] + k)
        mult = 1.0
        if r["pos"] == "DEF" and r["cbi90"] >= CBI_HEAVY_THRESH:
            mult = CBI_HAIRCUT
        elif r["pos"] in ("MID", "FWD"):
            mult = TACKLE_BUMP
        out[r["pid"]] = shrunk * mult
    return out, k


def expected_points(r, empirical=True):
    """Expected FPL points per 90. THE implementation — every caller imports
    this rather than re-deriving it. Every coefficient is a rule, not a
    choice. Row `r` needs: pos, cbit90, cbirt90, xg90, xa90, xgc90, sv90
    (GKP only), and optionally xbonus90 (defaults to 0 if absent, so callers
    that haven't computed bonus yet still get a valid — just bonus-less —
    score instead of a KeyError).

    p_cs is computed here from xgc90 rather than read off a precomputed
    r["p_cs"] — build_dashboard.py's pool never had that field (its own,
    now-removed local expected_points() computed it inline each call), which
    is exactly the kind of implicit precondition that makes an interface
    shallow. Callers may still carry their own r["p_cs"] for other uses
    (build_squad.py does); this function no longer depends on it existing.
    """
    pos = r["pos"]
    dc_metric = r["cbit90"] if pos == "DEF" else r["cbirt90"]
    p_cs = math.exp(-max(r["xgc90"], 0.05)) if CS[pos] else 0.0
    xp = APPEARANCE
    xp += GOAL[pos] * r["xg90"] + ASSIST * r["xa90"]
    xp += CS[pos] * p_cs
    xp += DC_PTS * p_threshold(dc_metric, DC_THRESH_POS[pos],
                                key=f'{r["name"]}|{r["team"]}', empirical=empirical)
    if pos in ("GKP", "DEF"):
        xp -= r["xgc90"] / GC_PER_MINUS
    if pos == "GKP":
        xp += r["sv90"] / SAVES_PER_POINT
    # Bonus is already in point units — no coefficient, unlike goals/saves.
    xp += r.get("xbonus90", 0.0)
    return xp


def expected_points_scaled_breakdown(r, att_x, def_x, scale_workload=True, empirical=True):
    """Same inputs as expected_points_scaled(), but returns the additive
    terms as a labelled dict instead of collapsing them to one number.

    Added 14 Aug 2026 for the squad page's scoring-route composition chart
    (ADR 0001 — docs/adr/0001-xi-scoring-route-composition-chart.md). Two
    deliberate departures from the raw formula, both explained in that ADR:

      - The goals-conceded penalty (GKP/DEF only, always <= 0) is NOT its own
        entry. A standalone negative term breaks a non-negative composition
        chart, so it's netted into "defensive_contribution" and that category
        is understood as NET defensive value, not the raw DC-points-only
        figure the CBIT screens show.
      - Every category is returned even when it's structurally zero for a
        position (e.g. clean_sheets for a FWD, saves for an outfield player)
        so callers can sum a fixed six-key set without per-position branching.

    expected_points_scaled() below is defined as sum(this dict) — one
    formula, not two independently-maintained copies that can drift.
    """
    pos = r["pos"]
    xg = r["xg90"] * att_x            # opponent defence scales what you score
    xa = r["xa90"] * att_x
    xgc = r["xgc90"] * def_x          # opponent attack scales what you concede
    p_cs = math.exp(-max(xgc, 0.05)) if CS[pos] else 0.0
    dc_metric = r["cbit90"] if pos == "DEF" else r["cbirt90"]
    saves = r["sv90"]
    if scale_workload:
        dc_metric *= def_x            # tougher opponent -> more defensive work
        saves *= def_x                # and more shots to save

    dc_pts = DC_PTS * p_threshold(dc_metric, DC_THRESH_POS[pos],
                                   key=f'{r["name"]}|{r["team"]}', empirical=empirical)
    gc_penalty = -(xgc / GC_PER_MINUS) if pos in ("GKP", "DEF") else 0.0
    saves_pts = (saves / SAVES_PER_POINT) if pos == "GKP" else 0.0

    return {
        "appearance": APPEARANCE,
        "goal_involvement": GOAL[pos] * xg + ASSIST * xa,
        "clean_sheets": CS[pos] * p_cs,
        "defensive_contribution": dc_pts + gc_penalty,   # netted — see docstring
        "saves": saves_pts,
        # xbonus90 carried through UNSCALED — no sourced fixture channel yet
        # for bonus (see the prior note in fixture_adjust.py: inventing one
        # would be exactly the kind of silent, untested coefficient this
        # project has already had to correct twice).
        "bonus": r.get("xbonus90", 0.0),
    }


def expected_points_scaled(r, att_x, def_x, scale_workload=True, empirical=True):
    """Same scoring table as expected_points(), inputs scaled by opponent
    strength. One implementation for both fixture_adjust.py's xP_adj and the
    dashboard's fixture-swing panel, instead of two independently-written
    copies of the same scaling logic. Defined as the sum of
    expected_points_scaled_breakdown()'s terms — see that function if you
    need the terms individually rather than their total.
    """
    return sum(expected_points_scaled_breakdown(
        r, att_x, def_x, scale_workload=scale_workload, empirical=empirical).values())
