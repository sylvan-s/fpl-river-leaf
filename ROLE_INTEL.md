# Role Intelligence — the forward-looking overlay

**Why this file exists.** Every screen in `fpl_research_mcp.py` is **backward-looking**.
xGI, CBIRT, CBIT and xGC are all computed from what already happened. They cannot
price a *change* — a new penalty taker, a tactical shift, a starting berth opening
through injury. That is a structural blind spot, not a bug, and it is precisely
where community research adds value the data cannot.

**How to use it.** Screens establish the baseline. This file adjusts it. Where the
two conflict, see the reconciliation rules at the bottom — the conflict must be
stated in the brief, never silently resolved.

**Discipline.** Every entry needs a **date**, a **source**, and a **falsifiable
check** — something observable in the opening gameweeks that confirms or kills it.
Entries without a check become folklore. Review and prune weekly.

---

## Active intel — logged Fri 7 Aug 2026

Source: Sylvan's research summary of the top-5 community/analytical creators,
7 Aug 2026. Pre-season theses, none yet observable in match data.

### 1. Szoboszlai (LIV, £7.0m, MID) — primary penalty + direct FK taker

**Thesis:** steps up as Liverpool's primary penalty and direct free-kick taker
following changes in their attacking structure.

**Why this matters more than any other entry:** it directly contradicts my screen,
which labels him **`limited`** (xGI 11.59, xGI/90 0.32, CBIRT/90 9.4 — clears
nothing). A penalty is worth roughly **0.79 xG**. A Liverpool season of 5–8
penalties adds **~4–6 xG**, taking his xGI to roughly **16–18** and his xGI/90 to
~0.45–0.50. That moves him from `limited` to a top-tier `attacker`.

**Corroboration:** Salah has left the Premier League, so the duty is genuinely
vacant. Independently established earlier, not taken from the creator claim.

**Upgraded 12 Aug 2026 — web-confirmed, not just community consensus.**
Multiple independent sources (ESPN, OneFootball, TikTok clip of the actual
penalty) now report Szoboszlai has taken and scored a penalty for Liverpool
and holds first-choice penalties, corners **and** direct free kicks — one of
only two Premier League players (alongside Bruno Fernandes) holding all three
duties at his club. One nuance not previously logged: Szoboszlai has said he
intends to hand the penalty duty back to Salah once Salah returns to the
matchday squad — so this is not necessarily a season-long lock, only a
season-opening one. Still **not** reflected in the FPL API's own
`penalties_order` field pre-season, hence the `?` suffix stays.

**Impact on decisions already taken:** he was **sold on 7 Aug**. This is the fifth
and most serious mark against that transfer — and unlike the other four it is not
a measurement error but a blind spot: *the screens cannot price a role change.*

**Practical constraint:** buying him back is **blocked by the 3-per-club cap**
(Virgil, Wirtz, Isak). The only route is **Wirtz ↔ Szoboszlai**, both LIV mids.

**Falsifiable check:** who takes Liverpool's first penalty and first direct free
kick? Also watch `penalties_order` in the API once populated.

