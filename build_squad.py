#!/usr/bin/env python3
"""Squad selection from first principles — the gates in SELECTION_FRAMEWORK.md.

This is the code that actually built the 9 Aug 2026 squad. It existed only as an
ad-hoc script when that squad went live, which meant the live team was produced
by a procedure nobody could re-run. That is the same failure as an inherited
player: it looks justified but cannot be reproduced.

    python3 build_squad.py                 # squad without Haaland (his preference)
    python3 build_squad.py --haaland       # allow Haaland
    python3 build_squad.py --gate 0.70     # loosen the availability gate
    python3 build_squad.py --season-starts # gate 2 on full-season starts, not last-16

NOT a live tool. It reads the frozen prior-season snapshot, so from GW1 it should
read player_gw from SQLite instead — see METHODOLOGY_ALTERNATIVES.md B6.

GATE 2 CHANGED 9 Aug 2026 — starts% is now measured over the LAST 16 GAMEWEEKS
of 2025/26 (GW23-38), not the full 38-GW season. Sylvan's point: a lot changes
over a season — managers get sacked, injuries resolve, pecking orders shift —
and a player's minutes share in August tells you less about his August-2026
role than his minutes share in April/May. The full-season number was pinned
in a Jan-2026 snapshot of the squad, not the one that actually finished it.

There is no per-gameweek data for last season anywhere in this project's own
pipeline — `player_gw` in the SQLite cache only ever holds the CURRENT season,
and it's pre-season (0 rows). The last-16 figures come from a third-party
archive (vaastav/Fantasy-Premier-League on GitHub, which mirrors the official
FPL API GW-by-GW), matched to our players by name — see last16_starts.json
and its `unmatched_current_squad_pool` list. That match is NOT the official
FPL API; treat it as a well-sourced but externally-derived input, and re-verify
before leaning on it for a single close gate decision. 5 of 267 players in the
900+-minute pool couldn't be matched with confidence and fall back to the
full-season rate — `--season-starts` reproduces the pre-9-Aug gate exactly.

ADDED 12 Aug 2026 — xbonus90 (roadmap A1). Bonus was the highest-priority known
gap: the Rice case showed real value hiding in clean sheets and bonus that the
xGI screen cannot see. Unlike xG or CBIT, bonus does not need modelling from
first principles — FPL already resolves the top-3-BPS-per-match competition
and reports the outcome directly (`bonus`, points actually awarded), so it is
shrunk the same way every other rate in the model is shrunk, not simulated.
Bonus points are already in point units, so xbonus90 is added to xP with no
coefficient — see `_bonus_shrinkage()` and `expected_points()`. A bounded,
DIRECTION-sourced-but-MAGNITUDE-unsourced adjustment is layered on top for the
2026/27 Bonus Points System change (CBI reweighted 1-per-3, not 1-per-2; the
tackled-penalty removed) — same evidentiary standard as the Rice `stp`
override in ROLE_INTEL.md. Pass `--no-bonus` to rebuild without it, for
comparison. Re-derive from real 2026/27 BPS data as soon as GW1-5 exist.
"""
import json, math, os, sys
import importlib.util as _il

HERE = os.path.dirname(os.path.abspath(__file__))
SNAP = os.path.join(HERE, "fpl_priors_2025_26_v2.json")
LAST16_PATH = os.path.join(HERE, "last16_starts.json")

# Roadmap "adjustments layer", 10 Aug 2026. Loaded via file path (not `import
# intel_adjust`) for the same reason every other cross-file import in this repo
# is - build_squad.py is itself loaded via spec_from_file_location by
# fixture_adjust.py, optimise_squad.py and fetch_gw_history.py, so a plain
# import cannot be relied on to resolve relative to this file's directory.
_ia_spec = _il.spec_from_file_location("intel_adjust", os.path.join(HERE, "intel_adjust.py"))
ia = _il.module_from_spec(_ia_spec)
_ia_spec.loader.exec_module(ia)

# ---- GATES (see SELECTION_FRAMEWORK.md "The gates") -------------------------
MIN_MINUTES = 900       # gate 1 - below this a per-90 rate is noise
GATE_XI     = 0.75      # gate 2 - start rate for anyone in the XI
GATE_BENCH  = 0.60      # gate 2 - relaxed for fodder, who still must PLAY
BUDGET      = 100.0
SQUAD_SHAPE = {1: 2, 2: 5, 3: 5, 4: 3}
MAX_PER_CLUB = 3


