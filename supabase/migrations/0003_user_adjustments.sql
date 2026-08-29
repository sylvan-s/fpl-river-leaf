-- Personal optimizer inputs: turn each user's accepted bites into the
-- (field, op, value) adjustments their own optimise_squad.py run should
-- apply, and log what a run actually used — replacing the single shared
-- ROLE_INTEL.md adjustments fence / intel_adjust.py, which only made
-- sense when there was one team.
--
-- Also fixes a real gap in 0002: views created without security_invoker
-- run with the VIEW OWNER's privileges by default (Postgres 15 default),
-- not the querying user's — which means they silently ignore the RLS
-- policies on the tables underneath. intel_bite_current_decision and
-- intel_review_queue were both left at the default in 0002, so as shipped
-- ANY authenticated user querying them would see EVERY user's decisions,
-- not just their own — RLS on intel_decisions itself was correct, but the
-- views sitting on top of it weren't honoring it. Fixed below.

begin;

-- ---------------------------------------------------------------------
-- Security fix: make existing views respect the querying user's RLS
-- ---------------------------------------------------------------------

alter view intel_bite_current_resolution set (security_invoker = true);
alter view intel_source_scorecard        set (security_invoker = true);
alter view intel_bite_current_decision   set (security_invoker = true);
alter view intel_review_queue            set (security_invoker = true);

-- ---------------------------------------------------------------------
-- user_adjustments — this user's accepted bites, in the exact
-- field/op/value shape optimise_squad.py needs to apply on top of the
-- shared base projections
-- ---------------------------------------------------------------------
-- Filtered to auth.uid() implicitly via RLS on intel_decisions once
-- security_invoker is set — same pattern as intel_review_queue.

create view user_adjustments with (security_invoker = true) as
select
  d.user_id,
  b.id            as bite_id,
  b.player,
  b.team,
  b.field_affected as field,
  b.suggested_op    as op,
  b.suggested_value  as value,
  b.source_name,
  b.source_tier,
  d.decision_date     as accepted_date,
  d.note
from intel_bite_current_decision d
join intel_bites b on b.id = d.bite_id
where d.decision = 'accepted'
  and b.field_affected is not null;

-- ---------------------------------------------------------------------
-- optimiser_runs — every suggestion a user's optimizer produced, and
-- exactly what it used to get there. Same reasoning as run_meta/
-- fpl_calibration_log.jsonl elsewhere in this repo: a suggestion that
-- can't later be explained ("why did it say sell X that week?") is a
-- suggestion nobody can audit or improve on. Snapshotting
-- adjustments_applied matters specifically because user_adjustments is a
-- live view — if Sylvan later reverts an accepted-then-contradicted bite
-- (ROLE_INTEL.md rule 6's manual prune, per-user now), the historical run
-- record should still show what was true when the suggestion was made.
-- ---------------------------------------------------------------------

create table if not exists optimiser_runs (
  id                    bigserial primary key,
  user_id               uuid not null references auth.users (id) on delete cascade,
  gw                    smallint not null,
  run_at                timestamptz not null default now(),
  squad_before          jsonb not null,
  adjustments_applied   jsonb not null,   -- snapshot of user_adjustments at run time
  suggested_transfers   jsonb not null,
  suggested_squad       jsonb,
  notes                 text
);

create index if not exists idx_optimiser_runs_user_id    on optimiser_runs (user_id);
create index if not exists idx_optimiser_runs_user_gw    on optimiser_runs (user_id, gw);

drop trigger if exists no_update_delete on optimiser_runs;
create trigger no_update_delete
  before update or delete on optimiser_runs
  for each row execute function reject_mutation();

alter table optimiser_runs enable row level security;

create policy "own optimiser runs select" on optimiser_runs
  for select using (auth.uid() = user_id);
create policy "own optimiser runs insert" on optimiser_runs
  for insert with check (auth.uid() = user_id);

commit;
