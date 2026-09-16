# Cloud-only optimisation: tools to add to the VM's fpl-research server

Drafted 15 Sep 2026 from the GW5 scenario run. Goal: a cloud Cowork session can
ask for the full transfer/scenario optimisation with **no dependency on the Mac
being open**. Today the VM connector exposes the 21 research tools only; the
optimiser, the fixture-window refresh, the quarantine overlay and the repo
state all still live on the Mac.

What the GW5 run needed and where it came from:

| Need | Came from today | Cloud-safe? |
|---|---|---|
| deadline, fixtures, injuries, prices, captaincy, xGI | VM connector | yes |
| squad.json, ROLE_INTEL.md fences, TEAM_CHANGE_LOG.md | Mac folder mount | **no** |
| fixture_adjust.py --update (window refresh) | Mac mount shell | **no** |
| optimise_squad.py / scenario_squad.py (PuLP ILP) | Mac mount shell, pulp pip-installed ad hoc | **no** |
| live bootstrap-static for raw/shrunk + live prices/clubs/status | Chrome download, served offline | **no** |
| ticked Trello checklist items (quarantine) | Trello connector, hand-transcribed to a scenario file | partly |
| per-player prior/raw/shrunk estimates | ad-hoc dump script | **no** |

## A. Prerequisites on the VM (before any tool)

- **A1 Repo clone on the VM**, `git pull --ff-only origin main` before every run. The
  VM is a runner, not the record: the repo stays the record and the Mac stays the
  Friday writer of squad.json / TEAM_CHANGE_LOG.md unless C1 below is built.
- **A2 Secrets in the server's environment:** `TRELLO_API_KEY` / `TRELLO_TOKEN`
  (read-only token) so `optimise_squad.py --quarantine` and `trello_quarantine.py`
  authenticate. Never in the repo.
- **A3 Python 3.10+ with `pulp` (CBC bundled)** — `requirements.txt` already pins
  `pulp>=3.1`. Verify with `python3 test_optimise_squad.py`.
- **A4 Fix `build_squad.LIVE_STATUS_EXCLUDE`** — it drops status `u`/`n` only, so an
  injured player (status `i`, chance_of_playing 0) still enters the pool; the GW5
  shrunk run recommended Hinshelwood (ankle, back 10 Oct). Exclude `i`, and scale
  `d` by chance_of_playing or exclude below a threshold. Without this every
  cloud-served answer needs a hand cross-check against `injury_report`.
- **A5 Decide the home of `docs/data/*`** written by `entry_summary` /
  `captaincy_snapshot_refresh`. Today they land on the VM and the Mac's copy is
  stale (entry_summary.json on the Mac still reads GW3/167 pts after the VM wrote
  GW4/261). Either the VM commits them (needs C2) or `publish_dashboard.sh` calls
  the VM's tools before building.

## B. Read/compute tools (the minimal cloud-only set)

All wrap existing scripts via subprocess in the repo clone; none writes to the
repo except the fixture window and the docs/data snapshots already written today.
Every response must carry: window stamp + live GW, estimator, intel ON/OFF,
quarantine ON/OFF, the two preference-cost lines, the LIVE FETCH / PRICE / CLUB /
STATUS / CONTAMINATED stderr lines verbatim (never swallowed), and repo HEAD.

1. **`repo_sync()`** — fetch + ff-only pull of the VM clone; returns HEAD,
   ahead/behind, dirty files. Called implicitly at the start of every tool below;
   a tool refuses (or flags loudly) if the clone is behind origin or dirty.
2. **`refresh_fixture_window(gw=None)`** — runs the fixture_difficulty model
   in-process and `fixture_adjust.py --update --gw N`, defaulting N to the live
   next GW. Removes the paste-the-table step. Returns the stamp and the 20 rows.
3. **`optimise_transfers(transfers=1, hits=False, estimator="shrunk",
   intel=True, quarantine=True, fixtures=True, haaland=False,
   max_attackers_per_club=2, free_transfers=None, gate=None,
   force_in=[], force_out=[], role_rivals=[], allow_contaminated=False)`** —
   wraps `optimise_squad.py`. Refuses if the window stamp ≠ live GW. Returns the
   script text plus structured JSON: gain xP/90, out/in, 5-GW net, breakeven GWs,
   HOLD flag, bank after, preference costs. `transfers=None` = wildcard rebuild
   mode. `quarantine=True` fails loudly (not fence-only fallback) if Trello is
   unreachable, per the script's own rule.
4. **`optimise_scenario(rows=[...], transfers=1, estimator="shrunk",
   base_intel=True, fixtures=True, force_in=[], force_out=[])`** — wraps
   `scenario_squad.py` with the 9-field rows passed inline (server writes a temp
   file). Output keeps the HYPOTHETICAL banner and the applied/unmatched audit.
5. **`optimise_matrix(estimators=["prior","raw","shrunk"],
   overlays=["fence","quarantine"], transfers=[1,2], extra_rows=[])`** — runs
   the grid (today: 12+ runs by hand, ~15 s each) and returns one table. Long
   call: either cache per (HEAD, window stamp, bootstrap etag) or run async and
   return a job id — an MCP call that takes 3–4 minutes will time out in Cowork.
6. **`quarantine_report()`** — wraps `--quarantine-report`: every ticked
   Required-Decisions item on Take-action cards, parsed rows, skipped items with
   reasons, and which ones are no-ops because the fence already holds them.
7. **`intel_report()`** — wraps `intel_adjust.py --report`: fence rows, stp/xP
   off vs on per player, stale-window warnings, unmatched names (Ruggeri today).
