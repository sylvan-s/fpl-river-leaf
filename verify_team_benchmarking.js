// Execute the Team Benchmarking page's script against a minimal DOM + Chart stub.
// Syntax checking alone missed a fatal parse error on the player-page sibling
// once (see verify_player_benchmarking.js); this actually RUNS this page's
// script too, rather than assuming a shared bug class can't recur here.
const charts = [];
global.Chart = function (cv, cfg) {
  charts.push({ canvas: cv && cv.id, type: cfg.type, datasets: (cfg.data.datasets || []).length,
                points: (cfg.data.datasets || []).reduce((a, d) => a + (d.data ? d.data.length : 0), 0) });
  (cfg.data.datasets || []).forEach(d => {
    if (d.data[0]) {
      const cb = cfg.options?.plugins?.tooltip?.callbacks;
      if (cb?.label) cb.label({ raw: d.data[0], label: '0' });
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
  return { canvas: cv && cv.id, config: cfg, data: cfg.data, options: cfg.options, update(){} };
};
Chart.defaults = { color: '', borderColor: '', font: {} };

// A panel's innerHTML carries a `<canvas id="c4">` (or c6) that panel()
// never separately creates an element for — the real page relies on the
// browser parsing that markup into a live element the later `new
// Chart(c4, ...)` call can reference as a bare global. Mirror that here by
// scanning for canvas ids on assignment, same as verify_player_benchmarking.js.
const made = {};
function mkEl(id) {
  const el = { id, style: {}, children: [],
    set innerHTML(v) { this._h = v; (v.match(/<canvas id="([^"]+)"/g) || []).forEach(m => {
        const cid = m.match(/id="([^"]+)"/)[1]; made[cid] = { id: cid }; global[cid] = made[cid]; }); },
    get innerHTML() { return this._h; },
    set textContent(v) { this._t = v; }, get textContent() { return this._t; },
    appendChild(c) { this.children.push(c); },
    addEventListener() {}, querySelectorAll: () => [] };
  return el;
}
const app = mkEl('app'), sub = mkEl('sub'), foot = mkEl('foot');
global.document = {
  createElement: () => mkEl(''),
  getElementById: id => ({ app, sub, foot }[id] || made[id] || mkEl(id)),
  querySelectorAll: () => [],
  documentElement: {}
};
global.getComputedStyle = () => ({ getPropertyValue: () => '#000' });
global.window = global;

try {
  require('./dash_team.js');
} catch (e) {
  console.log('RUNTIME ERROR:', e.message); process.exit(1);
}
console.log('panels rendered :', app.children.length);
console.log('charts created  :', charts.length);
charts.forEach(c => console.log(`   ${String(c.canvas).padEnd(5)} ${c.type.padEnd(8)} ${c.datasets} datasets, ${String(c.points).padStart(3)} points`));
console.log('header text     :', (sub.textContent || '').slice(0, 70) + '...');

// Panel 5 (fixtures): one point per club, no filters to drive here.
const p5 = charts.find(c => c.canvas === 'c4');
const p5ok = !!p5 && p5.points > 0;
console.log(`fixtures            : ${p5 ? p5.points : 0} clubs plotted`);

// Panel 8 (xGC vs CS per club): one point per club, no filters to drive.
const p8 = charts.find(c => c.canvas === 'c6');
const p8ok = !!p8 && p8.points > 0;
console.log(`xGC vs CS per club  : ${p8 ? p8.points : 0} clubs plotted`);

const ok = app.children.length === 2 && charts.length === 2 && p5ok && p8ok;
console.log('\nRESULT:', ok ? 'ALL PANELS RENDER' : 'INCOMPLETE');
process.exit(ok ? 0 : 1);