INTEL_PATH = os.path.join(HERE, "ROLE_INTEL.md")
_contam_cache = None


def _contaminated() -> dict:
    """{name: destination_team_code} from ROLE_INTEL.md's ```contaminated
    fence — mid-season club transfers whose 2025/26 record belongs to the
    OLD club.

    ADDED 12 Aug 2026. This gap was named explicitly in TEAM_CHANGE_LOG.md's
    10 Aug entry — "build_squad.py's load() never applies the `contaminated`
    fence correction that fpl_research_mcp.py's _baseline() does; worth
    closing before it costs a real transfer next time" — and surfaced for
    real the first time a full rebuild was run after that note: the ILP
    optimiser picked Senesi, Welbeck and Dubravka, three of the exact players
    removed from the squad on 9-10 Aug specifically because their record
    belongs to a different club. That is Tier 1 under
    SELECTION_FRAMEWORK.md — "the model is not wrong here, it is
    INAPPLICABLE... the player is either excluded or assessed entirely on
    Tier-1 grounds. Never quietly averaged with a stale number." Exclusion,
    not correction, is the prescribed fix, because this file (unlike the live
    MCP screens) has no team-baseline fallback machinery for xgi90/cbit90/etc
    to fall back TO — it would need the same _baseline()/_shrunk() apparatus
    fpl_research_mcp.py uses, which is a bigger change than this one needs.

    NAME COLLISION FOUND WHILE BUILDING THIS, 12 Aug 2026: the pool has TWO
    900+-minute players web_named "Henderson" — the BRE->CHE mover the fence
    entry actually means, AND Dean Henderson, Crystal Palace's long-standing
    #1 keeper, who has nothing to do with it. A plain surname match (which is
    what fpl_research_mcp._contaminated()/_baseline() also uses, so this bug
    likely exists live too, not just here) would wrongly exclude Palace's
    keeper. Fixed by parsing the destination club from the fence's own
    "OLD -> NEW" reason text and only excluding a same-surname player whose
    CURRENT team matches NEW — team+surname identifies the right player;
    surname alone does not.
    """
    global _contam_cache
    if _contam_cache is not None:
        return _contam_cache
    out = {}
    try:
        text = open(INTEL_PATH, encoding="utf-8").read()
        parts = text.split("```contaminated", 1)
        if len(parts) > 1:
            for line in parts[1].split("```", 1)[0].strip().splitlines():
                bits = [p.strip() for p in line.split("|")]
                if len(bits) < 2 or not bits[0]:
                    continue
                reason = bits[1]
                dest = reason.split("->", 1)[1].strip().split(";", 1)[0].strip() \
                    if "->" in reason else None
                out[bits[0]] = dest        # dest may be None if unparseable
    except Exception:
        pass
    _contam_cache = out
    return out


def _load_last16():
    """{(web_name, team): (starts, games)} from the last-16-GW archive match.

    Returns {} if the file is missing, so the module still runs (falling back
    to season-total starts for every player) rather than crashing.
    """
    try:
        payload = json.load(open(LAST16_PATH, encoding="utf-8"))
    except Exception:
        return {}
    out = {}
    for key, v in payload.get("matched", {}).items():
        name, team = key.rsplit("|", 1)
        out[(name, team)] = (v["starts"], v["games"])
    return out

CBIT_THRESH, CBIRT_THRESH = 10.0, 12.0

# gate 3 - unavailable right now. Verified against injury_report / status flags.
# Update before every run; a stale list silently re-admits a banned player.
UNAVAILABLE = {
    "Fofana", "Andersen", "Saliba", "J.Timber", "Gomez", "Bradley", "Mitoma",
    "Baleba", "Christie", "Onana", "Garner", "Gudmundsson", "Butland",
    "Milosavljević", "Kroupi.Jr",
}

POS = {1: "GKP", 2: "DEF", 3: "MID", 4: "FWD"}


def f(x):
    try: return float(x)
    except (TypeError, ValueError): return 0.0