**Contested, 20 Aug 2026 — daily sweep, pending Friday review.** Fantasy
Football Scout's 20 Aug Liverpool set-piece guide (corroborated by
thisisanfield.com and Il Margine) has the club/FPL-listed penalty order as
Isak first, Szoboszlai second, Gakpo third — not the sole-primary duty this
entry has assumed since 12 Aug. Szoboszlai is still the "evidence-led" taker
(took one on the pitch alongside Gakpo in pre-season; 90% career conversion
vs Isak's 76%), but no same-pitch competitive test has settled the order.
Worth revisiting the `xg90 mult 1.35` in the adjustments fence below once
GW1 team news shows who actually takes the first live penalty — a suggested
1.15 is logged in the sweep log (`Szoboszlai-LIV-xg90-20260820-1`) pending
that review, not applied here.?

### 2. Elliott Anderson (MCI, £6.5m, MID) — budget enabler, elevated creative role

**Thesis:** absorbs heavy minutes with an elevated creative role, out-projecting
several £8.0m midfielders.

**Screen agrees, and adds to it.** Anderson is one of only **4 of 47** midfielders
in the £6m+ band who actually clears the 12+ CBIRT threshold (**13.9/90**), with
180 points. My screen already rates his *floor* as genuine. The creator thesis
adds a *ceiling*. Floor + ceiling = **box-to-box**, the most valuable archetype.

**This is the strongest convergence in the set** — independent quantitative and
qualitative signals pointing the same way.

**Falsifiable check:** does his xGI/90 rise above ~0.30 in the opening weeks?

**Complication, 20 Aug 2026 — daily sweep, pending Friday review.** Man
City have a new manager: Enzo Maresca replaced Pep Guardiola over the
summer (see the new manager-change entry below), and Rodri has left for
Barcelona. In a 15 Aug press conference (mancity.com), Maresca said of
Anderson: "I see him as a holding midfielder, but he can also be attacking
midfielder... I think he doesn't need a physical player next to him" —
explicitly flagging him for a possible No.6 role, not fixing him in the
advanced creative one this entry's `xgi90 mult 1.15` assumes. Other
reporting frames him as a long-term Rodri replacement at the base of
midfield. Doesn't resolve which role wins out — logged as a flag
(`Anderson-MCI-xgi90-20260820-1`) for GW1-4 positional data to settle.?

### 3. Mosquera (ARS, £5.5m, DEF) — minutes opening through injury

**Thesis:** regular early-season minutes in the league's best defence while
starters recover.

**Corroborated by my own injury data**, not just the creator claim: `injury_report`
on 7 Aug returned **Saliba INJURED (back, no return date)** and **J.Timber INJURED
(groin, expected 21 Aug)**. The opportunity is real and verifiable.

**Screen view:** Arsenal defenders skew unusually busy for a dominant side —
Gabriel, Mosquera and Hincapie all landed `BOTH`. Mosquera at 8.7 CBIT/90 and
0.83 xGC/90 is a legitimate cheap route into the best defence.

**Falsifiable check:** does he start GW1 v Coventry? Timber's return date of
21 Aug is the deadline day itself — this could evaporate immediately.

**Strengthened 12 Aug 2026 — web-confirmed, and the window is longer than
previously recorded.** Arteta (via Yahoo/Sports Mole/CaughtOffside, all
reporting the same press conference) says Timber is "still a matter of weeks
away" and will miss the Community Shield plus the first three PL fixtures —
Cardiff, Villa and "most likely" Chelsea — not back by 21 Aug as the earlier
entry assumed. Saliba separately is "in rest mode... two weeks" for an
aggravated back injury with no firm return date. Both confirm the opportunity
is real and now looks **longer than GW1-3**, not shorter — the `stp` window in
the adjustments fence below may be under-crediting Mosquera's minutes rather
than over-crediting them. Revisit the GW window (currently set 1-3) once GW1
team news confirms he starts.

**Still open, 17 Aug 2026 — live `injury_report` check.** Both Timber and
Saliba remain flagged INJURED with 0% odds and "Unknown return date" as of
this check, two days before the deadline. Nothing has shortened the window;
if anything, "unknown" is less specific than the "weeks away" language from
12 Aug. Doesn't change the live squad decision — O'Reilly (4.67 xP_adj) and
Virgil (4.48) still beat Mosquera's intel-boosted 4.28 on the full-budget
rebuild — but the thesis itself is intact and worth another look if a swap is
ever considered.

**Window looks longer, not shorter, 20 Aug 2026 — daily sweep, pending
Friday review.** Fresh Arteta press-conference coverage (Yahoo/Sports Mole)
now puts Timber's return "in September," not by GW3 as the current
`stp` window (GWs 1-3) assumes, and Saliba's return is being pencilled for
"winter 2026" (a 2-3 month estimate). Both point to the current
`Mosquera | ARS | stp | set | 0.85 | 1-3` line in the adjustments fence
under-crediting the window's length rather than over-crediting it — logged
as `Saliba-ARS-stp-20260820-1` for the Friday review to size a wider
window, not changed here. `injury_report` itself still shows both simply
"INJURED, unknown return date," so this is press reporting ahead of the
API, same caveat as always.?

### 4. Ndiaye (EVE, £6.0m, MID) — penalties + shot volume

**Thesis:** locked-in penalty duty plus underlying volume beats his £6.0m price.

**Screen says `limited`** (xGI 11.09, xGI/90 0.36, CBIRT/90 9.2) — but with a
**−2.09 delta**, so already underperforming his chances. Penalty duty would lift
the xGI materially and the negative delta says the output is due rather than lucky.

**Falsifiable check:** confirm he takes Everton's first penalty.

**Upgraded 12 Aug 2026 — web-confirmed.** Independent sources (RotoWire, Il
Margine, Fantasy Football Scout's set-piece list) converge on Ndiaye as
Everton's primary penalty taker, ahead of Garner. Same caveat as Szoboszlai:
not yet in the FPL API's own field pre-season, `?` suffix stays.

**Reconfirmed 16 Aug 2026 — on-pitch evidence, not just reporting.** Ndiaye
has now taken AND SCORED Everton's last two pre-season penalties (most
recently in the 1-1 draw with Lille, 15 Aug), ahead of Thierno Barry, who had
taken an earlier one against Stuttgart. This is behavioural confirmation, not
just a source claim — the strongest form of evidence this file distinguishes.
No change to the `mult 1.25` in the adjustments fence; this reconfirms the
existing confidence rather than raising it further. Source: Fantasy Football
Scout, "FPL pre-season: Villa injuries, another Ndiaye pen + no Norgaard,"
16 Aug 2026.

### 5. João Pedro (CHE, £7.5m, FWD) — central catalyst — **ALREADY OWNED**

**Thesis:** operates as the focal point in Chelsea's setup.

**Screen is more cautious:** xGI 16.87 but a **+7.13 delta**, one of the largest
overperformances in the game — 24 G+A against 16.87 xGI. Both can be true: an
elite role *and* an unsustainable conversion rate. The role protects the xGI; it
does not protect the finishing.

**Falsifiable check:** does the delta compress toward zero over the opening weeks
as expected? If it stays high, he may be a genuine finisher rather than lucky.

**Observed 16 Aug 2026 — pre-season scoring streak continues, delta question
still unresolved.** Brace against Real Sociedad (Chelsea's final pre-season
friendly, 15 Aug) takes him to 7 goals in 5 pre-season appearances, 8 in his
last 7 for club and country. Played the full 90 as Chelsea's only recognised
striker with Delap, Jackson and Welbeck all missing — he is confirmed as
Alonso's first-choice #9 for GW1. This is a role/minutes confirmation, not
new evidence on the finishing-vs-luck question the falsifiable check above is
actually asking — pre-season friendlies against weaker opposition don't
resolve whether a +7.13 delta regresses. Logged for completeness; the check
above still stands and can only be answered by competitive matches. Source:
Fantasy Football Scout, "FPL pre-season: Pedro again, Rogers debut, Munoz
returns," 16 Aug 2026.

### 6. Botman (NEW, £5.0m, DEF) — recurring fitness fragility — **NOT CURRENTLY OWNED (tag corrected 18 Aug)**

**Thesis (risk flag, not a buy/sell thesis):** repeated fitness interruptions
across the last two seasons are a plausible, non-hype explanation for his low
ownership (0.4%) at this price — separate from any pecking-order or role
concern. Logged 10 Aug 2026, web-confirmed.

**History:** ACL surgery in 2023/24 (~9 months out). Facial fracture surgery
in **March 2026** after a collision with Sunderland's Brian Brobbey — missed
part of the run-in and played the rest of last season in a protective mask.
Another facial knock in **pre-season training, late July 2026**, ruling him
out of a friendly (Eddie Howe sounded unconcerned about him being ready for
the season).

**Why this matters for the model.** It's the likely reason his season-long
start rate (55%) sat well below his last-16 rate (75%) — he was recovering
from the March facial fracture for part of last season's run-in, not out of
favour. The gap the last-16 methodology change was designed to catch has a
real, findable cause here, not just noise.

**Re-verified live, 18 Aug 2026.** `injury_report` now shows Botman as
"available" with no active flag — a good sign he's cleared the late-July
facial knock. Note the tag correction above: the 12 Aug full-rebuild
(`TEAM_CHANGE_LOG.md`) superseded the 11 Aug Botman→Van den Berg swap and he
is not part of the current 15 — this entry was mislabelled "ALREADY OWNED"
since the rebuild and should have been corrected sooner. Left in the file as
a live watchlist item, not a squad concern.

**Falsifiable check:** does he complete pre-season and start GW1 without a new
knock? A clean run through August would meaningfully undercut this flag.

### 7. Rice (ARS, £7.5m, MID) — Guimarães signing shares his workload — **NOT OWNED**

**Thesis:** Sylvan heard on a podcast that Arsenal brought in support for Rice
specifically to let his role be rotated more. Checked 11 Aug 2026, web-confirmed
from multiple independent sources.

**Corroboration — direction, strongly supported.** Arsenal completed the
signing of Bruno Guimarães from Newcastle (~£75m) in August 2026. Coverage
converges independently on the same read: Arsenal's own **FPL Focus** column
is titled *"New heights for Rice, managing rotation"*; ReadArsenal reports
Guimarães "could give Mikel Arteta something he badly needed last season: the
freedom to manage Declan Rice's workload without weakening his midfield,"
after Rice "carried a huge workload last season"; multiple outlets describe a
likely shift to a box midfield (Zubimendi anchoring, Rice and Guimarães as
the two 8s) across a squad now genuinely competing for 3 midfield slots among
6 senior options (Rice, Zubimendi, Odegaard, Merino, Eze, Guimarães). This is
not one podcast's read — it is the consistent framing across Arsenal's own
site and independent transfer press.

**Corroboration — magnitude, NOT sourced.** No source puts a number on it.
Rice was essentially nailed last season (35/38 starts, 92%) even carrying the
extra load Guimarães is meant to relieve. **The 25% reduction applied below is
an estimate supplied on instruction, not a reported figure** — 0.92 × 0.75 ≈
0.69, so `stp` is set to **0.69**, not derived from any rotation plan Arteta
has actually stated.

**Why it matters:** at 0.69 this would drop Rice below the 75% starts gate,
i.e. from an auto-include to a live risk if he were ever priced in. He is not
currently owned, so this has no effect on the live squad — logged as intel
for if/when he's evaluated.

**Falsifiable check:** does Rice's start share over GW1-6 come in materially
below ~90%? If he's still starting nearly every match once the season begins,
the magnitude here was wrong even if the underlying signing/intent was real.
Review at GW6, not GW8 — a shorter window than usual given the magnitude is
unsourced guesswork rather than a specific injury/suspension window.

**Weak early signal, 16 Aug 2026 — noted, not acted on.** Rice was an unused
substitute for Arsenal's Community Shield win over Man City (Cardiff,
16 Aug). Directionally consistent with the rotation thesis, but one
non-competitive fixture is nowhere near the GW1-6 competitive-minutes window
the falsifiable check above requires, and a Community Shield squad often
rests players for reasons unrelated to a season-long plan. Not owned, so no
action regardless — logged so the eventual GW6 review has the full picture
rather than starting from zero.

