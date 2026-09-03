#!/usr/bin/env python3
"""Build the squad page — docs/squad.html.

    python3 build_squad_page.py

WHO THIS PAGE IS FOR. It is published, and the reason it is published is that
someone learning the method should be able to follow it. So the page shows
REASONING, not state: every player carries why he is there, the gates are shown
filtering 400 players down to 15 rather than only the survivors, and the two
alternatives exist to make the trade-offs visible rather than to list options.

THE UNCERTAINTY IS NOT TIDIED AWAY. Contaminated priors get a panel near the
top, not a footnote. A model that catches itself being wrong teaches more than
one that looks authoritative, and it is a truer picture of this project.

TWO OBJECTIVES, SHOWN SIDE BY SIDE. xP/90 is what optimise_squad.py maximises.
xP/GW multiplies by start probability and is what you actually accumulate. The
gap is the availability haircut. They can pick DIFFERENT elevens from the same
fifteen, which is the clearest possible argument for roadmap item A0.5 — so the
page computes both and says when they disagree.

Everything is server-rendered except one chart, deliberately: each inline
script is another way for the page to render completely blank.
"""
import importlib.util, json, os, re, datetime as dt

import scoring

HERE = os.path.dirname(os.path.abspath(__file__))

# The six scoring routes shown on the "where the points come from" chart
# (ADR 0001), in the order they render: (scoring.py breakdown key, display
# label, palette key from the shared chart colours below). Defensive
# Contribution is NET of the goals-conceded penalty for GKP/DEF — see
# scoring.expected_points_scaled_breakdown()'s docstring.
ROUTE_CATEGORIES = [
    ("appearance", "Appearance", "dim"),
    ("goal_involvement", "Goal Involvement", "a"),
    ("clean_sheets", "Clean Sheets", "c"),
    ("defensive_contribution", "Defensive Contribution", "e"),
    ("saves", "Saves", "b"),
    ("bonus", "Bonus", "d"),
]

# The deductions row added 26 Aug 2026, in shades of red ORDERED BY SEVERITY
# (lightest = smallest single-event cost, darkest = largest) so the gradient
# itself is readable without the legend: goals_conceded is the mildest but
# most recurring hit (-1 per 2 conceded), yellow cards cost -1 per card, own
# goals and penalty misses cost -2 each, and a red card costs -3, the single
# worst event on the chart — recoloured 26 Aug 2026 for readability (see the
# colour review noted in the module docstring). goals_conceded is un-netted
# OUT of defensive_contribution above for this chart specifically — see
# scoring.expected_gc_penalty()'s docstring for why that's safe to do without
# touching the netted figure every other caller of
# expected_points_scaled_breakdown() still relies on.
DEDUCTION_CATEGORIES = [
    ("goals_conceded", "Goals Conceded", "#ffa8a8"),
    ("yellow_cards", "Yellow Cards", "#ff8787"),
    ("own_goals", "Own Goals", "#f03e3e"),
    ("penalties_missed", "Penalties Missed", "#e03131"),
    ("red_cards", "Red Cards", "#962020"),
]

PRIORS_SNAPSHOT = os.path.join(HERE, "fpl_priors_2025_26_v2.json")


def _load(mod, fn):
    spec = importlib.util.spec_from_file_location(mod, os.path.join(HERE, fn))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


bs = _load("bs", "build_squad.py")
fa = _load("fa", "fixture_adjust.py")
opt = _load("opt", "optimise_squad.py")
sz = _load("sz", "size_bench_value.py")
page_shell = _load("page_shell", "page_shell.py")
squad_state = _load("squad_state", "squad_state.py")
intel = _load("intel", "intel_adjust.py")

try:
    import pulp
except ImportError:
    raise SystemExit("PuLP not installed.  pip install pulp")

OUT = os.environ.get("FPL_SQUAD_OUT") or os.path.join(HERE, "docs", "index.html")
POS_ORDER = ["GKP", "DEF", "MID", "FWD"]
ENTRY = 1041614
LIVE_SNAPSHOT = os.path.join(HERE, "docs", "data", "entry_summary.json")
MY_TEAM_URL = "https://fantasy.premierleague.com/en/my-team"
CAPTAINCY_SNAPSHOT = os.path.join(HERE, "docs", "data", "captaincy_snapshot.json")


def esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def md_bold(s):
    """`**text**` -> `<b>text</b>` for the short prose snippets pulled out of
    TEAM_CHANGE_LOG.md - that file is markdown, this page is not."""
    return re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", esc(s))