# ---- GATE 4: expected points from FPL's ACTUAL scoring table ----------------
#
# CORRECTED 9 Aug 2026. The first version used hand-picked coefficients -
# `xGI/90 * 8`, `(1.6 - xGC/90) * 6` - which appear nowhere in FPL's rules. That
# made the squad shape depend on constants nobody had tested, and it was right to
# call them out. Every coefficient below is now an FPL scoring rule, so there is
# nothing left to tune.
#
# ONE judgement survives: P(clearing the DC threshold) is estimated from a season
# MEAN. The award is per-match, so a player averaging 12 still misses in
# low-volume games. The honest fix is the true per-match hit rate from
# element-summary, which needs current-season data - see midfielder_screen
# and defender_screen with accurate=True.
#
# NOTE - this IS a composite expected-points score, which design note D5
# deliberately avoided. D5's objection was that naive blending ranks the
# mid-table defender highest. That objection does not apply here: this model
# scores him low because BOTH P(clean sheet) and P(threshold) are low. The
# archetypes remain the right tool for READING a screen; xP is the right tool
# for CHOOSING between positions under a budget.

# Roadmap A4. Set False (or pass --legacy-dc) to score on the superseded
# step function, for the GW10 comparison.
USE_EMPIRICAL_DC = "--legacy-dc" not in sys.argv

# Adjustments layer, 10 Aug 2026. OFF by default - pass --intel to apply the
# `adjustments` fence in ROLE_INTEL.md. load() also accepts an explicit
# `intel=True/False` override so a single process can build both pools for a
# with-vs-without comparison (see intel_adjust.py --report and
# optimise_squad.py --compare-intel) without relying on sys.argv twice.
USE_INTEL = "--intel" in sys.argv

GOAL   = {"GKP": 10, "DEF": 6, "MID": 5, "FWD": 4}
ASSIST = 3
CS     = {"GKP": 4, "DEF": 4, "MID": 1, "FWD": 0}
DC_PTS = 2                       # defensive contribution, capped
DC_THRESH_POS = {"GKP": 99.0, "DEF": 10.0, "MID": 12.0, "FWD": 12.0}
APPEARANCE = 2                   # 60+ minutes
SAVES_PER_POINT = 3
GC_PER_MINUS = 2                 # -1 per 2 goals conceded (GKP and DEF only)


# --- Roadmap A4: empirical hit rates, built 9 Aug 2026 ----------------------
# Loaded lazily and tolerantly: this file must still run before dc_hit_rates.json
# exists, or the project cannot bootstrap. A missing file falls back to the step
# function and SAYS SO on first use — silence would hide which estimator is live.
_DC_RATES, _DC_WARNED = None, False


_DC_DOC, _PRIOR_CACHE = None, {}


def _dc_rates():
    global _DC_RATES, _DC_DOC
    if _DC_RATES is None:
        try:
            _DC_DOC = json.load(open(os.path.join(HERE, "dc_hit_rates.json"),
                                     encoding="utf-8"))
            _DC_RATES = _DC_DOC["players"]
        except Exception:
            _DC_DOC, _DC_RATES = {}, {}
    return _DC_RATES


