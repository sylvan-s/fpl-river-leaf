// Structural verification across EVERY built page.
//
//     node verify_pages.js
//
// WHAT THIS IS FOR. verify_player_benchmarking.js and verify_team_benchmarking.js
// each run one page's script and assert its panels and filters behave. That is
// deep, and it is specific to that page. This file is the opposite: shallow
// checks applied to ALL pages, so that adding a page cannot quietly skip
// verification.
//
// THE FAILURE IT GUARDS. A page whose Chart.js tag drifts off the pinned
// jsdelivr URL renders COMPLETELY BLANK while every local check passes, because
// stubbed-DOM verification never fetches anything. That bug has already been
// paid for once. With seven pages the surface for it is seven times larger, and
// it is invisible in the one place you would look — the HTML looks complete and
// the file size looks right.
const fs = require('fs'), path = require('path'), vm = require('vm');

const DOCS = path.join(__dirname, 'docs');
const CHARTJS = 'https://cdn.jsdelivr.net/npm/chart.js@4.5.0/dist/chart.umd.js';
const INTEGRITY = 'sha384-iU8HYtnGQ8Cy4zl7gbNMOhsDTTKX02BTXptVP/vqAWIaTfM7isw76iyZCsjL2eVi';

// page file -> minimum plausible size. A page that builds but emits almost
// nothing is a failure that no syntax check catches.
const PAGES = [
  { file: 'index.html',              minKB: 10 },   // squad page — the landing page
  { file: 'player-benchmarking.html', minKB: 150, deep: 'player-benchmarking' },
  { file: 'team-benchmarking.html',   minKB: 8,   deep: 'team-benchmarking' },
  { file: 'relationships.html',      minKB: 80 },   // shares build_dashboard.py's payload
  { file: 'news.html',               minKB: 8 },
  { file: 'player.html',             minKB: 20 },
  { file: 'priors.html',             minKB: 8 },   // sits in a "waiting for GW1" empty state pre-season
];

let failures = 0;
const fail = (f, msg) => { console.log(`   FAIL  ${f}: ${msg}`); failures++; };

console.log('Structural checks across built pages\n');

for (const p of PAGES) {
  const full = path.join(DOCS, p.file);
  if (!fs.existsSync(full)) { fail(p.file, 'not built'); continue; }
  const h = fs.readFileSync(full, 'utf8');
  const kb = Buffer.byteLength(h) / 1024;
  const checks = [];

  checks.push(['size', kb >= p.minKB, `${kb.toFixed(0)} KB (min ${p.minKB})`]);
  checks.push(['chart.js pinned', h.includes(CHARTJS), 'exact jsdelivr URL']);
  checks.push(['integrity hash', h.includes(INTEGRITY), 'SRI attribute intact']);

  const navs = (h.match(/<nav class="top">/g) || []).length;
  checks.push(['shared nav', navs === 1, `${navs} nav blocks`]);
  const active = (h.match(/data-page="[a-z]+" class="on"/g) || []).length;
  checks.push(['one active tab', active === 1, `${active} marked active`]);

  checks.push(['no placeholders left',
    !/__[A-Z0-9_]+__/.test(h.replace(/\/\*__DATA__\*\//g, '')),
    'template markers substituted']);

  // Every inline script must PARSE. A syntax error anywhere kills the whole
  // page silently; the HTML still looks complete.
  const scripts = [...h.matchAll(/<script(?![^>]*\bsrc=)[^>]*>([\s\S]*?)<\/script>/g)];
  let parsed = true, why = `${scripts.length} inline script(s)`;
  for (const [, code] of scripts) {
    if (!code.trim()) continue;
    try { new vm.Script(code); } catch (e) { parsed = false; why = e.message; break; }
  }
  checks.push(['inline scripts parse', parsed, why]);

  const bad = checks.filter(c => !c[1]);
  console.log(`${bad.length ? 'FAIL' : ' ok '}  ${p.file.padEnd(15)} ` +
              checks.map(c => `${c[0]}${c[1] ? '' : ' ✗'}`).join(' · '));
  bad.forEach(c => fail(p.file, `${c[0]} — ${c[2]}`));
}

console.log('\nDeep verification (page-specific) is verify_player_benchmarking.js and');
console.log('verify_team_benchmarking.js, run separately by publish_dashboard.sh.');
console.log('\nRESULT:', failures === 0 ? 'ALL PAGES STRUCTURALLY SOUND' : `${failures} FAILURE(S)`);
process.exit(failures === 0 ? 0 : 1);
