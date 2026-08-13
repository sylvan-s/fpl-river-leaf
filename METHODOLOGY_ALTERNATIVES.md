# Methodology alternatives — assessment notes

---

## IMPLEMENTATION STATUS — built 7 Aug 2026

D1–D6 are **built and unit-tested**, but **not yet wired into the weekly brief**.
They are available as tools; the brief still runs the original screens. Adopt only
if the GW10 bake-off justifies it.

| Design | Status | Where |
|---|---|---|
| D1 rates-in / points-out | built | `_rates()`, `SHRINK_METRICS` |
| D2 baseline fallback ladder | built | `_baseline()` |
| D3 `k` derived from variance | built | `_estimate_k()` |
| D4 baseline bake-off | built | `predictive_backtest(compare_shrinkage=True)` |
| D5 scope limit (no xP) | **honoured** — screens still output archetypes | — |
| D6 captaincy distributions | built | `captaincy_odds()` |
| A0.1 availability + suspension | built 8 Aug 2026 | `_availability()`, `_suspension()` |
| **xP from FPL's scoring table** | built 9 Aug 2026 | `build_squad.py:expected_points()` |
| **Exact ILP optimiser** | built 9 Aug 2026 | `optimise_squad.py` |
| **xP validated against FPL's own official xP** | checked 11 Aug 2026 | see below |

**The xP model replaced hand-picked coefficients.** The first selection scorer used
`xGI/90 × 8` and `(1.6 − xGC/90) × 6` — numbers that appear nowhere in FPL's rules.
Sylvan rejected them: the point values are set by the game. Every coefficient is
now a rule (6/5/4 per goal by position, 3 per assist, 4/1/0 clean sheet, 2 for the
DC threshold, −1 per 2 conceded, saves ÷ 3). **13 of 15 players were unaffected**,
which is the reassuring part — the squad was not an artifact of the invented
constants.

**The optimiser replaced greedy slot-filling.** Measured, not asserted:

| Budget | ILP | Greedy |
|---|---|---|
| £100.0m | 49.54 | 49.54 — identical |
| £95.0m | 48.77 | **no feasible squad** |
| £85.0m | 45.85 | **no feasible squad** |

At full budget greedy is optimal and the ILP wins nothing. Below it greedy does
not degrade — **it fails**, because it never consults the budget while choosing.
**The tight case is the normal case**: every mid-season transfer is made with
£0.5m in the bank against a fixed squad.

**Two things the ILP exposed about itself.** With bench xP contributing nothing,
the solver was indifferent among equal-priced fodder and picked a 61%-starter — an
epsilon-weighted term now prefers fodder who actually play. And **the no-Haaland
preference had been hardcoded into something labelled "optimal"**; preferences are
now priced on every run (Haaland costs 0.06 xP/90).

**Dependency:** PuLP, with its bundled CBC solver. `pip install pulp` — no other
requirement, and nothing else in the project depends on it.

### External xP validation — checked 11 Aug 2026

`fetch_gw_history.py` has fetched FPL's own official per-gameweek `xP` field
since 9 Aug, flagged in its own docstring as "a free external benchmark for
our model" — but nothing had actually run the comparison. Checked now.

**Method.** Matched all 261 players from the 2025/26 archive with 450+ minutes
against the current pool's `score` field (both derived from the same
last-season underlying rates, so the comparison is fair pre-season). For each
player: summed FPL's own `xP` and `total_points` across the season, divided by
`minutes/90` to get true per-90 rates, and correlated against our `score`.

**Result — our model tracks reality better than FPL's own xP does:**

| | mean xP/90 | corr with actual pts/90 |
|---|---|---|
| FPL's official xP | 1.18 | **0.51** (r² ≈ 0.26) |
| Our `score` | 3.70 | **0.71** (r² ≈ 0.50) |

Correlation between our `score` and FPL's own xP is only **0.43** — the two
disagree a lot, and FPL's own xP sits at roughly a third of the real per-90
points scale (1.18 predicted vs 4.23 actual). That looks alarming until you
check which one actually predicts outcomes: FPL's official xP explains about a
quarter of the variance in real results, ours explains about half. **Palmer is
the clean example** — FPL's own xP had him at 1.00/90 (badly underrating him
against Chelsea's set-up), actual output was 5.25/90, and our `score` landed
at 5.24 — almost exact.

**Conclusion: do not treat FPL's own xP as ground truth for future checks.**
It is a known-blunt, publicly-conservative number, not a gold-standard
benchmark — this closes the "free external benchmark" question raised in
`fetch_gw_history.py` with a negative result for FPL's xP, not for ours. The
GW10 backtest (below) remains the real test, since it checks against actual
outcomes directly rather than against another model's guess.

**A0.1 fixed a live bug rather than adding a feature.** P(start) was drawn purely
from a player's historical start rate, so a **suspended or injured player still
received a full probability of starting** — P(blank) was worst exactly where it
most needed to be right. Status flags now zero it out, and doubtful players scale
by `chance_of_playing_next_round`.

### BUG FIXED 8 Aug 2026 — `_estimate_k` was broken for the entire xG family

Found while planning the diagnostic dashboard (B6). **The dashboard justified
itself before it existed.**

**The symptom.** `k` came back at exactly 40.0 or 60.0 for xGI — the fallback and
the clamp, not derived values:

```
DEF cbit : between_var = +3.34     -> k = 2.3    healthy
MID xgi  : between_var = +0.00018  -> k = 60     hit the cap
FWD xgi  : between_var = -0.0275   -> k = 40     NEGATIVE -> fallback
```

**Negative between-player variance is impossible.** It meant the noise model was
wrong, not that the players were identical.

**The cause.** `_estimate_k` assumed Poisson counts: `sampling_var = rate/n90`.
Correct for **CBIT** — tackles and clearances are whole events, and it worked
fine there. Wrong for **xGI**, which is a sum of per-shot *probabilities* (~0.11
each), never whole events. Its true variance is roughly `q ×` the Poisson value.
So the model overstated the noise, between-variance collapsed, and k pinned to
its maximum.

**Why it mattered.** `k` is in units of 90s, so **k = 60 means 60 full matches
before a player's own data carries half the weight. A season is 38.** Every
attacker would have stayed frozen on his 2025/26 prior all season, and "trust
shrunk early, raw late" would silently have meant "ignore this season". It was
invisible pre-season only because observed *is* the baseline then — **it would
have started doing damage at GW1.**

**The fix.** A per-metric `DISPERSION` factor: 1.0 for counts, 0.11 for the xG
family.

| Pool | before | after | |
|---|---|---|---|
| MID xGI | 60 (capped) | **15.5** | fixed |
| FWD xGI | 40 (fallback) | **27.1** | fixed |
| DEF CBIT | 2.3 | 2.3 | unchanged — counts were always right |
| GKP xGI | 40 | 40 | **correctly** still degenerate: keepers genuinely do not differ on xGI |

**`q = 0.11` is assumed, not derived** — shots are in no endpoint this file
fetches. From GW1 `player_gw` gives match-to-match variance directly, which
supersedes the constant; `_estimate_k(empirical_var=...)` already accepts it.

**The silence was the real defect.** A bare `return 40.0` hid a model failure
behind a plausible number. `_k_degenerate()` now flags fallback values and both
screens print a warning when `k` was not derived.

### D7 — opponent adjustment in captaincy (built 8 Aug 2026)

**The gap this closed.** `captaincy_odds` had **zero** fixture or opponent
references. It used the player's own season-average xG and his own team's
season-average xGC — answering "what does he do in a typical match", not "what
will he do against this opponent on Saturday". For a tool whose only job is a
single-fixture decision, that was worse than the fixture-difficulty heuristic it
replaced.

**A fixture has TWO difficulties, and FDR collapses them into one integer:**

| For your… | What matters | Measured by |
|---|---|---|
| Attackers | opponent's **defensive** weakness | their xG conceded |
| Defenders / GK | opponent's **attacking** potency | their xG created |

A side that concedes heavily *and* scores heavily is **good for your attackers
and bad for your defenders simultaneously.** One number cannot say that.
Demonstrated in the test suite: against a solid/blunt opponent the defender
out-scores the striker (4.24 vs 4.19); against a leaky/potent one the striker
wins by miles (7.78 vs 3.68). Same two players, ranking flipped by opponent
*profile*.

**Implementation.** FPL's own `strength_attack_*` / `strength_defence_*` fields
are **all zero pre-season**, so team strength is derived from player xG instead:

- team xG per game = summed player xG ÷ games played
- team xGC per game = mean per-90 xGC of the six highest-minute regulars (they
  were on the pitch for most of it)
- Both **shrunk toward the prior season** by games played (`K_TEAM = 6`), same
  logic as player shrinkage — so pre-season it uses priors, and converges on
  current-season data as the year progresses
- Factors are **ratios to the league average**, so absolute calibration cancels

Validated against real 2025/26 data: Arsenal best defence (0.71 xGC/game, 19
clean sheets), Man City best attack (2.15 xG/game), Fulham worst (0.75) —
promoted sides correctly return no data.

**Home advantage** is applied symmetrically (`HOME_FACTOR` 1.13 /
`AWAY_FACTOR` 0.89, ≈0.3–0.4 goals a game): at home your attack scales *up* and
the opponent's scales *down*; away, both reverse.

**Double gameweeks** are handled by convolving the per-fixture point
distributions — so a DGW roughly doubles E[points] and materially raises
P(haul), which is exactly the Triple Captain case. **Blank gameweeks** return
zero.

**Known limitation:** promoted teams have no PL data and are assumed *league
average*, marked with `*` in the output. That is generous — promoted sides are
usually leakier — so players facing them are, if anything, understated. Revisit
once a few gameweeks exist.

