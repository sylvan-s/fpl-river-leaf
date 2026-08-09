# Selection framework — when judgement may override the model

Created Sun 9 Aug 2026. Governs squad selection for River Leaf FC.

The screens produce a ranked, gated squad. This document defines **the only
circumstances in which a human call may override that output**, what evidence
each requires, and how those calls get scored afterwards.

---

## The gates — what the model actually does

*Added 9 Aug 2026. These existed only in conversation and a temp script when the
current squad went live, which meant **the live team was built by a procedure
nobody could re-run.** That is the same defect as an inherited player: it looks
justified but is not reproducible. Implemented in **`build_squad.py`**, which
reproduces the live squad exactly.*

Applied in order. A player failing any gate is out — no scoring, no argument.

| # | Gate | Rule | Why |
|---|---|---|---|
| 1 | **Sample** | 900+ minutes last season | Below that a per-90 rate is noise |
| 2 | **Starts** | **≥75%** over the last 16 GWs of 2025/26 · ≥60% bench | Minutes dominate blanks — see below |
| 3 | **Availability** | No current injury or suspension | Verified per player, every run |
| 4 | **Expected points** | FPL's scoring table, below | One scale, so positions compete for budget |
| 5 | **Constraints** | £100.0m · 2-5-5-3 · max 3 per club | |

### Gate 2 — starts%, changed 9 Aug 2026 to a trailing window

**Was: starts/38, the whole of 2025/26. Now: starts over GW23-38 only (the last
16 gameweeks).** Sylvan's point: a full-season figure is anchored on the squad
that started the campaign, not the one that finished it — managers get sacked,
injuries resolve, pecking orders shift, and a player's minutes share in August
2025 says less about his role today than his minutes share in April/May 2026.

**There is no per-gameweek data for last season anywhere in this project's own
pipeline.** `player_gw` in the SQLite cache only ever holds the *current*
season, and 2026/27 is pre-season — 0 rows. The last-16 figures come from a
third-party archive (`vaastav/Fantasy-Premier-League` on GitHub, which mirrors
the official FPL API gameweek-by-gameweek), matched to our 267-player pool by
name — surname tokens against the archive's full names, disambiguated by
position, team, and initials where needed. **262 of 267 matched automatically;
5 did not** (Gomes/AVL, Wilson/LEE, Fernandes/TOT, Beto/EVE, Morato/NFO) and
fall back to the season-total rate, flagged in `build_squad.py`'s output with
a `*`. The match itself is **not the official FPL API** — treat it as a
well-sourced but externally-derived input, not ground truth, and re-verify
before leaning on it for a single close gate call. Source, window, and the
unmatched list are stamped in `last16_starts.json`; `python3 build_squad.py
--season-starts` reproduces the pre-9-Aug gate exactly, for comparison.

**Measured effect, run 9 Aug 2026:** at the same 75%/60% thresholds, 108
players clear the XI gate under last-16 vs 91 under season-total — the window
is *less* restrictive overall, not more, so this is not simply a stricter gate.
The one attributable, above-noise-floor change to the standing weekly
recommendation: **Sarr (CRY, £6.5m)** was invisible to the optimiser before —
season-total starts 63%, below the 75% line — while his last-16 figure is
**75% exactly**, because he settled into the XI later in the season than his
full-season number suggests. His flat score (4.78 xP/90) already beat Enzo's
(4.63) under *either* basis; the gate was hiding him, not his rating. Proposed:
Enzo → Sarr, +0.42 xP/90 (+2.1 pts over a 5-GW hold) under `--fixtures
--transfers 1`. **Not actioned pending review** — see `TEAM_CHANGE_LOG.md`.

Secondary finding: **Tavernier's bench slot now reads 68.8%** over the last 16
GWs vs 81.6% for the season — still clears the 60% bench floor, but the drop
is real and worth a watch, not an action (bench fodder only needs to clear
60%, and he does).

### Gate 4 — expected points, from FPL's scoring table

