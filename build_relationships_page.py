#!/usr/bin/env python3
"""Build the statistical relationships page — docs/relationships.html.

    python3 build_relationships_page.py

WHAT LIVES HERE. Two panels moved off Player analysis on 11 Aug 2026: the
threshold cliff (does a season CBIT average predict actually clearing the
line, match to match) and shrinkage (is k derived from real variance, or
quietly defaulted). Both are diagnostics about the SHAPE of a relationship in
the data rather than a read on any one player or transfer decision — which is
what earned them their own page instead of sitting among the squad-facing
panels on analysis.html.

REUSES build_dashboard.py's payload RATHER THAN RECOMPUTING IT. Both panels
need the same player pool, the same CBIT hit-rate archive match, and the same
shrinkage diagnostics analysis.html already computes. A second implementation
of that pipeline would drift from the first the moment either one changed —
exactly the failure class this project keeps a standing warning about (see
squad.json's provenance note). So this file imports build_dashboard.py as a
module and reads its `payload` global directly, the same pattern
optimise_squad.py already uses for build_squad.py.

SIDE EFFECT, ACCEPTED DELIBERATELY. Importing build_dashboard.py runs its
whole top-level script, which also (re)writes FPL_DIAGNOSTICS.html. Running
this file standalone therefore rebuilds the diagnostics source too. That is
harmless — the two pages must always agree on this data, so keeping them
inseparable at build time is a feature, not a leak.
"""
import importlib.util, json, os, datetime as dt

HERE = os.path.dirname(os.path.abspath(__file__))


def _load(mod, fn):
    spec = importlib.util.spec_from_file_location(mod, os.path.join(HERE, fn))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


page_shell = _load("page_shell", "page_shell.py")
bd = _load("bd_for_relationships", "build_dashboard.py")   # runs build_dashboard.py; see docstring
SL = _load("stats_lite", "stats_lite.py")
OUT = os.environ.get("FPL_RELATIONSHIPS_OUT") or os.path.join(HERE, "docs", "relationships.html")

DATA = bd.payload

# ---------------------------------------------------------------------------
# Panels 7 & 8, added 25 Aug 2026 from a chat analysis session: does the
# weekly-points distribution differ by position, and how would the CURRENT
# squad's exact XI/bench/captain have scored across all of last season.
#
# BOTH READ docs/data/ AND squad.json LIVE, EVERY BUILD - nothing here is a
# pasted-in number from the chat session. squad.json changes the moment a
# transfer is actioned, and this page must never go stale relative to it -
# same "fetch, don't vendor" discipline fetch_gw_history.py already states
# for the archive itself.
# ---------------------------------------------------------------------------

PDIR = os.path.join(HERE, "docs", "data", "players")
_INDEX = json.load(open(os.path.join(HERE, "docs", "data", "index.json"), encoding="utf-8"))
_SLUG_BY_KEY = {(r["name"], r["team"]): r["slug"] for r in _INDEX}
_POS_BY_SLUG = {r["slug"]: r["pos"] for r in _INDEX}

# Panel 4, added 2 Sep 2026. historical_backtest_2025_26.py's one-off replay
# of build_prediction_tracker.walk_forward() across the full completed
# 2025/26 season - a frozen historical result (both seasons are finished),
# never rebuilt by this page's own pipeline, just read like any other static
# input. Tolerant of a missing file, same as every other optional panel here.
try:
    BACKTEST = json.load(open(os.path.join(HERE, "historical_backtest_2025_26.json"),
                              encoding="utf-8"))
except FileNotFoundError:
    BACKTEST = None


def _player_gw(slug):
    """{round: [minutes, points]} for one player, DGW fixtures summed into
    their round. None if the slug has no archive file (unmatched player)."""
    path = os.path.join(PDIR, f"{slug}.json")
    if not os.path.exists(path):
        return None
    d = json.load(open(path, encoding="utf-8"))
    by_round = {}
    for r in d["gw"]:
        rnd = int(r["round"])
        mins = int(r.get("minutes") or 0)
        pts = int(r.get("total_points") or 0)
        if rnd in by_round:
            by_round[rnd][0] += mins
            by_round[rnd][1] += pts
        else:
            by_round[rnd] = [mins, pts]
    return by_round


def _position_pools(min_season_points=150):
    """Pooled per-gameweek POINTS (not minutes) for every 2025/26 player
    whose season total beat min_season_points, split by position."""
    pools = {"GKP": [], "DEF": [], "MID": [], "FWD": []}
    qualifiers = {"GKP": [], "DEF": [], "MID": [], "FWD": []}
    for r in _INDEX:
        gw = _player_gw(r["slug"])
        if not gw:
            continue
        total = sum(pts for _, pts in gw.values())
        if total <= min_season_points:
            continue
        pos = r["pos"]
        if pos not in pools:
            continue
        pools[pos].extend(pts for _, pts in gw.values())
        qualifiers[pos].append({"name": r["name"], "team": r["team"], "total": total})
    return pools, qualifiers


