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

    bins = [0] * 9  # 0-9, 10-19, ..., 80-89
    for s in scores:
        bins[min(8, max(0, s) // 10)] += 1
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


def build():
    body = '<div id="app"></div>'

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

/* ---------- 2. threshold cliff (moved from Player analysis, 11 Aug 2026) ---------- */
panel('p2','2 · The threshold cliff: does the season average predict clearing the line?',
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

/* ---------- 6. shrinkage (moved from Player analysis, 11 Aug 2026) ---------- */
const rowsK = DATA.kpanel.map(k=>`<tr><td>${{k.label}}</td><td class="mono">${{k.n}}</td>
 <td class="mono">${{k.total.toFixed(5)}}</td><td class="mono">${{k.samp.toFixed(5)}}</td>
 <td class="mono">${{f3(k.between)}}</td>
 <td class="mono">${{k.k_before.toFixed(1)}} ${{k.deg_before?'<span class="tag bad">fallback</span>':''}}</td>
 <td class="mono">${{k.k_after.toFixed(1)}} ${{k.deg_after?'<span class="tag bad">fallback</span>':'<span class="tag ok">derived</span>'}}</td></tr>`).join('');
panel('p6','6 · Shrinkage: is k derived, or quietly defaulted?',
 'The panel that found a live bug. k is in units of 90s, so k = 60 means 60 matches before a player&rsquo;s own data carries half the weight. A season is 38.',
 `<table><thead><tr><th>pool</th><th>n</th><th>total var</th><th>sampling var</th>
   <th>between</th><th>k before</th><th>k after fix</th></tr></thead><tbody>${{rowsK}}</tbody></table>
  <div class="wrap short" style="margin-top:16px"><canvas id="c5"></canvas></div>
  <div class="find bad"><b>Bug found and fixed, 8 Aug 2026.</b> The Poisson noise model
  (<span class="mono">rate/n90</span>) is right for counts but wrong for xGI, which is a sum of
  ~0.11 per-shot probabilities, not whole events. It drove between-player variance
  <b>negative</b> for forwards and pinned k to its cap. Every attacker would have stayed
  frozen on his prior all season. Fixed with a per-metric dispersion factor.</div>
  <div class="find ok"><b>GKP still shows a fallback, and that is correct.</b> Keepers genuinely
  do not differ on xGI, so shrinking hard is the right answer. The fallback fires where it should
  &mdash; it no longer fires where it should not.</div>`);
const xs = Array.from({{length:39}},(_,i)=>i);
new Chart(c5,{{type:'line',data:{{labels:xs,datasets:DATA.kpanel.map((k,i)=>({{
  label:`${{k.label}} (k=${{k.k_after.toFixed(1)}})`,
  data:xs.map(n=>n/(n+k.k_after)),borderColor:[C.a,C.e,C.c,C.d][i],
  pointRadius:0,borderWidth:2,tension:.25}}))}},
 options:{{plugins:{{title:{{display:true,text:'weight on a player\\'s OWN data as matches accumulate',color:css('--tx')}}}},
  scales:{{x:{{title:{{display:true,text:'matches played (season = 38)'}},grid:{{color:css('--grid')}}}},
          y:{{min:0,max:1,title:{{display:true,text:'weight on own data'}},grid:{{color:css('--grid')}}}}}}}}}});

/* ---------- 7. weekly points distribution by position (added 25 Aug 2026) ---------- */
const PD = DATA.posdist, PDQ = PD.qualifiers, PDS = PD.stats;
panel('p7','7 \\u00b7 Weekly points distribution: is it really bimodal, and does it differ by position?',
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

/* ---------- 8. your squad, replayed across last season (added 25 Aug 2026) ---------- */
const SR = DATA.squad_replay;
panel('p8',`8 \\u00b7 Your squad, replayed across 2025/26`,
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
new Chart(c8,{{type:'bar',data:{{labels:['0-9','10-19','20-29','30-39','40-49','50-59','60-69','70-79','80-89'],
 datasets:[{{label:'gameweeks',data:SR.bins,backgroundColor:C.a,borderRadius:4}}]}},
 options:{{plugins:{{legend:{{display:false}}}},
  scales:{{x:{{title:{{display:true,text:'points scored that gameweek'}},grid:{{display:false}}}},
          y:{{title:{{display:true,text:'number of gameweeks (of 38)'}},grid:{{color:css('--grid')}}}}}}}}}});
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
               "Player analysis. Panels moved here 11 Aug 2026: the threshold cliff and "
               "shrinkage diagnostics test the SHAPE of a relationship, not a squad decision.")
    html = html.replace("</body>", script + "\n</body>")
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    open(OUT, "w", encoding="utf-8").write(html)
    return html


if __name__ == "__main__":
    h = build()
    print(f"written: {OUT}  ({len(h)/1024:.0f} KB)")
    assert "cdn.jsdelivr.net/npm/chart.js@4.5.0" in h, "Chart.js tag missing"
    assert DATA["kpanel"], "kpanel empty — build_dashboard.py payload changed shape?"
    print(f"  panels: threshold cliff (p2), shrinkage (p6) · "
          f"{len(DATA['rows'])} players shared with Player analysis")
