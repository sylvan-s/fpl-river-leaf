#!/usr/bin/env python3
"""
FPL Research MCP - read-only Fantasy Premier League research server.

Built for Sylvan Sitkey (River Leaf FC, entry 1041614).

DESIGN CONSTRAINTS:
  * READ-ONLY. Makes only HTTP GET requests. Cannot transfer, captain, or
    change anything. There is deliberately no write path in this file.
  * NO CREDENTIALS. Uses only unauthenticated public endpoints. Nothing to
    store, nothing to leak, unaffected by the PingOne/OIDC login migration.
  * COMPACT OUTPUT. Returns small formatted tables, not raw JSON, so the
    weekly brief spends tokens on reasoning rather than on parsing blobs.

The FPL API is undocumented and may change without notice.
"""

from __future__ import annotations

import datetime as _dt
import os as _os
import sys
import time
import warnings
from typing import Any

import httpx

# scoring.py lives alongside this file in the repo, not on the default
# import path a Claude Desktop-launched process may have — insert this
# file's own directory first so `import scoring` resolves regardless of cwd.
# Pure functions only (json/math/os/sys), so importing it here is cheap and
# has no side effects at import time — see scoring.py's own module docstring
# for why it exists (ending four independently-drifting copies of the same
# formula) and why squad_actual_points() below reuses it rather than adding
# a fifth.
_scoring_dir = _os.path.dirname(_os.path.abspath(__file__))
if _scoring_dir not in sys.path:
    sys.path.insert(0, _scoring_dir)
import scoring
del _scoring_dir  # _PRIORS_DIR (defined further down) is the name every
                  # other function in this file uses for the same path

# Keep stderr clean so real errors stand out in Claude Desktop's MCP log.
warnings.filterwarnings("ignore", message=".*incomplete definition.*")

# --- SDK compatibility --------------------------------------------------------
# Works on both SDK generations. Install pins mcp<2 on purpose: SDK 2.x imports
# `cryptography`, which inside a conda env is frequently linked against an older
# OpenSSL and dies with "symbol not found ... _EVP_DigestSqueeze". SDK 1.x
# imports no cryptography at all. Both paths are covered by test_fpl_mcp.py.
try:
    from mcp.server.mcpserver import MCPServer as _Server  # SDK >= 2.0
except ImportError:  # pragma: no cover
    from mcp.server.fastmcp import FastMCP as _Server  # SDK 1.x

mcp = _Server(
    "fpl-research",
    instructions=(
        "Read-only Fantasy Premier League research. Use xgi_delta for buy/sell "
        "signals, fixture_difficulty for fixture runs, injury_report for "
        "availability, and get_deadline for gameweek timing and chip windows."
    ),
)

BASE = "https://fantasy.premierleague.com/api"
UA = {"User-Agent": "fpl-research-mcp/1.0"}
ENTRY_ID = 1041614  # River Leaf FC

POS = {1: "GKP", 2: "DEF", 3: "MID", 4: "FWD"}
STATUS = {
    "a": "available",
    "d": "DOUBTFUL",
    "i": "INJURED",
    "s": "SUSPENDED",
    "u": "UNAVAILABLE",
    "n": "ON LOAN/NOT ELIGIBLE",
}

# First chip set expires at the GW19 deadline and cannot carry over.
CHIP_SET1_DEADLINE = _dt.datetime(2027, 1, 2, 13, 30, tzinfo=_dt.timezone.utc)

_cache: dict[str, tuple[float, Any]] = {}
_TTL = 900  # 15 min - price changes land daily, not minutely


def _get(path: str, ttl: int = _TTL) -> Any:
    now = time.time()
    hit = _cache.get(path)
    if hit and now - hit[0] < ttl:
        return hit[1]
    r = httpx.get(f"{BASE}{path}", headers=UA, timeout=30.0, follow_redirects=True)
    r.raise_for_status()
    data = r.json()
    _cache[path] = (now, data)
    return data


def _boot() -> Any:
    return _get("/bootstrap-static/")


def _f(v: Any, default: float = 0.0) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _maps() -> tuple[dict, dict]:
    b = _boot()
    return ({t["id"]: t for t in b["teams"]}, {e["id"]: e for e in b["elements"]})


def _next_event() -> dict | None:
    b = _boot()
    for e in b["events"]:
        if e.get("is_next"):
            return e
    for e in b["events"]:
        if e.get("is_current"):
            return e
    return next((e for e in b["events"] if not e.get("finished")), None)


def _price(el: dict) -> str:
    return f"£{el['now_cost'] / 10:.1f}m"


_INTEL_PATH = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "ROLE_INTEL.md")
_intel_cache: dict[str, str] | None = None
_contam_cache: dict[str, str] | None = None


def _intel_block(tag: str) -> dict[str, str]:
    """Parse a fenced ```<tag> block in ROLE_INTEL.md into {name: value}."""
    out: dict[str, str] = {}
    try:
        with open(_INTEL_PATH, encoding="utf-8") as fh:
            text = fh.read()
        parts = text.split("```" + tag, 1)
        if len(parts) > 1:
            for line in parts[1].split("```", 1)[0].strip().splitlines():
                bits = [p.strip() for p in line.split("|")]
                if len(bits) >= 2 and bits[0]:
                    out[bits[0].lower()] = bits[1]
    except Exception:
        pass
    return out


# =============================================================================
# EXTERNAL-RESEARCH ADJUSTMENT LAYER — captaincy_odds' with_intel defaults to
# TRUE since 13 Aug 2026 (was OFF by default). Pass with_intel=False for the
# raw, intel-blind comparison.
#
# FLIPPED to match build_squad.py / optimise_squad.py / fixture_adjust.py,
# which made the same change the same day: pre-season, `stp` (P(start)) here
# is derived purely from LAST SEASON's starts, with zero current-season
# signal - stale for an incumbent, potentially wrong or zero for a
# transferred-in or newly-promoted player. ROLE_INTEL.md's `set stp` overrides
# exist precisely to correct that, but were silently inert on the weekly
# captaincy call before this fix, since with_intel defaulted False and the
# fpl-weekly-brief skill's documented `captaincy_odds` call never passed it.
# See METHODOLOGY_ALTERNATIVES.md A0.5 for the full reasoning (found while
# assessing whether a start-weighted xP objective would add value).
#
# _cap_rows() itself keeps with_intel=False as ITS OWN default - only
# captaincy_odds (the tool) defaults to True and passes it through explicitly.
# log_predictions calls _cap_rows() directly with with_intel left unset
# (i.e. False) ON PURPOSE and unaffected by this change - calibration must
# score the MODEL, not model+intel.
#
# Delegates to intel_adjust.py, the single source of truth for the
# ROLE_INTEL.md `adjustments` fence (also used by build_squad.py) - see that
# file's docstring for the schema and "agreed with Sylvan 10 Aug 2026"
# reasoning. Do not fork a second parser here.
#
# LOADED LAZILY AND DEFENSIVELY, not at import time. This module's
# long-standing rule for every other ROLE_INTEL.md block (_role_intel,
# _contaminated) is "missing or malformed data must never break a screen" - a
# live MCP server has a much higher cost for a hard import failure than a
# standalone script does, so a missing/broken sibling file degrades
# with_intel to a no-op (with a stderr note) rather than taking every tool in
# this server down with it.
#
# Two shapes, per intel_adjust.py:
#   op=mult on xg90/xa90/xgi90/cbit90/cbirt90 - CAPPED to 0.5x-1.5x. A thesis
#     should move a score, never dominate a season of observed data.
#   op=set on stp ONLY - UNCAPPED. Non-availability is a binary fact ("out for
#     four weeks" is P(start)=0), not a graded belief, so it gets no guardrail.
# =============================================================================
MULT_LO, MULT_HI = 0.5, 1.5  # mirrors intel_adjust.py's own - keep in sync

_ia_mod = None
_ia_load_failed = False


def _ia():
    """Lazy-load intel_adjust.py. Cached after the first attempt either way."""
    global _ia_mod, _ia_load_failed
    if _ia_mod is not None or _ia_load_failed:
        return _ia_mod
    try:
        import importlib.util as _il
        spec = _il.spec_from_file_location(
            "intel_adjust",
            _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "intel_adjust.py"))
        mod = _il.module_from_spec(spec)
        spec.loader.exec_module(mod)
        _ia_mod = mod
    except Exception as exc:
        _ia_load_failed = True
        print(f"  INTEL WARNING: intel_adjust.py unavailable ({exc!r}) - "
              f"with_intel=True is a no-op until it's restored", file=sys.stderr)
    return _ia_mod


def _intel_entries(el: dict, teams: dict, current_gw: int | None) -> list[dict]:
    """ROLE_INTEL.md `adjustments` fence entries matching this player (by
    web_name + team short code), filtered to those whose gws window covers
    current_gw (None/ALL entries always match). Returns [] if intel_adjust.py
    is unavailable or the fence is malformed - see the module note above."""
    mod = _ia()
    if mod is None:
        return []
    team = teams.get(el.get("team"), {}).get("short_name", "")
    try:
        entries = mod.entries_for(el.get("web_name", ""), team)
    except SystemExit as exc:
        # intel_adjust.py deliberately raises on a malformed fence row (loud
        # by its own design) - must not take this server down for it.
        print(f"  INTEL WARNING: {exc}", file=sys.stderr)
        return []
    out = []
    for e in entries:
        if e["gws"] is not None and current_gw is not None:
            lo, hi = e["gws"]
            if not (lo <= current_gw <= hi):
                continue
        out.append(e)
    return out


def _contaminated() -> dict[str, str]:
    """Players whose prior-season stats blend two clubs - personal prior unusable."""
    global _contam_cache
    if _contam_cache is None:
        _contam_cache = _intel_block("contaminated")
    return _contam_cache


def _role_intel() -> dict[str, str]:
    """Parse the ```setpieces block in ROLE_INTEL.md.

    Returns {lowercased player name: 'P1F1'}. Curated, unconfirmed intel used
    only to cover the pre-season gap before FPL populates its own fields.
    Never overrides the API - see _setpiece().
    """
    global _intel_cache
    if _intel_cache is not None:
        return _intel_cache
    out: dict[str, str] = {}
    try:
        with open(_INTEL_PATH, encoding="utf-8") as fh:
            text = fh.read()
        block = text.split("```setpieces", 1)
        if len(block) > 1:
            for line in block[1].split("```", 1)[0].strip().splitlines():
                parts = [p.strip() for p in line.split("|")]
                if len(parts) >= 2 and parts[0]:
                    codes = parts[1].replace(" ", "")
                    if codes:
                        out[parts[0].lower()] = codes
    except Exception:
        pass  # missing or malformed file must never break a screen
    _intel_cache = out
    return out


def _setpiece(el: dict) -> str:
    """Set-piece duty. P=penalties, F=direct FKs, C=corners; number = order.

    API data (authoritative) shows plain: 'P1'.
    ROLE_INTEL.md data (expected, unconfirmed) shows with '?': 'P1?'.
    The API always wins where both exist. '-' means neither has anything.
    """
    bits = []
    for key, tag in (
        ("penalties_order", "P"),
        ("direct_freekicks_order", "F"),
        ("corners_and_indirect_freekicks_order", "C"),
    ):
        v = el.get(key)
        if v is not None and v <= 2:      # only 1st and 2nd choice matter
            bits.append(f"{tag}{v}")
    if bits:
        return "".join(bits)              # confirmed by the API

    name = el.get("web_name", "").lower()
    for who, codes in _role_intel().items():
        if who in name or name in who:
            return f"{codes}?"            # from curated intel, unconfirmed
    return "-"


# =============================================================================
# EMPIRICAL-BAYES SHRINKAGE (design D1-D3 in METHODOLOGY_ALTERNATIVES.md)
#
#   shrunk = (n * observed + k * baseline) / (n + k)
#
# n is measured in 90s played. The baseline comes from the fallback ladder in
# _baseline(). k is DERIVED from the data (Poisson-Gamma method of moments),
# not chosen - see _estimate_k().
# =============================================================================

_PRIORS_DIR = _os.path.dirname(_os.path.abspath(__file__))
_PRIORS_PATH = _os.path.join(_PRIORS_DIR, "fpl_priors_2025_26.json")
# v2 adds cards, saves and bps - fields the 7 Aug capture missed. Written to a
# SEPARATE file so the original snapshot is never at risk from a re-run; v2 is
# preferred when present and v1 remains a working fallback.
_PRIORS_PATH_V2 = _os.path.join(_PRIORS_DIR, "fpl_priors_2025_26_v2.json")
_priors_cache: dict | None = None

# Metrics that get shrunk, with how hard. Facts (price, ownership, FDR,
# set-piece order, status) are never shrunk.
SHRINK_METRICS = {
    # key in the snapshot        per-90?  shrink strength note
    "expected_goal_involvements": True,   # gentle  - persistence ~0.63
    "cbirt":                      True,   # gentle  - high volume, no luck
    "cbit":                       True,   # gentle
    "expected_goals_conceded":    True,   # gentle, team-level
    "conversion":                 False,  # HARD    - persistence ~0.12
}


def _load_priors() -> dict:
    """Load the prior-season snapshot. Returns {} if it has not been taken."""
    global _priors_cache
    if _priors_cache is not None:
        return _priors_cache
    import json
    for path in (_PRIORS_PATH_V2, _PRIORS_PATH):   # prefer v2, fall back to v1
        try:
            with open(path, encoding="utf-8") as fh:
                _priors_cache = json.load(fh)
                return _priors_cache
        except Exception:
            continue
    _priors_cache = {}
    return _priors_cache


def _rates(el: dict) -> dict:
    """Per-90 rates plus the raw n (in 90s) from a bootstrap element."""
    mins = el.get("minutes", 0) or 0
    n90 = mins / 90.0
    cbi = el.get("clearances_blocks_interceptions", 0) or 0
    tk = el.get("tackles", 0) or 0
    rec = el.get("recoveries", 0) or 0
    xgi = _f(el.get("expected_goal_involvements"))
    ga = (el.get("goals_scored", 0) or 0) + (el.get("assists", 0) or 0)
    return {
        "n90": n90,
        "expected_goal_involvements": xgi / n90 if n90 else 0.0,
        "expected_goals": _f(el.get("expected_goals")) / n90 if n90 else 0.0,
        "expected_assists": _f(el.get("expected_assists")) / n90 if n90 else 0.0,
        "cbirt": (cbi + tk + rec) / n90 if n90 else 0.0,
        "cbit": (cbi + tk) / n90 if n90 else 0.0,
        "expected_goals_conceded": _f(el.get("expected_goals_conceded")) / n90 if n90 else 0.0,
        # conversion is a ratio, not a per-90 rate: actual returns vs expected
        "conversion": (ga / xgi) if xgi > 0.3 else 1.0,
    }


# =============================================================================
# AVAILABILITY AND SUSPENSION RISK
#
# Minutes, not xG, are the dominant source of blanks. Two separate mechanisms
# are modelled here and they must NOT be conflated:
#
#   1. _availability()  - is he unavailable RIGHT NOW? Deterministic, from the
#      published status flag. This is what belongs in this week's P(blank).
#
#   2. _suspension()    - is he ABOUT to be banned? A fifth yellow picked up
#      this week bans him NEXT week, so this changes nothing about the current
#      gameweek. It is a transfer- and hold-planning signal.
#
# Conflating the two would overstate this week's blank risk and understate the
# cost of buying a player one booking from a ban.
# =============================================================================

# Premier League discipline: (yellows, reached by GW, matches banned).
YELLOW_THRESHOLDS = ((5, 19, 1), (10, 32, 2), (15, 38, 3))


def _availability(el: dict) -> tuple[float, str]:
    """Multiplier on P(start) from the published status flag, plus a label.

    Returns 0.0 for a player who cannot play at all. Before this existed a
    suspended or injured player still received a full P(start) drawn from his
    historical start rate, which made P(blank) badly wrong for exactly the
    players it most needed to be right about.
    """
    st = el.get("status", "a")
    if st in ("s", "i", "u", "n"):
        return 0.0, STATUS.get(st, st)
    if st == "d":
        c = el.get("chance_of_playing_next_round")
        try:
            return max(0.0, min(float(c) / 100.0, 1.0)), "DOUBTFUL"
        except (TypeError, ValueError):
            return 0.5, "DOUBTFUL"          # flagged but no percentage given
    return 1.0, ""


def _suspension(el: dict, gw: int, p_start: float = 1.0) -> dict:
    """Forward-looking ban risk from yellow-card accumulation.

    Cards are deterministic in a way almost nothing else in FPL is: the
    thresholds are published and the count is publicly visible, so a player one
    booking from a ban is a KNOWN risk rather than a modelled one.

    Only the immediately-next threshold matters, because a player cannot cross
    two in a single match (a second-yellow red is a separate rule and is not
    modelled here - it would need per-match data this file does not fetch).
    """
    y = el.get("yellow_cards", 0) or 0
    mins = el.get("minutes", 0) or 0
    n90 = mins / 90.0
    if el.get("status", "a") == "s":
        return {"label": "BANNED", "to_go": 0, "p_ban": 1.0, "yellows": y,
                "threshold": 0, "matches": 0}

    nxt = next(((t, by, ban) for t, by, ban in YELLOW_THRESHOLDS
                if y < t and gw <= by), None)
    if nxt is None:                         # every threshold passed or lapsed
        return {"label": "-", "to_go": 99, "p_ban": 0.0, "yellows": y,
                "threshold": 0, "matches": 0}
    thr, _by, ban = nxt
    to_go = thr - y

    # Poisson booking rate per 90, consistent with the rest of the file.
    rate = (y / n90) if n90 >= 3 else 0.15  # league-ish default on thin minutes
    p_card = 1.0 - 2.718281828459045 ** (-max(rate, 0.0) * max(p_start, 0.0))
    p_ban = p_card if to_go == 1 else 0.0   # cannot jump two thresholds at once

    if to_go == 1:
        label = f"{y}/{thr} RISK"
    elif to_go == 2:
        label = f"{y}/{thr} watch"
    else:
        label = f"{y}/{thr}"
    return {"label": label, "to_go": to_go, "p_ban": p_ban, "yellows": y,
            "threshold": thr, "matches": ban}


def _screen_gw() -> int:
    """Upcoming gameweek, for threshold selection. Falls back to 1 pre-season."""
    try:
        ev = _next_event()
        return ev["id"] if ev else 1
    except Exception:
        return 1


