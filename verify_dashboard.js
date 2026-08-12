// Execute the dashboard script against a minimal DOM + Chart stub.
// Syntax checking alone missed a fatal parse error; this actually RUNS it.
const charts = [];
// Real chart instances, exposed so the click-through test below can reach
// each chart's options.onClick — the `charts` array above is metadata only.
const chartInstances = [];
global.Chart = function (cv, cfg) {
  const tri = (cfg.data.datasets || []).reduce((a, d) =>
    a + (Array.isArray(d.pointStyle) ? d.pointStyle.filter(x => x === 'triangle').length : 0), 0);
  charts.push({ canvas: cv && cv.id, type: cfg.type, datasets: (cfg.data.datasets || []).length,
                points: (cfg.data.datasets || []).reduce((a, d) => a + (d.data ? d.data.length : 0), 0),
                triangles: tri });
  // exercise scriptable options + tooltip callbacks the way Chart.js would
  (cfg.data.datasets || []).forEach(d => {
    if (typeof d.pointRadius === 'function') d.pointRadius({ raw: d.data[0] });
    if (d.data[0]) {
      const cb = cfg.options?.plugins?.tooltip?.callbacks;
      if (cb?.label) cb.label({ raw: d.data[0], label: '0' });
      if (cb?.title) cb.title([{ label: '0' }]);
    }
  });
  (cfg.plugins || []).forEach(p => p.afterDatasetsDraw && p.afterDatasetsDraw({
    ctx: { save(){}, restore(){}, fillText(){}, beginPath(){}, moveTo(){}, lineTo(){},
           stroke(){}, setLineDash(){},
           set font(v){}, set fillStyle(v){}, set strokeStyle(v){}, set lineWidth(v){} },
    chartArea: { left: 0, right: 500, top: 0, bottom: 300 },
    scales: { x: { getPixelForValue: v => 50 + v * 10 },
              y: { getPixelForValue: v => 250 - v * 100 } },
    getDatasetMeta: () => ({ data: (cfg.data.datasets[0].data || []).map(() => ({ x: 0, y: 0 })) })
  }));
  const inst = {
    canvas: cv && cv.id, config: cfg, data: cfg.data, options: cfg.options,
    update() {
      const i = charts.findIndex(c => c.canvas === inst.canvas);
      const rec = { canvas: inst.canvas, type: cfg.type,
        datasets: inst.data.datasets.length,
        points: inst.data.datasets.reduce((a, d) => a + (d.data ? d.data.length : 0), 0),
        triangles: inst.data.datasets.reduce((a, d) =>
          a + (Array.isArray(d.pointStyle) ? d.pointStyle.filter(x => x === 'triangle').length : 0), 0) };
      if (i >= 0) charts[i] = rec; else charts.push(rec);
    }
  };
  chartInstances.push(inst);
  return inst;
};
Chart.defaults = { color: '', borderColor: '', font: {} };

const made = {};
function mkEl(id) {
  const el = { id, style: {}, children: [], value: '25',
    set innerHTML(v) { this._h = v; (v.match(/<canvas id="([^"]+)"/g) || []).forEach(m => {
        const cid = m.match(/id="([^"]+)"/)[1]; made[cid] = { id: cid }; global[cid] = made[cid]; }); },
    get innerHTML() { return this._h; },
    set textContent(v) { this._t = v; }, get textContent() { return this._t; },
    appendChild(c) { this.children.push(c); },
    addEventListener(ev, fn) { (this._ev ||= {})[ev] = fn; },
    set onclick(fn) { (this._ev ||= {}).click = fn; },
    querySelectorAll() { return []; },
    fire(ev, val, extra) {
      const f = (this._ev || {})[ev];
      if (f) f({ target: Object.assign({ value: val }, extra || {}) });
    } };
  return el;
}
const app = mkEl('app'), sub = mkEl('sub'), foot = mkEl('foot');
const byId = {};
global.document = {
  createElement: () => mkEl(''),
  getElementById: id => ({ app, sub, foot }[id] || made[id] || (byId[id] ||= mkEl(id))),
  querySelectorAll: () => [],
  documentElement: {}
};
global.getComputedStyle = () => ({ getPropertyValue: () => '#000' });
global.window = global;
// goToPlayer() writes window.location.href — a plain settable stub is enough
// to observe where a chart click would have sent the browser.
global.location = { href: '' };
// In-memory stand-in for the sticky start% filter (11 Aug 2026). A real
// stub, not just a try/catch bypass, so the round-trip actually gets
// exercised here rather than silently taking the "storage unavailable" path.
const _lsStore = {};
global.localStorage = {
  getItem: k => (k in _lsStore ? _lsStore[k] : null),
  setItem: (k, v) => { _lsStore[k] = String(v); },
  removeItem: k => { delete _lsStore[k]; },
};
// Pre-seed as if a PRIOR visit had left the filter at 50% — this is what
// "navigate away and back" looks like on a real page load, since the whole
// script re-runs from scratch and only localStorage survives.
const STP_KEY = 'fpl_analysis_min_start_pct';
_lsStore[STP_KEY] = '50';

