#!/usr/bin/env python3
"""Build the player timeseries page — docs/player.html.

    python3 fetch_gw_history.py     # first: produce docs/data/
    python3 build_player_page.py

THE ONLY PAGE THAT FETCHES. 261 player files are 6.5 MB — far too much to inline,
so this page loads docs/data/index.json on open and a single player file on
click. It therefore needs http(s): it will NOT work opened straight off disk.
That is the deliberate boundary from DASHBOARD_PLAN.md — pages carrying decisions
stay self-contained, the exploratory one may require a server.

    Local preview:  python3 -m http.server -d docs 8000

PROVENANCE IS RENDERED, NOT BURIED. The 9 Aug decision to fetch rather than
vendor came with a condition: show where the data came from. The header states
the source, the fetch time and the match rate, and says plainly that this is a
community archive mirroring the official API rather than the API itself.

THE CLUB-CHANGE MARKER IS THE POINT, NOT A DECORATION. A timeseries spanning a
transfer is two different populations on one axis. Nineteen pool players moved
this summer; for them, last season's line describes a club they have left, and
the page says so above the chart rather than in a caption.
"""
import importlib.util, json, os, datetime as dt

HERE = os.path.dirname(os.path.abspath(__file__))


def _load(mod, fn):
    spec = importlib.util.spec_from_file_location(mod, os.path.join(HERE, fn))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


page_shell = _load("page_shell", "page_shell.py")
OUT = os.environ.get("FPL_PLAYER_OUT") or os.path.join(HERE, "docs", "player.html")
DATA = os.path.join(HERE, "docs", "data")