**Still on FDR:** `fixture_difficulty` has not been converted and still averages
FPL's 1–5 integers. The team-strength machinery now exists to split it into
attack and defence difficulty; that is the obvious next piece.

### The calibration harness — the gate for full Bayesian modelling

`log_predictions()` and `score_calibration()`, writing to
`fpl_calibration_log.jsonl` (append-only).

**Why it exists.** A probabilistic model is only useful if its numbers mean what
they say. If `captaincy_odds` claims P(haul) = 20%, hauls must occur about 20% of
the time. That can only be checked against predictions recorded **before** the
gameweek — it cannot be reconstructed later, which is why logging has to start
now rather than when the question becomes interesting.

**Integrity controls, deliberate:**
- **Append-only.** The same player/gameweek is never overwritten; the first
  prediction stands. A record that can be revised after the outcome is worthless.
- **Pre-deadline check.** Each row stores `logged_after_deadline`, and
  `score_calibration()` excludes any row that fails it. Verified in testing: a
  late-logged prediction is refused at scoring time.
- Model settings (`shrunk`, `k`, `base`) are stored per row, so a later result
  can be attributed to the configuration that produced it.

**What scoring reports:** a reliability table (predicted vs observed haul rate by
probability bin), Brier score, skill score against the base rate, E[pts] MAE and
bias, and P(blank) predicted vs observed.

**How the verdict feeds the PyMC decision:**

| Result | Meaning |
|---|---|
| **Calibrated** (gap < 3%) | Probabilities can be read at face value. **No case for full Bayes on these grounds.** |
| **Over-confident** (hauls rarer than predicted) | The signature of treating λ as known when it is estimated — **exactly what full Bayes fixes.** But first check the gap is not driven by rotation, which is an intelligence problem no model solves. |
| **Under-confident** | Shrinkage likely too aggressive. Try a lower `k` before reaching for a bigger model. |
| **Negative skill score** | The model is worse than predicting the base rate for everyone. Investigate before trusting any of it. |

**Operational requirement:** run `log_predictions()` on the captaincy candidates
**every gameweek, before the deadline**. Miss a week and that week is gone. Review
from about GW15, when there is enough data for the bins to mean anything.

### The prior snapshot — TIME-CRITICAL, run before 21 Aug 2026

`bootstrap-static` serves **only the current season**. Pre-season it still holds
2025/26 totals; once GW1 completes they are overwritten and last season's
per-player rates are **gone from the endpoint permanently**. Every baseline in the
D2 ladder depends on them.

**Capture the snapshot:**

```bash
PY=$(python3 -c "import json,os;print(json.load(open(os.path.expanduser('~/Library/Application Support/Claude/claude_desktop_config.json')))['mcpServers']['fpl-research']['command'])")
"$PY" "/Users/sylvansitkey/Library/CloudStorage/GoogleDrive-sylvansitkey07@gmail.com/My Drive/FPL/fpl_research_mcp.py" --snapshot-priors
```

Writes `fpl_priors_2025_26.json` beside the server. Roughly 200 KB.

**Do NOT re-run after the GW1 deadline** — it would overwrite a good 2025/26
snapshot with 2026/27 data and silently destroy the baseline. The file carries a
`season_described` field and a warning note for exactly this reason.

### How the priors are used

`_baseline()` walks the D2 ladder for each player and metric:

1. **own prior-season rate** — requires ≥900 prior minutes, **same club**, and
   **no role change flagged in `ROLE_INTEL.md`**. A `?` in the `SP` column
   disqualifies the personal prior, because the old rate describes a different job.
2. **team × position** — when the club changed (Guéhi, Semenyo)
3. **position × price bracket** — when there is no PL history (van Ewijk)
4. **position overall** — last resort

The chosen source is reported alongside each estimate, so a shrunk number can
always be traced to the baseline that produced it.

**At GW1 shrinkage is a no-op** — with n = 0 the formula returns the baseline
exactly. Verified by test. Its value ramps through GW3–15 and fades as raw data
comes to dominate.

**Shrinkage only changes rankings when sample sizes VARY between players.** With
uniform n it is a monotonic transform and leaves correlations untouched — observed
in testing. Real seasons vary n through injury and rotation, which is where the
benefit lives.

### Correction to D6 found during implementation

The first build reported **P(blank) = 0.0% for everyone**, which is impossible.
Cause: the model gave every player appearance points plus a flat per-90 bonus,
putting a floor above the 2-point blank threshold — and, more seriously, **it
never modelled the chance of not starting**, which is the dominant source of
blanks in FPL.

Fixed by adding an explicit start probability from `starts / games`, with a
benched branch scoring 1, and by making bonus conditional on a return rather than
flat. A player with identical per-90 output but half the starts now correctly
shows **65% blank probability** against 30%.

---

Candidate approaches that could replace or augment the current screen-based
system. Not adopted; recorded for evaluation.

---

## 0. Price forecasting — logged Sat 8 Aug 2026. BUILD DECISION AT GW3.

**Status: not built. Deliberately deferred to ~GW3**, once real transfer-flow
data exists (all price fields are zero pre-season).

### Sizing first — this is a second-order effect

A price rise earns **budget, not points**, and only half of it: you bank 50% of a
rise rounded down, so £0.2m of paper gain returns £0.1m.

Across a season a manager who tracks prices well might accumulate **£2–3m** of
team value — roughly one upgrade tier across the squad, plausibly **20–40 points
over 38 gameweeks**. A single captaincy call swings ±10 points in one week.

**Effort here should be proportionate to that.** It is an order of magnitude
below the decisions already modelled.

### The design rule: price belongs in TIMING, not RANKING

**Price must never enter the player screens.** If a player is the right buy on
xGI, he is the right buy at £7.0m or £7.1m — a 0.1 difference does not touch an
18.52-vs-10.47 xGI gap.

Price answers exactly two questions, both about **when to act on a decision
already made**:

1. **Is a player I own about to fall?** Selling later costs value — act now.
2. **Is a watchlist target about to rise?** Buying later costs budget — act now.

Framed that way it prevents the entire error class below.

### The trap

Making a transfer *to capture* £0.1m, or worse taking a −4 for it. A free
transfer is worth perhaps 2–4 points of flexibility; a tenth of a million is
worth a fraction of a point.

**Price breaks a tie between two players already rated equally. It is never a
reason.**

### The second-order insight worth keeping

Net transfers are the crowd's opinion, and rising price means **rising
ownership** — good for team value, **bad for differential**. As ownership climbs,
owning a player protects rank but can no longer gain any. Same logic as `DiffUp`
in captaincy (`P(haul) × (1 − ownership)`).

**So a price rise on a player you own is genuinely two-sided.** Any tool must say
so rather than treating rises as unambiguously good.

### Where it actually matters — the wildcard, not the week

Budget binds hardest when rebuilding fifteen players at once. £2m of accumulated
value is the difference between a premium and a mid-price forward across a whole
squad. **Take price seriously in the run-up to Wildcard 1 (GW6–9); largely ignore
it otherwise.** The £1.0m bank already does the useful half — headroom against a
target rising out of reach.

### Proposed scope, if built

A deliberately narrow `price_watch` tool answering only the two timing questions,
from `transfers_in_event` and `transfers_out_event` **relative to ownership** —
the change threshold scales with how widely owned a player is, so niche players
move on a fraction of the flow template players need.

Output limited to: *these squad players are falling* · *these watchlist targets
are rising* · a note on the ownership trade-off. **No price in the rankings, no
team-value optimiser.**

### CHECK FIRST before building

FPL launched its own **Price Change Predictor** for 2026/27, using their real
transfer data. If it is exposed anywhere in the API, use their numbers rather
than reverse-engineering the threshold. Verify this before writing any code.

### Why GW3 and not now

All price and transfer fields (`transfers_in_event`, `transfers_out_event`,
`cost_change_event`, `cost_change_start`) are **zero pre-season**. There is
nothing to model until real flow exists, and a threshold model fitted to two
gameweeks of data would be noise. GW3 gives enough movement to sanity-check the
ownership-scaling assumption before relying on it.

---

## 1. Bayesian hierarchical regression — logged Fri 7 Aug 2026

**Source:** Sylvan's research summary, 7 Aug 2026, on how data scientists and
academics model FPL points.

### The proposal in brief

Rather than point estimates from tree-based regressors (XGBoost, LightGBM),
model expected points as a **posterior distribution** using probabilistic
programming (PyMC, Stan). Typical structures:

- **Poisson / negative binomial regressions** — goals and clean sheets are count
  data, so log-linear count models fit naturally. Player ability, teammate
  attacking strength and opponent defensive vulnerability enter as latent
  coefficients.
- **Hierarchical player–fixture frameworks** — a player's expected log-points in
  a gameweek from baseline skill + team attacking quality + opposition concession
  rate, regularised through hyper-priors.

Three claimed advantages: quantified **uncertainty**, **partial pooling** for
small samples, and **priors** as a channel for domain knowledge.

---

### Assessment against what we actually built

**This maps onto four specific weaknesses in the current system. That is the
strongest argument for it — it is not a generic "better model" pitch.**

#### (a) Partial pooling would solve our biggest live problem

The recurring refrain all through 7 Aug was *"below ~60 shots it's noise"*,
*"a large delta from under 300 minutes is noise"*, *"wait for GW6"*. The current
answer to sparse data is **fall back to last season and be sceptical** — a hack.

Partial pooling is the principled version: borrow strength from a player's
positional group and team so estimates stabilise before individual data
accumulates. **This is the single most valuable idea in the proposal**, because
it directly addresses the period we are in right now.

#### (b) Priors are what ROLE_INTEL.md is hand-rolling

We built a two-layer system on 7 Aug: backward-looking screens plus a curated
`ROLE_INTEL.md` overlay with `?` markers and reconciliation rules.

