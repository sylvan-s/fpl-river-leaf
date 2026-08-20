# Source reliability — generated, do not hand-edit

Regenerate with `python3 score_source_reliability.py`. Source: `docs/data/intel_sweep_log.jsonl` (0 bites logged, 0 resolutions). Live gameweek: 1.

**Accuracy only reported at 5+ resolved bites** (confirmed + contradicted) — below that, the percentage would be more noise than signal from two or three claims. Expired and superseded bites count toward `stale_rate` (the check never resolved either way) but not toward accuracy, since going stale is a different failure mode from being wrong.

| Source | Tier | n | Resolved | Accuracy | Stale rate | Open |
|---|---|---|---|---|---|---|
| *(no bites logged yet)* | | | | | | |

## By category, per source


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
