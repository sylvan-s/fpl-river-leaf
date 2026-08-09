# Glossary — what every acronym and column actually means

Plain-language reference for the numbers in the weekly brief and the MCP tools.
If a term appears in a table and isn't here, that's a gap worth flagging.

---

## 1. The expected-goals family

These are the foundation. Everything else builds on them.

**xG — expected goals.**
For every shot, a model estimates the chance it becomes a goal, based on where
it was taken from, what body part, how many defenders were nearby. A tap-in from
two yards might be 0.8 xG; a speculative 30-yarder 0.02. Add up a player's shots
and you get his xG: **how many goals an average player would have scored from
those chances.**

**xA — expected assists.**
The same idea for passes. A pass that sets up a tap-in scores high; a hopeful
cross scores low. It measures **chances created**, regardless of whether the
teammate actually scored.

**xGI — expected goal involvement.**
Simply `xG + xA`. One number for a player's total attacking output — goals and
assists combined, measured by the quality of chances rather than the outcome.

**This is the single most important metric in the system.** Everything about
attacking players is ranked on it.

**xGC — expected goals conceded.**
Same model, pointed the other way: how many goals a team *should* have conceded
given the chances they allowed. **Lower is better.** Used to judge defences and
clean-sheet potential.

---

## 2. Why xGI and not just goals?

Because goals are noisy and chance creation isn't.

Measured across seasons:

| What you measure | How much it repeats next season |
|---|---|
| **Chance creation** (xGI volume) | **~0.63** — mostly real skill |
| **Finishing** (beating your xG) | **~0.12** — mostly luck |

A player who created lots of chances last season will probably do it again. A
player who scored *more* than his chances deserved probably won't repeat it.

So we **rank on xGI**, not on goals. A player's goal tally mixes a repeatable
skill with a mostly-random one; xGI isolates the repeatable part.

**Delta — the discount signal.**

```
Delta = (goals + assists) − xGI
```

- **Negative delta** — he created more than he scored. The goals *haven't landed
  yet*, so his price and ownership are low. **Potentially underpriced.**
- **Positive delta** — he scored more than his chances warranted. Price and
  ownership reflect returns unlikely to repeat. **Be cautious.**

**Important:** delta is a *discount* signal, not a prediction. It tells you which
high-xGI players are cheap. **Never sell a high-xGI player on positive delta
alone** — the xGI is the asset.

**One exception: penalty takers.** A penalty converts far above open-play xG, so
regular takers run a permanently positive delta. That's their *role*, not luck.

---

## 3. Defensive contribution — the newer scoring route

FPL awards **2 points** per match for defensive work, capped, once a player
crosses a threshold.

**CBIT — Clearances, Blocks, Interceptions, Tackles.**
Used for **defenders**. Threshold: **10+ in a match**.

**CBIRT — the same four plus Recoveries.**
Used for **midfielders and forwards**. Threshold: **12+ in a match**.

### The trap: it's a threshold, not a total

The 2 points are awarded at the line and capped there.

- A player averaging **14** is worth **no more** than one averaging **11**
- A player averaging **9** is worth **far less** than one averaging **11**

So **consistency above the line beats raw volume**, and ranking players on
average CBIT is actively misleading. This is why the tables carry a **DC** column
rather than just the number.

**DC column:**

| Value | Meaning |
|---|---|
| `yes` | Actually clears the threshold — a genuine 2pt floor |
| `near` | Within 20% of the line — will miss often. **The floor is a mirage.** |
| `no` | Doesn't reach it |

**How rare is `yes`?** Only about **8 of 47** defenders and **4 of 47**
midfielders in the mid-price bands clear their threshold. A player priced as a
defensive workhorse who sits at `near` is the classic trap.

---

## 4. Role-based archetypes

Rather than one score, players are labelled by **which routes to points they
actually have**. The labels are computed, not assigned by judgement.

### Midfielders

Two axes: **xGI per 90** (attacking ceiling) and **CBIRT** (defensive floor).

| Archetype | Clears 12+ CBIRT? | Above-median xGI? | What it means |
|---|---|---|---|
| **box-to-box** | yes | yes | Both routes. Highest floor *and* ceiling. Rare and valuable. |
| **holder** | yes | no | A genuine 2pt floor, little attacking upside. Fine cheap; hard to justify at a premium. |
| **attacker** | no | yes | Ceiling but no floor. Boom or bust. |
| **borderline** | *near* | no | **The trap.** Priced like a holder, doesn't earn a holder's floor. |
| **limited** | no | no | Neither route. |

