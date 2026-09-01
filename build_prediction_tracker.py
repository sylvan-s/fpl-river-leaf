#!/usr/bin/env python3
"""Build the live prediction tracker — docs/priors.html.

    python3 build_prediction_tracker.py

REPLACES the one-off 2025/26 backtest (build_priors_backtest.py, retired —
see its docstring and "Shrinkage backtest" in METHODOLOGY_ALTERNATIVES.md).
That answered a single question once, in principle, on a season that had
already finished: does shrinkage beat raw and baseline at all? This answers
the ongoing version of that question, every week, on the season actually
being played: RIGHT NOW, for THIS metric, is raw data, the hierarchical
prior, or the shrunk blend the best predictor of what a player just did?

WALK-FORWARD, NOT RETROSPECTIVE. For gameweek N, "raw" and "shrunk" are built
from ONLY gameweeks 1..N-1 for that player — never from GW N itself. Scoring
a prediction against the data it was built from is not prediction, it is
recall, and would make every number on this page meaningless. GW1 is a
special case: there is no "this season so far" yet, so raw is undefined and
only the baseline (last season's prior) is scored.

THE HIERARCHICAL PRIOR, SIMPLIFIED FROM THE LIVE 4-TIER LADDER. build_squad.py
and fpl_research_mcp.py's _baseline() step through: own last-season rate ->
team+position pool -> position+price pool -> position-only pool. This file
collapses the middle two tiers into one: own last-season rate (900+ minutes)
if available, else the LAST-SEASON position-only pool mean. A player who
changed clubs or lost a starting role therefore falls straight to the coarser
position average here, where the live system would first try a team+position
estimate. Simplification, not a different model — noted so a reader comparing
this page to build_squad.py's actual behaviour isn't confused by the gap.

k IS RE-DERIVED EVERY WEEK, FROM THAT WEEK'S LIVE POOL. Not fixed from last
season. This matches how fpl_research_mcp.py's _estimate_k() is actually
called live (on the current bootstrap pool, not a frozen historical one), and
it is also the honest choice: early gameweeks, almost nobody has the 270+
minutes _estimate_k() requires to trust a variance estimate, so k correctly
falls back to a safe default and the page says so (tagged "fallback", not
silently presented as derived) rather than borrowing a stale number.

SOURCES FROM SQLITE FIRST, added 1 Sep 2026 — see docs/adr/0003. Prefers
fpl_research_mcp.py's player_gw table (~/.fpl-mcp/fpl_history_cache.sqlite,
warmed weekly by Sylvan's own routine calling that MCP server's
cache_history) over hitting the FPL API directly. Only falls back to a live
fetch — bootstrap-static once per run, then event/{gw}/live/ once per
newly-finished gameweek — when that database is not there to read, e.g. a
Cowork/Claude sandbox session, whose $HOME has no route to a file on the
real machine. Run this wherever publish_dashboard.sh normally runs; a
machine with neither the database nor internet access falls back further
still, to whatever was last persisted (see EMPTY-SEASON STATE below).

PERSISTENCE, FOUR LAYERS.
  live_gw_cache.json      raw per-gameweek FPL stats, keyed by gameweek. Only
                          FINISHED gameweeks are ever written — a live
                          gameweek is still changing, and caching a partial
                          row as final would poison every week after it, the
                          same rule fpl_research_mcp.py's cache follows.
                          Bulky, gitignored, fully regenerable from the API.
  prediction_tracker.json the small derived walk-forward scoreboard panels 1
                          and 2 render from — POOL-LEVEL (RMSE, mean weight),
                          answers "does shrinkage work". Committed, so the
                          season's track record survives even if the raw
                          cache is cleared.
  docs/data/priors_player_snapshot.json
                          ADDED 26 Aug 2026. PLAYER-LEVEL: prior/raw/shrunk/
                          weight for every scored player, as of the most
                          recently finished gameweek — panel 3 renders from
                          this. Re-derived fresh each run from `cum` (full
                          season-to-date, not walk-forward held-out — this is
                          "what does the estimate look like right now", not a
                          scored prediction, so nothing needs holding out).
                          Answers "how much has THIS player's own data moved
                          the needle" rather than the pool-level question the
                          other two files answer. Not yet consumed by
                          build_squad.py/optimise_squad.py — see A0.2/A0.5 in
                          METHODOLOGY_ALTERNATIVES.md for why that stays
                          gated at GW6, and the 26 Aug 2026 entry there for
                          why this file exists ahead of that gate anyway
                          (observe now, activate later).
  docs/data/priors_payload.json
                          ADDED 1 Sep 2026, see docs/adr/0002. Everything
                          panels 1 and 2 need — finished, weeks, metric
                          labels, empty_state, generated — in the shape the
                          page's JS wants it. Derived from prediction_tracker
                          .json each run, not a second source of truth.
                          It exists so the PAGE can stop carrying the numbers:
                          docs/priors.html used to inline the whole payload as
                          `const DATA = {...}` and weighed 256 KB, so every
                          weekly refresh rewrote the entire file. Now the HTML
                          is a 17 KB static shell that fetches this, and a
                          data-only week leaves it byte-identical. The page
                          fetches priors_player_snapshot.json separately for
                          panel 3 rather than this file duplicating it.

DO NOT PUT DATA BACK IN THE HTML. The point of the split is that the emitted
page depends on the layout and the JS and nothing else — that is what keeps a
weekly refresh out of the HTML diff. A build-time f-string that interpolates
so much as a gameweek number into the shell silently undoes it. The generated
stamp and "through GW n" in the subtitle are filled client-side from the
payload for exactly this reason. verify_priors.js guards the runtime half.

EMPTY-SEASON STATE. If bootstrap-static reports zero finished gameweeks (true
as of this file's creation — GW1 hasn't happened yet), the page renders a
clear "waiting for GW1" state rather than crashing or faking data.
"""
import importlib.util, json, os, statistics as st, datetime as dt
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
PRIORS_SNAP = os.path.join(HERE, "fpl_priors_2025_26_v2.json")
LIVE_CACHE = os.path.join(HERE, "live_gw_cache.json")
TRACKER = os.path.join(HERE, "prediction_tracker.json")
SNAPSHOT = os.path.join(HERE, "docs", "data", "priors_player_snapshot.json")
PAYLOAD = os.path.join(HERE, "docs", "data", "priors_payload.json")
OUT = os.environ.get("FPL_PRIORS_OUT") or os.path.join(HERE, "docs", "priors.html")

MIN_MINS_PRIOR = 900     # this project's standard "trust a season rate" gate
MIN_POOL = 20             # below this, _estimate_k() already falls back safely