In a Bayesian framework, "Szoboszlai now takes penalties" **is** a prior
adjustment — shift his goal-rate prior by the expected penalty volume
(~0.79 xG each). Our manual overlay is an approximation of exactly this
mechanism. A proper implementation would make the adjustment quantitative and
let it decay correctly as real data arrives, instead of relying on a human to
remember to prune the file.

#### (c) Uncertainty would fix captaincy, which we currently treat wrongly

Captaincy has been recommended on **point estimates** — fixture difficulty plus
xGI. But captaincy is a *variance* decision:

- **Protecting rank** → want high mean, low variance
- **Chasing rank** → want high variance, accept lower mean

A posterior gives both. The current method cannot distinguish "safe 6 points"
from "coin-flip between 2 and 14", and those are different armbands depending on
league position. **This is a real gap, not a refinement.**

#### (d) Hierarchical team effects would handle transferred players properly

Guéhi (Palace→City) and Semenyo (Bournemouth→City) both have blended-club stats.
The current answer is *"contaminated, treat as uninformative"* — which discards
real information. A hierarchical model separates **player ability** from **team
effect**, so a club change updates the team coefficient while retaining the
player's ability estimate.

---

### Costs and risks — honestly

**Environment risk is not theoretical.** Installing PyMC or Stan on this machine
means compiled dependencies in a conda environment that has already produced a
broken `cryptography` / OpenSSL link. Getting `mcp` working took three attempts
and ultimately required avoiding the dependency rather than fixing it. PyMC has a
substantially heavier dependency tree. See `python_env_constraints` in memory.

**Compute cost conflicts with the design goal.** The MCP exists to make the
weekly brief *cheap*. MCMC sampling across ~600 players and 38 gameweeks is
minutes per run, not seconds. That is tolerable weekly, poor for interactive use.

**Opacity is the serious one.** The current screens are legible — you can read
why Rice is `borderline` and argue with it. **On 7 Aug alone, five errors in my
own reasoning were caught precisely because the logic was inspectable**: the Rice
fixture error, the median-vs-threshold bug, the transferred-player contamination,
the Szoboszlai lateral move, and the clean-sheet/bonus blind spot. A posterior is
much harder to audit. A wrong model would be wrong *confidently* and quietly.

**False precision.** FPL's dominant variance sources are **rotation/minutes** and
**genuine match randomness**. Neither is fixed by better regression. A
sophisticated model risks producing narrow credible intervals around a quantity
that is irreducibly noisy.

**The honest strategic question:** is the marginal gain over "rank on xGI, check
the fixture run, check the role" actually large? Most FPL mispricing comes from
**role changes**, which is an intelligence problem, not a modelling one.

---

### PROPOSED DESIGN — empirical-Bayes shrinkage, v1

Worked up 7 Aug 2026 in response to two questions: *what do we shrink toward*,
and *which metrics get shrunk*. This is the concrete spec to implement and test.

---

#### D1. What gets shrunk — rates in, points out

**Shrink the input rates that generate points. Never shrink points directly.**

Points are a composite of processes with very different noise levels. One blanket
correction on a total would over-shrink the stable parts and under-shrink the
random ones.

| Metric | Shrinkage | Rationale |
|---|---|---|
| Conversion (goals ÷ xG) | **Almost fully to mean** | Persistence ~0.12 — near-pure noise |
| Bonus per 90 | Hard | Lumpy, BPS-threshold driven |
| Minutes / start rate | Moderate | Role-dependent, moderately sticky |
| xGI per 90 | **Gentle** | Persistence ~0.63 — mostly real signal |
| CBIRT / CBIT per 90 | **Gentle** | High volume, no luck component; most stable metric we hold |
| xGC per 90 | Gentle, **at team level** | Property of the defence, not the player |
| Price, ownership, FDR, set-piece order, status | **Never** | Facts, not estimates |

**Assembly:** shrunk components → combine via FPL scoring rules → expected points.

Three reasons to compose rather than shrink a total: each component needs its own
`k`; the result stays inspectable (which is what caught five reasoning errors on
7 Aug); and role intel can target the correct component — "Szoboszlai takes
penalties" adjusts his **xG rate**, and if you had shrunk total points there
would be nowhere to apply it.

**Key realisation.** The current xGI-first methodology is *already* empirical
Bayes on the conversion component, with `k` set to infinity — "assume everyone
finishes at league average". But persistence is **0.12, not 0.00**. Shrinkage
generalises the existing framework rather than replacing it, letting a player
with genuinely large evidence retain a *small* finishing premium instead of the
blunt all-or-nothing rule.

---

#### D2. What we shrink *toward* — a fallback ladder, per metric

There is no single baseline. Different metrics have different natures:

| Estimating | Natural baseline |
|---|---|
| xGI (individual attacking) | His own last-season rate |
| xGC / clean sheets | **Team** baseline |
| CBIT / CBIRT | His own last-season rate (role volume is sticky) |
| Minutes / starts | Own history + team depth |

**Position average is the weakest of the candidates — a last resort, not a
default.** Bruno and a £4.5m holder are both "midfielders" and share nothing.

**Hierarchy — shrink toward the most specific baseline with adequate data; that
baseline is itself shrunk toward a broader one:**

```
player's own history
  → team × position baseline
    → position × price bracket
      → position overall
```

Price bracket is underrated: it encodes the market's aggregate expectation and
exists for *everyone*, including players with no PL history.

**Three conditions disqualify the personal prior** — all encountered on 7 Aug:

| Condition | Example | Fall back to |
|---|---|---|
| Club changed | Guéhi (Palace→City), Semenyo (BOU→City) | Team × position at the **new** club |
| No PL history | van Ewijk (promoted, 0 minutes) | Position × price bracket |
| **Role changed** | Szoboszlai (now on penalties) | Position × price; old rate describes a different job |

**This makes `ROLE_INTEL.md` the mechanism that invalidates a prior** — a flagged
role change tells the model not to shrink toward a stale personal rate.

---

#### D3. How `k` is set — derived, not chosen

`k` is not a taste knob. Empirical Bayes derives it:

```
k ≈ within-player variance / between-player variance
```

If players genuinely differ from each other, trust individual data quickly (low
`k`). If they are similar and single-game results are noisy, shrink hard (high
`k`). Both variances are measurable.

**Estimate `k` separately per metric.** It should come out very different for
goals (noisy → shrink hard) than for CBIRT (stable → shrink gently). That
divergence is itself a useful diagnostic — if it does not appear, something is
wrong with the implementation.

---

#### D4. How the baseline choice gets decided — empirically

Everything above is a **hypothesis**, not a conclusion. Decide it the same way
the xGI framework is being tested: by backtest.

For each candidate baseline, compute shrunk estimates from GW1–5 and measure
which best predicts GW6–10 actuals. Whichever wins, wins.

**Extend `predictive_backtest` to compare, head to head:**
1. Raw observed rate (no shrinkage) — the control
2. Shrunk toward own last-season rate
3. Shrunk toward team × position
4. Shrunk toward position × price bracket
5. Shrunk toward position overall

Report correlation with period-2 actuals for each. Same discipline as the
existing test: pre-commit the interpretation, and a gap under ~0.05 is
inconclusive rather than a win.

---

#### D5. Scope warning — recorded before building

The screens currently output **component metrics and archetypes**, not an
expected-points number. Shrinkage pulls naturally toward computing xP.

**That is a bigger change than "add shrinkage".** It moves the system from
*decision support you argue with* to *a number you trust*. Given how much of the
value on 7 Aug came from arguing with outputs and catching errors, that should be
a deliberate choice, not a drift.

**Recommended v1 scope: shrink the component rates, keep the archetype output,
leave the judgement with Sylvan.** Compute xP only if the backtest shows the
components are reliable enough to justify it.

---

#### D6. Captaincy — a distribution problem, not an estimation problem

**D1–D5 are about *selection*: better point estimates of a rate. Captaincy needs
something different, and shrinkage alone does not provide it.**

##### Two distinct uncertainties, usually conflated

| | What it is | Fixed by |
|---|---|---|
| **Estimation uncertainty** | How sure am I of this player's true rate? | Shrinkage (D1–D3) |
| **Outcome variance** | Even knowing the rate exactly, one gameweek is a random draw | Modelling the **distribution** |

**For captaincy, outcome variance dominates.** Perfect knowledge of a striker's
true rate still tells you nothing about whether he scores this Saturday. So
shrinkage improves *who you pick*; it does almost nothing for *who you captain*.

##### Getting the distribution — cheap, no Bayesian machinery

FPL gameweek points are mostly count data. Model goals and assists as Poisson
draws around the (shrunk) expected rates for that fixture:

```
goals   ~ Poisson(lambda_g)
assists ~ Poisson(lambda_a)
points  = 2 + 5*goals + 3*assists + clean_sheet + bonus + DC     (midfielder)
```

Convolve and you have the **full distribution** of that player's gameweek score.
No MCMC, no PyMC — a few lines of arithmetic over a Poisson PMF.

##### The outputs that actually decide a captaincy

Report these, not raw variance:

| Statistic | Why it matters |
|---|---|
| **E[points]** | The baseline expectation |
| **P(haul)** — P(≥10 pts) | **This is what gains rank** |
| **P(blank)** — P(≤2 pts) | **This is what loses it** |
| SD | Summary only — less interpretable than the tails |

**Variance is symmetric; captaincy is not.** You care about the upper tail far
more than the spread. Two players with identical xP of 6 can be completely
different captaincy propositions:

- **A:** 60% chance of 2, 40% chance of 12 → chase pick
- **B:** 90% chance of 5–7 → protect pick

The current method — "Bruno FDR 2 vs Isak FDR 3, Bruno takes penalties" — cannot
distinguish these at all. It is a point estimate with no uncertainty whatsoever.