### 8. Bruno Fernandes (MUN, £12.0m, MID) — pre-season penalty misses — **ALREADY OWNED, VICE-CAPTAIN**

**Thesis (risk flag, not a buy/sell thesis):** two missed penalties in
pre-season raise a real, if unresolved, question about how much of his xP is
riding on retained set-piece duty. Logged 16 Aug 2026, web-confirmed.

**What happened.** Fernandes missed a penalty in United's final pre-season
friendly (2-4 defeat to AC Milan, 15 Aug) — the second miss "in a few days"
per Fantasy Football Scout, following an earlier one in the same week. He
also missed twice from the spot last season (autumn) and kept the duty both
times regardless.

**Why this doesn't (yet) change anything.** The screen's `xg90`/`xa90` for
Fernandes is derived from his actual accumulated match record, which already
includes his real conversion rate including past penalty misses — this isn't
a case of the model being blind to something, the way it is with a genuine
role change. Fantasy Football Scout's own read is there's "nothing yet to
suggest" he loses the duty over it, consistent with last season's pattern.
No `adjustments` fence entry warranted on current evidence — a multiplier
would need a specific reason to expect his rate to change, not just two
misses in meaningless friendlies.

**Why it's logged anyway.** He carries the armband (vice, since the 12 Aug
swap) and a large share of his xbonus90/xGI comes from set-piece
involvement (penalties, corners, free-kicks). If United's press conference
ever floats a change of taker, this is the thread to pull.

