# CLAUDE.md

## Agent skills

### Issue tracker

Issues live in GitHub Issues for `sylvan-s/fpl-river-leaf`, using the `gh` CLI. See `docs/agents/issue-tracker.md`.

### Triage labels

Default vocabulary — `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context layout — `CONTEXT.md` + `docs/adr/` at the repo root, created lazily as terms and decisions get resolved. See `docs/agents/domain.md`.

### Squad optimiser preferences

`optimise_squad.py` holds standing preferences (no Haaland, max attackers per club) as overridable ILP constraints and reports the point cost of each. Before running it, state the active defaults and ask whether to proceed or clear one — see `docs/agents/optimiser.md`.