##### Effective ownership — the variable currently missing entirely

Raw variance is not the whole story. **Captaincy is a bet against the field, so
ownership determines whether it is a bet at all.**

- Captain a 50%-owned player → largely **rank-neutral**, whatever happens
- Captain a 5%-owned player → a genuine **two-way rank bet**

So the decision statistic is really `P(haul) × (1 − effective ownership)` for
upside, against `P(blank) × (1 − EO)` for downside. Ownership is already in the
screens (`Own%`) and has never been used for captaincy.

##### Decision rule, by situation

| Situation | Optimise |
|---|---|
| Protecting a rank or a mini-league lead | High E[points], **low P(blank)**, high ownership |
| Chasing | **High P(haul)**, low ownership — accept the blank risk |
| Neutral / early season | Highest E[points], break ties on P(blank) |

##### This also solves Triple Captain timing

TC is *purely* a variance decision — its value is one extra copy of the score, so
you want **maximum P(haul)**, not maximum mean. The same machinery answers "is
this the week?" for the chip, which currently relies on the judgement call in
`TEAM_CHANGE_LOG.md` (target GW10–16, backstop GW16).

##### Cost and independence

**This is independent of D1–D5 and can be built first.** It needs only expected
goal and assist rates for the fixture — which the screens already approximate —
plus a Poisson PMF. No new dependencies.

**Arguably it is the higher-value half of this whole document.** Selection is
currently done with a defensible framework; captaincy is currently done on a
fixture-difficulty heuristic with no uncertainty at all. The marginal gain is
larger where the current method is weakest.

##### Honest caveats

- Poisson assumes independence and a constant rate within a match. Real football
  has game-state effects — a team 3-0 up stops attacking. Negative binomial
  handles the overdispersion better if Poisson proves too narrow.
- Bonus points are the hardest component to model (BPS thresholds, not counts)
  and may need an empirical distribution rather than a parametric one.
- Clean sheets are Bernoulli at team level, not Poisson — model separately.
- **Test the calibration, not the sharpness.** If the model says P(haul) = 20%,
  hauls should occur ~20% of the time across many predictions. A model that is
  confidently wrong is worse than the current heuristic.

---

### Recommended path — staged, cheapest first

**Step 1 — Empirical-Bayes shrinkage (do this first). Spec in D1–D5 above.**
Captures most of the partial-pooling benefit with no PyMC, no MCMC and no new
dependency:

```
shrunk_rate = (n * observed_rate + k * baseline) / (n + k)
```

`n` = minutes or shots; `baseline` = per the D2 ladder; `k` = per D3, derived
from the variance ratio rather than chosen. Roughly 20 lines inside the existing
screens. It would fix the early-season instability that currently forces every
decision to be deferred to the wildcard, and it stays fully legible.

**Known trade-off:** shrinkage improves *average* accuracy but deliberately makes
extreme players look less extreme. A genuine outlier is understated early. Fewer
false alarms, slightly slower to spot the real thing.

**Step 2 — Captaincy distributions. Spec in D6 above.**
Poisson model over goals and assists, reporting **E[points], P(haul ≥10),
P(blank ≤2)** and an ownership adjustment. No Bayesian machinery, no new
dependencies.

**Reconsider the ordering:** this may belong *before* step 1. Selection already
has a defensible framework; captaincy is currently decided on a fixture-difficulty
heuristic carrying no uncertainty at all. The marginal gain is largest where the
current method is weakest — and D6 is independent of D1–D5, so it can be built
first. It also answers Triple Captain timing, currently a judgement call.

**Step 3 — Full hierarchical model.** Only if steps 1 and 2 prove insufficient,
and only in an isolated environment (dedicated conda env or container), never in
his base or a project env.

### Decision point

**The GW10 backtest on 10 Nov 2026 is the natural gate.** It already measures
whether the current xGI-first approach beats naive goals-based prediction on his
own data. Extend it to also test shrunk estimates against raw ones. If shrinkage
materially improves prediction, that is the empirical case for going further. If
it does not, the full Bayesian build is unlikely to be worth the cost.

**Do not adopt on theoretical appeal.** The framework should have to beat the
simple version on his data, the same standard the current methodology was held to.

---
---

# ROADMAP — staged development across 2026/27

*Written Sat 8 Aug 2026, pre-GW1. Covers only ideas already discussed and
assessed. Revisit at each gate below; this is a plan, not a commitment.*

## The organising principle: gates, not dates

Nothing here is scheduled by calendar. Each item is **unlocked by evidence** —
enough data to fit, or enough calibration to justify. Building before the gate
means fitting to noise and then trusting the result.

## Read this first — the case against most of it

The system already has **16 tools and roughly 2,000 lines**, and the core
methodology has **not yet been validated on a single live gameweek**. Every
item below adds surface area to something unproven.

Two consequences:

1. **The GW10 backtest is the gate that matters most.** If shrinkage doesn't beat
   raw rates on real data, layering Bayesian machinery on top is building on
   sand — and several roadmap items should be cancelled outright, not deferred.
2. **The highest-value items are the ones that came from observed errors**, not
   from theoretical appeal. Bonus/BPS and goalkeepers are known blind spots found
   by getting something wrong. They outrank everything exotic on this list.

**A good season could end with most of this unbuilt.** That is a success
condition, not a failure.

---

## Tier A — real gaps, found through actual mistakes

*Reordered 8 Aug 2026 after an adversarial review. The minutes work below was
promoted above bonus and goalkeepers because **minutes are the dominant source of
blanks**, and the system had been modelling scoring in fine detail while treating
availability as an afterthought. The precision was on the part that varies least.*

### A0. Minutes and role — the largest gap in the system

Four layers, cheapest first. **Layer 1 is built (8 Aug 2026); 2–4 are not.**

Everything here terminates in **P(blank)**, which `captaincy_odds` already
computes. This is **not a new subsystem** — it improves an existing input.

#### A0.1 Availability and suspension risk — BUILT 8 Aug 2026

`_availability()` applies the published status flag to P(start): suspended,
injured or unavailable → 0; doubtful → scaled by `chance_of_playing_next_round`.
**This fixed a real bug** — a suspended player previously received a full P(start)
drawn from his historical start rate.

`_suspension()` adds a `SUSP` column from yellow-card accumulation against the
thresholds (5 by GW19, 10 by GW32, 15 by GW38).

**The distinction that must not be re-conflated:** a fifth yellow picked up this
week bans the player **next** week. So `SUSP` is a **hold/transfer signal, not a
this-week blank signal.** Only `BANNED` — the status flag — moves P(blank) now.

*Not modelled: second-yellow reds, which need per-match data this file does not
fetch.*

#### A0.2 Start-rate shrinkage — NOT BUILT. Gate: ~GW6

`start_rate` is a **binomial rate**, so the existing D1–D3 shrinkage machinery
applies unchanged — no new statistical apparatus, just pointed at a new metric.
Outputs a shrunk P(start) and E[mins | start] to replace the current crude
`starts / est_games`.

#### A0.3 Club rotation index — NOT BUILT. Gate: ~GW8 (needs 6–8 GWs)

Measure **XI churn between consecutive gameweeks**, averaged per club.

This is how you model a manager **without the API knowing who he is** — there is
no manager field anywhere in the FPL data. You cannot look up that a given coach
rotates; you *can* measure that his club's XI turns over 4.2 players a week
against another's 1.1. High churn widens the minutes distribution for every
player at that club.

**Known failure mode: a mid-season sacking silently corrupts the index**, which
keeps averaging across two different regimes. Structurally identical to the
contaminated-transfer problem and needs the same fix — **a dated manager-change
register in `ROLE_INTEL.md`.** Do not build the index without it.

#### A0.4 Congestion overlay — NOT BUILT. Gate: ~GW10, and only if 2–3 pay off

Which clubs are in Europe (known at season start, 6–8 of them) and which
gameweeks sit either side of a midweek round.

**The interaction is the signal, not the flag.** A manager who rotates *only* in
congested weeks is a completely different proposition from one who rotates
always — and the flag alone cannot tell them apart.

**This is the only piece needing data from outside the FPL API**, a deliberate
departure from the no-dependencies principle held all season. It is a calendar
entered once per season, not a scraper, and belongs in `ROLE_INTEL.md` as a dated
block alongside `setpieces` and `contaminated`. **Do it last, and only if the
cheaper layers have proved their worth.**

#### A0.5 Start-weighted XI objective — NOT BUILT. Gate: build behind a flag now, decide at GW10

*Logged Sun 9 Aug 2026. This is the layer A0.1–A0.4 were always feeding, and it
was missing: the estimates improve P(start), but **nothing multiplies P(start)
into the objective.***

`optimise_squad.py` maximises **xP per 90** over the XI. `stp` enters only as a
**hard gate at 75%**, never as a weight. So two players with equal xP/90 score
identically whether they start 76% of the time or 98%.

**Measured on the live GW1 squad (`size_bench_value.py --fixtures`):**

| | |
|---|---|
| XI, xP per 90 | **49.94** |
| XI, xP per gameweek (start-weighted) | **44.28** |
| availability haircut | **5.66 — 11%** |

**11% of the headline figure is never played**, and it is distributed *unevenly*:
Sarr and Schade at 75% carry a quarter more headline xP than they deliver;
Virgil and B.Fernandes at 100% carry none. Every weekly recommendation is
currently ranked on that distorted scale.

**The gate is doing two jobs and should be split.** (1) discounting availability
— which a multiplier does properly and without a cliff; (2) protecting against
noisy per-90 rates from thin samples — which is **gate 1's** job (900+ minutes)
and **A0.2's** (shrinkage). The 75% line also creates a genuine discontinuity:
74.9% and 75.1% differ by everything, which is exactly how **Sarr** went from
invisible to eligible on the last-16 basis while his score already beat the
incumbent's under either.

