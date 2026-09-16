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

MOSTLY not a live tool - its RATE stats (xg90/xa90/xgi90/...) still read the
frozen prior-season snapshot regardless of estimator, so from GW1 it should
read player_gw from SQLite instead — see METHODOLOGY_ALTERNATIVES.md B6.
PRICE and CLUB are the exceptions - both are live facts, not modelled rates,
so both are read from live bootstrap-static on every load() call and both
degrade to the frozen snapshot (with a warning) if it is unreachable.

    PRICE (3 Sep 2026) - a stale price is a wrong budget, not just a wrong
    estimate. See the "PRICE" comment above load()'s current-season fetch.
    CLUB  (7 Sep 2026) - a stale club is a wrong FIXTURE RUN. The frozen
    snapshot was captured 8 Aug, before the window shut, so it named the
    pre-deadline club for every late mover; 15 pool players were carrying
    one when this was fixed. Rows also keep `team_prior`, the snapshot club,
    because prior-season lookups (last16_starts.json, the gameweek archive)
    are still keyed by it. See the "CLUB" comment in load().
    STATUS (15 Sep 2026) - a stale availability is a player who cannot play.
    FPL's live `status` flag now feeds gate 3 alongside the hand-kept
    UNAVAILABLE list; see LIVE_STATUS_EXCLUDE for which flags exclude and why.

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
# Since 15 Sep 2026 this is an ADDITIONAL override on top of the live status
# flag (LIVE_STATUS_EXCLUDE below), not the only availability check - it still
# carries the injuries and bans the live flag doesn't exclude automatically.
UNAVAILABLE = {
    "Fofana", "Andersen", "Saliba", "J.Timber", "Gomez", "Bradley", "Mitoma",
    "Baleba", "Christie", "Onana", "Garner", "Gudmundsson", "Butland",
    "Milosavljević", "Kroupi.Jr",
}

# gate 3, LIVE - FPL's own `status` flag from bootstrap-static. ADDED 15 Sep
# 2026: Watkins left for Al-Hilal, but a player who leaves the Premier League
# stays in bootstrap-static with status 'u' and his OLD club, so neither the
# live CLUB pass nor this hand list caught him - he scored 4.89 xP, ok=True,
# with nothing but a since-removed ROLE_INTEL row ever holding him out. Same
# class of failure as the Sarr trap: a status assumed to flow into the
# optimiser that never did.
#
# Decided per flag, deliberately not "anything but 'a'":
#   'u' unavailable  - EXCLUDED. Left the club/league; no return this horizon.
#   'n' not available - EXCLUDED. FPL uses it mainly for loans out, so no return
#                      this horizon either. It is occasionally a short absence
#                      instead (e.g. ineligible vs parent club), which is why
#                      load() prints FPL's `news` text next to every exclusion.
#   's' suspended    - NOT excluded automatically. A ban ends, and this pool is
#                      scored over a multi-GW window (GW5-8 on 15 Sep 2026), so
#                      a short ban zeroing him for the whole horizon would
#                      overstate it - GLOSSARY.md's "hold signal, not a blank
#                      signal" point. (Strictly, that note is about yellow-card
#                      RISK; a ban being served does blank those GWs -
#                      GLOSSARY's BANNED row.) Bans are NOT reliably short:
#                      on 15 Sep 2026 Foden's ran to 17 Oct, past the whole
#                      window. So load() prints each one with FPL's "Suspended
#                      until" text; add him to UNAVAILABLE when it covers the
#                      window.
#   'i' injured      - EXCLUDED since 15 Sep 2026. Left to the hand list until
#                      then, which nobody updated in time: the GW5 shrunk run
#                      recommended Hinshelwood (status 'i', chance 0, ankle,
#                      back 10 Oct). Excluded for the whole window even when
#                      the return date lands inside it - a partial-window
#                      injury is a hold, not a buy.
#   'd' doubtful     - EXCLUDED when FPL's chance_of_playing_next_round is
#                      below DOUBTFUL_MIN_CHANCE (i.e. the 0/25% bands); at
#                      50/75% he stays selectable and load() reports him as
#                      STATUS DOUBTFUL, like 's' above. A missing chance on a
#                      'd' is treated as selectable-but-reported, never guessed.
LIVE_STATUS_EXCLUDE = {"u": "unavailable", "n": "not available", "i": "injured"}
DOUBTFUL_MIN_CHANCE = 50


