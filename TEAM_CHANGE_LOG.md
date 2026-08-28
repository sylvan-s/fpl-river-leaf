# River Leaf FC — Team & Strategy Change Log

Entry **1041614**. Manager **aSyd Reigns**.

**Why this file exists.** The FPL API only exposes a squad *after* a gameweek
deadline has passed. A team still being edited is private. So this log is the
only record of the current pre-deadline squad and the reasoning behind it.
Read it before advising on any mid-week change; append to it after every change.

**Pruned 9 Aug 2026.** This file had accumulated a full narrative of every
methodology correction made while the model was being built — useful in the
moment, dead weight now that it's stable. Closed watchlist items, superseded
scoring debates, and pre-rebuild transfer rationale were cut or condensed to a
one-line record. What remains is what actually governs a decision today.

---

## CURRENT STATE — as at Fri 28 Aug 2026 (GW2 pre-deadline)

**Deadline:** Fri 28 Aug 2026, 18:30 BST (17:30 UTC) · **Formation:** 3-4-3 (unchanged)
**Last change:** **1 free transfer, 28 Aug** — `Sarr -> Schade`, via
`optimise_squad.py --fixtures --transfers 1` (intel ON by default). **Not yet
actioned live on the FPL site** — this file and `squad.json` record the
decision; Sylvan still needs to submit it on fantasy.premierleague.com before
the deadline above.
**Previous change:** FULL REBUILD, 6 transfers, 12 Aug (see below)
**Squad value** £99.5m · **Bank** £0.5m · **Captain** João Pedro · **Vice** Thiago
(**armband moved from Thiago** — see Captaincy below)

**Why the transfer.** Ran per Step 2f of the weekly process: refreshed the
fixture window (`fixture_difficulty(next_n=4)` -> `fixture_adjust.py --update
--gw 2`), then `optimise_squad.py --fixtures --transfers 1` with intel
confirmed ACTIVE in the output banner — carrying the 8 bites Sylvan accepted
via the Trello board's Take Action swimlane earlier the same day (see
`ROLE_INTEL.md`'s `adjustments` fence: Mosquera's `stp` window extended
1-3 -> 1-8; O'Reilly split into `cbit90 mult 0.8` + `xgi90 mult 1.2`; 13 AVL
pool players at `xgi90 mult 0.7`). None of those eight changed the top
recommendation — the transfer the optimiser actually surfaced is driven by
Sarr's own live `injury_report` status (INJURED, 0% chance of playing,
unknown return date), which was itself accepted narrative-only in that same
Friday review (no `field_affected` — his availability flows through live
status directly, not a fence entry).

**The numbers.** `Sarr -> Schade`: +0.22 xP/90, +1.1 pts over a 5-GW hold.
Clears the ~0.10 xP/90 noise floor but is a real, not a blowout, edge. Free
transfer, no points cost. Sarr sells at £6.5m (bought for £6.5m, no rise
yet), Schade costs £6.0m — **bank moves £0.0m -> £0.5m.**

**Risk accepted:** Schade's own start rate/role at Brentford this season is
itself only lightly tested (GW1-2 data), and he sits behind Thiago in BRE's
penalty order (2nd) — this transfer trades a confirmed-out injury doubt for
a fresh, thinly-verified pick, not a like-for-like swap of certainties.

**Alternatives rejected:** holding Sarr on a 75% chance he clears late fitness
tests was the only alternative the optimiser considered — rejected because a
free transfer with no hit cost and a positive (if modest) xP/90 gain removes
that uncertainty at zero cost.

**Captaincy re-confirmed, 28 Aug 2026, post-transfer.** Per the "every
transfer resets the armband" rule, ran `captaincy_odds` (with intel, neutral
mode) fresh against the new squad's front-runners: **João Pedro** now leads
both **E[pts] (4.77)** and **P(haul) (10.0%)**, against Thiago's **4.04 /
8.6%** — a real change from the 12 Aug pick, not a formality. Armband moves
to João Pedro (CHE, home to BHA), Thiago to vice. **Captaincy is free until
the deadline** — re-confirm again if fresh GW2 team news lands before 17:30
UTC.

**HOLDING THE FIXTURE-WINDOW CAVEAT.** These figures use the GW2-5 window
stamped today. The objective remains xP per 90, still blind to how often a
player starts (roadmap A0.5, not yet built).

---

## CURRENT STATE — as at Wed 12 Aug 2026 (GW1 pre-deadline, superseded above)

**Deadline:** Fri 21 Aug 2026, 18:30 BST · **Formation:** 3-4-3 (was 3-5-2)
**Last change:** **FULL REBUILD, 6 transfers, 12 Aug** — via `optimise_squad.py`'s
exact ILP (`--fixtures --intel`), 0 pts (unlimited free pre-deadline). **Not yet
actioned live on the FPL site** — this file and `squad.json` record the decision;
Sylvan still needs to submit it on fantasy.premierleague.com before it counts.
**Previous change:** 1 transfer, 11 Aug — Botman → Van den Berg
**Squad value** £100.0m · **Bank** £0.0m · **Captain** Thiago · **Vice** B.Fernandes
(**armband swapped** — see Captaincy below)

**Why the rebuild.** Two corrections landed together on 12 Aug and neither had
been run through a full rebuild before today: **roadmap A1** (`xbonus90` —
bonus points, previously entirely absent from the model, shrunk the same
empirical-Bayes way as every other rate, plus a bounded adjustment for the
2026/27 BPS rule change) and a fix for a standing gap — `build_squad.py`'s
`load()` never applied the `contaminated`-prior exclusion the live screens do,
which the 9-10 Aug rebuild had already worked around by hand but a fresh
full-pool search would not. Both are documented in `METHODOLOGY_ALTERNATIVES.md`
and `SELECTION_FRAMEWORK.md`. XI xP/90 (fixture-adjusted, intel applied):
**56.87** — not directly comparable to the pre-12-Aug figures, which didn't
include bonus at all.

