# CLAUDE.md

## Repo sync — do this before anything else

**Run `bash preflight.sh` at the start of every session, before reading a
file or forming any view of repo state.**

`git status` is not a truthful answer in this repo. Cowork commits through
`safe_git_commit.sh`, which pushes from a scratch clone and deliberately
never advances this working tree's HEAD — so already-pushed files keep
showing as "changed" indefinitely, on a HEAD that may be many commits stale.
The only meaningful question is how the tree differs from `origin/main`
after a fresh fetch, which is what `preflight.sh` answers.

Do not resolve a divergence wholesale in either direction. On 12 Sep 2026
the same tree had `prediction_tracker.json` **older** locally and
`fixture_window.json` **newer** locally; committing the lot would have
destroyed a gameweek of prediction history. Direction is a per-file call.

Commit with `safe_git_commit.sh` from Cowork, plain git locally. See
`docs/agents/sync.md`.

## Agent skills

### Issue tracker

Issues live in GitHub Issues for `sylvan-s/fpl-river-leaf`, using the `gh` CLI. See `docs/agents/issue-tracker.md`.

### Triage labels

Default vocabulary — `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context layout — `CONTEXT.md` + `docs/adr/` at the repo root, created lazily as terms and decisions get resolved. See `docs/agents/domain.md`.

### Squad optimiser preferences

`optimise_squad.py` holds standing preferences (no Haaland, max attackers per club) as overridable ILP constraints and reports the point cost of each. Before running it, state the active defaults and ask whether to proceed or clear one — see `docs/agents/optimiser.md`.