def is_available(r):
    """Gate 3 for one pool row: the hand list AND the live status flag.

    `r["status"]` is None when bootstrap-static was unreachable or didn't list
    the player, which leaves the hand list as the only check (load() says so).
    """
    if r["name"] in UNAVAILABLE or r.get("status") in LIVE_STATUS_EXCLUDE:
        return False
    return not _doubtful_out(r)


def _doubtful_out(r):
    """'d' with a live chance below DOUBTFUL_MIN_CHANCE - see LIVE_STATUS_EXCLUDE."""
    chance = r.get("chance")
    return r.get("status") == "d" and chance is not None and chance < DOUBTFUL_MIN_CHANCE

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

# START RATE (roadmap A0.2 activation, 16 Sep 2026). Separate from ESTIMATOR
# above on purpose: that flag governs the per-90 rates, where the prior still
# wins or ties; this governs stp, where the frozen last-16 prior is the worst
# estimator by ~20% (see scoring.estimate_k_start). One of:
#   prior  - last-16 starts of 2025/26 (or season/38 fallback). The old stp.
#   shrunk - blended with 2026/27 starts per team match played, per-position k.
# stp does not enter xP/90 (that is A0.5); it decides the 75% XI / 60% bench
# gates, so this changes WHO IS ELIGIBLE, not anyone's score. ROLE_INTEL's
# `set stp` still applies on top. Pass --stp-estimator {prior,shrunk}.
# DEFAULT "shrunk" SINCE 16 Sep 2026, for the GW5 deadline (Sylvan's call; the
# roadmap's gate was GW6). Kill criterion: the GW10 predictive_backtest - if
# shrunk does not beat the last-16 prior out of sample over GW6-10, revert here.
STP_ESTIMATOR_CHOICES = ("prior", "shrunk")
STP_ESTIMATOR_DEFAULT = "shrunk"

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


# ---- live current-season fetch --------------------------------------------
# build_squad.py's own rate stats were fully offline until now (SNAP is a
# frozen JSON file on disk); this was its first live-network dependency,
# added for --estimator raw/shrunk. PRICE now depends on it unconditionally
# too (3 Sep 2026, see load()'s "PRICE" comment) - a real transfer target
# (Enzo, fallen to £6.9m) was priced unaffordable at the frozen snapshot's
# stale £7.0m starting price, in a plain --estimator prior run same as any
# other. Kept strictly optional and silent-safe either way: any failure (no
# egress, timeout, bad response) degrades to {} - every row falls back to its
# prior-only rate value (scoring.shrink_rate()'s n90<=0 branch for shrunk;
# the MIN_N90_RAW gate above for raw) and its frozen snapshot price, so a
# sandboxed or offline run behaves exactly as before this existed, just with
# one warning printed rather than a crash.
_current_cache = None
# {element_id: SHORT_CODE} from the same bootstrap-static call. Populated by
# _fetch_current_season(); {} when that fetch fails. See load()'s CLUB comment.
_live_clubs_cache = None
# The live gameweek id, from the SAME bootstrap-static call above - added
# 15 Sep 2026 so callers who need "what gameweek is it right now"
# (fixture_adjust.py's staleness check) don't have to make a second network
# round-trip, and don't have to import fpl_research_mcp.py's get_deadline()
# to get it (see load()'s CLUB comment / scoring.py's PRIORS_DISPERSION
# comment for why that file is never imported in-process). Mirrors
# fpl_research_mcp.py's _next_event() fallback chain (is_next, then
# is_current, then the first not-finished event) as a hand-maintained copy,
# same discipline as PRIORS_DISPERSION/estimate_k_priors in scoring.py -
# is_next is deliberately tried FIRST: it is the gameweek transfers are being
# planned for (matches get_deadline()'s answer), not whichever gameweek's
# matches happen to be mid-kickoff, which is what is_current alone would give
# right up until deadline day and would misdate the fixture window by one GW
# for most of the week. None when the fetch hasn't run yet or failed.
_live_gw_cache = None
# {team_id: SHORT_CODE}, same fetch; used to key team match counts.
_team_code_cache = None
# {SHORT_CODE: finished fixtures} for --stp-estimator shrunk. None = not
# fetched yet this process, {} = fetch failed.
_team_games_cache = None