# ADDED 2 Sep 2026. Minimum minutes for a gameweek appearance to be SCORED as
# ground truth on the per-90 rate metrics. A per-90 rate computed off a cameo
# is mostly a division artifact, not a measurement: a player with 2 minutes
# and one shot registers 19.35 xG/90, against a population mean nearer 0.21.
# Measured over the full 2025/26 season (historical_backtest_2025_26.py):
# actual xG/90 has sd 2.445 among sub-30-minute appearances vs 0.227 among
# 60+ minute ones, and gating at 60 cuts RMSE ~6x (1.467 -> 0.240 for raw)
# while WIDENING the relative gap between estimators (3.7% -> 6.3%) - the
# estimators were always separable, cameo noise was drowning the signal.
# Same threshold and same reasoning as build_dashboard.py's CBIT hit-rate
# loader ("a cameo is a different population").
#
# DELIBERATELY NOT APPLIED TO START RATE. stp's actual is binary (did he
# start, 1 or 0), not a per-90 rate, so it carries no division artifact to
# correct. Worse, gating it would systematically drop substitute appearances
# - which ARE the stp=0 cases - and bias the population toward starters:
# measured, the scored rows go from 72.7% stp=1 ungated to 99.5% at a
# 60-minute gate, which would destroy the metric rather than clean it.
MIN_MINS_SCORE = 60


def _load(mod, fn):
    spec = importlib.util.spec_from_file_location(mod, os.path.join(HERE, fn))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


page_shell = _load("page_shell", "page_shell.py")
squad_state = _load("squad_state", "squad_state.py")

# --- pure shrinkage machinery, copied not imported --------------------------
# Same reasoning as the retired backtest script: fpl_research_mcp.py's
# _estimate_k()/_k_degenerate() are pure functions, but importing that FILE
# pulls in the whole MCP-server dependency stack (httpx, the mcp SDK) for no
# reason a static-page build has. Keep in sync by hand if the canonical
# version in fpl_research_mcp.py changes.
_XG_DISPERSION = 0.11


def _estimate_k(samples, dispersion=1.0):
    pts = [(r, n) for r, n in samples if n >= 3 and r >= 0]
    if len(pts) < MIN_POOL:
        return 10.0, True
    rates = [r for r, _ in pts]
    m = sum(rates) / len(rates)
    if m <= 0:
        return 10.0, True
    total_var = sum((r - m) ** 2 for r in rates) / (len(rates) - 1)
    sampling_var = dispersion * (sum(r / n for r, n in pts) / len(pts))
    between_var = total_var - sampling_var
    if between_var <= 1e-9:
        return 40.0, True
    k = m / between_var
    k = max(1.0, min(k, 60.0))
    return k, False


def _estimate_k_binomial(samples):
    """Start-rate is a share of appearances, not a per-90 count — its own
    binomial method-of-moments k, same approach the retired backtest used."""
    pts = [(r, n) for r, n in samples if n >= 2]
    if len(pts) < MIN_POOL:
        return 8.0, True
    rates = [r for r, _ in pts]
    m = sum(rates) / len(rates)
    if not (0 < m < 1):
        return 8.0, True
    total_var = st.variance(rates)
    sampling_var = sum(r * (1 - r) / n for r, n in pts) / len(pts)
    between_var = total_var - sampling_var
    if between_var <= 1e-6:
        return 20.0, True
    k = max(1.0, min(30.0, m * (1 - m) / between_var - 1))
    return k, False


POS = {1: "GKP", 2: "DEF", 3: "MID", 4: "FWD"}

# key: short label used in baseline/cumulative dicts. field: bootstrap AND
# event/live stats field name (identical in both endpoints). dispersion: see
# fpl_research_mcp.py's DISPERSION table — 0.11 for the xG family (a sum of
# per-shot probabilities, not whole events), 1.0 for counts.
METRICS = [
    dict(key="xg90", short="xg", label="xG per 90", field="expected_goals",
         positions=["DEF", "MID", "FWD"], dispersion=_XG_DISPERSION),
    dict(key="xa90", short="xa", label="xA per 90", field="expected_assists",
         positions=["DEF", "MID", "FWD"], dispersion=_XG_DISPERSION),
    dict(key="xgc90", short="xgc", label="xGC per 90", field="expected_goals_conceded",
         positions=["GKP", "DEF"], dispersion=_XG_DISPERSION),
    dict(key="sv90", short="sv", label="Saves per 90", field="saves",
         positions=["GKP"], dispersion=1.0),
]
# CBIT/CBIRT are sums of two or three raw fields, not one - handled specially
# in _rates_from_totals()/the walk-forward loop rather than via `field`.
DC_METRICS = [
    dict(key="cbit90", short="cbit", label="CBIT per 90",
         positions=["DEF"], dispersion=1.0),
    dict(key="cbirt90", short="cbirt", label="CBIRT per 90",
         positions=["MID", "FWD"], dispersion=1.0),
]
ALL_METRIC_KEYS = [m["key"] for m in METRICS] + [m["key"] for m in DC_METRICS] + ["stp"]


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def _dc_totals(t):
    return _f(t.get("clearances_blocks_interceptions")) + _f(t.get("tackles"))


def _dcr_totals(t):
    return _dc_totals(t) + _f(t.get("recoveries"))


def _rates_from_totals(t, mins):
    n90 = mins / 90.0
    if n90 <= 0:
        return {k: 0.0 for k in ("xg", "xa", "xgc", "sv", "cbit", "cbirt")}
    return dict(
        xg=_f(t.get("expected_goals")) / n90, xa=_f(t.get("expected_assists")) / n90,
        xgc=_f(t.get("expected_goals_conceded")) / n90, sv=_f(t.get("saves")) / n90,
        cbit=_dc_totals(t) / n90, cbirt=_dcr_totals(t) / n90)


# ============================================================ NETWORK =======
def _http_get(url):
    import httpx
    r = httpx.get(url, timeout=20, headers={"User-Agent": "fpl-river-leaf-dashboard/1.0"})
    r.raise_for_status()
    return r.json()


def _bootstrap():
    return _http_get("https://fantasy.premierleague.com/api/bootstrap-static/")


def _fetch_live(gw):
    d = _http_get(f"https://fantasy.premierleague.com/api/event/{gw}/live/")
    return {str(e["id"]): e["stats"] for e in d["elements"]}


def update_live_cache(boot):
    """Fetch any newly-finished gameweek not already cached. Never re-fetches
    or overwrites one already stored - see module docstring."""
    cache = json.load(open(LIVE_CACHE, encoding="utf-8")) if os.path.exists(LIVE_CACHE) else {}
    finished = sorted(e["id"] for e in boot["events"] if e.get("finished"))
    new = [gw for gw in finished if str(gw) not in cache]
    for gw in new:
        cache[str(gw)] = _fetch_live(gw)
    if new:
        json.dump(cache, open(LIVE_CACHE, "w", encoding="utf-8"))
    return cache, finished, new


