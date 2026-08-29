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

**RESOLVED, 26 Aug 2026 — daily sweep, GW1 penalty taken.** Szoboszlai, not
Isak, took and scored Liverpool's actual first competitive penalty of the
season — a stoppage-time spot-kick in the 2-2 draw at Newcastle (21 Aug) —
contradicting the 20 Aug FFS-reported Isak-first order above. Resolution
logged against `Szoboszlai-LIV-xg90-20260820-1` as `contradicted`. Not fully
closed, though: post-match coverage still frames the duty as multi-person
rather than sole-nailed, naming Mac Allister (11/12 career) and Gakpo (9/10)
as other options Liverpool's camp regards as "very good" even after
Szoboszlai's successful kick — Szoboszlai's own 18/20 (90%) remains the
strongest record of the three. Logged as `Szoboszlai-LIV-xg90-20260826-1`,
pending Friday review; no change to the existing `mult 1.35` fence entry on
this evidence.?

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

**Fitness footnote, 27 Aug 2026 — daily sweep, pending Friday review.**
Separate from the role question above: Anderson's 63-minute night vs
Bournemouth (GW1, 23 Aug) was cut short by what Maresca described
post-match as severe cramp, not a significant knock, after a collision
with Bournemouth's Alex Scott. Live `injury_report` still shows him
DOUBTFUL at 75%, but multiple outlets (Sports Mole, CityXtra, Goal.com)
report he's expected available for City's GW2 fixture v Crystal Palace
(28 Aug) — where Sarr (own squad, entry 13) is on the opposing side.
Logged as `Anderson-MCI-injury-20260827-1`.?

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

**Real matchday evidence, plus a market signal, 21 Aug 2026 — daily
sweep, pending Friday review.** Mosquera actually started Arsenal's 3-0
Community Shield win over Man City (16 Aug) alongside Gabriel, with Ben
White filling in at right-back rather than Mosquera — a real team sheet,
not just reporting, corroborating the minutes-opening thesis. Separately,
Arteta's 20 Aug presser confirmed Arsenal are "really active in the
market" for Aston Villa's Ezri Konsa specifically because of "the
long-term issue with Willy" — the club's own recruitment behaviour is
independent evidence it expects Saliba's absence to run long, reinforcing
rather than superseding the "window is longer, not shorter" finding
logged yesterday. Logged as `Mosquera-ARS-stp-20260821-1`. Falsifiable
check for GW1 itself: does Mosquera start the actual Coventry fixture
tonight?

