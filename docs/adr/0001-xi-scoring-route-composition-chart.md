# 0001. XI scoring-route composition chart (page 1)

**Status:** Accepted — pre-build, per `DASHBOARD_PLAN.md`'s own precedent of logging
the decision before writing code so the build can be judged against what it
set out to do.

**Logged:** 14 Aug 2026, resolved via a `/grill-me` session. GW1 deadline is
21 Aug 2026.

## Context

Starting ask: "confidence that the optimiser is picking a balanced squad that
reflects the routes to points." That framing doesn't survive contact with
`optimise_squad.py`: the objective is `Σ score[i] * x[i]`, a pure sum of
`xP_adj`, constrained only by budget/formation/club-cap. A route-balance
constraint added there can only ever match or *reduce* total xP — a
constrained LP never beats its unconstrained optimum — so "balance" isn't an
accuracy question the optimiser can answer.

Reframed: this is not a solver constraint. It's a **human-in-the-loop risk
read** — a chart on the squad page that unblends `xP_adj` back into the
categories that produced it, so a person can apply judgement the blended
number hides (specifically: distrust of one route, e.g. bonus).

## Decision

Build a **squad-level composition chart** on page 1 (`docs/index.html`,
the squad page), showing the XI's expected points broken into six categories,
sourced from the existing additive terms inside `scoring.py`'s
`expected_points_scaled()` — no new modelling, just exposing intermediate
values that are currently computed and discarded.

### Categories and formula source

| Category | Formula (per player, per 90) | Applies to |
|---|---|---|
| Appearance | `APPEARANCE` (fixed, 2) | all |
| Goal Involvement | `GOAL[pos] * xg90 + ASSIST * xa90` | all (negligible for GKP) |
| Clean Sheets | `CS[pos] * p_cs`, `p_cs = exp(-xgc90)` | all except FWD (`CS[FWD]=0`) |
| Defensive Contribution (net) | `DC_PTS * p_threshold(...)`, **netted against `-xgc90/2`** for GKP/DEF only | all |
| Saves | `sv90 / SAVES_PER_POINT` | GKP only |
| Bonus | `xbonus90` | all |

**Netting detail:** `-xgc90/2` (goals-conceded penalty) is its own additive
term in the formula, scoped to GKP/DEF, and is negative — it doesn't fit a
non-negative stacked-composition chart as a standalone slice. It's merged
into Defensive Contribution and the category relabelled "net defensive
value" so it isn't confused with the raw DC-points-only figures shown
elsewhere (the CBIT screens). For MID/FWD, who don't carry the `-xgc90` term,
this category is the CBIRT-based DC term, unmodified.

**Bonus is flagged, not just plotted.** `scoring.py`'s `bonus_shrinkage()`
prints a warning — *"treat xbonus90 as unvalidated"* — when its shrinkage
constant falls back to a clamp. Since this v1 ships without confidence
intervals (see Deferred, below), Bonus gets a visual flag (distinct
hatching/marker, not a numeric band) rather than rendering as an
equal-confidence slice next to Clean Sheets or Goal Involvement. This follows
`DASHBOARD_PLAN.md`'s page-1 principle directly: *"do not hide the
uncertainty — it is the best lesson on the page."*

### Scope: XI only, start-weighted, reconciled to the existing header total

Page 1's header strip already shows `XI xP/GW` — per `build_squad_page.py`,
computed as `Σ (stp * score)` over the XI, where `stp` is start probability
and `score` is `expected_points_scaled()` (fixture-adjusted). This chart
**must total to that same figure**, not a flat per-90 or unweighted number,
or the page will show two disagreeing totals side by side.

This reconciles cleanly: `stp` multiplies the whole per-player score
linearly, so `stp * score = Σ_category (stp * category_term)`. Build each
category's chart value as `Σ_XI (stp * category_term(player))` and the six
slices sum to `XI xP/GW` exactly, category-by-category, no separate
normalisation step needed.

Bench (4 players) is excluded — including it would add a second total that
doesn't match either existing header figure (`XI xP/90` or `XI xP/GW`).

### Deferred: confidence intervals

The original ask evolved toward showing confidence limits per category. Not
in v1. The uncertainty representations aren't uniform across categories —
Gamma-Poisson dispersion (`_estimate_k`) for Goal Involvement, a separately
derived and explicitly-flagged-unvalidated `k` for Bonus, and a nonlinear
transform of Poisson uncertainty (`exp(-xgc90)`) for Clean Sheets — reconciling
three different uncertainty models into one visual scale is a new
statistical feature, not a cheap panel over existing sums. It belongs as a
future gated roadmap item, in the shape of `METHODOLOGY_ALTERNATIVES.md`'s
A1/A4 entries (named gate, kill criterion), once the underlying category-level
calibration can actually be checked — realistically no earlier than the GW6/
GW10 calibration reads already gating other roadmap items.

### Verification

`verify_dashboard.js` / `publish_dashboard.sh` already refuse to publish a
page whose panels don't build with non-empty data. Extend that check for this
panel: **assert `Σ categories == XI xP/GW` within float tolerance at build
time, and fail the build if it drifts.** Without this, a future change to
`scoring.py` (new category, changed coefficient) can silently break the
reconciliation this chart's whole premise depends on — exactly the failure
class the page-3 build's "fail loudly, never silently" rule exists to
prevent.

## Consequences

- No change to `optimise_squad.py` or any squad-selection logic. This is
  read-only, decision-support for a human, not a constraint.
- Bonus's known-unvalidated status is now visible on the squad page itself,
  not just in a code comment.
- The chart's total is now a second place (besides the header strip) that
  depends on `XI xP/GW`'s definition — if that definition changes (e.g. a
  future start-weighting refinement), both need updating together. Worth a
  code comment cross-referencing this ADR at both call sites when built.
- Confidence-interval version is explicitly out of scope and not promised on
  any timeline; revisit only once category-level calibration is checkable.

## Open (deferred to build time, not blocking)

- Exact chart type/placement within `docs/index.html` (single stacked bar vs.
  other Chart.js 4.5.0-compatible layout) — implementation detail, not a
  design fork.
- Exact visual treatment of the Bonus flag (hatch pattern vs. marker vs.
  footnote) — pick one during build, consistent with existing contamination-
  badge styling on the same page.
