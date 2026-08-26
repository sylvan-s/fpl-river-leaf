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

try:
    import pulp
except ImportError:
    raise SystemExit("PuLP not installed.  pip install pulp")

OUT = os.environ.get("FPL_SQUAD_OUT") or os.path.join(HERE, "docs", "index.html")
POS_ORDER = ["GKP", "DEF", "MID", "FWD"]
ENTRY = 1041614
LIVE_SNAPSHOT = os.path.join(HERE, "docs", "data", "entry_summary.json")
MY_TEAM_URL = "https://fantasy.premierleague.com/en/my-team"


def esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def md_bold(s):
    """`**text**` -> `<b>text</b>` for the short prose snippets pulled out of
    TEAM_CHANGE_LOG.md - that file is markdown, this page is not."""
    return re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", esc(s))


def _http_get(url):
    import httpx
    r = httpx.get(url, timeout=20, headers={"User-Agent": "fpl-river-leaf-dashboard/1.0"})
    r.raise_for_status()
    return r.json()


def live_snapshot(entry=ENTRY):
    """Actual FPL total points (cumulated for the squad) and the next real
    deadline, fetched live from the FPL API. Everything else on this page
    works fully offline from squad.json + the local pool files — this is the
    one panel that needs the network, so it fails soft: on any error it falls
    back to the last successful fetch cached at LIVE_SNAPSHOT, marked stale,
    rather than taking the whole page down. Same "NEEDS NETWORK, cache what
    you last got" pattern as build_prediction_tracker.py."""
    try:
        boot = _http_get("https://fantasy.premierleague.com/api/bootstrap-static/")
        hist = _http_get(f"https://fantasy.premierleague.com/api/entry/{entry}/history/")
        current = hist.get("current", [])
        total_points = current[-1]["total_points"] if current else 0
        gws_played = len(current)
        deadline_event = (next((e for e in boot["events"] if e.get("is_next")), None)
                           or next((e for e in boot["events"] if e.get("is_current")), None))
        snap = {
            "total_points": total_points,
            "gws_played": gws_played,
            "avg_per_gw": round(total_points / gws_played, 1) if gws_played else 0.0,
            "next_gw": deadline_event["id"] if deadline_event else None,
            "next_deadline_utc": deadline_event["deadline_time"] if deadline_event else None,
            "fetched_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
            "stale": False,
        }
        os.makedirs(os.path.dirname(LIVE_SNAPSHOT), exist_ok=True)
        json.dump(snap, open(LIVE_SNAPSHOT, "w", encoding="utf-8"), indent=2)
        return snap
    except Exception:
        if os.path.exists(LIVE_SNAPSHOT):
            snap = json.load(open(LIVE_SNAPSHOT, encoding="utf-8"))
            snap["stale"] = True
            return snap
        return None