# Ratio of a metric's TRUE sampling variance to the Poisson value (rate/n90).
#
# BUG FIXED 8 Aug 2026. Poisson is correct for COUNTS - tackles, clearances and
# recoveries are whole events, and CBIT behaved fine (k=2.3). It is badly wrong
# for the xG family. xGI is a sum of per-shot PROBABILITIES, ~0.11 each, never
# whole events, so its real variance is roughly q x the Poisson value where q is
# mean xG per shot. Using the Poisson form made sampling_var exceed total_var,
# drove between-variance NEGATIVE (FWD xGI: -0.0275), and collapsed k onto its
# cap or fallback.
#
# WHY THAT MATTERED. k is in units of 90s, so k=60 means a player needs 60 full
# matches before his own data carries half the weight. A season is 38. Every
# attacker would have stayed pinned to his 2025/26 prior for the WHOLE season,
# and "trust shrunk early, raw late" would silently have meant "ignore this
# season". Invisible pre-season only because observed IS the baseline then.
#
# q = 0.11 is ASSUMED, not derived - shots are not in any endpoint this file
# fetches, so it cannot be measured from available data. From GW1 the player_gw
# table gives match-to-match variance directly, which supersedes this constant;
# see _estimate_k(empirical_var=...).
_XG_DISPERSION = 0.11
DISPERSION = {
    "expected_goals": _XG_DISPERSION,
    "expected_assists": _XG_DISPERSION,
    "expected_goal_involvements": _XG_DISPERSION,
    "expected_goals_conceded": _XG_DISPERSION,
    "cbit": 1.0,                           # counts - Poisson is correct
    "cbirt": 1.0,
    "conversion": 1.0,                     # a ratio; handled by its own clamp
}


def _estimate_k(samples: list[tuple[float, float]], dispersion: float = 1.0,
                empirical_var: float | None = None) -> float:
    """Derive k from the data - Poisson-Gamma method of moments.

    samples: [(rate, n90), ...] for the population.
    dispersion: true sampling variance as a multiple of the Poisson value.
                1.0 for counts; ~0.11 for the xG family. See DISPERSION.
    empirical_var: measured per-90 sampling variance, if available. Overrides
                the dispersion model entirely - prefer it once player_gw has
                enough finished gameweeks to measure match-to-match spread.

    Between-player variance is total variance minus expected sampling noise.
    k = mean / between_variance, in units of 90s.

    Intuition: if players genuinely differ a lot, between_var is large and k is
    small - trust individual data quickly. If they are alike and single-match
    results are noisy, between_var is small and k is large - shrink hard.
    """
    pts = [(r, n) for r, n in samples if n >= 3 and r >= 0]
    if len(pts) < 20:
        return 10.0                        # not enough population - safe default
    rates = [r for r, _ in pts]
    m = sum(rates) / len(rates)
    if m <= 0:
        return 10.0
    total_var = sum((r - m) ** 2 for r in rates) / (len(rates) - 1)
    if empirical_var is not None:
        sampling_var = max(empirical_var, 0.0)
    else:
        sampling_var = dispersion * (sum(r / n for r, n in pts) / len(pts))
    between_var = total_var - sampling_var
    if between_var <= 1e-9:
        # Reaching here means the noise model still exceeds the observed spread,
        # which cannot be literally true. Shrink hard, but this is a MODEL
        # FAILURE, not a finding - _k_degenerate() lets callers say so.
        return 40.0
    k = m / between_var
    return max(1.0, min(k, 60.0))          # clamp to a sane range


def _k_degenerate(k: float) -> bool:
    """True if k is a fallback/clamp value rather than something derived.

    The original bug hid behind a silent `return 40.0`. Screens now flag it.
    """
    return abs(k - 40.0) < 1e-9 or abs(k - 60.0) < 1e-9 or abs(k - 10.0) < 1e-9


def _price_band(cost: int) -> int:
    """Price bracket in half-millions, used as a fallback baseline group."""
    return int(round(cost / 5.0))


def _baseline(el: dict, metric: str, pool: list[dict], teams: dict) -> tuple[float, str]:
    """Fallback ladder from design D2. Returns (baseline_value, source_label).

    1. own prior-season rate      (>=900 mins, same club, no flagged role change)
    2. team x position baseline   (club changed)
    3. position x price bracket   (no PL history)
    4. position overall           (last resort)
    """
    pos = POS.get(el["element_type"])
    priors = _load_priors()
    pl = priors.get("players", {}).get(str(el["id"]))

    # --- 1. own prior-season rate ---
    if pl and pl.get("minutes", 0) >= 900:
        same_club = pl.get("team") == el.get("team")
        role_changed = _setpiece(el).endswith("?")   # ROLE_INTEL flagged a change
        nm = el.get("web_name", "").lower()
        # The same_club test cannot catch pre-snapshot transfers - the snapshot
        # records the CURRENT club, not the one those minutes were played for.
        # ROLE_INTEL's `contaminated` block covers them explicitly.
        contaminated = any(w in nm or nm in w for w in _contaminated())
        if same_club and not role_changed and not contaminated:
            v = _rates(pl).get(metric)
            if v is not None:
                return v, "own"

    def _mean(sel: list[dict]) -> float | None:
        vals = [_rates(p)[metric] for p in sel if p.get("minutes", 0) >= 450]
        return sum(vals) / len(vals) if vals else None

    # --- 2. team x position ---
    v = _mean([p for p in pool
               if p["element_type"] == el["element_type"] and p["team"] == el["team"]])
    if v is not None:
        return v, "team+pos"

    # --- 3. position x price bracket ---
    band = _price_band(el["now_cost"])
    v = _mean([p for p in pool
               if p["element_type"] == el["element_type"]
               and _price_band(p["now_cost"]) == band])
    if v is not None:
        return v, "pos+price"

    # --- 4. position overall ---
    v = _mean([p for p in pool if p["element_type"] == el["element_type"]])
    return (v if v is not None else 0.0), "pos"


def _shrunk(el: dict, metric: str, pool: list[dict], teams: dict,
            k: float) -> tuple[float, float, str]:
    """Returns (shrunk_rate, raw_rate, baseline_source)."""
    r = _rates(el)
    raw, n90 = r[metric], r["n90"]
    base, src = _baseline(el, metric, pool, teams)
    if n90 <= 0:
        return base, raw, src + "*"        # no current data at all
    return ((n90 * raw + k * base) / (n90 + k)), raw, src


# ============================================================ LOCAL CACHE ====
# element-summary is one HTTP call PER PLAYER - ~600 calls, 1-3 minutes. That is
# the only slow thing in this server, and it is an API-rate problem, not a query
# problem. So cache the per-gameweek rows locally and never re-fetch them.
#
# CORRECTNESS RULE: only FINISHED gameweeks are persisted. A live gameweek's data
# is still changing, and caching a partial row as final would silently poison
# every downstream analysis. Nothing in this file writes an unfinished round.
#
# The win is across ANALYSES, not weeks: a new gameweek still means a fresh fetch
# per player, but running the backtest five times, or over five different windows,
# costs one fetch instead of five.
# =============================================================================
def _default_db_path() -> str:
    """Where the SQLite store lives.

    DELIBERATELY OUTSIDE THE GOOGLE DRIVE FOLDER. A cloud-sync client can copy a
    SQLite file mid-write, which corrupts it - the database has no idea a second
    process is reading its pages. Text files (the JSON snapshot, the JSONL
    calibration log) are safe there; a live database is not.

    Nothing irreplaceable lives here: player_gw is refetchable from the API and
    player_season reloads from the frozen JSON, so losing this file costs only
    time. Override with FPL_MCP_DB if you want it somewhere specific.
    """
    env = _os.environ.get("FPL_MCP_DB")
    if env:
        return env
    home = _os.path.expanduser("~/.fpl-mcp")
    try:
        _os.makedirs(home, exist_ok=True)
        return _os.path.join(home, "fpl_history_cache.sqlite")
    except Exception:                       # read-only home - fall back
        return _os.path.join(
            _os.path.dirname(_os.path.abspath(__file__)), "fpl_history_cache.sqlite"
        )


_DB_PATH = _default_db_path()

_GW_COLS = (
    "minutes", "total_points", "goals_scored", "assists", "bonus", "bps",
    "expected_goals", "expected_assists", "expected_goal_involvements",
    "expected_goals_conceded", "clean_sheets", "goals_conceded", "saves",
    "clearances_blocks_interceptions", "tackles", "recoveries", "starts",
    "was_home", "opponent_team",
    # added 26 Aug 2026 for the squad page's actual-points deductions bar —
    # see the migration note in _db() for how an existing database picks
    # these up on already-cached gameweeks.
    "yellow_cards", "red_cards", "own_goals", "penalties_missed",
)

# entry_gw is the per-MANAGER counterpart to player_gw: one row per entry per
# finished gameweek, from /entry/{id}/event/{gw}/picks/'s `entry_history`
# object. total_points there is FPL's OWN cumulative total after that
# gameweek (captain doubling and autosubs already applied) - not something
# recomputed from player_gw, which only has raw per-player stats and no idea
# who was captained or benched in any past gameweek.
_ENTRY_GW_COLS = (
    "points", "total_points", "bank", "value",
    "event_transfers", "event_transfers_cost", "points_on_bench", "overall_rank",
)


def _db():
    import sqlite3
    conn = sqlite3.connect(_DB_PATH)
    cols = ",\n            ".join(f"{c} REAL" for c in _GW_COLS)
    conn.execute(f"""
        CREATE TABLE IF NOT EXISTS player_gw (
            player_id INTEGER NOT NULL,
            round     INTEGER NOT NULL,
            {cols},
            fetched_utc TEXT,
            PRIMARY KEY (player_id, round)
        )""")
    # synced_to = the highest FINISHED round we have already pulled for a player.
    # Tracked separately from rows, because a player with no appearance in a
    # gameweek legitimately has no row for it.
    conn.execute("""
        CREATE TABLE IF NOT EXISTS player_sync (
            player_id   INTEGER PRIMARY KEY,
            synced_to   INTEGER NOT NULL,
            fetched_utc TEXT
        )""")
    ecols = ",\n            ".join(f"{c} REAL" for c in _ENTRY_GW_COLS)
    conn.execute(f"""
        CREATE TABLE IF NOT EXISTS entry_gw (
            entry_id  INTEGER NOT NULL,
            event     INTEGER NOT NULL,
            {ecols},
            fetched_utc TEXT,
            PRIMARY KEY (entry_id, event)
        )""")

    # MIGRATION for a database created before a column was added to
    # _GW_COLS (e.g. the 26 Aug 2026 card/own-goal/penalty-miss addition for
    # the squad page's actual-points deductions bar). CREATE TABLE IF NOT
    # EXISTS above is a no-op on a table that already exists, so an older
    # database needs its new column(s) ALTERed in explicitly. That alone
    # leaves already-cached rows with NULL in the new column forever, since
    # a round already marked synced in player_sync is never re-fetched (see
    # _player_history()) — so clear player_sync too, exactly once, the run
    # a column actually gets added. The next cache_history(refresh=True)
    # then re-pulls every player and backfills the new field for
    # gameweeks already on disk. A database created fresh from today's
    # _GW_COLS already has every column from the CREATE TABLE above, so
    # `missing` is empty and this whole block is a cheap PRAGMA-only no-op
    # on every call after the one that actually needed it.
    have = {row[1] for row in conn.execute("PRAGMA table_info(player_gw)")}
    missing = [c for c in _GW_COLS if c not in have]
    if missing:
        for c in missing:
            conn.execute(f"ALTER TABLE player_gw ADD COLUMN {c} REAL")
        conn.execute("DELETE FROM player_sync")

    conn.commit()
    return conn


# --- prior-season totals, loaded from the frozen JSON snapshot ---------------
#
# WHY A SEPARATE TABLE. player_gw holds per-gameweek rows; the snapshot holds
# season TOTALS. Inserting totals into player_gw under a synthetic round number
# would silently double-count in every aggregate query downstream. They are
# different shapes and they stay in different tables.
#
# WHY IT IS SAFE TO KEEP THIS IN THE CACHE FILE. The JSON snapshot remains the
# canonical source and this loader is idempotent, so the table is a DERIVED
# analytical view. Deleting the cache to force a rebuild costs nothing - rerun
# the loader. The irreplaceable data never lives only here.
_SEASON_NUM = (
    "now_cost", "minutes", "starts", "goals_scored", "assists",
    "clearances_blocks_interceptions", "tackles", "recoveries", "clean_sheets",
    "goals_conceded", "total_points", "bonus", "bps", "yellow_cards",
    "red_cards", "saves", "penalties_saved", "own_goals", "penalties_missed",
    "penalties_order", "direct_freekicks_order",
    "corners_and_indirect_freekicks_order", "element_type", "team",
)
# Stored as strings in the API payload - cast on load or every comparison breaks.
_SEASON_REAL = (
    "expected_goals", "expected_assists", "expected_goal_involvements",
    "expected_goals_conceded", "selected_by_percent",
)