**CONFIRMED, 23 Aug 2026 — GW1 team sheet, daily sweep.** Mosquera
started Arsenal's actual GW1 fixture, the 3-0 win over Coventry (21 Aug),
partnering Gabriel at centre-back, with Ben White again covering
right-back for Timber. Saliba remained out. Resolution logged against
`Mosquera-ARS-stp-20260821-1`. Konsa was also introduced to fans
pre-match and, per Arteta, is now in contention for next Monday's Villa
trip — the defensive-cover picture (and Mosquera's minutes runway) stays
live beyond just Saliba/Timber's return dates.

**Accepted, Friday review 28 Aug 2026.** Both `Mosquera-ARS-stp-20260821-1`
(GW1 matchday confirmation) and `Saliba-ARS-stp-20260820-1` (Timber "in
September", Saliba pencilled for winter) accepted. The `stp` fence entry
below is updated: window extended from GWs 1-3 to 1-8, confidence raised
from medium to high given actual matchday evidence rather than predicted
lineups.

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

**CONFIRMED, 26 Aug 2026 — daily sweep, GW1 lineup evidence.** Maresca's
actual GW1 XI vs Bournemouth (23 Aug) does materially differ from
Guardiola-era patterns: Abdukodir Khusanov (not a specialist right-back)
started at RB, O'Reilly was repurposed into central midfield rather than
his usual full-back role, and Elliot Anderson was deployed in the deep
No.6 role vacated by Rodri's departure. Resolution logged against
`Maresca-MCI-managerchange-20260820-1`. Sources: mancity.com, Sports Mole,
Yahoo Sports GW1 lineup coverage.

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
City's actual GW1 fixture? Source: `OReilly-MCI-stp-20260820-1`.

**Still open, 23 Aug 2026 — daily sweep, ahead of kickoff.** City's GW1
fixture vs Bournemouth kicks off 14:00 UK today (23 Aug) and has not yet
been played as of this sweep, so the falsifiable check above remains
unresolved. Freshest available signal: a 21 Aug predicted XI (CityXtra)
has Matheus Nunes at right-back and O'Reilly starting in central
midfield alongside Kovacic in a double pivot — not the back four at all —
while noting Nunes has recovered from the knock that kept him out of the
Community Shield and is available for selection (confirmed by Maresca's
matchday-minus-one presser). Still a prediction, not a team sheet;
carried forward for next sweep to resolve against the actual lineup.?

**CONFIRMED, 26 Aug 2026 — daily sweep, actual GW1 team sheet.** Neither
prediction was quite right: City's actual right-back vs Bournemouth (23
Aug) was Abdukodir Khusanov, not Nunes or Ait-Nouri. O'Reilly did start,
but in central midfield alongside Anderson, not at right-back — the
core competition-risk thesis (not nailed at RB) is confirmed even though
the specific replacement guessed on 20-21 Aug was wrong. Resolution
logged against `OReilly-MCI-stp-20260820-1`. Sources: Sports Mole,
mancity.com confirmed lineups.

**New question opened, not closed, by the resolution above, 26 Aug 2026
— daily sweep, pending Friday review.** The stp resolution only answers
whether he still starts (yes, all 90). It does not answer whether a
DEF-priced player actually lining up in central midfield still produces
DEF-level defensive-contribution numbers. He remains FPL-registered as a
DEF (clean-sheet/GC scoring is unaffected by where he lines up), but a
player playing auxiliary midfield rather than in the back four would be
expected to log fewer clearances/blocks/interceptions/tackles than a
genuine defender — a live risk to his `cbit90`/DC-threshold value that
the last-16 start-rate framing doesn't capture. No sourced magnitude yet;
logged as `OReilly-MCI-cbit90-20260826-1` for the Friday review to size,
same as the Rice/Villa instructed-estimate precedent, if you want to put
a number on it.?

**Sized, 26 Aug 2026 — instructed estimate, pending Friday review.**
Sylvan reviewed the modelled xP impact directly via `scoring.
expected_points()` and instructed a paired hypothetical: `cbit90 mult
0.8` (-20% defensive contribution) alongside `xgi90 mult 1.2` (+20%
attacking involvement), kept scored as DEF. Net effect on his raw xP/90:
**4.636 -> 4.831 (+0.195)** — positive, because his baseline P(clearing
the 10.0 CBIT/90 DEF threshold) is already only ~7% under the empirical
hit-rate model (DC points were just 0.14 of his 4.64 total even before
the cut), while DEF's 6-points-per-goal rate makes the attacking-side
gain worth more than the defensive-side loss. Logged as
`OReilly-MCI-cbit90-20260826-2` (cbit90) and
`OReilly-MCI-xgi90-20260826-1` (xgi90) — **both magnitudes are Sylvan's
own instructed estimates, not sourced figures**, same discipline as the
Rice/Villa entries. Not applied to the live fence; Friday review still
decides accept/reject/defer on both.?

**Accepted, Friday review 28 Aug 2026.** `OReilly-MCI-cbit90-20260826-1`
(the flag), `OReilly-MCI-cbit90-20260826-2` (cbit90 mult 0.8) and
`OReilly-MCI-xgi90-20260826-1` (xgi90 mult 1.2) all accepted. Both
multipliers now live in the adjustments fence below, GWs 1-4 (matching
the bites' own check_by_gw).

**Continued into GW2, 29 Aug 2026 — daily sweep.** Second gameweek
running with the same pattern: City's actual GW2 lineup vs Crystal
Palace (28 Aug, won 1-4) again had O'Reilly outside the back four
(Khusanov, Dias, Gvardiol at the back), grouped instead with Anderson,
Foden and Cherki in an advanced unit behind Haaland — multiple
independent GW2 confirmed-lineup reports agree (beIN Sports, Al
Jazeera, SI.com, Yahoo Sports, lastwordonsports, 101GreatGoals).
`compare_players` post-GW2 shows his underlying numbers tracking an
attacking-midfield workload more than a defender's: 150 minutes across
2 starts (75 min/game, still being subbed early — managed minutes, not
a fixed 90), xGI 0.52 (~0.31/90), materially elevated for a DEF and
close to Anderson's own 0.54. Corroborates, but doesn't newly size, the
already-accepted `cbit90 mult 0.8` / `xgi90 mult 1.2` above. Logged as
`OReilly-MCI-role-20260829-1`, updates `OReilly-MCI-cbit90-20260826-1`/
`-2` and `OReilly-MCI-xgi90-20260826-1`, pending Friday review.?

### 11. Guimarães (ARS, £7.0m, MID) — GW1 fitness doubt, relevant to Rice's workload-sharing thesis — **NOT OWNED**

**Logged 21 Aug 2026, daily sweep, pending Friday review.** Guimarães was
substituted at half-time in the Community Shield with ice strapped to his
thigh, and Arteta's 20 Aug presser would not confirm his involvement
against Coventry tonight ("Let's see how he is... he's evolving really
well"). Rice and Saka are both confirmed fit and available. Relevant to
entry 7's Rice workload-sharing thesis: if Guimarães sits out GW1, Rice is
likely to play a full workload this week rather than an immediately-shared
one — a possible one-week lag on the thesis's onset, not a contradiction
of it. Not owned, so no effect on the live squad. Source:
`Guimaraes-ARS-injury-20260821-1`.

**Falsifiable check:** does Guimarães start (or feature) for Arsenal vs
Coventry tonight, and does Rice play close to 90 minutes if he doesn't?

**CONFIRMED (part), 23 Aug 2026 — daily sweep.** Guimarães did not
feature at all in the actual GW1 win over Coventry, still recovering from
the Community Shield thigh/groin issue (Rice and Saka came in for
Guimarães and Madueke). Rice started but was withdrawn after 67 minutes
alongside Saka, "handed partial breathers" per Arteta — not close to a
full 90, so the second half of the falsifiable check reads as a mild
extra data point for the workload-sharing thesis (entry 7) even in
Guimarães' continued absence. Resolution logged against
`Guimaraes-ARS-injury-20260821-1`.

**Timeline update, 23 Aug 2026 — daily sweep, pending Friday review.**
Arteta's post-match comments give a materially shorter estimate than the
open-ended "let's see how he is" from before kickoff: "We expect him not
to be out for weeks... I don't expect that to be a big issue." If
accurate, this narrows the window in which Rice's minutes run unshared to
roughly 1-2 gameweeks rather than open-ended. Logged as
`Guimaraes-ARS-injury-20260823-1`. Source: Fantasy Football Scout, "FPL
notes: Bruno G injury latest, Tzolis sharp + Odegaard 'rhythm'," 22 Aug
2026.?

**Timeline firms up further, 26 Aug 2026 — daily sweep, pending Friday
review.** Reporting now pencils a potential return date of 31 Aug —
Arsenal's actual GW2 fixture, away at Aston Villa — citing the 10-day gap
since the Coventry win as recovery time. If accurate, Rice's
unshared-workload window (entry 7) would close after only one full
gameweek rather than the 1-2 GW estimate logged 23 Aug. Not yet a
falsifiable resolution — he still has to actually be in the squad.
Logged as `Guimaraes-ARS-injury-20260826-1`. Source: Read Arsenal F.C. /
SI.com, citing Arteta press comments.?

**Note, 27 Aug 2026 — daily sweep.** The 23 Aug timeline update above
(`Guimaraes-ARS-injury-20260823-1`) is now marked `superseded` in the
sweep log by the more specific 31 Aug estimate logged 26 Aug directly
above — no new evidence today, just tidying the resolution record to
match what the narrative already showed.

### 12. Aston Villa (AVL, £0.0m, TEAM) — squad exodus + GW1 collapse — **structural context, not a single-player thesis, NOT CURRENTLY OWNED**

**Logged 25 Aug 2026, raised by Sylvan in chat, pending Friday review.**
Villa lost 4-0 at home to Brighton in GW1 — 0.31 xG from six shots, no
recognised striker on the pitch (Buendía played as the most advanced
attacker), and João Gomes sent off for violent conduct before half-time
(bans him for the next three: Arsenal, Hull, Nottingham Forest). Confirmed
summer sales: Morgan Rogers, Ezri Konsa, Youri Tielemans, Lucas Digne.
Ollie Watkins and Emiliano Martínez — first-choice striker and keeper —
were both left out of the GW1 squad entirely, amid unresolved exit
speculation rather than injury; Emery declined to explain Watkins'
absence directly. Sources: Fantasy Football Scout GW1 Scout Notes, Sports
Mole's summer transfer tracker.

**The 30% figure is Sylvan's own instructed estimate, not a sourced
one** — same discipline as entry 7's Rice reduction: the sources above
support the facts (sales, absences, scoreline), not the size of any
resulting dip. Logged as `xgi90 mult 0.70` — at the guardrail's edge
(0.5x–1.5x cap) but within it.

**Team-wide, not one player — the adjustments fence has no team-wildcard
syntax.** If accepted Friday, this needs one `xgi90 | mult | 0.70` row per
AVL pool player individually (Cash, Mings, Pau Torres, Bogarde, Maatsen,
Lindelöf, Buendía, Guessand, McGinn, Kamara, Onana, Watkins, Martínez,
Ruggeri — contaminated-fence and sub-900-minute players excluded as
usual), not a single fence entry. Currently no Villa player is in the
squad, so this has no live-team effect either way yet.

**Falsifiable check:** does Villa's attacking output stay depressed (xG
per match materially below their 2025/26 rate) across the next 3-4
fixtures — Arsenal, Hull, Nottingham Forest (all three without the
suspended Gomes), then Brentford — rather than reverting toward pre-sale
form as Watkins/Martínez's situations resolve and new signings (record
buy Manzambi, João Gomes' namesake-free replacement roles, Garnacho on
loan) bed in? Source: `AstonVilla-AVL-xgi90-20260825-1`.?

**Defensive-solidity mirror, requested by Sylvan 25 Aug 2026 — logged
narrative-only, NO MODEL EFFECT, and none is currently possible.** Same
GW1 match, other half of the evidence: Villa conceded 4, "mistake after
mistake" defensively, Pau Torres "particularly poor." Sylvan asked for the
mirror of the attacking multiplier above — same 30% instructed magnitude,
same caveat — applied to players FACING Villa, i.e. raising opponents'
attacking expectations against Villa's defence rather than lowering
Villa's own.

This is an opponent-side effect, and **the adjustments fence has no lever
for it.** Confirmed by reading `intel_adjust.py`: `MULT_FIELDS`/`SET_FIELDS`
only mutate a matched player's own row (`xg90`/`xa90`/`xgi90`/`cbit90`/
`cbirt90`/`stp`, keyed on player+team). "This team is a soft defensive
opponent" isn't one of those fields — `fixture_difficulty`/`fixture_outlook`/
`captaincy_odds`'s ATT x / DEF x / exp CS come purely from data (shrunk
xG/xGC), with no ROLE_INTEL override hook at all. Applying it via Villa's
own defenders' `cbit90` would be a category error — that field drives
*their own* DC points, not their opponents' xG — so it was rejected rather
than logged wrong. Presented as a three-way choice; Sylvan chose
narrative-only. Building a real opponent-override mechanism remains
possible but is a code change, not a data entry — not done here.