def deadline_line(live):
    """Bold banner above the stat boxes: when the next team-choice lockdown
    actually is, in place of the old static 'Deadline' stat box (which went
    stale the moment GW1's deadline passed)."""
    if not live or not live.get("next_deadline_utc"):
        return ("<b>Next deadline unknown</b> — live fetch failed and no cached "
                "snapshot exists yet. Run this build with network access once "
                f"to populate {os.path.relpath(LIVE_SNAPSHOT, HERE)}.")
    d = dt.datetime.fromisoformat(live["next_deadline_utc"].replace("Z", "+00:00"))
    now = dt.datetime.now(dt.timezone.utc)
    remaining = d - now
    if remaining.total_seconds() > 0:
        away = f"{remaining.days}d {remaining.seconds // 3600}h away"
    else:
        away = "deadline has passed"
    stale = (' <span class="tag bad">cached — live fetch failed, showing the '
              f'last successful pull ({live["fetched_utc"]})</span>'
              if live.get("stale") else "")
    return (f"<b>Next team-choice lockdown: Gameweek {live['next_gw']} — "
            f"{d:%a %d %b %Y, %H:%M} UTC ({away})</b>{stale}")


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
    for p in declared_xi:
        terms = scoring.expected_points_scaled_breakdown(
            p, p["att_x"], p["def_x"], scale_workload=fa.SCALE_WORKLOAD,
            empirical=bs.USE_EMPIRICAL_DC)
        for k in route_totals:
            route_totals[k] += p["stp"] * terms[k]
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

    bench_pts, bench_rows, blank_dist = sz.bench_value(declared_xi, declared_bench)
    exp_blanks = sum(j * q for j, q in enumerate(blank_dist))
    live = live_snapshot()
    dl_line = deadline_line(live)

    # --- alternatives -----------------------------------------------------
    alt90 = best_xi(mine, weight_by_start=False)
    altgw = best_xi(mine, weight_by_start=True)
    same = {p["name"] for p in alt90} == {p["name"] for p in altgw}

    # force=True: always return the best SINGLE swap, even if its impact is
    # small or negative, rather than letting the solver hand back the current
    # squad unchanged. The table should show "what's the next-best move if
    # you had to make one", not silently collapse to nothing - the actual
    # hold-vs-transfer call is made separately below via MIN_GAIN, and stated
    # explicitly in its own recommendation line rather than implied by a
    # blank row.
    res = opt.optimise_transfers(pool, state.name_set, state.bank, 1,
                                  allow_haaland=False, force=True)
    t_xi, t_bench, _ = res
    t_out = sorted(state.name_set - {p["name"] for p in t_xi + t_bench})
    t_in = sorted({p["name"] for p in t_xi + t_bench} - state.name_set)
    t_b, _r, _d = sz.bench_value(t_xi, t_bench)
    t_90 = sum(p["score"] for p in t_xi)
    t_gw = sum(p["stp"] * p["score"] for p in t_xi)
    # Same threshold optimise_squad.py's CLI uses (transfer_mode()'s
    # MIN_GAIN) - a swap worth less than this on XI xP/90 is noise, not a
    # recommendation, however clean the arithmetic looks in the table above it.
    MIN_GAIN = 0.01
    t_gain = t_90 - xi90
    t_hold = t_gain < MIN_GAIN

    # --- the no-Haaland preference, repriced on every run -------------------
    # TEAM_CHANGE_LOG.md's "STANDING PREFERENCES" section carries the dated
    # decision (confirmed 9 Aug 2026, cost 0.06 xP/90 then) and the trigger to
    # revisit it (cost above ~0.30 xP/90). This block does not read that file -
    # it recomputes the cost live, on the same intel+fixture-adjusted pool the
    # rest of this page uses, so the number on the page can never go stale
    # relative to the number that decision was actually made on.
    h_noH_xi, h_noH_bench, _ = opt.optimise(pool, allow_haaland=False)
    h_H_xi, h_H_bench, _ = opt.optimise(pool, allow_haaland=True)
    h_noH_90 = sum(p["score"] for p in h_noH_xi)
    h_H_90 = sum(p["score"] for p in h_H_xi)
    h_cost = h_H_90 - h_noH_90
    h_picked = "Haaland" in {p["name"] for p in h_H_xi + h_H_bench}

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
    total_pts_note = (f"{live['avg_per_gw']:.1f} avg/GW · {live['gws_played']} GW played"
                       if live else "live fetch unavailable")
    kpis = "".join([
        kpi("Squad value", f"£{state.value:.1f}m", f"bank £{state.bank:.1f}m"),
        kpi("XI xP per 90", f"{xi90:.1f}", "what the optimiser maximises"),
        kpi("XI xP per gameweek", f"{xigw:.1f}",
            f"{(1-xigw/xi90)*100:.0f}% never played"),
        kpi("Bench value", f"{bench_pts:.1f}", f"{exp_blanks:.2f} expected blanks"),
        kpi("Chips left", f"{len(chips1)}/4", "set 1 expires GW19"),
        kpi("Total points", f"{live['total_points']}" if live else "—", total_pts_note),
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
  <h2>Alternative 1 — same fifteen, different eleven</h2>
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
</div>

<div class="panel">
  <h2>Alternative 2 — one transfer</h2>
  <p class="tests">The current fifteen against the <b>next-best forced swap</b> — the
  optimiser is required to change exactly one player, so this shows the best move
  available even when the honest answer is to hold, priced on both objectives and
  with its knock-on effect on the bench. The recommendation below the table, not
  this row, is where "hold" actually gets said.</p>
  <div class="find">Every score on this page, including this table, runs through
  the ROLE_INTEL.md adjustment layer — set-piece duty, availability overrides
  like an injury opening up minutes, and the guardrailed 0.5x&ndash;1.5x role
  multipliers — and through shrinkage on each player's observed rate stats,
  which blends a small early-season sample toward a positional baseline rather
  than trusting a handful of matches at face value. Both exist so this table
  can't recommend selling a player for a reason the model already has better
  information about, like an injury to the man ahead of him.</div>
  <table>
    <thead><tr><th>&nbsp;</th><th>XI xP/90</th><th>XI xP/GW</th><th>Bench</th><th>Total /GW</th></tr></thead>
    <tbody>
      <tr><td>Current</td><td class="mono">{xi90:.2f}</td><td class="mono">{xigw:.2f}</td>
          <td class="mono">{bench_pts:.2f}</td><td class="mono">{xigw+bench_pts:.2f}</td></tr>
      <tr><td>{esc(' · '.join(t_out))} → {esc(' · '.join(t_in))}</td>
          <td class="mono">{t_90:.2f}</td><td class="mono">{t_gw:.2f}</td>
          <td class="mono">{t_b:.2f}</td><td class="mono">{t_gw+t_b:.2f}</td></tr>
      <tr><td><b>Change</b></td><td class="mono">{t_90-xi90:+.2f}</td>
          <td class="mono">{t_gw-xigw:+.2f}</td><td class="mono">{t_b-bench_pts:+.2f}</td>
          <td class="mono"><b>{(t_gw+t_b)-(xigw+bench_pts):+.2f}</b></td></tr>
    </tbody></table>
  <div class="find {'ok' if t_hold else 'bad'}">
    <b>Recommendation: {'HOLD' if t_hold else 'transfer'}.</b>
    {f"The best available swap ({esc(' · '.join(t_out))} &rarr; {esc(' · '.join(t_in))}) "
     f"moves XI xP/90 by {t_gain:+.2f} &mdash; under the {MIN_GAIN:.2f} xP/90 noise floor, "
     f"so it is not a real edge, just the least-bad forced move. Keep the fifteen as is."
     if t_hold else
     f"{esc(' · '.join(t_out))} &rarr; {esc(' · '.join(t_in))} clears the {MIN_GAIN:.2f} "
     f"xP/90 noise floor by {t_gain:+.2f}. Worth making, hit cost permitting."}
  </div>
  <div class="find">Read the last column, not the first. Mixing an XI measured per 90
  with a bench measured per gameweek produced a confident, entirely false answer once
  already — the two must share a unit before they are added.</div>
</div>"""

    chip_html = ""
    if cp:
        def chip_row(label, window, trigger, backstop):
            used = chip_used.get(label, False)
            status = ('<span class="tag">used</span>' if used
                       else '<span class="tag ok">available</span>')
            return (f"<tr><td><b>{esc(label)}</b> {status}</td>"
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

    # --- "where the points come from" chart (ADR 0001) ---------------------
    # The one inline script on this page, deliberately — see the module
    # docstring. Everything else here is server-rendered HTML.
    route_payload = json.dumps({
        "labels": [label for _, label, _ in ROUTE_CATEGORIES],
        "values": [round(route_totals[k], 4) for k, _, _ in ROUTE_CATEGORIES],
        "colors": [pal for _, _, pal in ROUTE_CATEGORIES],
        "bonusUnvalidated": bonus_unvalidated,
        "total": round(xigw, 4),
    })
    bonus_note = (f"""<div class="find bad"><b>Bonus is flagged, not just plotted.</b>
      This build's bonus shrinkage constant (k={bonus_k:.1f}) is one of scoring.py's
      fallback/clamp values, not one fitted from observed variance — the code's own
      comment says to treat <span class="mono">xbonus90</span> as unvalidated until
      investigated. The Bonus segment below is dashed for exactly that reason: it is
      a real number, not a trusted one.</div>"""
                  if bonus_unvalidated else
                  f"""<div class="find ok">Bonus shrinkage constant this build:
      k={bonus_k:.1f}, fitted from observed variance rather than a fallback/clamp
      value — no flag needed on the segment below.</div>""") if bonus_k is not None else ""
    route_chart_html = f"""
<div class="panel">
  <h2>Where the points come from</h2>
  <p class="tests">A human-in-the-loop risk read, not an optimiser constraint —
  see <span class="mono">docs/adr/0001-xi-scoring-route-composition-chart.md</span>.
  <span class="mono">xP_adj</span> blends goals, assists, clean sheets, defensive
  actions and bonus into one number per player; this unblends the XI's
  {xigw:.1f} xP/GW back into the six routes that produce it, start-weighted the
  same way, so the segments below sum to that figure exactly.</p>
  <div class="wrap tiny"><canvas id="routeChart"></canvas></div>
  {bonus_note}
  <div class="find">Composition only, not a risk measure — showing where the
  points come from doesn't yet say how sure the model is about each route.
  Goal Involvement and Defensive Contribution carry a Gamma-Poisson dispersion
  estimate, Clean Sheets a nonlinear transform of Poisson uncertainty, and
  Bonus a differently-derived shrinkage constant that can itself go unvalidated
  (above) — three incompatible uncertainty models, not one confidence scale
  yet. Per-route confidence intervals are deferred to a future gated roadmap
  item rather than faked here.</div>
</div>
<script>
const RC = {route_payload};
const RCC = {{a:'#4ea3ff',b:'#ffc857',c:'#5fd38d',d:'#ff6b6b',e:'#c792ea',dim:'#8b98a5'}};
const rcCss = k => getComputedStyle(document.documentElement).getPropertyValue(k).trim();
new Chart(document.getElementById('routeChart'), {{
  type: 'bar',
  data: {{
    labels: ['XI, this gameweek'],
    datasets: RC.labels.map((lab, i) => {{
      const flagged = lab === 'Bonus' && RC.bonusUnvalidated;
      return {{
        label: lab, data: [RC.values[i]], backgroundColor: RCC[RC.colors[i]],
        borderColor: flagged ? '#ff6b6b' : RCC[RC.colors[i]],
        borderWidth: flagged ? 2 : 0, borderDash: flagged ? [4, 3] : [],
      }};
    }}),
  }},
  options: {{
    indexAxis: 'y', responsive: true, maintainAspectRatio: false,
    scales: {{
      x: {{ stacked: true, min: 0, title: {{ display: true, text: 'xP per gameweek' }},
            grid: {{ color: rcCss('--grid') }} }},
      y: {{ stacked: true, grid: {{ display: false }} }},
    }},
    plugins: {{
      legend: {{ position: 'bottom' }},
      tooltip: {{ callbacks: {{ label: cx =>
        `${{cx.dataset.label}}: ${{cx.raw.toFixed(2)}} xP` +
        (cx.dataset.label === 'Bonus' && RC.bonusUnvalidated
          ? '  (unvalidated shrinkage — ADR 0001)' : '') }} }},
    }},
  }},
}});
</script>"""

    body = f"""
<p class="deadline-line">{dl_line}</p>
<div class="kpis">{kpis}</div>
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

<div class="panel">
  <h2>Squad shape — the archetype each position is bought for</h2>
  <p class="tests">The qualitative read behind the xP formula: what a good pick
  looks like at each position, and the trap that number alone can hide.</p>
  <div class="find {'ok' if h_cost < 0.30 else 'bad'}">
    <b>This squad is built without Haaland — a standing, confirmed preference,
    not an oversight.</b> Repriced on every build against the unconstrained
    optimum (same intel+fixture-adjusted pool as the rest of this page):
    <table style="margin:8px 0">
      <tbody>
        <tr><td>Unconstrained optimum{' (Haaland IS in it)' if h_picked else ' (solver leaves him out anyway)'}</td>
            <td class="mono">{h_H_90:.2f} xP/90</td></tr>
        <tr><td>With the no-Haaland preference held</td>
            <td class="mono">{h_noH_90:.2f} xP/90</td></tr>
        <tr><td><b>Cost of the preference</b></td>
            <td class="mono"><b>{h_cost:+.2f}</b></td></tr>
      </tbody>
    </table>
    {"Well inside model error &mdash; effectively free. &pound;15.5m on Haaland buys "
     "almost exactly what the budget it frees up buys spread across the rest of the "
     "squad instead." if h_cost < 0.30 else
     "This has drifted past the ~0.30 xP/90 trigger TEAM_CHANGE_LOG.md set for "
     "revisiting the preference &mdash; worth an explicit re-check, not a silent hold."}
  </div>
  <table class="archetype">
    <thead><tr><th>Pos</th><th>Buy for</th><th>The trap</th></tr></thead>
    <tbody>
      <tr><td><b>GK</b></td>
        <td>Undisputed #1 first — everything else is void if he's benched.
        Then low season xGC and save volume, a distant second.</td>
        <td>Strong save stats on a keeper one bad week from losing the
        gloves. Starts is the gate for a reason.</td></tr>
      <tr><td><b>DEF</b></td>
        <td><b>Both</b> legs at once — a side with genuinely low xGC / a real
        clean sheet record, <b>and</b> the player's own CBIT clearing the
        10+ per-match threshold reliably (his real hit-rate, not a season
        average sitting near the line).</td>
        <td>Either leg alone. A great individual defender on a leaky side
        rarely banks the clean sheet. High CBIT on a leaky side is often a
        player under siege, not a good defender.</td></tr>
      <tr><td><b>MID</b></td>
        <td>Attacking output first (xGI/90 — a goal pays 5, an assist 3,
        near forward money) <b>plus</b> the clean sheet sitting on top for
        free if his side is tight at the back too.</td>
        <td>A rarer, lower-reliability route exists — a genuinely defensive
        midfielder clearing 12+ CBIRT — but it's not worth building a pick
        around.</td></tr>
      <tr><td><b>FWD</b></td>
        <td>Pure goals + assists + minutes. No clean sheet credit, and no
        real defensive-contribution route either.</td>
        <td>Reading a forward's CBIT/90 as if it predicts anything — 2025/26
        data shows forwards essentially never clear 10+ CBIT in a match
        (0% hit-rate across every matched forward in the pool), so there's
        no variance left to explain.</td></tr>
    </tbody>
  </table>
  <div class="find">
    <b>What holding the no-Haaland preference actually requires — it is not free
    to execute, even though it is priced as near-free above.</b>
    <ul style="margin:8px 0 0 18px;padding:0">
      <li><b>Captaincy has to be reviewed every week, not set once.</b> A
      Haaland squad has a standing captain and the decision is mostly "anyone
      beating him this week"; without a nailed 75%-owned explosive premium,
      the armband goes to whoever's fixture and form line up that gameweek —
      see <span class="mono">captaincy_odds</span> and the escalation check
      each week, not a default name.</li>
      <li><b>Triple Captain is structurally weaker.</b> TEAM_CHANGE_LOG.md
      already flags this: most managers triple the nailed premium; the
      realistic targets here (Thiago, B.Fernandes) are good, not explosive.
      TC is purely a P(haul) maximisation, so this preference caps its
      ceiling — a real cost the table above does not capture in xP/90 terms.</li>
      <li><b>The budget freed up buys flexibility, not just depth.</b> No
      single £15.5m anchor means more of the squad can turn over as form and
      fixtures shift, and a genuinely emerging player (a breakout midfielder,
      a new-signing forward finding his feet) can be worked in without first
      funding him by selling a name that's still producing. A Haaland squad
      effectively locks 15%+ of budget for the season; this one doesn't lock
      any of it.</li>
      <li><b>The trade-off is real, not just upside.</b> Spreading value across
      the XI raises the floor and lowers variance — fewer explosive weeks, fewer
      disaster weeks. Whether that trade is right depends on where in the mini-league
      table this squad needs to be climbing from; it is a strategy choice, not a
      free lunch the model found.</li>
    </ul>
  </div>
</div>

{alt_html}
{chip_html}
"""

    extra_css = """
<style>
.archetype td,.archetype th{text-align:left;vertical-align:top;padding:8px 10px;border-bottom:1px solid var(--line)}
.archetype td:first-child,.archetype th:first-child{white-space:nowrap;width:48px}
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