try {
  require('./dash.js');
} catch (e) {
  console.log('RUNTIME ERROR:', e.message); process.exit(1);
}
console.log('panels rendered :', app.children.length);
console.log('charts created  :', charts.length);
charts.forEach(c => console.log(`   ${String(c.canvas).padEnd(5)} ${c.type.padEnd(8)} ${c.datasets} datasets, ${String(c.points).padStart(3)} points, ${c.triangles} triangles`));

// Sticky start% filter: the 50% seeded into localStorage above should already
// be applied — readout, slider value, AND the charts themselves — with no
// user interaction at all. This is the "navigated back to the page" case;
// a filter that only works via the input event would pass every other check
// here and still fail the one thing this feature was built for.
const stpReadout = byId['globalStpV'];
const stpSlider = byId['globalStp'];
const restoredOk = !!stpReadout && !!stpSlider
  && stpReadout.textContent === '50%' && String(stpSlider.value) === '50'
  && charts.find(c => c.canvas === 'c1').points < 110;
console.log(`sticky filter restored on load : readout "${stpReadout?.textContent}" `
  + `slider "${stpSlider?.value}" c1 points ${charts.find(c => c.canvas === 'c1').points} -> ${restoredOk ? 'OK' : 'WRONG'}`);
// Reset to the unfiltered baseline the rest of this suite assumes (squad
// marker counts, default xP explorer row counts, etc. are all written
// against the full pool) — the sticky-restore check above is done with it.
if (stpSlider) stpSlider.fire('input', '0');
// Derived from squad.json, the single source of truth. These were hardcoded as
// `5, 5` beside a comment listing O'Reilly, Enzo and Berge — three players who
// had already been transferred out. The numbers still happened to be right,
// which is exactly why nobody noticed: a stale constant that agrees with
// reality by coincidence is indistinguishable from a correct one until it
// isn't. Deriving it means a transfer can no longer silently invalidate this.
const _sq = require('./squad.json').squad;
const SQUAD_DEF = _sq.filter(p => p.pos === 'DEF').length;
const SQUAD_MID = _sq.filter(p => p.pos === 'MID').length;
const triOk = charts.find(c => c.canvas === 'c1').triangles === SQUAD_DEF
           && charts.find(c => c.canvas === 'c3m').triangles === SQUAD_MID;
console.log(`squad markers   : c1 expects ${SQUAD_DEF} triangles, c3m expects ${SQUAD_MID} -> ${triOk ? 'OK' : 'WRONG'}`);
console.log('header text     :', (sub.textContent || '').slice(0, 70) + '...');
// Panel 7 renders a table, not a canvas, so chart counts say nothing about it.
// Exercise the filters directly and assert the row counts actually change.
function tableRows(html) { return (html.match(/<tr class=/g) || []).length; }
let xpOk = false;
const xpTable = byId['xptable'], nsel = byId['nsel'], mine = byId['mineonly'], btns = byId['posbtns'];
if (xpTable && nsel && btns) {
  const all25 = tableRows(xpTable.innerHTML);
  nsel.value = '10'; nsel.fire('change');
  const ten = tableRows(xpTable.innerHTML);
  nsel.value = '9999'; nsel.fire('change');
  const everything = tableRows(xpTable.innerHTML);
  btns.fire('click', null, { dataset: { p: 'GKP' } });
  const gkp = tableRows(xpTable.innerHTML);
  const gkpArch = (xpTable.innerHTML.match(/—/g) || []).length;
  console.log(`xP explorer     : default ${all25} rows -> 10 gives ${ten} -> all gives ${everything} -> GKP gives ${gkp}`);
  console.log(`                  GKP archetypes blank (correct, A2 undefined): ${gkpArch > 0}`);
  xpOk = all25 === 25 && ten === 10 && everything > 250 && gkp === 23;
}