**Note the asymmetry:** the defensive axis is judged against the **real 12+
threshold**; the attacking axis against the **median of the group**, because xGI
has no absolute cut-off.

**Why role matters more than team here:** a midfielder's archetype follows *where
he plays on the pitch*. A holder pushed forward, or a No.10 asked to sit deeper,
changes profile immediately — long before season stats show it. So **role news
moves this faster than data does.**

### Defenders

Defenders score three ways: **clean sheet (4pts)**, **defensive contribution
(2pts at 10+ CBIT)**, and **goals (6pts — the highest in the game)**.

**All three count in selection.** A defender can be picked on attacking output
alone despite a low CBIT/90 — O'Reilly at 0.30 xGI/90 is roughly double any other
defender in the current squad. See `SELECTION_FRAMEWORK.md` "Gate 4" for the
weights. **A low CBIT/90 is not by itself a reason to reject a defender.**

**The two routes are nearly independent** — corrected 8 Aug 2026.

The intuition is that they pull against each other: a dominant team keeps clean
sheets but its defenders rarely reach 10 CBIT, while a pressured team's defenders
clear the threshold every week and never keep a clean sheet.

**Measured on 2025/26, that effect is far weaker than assumed:**

```
corr(CBIT/90, clean sheets) = -0.04    essentially zero
corr(CBIT/90, xGC/90)       = +0.14    weak, right direction
```

So the routes are **near-independent rather than opposed**. That does not change
the design — **independence is its own argument against blending.** One number
cannot carry two unrelated routes to points. It does mean you should not expect a
busy defender to be on a bad team, or a clean-sheet defender to be idle: **knowing
one tells you almost nothing about the other**, which is precisely why both are
shown.

| Archetype | Clears 10+ CBIT? | Solid defence? | What it means |
|---|---|---|---|
| **BOTH** | yes | yes | Busy *and* solid. Rare, best of both. |
| **workhorse** | yes | no | Real 2pt floor on a leaky team. Buy for the floor, not clean sheets. |
| **cleansheet** | no | yes | Clean sheets and attacking returns, no defensive floor. |
| **borderline** | *near* | no | Near the line but doesn't clear it. |
| **avoid** | no | no | **The mid-table trap** — neither route. |

**This is why the two are never blended into one score.** A single number would
rank the mid-table defender highest — the one archetype with no reliable route to
points.

**How rare is each?** Of 110 defenders with 450+ minutes in 2025/26, only **15
clear 10+ CBIT/90** — but **34 sit in the `near` band**. Roughly a third of the
population is priced for a floor it does not actually earn.

---

## 5. Fixture columns

**FDR — Fixture Difficulty Rating.** FPL's own 1–5 integer per fixture.
**No longer used anywhere in this system.** It merges attacking and defensive
difficulty into one number and exaggerates differences the underlying xG doesn't
support. It appears in the change log only as history.

Replaced by two columns, derived from opponent xG:

**ATT x** — multiplier on your **attackers'** output. **Higher is better.**
Driven by how leaky the opponent's defence is. `1.00` = average opponent.

**DEF x** — multiplier on the goals you **concede**. **Lower is better.**
Driven by how potent the opponent's attack is.

**The best attacking run and the best defensive run are usually different teams.**
Read the column matching the position you're buying.

**exp xGI** — expected goal involvement over the whole window: the player's rate
× each opponent's leakiness × home/away, summed across fixtures.

**exp CS** — expected **clean sheets** over the window, from opponent potency.

Both sum over **fixtures, not gameweeks** — so a double counts twice and a blank
counts zero, automatically.

**One thing to keep in perspective:** league-wide attacking multipliers span only
about **0.89 to 1.11**. Over five gameweeks, **player quality usually matters
more than fixtures.** Don't overstate a 0.05 difference.

**DefΔ (DefDelta)** — `xGC − actual goals conceded` for a defender's team.
- **Positive** = conceded fewer than expected. **Riding luck** — clean sheets
  likely to dry up.
- **Negative** = conceded more than expected. **Unlucky** — clean sheets are due.

---

## 6. Shrinkage — the raw vs shrunk columns

Early in a season a player's own numbers are almost meaningless. Two games isn't
evidence. But throwing them away entirely is also wrong.