8. **`player_estimates(names=[] | squad=True, candidates=True)`** — per player:
   stp, xg90, xa90, cbit90, xP_flat and xP_adj under prior / raw / shrunk × intel
   on/off, live price, status, chance_of_playing, contaminated flag. This is the
   "raw, priors, shrunk" view; today it was an ad-hoc script.
9. **`squad_state()`** — `squad_state.py`-validated squad.json from the clone:
   fifteen, roles, bench order, captain/vice, bank, chips, `selected_on`, plus a
   live-price drift column (bought_for vs now_cost, the B1 gap) so a cloud brief
   never spends a phantom surplus.
10. **`repo_file(path)`** — read-only text of an allow-listed file
    (`ROLE_INTEL.md`, `TEAM_CHANGE_LOG.md`, `SELECTION_FRAMEWORK.md`,
    `METHODOLOGY_ALTERNATIVES.md`, `fixture_window.json`, `scenarios/*.txt`,
    `docs/data/*.json`). No globbing outside the allow-list.
11. **`bench_value()`** (optional) — `size_bench_value.py`, with its unit-trap
    note carried in the response so nobody adds it to XI xP/90.

Minimal set to make "run a scenario optimisation" cloud-only: A1–A4 + tools 1, 2,
3, 4, 6, 8, 9, 10. Tools 5, 7, 11 are convenience.

## C. Write tools (phase 2, gated — not needed to *request* an optimisation)

- **C1 `record_decision(...)`** — writes squad.json + TEAM_CHANGE_LOG.md +
  `selected_on`, validates with `squad_state.py`, commits via the scratch-clone
  path. Requires an explicit confirmation string in the call; append-only on the
  log; never touches ROLE_INTEL.md (that stays the Friday review's).
- **C2 `publish_dashboard()`** — `publish_dashboard.sh` + commit of `docs/`, so
  VM-written `docs/data` snapshots reach the public page without the Mac.
- **C3 `save_scenario(name, rows)`** — persist a scenario file under `scenarios/`
  and commit, so a cloud what-if is reproducible.
- `log_predictions` already exists on the server and is append-only.

## D. Operating rules the tools should encode

- Tool defaults = the weekly configuration: `--fixtures`, intel ON, estimator
  `shrunk`, quarantine ON. Fence-only and prior are opt-in comparisons, not the
  default, because the fence-only/prior answer on 15 Sep (buy O'Reilly) was an
  artefact of a stale 75% start row Sylvan's ticked 65% overrides.
- Standing preferences (no Haaland, max 2 attackers/club) stay as overridable
  constraints with their cost printed; a cloud call states which were active.
- Every result that names a player runs him through the status flag and the
  contaminated fence before returning; a recommendation of a flagged player is
  an error, not a footnote.
- Ties (`no gain above 0.01`) are returned as HOLD, never resolved by the tool.

## Status — built 15 Sep 2026

Implemented in `vm_runner.py`, registered by `fpl_research_mcp.py` only when
the server's environment has `FPL_RUNNER=1` (the VM's systemd drop-in). The
Mac's stdio server never loads them. Tests: `python3 test_vm_runner.py`.

| Item | State |
|---|---|
| A1 clone + ff-only sync | `repo_sync()` before every tool; cron uses `vm_runner.py --sync` |
| A2 Trello secrets | **done 16 Sep 2026** — `/etc/fpl-mcp/runner.env` (root, 0600) via `EnvironmentFile=`; fresh Power-Up key + read-only token, overlay verified live from the VM |
| A3 PuLP + CBC | installed in the service venv (aarch64, PuLP 3.3.2) |
| A4 status exclusion | `i` excluded; `d` below 50% chance excluded, 50%+ reported as STATUS DOUBTFUL |
| A5 docs/data home | **open** — see below |
| B1–B11 | all built; B5 is `optimise_matrix` (background job) + `optimise_job(job_id)` |
| C1–C3 | not built (phase 2) |

How the rules in D are enforced:

- Tool defaults are the weekly configuration. A call that isn't says so with a
  "not the weekly configuration" note.
- Every response starts with repo HEAD, window stamp, live GW, estimator,
  intel/quarantine state, both preference-cost lines, then the stderr
  LIVE-DATA lines, the full stderr verbatim, the script text and the JSON.
- `optimise_squad.py --json` / `scenario_squad.py --json` carry each named
  player's status, chance, `ok` and `contaminated` flags. The runner turns a
  MOVE naming a flagged player into `ERROR_FLAGGED_PLAYER`. A `d`/`s` player
  it lets through comes with a warning.
- `build_squad.load()` now tags admitted movers `contaminated=True`, so even
  `allow_contaminated=True` can't return one as advice.
- HOLD stays HOLD. The runner never re-solves a tie.
- Repo rule: a runner-owned file (`fixture_window.json`, `docs/data/`, `logs/`)
  that origin also changed is copied to `~/.fpl-mcp/runner-backup/` and reset
  before the pull. Any other dirty file, or a clone ahead of origin, makes
  every tool refuse.

Also changed along the way: `optimise_squad.py` gained `--force-in/--force-out`
(scenario_squad.py had them, the weekly tool never parsed them), bank-after
lines, and a PRICE OF THE PREFERENCES block in transfer mode, which had none.
`_sell_price` moved to `squad_state.sell_price` so `squad_state.py --json --live`
can report realisable sell value without PuLP.

A5, still to decide: the VM's `entry_summary` / `captaincy_snapshot_refresh`
writes stay local to the clone as runner-owned files and are reset (with a
backup) whenever origin updates them. Until C2 exists they do not reach the
public page. `publish_dashboard.sh` on the Mac should keep calling its own tools.