**Corrected 9 Aug 2026.** The first version used hand-picked coefficients —
`xGI/90 × 8`, `(1.6 − xGC/90) × 6`. **Those numbers appear nowhere in FPL's
rules.** They were mine, and they made the squad's shape depend on constants
nobody had tested. Sylvan was right to reject them: the point values are set by
the game, not by us.

Selection now scores **expected points per 90**, and every coefficient is a rule:

```
xP/90 = 2                                    appearance (60+ mins)
      + GOAL[pos] × xG/90 + 3 × xA/90        6 DEF · 5 MID · 4 FWD · 3 assist
      + CS[pos]   × P(clean sheet)           4 GKP/DEF · 1 MID · 0 FWD
      + 2         × P(clearing DC threshold) 10+ CBIT DEF · 12+ CBIRT MID/FWD
      − xGC/90 ÷ 2                           GKP and DEF only
      + saves/90 ÷ 3                         GKP only
```

`P(clean sheet) = exp(−xGC/90)`. **Goals and assists are scored separately** —
lumping them into xGI was itself an error, since a defender's goal pays 6 and his
assist 3.

**One judgement survives, and it is stated rather than hidden.**
`P(clearing the DC threshold)` is estimated from a **season mean**, in bands
(≥1.3× the line → 0.75, ≥line → 0.55, ≥0.8× → 0.20, else 0.05). The award is
**per match**, so consistency beats volume — a player averaging 14 is worth no
more than one averaging 11, and one averaging 9 far less. A linear function of
the mean would get all three wrong. **The honest fix is the true per-match hit
rate** from `element-summary`, which needs current-season data (`accurate=True`
on the screens).

**Delta stays out of the model.** It is a discount signal for spotting underpriced
players, not a component of expected points.

#### This is a composite score, which D5 warned against

Design note **D5** deliberately avoided a blended xP. That objection was that a
single number ranks the **mid-table defender highest** — the archetype with no
reliable route. **It does not apply here**: this model scores him low because
*both* `P(clean sheet)` and `P(threshold)` are low, rather than averaging them
into a flattering middle.

**Both tools stay.** Archetypes are the right way to **read a screen** — they show
*which* route a player has. xP is the right way to **choose between positions
under a budget** — it puts a keeper, a defender and a forward on one scale.

#### What changed when the weights were corrected

**13 of 15 players were unaffected**, which is the useful result: the squad was
not an artifact of the invented constants. The two differences:

| | |
|---|---|
| **Schade** (BRE, £6.0m, xP 4.55) in for **Berge** | a genuine upgrade — Berge was bench fodder |
| Formation **3-4-3 → 3-5-2** | drops Calvert-Lewin (4.27) as a third starter for **Evanilson** (3.64) as cheaper fodder |

### Gate 5 — how the constraints are actually solved

**`build_squad.py` is greedy. `optimise_squad.py` is exact.** Both use the same
gates and the same xP model; they differ only in method.

**The greedy fills each slot with the best available and checks the budget at the
end.** It never consults the budget while choosing. Measured:

| Budget | ILP xP | Greedy |
|---|---|---|
| £100.0m | 49.54 | **49.54 — identical** |
| £95.0m | 48.77 | **no feasible squad** |
| £90.0m | 47.79 | **no feasible squad** |
| £85.0m | 45.85 | **no feasible squad** |

**At full budget greedy is optimal**, and claiming otherwise would oversell the
optimiser — the constraint is slack, so slot-by-slot picking happens to fit. Below
that it does not degrade gracefully; **it returns nothing at all.**

**The tight case is the normal case.** A pre-season rebuild with the whole £100m
free is the one situation greedy handles. Every mid-season transfer is made with
£0.5m in the bank against a fixed squad — exactly where greedy has nothing to say.

The ILP formulation:

```
maximise   Σ xP_i · x_i                      only the XI scores
subject to Σ price_i · (x_i + b_i) ≤ 100.0   but all 15 are bought
           Σ (x_i + b_i) = 15,  2/5/5/3 by position
           Σ x_i = 11,  1 GKP · 3-5 DEF · 2-5 MID · 1-3 FWD
           Σ per club (x_i + b_i) ≤ 3
           x_i + b_i ≤ 1
```

