# 0003. Source the prediction tracker from the SQLite cache, not the live API

**Status:** Accepted for `build_prediction_tracker.py`. Live-API fetching is
kept as a fallback, not removed.

**Logged:** 1 Sep 2026, the same day as docs/adr/0002 — a direct follow-on to
it, not a separate initiative.

## Context

Immediately after 0002 shipped, Sylvan asked to see `docs/priors.html` live.
The build that produced the committed payload had run inside a Claude/Cowork
sandbox session (this one) with no `httpx` installed and no route to the
live FPL API — `build()`'s except-branch caught that, set `empty_state` to a
diagnostic string, and fell back to whatever was last persisted. That
exposed a real bug (fixed separately, same day): the front end treated ANY
truthy `empty_state` as "nothing to show", hiding a full GW1 of real cached
data behind a "waiting for gameweeks" panel. That fix made a failed fetch
degrade honestly. It did not get fresh data onto the page.

Sylvan's next ask was direct: this should build from the SQLite database that
pulls FPL data every Tuesday, not do its own live fetch. Checking what that
database actually held (`cache_history(refresh=false)` via the fpl-research
MCP tools, which run on Sylvan's own machine): `player_gw`, warm through GW2,
364 players current, at `~/.fpl-mcp/fpl_history_cache.sqlite`. Real, current
data was already sitting on disk the whole time; `build_prediction_tracker.py`
had simply never looked there.

This is not a new problem for this codebase. `build_squad_page.py`'s
`actual_route_snapshot()` hit the identical constraint on 26 Aug 2026 for a
different chart: reading that SQLite file directly works from Sylvan's own
terminal, but not from a Cowork/Claude sandbox, whose `$HOME` has no route to
a file that lives outside the explicitly connected project folder. That
build silently saw "no data" from inside a sandbox even after the real cache
was warm. The fix there was to move the computation into an MCP tool
(`squad_actual_points`) that runs where the database actually lives and
writes a small aggregate into `docs/data/` for the build to read.

## Decision

`build_prediction_tracker.py` tries the SQLite cache first, and falls back to
the live API only when that database is not there to read.

- `_cache_from_sqlite()` opens `player_gw` read-only and reshapes it into the
  exact `{round: {player_id: stats}}` shape `_fetch_live()` already returns
  from the live API — so `walk_forward()` needed no changes at all to
  consume either source. The nine columns it selects
  (`minutes, starts, expected_goals, expected_assists,
  expected_goals_conceded, saves, clearances_blocks_interceptions, tackles,
  recoveries`) are exactly the fields the walk-forward math reads.
- Every distinct round present in `player_gw` is treated as finished, with
  no separate flag check: `fpl_research_mcp.py`'s own `_player_history()`
  already enforces upstream that only finished gameweeks are ever written
  there, so a round showing up here at all already carries that guarantee.
- `id_pos`/`id_name` — the only other thing the live `bootstrap-static` call
  supplied — come from the frozen prior-season snapshot
  (`fpl_priors_2025_26_v2.json`) instead, via `_boot_from_priors_snapshot()`.
  That snapshot already has `element_type` and `web_name` per player, and is
  already the exact population `build_baselines()` restricts predictions to
  — so this introduces no new gap. A genuine 2026/27-only newcomer with no
  2025/26 record has never had a baseline and has never produced a
  walk-forward row, regardless of where names and positions come from.
- Net effect: the normal path now needs neither `httpx` nor network access
  at all. `build()` reports which source it used (`sqlite` or `live API`) on
  stdout for the person running it; that flag is diagnostic only and is
  deliberately not written into `docs/data/priors_payload.json` — the page
  itself only needs to know current vs stale, which `empty_state` already
  conveys, not which pipe the numbers came down.

## Why not the same fix as the squad page

`actual_route_snapshot()`'s problem was solved by moving the read into an MCP
tool, so it works identically no matter which environment initiates the
build. That is the more complete fix, and it was considered here. It was set
aside for this file specifically because of what it would have cost:
either `build_prediction_tracker.py` duplicating a new copy of the ~250 lines
of shrinkage/walk-forward machinery inside the live production
`fpl_research_mcp.py` server, or that server importing this build file
instead. `fpl_research_mcp.py` has its own test suite (`test_fpl_mcp.py`) and
is the one thing every other MCP tool and the fpl-weekly-brief skill depend
on being reliable; a change to it cannot be verified end-to-end from a
sandbox session the way a change to a build script can, since picking up a
new tool definition needs Claude Desktop restarted on the real machine. That
is a materially bigger, harder-to-verify change than reading one already-
matching table shape from a different data source.

## Consequences

**Fixed today, permanently, for anyone running this from Sylvan's own
terminal**: no `httpx` dependency, no network round-trip, no chance of a 403
or a timeout, as long as the weekly `cache_history` routine keeps the
database warm.

**Not fixed, deliberately, for a Cowork/Claude sandbox session**: it still
has no route to `~/.fpl-mcp/fpl_history_cache.sqlite`, so a build initiated
from a session like this one still falls through to the live API, and — if
that also fails, as it did in this sandbox specifically because outbound
network here is allowlisted and blocks the FPL API — falls through again to
last-persisted state with the honest stale-data banner docs/adr/0002's fix
added. That is the accepted degrade path, not a bug: the alternative is the
bigger MCP-tool change ruled out above.

**As-designed staleness**: the SQLite path is only as fresh as Sylvan's own
Tuesday cache-warming routine. A build run between a Sunday gameweek finish
and the following Tuesday will show the previous gameweek until that routine
runs — expected, and exactly what was asked for, not a defect to fix here.

**Verification.** No access to the real database from this session, so the
reshape and the full `build()` path were tested against a synthetic SQLite
file built to the identical schema (`_GW_COLS` superset, real player ids
drawn from the actual priors snapshot), covering: the reshape produces the
right shape and rounds, `_boot_from_priors_snapshot()` returns a usable
element list, `build()` runs end to end with `source="sqlite"` and
`empty_state=null`, and the no-database/no-network sandbox path still
degrades to the last-saved-state fallback exactly as before. `verify_priors.js`
and `verify_pages.js` both still pass unchanged against the real committed
files — expected, since the page's JS was not touched, only where its input
JSON comes from.
