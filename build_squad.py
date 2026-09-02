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
    python3 build_squad.py --no-intel      # disable ROLE_INTEL.md adjustments (ON by default since 13 Aug 2026)
    python3 build_squad.py --estimator raw     # live 2026/27 per-90 rates only, no blending (gated - see
                                                # scoring.MIN_N90_RAW). Needs live network.
    python3 build_squad.py --estimator shrunk  # blend live 2026/27 rates toward the 2025/26 prior (roadmap A0.2,
                                                # OFF by default until exercised - see METHODOLOGY_ALTERNATIVES.md
                                                # "Phase 2"). Needs live network; degrades to prior-only if unreachable.
                                                # (--shrunk-priors still works as a legacy alias for this.)

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

import scoring
import constants

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

# Squad shape (architecture review candidate #4) — was hand-duplicated here
# with int position keys (1-4) and again in optimise_squad.py with string
# keys ("GKP" etc). One representation now, in constants.py.
BUDGET = constants.BUDGET
SQUAD_SHAPE = constants.SQUAD_SHAPE
MAX_PER_CLUB = constants.MAX_PER_CLUB


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

# Defaults for load()'s optional overrides (architecture review candidate
# #3). NOT read from sys.argv at import time any more — build_squad.py is
# loaded dynamically by six other scripts, so an ambient read here picked up
# whichever process happened to import it, not a real per-call choice (see
# build_squad_page.py's 11 Aug 2026 bug, fixed at the time by passing
# intel=True explicitly at that one call site rather than by removing the
# hazard). Every script now parses its OWN CLI flags in its OWN main() and
# passes them to load() explicitly; these four are just the defaults a
# caller gets when it doesn't override. Every default here matches the
# pipeline's long-standing behaviour — all ON.
USE_EMPIRICAL_DC = True   # roadmap A4. Pass --legacy-dc for the superseded step function.
USE_INTEL = True          # ROLE_INTEL.md adjustments. Pass --no-intel to disable.
USE_BONUS = True          # roadmap A1 (xbonus90). Pass --no-bonus to rebuild without it.
USE_CONTAM_FILTER = True  # Tier-1 contaminated-prior exclusion. Pass --allow-contaminated to include them.
ESTIMATOR_CHOICES = ("prior", "raw", "shrunk")
ESTIMATOR_DEFAULT = "prior"  # roadmap A0.2 Phase 2 (revised 31 Aug 2026; extended
                          # 2 Sep 2026 with the standalone "raw" choice). One of:
                          #   prior  - 2025/26 prior season only, no live fetch.
                          #            The long-standing default.
                          #   raw    - live 2026/27 per-90 rates only, gated at
                          #            scoring.MIN_N90_RAW (below that, falls
                          #            back to the prior for that metric - see
                          #            scoring.MIN_N90_RAW's comment for why an
                          #            un-gated raw rate is unusable early on).
                          #            No blending toward the prior at all.
                          #   shrunk - Bayesian blend of the two (roadmap A0.2).
                          # Pass --estimator {prior,raw,shrunk} to override.
                          # DEFAULT STAYS "prior" until shrunk/raw are exercised
                          # via --compare-estimators and look sane - see
                          # METHODOLOGY_ALTERNATIVES.md A0.2 "Phase 2".

# Scoring table, the DC-threshold estimator, and bonus shrinkage all moved to
# scoring.py (architecture review candidate #1) — see that module's
# docstring for the drift bug this fixed. Re-exported here so any caller
# still doing bs.GOAL / bs.expected_points / bs.p_threshold keeps working;
# the implementation lives in scoring.py, this is not a second copy of it.
GOAL, ASSIST, CS = scoring.GOAL, scoring.ASSIST, scoring.CS
DC_PTS, DC_THRESH_POS = scoring.DC_PTS, scoring.DC_THRESH_POS
APPEARANCE = scoring.APPEARANCE
SAVES_PER_POINT, GC_PER_MINUS = scoring.SAVES_PER_POINT, scoring.GC_PER_MINUS
p_threshold = scoring.p_threshold
p_threshold_legacy = scoring.p_threshold_legacy
expected_points = scoring.expected_points
_bonus_shrinkage = scoring.bonus_shrinkage


# delta is NOT in the xP model - it is a discount signal for spotting underpriced
# players, not a component of expected points. Kept separate on purpose.


# ---- live current-season fetch, for --estimator raw/shrunk only -------------
# build_squad.py has been fully offline until now (SNAP is a frozen JSON file
# on disk). This is its first live-network dependency, and it is kept
# strictly optional and silent-safe: any failure (no egress, timeout, bad
# response) degrades to {} - every row then falls back to its prior-only
# value (scoring.shrink_rate()'s n90<=0 branch for shrunk; the MIN_N90_RAW
# gate above for raw), so a sandboxed or offline run behaves exactly as
# estimator='prior' were passed, just with one warning printed rather than
# a crash.
_current_cache = None