**Proposed:** add `xp_gw = stp × xP_adj` **alongside** `score`, never
overwriting it, selected by a flag so both objectives run side by side — the
same pattern as `--season-starts`. Keep a low floor (~40–50%) to exclude genuine
non-players. **A0.2 is a precondition, not a parallel option:** a gate only needs
the ranking right near one threshold, whereas a multiplier propagates `stp` noise
into every score.

**A second precondition, found 13 Aug 2026 and now fixed.** Sylvan asked, before
building this: pre-season, `stp` is a pure 2025/26 number (last-16-GW starts,
or a full-season fallback) — for a transferred-in or newly-promoted player that
is either stale or, for a genuine newcomer, literally zero. `ROLE_INTEL.md`'s
`adjustments` fence can `set stp` for exactly these players and was already
wired to the same field the objective would use — but it required an explicit
`--intel` flag that the weekly brief's documented command never passed. So
building `xp_gw` at that point would have multiplied xP by a number that is
correct for incumbents and silently wrong for the specific players (transfers,
promoted-club signings) where a start-weighted objective matters most, with no
mechanism to un-freeze it as the season progressed. **Fixed 13 Aug 2026:**
`--intel` is now applied by default in `build_squad.py` / `optimise_squad.py`
/ `fixture_adjust.py` (`--no-intel` to opt out); see the roadmap table entry
and `ROLE_INTEL.md`. This does not replace A0.2 — it only ensures the manually
curated overrides that exist are actually live. A0.2's automatic blending
toward real 2026/27 starts, as they accrue, is still needed before `stp` stops
being frozen on last season for everyone WITHOUT a hand-entered override.

**Unit discipline — this bit is load-bearing.** The change makes the objective
expected points **per gameweek**, so every historic xP/90 figure in
`TEAM_CHANGE_LOG.md` stops being comparable. Date the switch in the log.

**Kill criterion:** if `predictive_backtest` at GW10 shows start-weighted
ranking does not beat per-90 ranking out of sample, revert to the gate and
delete `xp_gw`. Do not keep both objectives indefinitely.

#### A0.6 Autosub bench value — NOT BUILT. Gate: **after A0.5**, not before

*Logged Sun 9 Aug 2026, with a corrected sizing. See `size_bench_value.py`.*

`optimise_squad.py` scores the bench at **zero** — deliberately, so the model
does not buy a luxury bench. But the bench does score, through autosubs.

```
E[outfield bench] = sum_k P(>= k blanks among the 10 outfield starters)
                          * s_k * xP_k                      k = 1..3
E[GK bench]       = (1 - s_gk_start) * s_gk_bench * xP_gk_bench
```

`P(>= k blanks)` is a **Poisson-binomial** over the starters' `(1 - s_i)`, exact
by DP and cheap for eleven players.

**Sized on the live GW1 squad:** expected blanks **1.19**, so
`P(≥1) = 0.736 · P(≥2) = 0.339 · P(≥3) = 0.095`. The current bench is worth
**3.72 pts/GW**, of which **Tavernier alone is 2.34 — 63%**. Reallocating the
same £19.0m gains **+0.53 pts/GW**; moving £1m across from the XI nets
**+0.86 pts/GW** after paying 0.18 in XI quality. Comfortably above the 0.10
noise floor.

**Slot 3 fires once in ten gameweeks.** Bench value is not spread across the
bench — it concentrates in **one player**. You are buying a first substitute and
two pieces of near-worthless insurance.

**THE ORDERING IS NOT A PREFERENCE — IT IS A CORRECTNESS CONSTRAINT.** Adding
this term to the *current* per-90 objective produces false results, because the
bench term is start-weighted and the XI term is not. Worked example, the live
`Tavernier → Anderson` recommendation:

```
                                    before    after   change
XI, xP per 90 (current model)        49.94    50.31    +0.37
XI, xP per GW (start-weighted)       44.28    45.40    +1.12
bench autosub                         3.72     3.13    -0.59
per-90 XI + bench   (INVALID)        53.66    53.44    -0.21   <- false reversal
per-GW XI + bench   (correct)        48.00    48.53    +0.54   <- no reversal
```

Anderson (94%) replacing João Pedro (75%) in the XI means fewer blanks, so the
bench is needed less. **Bench slots 2 and 3 hold the same players before and
after and still lose 0.318 between them** — that fall is the transfer's benefit
appearing with a minus sign. Bolted onto the per-90 objective, this term would
**systematically penalise every upgrade in XI reliability**, which is precisely
the class of transfer worth making.

*This error was made and committed on 9 Aug 2026 (`70ae735`), then corrected
(`ea9df51`). Recorded because the wrong answer was plausible, arithmetically
clean, and pointed at a live recommendation.*

**Known optimistic assumptions**, all inflating the estimate: formation validity
ignored; blanks assumed independent when they cluster; bench players scored at
their full per-90 rate; and **a 20-minute cameo treated as a start when it
actually scores ~1 point and blocks the autosub entirely.** Tighten the cameo
assumption first — it is the one most likely to be carrying the error.

**Build shape** — the exact objective is **non-linear in the decision variables**
(the blank distribution depends on which players are in the XI), so it cannot go
into CBC directly. Two workable routes: **fixed-point iteration** on per-slot
constants `π_k`, re-solving until stable (2–3 passes, start here); or **linear
surrogate then exact re-ranking** of the top 20–50 squads. Optimising is hard;
evaluating is free.

**Side benefit:** a bench with real expected value prices **Bench Boost** for the
first time — it currently has no model behind it at all.

#### What is deliberately excluded

Motivation — dead rubbers, relegation scraps, run-ins, a side already on the
beach in May. **Real, and not modellable from this data.** The eye test stays
primary and no column should pretend otherwise.

---

These aren't refinements. They are **routes to points the system cannot currently
see at all.**

### A1. Bonus points / BPS — the highest-value gap

**Why it's here:** the Rice analysis. His genuine value came from **clean sheets
and bonus**, and the midfielder screen was blind to both — the screen said
"lateral swap" while missing the actual case for him. That was a real error, and
the blind spot is still open.

BPS rewards passes completed, tackles, recoveries, saves and clean sheets, then
converts the top three per match into **3/2/1 points**. Deep-lying midfielders and
defenders on solid teams accumulate BPS in ways xGI never shows.

**Quantified 8 Aug 2026 from the v2 snapshot.** Top BPS/90 among midfielders who
**fail** the 12+ CBIRT threshold — i.e. players the screen currently sees no floor
for:

| Player | BPS/90 | CBIRT/90 | xGI/90 |
|---|---|---|---|
| **B.Fernandes** *(his vice-captain)* | 29.6 | 8.4 | 0.68 |
| Cherki | 29.5 | 6.9 | 0.67 |
| Doku | 26.7 | 6.4 | 0.44 |
| Bruno G. | 25.0 | 9.2 | 0.39 |

The screen labels these `attacker` — ceiling, no floor. **The BPS says otherwise.**
This is the Rice error in reverse: the same blind spot, now with numbers.

**Gate:** ~GW6, once there is enough BPS history to compute a per-90 rate.
**Scope:** a `bps` column in both screens, plus BPS in the archetype logic so a
`holder` with a strong bonus record is distinguishable from one without.
**Risk:** BPS is dominated by whether the team wins, so it will correlate heavily
with team strength. Check it adds information beyond team quality before trusting.

**BUILT EARLY — 12 Aug 2026, ahead of the GW6 gate.** Moved up because the
2026/27 BPS rule change (below) meant waiting to GW6 would mean playing the
whole first quarter of the season on a known, quantifiable blind spot. Unlike
xG or CBIT, bonus doesn't need first-principles modelling — FPL already
resolves the top-3-BPS-per-match competition and reports the outcome directly
(`bonus`), so `xbonus90` is a rate-shrinkage problem, not a simulation
problem. Full method in `build_squad.py`'s `_bonus_shrinkage()` docstring;
formula in `SELECTION_FRAMEWORK.md`.

**Sizing, measured on the pool (`bonus_swing.py`, kept as a one-off diagnostic
script):** mean pool swing **+0.325 xP/90**, always positive (it's a pure
addition, not a reallocation) — ranging from **+1.23** (Haaland) down to
**+0.04** (bench fodder). On the live squad: XI xP/90 **50.81 → 56.24**
(+5.43, once the `fixture_adjust.py` integration bug below was fixed).
Rice vs Sarr, the comparison that motivated this build: **+0.66 vs +0.33** —
a **0.33 xP/90 gap from bonus alone**, above the 0.10 noise floor.

**A real integration bug was caught and fixed while building this.**
`fixture_adjust.py`'s `adjust()` — which is what `--fixtures` mode actually
runs, i.e. every real weekly-brief call — rebuilds `xp` from scratch rather
than calling `build_squad.expected_points()`, so it silently dropped
`xbonus90` entirely on first build. The symptom was concrete: "current squad
XI xP/90" printed the identical 50.81 with and without `--no-bonus`, which is
how it was caught rather than assumed correct. Fixed by adding the same
`xp += r.get("xbonus90", 0.0)` line there — carried through **unscaled**, on
the honest grounds that there's no sourced way yet to say how a fixture
should scale bonus.

**Not yet validated against live 2026/27 data** — none exists. Re-derive and
re-check the direction of the rule-change adjustment against real BPS as soon
as GW1-5 are played; delete the block in `build_squad.py` if it disagrees.

### A2. Goalkeeper methodology — currently undefined

Explicitly deferred when the defender screen was built. He owns **Raya and
Dubravka** and there is **no method behind either pick.**