| Pos | Player | Club | Price | st% | xbonus90 | Selected on |
|---|---|---|---|---|---|---|
| GK | Raya | ARS | £6.0m | 94% | 0.30 | 19 CS, best xGC (0.74). Unchanged. |
| DEF | Gabriel | ARS | £8.0m | 94% | 0.82 | xGC 0.72, 18 CS, 3rd-highest DEF xbonus90 in the pool. Unchanged. |
| DEF | O'Reilly | MCI | £6.5m | 81% | — | xP_adj 4.67 with intel vs Mosquera's 4.28 (Mosquera's own intel boost included) |
| DEF | Virgil | LIV | £6.5m | **100%** | — | Liverpool's GW1-4 DEF x is 0.69, the best defensive run in the league |
| MID | B.Fernandes | MUN | £12.0m | **100%** | 1.11 | xGI/90 0.68, highest in game, xbonus90 2nd-highest in the pool · **VICE (was captain)** |
| MID | Mbeumo | MUN | £8.0m | 88% | 0.55 | xGI/90 0.58, delta −3.0. Unchanged. |
| MID | O.Dango | BRE | £6.5m | 81% | — | xP_adj 5.23 with intel — the cheaper route the ILP found once Palmer's budget was reallocated |
| MID | Sarr | CRY | £6.5m | 75% | 0.33 | flat xP 4.78, delta −1.1. Unchanged. |
| FWD | Thiago | BRE | £8.0m | **100%** | 0.63 | xGI/90 0.62, 22 goals · **CAPTAIN** — highest E[pts]/P(haul) on `captaincy_odds`, 12 Aug |
| FWD | João Pedro | CHE | £7.5m | 75% | **0.97** | xbonus90 4th-highest in the ENTIRE 248-player pool. Delta +7.13 remains unresolved, but bonus is a second route not riding on his finishing |
| FWD | Calvert-Lewin | LEE | £6.0m | 94% | 0.68 | 14 goals, delta −0.6. Unchanged. |
| BEN | Leno | FUL | £4.5m | **100%** | — | GK cover, effectively tied with Verbruggen (xP_adj 3.36 v 3.47) — a coin-flip, not a finding |
| BEN | Justin | LEE | £4.5m | **100%** | — | bench 1 · the autosub that matters. Unchanged. |
| BEN | Shaw | MUN | £4.5m | **100%** | — | bench 2. Unchanged. |
| BEN | Sadiki | SUN | £5.0m | **100%** | — | bench 3, replaces Evanilson — a real autosub-value downgrade the objective can't see (A0.6 not built), accepted to fund João Pedro |

**Club counts:** MUN 3 (B.Fernandes, Mbeumo, Shaw — at the cap) · ARS 2 (Raya,
Gabriel) · BRE 2 (O.Dango, Thiago) · LEE 2 (Calvert-Lewin, Justin) · LIV 1
(Virgil) · MCI 1 (O'Reilly) · CHE 1 (João Pedro) · CRY 1 (Sarr) · FUL 1 (Leno)
· SUN 1 (Sadiki). Only MUN is at the 3-per-club cap.

**Trade-offs stated, not hidden — the reconciliation this rebuild required:**

- **Mosquera's minutes-opening thesis was not wrong, it was outbid.** The
  ROLE_INTEL intel boost (stp set to 0.85, GW1-3) is still active and still
  correctly raises his score — 4.28 xP_adj with intel vs 4.02 flat without —
  but that isn't enough to beat O'Reilly (4.67) or, once Liverpool's fixture
  run is counted, Virgil (4.48). A single 1-for-1 swap search (what ran on
  11 Aug) had already found this: Mosquera → Muñoz showed +0.70 xP/90
  *without* intel, closing to a HOLD *with* intel. A full-budget rebuild can
  reach further than a 1-for-1 search — it can also drop Palmer's £9.5m
  entirely and fund two defensive upgrades plus João Pedro at once, a move no
  single swap could price. Both readings are correct; they're answering
  different questions (SELECTION_FRAMEWORK.md's transfer-mode-vs-rebuild-mode
  distinction).
- **Palmer (xP_adj 5.51, individually one of the best midfielders in the
  pool) was dropped anyway.** Not because his own number is weak — because
  freeing his £9.5m, combined with Schade's £6.0m, is what pays for O'Reilly,
  Virgil and João Pedro together. A real trade, not a free upgrade.
- **Evanilson → Sadiki is a genuine downgrade in bench value** (94% → 100%
  starts sounds like an upgrade, but Evanilson's xP_adj 3.91 beats Sadiki's
  2.79) — bench autosub value isn't in the objective at all (roadmap A0.6,
  not built), so this loss doesn't show up in the 56.87 headline number.
  Accepted as the cost of the reallocation above, not unnoticed.

### Squad shape — the archetype each position is bought for

*Added 11 Aug 2026.* This is the qualitative read behind the xP formula in
`SELECTION_FRAMEWORK.md` — what a good pick actually looks like at each
position, and the trap to avoid. Restated whenever a transfer is argued, so
"why does this player fit" has a fixed answer rather than a fresh one each week.

| Pos | Buy for | The trap |
|---|---|---|
| **GK** | Undisputed #1 at his club first — everything else is void if he's benched. Then low season xGC (his side doesn't concede good chances) and save volume as a distant second. | A keeper with strong save stats who is one bad week from losing the gloves. Starts is gate 2 for a reason. |
| **DEF** | **Both** legs at once: a side with a genuinely low xGC/team CS rate, **and** the player's own CBIT volume clearing the 10+ per-match threshold reliably (his real hit-rate, not a season average sitting near the line — see the `KNOWN FRAGILITY` note on band edges). | Either leg alone. A great individual defender on a leaky side rarely banks the 4pt clean sheet. A defender racking up CBIT on a leaky side is often busy *because* his side is under siege, not because he's a good defender — high CBIT is not automatically good news. |
| **MID** | Attacking output first (xGI/90 — a goal pays 5, an assist 3, nearly forward money), **plus** the 1pt clean sheet sitting on top for free if his side is also tight at the back. Best case is both at once, not a trade between them. | Rarer, lower-reliability route: a genuinely defensive midfielder clearing 12+ CBIRT — worth knowing exists, not worth building a pick around. |
| **FWD** | Pure goals + assists + minutes. No clean sheet credit at all, and the DC threshold is not a real route — 2025/26 data shows forwards essentially never clear 10+ CBIT in a match (0% hit-rate across every matched forward in the pool). | Treating a forward's CBIT/90 average as if it predicts anything — there's no variance to explain, so a defensive-work argument for a forward is not a real argument. Availability matters more here precisely because there's no defensive floor under a blank. |

### The 5 transfers, and why

| Out | In | Reason |
|---|---|---|
| **Lacroix** (CHE) | **O'Reilly** (MCI) | Lacroix's 57% DC was already scored generously at 0.55 by the old model, so A4 barely moved him while it raised others past him. He also carries a **Crystal Palace** record — see the contaminated fence. |
| **Dubravka** (TOT) | **Verbruggen** (BHA) | Dubravka is a **Burnley** record *and* reported second choice at Spurs. Verbruggen is a genuine first-choice keeper at the same price. |
| **João Pedro** (CHE) | **O.Dango** (BRE) | delta **+7.1** — one of the largest overperformances in the game, and unlikely to persist. |
| **Tavernier** (BOU) | **Evanilson** (BOU) | Tavernier could not start (69%, below the 75% gate). Evanilson starts 94% and is worth more as the first substitute. |
| **Kayode** (BRE) | **Justin** (LEE) | Club cap: BRE was full. Justin is the same price with 100% starts. |

**Both contaminated players fell out on their own.** The corrected DC estimator
dropped Lacroix and Dubravka without being told anything about club changes —
two independent lines of evidence landing on the same two players.

**Captaincy is provisional, and it moved on 12 Aug.** `captaincy_odds` run
against the new squad's front-runners has Thiago ahead on both E[pts] (5.15)
and P(haul) (15.1%), narrowly ahead of B.Fernandes (5.05, 9.9%) — armband
swapped, B.Fernandes to vice. **Captaincy is free until the deadline** —
re-confirm with `captaincy_odds` on team news before Fri 21 Aug, not on this
table.

**HOLDING THE FIXTURE-WINDOW CAVEAT.** These figures use the GW1–4 window stamped
for GW1. The objective remains **xP per 90**, so it is blind to how often a
player starts (roadmap A0.5 — the availability haircut is ~11%).

## CHIP STRATEGY — SET 1 (expires GW19 deadline, Sat 2 Jan 2027 13:30 GMT)

*Last reviewed: Fri 7 Aug 2026. **Review every week as part of the brief.***

**Status:** all four unused. 18 gameweeks (GW1–18) to place four chips.

### The governing constraint

Doubles and blanks are created by cup rescheduling and land overwhelmingly in
the **second half**. Confirmed from live fixture data: **GW1–6 contain no
doubles and no blanks — all 20 teams play exactly six times.**

So set 1 must be spent in a window where the ideal conditions largely don't
exist. **The bar for a "good enough" first-half chip is deliberately lower than
instinct suggests.** The failure mode to avoid is holding out for a perfect week
that never arrives and panic-dumping in GW17–18. Be precious with set 2, not set 1.

### Plan

| Chip | Target window | Trigger | Hard backstop |
|---|---|---|---|
| **Wildcard 1** | GW6–9 | Once ~6 GWs of 2026/27 xGI exist and the delta rule has real signal | GW12 |
| **Bench Boost 1** | 1–2 GWs after WC1 | Only after a bench has been deliberately built on the wildcard | GW17 |
| **Triple Captain 1** | GW10–16 | Best available Thiago/Bruno home fixture vs bottom-six, or any confirmed DGW | GW16 |
| **Free Hit 1** | Held as insurance | Injury crisis, or a blank/fixture swing if one emerges | GW18 |

### Reasoning

**Wildcard 1 is the most valuable chip in set 1.** The current squad was built on
2025/26 data — the deltas driving it are last season's. By GW6 there will be real
current-season signal, and the squad will likely need restructuring. GW6 also
follows a long break (GW5 is 18 Sep, GW6 is 10 Oct), giving time to plan.

**Wildcard 1's original priority list (from 7 Aug) is fully superseded.** The
9 Aug rebuild addressed all of it — bench rebuilt, weak defenders replaced —
while transfers were still free. **New WC1 purpose: whatever the first 6 GWs
of 2026/27 data say**, once `A0.2`/`A0.3` exist and the delta rule has live
meaning.

**Bench Boost is no longer chip-starved.** The rebuilt bench averages **92.8%
start rate**, so BB1 is no longer strictly chained to WC1 — though a *good*
bench still beats a *playing* one, so review both together at GW6.

**Triple Captain is structurally weaker without Haaland.** Most managers triple
the 74%-owned nailed premium; the realistic targets here are Thiago or Bruno —
good, not explosive. Thiago's GW1 numbers (15.1% haul, 97% starts) make him the
current front-runner, and **TC is purely a P(haul) maximisation.** Because a pre-GW19 double is not guaranteed, do not hold TC1
hostage to one. Deploy on the best home fixture against weak opposition by GW16.
Both sit on reasonable runs, but note the spread is narrow: league-wide
attacking multipliers span only ~0.89–1.11, so **player quality dominates
fixtures** when choosing a TC target.

**Free Hit is the hardest to place** in a first half with no blanks. Hold it as
insurance against an injury cluster or congestion pile-up. If nothing has
triggered it by GW17, spend it on the best available fixture swing rather than
losing it.

### Review checklist (run weekly)

1. Has a double or blank gameweek appeared in the lookahead? → re-plan immediately
2. Is any chip inside 4 gameweeks of its backstop? → escalate to a decision
3. Has the squad changed enough to alter the WC1 case?
4. Is the bench now worth boosting?
5. `escalation_check` flags chip pressure from 6 gameweeks out — treat that as the alarm

### Decisions taken

- **GW1: no chip.** Nothing to boost, no double to triple, squad freshly shaped
  with free pre-season transfers. Wildcard would be redundant while transfers
  are unlimited and free.

### External validation — 11 Aug 2026

Checked the set-1 plan above against official PL guidance and community
consensus (Fantasy Football Scout, Fantasy Football Hub) for 2026/27. Our plan
is more conservative and more sequenced than generic advice, deliberately so —
recorded here so the divergence isn't mistaken for an oversight later.

- **Bench Boost.** Consensus default is GW1 or GW2, on the logic that pre-season
  predictability beats a deliberately-built bench. We explicitly rejected GW1
  (nothing to boost, WC1 would be redundant) and chain BB1 to 1–2 GWs after WC1
  instead. Correct call given the bench already runs 92.8% starts — no reason
  to trade a good bench for an early one.
- **Wildcard.** Consensus range GW4–8, sometimes GW6. Our GW6–9 window
  (backstop GW12) overlaps but is trigger-driven — ~6 GWs of live 2026/27 xGI
  before the delta rule has real signal — rather than a fixed calendar date.
  No change indicated.
- **Triple Captain — new concrete data.** Official PL fixture list gives exact
  home dates vs promoted sides in the first half: **Bruno** hosts Ipswich GW2
  and **Coventry GW14** (inside our GW10–16 window); **Haaland** hosts Coventry
  GW3, Ipswich GW7, and **Hull GW16** (lines up with our TC1 backstop, relevant
  only if Haaland re-enters the squad). Bruno/GW14 is now the concrete
  candidate to check against `captaincy_odds` as it comes into range, rather
  than a generic "best fixture by GW16" placeholder.
- **Free Hit.** Full agreement — insurance chip, not scheduled, hold for an
  injury cluster or fixture swing. No change.
- **DGW/BGW timing.** Consensus confirms blanks/doubles won't firm up until FA
  Cup rounds resolve, typically GW26+ — consistent with roadmap **B4**'s GW12
  gate. Confirms the gate is well-placed, not arbitrary.

---

## STANDING PREFERENCES — confirmed, priced, do not re-litigate

**No Haaland.** Confirmed by Sylvan 9 Aug 2026 *after* being shown the price —
the exclusion had previously been a hardcoded name filter, and the result was
reported as "optimal" without ever being tested.

| | xP/90 |
|---|---|
| Unconstrained optimum — Haaland is in it | 49.60 |
| With the preference held | 49.54 |
| **Cost** | **0.06** (~2 pts/season) |

**Well inside model error, so effectively free.** The reverse finding matters
more than the number: **£15.5m on Haaland buys almost exactly what £12.0m on
B.Fernandes plus squad depth buys** — holding the preference gives up Haaland,
Scott and Calvert-Lewin to start B.Fernandes, Thiago and João Pedro.
`optimise_squad.py` reprices the preference on every run and prints the cost,
so it can't be silently baked into something labelled "optimal" again.
**Trigger to revisit: cost above ~0.30 xP/90** — not before.

*Squad depth over one nailed premium* — the same preference, stated differently.

---

## OVERRIDES

*Governed by `SELECTION_FRAMEWORK.md`. **Max 3 active Tier 2–3 at any time**;
Tier 1 uncapped. Every entry needs a falsification test and a scoring date — an
override without one is invalid and the model stands.*

**Active: 0 of 3.** The 9 Aug rebuild used zero overrides — every pick came
from the gates. Three candidates were considered and all three failed the
evidence standard:

- `[T2] Isak` — model excludes him (694 mins, 21% starts, baseline falls back to
  `pos+price`). **Invalid as it stands** — no representative-window rate
  supplied. Excluded, and should not be captain.
- `[T2] Cherki` — 50% starts. Legitimate candidate; needs a post-settling per-90
  split. Falsifies if he starts fewer than 3 of GW1–4.
- `[T2] Mateta` — 66% starts, fails the availability gate. Defending the 8 Aug
  swap on any other basis would be Tier 5 sunk cost. Supply a T2 number or drop it.

Tier 1 (uncapped, model inapplicable): **van Ewijk** — no PL data at all;
**Guéhi** — contaminated Palace/City prior; **Fofana** — banned to 6 Sep.

---

## OPEN METHODOLOGY ITEMS

Live gaps and standing technical notes — not resolved, not urgent unless flagged.

- **Screens sort on season-total, not per-90.** `midfielder_screen(sort_by="xgi")`
  ranks by total xGI while displaying xGI/90, so high-rate/low-minutes players
  (Cherki, Palmer) sink out of a small `limit` and are never seen, not
  rejected. `analyze_players(names=...)` also ignores its own name filter.
  **NOT YET FIXED.**
- **Price forecasting — decide at ~GW3.** Not built; price/transfer fields
  are zero pre-season. If built: price belongs in *timing* ("is a player
  about to move"), never in *ranking* ("who to buy"). Check whether FPL's own
  Price Change Predictor is API-accessible first.
- **Goalkeeper methodology still undefined.** One real finding so far:
  saves/90 and clean sheets are anti-correlated for keepers (corr −0.58,
  n=19) — the opposite of defenders, so the GK screen can't reuse the
  defender archetype logic. Flag if GK selection comes up.
- **Midfielder clean-sheet and bonus routes are not modelled.**
  `midfielder_screen` misses value from clean sheets/bonus in a dominant
  defence — the reason Rice (184 pts, best value in his band last season)
  reads weak on the xGI screen alone. Bruno is held as vice partly *because*
  of this gap: he posts 29.6 BPS/90 while failing the CBIRT threshold, so the
  bonus route says more about him than the screen shows.
- **Roadmap staged by evidence gates, not dates** — see
  `METHODOLOGY_ALTERNATIVES.md`. The GW10 backtest is the decisive gate;
  bonus/BPS and goalkeeper methodology are the two highest-value blind spots
  found so far. Empirical-Bayes shrinkage (not full hierarchical Bayesian
  modelling) is the recommended next step, and it's what the GW10 backtest
  actually tests — it would also fix captaincy, currently a point-estimate
  decision when it's really a variance one.
- **SQLite lives at `~/.fpl-mcp/`, not in the Google Drive folder** — a sync
  client can corrupt a database mid-write. Text files stay in the folder; the
  live DB doesn't.

---

## PENDING — METHODOLOGY BACKTEST, GW10

**Scheduled: Tue 10 Nov 2026, 09:00** (task `fpl-methodology-backtest-gw10`, one-off).

Tests the xGI-first framework against real 2026/27 data rather than borrowed
literature. Splits GW1–5 and GW6–10 and asks which period-1 metric better
predicts period-2 goals+assists: **period-1 xGI, or period-1 actual G+A**.

Runs via the `predictive_backtest` MCP tool. Verified against a positive control
(xGI-driven synthetic data → correctly SUPPORTED) and a **negative control**
(goal-driven synthetic data where xGI is pure noise → correctly NOT SUPPORTED),
so the test is capable of failing.

**Pre-committed interpretation, recorded before the result is known:**
- Difference under 0.05 → inconclusive, not a refutation
- A negative result gets logged and acted on, not explained away
- The skill is not rewritten unilaterally — the case goes to Sylvan

---

## WATCHLIST — conditional decisions to revisit

Everything logged here before the 9 Aug rebuild has been closed and removed —
the players are gone and the reasoning no longer bears on the current squad.
Three open items:

**GW2 — three options recorded, none actioned (Tue 25 Aug 2026, deadline Fri
28 Aug 17:30 UTC).** Squad news: Sarr (CRY) DOUBTFUL 75%, groin — trained
Monday per Sage, expected back. Rest of squad clean. Optimiser
(`optimise_squad.py --fixtures --transfers 1`, window refreshed for GW2): best
1-transfer move gains nothing above 0.01 xP/90 — explicit HOLD from the model
itself. `captaincy_odds` (neutral): **Mbeumo** tops on E[pts] 5.41 / P(haul)
13.0% / P(blank) 21.1% / DiffUp 8.2, narrowly ahead of B.Fernandes (5.30 /
12.2% / 20.2%) — both benefit from Man Utd hosting Ipswich (promoted, treated
as league-average — likely conservative in United's favour). Predictions
logged for GW2 (Mbeumo, B.Fernandes, Thiago, João Pedro, Calvert-Lewin) before
this entry, per the mandatory pre-deadline rule.

  1. **Hold / Protect Rank** — no transfer. Captain Mbeumo. Cost 0.
  2. **Value Transfer — de-risk Sarr** — Sarr → Dewsbury-Hall (EVE, £6.5m for
     £6.5m). Edges Ødegaard at the same price and points (11 each, delta +0.71
     v +0.69): Everton's GW2-5 run is better on both ends (ATT x 1.03 v
     Arsenal 0.99, DEF x 0.94 v 1.04). Direct answer to taking Sarr's injury
     doubt seriously — equal-priced, better fixtures, no speculation. Cost 0.
  3. **Aggressive Play — compound move** — O.Dango → Sangaré (BRE, £6.5m →
     £5.5m, frees £1.0m; 13 DefCon + 2 assists on debut, Scout's explicit BUY,
     but zero 2025/26 PL minutes so he clears none of our gates — pure
     speculation) **+** Sarr → Gakpo (LIV, £7.0m, only reachable once the
     freed £1.0m stacks with Sarr's own £6.5m sale). Gakpo has an established
     personal prior, clears the 12+ CBIRT floor reliably (box-to-box, not just
     attacker), and sits on Liverpool's best DEF x in the league (0.72). Second
     transfer this window costs **-4**. The Gakpo half is model-backed: the
     Sangaré half is not.

No option actioned yet — Sylvan is holding the decision open across the week.
Revisit before Friday's deadline; update CURRENT STATE and CHANGE HISTORY the
moment one is actioned, and re-set the captain regardless of which option is
picked (captaincy is free until the deadline).

**Palmer (CHE, £9.5m)** — logged 9 Aug alongside the Enzo→Sarr swap. **Not
excluded by any gate**: 5.11 xP/90 (best midfielder in the pool, ahead of
B.Fernandes' 5.04), 88% last-16 starts. Blocked on price and the CHE club cap
(would make 3 with Lacroix + João Pedro) — a budget question, not a form
question. Revisit at Wildcard 1 or if £0.5m+ frees up sooner.

**Danso (TOT, £5.0m)** — rejected by the 75% start-rate gate (45% starts, 17
of 38) despite the best CBIT/90 in the game (11.6). Revisit only if his start
share rises; the differential case depends entirely on him playing.

---

## CHANGE HISTORY (newest first)

### Wed 12 Aug 2026 — GW1 — FULL REBUILD via optimise_squad.py (6 transfers, 0 pts)

**Trigger.** Sylvan: "update the squad selection based on the full optimisation
run." Two model corrections had just landed and neither had been run through a
full rebuild: **roadmap A1** (`xbonus90`, bonus points — previously entirely
absent from the model) and a fix for `build_squad.py` never applying the
`contaminated`-prior exclusion the live screens use.

**Method.** `optimise_squad.py` (exact ILP, no `--transfers` = rebuild/wildcard
mode), `--fixtures --intel`. Fixture window still correctly stamped for GW1
(checked, not stale). 248-player pool (267 minus 19 excluded on the
contaminated fence).

**OUT** (6): Mosquera (ARS, £5.5m) · Van den Berg (BRE, £5.0m) · Palmer (CHE,
£9.5m) · Schade (BRE, £6.0m) · Verbruggen (BHA, £4.5m) · Evanilson (BOU, £6.0m)
— **£36.5m**
**IN** (6): O'Reilly (MCI, £6.5m) · Virgil (LIV, £6.5m) · O.Dango (BRE, £6.5m)
· João Pedro (CHE, £7.5m) · Leno (FUL, £4.5m) · Sadiki (SUN, £5.0m) — **£36.5m**

Cost **0 pts** — unlimited free transfers pre-deadline. Squad value and bank
unchanged (£100.0m / £0.0m). Formation **3-5-2 → 3-4-3**.

**Why each swap, and the trade-offs NOT hidden by the 56.87 headline number**
— full detail in CURRENT STATE above, summarised here:

- **O'Reilly, Virgil in for Mosquera, Van den Berg.** Mosquera's ROLE_INTEL
  boost (minutes opening at Arsenal, Saliba/Timber both out — strengthened
  just this week) is real and still applied, but it lifts him to 4.28 xP_adj,
  short of O'Reilly's 4.67 and Virgil's 4.48 (Liverpool's GW1-4 DEF x of 0.69
  is the best defensive fixture run in the league). A full rebuild can afford
  both upgrades at once by reallocating Palmer's price tag; a single 1-for-1
  swap search (11 Aug) could not, and correctly read as HOLD once intel was
  applied. Both answers are right — different questions.
- **Palmer dropped despite scoring individually well** (xP_adj 5.51, one of
  the best midfielders in the pool) — his £9.5m plus Schade's £6.0m is what
  funds O'Reilly + Virgil + João Pedro together. Stated as a real trade, not
  a free upgrade.
- **João Pedro in for O.Dango's old slot** (O.Dango moves into the XI
  himself, replacing Palmer/Schade's midfield minutes) — his xbonus90 (0.97)
  is 4th-highest in the entire pool. His +7.13 delta is still an open
  question the model doesn't resolve, but bonus gives him a second route to
  points independent of whether his finishing regresses.
- **Verbruggen → Leno is a coin-flip, not a finding** — xP_adj 3.47 v 3.36,
  both 100% starters at the same price; the ILP's bench objective doesn't
  distinguish tied cases like this.
- **Evanilson → Sadiki is a genuine downgrade in bench autosub value**
  (xP_adj 3.91 v 2.79) that the objective cannot see at all — bench value
  (roadmap A0.6) isn't built. Accepted as the cost of funding the rest.

**Captaincy.** Armband moves from B.Fernandes to **Thiago** —
`captaincy_odds` on the new squad's front-runners: Thiago E[pts] 5.15,
P(haul) 15.1%, vs B.Fernandes 5.05, 9.9%. B.Fernandes to vice.

**Actioned live on the FPL site, confirmed 12 Aug 2026.** All 6 transfers
submitted via Claude-in-Chrome browser automation (0 pts cost — unlimited free
transfers pre-deadline), formation set to 3-4-3, captain=Thiago and
vice=B.Fernandes confirmed by a zoomed screenshot of the armbands (per the
standing practice below of not trusting FPL's post-transfer captain default).
Final state on site: 15/15 players, £0.0m bank. Dashboard republished same
session — see commit for the exact hash.

### Tue 11 Aug 2026 — GW1 — Botman → Van den Berg (1 transfer, 0 pts)

**Trigger.** Sylvan asked which defence looked stronger this season, Brentford
or Newcastle, then whether Van den Berg would be a better pick than Botman
given that research, then actioned it — pre-deadline transfers are still free.

**Research.** 2025/26: both sides kept exactly **8 clean sheets**; Brentford
conceded fewer actual goals (1.36/match vs Newcastle's 14-game clean-sheet
drought through the back half of last season) and finished 8th vs Newcastle
lower. Summer continuity favours Brentford too — Pinnock signed a new
contract rather than leaving, Schuster (£12m CB) added as reinforcement, no
defensive departures found. Newcastle lost Trippier, Krafth, Targett and,
more relevantly, **Guimarães** (defensive-midfield shield) to Arsenal, adding
Thiaw as the one clear reinforcement — more personnel change to absorb.

**Model comparison, same £5.0m price:** xGC/90 is within noise of each other
(Botman 1.353, Van den Berg 1.356 — matches the team-level finding almost
exactly). The gap is starts: Botman 75%, Van den Berg 81%, worth **+0.19
xP/GW** (3.19 vs 3.00). Van den Berg also carries none of Botman's logged
fitness-fragility flag (ROLE_INTEL.md entry 6 — ACL surgery 2023/24, two
facial-fracture incidents in the last 18 months).

**Trade-off, stated rather than hidden.** Botman clears the 10+ CBIT
threshold (archetype `BOTH` — both routes to points); Van den Berg sits just
under it (8.9 CBIT/90, archetype `cleansheet` — reliant on clean sheets only,
no DC floor). This transfer trades the rarer two-routes profile for higher
reliability at an identical defensive quality — a real trade, not a free
upgrade, though the model reads it as net positive.

**Squad-level effect (from the dashboard's Alternative 2 panel, fixture-adjusted):
+0.12 xP/GW** — inside the project's own noise floor (~4 pts/season). Actioned
anyway because the transfer is free and the qualitative case (fitness risk,
squad continuity) isn't fully priced into the model.

**OUT** (1): Botman (NEW, £5.0m) **IN** (1): Van den Berg (BRE, £5.0m)
Bank unchanged £0.0m. Squad value unchanged £100.0m. Formation unchanged, 3-5-2.
Club counts: BRE now at the 3-per-club cap (Schade, Thiago, Van den Berg).

**Actioned live** on fantasy.premierleague.com (entry 1041614), confirmed by
Sylvan 11 Aug 2026. `squad.json` and this log updated same session.

### Mon 10 Aug 2026 — GW1 — O'Reilly/Virgil/O.Dango → Mosquera/Botman/Palmer (3 transfers, 0 pts)

**Trigger.** Sylvan: "please implement my optimal squad as transfers are
currently free." Ran `optimise_squad.py`'s transfer optimiser with
`free_transfers` set equal to the transfer count each time (correcting an
earlier answer that had wrongly priced a -4 hit pre-deadline — **transfers are
unlimited and free before the GW1 deadline**, so there is no hit to weigh).

**Method.** Compared WITH and WITHOUT the ROLE_INTEL.md `adjustments` fence
(`intel_adjust.py`, capped 0.5x-1.5x multipliers / uncapped stp overrides).
Both converge on the same 4-transfer ceiling (+0.55 xP/90), but the *cheapest
path* there differs — intel prefers Mosquera (minutes opening at Arsenal on
Saliba/Timber injuries) over Muñoz at 2+ transfers.

**Welbeck excluded.** The 4-transfer version would have added Welbeck (CHE),
but he's on ROLE_INTEL.md's `contaminated` list (BHA→CHE — his 2025/26 record
is a Brighton season, not a Chelsea one) and `build_squad.py` does not correct
for it. Flagged to Sylvan before acting; he chose the 3-transfer version
instead (O'Reilly, O.Dango, Virgil → Botman, Mosquera, Palmer), which gets
+0.49 xP/90 — nearly identical to the 4-transfer total — without relying on
the questionable number. **This is a real gap**: build_squad.py's `load()`
never applies the `contaminated` fence correction that fpl_research_mcp.py's
`_baseline()` does; worth closing before it costs a real transfer next time.

**OUT** (3): O'Reilly (MCI, £6.5m) · Virgil (LIV, £6.5m) · O.Dango (BRE, £6.5m)
**IN** (3): Botman (NEW, £5.0m) · Mosquera (ARS, £5.5m) · Palmer (CHE, £9.5m)
Bank £0.5m → £0.0m. Squad value £99.5m → £100.0m. Formation unchanged, 3-5-2.
Captain (B.Fernandes) and vice (Thiago) unchanged.

**Actioned live** via Claude in Chrome on fantasy.premierleague.com (entry
1041614) after confirming the 15/15 squad and £0.0m bank matched the computed
plan exactly. Verified post-submit on Pick Team: squad value £100.0m, bank
£0.0m, XI/bench match. `squad.json` and this log updated same session.

### Sun 9 Aug 2026 — GW1 — Enzo → Sarr (1 transfer, 0 pts)

**Trigger.** The Gate 2 methodology change (starts% now over the last 16 GWs
of 2025/26, not the full season — see CURRENT STATE and
`SELECTION_FRAMEWORK.md`). Sarr's season-total starts (63%) failed the old
75% gate; his last-16 figure (75% exactly) does not, and his flat score
(4.78 xP/90) already beat Enzo's (4.63) under either basis. `optimise_squad.py
--fixtures --transfers 1` returned **+0.42 xP/90, free** — well above the
~0.10 noise floor.

**OUT** Enzo (CHE, £7.0m) · **IN** Sarr (CRY, £6.5m). Squad value
£100.0m → £99.5m, **bank £0.0m → £0.5m.**

**Sylvan's reasoning for actioning, beyond the raw gain:** the swap drops CHE
from the 3-per-club cap to 2 (Lacroix, João Pedro), freeing a slot and £0.5m
toward **Palmer** — checked immediately after and found to be gated on price,
not on starts reliability (88% last-16, 5.11 xP/90, the best midfielder score
in the pool). Logged on WATCHLIST as a live budget question, not deferred as
a conditional one.

**Also fixed while syncing:** `fixture_adjust.py`'s own squad constant (`SQ`)
had been stale since the O'Reilly→Virgil swap two changes ago — still listed
O'Reilly instead of Virgil, and nobody had caught it because `--squad` mode
hadn't been run since. Now three files carry the squad (`TEAM_CHANGE_LOG.md`,
`optimise_squad.py`, `build_dashboard.py`) plus this one — **added to the
Step 4 sync checklist in the weekly-brief skill.**

**Captain reverted to João Pedro on confirm** — fourth occasion. Reset to
Thiago and **verified by zooming the armband.**

### Sun 9 Aug 2026 — GW1 — O'Reilly → Virgil (1 transfer, 0 pts)

Driven by `optimise_squad.py --fixtures`: Liverpool have the league's best
defensive run over GW1–4 (**DEF x 0.69** vs Man City's 1.14), and Virgil
starts 100% against O'Reilly's 76%. Squad xP_adj **49.93 → 50.02**. FPL
slotted him straight into the XI this time — no auto-benching.

**Captain reverted to João Pedro on confirm** — third occasion. Reset to
Thiago and **verified by zooming the armband** rather than a flat screenshot.

### Sun 9 Aug 2026, 01:2x BST — GW1 — Berge → Schade (1 transfer, 0 pts)

**Trigger.** Sylvan rejected the hand-picked scoring weights: *"those weights are
given by FPL and are not my choice or variables that can be optimized."* Correct —
and the `×8` on defender xGI was not even an FPL number. Rebuilt selection on
**expected points from FPL's scoring table**; this was the only change with a
clear points case.

**OUT** Berge (FUL, £5.0m, bench) · **IN** Schade (BRE, £6.0m) — bank £1.0m → £0.0m.

**Why.** Schade **xP 4.55** vs Tavernier **4.31**, so he starts and Tavernier drops
to the bench. 32 starts (84%), 8 goals, delta −1.13, £6.0m, 2.1% owned. Berge was
bench fodder at 0.09 xGI/90.

**Also fixed:** FPL again auto-benched Gabriel and O'Reilly after the transfer,
and the captaincy had reverted to João Pedro. Both corrected; Thiago restored
and verified by zooming the armband.

### Sun 9 Aug 2026, 00:45 BST — GW1 — FULL SQUAD REBUILD (9 transfers, 0 pts)

**Trigger.** Sylvan: *"I am not happy with all these inherited players. We should
start the season looking at players with the best stats in terms of starts, then
core metrics for their position/archetype."*

**OUT** (9): Virgil £6.5m, Guéhi £6.0m, Ballard £5.0m, van Ewijk £4.0m,
Diop £4.0m, Wirtz £7.5m, Hughes £4.5m, Isak £9.0m, Mateta £6.5m — **£53.0m**
**IN** (9): Gabriel £8.0m, O'Reilly £6.5m, Lacroix £6.0m, Shaw £4.5m,
Kayode £4.5m, Tavernier £6.0m, Berge £5.0m, João Pedro £7.5m,
Calvert-Lewin £6.0m — **£54.0m**

**Cost 0 pts** — unlimited free transfers pre-deadline.

**Method.** Gates applied in order per `SELECTION_FRAMEWORK.md`: 900+ minute
sample → **≥75% starts** → available now → position core metric → £100.0m /
2-5-5-3 / max 3 per club. **Zero overrides used.**

**What the availability gate alone decided:**
- **Isak out** — 21% starts. He was *captain*, with only 694 prior minutes,
  so his baseline fell back to `pos+price` — the player the model knew least
  about was wearing the armband.
- **Mateta out** — 66% starts, reversing a transfer made 21 hours earlier.
- **Cherki never entered** — 50% starts, despite the best xGI/90 in his price band.
- **Danso permanently rejected** — 45% starts, despite the best CBIT/90 in
  the game. Exactly the trap the gate exists to catch.

**Captaincy: Isak → Thiago**, from `captaincy_odds`. FPL auto-assigned João
Pedro on removal of Isak; Thiago beat him on all four measures.
**B.Fernandes retained as vice.**

**Also corrected:** FPL auto-arranged the XI wrongly after the transfers,
benching Gabriel and O'Reilly and starting Berge. Fixed with three substitutions.

**Risks accepted.** Only four players survive from 48 hours earlier (Raya,
B.Fernandes, Mbeumo, Enzo). Squad now exposed to CHE and MUN, both at the
3-player cap. **João Pedro's +7.1 delta was knowingly retained** because his
rate survives the penalty — review GW4.

**Predictions logged** to `fpl_calibration_log.jsonl` for GW1 (5 players),
before the deadline, so the week is scoreable.

---

### Pre-rebuild churn (7–8 Aug 2026) — superseded, kept as a terse record

Everything below was overwritten by the 9 Aug full rebuild — different
squad, different scoring model (xGI-delta rather than FPL's own scoring
table). Kept only so the audit trail isn't broken; the reasoning behind each
no longer applies to the current squad.

- **Fri 7 Aug, 15:40** — Vice-captain Raya → B.Fernandes (a GK vice is a dead slot).
- **Fri 7 Aug, 15:50** — Bench order: Hughes moved ahead of van Ewijk/Diop.
- **Fri 7 Aug, 16:05** — Szoboszlai → Rice, on a fixture/concentration
  rationale later found to be weak (FDR was measuring GW1 only).
- **Fri 7 Aug, 18:10** — Rogers → Mbeumo, Semenyo → Wirtz, on xGI-delta screening.
- **Fri 7 Aug, 18:55** — Methodology: xGI promoted to primary screen, delta
  demoted to a discount signal. Superseded 9 Aug — delta plays no part in
  the current xP model at all.
- **Fri 7 Aug, 19:30** — Screen fix: DC axis switched from a median split to
  the actual CBIRT/CBIT threshold.
- **Fri 7 Aug, 20:10** — Rice → Enzo, on the corrected threshold screen.
- **Sat 8 Aug, 01:30** — Fixture review: xG-derived ATT x/DEF x replaced FDR
  (FDR was later removed from the server entirely).
- **Sat 8 Aug, 11:30** — N.Williams → Ballard, on the DC-threshold floor.

Both Wirtz and Ballard were subsequently transferred out in the 9 Aug
rebuild; Mbeumo, Enzo and B.Fernandes-as-vice survive it, but on the
rebuild's own gates rather than the reasoning above.

---

## ACCOUNT CHANGES (non-team)

- **Fri 7 Aug 2026, ~17:00 BST** — manager display name changed
  "Joe de Mama" → "aSyd Reigns" via myPremierLeague settings. To clear a forced
  onboarding gate, **Arsenal was followed** on the myPL account (reversible:
  Settings → Interests) and a **pre-ticked EA Sports marketing consent was
  switched off**. FPL `favourite_team` was unaffected and remains null.