**Falsifiable check:** does he take and convert United's first competitive
penalty of the season? A miss there, or a hint from Amorim/Carrick about a
change of taker, would warrant a `stp`-adjacent look at his set-piece share —
a straight miss with no taker change does not.

### 9. Maresca (MCI, £0.0m, MGR) — new Man City manager replaces Guardiola — **structural context, not a single-player thesis**

**Logged 20 Aug 2026, daily sweep, pending Friday review.** Pep Guardiola
left City after 10 years; Enzo Maresca (ex-Chelsea) has been permanent
first-team manager since being announced 29 June 2026, confirmed on City's
own site and widely in the press. Rodri has also departed to Barcelona.
Neither change has been logged anywhere in this file before today, despite
underlying both the Anderson (entry 2) and O'Reilly (entry 10) items below.
Guardiola-era pecking order and role assumptions for City players are not a
safe prior for 2026/27 — treat any City-specific stp/role read from before
summer 2026 with that in mind.

**Falsifiable check:** does Maresca's confirmed GW1 XI/setup materially
differ from Guardiola's final-season patterns (formation, who plays the
Rodri role, fullback usage)? Source: `Maresca-MCI-managerchange-20260820-1`.?

### 10. O'Reilly (MCI, £6.5m, DEF) — right-back competition risk — **ALREADY OWNED**

