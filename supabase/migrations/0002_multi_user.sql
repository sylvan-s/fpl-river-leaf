-- Multi-user support: separate logins, each with their own FPL squad and
-- their own accept/reject/defer calls on the shared intel feed.
--
-- KEY DESIGN SPLIT — this is the part that isn't just "add a user_id
-- column everywhere":
--
--   SHARED across all users            PERSONAL to each user
--   ----------------------------       ----------------------------
--   intel_bites       (research)       intel_decisions (accept/reject/defer)
--   intel_resolutions (what happened)  squads          (their 15, their bank)
--   intel_source_scorecard             team_changes    (their transfer log)
--
-- "Szoboszlai looks likely to take penalties" is a fact about the world —
-- every user should see the same bite, logged once by the research
-- pipeline. Whether to act on it is personal: two users can look at the
-- identical bite and one accepts it into their squad's model inputs while
-- the other defers. That's why intel_bites/intel_resolutions need almost
-- no change below, and intel_decisions gets a user_id. Squads and the
-- transfer log are new tables — there was only ever one team before.

begin;

-- ---------------------------------------------------------------------
-- profiles — one row per Supabase Auth user, created automatically
-- ---------------------------------------------------------------------
-- auth.users is Supabase-managed; don't add app columns to it directly.
-- profiles.id mirrors auth.users.id 1:1.

create table if not exists profiles (
  id            uuid primary key references auth.users (id) on delete cascade,
  display_name  text,
  fpl_entry_id  integer,   -- their official FPL entry/team ID, if linked
  created_at    timestamptz not null default now()
);

create or replace function handle_new_user() returns trigger as $$
begin
  insert into profiles (id, display_name)
  values (new.id, new.raw_user_meta_data ->> 'display_name');
  return new;
end;
$$ language plpgsql security definer set search_path = public;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function handle_new_user();

-- ---------------------------------------------------------------------
-- intel_decisions — add the owner. This is the whole change on the
-- research side: bites and resolutions stay exactly as they are.
-- ---------------------------------------------------------------------

alter table intel_decisions
  add column if not exists user_id uuid references auth.users (id) on delete cascade;

-- Existing rows (Sylvan's, pre-multi-user) need user_id backfilled by hand
-- before this can be NOT NULL — e.g.:
--   update intel_decisions set user_id = '<sylvan-auth-uuid>' where user_id is null;
--   alter table intel_decisions alter column user_id set not null;
-- Left nullable here so the migration itself doesn't fail on old data.

create index if not exists idx_intel_decisions_user_id on intel_decisions (user_id);

-- "Latest decision per bite" is now "latest decision per bite, per user" —
-- replace the view rather than just re-filter it, since two users can
-- both have a current decision on the same bite.
create or replace view intel_bite_current_decision as
select distinct on (bite_id, user_id)
  bite_id,
  user_id,
  decision,
  decided_by,
  note,
  decision_date,
  logged_utc
from intel_decisions
where user_id is not null
order by bite_id, user_id, logged_utc desc;

-- The review queue becomes personal: auth.uid() resolves to whoever the
-- request is authenticated as, so each user querying this view gets their
-- own pending list with no user_id parameter to pass around. Requires
-- querying through Supabase (PostgREST/RLS context) rather than a raw
-- superuser connection, which is exactly how the Render API should be
-- calling it if you go this route — see the RLS note at the bottom on
-- service-role vs. per-user connections.
create or replace view intel_review_queue as
select
  b.*,
  cr.outcome               as resolution_status,
  cr.evidence               as resolution_evidence,
  cd.decision                as current_decision,
  cd.decision_date           as current_decision_date,
  s.accuracy_pct              as source_accuracy_pct,
  s.n_resolved                 as source_n_resolved,
  s.insufficient_data          as source_insufficient_data,
  s.stale_rate_pct             as source_stale_rate_pct
from intel_bites b
left join intel_bite_current_resolution cr on cr.bite_id = b.id
left join intel_bite_current_decision cd
  on cd.bite_id = b.id and cd.user_id = auth.uid()
left join intel_source_scorecard s on s.source_name = b.source_name
where cd.decision is null or cd.decision = 'deferred';

-- ---------------------------------------------------------------------
-- squads — each user's current 15, replacing the single squad.json
-- ---------------------------------------------------------------------
-- Mutable, not append-only: a squad naturally gets edited by transfers
-- right up to deadline. team_changes below is the audit trail; this
-- table is just current state per (user, gameweek).

create table if not exists squads (
  id              bigserial primary key,
  user_id         uuid not null references auth.users (id) on delete cascade,
  gw              smallint not null,
  picks           jsonb not null,     -- 15 players, positions, captain/vice — same shape as squad.json
  bank            numeric,
  free_transfers  smallint,
  active_chip     text,
  updated_at      timestamptz not null default now(),
  unique (user_id, gw)
);

create index if not exists idx_squads_user_id on squads (user_id);

-- ---------------------------------------------------------------------
-- team_changes — per-user transfer/strategy log, replacing the single
-- shared TEAM_CHANGE_LOG.md
-- ---------------------------------------------------------------------

create table if not exists team_changes (
  id           bigserial primary key,
  user_id      uuid not null references auth.users (id) on delete cascade,
  change_date  date not null,
  gw           smallint,
  summary      text not null,
  rationale    text,
  logged_utc   timestamptz not null,
  created_at   timestamptz not null default now()
);

create index if not exists idx_team_changes_user_id on team_changes (user_id);

drop trigger if exists no_update_delete on team_changes;
create trigger no_update_delete
  before update or delete on team_changes
  for each row execute function reject_mutation();

-- ---------------------------------------------------------------------
-- Row Level Security — now load-bearing, not optional
-- ---------------------------------------------------------------------
-- Once decisions and squads are personal, RLS is what actually stops user
-- A from reading or editing user B's data if the Render API ever queries
-- Supabase using each user's own JWT (rather than always going through a
-- single service-role connection). Turn this on regardless of which
-- pattern the API uses — cheap insurance, and required if the frontend
-- ever talks to Supabase directly for anything (e.g. Supabase Auth's own
-- client-side session).

alter table profiles       enable row level security;
alter table intel_bites    enable row level security;
alter table intel_resolutions enable row level security;
alter table intel_decisions enable row level security;
alter table squads          enable row level security;
alter table team_changes    enable row level security;

-- Shared research: every authenticated user can read; only the service
-- role (the ingestion pipeline) can write — no insert/update policy for
-- ordinary users means those actions default-deny.
create policy "bites readable by all authenticated users"
  on intel_bites for select
  to authenticated
  using (true);

create policy "resolutions readable by all authenticated users"
  on intel_resolutions for select
  to authenticated
  using (true);

-- Personal data: owner only, both directions.
create policy "own profile" on profiles
  for select using (auth.uid() = id);
create policy "update own profile" on profiles
  for update using (auth.uid() = id);

create policy "own decisions select" on intel_decisions
  for select using (auth.uid() = user_id);
create policy "own decisions insert" on intel_decisions
  for insert with check (auth.uid() = user_id);

create policy "own squad select" on squads
  for select using (auth.uid() = user_id);
create policy "own squad upsert" on squads
  for insert with check (auth.uid() = user_id);
create policy "own squad update" on squads
  for update using (auth.uid() = user_id);

create policy "own team changes select" on team_changes
  for select using (auth.uid() = user_id);
create policy "own team changes insert" on team_changes
  for insert with check (auth.uid() = user_id);

commit;