def _fetch_current_season():
    global _current_cache
    if _current_cache is not None:
        return _current_cache
    import urllib.request
    try:
        req = urllib.request.Request(
            "https://fantasy.premierleague.com/api/bootstrap-static/",
            headers={"User-Agent": "fpl-build-squad/1.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        _current_cache = {str(e["id"]): e for e in data.get("elements", [])}
    except Exception as exc:
        print(f"  SHRUNK PRIORS: live bootstrap-static fetch failed ({exc}) - "
              f"falling back to prior-only rates for every player this run.",
              file=sys.stderr)
        _current_cache = {}
    return _current_cache


def _current_rates(el):
    """Current-season per-90 rates from a LIVE bootstrap element, in this
    file's own field names. Mirrors fpl_research_mcp.py's `_rates()` — see
    scoring.py's PRIORS_DISPERSION comment for why that file isn't imported
    directly. `el` may be {} (player not found in the live fetch, or the
    fetch itself failed) - returns all-zero/n90=0, which shrink_rate() then
    treats as "no current data, keep the baseline" rather than a divide.
    """
    m = el.get("minutes", 0) or 0
    n90 = m / 90.0
    if n90 <= 0:
        return dict(n90=0.0, xg90=0.0, xa90=0.0, xgi90=0.0, xgc90=0.0,
                    cbit90=0.0, cbirt90=0.0, sv90=0.0)
    cbi = el.get("clearances_blocks_interceptions", 0) or 0
    tk, rec = el.get("tackles", 0) or 0, el.get("recoveries", 0) or 0
    return dict(
        n90=n90,
        xg90=f(el.get("expected_goals")) / n90,
        xa90=f(el.get("expected_assists")) / n90,
        xgi90=f(el.get("expected_goal_involvements")) / n90,
        xgc90=f(el.get("expected_goals_conceded")) / n90,
        cbit90=(cbi + tk) / n90,
        cbirt90=(cbi + tk + rec) / n90,
        sv90=(el.get("saves") or 0) / n90,
    )


def load(season_starts=False, intel=None, bonus=None, exclude_contaminated=None,
         empirical=None, estimator=None):
    use_intel = USE_INTEL if intel is None else intel
    use_bonus = USE_BONUS if bonus is None else bonus
    use_contam_filter = USE_CONTAM_FILTER if exclude_contaminated is None else exclude_contaminated
    use_empirical_dc = USE_EMPIRICAL_DC if empirical is None else empirical
    use_estimator = ESTIMATOR_DEFAULT if estimator is None else estimator
    if use_estimator not in ESTIMATOR_CHOICES:
        raise ValueError(f"estimator must be one of {ESTIMATOR_CHOICES}, got {use_estimator!r}")
    needs_live = use_estimator in ("raw", "shrunk")
    snap = json.load(open(SNAP, encoding="utf-8"))
    teams = {int(k): v for k, v in snap["teams"].items()}
    last16 = {} if season_starts else _load_last16()
    xbonus_map, _bonus_k = _bonus_shrinkage(snap["players"], teams) if use_bonus else ({}, None)
    contam = _contaminated() if use_contam_filter else {}
    current = _fetch_current_season() if needs_live else {}
    excluded = []
    matched = set()
    # PASS A - baseline rows (prior-season / last16 / bonus), no intel yet.
    # Shrinkage needs every row's current-season sample BEFORE it can derive
    # a population k for any one of them, so this has to be a full pass
    # before anything downstream (intel, p_cs, score) runs - see PASS B below.
    rows = []
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
                 bonus90=(p.get("bonus") or 0)/n90, xbonus90=xbonus_map.get(pid, 0.0),
                 # Population-level shrinkage k, same value on every row this
                 # load() call — carried per-row (rather than returned
                 # separately) so callers already threading `pool`/`r` around
                 # (e.g. the squad page's composition chart, ADR 0001) can
                 # tell whether xbonus90 came from a fitted k or one of
                 # scoring.BONUS_FALLBACK_KS without re-deriving it.
                 bonus_k=_bonus_k)
        if needs_live:
            r["_cur"] = _current_rates(current.get(pid, {}))
        rows.append(r)

    # Between passes: derive one k per metric from the WHOLE population's
    # current-season samples, then blend every row toward it. Pool-wide, not
    # per-position — a deliberate scope decision for this first activation,
    # not an oversight; see METHODOLOGY_ALTERNATIVES.md A0.2 "Phase 2" for
    # what the GW5 review should reconsider if this looks wrong.
    if use_estimator == "shrunk":
        ks = {}
        for metric, disp in scoring.PRIORS_DISPERSION.items():
            samples = [(r["_cur"][metric], r["_cur"]["n90"]) for r in rows]
            ks[metric] = scoring.estimate_k_priors(samples, dispersion=disp)
        degenerate = sorted(m for m, k in ks.items() if k in (10.0, 40.0, 60.0))
        if degenerate:
            print(f"  SHRUNK PRIORS: fallback/clamp k for {', '.join(degenerate)} "
                  f"— not derived from variance (population too thin, or GW1's "
                  f"no-current-data case) — treat those metrics as unvalidated "
                  f"this run.", file=sys.stderr)
        for r in rows:
            cur = r.pop("_cur")
            for metric in scoring.PRIORS_DISPERSION:
                r[metric] = scoring.shrink_rate(cur[metric], cur["n90"], r[metric], ks[metric])
    elif use_estimator == "raw":
        # No blending at all - the live rate replaces the prior outright once
        # there is enough current-season sample to trust it (scoring.MIN_N90_RAW),
        # otherwise the prior value already sitting in r[metric] is left in
        # place untouched, same "not enough data yet" fallback shrink_rate()
        # gives at n90<=0, just gated at a higher bar since raw has no k to
        # cushion a thin sample.
        below_gate = 0
        for r in rows:
            cur = r.pop("_cur")
            if cur["n90"] < scoring.MIN_N90_RAW:
                below_gate += 1
                continue
            for metric in scoring.PRIORS_DISPERSION:
                r[metric] = cur[metric]
        if current and below_gate:
            print(f"  RAW: {below_gate}/{len(rows)} player(s) below the "
                  f"{scoring.MIN_N90_RAW:.1f}-n90 current-season gate — using "
                  f"their 2025/26 prior rate for those metrics instead (raw "
                  f"mode does not blend; see scoring.MIN_N90_RAW).",
                  file=sys.stderr)

    # PASS B - intel, availability, score. Same order as the old single-pass
    # loop (intel BEFORE p_cs/score), so a ROLE_INTEL `mult`/`set` entry
    # applies ON TOP of the now-estimated baseline, not the other way round -
    # unchanged whichever estimator ran above.
    out = []
    for r in rows:
        if use_intel:
            for e in ia.apply(r):
                matched.add((e["player"], e["team"]))
        r["p_cs"] = math.exp(-max(r["xgc90"], 0.05)) if CS[r["pos"]] else 0.0
        r["ok"] = r["name"] not in UNAVAILABLE
        r["score"] = scoring.expected_points(r, empirical=use_empirical_dc)
        out.append(r)
    if needs_live and not current:
        print(f"  {use_estimator.upper()}: enabled but no live current-season data "
              f"was available this run (see the fetch warning above, if any) — "
              f"every rate fell back to its prior-only value, same as "
              f"estimator='prior' were passed.", file=sys.stderr)
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
    # Each script parses its OWN argv now (architecture review candidate #3)
    # rather than relying on the USE_INTEL/USE_BONUS/USE_CONTAM_FILTER/
    # USE_EMPIRICAL_DC ambient defaults above — those are for callers that
    # import load() without an opinion, not for this file's own CLI.
    use_intel = "--no-intel" not in sys.argv
    use_bonus = "--no-bonus" not in sys.argv
    use_contam_filter = "--allow-contaminated" not in sys.argv
    use_empirical_dc = "--legacy-dc" not in sys.argv
    if "--estimator" in sys.argv:
        estimator = sys.argv[sys.argv.index("--estimator") + 1]
    elif "--shrunk-priors" in sys.argv:       # legacy alias, kept working
        estimator = "shrunk"
    else:
        estimator = ESTIMATOR_DEFAULT
    if estimator not in ESTIMATOR_CHOICES:
        sys.exit(f"--estimator must be one of {ESTIMATOR_CHOICES}, got {estimator!r}")
    gate = GATE_XI
    if "--gate" in sys.argv:
        gate = float(sys.argv[sys.argv.index("--gate") + 1])
    pool = load(season_starts=season_starts, intel=use_intel, bonus=use_bonus,
                exclude_contaminated=use_contam_filter, empirical=use_empirical_dc,
                estimator=estimator)
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
          + (" · INTEL ADJUSTMENTS APPLIED (default)" if use_intel else " · INTEL OFF (--no-intel)")
          + (f" · ESTIMATOR={estimator.upper()} (--estimator)" if estimator != "prior" else ""))
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