**Logged 20 Aug 2026, daily sweep, pending Friday review.** O'Reilly is in
the live XI on an 81%-starts assumption (see squad.json). Under the new
Maresca regime (entry 9), multiple predicted-lineup reports for City's next
fixture have Matheus Nunes as first-choice right-back and Ait-Nouri at left,
with O'Reilly used in midfield or left out of the back four rather than
nailed at RB. Corroborating: Fantasy Football Scout (18 Aug) notes his
Community Shield start was capped under an hour "as planned," consistent
with managed minutes rather than a fixed berth. Sourcing here is scattered
predicted-XI pieces, not a confirmed team sheet or press-conference quote —
a flag to watch, not settled. Evidence is mixed even within the day: a
fresher predicted XI (20 Aug, naming City's actual GW1 opponent Bournemouth)
had O'Reilly starting alongside Gvardiol, contradicting the 18 Aug
Nunes/Ait-Nouri reports above — not enough to act on either way.

**Key confirmation point, 21 Aug 2026.** Maresca's pre-Bournemouth press
conference is Friday 21 Aug from 13:30 UK — a few hours ahead of the 18:30
BST GW1 deadline, and after that morning's `fpl-friday-intel-review` (07:30
UTC) — the first point real team-news signal, rather than scattered
predicted XIs, is likely to surface. Discussed with Sylvan 20 Aug: holding
off any swap until then given the free pre-season transfer window makes
waiting close to costless. A supplementary intel sweep is scheduled for
14:30 UK that day, after the presser, specifically to catch its fallout
ahead of a 15:00 review.

**Falsifiable check:** does O'Reilly start at right-back (or at all) in
City's actual GW1 fixture? Source: `OReilly-MCI-stp-20260820-1`.?

---

## Machine-readable set-piece overrides

`fpl_research_mcp.py` parses the block below and merges it into the `SP` column
of both screens. **Provenance is preserved:** duty confirmed by the FPL API shows
plain (`P1`), duty taken from this file shows with a **`?`** suffix (`P1?`) —
expected, not confirmed. API data always wins where both exist.

Format: `player | codes | date added | source`.
Codes: `P`=penalties, `F`=direct free kicks, `C`=corners; number = order.

Delete a line the moment the API confirms or contradicts it — this block exists
only to cover the pre-season gap before FPL populates its own fields.

```setpieces
Szoboszlai | P1 F1 C1 | 2026-08-12 | web-confirmed (ESPN, OneFootball, penalty footage); reverts to Salah on his return; not yet in FPL API
Ndiaye     | P1       | 2026-08-12 | web-confirmed (RotoWire, Il Margine, FF Scout set-piece list); not yet in FPL API
```

