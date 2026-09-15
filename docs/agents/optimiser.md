# Squad optimiser: exogenous preferences and the pre-run dialogue

`optimise_squad.py` is an exact ILP over expected points (see its own
docstring, "THE FORMULATION"). Two standing choices are layered on top as
constraints, not as edits to the underlying model:

| preference                          | default | relax per run                      | disable entirely            |
|--------------------------------------|---------|-------------------------------------|------------------------------|
| exclude Haaland                      | on      | `--haaland`                         | (same flag)                  |
| max attackers (MID+FWD) per club     | 2       | `--max-attackers-per-club N`        | `--no-max-attackers-per-club`|

Neither is an FPL rule. The real rules — £100m budget, 2-5-5-3 squad shape,
max 3 players per club — live in `constants.py` and never change. These two
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

  - exclude Haaland: ON
  - max attackers per club: 2

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

## Trello quarantine overlay (`--quarantine`) — opt-in, off by default

`--quarantine` layers every **ticked** item on a `Required Decisions`
checklist on a **Take action** card onto the ROLE_INTEL fence, for that one
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
