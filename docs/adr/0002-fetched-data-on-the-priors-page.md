# 0002. Fetched data on the priors page

**Status:** Accepted for `docs/priors.html` only — a deliberate, scoped reversal
of the "self-contained outputs" rule that `page_shell.py` states and every other
page still follows.

**Logged:** 1 Sep 2026. Pilot conversion; the other five pages are unchanged and
no decision has been taken about them.

## Context

Starting ask: can a Claude artifact be embedded in the dashboard by iframe, so
that refreshed player data doesn't mean rebuilding HTML every week? No — an
artifact is hosted on claude.ai, default-private, and framing-restricted, and it
would not have helped anyway: an artifact is also a static published page, so
new data means republishing it. Same weekly work, plus a dead embed.

That reframed the actual problem. The weekly rebuild is not a rendering cost, it
is a **coupling** cost: `build_prediction_tracker.py` emitted the page as an
f-string with `const DATA = {json.dumps(payload)}` inlined, so `docs/priors.html`
was 256 KB of mostly numbers, and every data refresh rewrote the whole file. The
layout and the numbers shared a lifecycle for no reason other than how the
builder happened to be written. `docs/data/` already existed and already held
`priors_player_snapshot.json` — the data was *already* split; the page just
wasn't reading it.

The rule this collides with is real and load-bearing, from `page_shell.py`:

> The pages that carry decisions must keep working when opened straight off
> disk, so the build INLINES the shared source into each page.

That is why the CSS is inlined rather than linked, and the same reasoning covers
data. `fetch()` cannot run on a `file://` URL in any current browser, so
splitting the data means this page stops working off disk. Permanently, not as a
bug to be fixed later.

## Decision

Split `docs/priors.html` into a static shell plus fetched JSON, accepting the
loss of off-disk operation **for this page**.

- `build_prediction_tracker.py` writes `docs/data/priors_payload.json` (panels 1
  and 2: `finished`, `weeks`, `metric_labels`, `empty_state`, `generated`).
- The page fetches that, plus the already-existing
  `priors_player_snapshot.json` for panel 3. The payload deliberately does not
  carry a second copy of the snapshot's ~180 KB.
- The emitted HTML is now 17 KB and depends on the layout and the JS only. A
  data-only refresh leaves it **byte-identical** — verified by building twice
  and comparing checksums.
- The generated stamp and "through GW n" moved out of the build-time subtitle
  and are filled client-side from the payload, because a data-dependent
  subtitle would have put the file back in the weekly diff for two facts.
- `verify_priors.js` is new and runs in `publish_dashboard.sh`.

## Why this page and not the others

`priors.html` was the extreme case on both axes: the largest file (256 KB, ~10x
the next page) and the one whose contents change most mechanically week to week.
It also has the weakest claim on off-disk operation — it is a *tracker*, read to
watch a trend accumulate over a season, not a page consulted under time pressure
at a deadline. `index.html` (the squad page) is the opposite on that last point
and should probably keep inlining regardless of what this pilot shows.

## Consequences

**Accepted cost.** `docs/priors.html` opened as `file://` will never render its
panels again. It fails *loudly* rather than blankly: the catch branch prints a
panel naming `file://` as the cause and `python3 -m http.server` as the fix.
Locally: `(cd docs && python3 -m http.server)`.

**New failure mode, and the guard for it.** Inlined data made
`verify_pages.js`'s "the inline script parses" nearly equivalent to "the page
works" — the data was in the file it had just checked. That equivalence is now
broken for this page: a mistyped fetch path, or a `render()` that throws on its
first line, passes every structural check and deploys blank. There is no local
symptom at all. Hence `verify_priors.js`, which runs the page's script against a
stubbed DOM and a real payload and asserts the panels get built, that the two
URLs it requests are files that actually ship, and that `const DATA` has not
crept back into the HTML. All three branches are covered — success, empty-season,
and fetch-failure — the latter two being the ones nobody notices breaking. The
checks were mutation-tested: renaming the payload path, breaking `render()`, and
gutting the error copy each fail it.

**Not addressed.** Whether the other five pages follow. That needs the squad
page's off-disk requirement taken seriously as its own question, not settled by
this precedent.