## Machine-readable contaminated priors

**Why this is needed.** `_baseline()` disqualifies a personal prior when the club
changed, by comparing the prior record's team against the current one. But the
prior snapshot was taken *after* the January 2026 window, so it records each
player's **current** club — not the club he actually played those minutes for.
The check therefore cannot fire for anyone who moved *before* the snapshot.

**CORRECTED 9 Aug 2026.** This block previously claimed the check "works normally
for transfers from 2026/27 onward." **It does not.** The snapshot was captured
**8 Aug 2026**, by which point the entire 2026/27 summer window was already
reflected in the `team` field. So a July 2026 signing reads as
*new club + old club's minutes*, with **nothing flagging it** — the same defect
as a January mover, over a window that moves far more players. The check only
becomes reliable for transfers made **after 8 Aug 2026**.

`stp` is affected as badly as the rate stats: `last16_starts.json` keys on
`name|CURRENT_team`, so a mover's start rate is last season's club's start rate
wearing this season's badge. **That is the number the 75% gate reads.**

List movers here. Their personal prior is skipped and the D2 ladder falls
through to team × position at the new club.

Format: `player | reason`.


**DERIVED, NOT HAND-MAINTAINED — regenerated 9 Aug 2026.** This block used to
be kept by hand and listed 5 players. `fetch_gw_history.py` compares each
player's **current** club against the club the archive says he actually played
for in 2025/26, and found **19**. The hand-kept list was missing 14, including
**Robertson, Senesi, Tonali and Van Hecke** — four of Tottenham's five arrivals.

Regenerate with `python3 fetch_gw_history.py`; the machine-readable output is
`docs/data/club_changes.json`. **Do not edit the block below by hand.**

The earlier caveat that "absence is not evidence" no longer applies to anyone
the archive covers — 261 of 267 pool players are matched. It still applies to
the 6 unmatched, listed in `docs/data/provenance.json`.

```contaminated
Garnacho      | CHE -> AVL; 2025/26 record is a CHE record
Struijk       | LEE -> BHA; 2025/26 record is a LEE record
Henderson     | BRE -> CHE; 2025/26 record is a BRE record
Lacroix       | CRY -> CHE; 2025/26 record is a CRY record [IN SQUAD]
Rogers        | AVL -> CHE; 2025/26 record is a AVL record
Welbeck       | BHA -> CHE; 2025/26 record is a BHA record
Strand Larsen | WOL -> CRY; 2025/26 record is a WOL record
Anderson      | NFO -> MCI; 2025/26 record is a NFO record
Grealish      | EVE -> MCI; 2025/26 record is a EVE record
Guéhi         | CRY -> MCI; 2025/26 record is a CRY record
Semenyo       | BOU -> MCI; 2025/26 record is a BOU record
Andrey Santos | CHE -> MUN; 2025/26 record is a CHE record
Darlow        | LEE -> MUN; 2025/26 record is a LEE record
Tielemans     | AVL -> MUN; 2025/26 record is a AVL record
Dubravka      | BUR -> TOT; 2025/26 record is a BUR record [IN SQUAD]
Robertson     | LIV -> TOT; 2025/26 record is a LIV record
Senesi        | BOU -> TOT; 2025/26 record is a BOU record
Tonali        | NEW -> TOT; 2025/26 record is a NEW record
Van Hecke     | BHA -> TOT; 2025/26 record is a BHA record
```

### Summer-2026 sweep — done 9 Aug 2026

**Method.** The snapshot cannot reveal a player's previous club, so club change
is undetectable from inside the data. Two things *are* detectable:

1. **Promoted clubs are safe.** HUL, COV and IPS carry 0, 88 and 812 minutes of
   2025/26 PL football across their whole squads. Their players never clear
   gate 1 (900+ mins), so they are absent from the pool rather than contaminated.