// Panel 2 (threshold cliff) moved to relationships.html on 11 Aug 2026 — its
// position-filter check moved with it and is no longer exercised here.

// Panel 4 position buttons: clicking DEF should also change the point count.
let p4ok = false;
const p4btns = byId['p4pos'];
if (p4btns) {
  const before = charts.find(c => c.canvas === 'c3').points;
  p4btns.fire('click', null, { dataset: { p: 'DEF' } });
  const after = charts.find(c => c.canvas === 'c3').points;
  console.log(`p4 position filter  : ALL ${before} pts -> DEF ${after}`);
  p4ok = after !== before;
}

// Panel 7: xP4_adj replaces blank%.
const xpHeadOk = xpTable && /xP4_adj/.test(xpTable.innerHTML) && !/blank%/.test(xpTable.innerHTML);
console.log(`xP explorer columns : xP4_adj present, blank% gone -> ${xpHeadOk}`);

// The single global start% filter (11 Aug 2026) replaced four separate
// per-panel sliders. Fire it once and confirm it drives panels 1, 3, 4 AND
// the panel 7 table together — a shared control that only moves one of them
// would be the exact failure this consolidation could introduce silently.
let globalOk = false;
const globalStp = byId['globalStp'];
if (globalStp) {
  const before = {
    c1: charts.find(c => c.canvas === 'c1').points,
    c3m: charts.find(c => c.canvas === 'c3m').points,
    c3: charts.find(c => c.canvas === 'c3').points,
    rows: tableRows(xpTable.innerHTML),
  };
  globalStp.fire('input', '80');
  const after = {
    c1: charts.find(c => c.canvas === 'c1').points,
    c3m: charts.find(c => c.canvas === 'c3m').points,
    c3: charts.find(c => c.canvas === 'c3').points,
    rows: tableRows(xpTable.innerHTML),
  };
  console.log(`global start% filter: c1 ${before.c1}->${after.c1}  c3m ${before.c3m}->${after.c3m}  `
    + `c3 ${before.c3}->${after.c3}  xp rows ${before.rows}->${after.rows} `
    + `(readout "${byId['globalStpV']?.textContent}")`);
  globalOk = after.c1 < before.c1 && after.c3m < before.c3m
    && after.c3 < before.c3 && after.rows < before.rows;
}
// Moving the slider should also persist the new value — the other half of
// "sticky": restore-on-load only works if input events actually write.
const stickyWriteOk = _lsStore[STP_KEY] === '80';
console.log(`sticky filter persisted     : localStorage[${STP_KEY}] = "${_lsStore[STP_KEY]}" -> ${stickyWriteOk ? 'OK' : 'WRONG'}`);

// Panel 8 (xGC vs CS per club), added 11 Aug 2026: one point per club, no
// filters to drive — just confirm it actually rendered with real data.
const p8 = charts.find(c => c.canvas === 'c6');
const p8ok = !!p8 && p8.points > 0;
console.log(`xGC vs CS per club  : ${p8 ? p8.points : 0} clubs plotted`);

// Click-through: a point clicked on c1/c3m/c3 should send the browser to
// player.html carrying that player's name + team (12 Aug 2026 addition).
let clickOk = false;
const wired = chartInstances.filter(i => i.options && typeof i.options.onClick === 'function');
if (wired.length === 3) {
  const target = wired.find(i => i.data.datasets.some(d => d.data && d.data.length));
  if (target) {
    const ds = target.data.datasets.findIndex(d => d.data && d.data.length);
    location.href = '';
    target.options.onClick({ native: { target: { style: {} } } }, [{ datasetIndex: ds, index: 0 }]);
    clickOk = /^player\.html\?name=/.test(location.href);
  }
}
console.log(`chart click-through : ${wired.length} charts wired, sample -> "${location.href}" -> ${clickOk ? 'OK' : 'WRONG'}`);

const ok = app.children.length === 6 && charts.length === 5
  && charts.every(c => c.points > 0) && triOk && xpOk
  && p4ok && xpHeadOk && globalOk && p8ok && restoredOk && stickyWriteOk && clickOk;
console.log('\nRESULT:', ok ? 'ALL PANELS RENDER, ALL FILTERS WORK' : 'INCOMPLETE');
process.exit(ok ? 0 : 1);
