# FPL — River Leaf FC

A reproducible Fantasy Premier League selection pipeline. The point of this
repo is that **no team decision should exist only in a conversation**: every
squad, transfer and captaincy call is produced by a script that can be re-run,
and every human override is logged and later scored.

## Layout

### Pipeline

| File | Does |
|---|---|
| `build_squad.py` | Applies the five selection gates and reproduces the live squad exactly |
| `optimise_squad.py` | Tests transfers against the current squad under budget/formation/club constraints |
| `fixture_adjust.py` | Weights expected points by the fixture window |
| `build_dashboard.py` | Emits `FPL_DIAGNOSTICS.html`, one self-contained diagnostic page |
| `make_artifact.py` | Wraps the dashboard for publishing |
| `verify_dashboard.js` | Executes the dashboard's inline script against a stubbed DOM — a syntax error there kills the page silently |

### Research server

`fpl_research_mcp.py` is a read-only MCP server over the public FPL API.
It has **no write path** — it cannot change the team, and stores no
credentials. `test_fpl_mcp.py` covers it; `install_fpl_mcp.sh` and
`diagnose_fpl_mcp.sh` install and troubleshoot it. See `FPL_MCP_SETUP.md`.

### Inputs (committed — the pipeline does not run without them)

| File | Is |
|---|---|
| `fpl_priors_2025_26_v2.json` | Frozen prior-season snapshot, current |
| `fpl_priors_2025_26.json` | Previous snapshot, kept for fallback |
| `last16_starts.json` | Starts over GW23–38 of 2025/26, sourced from `vaastav/Fantasy-Premier-League`, provenance stamped in the file. **Externally derived, not the official API** |
| `fixture_window.json` | Current fixture window |
| `fpl_calibration_log.jsonl` | Logged captaincy predictions, for scoring calibration |
| `template.html` | Dashboard source template |

### Documents

- `SELECTION_FRAMEWORK.md` — the gates, and the only circumstances in which judgement may override the model
- `METHODOLOGY_ALTERNATIVES.md` — approaches considered and why they were or weren't adopted
- `TEAM_CHANGE_LOG.md` — every team and strategy change actioned
- `GLOSSARY.md`, `ROLE_INTEL.md`, `SWEEP_2026-08-08.md`
- `WEEKLY_WORKFLOW.svg` — the weekly loop

## Running it

```bash
pip3 install mcp httpx
python3 build_squad.py            # reproduce the live squad
python3 build_squad.py --season-starts   # pre-9-Aug-2026 gate, for comparison
python3 optimise_squad.py         # test transfers
python3 build_dashboard.py && node verify_dashboard.js   # rebuild + verify the dashboard
```

Always run `verify_dashboard.js` after touching the dashboard. The HTML will
look complete and the file size will look right even when nothing renders.

## Not committed

`__pycache__`, the SQLite history cache, and the generated dashboard HTML/JS.
Rebuild the dashboard rather than pulling it.