def _position_stats(pools):
    """Kruskal-Wallis omnibus over DEF/MID/FWD, then Mann-Whitney U and KS
    pairwise with Bonferroni correction (x3). GKP excluded - too few 150+
    qualifiers most seasons for the tests to mean anything."""
    groups = {p: pools[p] for p in ("DEF", "MID", "FWD") if pools[p]}
    if len(groups) < 3:
        return None
    order = ["DEF", "MID", "FWD"]
    H, kw_p = SL.kruskal_wallis([groups[p] for p in order])
    pairs = [("DEF", "MID"), ("DEF", "FWD"), ("MID", "FWD")]
    mwu, ks = [], []
    mwu_p_raw, ks_p_raw = [], []
    for a, b in pairs:
        U, p = SL.mannwhitney_u(groups[a], groups[b])
        mwu.append({"a": a, "b": b, "stat": U, "p": p})
        mwu_p_raw.append(p)
        D, p = SL.ks_2samp(groups[a], groups[b])
        ks.append({"a": a, "b": b, "stat": D, "p": p})
        ks_p_raw.append(p)
    mwu_corr = SL.bonferroni(mwu_p_raw)
    ks_corr = SL.bonferroni(ks_p_raw)
    for row, pc in zip(mwu, mwu_corr):
        row["p_bonf"] = pc
    for row, pc in zip(ks, ks_corr):
        row["p_bonf"] = pc
    return {"H": H, "kw_p": kw_p, "mwu": mwu, "ks": ks,
            "n": {p: len(groups[p]) for p in order}}