2. **Net inbound minutes flag the risk clubs.** A club generates 11 × 90 × 38 =
   **37,620** minutes of its own PL football a season. Where the *current* squad
   holds more 2025/26 minutes than that, the surplus arrived from elsewhere:

   | club | 25/26 mins in current squad | vs baseline |
   |---|---|---|
   | TOT | 48,111 | **+10,491 (~3.1 players)** |
   | CHE | 42,266 | +4,646 (~1.4) |
   | MCI | 41,244 | +3,624 (~1.1) |
   | MUN | 39,913 | +2,293 (~0.7) |

   Every other club is net negative. **This does not name players** — it says
   where to look, and it is worth re-running whenever the snapshot changes.

**Verified against the current squad and live recommendations** (web-confirmed,
not inferred). Clean: Raya, Gabriel, Virgil, B.Fernandes, Mbeumo, Shaw, Sarr,
Schade, Thiago, Kayode, Tavernier, João Pedro, and **Calvert-Lewin** — who
joined Leeds in summer **2025**, so 2025/26 is genuinely a Leeds season.

**Not yet swept: the remaining ~250 pool players.** The four risk clubs above
are where to start. Until that is done, treat any TOT, CHE, MCI or MUN player
surfacing from a screen as unverified.

## Machine-readable internal competition

Players whose **place in the XI is contested**, where the history says one thing
and the current pecking order says another. Distinct from `contaminated`: there
the numbers belong to another club, here they belong to another *role*.

A start rate is the single most load-bearing number in the model — it gates
selection and, under roadmap item A0.5, will weight the objective. A player who
was first choice and is now second is the case the data cannot see at all,
because last season he did start.

Format: `player | status | date | detail`.
Status: `backup` · `contested` · `promoted`.

```competition
Dubravka | backup | 2026-08-09 | First-choice at Burnley (35 apps, 81% starts); reported behind Antonin Kinsky at Spurs. True P(start) near zero, not 81%
```

### Dubravka is a role change, not just a contaminated prior

He was **Burnley's first-choice** keeper in 2025/26 (35 PL appearances, hence
the 81% start rate). At Tottenham he is reported as **backup to Antonin Kinsky**.
His true P(start) is therefore near **zero**, not 81%.

He is the bench GK, so the direct cost is small — `size_bench_value.py` prices
that slot at 0.144 pts/GW, and the true figure is close to nil. But it is worth
knowing that the GK bench slot is currently **dead weight**, and that a keeper
who actually deputises would be worth roughly £4.0m better spent.

**Falsifiable check:** who starts Spurs' GW1 fixture in goal.

## Machine-readable adjustments — narrative intel to model inputs

**Why this exists.** Every entry above states a thesis. None of them, until
10 Aug 2026, changed a single number `build_squad.py` actually scores on — a
penalty-duty claim sat next to the model without ever touching `xg90`. This
fence closes that gap. It is parsed by `intel_adjust.py` and applied to
`build_squad.py` / `optimise_squad.py` / `fixture_adjust.py` **by default,
since 13 Aug 2026** — pass `--no-intel` to see the raw, unadjusted numbers.