**Falsifiable check:** do teams facing Villa over the next 3-4 fixtures
(Arsenal, Hull, Nottingham Forest, Brentford) outperform their own
season-average attacking rate specifically against Villa, consistent with
a genuinely leaky defence rather than a one-off chaotic match played
mostly with ten men? Source: `AstonVilla-AVL-defsolidity-20260825-1`.?

**Update, 26 Aug 2026 — daily sweep, pending Friday review, ahead of the
GW2 Arsenal fixture (31 Aug).** Some pull-back on the exit speculation
this entry logged: Villa have rejected four Al Hilal bids for Watkins
this week and Emery now says he is "happy to stay." Villa have also
signed a new goalkeeper, Zion Suzuki — framed by Emery as depth/
competition rather than a direct Martínez replacement, but still a fresh
signal given Martínez's own unresolved situation. Specific defender
return timelines, relevant to how much of the GW1 picture is
personnel-availability-driven rather than settled: Matty Cash out
"3-4 weeks", Tyrone Mings needs "some days more." Logged as
`AstonVilla-AVL-transfers-20260826-1`. Source: ESPN / Yahoo Sports,
citing Emery press comments.?

**Accepted, Friday review 28 Aug 2026.** `AstonVilla-AVL-xgi90-20260825-1`
accepted — `xgi90 mult 0.70` now live in the adjustments fence below, one
row per AVL pool player (Bogarde, Buendía, Cash, Guessand, Kamara,
Lindelöf, Maatsen, Martinez, McGinn, Mings, Onana, Pau, Watkins — Ruggeri
excluded, not in the current pool), GWs 1-6. `AstonVilla-AVL-defsolidity-
20260825-1` and `AstonVilla-AVL-transfers-20260826-1` remain undecided —
still on the Trello board.