def _load_priors_db(db_path: str | None = None) -> str:
    """Load the frozen prior-season snapshot into SQLite for analysis.

    Idempotent: safe to re-run, and re-running after the v2 snapshot exists
    backfills the columns v1 lacked (cards, saves, bps).
    """
    import json
    import sqlite3

    snap, src = None, None
    for path, tag in ((_PRIORS_PATH_V2, "v2"), (_PRIORS_PATH, "v1")):
        try:
            with open(path, encoding="utf-8") as fh:
                snap, src = json.load(fh), tag
            break
        except Exception:
            continue
    if not snap:
        return "No priors snapshot found. Run --snapshot-priors first."

    cols = list(_SEASON_NUM) + list(_SEASON_REAL)
    defs = ", ".join(f"{c} {'REAL' if c in _SEASON_REAL else 'INTEGER'}"
                     for c in cols)
    conn = sqlite3.connect(db_path or _DB_PATH)
    try:
        conn.execute(f"""
            CREATE TABLE IF NOT EXISTS player_season (
                player_id INTEGER NOT NULL,
                season    TEXT    NOT NULL,
                web_name  TEXT,
                {defs},
                source       TEXT,
                captured_utc TEXT,
                PRIMARY KEY (player_id, season)
            )""")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS team_season (
                team_id    INTEGER NOT NULL,
                season     TEXT    NOT NULL,
                short_name TEXT,
                PRIMARY KEY (team_id, season)
            )""")
        # Mechanical per-90 divisions only. Archetype logic and `conversion`
        # deliberately live in Python (_rates) so there is ONE implementation of
        # anything with a judgement call in it.
        conn.execute("DROP VIEW IF EXISTS v_player_season_rates")
        conn.execute("""
            CREATE VIEW v_player_season_rates AS
            SELECT player_id, season, web_name, element_type, team, now_cost,
                   minutes, starts, minutes/90.0 AS n90,
                   CASE WHEN minutes>0 THEN expected_goal_involvements/(minutes/90.0) END AS xgi90,
                   CASE WHEN minutes>0 THEN expected_goals_conceded/(minutes/90.0) END AS xgc90,
                   CASE WHEN minutes>0 THEN
                        (clearances_blocks_interceptions+tackles)/(minutes/90.0) END AS cbit90,
                   CASE WHEN minutes>0 THEN
                        (clearances_blocks_interceptions+tackles+recoveries)/(minutes/90.0) END AS cbirt90,
                   (goals_scored+assists) - expected_goal_involvements AS delta,
                   clean_sheets, yellow_cards, bps, saves, selected_by_percent
            FROM player_season""")

        season = snap.get("season_described", "unknown")
        cap = snap.get("captured_utc", "")
        for tid, sn in (snap.get("teams") or {}).items():
            conn.execute("INSERT OR REPLACE INTO team_season VALUES (?,?,?)",
                         (int(tid), season, sn))

        def _num(v):
            if v is None or v == "":
                return None
            try:
                return float(v)
            except (TypeError, ValueError):
                return None

        n = 0
        ph = ",".join("?" * (len(cols) + 5))
        for pid, p in (snap.get("players") or {}).items():
            vals = [int(pid), season, p.get("web_name")]
            vals += [_num(p.get(c)) for c in cols]
            vals += [f"priors_snapshot_{src}", cap]
            conn.execute(f"INSERT OR REPLACE INTO player_season VALUES ({ph})", vals)
            n += 1
        conn.commit()

        have = [c for c in ("yellow_cards", "saves", "bps") if conn.execute(
            f"SELECT COUNT({c}) FROM player_season").fetchone()[0] > 0]
        missing = [c for c in ("yellow_cards", "saves", "bps") if c not in have]
    finally:
        conn.close()

    out = [
        "PRIOR-SEASON TABLE LOADED",
        f"  source   {src} snapshot ({season}, captured {cap[:19]})",
        f"  players  {n}",
        f"  tables   player_season, team_season",
        f"  view     v_player_season_rates (per-90s; archetypes stay in Python)",
    ]
    if missing:
        out.append(f"  EMPTY    {', '.join(missing)} - v1 snapshot lacks these. "
                   f"Re-run --snapshot-priors then --load-priors-db to backfill.")
    return "\n".join(out)


def _finished_rounds() -> set[int]:
    """Gameweeks whose data is final. Anything else must not be persisted."""
    return {e["id"] for e in _boot().get("events", [])
            if e.get("finished") and e.get("data_checked", True)}


def _player_history(player_id: int, force: bool = False) -> list[dict]:
    """Per-gameweek history for one player, served from cache where possible.

    Returns the same shape the API does, so call sites need no other change.
    """
    fin = _finished_rounds()
    max_fin = max(fin) if fin else 0
    conn = _db()
    try:
        row = conn.execute("SELECT synced_to FROM player_sync WHERE player_id=?",
                           (player_id,)).fetchone()
        synced = row[0] if row else -1

        if not force and synced >= max_fin and max_fin > 0:
            cur = conn.execute(
                f"SELECT round,{','.join(_GW_COLS)} FROM player_gw "
                f"WHERE player_id=? ORDER BY round", (player_id,))
            return [dict(zip(("round",) + _GW_COLS, r)) for r in cur.fetchall()]

        hist = _get(f"/element-summary/{player_id}/", ttl=3600)["history"]

        if max_fin > 0:
            now = _dt.datetime.now(_dt.timezone.utc).isoformat()
            rows = []
            for h in hist:
                r = h.get("round")
                if r in fin:                      # ONLY finished gameweeks
                    rows.append([player_id, r]
                                + [h.get(c) for c in _GW_COLS] + [now])
            if rows:
                conn.executemany(
                    f"INSERT OR REPLACE INTO player_gw "
                    f"(player_id,round,{','.join(_GW_COLS)},fetched_utc) "
                    f"VALUES ({','.join('?' * (len(_GW_COLS) + 3))})", rows)
            conn.execute("INSERT OR REPLACE INTO player_sync VALUES (?,?,?)",
                         (player_id, max_fin, now))
            conn.commit()
        return hist
    finally:
        conn.close()


@mcp.tool(
    description=(
        "Warm or inspect the local history cache. element-summary is one HTTP call "
        "per player, so the first pass is slow (1-3 min) and every later analysis "
        "is instant. Only FINISHED gameweeks are stored - a live gameweek is still "
        "changing and caching it as final would poison downstream analysis. Run "
        "with refresh=False to just see cache status. Stores minutes, goals, "
        "assists, clean sheets, defensive actions, cards, own goals and penalty "
        "misses per player per gameweek - the squad page's Expected/Actual "
        "points-breakdown toggle reads this table directly (offline, no MCP call "
        "of its own) once it's warm."
    )
)
def cache_history(refresh: bool = True, max_players: int = 700,
                  min_minutes: int = 1) -> str:
    import sqlite3
    b = _boot()
    fin = _finished_rounds()
    max_fin = max(fin) if fin else 0

    conn = _db()
    try:
        n_rows = conn.execute("SELECT COUNT(*) FROM player_gw").fetchone()[0]
        n_pl = conn.execute("SELECT COUNT(*) FROM player_sync").fetchone()[0]
        up_to_date = conn.execute(
            "SELECT COUNT(*) FROM player_sync WHERE synced_to>=?", (max_fin,)
        ).fetchone()[0] if max_fin else 0
    finally:
        conn.close()

    # The store holds TWO shapes: per-gameweek rows and prior-season totals.
    # Reporting only the former made it impossible to tell from chat whether the
    # priors load had actually run.
    conn = _db()
    try:
        season = conn.execute(
            "SELECT season, source, COUNT(*) FROM player_season GROUP BY season, source"
        ).fetchall()
        filled = conn.execute(
            "SELECT COUNT(yellow_cards), COUNT(saves), COUNT(bps) FROM player_season"
        ).fetchone()
    except Exception:
        season, filled = [], (0, 0, 0)
    finally:
        conn.close()

    out = [
        "LOCAL STORE",
        f"  file            {_DB_PATH}",
        "",
        "  player_gw (per-gameweek, current season)",
        f"    finished GWs    {sorted(fin) if fin else 'none yet (pre-season)'}",
        f"    rows stored     {n_rows}",
        f"    players tracked {n_pl}  ({up_to_date} current to GW{max_fin})",
        "",
        "  player_season (prior-season totals, from the frozen snapshot)",
    ]
    if not season:
        out.append("    NOT LOADED - run:  python fpl_research_mcp.py --load-priors-db")
    for s, src, cnt in season:
        out.append(f"    {s}  {cnt} players  (source: {src})")
        out.append(f"    cards/saves/bps populated: {filled[0]}/{filled[1]}/{filled[2]}"
                   + ("  <- v1 snapshot, re-run --snapshot-priors then --load-priors-db"
                      if filled[2] == 0 else ""))
    if max_fin == 0:
        out += ["", "No finished gameweeks yet, so there is nothing to cache. "
                    "Nothing is stored until a gameweek is final."]
        return "\n".join(out)

    if not refresh:
        return "\n".join(out)

    pool = [e for e in b["elements"] if (e.get("minutes") or 0) >= min_minutes]
    pool.sort(key=lambda e: -(e.get("minutes") or 0))
    pool = pool[:max_players]

    fetched = served = errors = 0
    for el in pool:
        try:
            before = _cache.get(f"/element-summary/{el['id']}/")
            _player_history(el["id"])
            after = _cache.get(f"/element-summary/{el['id']}/")
            if after is not before:
                fetched += 1
            else:
                served += 1
        except Exception:
            errors += 1

    conn = _db()
    try:
        n_rows2 = conn.execute("SELECT COUNT(*) FROM player_gw").fetchone()[0]
        size = _os.path.getsize(_DB_PATH) / 1024
    finally:
        conn.close()

    out += [
        "",
        f"REFRESH: {len(pool)} players considered",
        f"  fetched from API  {fetched}",
        f"  served from cache {served}",
        f"  errors            {errors}",
        f"  rows now          {n_rows2}  (+{n_rows2 - n_rows})",
        f"  db size           {size:.0f} KB",
        "",
        "Later analyses over these gameweeks now cost no API calls. Re-run after "
        "each gameweek finishes to keep it current.",
    ]
    return "\n".join(out)


# ------------------------------------------------------------- entry history --
_ENTRY_SNAPSHOT_PATH = _os.path.join(_PRIORS_DIR, "docs", "data", "entry_summary.json")


def _entry_history(entry: int = ENTRY_ID) -> tuple[list[dict], list[int]]:
    """Per-gameweek ACTUAL points for one manager's entry, cached in entry_gw.

    Same shape of fix as _player_history(): only finished gameweeks are ever
    persisted (a live gameweek's total is still moving), and a gameweek
    already cached is never re-fetched. Unlike player_gw there is no separate
    sync table - an entry only ever has up to 38 rows, so a plain
    `SELECT MAX(event)` is cheap enough not to need one.

    Returns (rows ordered by event, event ids that failed to fetch this call -
    typically a transient API hiccup, not something to persist as a gap).
    """
    fin = sorted(_finished_rounds())
    conn = _db()
    try:
        have = {r[0] for r in conn.execute(
            "SELECT event FROM entry_gw WHERE entry_id=?", (entry,))}
        missing = [gw for gw in fin if gw not in have]
        errors: list[int] = []
        if missing:
            now = _dt.datetime.now(_dt.timezone.utc).isoformat()
            for gw in missing:
                try:
                    data = _get(f"/entry/{entry}/event/{gw}/picks/", ttl=3600)
                except httpx.HTTPStatusError:
                    errors.append(gw)
                    continue
                eh = data.get("entry_history", {})
                if not eh:
                    errors.append(gw)
                    continue
                row = [entry, gw] + [eh.get(c) for c in _ENTRY_GW_COLS] + [now]
                conn.execute(
                    f"INSERT OR REPLACE INTO entry_gw "
                    f"(entry_id,event,{','.join(_ENTRY_GW_COLS)},fetched_utc) "
                    f"VALUES ({','.join('?' * (len(_ENTRY_GW_COLS) + 3))})", row)
            conn.commit()
        cur = conn.execute(
            f"SELECT event,{','.join(_ENTRY_GW_COLS)} FROM entry_gw "
            f"WHERE entry_id=? ORDER BY event", (entry,))
        rows = [dict(zip(("event",) + _ENTRY_GW_COLS, r)) for r in cur.fetchall()]
        return rows, errors
    finally:
        conn.close()


def _write_dashboard_snapshot(snap: dict, path: str) -> None:
    """Best-effort JSON write for build_squad_page.py to read OFFLINE - that
    script (like every build_*.py page except build_prediction_tracker.py)
    is a pure function of local files and makes no network calls of its own.
    This is the bridge that gets live data into that contract, shared by
    every tool on this file that has a dashboard snapshot to write (see
    _ROUTE_ACTUAL_SNAPSHOT_PATH below for the second user). Wrapped in
    try/except because writing the snapshot is a bonus, not the job the
    calling tool exists to do - a filesystem hiccup here must not stop that
    tool from returning its actual answer to whoever called it."""
    try:
        _os.makedirs(_os.path.dirname(path), exist_ok=True)
        import json
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(snap, fh, indent=2)
    except Exception:
        pass


@mcp.tool(
    description=(
        "Actual cumulative FPL points for the entry (total to date, average per "
        "gameweek) plus the next deadline. Fetches only newly-finished gameweeks "
        "not already cached in entry_gw - cheap, safe to call often, unlike "
        "cache_history's ~700-call player refresh. Also refreshes "
        "docs/data/entry_summary.json so the squad dashboard page can show this "
        "offline without its own network call."
    )
)
def entry_summary(entry: int = ENTRY_ID) -> str:
    rows, errors = _entry_history(entry)
    ev = _next_event()
    next_gw = ev["id"] if ev else None
    next_deadline = ev["deadline_time"] if ev else None

    if not rows:
        msg = f"No finished-gameweek history cached yet for entry {entry}."
        if errors:
            msg += f" {len(errors)} gameweek(s) failed to fetch: {errors}."
        return msg

    total = rows[-1]["total_points"]
    gws = len(rows)
    avg = total / gws if gws else 0.0
    snap = {
        "entry": entry,
        "total_points": total,
        "gws_played": gws,
        "avg_per_gw": round(avg, 1),
        "next_gw": next_gw,
        "next_deadline_utc": next_deadline,
        "fetched_utc": _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds"),
    }
    _write_dashboard_snapshot(snap, _ENTRY_SNAPSHOT_PATH)

    out = [
        f"Entry {entry} - {gws} finished gameweek(s) cached (GW{rows[0]['event']}-{rows[-1]['event']})",
        f"Total points {total:.0f}  |  average {avg:.1f} per gameweek",
    ]
    if ev:
        dl = _dt.datetime.fromisoformat(next_deadline.replace("Z", "+00:00"))
        now = _dt.datetime.now(_dt.timezone.utc)
        delta = dl - now
        when = (f"{delta.days}d {int(delta.total_seconds() % 86400 // 3600)}h away"
                if delta.total_seconds() > 0 else "DEADLINE PASSED")
        out.append(f"Next deadline: GW{next_gw} - {dl:%a %d %b %Y %H:%M} UTC ({when})")
    if errors:
        out.append(f"{len(errors)} gameweek(s) failed to fetch and were skipped: {errors}")
    out.append(f"dashboard snapshot written: {_os.path.relpath(_ENTRY_SNAPSHOT_PATH, _PRIORS_DIR)}")
    return "\n".join(out)


# --------------------------------------------------------- squad actual pts --
# WHY THIS EXISTS. build_squad_page.py's "Where the points come from" chart
# (Expected/Actual toggle, added 26 Aug 2026) originally read player_gw
# straight out of SQLite itself. That works when Sylvan runs the build from
# his own terminal, but not from a Cowork/Claude session — every sandboxed
# session's $HOME is its own container, with no route to
# ~/.fpl-mcp/fpl_history_cache.sqlite on the real machine, only to the
# explicitly connected ~/Projects/FPL folder. This tool runs where the
# database actually lives (this MCP server, launched by Claude Desktop on
# Sylvan's own machine) and writes the small aggregate the chart needs into
# docs/data/ — inside the connected folder, reachable from anywhere — the
# same fix entry_summary already applies to the same problem for total
# points and the deadline.
_ROUTE_ACTUAL_SNAPSHOT_PATH = _os.path.join(_PRIORS_DIR, "docs", "data", "route_actual_snapshot.json")
_ROUTE_ACTUAL_POS_KEYS = ("appearance", "goal_involvement", "clean_sheets",
                          "defensive_contribution", "saves", "bonus")
_ROUTE_ACTUAL_DED_KEYS = ("goals_conceded", "yellow_cards", "red_cards",
                          "own_goals", "penalties_missed")


def _squad_xi() -> list[dict]:
    """The current XI's name+pos from squad.json - two fields only, read
    directly rather than through squad_state.py's full validation. That
    module's fail-loudly-on-any-defect posture is right for the pipeline
    that actually SELECTS the squad; this is a read-only reporting tool that
    should degrade to "nothing to compute" on a malformed or missing
    squad.json rather than raise into the MCP caller."""
    path = _os.path.join(_PRIORS_DIR, "squad.json")
    try:
        import json
        raw = json.load(open(path, encoding="utf-8"))
    except Exception:
        return []
    return [{"name": p["name"], "pos": p["pos"]}
            for p in raw.get("squad", []) if p.get("role") == "XI"]


@mcp.tool(
    description=(
        "Real per-gameweek average points for the CURRENT squad's XI "
        "(squad.json), split the same way the squad page's Expected/Actual "
        "chart is: six earned categories (appearance, goal involvement, "
        "clean sheets, defensive contribution, saves, bonus) plus five "
        "deductions (goals conceded, yellow/red cards, own goals, penalty "
        "misses). Reads player_gw locally, no new API calls of its own - "
        "call cache_history first if it hasn't been warmed since the "
        "card/own-goal/penalty-miss columns were added (26 Aug 2026). "
        "Writes docs/data/route_actual_snapshot.json so the squad page can "
        "show this offline, the same pattern entry_summary uses for total "
        "points."
    )
)
def squad_actual_points() -> str:
    xi = _squad_xi()
    if not xi:
        return "squad.json not found, unreadable, or has no XI players — nothing to compute."

    import json
    try:
        with open(_PRIORS_PATH_V2, encoding="utf-8") as fh:
            snap = json.load(fh)
    except Exception:
        return (f"Prior-season snapshot not found at {_PRIORS_PATH_V2} — "
                 f"needed to resolve player names to FPL ids.")
    id_by_name = {p.get("web_name"): pid for pid, p in snap.get("players", {}).items()}

    ids: dict[int, str] = {}
    unresolved = []
    for p in xi:
        pid = id_by_name.get(p["name"])
        if pid is not None:
            ids[int(pid)] = p["pos"]
        else:
            unresolved.append(p["name"])
    if not ids:
        return f"None of the XI's {len(xi)} names resolved to an FPL id — nothing to compute."

    cols = ("minutes", "goals_scored", "assists", "clean_sheets", "goals_conceded",
            "saves", "bonus", "clearances_blocks_interceptions", "tackles", "recoveries",
            "yellow_cards", "red_cards", "own_goals", "penalties_missed")
    conn = _db()
    try:
        placeholders = ",".join("?" * len(ids))
        rows = conn.execute(
            f"SELECT player_id, round, {','.join(cols)} FROM player_gw "
            f"WHERE player_id IN ({placeholders})", list(ids)).fetchall()
    finally:
        conn.close()

    if not rows:
        return (f"No cached player_gw rows yet for any of the {len(ids)} resolved "
                 f"XI player(s) — call cache_history(refresh=True) first.")

    by_gw: dict[int, tuple[dict, dict]] = {}
    for r in rows:
        pid, rnd, rest = r[0], r[1], r[2:]
        row = dict(zip(cols, rest))
        pos_pts, ded_pts = scoring.actual_points_breakdown(row, ids[pid])
        acc = by_gw.setdefault(rnd, ({k: 0.0 for k in _ROUTE_ACTUAL_POS_KEYS},
                                      {k: 0.0 for k in _ROUTE_ACTUAL_DED_KEYS}))
        for k in _ROUTE_ACTUAL_POS_KEYS:
            acc[0][k] += pos_pts[k]
        for k in _ROUTE_ACTUAL_DED_KEYS:
            acc[1][k] += ded_pts[k]

    n_gw = len(by_gw)
    totals_pos = {k: 0.0 for k in _ROUTE_ACTUAL_POS_KEYS}
    totals_ded = {k: 0.0 for k in _ROUTE_ACTUAL_DED_KEYS}
    for pos_pts, ded_pts in by_gw.values():
        for k in _ROUTE_ACTUAL_POS_KEYS:
            totals_pos[k] += pos_pts[k]
        for k in _ROUTE_ACTUAL_DED_KEYS:
            totals_ded[k] += ded_pts[k]

    snap_out = {
        "gws": sorted(by_gw),
        "positive": {k: round(v / n_gw, 4) for k, v in totals_pos.items()},
        "deductions": {k: round(v / n_gw, 4) for k, v in totals_ded.items()},
        "resolved": len(ids), "xi_size": len(xi), "unresolved": unresolved,
        "fetched_utc": _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds"),
    }
    _write_dashboard_snapshot(snap_out, _ROUTE_ACTUAL_SNAPSHOT_PATH)

    total = sum(snap_out["positive"].values()) + sum(snap_out["deductions"].values())
    out = [
        f"XI actual points: {total:.2f}/GW avg over {n_gw} finished gameweek(s) "
        f"(GW{snap_out['gws'][0]}-{snap_out['gws'][-1]}), "
        f"{len(ids)}/{len(xi)} XI players resolved to an FPL id",
    ]
    if unresolved:
        out.append(f"unresolved (not in the prior-season snapshot, skipped): {unresolved}")
    out.append(f"snapshot written: {_os.path.relpath(_ROUTE_ACTUAL_SNAPSHOT_PATH, _PRIORS_DIR)}")
    return "\n".join(out)


# ---------------------------------------------------------------- deadline ---
@mcp.tool(description="Current/next gameweek, exact deadline, and chip-window status.")
def get_deadline() -> str:
    ev = _next_event()
    if not ev:
        return "No upcoming gameweek found (season may be complete)."
    dl = _dt.datetime.fromisoformat(ev["deadline_time"].replace("Z", "+00:00"))
    now = _dt.datetime.now(_dt.timezone.utc)
    delta = dl - now
    hrs = delta.total_seconds() / 3600

    when = (
        f"{delta.days}d {int(hrs % 24)}h away"
        if delta.total_seconds() > 0
        else "DEADLINE PASSED"
    )
    out = [
        f"{ev['name']} (event id {ev['id']})",
        f"Deadline: {dl:%a %d %b %Y %H:%M} UTC  ({when})",
    ]
    chip_left = CHIP_SET1_DEADLINE - now
    if chip_left.total_seconds() > 0:
        out.append(
            f"Chip set 1 expires {CHIP_SET1_DEADLINE:%a %d %b %Y %H:%M} UTC "
            f"- {chip_left.days}d left. Wildcard/Free Hit/Bench Boost/Triple "
            f"Captain in set 1 do NOT carry over."
        )
    else:
        out.append("Chip set 1 window has closed; set 2 in play.")
    if ev.get("average_entry_score"):
        out.append(f"Average score: {ev['average_entry_score']}")
    return "\n".join(out)


# --------------------------------------------------------------- xGI delta ---
@mcp.tool(
    description=(
        "SECONDARY discount screen. Delta = (goals+assists) - xGI. Rank on xGI "
        "first via analyze_players(sort_by='xgi') - chance creation persists ~0.63 "
        "year to year, finishing overperformance only ~0.12, so xGI is the signal "
        "and delta is mostly noise. Use delta to find which HIGH-xGI players are "
        "underpriced (negative delta = cheap because goals haven't landed yet). Do "
        "not sell a high-xGI player on positive delta alone, and note that penalty "
        "takers run structurally positive. Set season=False for a rolling last-N "
        "window (slower, one call per player)."
    )
)
def xgi_delta(
    position: str = "MID,FWD",
    min_minutes: int = 270,
    max_price: float = 15.5,
    limit: int = 20,
    season: bool = True,
    last_n: int = 4,
) -> str:
    teams, _ = _maps()
    b = _boot()
    want = {p.strip().upper() for p in position.split(",") if p.strip()}

    rows = []
    for el in b["elements"]:
        if POS.get(el["element_type"]) not in want:
            continue
        if el["now_cost"] / 10 > max_price:
            continue
        if el.get("minutes", 0) < min_minutes:
            continue

        if season:
            xgi = _f(el.get("expected_goal_involvements"))
            ga = el.get("goals_scored", 0) + el.get("assists", 0)
            mins = el.get("minutes", 0)
        else:
            try:
                hist = _player_history(el["id"])
            except Exception:
                continue
            recent = hist[-last_n:]
            if not recent:
                continue
            xgi = sum(_f(h.get("expected_goal_involvements")) for h in recent)
            ga = sum(h.get("goals_scored", 0) + h.get("assists", 0) for h in recent)
            mins = sum(h.get("minutes", 0) for h in recent)

        if xgi <= 0 and ga == 0:
            continue
        rows.append(
            {
                "name": el["web_name"],
                "team": teams[el["team"]]["short_name"],
                "pos": POS[el["element_type"]],
                "price": _price(el),
                "xgi": xgi,
                "ga": ga,
                "delta": ga - xgi,
                "mins": mins,
                "own": _f(el.get("selected_by_percent")),
                "status": el.get("status", "a"),
                "news": (el.get("news") or "").strip(),
            }
        )

    if not rows:
        return (
            "No players matched. Early in the season min_minutes is often the "
            "blocker - try min_minutes=0."
        )

    scope = "season-to-date" if season else f"last {last_n} GW"
    buys = sorted(rows, key=lambda r: r["delta"])[:limit]
    sells = sorted(rows, key=lambda r: -r["delta"])[:limit]

    def table(rs: list[dict]) -> str:
        head = (
            f"{'Player':<16}{'Tm':<5}{'Pos':<5}{'Price':<8}"
            f"{'xGI':>6}{'G+A':>6}{'Delta':>8}{'Own%':>7}  Flag"
        )
        lines = [head, "-" * len(head)]
        for r in rs:
            flag = "" if r["status"] == "a" else STATUS.get(r["status"], r["status"])
            lines.append(
                f"{r['name'][:15]:<16}{r['team']:<5}{r['pos']:<5}{r['price']:<8}"
                f"{r['xgi']:>6.2f}{r['ga']:>6}{r['delta']:>+8.2f}{r['own']:>7.1f}  {flag}"
            )
        return "\n".join(lines)

    return (
        f"xGI DELTA ({scope}, min {min_minutes} mins, <= £{max_price}m)\n\n"
        f"UNDERPERFORMERS - regression BUY candidates (most negative delta):\n"
        f"{table(buys)}\n\n"
        f"OVERPERFORMERS - SELL/avoid unless elite finisher:\n"
        f"{table(sells)}\n\n"
        f"Cross-reference the buy list against fixture_difficulty before acting."
    )


# ------------------------------------------------------------------ fixtures --
@mcp.tool(
    description=(
        "League-wide fixture runs over the next N gameweeks, SPLIT BY POSITION. "
        "FPL's own FDR merges attacking and defensive difficulty into one integer "
        "and is no longer used here: a leaky-but-potent opponent is good for your "
        "attackers and bad for your defenders at the same time. Instead this "
        "derives opponent strength from xG (same model as captaincy_odds and "
        "fixture_outlook, so they cannot contradict each other) and reports two "
        "columns. Also flags doubles and blanks. sort_by: 'attack' or 'defence'."
    )
)
def fixture_difficulty(next_n: int = 4, sort_by: str = "attack") -> str:
    teams, _ = _maps()
    ev = _next_event()
    if not ev:
        return "No upcoming gameweek."
    start = ev["id"]
    window = set(range(start, start + next_n))

    per_gw: dict[int, dict[int, int]] = {t: {} for t in teams}
    for f in _get("/fixtures/?future=1", ttl=3600):
        if f.get("event") not in window:
            continue
        for side in ("team_h", "team_a"):
            tid = f.get(side)
            if tid in per_gw:
                per_gw[tid][f["event"]] = per_gw[tid].get(f["event"], 0) + 1

    rows = []
    for tid in teams:
        fxs = _window_factors(tid, start, next_n, teams)
        if not fxs:
            continue
        att = sum(f["def_factor"] for f in fxs) / len(fxs)   # your attack multiplier
        dfn = sum(f["att_factor"] for f in fxs) / len(fxs)   # your goals-conceded multiplier
        rows.append({
            "team": teams[tid]["short_name"], "att": att, "dfn": dfn, "n": len(fxs),
            "doubles": [gw for gw, c in per_gw[tid].items() if c > 1],
            "blanks": [gw for gw in window if per_gw[tid].get(gw, 0) == 0],
            "unknown": sum(1 for f in fxs if not f["known"]),
        })
    if not rows:
        return "No fixtures scheduled in that window."

    rows.sort(key=(lambda r: r["dfn"]) if sort_by.lower().startswith("d")
              else (lambda r: -r["att"]))

    lines = [
        f"FIXTURE RUNS, GW{start}-{start + next_n - 1}  (sorted by {sort_by})",
        "ATT x = multiplier on your ATTACKERS' output   - HIGHER is better",
        "DEF x = multiplier on the goals you CONCEDE    - LOWER is better",
        "",
        f"{'Team':<6}{'ATT x':>8}{'DEF x':>8}{'Gms':>5}  Notes",
        "-" * 56,
    ]
    for r in rows:
        notes = []
        if r["doubles"]:
            notes.append("DGW " + ",".join(f"GW{g}" for g in sorted(r["doubles"])))
        if r["blanks"]:
            notes.append("BLANK " + ",".join(f"GW{g}" for g in sorted(r["blanks"])))
        if r["unknown"]:
            notes.append(f"{r['unknown']} vs no-data side(s)")
        lines.append(f"{r['team']:<6}{r['att']:>8.2f}{r['dfn']:>8.2f}{r['n']:>5}  "
                     f"{'; '.join(notes)}")

    # The point of two columns: surface where they disagree.
    best_att = max(rows, key=lambda r: r["att"])
    best_def = min(rows, key=lambda r: r["dfn"])
    lines += ["", f"Best run for ATTACKERS: {best_att['team']} ({best_att['att']:.2f}x)",
              f"Best run for DEFENDERS: {best_def['team']} ({best_def['dfn']:.2f}x conceded)"]
    if best_att["team"] != best_def["team"]:
        lines.append("These differ - which is exactly why one FDR integer is not enough. "
                     "Pick the column that matches the position you are buying.")
    lines += [
        "",
        "Derived from opponent xG/xGC (shrunk toward the prior season early on), NOT",
        "from FPL's FDR. Same model as captaincy_odds and fixture_outlook.",
        "Sides with no PL data (promoted) are assumed league average - GENEROUS to",
        "them, so those fixtures are probably easier than shown.",
    ]
    if next_n > 6:
        lines.append("CAUTION: beyond ~6 gameweeks cup rescheduling moves fixtures.")
    return "\n".join(lines)


# ------------------------------------------------------------------ injuries --
@mcp.tool(
    description=(
        "Availability flags. Pass names='Isak,Rice' to check specific players, "
        "or leave blank to list every currently flagged player."
    )
)
def injury_report(names: str = "", max_rows: int = 40) -> str:
    teams, _ = _maps()
    b = _boot()
    wanted = [n.strip().lower() for n in names.split(",") if n.strip()]

    rows = []
    for el in b["elements"]:
        flagged = el.get("status", "a") != "a"
        nm = el["web_name"].lower()
        if wanted:
            if not any(w in nm for w in wanted):
                continue
        elif not flagged:
            continue
        rows.append(
            f"{el['web_name'][:18]:<19}{teams[el['team']]['short_name']:<5}"
            f"{POS[el['element_type']]:<5}{_price(el):<8}"
            f"{STATUS.get(el.get('status','a'),'?'):<14}"
            f"{el.get('chance_of_playing_next_round') if el.get('chance_of_playing_next_round') is not None else '-':>4}%  "
            f"{(el.get('news') or '').strip()[:60]}"
        )

    if not rows:
        return "No flagged players matched." if wanted else "No players currently flagged."
    head = f"{'Player':<19}{'Tm':<5}{'Pos':<5}{'Price':<8}{'Status':<14}{'Odds':>5}  News"
    return "\n".join([head, "-" * len(head)] + rows[:max_rows])


# --------------------------------------------------------------------- squad --
@mcp.tool(
    description=(
        "Read a squad for a given gameweek. PUBLIC ONLY AFTER THAT GW'S DEADLINE - "
        "before the deadline the live team is private and this returns an error. "
        "Defaults to Sylvan's entry and the most recent locked gameweek."
    )
)
def get_squad(entry: int = ENTRY_ID, gameweek: int = 0) -> str:
    teams, els = _maps()
    if gameweek <= 0:
        ev = _next_event()
        gameweek = max(1, (ev["id"] - 1) if ev else 1)
    try:
        data = _get(f"/entry/{entry}/event/{gameweek}/picks/", ttl=300)
    except httpx.HTTPStatusError as e:
        return (
            f"Could not read GW{gameweek} for entry {entry} (HTTP {e.response.status_code}). "
            f"Picks only become public after that gameweek's deadline. "
            f"For a team you are still editing, check the FPL site directly."
        )

    ec = data.get("entry_history", {})
    lines = [
        f"Entry {entry} - GW{gameweek}",
        f"Points {ec.get('points','?')} | Bank £{_f(ec.get('bank'))/10:.1f}m | "
        f"Value £{_f(ec.get('value'))/10:.1f}m | Transfers {ec.get('event_transfers','?')} "
        f"(cost {ec.get('event_transfers_cost',0)})",
    ]
    if data.get("active_chip"):
        lines.append(f"CHIP PLAYED: {data['active_chip']}")
    lines.append("")
    lines.append(f"{'#':<3}{'Player':<18}{'Tm':<5}{'Pos':<5}{'Price':<8}Role")

    for p in data.get("picks", []):
        el = els.get(p["element"])
        if not el:
            continue
        role = []
        if p.get("is_captain"):
            role.append("CAPTAIN")
        if p.get("is_vice_captain"):
            role.append("VICE")
        if p["position"] > 11:
            role.append(f"bench {p['position'] - 11}")
        lines.append(
            f"{p['position']:<3}{el['web_name'][:17]:<18}"
            f"{teams[el['team']]['short_name']:<5}{POS[el['element_type']]:<5}"
            f"{_price(el):<8}{', '.join(role)}"
        )
    return "\n".join(lines)


# ------------------------------------------------------------------- compare --
@mcp.tool(description="Side-by-side comparison of named players on FPL's underlying metrics.")
def compare_players(names: str) -> str:
    teams, _ = _maps()
    b = _boot()
    wanted = [n.strip().lower() for n in names.split(",") if n.strip()]
    found = []
    for w in wanted:
        m = [e for e in b["elements"] if w in e["web_name"].lower()]
        if m:
            found.append(max(m, key=lambda e: e.get("minutes", 0)))
    if not found:
        return f"No players matched: {names}"

    fields = [
        ("Team", lambda e: teams[e["team"]]["short_name"]),
        ("Pos", lambda e: POS[e["element_type"]]),
        ("Price", _price),
        ("Owned %", lambda e: f"{_f(e.get('selected_by_percent')):.1f}"),
        ("Points", lambda e: e.get("total_points", 0)),
        ("Form", lambda e: e.get("form", "0")),
        ("Minutes", lambda e: e.get("minutes", 0)),
        ("Starts", lambda e: e.get("starts", 0)),
        ("Goals", lambda e: e.get("goals_scored", 0)),
        ("Assists", lambda e: e.get("assists", 0)),
        ("xG", lambda e: f"{_f(e.get('expected_goals')):.2f}"),
        ("xA", lambda e: f"{_f(e.get('expected_assists')):.2f}"),
        ("xGI", lambda e: f"{_f(e.get('expected_goal_involvements')):.2f}"),
        (
            "Delta",
            lambda e: f"{(e.get('goals_scored',0)+e.get('assists',0)) - _f(e.get('expected_goal_involvements')):+.2f}",
        ),
        ("ICT", lambda e: e.get("ict_index", "0")),
        ("Status", lambda e: STATUS.get(e.get("status", "a"), "?")),
    ]
    w0 = 12
    lines = ["".ljust(w0) + "".join(f"{e['web_name'][:14]:<16}" for e in found)]
    lines.append("-" * (w0 + 16 * len(found)))
    for label, fn in fields:
        lines.append(f"{label:<{w0}}" + "".join(f"{str(fn(e)):<16}" for e in found))
    return "\n".join(lines)


# --------------------------------------------------------------------- value --
@mcp.tool(
    description=(
        "Filter and rank players. sort_by: points, form, value (points per £m), "
        "xgi, ownership. Useful for finding differentials and budget enablers."
    )
)
def analyze_players(
    position: str = "MID",
    max_price: float = 15.5,
    min_price: float = 3.5,
    max_ownership: float = 100.0,
    sort_by: str = "points",
    limit: int = 15,
    available_only: bool = True,
) -> str:
    teams, _ = _maps()
    b = _boot()
    want = {p.strip().upper() for p in position.split(",") if p.strip()}

    keys = {
        "points": lambda e: -e.get("total_points", 0),
        "form": lambda e: -_f(e.get("form")),
        "value": lambda e: -(e.get("total_points", 0) / max(e["now_cost"] / 10, 0.1)),
        "xgi": lambda e: -_f(e.get("expected_goal_involvements")),
        "ownership": lambda e: -_f(e.get("selected_by_percent")),
    }
    key = keys.get(sort_by.lower(), keys["points"])

    sel = [
        e
        for e in b["elements"]
        if POS.get(e["element_type"]) in want
        and min_price <= e["now_cost"] / 10 <= max_price
        and _f(e.get("selected_by_percent")) <= max_ownership
        and (not available_only or e.get("status", "a") == "a")
    ]
    sel.sort(key=key)

    head = (
        f"{'Player':<18}{'Tm':<5}{'Pos':<5}{'Price':<8}{'Pts':>5}{'Form':>6}"
        f"{'xGI':>7}{'Own%':>7}{'Pts/£m':>8}"
    )
    lines = [f"Top {position} by {sort_by} (£{min_price}-{max_price}m, <= {max_ownership}% owned)", head, "-" * len(head)]
    for e in sel[:limit]:
        lines.append(
            f"{e['web_name'][:17]:<18}{teams[e['team']]['short_name']:<5}"
            f"{POS[e['element_type']]:<5}{_price(e):<8}{e.get('total_points',0):>5}"
            f"{_f(e.get('form')):>6.1f}{_f(e.get('expected_goal_involvements')):>7.2f}"
            f"{_f(e.get('selected_by_percent')):>7.1f}"
            f"{e.get('total_points',0)/max(e['now_cost']/10,0.1):>8.1f}"
        )
    return "\n".join(lines)


# ------------------------------------------------------- midfielder screen ---
@mcp.tool(
    description=(
        "Midfielder (and forward) screen combining BOTH scoring routes. Mids score "
        "5/goal (more than a forward's 4), 3/assist, 1/clean sheet, plus 2pts for "
        "12+ CBIRT per match (clearances, blocks, interceptions, tackles AND "
        "recoveries - a higher bar than defenders' 10 but recoveries are "
        "high-volume). Ranks xGI against CBIRT floor and labels the archetype: "
        "attacker (xGI, no floor), holder (floor, no ceiling), box-to-box (both - "
        "rare and valuable), or limited. Unlike defenders, where the split is driven "
        "by TEAM dominance, a midfielder's archetype is driven by his individual "
        "ROLE - so role news moves it faster than season stats reveal. Set "
        "accurate=True for the true per-match 12+ hit-rate (slow, one call per player)."
    )
)
def midfielder_screen(
    position: str = "MID",
    max_price: float = 15.5,
    min_price: float = 3.5,
    min_minutes: int = 900,
    limit: int = 20,
    accurate: bool = False,
    sort_by: str = "xgi",
) -> str:
    teams, _ = _maps()
    b = _boot()
    want = {p.strip().upper() for p in position.split(",") if p.strip()}
    thresh = 12  # CBIRT threshold for MID/FWD

    rows = []
    for el in b["elements"]:
        if POS.get(el["element_type"]) not in want:
            continue
        p = el["now_cost"] / 10
        if not (min_price <= p <= max_price):
            continue
        mins = el.get("minutes", 0)
        if mins < min_minutes:
            continue

        n90 = max(mins / 90.0, 0.01)
        cbirt = (
            el.get("clearances_blocks_interceptions", 0)
            + el.get("tackles", 0)
            + el.get("recoveries", 0)
        )
        xgi = _f(el.get("expected_goal_involvements"))
        ga = el.get("goals_scored", 0) + el.get("assists", 0)

        r = {
            "name": el["web_name"], "team": teams[el["team"]]["short_name"],
            "pos": POS[el["element_type"]], "price": p,
            "own": _f(el.get("selected_by_percent")),
            "cbirt90": cbirt / n90, "xgi90": xgi / n90, "xgi": xgi,
            "delta": ga - xgi, "pts": el.get("total_points", 0),
            "mins": mins, "hit": None, "status": el.get("status", "a"),
            "sp": _setpiece(el),
            "susp": _suspension(el, _screen_gw()),
        }

        if accurate:
            try:
                hist = _player_history(el["id"])
                played = [h for h in hist if h.get("minutes", 0) >= 60]
                if played:
                    hits = sum(
                        1 for h in played
                        if h.get("clearances_blocks_interceptions", 0)
                        + h.get("tackles", 0) + h.get("recoveries", 0) >= thresh
                    )
                    r["hit"] = 100.0 * hits / len(played)
            except Exception:
                pass
        rows.append(r)

    if not rows:
        return "No players matched. Early season, try min_minutes=0."

    # --- shrinkage (D1-D3): shown ALONGSIDE raw, never silently replacing it ---
    pool_all = [e for e in b["elements"] if POS.get(e["element_type"]) in want]
    k_xgi = _estimate_k([(r["xgi90"], r["mins"] / 90.0) for r in rows],
                        DISPERSION["expected_goal_involvements"])
    for r in rows:
        el = next((e for e in pool_all if e["web_name"] == r["name"]), None)
        if el is not None:
            s, _raw, srcb = _shrunk(el, "expected_goal_involvements",
                                    pool_all, teams, k_xgi)
            r["sxgi"], r["base"] = s, srcb
        else:
            r["sxgi"], r["base"] = r["xgi90"], "-"

    def med(k: str) -> float:
        v = sorted(x[k] for x in rows)
        n = len(v)
        return v[n // 2] if n % 2 else (v[n // 2 - 1] + v[n // 2]) / 2

    # The DEFENSIVE axis is judged against the ACTUAL 12+ threshold, not the
    # median. A median split says "above average", which is not the same as
    # "earns the 2 points" - most midfielders never reach 12, so a relative
    # split flatters players who never actually score the floor.
    # The ATTACKING axis stays median-relative: xGI has no absolute threshold.
    m_xgi = med("xgi90")
    for r in rows:
        if r["hit"] is not None:          # true per-match hit-rate available
            clears = r["hit"] >= 50.0
            near = r["hit"] >= 30.0
            r["dc"] = f"{r['hit']:.0f}%"
        else:                              # season-mean proxy
            clears = r["cbirt90"] >= thresh
            near = r["cbirt90"] >= thresh * 0.8
            r["dc"] = "yes" if clears else ("near" if near else "no")
        ceiling = r["xgi90"] > m_xgi

        if clears and ceiling:
            r["type"] = "box-to-box"  # both routes - rare, valuable
        elif clears:
            r["type"] = "holder"      # real 2pt floor, little attacking upside
        elif ceiling:
            r["type"] = "attacker"    # xGI ceiling, no defensive floor
        elif near:
            r["type"] = "borderline"  # close to the line, floor unreliable
        else:
            r["type"] = "limited"     # neither route

    keys = {
        "xgi": lambda r: -r["xgi"],
        "cbirt": lambda r: -(r["hit"] if r["hit"] is not None else r["cbirt90"]),
        "value": lambda r: -(r["pts"] / max(r["price"], 0.1)),
        "discount": lambda r: r["delta"],      # most negative = cheapest vs xGI
        "price": lambda r: r["price"],
    }
    rows.sort(key=keys.get(sort_by.lower(), keys["xgi"]))

    col = "Hit%" if accurate else "CBIRT/90"
    n_clear = sum(1 for r in rows if r["type"] in ("holder", "box-to-box"))
    head = (
        f"{'Player':<15}{'Tm':<5}{'Pos':<5}{'Price':<7}{'xGI/90':>8}{'shrunk':>8} "
        f"{'base':<10}{col:>9}{'DC':>6}{'SP':>7}{'Delta':>7}{'Own%':>6}"
        f"{'SUSP':>11}  Archetype"
    )
    out = [
        f"MIDFIELD SCREEN (sorted by {sort_by}, min {min_minutes} mins)",
        f"DC threshold: {thresh}+ CBIRT per match for 2pts. "
        f"{n_clear}/{len(rows)} players actually clear it.",
        f"Shrinkage: k={k_xgi:.1f}" + (
            " *** FALLBACK VALUE, NOT DERIVED - the noise model exceeded the "
            "observed spread. Treat the shrunk column with suspicion. ***"
            if _k_degenerate(k_xgi) else
            f" derived from the data ({'~%.0f matches to half weight' % k_xgi})") +
        ". 'shrunk' blends observed "
        f"xGI/90 toward the baseline named in 'base', weighted by minutes played.",
        "", head, "-" * len(head),
    ]
    for r in rows[:limit]:
        v = f"{r['hit']:.0f}%" if r["hit"] is not None else f"{r['cbirt90']:.1f}"
        flag = "" if r["status"] == "a" else " " + STATUS.get(r["status"], "")
        out.append(
            f"{r['name'][:14]:<15}{r['team']:<5}{r['pos']:<5}£{r['price']:<6.1f}"
            f"{r['xgi90']:>8.2f}{r['sxgi']:>8.2f} {r['base']:<10}{v:>9}{r['dc']:>6}"
            f"{r['sp']:>7}{r['delta']:>+7.2f}{r['own']:>6.1f}"
            f"{r['susp']['label']:>11}  {r['type']}{flag}"
        )

    out += [
        "",
        "SP = set-piece duty. P=penalties, F=direct FKs, C=corners, number = order.\n"
        "Plain (P1) = confirmed by the FPL API. With ? (P1?) = expected, from\n"
        "ROLE_INTEL.md, UNCONFIRMED. '-' = neither source has anything.",
        "",
        f"DC column: does he ACTUALLY reach the {thresh}+ threshold?",
        f"  yes   season mean >= {thresh} (or 50%+ of matches in accurate mode)",
        f"  near  within 20% of the line - unreliable, will miss often",
        f"  no    does not reach it",
        "",
        "ARCHETYPES - defensive axis vs the REAL threshold, attacking axis vs median:",
        "  box-to-box  clears the threshold AND above-median xGI - rare, best",
        "  holder      clears the threshold, low xGI - a genuine 2pt floor",
        "  attacker    above-median xGI, no floor - boom or bust",
        "  borderline  near the line but does not clear it - the floor is a mirage",
        "  limited     neither route",
        "",
        "",
        "SHRUNK vs RAW: early season the raw column is unstable - a player with 2\n"
        "games has an almost meaningless rate. The shrunk column blends it toward\n"
        "the baseline in 'base' (own = his own prior season, team+pos / pos+price /\n"
        "pos = fallbacks when that is unavailable or contaminated). At GW1 shrunk IS\n"
        "the baseline; by GW20 it has largely converged on raw. TRUST SHRUNK EARLY,\n"
        "RAW LATE, and say which one is driving a recommendation.",
        "A 'borderline' player at a premium price is the classic trap: priced as a",
        "holder, but does not reliably earn the points that justify a holder.",
        "",
        "Unlike defenders (where the split is team-driven), a midfielder's archetype",
        "follows his individual ROLE. A holder pushed forward, or a No.10 asked to",
        "sit, changes profile immediately - check role news before trusting these.",
        "A midfield goal is 5pts vs a forward's 4, so equal xGI is worth more here.",
    ]
    if not accurate:
        out.append("")
        out.append(
            f"NOTE: CBIRT/90 is a season MEAN. The award is a per-match threshold, so "
            f"a player averaging {thresh} still misses in low-volume games. Re-run with "
            f"accurate=True for the true per-match hit-rate (needs current-season data)."
        )
    return "\n".join(out)


# --------------------------------------------------------- defender screen ---
@mcp.tool(
    description=(
        "Defender screen. Defenders do NOT use the xGI framework - they score from "
        "three separate sources: clean sheets (driven by team xGC), defensive "
        "contribution points (2pts at 10+ CBIT, capped), and attacking returns (a "
        "defender goal is 6pts). CRITICALLY, clean sheets and CBIT are NEARLY "
        "INDEPENDENT - measured on 2025/26, corr(CBIT/90, clean sheets) = -0.04 and "
        "corr(CBIT/90, xGC/90) = +0.14. They are NOT strongly anti-correlated as "
        "once assumed, but independence is its own reason not to blend them: one "
        "number cannot carry two unrelated routes to points. This tool reports both "
        "separately and labels the archetype instead. Set accurate=True to compute "
        "the true per-match threshold hit-rate from match history (slow, one call "
        "per player)."
    )
)
def defender_screen(
    max_price: float = 15.5,
    min_price: float = 3.5,
    min_minutes: int = 450,
    limit: int = 20,
    accurate: bool = False,
    sort_by: str = "cbit",
) -> str:
    teams, _ = _maps()
    b = _boot()

    rows = []
    for el in b["elements"]:
        if POS.get(el["element_type"]) != "DEF":
            continue
        p = el["now_cost"] / 10
        if not (min_price <= p <= max_price):
            continue
        mins = el.get("minutes", 0)
        if mins < min_minutes:
            continue

        n90 = max(mins / 90.0, 0.01)
        cbit = el.get("clearances_blocks_interceptions", 0) + el.get("tackles", 0)
        xgc = _f(el.get("expected_goals_conceded"))
        gc = el.get("goals_conceded", 0)

        r = {
            "name": el["web_name"], "team": teams[el["team"]]["short_name"],
            "price": p, "own": _f(el.get("selected_by_percent")),
            "cbit90": cbit / n90,
            "xgc90": xgc / n90,
            # positive = conceded FEWER than expected = riding luck = regression risk
            "def_delta": xgc - gc,
            "cs": el.get("clean_sheets", 0),
            "sp": _setpiece(el),
            "xgi": _f(el.get("expected_goal_involvements")),
            "dc": el.get("defensive_contribution", 0),
            "mins": mins, "hit": None,
            "status": el.get("status", "a"),
            "susp": _suspension(el, _screen_gw()),
        }

        if accurate:
            try:
                hist = _player_history(el["id"])
                played = [h for h in hist if h.get("minutes", 0) >= 60]
                if played:
                    hits = sum(
                        1 for h in played
                        if h.get("clearances_blocks_interceptions", 0) + h.get("tackles", 0) >= 10
                    )
                    r["hit"] = 100.0 * hits / len(played)
            except Exception:
                pass
        rows.append(r)

    if not rows:
        return "No defenders matched. Early season, try min_minutes=0."

    # --- shrinkage (D1-D3), shown alongside raw ---
    pool_all = [e for e in b["elements"] if POS.get(e["element_type"]) == "DEF"]
    k_cbit = _estimate_k([(r["cbit90"], r["mins"] / 90.0) for r in rows],
                         DISPERSION["cbit"])
    for r in rows:
        el = next((e for e in pool_all if e["web_name"] == r["name"]), None)
        if el is not None:
            s, _raw, srcb = _shrunk(el, "cbit", pool_all, teams, k_cbit)
            r["scbit"], r["base"] = s, srcb
        else:
            r["scbit"], r["base"] = r["cbit90"], "-"

    # Archetype by median split - relative, so it adapts as the season develops.
    def med(k: str) -> float:
        v = sorted(x[k] for x in rows)
        n = len(v)
        return v[n // 2] if n % 2 else (v[n // 2 - 1] + v[n // 2]) / 2

    # DEFENSIVE axis judged against the ACTUAL 10+ CBIT threshold, not the median -
    # "above average" is not the same as "earns the 2 points". The CLEAN SHEET axis
    # stays median-relative, since there is no absolute xGC threshold.
    thresh = 10
    m_xgc = med("xgc90")
    for r in rows:
        if r["hit"] is not None:
            busy = r["hit"] >= 50.0
            near = r["hit"] >= 30.0
            r["dc"] = f"{r['hit']:.0f}%"
        else:
            busy = r["cbit90"] >= thresh
            near = r["cbit90"] >= thresh * 0.8
            r["dc"] = "yes" if busy else ("near" if near else "no")
        solid = r["xgc90"] < m_xgc      # below-median expected goals conceded

        if busy and solid:
            r["type"] = "BOTH"       # clears threshold AND solid - rare, best
        elif busy:
            r["type"] = "workhorse"  # real CBIT floor, few clean sheets
        elif solid:
            r["type"] = "cleansheet" # clean sheets + attack, no CBIT floor
        elif near:
            r["type"] = "borderline" # near the line but does not clear it
        else:
            r["type"] = "avoid"      # neither - the mid-table trap

    keys = {
        "cbit": lambda r: -(r["hit"] if r["hit"] is not None else r["cbit90"]),
        "cleansheet": lambda r: r["xgc90"],
        "xgi": lambda r: -r["xgi"],
        "regression": lambda r: r["def_delta"],  # most negative = unluckiest = buy
        "price": lambda r: r["price"],
    }
    rows.sort(key=keys.get(sort_by.lower(), keys["cbit"]))

    col = "Hit%" if accurate else "CBIT/90"
    n_clear = sum(1 for r in rows if r["type"] in ("BOTH", "workhorse"))
    head = (
        f"{'Player':<15}{'Tm':<5}{'Price':<7}{col:>8}{'shrunk':>8} {'base':<10}"
        f"{'DC':>6}{'SP':>7}{'xGC/90':>8}{'CS':>4}{'DefΔ':>7}{'Own%':>6}"
        f"{'SUSP':>11}  Archetype"
    )
    out = [
        f"DEFENDER SCREEN (sorted by {sort_by}, min {min_minutes} mins)",
        f"DC threshold: {thresh}+ CBIT per match for 2pts. "
        f"{n_clear}/{len(rows)} players actually clear it.",
        f"Shrinkage: k={k_cbit:.1f}" + (
            " *** FALLBACK VALUE, NOT DERIVED - the noise model exceeded the "
            "observed spread. Treat the shrunk column with suspicion. ***"
            if _k_degenerate(k_cbit) else
            f" derived from the data ({'~%.0f matches to half weight' % k_cbit})") +
        ". 'shrunk' blends observed "
        f"CBIT/90 toward the baseline named in 'base', weighted by minutes played.",
        "",
        head, "-" * len(head),
    ]
    for r in rows[:limit]:
        v = f"{r['hit']:.0f}%" if r["hit"] is not None else f"{r['cbit90']:.1f}"
        flag = "" if r["status"] == "a" else " " + STATUS.get(r["status"], "")
        out.append(
            f"{r['name'][:14]:<15}{r['team']:<5}£{r['price']:<6.1f}{v:>8}"
            f"{r['scbit']:>8.1f} {r['base']:<10}{r['dc']:>6}{r['sp']:>7}"
            f"{r['xgc90']:>8.2f}{r['cs']:>4}{r['def_delta']:>+7.1f}{r['own']:>6.1f}"
            f"{r['susp']['label']:>11}  {r['type']}{flag}"
        )

    out += [
        "",
        "SP = set-piece duty. P=penalties, F=direct FKs, C=corners, number = order.\n"
        "Plain (P1) = confirmed by the FPL API. With ? (P1?) = expected, from\n"
        "ROLE_INTEL.md, UNCONFIRMED. '-' = neither source has anything.",
        "",
        f"DC column: does he ACTUALLY reach {thresh}+ CBIT? yes / near (within 20%) / no",
        "",
        "ARCHETYPES - defensive axis vs the REAL threshold, clean-sheet axis vs median:",
        "  BOTH       clears the threshold AND solid defence - rare, best of both",
        "  workhorse  clears the threshold, leaky team - a genuine 2pt floor",
        "  cleansheet solid team, no CBIT floor - clean sheets and attacking returns",
        "  borderline near the line but does not clear it - the floor is a mirage",
        "  avoid      neither - the mid-table trap",
        "",
        "SHRUNK vs RAW: early season the raw column is unstable - a player with 2\n"
        "games has an almost meaningless rate. The shrunk column blends it toward\n"
        "the baseline in 'base' (own = his own prior season, team+pos / pos+price /\n"
        "pos = fallbacks when that is unavailable or contaminated). At GW1 shrunk IS\n"
        "the baseline; by GW20 it has largely converged on raw. TRUST SHRUNK EARLY,\n"
        "RAW LATE, and say which one is driving a recommendation.",

        "",
        "DefΔ = xGC - actual goals conceded. POSITIVE means the team has conceded",
        "fewer than expected (riding luck - clean sheets likely to dry up).",
        "NEGATIVE means unlucky - clean sheets are due. Sort by 'regression' for these.",
    ]
    if not accurate:
        out.append("")
        out.append(
            "NOTE: CBIT/90 is a proxy. The 2pt award is a per-match THRESHOLD (10+), "
            "capped, so consistency beats volume - a player averaging 14 is worth no "
            "more than one averaging 11. Re-run with accurate=True for the true "
            "per-match hit-rate."
        )
    return "\n".join(out)


# ==================================================================== D7 =====
# OPPONENT ADJUSTMENT
#
# A fixture has TWO independent difficulties, and FPL's FDR collapses them into
# one integer, losing the distinction:
#   * for your ATTACKERS  - how leaky the opponent's DEFENCE is (their xGC)
#   * for your DEFENDERS  - how potent the opponent's ATTACK  is (their xG)
# A team that both concedes and scores heavily is GOOD for your attackers and
# BAD for your defenders simultaneously. One number cannot say that.
#
# FPL's own strength_attack_* / strength_defence_* fields are zero pre-season,
# so team strength is derived from player xG data instead.
# =============================================================================

# Home advantage in the Premier League is worth roughly 0.3-0.4 goals a game.
# Expressed as multipliers either side of 1.0.
HOME_FACTOR = 1.13
AWAY_FACTOR = 0.89

_strength_cache: dict | None = None


def _team_strength() -> dict:
    """Per-team xG and xGC per game, blended toward the prior season when the
    current one is young. Returns {"teams": {id: {...}}, "lg_xg":, "lg_xgc":}."""
    global _strength_cache
    if _strength_cache is not None:
        return _strength_cache

    b = _boot()
    finished = [e for e in b["events"] if e.get("finished")]
    games_now = max(len(finished), 0)

    def from_pool(players: list[dict], games: int) -> dict:
        out = {}
        by_team: dict[int, list[dict]] = {}
        for e in players:
            by_team.setdefault(e["team"], []).append(e)
        for tid, sq in by_team.items():
            if games <= 0:
                continue
            xg = sum(_f(x.get("expected_goals")) for x in sq) / games
            # xGC per 90 of the highest-minute regulars approximates the team's
            # rate, since they were on the pitch for most of it.
            reg = sorted([x for x in sq if (x.get("minutes") or 0) >= games * 45],
                         key=lambda x: -(x.get("minutes") or 0))[:6]
            xgc = (sum(_f(x.get("expected_goals_conceded")) / max((x["minutes"] / 90), 0.1)
                       for x in reg) / len(reg)) if reg else None
            out[tid] = {"xg": xg, "xgc": xgc}
        return out

    cur = from_pool(b["elements"], games_now)

    priors = _load_priors()
    pri = {}
    if priors.get("players"):
        pri = from_pool(list(priors["players"].values()), 38)

    # Blend current toward prior by games played - same logic as player shrinkage.
    K_TEAM = 6.0
    merged: dict[int, dict] = {}
    for tid in set(list(cur) + list(pri)):
        c, p = cur.get(tid), pri.get(tid)
        rec: dict[str, Any] = {"source": "current"}
        for key in ("xg", "xgc"):
            cv = c.get(key) if c else None
            pv = p.get(key) if p else None
            if cv is not None and pv is not None and games_now > 0:
                rec[key] = (games_now * cv + K_TEAM * pv) / (games_now + K_TEAM)
                rec["source"] = f"blend({games_now}g)"
            elif cv is not None and games_now > 0:
                rec[key] = cv
            elif pv is not None:
                rec[key] = pv
                rec["source"] = "prior"
            else:
                rec[key] = None
                rec["source"] = "none"
        merged[tid] = rec

    xgs = [v["xg"] for v in merged.values() if v.get("xg")]
    xgcs = [v["xgc"] for v in merged.values() if v.get("xgc")]
    _strength_cache = {
        "teams": merged,
        "lg_xg": (sum(xgs) / len(xgs)) if xgs else 1.35,
        "lg_xgc": (sum(xgcs) / len(xgcs)) if xgcs else 1.35,
        "games": games_now,
    }
    return _strength_cache


def _fixtures_for(team_id: int, event_id: int) -> list[dict]:
    """All of a team's fixtures in one gameweek - a list, because of doubles."""
    out = []
    try:
        for f in _get("/fixtures/?future=1", ttl=3600):
            if f.get("event") != event_id:
                continue
            if f.get("team_h") == team_id:
                out.append({"opp": f.get("team_a"), "home": True})
            elif f.get("team_a") == team_id:
                out.append({"opp": f.get("team_h"), "home": False})
    except Exception:
        pass
    return out


def _opp_factors(team_id: int, event_id: int, teams: dict) -> list[dict]:
    """Per fixture: how much to scale attacking output and goals conceded.

    def_factor scales YOUR attacking rates  (opponent's leakiness)
    att_factor scales YOUR goals conceded   (opponent's potency)
    Both are relative to the league average, so 1.0 = an average opponent.
    """
    st = _team_strength()
    res = []
    for fx in _fixtures_for(team_id, event_id):
        o = st["teams"].get(fx["opp"], {})
        oxgc, oxg = o.get("xgc"), o.get("xg")
        # No data (promoted side) -> assume average, and flag low confidence.
        dfac = (oxgc / st["lg_xgc"]) if oxgc else 1.0   # how leaky they are
        afac = (oxg / st["lg_xg"]) if oxg else 1.0      # how potent they are

        # Home advantage cuts both ways and is symmetric: at home YOU attack
        # better (scale your output up) and the OPPONENT attacks worse (scale
        # your goals-conceded down). Away, both reverse.
        if fx["home"]:
            your_attack_ha, their_attack_ha = HOME_FACTOR, AWAY_FACTOR
        else:
            your_attack_ha, their_attack_ha = AWAY_FACTOR, HOME_FACTOR

        res.append({
            "opp": fx["opp"],
            "opp_name": teams.get(fx["opp"], {}).get("short_name", "???"),
            "home": fx["home"],
            "def_factor": max(0.4, min(dfac * your_attack_ha, 2.2)),  # scales your attack
            "att_factor": max(0.4, min(afac * their_attack_ha, 2.2)), # scales your GC
            "known": oxgc is not None and oxg is not None,
        })
    return res


def _window_factors(team_id: int, start_event: int, n: int, teams: dict) -> list[dict]:
    """Every fixture a team has across an N-gameweek window, with its factors.

    Iterates FIXTURES, not gameweeks - so a double contributes twice and a blank
    contributes nothing, with no special-casing.
    """
    out = []
    for ev in range(start_event, start_event + n):
        for fx in _opp_factors(team_id, ev, teams):
            fx["event"] = ev
            out.append(fx)
    return out


@mcp.tool(
    description=(
        "5-6 gameweek fixture outlook in CONCRETE UNITS, split by position. "
        "Attackers get expected xGI over the window (player rate x opponent "
        "leakiness x home/away); defenders get expected CLEAN SHEETS (from "
        "opponent potency) plus expected attacking returns, because a defender "
        "goal is 6pts. TWO scores, never one: a leaky-but-potent opponent is good "
        "for your attackers and bad for your defenders at the same time, which a "
        "single FDR integer cannot express. Doubles count twice and blanks count "
        "zero automatically, since it sums over FIXTURES not gameweeks. Pass "
        "compare='OutPlayer>InPlayer' for a head-to-head transfer view."
    )
)
def fixture_outlook(
    names: str = "",
    next_n: int = 5,
    compare: str = "",
    shrunk: bool = True,
) -> str:
    teams, _ = _maps()
    b = _boot()
    ev = _next_event()
    if not ev:
        return "No upcoming gameweek."
    start = ev["id"]

    if compare:
        names = compare.replace(">", ",")
    wanted = [w.strip().lower() for w in names.split(",") if w.strip()]
    if not wanted:
        return "Pass names='A,B' or compare='Out>In'."

    found = []
    for w in wanted:
        cands = [e for e in b["elements"] if w in e["web_name"].lower()]
        if cands:
            found.append(max(cands, key=lambda e: e.get("minutes", 0)))
    if not found:
        return f"No players matched: {names}"

    pools = {p: [e for e in b["elements"] if POS.get(e["element_type"]) == p]
             for p in {POS[e["element_type"]] for e in found}}
    ks = {p: _estimate_k([(_rates(e)["expected_goal_involvements"], _rates(e)["n90"])
                          for e in pl if (e.get("minutes") or 0) > 0],
                         DISPERSION["expected_goal_involvements"])
          for p, pl in pools.items()}

    rows = []
    for el in found:
        pos = POS[el["element_type"]]
        mins = el.get("minutes", 0) or 0
        n90 = max(mins / 90.0, 0.01)
        if shrunk:
            xgi90, _raw, base = _shrunk(el, "expected_goal_involvements",
                                        pools[pos], teams, ks[pos])
        else:
            xgi90, base = _f(el.get("expected_goal_involvements")) / n90, "raw"
        own_xgc90 = (_f(el.get("expected_goals_conceded")) / n90) if mins else 1.35

        fxs = _window_factors(el["team"], start, next_n, teams)
        exp_xgi = sum(xgi90 * f["def_factor"] for f in fxs)
        exp_cs = sum(2.718281828459045 ** (-(max(own_xgc90, 0.05) * f["att_factor"]))
                     for f in fxs)

        by_ev: dict[int, int] = {}
        for f in fxs:
            by_ev[f["event"]] = by_ev.get(f["event"], 0) + 1
        dgw = [e for e, c in by_ev.items() if c > 1]
        blank = [e for e in range(start, start + next_n) if by_ev.get(e, 0) == 0]

        rows.append({
            "name": el["web_name"], "team": teams[el["team"]]["short_name"],
            "pos": pos, "price": el["now_cost"] / 10,
            "games": len(fxs), "exp_xgi": exp_xgi, "exp_cs": exp_cs,
            "xgi90": xgi90, "base": base, "dgw": dgw, "blank": blank,
            "unknown": sum(1 for f in fxs if not f["known"]),
            "run": " ".join(f"{f['opp_name']}{'(H)' if f['home'] else '(a)'}" for f in fxs),
            "own": _f(el.get("selected_by_percent")),
            "status": el.get("status", "a"),
        })

    head = (f"{'Player':<14}{'Tm':<5}{'Pos':<5}{'Price':<7}{'Gms':>4}"
            f"{'exp xGI':>9}{'exp CS':>8}  Fixtures")
    out = [f"FIXTURE OUTLOOK - GW{start} to GW{start + next_n - 1} "
           f"({'shrunk' if shrunk else 'raw'} rates)", "", head, "-" * 92]
    for r in sorted(rows, key=lambda r: -(r["exp_xgi"] if r["pos"] in ("MID", "FWD")
                                          else r["exp_cs"])):
        flag = "" if r["status"] == "a" else " " + STATUS.get(r["status"], "")
        out.append(
            f"{r['name'][:13]:<14}{r['team']:<5}{r['pos']:<5}£{r['price']:<6.1f}"
            f"{r['games']:>4}{r['exp_xgi']:>9.2f}{r['exp_cs']:>8.2f}  {r['run'][:34]}{flag}")
        if r["dgw"] or r["blank"]:
            note = []
            if r["dgw"]:
                note.append("DGW " + ",".join(f"GW{e}" for e in sorted(r["dgw"])))
            if r["blank"]:
                note.append("BLANK " + ",".join(f"GW{e}" for e in sorted(r["blank"])))
            out.append(f"{'':<14}{' '.join(note)}")

    if compare and len(rows) >= 2:
        a, bb = rows[0], rows[1]
        metric = "exp_xgi" if a["pos"] in ("MID", "FWD") else "exp_cs"
        label = "expected xGI" if metric == "exp_xgi" else "expected clean sheets"
        d = bb[metric] - a[metric]
        out += ["", f"HEAD TO HEAD over GW{start}-{start + next_n - 1} ({label}):",
                f"  OUT  {a['name']:<14}{a[metric]:>6.2f}   ({a['games']} fixtures)",
                f"  IN   {bb['name']:<14}{bb[metric]:>6.2f}   ({bb['games']} fixtures)",
                f"  NET  {d:>+21.2f}",
                ""]
        if a["pos"] != bb["pos"]:
            out.append("  NOTE: different positions - the metrics are not comparable. "
                       "Compare like for like.")
        elif abs(d) < 0.25:
            out.append("  Negligible on fixtures. Decide on xGI, role or price instead.")
        else:
            out.append(f"  {'Favours the incoming player.' if d > 0 else 'Favours holding.'} "
                       f"Fixtures should break a tie, not make the case - everyone reads "
                       f"the same ticker, so the edge is TIMING, not spotting.")

    out += [
        "",
        "exp xGI = player xGI/90 x opponent LEAKINESS x home/away, summed over fixtures.",
        "exp CS  = expected clean sheets, from opponent POTENCY. Two scores, because a",
        "          leaky-but-potent side is GOOD for your attackers and BAD for your",
        "          defenders at once - one FDR integer cannot say that.",
        "Read exp xGI for MID/FWD; exp CS for DEF/GK (but a defender goal is 6pts, so",
        "an attacking full-back is judged on both).",
        "Doubles count twice, blanks count zero - it sums FIXTURES, not gameweeks.",
    ]
    unknown = sum(r["unknown"] for r in rows)
    if unknown:
        out.append(f"CAUTION: {unknown} fixture(s) against sides with no PL data "
                   f"(promoted). Assumed league average, which is GENEROUS to them - "
                   f"those fixtures are probably easier than shown.")
    if next_n > 6:
        out.append("CAUTION: beyond ~6 gameweeks fixtures get rescheduled by cup ties. "
                   "Treat a long window as fiction.")
    return "\n".join(out)


# --------------------------------------------------------------- captaincy ---
def _pois_pmf(lam: float, kmax: int = 6) -> list[float]:
    """Poisson PMF for 0..kmax events."""
    out, term = [], 2.718281828459045 ** (-lam)
    for i in range(kmax + 1):
        out.append(term)
        term = term * lam / (i + 1)
    return out


def _cap_rows(names: str, shrunk: bool = True, with_intel: bool = False):
    """Shared by captaincy_odds and log_predictions so the two can never
    disagree about what was predicted.

    with_intel=True applies the ROLE_INTEL.md `adjustments` fence (see the
    module note above _load_adjustments()): a CAPPED 0.5x-1.5x multiplier on
    xg90/xa90/xgi90, and an UNCAPPED op=set override on stp/P(start).

    THIS FUNCTION'S OWN DEFAULT STAYS False - it is captaincy_odds (the tool)
    that defaults with_intel=True since 13 Aug 2026 and passes it through
    explicitly. log_predictions deliberately calls this with with_intel
    unset (False) and must keep doing so - calibration needs to score the
    model, not model+intel."""
    teams, _ = _maps()
    b = _boot()
    wanted = [n.strip().lower() for n in names.split(",") if n.strip()]
    found = []
    for w in wanted:
        m2 = [e for e in b["elements"] if w in e["web_name"].lower()]
        if m2:
            found.append(max(m2, key=lambda e: e.get("minutes", 0)))
    if not found:
        return [], {}
    # Shrink the rates before building the distribution. A player with two
    # games has a wildly unstable raw rate, and captaincy needs the MAGNITUDE
    # right, not just the ranking - this is the case shrinkage most helps.
    pools = {p: [e for e in b["elements"] if POS.get(e["element_type"]) == p]
             for p in {POS[e["element_type"]] for e in found}}
    ks = {}
    for p, pl in pools.items():
        ks[p] = _estimate_k([
            (_rates(e)["expected_goals"], _rates(e)["n90"])
            for e in pl if (e.get("minutes") or 0) > 0
        ], DISPERSION["expected_goals"])

    rows = []
    for el in found:
        pos = POS[el["element_type"]]
        mins = el.get("minutes", 0) or 0
        n90 = max(mins / 90.0, 0.01)
        if shrunk:
            xg90, raw_xg, base_src = _shrunk(el, "expected_goals", pools[pos],
                                             teams, ks[pos])
            xa90, _, _ = _shrunk(el, "expected_assists", pools[pos], teams, ks[pos])
        else:
            xg90 = _f(el.get("expected_goals")) / n90
            xa90 = _f(el.get("expected_assists")) / n90
            raw_xg, base_src = xg90, "raw"
        g_pts = {"GKP": 10, "DEF": 6, "MID": 5, "FWD": 4}[pos]
        cs_pts = {"GKP": 4, "DEF": 4, "MID": 1, "FWD": 0}[pos]
        # crude clean-sheet probability from team xGC per 90
        xgc90 = _f(el.get("expected_goals_conceded")) / n90 if mins else 1.4
        p_cs = 2.718281828459045 ** (-max(xgc90, 0.05))
        # Bonus only lands on a returning game - a flat per-90 average would put
        # a floor under every score and make blanks impossible.
        bonus_on_return = min(_f(el.get("bonus")) / max(n90, 1), 3.0)

        # ROTATION IS THE DOMINANT SOURCE OF BLANKS. Model it explicitly:
        # a player who does not start scores 0-1, and no xG model can rescue that.
        starts = el.get("starts", 0) or 0
        est_games = max(n90 / 0.95, 1)          # rough games available
        p_start = min(max(starts / est_games, 0.05), 0.98) if starts else 0.6

        # Historical start rate says nothing about a player who is suspended or
        # injured RIGHT NOW. Apply the published status before anything else.
        avail, avail_lbl = _availability(el)
        p_start *= avail

        # External-research overlay (ROLE_INTEL.md `adjustments` fence) - runs
        # only when with_intel=True is passed in. captaincy_odds passes True
        # by default since 13 Aug 2026; log_predictions never passes it, so
        # this stays a no-op for calibration regardless of the tool default.
        intel_note = ""
        if with_intel:
            for e in _intel_entries(el, teams, _screen_gw()):
                if e["op"] == "set" and e["field"] == "stp":
                    # UNCAPPED - non-availability is a binary fact, not a
                    # graded belief; overrides the status flag outright.
                    clamped = min(max(e["value"], 0.0), 1.0)
                    avail, avail_lbl, p_start = clamped, f"INTEL: {e['why'][:50]}", clamped
                    tag = f"stp->{clamped:.2f} (intel)"
                elif e["op"] == "mult" and e["field"] in ("xg90", "xa90", "xgi90"):
                    factor = min(max(e["value"], MULT_LO), MULT_HI)
                    if e["field"] in ("xg90", "xgi90"):
                        xg90 *= factor
                    if e["field"] in ("xa90", "xgi90"):
                        xa90 *= factor
                    tag = f"{e['field']} x{factor:.2f}"
                else:
                    continue
                intel_note = f"{intel_note}; {tag}" if intel_note else tag

        # --- D7: adjust for the ACTUAL opponent, per fixture -----------------
        ev = _next_event()
        fixtures = _opp_factors(el["team"], ev["id"] if ev else 0, teams)
        if not fixtures:                       # blank gameweek - no fixture at all
            dist = {0.0: 1.0}
            opp_desc, dgw, known = "BLANK", False, True
        else:
            dgw = len(fixtures) > 1
            known = all(fx["known"] for fx in fixtures)
            opp_desc = "+".join(
                f"{fx['opp_name']}({'H' if fx['home'] else 'A'})" for fx in fixtures)

            per_fixture = []
            for fx in fixtures:
                axg = xg90 * fx["def_factor"]          # opponent leakiness x H/A
                axa = xa90 * fx["def_factor"]
                a_gc = max(xgc90, 0.05) * fx["att_factor"]
                p_cs_f = 2.718281828459045 ** (-a_gc)

                pg, pa = _pois_pmf(max(axg, 0.001)), _pois_pmf(max(axa, 0.001))
                d: dict[float, float] = {}
                for gi, pgi in enumerate(pg):
                    for ai, pai in enumerate(pa):
                        for cs, pcs in ((1, p_cs_f), (0, 1 - p_cs_f)):
                            ret = gi + ai
                            pts = 2 + g_pts * gi + 3 * ai + cs_pts * cs
                            if ret > 0:
                                pts += bonus_on_return
                            d[pts] = d.get(pts, 0.0) + pgi * pai * pcs * p_start
                d[1.0] = d.get(1.0, 0.0) + (1 - p_start)   # benched / cameo
                per_fixture.append(d)

            # A double gameweek is the SUM of two matches - convolve them.
            dist = per_fixture[0]
            for nxt in per_fixture[1:]:
                conv: dict[float, float] = {}
                for v1, p1 in dist.items():
                    for v2, p2 in nxt.items():
                        conv[v1 + v2] = conv.get(v1 + v2, 0.0) + p1 * p2
                dist = conv

        tot = sum(dist.values()) or 1.0
        exp = sum(p * v for v, p in dist.items()) / tot
        haul = sum(p for v, p in dist.items() if v >= 10) / tot
        blank = sum(p for v, p in dist.items() if v <= 2) / tot
        sd = (sum(p * (v - exp) ** 2 for v, p in dist.items()) / tot) ** 0.5
        own = _f(el.get("selected_by_percent"))
        rows.append({
            "id": el["id"],
            "name": el["web_name"], "team": teams[el["team"]]["short_name"],
            "pos": pos, "exp": exp, "haul": haul * 100, "blank": blank * 100,
            "sd": sd, "own": own, "base": base_src, "xg90": xg90,
            "opp": opp_desc, "dgw": dgw, "opp_known": known,
            "diff": haul * 100 * (1 - own / 100),      # ownership-adjusted upside
            "risk": blank * 100 * (1 - own / 100),
            "status": el.get("status", "a"),
            "avail": avail, "avail_lbl": avail_lbl, "intel": intel_note,
            "susp": _suspension(el, ev["id"] if ev else 1, p_start),
        })

    return rows, {"k": (sum(ks.values()) / len(ks)) if ks else 0.0}


@mcp.tool(
    description=(
        "Captaincy analysis by DISTRIBUTION, not point estimate (design D6). "
        "Models goals and assists as Poisson draws and reports E[points], "
        "P(haul >=10) and P(blank <=2). Variance is symmetric but captaincy is "
        "not - the upper tail is what gains rank, the lower tail is what loses "
        "it. Also reports an ownership-adjusted differential score, because "
        "captaining a heavily-owned player is largely rank-neutral whatever "
        "happens. Use for both the weekly armband and Triple Captain timing "
        "(TC is purely a P(haul) maximisation). Layers the ROLE_INTEL.md "
        "`adjustments` fence on top by default since 13 Aug 2026 (capped "
        "0.5x-1.5x xG/xA multipliers, uncapped P(start) overrides) - pass "
        "with_intel=False for the raw, intel-blind comparison."
    )
)
def captaincy_odds(names: str, mode: str = "neutral", shrunk: bool = True,
                    with_intel: bool = True) -> str:
    rows, _meta = _cap_rows(names, shrunk, with_intel)
    if not rows:
        return f"No players matched: {names}"

    key = {"chase": lambda r: -r["diff"], "protect": lambda r: (r["blank"], -r["exp"])}
    rows.sort(key=key.get(mode.lower(), lambda r: -r["exp"]))

    head = (f"{'Player':<14}{'Tm':<5}{'Opponent':<16}{'xG/90':>7}{'E[pts]':>8}"
            f"{'P(haul)':>9}{'P(blank)':>10}{'SD':>7}{'Own%':>7}{'DiffUp':>8}"
            f"{'SUSP':>11}")
    out = [f"CAPTAINCY ODDS (mode: {mode}, "
           f"{'SHRUNK rates' if shrunk else 'RAW rates'}"
           f"{', WITH INTEL ADJUSTMENTS (default)' if with_intel else ', INTEL OFF (with_intel=False)'})",
           "", head, "-" * len(head)]
    for r in rows:
        flag = "" if r["status"] == "a" else " " + STATUS.get(r["status"], "")
        out.append(
            f"{r['name'][:13]:<14}{r['team']:<5}"
            f"{(r['opp'] + ('*' if not r['opp_known'] else ''))[:15]:<16}"
            f"{r['xg90']:>7.2f}{r['exp']:>8.2f}{r['haul']:>8.1f}%{r['blank']:>9.1f}%"
            f"{r['sd']:>7.2f}{r['own']:>7.1f}{r['diff']:>8.1f}"
            f"{r['susp']['label']:>11}"
            f"{'  DGW' if r['dgw'] else ''}{flag}"
            f"{'  [' + r['intel'] + ']' if r.get('intel') else ''}"
        )
    at_risk = [r for r in rows if r["susp"]["to_go"] == 1 and r["susp"]["p_ban"] > 0]
    if at_risk:
        out.append("")
        out.append("ONE BOOKING FROM A BAN - affects NEXT week, not this one:")
        for r in at_risk:
            s = r["susp"]
            out.append(f"  {r['name']}: {s['yellows']}/{s['threshold']} yellows, "
                       f"~{s['p_ban']*100:.0f}% chance of picking up the next one "
                       f"this GW -> {s['matches']}-match ban")
    out += [
        "",
        "OPPONENT-ADJUSTED (D7). xG/90 is the shrunk baseline; E[pts] and the",
        "probabilities apply the ACTUAL fixture: opponent xGC for your attacking",
        "output, opponent xG for your clean-sheet odds, plus home/away. A single",
        "FDR integer cannot express both - a leaky-but-potent side is GOOD for your",
        "attackers and BAD for your defenders at the same time.",
        "  * after an opponent = no data for them (promoted side) - assumed average",
        "  DGW = double gameweek, distributions convolved across both matches",
        "",
        "P(haul) = P(>=10 pts) - what GAINS rank.  P(blank) = P(<=2) - what LOSES it.",
        "P(blank) now applies the published STATUS FLAG: a suspended, injured or",
        "unavailable player gets P(start) = 0 rather than his historical start rate,",
        "and a doubtful one is scaled by his chance of playing. Minutes are the",
        "dominant source of blanks and no xG model can rescue a player who sits.",
        "",
        "SUSP = yellow cards against the next ban threshold (5 by GW19, 10 by GW32,",
        "       15 by GW38). READ IT AS A HOLD SIGNAL, NOT A BLANK SIGNAL: a fifth",
        "       yellow this week bans him NEXT week, so it does not change the",
        "       P(blank) above. 'BANNED' does - that is the status flag, already",
        "       priced in. Second-yellow reds are a separate rule, not modelled.",
        "DiffUp  = P(haul) x (1 - ownership). Captaining a heavily-owned player is",
        "          largely rank-neutral whatever happens; a differential is a real bet.",
        "",
        "MODES: protect = lowest P(blank) first | chase = highest DiffUp first",
        "       neutral = highest expected points",
        "",
        "TRIPLE CAPTAIN is purely a P(haul) maximisation - the chip's value is one",
        "extra copy of the score, so target the upper tail, not the mean.",
        "",
        "RATES ARE SHRUNK by default (base column names the prior used). Early season",
        "a raw two-game rate would make the distribution wildly over-confident.",
        "Pass shrunk=False to see the unsmoothed version.",
        "",
        "with_intel=True (ON by default since 13 Aug 2026) layers ROLE_INTEL.md's",
        "`adjustments` fence on top: a CAPPED 0.5x-1.5x multiplier on xg90/xa90/xgi90,",
        "and an UNCAPPED op=set override on stp/P(start) - a binary non-availability",
        "claim, not a graded one. Any player it touched is tagged '[...]' in the row.",
        "Pass with_intel=False for the raw, intel-blind comparison.",
        "",
        "CAVEATS: Poisson assumes a constant rate and independence - real matches",
        "have game-state effects. Bonus is a flat per-90 average, not modelled from",
        "BPS. Clean sheet is a crude exp(-xGC90). TEST CALIBRATION, NOT SHARPNESS:",
        "if it says P(haul)=20%, hauls should occur ~20% of the time over many weeks.",
    ]
    return "\n".join(out)


# ------------------------------------------------------------- calibration ---
# A probabilistic model is only useful if its numbers mean what they say. If it
# claims P(haul)=20%, hauls must occur ~20% of the time. That can only be checked
# against predictions recorded BEFORE the gameweek - hence an append-only log.
_CALIB_PATH = _os.path.join(
    _os.path.dirname(_os.path.abspath(__file__)), "fpl_calibration_log.jsonl"
)


@mcp.tool(
    description=(
        "Record this gameweek's captaincy predictions so they can be scored later. "
        "MUST be run BEFORE the deadline - a prediction logged afterwards is not a "
        "prediction, and score_calibration() will exclude it. Append-only; the same "
        "player/gameweek is never overwritten, so the record cannot be revised "
        "after the fact. Writes one local file and still makes only HTTP GETs."
    )
)
def log_predictions(names: str, gameweek: int = 0, shrunk: bool = True) -> str:
    import json
    ev = _next_event()
    if gameweek <= 0:
        gameweek = ev["id"] if ev else 1
    dl = None
    for e in _boot()["events"]:
        if e["id"] == gameweek:
            dl = e["deadline_time"]
    now = _dt.datetime.now(_dt.timezone.utc)
    late = False
    if dl:
        late = now > _dt.datetime.fromisoformat(dl.replace("Z", "+00:00"))

    rows, meta = _cap_rows(names, shrunk)
    if not rows:
        return f"No players matched: {names}"

    existing = set()
    try:
        with open(_CALIB_PATH, encoding="utf-8") as fh:
            for line in fh:
                try:
                    d = json.loads(line)
                    existing.add((d["gw"], d["id"]))
                except Exception:
                    pass
    except FileNotFoundError:
        pass

    written, skipped = 0, 0
    with open(_CALIB_PATH, "a", encoding="utf-8") as fh:
        for r in rows:
            if (gameweek, r["id"]) in existing:
                skipped += 1
                continue
            fh.write(json.dumps({
                "gw": gameweek, "id": r["id"], "name": r["name"],
                "pos": r["pos"], "team": r["team"],
                "exp": round(r["exp"], 3), "p_haul": round(r["haul"] / 100, 4),
                "p_blank": round(r["blank"] / 100, 4), "sd": round(r["sd"], 3),
                "own": r["own"], "base": r["base"], "shrunk": shrunk,
                "logged_utc": now.isoformat(), "deadline": dl,
                "logged_after_deadline": late,
                "k": round(meta.get("k", 0), 2),
            }) + "\n")
            written += 1

    if late:
        warn = ("\n  WARNING: logged AFTER the deadline - these are not predictions "
                "and will be EXCLUDED from scoring.")
    elif dl is None:
        warn = ("\n  NOTE: no deadline found for that gameweek, so the pre-deadline "
                "check could not be applied.")
    else:
        warn = ""
    return (f"Logged {written} prediction(s) for GW{gameweek}"
            f"{f', skipped {skipped} already recorded' if skipped else ''}."
            f"\n  file: {_CALIB_PATH}{warn}")


@mcp.tool(
    description=(
        "Score previously logged predictions against what actually happened. "
        "Produces a reliability table (predicted vs observed haul rate by "
        "probability bin), a Brier score, and a verdict on whether the model is "
        "over-confident, under-confident or calibrated. Over-confidence is the "
        "signature of ignoring parameter uncertainty - the specific deficiency "
        "full Bayesian modelling would fix, so this is the gate for that decision."
    )
)
def score_calibration(min_gw: int = 1, max_gw: int = 38) -> str:
    import json
    try:
        raw = [json.loads(l) for l in open(_CALIB_PATH, encoding="utf-8") if l.strip()]
    except FileNotFoundError:
        return ("No calibration log yet. Run log_predictions() BEFORE a deadline to "
                "start recording. Nothing can be scored retrospectively - that is "
                "the point.")

    seen, preds, excluded = set(), [], 0
    for d in raw:
        if not (min_gw <= d["gw"] <= max_gw):
            continue
        if d.get("logged_after_deadline"):
            excluded += 1
            continue
        key = (d["gw"], d["id"])
        if key in seen:            # keep only the FIRST prediction made
            continue
        seen.add(key)
        preds.append(d)

    if not preds:
        return (f"No scorable predictions in GW{min_gw}-{max_gw} "
                f"({excluded} excluded as logged after the deadline).")

    scored, missing = [], 0
    for d in preds:
        try:
            hist = _player_history(d["id"])
        except Exception:
            missing += 1
            continue
        got = [h for h in hist if h.get("round") == d["gw"]]
        if not got:
            missing += 1
            continue
        actual = sum(h.get("total_points", 0) for h in got)
        scored.append((d, actual))

    if len(scored) < 5:
        return (f"Only {len(scored)} predictions have results yet "
                f"(need the gameweek to have finished). Try again later.")

    bins = [(0.0, 0.05), (0.05, 0.10), (0.10, 0.20), (0.20, 0.30), (0.30, 1.01)]
    out = [f"CALIBRATION - GW{min_gw}-{max_gw}",
           f"n = {len(scored)} scored predictions"
           + (f", {excluded} excluded (logged late)" if excluded else "")
           + (f", {missing} awaiting results" if missing else ""),
           "",
           "HAUL RELIABILITY - does P(haul) mean what it says?",
           f"{'P(haul) bin':<16}{'n':>5}{'predicted':>11}{'observed':>10}{'gap':>8}",
           "-" * 50]
    tot_pred = tot_obs = 0.0
    for lo, hi in bins:
        sel = [(d, a) for d, a in scored if lo <= d["p_haul"] < hi]
        if not sel:
            continue
        pm = sum(d["p_haul"] for d, _ in sel) / len(sel)
        om = sum(1 for _, a in sel if a >= 10) / len(sel)
        tot_pred += pm * len(sel)
        tot_obs += om * len(sel)
        out.append(f"{f'{lo:.0%}-{hi:.0%}':<16}{len(sel):>5}{pm:>10.1%}"
                   f"{om:>10.1%}{om - pm:>+8.1%}")

    brier = sum((d["p_haul"] - (1 if a >= 10 else 0)) ** 2 for d, a in scored) / len(scored)
    base = sum(1 for _, a in scored if a >= 10) / len(scored)
    brier_base = base * (1 - base)
    skill = (1 - brier / brier_base) if brier_base > 0 else 0.0

    mae = sum(abs(d["exp"] - a) for d, a in scored) / len(scored)
    bias = sum(d["exp"] - a for d, a in scored) / len(scored)
    blank_pred = sum(d["p_blank"] for d, _ in scored) / len(scored)
    blank_obs = sum(1 for _, a in scored if a <= 2) / len(scored)

    gap = (tot_obs - tot_pred) / len(scored)
    out += [
        "",
        f"Brier score        {brier:.4f}  (lower better; base rate {brier_base:.4f})",
        f"Skill vs base rate {skill:+.1%}  (positive = better than guessing the average)",
        f"E[pts] MAE         {mae:.2f}   bias {bias:+.2f} "
        f"({'over' if bias > 0 else 'under'}-predicting)",
        f"P(blank) predicted {blank_pred:.1%} vs observed {blank_obs:.1%}",
        "",
    ]
    if abs(gap) < 0.03:
        out.append(f"VERDICT: CALIBRATED (haul gap {gap:+.1%}). The probabilities can be "
                   f"read at face value. No case for full Bayesian modelling on these "
                   f"grounds.")
    elif gap < 0:
        out.append(f"VERDICT: OVER-CONFIDENT (haul gap {gap:+.1%}) - hauls happen LESS "
                   f"often than predicted. This is the signature of ignoring parameter "
                   f"uncertainty: lambda is treated as known when it is estimated. It is "
                   f"exactly what a full Bayesian model fixes. Consider PyMC - but first "
                   f"check the gap is not driven by rotation, which is an intelligence "
                   f"problem, not a modelling one.")
    else:
        out.append(f"VERDICT: UNDER-CONFIDENT (haul gap {gap:+.1%}) - hauls happen MORE "
                   f"often than predicted. Shrinkage may be too aggressive; try a lower "
                   f"k before reaching for a bigger model.")
    if skill < 0:
        out.append("WARNING: negative skill score - the model is worse than predicting "
                   "the base rate for everyone. Investigate before trusting any of it.")
    return "\n".join(out)


# --------------------------------------------------------------- backtest ----
def _pearson(xs: list[float], ys: list[float]) -> float | None:
    n = len(xs)
    if n < 3:
        return None
    mx, my = sum(xs) / n, sum(ys) / n
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    dx = sum((x - mx) ** 2 for x in xs)
    dy = sum((y - my) ** 2 for y in ys)
    if dx <= 0 or dy <= 0:
        return None
    return num / ((dx * dy) ** 0.5)


@mcp.tool(
    description=(
        "Empirical test of the methodology on THIS season's data. Splits the "
        "season into two windows and asks which period-1 metric better predicts "
        "period-2 goals+assists: period-1 xGI, or period-1 actual G+A. If xGI "
        "wins, the xGI-first framework is supported for this dataset. Makes one "
        "API call per player, so it is slow - expect 1-3 minutes."
    )
)
def predictive_backtest(
    p1_start: int = 1,
    p1_end: int = 5,
    p2_start: int = 6,
    p2_end: int = 10,
    min_minutes_p1: int = 270,
    min_minutes_p2: int = 180,
    max_players: int = 200,
    positions: str = "MID,FWD",
    compare_shrinkage: bool = False,
) -> str:
    teams, _ = _maps()
    b = _boot()
    want = {p.strip().upper() for p in positions.split(",") if p.strip()}

    pool = [e for e in b["elements"] if POS.get(e["element_type"]) in want]
    pool.sort(key=lambda e: -e.get("minutes", 0))
    pool = pool[:max_players]

    rows = []
    skipped = 0
    for el in pool:
        try:
            hist = _player_history(el["id"])
        except Exception:
            skipped += 1
            continue

        def agg(lo: int, hi: int) -> tuple[float, int, int]:
            xgi = ga = mins = 0.0
            for h in hist:
                r = h.get("round")
                if r is not None and lo <= r <= hi:
                    xgi += _f(h.get("expected_goal_involvements"))
                    ga += h.get("goals_scored", 0) + h.get("assists", 0)
                    mins += h.get("minutes", 0)
            return xgi, int(ga), int(mins)

        x1, g1, m1 = agg(p1_start, p1_end)
        x2, g2, m2 = agg(p2_start, p2_end)
        # For the bake-off keep anyone who appeared at all in period 1. Filtering
        # to a high p1 minutes floor would exclude the sparse-data players that
        # shrinkage exists to help, and rig the test toward "no effect".
        p1_floor = 45 if compare_shrinkage else min_minutes_p1
        if m1 < p1_floor or m2 < min_minutes_p2:
            continue
        rows.append(
            {"name": el["web_name"], "team": teams[el["team"]]["short_name"],
             "id": el["id"],
             "x1": x1, "g1": g1, "x2": x2, "g2": g2, "m1": m1, "m2": m2}
        )

    all_rows = rows
    rows = [r for r in rows if r["m1"] >= min_minutes_p1]
    n = len(rows)
    if n < 10:
        return (
            f"Only {n} players cleared the minutes filters ({skipped} fetch errors). "
            f"Too few for a meaningful correlation - lower min_minutes_p1/p2, widen "
            f"the windows, or wait for more gameweeks."
        )

    g2 = [r["g2"] for r in rows]
    r_xgi = _pearson([r["x1"] for r in rows], g2)
    r_ga = _pearson([float(r["g1"]) for r in rows], g2)
    r_x2 = _pearson([r["x1"] for r in rows], [r["x2"] for r in rows])
    r_dd = _pearson(
        [r["g1"] - r["x1"] for r in rows], [r["g2"] - r["x2"] for r in rows]
    )

    def fmt(v: float | None) -> str:
        return "n/a" if v is None else f"{v:+.3f}"

    if r_xgi is None or r_ga is None:
        return "Could not compute correlations (zero variance in a column)."

    gap = r_xgi - r_ga
    if gap > 0.05:
        verdict = "SUPPORTED - period-1 xGI predicts period-2 returns better than period-1 goals did."
    elif gap < -0.05:
        verdict = "NOT SUPPORTED - period-1 actual G+A predicted better than xGI in this sample."
    else:
        verdict = "INCONCLUSIVE - the two predictors are within noise of each other."

    extra: list[str] = []
    if compare_shrinkage:
        # ---- D4 baseline bake-off -------------------------------------------
        # Which baseline, shrunk into period-1 xGI, best predicts period-2 G+A?
        teams_m, els_m = _maps()
        pool = [e for e in b["elements"] if POS.get(e["element_type"]) in want]
        n90s = [(r["x1"] / max(r["m1"] / 90.0, 0.01), r["m1"] / 90.0) for r in rows]
        k_est = _estimate_k(n90s, DISPERSION["expected_goals"])

        def bl_own(r, el):
            pr = _load_priors().get("players", {}).get(str(el["id"]))
            return _rates(pr)["expected_goal_involvements"] if pr and pr.get("minutes", 0) >= 900 else None

        def bl_group(r, el, same_team):
            sel = [p for p in pool if p["element_type"] == el["element_type"]
                   and (p["team"] == el["team"] if same_team else True)
                   and (p.get("minutes", 0) or 0) >= 450]
            if not sel:
                return None
            v = [_rates(p)["expected_goal_involvements"] for p in sel]
            return sum(v) / len(v)

        def bl_price(r, el):
            band = _price_band(el["now_cost"])
            sel = [p for p in pool if p["element_type"] == el["element_type"]
                   and _price_band(p["now_cost"]) == band
                   and (p.get("minutes", 0) or 0) >= 450]
            if not sel:
                return None
            v = [_rates(p)["expected_goal_involvements"] for p in sel]
            return sum(v) / len(v)

        strata = [
            ("sparse  (<180 p1 mins)", lambda r: r["m1"] < 180),
            ("moderate(180-450)",      lambda r: 180 <= r["m1"] < 450),
            ("rich    (450+)",         lambda r: r["m1"] >= 450),
            ("ALL",                    lambda r: True),
        ]
        cands = {
            "raw (control)": None,
            "own last season": bl_own,
            "team x position": lambda r, e: bl_group(r, e, True),
            "position x price": bl_price,
            "position overall": lambda r, e: bl_group(r, e, False),
        }
        extra += ["", f"D4 BASELINE BAKE-OFF  (k estimated from data = {k_est:.1f})",
                  f"n = {len(all_rows)} players (p1 floor lowered to 45 mins so the",
                  "sparse-data population shrinkage exists to serve is included)", ""]

        def score(rws, fn):
            xs, ys = [], []
            for r in rws:
                el = els_m.get(r.get("id"))
                n90 = r["m1"] / 90.0
                raw = r["x1"] / max(n90, 0.01)
                if fn is None or el is None:
                    val = raw
                else:
                    base = fn(r, el)
                    val = raw if base is None else (n90 * raw + k_est * base) / (n90 + k_est)
                xs.append(val)
                ys.append(float(r["g2"]))
            r = _pearson(xs, ys)
            # Scale the prediction to period-2 units before measuring error:
            # xGI/90 vs total G+A are different scales, and MSE is scale-sensitive.
            sx = sum(xs) / len(xs) if xs else 0
            sy = sum(ys) / len(ys) if ys else 0
            sc = (sy / sx) if sx > 1e-9 else 1.0
            mse = sum((x * sc - y) ** 2 for x, y in zip(xs, ys)) / len(xs) if xs else None
            return r, mse

        extra += ["PREDICTION ERROR (MSE, lower is better). Correlation is the WRONG",
                  "metric here: with similar sample sizes shrinkage is an affine",
                  "transform, and r is invariant to those. Shrinkage guarantees lower",
                  "SQUARED ERROR (James-Stein), not better ranking.", ""]
        hdr = f"{'Stratum':<24}{'n':>5}" + "".join(f"{c[:11]:>13}" for c in cands)
        extra += [hdr, "-" * len(hdr)]
        gains, bests = {}, {}
        for sname, pred in strata:
            sub = [r for r in all_rows if pred(r)]
            if len(sub) < 10:
                extra.append(f"{sname:<24}{len(sub):>5}   (too few to score)")
                continue
            vals, mses = {}, {}
            for label, fn in cands.items():
                rr, mm = score(sub, fn)
                vals[label], mses[label] = rr, mm
            extra.append(f"{sname:<24}{len(sub):>5}" +
                         "".join(f"{('n/a' if mses[c] is None else f'{mses[c]:.3f}'):>13}"
                                 for c in cands))
            cm = mses.get("raw (control)")
            bl, bm = None, None
            for k2, v2 in mses.items():
                if k2 != "raw (control)" and v2 is not None and (bm is None or v2 < bm):
                    bl, bm = k2, v2
            if cm is not None and bm is not None:
                gains[sname] = (cm - bm) / cm * 100.0   # % MSE reduction
                bests[sname] = bl

        extra += ["", "MSE REDUCTION vs control (%), by period-1 sample size:"]
        for sname, g in gains.items():
            extra.append(f"  {sname:<24}{g:+6.1f}%   best: {bests.get(sname,'-')}")

        sparse = next((g for s, g in gains.items() if s.startswith("sparse")), None)
        rich = next((g for s, g in gains.items() if s.startswith("rich")), None)
        extra.append("")
        if sparse is None:
            extra.append("VERDICT: cannot judge - too few sparse-data players to score.")
        elif sparse <= 5.0:
            extra.append(
                f"VERDICT: DO NOT ADOPT. MSE reduction in the sparse stratum is only "
                f"{sparse:+.1f}%, under the 5% bar set before the test.")
        elif rich is not None and rich >= sparse:
            extra.append(
                f"VERDICT: SUSPICIOUS - {sparse:+.1f}% sparse vs {rich:+.1f}% rich. "
                f"Theory says the benefit must SHRINK as data accumulates. It does not, "
                f"so investigate the implementation before adopting.")
        else:
            extra.append(
                f"VERDICT: ADOPT ({bests.get('sparse  (<180 p1 mins)','-')}). "
                f"MSE cut {sparse:.1f}% where data is sparse, decaying to "
                f"{rich if rich is not None else 0:.1f}% where it is rich - exactly the "
                f"pattern the theory predicts.")
        extra += ["",
                  "NOTE: the screens RANK players, and shrinkage improves calibration",
                  "more than ranking. A pass here means better point estimates - which",
                  "matters for captaincy_odds and any expected-points work, but may not",
                  "change which player a screen puts top."]

    return "\n".join([
        f"PREDICTIVE BACKTEST - GW{p1_start}-{p1_end} vs GW{p2_start}-{p2_end}",
        f"n = {n} players ({positions}), min {min_minutes_p1}/{min_minutes_p2} mins per window",
        "",
        "Which period-1 metric better predicts period-2 GOALS+ASSISTS?",
        f"  period-1 xGI   -> period-2 G+A :  r = {fmt(r_xgi)}   <-- the framework's claim",
        f"  period-1 G+A   -> period-2 G+A :  r = {fmt(r_ga)}",
        f"  difference                     :  {gap:+.3f}",
        "",
        f"VERDICT: {verdict}",
        "",
        "Supporting persistence checks:",
        f"  xGI period-1 -> xGI period-2   :  r = {fmt(r_x2)}  (chance creation repeatability)",
        f"  delta p1     -> delta p2       :  r = {fmt(r_dd)}  (finishing repeatability - expect near zero)",
        "",
        "Published benchmarks: chance creation ~0.63, finishing over-expected ~0.12.",
        "Caveat: a single 5-gameweek split is a small, noisy sample. Treat a narrow",
        "gap as inconclusive rather than as a refutation.",
    ] + extra)


# ------------------------------------------------------------- escalation ----
def _gw_shape(horizon: int) -> tuple[int, dict[int, dict[str, list[str]]]]:
    """Per-gameweek doubles/blanks across the lookahead window."""
    teams, _ = _maps()
    ev = _next_event()
    if not ev:
        return 0, {}
    start = ev["id"]
    window = list(range(start, start + horizon + 1))

    counts: dict[int, dict[int, int]] = {gw: {t: 0 for t in teams} for gw in window}
    for f in _get("/fixtures/?future=1", ttl=3600):
        gw = f.get("event")
        if gw in counts:
            for side in ("team_h", "team_a"):
                if f[side] in counts[gw]:
                    counts[gw][f[side]] += 1

    shape: dict[int, dict[str, list[str]]] = {}
    for gw in window:
        played = counts[gw]
        if not any(played.values()):
            continue  # gameweek not yet scheduled - no data, not a real blank
        shape[gw] = {
            "doubles": sorted(teams[t]["short_name"] for t, n in played.items() if n > 1),
            "blanks": sorted(teams[t]["short_name"] for t, n in played.items() if n == 0),
        }
    return start, shape


@mcp.tool(
    description=(
        "Decide whether the NEXT weekly brief needs a stronger model. Looks ahead "
        "for double/blank gameweeks, chip-deadline pressure and squad availability, "
        "and returns a RUN WITH OPUS / SONNET IS FINE verdict with reasons. "
        "Call this at the end of every brief so escalation is flagged a week early."
    )
)
def escalation_check(horizon: int = 3, entry: int = ENTRY_ID) -> str:
    start, shape = _gw_shape(horizon)
    if not start:
        return "No upcoming gameweek; cannot assess."

    score = 0
    hits: list[tuple[int, str, str]] = []  # (weight, severity, text)

    def add(w: int, sev: str, txt: str) -> None:
        nonlocal score
        score += w
        hits.append((w, sev, txt))

    # Doubles / blanks. Weight by how soon, with GW+1 as the advance-warning slot.
    for gw, s in sorted(shape.items()):
        offset = gw - start
        if offset == 0:
            w, when = 4, "THIS gameweek"
        elif offset == 1:
            w, when = 4, "NEXT gameweek"
        elif offset == 2:
            w, when = 2, "in 2 gameweeks"
        else:
            w, when = 1, f"in {offset} gameweeks"

        if s["doubles"]:
            add(
                w,
                "HIGH" if w >= 4 else "MED",
                f"GW{gw} ({when}) is a DOUBLE for {len(s['doubles'])} team(s): "
                f"{', '.join(s['doubles'][:8])}. Bench Boost / Triple Captain decision.",
            )
        if s["blanks"]:
            add(
                w,
                "HIGH" if w >= 4 else "MED",
                f"GW{gw} ({when}) is a BLANK for {len(s['blanks'])} team(s): "
                f"{', '.join(s['blanks'][:8])}. Free Hit candidate; squad may not field 11.",
            )

    # Chip set 1 expiry pressure.
    b = _boot()
    gw19 = next((e for e in b["events"] if e["id"] == 19), None)
    if gw19:
        dl19 = _dt.datetime.fromisoformat(gw19["deadline_time"].replace("Z", "+00:00"))
        if dl19 > _dt.datetime.now(_dt.timezone.utc):
            left = 19 - start
            if left <= 2:
                add(4, "HIGH", f"Chip set 1 expires in {left} gameweek(s) (GW19, {dl19:%a %d %b %H:%M} UTC). Final call.")
            elif left <= 4:
                add(3, "HIGH", f"Chip set 1 expires in {left} gameweeks (GW19). Plan the run-in now.")
            elif left <= 6:
                add(2, "MED", f"Chip set 1 expires in {left} gameweeks (GW19). Start sequencing.")

    # Squad availability, from the most recent locked gameweek.
    try:
        picks = _get(f"/entry/{entry}/event/{max(1, start - 1)}/picks/", ttl=300)
        _, els = _maps()
        flagged = [
            els[p["element"]]
            for p in picks.get("picks", [])
            if p["element"] in els and els[p["element"]].get("status", "a") != "a"
        ]
        if len(flagged) >= 4:
            add(3, "HIGH", f"{len(flagged)} squad players flagged ({', '.join(e['web_name'] for e in flagged[:6])}). Wildcard territory.")
        elif len(flagged) == 3:
            add(2, "MED", f"3 squad players flagged ({', '.join(e['web_name'] for e in flagged)}).")
        elif flagged:
            hits.append((0, "LOW", f"{len(flagged)} squad player(s) flagged: {', '.join(e['web_name'] for e in flagged)}."))
    except Exception:
        hits.append((0, "LOW", "Squad availability not checked (no locked gameweek readable yet)."))

    verdict = "RUN WITH OPUS" if score >= 4 else "SONNET IS FINE"
    lines = [
        f"MODEL RECOMMENDATION FOR THE NEXT BRIEF: {verdict}",
        f"Escalation score {score} (threshold 4) | lookahead GW{start}-GW{start + horizon}",
        "",
    ]
    if hits:
        lines.append("Signals:")
        for w, sev, txt in sorted(hits, key=lambda h: -h[0]):
            lines.append(f"  [{sev}] {txt}")
    else:
        lines.append("Signals: none. Routine gameweek - no doubles, blanks or chip pressure.")
    if score >= 4:
        lines += [
            "",
            "Why: these weeks involve multi-week planning under constraints "
            "(chip sequencing, squad restructuring) where a better decision is "
            "worth real rank. Switch the scheduled task to Opus for one run, "
            "then switch back.",
        ]
    return "\n".join(lines)


def _snapshot_priors() -> str:
    """Capture the prior-season baseline. TIME-CRITICAL: run before GW1.

    bootstrap-static serves only the CURRENT season. Pre-season it still holds
    2025/26 totals; once GW1 completes they are overwritten and last season's
    per-player rates are gone from the endpoint for good. Every baseline in the
    D2 fallback ladder depends on them.

    Writes ONE local JSON file. Still makes only HTTP GETs - this does not touch
    the FPL team in any way.
    """
    import json
    b = _get("/bootstrap-static/", ttl=0)
    keep = (
        "id", "web_name", "team", "element_type", "now_cost", "minutes", "starts",
        "goals_scored", "assists", "expected_goals", "expected_assists",
        "expected_goal_involvements", "clearances_blocks_interceptions", "tackles",
        "recoveries", "clean_sheets", "goals_conceded", "expected_goals_conceded",
        "total_points", "bonus", "selected_by_percent", "penalties_order",
        "direct_freekicks_order", "corners_and_indirect_freekicks_order",
        # --- added 8 Aug 2026 -------------------------------------------------
        # The original 7 Aug capture omitted these, and three planned pieces of
        # work each need a prior-season baseline that only exists until the GW1
        # deadline. Once bootstrap-static rolls over to 2026/27 they are gone
        # for good, so they are captured now even though nothing consumes them
        # yet.
        "yellow_cards", "red_cards",        # suspension-risk baseline
        "saves", "penalties_saved",         # goalkeeper methodology
        "bps",                              # bonus modelling: the RAW score,
                                            # not `bonus`, which is the awarded
                                            # points and cannot predict itself
        "own_goals", "penalties_missed",    # cheap to keep, awkward to refit
    )
    players = {
        str(e["id"]): {k: e.get(k) for k in keep}
        for e in b["elements"] if (e.get("minutes") or 0) > 0
    }
    snap = {
        "captured_utc": _dt.datetime.now(_dt.timezone.utc).isoformat(),
        "season_described": "2025/26",
        "note": (
            "Prior-season baseline for empirical-Bayes shrinkage. Captured from "
            "bootstrap-static during the 2026/27 pre-season, while it still held "
            "last season's totals. Do NOT regenerate after the GW1 deadline - the "
            "endpoint will by then describe 2026/27 and this file would be "
            "overwritten with the wrong season."
        ),
        "teams": {str(t["id"]): t["short_name"] for t in b["teams"]},
        "players": players,
    }
    # Write to the v2 path. The 7 Aug v1 file is deliberately NOT touched - if
    # this run were to happen after the rollover it would capture the wrong
    # season, and v1 would still be intact to fall back on.
    with open(_PRIORS_PATH_V2, "w", encoding="utf-8") as fh:
        json.dump(snap, fh, separators=(",", ":"))
    size = _os.path.getsize(_PRIORS_PATH_V2)
    missing = [f for f in ("yellow_cards", "saves", "bps")
               if not any(f in p for p in list(players.values())[:5])]
    warn = ""
    if missing:
        warn = (f"  WARNING : fields absent from the API response: "
                f"{', '.join(missing)}\n")
    sample = next(iter(players.values()), {})
    return (
        f"Prior snapshot v2 written\n"
        f"  file    : {_PRIORS_PATH_V2}\n"
        f"  players : {len(players)} with minutes > 0\n"
        f"  teams   : {len(snap['teams'])}\n"
        f"  fields  : {len(sample)} per player\n"
        f"  size    : {size/1024:.0f} KB\n"
        f"  season  : 2025/26 (captured {snap['captured_utc'][:19]} UTC)\n"
        f"{warn}"
        f"  v1 file : left untouched at {_os.path.basename(_PRIORS_PATH)}\n"
        f"  NOTE    : v2 is preferred automatically on load; v1 is the fallback.\n"
    )


if __name__ == "__main__":
    if "--snapshot-priors" in sys.argv:
        print(_snapshot_priors())
        sys.exit(0)
    if "--load-priors-db" in sys.argv:
        # Purely local: reads the frozen JSON, writes SQLite. No network.
        print(_load_priors_db())
        sys.exit(0)
    # CLI escape hatches - run a tool without restarting Claude Desktop.
    if "--defenders" in sys.argv:
        acc = "--accurate" in sys.argv
        sort = "cbit"
        for i, a in enumerate(sys.argv):
            if a == "--sort" and i + 1 < len(sys.argv):
                sort = sys.argv[i + 1]
        print(defender_screen(min_minutes=900, limit=25, accurate=acc, sort_by=sort))
        sys.exit(0)
    if "--selftest" in sys.argv:
        print(escalation_check(), "\n")
        print(get_deadline(), "\n")
        print(fixture_difficulty(4), "\n")
        print(injury_report()[:1500])
        sys.exit(0)
    mcp.run()
