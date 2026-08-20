# Intel sweep — the daily community-research pipeline

Created 20 Aug 2026. Governs `fpl-daily-intel-sweep`, the scheduled task that
replaced the ad-hoc Friday-only `fpl-pre-deadline-news-watch`.

**Why this exists.** `ROLE_INTEL.md` has always required a date, a source and
a falsifiable check for every entry — but the gathering itself was manual and
weekly, riding inside `fpl-weekly-brief`. That meant two gaps: news that broke
Sunday–Thursday waited for Friday to get logged, and no source's track record
was ever measured — "Fantasy Football Scout said X" and "some podcast said Y"
carried equal weight the moment either was written down. This closes both:
daily, structured gathering, plus a closed loop that scores each source
against what actually happened. See `SELECTION_FRAMEWORK.md`'s reconciliation
rules and `score_calibration()` for the same discipline applied elsewhere —
this is that pattern, applied to intel sources instead of captaincy calls.

**This is not C3.** `METHODOLOGY_ALTERNATIVES.md` Tier C rejected "automated
ROLE_INTEL" because scraping consensus into the file without a human checking
it trades falsifiability for convenience. This pipeline keeps every rule C3
was protecting — dated, sourced, falsifiable, expiring — and only automates
the frequency and the record-keeping, not the judgement.

**Hard rule, set by Sylvan 20 Aug 2026: intel never informs player-selection
data automatically, full stop.** The daily sweep gathers, logs and drafts
narrative notes only. Nothing reaches `ROLE_INTEL.md`'s machine-readable
`setpieces`/`adjustments` fences — the code blocks `intel_adjust.py` parses,
which feed `build_squad.py`/`optimise_squad.py` and therefore actual
selection — without Sylvan explicitly accepting it in the weekly
`fpl-friday-intel-review` meeting. Corroboration across sources is evidence
he can weigh in that meeting; it is no longer, by itself, a promotion
trigger the pipeline can act on unattended.

---

## Sources, by tier

Same tiers as the reliability README already used informally; now the
authoritative list.

**Tier 3 — named journalism / analytics outlets.** Fantasy Football Scout,
RotoWire, Il Margine, ESPN, OneFootball, official club channels (e.g.
Arsenal.com's FPL Focus column), and general sports press (Yahoo, Sports
Mole, CaughtOffside and similar) when a press-conference quote is being
reported directly.

**Tier 4 — community creator consensus.** Let's Talk FPL (Andy Martin), FPL
Focal, FPL Mate, FPL Harry, Big Man Bakar, FPL Fran, The FPL Wire, FPL
Blackbox.

