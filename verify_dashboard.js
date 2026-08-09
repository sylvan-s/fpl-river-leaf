// Execute the dashboard script against a minimal DOM + Chart stub.
// Syntax checking alone missed a fatal parse error; this actually RUNS it.
const charts = [];
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
    canvas: cv && cv.id, config: cfg, data: cfg.data,
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

try {
  require('./dash.js');
} catch (e) {
  console.log('RUNTIME ERROR:', e.message); process.exit(1);
}
console.log('panels rendered :', app.children.length);
console.log('charts created  :', charts.length);
charts.forEach(c => console.log(`   ${String(c.canvas).padEnd(5)} ${c.type.padEnd(8)} ${c.datasets} datasets, ${String(c.points).padStart(3)} points, ${c.triangles} triangles`));
const SQUAD_DEF = 5, SQUAD_MID = 5;   // Lacroix Gabriel O'Reilly Kayode Shaw / Bruno Tavernier Mbeumo Enzo Berge
const triOk = charts.find(c => c.canvas === 'c1').triangles === SQUAD_DEF
           && charts.find(c => c.canvas === 'c3m').triangles === SQUAD_MID;
console.log(`squad markers   : c1 expects ${SQUAD_DEF} triangles, c3m expects ${SQUAD_MID} -> ${triOk ? 'OK' : 'WRONG'}`);
console.log('header text     :', (sub.textContent || '').slice(0, 70) + '...');
// Exercise panel 1's blank-risk slider - a chart that renders but whose filter
// throws is still broken. Drive it to a low value and confirm points drop.
function drive(id, val, canvas, label) {
  const el = byId[id];
  if (!el) { console.log(`${label}: MISSING`); return false; }
  const before = charts.find(c => c.canvas === canvas).points;
  el.fire('input', val);
  const after = charts.find(c => c.canvas === canvas).points;
  console.log(`${label}: ${before} pts -> ${after} (readouts "${byId[id.replace('s','v')]?.textContent}", "${byId[id.replace('s','c')]?.textContent}")`);
  return after < before;
}
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

const s1 = drive('p1s', 80, 'c1', 'start% slider (DEF)');
const s3 = drive('p3s', 80, 'c3m', 'start% slider (MID)');
const s4 = drive('p4s', 80, 'c3', 'start% slider (P4) ');

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

// Panel 7: xP4_adj replaces blank%, and its own start% slider filters rows.
const xpHeadOk = xpTable && /xP4_adj/.test(xpTable.innerHTML) && !/blank%/.test(xpTable.innerHTML);
console.log(`xP explorer columns : xP4_adj present, blank% gone -> ${xpHeadOk}`);
let p7ok = false;
if (byId['p7s']) {
  const before = tableRows(xpTable.innerHTML);
  byId['p7s'].fire('input', '80');
  const after = tableRows(xpTable.innerHTML);
  console.log(`p7 start% slider    : ${before} rows -> ${after}`);
  p7ok = after < before;
}

const ok = app.children.length === 7 && charts.length === 7
  && charts.every(c => c.points > 0) && s1 && s3 && s4 && triOk && xpOk
  && p4ok && xpHeadOk && p7ok;
console.log('\nRESULT:', ok ? 'ALL PANELS RENDER, ALL FILTERS WORK' : 'INCOMPLETE');
process.exit(ok ? 0 : 1);
