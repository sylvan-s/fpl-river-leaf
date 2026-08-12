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
OUT = os.environ.get("FPL_RELATIONSHIPS_OUT") or os.path.join(HERE, "docs", "relationships.html")

DATA = bd.payload


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