# ==================================================== SQLITE (PREFERRED) ====
# ADDED 1 Sep 2026. build() tries this FIRST, before update_live_cache()'s own
# httpx calls - fpl_research_mcp.py's player_gw table is warmed weekly (every
# Tuesday, by Sylvan's own routine calling that MCP server's cache_history)
# from the exact same live/{gw} endpoint _fetch_live() hits, so a build run
# from Sylvan's own terminal has no reason to fetch what is already sitting
# on disk. Falls back to the live API untouched when the database is not
# there to read - e.g. any Cowork/Claude sandbox session, whose $HOME has no
# route to ~/.fpl-mcp/ on the real machine (see build_squad_page.py's
# actual_route_snapshot() docstring for the identical constraint, solved
# there by moving the read into an MCP tool instead - not done here because
# that would mean this file duplicating ~250 lines of shrinkage machinery
# into fpl_research_mcp.py, or that live production server importing THIS
# file; either is a bigger, riskier change than the one-week-stale sandbox
# fallback this file already handles via empty_state).
def _sqlite_db_path():
    """Mirrors fpl_research_mcp.py's _default_db_path() rather than
    importing it - importing that FILE pulls in the whole MCP-server
    dependency stack (httpx, the mcp SDK) for no reason a static-page build
    has, same reasoning as the shrinkage machinery copied above."""
    return os.environ.get("FPL_MCP_DB") or os.path.expanduser("~/.fpl-mcp/fpl_history_cache.sqlite")


_SQLITE_GW_COLS = ("minutes", "starts", "expected_goals", "expected_assists",
                   "expected_goals_conceded", "saves",
                   "clearances_blocks_interceptions", "tackles", "recoveries")


def _cache_from_sqlite():
    """Reshape fpl_research_mcp.py's player_gw table into the same
    {round_str: {player_id_str: stats}} shape _fetch_live() returns from the
    live API, so walk_forward() needs no changes to consume either source.

    Returns (cache, finished) normally, or (None, None) if the database does
    not exist or cannot be read - the caller falls back to the live API in
    that case, exactly as it always has.

    ONLY DISTINCT ROUNDS PRESENT ARE TREATED AS FINISHED, with no separate
    finished-flag check needed: cache_history's own _player_history() in
    fpl_research_mcp.py enforces upstream that only finished gameweeks are
    ever written to this table (see that file's "CORRECTNESS RULE" comment),
    so a round showing up here at all is already that guarantee holding.
    """
    path = _sqlite_db_path()
    if not os.path.exists(path):
        return None, None
    import sqlite3
    try:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        try:
            cols = ",".join(_SQLITE_GW_COLS)
            rows = conn.execute(
                f"SELECT player_id, round, {cols} FROM player_gw").fetchall()
        finally:
            conn.close()
    except Exception:
        return None, None
    cache = {}
    for pid, rnd, *vals in rows:
        cache.setdefault(str(rnd), {})[str(pid)] = dict(zip(_SQLITE_GW_COLS, vals))
    finished = sorted(int(r) for r in cache)
    return cache, finished


def _boot_from_priors_snapshot():
    """A boot["elements"]-shaped stand-in built from the frozen prior-season
    snapshot, so the SQLite path never needs a bootstrap-static call either -
    walk_forward() and build()'s id_pos/id_name only read `id`, `element_type`
    and `web_name` off each entry, all three already loaded for baselines.

    Same population baselines() already restricts to, so this introduces no
    NEW gap: a genuine 2026/27 newcomer with no 2025/26 record has never had
    a baseline (and therefore never scored a walk-forward row) regardless of
    where id_pos/id_name come from.
    """
    snap = json.load(open(PRIORS_SNAP, encoding="utf-8"))
    return {"elements": [
        {"id": int(pid), "element_type": p["element_type"], "web_name": p["web_name"]}
        for pid, p in snap["players"].items()
    ]}


# ============================================================ BASELINES =====
def build_baselines():
    """Hierarchical prior per element id: own last-season rate (900+ mins) if
    available, else the last-season position-only pool mean. See module
    docstring for how this simplifies the live 4-tier _baseline() ladder."""
    snap = json.load(open(PRIORS_SNAP, encoding="utf-8"))
    players = snap["players"]  # keyed by str(id)
    pool_by_pos = defaultdict(list)
    rates = {}
    for pid, p in players.items():
        pos = POS.get(p["element_type"])
        r = _rates_from_totals(p, p.get("minutes", 0) or 0)
        rates[pid] = (r, pos)
        if (p.get("minutes", 0) or 0) >= MIN_MINS_PRIOR:
            pool_by_pos[pos].append(r)
    pos_mean = {}
    for pos, rs in pool_by_pos.items():
        pos_mean[pos] = {k: sum(r[k] for r in rs) / len(rs) for k in ("xg", "xa", "xgc", "sv", "cbit", "cbirt")}
    baselines = {}
    for pid, p in players.items():
        r, pos = rates[pid]
        mins = p.get("minutes", 0) or 0
        if mins >= MIN_MINS_PRIOR and pos in pool_by_pos:
            baselines[pid] = dict(rates=r, source="own", pos=pos,
                                   stp=(p.get("starts", 0) or 0) / 38.0)
        elif pos in pos_mean:
            baselines[pid] = dict(rates=pos_mean[pos], source="pos", pos=pos,
                                   stp=(p.get("starts", 0) or 0) / 38.0 if mins else None)
        else:
            baselines[pid] = dict(rates={k: 0.0 for k in ("xg", "xa", "xgc", "sv", "cbit", "cbirt")},
                                   source="pos", pos=pos, stp=None)
    # position-only fallback for stp when a player has no own last-season data at all
    stp_pos_mean = {}
    for pos in ("GKP", "DEF", "MID", "FWD"):
        vals = [b["stp"] for b in baselines.values() if b["pos"] == pos and b["stp"] is not None]
        stp_pos_mean[pos] = sum(vals) / len(vals) if vals else 0.3
    for b in baselines.values():
        if b["stp"] is None:
            b["stp"] = stp_pos_mean.get(b["pos"], 0.3)
    return baselines