def current_live_gw():
    """The live gameweek id, from the same bootstrap-static fetch _fetch_current_season()
    already makes. Returns None if that fetch hasn't happened yet this process or failed -
    callers must treat None as "unknown", never as gameweek 0/None-is-falsy-so-stale.
    """
    _fetch_current_season()
    return _live_gw_cache


def _fetch_current_season():
    global _current_cache, _live_clubs_cache, _live_gw_cache
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
        _events = data.get("events", [])
        _live_gw_cache = (
            next((ev["id"] for ev in _events if ev.get("is_next")), None)
            or next((ev["id"] for ev in _events if ev.get("is_current")), None)
            or next((ev["id"] for ev in _events if not ev.get("finished")), None))
        _code = {t["id"]: t["short_name"] for t in data.get("teams", [])}
        globals()["_team_code_cache"] = _code
        _live_clubs_cache = {str(e["id"]): _code[e["team"]]
                             for e in data.get("elements", [])
                             if e.get("team") in _code}
    except Exception as exc:
        print(f"  LIVE FETCH: bootstrap-static fetch failed ({exc}) - raw/shrunk "
              f"rates fall back to prior-only for every player this run, every "
              f"price falls back to the frozen 8 Aug pre-season snapshot, and so "
              f"does every CLUB - so anyone transferred since 8 Aug 2026 is "
              f"scored on his OLD club's fixtures this run - and no live STATUS "
              f"flag excludes anyone either. Treat a fixture-"
              f"adjusted run under this warning as unreliable for movers. Also: "
              f"current_live_gw() returns None, so fixture_adjust.py's staleness "
              f"check cannot run this call and will not auto-refresh the window.",
              file=sys.stderr)
        _current_cache = {}
        _live_clubs_cache = {}
        _live_gw_cache = None
    return _current_cache


