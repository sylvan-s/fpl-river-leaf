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

HERE = os.path.dirname(os.path.abspath(__file__))


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
DEADLINE = dt.datetime(2026, 8, 21, 17, 30, tzinfo=dt.timezone.utc)


def esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


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
    bench_pts, bench_rows, blank_dist = sz.bench_value(declared_xi, declared_bench)
    exp_blanks = sum(j * q for j, q in enumerate(blank_dist))
    days = (DEADLINE - dt.datetime.now(dt.timezone.utc)).total_seconds() / 86400

    # --- alternatives -----------------------------------------------------
    alt90 = best_xi(mine, weight_by_start=False)
    altgw = best_xi(mine, weight_by_start=True)
    same = {p["name"] for p in alt90} == {p["name"] for p in altgw}

    res = opt.optimise_transfers(pool, state.name_set, state.bank, 1, allow_haaland=False)
    t_xi, t_bench, _ = res
    t_out = sorted(state.name_set - {p["name"] for p in t_xi + t_bench})
    t_in = sorted({p["name"] for p in t_xi + t_bench} - state.name_set)
    t_b, _r, _d = sz.bench_value(t_xi, t_bench)
    t_90 = sum(p["score"] for p in t_xi)
    t_gw = sum(p["stp"] * p["score"] for p in t_xi)

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
    kpis = "".join([
        kpi("Squad value", f"£{state.value:.1f}m", f"bank £{state.bank:.1f}m"),
        kpi("XI xP per 90", f"{xi90:.1f}", "what the optimiser maximises"),
        kpi("XI xP per gameweek", f"{xigw:.1f}",
            f"{(1-xigw/xi90)*100:.0f}% never played"),
        kpi("Bench value", f"{bench_pts:.1f}", f"{exp_blanks:.2f} expected blanks"),
        kpi("Chips left", f"{len(chips1)}/4", "set 1 expires GW19"),
        kpi("Deadline", f"{days:.0f}d", "GW1 · Fri 21 Aug 17:30 UTC"),
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
  <p class="tests">The current fifteen against the single best transfer away from
  it for the next gameweek — exactly one swap, everything else held fixed —
  priced on both objectives and with its knock-on effect on the bench.</p>
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
  <div class="find">Read the last column, not the first. Mixing an XI measured per 90
  with a bench measured per gameweek produced a confident, entirely false answer once
  already — the two must share a unit before they are added.</div>
</div>"""

    body = f"""
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

<div class="panel">
  <h2>Squad shape — the archetype each position is bought for</h2>
  <p class="tests">The qualitative read behind the xP formula: what a good pick
  looks like at each position, and the trap that number alone can hide.</p>
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
</div>

{alt_html}
"""

    extra_css = """
<style>
.archetype td,.archetype th{text-align:left;vertical-align:top;padding:8px 10px;border-bottom:1px solid var(--line)}
.archetype td:first-child,.archetype th:first-child{white-space:nowrap;width:48px}
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
@media(max-width:700px){.pc{flex:1 1 100%;max-width:none}}
</style>"""

    html = page_shell.shell(
        title="River Leaf FC — squad",
        active="squad",
        subtitle=f"GW{state.gameweek} · {esc(state.formation)} · £{state.value:.1f}m "
                 f"+ £{state.bank:.1f}m bank · squad.json updated {state.updated_utc} · "
                 f"page generated {dt.datetime.now():%Y-%m-%d %H:%M}",
        body=body,
        footer="Built by <span class='mono'>build_squad_page.py</span> from "
               "<span class='mono'>squad.json</span>. Expected points come from FPL's own "
               "scoring table — nothing invented. Where a number is unreliable, the page says so.")
    html = html.replace("</head>", extra_css + "\n</head>")

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    open(OUT, "w", encoding="utf-8").write(html)
    return html, same


if __name__ == "__main__":
    h, same = build()
    print(f"written: {OUT}  ({len(h)/1024:.0f} KB)")
    assert "cdn.jsdelivr.net/npm/chart.js@4.5.0" in h, "Chart.js tag missing"
    assert 'class="on"' in h, "nav active state missing"
    assert "pc-w" in h, "selection reasoning did not render"
    print("  chart.js pinned · nav active · reasoning rendered")
    print(f"  the two objectives pick the {'SAME' if same else 'DIFFERENT'} XI")