**The bench is a cost, not a benefit** — which is what makes it a real problem.
Every pound on fodder is a pound off the XI. Maximising over all 15 would buy a
luxury bench that never plays.

**One correction the ILP forced.** With bench xP contributing nothing, the solver
was indifferent among equal-priced fodder and picked a 61%-starter — worthless for
autosub and Bench Boost. An epsilon-weighted secondary term now prefers the
fodder who actually plays. It is small enough that it can never alter an XI
decision.

### xP_adj — expected points against the actual opponents

**Added 9 Aug 2026.** `fixture_adjust.py`, wired in via
`optimise_squad.py --fixtures`. Flat xP asks *what does he do in an average
match*; xP_adj asks *what will he do against the sides he is about to face*.

**Same scoring table, same coefficients.** Only the inputs are scaled, through
two channels that are deliberately kept separate:

| Channel | Scales | Source |
|---|---|---|
| **ATT x** — opponent leakiness | your goals and assists | `fixture_difficulty` |
| **DEF x** — opponent potency | your goals conceded, hence clean sheets | same |

The multipliers are taken from the MCP rather than recomputed, so this file and
`captaincy_odds` can never disagree about how hard a fixture is.

**A third, second-order channel** (`SCALE_WORKLOAD`, default on): a defender
facing a potent side makes more clearances and blocks, and a keeper faces more
shots. Directionally obvious, but see the fragility note below.

#### The measured effect is small, and that is the point

```
swing across the pool : −0.66 to +0.75 xP/90
mean |swing|          :  0.13 xP/90  ≈ 0.5 pts over 4 gameweeks
```

**This confirms the standing discipline rather than overturning it.** League-wide
multipliers span roughly 0.88–1.23, so **player quality still dominates fixtures**.
Fixtures break ties; they do not make the case.

#### KNOWN FRAGILITY — the threshold bands create cliffs

`p_threshold` is a **step function** (0.75 / 0.55 / 0.20 / 0.05). **52% of the
pool sits within 15% of a band edge**, so a small fixture nudge can jump a player
a whole band — worth 0.3–0.7 xP for no footballing reason.

Robustness check, workload scaling on vs off:

- **9 of 11 agree.** Virgil and Calvert-Lewin enter under *both*, so they are
  driven by the primary channels — Liverpool's 0.69 DEF x is the best defensive
  run in the league by a distance.
- **The two that disagree** (Anderson/Tavernier vs Enzo/Gakpo) are precisely the
  players sitting on band edges. **Treat those slots as coin-flips, not findings.**

**The proper fix is a smooth hit-rate from per-match data**, not a wider band —
`accurate=True` on the screens, once current-season data exists.

#### Refreshing the window — a weekly step, not a reminder

A stale window **silently optimises for matches already played**, and nothing in
the output would look wrong. So the window is no longer a hand-edited constant:

```
fixture_difficulty(next_n=4)          # MCP
  └─> python3 fixture_adjust.py --update --gw N
        writes fixture_window.json, stamped with the gameweek
```

**`--update` parses the tool output** rather than asking anyone to retype 40
numbers — hand transcription is exactly the class of silent error this project
has already hit twice. It **refuses a truncated paste** (fewer than 20 teams) and
reports if the fixture counts are uneven, which is how a double or blank
gameweek announces itself.

**Every run prints the stamp.** `check_stale(current_gw)` compares it against
`get_deadline`, and the weekly brief **must not quote the optimiser if they
disagree**. The built-in `FIXTURES` constant is a fallback and a committed record
of GW1–4 only — do not hand-edit it.

### The bench is selected on different rules entirely

**Cheapest player who still actually plays** — not a merit ranking. Bench points
arrive only via autosub or Bench Boost, so **availability is the whole point and
quality is not worth paying for.** This is why Shaw (£4.5m, 38/38 starts, 0.08
xGI/90) is in the squad and why that is not a contradiction.

---

## The governing principle

