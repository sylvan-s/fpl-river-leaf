# Multi-user dashboard plan — Render + Supabase

Status: **plan only, nothing implemented.** Three draft migrations exist
under `supabase/migrations/` as a concrete sketch of the schema this
describes; none have been applied to a real Supabase project, and no
backend/hosting code exists yet. This document is the reference for when
that work actually starts.

## Why this is being considered

The dashboard today is fully static: `build_dashboard.py` and friends bake
data into self-contained HTML pages (`const DATA` inline in a `<script>`
tag), `publish_dashboard.sh` verifies them, and GitHub Pages serves
`docs/`. There's one team (River Leaf FC, entry 1041614), one set of
squad/transfer decisions, and one intel-review queue — all of it Sylvan's.

Moving hosting to Render and pulling data from a Postgres server on
Supabase is a real architecture change, not a hosting swap, and it opens a
second question: if the backend is now a live app with a real database
instead of files baked at build time, could other people log in and run
the same pipeline against their own FPL team? This plan covers both.

## Target architecture

A Render Web Service (API, e.g. FastAPI) replaces the static build step.
It queries a Supabase Postgres database on each request rather than
reading baked JSON. The existing frontend (`dash.js` and the other page
scripts) is adapted to `fetch()` from that API instead of reading an
inline `DATA` blob — a full rewrite into server-rendered templates is a
much bigger lift than the API-plus-existing-frontend path and isn't
planned. Scheduled ingestion (the FPL API pulls that currently happen via
`fpl_research_mcp.py` and the daily intel sweep) moves to a Render Cron
Job or Supabase `pg_cron`, replacing the "run locally, commit, push"
workflow.

## Phased rollout

1. **Stand up Supabase, migrate data, run in parallel.** Design the full
   schema (not just intel — also players/priors, gameweek stats, fixtures,
   squad state), write a one-time migration script pulling from the
   existing JSON/CSV/JSONL files (`fpl_priors_2025_26_v2.json`,
   `last16_starts.json`, `squad.json`, `live_gw_cache.json`,
   `.cache_merged_gw.csv`, `fpl_calibration_log.jsonl`,
   `docs/data/intel_sweep_log.jsonl`), backfill Supabase, leave the current
   static site untouched and live.
2. **Build and locally test the API** against the migrated Supabase data.
3. **Deploy to Render**, point the frontend's fetch calls at it, run a
   side-by-side parity check against the current static dashboard before
   trusting it.
4. **Move ingestion crons over to Render**, retire the local
   `publish_dashboard.sh` → GitHub Pages loop (or keep Pages as a frozen
   fallback for a while).
5. **Cut over fully** once confident; decommission the old pages.

Multi-user work (below) layers on top of step 1 onward — it changes what
gets migrated and how RLS is set up, not the phase order.

## Data split: shared research vs. personal decisions

This is the central design decision for multi-user support, and it's what
the schema is built around. A researched fact — "Szoboszlai looks likely
to take penalties," "Sarr is out with a groin injury" — is true regardless
of who's looking at it, so it stays in one shared table that the daily
intel sweep writes to once. Whether to act on that fact is personal: two
users can see the identical bite and one accepts it into their squad's
model inputs while the other defers or rejects it. That split holds all
the way through to the optimizer — see the last section.

| Shared across all users | Personal to each user |
|---|---|
| `intel_bites` (the researched findings) | `intel_decisions` (accept/reject/defer) |
| `intel_resolutions` (did the claim pan out) | `squads` (their 15, bank, chip state) |
| `intel_source_scorecard` (source accuracy) | `team_changes` (their transfer log) |
| base player projections/priors (not yet migrated) | `user_adjustments` / `optimiser_runs` |

## Schema: intel bites, resolutions, decisions

`supabase/migrations/0001_intel_bites.sql` — mirrors the record shapes
already defined in `INTEL_SWEEP.md`, `score_source_reliability.py`, and
`build_intel_review.py`, one table per JSONL record kind:

- **`intel_bites`** — first-write-stands, one row per researched finding:
  id (`<player>-<team>-<field>-<YYYYMMDD>-<n>`), source name/tier/url,
  player/team/category, the claim itself, the `field_affected`/
  `suggested_op`/`suggested_value` triple (vocabulary must stay in sync
  with `intel_adjust.py`'s `MULT_FIELDS`/`SET_FIELDS`), confidence,
  falsifiable check, `check_by_gw`, and `updates_bite_ids[]` for a bite
  that revises an earlier one.
- **`intel_resolutions`** — first-write-stands, whether a bite's
  falsifiable check came true: `confirmed` / `contradicted` / `expired` /
  `superseded`.
- **`intel_decisions`** — accept/reject/defer, append-only but *not*
  first-write-stands: every decision row is kept, the latest one per bite
  is the effective one, mirroring the JSONL's existing "Sylvan can change
  his mind" rule.

All three tables have an actual Postgres trigger (`reject_mutation()`)
blocking `UPDATE`/`DELETE` — enforcing in the database the append-only
rule the JSONL only ever had by convention. Three views do the work the
Python scripts currently do: `intel_bite_current_resolution`,
`intel_source_scorecard` (the same 5-resolved-bites-before-reporting-
accuracy gate `score_source_reliability.py` uses), and `intel_review_queue`
(bites with no decision or a deferred one, joined with the source's
track record — the Friday-review shape).

## Schema: multi-user support

`supabase/migrations/0002_multi_user.sql` adds logins and personal teams
without touching how bites/resolutions work.

- **`profiles`** — one row per Supabase Auth user (`auth.users` is
  Supabase-managed; app columns like display name and their real FPL
  entry ID live in a linked table instead), created automatically via a
  trigger on `auth.users` insert.
- **`intel_decisions` gains a `user_id` column.** This is the only change
  on the research side. Existing rows (Sylvan's, pre-multi-user) need
  `user_id` backfilled by hand before the column can be made `NOT NULL` —
  the migration leaves this as a commented-out step rather than guessing.
- **`squads`** — each user's current 15, bank, free transfers, active
  chip, keyed by `(user_id, gw)`. Mutable, not append-only — a squad gets
  edited by transfers right up to deadline, unlike the log tables.
- **`team_changes`** — per-user transfer/strategy log, replacing the
  single shared `TEAM_CHANGE_LOG.md`. Append-only, same trigger pattern
  as the intel tables.
- **Row Level Security goes from optional to load-bearing.** With one
  user, a service-role connection from the backend was enough protection
  by itself. With many, RLS is what actually stops user A from reading or
  writing user B's squad or decisions — enabled on every table, with
  policies scoping personal tables to `auth.uid() = user_id` and leaving
  shared research tables readable by any authenticated user but writable
  only by the service role (i.e., the ingestion pipeline, not end users).
- **`intel_review_queue` becomes personal for free** — it filters on
  `auth.uid()`, which Postgres resolves from the caller's session, so
  each user querying it gets their own pending list with nothing to pass
  explicitly. This only works if queries go through Supabase's
  authenticated context (PostgREST or a per-user JWT) rather than a
  single superuser/service-role connection for everyone.

**Bug found and fixed in the same pass:** views created without
`security_invoker` run with the *view owner's* privileges by default in
Postgres 15, not the querying user's — meaning `intel_bite_current_decision`
and `intel_review_queue` as first drafted would have silently ignored the
RLS policies sitting right below them. As drafted, any authenticated user
querying `intel_review_queue` would have seen every user's decisions, not
just their own. This is fixed in the third migration by setting
`security_invoker = true` on all four views — worth remembering as a
general Supabase gotcha: RLS on a base table doesn't protect a view over
it unless that option is set explicitly.

## Schema: per-user optimizer inputs

`supabase/migrations/0003_user_adjustments.sql`. Once decisions are
personal, the "accepted intel becomes a model input" step can't stay a
single shared file either — today that's `ROLE_INTEL.md`'s `setpieces`/
`adjustments` fence, parsed by `intel_adjust.py`, feeding `build_squad.py`
and `optimise_squad.py` for the one team that exists. Multi-user turns
that into: shared bites → each user's personal accept/reject → each
user's personal set of adjustments → their own optimizer run against
their own squad.

- **`user_adjustments`** (view) — each user's accepted bites translated
  into the `(field, op, value)` triples the optimizer applies on top of
  shared base projections. Same vocabulary as `intel_adjust.py` uses
  today, just scoped by RLS to whoever's logged in instead of read from
  one global file.
- **`optimiser_runs`** — logs every suggestion a user's optimizer
  produced: their squad before the run, a *snapshot* of the adjustments
  applied (not a live reference), and the resulting suggested transfers.
  The snapshot matters because `user_adjustments` is a live view — if a
  bite is later reverted (an accepted-then-contradicted bite, per
  `ROLE_INTEL.md` rule 6's manual-prune process, now per-user), the
  historical run record should still show what was actually true when
  that suggestion was made. Append-only, same trigger as everywhere else.

**Application-layer implication, not yet built:** `optimise_squad.py` (or
its live equivalent) needs to take a `user_id`, load that user's row from
`squads`, join in `user_adjustments` for their accepted intel, and run
the same gate logic per user. Base priors/fixture data ingestion stays a
single shared job feeding everyone — the FPL API only gets pulled once,
not once per user; only the optimization math re-runs per user, and
that's cheap.

## Open items / not yet designed

- **Base player projections/priors have no Postgres schema yet.** Today
  these live in `fpl_priors_2025_26_v2.json`, `last16_starts.json`,
  `fixture_window.json`, and the merged-gameweek CSV. `user_adjustments`
  assumes some shared `player_projections`-shaped table exists for the
  optimizer to layer onto, but that table hasn't been designed —
  deliberately deferred so this plan didn't have to guess its shape
  before the ingestion pipeline that would populate it is designed too.
- **Auth model.** Supabase Auth (email/password, magic link, or OAuth)
  is assumed but not chosen. This decides whether the Render API talks to
  Postgres with a single service-role connection (simplest, but means the
  API itself must enforce per-user scoping in application code, with RLS
  as a backstop) or with each user's own JWT passed through (RLS does the
  enforcement directly). Worth deciding alongside the API's own design,
  not before.
- **Whether "accepted" should ever be collective for anything.** The
  design above makes acceptance fully personal — no shared promotion path
  exists anymore. If some findings (e.g. a confirmed injury) should
  arguably update everyone's view rather than requiring each user to
  independently accept the same bite, that's a deliberate product
  decision to make later, not an oversight in the schema.
- **Migration script** from the existing JSONL/JSON/CSV files into the
  tables above doesn't exist yet — this plan describes the target shape,
  not the backfill.
- **Cost/uptime tradeoffs**, unresolved: Supabase's free tier pauses a
  database after a week of inactivity, and Render's free web service tier
  spins down after 15 minutes idle (cold starts on the next request).
  Relevant here since usage is weekly by design — either ping both to
  keep them warm or accept the cold-start cost, or pay for always-on
  tiers (~$7/mo Render Starter is the usual fix).

## Reference

- `supabase/migrations/0001_intel_bites.sql` — bites/resolutions/decisions,
  single-user
- `supabase/migrations/0002_multi_user.sql` — profiles, squads,
  team_changes, RLS, per-user decisions
- `supabase/migrations/0003_user_adjustments.sql` — per-user optimizer
  inputs, `optimiser_runs`, the `security_invoker` fix
- All three validated for syntax with `pglast` (the real Postgres parser),
  not applied to any live database