# ============================================================ WALK-FORWARD ==
def walk_forward(boot, cache, finished, baselines):
    id_pos = {el["id"]: POS.get(el["element_type"]) for el in boot["elements"]}
    id_name = {el["id"]: el["web_name"] for el in boot["elements"]}
    cum = defaultdict(lambda: dict(mins=0.0, apps=0, starts=0, xg=0.0, xa=0.0,
                                    xgc=0.0, sv=0.0, cbit=0.0, cbirt=0.0))
    weeks = {}
    for gw in finished:
        stats = cache[str(gw)]
        buckets = {k: {"raw": [], "base": [], "shrunk": [], "weights": [],
                       "raw_val": [], "base_val": [], "shrunk_val": []}
                   for k in ALL_METRIC_KEYS}
        pool_now = {mk["key"]: defaultdict(list) for mk in METRICS + DC_METRICS}
        pool_now["stp"] = defaultdict(list)
        # Pass 1: gather this gameweek's live pool (rate-through-prev-GW, n)
        # per position, so k can be derived from THIS week's actual data.
        prepared = []
        for pid_s, s in stats.items():
            pid = int(pid_s)
            pos = id_pos.get(pid)
            mins = _f(s.get("minutes"))
            if mins <= 0 or pos is None:
                continue
            base = baselines.get(pid_s)
            if base is None:
                continue
            c = cum[pid_s]
            prev_n90, prev_apps = c["mins"] / 90.0, c["apps"]
            prepared.append((pid_s, pid, pos, mins, s, base, prev_n90, prev_apps))
            for mk in METRICS + DC_METRICS:
                if pos in mk["positions"] and prev_n90 > 0:
                    short = mk["short"]
                    raw_rate = c[short] / prev_n90
                    pool_now[mk["key"]][pos].append((raw_rate, prev_n90))
            if prev_apps > 0:
                pool_now["stp"][pos].append((c["starts"] / prev_apps, prev_apps))

        k_by_pos = {}
        for mk in METRICS + DC_METRICS:
            for pos in mk["positions"]:
                k, deg = _estimate_k(pool_now[mk["key"]].get(pos, []), mk["dispersion"])
                k_by_pos[(mk["key"], pos)] = (k, deg)
        for pos in ("GKP", "DEF", "MID", "FWD"):
            k, deg = _estimate_k_binomial(pool_now["stp"].get(pos, []))
            k_by_pos[("stp", pos)] = (k, deg)

        # Pass 2: score this gameweek's ACTUAL against predictions built only
        # from data through the previous gameweek, then accumulate.
        for pid_s, pid, pos, mins, s, base, prev_n90, prev_apps in prepared:
            actual = _rates_from_totals(s, mins)
            actual["stp"] = 1.0 if _f(s.get("starts")) > 0 else 0.0
            # Cameo gate - see MIN_MINS_SCORE. Applies to the per-90 rate
            # metrics only; the start-rate block below is deliberately
            # ungated. Gates SCORING, never ACCUMULATION: those cameo
            # minutes are still real data about the player and still feed
            # next week's raw/shrunk estimate further down this loop.
            score_rates = mins >= MIN_MINS_SCORE
            for mk in (METRICS + DC_METRICS) if score_rates else ():
                if pos not in mk["positions"]:
                    continue
                short, key = mk["short"], mk["key"]
                b = base["rates"][short]
                k, deg = k_by_pos[(key, pos)]
                if prev_n90 > 0:
                    raw = cum[pid_s][short] / prev_n90
                    shrunk = (prev_n90 * raw + k * b) / (prev_n90 + k)
                    buckets[key]["raw"].append((raw - actual[short]) ** 2)
                    buckets[key]["raw_val"].append(raw)
                    buckets[key]["weights"].append(prev_n90 / (prev_n90 + k))
                else:
                    shrunk = b
                buckets[key]["base"].append((b - actual[short]) ** 2)
                buckets[key]["base_val"].append(b)
                buckets[key]["shrunk"].append((shrunk - actual[short]) ** 2)
                buckets[key]["shrunk_val"].append(shrunk)
            k, deg = k_by_pos[("stp", pos)]
            bstp = base["stp"]
            if prev_apps > 0:
                raw = cum[pid_s]["starts"] / prev_apps
                shrunk = (prev_apps * raw + k * bstp) / (prev_apps + k)
                buckets["stp"]["raw"].append((raw - actual["stp"]) ** 2)
                buckets["stp"]["raw_val"].append(raw)
                buckets["stp"]["weights"].append(prev_apps / (prev_apps + k))
            else:
                shrunk = bstp
            buckets["stp"]["base"].append((bstp - actual["stp"]) ** 2)
            buckets["stp"]["base_val"].append(bstp)
            buckets["stp"]["shrunk"].append((shrunk - actual["stp"]) ** 2)
            buckets["stp"]["shrunk_val"].append(shrunk)

            # accumulate AFTER scoring, so next week's "raw" includes this week
            c = cum[pid_s]
            c["mins"] += mins; c["apps"] += 1
            c["starts"] += _f(s.get("starts"))
            c["xg"] += _f(s.get("expected_goals")); c["xa"] += _f(s.get("expected_assists"))
            c["xgc"] += _f(s.get("expected_goals_conceded")); c["sv"] += _f(s.get("saves"))
            c["cbit"] += _dc_totals(s); c["cbirt"] += _dcr_totals(s)

        def rmse(xs):
            return (sum(xs) / len(xs)) ** 0.5 if xs else None

        def mean(xs):
            return sum(xs) / len(xs) if xs else None

        weeks[str(gw)] = {
            key: dict(n=len(b["shrunk"]), rmse_raw=rmse(b["raw"]), rmse_base=rmse(b["base"]),
                      rmse_shrunk=rmse(b["shrunk"]), mean_weight=mean(b["weights"]),
                      avg_raw=mean(b["raw_val"]), avg_base=mean(b["base_val"]),
                      avg_shrunk=mean(b["shrunk_val"]),
                      k_by_pos={p: round(k_by_pos[(key, p)][0], 2) for p in ("GKP", "DEF", "MID", "FWD")
                                if (key, p) in k_by_pos},
                      degenerate=any(k_by_pos[(key, p)][1] for p in ("GKP", "DEF", "MID", "FWD")
                                     if (key, p) in k_by_pos))
            for key, b in buckets.items()
        }
    return weeks, cum


