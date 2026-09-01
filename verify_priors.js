// Deep verification for docs/priors.html — the one page whose data is FETCHED.
//
//     node verify_priors.js
//
// WHY THIS FILE EXISTS. Every other page carries its numbers inline, so
// verify_pages.js's "the inline script parses" is close to "the page works":
// the data is right there in the file it just checked. priors.html stopped
// working that way on 1 Sep 2026 (docs/adr/0002) — it is now a static shell
// that fetches docs/data/priors_payload.json at load. A script that parses
// perfectly and then throws on the first line of render(), or fetches a path
// that 404s, produces a page that is structurally sound by every check
// verify_pages.js knows how to make, and blank in a browser.
//
// So this file does what that one cannot: it RUNS the page's script against a
// stubbed DOM and a real payload, and asserts panels actually got built —
// the same trade verify_dashboard.js makes for the diagnostics page.
//
// THREE BRANCHES, ALL THREE CHECKED. The success path is the one that matters
// weekly, but the other two are the ones nobody notices breaking: the
// empty-state path only runs between seasons, and the fetch-failure path only
// runs when something is already wrong — which is exactly when a broken error
// handler costs the most.
const fs = require('fs'), path = require('path'), vm = require('vm');

const HERE = __dirname;
const PAGE = path.join(HERE, 'docs', 'priors.html');
const PAYLOAD = path.join(HERE, 'docs', 'data', 'priors_payload.json');
const SNAPSHOT = path.join(HERE, 'docs', 'data', 'priors_player_snapshot.json');

let failures = 0;
const t = (name, ok, got) => {
  console.log((ok ? ' ok  ' : 'FAIL ') + name + (ok ? '' : `  <- ${got}`));
  if (!ok) failures++;
};

for (const f of [PAGE, PAYLOAD]) {
  if (!fs.existsSync(f)) {
    console.log(`FAIL missing ${path.relative(HERE, f)} — run build_prediction_tracker.py first`);
    process.exit(1);
  }
}

const html = fs.readFileSync(PAGE, 'utf8');
const code = [...html.matchAll(/<script(?![^>]*\bsrc=)[^>]*>([\s\S]*?)<\/script>/g)]
  .map(m => m[1]).join('\n');
const payload = JSON.parse(fs.readFileSync(PAYLOAD, 'utf8'));
const snapshot = fs.existsSync(SNAPSHOT)
  ? JSON.parse(fs.readFileSync(SNAPSHOT, 'utf8')) : { rows: [] };

// --- the smallest DOM the page can be fooled by -----------------------------
function run(fetchImpl) {
  const appended = [];
  const mk = id => ({
    id, innerHTML: '', textContent: '', className: '', dataset: {}, style: {},
    appendChild(c) { appended.push(c); },
    addEventListener() {}, querySelectorAll: () => [], closest: () => null,
  });
  const els = { app: mk('app') };
  const sb = {
    console, Object, Math, String, Number, Promise, Error, Infinity, JSON,
    Chart: function () { return {}; },
    getComputedStyle: () => ({ getPropertyValue: () => '#000' }),
    document: {
      documentElement: {}, createElement: mk, querySelectorAll: () => [],
      getElementById: id => (els[id] = els[id] || mk(id)),
    },
    fetch: fetchImpl,
  };
  sb.Chart.defaults = { color: '', borderColor: '', font: {} };
  sb.window = sb;
  // In a real browser every element with an id is also a global — that is how
  // the page reaches `cWeight` to build the chart. Without this the success
  // path dies on a ReferenceError and the .catch() quietly swallows it.
  const ctx = vm.createContext(new Proxy(sb, {
    has: () => true,
    get: (o, k) => k in o ? o[k]
      : (k === 'Symbol' ? undefined : (els[k] = els[k] || mk(String(k)))),
  }));
  new vm.Script(code).runInContext(ctx);
  return { els, appended };
}

// Every URL the page asks for, recorded — so a rename that the substring
// match below would happily keep serving still gets caught.
const asked = [];
const both = (p, s) => u => {
  asked.push(u);
  return Promise.resolve({ ok: true, json: () => Promise.resolve(u.includes('payload') ? p : s) });
};

console.log('Deep verification: docs/priors.html (fetched-data page)\n');