Keepers score differently from every other position: **1pt per 3 saves**, 4pts
clean sheet, 5pts penalty save, −1 per 2 goals conceded. The save route means the
*same* tension as defenders but sharper — **a keeper on a bad team gets more save
points and fewer clean sheets.**

**Gate:** ~GW5. Low urgency because the position is cheap and low-variance, which
is exactly why it can wait — but "no method at all" should not persist all season.
**Scope:** a `keeper_screen` on the save/clean-sheet axes.

#### Measured 8 Aug 2026 — the tension is REAL for keepers, unlike defenders

```
corr(saves/90, clean sheets) = -0.579     n = 19 keepers, 900+ mins, 2025/26
```

**This is the anti-correlation that was wrongly claimed for defenders** (where it
measured −0.04). For goalkeepers it is strong and in the expected direction: a
keeper on a bad team makes save points and no clean sheets, and vice versa.

**So the keeper screen is NOT a copy of the defender screen.** Defenders need two
axes *because the routes are independent*; keepers need two *because the routes
actively trade off*. Different reason, and it changes the archetype boundaries —
a "high saves" keeper is implicitly a "low clean sheets" keeper, which is not true
of a high-CBIT defender.

**Caveat: n = 19.** The confidence interval is wide (roughly −0.82 to −0.16).
Directionally solid, but do not treat −0.58 as a precise coefficient.

Illustrative, from the v2 snapshot — note both his own keepers sit at opposite
extremes:

| Keeper | saves/90 | CS | xGC/90 |
|---|---|---|---|
| Dubravka *(his bench)* | 3.63 | 4 | 2.04 |
| Pope | 3.32 | 7 | 1.23 |
| Roefs | 3.11 | 10 | 1.43 |

### A3. Clean sheets for midfielders (1pt)

Same blind spot as A1, smaller. **Fold into A1 rather than building separately.**

---

### A4. `p_threshold` is mis-calibrated — HIGH PRIORITY, BUILD NOW

*Logged Sun 9 Aug 2026. **Not gated on a future gameweek.** The data needed to
fix this arrived with `fetch_gw_history.py`; it can be built today.*

**What the model does.** `build_squad.py` converts an average CBIT/CBIRT into
expected DC points through a four-band step function on the season mean:

```python
xp += DC_PTS * p_threshold(dc_metric, DC_THRESH_POS[pos])   # DC_PTS = 2

def p_threshold(mean, thresh):
    if mean >= thresh * 1.30: return 0.75
    if mean >= thresh:        return 0.55
    if mean >= thresh * 0.80: return 0.20
    return 0.05
```

The code already names this as its weak point: *"ONE judgement survives:
P(clearing the DC threshold) is estimated from a season MEAN... The honest fix
is the true per-match hit rate."* **That fix is now available.**

**Measured against 2025/26 per-match counts** (60+ minute appearances, players
with 20+ such appearances):

| Band | n | Assumed | Actual | xP error |
|---|---|---|---|---|
| ≥1.30× | **0** | 0.75 | — | *unreachable — no player qualified* |
| ≥1.00× | 15 | 0.55 | 0.59 | −0.09/90 |
| **≥0.80×** | **39** | **0.20** | **0.41** | **−0.42/90** |
| <0.80× | 106 | 0.05 | 0.10 | −0.10/90 |

**Three defects, in order of cost:**

1. **The 0.80–1.00 band understates by 0.21 in probability — 0.42 xP/90, about
   16 points a season.** Four times the noise floor, and the largest known
   mis-calibration in the model. It is the overdispersion effect: CBIT counts
   have variance/mean ≈ **1.38**, so a fat right tail rescues near-miss players
   far more often than a tight distribution would allow. **39 of 160 qualifying
   players sit in this band** — it is not an edge case.
2. **The top band never fires.** Not one qualifying player averaged 1.30× his
   threshold. `0.75` is dead code wearing the appearance of a considered choice.
3. **The bands hide the variation that matters.** Everyone at ≥1.00× scores an
   identical 0.55, while actual hit rates inside that band run **52% to 70%** —
   Senesi and Anderson at 70%, Keane and Bijol at 52%. A 0.36 xP/90 spread the
   model cannot see, and precisely the difference between a real DC asset and a
   player who merely averages above the line.

**Every error runs the same way: the model UNDERSTATES DC.** Given the 2025/26
champion identified DC as his decisive edge, systematically under-pricing it is
the wrong direction to be wrong in.

**Proposed fix.** Replace `p_threshold(mean, thresh)` with the **empirical
per-match hit rate** — directly observable now that `docs/data/players/*.json`
holds per-match counts. No distributional assumption, no bands, no constants to
tune. Where a player has too few matches to estimate a rate, shrink toward the
position-and-band mean rather than falling back to the step function; this is
the same machinery as **A0.2**.

**Interaction with A0.5.** Hit rate is a per-match probability, so it composes
cleanly with a start-weighted objective. Build A4 first — it is smaller,
independently valuable, and needs no flag.

**Caveats, held honestly.** Per-match means here come from 60+ minute
appearances while the model uses per-90 rates from season totals — close but not
identical, so these figures are indicative. One season of a brand-new metric,
so the dispersion estimate itself carries real uncertainty. And note the
direction: an empirical rate fitted on 2025/26 assumes the DC rules and referee
interpretation are stable into 2026/27.

**Kill criterion.** If the empirical hit rate does not beat `p_threshold` at the
GW10 backtest, revert. Do not keep both.

## Tier B — designed, gated on evidence

### B1. Price forecasting — see §0

**Gate: GW3.** All price fields are zero pre-season. Narrow `price_watch` scope
only; **price in timing, never in ranking.** Check FPL's own predictor first.

### B2. Effective ownership (EO)

D6 names this as *"the variable currently missing entirely."* We use raw
ownership, but what actually determines rank movement is **effective ownership** —
ownership weighted by captaincy, so a 30%-owned player captained by half of them
has EO ≈ 45%.

This sharpens `DiffUp` and the protect/chase modes, both of which currently use a
cruder input than they should.

**Gate:** GW4+, once captaincy distribution data is public enough to estimate.
**Honest limit:** the API doesn't publish captaincy rates directly. This may
require an external source, which is a dependency we've otherwise avoided —
**if it can't be sourced cleanly, don't fake it with an assumption.**

### B3. Rank-aware mode selection

`protect` / `chase` modes exist but **he selects them by hand.** They could be
driven by actual mini-league position and gap — chase when behind late, protect
when ahead.

**Gate:** GW8+, when standings are meaningful. **Low priority** — the modes work,
this only automates a judgement he can make himself in five seconds.

### B4. DGW / BGW forecasting

Chip strategy depends almost entirely on doubles and blanks, and the fixture list
only firms up **4–6 weeks ahead** as cup rounds resolve. `fixture_outlook` already
counts fixtures-not-gameweeks correctly, so the plumbing exists; what's missing is
**forward projection of likely doubles.**

**Gate:** ~GW12, ahead of the GW19 chip-set-1 deadline. **This is the item most
likely to actually change a decision**, because chip timing is worth more than any
single transfer.

### B5. Elite squad sampling — CURRENT season, small sample

**Gate: GW10+.** Before that the top of the table is noise, not skill.

**What was ruled out first.** Identifying *last* season's top 0.1% is
**impossible and would be the wrong signal anyway**:

- The Overall league (id 314) is **recreated each season** — verified 8 Aug 2026,
  standings empty, created 23 Jul 2026. Last season's final table is not in the
  API. `/entry/{id}/history/` exposes past-season rank, but only if you already
  hold the ID, and there is no path from "top 0.1%" to a list of IDs without
  enumerating ~11M entries.
- **More importantly it inverts the core principle.** "Top 0.1% last season" is an
  **outcome**, from the extreme tail of an 11-million-sample distribution — so a
  large share of it is luck. Copying it is **buying the delta, not the xGI**,
  exactly the error the methodology exists to prevent. Year-on-year manager rank
  correlation is weak; most top-10k finishers do not repeat.

**Why a narrow version still earns its place.** Top-10k *ownership* is already
published live (LiveFPL, FPL Statistics) and is cheaper than anything we'd build —
**so ownership alone is not a reason to build this.** What ownership percentages
cannot show is **squad structure**: formation, how budget is distributed across
the price ladder, captaincy concentration, bench construction, and chip timing.
That is the only justification for sampling actual squads.

**Scope if built:** top ~50–100 entries of the *current* Overall standings,
one `picks` call each. Report **structure, not a shopping list.**

**Use as a sanity check, never a source.** Three players from elite consensus is
fine; eleven is worth a second look. **Irrelevant to the Washing Up Cup** — that
is a two-player league with no field to be template against.

---

### B6. Diagnostic dashboard — BUILT 8 Aug 2026

**Files:** `FPL_DIAGNOSTICS.html` (open in a browser) · `build_dashboard.py` +
`template.html` (regenerate with `python3 build_dashboard.py`).

Self-contained, ~122 KB, Chart.js from CDN, 311 players with 450+ minutes.
**Reads the frozen prior-season snapshot** — no MCP, no text parsing, no live
dependency. From GW1 the generator should read `player_gw` from SQLite instead.

**Five panels, four as designed plus one substitution:**

1. Defender independence scatter — the corr −0.04 / +0.14 finding
2. Threshold cliff histograms — 15/110 and 9/146 clear, 34 and 35 in the trap band
3. xGI × delta decision surface, his squad ringed
4. Fixture multipliers, ATT × against DEF ×, showing the 0.89–1.19 spread
5. **Shrinkage diagnostic** — substituted for the planned raw→shrunk arrows,
   which are degenerate pre-season (observed *is* the baseline, so every arrow
   would have zero length; verified against the live screens). Shows the variance
   decomposition per pool, `k` before and after the dispersion fix, and
   convergence curves. **This panel is what found the `_estimate_k` bug.**