# ============================================================ LIVE SNAPSHOT =
def player_snapshot(cum, id_pos, id_name, baselines):
    """PER-PLAYER prior/raw/shrunk, as of the most recent finished gameweek —
    the table panel 1/2 don't give you. Those two answer "does shrinkage work,
    on average, across the pool" (RMSE) and "how much is the pool leaning on
    its own data" (mean weight); neither lets you look up one player. This
    does, using the SAME machinery (own _estimate_k / _estimate_k_binomial,
    same baselines), just re-derived from the FULL season-to-date `cum`
    (every finished gameweek) rather than the walk-forward's held-out
    through-gw-minus-one view — this is "what does the estimate look like
    right now", not a scored prediction, so there is nothing to hold out.

    Returns a flat list of rows, one per (player, metric) with n90/apps > 0.
    """
    pool_now = {mk["key"]: defaultdict(list) for mk in METRICS + DC_METRICS}
    pool_now["stp"] = defaultdict(list)
    prepared = []
    for pid_s, c in cum.items():
        pid = int(pid_s)
        pos = id_pos.get(pid)
        base = baselines.get(pid_s)
        if pos is None or base is None or c["mins"] <= 0:
            continue
        n90, apps = c["mins"] / 90.0, c["apps"]
        prepared.append((pid_s, pos, base, n90, apps, c))
        for mk in METRICS + DC_METRICS:
            if pos in mk["positions"]:
                pool_now[mk["key"]][pos].append((c[mk["short"]] / n90, n90))
        if apps > 0:
            pool_now["stp"][pos].append((c["starts"] / apps, apps))

    k_by_pos = {}
    for mk in METRICS + DC_METRICS:
        for pos in mk["positions"]:
            k_by_pos[(mk["key"], pos)] = _estimate_k(pool_now[mk["key"]].get(pos, []), mk["dispersion"])
    for pos in ("GKP", "DEF", "MID", "FWD"):
        k_by_pos[("stp", pos)] = _estimate_k_binomial(pool_now["stp"].get(pos, []))

    def _ratio(shrunk, prior):
        """shrunk/prior — how the current view compares to the original one.
        None (not 0 or inf) when prior is ~0: "infinitely better than a
        baseline of zero" is not a number worth sorting on."""
        return round(shrunk / prior, 3) if abs(prior) > 1e-9 else None

    rows = []
    for pid_s, pos, base, n90, apps, c in prepared:
        name = id_name.get(int(pid_s), pid_s)
        for mk in METRICS + DC_METRICS:
            if pos not in mk["positions"]:
                continue
            short, key = mk["short"], mk["key"]
            b = base["rates"][short]
            k, deg = k_by_pos[(key, pos)]
            raw = c[short] / n90
            shrunk = (n90 * raw + k * b) / (n90 + k)
            rows.append(dict(name=name, pos=pos, metric=key, prior=round(b, 3),
                              raw=round(raw, 3), shrunk=round(shrunk, 3),
                              ratio=_ratio(shrunk, b),
                              weight=round(n90 / (n90 + k), 3), n=round(n90, 1),
                              base_src=base["source"], degenerate=deg))
        if apps > 0:
            k, deg = k_by_pos[("stp", pos)]
            b = base["stp"]
            raw = c["starts"] / apps
            shrunk = (apps * raw + k * b) / (apps + k)
            rows.append(dict(name=name, pos=pos, metric="stp", prior=round(b, 3),
                              raw=round(raw, 3), shrunk=round(shrunk, 3),
                              ratio=_ratio(shrunk, b),
                              weight=round(apps / (apps + k), 3), n=apps,
                              base_src=base["source"], degenerate=deg))
    return rows


