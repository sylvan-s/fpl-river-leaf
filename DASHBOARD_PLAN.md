# Multipage dashboard — plan, logged before the build

Created Sun 9 Aug 2026. Logged before writing code, following the B6 precedent
in `METHODOLOGY_ALTERNATIVES.md`: the plan is recorded so the build can be
judged against what it set out to do, not against what it turned out to be.

**Nothing here is built yet.** The current dashboard is the single-page
diagnostic set, which becomes page 2 of this structure largely unchanged.

---

## The decision that shapes everything else: where squad state lives

Today the live squad is recorded in **five** places:

| # | Location | Form |
|---|---|---|
| 1 | `TEAM_CHANGE_LOG.md` CURRENT STATE | prose |
| 2 | `CURRENT_SQUAD` / `BANK` in `optimise_squad.py` | Python literal |
| 3 | `SQUAD` in `build_dashboard.py` | Python literal |
| 4 | `SQ` in `fixture_adjust.py` | Python literal |
| 5 | chip status in `TEAM_CHANGE_LOG.md` CHIP STRATEGY | prose |

The weekly brief already carries a standing warning to update 1–4 together, and
**#4 was found stale on 9 Aug 2026** — listing a player transferred out two
changes earlier, because nothing had exercised `--squad` since.

A pitch page needs all of it: the fifteen, the formation, the bank, the chips.
**Adding a sixth copy would be the wrong move.** Instead:

> **`squad.json` becomes the single machine-readable source of truth.**
> `optimise_squad.py`, `build_dashboard.py` and `fixture_adjust.py` all read it
> instead of holding literals. `TEAM_CHANGE_LOG.md` stays the human narrative
> and the append-only history; `squad.json` is the current state it describes.

Schema, first cut:

```json
{
  "updated_utc": "...", "gameweek": 1, "bank": 0.5,
  "squad": [{"name":"Raya","pos":"GKP","team":"ARS","price":6.0,
             "bought_for":6.0,"role":"XI","bench_order":null}],
  "captain": "B.Fernandes", "vice": "Mbeumo",
  "chips": {"set1": {"expires":"2027-01-02T13:30Z",
                     "wildcard":"available","freehit":"available",
                     "benchboost":"available","triplecaptain":"available"},
            "set2": {...}}
}
```

**This is a prerequisite for page 1, and worth doing even if the dashboard is
never built.** It retires a known, recurring failure mode.

---

## Architecture

### Pages, one HTML file each, in `docs/`

```
docs/index.html      1. Squad
docs/analysis.html   2. Player analysis  (the current dashboard)
docs/player.html     3. Player timeseries (?id=)
docs/workflow.html   4. Weekly workflow
docs/news.html       5. Availability & intel
docs/data/*.json     shared data, fetched
```

### The self-contained-file question

The current page inlines all its data, which is what makes it robust — it opens
from anywhere with no server. **Five pages cannot each inline a 166KB blob**,
and the timeseries data is far larger again.

**Proposal: split the difference.**

- Pages **1, 2, 4** stay self-contained and inline their own (small) data. They
  remain openable as local files, and page 2 keeps exactly the property it has
  today.
- Pages **3 and 5** fetch from `docs/data/`. They will only work over `http(s)`,
  i.e. on Pages, not `file://`.

That boundary is deliberate: the pages that must never break are the ones that
carry decisions; the pages that can require a server are the exploratory ones.

**Consequence to accept:** `python3 -m http.server` becomes the local preview
command for pages 3 and 5. Document it or it will be rediscovered painfully.

### Verification — non-negotiable

`verify_dashboard.js` exists because a syntax error in the inline script leaves
the HTML looking complete, the right size, and rendering **nothing**. That risk
multiplies by five here.

- Extend the harness to **loop over every page**, asserting each panel builds
  with non-empty data.
- Keep the CDN assertion from `publish_dashboard.sh` **per page** — the blank
  render caused by a blocked Chart.js is invisible to a stubbed-DOM check.
- `publish_dashboard.sh` should refuse to publish if **any** page fails.

---

## Page 1 — Squad

**Purpose:** answer "what do I own, what is it worth, and what is it projected
to do" in one screen, without reading a table.

### Header strip