Both tiers are logged and scored on the same scale, deliberately — the
scorecard exists to let the data say which sources are actually reliable
rather than assuming Tier 3 outranks Tier 4 by construction. A source outside
this list can still be logged (e.g. a specific penalty-footage clip, a
manager's direct quote) — tag it with the most accurate `source_name` and add
it to this list next time it recurs.

**Not in scope here:** Understat/FBref xGI numbers and `fantasy.premierleague.
com/news` — those feed the weekly brief's delta calculation directly and are
not "intel" in the falsifiable-hypothesis sense this pipeline logs.

---

## What the daily sweep does

0. **Record a start timestamp** — `started_utc`, ISO 8601 UTC, captured
   before any reading or searching begins. Needed for the run-metadata
   record in step 4.

1. **Check open bites first.** Read `docs/data/intel_sweep_log.jsonl`,
   filter to bites with no resolution record, and for any whose
   `falsifiable_check` can be evaluated now (team news, `injury_report`,
   confirmed lineups, `penalties_order` once populated), append a
   `resolution` record — `confirmed`, `contradicted`, `expired` (the
   `check_by_gw` window passed with no evidence either way), or
   `superseded` (a later, better-sourced finding replaced the question).
   **Never edit or delete a bite or an existing resolution** — append-only,
   same rule `fpl_calibration_log.jsonl` enforces, for the same reason: a
   record that can be revised after the outcome is worthless.

2. **Sweep for new findings.** Web search across the Tier 3/4 sources above
   for anything about River Leaf FC's 15, the standing watchlist in
   `ROLE_INTEL.md`, and general set-piece/rotation/injury news. For each
   genuinely new, actionable claim, append a `bite` record:

   ```json
   {"kind": "bite", "id": "<player>-<team>-<field>-<YYYYMMDD>-<n>",
    "date": "2026-08-21", "source_name": "Fantasy Football Scout",
    "source_tier": 3, "source_url": "https://...",
    "player": "Szoboszlai", "team": "LIV", "category": "setpiece",
    "hypothesis": "one sentence, the claim itself",
    "field_affected": "xg90", "suggested_op": "mult",
    "suggested_value": 1.35, "confidence": "high",
    "falsifiable_check": "who takes LIV's first penalty",
    "check_by_gw": 8, "logged_utc": "2026-08-21T07:05:00Z"}
   ```

   `category` is one of `setpiece · injury · rotation · tactical ·
   manager_change · other`. `field_affected`/`suggested_op`/`suggested_value`
   use the same vocabulary as `ROLE_INTEL.md`'s `adjustments` fence
   (`intel_adjust.py`'s `MULT_FIELDS`/`SET_FIELDS`) — leave them null if the
   finding doesn't map to a specific model input yet. **A restated screen
   finding is not a bite** — reconciliation rule 7 in `ROLE_INTEL.md` still
   applies: value comes only from what the data cannot already see.

3. **Draft into `ROLE_INTEL.md` — narrative only.** Every new bite gets a
   one- or two-line entry under "Active intel", dated and sourced, exactly as
   the file's existing entries already look, marked `?` if unconfirmed and
   noted as "pending Friday review". **The daily sweep never writes to the
   `setpieces` or `adjustments` fences, regardless of how well-corroborated a
   finding is.** That gate only opens in the Friday review, below.

4. **Record run metadata, then commit — every day, even a quiet one.**
   Immediately before committing, append one `run_meta` line to
   `docs/data/intel_sweep_log.jsonl` (same append-only file, new `kind`,
   never edited or deleted like every other record here):

   ```json
   {"kind": "run_meta", "date": "2026-08-21", "started_utc": "2026-08-21T07:02:10Z",
    "finished_utc": "2026-08-21T07:19:44Z", "duration_seconds": 1054,
    "tokens_input": 18420, "tokens_output": 3110, "tokens_cache_read": 96500,
    "tokens_cache_write": 21200, "bites_logged": 3, "resolutions_logged": 1,
    "logged_utc": "2026-08-21T07:19:44Z"}
   ```

   `started_utc` comes from step 0. `finished_utc`/`duration_seconds` are
   captured right here, right before the commit. Token fields are summed
   from this run's own transcript — the most recently modified `*.jsonl`
   under `$HOME/mnt/.claude/projects/*/` — by reading every turn's `usage`
   block (`input_tokens`, `output_tokens`, `cache_read_input_tokens`,
   `cache_creation_input_tokens`) and totalling across the file, the same
   technique the `explain-usage` skill uses. `bites_logged`/
   `resolutions_logged` are just counts of what steps 1-2 wrote this run
   (0 is fine). If the transcript can't be found or parsed, log zeros
   rather than skip the record or guess — a visibly-wrong zero is easier
   to notice and fix than a silently missing record.

   Then: `git add ROLE_INTEL.md docs/data/intel_sweep_log.jsonl && git
   commit -m "Intel sweep <date>: <n> new bites, <n> resolved"`. The
   commit now happens every run regardless of whether steps 1-3 found
   anything, since `run_meta` itself is always new — the commit message
   still says "0 new bites, 0 resolved" on a quiet day rather than
   claiming there's nothing to commit. Do not regenerate
   `SOURCE_RELIABILITY.md`/`INTEL_REVIEW.md` on every daily run — see
   below, those are weekly.

---

## The Friday review — the only path into the model

`fpl-friday-intel-review`, every Friday at 07:30, ahead of the
`fpl-weekly-deadline-brief` transfer-strategy task.

1. Runs `score_source_reliability.py` then `build_intel_review.py`, which
   builds `INTEL_REVIEW.md` — every bite with no decision yet (or previously
   `deferred`), each paired with its source's current accuracy/n/stale-rate
   from the scorecard, plus its resolution status so far.
2. Presents that queue to Sylvan alongside the full `SOURCE_RELIABILITY.md`
   table, and asks explicitly: **accept / reject / defer**, per bite. The
   task waits for his reply rather than guessing.
3. On reply, appends one `decision` record per bite to
   `docs/data/intel_sweep_log.jsonl` — the one record kind in this log that
   is **not** first-write-stands: Sylvan can change his mind, and the latest
   decision for a given bite wins.
4. **Only `accepted` bites with a `field_affected` get written into the
   `setpieces`/`adjustments` fence**, following the exact format the fence
   already uses, with the `why` column stating it was accepted in that
   week's review. `rejected` bites get a one-line dated note in the
   narrative section and nothing else. `deferred` bites simply reappear in
   next week's queue.
5. Regenerates the queue and commits everything, including the two derived
   reports.

**Resolution and decision are independent axes.** A bite can be `open`
(nobody has confirmed or contradicted the claim yet) and still be `accepted`
— that mirrors a Tier-3 override in `SELECTION_FRAMEWORK.md`, which is
explicitly allowed to run ahead of full confirmation provided it's dated,
sourced and falsifiable. Conversely an `accepted` bite that later resolves
`contradicted` should be reverted from the fence by hand at the next review —
this pipeline doesn't yet auto-revert an accepted-then-contradicted entry;
treat that as a manual prune, same as `ROLE_INTEL.md` rule 6 always has.

**If nothing material was found and no bite resolved**, log no `bite` or
`resolution` records and reply with one line saying so — same discipline
`fpl-pre-deadline-news-watch` already used; a daily task that pads out
empty days trains everyone to stop reading it. The `run_meta` record from
step 4 still gets logged and committed regardless — that's timing/cost
bookkeeping, not a finding, and skipping it on quiet days would leave gaps
in the one place duration and token cost are tracked.

---

## The scorecard

`score_source_reliability.py` reads the log and writes
`docs/data/source_scorecard.json` + `SOURCE_RELIABILITY.md`. **Regenerate
weekly, inside `fpl-friday-intel-review`, not on every daily sweep** —
accuracy numbers that visibly jitter day to day on a handful of resolutions
would look more precise than they are. `fpl-weekly-deadline-brief`'s
methodology-gate check should also report the scorecard's headline
(best/worst tracked source, any newly-crossed accuracy gate) alongside the
existing methodology-gate lines.

**Gating, same threshold as `score_calibration()`:** a source needs 5+
resolved bites (confirmed or contradicted) before its accuracy is reported as
a percentage rather than "insufficient data". Expect this gate to bind for
every source until roughly GW6–8, the same horizon `score_calibration()`
itself needs.

**What the score does and doesn't mean.** `stale_rate` (bites that hit
`check_by_gw` without resolving) is tracked separately from accuracy —
a source that goes quiet rather than wrong is a different failure mode, and
conflating the two would punish sources that make longer-horizon, harder-to-
verify calls the same as sources that are simply incorrect.

---

## Known issue — stray `.git/index.lock`

Some sandboxed sessions running against this repo (this was first hit
interactively on 20 Aug 2026) have left a stray, unremovable-from-that-session
`.git/index.lock` behind after a git operation, which then blocks the next
`git add`/`git commit` with `fatal: Unable to create '.git/index.lock': File
exists.` It is not a real concurrent-process conflict — nothing else writes to
this repo automatically except `fpl-daily-intel-sweep` and
`fpl-friday-intel-review`, which never run at the same time as each other.

Both of those tasks now self-heal once (`rm -f .git/index.lock`, retry the
commit, give up and report honestly if it fails twice) rather than silently
dropping a commit — see their `KNOWN ISSUE` step. If you ever see a task
report a failed commit, the fix is the same one used a few times by hand
already:

```bash
cd ~/Projects/FPL
rm -f .git/index.lock
git status        # confirm what's actually staged before committing
git add -A && git commit -m "..."
git push
```

If stray lock files keep recurring, `git gc --prune=now` afterward clears out
any orphaned `.git/objects/*/tmp_obj_*` files left behind by the interrupted
attempts — cosmetic clutter, not corruption, but worth a periodic clean.

## Kill criteria

- **A source sits at <30% accuracy past the 5-resolved gate** — stop logging
  its claims as bites; keep reading it for colour, not for intel.
- **`stale_rate` exceeds ~50% for a source** — its claims aren't falsifiable
  enough as reported; tighten what counts as a loggable bite from it, or drop
  it.
- **The daily sweep produces fewer than ~2 bites/week across all sources for
  three straight weeks in-season** — the cadence is more than the news flow
  supports; fold back to a 2–3×/week schedule rather than keep an empty daily
  task running.
- **`ROLE_INTEL.md` entries start citing the sweep log instead of restating
  the finding in prose** — the narrative file must stay human-readable on its
  own; the JSONL is the audit trail, not a replacement for step 3 above.

---

## Reference

- `docs/data/intel_sweep_log.jsonl` — append-only (bites, resolutions,
  run_meta — first-write-stands) / mutable-by-design for `decision` records
  (latest wins) — the source of truth. `run_meta` is one record per daily
  run: `started_utc`/`finished_utc`/`duration_seconds` plus a token-usage
  breakdown pulled from that run's own transcript, logged even on days
  with zero bites — see step 4 above.
- `score_source_reliability.py` — per-source scorer; `build_intel_review.py`
  — Friday decision-queue builder; both regenerate weekly, do not hand-edit
  their outputs
- `docs/data/source_scorecard.json` / `SOURCE_RELIABILITY.md` — generated,
  full per-source track record
- `docs/data/intel_review_queue.json` / `INTEL_REVIEW.md` — generated,
  this week's pending decisions
- `ROLE_INTEL.md` — the curated narrative overlay the daily sweep feeds
  directly; its `setpieces`/`adjustments` fences are written **only** by the
  Friday review, on Sylvan's explicit accept
- `intel_adjust.py` — the vocabulary (`field`/`op`/`value`) bites should use
  when they map to a model input
- Scheduled tasks: `fpl-daily-intel-sweep` (daily, gather + log + narrative
  draft, never touches the fences) and `fpl-friday-intel-review` (Friday
  07:30, the decision meeting, the only writer of the fences). Together they
  superseded `fpl-pre-deadline-news-watch` (Friday-only), whose safety-net
  function — catching late-breaking squad news before a deadline — is now
  covered by the daily cadence plus the deadline-week emphasis in step 2
  above.