### 13. Sarr (CRY, £6.5m, MID) — groin injury, doubtful for GW2 — **ALREADY OWNED**

**Logged 26 Aug 2026, daily sweep, pending Friday review.** Sarr (live XI)
missed Crystal Palace's GW1 defeat to Everton with a groin injury, having
not trained for two days beforehand; manager Pierre Sage said he was
getting treatment and expected back in training the following Monday.
Separately, reports linked him with a move to Galatasaray, which Sage
denied, saying the club wants to keep him (three years left on contract).
`injury_report` now shows him DOUBTFUL, 75% chance of playing, ahead of
the GW2 deadline (Fri 28 Aug 17:30 UTC). Sources: Fantasy Football Scout,
"FPL notes: Garner's fitness, Sarr latest + Ndiaye's threat," 24 Aug 2026;
Hayters (Pierre Sage press comments).

**Falsifiable check:** does Sarr start (or feature) for Crystal Palace in
GW2, and does his 75% odds firm up or drop as the deadline approaches?
Source: `Sarr-CRY-injury-20260826-1`.?

**Odds have dropped, not firmed, 27 Aug 2026 — daily sweep, ahead of the
GW2 deadline.** Live `injury_report` now shows Sarr INJURED at 0%
("unknown return date"), down from DOUBTFUL/75% logged yesterday —
directly answers half the falsifiable check above, though no fresh press
quote has surfaced explaining the downgrade and the actual GW2 team
sheet is still to come. Logged as `Sarr-CRY-injury-20260827-1`.?