def build():
    prov_path = os.path.join(DATA, "provenance.json")
    if not os.path.exists(prov_path):
        raise SystemExit(
            "docs/data/provenance.json missing — run `python3 fetch_gw_history.py`\n"
            "first. This page is not built from assumptions about data that may\n"
            "not exist.")
    prov = json.load(open(prov_path, encoding="utf-8"))
    changes = json.load(open(os.path.join(DATA, "club_changes.json"), encoding="utf-8"))
    index = json.load(open(os.path.join(DATA, "index.json"), encoding="utf-8"))

    fetched = prov["fetched_utc"][:16].replace("T", " ")
    body = f"""
<div class="panel">
  <h2>Where this data comes from</h2>
  <table><tbody>
    <tr><td>Source</td><td style="text-align:left"><span class="mono">{prov['source']}</span>
        — a community archive mirroring the official FPL API gameweek by gameweek.
        <b>Not the API itself.</b></td></tr>
    <tr><td>Season</td><td style="text-align:left" class="mono">{prov['season']} ·
        gameweeks {prov['gameweeks'][0]}–{prov['gameweeks'][1]}</td></tr>
    <tr><td>Fetched</td><td style="text-align:left" class="mono">{fetched} UTC</td></tr>
    <tr><td>Matched</td><td style="text-align:left" class="mono">{prov['matched']} of
        {prov['pool_size']} pool players · {len(prov['unmatched'])} unmatched</td></tr>
  </tbody></table>
  {'<div class="find">Unmatched, and therefore absent from this page: <b>' +
   ', '.join(prov['unmatched']) + '</b>. Element ids are reassigned each season, so '
   'matching goes through names; these could not be resolved unambiguously.</div>'
   if prov['unmatched'] else ''}
</div>

<div class="panel">
  <h2>Pick a player</h2>
  <p class="tests">{len(index)} players with 900+ minutes last season.</p>
  <input id="q" type="text" placeholder="Type a name…" autocomplete="off">
  <div id="hits" class="hits"></div>
</div>

<div id="detail"></div>
"""

    extra_css = """
<style>
#q{width:100%;max-width:420px;padding:9px 12px;border-radius:8px;font-size:14px;
background:var(--bg);color:var(--tx);border:1px solid var(--line)}
.hits{display:flex;flex-wrap:wrap;gap:6px;margin-top:10px}
.hit{padding:5px 10px;border-radius:7px;border:1px solid var(--line);
background:var(--bg);cursor:pointer;font-size:12.5px}
.hit:hover{border-color:var(--a);color:var(--a)}
.hit b{margin-right:5px}
.stat{display:grid;grid-template-columns:repeat(auto-fit,minmax(120px,1fr));gap:10px;margin:4px 0 16px}
.stat div{background:var(--bg);border:1px solid var(--line);border-radius:8px;padding:9px 11px}
.stat .v{font-size:18px;font-weight:700;font-variant-numeric:tabular-nums}
.stat .l{font-size:11px;color:var(--dim)}
</style>"""

    script = f"""
<script>
const INDEX = {json.dumps(index, ensure_ascii=False)};
const MOVED = {json.dumps({c['player']: c for c in changes}, ensure_ascii=False)};
const num = (r,k) => {{ const v = parseFloat(r[k]); return isNaN(v) ? 0 : v; }};
let chart1 = null, chart2 = null;

function render(list) {{
  document.getElementById('hits').innerHTML = list.slice(0, 40).map(p =>
    `<span class="hit" data-slug="${{p.slug}}"><b>${{p.name}}</b>${{p.team}} · ${{p.pos}}</span>`
  ).join('');
}}

function search() {{
  const q = document.getElementById('q').value.trim().toLowerCase();
  render(q ? INDEX.filter(p => p.name.toLowerCase().includes(q) ||
                               p.team.toLowerCase().includes(q)) : INDEX);
}}

async function show(slug) {{
  const p = INDEX.find(x => x.slug === slug);
  const d = await (await fetch('data/players/' + slug + '.json')).json();
  const gw = d.gw;
  const mv = MOVED[d.name];

  const mins = gw.map(r => num(r,'minutes'));
  const pts  = gw.map(r => num(r,'total_points'));
  const xgi  = gw.map(r => num(r,'expected_goal_involvements'));
  const ret  = gw.map(r => num(r,'goals_scored') + num(r,'assists'));
  let cx = 0, cr = 0;
  const cumX = xgi.map(v => cx += v), cumR = ret.map(v => cr += v);
  const starts = gw.filter(r => num(r,'starts') > 0).length;
  const tot = pts.reduce((a,b) => a+b, 0);

  document.getElementById('detail').innerHTML = `
    <div class="panel">
      <h2>${{d.name}} <span class="mono" style="font-size:13px;color:var(--dim)">
        ${{d.team}} · ${{d.pos}} · ${{d.season}}</span></h2>
      ${{mv ? `<div class="find bad"><b>Played for ${{mv.was}} last season, now at
        ${{mv.now}}.</b> Everything below describes a club he has left — a different
        side, different tactics, different team-mates. It is history, not a
        forecast of his new role.</div>` : ''}}
      <div class="stat">
        <div><div class="v">${{tot}}</div><div class="l">total points</div></div>
        <div><div class="v">${{starts}}/${{gw.length}}</div><div class="l">starts</div></div>
        <div><div class="v">${{mins.reduce((a,b)=>a+b,0).toLocaleString()}}</div><div class="l">minutes</div></div>
        <div><div class="v">${{cumX.at(-1).toFixed(1)}}</div><div class="l">xGI</div></div>
        <div><div class="v">${{cumR.at(-1)}}</div><div class="l">goals + assists</div></div>
        <div><div class="v">${{(cumR.at(-1)-cumX.at(-1)).toFixed(1)}}</div><div class="l">delta</div></div>
      </div>
      <div class="wrap short"><canvas id="c1"></canvas></div>
      <p class="tests" style="margin-top:14px">Cumulative expected involvement against
      what actually landed. The gap IS the delta — and when it opens tells you more
      than its season total.</p>
      <div class="wrap short"><canvas id="c2"></canvas></div>
    </div>`;

  const grid = {{ color: '#232b34' }};
  if (chart1) chart1.destroy();
  if (chart2) chart2.destroy();
  chart1 = new Chart(document.getElementById('c1'), {{
    data: {{ labels: gw.map(r => 'GW' + r.round), datasets: [
      {{ type:'bar', label:'points', data: pts, backgroundColor:'#4ea3ff', borderRadius:3, yAxisID:'y' }},
      {{ type:'line', label:'minutes', data: mins, borderColor:'#ffc857',
         backgroundColor:'#ffc857', pointRadius:2, tension:.25, yAxisID:'y1' }} ]}},
    options: {{ responsive:true, maintainAspectRatio:false,
      scales: {{ y:{{ beginAtZero:true, grid }},
                 y1:{{ position:'right', beginAtZero:true, max:95, grid:{{display:false}} }},
                 x:{{ grid:{{display:false}} }} }} }}
  }});
  chart2 = new Chart(document.getElementById('c2'), {{
    data: {{ labels: gw.map(r => 'GW' + r.round), datasets: [
      {{ type:'line', label:'cumulative xGI', data: cumX, borderColor:'#c792ea',
         pointRadius:0, tension:.2 }},
      {{ type:'line', label:'cumulative goals + assists', data: cumR, borderColor:'#5fd38d',
         pointRadius:0, tension:.2 }} ]}},
    options: {{ responsive:true, maintainAspectRatio:false,
      scales: {{ y:{{ beginAtZero:true, grid }}, x:{{ grid:{{display:false}} }} }} }}
  }});
  window.scrollTo({{ top: document.getElementById('detail').offsetTop - 20, behavior:'smooth' }});
}}

document.getElementById('q').addEventListener('input', search);
document.getElementById('hits').addEventListener('click', e => {{
  const el = e.target.closest('.hit');
  if (el) show(el.dataset.slug);
}});

// Deep-link from Player Analysis: a clicked chart point there sends
// ?name=..&team=.. here. Team disambiguates duplicate surnames (e.g. two
// "Martinez"es); without it a name-only match still degrades gracefully to
// the first hit rather than failing silently.
(function initFromQuery(){{
  const params = new URLSearchParams(location.search);
  const qName = params.get('name');
  if (!qName) {{ render(INDEX); return; }}
  document.getElementById('q').value = qName;
  const qTeam = params.get('team');
  let match = INDEX.find(p => p.name === qName && (!qTeam || p.team === qTeam));
  if (!match) match = INDEX.find(p => p.name.toLowerCase() === qName.toLowerCase());
  if (match) {{
    render(INDEX.filter(p => p.name.toLowerCase().includes(qName.toLowerCase())));
    show(match.slug);
  }} else {{
    search();
  }}
}})();
</script>"""

    html = page_shell.shell(
        title="Player timeseries",
        active="player",
        subtitle=f"{prov['season']} gameweek history · {prov['matched']} players · "
                 f"archive fetched {fetched} UTC · page generated "
                 f"{dt.datetime.now():%Y-%m-%d %H:%M}",
        body=body,
        footer="Built by <span class='mono'>build_player_page.py</span>. Data fetched by "
               "<span class='mono'>fetch_gw_history.py</span> from a community archive — "
               "well-sourced, but not the official API.")
    html = html.replace("</head>", extra_css + "\n</head>").replace("</body>", script + "\n</body>")
    open(OUT, "w", encoding="utf-8").write(html)
    return html, prov, changes


if __name__ == "__main__":
    h, prov, changes = build()
    print(f"written: {OUT}  ({len(h)/1024:.0f} KB)")
    assert "cdn.jsdelivr.net/npm/chart.js@4.5.0" in h, "Chart.js tag missing"
    assert prov["source"] in h, "provenance not rendered"
    print(f"  provenance rendered · {prov['matched']}/{prov['pool_size']} matched · "
          f"{len(changes)} club changes flagged")