def _fetch_team_games():
    """{SHORT_CODE: finished fixtures} - the start-rate denominator. Counted
    from /fixtures/ rather than bootstrap's teams[].played, which reads 0 all
    season (checked 16 Sep 2026). {} on any failure; load() then keeps the
    prior stp for everyone and says so."""
    global _team_games_cache
    if _team_games_cache is not None:
        return _team_games_cache
    _fetch_current_season()
    import urllib.request
    try:
        req = urllib.request.Request(
            "https://fantasy.premierleague.com/api/fixtures/",
            headers={"User-Agent": "fpl-build-squad/1.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            fixtures = json.loads(resp.read().decode("utf-8"))
        codes = _team_code_cache or {}
        games = {}
        for fx in fixtures:
            if fx.get("finished") and fx.get("event"):
                for side in ("team_h", "team_a"):
                    code = codes.get(fx.get(side))
                    if code:
                        games[code] = games.get(code, 0) + 1
        _team_games_cache = games
    except Exception as exc:
        print(f"  STP: fixtures fetch failed ({exc}) - no team match counts, so "
              f"every start rate stays on its 2025/26 prior this run.", file=sys.stderr)
        _team_games_cache = {}
    return _team_games_cache


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


def _shrink_start_rates(rows, games, season_starts):
    """--stp-estimator shrunk: blend each row's prior stp with its 2026/27
    starts per team match (scoring.estimate_k_start / shrink_start), k per
    position. Runs before intel, so a ROLE_INTEL `set stp` still wins. Keeps
    stp_prior / stp_raw / stp_n / stp_k on every row, and prints who crossed
    the XI gate, never silently."""
    for r in rows:
        r["stp_prior"], r["stp_raw"], r["stp_n"], r["stp_k"] = r["stp"], None, 0, None
    if not games:
        for r in rows:
            r.pop("_starts", None)
        print("  STP: shrunk requested but no team match counts (live fetch failed) - "
              "start rates are the 2025/26 prior this run.", file=sys.stderr)
        return
    ks = {}
    for pos in ("GKP", "DEF", "MID", "FWD"):
        samples = [(min(1.0, r["_starts"] / games[r["team"]]), games[r["team"]], r["stp"])
                   for r in rows if r["pos"] == pos and r.get("_starts") is not None
                   and games.get(r["team"])]
        ks[pos] = scoring.estimate_k_start(samples)
    for r in rows:
        k = ks[r["pos"]][0]
        shrunk, raw = scoring.shrink_start(r.pop("_starts", None), games.get(r["team"]),
                                           r["stp"], k)
        if raw is not None:
            r.update(stp=shrunk, stp_raw=raw, stp_n=games[r["team"]], stp_k=k,
                     stp_src=r["stp_src"] + "+live")
    n_games = sorted(set(games.values()))
    print(f"  STP SHRUNK — start rates blended with 2026/27 starts over "
          f"{n_games[0] if len(n_games) == 1 else n_games} team match(es); k "
          + ", ".join(f"{p} {k:.1f}{f' ({note})' if note else ''}" for p, (k, note) in ks.items())
          + (" · prior is SEASON starts (--season-starts)" if season_starts else ""),
          file=sys.stderr)
    for gate, label in ((GATE_XI, "XI"), (GATE_BENCH, "bench")):
        up = sorted((r for r in rows if r["stp_prior"] < gate <= r["stp"]),
                    key=lambda r: r["stp_prior"] - r["stp"])
        down = sorted((r for r in rows if r["stp"] < gate <= r["stp_prior"]),
                      key=lambda r: r["stp"] - r["stp_prior"])
        def fmt(rs):
            return ", ".join(f"{r['name']} ({r['team']}) {r['stp_prior']:.0%}->{r['stp']:.0%}"
                             for r in rs[:15]) + (f" +{len(rs) - 15} more" if len(rs) > 15 else "")
        if up:
            print(f"  STP {label} GATE {gate:.0%} — now clear it ({len(up)}): {fmt(up)}",
                  file=sys.stderr)
        if down:
            print(f"  STP {label} GATE {gate:.0%} — now below it ({len(down)}): {fmt(down)}",
                  file=sys.stderr)


def load(season_starts=False, intel=None, bonus=None, exclude_contaminated=None,
         empirical=None, estimator=None, stp_estimator=None):
    use_stp = STP_ESTIMATOR_DEFAULT if stp_estimator is None else stp_estimator
    if use_stp not in STP_ESTIMATOR_CHOICES:
        raise ValueError(f"stp_estimator must be one of {STP_ESTIMATOR_CHOICES}, got {use_stp!r}")
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
    # Read even when the filter is off, so an admitted mover still carries
    # r["contaminated"] = True - callers (the VM runner) refuse to return a
    # recommendation that names one.
    contam = _contaminated()
    # Fetched UNCONDITIONALLY, not gated by estimator - price is a live fact,
    # not a modelled rate, so it stays current in "prior" mode too. Added
    # 3 Sep 2026 after this pool's frozen `now_cost` (last refreshed 8 Aug
    # pre-season) sat stale through 2+ gameweeks of real price movement and
    # made a real transfer target (Enzo, fallen to £6.9m) look unaffordable
    # at its old £7.0m starting price. `needs_live` below still gates the
    # xg90/xa90/... RATE blending (raw/shrunk) specifically - that is a
    # deliberate methodology choice, not something price staleness should
    # force on; price correctness shouldn't depend on which estimator a run
    # happens to be using.
    current = _fetch_current_season()
    # CLUB IS A LIVE FACT, NOT A MODELLED RATE - the same argument the PRICE
    # comment above makes, and the same fix. `teams` above is the frozen
    # 8 Aug 2026 pre-season snapshot, so it names the club a player was at
    # BEFORE the transfer window closed. Everything downstream that keys off
    # a row's club - fixture_adjust.py's opponent multipliers, the 3-per-club
    # and max-attackers-per-club ILP constraints, the `contaminated` fence's
    # team+surname match - was therefore reading a pre-deadline club for
    # every deadline-day mover.
    #
    # ADDED 7 Sep 2026, found while running the GW4 brief: Konsa moved
    # AVL->ARS on deadline day, and NOTHING caught it. He was not in
    # club_changes.json, because fetch_gw_history.py's sweep detects a move by
    # comparing the archive's club against THIS pool's club - and both said
    # AVL, so there was nothing to see. He was not excluded by the
    # `contaminated` fence either, because that match requires the fence's
    # destination club to equal the row's club, and the row said AVL while
    # the fence would have said ARS. One stale field defeated both guards at
    # once. 15 pool players carried a wrong club the day this was fixed, not
    # one. scenario_squad.py's hand-maintained KNOWN_CORRECTIONS dict was the
    # only thing correcting any of them, and only for two players, and only
    # in the scenario tool - never in optimise_squad.py, the weekly tool.
    #
    # `team_prior` is kept on every row because the prior-season club is
    # still the right key for prior-season data: last16_starts.json is keyed
    # by it (below), and fetch_gw_history.py tie-breaks archive name matches
    # on it.
    live_clubs = _live_clubs_cache or {}
    stale_price_n = 0
    club_fixed = []
    live_news = {}   # {id(row): FPL `news` text} for flagged rows, for the STATUS report
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
        team_prior = teams.get(p.get("team"), "?")
        team = live_clubs.get(pid, team_prior)
        if team != team_prior:
            club_fixed.append((name, team_prior, team))
        is_contam = False
        if contam:
            hit_dest = next((dest for w, dest in contam.items()
                              if w.lower() in name.lower() or name.lower() in w.lower()), "MISS")
            # team+surname match — a same-surname player at the WRONG club
            # (see Henderson/Henderson in the docstring above) is not this
            # fence entry and must not be excluded. `dest is None` means the
            # fence line couldn't be parsed — exclude on surname alone rather
            # than silently admit an unverifiable case.
            is_contam = hit_dest != "MISS" and (hit_dest is None or hit_dest == team)
            if is_contam and use_contam_filter:
                excluded.append(f"{name} ({team})")
                continue
        n90 = m / 90.0
        cbi = p.get("clearances_blocks_interceptions", 0) or 0
        tk, rec = p.get("tackles", 0) or 0, p.get("recoveries", 0) or 0
        xgi = f(p.get("expected_goal_involvements"))
        ga = (p.get("goals_scored", 0) or 0) + (p.get("assists", 0) or 0)
        stp_season = (p.get("starts", 0) or 0) / 38
        # PRIOR club, deliberately: last16_starts.json was built on 9 Aug
        # against the frozen snapshot, so its keys are pre-deadline clubs.
        # Looking it up with the corrected live club would miss every mover
        # and silently drop him to the weaker `season_fallback` start rate.
        hit = last16.get((name, team_prior))
        if hit:
            starts16, games16 = hit
            stp, stp_src = starts16 / games16, "last16"
        else:
            stp, stp_src = stp_season, "season_fallback"
        live_cost = current.get(pid, {}).get("now_cost")
        if live_cost is None:
            stale_price_n += 1
        price = (live_cost if live_cost is not None else (p.get("now_cost") or 0)) / 10
        r = dict(name=name, pos=POS[p["element_type"]],
                 team=team, team_prior=team_prior, price=price,
                 # Live FPL status flag, None if the fetch failed - see
                 # LIVE_STATUS_EXCLUDE / is_available().
                 status=current.get(pid, {}).get("status"),
                 # FPL's chance_of_playing_next_round (0-100), None when unset
                 # or the fetch failed - read by is_available() for 'd' rows.
                 chance=current.get(pid, {}).get("chance_of_playing_next_round"),
                 contaminated=is_contam,
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
        if use_stp == "shrunk":
            r["_starts"] = current.get(pid, {}).get("starts")
        if r["status"] not in (None, "a"):
            live_news[id(r)] = (current[pid].get("news") or "").strip()
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

    if use_stp == "shrunk":
        _shrink_start_rates(rows, _fetch_team_games() if current else {}, season_starts)

    # PASS B - intel, availability, score. Same order as the old single-pass
    # loop (intel BEFORE p_cs/score), so a ROLE_INTEL `mult`/`set` entry
    # applies ON TOP of the now-estimated baseline, not the other way round -
    # unchanged whichever estimator ran above.
    out = []
    if use_intel and ia.overlay_active():
        # Trello quarantine overlay (optimise_squad.py --quarantine). Resolved
        # HERE because Trello uses full names and the only trustworthy name
        # list is these rows, clubs already corrected to live.
        for w in ia.resolve_overlay(rows):
            print(f"  {w}", file=sys.stderr)
    for r in rows:
        if use_intel:
            for e in ia.apply(r):
                matched.add((e["player"], e["team"]))
        r["p_cs"] = math.exp(-max(r["xgc90"], 0.05)) if CS[r["pos"]] else 0.0
        r["ok"] = is_available(r)
        r["score"] = scoring.expected_points(r, empirical=use_empirical_dc)
        out.append(r)
    if needs_live and not current:
        print(f"  {use_estimator.upper()}: enabled but no live current-season data "
              f"was available this run (see the fetch warning above, if any) — "
              f"every rate fell back to its prior-only value, same as "
              f"estimator='prior' were passed.", file=sys.stderr)
    if stale_price_n:
        print(f"  PRICE: {stale_price_n}/{len(rows)} player(s) missing from the live "
              f"fetch — using the frozen 8 Aug pre-season price for those (see the "
              f"fetch warning above, if any). Affordability for everyone else is live.",
              file=sys.stderr)
    if club_fixed:
        # Reported, not hidden — the same rule fetch_gw_history.py applies to
        # its unmatched list. A silent club correction would be its own
        # version of the bug this fixes.
        print(f"  CLUB CORRECTED — {len(club_fixed)} player(s) whose frozen 8 Aug "
              f"club is not their live club; scored on the LIVE one: "
              + ", ".join(f"{n} {a}->{b}" for n, a, b in sorted(club_fixed))
              + ". Prior-season rates still describe the OLD club — check the "
                "`contaminated` fence in ROLE_INTEL.md covers anyone here who "
                "matters.", file=sys.stderr)
    elif not live_clubs:
        print(f"  CLUB: no live club map this run (bootstrap-static unreachable) "
              f"— every club is the frozen 8 Aug snapshot's, so any post-deadline "
              f"mover is scored on his OLD club's fixtures.", file=sys.stderr)
    if current:
        # Reported, never silent - the CLUB CORRECTED rule again. Printed even
        # for a player the hand list already covers, so the two can be seen
        # to agree.
        def _news(r):
            n = live_news.get(id(r))
            return f" [{r['status']}: {n}]" if n else f" [{r['status']}]"
        status_out = sorted((r for r in out if r["status"] in LIVE_STATUS_EXCLUDE),
                            key=lambda r: r["name"])
        suspended = sorted((r for r in out if r["status"] == "s"), key=lambda r: r["name"])
        if status_out:
            print(f"  STATUS EXCLUDED — {len(status_out)} player(s) FPL flags as "
                  f"unavailable ('u'), not available ('n') or injured ('i'), set "
                  f"ok=False whatever their rates say: "
                  + ", ".join(f"{r['name']} ({r['team']}){_news(r)}" for r in status_out)
                  + ". A club here may be stale: FPL keeps a player who left the "
                    "league on his old club.", file=sys.stderr)
        doubtful = sorted((r for r in out if r["status"] == "d"), key=lambda r: r["name"])
        d_out = [r for r in doubtful if _doubtful_out(r)]
        d_in = [r for r in doubtful if not _doubtful_out(r)]
        if d_out:
            print(f"  STATUS EXCLUDED (doubtful) — {len(d_out)} player(s) flagged 'd' "
                  f"with chance of playing below {DOUBTFUL_MIN_CHANCE}%, set ok=False: "
                  + ", ".join(f"{r['name']} ({r['team']}, {r['chance']}%){_news(r)}"
                              for r in d_out) + ".", file=sys.stderr)
        if d_in:
            print(f"  STATUS DOUBTFUL — {len(d_in)} player(s) flagged 'd' at "
                  f"{DOUBTFUL_MIN_CHANCE}%+ (or no chance given), still SELECTABLE: "
                  + ", ".join(f"{r['name']} ({r['team']}, {r['chance']}%){_news(r)}"
                              for r in d_in)
                  + ". Check each before acting on a recommendation that names him.",
                  file=sys.stderr)
        if suspended:
            print(f"  STATUS SUSPENDED — {len(suspended)} player(s) FPL flags as "
                  f"suspended ('s'), still SELECTABLE - not excluded automatically: "
                  + ", ".join(f"{r['name']} ({r['team']}){_news(r)}" for r in suspended)
                  + ". Check each end date against the scoring window and add "
                    "anyone it covers to UNAVAILABLE in build_squad.py.",
                  file=sys.stderr)
    else:
        print(f"  STATUS: no live status flags this run (bootstrap-static "
              f"unreachable) — availability is the hand-maintained UNAVAILABLE "
              f"list ONLY, so a player who has left the league since it was last "
              f"updated (Watkins, 15 Sep 2026) can still be picked.", file=sys.stderr)
    if use_intel:
        # UNMATCHED IS A BUG, NOT A NO-OP. A typo'd name/team in the fence
        # would otherwise adjust nothing and say nothing - the exact silent
        # failure this project has been bitten by before (see module docstring
        # of intel_adjust.py).
        for e in ia.load_adjustments():
            if (e["player"], e["team"]) not in matched and not ia.overlay_suppressed(e):
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
        flag = "*" if str(r.get("stp_src", "")).startswith("season_fallback") else " "
        print(f"  {r['name'][:14]:<15}{r['pos']:<5}{r['team']:<5}£{r['price']:<5.1f}"
              f"{r['stp']*100:>4.0f}%{flag}  xP {r['score']:>5.2f}")
    print("  --- bench ---")
    for r in [x for x in sq if x not in xi]:
        flag = "*" if str(r.get("stp_src", "")).startswith("season_fallback") else " "
        print(f"  {r['name'][:14]:<15}{r['pos']:<5}{r['team']:<5}£{r['price']:<5.1f}"
              f"{r['stp']*100:>4.0f}%{flag}")
    if not season_starts and any(str(r.get("stp_src", "")).startswith("season_fallback") for r in xi + sq):
        print("\n  * = no last-16 match found; using full-season start rate as fallback.")


if __name__ == "__main__":
    main()