**Shrinkage blends** what you've observed with what you already knew, weighted by
how much evidence exists:

```
shrunk = (n × observed + k × baseline) / (n + k)
```

- **At GW1** the shrunk value *is* the baseline — no current data to weigh
- **By ~GW20** it has largely converged on the raw number
- **The useful window is GW3–15**

**Rule of thumb: trust shrunk early, raw late.** Both are always shown side by
side so neither can be quietly substituted for the other.

**base column — which baseline was used:**

| Value | Meaning |
|---|---|
| `own` | His own prior-season rate — the best case |
| `team+pos` | Team and position average — used when he changed club |
| `pos+price` | Position and price bracket — used when he has no PL history |
| `pos` | Position overall — last resort |

**Anything other than `own` means the personal prior was unavailable or
disqualified** — a club change, no Premier League history, or a flagged role
change that makes his old numbers describe a different job.

**k** — how much evidence the baseline is worth, in matches. It's **derived from
the data**, not chosen: if players genuinely differ a lot, trust individual data
quickly (low k); if they're alike and results are noisy, shrink hard (high k).

---

## 7. Captaincy columns

Captaincy is a **distribution** problem, not a fixture-difficulty one.

**E[pts]** — expected points. The average outcome.

**P(haul)** — probability of **10 or more** points. **This is what gains rank.**
For a midfielder, 10 points means roughly a goal *plus* something else.

**P(blank)** — probability of **2 or fewer** points. **This is what loses rank.**
2 points is exactly what a player gets for playing the full match and doing
nothing. **Dominated by rotation risk** — not starting is the biggest cause.

Since 8 Aug 2026 this applies the **published status flag**: a suspended, injured
or unavailable player gets P(start) = 0 rather than his historical start rate,
and a doubtful player is scaled by his stated chance of playing. Before that fix
a banned player could still show a low P(blank), which was the single worst
failure in the model.

**SD** — standard deviation. Volatility summary; less useful than the two tails,
because captaincy is asymmetric — you care about the upside far more than spread.

**SUSP — suspension risk.** Yellow cards against the next ban threshold: **5 by
GW19** (1-match ban), **10 by GW32** (2 matches), **15 by GW38** (3 matches).

| Value | Meaning |
|---|---|
| `BANNED` | Already suspended. **This one does hit P(blank)** — he cannot play |
| `4/5 RISK` | **One booking away.** A yellow this week bans him *next* week |
| `3/5 watch` | Two away — worth tracking over a long hold |
| `2/5` | Counting only |
| `-` | All thresholds passed or lapsed |

**Read it as a hold signal, not a blank signal.** This is the one people get
wrong: a fifth yellow picked up on Saturday bans the player from the *following*
match, so it does **not** change this week's P(blank). It changes what a
multi-gameweek hold is worth. Second-yellow reds are a separate rule and aren't
modelled.

**DiffUp** — `P(haul) × (1 − ownership)`. **Whether the captaincy is a bet at
all.** Captaining a 50%-owned player is largely rank-neutral whatever happens;
captaining a 5%-owned player is a genuine two-way bet against the field.

**Modes:**
- `protect` — low P(blank), high ownership. Defending a rank or a lead.
- `chase` — high DiffUp, low ownership. Need to make up ground.
- `neutral` — highest expected points.

**Triple Captain is purely a P(haul) maximisation** — the chip's value is one
extra copy of the score, so target the upper tail, not the mean.

---

## 8. Other columns

**SP — set-piece duty.** `P` penalties, `F` direct free kicks, `C` corners.
Number = order, so `P1` is first-choice penalty taker.

- **Plain** (`P1`) — confirmed by the FPL API
- **With `?`** (`P1?`) — expected, from `ROLE_INTEL.md`, **unconfirmed**
- **`-`** — neither source has anything

FPL doesn't populate these until the season is under way, so `-` is normal
pre-season.

**Own% — ownership.** Percentage of all FPL managers who own him. High ownership
means a player is "template" — owning him protects your rank but can't gain you
any. Low ownership means a differential: a two-way bet.

**Status flags** — `INJURED`, `DOUBTFUL`, `SUSPENDED`, `UNAVAILABLE`, with a
percentage chance of playing where FPL provides one.

**Gms** — number of *fixtures* in the window, not gameweeks. A team with a double
gameweek shows more fixtures than gameweeks; a blank shows fewer.

---

## 9. Chips