def _squad_replay():
    """Replay the CURRENT squad.json XI/bench/captain over every 2025/26
    gameweek using each player's REAL points that season, applying autosubs
    on 0 minutes (bench priority order, formation-legal only) and passing
    the armband to vice if captain blanks. Returns per-GW scores plus which
    squad members had no matching archive record (reported, not hidden)."""
    squad = json.load(open(os.path.join(HERE, "squad.json"), encoding="utf-8"))
    captain, vice = squad["captain"], squad["vice"]
    starters = [p for p in squad["squad"] if p["role"] == "XI"]
    bench = sorted((p for p in squad["squad"] if p["role"] == "BENCH"),
                    key=lambda p: (p["bench_order"] if p["bench_order"] is not None else 99))
    bench_gk = next((p for p in bench if p["pos"] == "GKP"), None)
    bench_out = [p for p in bench if p["pos"] != "GKP"]

    def gw(p):
        slug = _SLUG_BY_KEY.get((p["name"], p["team"]))
        return _player_gw(slug) if slug else None

    starter_gw = {p["name"]: gw(p) for p in starters}
    bench_gk_gw = gw(bench_gk) if bench_gk else None
    bench_out_gw = [(p["name"], p["pos"], gw(p)) for p in bench_out]
    missing = [p["name"] for p in starters + bench
               if (starter_gw.get(p["name"]) if p["role"] == "XI" else
                   (bench_gk_gw if p is bench_gk else
                    next((g for n, _, g in bench_out_gw if n == p["name"]), None))) is None]

    def formation_ok(c):
        return c["GKP"] == 1 and 3 <= c["DEF"] <= 5 and 2 <= c["MID"] <= 5 and 1 <= c["FWD"] <= 3

    scores = []
    for rnd in range(1, 39):
        lineup = {}
        for p in starters:
            g = starter_gw.get(p["name"]) or {}
            mins, pts = g.get(rnd, [0, 0])
            lineup[p["name"]] = {"pos": p["pos"], "pts": pts, "mins": mins}
        counts = {"GKP": 0, "DEF": 0, "MID": 0, "FWD": 0}
        for v in lineup.values():
            counts[v["pos"]] += 1

        gk_name = next((p["name"] for p in starters if p["pos"] == "GKP"), None)
        if gk_name and lineup[gk_name]["mins"] == 0 and bench_gk_gw:
            gm, gp = bench_gk_gw.get(rnd, [0, 0])
            if gm > 0:
                lineup[gk_name] = {"pos": "GKP", "pts": gp, "mins": gm}

        for rname, rpos, rgw in bench_out_gw:
            rm, rp = (rgw or {}).get(rnd, [0, 0])
            if rm == 0:
                continue
            candidate = None
            for name, v in lineup.items():
                if v["mins"] == 0 and not v.get("_filled"):
                    trial = dict(counts)
                    trial[v["pos"]] -= 1
                    trial[rpos] += 1
                    if formation_ok(trial):
                        candidate = name
                        break
            if candidate:
                counts[lineup[candidate]["pos"]] -= 1
                counts[rpos] += 1
                lineup[candidate] = {"pos": rpos, "pts": rp, "mins": rm, "_filled": True}

        cap_name = captain
        if lineup.get(captain, {}).get("mins", 0) == 0:
            cap_name = vice if lineup.get(vice, {}).get("mins", 0) > 0 else None

        total = sum(v["pts"] for v in lineup.values())
        if cap_name:
            total += lineup[cap_name]["pts"]
        scores.append(total)

    bins = [0] * 18  # 0-4, 5-9, ..., 85-89
    for s in scores:
        bins[min(17, max(0, s) // 5)] += 1
    n = len(scores)
    mean = sum(scores) / n
    variance = sum((s - mean) ** 2 for s in scores) / (n - 1)
    sd = variance ** 0.5
    srt = sorted(scores)
    median = srt[n // 2] if n % 2 else (srt[n // 2 - 1] + srt[n // 2]) / 2
    return {
        "scores": scores, "bins": bins, "missing": missing,
        "mean": mean, "median": median, "sd": sd,
        "min": min(scores), "max": max(scores),
        "captain": captain, "vice": vice, "formation": squad.get("formation"),
        "squad_gw": squad.get("gameweek"), "squad_updated": squad.get("updated_utc"),
    }


_POOLS, _QUALIFIERS = _position_pools(150)
DATA["posdist"] = {"pools": _POOLS, "qualifiers": _QUALIFIERS,
                    "stats": _position_stats(_POOLS)}
DATA["squad_replay"] = _squad_replay()


_PAL = dict(a='#4ea3ff', b='#ffc857', c='#5fd38d', dim='#8b98a5')  # mirrors JS const C below


def _backtest_panel():
    """Panel 4: historical_backtest_2025_26.py's per-gameweek RMSE trajectory
    (raw/prior/shrunk) plus the actual per-90 value, for the four metrics
    that have a real 2024/25 prior, with a position filter (all positions
    pooled, or one of POSITION_FILTERS' breakdowns - just FWD so far, since
    that is what was asked; add more the same way if wanted). Built as its
    own function, not inline in build(), so the f-string brace-doubling for
    the JS below stays isolated from the rest of the script. Returns '' if
    the backtest file is missing - same tolerant pattern as every other
    optional panel on this page."""
    if not BACKTEST:
        return ""
    all_keys = [k for k in ("xg90", "xa90", "xgc90", "sv90") if k in BACKTEST["trajectory"]]
    labels = {k: BACKTEST["metric_labels"].get(k, k) for k in all_keys}
    corr = BACKTEST.get("deviation_corr", {})

    # {"all": {trajectory: {...}, corr: {...}, n: null}, "FWD": {...}, ...}
    by_pos = {"all": dict(
        label="All positions", n=None,
        trajectory={k: BACKTEST["trajectory"][k] for k in all_keys},
        corr={k: corr.get(k) for k in all_keys + ["stp"]},
    )}
    for pos_label, d in (BACKTEST.get("by_position") or {}).items():
        pos_keys = [k for k in all_keys if k in d["trajectory"]]
        pos_corr = d.get("deviation_corr", {})
        by_pos[pos_label] = dict(
            label=f"{pos_label} only", n=d.get("n_players"),
            trajectory={k: d["trajectory"][k] for k in pos_keys},
            corr={k: pos_corr.get(k) for k in pos_keys},
        )

    a, b, c, dim = _PAL["a"], _PAL["b"], _PAL["c"], _PAL["dim"]
    return f"""
/* ---------- 4. full-season backtest: does own-season data actually help? (added 2 Sep 2026) ---------- */
const BT = {json.dumps(by_pos)};
const BTLABELS = {json.dumps(labels)};
panel('p9','4 \\u00b7 Full-season backtest: does own-season data actually predict reality?',
 `historical_backtest_2025_26.py replays build_prediction_tracker.py's own walk_forward()
  UNMODIFIED across every real 2025/26 gameweek, using a genuine 2024/25-derived prior \\u2014
  not the 2-gameweek sample the live tracker has to work with on the season actually being
  played. Each point is that single gameweek's own RMSE (not pooled with other weeks), scoring
  only 60+ minute appearances; raw is additionally scored only once a player carries 1.0+ full
  match-equivalents of PRIOR minutes, so a single early cameo can't explode the prediction the
  moment he plays a real game. CBIT/CBIRT are excluded \\u2014 2024/25's archive has no
  clearances_blocks_interceptions/tackles/recoveries columns, so there is no real prior for them.
  Position-filtered runs (e.g. FWD only) restrict the INPUT before walk_forward() runs, not the
  output \\u2014 k is already derived per-position internally, so this is exact, not an
  approximation.`,
 `<div style="display:flex;align-items:center;gap:14px;margin:0 0 14px;flex-wrap:wrap">
    <span style="font-size:13px;color:var(--dim)">Position</span>
    <span id="p9pos" style="display:flex;gap:6px"></span>
    <span style="font-size:13px;color:var(--dim);margin-left:10px">Metric</span>
    <span id="p9m" style="display:flex;gap:6px"></span>
  </div>
  <div class="wrap"><canvas id="c9"></canvas></div>
  <div class="legend">
   <span><i style="background:{a}"></i>raw RMSE</span>
   <span><i style="background:{b}"></i>prior RMSE</span>
   <span><i style="background:{c}"></i>shrunk RMSE</span>
   <span><i style="background:{dim}"></i>actual, avg per-90 (right axis)</span>
  </div>
  <div class="find" id="p9find"></div>`);
const P9POS = {json.dumps(list(by_pos.keys()))};
let p9pos = 'all', p9k = 'xgc90';
function p9Btn(active, label){{
  return `style="font-size:12px;padding:4px 10px;border-radius:6px;cursor:pointer;border:1px solid var(--line);background:${{active?C.a:'transparent'}};color:${{active?'#fff':'var(--tx)'}}"`;
}}
document.getElementById('p9pos').innerHTML = P9POS.map(p=>
  `<button data-p="${{p}}" ${{p9Btn(p===p9pos)}}>${{BT[p].label}}</button>`).join('');
let ch9;
function p9RenderMetricButtons(){{
  const keys = Object.keys(BT[p9pos].trajectory);
  if (!keys.includes(p9k)) p9k = keys[0];
  document.getElementById('p9m').innerHTML = keys.map(k=>
    `<button data-k="${{k}}" ${{p9Btn(k===p9k)}}>${{BTLABELS[k]}}</button>`).join('');
}}
function p9Draw(){{
  const posData = BT[p9pos], d = posData.trajectory[p9k], cr = posData.corr[p9k];
  const labels = d.gw.map(g=>'GW'+g);
  const mkLine = (arr,color) => ({{type:'line',data:arr,borderColor:color,backgroundColor:color,
    pointRadius:0,borderWidth:2,spanGaps:true,tension:0.2,yAxisID:'y'}});
  const barDs = {{type:'bar',data:d.actual,backgroundColor:C.dim+'55',borderWidth:0,
    yAxisID:'y1',order:3,barPercentage:0.6}};
  if (ch9) ch9.destroy();
  ch9 = new Chart(c9,{{data:{{labels,datasets:[
      Object.assign(mkLine(d.raw,C.a),{{order:0}}),
      Object.assign(mkLine(d.prior,C.b),{{order:1}}),
      Object.assign(mkLine(d.shrunk,C.c),{{order:2}}),
      barDs
    ]}},
    options:{{plugins:{{legend:{{display:false}},tooltip:{{mode:'index',intersect:false}}}},
      scales:{{
        y:{{position:'left',title:{{display:true,text:'RMSE this gameweek'}},grid:{{color:css('--grid')}}}},
        y1:{{position:'right',title:{{display:true,text:'actual, avg per-90'}},grid:{{display:false}},beginAtZero:true}},
        x:{{ticks:{{maxTicksLimit:10}},grid:{{display:false}}}}
      }}}}}});
  const nNote = posData.n===null ? '' : ` across <b>${{posData.n}}</b> players`;
  const stpCorr = BT.all.corr.stp;
  document.getElementById('p9find').innerHTML =
    `<b>Why shrunk stays close to prior here:</b> corr(raw&minus;prior, actual&minus;prior) =
     <span class="mono">${{cr.corr.toFixed(3)}}</span> (n=${{cr.n}})${{nNote}} &mdash; when a player's
     own-season rate diverges from his 2024/25 rate, that predicts which way reality actually
     moves about that strongly. A high blend weight still leaves shrunk close to prior when this
     is low, because raw's extra information is close to noise for that metric/position. Start
     rate (all positions) is the outlier at r=${{stpCorr.corr.toFixed(3)}} (not charted here \\u2014
     it is a binary metric with no per-90 actual to bar).`;
}}
document.getElementById('p9pos').addEventListener('click', e=>{{
  if (!e.target.dataset.p) return;
  p9pos = e.target.dataset.p;
  document.querySelectorAll('#p9pos button').forEach(btn=>{{
    const on = btn.dataset.p===p9pos;
    btn.style.background = on ? C.a : 'transparent';
    btn.style.color = on ? '#fff' : 'var(--tx)';
  }});
  p9RenderMetricButtons();
  p9Draw();
}});
document.getElementById('p9m').addEventListener('click', e=>{{
  if (!e.target.dataset.k) return;
  p9k = e.target.dataset.k;
  document.querySelectorAll('#p9m button').forEach(btn=>{{
    const on = btn.dataset.k===p9k;
    btn.style.background = on ? C.a : 'transparent';
    btn.style.color = on ? '#fff' : 'var(--tx)';
  }});
  p9Draw();
}});
p9RenderMetricButtons();
p9Draw();
"""


_PRED_COLOR = {"raw": _PAL["a"], "prior": _PAL["b"], "shrunk": _PAL["c"]}
_METRIC_ROWS = [  # (backtest key or None, display label, per-position note)
    ("xg90", "xG per 90", None),
    ("xa90", "xA per 90", None),
    ("xgc90", "xGC per 90", None),
    ("sv90", "Saves per 90", None),
    ("cbit90", "CBIT per 90", "no 2024/25 prior for this stat"),
    ("cbirt90", "CBIRT per 90", "no 2024/25 prior for this stat"),
    ("stp", "Start rate", None),
]
_POS_ORDER = ["GKP", "DEF", "MID", "FWD"]


def _predictor_cell(name, note=None):
    if note:
        return f'<td class="mono" style="color:var(--dim);font-size:11px">{note}</td>'
    if name is None:
        return '<td class="mono" style="color:var(--dim)">&mdash;</td>'
    color = _PRED_COLOR[name]
    return (f'<td class="mono"><span style="display:inline-flex;align-items:center;gap:6px">'
            f'<span style="width:9px;height:9px;border-radius:2px;background:{color};'
            f'display:inline-block;flex:none"></span>{name}</span></td>')


def _best_predictor_table():
    """Panel 5: a static (non-interactive) summary of panel 4's per-position
    backtest - one row per metric, one column per position, each cell the
    predictor (raw/prior/shrunk) with the lowest average per-gameweek RMSE
    for that exact combination. Built entirely in Python since there is
    nothing to filter or redraw client-side; the table below is baked HTML,
    not JS-constructed. Returns '' under the same tolerant/missing-file rule
    as _backtest_panel()."""
    if not BACKTEST:
        return ""
    by_pos = BACKTEST.get("by_position") or {}
    head = "<th>metric</th>" + "".join(f"<th>{p[:2] if p != 'GKP' else 'GK'}</th>" for p in _POS_ORDER)
    rows_html = []
    for key, label, note in _METRIC_ROWS:
        cells = []
        for pos in _POS_ORDER:
            if note:
                cells.append(_predictor_cell(None, note))
                continue
            d = by_pos.get(pos)
            best = (d or {}).get("best_predictor", {}).get(key)
            cells.append(_predictor_cell(best))
        rows_html.append(f"<tr><td><b>{label}</b></td>{''.join(cells)}</tr>")
    table_html = (f'<table><thead><tr>{head}</tr></thead><tbody>'
                  f'{"".join(rows_html)}</tbody></table>')
    a, b, c = _PAL["a"], _PAL["b"], _PAL["c"]
    legend = (f'<div class="legend">'
              f'<span><i style="background:{a}"></i>raw wins</span>'
              f'<span><i style="background:{b}"></i>prior wins</span>'
              f'<span><i style="background:{c}"></i>shrunk wins</span>'
              f'<span>&mdash; = metric doesn\'t apply to this position</span>'
              f'</div>')
    body_html = table_html + legend
    return f"""
/* ---------- 5. best predictor by position x metric, at a glance (added 2 Sep 2026) ---------- */
panel('p10','5 \\u00b7 Best predictor, by position and metric',
 `The same full-season backtest as panel 4, one cell per position x metric combination \\u2014
  whichever of raw, prior or shrunk has the lowest average per-gameweek RMSE for that exact
  pairing (GK start rate, DEF xG, and so on), each computed on that position's own players only.
  Two results stand out: GK start rate is won by raw with a huge margin (keeper rotation is close
  to deterministic once a club has a settled #1, far stickier than any outfield minutes pattern),
  and FWD xA is the only rate metric anywhere in this analysis where raw beats both prior and
  shrunk \\u2014 see panel 4's FWD/xA view for the trajectory.`,
 {json.dumps(body_html)});
"""


def build():
    body = '<div id="app"></div>'
    backtest_panel = _backtest_panel()
    predictor_table_panel = _best_predictor_table()

    script = f"""
<script>
const DATA = {json.dumps(DATA)};
const C = {{a:'#4ea3ff',b:'#ffc857',c:'#5fd38d',d:'#ff6b6b',e:'#c792ea',dim:'#8b98a5'}};
const css = k => getComputedStyle(document.documentElement).getPropertyValue(k).trim();
Chart.defaults.color = css('--dim');
Chart.defaults.borderColor = css('--grid');
Chart.defaults.font.family = "ui-monospace,Menlo,monospace";
const f2 = n => (Math.round(n*1000)/1000).toFixed(2);
const f3 = n => (n>=0?'+':'') + n.toFixed(3);
const edge = css('--tx');
const S = DATA.stats;

function panel(id, title, tests, body){{
  const d = document.createElement('div'); d.className='panel';
  d.innerHTML = `<h2>${{title}}</h2><p class="tests">${{tests}}</p>${{body}}`;
  document.getElementById('app').appendChild(d); return d;
}}

/* ---------- 1. threshold cliff (moved from Player analysis, 11 Aug 2026) ---------- */
panel('p2','1 · The threshold cliff: does the season average predict clearing the line?',
 'The 2pt DC bonus is a per-match threshold, not a rate. Plots each player\\'s season CBIT/90 average against how often they ACTUALLY cleared 10+ CBIT in a given 2025/26 match &mdash; a uniform 10+ line for every position, not each position\\'s own DC rule, so the three are directly comparable.',
 `<div style="display:flex;align-items:center;gap:14px;margin:0 0 14px;flex-wrap:wrap">
    <span style="font-size:13px;color:var(--dim)">Position</span>
    <span id="p2pos" style="display:flex;gap:6px"></span>
    <span id="p2c" class="mono" style="font-size:12px;color:var(--dim);min-width:140px"></span>
  </div>
  <div class="wrap"><canvas id="c2"></canvas></div>
  <div class="legend"><span>▲ = in your squad</span> <span>┄ dotted: 10+ CBIT average line</span></div>
  <div class="find" id="p2find"></div>`);
const P2POSES = ['DEF','MID','FWD'];
const P2 = DATA.rows.filter(r=>P2POSES.includes(r.pos) && r.cbit_hit10!==null);
let p2Pos = 'DEF';
document.getElementById('p2pos').innerHTML = P2POSES.map(p=>
  `<button data-p="${{p}}" style="font-size:12px;padding:4px 10px;border-radius:6px;cursor:pointer;border:1px solid var(--line);background:${{p==='DEF'?C.a:'transparent'}};color:${{p==='DEF'?'#fff':'var(--tx)'}}">${{p}}</button>`).join('');
function d2(pos){{
  const pts = P2.filter(r=>r.pos===pos);
  return [{{label:pos, backgroundColor:C.a,
    data:pts.map(r=>({{x:r.cbit90,y:r.cbit_hit10,n:r.name,tm:r.team,sq:r.squad,apps:r.cbit_hit10_apps}})),
    pointStyle:pts.map(r=>r.squad?'triangle':'circle'),
    pointRadius:pts.map(r=>r.squad?9:4),
    pointHoverRadius:pts.map(r=>r.squad?12:8),
    borderColor:pts.map(r=>r.squad?edge:'transparent'),
    borderWidth:pts.map(r=>r.squad?1.5:0)}}];
}}
const lines2 = {{id:'l2', afterDatasetsDraw(ch){{
  const {{ctx, chartArea:ca, scales}} = ch; ctx.save();
  ctx.setLineDash([4,4]); ctx.lineWidth=1;
  const xT = scales.x.getPixelForValue(10);
  if (xT>ca.left && xT<ca.right){{ ctx.strokeStyle=C.c;
    ctx.beginPath(); ctx.moveTo(xT,ca.top); ctx.lineTo(xT,ca.bottom); ctx.stroke();
    ctx.fillStyle=C.c; ctx.font='10px ui-monospace,Menlo,monospace';
    ctx.fillText('10+ CBIT avg', xT+4, ca.top+11); }}
  ctx.restore();
}}}};
const ch2 = new Chart(c2,{{type:'scatter',data:{{datasets:d2(p2Pos)}},
 options:{{plugins:{{legend:{{display:false}},tooltip:{{callbacks:{{label:cx=>
   `${{cx.raw.n}} (${{cx.raw.tm}})${{cx.raw.sq?' · yours':''}}  CBIT/90 avg ${{f2(cx.raw.x)}}  10+ CBIT hit-rate ${{cx.raw.y.toFixed(0)}}%  (${{cx.raw.apps}} apps)`}}}}}},
  scales:{{x:{{title:{{display:true,text:'CBIT per 90, season average'}},grid:{{color:css('--grid')}}}},
          y:{{title:{{display:true,text:'% of matches clearing 10+ CBIT'}},min:0,max:100,grid:{{color:css('--grid')}}}}}}}},
 plugins:[lines2]}});
function p2Find(pos){{
  const n = S['cbit_hit_n_'+pos.toLowerCase()], c = S['cbit_hit_corr_'+pos.toLowerCase()],
        mx = S['cbit_hit_max_'+pos.toLowerCase()];
  const el = document.getElementById('p2find');
  if (mx !== undefined && mx < 1){{
    el.innerHTML =
      `<b>${{pos}}:</b> across <b>${{n}}</b> matched players (2025/26 archive, 5+ appearances of
       60+ minutes), the highest single-player hit-rate is <span class="mono">${{f2(mx)}}%</span>
       &mdash; a correlation coefficient isn't meaningful here because there's essentially no
       variance to explain. ${{pos}}s just don't do 10+ CBIT worth of defensive work in a match;
       this line is the wrong lens for their defensive contribution.`;
    return;
  }}
  el.innerHTML =
    `<b>${{pos}}:</b> corr(CBIT/90 avg, 10+ hit-rate) = <span class="mono">${{f3(c)}}</span> over
     <b>${{n}}</b> matched players (2025/26 archive, 5+ appearances of 60+ minutes).
     A perfect proxy would sit near +1.0 on a tight diagonal &mdash; the vertical spread at any given
     x is players the season average prices identically but who clear the line at very different
     rates match to match.`;
}}
function p2Upd(pos){{
  p2Pos = pos;
  document.querySelectorAll('#p2pos button').forEach(btn=>{{
    const on = btn.dataset.p===p2Pos;
    btn.style.background = on ? C.a : 'transparent';
    btn.style.color = on ? '#fff' : 'var(--tx)';
  }});
  ch2.data.datasets = d2(p2Pos); ch2.update();
  const pts = P2.filter(r=>r.pos===p2Pos);
  const sq = pts.filter(r=>r.squad).length;
  document.getElementById('p2c').textContent = `${{pts.length}} shown · ${{sq}} yours`;
  p2Find(p2Pos);
}}
document.getElementById('p2pos').addEventListener('click', e=>{{
  if (!e.target.dataset.p) return;
  p2Upd(e.target.dataset.p);
}});
p2Upd('DEF');

/* ---------- 2. weekly points distribution by position (added 25 Aug 2026) ---------- */
const PD = DATA.posdist, PDQ = PD.qualifiers, PDS = PD.stats;
panel('p7','2 \\u00b7 Weekly points distribution: is it really bimodal, and does it differ by position?',
 `Every 2025/26 archive player who finished with more than 150 season points
  (DEF ${{PDQ.DEF.length}}, MID ${{PDQ.MID.length}}, FWD ${{PDQ.FWD.length}} qualifiers),
  every one of their individual gameweek scores pooled by position. Kruskal-Wallis tests whether
  the three positions differ in overall rank/location; pairwise Mann-Whitney U and
  Kolmogorov-Smirnov (shape of the whole distribution, not just its centre) follow, both
  Bonferroni-corrected for three comparisons.`,
 `<div class="wrap"><canvas id="c7"></canvas></div>
  <div class="legend"><span>normalised so each curve integrates to 1 &mdash; shapes are directly
   comparable despite unequal player counts</span></div>
  <table style="margin-top:14px"><thead><tr><th>test</th><th>comparison</th><th>statistic</th>
   <th>p (raw)</th><th>p (bonferroni)</th></tr></thead><tbody>
   <tr><td>Kruskal-Wallis</td><td>DEF vs MID vs FWD</td><td class="mono">H=${{f2(PDS.H)}}</td>
    <td class="mono">${{f2(PDS.kw_p)}}</td><td class="mono">&mdash;</td></tr>
   ${{PDS.mwu.map(r=>`<tr><td>Mann-Whitney U</td><td>${{r.a}} vs ${{r.b}}</td>
    <td class="mono">U=${{r.stat.toFixed(0)}}</td><td class="mono">${{f2(r.p)}}</td>
    <td class="mono">${{f2(r.p_bonf)}}${{r.p_bonf<0.05?' <span class="tag bad">sig</span>':''}}</td></tr>`).join('')}}
   ${{PDS.ks.map(r=>`<tr><td>Kolmogorov-Smirnov</td><td>${{r.a}} vs ${{r.b}}</td>
    <td class="mono">D=${{f2(r.stat)}}</td><td class="mono">${{f2(r.p)}}</td>
    <td class="mono">${{f2(r.p_bonf)}}${{r.p_bonf<0.05?' <span class="tag bad">sig</span>':''}}</td></tr>`).join('')}}
   </tbody></table>
  <div class="find"><b>Location: no difference.</b> Kruskal-Wallis and pairwise Mann-Whitney both
   fail to distinguish DEF, MID and FWD by rank/central tendency (all p &gt; 0.5 even before
   correction). Medians and means sit within a point of each other across all three.</div>
  <div class="find bad"><b>Shape: forwards differ from both.</b> The Kolmogorov-Smirnov test
   compares the full distribution, not just its centre, and finds FWD significantly different
   from both DEF and MID even after Bonferroni correction &mdash; a sharper, more polarised peak
   at 2 points with a secondary hump further out, not a shifted average. DEF vs MID shows no
   shape difference either.</div>
  <div class="find bad"><b>Caveat: the FWD read rests on ${{PDQ.FWD.length}} players
   (${{PD.pools.FWD.length}} gameweek observations).</b> A KS result from that few players can
   easily be one player's idiosyncratic pattern rather than a genuine positional effect &mdash;
   treat it as suggestive, not settled, until a bigger forward sample is available.</div>`);
function hist(arr, xs){{
  const c = {{}}; arr.forEach(v=>c[v]=(c[v]||0)+1);
  const n = arr.length;
  return xs.map(x=>(c[x]||0)/n);
}}
const PDxs = Array.from({{length:24}},(_,i)=>i-2);
new Chart(c7,{{type:'line',data:{{labels:PDxs,datasets:[
  {{label:`DEF (n=${{PD.pools.DEF.length}})`,data:hist(PD.pools.DEF,PDxs),borderColor:C.a,backgroundColor:'transparent',borderWidth:2,pointRadius:0,tension:.3}},
  {{label:`MID (n=${{PD.pools.MID.length}})`,data:hist(PD.pools.MID,PDxs),borderColor:C.c,backgroundColor:'transparent',borderWidth:2,borderDash:[6,3],pointRadius:0,tension:.3}},
  {{label:`FWD (n=${{PD.pools.FWD.length}})`,data:hist(PD.pools.FWD,PDxs),borderColor:C.d,backgroundColor:'transparent',borderWidth:2,borderDash:[2,2],pointRadius:0,tension:.3}}
]}},options:{{plugins:{{legend:{{display:true,position:'top',labels:{{boxWidth:10}}}}}},
 scales:{{x:{{title:{{display:true,text:'points in a gameweek'}},grid:{{color:css('--grid')}}}},
         y:{{title:{{display:true,text:'proportion of gameweeks'}},grid:{{color:css('--grid')}}}}}}}}}});

/* ---------- 3. your squad, replayed across last season (added 25 Aug 2026) ---------- */
const SR = DATA.squad_replay;
panel('p8',`3 \\u00b7 Your squad, replayed across 2025/26`,
 `The CURRENT squad.json XI (formation ${{SR.formation||'?'}}), bench order, captain
  (${{SR.captain}}) and vice (${{SR.vice}}) &mdash; unchanged &mdash; against every REAL
  2025/26 gameweek. Autosubs apply on 0 minutes (bench priority order, formation-legal swaps
  only); the armband passes to vice if the captain blanks. This is NOT a 2026/27 prediction:
  it's last season's fixtures and form mapped onto this season's squad, so it shows the
  WEEK-TO-WEEK VARIANCE this set of 15 tends to produce, not what to expect going forward.
  Recomputed on every build from squad.json &mdash; the moment a transfer is actioned this
  panel updates with it.`,
 `<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin:0 0 14px">
   <div style="background:var(--grid);border-radius:8px;padding:10px 12px">
    <div style="color:var(--dim);font-size:12px">mean</div>
    <div class="mono" style="font-size:20px;font-weight:600">${{f2(SR.mean)}}</div></div>
   <div style="background:var(--grid);border-radius:8px;padding:10px 12px">
    <div style="color:var(--dim);font-size:12px">median</div>
    <div class="mono" style="font-size:20px;font-weight:600">${{SR.median}}</div></div>
   <div style="background:var(--grid);border-radius:8px;padding:10px 12px">
    <div style="color:var(--dim);font-size:12px">std dev</div>
    <div class="mono" style="font-size:20px;font-weight:600">${{f2(SR.sd)}}</div></div>
   <div style="background:var(--grid);border-radius:8px;padding:10px 12px">
    <div style="color:var(--dim);font-size:12px">range</div>
    <div class="mono" style="font-size:20px;font-weight:600">${{SR.min}}&ndash;${{SR.max}}</div></div>
  </div>
  <div class="wrap"><canvas id="c8"></canvas></div>
  ${{SR.missing.length?`<div class="find bad"><b>Unmatched squad players (excluded from the
   replay, not silently zeroed):</b> ${{SR.missing.join(', ')}}</div>`:''}}`);
new Chart(c8,{{type:'bar',data:{{labels:['0-4','5-9','10-14','15-19','20-24','25-29','30-34','35-39','40-44','45-49','50-54','55-59','60-64','65-69','70-74','75-79','80-84','85-89'],
 datasets:[{{label:'% of gameweeks',data:SR.bins.map(b=>b/SR.scores.length*100),backgroundColor:C.a,borderRadius:4}}]}},
 options:{{plugins:{{legend:{{display:false}}}},
  scales:{{x:{{title:{{display:true,text:'points scored that gameweek'}},grid:{{display:false}}}},
          y:{{title:{{display:true,text:'% of gameweeks'}},grid:{{color:css('--grid')}}}}}}}}}});

{backtest_panel}
{predictor_table_panel}
</script>"""

    html = page_shell.shell(
        title="Statistical relationships",
        active="relationships",
        subtitle=f"Prior season {bd.snap.get('season_described','?')} &middot; "
                 f"same player pool as Player analysis &middot; page generated "
                 f"{dt.datetime.now():%Y-%m-%d %H:%M}",
        body=body,
        footer="Built by <span class='mono'>build_relationships_page.py</span>, reading "
               "the same payload <span class='mono'>build_dashboard.py</span> computes for "
               "Player analysis. Panel 1 moved here 11 Aug 2026: the threshold cliff tests "
               "the SHAPE of a relationship, not a squad decision.")
    html = html.replace("</body>", script + "\n</body>")
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    open(OUT, "w", encoding="utf-8").write(html)
    return html


if __name__ == "__main__":
    h = build()
    print(f"written: {OUT}  ({len(h)/1024:.0f} KB)")
    assert "cdn.jsdelivr.net/npm/chart.js@4.5.0" in h, "Chart.js tag missing"
    print(f"  panels: threshold cliff (p2), points distribution (p7), squad replay (p8) · "
          f"{len(DATA['rows'])} players shared with Player analysis")