// 1. the weekly path — real payload, real snapshot, panels must appear
const live = run(both(Object.assign({}, payload, { empty_state: null }), snapshot));
// 2. genuinely between seasons — no finished gameweeks at all, not even cached
const idle = run(both(Object.assign({}, payload, {
  finished: [], weeks: {}, empty_state: 'no finished gameweeks',
}), { rows: [] }));
// 3. THE BUG THIS CAUGHT, 1 Sep 2026. A live fetch failing must not hide good
// cached data — empty_state is a diagnostic string set on ANY fetch failure,
// even when `finished` still holds a full season of real weeks (exactly what
// shipped the first time: no httpx in the build environment, real GW1 data
// underneath). Synthesized rather than reused from the committed payload
// unmodified — that payload's own empty_state clears back to null the next
// time a live refresh succeeds, which would silently stop this branch from
// testing anything at all.
const stale = run(both(Object.assign({}, payload, {
  empty_state: 'synthetic: live fetch failed, showing last cached build',
}), snapshot));
// 4. the JSON is missing or unreachable (the file:// case, and a bad deploy)
const dead = run(() => Promise.resolve({ ok: false, status: 404, json: () => Promise.resolve({}) }));

setTimeout(() => {
  const ids = r => r.appended.map(c => c.id).join(',');

  t('success: builds all three panels', ids(live) === 'p1,p2,p3', ids(live) || '(none)');
  t('success: player table populated',
    (live.els.pBody.innerHTML.match(/<tr>/g) || []).length > 0, '0 rows');
  t('success: sortable header rendered', /data-key="weight"/.test(live.els.pHead.innerHTML), 'no headers');
  t('success: weight chart constructed', !!live.els.cWeight, 'canvas never touched');
  t('success: subtitle stamped from payload',
    /data generated /.test(live.els.subMeta.textContent), live.els.subMeta.textContent || '(empty)');
  t('success: no error panel', !live.els.app.innerHTML.includes('Data not loaded'),
    'fell into the catch branch');
  t('success: no stale-data banner when empty_state is null',
    !live.els.app.innerHTML.includes('Showing last saved data'), 'banner shown with nothing stale');

  t('empty state: waiting panel only', ids(idle) === 'waiting', ids(idle) || '(none)');
  // pBody is never even looked up on this branch, so absent is the pass.
  t('empty state: no player table built', !(idle.els.pBody || {}).innerHTML, 'table built anyway');

  t('stale-but-cached: does NOT fall back to the waiting panel',
    ids(stale).includes('p1') && ids(stale).includes('p3'), ids(stale) || '(none)');
  t('stale-but-cached: player table still populated',
    (stale.els.pBody.innerHTML.match(/<tr>/g) || []).length > 0, '0 rows — real data got hidden');
  // panel()/the warning div both go through appendChild, not app.innerHTML=
  // (that assignment form is only used by the fetch-failure catch branch) —
  // so look at what was actually appended, the same way ids() does.
  const staleNote = stale.appended.find(c => c.id === 'stale');
  t('stale-but-cached: shows a note that the fetch failed',
    !!staleNote && staleNote.innerHTML.includes('Showing last saved data'),
    staleNote ? 'wrong copy' : 'no stale-data warning appended');

  t('fetch failure: explains itself', dead.els.app.innerHTML.includes('Data not loaded'),
    dead.els.app.innerHTML.slice(0, 120) || '(blank)');
  t('fetch failure: names the file:// cause and the fix',
    dead.els.app.innerHTML.includes('file://') && dead.els.app.innerHTML.includes('http.server'),
    'error copy no longer tells the reader what to do');

  // Fetching a path that does not exist on disk is the failure mode with no
  // local symptom at all: the build succeeds, the script parses, and the
  // deployed page is blank. Check the page asks for files actually shipped.
  const wanted = [...new Set(asked)].sort();
  t('fetches exactly the two data files it ships',
    wanted.join(' ') === 'data/priors_payload.json data/priors_player_snapshot.json',
    wanted.join(' ') || '(fetched nothing)');
  for (const u of wanted) {
    t(`  ${u} exists in docs/`, fs.existsSync(path.join(HERE, 'docs', u)), 'not on disk');
  }

  // The whole point of the split: the HTML must not carry the numbers.
  t('shell carries no inlined payload', !/const DATA\s*=\s*\{/.test(html),
    'const DATA is back in the HTML — the weekly diff is back too');
  t('shell stays small', Buffer.byteLength(html) / 1024 < 40,
    `${(Buffer.byteLength(html) / 1024).toFixed(0)} KB`);

  console.log('\nRESULT:', failures === 0
    ? 'priors.html RENDERS FROM FETCHED DATA'
    : `${failures} FAILURE(S)`);
  process.exit(failures === 0 ? 0 : 1);
}, 200);
