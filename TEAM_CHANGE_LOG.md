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

## CURRENT STATE — as at Sun 9 Aug 2026, 22:40 BST (GW1 pre-deadline)

**Deadline:** Fri 21 Aug 2026, 18:30 BST · **Formation:** 3-5-2
**Last change:** **REBUILT 9 Aug** under roadmap A4 — 5 transfers, 0 pts (all free pre-season)
**Squad value** £99.5m · **Bank** £0.5m · **Captain** B.Fernandes · **Vice** Thiago

**Why the rebuild.** `p_threshold` converted an average CBIT/CBIRT into expected
DC points through a four-band step function on the season mean. Measured against
2025/26 per-match counts it was wrong three ways — the 0.80–1.00× band assumed
0.20 against an actual **0.41**, the 1.30× band was **unreachable**, and everyone
above the line scored an identical 0.55 while real hit rates ran **52%–70%**.
Roadmap **A4** replaced it with each player's observed per-match hit rate.
Scored under the corrected model, rebuilding is worth **+1.17 pts/GW (~44
pts/season)** over holding.

| Pos | Player | Club | Price | st% | DC hit | Selected on |
|---|---|---|---|---|---|---|
| GK | Raya | ARS | £6.0m | 94% | — | 19 CS, best xGC (0.74) |
| DEF | Gabriel | ARS | £8.0m | 94% | 37% | xGC 0.72, 18 CS, bps/90 23.7 |
| DEF | O'Reilly | MCI | £6.5m | 81% | 4% | **5 goals, 4 assists, 14 CS** — returns, not a defensive floor |
| DEF | Virgil | LIV | £6.5m | **100%** | 42% | best DEF x 0.69 in GW1–4 |
| MID | B.Fernandes | MUN | £12.0m | **100%** | 15% | xGI/90 0.68, highest in game · **CAPTAIN** |
| MID | Mbeumo | MUN | £8.0m | 88% | 0% | xGI/90 0.58, delta −3.0 |
| MID | Sarr | CRY | £6.5m | 75% | 0% | flat xP 4.78, delta −1.1 |
| MID | O.Dango | BRE | £6.5m | 81% | 8% | 7 goals, 8 assists at £6.5m |
| MID | Schade | BRE | £6.0m | 75% | 0% | flat xP 4.55, delta −1.1 |
| FWD | Thiago | BRE | £8.0m | **100%** | 3% | 22 goals, best availability · **VICE** |
| FWD | Calvert-Lewin | LEE | £6.0m | 94% | 0% | 14 goals, delta −0.6 |
| BEN | Verbruggen | BHA | £4.5m | **100%** | — | GK cover — a **first-choice** keeper |
| BEN | Evanilson | BOU | £6.0m | 94% | 0% | bench 1 · the autosub that matters |
| BEN | Justin | LEE | £4.5m | **100%** | 20% | bench 2 |
| BEN | Shaw | MUN | £4.5m | **100%** | 14% | bench 3 |

**Club counts:** MUN 3 and BRE 3 — **both at the cap.**

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

**Captaincy is provisional.** B.Fernandes has the highest xP (5.27) at 100%
starts, but **captaincy is free until the deadline** — confirm with
`captaincy_odds` on team news, not on this table.

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
Two open items:

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
