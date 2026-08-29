-- Intel bites schema — replaces docs/data/intel_sweep_log.jsonl once the
-- dashboard moves to a live Render + Supabase app.
--
-- Source of truth for the record shapes this mirrors: INTEL_SWEEP.md,
-- score_source_reliability.py, build_intel_review.py.
--
-- Three record kinds, three tables, same semantics the JSONL already
-- enforces by convention:
--   intel_bites       — first-write-stands. A finding, logged once, never
--                        edited. (JSONL "bite" records.)
--   intel_resolutions — first-write-stands. Whether a bite's falsifiable
--                        check panned out. (JSONL "resolution" records.)
--   intel_decisions   — append-only, but NOT first-write-stands: this is
--                        Sylvan's live editorial call (accept/reject/defer),
--                        made in the Friday review, and he's allowed to
--                        change his mind. Every decision is still kept —
--                        nothing is edited or deleted — the LATEST row per
--                        bite_id is the effective one. (JSONL "decision"
--                        records.)
--
-- All three tables are protected against UPDATE/DELETE by a trigger below —
-- Postgres now enforces the append-only rule the JSONL only had by
-- discipline. If a genuine correction is ever needed, drop the trigger,
-- fix the row, recreate the trigger — same as hand-editing the JSONL was
-- always a last resort, not a supported path.

begin;

-- ---------------------------------------------------------------------
-- intel_bites
-- ---------------------------------------------------------------------

create table if not exists intel_bites (
  id                text primary key,
  -- human-readable id, same convention as the JSONL:
  -- "<player>-<team>-<field>-<YYYYMMDD>-<n>", e.g.
  -- "szoboszlai-liv-xg90-20260821-1"

  bite_date         date not null,
  source_name       text not null,
  source_tier       smallint not null check (source_tier between 1 and 5),
  -- denormalized on purpose, not a FK to a sources table: a source's tier
  -- can be reassessed later, but a bite must keep the tier it was logged
  -- against at the time — same reasoning as the audit trail itself.
  source_url        text,

  player             text,
  team               text,        -- 3-letter club code, e.g. 'LIV'
  category           text not null check (
                       category in ('setpiece', 'injury', 'rotation',
                                    'tactical', 'manager_change', 'other')
                     ),
  hypothesis         text not null,   -- the claim itself, one sentence

  -- If this maps to a specific model input, the vocabulary must match
  -- intel_adjust.py's MULT_FIELDS/SET_FIELDS — currently xg90, xa90,
  -- xgi90, cbit90, cbirt90 (mult) and stp (set). Left as free text rather
  -- than a hard enum because that Python set can grow; keep it in sync
  -- by hand, same as today.
  field_affected     text,
  suggested_op       text check (suggested_op in ('mult', 'set')),
  suggested_value    numeric,

  confidence          text check (confidence in ('high', 'medium', 'low')),
  falsifiable_check   text not null,
  check_by_gw         smallint,

  -- Bite(s) this one materially updates rather than a new independent
  -- finding — INTEL_SWEEP.md step 2 allows a list, so this is an array,
  -- not a single FK. Not FK-enforced (older/edge-case ids may not
  -- resolve) but validated at write time by the app.
  updates_bite_ids    text[] not null default '{}',

  logged_utc          timestamptz not null,   -- author-supplied, from the sweep
  created_at          timestamptz not null default now()  -- ingestion time
);

create index if not exists idx_intel_bites_player       on intel_bites (player);
create index if not exists idx_intel_bites_team          on intel_bites (team);
create index if not exists idx_intel_bites_category      on intel_bites (category);
create index if not exists idx_intel_bites_check_by_gw   on intel_bites (check_by_gw);
create index if not exists idx_intel_bites_bite_date     on intel_bites (bite_date);
create index if not exists idx_intel_bites_source_name   on intel_bites (source_name);

-- ---------------------------------------------------------------------
-- intel_resolutions
-- ---------------------------------------------------------------------

create table if not exists intel_resolutions (
  id                bigserial primary key,
  bite_id           text not null references intel_bites (id),
  resolution_date   date not null,
  outcome           text not null check (
                      outcome in ('confirmed', 'contradicted', 'expired', 'superseded')
                    ),
  evidence          text,
  logged_utc        timestamptz not null,
  created_at        timestamptz not null default now()
);

create index if not exists idx_intel_resolutions_bite_id on intel_resolutions (bite_id);

-- A bite is normally resolved once. Not hard-constrained to one row
-- (a "superseded" outcome legitimately follows an earlier one) but the
-- common case is 0 or 1 — see intel_bite_status view below for "current".

-- ---------------------------------------------------------------------
-- intel_decisions — the user-input table: what Sylvan wants actioned
-- ---------------------------------------------------------------------

create table if not exists intel_decisions (
  id             bigserial primary key,
  bite_id        text not null references intel_bites (id),
  decision_date  date not null,
  decision       text not null check (decision in ('accepted', 'rejected', 'deferred')),
  decided_by     text not null default 'sylvan',
  note           text,
  logged_utc     timestamptz not null,
  created_at     timestamptz not null default now()
);