| Metric | Source |
|---|---|
| Squad value · bank · total | `squad.json` |
| **XI xP/90** and **XI xP/GW** | `optimise_squad.py` objective + start-weighted |
| Expected blanks in the XI | Poisson-binomial, `size_bench_value.py` |
| Bench autosub value | `size_bench_value.py` |
| Chips deployed / remaining | `squad.json`, with **set-1 expiry countdown** |
| Deadline countdown | `get_deadline` |

Showing **both** xP/90 and xP/GW is the point, not clutter: the gap is the
availability haircut (**11% on the current squad**), and putting it on screen
makes A0.5 in the roadmap self-evidently necessary.

### Pitch

Formation-accurate, XI plus four bench in order. Each player as a card:

- name · club · position · price
- **start%**, with the source flagged (`last16` vs `season_fallback`)
- **xP_adj** over the window
- a **four-fixture ticker**, coloured by ATT× for attackers and DEF× for
  defenders and keepers — *these are different scales and must not share a
  colour legend*
- badges: captain, vice, penalty taker, **contaminated prior**, injury/suspension

### "Expected goals over the next 4 games" — a clarification

The system does not currently project goals; it projects **points** (`xP_adj`),
and `xp_adj_win = xp_adj × games` is the four-gameweek total. Underlying
**xGI/90** exists per player and can be shown alongside.

**Recommend showing xP for the window** as the headline, with xGI as a
secondary column — mixing them invites the exact unit error recorded in
`size_bench_value.py`.

### Alternative formations

Two alternatives beside the current squad, identical card format, each with a
delta bar against the current:

- **Same fifteen, different XI** — the free decision. Bench order and formation
  only, no transfer. This is genuinely free and is currently invisible.
- **One transfer** — the optimiser's recommendation, shown *with* its bench
  consequence, not just the XI gain.

### DECIDED 9 Aug 2026 — publish it, and change the design accordingly

**Publish page 1, squad and alternatives included.** Rationale: these are not
heavy competitive secrets, and there is more value in Dylan seeing the
analytical approach than there is edge in hiding it. He may find it
interesting; he may not; that is a better bet than a marginal points advantage
in a two-player league.

**This is not merely a permission — it changes what the page should be.** If
the audience is someone learning, then a state dump is the wrong artefact. The
page has to make the *reasoning* legible, not just the outcome:

1. **Every player carries his reason.** `squad.json` now holds `selected_on`
   per player, mirroring TEAM_CHANGE_LOG's "Selected on" column, so the card
   can say *why* — "below the 75% starts line, so he cannot start, but he is
   the most valuable autosub in the squad" — rather than only *what*.
2. **Show what was rejected, not only what was picked.** The gates are the
   interesting part. A panel showing how 700-odd players become 267 become 15,
   with the count falling at each gate, teaches more than the final fifteen.
3. **Alternatives become a teaching device**, not just an options list: the
   same £100m spent three ways, with the cost of each difference named.
4. **Link the jargon.** `GLOSSARY.md` exists; xGI, CBIT, delta and xP_adj
   should all be hoverable rather than assumed.
5. **Do not hide the uncertainty — it is the best lesson on the page.**
   Lacroix starts on a Crystal Palace start rate and Dubravka is a bench keeper
   on a Burnley one. Showing "this number is not what it appears to be, and
   here is how we caught it" is more instructive than a page that looks
   authoritative. The contamination flags should be prominent, not tucked away.

The honest-about-limits framing also happens to be the project's actual
character, so the page will be truer for it.

---

## Page 2 — Player analysis

The existing seven-panel diagnostic set, moved to `analysis.html`, essentially
unchanged. Additions:

- shared nav
- every player name becomes a **link to page 3**
- contamination badges wherever a player is named

---

## Page 3 — Player timeseries

**The largest piece of new work, because it needs data the project does not
hold.**

### Data sources