**The model is the default. An override is an exception that must be argued,
recorded, and later scored.**

The burden of proof sits on the override, never on the model. "I prefer him" is
not an argument. If a reason cannot be written as a falsifiable statement with a
date attached, it is not a reason — it is a preference, and preferences are what
this system exists to remove.

**An override you cannot be proved wrong about is worthless**, because it can
never teach you anything.

---

## The hierarchy

Overrides are ranked by how badly the model is failing. **Higher tiers are
stronger claims and require less argument, because at the top the model has no
valid input at all.**

### Tier 1 — MODEL INVALID · override is required, not optional

The player's data describes a situation that **no longer exists**. The model is
not wrong here, it is *inapplicable*.

| Trigger | Example |
|---|---|
| Mid-season club transfer | Guéhi (Palace → City) — prior blends two clubs |
| Confirmed role change | A holder moved to No.10 |
| Manager change at the club | Rotation and system both reset |
| No Premier League history | van Ewijk (promoted) — **no row at all** |
| Suspension or long-term injury | Fofana, banned to 6 Sep |

**Evidence needed:** the fact itself, dated and sourced. Nothing more.
**Cap:** none. This is not discretion; it is repair.
**Consequence:** the player is either excluded or assessed entirely on Tier-1
grounds. **Never quietly averaged with a stale number.**

### Tier 2 — SAMPLE MISLEADING · override allowed with a quantified alternative

The data is valid but **unrepresentative of what the player will do next**.

| Trigger | Example |
|---|---|
| Injury-shortened season | Isak — **694 minutes, 21% starts** |
| Broke into the side late | Strong final 10 GWs, weak first 28 |
| Rotation that has since resolved | Cherki — 50% starts in a first season at City |

**Evidence needed — this is the strict part.** A claim that the sample misleads
must come with **a better-specified sample**: a split (last 10 GWs vs first 28),
a per-90 rate over the representative window, or the equivalent at a former club.
**"Small sample, trust me" is rejected.** State the alternative number.

**Cap:** counts against the override budget below.

### Tier 3 — FORWARD-LOOKING FACT · override allowed, capped, must expire

Something knowable now that the backward-looking data cannot contain.

| Trigger | Example |
|---|---|
| Set-piece duty change | Penalty taker departed |
| Starting berth confirmed | The competing player left or is injured |
| Pre-season role signal | Played as a No.9 throughout pre-season |

**Evidence needed:** dated, sourced, **falsifiable**, with an expiry. This is the
existing `ROLE_INTEL.md` standard and it is not relaxed here — anything
unconfirmed is marked `?` and **auto-voids after ~5 gameweeks** if unproven.

**Cap:** counts against the override budget.

### Tier 4 — TIEBREAK ONLY · never a primary reason