create index if not exists idx_intel_decisions_bite_id  on intel_decisions (bite_id);
create index if not exists idx_intel_decisions_decision on intel_decisions (decision);

-- ---------------------------------------------------------------------
-- Append-only enforcement
-- ---------------------------------------------------------------------

create or replace function reject_mutation() returns trigger as $$
begin
  raise exception
    'append-only table: % rows are never edited or deleted (attempted % on %)',
    tg_table_name, tg_op, tg_table_name;
end;
$$ language plpgsql;

drop trigger if exists no_update_delete on intel_bites;
create trigger no_update_delete
  before update or delete on intel_bites
  for each row execute function reject_mutation();

drop trigger if exists no_update_delete on intel_resolutions;
create trigger no_update_delete
  before update or delete on intel_resolutions
  for each row execute function reject_mutation();

drop trigger if exists no_update_delete on intel_decisions;
create trigger no_update_delete
  before update or delete on intel_decisions
  for each row execute function reject_mutation();

-- ---------------------------------------------------------------------
-- Views — the read shapes the app actually needs
-- ---------------------------------------------------------------------

-- Current resolution status per bite. 'open' means no resolution row yet —
-- matches score_source_reliability.py's _status().
create or replace view intel_bite_current_resolution as
select distinct on (bite_id)
  bite_id,
  outcome,
  resolution_date,
  evidence,
  logged_utc
from intel_resolutions
order by bite_id, logged_utc desc;

-- Current (latest) decision per bite. No row means "no decision yet" —
-- the bite is still pending.
create or replace view intel_bite_current_decision as
select distinct on (bite_id)
  bite_id,
  decision,
  decided_by,
  note,
  decision_date,
  logged_utc
from intel_decisions
order by bite_id, logged_utc desc;

-- Per-source accuracy, mirroring score_source_reliability.py: gated at 5+
-- resolved (confirmed or contradicted) bites before accuracy is meaningful.
-- expired/superseded count toward stale_rate, not accuracy.
create or replace view intel_source_scorecard as
with resolved as (
  select
    b.source_name,
    r.outcome
  from intel_bites b
  join intel_bite_current_resolution r on r.bite_id = b.id
),
agg as (
  select
    source_name,
    count(*) filter (where outcome in ('confirmed', 'contradicted')) as n_resolved,
    count(*) filter (where outcome = 'confirmed')                    as n_confirmed,
    count(*) filter (where outcome in ('expired', 'superseded'))     as n_stale,
    count(*)                                                          as n_total
  from resolved
  group by source_name
)
select
  source_name,
  n_total,
  n_resolved,
  n_confirmed,
  case when n_resolved >= 5
       then round(100.0 * n_confirmed / n_resolved, 1)
       else null end as accuracy_pct,
  case when n_resolved < 5 then true else false end as insufficient_data,
  case when n_total > 0
       then round(100.0 * n_stale / n_total, 1)
       else 0 end as stale_rate_pct
from agg;

-- The Friday review queue: bites with no decision yet, or whose latest
-- decision is 'deferred' — mirrors build_intel_review.py's pending_bites().
create or replace view intel_review_queue as
select
  b.*,
  cr.outcome            as resolution_status,   -- null = open
  cr.evidence            as resolution_evidence,
  cd.decision             as current_decision,    -- null = never decided
  cd.decision_date        as current_decision_date,
  s.accuracy_pct          as source_accuracy_pct,
  s.n_resolved             as source_n_resolved,
  s.insufficient_data      as source_insufficient_data,
  s.stale_rate_pct         as source_stale_rate_pct
from intel_bites b
left join intel_bite_current_resolution cr on cr.bite_id = b.id
left join intel_bite_current_decision cd   on cd.bite_id = b.id
left join intel_source_scorecard s         on s.source_name = b.source_name
where cd.decision is null or cd.decision = 'deferred';

commit;

-- ---------------------------------------------------------------------
-- Row Level Security — enable once auth model is decided
-- ---------------------------------------------------------------------
-- Personal single-user app: simplest path is the Render backend talking to
-- Supabase with the service_role key (bypasses RLS entirely), and RLS left
-- enabled with no policies so anon/authenticated keys see nothing if they
-- ever leak into a client bundle by mistake:
--
--   alter table intel_bites       enable row level security;
--   alter table intel_resolutions enable row level security;
--   alter table intel_decisions   enable row level security;
--
-- If the live dashboard instead has Sylvan log in via Supabase Auth and
-- talks to Postgres directly (no separate backend), add a policy scoped
-- to his user id instead of relying on the service role, e.g.:
--
--   create policy "sylvan full access" on intel_decisions
--     for all using (auth.uid() = '<sylvan-user-uuid>');
--
-- Decide this alongside the Render API's auth design, not before.