**Accepted, Friday review 28 Aug 2026.** Both `Sarr-CRY-injury-20260826-1`
and `Sarr-CRY-injury-20260827-1` accepted as read — no `field_affected`,
narrative-only; his live availability (INJURED, 0%, unknown return)
already flows through `injury_report` directly, nothing for the
adjustments fence to add.

**Confirmed, 29 Aug 2026 — daily sweep, actual GW2 team sheet.** Sarr
did not feature in Crystal Palace's 1-4 home defeat to Man City (28
Aug) — confirmed lineup has no Sarr, Nketiah started up front in his
place, as previewed. Sage's pre-match presser (RotoWire, 26 Aug) had
already ruled him out definitively ("There's no chance he plays on
Friday... he's really in pain with his groin"). Resolves both
`Sarr-CRY-injury-20260826-1` and `Sarr-CRY-injury-20260827-1` as
`confirmed`. Separately — a genuinely new thread, not an injury
update — Liverpool's transfer interest (a reported £50m bid, 26 Aug,
alongside a since-abandoned Galatasaray £34m approach) has now been
resolved as the window closes: Read Crystal Palace (29 Aug, citing
Fabrizio Romano and BBC Sport) reports Liverpool have pulled out to
pursue PSG's Bradley Barcola instead, and Galatasaray have signed AC
Milan's Rafael Leao — both suitors gone, though some Saudi (Al Ittihad)
interest lingers per Sacha Tavolieri. Sarr was sold out of the live
squad for Schade on 28 Aug purely on his injury status, not a
transfer-exit concern — this closes off the small residual risk that a
sale would have made any future reconsideration moot regardless of his
fitness. Logged as `Sarr-CRY-transfer-20260829-1`, pending Friday
review.?

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