def _prior_at(pos, eff):
    """Positional mean hit rate AT this effective threshold, and shrinkage k.

    Recomputed per threshold because a fixture-scaled line moves the whole
    population, not just one player — shrinking toward a fixed prior would drag
    every scaled estimate back toward the unscaled world.
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
    """SUPERSEDED by the empirical hit rate. Kept for the GW10 comparison only.

    Measured against 2025/26 per-match counts this was wrong three ways:
    the 0.80-1.00x band assumed 0.20 against an actual 0.41 (0.42 xP/90 over
    39 of 160 qualifying players); the 1.30x band was unreachable and never
    fired; and everyone above the line scored an identical 0.55 while real
    hit rates inside that band ran 52%-70%. See METHODOLOGY_ALTERNATIVES A4.
    """
    if mean >= thresh * 1.30: return 0.75
    if mean >= thresh:        return 0.55
    if mean >= thresh * 0.80: return 0.20
    return 0.05


def p_threshold(mean, thresh, key=None):
    """P(clearing the DC line in a given match).

    Prefers the player's OBSERVED per-match hit rate, shrunk toward the
    positional prior. The award is a per-match threshold, so the hit rate is
    the quantity itself rather than an estimate of it — no distribution assumed,
    no bands, no constants. Falls back to the step function only where the
    player is absent from the archive.
    """
    global _DC_WARNED
    if not USE_EMPIRICAL_DC:
        return p_threshold_legacy(mean, thresh)
    rec = _dc_rates().get(key or "")
    if rec:
        # `mean` arrives already fixture-scaled by fixture_adjust; recover the
        # scale and move the THRESHOLD by the inverse, so P(X >= thresh/scale).
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


# ---- xbonus90 (roadmap A1, added 12 Aug 2026) -------------------------------
#
# Bonus points are already resolved by FPL into a per-player, per-match award
# (`bonus`), so this is a rate-shrinkage problem like xG90/CBIT90/etc., not a
# from-scratch simulation of the BPS ranking. Mirrors
# fpl_research_mcp._estimate_k (design D3) as a LOCAL COPY rather than an
# import — same pattern build_dashboard.py already uses for the same reason:
# this file has no other dependency on the MCP module, and importing it would
# pull in its whole server/tool surface for ~15 lines of arithmetic.
USE_BONUS = "--no-bonus" not in sys.argv

BONUS_DISPERSION = 1.0        # ASSUMED count-like (bonus is bounded 0-3/match).
                               # NOT derived from measured match-to-match
                               # variance — flagged, not trusted, exactly the
                               # kind of unverified assumption that caused the
                               # xGI dispersion bug (see METHODOLOGY_ALTERNATIVES.md).

# 2026/27 Bonus Points System change, PL's own "What's new" article (20 Jul
# 2026): CBI now feeds BPS at 1-per-3 (was 1-per-2) — worse for CBI-heavy
# defenders. The -1 BPS tackled-penalty is removed — better for dribble-exposed
# MID/FWD, who took that penalty most. DIRECTION is sourced. MAGNITUDE IS NOT —
# there is no published number, and this file lacks the full BPS component
# breakdown needed to recompute it exactly. Same standard as the Rice `stp`
# override in ROLE_INTEL.md: a small, capped, clearly-labelled nudge, not a
# fabricated precise coefficient. RE-DERIVE FROM REAL 2026/27 BPS DATA (GW1-5)
# AND DELETE THIS BLOCK once it can be measured directly.
CBI_HAIRCUT = 0.95             # UNSOURCED magnitude, bounded
TACKLE_BUMP = 1.05             # UNSOURCED magnitude, bounded
CBI_HEAVY_THRESH = 6.0         # CBI(not CBIT)/90 above which a defender counts
                               # as "CBI-heavy" for the haircut


def _estimate_k_bonus(samples):
    """Poisson-Gamma method of moments, mirrors fpl_research_mcp._estimate_k."""
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


def _bonus_shrinkage(players, teams):
    """{pid: xbonus90} for every 900+-minute player.

    shrunk = (n90*raw + k*baseline) / (n90+k), baseline = team x position
    mean bonus90, falling back to position mean where the team+pos group is
    thin (<3 players). This is the D2 ladder's TAIL only, without the "own
    prior season" head — for this file the prior season IS the only season
    on record (it reads nothing but the frozen snapshot), so there is no
    separate prior to fall back FROM.
    """
    rows = []
    for pid, p in players.items():
        m = p.get("minutes", 0) or 0
        if m < MIN_MINUTES:
            continue
        n90 = m / 90.0
        cbi = p.get("clearances_blocks_interceptions", 0) or 0
        rows.append(dict(
            pid=pid, pos=POS[p["element_type"]], team=teams.get(p.get("team"), "?"),
            n90=n90, raw=(p.get("bonus", 0) or 0) / n90, cbi90=cbi / n90))

    k = _estimate_k_bonus([(r["raw"], r["n90"]) for r in rows])
    if k in (10.0, 40.0, 60.0):
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


def expected_points(r):
    """Expected FPL points per 90. Every coefficient is a rule, not a choice."""
    pos = r["pos"]
    dc_metric = r["cbit90"] if pos == "DEF" else r["cbirt90"]
    xp = APPEARANCE
    xp += GOAL[pos] * r["xg90"] + ASSIST * r["xa90"]
    xp += CS[pos] * r["p_cs"]
    xp += DC_PTS * p_threshold(dc_metric, DC_THRESH_POS[pos],
                           key=f'{r["name"]}|{r["team"]}')
    if pos in ("GKP", "DEF"):
        xp -= r["xgc90"] / GC_PER_MINUS
    if pos == "GKP":
        xp += r["sv90"] / SAVES_PER_POINT
    # Bonus is already in point units — no coefficient, unlike goals/saves.
    xp += r.get("xbonus90", 0.0)
    return xp


# delta is NOT in the xP model - it is a discount signal for spotting underpriced
# players, not a component of expected points. Kept separate on purpose.


USE_CONTAM_FILTER = "--allow-contaminated" not in sys.argv


def load(season_starts=False, intel=None, bonus=None, exclude_contaminated=None):
    use_intel = USE_INTEL if intel is None else intel
    use_bonus = USE_BONUS if bonus is None else bonus
    use_contam_filter = USE_CONTAM_FILTER if exclude_contaminated is None else exclude_contaminated
    snap = json.load(open(SNAP, encoding="utf-8"))
    teams = {int(k): v for k, v in snap["teams"].items()}
    last16 = {} if season_starts else _load_last16()
    xbonus_map, _bonus_k = _bonus_shrinkage(snap["players"], teams) if use_bonus else ({}, None)
    contam = _contaminated() if use_contam_filter else {}
    excluded = []
    matched = set()
    out = []
    for pid, p in snap["players"].items():
        m = p.get("minutes", 0) or 0
        if m < MIN_MINUTES:
            continue
        name = p["web_name"]
        team = teams.get(p.get("team"), "?")
        if contam:
            hit_dest = next((dest for w, dest in contam.items()
                              if w.lower() in name.lower() or name.lower() in w.lower()), "MISS")
            # team+surname match — a same-surname player at the WRONG club
            # (see Henderson/Henderson in the docstring above) is not this
            # fence entry and must not be excluded. `dest is None` means the
            # fence line couldn't be parsed — exclude on surname alone rather
            # than silently admit an unverifiable case.
            if hit_dest != "MISS" and (hit_dest is None or hit_dest == team):
                excluded.append(f"{name} ({team})")
                continue
        n90 = m / 90.0
        cbi = p.get("clearances_blocks_interceptions", 0) or 0
        tk, rec = p.get("tackles", 0) or 0, p.get("recoveries", 0) or 0
        xgi = f(p.get("expected_goal_involvements"))
        ga = (p.get("goals_scored", 0) or 0) + (p.get("assists", 0) or 0)
        stp_season = (p.get("starts", 0) or 0) / 38
        hit = last16.get((name, team))
        if hit:
            starts16, games16 = hit
            stp, stp_src = starts16 / games16, "last16"
        else:
            stp, stp_src = stp_season, "season_fallback"
        r = dict(name=name, pos=POS[p["element_type"]],
                 team=team, price=(p.get("now_cost") or 0)/10,
                 starts=p.get("starts", 0) or 0, stp=stp, stp_season=stp_season,
                 stp_src=stp_src,
                 xgi90=xgi/n90, delta=ga - xgi, cbit90=(cbi+tk)/n90,
                 cbirt90=(cbi+tk+rec)/n90, xgc90=f(p.get("expected_goals_conceded"))/n90,
                 cs=p.get("clean_sheets", 0) or 0, bps90=(p.get("bps") or 0)/n90,
                 sv90=(p.get("saves") or 0)/n90, own=f(p.get("selected_by_percent")),
                 xg90=f(p.get("expected_goals"))/n90, xa90=f(p.get("expected_assists"))/n90,
                 bonus90=(p.get("bonus") or 0)/n90, xbonus90=xbonus_map.get(pid, 0.0))
        if use_intel:
            for e in ia.apply(r):
                matched.add((e["player"], e["team"]))
        r["p_cs"] = math.exp(-max(r["xgc90"], 0.05)) if CS[r["pos"]] else 0.0
        r["ok"] = r["name"] not in UNAVAILABLE
        r["score"] = expected_points(r)
        out.append(r)
    if use_intel:
        # UNMATCHED IS A BUG, NOT A NO-OP. A typo'd name/team in the fence
        # would otherwise adjust nothing and say nothing - the exact silent
        # failure this project has been bitten by before (see module docstring
        # of intel_adjust.py).
        for e in ia.load_adjustments():
            if (e["player"], e["team"]) not in matched:
                print(f"  INTEL WARNING: {e['player']}|{e['team']} "
                      f"({e['field']}) matched no player in the pool - check "
                      f"spelling/team code, or he may be below the {MIN_MINUTES}"
                      f"-minute gate", file=sys.stderr)
    if excluded:
        print(f"  CONTAMINATED PRIOR — {len(excluded)} player(s) excluded "
              f"(Tier 1, ROLE_INTEL.md): {', '.join(sorted(excluded))}. "
              f"Pass --allow-contaminated to include them anyway.",
              file=sys.stderr)
    return out


def build(pool, form, allow_haaland, gate_xi):
    """form = (n_def, n_mid, n_fwd) in the XI. Bench fills the remainder."""
    nd, nm, nf = form
    pick, spend, club = [], 0.0, {}

    def take(pos, k, gate, cheapest=False):
        nonlocal spend
        got = 0
        cands = [p for p in pool if p["pos"] == pos]
        cands.sort(key=(lambda x: (x["price"], -x["stp"])) if cheapest
                   else (lambda x: -x["score"]))
        for r in cands:
            if got >= k:
                break
            if r in pick or not r["ok"] or r["stp"] < gate:
                continue
            if club.get(r["team"], 0) >= MAX_PER_CLUB:
                continue
            if not allow_haaland and r["name"] == "Haaland":
                continue
            pick.append(r); spend += r["price"]
            club[r["team"]] = club.get(r["team"], 0) + 1
            got += 1
        return got

    ok = take("GKP", 1, gate_xi) == 1
    ok &= take("DEF", nd, gate_xi) == nd
    ok &= take("MID", nm, gate_xi) == nm
    ok &= take("FWD", nf, gate_xi) == nf
    xi, xi_spend = list(pick), spend
    # Bench: cheapest player who still actually PLAYS. Not a merit ranking -
    # bench points only arrive via autosub or Bench Boost, so availability is
    # the whole point and quality is not worth paying for.
    for pos, k in (("GKP", 1), ("DEF", 5-nd), ("MID", 5-nm), ("FWD", 3-nf)):
        ok &= take(pos, k, GATE_BENCH, cheapest=True) == k
    return ok, xi, pick, xi_spend, spend


def main():
    allow_haaland = "--haaland" in sys.argv
    season_starts = "--season-starts" in sys.argv
    gate = GATE_XI
    if "--gate" in sys.argv:
        gate = float(sys.argv[sys.argv.index("--gate") + 1])
    pool = load(season_starts=season_starts)
    best = None
    for form in ((3,4,3),(3,5,2),(4,4,2),(4,3,3),(5,3,2),(4,5,1),(5,4,1)):
        ok, xi, sq, xs, tot = build(pool, form, allow_haaland, gate)
        if ok and tot <= BUDGET:
            m = sum(r["score"] for r in xi)
            if best is None or m > best[0]:
                best = (m, form, xi, sq, xs, tot)
    if not best:
        sys.exit(f"No feasible squad within £{BUDGET}m at gate {gate:.0%}.")
    _, form, xi, sq, xs, tot = best
    basis = "last-16-GW (2025/26 GW23-38)" if not season_starts else "full-season (38 GW)"
    print(f"gates: {MIN_MINUTES}+ mins · starts% basis: {basis} · "
          f">={gate:.0%} (XI) / {GATE_BENCH:.0%} (bench) "
          f"· £{BUDGET}m · max {MAX_PER_CLUB}/club" + ("" if allow_haaland else " · no Haaland")
          + (" · INTEL ADJUSTMENTS APPLIED (--intel)" if USE_INTEL else ""))
    print(f"formation {form[0]}-{form[1]}-{form[2]}   XI £{xs:.1f}m   "
          f"squad £{tot:.1f}m   bank £{BUDGET-tot:.1f}m\n")
    for r in sorted(xi, key=lambda x: (list(POS.values()).index(x["pos"]), -x["score"])):
        flag = "*" if r.get("stp_src") == "season_fallback" else " "
        print(f"  {r['name'][:14]:<15}{r['pos']:<5}{r['team']:<5}£{r['price']:<5.1f}"
              f"{r['stp']*100:>4.0f}%{flag}  xP {r['score']:>5.2f}")
    print("  --- bench ---")
    for r in [x for x in sq if x not in xi]:
        flag = "*" if r.get("stp_src") == "season_fallback" else " "
        print(f"  {r['name'][:14]:<15}{r['pos']:<5}{r['team']:<5}£{r['price']:<5.1f}"
              f"{r['stp']*100:>4.0f}%{flag}")
    if not season_starts and any(r.get("stp_src") == "season_fallback" for r in xi + sq):
        print("\n  * = no last-16 match found; using full-season start rate as fallback.")


if __name__ == "__main__":
    main()