**Known gap:** van Ewijk has no prior-season row — Coventry were promoted, so 14
of 15 squad players appear. Expected, not an error.

#### Original plan, retained for the reasoning

### B6 (plan) — logged before the build

**Gate: revisit once there is live gameweek data to plot (~GW6).** Planned in full
now because planning it already paid for itself — see the correction below.

**The governing test for every chart: can it change a decision or expose an
error?** Anything that merely re-displays a table gets cut.

#### What planning it found — a correction to the defender rationale

Computing the correlations behind the defender archetypes showed the stated
justification was wrong:

```
corr(CBIT/90, clean sheets) = -0.04     essentially zero
corr(CBIT/90, xGC/90)       = +0.14     weak, right direction
n = 110 defenders, 450+ minutes, 2025/26
```

The routes are **near-independent, not anti-correlated.** The design is unchanged
— **independence is its own argument against blending**, since one number cannot
carry two unrelated routes. But "they pull against each other" was not supported,
and has been corrected in the tool description, `GLOSSARY.md` and
`WEEKLY_WORKFLOW.svg`.

#### Panel 7 — the xP explorer (added 9 Aug 2026)

A sortable table of **expected points per 90 for all 311 players**, filterable by
position and row count, with the **archetype** alongside. Squad players are
highlighted and marked with a triangle.

**Why both columns are shown.** Archetype says *which route to points a player
has*; xP says *how many*. Neither replaces the other — an archetype cannot compare
a keeper to a forward, and xP hides the difference between a reliable floor and a
lucky average. **A `borderline` label still beats a good xP** when judging
reliability.

**Goalkeepers show a blank archetype, deliberately.** A2 is undefined, and for
keepers saves and clean sheets genuinely trade off (corr −0.579) rather than being
independent as for defenders. Inventing a label to fill the column would be worse
than the blank.

#### The five charts

| Chart | What it tests |
|---|---|
| Defender scatter — CBIT/90 × xGC/90, sized by CS, coloured by archetype | The independence finding above; whether the `avoid` quadrant is truly empty |
| **Threshold cliff histogram** — CBIT/90 and CBIRT/90 with line and `near` band | **The strongest.** 15/110 defenders clear 10+, 9/146 mids clear 12+ — but **34 and 36 sit in the near band**. A third of the population priced for a floor it doesn't earn |
| xGI × delta quadrant, squad highlighted | The actual transfer decision surface, and how thin the buy zone is |
| Shrinkage arrows — raw → shrunk, coloured by `base` | Whether `k` is sane; how many players fall off `own` |
| Fixture multiplier heatmap — team × GW, ATT and DEF panels | The 0.89–1.11 spread. **A chart that argues against over-weighting fixtures is worth more than one that flatters them** |

#### Corrected 8 Aug 2026 — the SQLite warehouse is the right source, not the MCP

**An earlier draft of this plan proposed adding a `format="json"` mode to the MCP
so a dashboard could parse its output. That was solving a problem that does not
exist.** The MCP returns formatted text tables by design, and parsing them in
JavaScript would have been fragile — but there is no reason to go through the MCP
at all. **`fpl_history_cache.sqlite` is queryable directly.**

**It is a warehouse, not a lazy cache.** `cache_history(refresh=True)` sweeps up
to **700 players sorted by minutes**, not merely those someone happened to look
up, and the Tuesday task runs it weekly.

**It is also strictly richer than the priors snapshot** — 19 columns **per
gameweek**, where the snapshot holds season totals only:

```
minutes total_points goals_scored assists bonus bps
expected_goals expected_assists expected_goal_involvements
expected_goals_conceded clean_sheets goals_conceded saves
clearances_blocks_interceptions tackles recoveries starts
was_home opponent_team
```

Note `bps` and `saves` are already captured per gameweek — the v2 snapshot gaps
apply to the **prior season only**.

**Verified 8 Aug 2026: the file does not exist yet.** Zero rows, by design — no
gameweek is finished, and nothing unfinished is ever persisted. That, and only
that, is why a pre-season dashboard would have had to use the priors JSON.

**Revised approach:**

- **From GW1**, generate the dashboard with a Python script reading SQLite
  directly and emitting a self-contained HTML file. No MCP involvement, no text
  parsing, no new tool surface.
- The **priors JSON becomes the GW0 baseline layer** for raw-vs-shrunk comparison,
  not the primary source.

#### Correction: the persistence chart IS buildable — around GW20

**An earlier draft said the 0.63 / 0.12 persistence claim could not be tested
before mid-2027 because it needs two seasons. That was wrong.** Per-gameweek data
supports a **within-season split-half test**: correlate first-half xGI/90 against
second-half xGI/90, and first-half delta against second-half delta.

**Honest caveat: within-season persistence is not the same quantity as
between-season persistence.** No transfer window, same club, same manager, same
role — so it should come out *higher* than 0.63. It tests the **direction of the
claim** (chance creation repeats, finishing does not) rather than reproducing the
published coefficients.

That still moves the single most load-bearing assumption in the system from
"unverifiable" to "testable around GW20", which is worth more than any other chart
on the list.

**The calibration reliability plot** remains gated on logged predictions —
nothing before ~GW6, meaningful around GW15.

#### Prior season loaded into the same store — 8 Aug 2026

`--load-priors-db` reads the frozen JSON and writes **`player_season`**,
**`team_season`** and the view **`v_player_season_rates`** into the same database,
so prior assumptions and live gameweeks are queryable together.

**Season totals are kept OUT of `player_gw`.** They are a different shape — one
row per player, not per gameweek — and inserting them under a synthetic round
number would silently double-count every aggregate downstream. A test asserts the
separation.

**The JSON remains canonical.** The loader is idempotent and the table is a
derived view, so deleting the database costs nothing but a re-run. Nothing
irreplaceable lives only in SQLite.

**Verified: the SQL view reproduces the Python analysis exactly** — n=110
defenders, 15 clearing 10+ CBIT, 34 near, corr −0.037 and +0.140, all matching.
The view does **mechanical per-90 divisions only**; `conversion` and archetype
logic stay in Python so anything involving a judgement call has one
implementation.

#### The database moved out of Google Drive — 8 Aug 2026

**A cloud-sync client can copy a SQLite file mid-write and corrupt it**; the
database has no idea another process is reading its pages. Text files — the JSON
snapshot, the JSONL calibration log — are safe in a synced folder. **A live
database is not.**

`_DB_PATH` now defaults to **`~/.fpl-mcp/`**, overridable via `FPL_MCP_DB`. This
cost nothing to change because the cache did not yet exist. Both tables are
regenerable, which is why the store can live outside the folder without risk.

#### What the warehouse also unlocks

- **A0.2 start-rate shrinkage** and **A0.3 rotation index** need per-gameweek
  `starts` and `minutes` — already in the schema. **The data source for the
  minutes work exists.**
- `was_home` and `opponent_team` per gameweek allow the **D7 opponent model to be
  validated** against outcomes rather than assumed.

---

### B7. Variance and overlap against Dylan — DEFERRED to ~GW20 by decision

*Logged Sun 9 Aug 2026. **Decided: optimise on expected points only for now.***

`optimise_squad.py` maximises expected points and is blind to three things that
matter in a two-player league: the **variance** of the weekly score, the
**overlap** with Dylan's squad, and the interaction between them.

**The mechanic.** Only the difference between the two squads scores, so a player
you both own contributes **exactly zero variance** to the gap, however volatile.
The instrument for controlling variance is therefore **overlap**, not player
steadiness. Win probability is `Φ((lead + N·μ) / (σ√N))`, and variance always
drags that toward 50% — so:

- **lead + N·μ > 0** → suppress σ. Own what he owns where you have no edge.
- **lead + N·μ < 0** → manufacture σ. Own what he does not.

Note the switch is **not** "am I ahead?" but "does my expected finishing position
win?". With a genuine edge, low variance helps even at level scores, because
variance dilutes an edge — at μ = +0.5/GW and scores level, P(win) is 70% at
σ = 6 versus 58% at σ = 16.

**Why deferred.** At GW1, level, with 38 weeks to play, `N·μ` dominates the lead
term and there is no measured edge to protect — μ is the thing to maximise, which
is exactly what the current objective does. The protect/chase distinction only
becomes material once the gap is comparable to `σ√N`.

**Gate: ~GW20.** By then roughly half the season is scored, `N` has halved, and a
gap of any size starts to bind. GW20 also follows the set-1 chip deadline, so it
is already a strategic checkpoint.

**Prerequisite:** `get_squad(entry=87058)` returns 404 until the GW1 deadline
passes. Overlap cannot be computed at all before then.

**Kill criterion:** if the gap at GW20 is smaller than one gameweek's typical
differential spread, this is noise — leave the objective alone and revisit at GW30.

### B6-P. Split-half persistence — **CLOSED 9 Aug 2026, a year early**

*The gate said GW20 2026/27. The 2025/26 archive answered it now. Reproduce with
`python3 persistence_test.py`.*

The xGI-first method rested on two numbers taken from external literature and
flagged as unverifiable without two seasons of our own data. Both are now
measured, and **both are more favourable to the method than assumed**:

| Quantity | Assumed | **Measured** |
|---|---|---|
| chance creation persists | 0.63 | **0.84** (xGI/90, r) |
| finishing over-performance persists | 0.12 | **−0.01** (delta/90, r) |

n = 256 players with 450+ minutes in both halves of 2025/26, split at GW19.
xG 0.83 · xA 0.76 · actual G+A 0.59 · finishing (G−xG) −0.09.

**Delta retains nothing.** By first-half quintile, the heaviest over-performers
(+0.246/90) kept **9%**; the heaviest under-performers (−0.137/90) crossed zero
and finished **positive**. Cherki +4.2 → −0.4. Buendía +3.5 → −1.1.