May **only** choose between candidates the model already rates as near-equal
(within ~5% on the position's core metric).

- Creator or community consensus
- Eye test
- Fixture run *(already modelled — do not double-count)*
- **Price and ownership** — see below

**Never sufficient to promote a player the model ranks materially lower.**
If a Tier-4 argument is doing real work, the honest conclusion is that you want
the player for reasons the system does not support. Say that out loud.

### Preferences must be PRICED, not just labelled

*Added 9 Aug 2026, after a failure of exactly this kind.*

The no-Haaland preference was correctly recorded as **a preference, not a
finding** — and then **silently hardcoded into the optimiser**, whose output was
reported as "OPTIMAL". Labelling a preference honestly in one document does
nothing if the code applies it invisibly somewhere else.

**Rule: any preference that constrains selection must report its cost every time
it is applied.** `optimise_squad.py` now solves the problem twice — once free,
once constrained — and prints the difference.

For the Haaland case:

```
unconstrained optimum : 49.60 xP/90   (Haaland IS in it)
with no-Haaland held  : 49.54 xP/90
COST OF THE PREFERENCE: 0.06 xP/90    (~2 pts/season)
```

**Haaland is genuinely in the optimal squad** — the preference was never tested
against the model until now. But it costs **0.06 xP/90**, comfortably inside model
error, so it is effectively free to hold.

Holding it gives up Haaland, Scott and Calvert-Lewin; it starts B.Fernandes,
Thiago and João Pedro instead. **£15.5m on one striker buys almost exactly what
£12.0m on Bruno plus depth buys** — which is a real finding, and the opposite of
what "Haaland is excluded" implied.

**The general rule:** if a preference costs **< 0.30 xP/90** it is free — hold it
without argument. Above that it is buying something with points, and the trade
should be stated out loud.

### Tier 5 — NEVER VALID

These are recorded so they are recognised and refused, not debated:

- **Price rises or falls.** Price is a *timing* signal, never a *ranking* one.
- **Ownership FOMO** — "everyone has him".
- **Recency** — one big haul, or one blank.
- **"He's due."** Regression is already in delta.
- **Sunk cost** — defending a transfer already made. *(Live risk: the Mateta
  swap of 8 Aug is exactly this trap.)*
- **Reputation or transfer fee.**

---

## The override budget

**Maximum 3 active Tier 2–3 overrides at any time.**

Tier 1 is uncapped — it is repair, not discretion.

The cap exists because **an unlimited override right means there is no model**.
If more than three feel necessary, the model is wrong and should be fixed, not
bypassed. Hitting the cap is a signal to review methodology, not to raise it.

---

## Record format

Every override goes in `TEAM_CHANGE_LOG.md` under **OVERRIDES**, in this shape.
An override without a falsification test is **not valid** and should be reverted.

```
[T2] Isak — 2026-08-09 — EXPIRES GW6
  Model says : excluded. 694 mins, 21% starts, below the 900-min sample floor.
                Baseline falls back to pos+price, not his own record.
  Override   : the 2025/26 sample is injury- and transfer-distorted, not a
                true rotation signal.
  Alternative: [REQUIRED - his per-90 over a representative window. Without
                this number the override is INVALID and he stays excluded.]
  Source     : [required]
  Falsifies  : starts fewer than 4 of GW1-6.
  Scored at  : GW6.
```

---

## Scoring — the part that makes this real

**Every override is logged as a prediction and scored later**, alongside
`log_predictions`. At GW10 and GW20, compute for each resolved override:

1. What the model would have delivered
2. What the override actually delivered
3. The difference

Then report **net override value**.

**If judgement is net negative at GW20, cut the cap from 3 to 1.** If it is
strongly positive, the model is missing something systematic — find out what and
build it, rather than continuing to patch by hand.

**This is the only mechanism that distinguishes judgement from bias.** Without
it, every override looks reasonable in hindsight.

---

## Applying it to the open cases

| Case | Tier | Verdict |
|---|---|---|
| **van Ewijk** — no PL data | **T1** | Model inapplicable. Pick on Tier-1 grounds or not at all. Currently a placeholder with no assessment. |
| **Guéhi** — contaminated prior | **T1** | Prior blends Palace and City. Must not be averaged. Needs a City-only rate. |
| **Fofana** — banned to 6 Sep | **T1** | Hard fact. Excluded now; reassess GW4+. |
| **Isak** — 694 mins, captain | **T2** | **Override INVALID as it stands** — no alternative number supplied. On the framework he is excluded, and should not be captain. |
| **Cherki** — 50% starts | **T2** | Legitimate candidate. Needs his post-settling per-90 split. Falsifiable: starts in GW1–4. |
| **Mateta** — 66% starts | **T2** | Fails the gate. **Defending the 8 Aug swap would be Tier 5 sunk cost.** Either supply a T2 alternative number or revert. |
| **B.Fernandes** — delta +9.9 | **none** | Not an override case. Delta is already inside the model; the model kept him knowingly. |
| **Haaland** — squad preference | **T5** | "Plays without Haaland" is a preference, not evidence. **Legitimate to hold — but record it as a preference, not a finding.** |

---

## What this framework refuses to do

It does **not** stop him picking whoever he wants. It makes the reason explicit,
so that at GW20 the question *"did judgement help?"* has an answer instead of an
argument.
