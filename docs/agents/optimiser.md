# Squad optimiser: exogenous preferences and the pre-run dialogue

`optimise_squad.py` is an exact ILP over expected points (see its own
docstring, "THE FORMULATION"). Standing choices are layered on top as
constraints, not as edits to the underlying model:

| preference                          | default | change per run                      | disable entirely            |
|--------------------------------------|---------|-------------------------------------|------------------------------|
| exclude Haaland                      | **off** (since 16 Sep 2026) | `--no-haaland` to exclude him | (default) — `--haaland` is an accepted no-op |
| max attackers (MID+FWD) per club     | 2       | `--max-attackers-per-club N`        | `--no-max-attackers-per-club`|

Neither is an FPL rule. The real rules — £100m starting budget, 2-5-5-3 squad
shape, max 3 players per club — live in `constants.py` and never change. These
are Sylvan's standing choices, applied as constraints specifically so their
cost is measurable rather than silently baked into a result labelled
"optimal". Every run prints the point cost of holding each one ("PRICE OF
THE PREFERENCE" / "PRICE OF THE CONCENTRATION PREFERENCE").

The concentration preference exists because the objective is
`sum(score_i * x_i)` — additive across players, blind to correlation. Three
attacking returns sources from the same club can blank or explode together
on the same match result; the flat expected-value objective can't see that,
only variance can, and this codebase's solver (PuLP/CBC) doesn't do
quadratic objectives. Capping MID+FWD-per-club at 2 is the linear surrogate
for that risk.

## Before running the optimiser

Whenever a request — from Sylvan directly, or a scheduled skill such as the
weekly brief — asks to run the optimiser, open with a short statement of the
active defaults and a choice, before executing anything:

  - Haaland: allowed (exclusion is opt-in since 16 Sep 2026)
  - max attackers per club: 2
  - wildcard/rebuild budget: squad selling value + bank (not £100m)

Ask (via AskUserQuestion in an interactive session) whether to proceed with
both defaults, or clear/adjust one. Do not run first and ask after — the
point of the dialogue is that the constraints shape which squad comes back,
not that they get explained afterward.

For an unattended/scheduled run with no one to ask, proceed with the
defaults above and state plainly in the output which settings were used
(the script already does this: the "pool N players · ... · no Haaland · max
2 attackers/club" line, and the PRICE OF THE PREFERENCE sections) — never
change a default silently for a scheduled run just because no one was there
to confirm it.

## Wildcard budget — selling value plus bank, not £100m

A wildcard is unlimited free transfers, not a fresh start. FPL lets you spend
what the current fifteen sell for (a fall in full, half of any rise rounded
down to £0.1m) plus the bank. Rebuild mode (no `--transfers`) therefore budgets
at `squad_state` selling value + bank, and costs any player it KEEPS at his
sell price, the same rule transfer mode uses. `--budget 100` reproduces the old
fresh-£100m answer for comparison only; `--budget` is refused in transfer mode.
Changed 16 Sep 2026 (GW5: £98.2m + £1.3m = £99.5m, not £100m).

## Trello quarantine overlay (`--quarantine`) — opt-in, off by default

`--quarantine` layers every **ticked** row item on a `Rows in model` checklist
(**Live in model** list) or a `Decisions` checklist (**Quarantined decisions**
list) onto the ROLE_INTEL fence — board reshaped 17 Sep 2026 — for that one
run only. Nothing is written to Trello, `ROLE_INTEL.md` or the repo; the
Friday review is still the only path from "approved" to "permanent". Without
the flag, output is byte-for-byte the fence-only result (verified 15 Sep 2026
by diffing before/after runs in both transfer and rebuild modes).

When stating the active defaults before a run, say whether the overlay is on.
A quarantine run can recommend a different transfer from the fence-only run —
on 15 Sep 2026 Sylvan's ticked O'Reilly stp 0.65 dropped him below the 75% XI
gate and replaced Virgil -> O'Reilly with Van de Ven -> Botman.

| flag | does |
|---|---|
| `--quarantine-report` | fetch + parse + resolve, print what each ticked item would do vs the fence (`NEW`, `CHANGES`, `REMOVES`, `same as fence`, `OUT OF WINDOW`, `DROPPED`). Never optimises. Run this first. |
| `--quarantine` | apply the overlay; touched players are marked `(quarantine: field)`, and a banner plus a per-item status table print before the results |
| `--allow-fence-only-fallback` | with `--quarantine`, run fence-only (with a loud banner) instead of exiting if Trello cannot be read |

Semantics worth knowing before trusting a result — full detail in
`trello_quarantine.py`'s docstring:

- **Replace, never stack.** Ticks stay ticked after promotion, so an overlay
  entry replaces every fence entry for the same (player, team, field).
- **Windows gate.** `GWs a-b` must contain the fixture window's target GW, or
  the fence value stands. Stricter than the fence's own `gws`, deliberately.
- **Unparseable, unmatched, ambiguous or conflicting ticks are dropped with a
  warning**, never guessed.
- **Needs `TRELLO_API_KEY` and `TRELLO_TOKEN`** in the environment — the board
  is private. Never commit them; this repo is public. `--quarantine` cannot
  combine with `--no-intel`.

## Running it from a cloud session (VM runner)

When the VM's fpl-research connector has the runner tools (`optimise_transfers`,
`optimise_scenario`, `optimise_matrix`/`optimise_job`, `refresh_fixture_window`,
`quarantine_report`, `player_estimates`, `squad_state`, `repo_file`, ...), the
same pre-run dialogue applies. State the defaults first: objective
start-weighted xP/GW, estimator shrunk, start rate shrunk, intel ON, quarantine
ON, fixtures ON, Haaland allowed, max 2 attackers/club.
The tools refuse on a stale fixture window (call `refresh_fixture_window`
first) or a clone that isn't origin's. They return a flagged player as an
ERROR, never as advice. See `VM_OPTIMISER_TOOLS.md`.

## Fixture-window gameweek weighting

`--fixtures` scores on xP_adj over a 4-GW window whose opponent multipliers are
a weighted mean, next GW first: 40 / 30 / 20 / 10 (`constants.FIXTURE_GW_WEIGHTS`,
15 Sep 2026; previously equal). The weights are stamped into
`fixture_window.json`. A window without them, or with different ones, is stale
and gets auto-refreshed (the VM runner refuses and asks for
`refresh_fixture_window`). The `fixture_difficulty` research tool stays
equal-weighted unless given `gw_weights`.

## Start rate — shrunk by default since 16 Sep 2026 (GW5)

`stp` blends each player's 2025/26 last-16 start rate with his 2026/27 starts
per team match (`--stp-estimator shrunk`, roadmap A0.2). It decides the 75% XI /
60% bench gates and is not part of xP/90, so it changes who is eligible, not
anyone's score. A ROLE_INTEL `set stp` still overrides it. `--stp-estimator
prior` restores the frozen rate; `--compare-stp` shows both. When stating the
defaults before a run, say start rate is shrunk.

## Start-weighted objective — THE DEFAULT since 16 Sep 2026 (A0.5, GW5)

Scores stp × xP per GAMEWEEK instead of xP/90, with a 50% XI floor in place of
the 75% gate. Every figure is xP/GW and is NOT comparable with the xP/90
figures logged before 16 Sep 2026, so always say which objective a quoted
number came from. `--per90` (or `start_weighted=False` on the VM runner) gives
the old objective; `--compare-start-weighted` shows both. Its 5-GW net and
breakeven lines are the unit-consistent ones for judging a −4 hit. When stating
the defaults before a run, include "objective start-weighted xP/GW".