Two full sets per season. **Set 1 must be used before the GW19 deadline
(Sat 2 Jan 2027, 13:30 GMT) and does not carry over.**

**Wildcard** — unlimited permanent transfers in one gameweek, no points hit.
**Free Hit** — unlimited transfers for one week only; squad reverts afterwards.
**Bench Boost** — your four bench players' points count that week.
**Triple Captain** — captain scores ×3 instead of ×2.

**DGW / double gameweek** — a team plays twice. **BGW / blank** — a team doesn't
play at all.

**The key idea: a chip's value is *marginal*.** Triple Captain earns you one
*extra copy* of the captain's score, not the whole score. Bench Boost earns the
bench's points, minus anything that would have been auto-substituted in anyway.

---

## 10. Expected points and the optimiser

**xP — expected points per 90.** One number per player, built entirely from
**FPL's own scoring table**. Nothing in it is a tuned coefficient:

```
xP/90 = 2                              appearance (60+ mins)
      + GOAL[pos] × xG/90 + 3 × xA/90  6 DEF · 5 MID · 4 FWD · 3 per assist
      + CS[pos]   × P(clean sheet)     4 GKP/DEF · 1 MID · 0 FWD
      + 2         × P(clears DC line)  10+ CBIT DEF · 12+ CBIRT MID/FWD
      − xGC/90 ÷ 2                     GKP and DEF only
      + saves/90 ÷ 3                   GKP only
```

**Rule of thumb: xP/90 × 38 ≈ season points.** So a 0.10 difference between two
players is roughly **4 points across a season** — useful for telling a real
upgrade from a rounding error.

**Why xP exists alongside the archetypes.** They answer different questions and
both are kept:

| | Question | Tool |
|---|---|---|
| **Archetype** | *Which route to points does he have?* | reading a screen |
| **xP** | *Who do I buy with £6.0m?* | choosing across positions |

An archetype cannot compare a goalkeeper to a forward. xP can, because it is
denominated in points. **A `borderline` label still beats a good xP** when you are
judging reliability — the label carries information the average hides.

**The one estimate inside xP.** `P(clears the DC line)` comes from a season
**mean**, in bands. The award is per-match, so consistency beats volume. The
proper fix is the true per-match hit rate, which needs current-season data.

### The optimiser

**Two tools, two questions.**

**`build_squad.py` — greedy.** Fills each slot with the best available and checks
the budget at the end. **It never consults the budget while choosing**, so it works
only when the unconstrained-best squad happens to be affordable. Below full budget
it does not degrade — it returns **nothing at all**.

**`optimise_squad.py` — exact.** An integer linear program (PuLP + CBC). Two modes:

- **Rebuild** — best 15 for £100m. The **wildcard** question, asked ~3 times a season.
- **Transfer** — best swap from the squad you own, with the real bank and free
  transfer count. **The weekly question.**

**The bench is a cost, not a benefit.** Only the XI scores, so every pound spent on
fodder is a pound off the starting eleven. Maximising over all 15 would buy a
luxury bench that never plays.

**Reading the output:**

- **"no gain above 0.01 xP/90 — HOLD"** means hold. It is not a tool failure, and
  a transfer should not be invented to fill a brief.
- **A −4 hit needs a hold horizon.** The output prints **breakeven gameweeks**: a
  hit is only worth it if you hold longer than that.
- **Preference cost.** Any preference constraining selection is priced on every
  run. The no-Haaland preference costs **0.06 xP/90 (~2 pts/season)** — inside
  model error, so effectively free.
- **Sell-price caveat.** It uses current price; FPL pays purchase price plus half
  any rise. Identical pre-season, lower mid-season. **Do not trust a marginal
  £0.1m call once prices have moved.**

---

## 11. Terms from the methodology

**Calibration** — does a stated probability mean what it says? If the model
claims 20% haul chance, hauls should occur about 20% of the time. Checked against
predictions recorded *before* the gameweek — it cannot be done retrospectively.

**Brier score** — how good probabilistic forecasts are. Lower is better.

**Skill score** — whether the model beats simply guessing the average for
everyone. Negative means it's worse than that, and shouldn't be trusted.

**Backtest** — computing a prediction from an early window and checking it
against a later one the prediction never saw.

**Contaminated prior** — a player whose prior-season stats blend two clubs
because he transferred mid-season. His personal baseline describes a situation
that no longer exists, so the fallback ladder skips it.