| Season | Source | Notes |
|---|---|---|
| 2025/26 | [`vaastav/Fantasy-Premier-League`](https://github.com/vaastav/Fantasy-Premier-League) | already the source for `last16_starts.json`, but only the aggregate is kept |
| 2026/27 | FPL API `element-summary/{id}/` | via the MCP or the SQLite cache's `player_gw` table |

**`player_gw` holds only the current season and is empty pre-season**, so
2026/27 populates naturally from GW1. Last season must be vendored.

### Metrics per gameweek

minutes · started · points · goals · assists · **xG · xA · xGI** · CBIT/CBIRT ·
clean sheet · goals conceded · xGC · bonus · BPS · price · opponent · H/A ·
**fixture difficulty at the time**

The last one matters: a flat return against Liverpool away is not the same
observation as a flat return at home to a promoted side, and a raw timeseries
that omits it invites the wrong read.

### Size — the constraint that decides the design

~700 players × 38 gameweeks × ~15 metrics. **One file per player**
(`docs/data/players/{id}.json`), fetched on click. Never one large blob.

An index file carries names, ids, clubs and positions for search.

### Overlays worth having

- **xGI vs actual returns**, cumulative — this is the delta method made visual,
  and shows *when* a player's over- or under-performance accrued rather than
  just its season total
- **rolling 5-GW minutes**, which is what a start rate is trying to summarise
- a **club-change marker** where known, since a timeseries spanning a transfer
  is two different populations on one axis

---

## Page 4 — Weekly workflow

`WEEKLY_WORKFLOW.svg` exists. This page wraps it and makes it navigable:

- each step links to the page or file it describes
- the current position in the week is highlighted from the deadline countdown
- gates due this gameweek (roadmap step 2e) surface inline

Cheapest page to build. Reasonable place to start to prove the shared nav,
CSS and verify harness before committing to page 3.

---

## Page 5 — Availability & intel

**Do not build a new data store. Render `ROLE_INTEL.md`**, which already has
the required discipline: dated, sourced, falsifiable, deleted after ~5
gameweeks if unproven.

That means adding machine-readable blocks to `ROLE_INTEL.md` alongside the
existing ```` ```setpieces ```` and ```` ```contaminated ```` fences, rather
than parsing prose.

Status chips per player:

| Chip | Source |
|---|---|
| Available / Doubtful / Injured / Suspended | FPL status flag + `chance_of_playing_next_round` |
| **Suspension risk** | yellow-card count vs 5 / 10 / 15 thresholds |
| **Contaminated prior** | `contaminated` block in `ROLE_INTEL.md` |
| Role change | `ROLE_INTEL.md` narrative entries |
| Internal competition | `ROLE_INTEL.md`; needs a new fenced block |
| Set-piece / penalty duty | existing `setpieces` block |

Each chip shows **date, source, and its falsifiable check**. A chip without a
check is a rumour with styling.

**This page is the most useful one right now**, because contamination is live:
Lacroix starts the XI on a Palace start rate, and Dubravka is a bench keeper on
a Burnley start rate who is reported as backup at Spurs.

---

## Look and feel

- Keep the existing dark palette; `make_artifact.py` already produces the light
  variant for Cowork and that split should survive.
- One shared `docs/style.css`. The current CSS is inlined in `template.html`;
  extracting it is a prerequisite for consistency across five pages.
- Charts stay **Chart.js 4.5.0 from the pinned jsdelivr URL with its integrity
  hash** — any other CDN silently blanks the Cowork artifact.
- Mobile matters: Dylan will open this on a phone. The pitch view should stack;
  wide tables should scroll rather than shrink.

---

## Suggested order

1. **`squad.json`** + repoint the three Python files. Independent value, retires
   a live failure mode.
2. **Extract shared CSS and nav; build page 4.** Cheapest page, proves the
   scaffolding, extends the verify harness while the surface is small.
3. **Page 5.** Highest current value, needs no new external data.
4. **Page 1.** Depends on step 1. Decide the publishing question first.
5. **Page 3.** Largest, needs the vaastav pipeline. Do last, and note that this
   season's half of it fills in on its own from GW1.

## Open questions

- ~~Publish page 1 at all?~~ **Decided 9 Aug 2026: yes** — see the squad page
  section. The reason changes the design, not just the permission.
- Vendor the 2025/26 vaastav data into the repo, or fetch at build time? In
  repo is reproducible and offline-safe but adds megabytes; fetching is light
  but makes the build network-dependent and silently stale.
- Does page 2 stay self-contained, or join the shared-data model? Recommend it
  stays — it is the page that currently works.

## Progress

| Step | State |
|---|---|
| 1 · `squad.json` + repoint three files | **done** — `c211ba3` |
| 2 · Shared CSS/nav, workflow page, per-page verify | **done** — `7f80bc8` |
| 3 · Page 5, availability & intel | not started |
| 4 · Page 1, squad | unblocked by the 9 Aug decision |
| 5 · Page 3, player timeseries | not started; needs the vaastav pipeline |
