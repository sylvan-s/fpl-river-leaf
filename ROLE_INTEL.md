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

**Impact on decisions already taken:** he was **sold on 7 Aug**. This is the fifth
and most serious mark against that transfer — and unlike the other four it is not
a measurement error but a blind spot: *the screens cannot price a role change.*

**Practical constraint:** buying him back is **blocked by the 3-per-club cap**
(Virgil, Wirtz, Isak). The only route is **Wirtz ↔ Szoboszlai**, both LIV mids.

**Falsifiable check:** who takes Liverpool's first penalty and first direct free
kick? Also watch `penalties_order` in the API once populated.

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

### 4. Ndiaye (EVE, £6.0m, MID) — penalties + shot volume

**Thesis:** locked-in penalty duty plus underlying volume beats his £6.0m price.

**Screen says `limited`** (xGI 11.09, xGI/90 0.36, CBIRT/90 9.2) — but with a
**−2.09 delta**, so already underperforming his chances. Penalty duty would lift
the xGI materially and the negative delta says the output is due rather than lucky.

**Falsifiable check:** confirm he takes Everton's first penalty.

### 5. João Pedro (CHE, £7.5m, FWD) — central catalyst — **ALREADY OWNED**

**Thesis:** operates as the focal point in Chelsea's setup.

**Screen is more cautious:** xGI 16.87 but a **+7.13 delta**, one of the largest
overperformances in the game — 24 G+A against 16.87 xGI. Both can be true: an
elite role *and* an unsustainable conversion rate. The role protects the xGI; it
does not protect the finishing.

**Falsifiable check:** does the delta compress toward zero over the opening weeks
as expected? If it stays high, he may be a genuine finisher rather than lucky.

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
Szoboszlai | P1 F1 | 2026-08-07 | community consensus; Salah departure vacates duty; UNCONFIRMED
Ndiaye     | P1    | 2026-08-07 | community consensus; "locked-in" penalty role claimed; UNCONFIRMED
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