*Corrected 13 Aug 2026: this was originally off-by-default, gated behind an
explicit `--intel` flag. The flag was never actually passed by the
`fpl-weekly-brief` skill's documented weekly optimiser command, so every `set
stp` / `mult` entry below was silently inert in the real weekly run — only
live in explicit `--intel`/`--compare-intel` comparisons. This mattered most
for exactly the players this fence is meant to correct: transferred-in or
newly-promoted signings whose pre-season `stp` is a stale 2025/26 number with
no current-season signal at all. Flipped after a review of whether a
start-weighted xP objective (roadmap A0.5) would add value found this gap.*

    python3 build_squad.py                       # squad WITH intel applied (default)
    python3 optimise_squad.py --no-intel          # squad WITHOUT intel, for comparison
    python3 optimise_squad.py --compare-intel     # WITH vs WITHOUT, one run
    python3 intel_adjust.py --report              # per-player xP with vs without

**Two shapes, not one — agreed with Sylvan 10 Aug 2026.**

- `op=mult` on `xg90` / `xa90` / `xgi90` / `cbit90` / `cbirt90` — a bounded
  multiplier, **guardrailed to 0.5x–1.5x**. A thesis is a probability-weighted
  guess, not a measurement, and should never be able to outweigh a season of
  observed data. `xgi90` is a convenience alias for xG **and** xA together,
  scaled by the same factor.
- `op=set` on `stp` **only** — an override, not a multiplier, **not** subject
  to the 0.5x-1.5x cap. Unavailability is closer to binary than continuous:
  "out for four weeks" is P(start) = 0, and a 0.5x floor would leave a
  nailed-on absentee at 37%. Works in both directions — Mosquera's minutes
  opening through injury is `stp` being set UP, not just less down.

Format: `player | team | field | op | value | gws | confidence | date | why`.
`player` and `team` must match the pool exactly (web_name + FPL short code) —
a typo matches nothing, and `build_squad.load()` warns loudly on any entry
that never fires rather than staying silent about it. `gws` is a window like
`1-4`, a single GW, or `ALL`; it is provenance plus a staleness nudge, not an
auto-expiry — still prune by hand per rule 6 below.

The five seeded below translate the theses already logged above. Delete or
re-date a line the moment reality confirms or contradicts the thesis it rests
on — same discipline as the `setpieces` block.

```adjustments
Szoboszlai | LIV | xg90  | mult | 1.35 | 1-8 | high   | 2026-08-12 | Penalty + direct FK + corner duty, web-confirmed 12 Aug (reverts to Salah on his return); see entry 1 above
Ndiaye     | EVE | xg90  | mult | 1.25 | 1-8 | high   | 2026-08-12 | Penalty duty web-confirmed 12 Aug plus -2.09 delta already underperforming his chances; see entry 4 above
Anderson   | MCI | xgi90 | mult | 1.15 | 1-8 | medium | 2026-08-07 | Elevated box-to-box creative role per community read; screen already confirms the CBIRT floor, this prices the ceiling; see entry 2 above
Mosquera   | ARS | stp   | set  | 0.85 | 1-3 | medium | 2026-08-12 | Saliba back-injury "rest mode", Timber "weeks away" - out for Cardiff/Villa/likely Chelsea, later than the 21 Aug date previously logged; minutes opening in the league's best defence; see entry 3 above
Dubravka   | TOT | stp   | set  | 0.05 | ALL | high   | 2026-08-09 | Reported backup to Antonin Kinsky at Spurs; 81% last16 rate is a Burnley-era number wearing a Spurs badge; see the competition fence above
Rice       | ARS | stp   | set  | 0.69 | 1-6 | medium | 2026-08-11 | Guimaraes signed to share his DM/CM workload per Arsenal.com + independent press (rotation intent well corroborated); 25% reduction off his 92% 2025/26 start rate is an UNSOURCED estimate applied on instruction, not a reported figure; see entry 7 above
```

**Also wired into the live weekly tools, not just the offline squad scripts.**
`fpl_research_mcp.py`'s `captaincy_odds` (and the shared `_cap_rows` it feeds
`log_predictions` from) reads this same fence via `intel_adjust.py`'s
`entries_for()` — no second parser, same `gws` window check, same 0.5x-1.5x
cap on `mult`, same uncapped `set` on `stp`. Pass `with_intel=True` (off by
default) to layer it on; any player it touched is tagged in the row.
`log_predictions` never sets it — calibration must score the model, not
model+intel, or a good intel call would get credited as if the model made it.

## Reconciliation rules

1. **Forward-looking intel about a ROLE beats backward-looking stats about
   PRODUCTION** — but only when dated, sourced, and carrying a falsifiable check.
2. **Never silently override a screen.** If intel and screen disagree, the brief
   must state both and name which is driving the call.
3. **Set-piece duty is the highest-value intel type**, because it is a large,
   quantifiable, persistent xGI shift the historic data cannot see. Penalties
   ≈ 0.79 xG each.
4. **Minutes intel is second** — it gates everything else. A great role is worth
   nothing if he does not start.
5. **"Tactical shift" claims without a specific mechanism are the weakest** —
   treat as a tiebreak, not a thesis.
6. **Prune on contact with reality.** Once the season starts, a thesis that has
   not shown up in the data within ~5 gameweeks is dead. Delete it and note why.
7. **Beware circularity.** Creators read the same public stats. Intel that merely
   restates what the screen already shows adds no information — value comes only
   from what the data *cannot* see.