def build():
    empty_state = None
    weeks, finished, snapshot = {}, [], []
    source = None
    try:
        cache, finished = _cache_from_sqlite()
        if cache is not None:
            source = "sqlite"
            boot = _boot_from_priors_snapshot()
        else:
            source = "live API"
            boot = _bootstrap()
            cache, finished, new = update_live_cache(boot)
        if not finished:
            empty_state = "The 2026/27 season has not started yet — no finished gameweeks to score against."
        else:
            baselines = build_baselines()
            weeks, cum = walk_forward(boot, cache, finished, baselines)
            id_pos = {el["id"]: POS.get(el["element_type"]) for el in boot["elements"]}
            id_name = {el["id"]: el["web_name"] for el in boot["elements"]}
            snapshot = player_snapshot(cum, id_pos, id_name, baselines)
            json.dump(dict(updated_utc=f"{dt.datetime.utcnow():%Y-%m-%dT%H:%M:%SZ}", weeks=weeks),
                      open(TRACKER, "w", encoding="utf-8"), indent=1)
            json.dump(dict(updated_utc=f"{dt.datetime.utcnow():%Y-%m-%dT%H:%M:%SZ}",
                            through_gw=finished[-1], rows=snapshot),
                      open(SNAPSHOT, "w", encoding="utf-8"))
    except Exception as e:
        # Network is unavailable in some environments this build runs in
        # (see module docstring) — fall back to whatever was last persisted
        # rather than crashing the whole dashboard publish.
        saved = json.load(open(TRACKER, encoding="utf-8")) if os.path.exists(TRACKER) else {}
        weeks = saved.get("weeks", {})
        snap_saved = json.load(open(SNAPSHOT, encoding="utf-8")) if os.path.exists(SNAPSHOT) else {}
        snapshot = snap_saved.get("rows", [])
        if weeks:
            finished = sorted(int(k) for k in weeks)
            empty_state = f"Live fetch failed ({e}); showing last saved tracker state."
        else:
            empty_state = f"Live fetch failed ({e}) and no saved tracker state exists yet."

    metric_labels = {m["key"]: m["label"] for m in METRICS + DC_METRICS}
    metric_labels["stp"] = "Start rate"
    payload = dict(finished=finished, weeks=weeks, empty_state=empty_state,
                    generated=f"{dt.datetime.now():%Y-%m-%d %H:%M}",
                    metric_labels=metric_labels,
                    # Carried in the payload rather than written into the JS as
                    # a literal: the script below is a plain (non-f) string, so
                    # a hardcoded copy there could drift from MIN_MINS_SCORE.
                    min_mins_score=MIN_MINS_SCORE)

    # DATA IS FETCHED, NOT INLINED — changed 1 Sep 2026, see docs/adr/0002.
    # Everything below the payload write is STATIC: the emitted HTML depends on
    # the layout and the JS, never on this week's numbers, so a data refresh
    # rewrites JSON and leaves docs/priors.html byte-identical. `snapshot` is
    # deliberately absent from the payload — it is already written to SNAPSHOT
    # and the page fetches that file directly, rather than the build shipping a
    # second copy of the same ~180 KB under a different name.
    os.makedirs(os.path.dirname(PAYLOAD), exist_ok=True)
    json.dump(payload, open(PAYLOAD, "w", encoding="utf-8"))

    body = '<div id="app"></div>'
    script = """
<script>
const C = {a:'#4ea3ff',b:'#ffc857',c:'#5fd38d',d:'#ff6b6b',e:'#c792ea',dim:'#8b98a5'};
const css = k => getComputedStyle(document.documentElement).getPropertyValue(k).trim();
Chart.defaults.color = css('--dim');
Chart.defaults.borderColor = css('--grid');
Chart.defaults.font.family = "ui-monospace,Menlo,monospace";
const f3 = n => n===null||n===undefined ? '\\u2014' : n.toFixed(3);
const METRIC_ORDER = ['xg90','xa90','xgc90','sv90','cbit90','cbirt90','stp'];
const COLORS = {xg90:C.a,xa90:C.b,xgc90:C.d,sv90:C.e,cbit90:C.c,cbirt90:'#7aa2ff',stp:'#e0a458'};

function panel(id, title, tests, body){
  const d = document.createElement('div'); d.className='panel'; d.id=id;
  d.innerHTML = `<h2>${title}</h2><p class="tests">${tests}</p>${body}`;
  document.getElementById('app').appendChild(d); return d;
}

function render(DATA) {
// NOT the same test. empty_state is a diagnostic string that gets set in TWO
// different situations (see build_prediction_tracker.py's build()): truly no
// gameweeks scored yet, OR a live fetch just failed and the page is falling
// back to whatever was last persisted \\u2014 which can easily still be a full
// season of real weeks. Gating on empty_state's truthiness conflated those:
// a machine with no network, or missing httpx, silently hid GOOD cached data
// behind a "waiting for gameweeks" panel instead of showing it with a warning.
// The only question that panel should answer is "is there anything to show" \\u2014
// that is DATA.finished, not empty_state.
if (!DATA.finished || DATA.finished.length === 0) {
  panel('waiting', 'Waiting for gameweeks', DATA.empty_state || 'No finished gameweeks yet.',
    `<div class="find">This page tracks, week by week, which of RAW (this season's own data),
     the HIERARCHICAL PRIOR (last season, or a positional fallback), or the SHRUNK blend of the
     two best predicts what a player actually does \\u2014 scored only after the fact, never on
     data it was built from. It fills in automatically as gameweeks finish and this build is
     re-run. See <span class="mono">build_prediction_tracker.py</span> for the full method, and
     <span class="mono">METHODOLOGY_ALTERNATIVES.md</span> ("Shrinkage backtest") for the
     retrospective check already run on 2025/26 that justified building this.</div>`);
} else {
  if (DATA.empty_state) {
    const w = document.createElement('div'); w.className = 'panel'; w.id = 'stale';
    w.innerHTML = `<h2>Showing last saved data</h2><p class="tests">${DATA.empty_state}</p>
      <div class="find">The live fetch did not run this time, so the numbers below are from the
      most recent successful build rather than just now \\u2014 still real, just not necessarily
      current to the latest kickoff.</div>`;
    document.getElementById('app').appendChild(w);
  }
  const gws = DATA.finished;
  const latest = String(gws[gws.length-1]);

  /* ---------- 1. which estimator predicts best \\u2014 latest GW + cumulative ---------- */
  function cum(mkey, uptoIdx){
    let n=0, sr=0, sb=0, ss=0, nr=0, nb=0, ns=0, ar=0, ab=0, as_=0;
    for (let i=0;i<=uptoIdx;i++){
      const w = DATA.weeks[String(gws[i])][mkey];
      if (!w || !w.n) continue;
      n += w.n;
      // Each estimator pools n only over the gameweeks where IT was actually
      // scored that week - raw is null in GW1 (no own-season data yet to
      // build it from), so GW1's n must not inflate raw's denominator even
      // though it inflates n above (n is still shown as "this metric's
      // sample size", which raw's own weeks don't fully cover early season).
      // avg_* is pooled the same n-weighted way, for the same reason.
      if (w.rmse_raw!==null) { sr += w.rmse_raw*w.rmse_raw*w.n; ar += w.avg_raw*w.n; nr += w.n; }
      if (w.rmse_base!==null) { sb += w.rmse_base*w.rmse_base*w.n; ab += w.avg_base*w.n; nb += w.n; }
      if (w.rmse_shrunk!==null) { ss += w.rmse_shrunk*w.rmse_shrunk*w.n; as_ += w.avg_shrunk*w.n; ns += w.n; }
    }
    return {
      n,
      raw: nr?Math.sqrt(sr/nr):null, base: nb?Math.sqrt(sb/nb):null, shrunk: ns?Math.sqrt(ss/ns):null,
      avgRaw: nr?ar/nr:null, avgBase: nb?ab/nb:null, avgShrunk: ns?as_/ns:null,
    };
  }
  // Every cell is (avg predicted value, RMSE against what actually happened) -
  // the average alone can't tell you if an estimator is trustworthy (a wildly
  // wrong prediction and a spot-on one can average to the same number), so it
  // is always shown next to the error that actually measures that.
  const pair = (avg, rmse) => `(${f3(avg)}, ${f3(rmse)})`;
  const rowsSum = METRIC_ORDER.map((k,i)=>{
    const wk = DATA.weeks[latest][k];
    const c = cum(k, gws.length-1);
    const bestLatest = Math.min(wk.rmse_raw??1e9, wk.rmse_base??1e9, wk.rmse_shrunk??1e9);
    const bestCum = Math.min(c.raw??1e9, c.base??1e9, c.shrunk??1e9);
    // "best" now colors the tuple itself rather than appending a pill badge
    // below it - a badge pushed the row taller and visually separated itself
    // from the number it was describing.
    const isBest = (v,best) => v!==null && Math.abs(v-best)<1e-9;
    const bcls = (v,best) => isBest(v,best) ? ' best' : '';
    return `<tr><td><b>${DATA.metric_labels[k]}</b></td><td class="mono">${wk.n}</td>
      <td class="mono cum-gw${bcls(wk.rmse_raw,bestLatest)}">${pair(wk.avg_raw, wk.rmse_raw)}</td>
      <td class="mono cum-gw${bcls(wk.rmse_base,bestLatest)}">${pair(wk.avg_base, wk.rmse_base)}</td>
      <td class="mono cum-gw${bcls(wk.rmse_shrunk,bestLatest)}">${pair(wk.avg_shrunk, wk.rmse_shrunk)}</td>
      <td class="mono cum-season cum-season-start${bcls(c.raw,bestCum)}">${pair(c.avgRaw, c.raw)}</td>
      <td class="mono cum-season${bcls(c.base,bestCum)}">${pair(c.avgBase, c.base)}</td>
      <td class="mono cum-season${bcls(c.shrunk,bestCum)}">${pair(c.avgShrunk, c.shrunk)}</td></tr>`;
  }).join('');
  panel('p1', '1 \\u00b7 Which estimator predicts best right now?',
   `GW${latest} is the latest finished gameweek. Every cell is (average predicted value, RMSE
    against what actually happened that week) \\u2014 lower RMSE is better, best of the three
    tagged per row. <span class="cum-gw-swatch"></span>GW${latest} only on the left,
    <span class="cum-season-swatch"></span>cumulative across every gameweek this season on the
    right, each estimator pooled only over the weeks it was actually scored. Raw for GW1 is blank
    by design: there was no season-so-far data yet to build a raw estimate from. Shrunk is NOT
    blank that week \\u2014 with zero own-season data to blend in it collapses to the prior
    baseline, same number as the
    "prior" column. The per-90 rate metrics score only appearances of
    ${DATA.min_mins_score}+ minutes: a rate computed off a cameo is mostly a division
    artifact (2 minutes and one shot reads as 19 xG/90), and including them
    buried the difference between the three estimators under noise none of
    them can predict. Start rate is deliberately NOT gated \\u2014 it is a
    binary did-he-start, and dropping substitutes would remove exactly the
    zeroes it needs to measure.`,
   `<table class="cum-split"><thead><tr><th>metric</th><th>n (GW${latest})</th>
     <th colspan="3" class="cum-gw-head">Predictions for GW${latest} based on previous weeks</th>
     <th colspan="3" class="cum-season-head cum-season-start">Pooled predictions across all GWs</th></tr>
     <tr><th></th><th></th>
     <th class="cum-gw">raw<span class="th-sub">(&mu;, &sigma;)</span></th>
     <th class="cum-gw">prior<span class="th-sub">(&mu;, &sigma;)</span></th>
     <th class="cum-gw">shrunk<span class="th-sub">(&mu;, &sigma;)</span></th>
     <th class="cum-season cum-season-start">raw<span class="th-sub">(&mu;, &sigma;)</span></th>
     <th class="cum-season">prior<span class="th-sub">(&mu;, &sigma;)</span></th>
     <th class="cum-season">shrunk<span class="th-sub">(&mu;, &sigma;)</span></th></tr></thead>
     <tbody>${rowsSum}</tbody></table>
    <p class="tests" style="margin-top:6px">Each cell reads <span class="mono">(&mu;, &sigma;)</span>
    \\u2014 &mu; is the mean value that estimator predicted across the players scored, &sigma; is
    its RMSE against what they actually did. Two players averaging to the same predicted rate can
    still have wildly different &sigma;, so &mu; alone never tells you which estimator to trust;
    it just tells you what it was predicting when you compare the errors.</p>
    <div class="find">Early season, "prior" (last season, or a positional fallback) often wins
    \\u2014 a handful of matches of noise can be worse than a full season of someone else's
    history. Watch for "shrunk" starting to beat "prior" consistently as gameweeks accumulate;
    that crossover is when a player's own 2026/27 data has become more informative than his
    2025/26 record, which is exactly what panel 2 plots directly.</div>`);

  /* ---------- 2. does raw data gain influence as the season progresses? ---------- */
  panel('p2', '2 \\u00b7 Weight on a player\\'s own data, by gameweek',
   'weight = n90 / (n90 + k) \\u2014 the share of the shrunk estimate coming from THIS season\\'s observations rather than the prior. k is re-derived fresh each gameweek from that week\\'s live pool (not fixed from last season), so a fallback k early on is visible here rather than hidden. Averaged across every player with enough minutes to be scored that week.',
   `<div class="wrap"><canvas id="cWeight"></canvas></div>
    <div class="legend">${METRIC_ORDER.map(k=>`<span><i style="background:${COLORS[k]}"></i>${DATA.metric_labels[k]}</span>`).join('')}</div>
    <div class="find" id="weightFind"></div>`);
  const labels = gws.map(g=>'GW'+g);
  new Chart(cWeight, {type:'line', data:{labels, datasets: METRIC_ORDER.map(k=>({
    label: DATA.metric_labels[k], borderColor: COLORS[k], backgroundColor: COLORS[k],
    data: gws.map(g => DATA.weeks[String(g)][k].mean_weight),
    spanGaps: true, pointRadius: 3, pointHoverRadius: 6, borderWidth: 2, tension: 0.2})) },
   options:{plugins:{legend:{display:false}},
    scales:{y:{min:0,max:1,title:{display:true,text:'weight on own data (0 = pure prior, 1 = pure raw)'},grid:{color:css('--grid')}},
            x:{title:{display:true,text:'gameweek'},grid:{color:css('--grid')}}}}});
  const firstDeg = METRIC_ORDER.find(k => DATA.weeks[latest][k].degenerate);
  document.getElementById('weightFind').innerHTML = firstDeg
    ? `<b>${DATA.metric_labels[firstDeg]}</b> is still on a fallback k as of GW${latest} \\u2014
       not enough players have crossed the 270-minute (3 x 90) floor _estimate_k() requires for
       a trustworthy variance read yet. Expect the fallback tag to clear metric by metric as the
       season goes on, not all at once.`
    : `Every metric has a properly-derived (non-fallback) k as of GW${latest}.`;

  /* ---------- 3. per player \\u2014 look one up ---------- */
  panel('p3', '3 \\u00b7 One player: prior vs raw vs shrunk, right now',
   `As of GW${latest}. Click any column header to sort by it (click again to reverse); starts
    sorted by WEIGHT, highest first. <b>PRIOR</b> = last season\\'s rate, or a positional fallback
    for a mover/newcomer (see BASE). <b>RAW</b> = this player\\'s own 2026/27 rate so far \\u2014
    unstable on a handful of matches, shown for reference. <b>SHRUNK</b> = the blend the live
    screens actually use; this is the number that matters. <b>SHRUNK/PRIOR</b> = shrunk divided by
    prior \\u2014 the quickest way to spot who is tracking meaningfully above (green, >1) or below
    (red, <1) the original pre-season view, once weight has moved enough for it to mean anything.
    <b>WEIGHT</b> = n90/(n90+k) (or apps/(apps+k) for start rate) \\u2014 the share of SHRUNK coming
    from this player\\'s own data rather than the prior; 0 = pure prior, 1 = pure raw. Low weight
    means don\\'t read much into SHRUNK/PRIOR yet, however extreme it looks. <b>N</b> = 90s played
    (or appearances, for start rate) backing RAW \\u2014 the sample size WEIGHT is built from.
    <b>BASE</b> = where PRIOR came from: <span class="mono">own</span> (this player\\'s own 900+-min
    2025/26 rate) or <span class="mono">pos</span> (a positional fallback \\u2014 less trustworthy,
    typical for a newcomer or a mover the contaminated-prior check excluded).`,
   `<input id="pq" type="text" placeholder="Filter by name\\u2026" autocomplete="off"
      style="width:100%;box-sizing:border-box;padding:6px 8px;margin:6px 0;
      background:${css('--panel')};color:inherit;border:1px solid ${css('--grid')};border-radius:4px;">
    <div style="max-height:480px;overflow:auto">
    <table><thead><tr id="pHead"></tr></thead>
      <tbody id="pBody"></tbody></table></div>`);
  const SNAP_COLS = [
    {key:'name',    label:'player', type:'str'},
    {key:'pos',     label:'pos',    type:'str'},
    {key:'metric',  label:'metric', type:'str',
      fmt: r => DATA.metric_labels[r.metric] || r.metric},
    {key:'prior',   label:'prior',  type:'num'},
    {key:'raw',     label:'raw',    type:'num'},
    {key:'shrunk',  label:'shrunk', type:'num'},
    {key:'ratio',   label:'shrunk/prior', type:'num',
      fmt: r => r.ratio===null ? '\\u2014'
        : `<span style="color:${r.ratio>1.02?css('--c'):r.ratio<0.98?css('--d'):'inherit'}">`
          +`${r.ratio.toFixed(2)}\\u00d7</span>`},
    {key:'weight',  label:'weight', type:'num',
      fmt: r => f3(r.weight) + (r.degenerate ? ' <span class="tag bad">fallback k</span>' : '')},
    {key:'n',       label:'n',      type:'num'},
    {key:'base_src',label:'base',   type:'str'},
  ];
  let sortKey = 'weight', sortDir = -1;   // -1 = desc (matches the old default)
  document.getElementById('pHead').innerHTML = SNAP_COLS.map(c =>
    `<th data-key="${c.key}" style="cursor:pointer;user-select:none">${c.label}`
    + `<span class="sortmark" data-key="${c.key}"></span></th>`).join('');
  function markSort() {
    document.querySelectorAll('#pHead .sortmark').forEach(el => {
      el.textContent = el.dataset.key === sortKey ? (sortDir === 1 ? ' \\u25b2' : ' \\u25bc') : '';
    });
  }
  const SNAP = (DATA.snapshot || []).slice();
  function renderSnap(filter) {
    const q = (filter||'').toLowerCase();
    const col = SNAP_COLS.find(c => c.key === sortKey);
    const rows = (q ? SNAP.filter(r => r.name.toLowerCase().includes(q)) : SNAP).slice().sort((a,b) => {
      let av = a[sortKey], bv = b[sortKey];
      if (col.type === 'num') { av = av===null?-Infinity:av; bv = bv===null?-Infinity:bv; return sortDir*(av-bv); }
      return sortDir*String(av).localeCompare(String(bv));
    }).slice(0, 400);
    document.getElementById('pBody').innerHTML = rows.map(r => '<tr>' + SNAP_COLS.map(c =>
      `<td class="${c.key==='name'?'':'mono'}">`
      + `${c.fmt ? c.fmt(r) : (c.type==='num' ? f3(r[c.key]) : (r[c.key]??'\\u2014'))}</td>`).join('')
      + '</tr>').join('') || `<tr><td colspan="${SNAP_COLS.length}">No match.</td></tr>`;
    markSort();
  }
  document.getElementById('pHead').addEventListener('click', e => {
    const th = e.target.closest('th'); if (!th) return;
    const key = th.dataset.key;
    sortDir = (key === sortKey) ? -sortDir : -1;
    sortKey = key;
    renderSnap(document.getElementById('pq').value);
  });
  renderSnap('');
  document.getElementById('pq').addEventListener('input', e => renderSnap(e.target.value));
}
}

fetch('data/priors_payload.json', {cache: 'no-store'})
  .then(r => { if (!r.ok) throw new Error('priors_payload.json \u2014 HTTP ' + r.status); return r.json(); })
  .then(payload =>
    fetch('data/priors_player_snapshot.json', {cache: 'no-store'})
      .then(r => r.ok ? r.json() : {rows: []})
      .catch(() => ({rows: []}))
      .then(snap => Object.assign(payload, {snapshot: snap.rows || []})))
  .then(DATA => {
    const m = document.getElementById('subMeta');
    if (m) m.textContent = 'data generated ' + DATA.generated
      + (DATA.finished && DATA.finished.length
         ? ' \u00b7 through GW' + DATA.finished[DATA.finished.length - 1] : '');
    render(DATA);
  })
  .catch(e => {
    document.getElementById('app').innerHTML =
      '<div class="panel"><h2>Data not loaded</h2>'
      + '<p class="tests">' + e.message + '</p>'
      + '<div class="find">This page reads its numbers from '
      + '<span class="mono">data/priors_payload.json</span> at load time rather than carrying '
      + 'them inline, so a weekly refresh rewrites JSON and leaves this file unchanged '
      + '(see <span class="mono">docs/adr/0002</span>). The cost is that opening it straight '
      + 'off disk on a <span class="mono">file://</span> URL can never work \u2014 browsers '
      + 'refuse fetch there. Serve the folder instead: <span class="mono">python3 -m '
      + 'http.server</span> from <span class="mono">docs/</span>, then open '
      + '<span class="mono">localhost:8000/priors.html</span>.</div></div>';
  });
</script>"""

    html = page_shell.shell(
        title="Prior vs reality",
        active="priors",
        # No generated-at stamp or gameweek number here: both are data, and a
        # data-dependent subtitle would put this file back in the weekly diff
        # for the sake of two facts. render() fills #subMeta from the payload.
        subtitle=('Live weekly walk-forward tracker &middot; '
                   '<span id="subMeta">loading&hellip;</span>'),
        body=body,
        footer="Built by <span class='mono'>build_prediction_tracker.py</span>. Scores raw, prior, "
               "and shrunk against each gameweek only AFTER it finishes, using only data through "
               "the gameweek before. Numbers load from <span class='mono'>data/priors_payload.json</span>; "
               "see METHODOLOGY_ALTERNATIVES.md for the 2025/26 backtest that "
               "validated the shrinkage mechanism before this live version was built.")
    html = html.replace("</body>", script + "\n</body>")
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    open(OUT, "w", encoding="utf-8").write(html)
    # `source` is CLI-only diagnostic (was this run sourced from the SQLite
    # cache or the live API), never written to PAYLOAD - the browser only
    # needs empty_state to know whether the numbers are current or stale.
    return html, dict(payload, snapshot=snapshot, source=source)


if __name__ == "__main__":
    h, payload = build()
    print(f"written: {OUT}  ({len(h)/1024:.0f} KB)")
    print(f"  data source: {payload['source'] or 'unknown'}")
    assert "cdn.jsdelivr.net/npm/chart.js@4.5.0" in h, "Chart.js tag missing"
    if payload["empty_state"]:
        print(f"  {payload['empty_state']}")
    else:
        latest = payload["finished"][-1]
        print(f"  through GW{latest}, {len(payload['finished'])} gameweek(s) scored")
        for k, label in payload["metric_labels"].items():
            w = payload["weeks"][str(latest)][k]
            print(f"  {label:16s} n={w['n']:4d}  RMSE raw {w['rmse_raw']}  base {w['rmse_base']}  "
                  f"shrunk {w['rmse_shrunk']}  weight {w['mean_weight']}")
        n_deg = sum(1 for r in payload["snapshot"] if r["degenerate"])
        print(f"  player snapshot: {len(payload['snapshot'])} (player, metric) rows written to "
              f"{SNAPSHOT}  ({n_deg} still on a fallback k)")