**"Good finishers stay good" — tested and not supported.** FWD −0.10 (n=28),
MID −0.12, DEF +0.03. Nor does it emerge with shot volume: no first-half xG
bucket shows positive persistence. Of the ten best first-half finishers, **four**
stayed positive in the second; a coin gives five. Haaland +2.5 → −1.0.

**The honest limit.** With 28 forwards the interval on r is roughly ±0.39, so
this rules out a *large* finishing effect, not a modest one. Half a season is
~40–60 shots against the hundreds the supporting literature uses. The defensible
claim is **"not detectable at the horizon this model operates on"** — which for
selection has the same consequence: a positive delta cannot be traded on.

**What changes.** Nothing in the code — the delta rule was already "never sell
high xGI on positive delta alone". It is now **evidence, not borrowed belief**,
and if anything understated. Update the caveat wording wherever 0.63/0.12 appear.

**Other limits:** one season, one split; requiring minutes in both halves selects
for players who stayed fit; the January window sits inside the split, so some
players moved club mid-sample — `docs/data/club_changes.json` allows a stricter
re-run if ever wanted.

### B6-Q. Position-specific persistence — NOT BUILT. Gate: a second season

*Fell out of B6-P, 9 Aug 2026.*

xG persistence is **not uniform by position**: MID 0.73, FWD 0.47, DEF 0.23. The
model applies a single figure to everyone.

**Do not act on this yet.** Much of the spread is likely a statistical artefact —
forwards are a narrower, higher-xG group, and restricted range attenuates
correlation. Distinguishing genuine positional difference from range restriction
needs a second season, or a within-position variance-corrected estimate.

**Kill criterion:** if the 2026/27 split reproduces a similar ordering *after*
correcting for range, build position-specific shrinkage into A0.2's machinery.
If not, keep one number and stop asking.

## Tier C — conditional, may never be built

### C1. Full Bayesian / PyMC — see §1, step 3

**Gate: the GW10 backtest, 10 Nov 2026.** Build only if shrinkage demonstrably
improves prediction *and* calibration shows residual error that shrinkage cannot
fix. **Isolated environment only** — never his base or a project env.

**Kill criterion:** if shrunk estimates don't beat raw ones at GW10, cancel this
permanently rather than deferring it.

### C2. Graph database

Already assessed; **SQLite was chosen deliberately.** Revisit only if a concrete
reasoning task turns out to need multi-hop relationship traversal that SQL makes
genuinely awkward. **No gate — needs a real triggering problem, not a date.**

### C3. Automated ROLE_INTEL

Set-piece and role intelligence is entered by hand, dated and sourced. Automating
it means scraping community consensus, which trades **falsifiability for
convenience** — the current entries are honest precisely because a human wrote
"UNCONFIRMED" next to them.

**Recommendation: don't.** Listed so the decision is recorded rather than
re-litigated.

### C4. The 5-GW fixture score proposal

Received from dispatch, marked *do not enact*. Substantially overlaps
`fixture_outlook`. **Re-read it after GW10** and take only what the existing tool
lacks.

---

## Tier D — validation, not features

**These outrank every build item above.** Tools that are never scored are
decoration.

| Item | Gate | Status |
|---|---|---|
| `log_predictions` running weekly | Every GW | **Wired into the skill — verify it actually fires GW1** |
| `score_calibration` first real read | ~GW6 | Needs ~5 weeks of logs before it says anything |
| GW10 predictive backtest | 10 Nov 2026 | **Scheduled.** The season's main gate |
| SQLite cache populating | Tuesdays | **Scheduled.** Verify rows appear after GW1 |

**The GW6 calibration read is the first honest feedback the system has ever
had.** If P(haul) is badly calibrated, fix that before adding anything new.

---

## Sequencing summary

```
GW1–2    Build nothing. Priors only. Verify logging fires.
NOW      ** A4: p_threshold recalibration ** — NOT gated. The data exists.
         0.42 xP/90 understated for the 39 players in the 0.80-1.00 band;
         the 1.30x band is unreachable and never fires.
GW3      Price decision (B1). First calibration entries exist.
GW5–6    Start-rate shrinkage (A0.2). Goalkeeper screen (A2). Bonus/BPS (A1) —
         DONE 12 Aug 2026, ahead of schedule.
         First calibration read.
         Start-weighted objective (A0.5) behind a flag — needs A0.2. Its other
         precondition, intel actually reaching `stp` by default, was fixed
         13 Aug 2026 (see A0.5 section) — was silently off in the real weekly
         run before that.
         Autosub bench value (A0.6) ONLY after A0.5 ships; before it, the
         term is not merely premature, it gives wrong answers.
GW8      Club rotation index (A0.3) + manager-change register. EO if
         sourceable (B2). Rank-awareness if wanted (B3).
GW10     ** THE GATE ** Backtest. Decides C1 outright. Re-read C4.
         Also decides A0.5: if start-weighted ranking does not beat per-90
         out of sample, revert to the gate and delete xp_gw.
         Elite squad structure sampling unlocks (B5) — table no longer noise.
         Congestion overlay (A0.4) — only if A0.2/A0.3 have paid off.
GW12–19  DGW/BGW forecasting (B4) ahead of chip-set-1 deadline.
GW20     ** Protect/chase review (B7) ** — compute overlap with Dylan and the
         gap vs sigma*sqrt(N). Only then consider a variance term.
GW20     Split-half persistence — ** CLOSED EARLY 9 Aug 2026 ** using the
         2025/26 archive. xGI r=0.84 (assumed 0.63), delta r=-0.01 (assumed
         0.12). See B6-P. Re-run to confirm on 2026/27; B6-Q still open.
GW20+    Shrinkage fades in value; raw data is reliable. Second chip set.
```

## Kill criteria — when to remove, not add

- **Shrinkage fails at GW10** → cancel C1 permanently; consider stripping shrinkage
  itself back to raw rates.
- **A screen never changes a decision across ~10 gameweeks** → it isn't earning
  its complexity. Remove it.
- **Calibration skill score goes negative** → the probabilities are worse than
  guessing the average. Stop quoting them until fixed.
- **A4 empirical hit rate does not beat `p_threshold` at GW10** → revert to the
  step function and delete the hit-rate path. Do not carry both.
- **Any tool needs an unfalsifiable input to work** → don't ship it. The system's
  main virtue is that every number can be traced to a source or a formula.
- **A0.5 start-weighting does not beat per-90 at the GW10 backtest** → revert to
  the 75% gate and delete `xp_gw`. Do not carry two objectives past the gate.
- **A0.6 bench headroom falls below ~0.10 pts/GW once the cameo assumption is
  tightened** → don't build it. The bench-as-pure-cost model was right, and the
  current sizing is an upper bound resting on the most optimistic assumption in
  the set.
- **Two terms measured in different units are ever summed** → the result is void,
  not approximate. See A0.6's worked example: it produced a clean, plausible,
  entirely false reversal of a live recommendation.

---

## Shrinkage backtest — 2025/26 GW1-8 vs GW9-38, 12 Aug 2026

**Question.** Does the shrunk posterior (empirical-Bayes blend of a player's own
rate and a positional baseline, weight `k` derived from the pool's own variance)
actually predict reality better than either input alone — before trusting it on
a 2026/27 season that had not started yet (GW1 deadline: 21 Aug 2026, so there
was no current-season data to test against directly)?

**Method.** Split the finished 2025/26 archive (`.cache_merged_gw.csv`, 38
rounds) into period 1 (GW1-8, standing in for "the season so far") and period 2
(GW9-38, ground truth). For every metric feeding `expected_points()` — xG90,
xA90, xGC90, saves90, CBIT90, CBIRT90, start rate — scored three period-1-only
estimates against period-2 reality: RAW (the player's own period-1 rate),
BASELINE (period-1 positional pool mean, ignoring the player), SHRUNK (the same
`_estimate_k()`/blend formula `fpl_research_mcp.py` uses live). Built as a
one-off dashboard page (`build_priors_backtest.py` → `docs/priors.html`),
now retired — see below.

**Result.** Shrunk beat both raw and baseline on RMSE for all seven metrics:

| metric | RMSE raw | RMSE baseline | RMSE shrunk | n |
|---|---|---|---|---|
| xG per 90 | 0.128 | 0.089 | **0.082** | 217 |
| xA per 90 | 0.062 | 0.061 | **0.056** | 217 |
| xGC per 90 | 0.357 | 0.285 | **0.253** | 111 |
| Saves per 90 | 0.932 | 0.614 | **0.593** | 22 |
| CBIT per 90 | 1.651 | 1.935 | **1.443** | 89 |
| CBIRT per 90 | 1.736 | 2.485 | **1.593** | 128 |
| Start rate | 0.271 | 0.234 | **0.226** | 378 |

Two pools honestly fell back to a default `k` rather than deriving one from
variance (FWD xA90, n=26; GKP start rate, n=27) — both flagged as fallback in
the original page's output, not silently treated as derived.

**Verdict.** Shrinkage is validated in principle on a season with a full 38
rounds of ground truth. Not re-run against 2026/27 — the point was to check the
mechanism before trusting it live, not to re-derive last season's answer.

**Disposition.** The dashboard page this ran on (`docs/priors.html` v1,
`build_priors_backtest.py`) is retired now that its one question is answered;
kept as this note instead of an ongoing tab. `docs/priors.html` was rebuilt on
12 Aug 2026 as a live weekly walk-forward tracker (`build_prediction_tracker.py`)
that answers the *ongoing* version of this question once 2026/27 gameweeks
start finishing — see that file's docstring for the walk-forward methodology,
which differs from this backtest's fixed-split design.