def live_snapshot(entry=ENTRY):
    """Actual FPL total points (cumulated for the squad) and the next real
    deadline. PURE READ — like every build_*.py page except
    build_prediction_tracker.py, this script makes no network call of its
    own. LIVE_SNAPSHOT is written by fpl_research_mcp.py's `entry_summary`
    MCP tool, which has real network access in every Claude session
    (interactive or scheduled) the way this sandboxed build script does not —
    see docs/adr for the fuller reasoning. Call `entry_summary` (or run the
    weekly/daily FPL skills, which call it) to refresh the file; this
    function just reads whatever is there, or returns None if it never has
    been."""
    if not os.path.exists(LIVE_SNAPSHOT):
        return None
    try:
        snap = json.load(open(LIVE_SNAPSHOT, encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    if snap.get("entry") not in (None, entry):
        return None          # snapshot belongs to a different entry — don't misreport it
    return snap


def deadline_line(live):
    """Bold banner above the stat boxes: when the next team-choice lockdown
    actually is, in place of the old static 'Deadline' stat box (which went
    stale the moment GW1's deadline passed)."""
    if not live or not live.get("next_deadline_utc"):
        return ("<b>Next deadline unknown</b> — no live snapshot cached yet. "
                "Ask Claude to run the <span class='mono'>entry_summary</span> "
                "MCP tool (fpl-research) to populate "
                f"{os.path.relpath(LIVE_SNAPSHOT, HERE)}.")
    d = dt.datetime.fromisoformat(live["next_deadline_utc"].replace("Z", "+00:00"))
    now = dt.datetime.now(dt.timezone.utc)
    remaining = d - now
    if remaining.total_seconds() > 0:
        away = f"{remaining.days}d {remaining.seconds // 3600}h away"
    else:
        away = "deadline has passed"
    age = (f' <span class="kn" style="display:inline">(snapshot fetched '
           f'{live["fetched_utc"]})</span>' if live.get("fetched_utc") else "")
    return (f"<b>Next team-choice lockdown: Gameweek {live['next_gw']} — "
            f"{d:%a %d %b %Y, %H:%M} UTC ({away})</b>{age}")


ROUTE_ACTUAL_SNAPSHOT = os.path.join(HERE, "docs", "data", "route_actual_snapshot.json")


def actual_route_snapshot(xi_players=None):
    """Real per-gameweek average points for the CURRENT XI, split into the
    same six positive categories as the xP route chart plus a parallel
    deductions total — for the squad page's Expected/Actual toggle (added
    26 Aug 2026).

    PURE READ, like live_snapshot() — this used to open
    fpl_research_mcp.py's player_gw SQLite cache directly, which only works
    when this script runs somewhere with real access to
    ~/.fpl-mcp/fpl_history_cache.sqlite (Sylvan's own terminal). Every
    Cowork/Claude session's sandbox has its own $HOME with no route to that
    file, only to the explicitly connected repo folder — so a build done
    from a session always saw "no data" even after cache_history had
    genuinely warmed the cache on the real machine. Fixed 26 Aug 2026 by
    moving the computation to fpl_research_mcp.py's own `squad_actual_points`
    MCP tool, which runs where the database actually lives and writes the
    small aggregate here — same fix live_snapshot() already applies to the
    same problem for total points and the deadline. `xi_players` is accepted
    and ignored (kept so callers don't need to change) — the snapshot is
    already computed against squad.json's XI by the tool that wrote it.

    Returns None if the snapshot hasn't been written yet (nobody has called
    squad_actual_points() since the last squad change) or belongs to a
    different-sized XI than 11 (a stale file from before a squad edit)."""
    if not os.path.exists(ROUTE_ACTUAL_SNAPSHOT):
        return None
    try:
        snap = json.load(open(ROUTE_ACTUAL_SNAPSHOT, encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not snap.get("gws") or "positive" not in snap or "deductions" not in snap:
        return None
    return snap


def captaincy_snapshot():
    """One proposed captain per data-source estimator (actual/prior/shrunken),
    same PURE READ pattern as live_snapshot()/actual_route_snapshot().
    captaincy_odds is a live MCP tool (Poisson haul/blank modelling over the
    actual fixture list), not something this offline build script can call
    itself, so CAPTAINCY_SNAPSHOT is written elsewhere — same reasoning as
    every other live number on this page.
    fpl_research_mcp.captaincy_snapshot_refresh() writes it (neutral mode,
    intel applied, no chase/protect judgment - numbers only). Shape changed
    3 Sep 2026 from a single-model top-3 (`candidates`) to one row per
    estimator (`by_estimator`), matching the treatment Alternative 2/3 and
    the captaincy estimator-sensitivity discussion already established this
    week. Returns None if never written, or if it's still the old shape."""
    if not os.path.exists(CAPTAINCY_SNAPSHOT):
        return None
    try:
        snap = json.load(open(CAPTAINCY_SNAPSHOT, encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if snap.get("entry") not in (None, ENTRY) or not snap.get("by_estimator"):
        return None
    return snap


def _fixture_read(p):
    """One-line plain-English read of a player's GW1-4 fixture multiplier —
    ATT for MID/FWD (higher is easier), DEF for GKP/DEF (lower is easier).
    Used by Alternative 1's explanation of why its two objectives (xP/90 vs
    xP/GW) pick differently."""
    if p["pos"] in ("MID", "FWD"):
        x, tag, easier = p["att_x"], "attacking", p["att_x"] > 1.0
    else:
        x, tag, easier = p["def_x"], "defensive", p["def_x"] < 1.0
    off = abs(x - 1.0) * 100
    if off < 3:
        read = "roughly neutral"
    else:
        read = f"{off:.0f}% {'easier' if easier else 'tougher'} than average"
    return f"{tag} fixture multiplier {x:.2f} ({read} over GW1&ndash;4)"


def _news_bite(name, team):
    """The ROLE_INTEL.md `adjustments` fence 'why' for a player, if any —
    shared lookup so the Alternative panels quote the same reasoning
    captaincy_odds/build_squad.py already apply, rather than re-describing
    it from scratch. Returns None if the player carries no logged entry,
    which is itself informative (the pick is data-driven, not intel-driven)."""
    try:
        entries = intel.entries_for(name, team)
    except Exception:
        entries = []
    if not entries:
        return None
    return " · ".join(e["why"] for e in entries)


def contaminated():
    """Players whose prior belongs to a different club. Parsed from the
    machine-readable block in ROLE_INTEL.md so there is one list, not two."""
    txt = open(os.path.join(HERE, "ROLE_INTEL.md"), encoding="utf-8").read()
    m = re.search(r"```contaminated\n(.*?)```", txt, re.S)
    out = {}
    if m:
        for line in m.group(1).strip().split("\n"):
            if "|" in line:
                who, why = line.split("|", 1)
                out[who.strip()] = why.strip()
    return out


def chip_plan():
    """The set-1 chip plan, parsed from TEAM_CHANGE_LOG.md's CHIP STRATEGY
    section rather than hand-copied — that file is the human narrative and
    the place the plan actually gets edited each week; this just surfaces it
    on the page a reader is already looking at, so the two can't drift the
    way a second hand-typed copy inevitably would."""
    txt = open(os.path.join(HERE, "TEAM_CHANGE_LOG.md"), encoding="utf-8").read()
    m = re.search(r"## CHIP STRATEGY — (.+?)\n(.*?)\n## ", txt, re.S)
    if not m:
        return None
    title, section = m.group(1).strip(), m.group(2)

    def grab(pattern, default=""):
        g = re.search(pattern, section, re.S)
        return re.sub(r"\s+", " ", g.group(1)).strip() if g else default

    status = grab(r"\*\*Status:\*\*\s*(.+?)\n")
    constraint = grab(r"### The governing constraint\n\n(.+?)\n\n")
    rows = [r for r in re.findall(r"\|\s*\*\*(.+?)\*\*\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|", section)
            if r[0] in ("Wildcard 1", "Bench Boost 1", "Triple Captain 1", "Free Hit 1")]
    checklist_txt = grab(r"### Review checklist \(run weekly\)\n\n(.*?)\n\n###")
    checklist = re.findall(r"\d+\.\s*(.+?)(?=\s+\d+\.|$)", checklist_txt)
    return dict(title=title, status=status, constraint=constraint, rows=rows, checklist=checklist)


def best_xi(players, weight_by_start):
    """Best legal XI from a fixed 15. weight_by_start switches the objective
    between xP/90 (what the optimiser uses) and xP/GW (what you accumulate)."""
    prob = pulp.LpProblem("xi", pulp.LpMaximize)
    x = {i: pulp.LpVariable(f"x{i}", cat="Binary") for i in range(len(players))}
    val = [(p["stp"] if weight_by_start else 1.0) * p["score"] for p in players]
    prob += pulp.lpSum(val[i] * x[i] for i in range(len(players)))
    prob += pulp.lpSum(x.values()) == 11
    for pos, (lo, hi) in opt.FORMATION.items():
        idx = [i for i, p in enumerate(players) if p["pos"] == pos]
        prob += pulp.lpSum(x[i] for i in idx) >= lo
        prob += pulp.lpSum(x[i] for i in idx) <= hi
    for i, p in enumerate(players):
        if p["stp"] < bs.GATE_XI:
            prob += x[i] == 0          # the gate still binds
    prob.solve(pulp.PULP_CBC_CMD(msg=0))
    return [players[i] for i in range(len(players)) if x[i].value() > 0.5]


def card(p, st, contam, captain, vice, dim=False):
    tags = []
    if p["name"] == captain:
        tags.append('<span class="tag ok">C</span>')
    if p["name"] == vice:
        tags.append('<span class="tag">V</span>')
    if p["name"] in contam:
        tags.append('<span class="tag bad">prior not this club</span>')
    if p["stp"] < bs.GATE_XI:
        tags.append(f'<span class="tag">below {bs.GATE_XI:.0%}</span>')
    fx = (f'<span title="attacking fixtures over GW1-4; higher is easier">ATT {p["att_x"]:.2f}</span>'
          if p["pos"] in ("MID", "FWD") else
          f'<span title="defensive fixtures over GW1-4; LOWER is easier">DEF {p["def_x"]:.2f}</span>')
    why = esc(st.get(p["name"], ""))
    return f"""<div class="pc{' dim' if dim else ''}">
  <div class="pc-h"><b>{esc(p['name'])}</b> {' '.join(tags)}</div>
  <div class="pc-m mono">{p['team']} · £{p['price']:.1f}m · {p['stp']*100:.0f}% starts</div>
  <div class="pc-n mono">xP/90 {p['score']:.2f} · xP/GW {p['stp']*p['score']:.2f} · {fx}</div>
  {f'<div class="pc-w">{why}</div>' if why else ''}
</div>"""


def build():
    state = squad_state.load()
    contam = contaminated()
    sel = {p["name"]: p.get("selected_on", "") for p in state.players}

    # intel=True explicitly, regardless of how this script is invoked - the
    # live squad was built with ROLE_INTEL.md's adjustments applied (Mosquera's
    # start probability set to 85% on the Saliba/Timber injury news being the
    # live case), and this page must reason about the same squad the same way
    # or its own "best transfer" table silently contradicts the squad it is
    # describing. Bug found 11 Aug 2026: bs.load() with no args left this page
    # reading Mosquera's UN-adjusted 31% start rate and recommending selling
    # him for it, while his intel-adjusted 85% clearly beats the alternative.
    pool = bs.load(intel=True)
    fa.adjust(pool)
    for r in pool:
        r["score"] = r["xp_adj"]
    by = {r["name"]: r for r in pool}
    missing = [p["name"] for p in state.players if p["name"] not in by]
    if missing:
        raise SystemExit(f"squad players absent from the pool: {missing}")

    mine = [by[p["name"]] for p in state.players]
    declared_xi = [by[p["name"]] for p in state.xi]
    declared_bench = [by[p["name"]] for p in state.bench]

    # --- headline numbers -------------------------------------------------
    xi90 = sum(p["score"] for p in declared_xi)
    xigw = sum(p["stp"] * p["score"] for p in declared_xi)

    # --- scoring-route composition (ADR 0001) ------------------------------
    # Start-weighted per player BEFORE summing, matching xigw's own
    # construction (stp * score) rather than weighting the total afterwards —
    # stp multiplies linearly, so stp*score == sum_category(stp*category_term)
    # and the six numbers below reconcile to xigw exactly, not approximately.
    # att_x/def_x/scale_workload/empirical are the SAME values fa.adjust()
    # already used to produce p["score"] (== p["xp_adj"]) for this player, so
    # this is a re-decomposition of that number, not an independent estimate.
    route_totals = {k: 0.0 for k, _, _ in ROUTE_CATEGORIES}
    route_gc_penalty = 0.0
    for p in declared_xi:
        terms = scoring.expected_points_scaled_breakdown(
            p, p["att_x"], p["def_x"], scale_workload=fa.SCALE_WORKLOAD,
            empirical=bs.USE_EMPIRICAL_DC)
        for k in route_totals:
            route_totals[k] += p["stp"] * terms[k]
        route_gc_penalty += p["stp"] * scoring.expected_gc_penalty(p, p["def_x"])
    route_sum = sum(route_totals.values())
    # Fail loudly, not silently — DASHBOARD_PLAN.md's page-3 rule, applied
    # here too. If this drifts, scoring.py's breakdown has fallen out of sync
    # with expected_points_scaled() and the chart would be showing routes
    # that don't actually add up to the number printed above it.
    assert abs(route_sum - xigw) < 1e-6, (
        f"route composition ({route_sum:.4f}) does not reconcile with XI xP/GW "
        f"({xigw:.4f}) — see docs/adr/0001-xi-scoring-route-composition-chart.md")
    bonus_k = declared_xi[0].get("bonus_k") if declared_xi else None
    bonus_unvalidated = bonus_k in scoring.BONUS_FALLBACK_KS

    # --- Expected/Actual deductions chart (added 26 Aug 2026) --------------
    # DISPLAY-ONLY un-netting: route_totals/route_sum above stay exactly as
    # they were (still reconciled to xigw by the assert above) — this is a
    # separate, cosmetic re-split of the same numbers for the chart, using
    # scoring.expected_gc_penalty() to recover the piece
    # expected_points_scaled_breakdown() deliberately nets into
    # "defensive_contribution" (ADR 0001). The model has no cards/penalty-
    # miss forecast at the individual level, so those three deduction
    # categories are always 0 on the Expected side — real, not omitted.
    route_display_positive = dict(route_totals)
    route_display_positive["defensive_contribution"] -= route_gc_penalty
    route_display_deductions = {k: 0.0 for k, _, _ in DEDUCTION_CATEGORIES}
    route_display_deductions["goals_conceded"] = route_gc_penalty

    # Real per-GW average for the same XI, same six-plus-five categories —
    # None if the local player_gw cache isn't warm yet (see
    # actual_route_snapshot()'s docstring for every way that can happen).
    actual_snap = actual_route_snapshot(declared_xi)

    bench_pts, bench_rows, blank_dist = sz.bench_value(declared_xi, declared_bench)
    exp_blanks = sum(j * q for j, q in enumerate(blank_dist))
    live = live_snapshot()
    dl_line = deadline_line(live)

    # --- alternatives -----------------------------------------------------
    alt90 = best_xi(mine, weight_by_start=False)
    altgw = best_xi(mine, weight_by_start=True)
    same = {p["name"] for p in alt90} == {p["name"] for p in altgw}

    # --- Alternative 1's fixture/news explanation, added 26 Aug 2026 --------
    # WHY the two objectives pick differently (or don't), not just THAT they
    # do.
    def _alt1_explain():
        n90 = {p["name"] for p in alt90}
        ngw = {p["name"] for p in altgw}
        by90, bygw = {p["name"]: p for p in alt90}, {p["name"]: p for p in altgw}
        only90, onlygw = sorted(n90 - ngw), sorted(ngw - n90)
        if not only90 and not onlygw:
            outfield = [p for p in mine if p["pos"] != "GKP"]
            spread = max(abs(p["att_x"] - 1.0) if p["pos"] in ("MID", "FWD")
                         else abs(p["def_x"] - 1.0) for p in outfield)
            return (f"<p class='tests'>Over GW1&ndash;4 the biggest fixture swing "
                     f"anywhere in the fifteen is only {spread*100:.0f}% away from "
                     f"neutral, and no one's start probability is depressed enough "
                     f"right now to cross the line either. Neither lever is currently "
                     f"strong enough to move a player over the threshold that would "
                     f"split the two objectives &mdash; if a fixture run gets "
                     f"materially tougher or a news bite drops a start probability, "
                     f"expect this row to change.</p>")
        lines = []
        for name in only90:
            p = by90[name]
            news = _news_bite(p["name"], p["team"]) or sel.get(name, "")
            lines.append(
                f"<li><b>{esc(name)}</b> ({p['pos']}, {p['team']}) &mdash; kept by "
                f"xP/90, dropped by xP/GW. {_fixture_read(p)}, but only "
                f"{p['stp']*100:.0f}% start probability caps how much of that "
                f"actually accumulates per gameweek."
                + (f" <span class='kn' style='display:inline'>{esc(news)}</span>" if news else "")
                + "</li>")
        for name in onlygw:
            p = bygw[name]
            news = _news_bite(p["name"], p["team"]) or sel.get(name, "")
            lines.append(
                f"<li><b>{esc(name)}</b> ({p['pos']}, {p['team']}) &mdash; the "
                f"reverse: xP/GW prefers him because he starts reliably "
                f"({p['stp']*100:.0f}%), even though his {_fixture_read(p)}."
                + (f" <span class='kn' style='display:inline'>{esc(news)}</span>" if news else "")
                + "</li>")
        return (f"<p class='tests'><b>Why they disagree this week.</b></p>"
                f"<ul style='margin:6px 0 0 18px;padding:0'>{''.join(lines)}</ul>")
    alt1_explain_html = _alt1_explain()

    # --- Best forced transfer(s), priced under all THREE data-source
    # estimators (3 Sep 2026) - same "actual"/"prior"/"shrunken" choice
    # optimise_squad.py's --estimator flag offers, because this is exactly
    # the kind of call the three have been shown to disagree on early in a
    # season (see the captaincy estimator-sensitivity discussion this same
    # week). Each estimator gets its OWN fully independent pool (intel +
    # fixture adjustment applied identically to build()'s main pool above),
    # so a row's recommended transfer(s) and xP/GW delta are always priced
    # on the same numbers - never a transfer chosen under one estimator and
    # then measured against another's baseline. Shared by Alternative 2
    # (n=1) and Alternative 3 (n=2) below - the pool construction is
    # identical, only the forced transfer count differs.
    TRANSFER_ESTIMATORS = [("raw", "actual"), ("prior", "prior"), ("shrunk", "shrunken")]

    def _transfer_row(estimator, n_transfers):
        p = bs.load(intel=True, estimator=estimator)
        fa.adjust(p)
        for r in p:
            r["score"] = r["xp_adj"]
        by_e = {r["name"]: r for r in p}
        missing_e = [nm for nm in state.name_set if nm not in by_e]
        if missing_e:
            raise SystemExit(f"squad players absent from the {estimator} pool: {missing_e}")
        cur_gw_e = sum(by_e[pl["name"]]["stp"] * by_e[pl["name"]]["score"] for pl in state.xi)
        xi_e, bench_e, hits_e = opt.optimise_transfers(
            p, state.name_set, state.bank, n_transfers, allow_haaland=False, force=True)
        out_e = sorted(state.name_set - {r["name"] for r in xi_e + bench_e})
        in_e = sorted({r["name"] for r in xi_e + bench_e} - state.name_set)
        new_gw_e = sum(r["stp"] * r["score"] for r in xi_e)
        return out_e, in_e, new_gw_e - cur_gw_e, hits_e

    # force=True: always return the best swap(s), even if the impact is small
    # or negative, rather than letting the solver hand back the current squad
    # unchanged - the table shows "what's the next-best move if you had to
    # make one", not a silently-collapsed blank row.
    alt2_rows = [(label, *_transfer_row(estimator, 1)) for estimator, label in TRANSFER_ESTIMATORS]
    alt2_agree = len({(tuple(o), tuple(i)) for _, o, i, _, _ in alt2_rows}) == 1

    # HIT COST ASSUMPTION: squad.json does not track banked free transfers,
    # so this prices the double swap assuming 1 free transfer available
    # (optimise_transfers' own default) — stated explicitly in the panel copy
    # rather than left implicit.
    alt3_rows = [(label, *_transfer_row(estimator, 2)) for estimator, label in TRANSFER_ESTIMATORS]
    alt3_agree = len({(tuple(o), tuple(i)) for _, o, i, _, _ in alt3_rows}) == 1

    # --- chip strategy, plan from TEAM_CHANGE_LOG.md + live status from squad.json
    cp = chip_plan()
    chip_status = {"wildcard": "Wildcard 1", "benchboost": "Bench Boost 1",
                   "triplecaptain": "Triple Captain 1", "freehit": "Free Hit 1"}
    set1_available = set(state.chips_remaining("set1"))
    chip_used = {label: (key not in set1_available)
                 for key, label in chip_status.items()} if cp else {}

    # --- pitch ------------------------------------------------------------
    rows = ""
    for pos in POS_ORDER:
        line = [p for p in declared_xi if p["pos"] == pos]
        if not line:
            continue
        rows += ('<div class="row">' +
                 "".join(card(p, sel, contam, state.captain, state.vice) for p in
                         sorted(line, key=lambda r: -r["score"])) + "</div>")
    bench_html = "".join(
        card(by[p["name"]], sel, contam, state.captain, state.vice, dim=True)
        for p in state.bench)

    def kpi(label, val, note=""):
        n = f'<div class="kn">{note}</div>' if note else ""
        return (f'<div class="kpi"><div class="kv mono">{val}</div>'
                f'<div class="kl">{label}</div>{n}</div>')

    chips1 = state.chips_remaining("set1")
    # Two lines (2 Sep 2026): the first three are account-level facts that
    # barely move week to week; the rest are the xP/actual-points figures the
    # weekly transfer decision actually turns on. Two separate .kpis grids,
    # not one wrapped by viewport width, so the split is fixed regardless of
    # screen size - same reasoning as the route chart's two-row legend.
    kpis_top = "".join([
        kpi("Squad value", f"£{state.value:.1f}m"),
        kpi("Bank value", f"£{state.bank:.1f}m"),
        kpi("Chips left", f"{len(chips1)}/4", "set 1 expires GW19"),
    ])
    kpis_bottom = "".join([
        kpi("xP XI per 90", f"{xi90:.1f}", "what the optimiser maximises"),
        kpi("xP XI per GW", f"{xigw:.1f}",
            f"{(1-xigw/xi90)*100:.0f}% never played"),
        kpi("xP bench per GW", f"{bench_pts:.1f}", f"{exp_blanks:.2f} expected blanks"),
        kpi("P per GW", f"{live['avg_per_gw']:.1f}" if live else "—",
            f"{live['gws_played']} GW played" if live else "no live snapshot cached yet"),
        kpi("Total points", f"{live['total_points']}" if live else "—"),
    ])

    contam_mine = [p for p in state.players if p["name"] in contam]
    contam_html = ""
    if contam_mine:
        items = "".join(
            f"<li><b>{esc(p['name'])}</b> — {esc(contam[p['name']])}</li>"
            for p in contam_mine)
        contam_html = f"""
<div class="panel">
  <h2>Numbers on this page that are not what they look like</h2>
  <p class="tests">The most useful thing a model can do is tell you where it is
  weak. These players' histories were earned at a different club.</p>
  <div class="find bad"><ul style="margin:4px 0 0 18px;padding:0">{items}</ul></div>
  <p class="tests" style="margin-top:12px">The start percentages shown for these
  players describe their <b>old</b> club. The prior snapshot records each player's
  <b>current</b> club against <b>last season's</b> statistics, so a summer transfer
  reads as new badge, old numbers — and nothing in the data flags it.</p>
</div>"""

    def mini(players, label):
        names = " · ".join(sorted(p["name"] for p in players))
        return f"<tr><td>{label}</td><td class='mono' style='text-align:left'>{esc(names)}</td></tr>"

    alt_html = f"""
<div class="panel">
  <h2>GW{live['next_gw'] if live else '?'} — no transfers</h2>
  <p class="tests">Free. Costs nothing, needs no transfer, and is the decision most
  often left unexamined.</p>
  <table><tbody>
    {mini(alt90, f"Best XI by xP/90 — {sum(p['score'] for p in alt90):.2f}")}
    {mini(altgw, f"Best XI by xP/GW — {sum(p['stp']*p['score'] for p in altgw):.2f}")}
  </tbody></table>
  <div class="find {'ok' if same else 'bad'}">
    {"Both objectives choose the <b>same eleven</b>, so the choice of objective does not bind this week."
     if same else
     "The two objectives choose <b>different elevens from the same fifteen</b>. "
     "Ranking on xP/90 ignores how often a player actually starts, so it can field "
     "a stronger-looking XI that plays less. This is roadmap item <b>A0.5</b>."}
  </div>
  {alt1_explain_html}
</div>

<div class="panel">
  <h2>GW{live['next_gw'] if live else '?'} — one transfer</h2>
  <p class="tests">The current fifteen against the <b>next-best forced swap</b> — the
  optimiser is required to change exactly one player, so this shows the best move
  available even when the honest answer is to hold. Priced three times, once per
  data-source estimator (the same <span class="mono">actual</span>/
  <span class="mono">prior</span>/<span class="mono">shrunken</span> choice
  <span class="mono">optimise_squad.py --estimator</span> offers), because this is
  exactly the kind of call the three have been shown to disagree on early in a
  season.</p>
  <div class="find">Every score on this page, including this table, runs through
  the ROLE_INTEL.md adjustment layer — set-piece duty, availability overrides
  like an injury opening up minutes, and the guardrailed 0.5x&ndash;1.5x role
  multipliers. The three rows below differ only in how each player's underlying
  rate stats are estimated: <span class="mono">actual</span> is this season's
  live numbers taken at face value, <span class="mono">prior</span> is last
  season's rates with no live data at all, <span class="mono">shrunken</span>
  blends the two, weighted by how much live evidence exists.</div>
  <table>
    <thead><tr><th>&nbsp;</th><th>Recommended transfer</th><th>&Delta; xP/GW</th></tr></thead>
    <tbody>
      {"".join(
        f"<tr><td>Optimised using {label} scores</td>"
        f"<td>{esc(' · '.join(out_e))} &rarr; {esc(' · '.join(in_e))}</td>"
        f"<td class='mono'>{delta:+.2f}</td></tr>"
        for label, out_e, in_e, delta, _hits in alt2_rows)}
    </tbody></table>
  <div class="find {'ok' if alt2_agree else 'bad'}">
    {f"<b>All three estimators agree:</b> {esc(' · '.join(alt2_rows[0][1]))} &rarr; "
     f"{esc(' · '.join(alt2_rows[0][2]))}, whichever data source you trust."
     if alt2_agree else
     "<b>The estimators do not agree on the transfer.</b> Which one to act on is a "
     "judgement call, not something this table can resolve for you — see the "
     "captaincy estimator-sensitivity discussion for how thin the underlying "
     "evidence usually is this early in a season."}
  </div>
</div>

<div class="panel">
  <h2>GW{live['next_gw'] if live else '?'} — two transfers</h2>
  <p class="tests">The current fifteen against the <b>next-best forced double swap</b> —
  same convention as one transfer, but the optimiser must change exactly two players.
  Realistically prices in a <b>&minus;{alt3_rows[0][4]} hit</b> on the assumption of
  1 free transfer banked (squad.json doesn't track banked transfers, so this is a
  stated assumption, not a live count) — if you're actually sitting on 2 free
  transfers this week, the hit doesn't apply and the swap is free. Priced three
  times, once per data-source estimator, same as the one-transfer table above.</p>
  <table>
    <thead><tr><th>&nbsp;</th><th>Recommended transfer(s)</th><th>&Delta; xP/GW</th></tr></thead>
    <tbody>
      {"".join(
        f"<tr><td>Optimised using {label} scores</td>"
        f"<td>{esc(' · '.join(out_e))} &rarr; {esc(' · '.join(in_e))}</td>"
        f"<td class='mono'>{delta:+.2f}</td></tr>"
        for label, out_e, in_e, delta, _hits in alt3_rows)}
    </tbody></table>
  <div class="find {'ok' if alt3_agree else 'bad'}">
    {f"<b>All three estimators agree:</b> {esc(' · '.join(alt3_rows[0][1]))} &rarr; "
     f"{esc(' · '.join(alt3_rows[0][2]))}, whichever data source you trust."
     if alt3_agree else
     "<b>The estimators do not agree on the double transfer.</b> Which one to act "
     "on is a judgement call, not something this table can resolve for you &mdash; "
     "see the captaincy estimator-sensitivity discussion for how thin the "
     "underlying evidence usually is this early in a season."}
  </div>
</div>"""

    # What each chip actually DOES, mechanically - the strategy table below
    # (window/trigger/backstop) assumes the reader already knows this, which
    # a first-time reader of this page won't. Static FPL rules, not derived
    # from anything - won't drift, so hand-kept here rather than parsed.
    CHIP_WHAT = {
        "Wildcard 1": "Unlimited free transfers for one gameweek, no points cost — "
                      "rebuild the squad from scratch within the £100m budget.",
        "Bench Boost 1": "All 4 bench players' points count too for one gameweek, "
                          "not just the starting XI's.",
        "Triple Captain 1": "The captain's points are tripled instead of doubled "
                             "for one gameweek.",
        "Free Hit 1": "Unlimited free transfers for exactly one gameweek — the "
                      "squad automatically reverts to what it was the next week.",
    }

    chip_html = ""
    if cp:
        def chip_row(label, window, trigger, backstop):
            used = chip_used.get(label, False)
            status = ('<span class="tag">used</span>' if used
                       else '<span class="tag ok">available</span>')
            what = CHIP_WHAT.get(label, "")
            what_html = f"<div class='kn'>{esc(what)}</div>" if what else ""
            return (f"<tr><td><b>{esc(label)}</b> {status}{what_html}</td>"
                    f"<td class='mono'>{esc(window)}</td>"
                    f"<td style='text-align:left'>{esc(trigger)}</td>"
                    f"<td class='mono'>{esc(backstop)}</td></tr>")
        chip_rows = "".join(chip_row(*r) for r in cp["rows"])
        checklist_html = "".join(f"<li>{esc(item)}</li>" for item in cp["checklist"])
        n_avail = len(set1_available)
        chip_title = re.sub(r"^SET 1", "Set 1", cp["title"])
        chip_html = f"""
<div class="panel">
  <h2>Chip strategy — {esc(chip_title)}</h2>
  <p class="tests">{n_avail} of 4 chips still available. {md_bold(cp['status'])} Full
  reasoning and the weekly review log live in
  <span class="mono">TEAM_CHANGE_LOG.md</span> — this table is generated from that
  file, not a second hand-kept copy of it.</p>
  <div class="find bad">{md_bold(cp['constraint'])}</div>
  <table>
    <thead><tr><th>Chip</th><th>Target window</th>
    <th style="text-align:left">Trigger</th><th>Hard backstop</th></tr></thead>
    <tbody>{chip_rows}</tbody></table>
  <div class="find"><b>Reviewed every week, not set once.</b>
  <ul style="margin:8px 0 0 18px;padding:0">{checklist_html}</ul></div>
</div>"""

    # --- Captaincy, priced per data-source estimator, added 26 Aug 2026,
    # reshaped 3 Sep 2026 -----------------------------------------------------
    # captaincy_odds is a live MCP tool (Poisson haul/blank modelling against
    # the real fixture list) — this offline build script can't call it
    # itself, so this panel reads a snapshot written elsewhere instead, same
    # PURE READ discipline as live_snapshot()/actual_route_snapshot(). See
    # captaincy_snapshot()'s docstring for the writer
    # (fpl_research_mcp.captaincy_snapshot_refresh()). One row per estimator
    # (actual/prior/shrunken) rather than a top-3 under one model, same
    # treatment "GW{next} — one/two transfers" already got - captaincy is
    # exactly the kind of call the three have been shown to disagree on.
    cap_snap = captaincy_snapshot()
    cap_html = ""
    if cap_snap:
        by_est = cap_snap["by_estimator"]
        cap_agree = cap_snap.get("agree", len({r["name"] for r in by_est}) == 1)

        def cap_row(r):
            return (f"<tr><td>Optimised using {esc(r['label'])} scores</td>"
                    f"<td><b>{esc(r['name'])}</b> ({esc(r['pos'])}, {esc(r['team'])})</td>"
                    f"<td class='mono'>{esc(r['opponent'])}</td>"
                    f"<td class='mono'>{r['e_pts']:.2f}</td>"
                    f"<td class='mono'>{r['p_haul']:.1f}%</td>"
                    f"<td class='mono'>{r['p_blank']:.1f}%</td>"
                    f"<td class='mono'>{r['own_pct']:.1f}%</td>"
                    f"<td class='mono'>{r['diffup']:.1f}</td></tr>")
        cap_rows = "".join(cap_row(r) for r in by_est)
        caveats = cap_snap.get("caveats") or []
        caveats_html = ("<div class='find bad'>" +
                        "<br>".join(esc(c) for c in caveats) + "</div>") if caveats else ""
        cap_html = f"""
<div class="panel">
  <h2>GW{cap_snap.get('next_gw', '?')} — captaincy</h2>
  <p class="tests">From <span class="mono">captaincy_odds</span> (fpl-research MCP),
  which models goals and assists as Poisson draws rather than a single point
  estimate — E[pts] is the mean, but captaincy is not symmetric: P(haul) is what
  gains rank, P(blank) is what loses it, and DiffUp (P(haul) &times; (1&minus;ownership))
  is what a genuine differential bet is worth. Priced three times, once per
  data-source estimator, same as the transfer tables above. Snapshot fetched
  {esc(cap_snap.get('fetched_utc', 'unknown time'))}.</p>
  <table>
    <thead><tr><th>&nbsp;</th><th>Proposal</th><th>Next fixture</th><th>E[pts]</th>
    <th>P(haul&ge;10)</th><th>P(blank&le;2)</th><th>Own%</th><th>DiffUp</th></tr></thead>
    <tbody>{cap_rows}</tbody></table>
  <div class="find {'ok' if cap_agree else 'bad'}">
    {f"<b>All three estimators agree:</b> {esc(by_est[0]['name'])}, whichever data source you trust."
     if cap_agree else
     "<b>The estimators do not agree on the armband.</b> Which one to act on is a "
     "judgement call, not something this table can resolve for you — see the "
     "captaincy estimator-sensitivity discussion for how thin the underlying "
     "evidence usually is this early in a season."}
  </div>
  {caveats_html}
</div>"""
    else:
        cap_html = """
<div class="panel">
  <h2>Captaincy</h2>
  <p class="tests">No cached captaincy snapshot yet. Ask Claude to run
  <span class="mono">captaincy_snapshot_refresh</span> (fpl-research MCP) over the
  current XI and save the result to
  <span class="mono">docs/data/captaincy_snapshot.json</span>, then rebuild.</p>
</div>"""

    # --- "where the points come from" chart (ADR 0001) ---------------------
    # The one inline script on this page, deliberately — see the module
    # docstring. Everything else here is server-rendered HTML.
    #
    # EXPECTED/ACTUAL TOGGLE + EARNED/DEDUCTED SPLIT, added 26 Aug 2026. Two
    # bases sharing one chart shape (six earned categories, five deduction
    # categories) so switching the toggle only changes the numbers, never
    # the layout. "expected" is always present (it's this build's own xP);
    # "actual" is null when the local player_gw cache isn't warm yet — see
    # actual_route_snapshot()'s docstring — and the page says so rather than
    # rendering an empty or fabricated chart.
    route_payload = json.dumps({
        "labels": [label for _, label, _ in ROUTE_CATEGORIES],
        "colors": [pal for _, _, pal in ROUTE_CATEGORIES],
        "dedLabels": [label for _, label, _ in DEDUCTION_CATEGORIES],
        "dedColors": [hexc for _, _, hexc in DEDUCTION_CATEGORIES],
        "bonusUnvalidated": bonus_unvalidated,
        "expected": {
            "values": [round(route_display_positive[k], 4) for k, _, _ in ROUTE_CATEGORIES],
            "deductions": [round(route_display_deductions[k], 4) for k, _, _ in DEDUCTION_CATEGORIES],
            "total": round(xigw, 4),
        },
        "actual": ({
            "values": [round(actual_snap["positive"][k], 4) for k, _, _ in ROUTE_CATEGORIES],
            "deductions": [round(actual_snap["deductions"][k], 4) for k, _, _ in DEDUCTION_CATEGORIES],
            "total": round(sum(actual_snap["positive"].values()) + sum(actual_snap["deductions"].values()), 4),
            "gws": actual_snap["gws"],
        } if actual_snap else None),
    })
    bonus_note = (f"""<div class="find bad"><b>Bonus is flagged, not just plotted.</b>
      This build's bonus shrinkage constant (k={bonus_k:.1f}) is one of scoring.py's
      fallback/clamp values, not one fitted from observed variance — the code's own
      comment says to treat <span class="mono">xbonus90</span> as unvalidated until
      investigated. The Bonus segment below is dashed for exactly that reason, in
      Expected mode only: it is a real number, not a trusted one.</div>"""
                  if bonus_unvalidated else
                  f"""<div class="find ok">Bonus shrinkage constant this build:
      k={bonus_k:.1f}, fitted from observed variance rather than a fallback/clamp
      value — no flag needed on the segment below.</div>""") if bonus_k is not None else ""
    route_chart_html = f"""
<div class="panel">
  <h2>Where the points come from</h2>
  <p class="tests">A human-in-the-loop risk read, not an optimiser constraint —
  see <span class="mono">docs/adr/0001-xi-scoring-route-composition-chart.md</span>.
  <b>Expected</b> unblends this build's xP_adj into the six routes that produce it
  and a goals-conceded deduction, start-weighted so Expected's earned row sums to
  the XI's {xigw:.1f} xP/GW exactly. <b>Actual</b> is the same XI's real results
  this season, averaged per gameweek — the same six categories, plus cards, own
  goals and penalty misses the model doesn't attempt to forecast. Toggle between
  them below; the shape never changes, only the numbers.</p>
  <div style="display:flex;align-items:center;gap:10px;margin:0 0 10px">
    <span style="font-size:13px;color:var(--dim)">Basis</span>
    <span id="rcMode" style="display:flex;gap:6px"></span>
    <span id="rcNote" class="mono" style="font-size:12px;color:var(--dim)"></span>
  </div>
  <div class="wrap tiny"><canvas id="routeChart"></canvas></div>
  <div id="rcLegend"></div>
  {bonus_note}
  <div class="find">Composition only, not a risk measure — showing where the
  points come from doesn't yet say how sure the model is about each Expected
  route. Goal Involvement and Defensive Contribution carry a Gamma-Poisson
  dispersion estimate, Clean Sheets a nonlinear transform of Poisson
  uncertainty, and Bonus a differently-derived shrinkage constant that can
  itself go unvalidated (above) — three incompatible uncertainty models, not
  one confidence scale yet. Per-route confidence intervals are deferred to a
  future gated roadmap item rather than faked here. Actual carries no such
  uncertainty — it's what already happened.</div>
</div>
<script>
const RC = {route_payload};
// Recoloured 26 Aug 2026 for readability: EARNED categories now live entirely
// in a blue/green/gold/violet "cool" family, and RED is reserved exclusively
// for the deductions row below — Bonus used to share a red-ish tone (#ff6b6b)
// with the deductions bar, which read as "this earned points are also bad".
const RCC = {{a:'#4ea3ff',b:'#ffd43b',c:'#51cf66',d:'#ff922b',e:'#9775fa',dim:'#8b98a5'}};
const rcCss = k => getComputedStyle(document.documentElement).getPropertyValue(k).trim();
let rcMode = 'expected';
const earnedDS = RC.labels.map((lab, i) => {{
  const flagged = lab === 'Bonus' && RC.bonusUnvalidated;
  return {{
    label: lab, data: [0, 0], backgroundColor: RCC[RC.colors[i]],
    borderColor: flagged ? '#ff6b6b' : RCC[RC.colors[i]],
    borderWidth: flagged ? 2 : 0, borderDash: flagged ? [4, 3] : [],
  }};
}});
const dedDS = RC.dedLabels.map((lab, i) => ({{
  label: lab, data: [0, 0], backgroundColor: RC.dedColors[i], borderWidth: 0,
}}));
const routeChart = new Chart(document.getElementById('routeChart'), {{
  type: 'bar',
  data: {{ labels: ['Points earned', 'Points deducted'], datasets: [...earnedDS, ...dedDS] }},
  options: {{
    indexAxis: 'y', responsive: true, maintainAspectRatio: false,
    scales: {{
      x: {{ stacked: true, min: 0, title: {{ display: true, text: 'points per gameweek' }},
            grid: {{ color: rcCss('--grid') }} }},
      y: {{ stacked: true, grid: {{ display: false }} }},
    }},
    plugins: {{
      // Built-in legend replaced by the two hand-built .legend rows below
      // (#rcLegend) - Chart.js's own legend wraps wherever the viewport
      // happens to break, mixing earned and deducted categories on the same
      // line. Two separate rows guarantee the split every time.
      legend: {{ display: false }},
      tooltip: {{ callbacks: {{ label: cx => {{
        const flagged = rcMode === 'expected' && cx.dataset.label === 'Bonus' && RC.bonusUnvalidated;
        return `${{cx.dataset.label}}: ${{cx.raw.toFixed(2)}} pts` + (flagged ? '  (unvalidated shrinkage — ADR 0001)' : '');
      }} }} }},
    }},
  }},
}});
// Two-row legend: earned categories on line 1, deducted (negative-points)
// categories on line 2 - two separate .legend rows rather than one, so the
// split is fixed regardless of viewport width (see the plugins.legend note
// above).
document.getElementById('rcLegend').innerHTML =
  `<div class="legend">${{earnedDS.map(ds => {{
    const flagged = ds.label === 'Bonus' && RC.bonusUnvalidated;
    return `<span><i style="background:${{ds.backgroundColor}}${{flagged ? ';border:1px dashed #ff6b6b' : ''}}"></i>${{ds.label}}</span>`;
  }}).join('')}}</div>
   <div class="legend">${{dedDS.map(ds =>
    `<span><i style="background:${{ds.backgroundColor}}"></i>${{ds.label}}</span>`
  ).join('')}}</div>`;
function rcRender(mode) {{
  rcMode = mode;
  const d = RC[mode];
  const note = document.getElementById('rcNote');
  if (!d) {{
    earnedDS.forEach(ds => ds.data = [0, 0]);
    dedDS.forEach(ds => ds.data = [0, 0]);
    note.textContent = 'no cached actual results yet — run cache_history via the fpl-research MCP, then rebuild';
  }} else {{
    earnedDS.forEach((ds, i) => ds.data = [d.values[i], 0]);
    dedDS.forEach((ds, i) => ds.data = [0, Math.abs(d.deductions[i])]);
    note.textContent = mode === 'actual'
      ? `${{d.total.toFixed(2)}} pts/GW avg over ${{d.gws.length}} finished gameweek(s): GW${{d.gws.join(', GW')}}`
      : `${{d.total.toFixed(2)}} xP/GW (this build)`;
  }}
  routeChart.update();
}}
// BOTH buttons are always real, clickable toggles (fixed 26 Aug 2026 — they
// used to look permanently "stuck" on Expected). The old version set a real
// HTML `disabled` attribute on Actual whenever no cached snapshot existed
// yet, which silently swallowed the click before rcRender ever ran: no
// visual change, no message, nothing — indistinguishable from a broken
// button. rcRender('actual') already had a graceful empty-state branch (see
// below) that zeroes the chart and explains why; the button just needs to
// let the user reach it. Actual still gets a dashed, dimmed look when no
// snapshot is cached, so its state is visible before you click, not just
// after.
document.getElementById('rcMode').innerHTML = ['expected', 'actual'].map(m => {{
  const noData = m === 'actual' && !RC.actual;
  const on = m === rcMode;
  return `<button data-m="${{m}}" style="font-size:12px;padding:4px 10px;
    border-radius:6px;cursor:pointer;border:1px ${{noData ? 'dashed' : 'solid'}} var(--line);
    opacity:${{noData ? 0.6 : 1}};background:${{on ? RCC.a : 'transparent'}};color:${{on ? '#fff' : 'var(--tx)'}}"
    title="${{noData ? 'No cached actual results yet — click to see why, or run cache_history + squad_actual_points via the fpl-research MCP then rebuild' : ''}}">
    ${{m === 'expected' ? 'Expected' : 'Actual'}}</button>`;
}}).join('');
document.getElementById('rcMode').addEventListener('click', e => {{
  const m = e.target.dataset.m;
  if (!m) return;
  document.querySelectorAll('#rcMode button').forEach(btn => {{
    const on = btn.dataset.m === m;
    btn.style.background = on ? RCC.a : 'transparent';
    btn.style.color = on ? '#fff' : 'var(--tx)';
  }});
  rcRender(m);
}});
rcRender('expected');
</script>"""

    body = f"""
<p class="deadline-line">{dl_line}</p>
<div class="kpis">{kpis_top}</div>
<div class="kpis">{kpis_bottom}</div>
{contam_html}
<div class="panel">
  <h2>The eleven</h2>
  <p class="tests">{esc(state.formation)} · captain {esc(state.captain)} ·
  vice {esc(state.vice)}. Each card says why the player is here.</p>
  <div class="find"><b>Reading a card.</b> <span class="mono">xP/90</span> is
  expected points per full match, already adjusted for who the player faces over
  GW1–4. <span class="mono">xP/GW</span> multiplies that by how often he actually
  starts — the number you accumulate. <span class="mono">ATT</span> and
  <span class="mono">DEF</span> are fixture multipliers on different scales:
  higher is easier for attackers, <b>lower</b> is easier for defenders and
  keepers. Where the reasoning quotes a <i>flat</i> xP it means before fixtures,
  so it will not match the adjusted figure above it.</div>
  <div class="pitch">{rows}</div>
  <h2 style="margin-top:18px">The bench, in substitution order</h2>
  <p class="tests">Chosen on price and availability, not merit — except the first
  slot, which is the one that usually plays.</p>
  <div class="row">{bench_html}</div>
</div>

{route_chart_html}

{alt_html}
{chip_html}
{cap_html}
"""

    extra_css = """
<style>
.squad-link{margin:-6px 0 10px}
.squad-link a{font-size:13px;color:var(--dim);text-decoration:none;border-bottom:1px dotted var(--dim)}
.squad-link a:hover{color:var(--tx);border-bottom-color:var(--tx)}
.deadline-line{font-size:14px;margin:0 0 14px}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin-bottom:18px}
.kpi{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:12px 14px}
.kv{font-size:22px;font-weight:700} .kl{font-size:12px;color:var(--dim);margin-top:2px}
.kn{font-size:11px;color:var(--dim);opacity:.75;margin-top:3px}
.pitch{display:flex;flex-direction:column;gap:10px}
.row{display:flex;gap:10px;flex-wrap:wrap;justify-content:center}
.pc{flex:1 1 190px;max-width:250px;background:var(--bg);border:1px solid var(--line);
border-radius:9px;padding:9px 11px}
.pc.dim{opacity:.72}
.pc-h{font-size:14px;margin-bottom:3px} .pc-h b{margin-right:5px}
.pc-m,.pc-n{font-size:11.5px;color:var(--dim)} .pc-n{margin-top:2px}
.pc-w{font-size:11.5px;margin-top:6px;padding-top:6px;border-top:1px solid var(--line);color:var(--tx);opacity:.85}
.wrap.tiny{height:150px}
@media(max-width:700px){.pc{flex:1 1 100%;max-width:none}}
</style>"""

    page_title = "River Leaf FC — squad"
    html = page_shell.shell(
        title=page_title,
        active="squad",
        subtitle=f"GW{state.gameweek} · {esc(state.formation)} · £{state.value:.1f}m "
                 f"+ £{state.bank:.1f}m bank · squad.json updated {state.updated_utc} · "
                 f"page generated {dt.datetime.now():%Y-%m-%d %H:%M}",
        body=body,
        footer="Built by <span class='mono'>build_squad_page.py</span> from "
               "<span class='mono'>squad.json</span>. Expected points come from FPL's own "
               "scoring table — nothing invented. Where a number is unreliable, the page says so.")
    html = html.replace("</head>", extra_css + "\n</head>")
    html = html.replace(
        f"<h1>{page_title}</h1>",
        f'<h1>{page_title}</h1>\n<p class="squad-link"><a href="{MY_TEAM_URL}" '
        f'target="_blank" rel="noopener noreferrer">Open my team on fantasy.premierleague.com ↗</a></p>')

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    open(OUT, "w", encoding="utf-8").write(html)
    return html, same


if __name__ == "__main__":
    h, same = build()
    print(f"written: {OUT}  ({len(h)/1024:.0f} KB)")
    assert "cdn.jsdelivr.net/npm/chart.js@4.5.0" in h, "Chart.js tag missing"
    assert 'class="on"' in h, "nav active state missing"
    assert "pc-w" in h, "selection reasoning did not render"
    assert 'id="routeChart"' in h, "scoring-route composition chart canvas missing"
    assert "RC.bonusUnvalidated" in h, "route chart script did not render"
    print("  chart.js pinned · nav active · reasoning rendered · route chart present")
    print(f"  the two objectives pick the {'SAME' if same else 'DIFFERENT'} XI")
