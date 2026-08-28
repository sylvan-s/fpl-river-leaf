# Source reliability — generated, do not hand-edit

Regenerate with `python3 score_source_reliability.py`. Source: `docs/data/intel_sweep_log.jsonl` (19 bites logged, 6 resolutions). Live gameweek: 2.

**Accuracy only reported at 5+ resolved bites** (confirmed + contradicted) — below that, the percentage would be more noise than signal from two or three claims. Expired and superseded bites count toward `stale_rate` (the check never resolved either way) but not toward accuracy, since going stale is a different failure mode from being wrong.

| Source | Tier | n | Resolved | Accuracy | Stale rate | Open |
|---|---|---|---|---|---|---|
| Fantasy Football Scout | 3 | 2 | 1 | n=1, need 5 | 0% | 1 |
| Manchester City official site | 3 | 2 | 1 | n=1, need 5 | 0% | 1 |
| Sports Mole / mancity.com (GW1 lineup); magnitude sized by Sylvan Sitkey against scoring.expected_points() | 3 | 2 | 0 | n=0, need 5 | — | 2 |
| Yardbarker / Yahoo Sports (Man City predicted-lineup reports) + Fantasy Football Scout | 3 | 1 | 1 | n=1, need 5 | 0% | 0 |
| Yahoo Sports / Sports Mole (Arteta press conference) | 3 | 1 | 0 | n=0, need 5 | — | 1 |
| RoundtableSports (Arsenal), citing Arteta 20 Aug press conference and Community Shield lineup | 3 | 1 | 1 | n=1, need 5 | 0% | 0 |
| RoundtableSports (Arsenal), citing Arteta 20 Aug press conference | 3 | 1 | 1 | n=1, need 5 | 0% | 0 |
| Fantasy Football Scout, quoting Mikel Arteta's post-Coventry press comments | 3 | 1 | 0 | n=0, need 5 | 0% | 0 |
| Fantasy Football Scout (GW1 Scout Notes) + Sports Mole (summer transfer confirmations) | 3 | 1 | 0 | n=0, need 5 | — | 1 |
| Fantasy Football Scout (GW1 Scout Notes) - same match report as AstonVilla-AVL-xgi90-20260825-1 | 3 | 1 | 0 | n=0, need 5 | — | 1 |
| Fantasy Football Scout / Hayters (Pierre Sage press comments) | 3 | 1 | 0 | n=0, need 5 | — | 1 |
| Read Arsenal F.C. / SI.com, citing Arteta press comments | 3 | 1 | 0 | n=0, need 5 | — | 1 |
| ESPN / Yahoo Sports, citing Unai Emery press comments | 3 | 1 | 0 | n=0, need 5 | — | 1 |
| Sports Mole / mancity.com (GW1 confirmed lineup) | 3 | 1 | 0 | n=0, need 5 | — | 1 |
| Sports Mole / CityXtra / Goal.com, citing Enzo Maresca post-Bournemouth press comments | 3 | 1 | 0 | n=0, need 5 | — | 1 |
| Live injury_report (fpl-research MCP, FPL API-derived) | 3 | 1 | 0 | n=0, need 5 | — | 1 |

## By category, per source

- **Fantasy Football Scout** — setpiece: 2
- **Manchester City official site** — manager_change: 1, tactical: 1
- **Sports Mole / mancity.com (GW1 lineup); magnitude sized by Sylvan Sitkey against scoring.expected_points()** — tactical: 2
- **Yardbarker / Yahoo Sports (Man City predicted-lineup reports) + Fantasy Football Scout** — rotation: 1
- **Yahoo Sports / Sports Mole (Arteta press conference)** — injury: 1
- **RoundtableSports (Arsenal), citing Arteta 20 Aug press conference and Community Shield lineup** — rotation: 1
- **RoundtableSports (Arsenal), citing Arteta 20 Aug press conference** — injury: 1
- **Fantasy Football Scout, quoting Mikel Arteta's post-Coventry press comments** — injury: 1
- **Fantasy Football Scout (GW1 Scout Notes) + Sports Mole (summer transfer confirmations)** — other: 1
- **Fantasy Football Scout (GW1 Scout Notes) - same match report as AstonVilla-AVL-xgi90-20260825-1** — tactical: 1
- **Fantasy Football Scout / Hayters (Pierre Sage press comments)** — injury: 1
- **Read Arsenal F.C. / SI.com, citing Arteta press comments** — injury: 1
- **ESPN / Yahoo Sports, citing Unai Emery press comments** — other: 1
- **Sports Mole / mancity.com (GW1 confirmed lineup)** — tactical: 1
- **Sports Mole / CityXtra / Goal.com, citing Enzo Maresca post-Bournemouth press comments** — injury: 1
- **Live injury_report (fpl-research MCP, FPL API-derived)** — injury: 1

---

**How to read this.** A source with high accuracy on a small n is not
yet proven — treat it the same way `predictive_backtest`'s own gating
treats a thin sample. Tier 3 (named journalism/analytics outlets:
Fantasy Football Scout, RotoWire, Il Margine, ESPN, OneFootball, club-
official channels) and Tier 4 (community creator consensus: Let's Talk
FPL, FPL Focal, FPL Mate, FPL Harry, Big Man Bakar, FPL Fran, The FPL
Wire, FPL Blackbox) are scored on the same scale deliberately — the
point of this table is to let the data say which tier label is doing
real work, rather than assuming Tier 3 outranks Tier 4 by construction.

**A high `stale_rate` is itself informative** — a source whose claims
routinely go unconfirmed either makes vaguer claims than the falsifiable-
check discipline wants, or reports things further out that take longer
to resolve than the `check_by_gw` window allows. Either is worth knowing
before weighting the source next time.