**Trello-gated since 28 Aug 2026.** Every row below must trace to a bite that
was sorted into the Trello board's `Take action` list and accepted at a
Friday review (see `INTEL_SWEEP.md` step 3a). This is retroactive: on
28 Aug 2026, five rows — Szoboszlai (xg90), Ndiaye (xg90), Anderson (xgi90),
Dubravka (stp), Rice (stp) — were **pulled from this fence** because they
were agreed directly in chat between 7–12 Aug, before the Trello board
existed, and have no Take Action card behind them. Backlog cards were
created for all five the same day so they can go through the normal
gate; they are **out of the live model** until each is accepted. See the
narrative entries above (1, 2, 4, 7, and the Dubravka competition-fence
note) for the underlying theses — those still stand as intel, they just no
longer move a number until re-approved.

```adjustments
Mosquera   | ARS | stp   | set  | 0.85 | 1-8 | high   | 2026-08-28 | Accepted in Friday review 28 Aug 2026 (Mosquera-ARS-stp-20260821-1, Saliba-ARS-stp-20260820-1): GW1 matchday evidence confirms he started ahead of Ben White; window extended from 1-3 to 1-8 given Timber now "in September" and Saliba pencilled for winter (earliest contention ~GW8, 10 Oct Leeds fixture); see entry 3 above
O'Reilly   | MCI | cbit90 | mult | 0.8 | 1-4 | medium | 2026-08-28 | Accepted in Friday review 28 Aug 2026 (OReilly-MCI-cbit90-20260826-1/-2): GW1 confirmed lineup has him in central midfield not RB, expected to cut his DC-threshold numbers; magnitude is Sylvan's own instructed estimate (-20%), not sourced; see entry 10 above
O'Reilly   | MCI | xgi90  | mult | 1.2 | 1-4 | medium | 2026-08-28 | Accepted in Friday review 28 Aug 2026 (OReilly-MCI-xgi90-20260826-1): paired attacking-side lever to the cbit90 cut above; Sylvan's own instructed estimate (+20%), not sourced; see entry 10 above
Bogarde    | AVL | xgi90  | mult | 0.7 | 1-6 | low    | 2026-08-28 | Accepted in Friday review 28 Aug 2026 (AstonVilla-AVL-xgi90-20260825-1): squad exodus (Rogers/Konsa/Tielemans/Digne sold) + GW1 4-0 collapse to Brighton, Watkins/Martinez left out amid exit talk; -30% magnitude is Sylvan's own instructed estimate, not sourced; see entry 12 above
Buendía    | AVL | xgi90  | mult | 0.7 | 1-6 | low    | 2026-08-28 | Accepted in Friday review 28 Aug 2026 (AstonVilla-AVL-xgi90-20260825-1): squad exodus (Rogers/Konsa/Tielemans/Digne sold) + GW1 4-0 collapse to Brighton, Watkins/Martinez left out amid exit talk; -30% magnitude is Sylvan's own instructed estimate, not sourced; see entry 12 above
Cash       | AVL | xgi90  | mult | 0.7 | 1-6 | low    | 2026-08-28 | Accepted in Friday review 28 Aug 2026 (AstonVilla-AVL-xgi90-20260825-1): squad exodus (Rogers/Konsa/Tielemans/Digne sold) + GW1 4-0 collapse to Brighton, Watkins/Martinez left out amid exit talk; -30% magnitude is Sylvan's own instructed estimate, not sourced; see entry 12 above
Guessand   | AVL | xgi90  | mult | 0.7 | 1-6 | low    | 2026-08-28 | Accepted in Friday review 28 Aug 2026 (AstonVilla-AVL-xgi90-20260825-1): squad exodus (Rogers/Konsa/Tielemans/Digne sold) + GW1 4-0 collapse to Brighton, Watkins/Martinez left out amid exit talk; -30% magnitude is Sylvan's own instructed estimate, not sourced; see entry 12 above
Kamara     | AVL | xgi90  | mult | 0.7 | 1-6 | low    | 2026-08-28 | Accepted in Friday review 28 Aug 2026 (AstonVilla-AVL-xgi90-20260825-1): squad exodus (Rogers/Konsa/Tielemans/Digne sold) + GW1 4-0 collapse to Brighton, Watkins/Martinez left out amid exit talk; -30% magnitude is Sylvan's own instructed estimate, not sourced; see entry 12 above
Lindelöf   | AVL | xgi90  | mult | 0.7 | 1-6 | low    | 2026-08-28 | Accepted in Friday review 28 Aug 2026 (AstonVilla-AVL-xgi90-20260825-1): squad exodus (Rogers/Konsa/Tielemans/Digne sold) + GW1 4-0 collapse to Brighton, Watkins/Martinez left out amid exit talk; -30% magnitude is Sylvan's own instructed estimate, not sourced; see entry 12 above
Maatsen    | AVL | xgi90  | mult | 0.7 | 1-6 | low    | 2026-08-28 | Accepted in Friday review 28 Aug 2026 (AstonVilla-AVL-xgi90-20260825-1): squad exodus (Rogers/Konsa/Tielemans/Digne sold) + GW1 4-0 collapse to Brighton, Watkins/Martinez left out amid exit talk; -30% magnitude is Sylvan's own instructed estimate, not sourced; see entry 12 above
Martinez   | AVL | xgi90  | mult | 0.7 | 1-6 | low    | 2026-08-28 | Accepted in Friday review 28 Aug 2026 (AstonVilla-AVL-xgi90-20260825-1): squad exodus (Rogers/Konsa/Tielemans/Digne sold) + GW1 4-0 collapse to Brighton, Watkins/Martinez left out amid exit talk; -30% magnitude is Sylvan's own instructed estimate, not sourced; see entry 12 above
McGinn     | AVL | xgi90  | mult | 0.7 | 1-6 | low    | 2026-08-28 | Accepted in Friday review 28 Aug 2026 (AstonVilla-AVL-xgi90-20260825-1): squad exodus (Rogers/Konsa/Tielemans/Digne sold) + GW1 4-0 collapse to Brighton, Watkins/Martinez left out amid exit talk; -30% magnitude is Sylvan's own instructed estimate, not sourced; see entry 12 above
Mings      | AVL | xgi90  | mult | 0.7 | 1-6 | low    | 2026-08-28 | Accepted in Friday review 28 Aug 2026 (AstonVilla-AVL-xgi90-20260825-1): squad exodus (Rogers/Konsa/Tielemans/Digne sold) + GW1 4-0 collapse to Brighton, Watkins/Martinez left out amid exit talk; -30% magnitude is Sylvan's own instructed estimate, not sourced; see entry 12 above
Onana      | AVL | xgi90  | mult | 0.7 | 1-6 | low    | 2026-08-28 | Accepted in Friday review 28 Aug 2026 (AstonVilla-AVL-xgi90-20260825-1): squad exodus (Rogers/Konsa/Tielemans/Digne sold) + GW1 4-0 collapse to Brighton, Watkins/Martinez left out amid exit talk; -30% magnitude is Sylvan's own instructed estimate, not sourced; see entry 12 above
Pau        | AVL | xgi90  | mult | 0.7 | 1-6 | low    | 2026-08-28 | Accepted in Friday review 28 Aug 2026 (AstonVilla-AVL-xgi90-20260825-1): squad exodus (Rogers/Konsa/Tielemans/Digne sold) + GW1 4-0 collapse to Brighton, Watkins/Martinez left out amid exit talk; -30% magnitude is Sylvan's own instructed estimate, not sourced; see entry 12 above
Watkins    | AVL | xgi90  | mult | 0.7 | 1-6 | low    | 2026-08-28 | Accepted in Friday review 28 Aug 2026 (AstonVilla-AVL-xgi90-20260825-1): squad exodus (Rogers/Konsa/Tielemans/Digne sold) + GW1 4-0 collapse to Brighton, Watkins/Martinez left out amid exit talk; -30% magnitude is Sylvan's own instructed estimate, not sourced; see entry 12 above
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
