#!/usr/bin/env python3
"""Source reliability scorer — turns logged community intel into a track record.

WHY. ROLE_INTEL.md has always required a date, a source and a falsifiable check
for every entry. What it never did was close the loop: nothing recorded whether
a given source's claim actually panned out, so "Fantasy Football Scout said X"
and "some podcast said Y" carried equal weight the moment they were logged.
This is the same defect log_predictions()/score_calibration() fixed for
captaincy calls, applied to intel sources instead.

INPUT. docs/data/intel_sweep_log.jsonl — append-only, written by the daily
fpl-daily-intel-sweep scheduled task (see INTEL_SWEEP.md). Three record kinds.
Bites and resolutions follow the same integrity rule as fpl_calibration_log.
jsonl: THE FIRST RECORD FOR A GIVEN ID STANDS. A bite is never edited; a later
finding about the same claim is appended as a separate "resolution" record
that references it.

    {"kind": "bite", "id": "...", "date": "2026-08-21",
     "source_name": "Fantasy Football Scout", "source_tier": 3,
     "source_url": "...", "player": "Szoboszlai", "team": "LIV",
     "category": "setpiece", "hypothesis": "...", "field_affected": "xg90",
     "suggested_op": "mult", "suggested_value": 1.35, "confidence": "high",
     "falsifiable_check": "...", "check_by_gw": 8, "logged_utc": "..."}

    {"kind": "resolution", "bite_id": "...", "date": "2026-08-25",
     "outcome": "confirmed", "evidence": "...", "logged_utc": "..."}

outcome is one of: confirmed | contradicted | expired | superseded.
expired/superseded are NOT counted as wrong — they mean the check never
resolved either way, which is a different failure mode from being wrong (see
_accuracy below). A bite with no resolution record is "open".

The third kind, "decision", is DELIBERATELY NOT first-write-stands — it is
Sylvan's live editorial call, made in the Friday `fpl-friday-intel-review`
meeting (see INTEL_SWEEP.md), and he is allowed to change his mind, so THE
LATEST decision for a given bite_id wins.

    {"kind": "decision", "bite_id": "...", "date": "2026-08-22",
     "decision": "accepted", "decided_by": "Sylvan",
     "note": "...", "logged_utc": "..."}

decision is one of: accepted | rejected | deferred. Only an "accepted"
decision may be promoted into ROLE_INTEL.md's machine-readable `setpieces`/
`adjustments` fences — the daily sweep never writes those fences itself.
Resolution (was the claim true?) and decision (do we act on it?) are
independent axes: a still-open, unresolved bite can be accepted on the
strength of its sourcing, exactly like a Tier-3 override in
SELECTION_FRAMEWORK.md.

OUTPUT. docs/data/source_scorecard.json (machine-readable, one row per source)
and SOURCE_RELIABILITY.md at the repo root (the human-readable report) —
regenerate, do not hand-edit, same discipline as docs/data/club_changes.json
feeding ROLE_INTEL.md's contaminated fence.

GATING. Same threshold score_calibration() uses: a source's accuracy is only
reported once it has 5+ resolved (confirmed or contradicted) bites. Below
that, n is shown but accuracy reads "insufficient data" rather than a
misleadingly precise percentage from two or three claims.

    python3 score_source_reliability.py             # full report
    python3 score_source_reliability.py --json-only # skip the .md write

See build_intel_review.py for the companion Friday-review queue report,
which pairs each undecided bite with its source's row from this scorecard.
"""
import json
import os
import sys
import datetime as dt

HERE = os.path.dirname(os.path.abspath(__file__))
LOG_PATH = os.path.join(HERE, "docs", "data", "intel_sweep_log.jsonl")
SCORECARD_PATH = os.path.join(HERE, "docs", "data", "source_scorecard.json")
REPORT_PATH = os.path.join(HERE, "SOURCE_RELIABILITY.md")

MIN_RESOLVED_FOR_ACCURACY = 5
VALID_OUTCOMES = {"confirmed", "contradicted", "expired", "superseded"}
VALID_DECISIONS = {"accepted", "rejected", "deferred"}


def _current_gw():
    """Best-effort live gameweek, from fixture_window.json. None if unknown.
    Same lookup intel_adjust.py uses for its staleness warning."""
    try:
        w = json.load(open(os.path.join(HERE, "fixture_window.json"), encoding="utf-8"))
        return w.get("generated_for_gw")
    except Exception:
        return None


def load_log():
    """Returns (bites, resolutions, decisions). Malformed lines are reported,
    not silently skipped — a bite nobody can read back is worse than a loud
    crash, same stance intel_adjust.py takes on a malformed adjustments row."""
    if not os.path.exists(LOG_PATH):
        return {}, {}, {}
    bites, resolutions, decisions = {}, {}, {}
    with open(LOG_PATH, encoding="utf-8") as fh:
        for lineno, line in enumerate(fh, 1):
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
            except json.JSONDecodeError as e:
                raise SystemExit(f"{LOG_PATH}:{lineno}: invalid JSON — {e}")
            kind = d.get("kind")
            if kind == "bite":
                bid = d.get("id")
                if not bid:
                    raise SystemExit(f"{LOG_PATH}:{lineno}: bite has no 'id'")
                if bid not in bites:           # first write stands
                    bites[bid] = d
            elif kind == "resolution":
                bid = d.get("bite_id")
                outcome = d.get("outcome")
                if not bid:
                    raise SystemExit(f"{LOG_PATH}:{lineno}: resolution has no 'bite_id'")
                if outcome not in VALID_OUTCOMES:
                    raise SystemExit(
                        f"{LOG_PATH}:{lineno}: resolution outcome {outcome!r} "
                        f"not one of {sorted(VALID_OUTCOMES)}")
                if bid not in resolutions:     # first resolution stands too
                    resolutions[bid] = d
            elif kind == "decision":
                bid = d.get("bite_id")
                decision = d.get("decision")
                if not bid:
                    raise SystemExit(f"{LOG_PATH}:{lineno}: decision has no 'bite_id'")
                if decision not in VALID_DECISIONS:
                    raise SystemExit(
                        f"{LOG_PATH}:{lineno}: decision {decision!r} not one "
                        f"of {sorted(VALID_DECISIONS)}")
                decisions[bid] = d              # LATEST decision wins — see docstring
            else:
                raise SystemExit(f"{LOG_PATH}:{lineno}: unknown kind {kind!r}")
    return bites, resolutions, decisions


def _status(bite_id, resolutions, gw):
    r = resolutions.get(bite_id)
    if r:
        return r["outcome"]
    return "open"


def score():
    bites, resolutions, _decisions = load_log()
    gw = _current_gw()

    by_source = {}
    for bid, b in bites.items():
        src = b.get("source_name", "UNKNOWN")
        row = by_source.setdefault(src, {
            "source_name": src,
            "source_tier": b.get("source_tier"),
            "n_bites": 0, "n_confirmed": 0, "n_contradicted": 0,
            "n_expired": 0, "n_superseded": 0, "n_open": 0,
            "categories": {},
        })
        row["n_bites"] += 1
        status = _status(bid, resolutions, gw)
        row["n_" + status] += 1
        cat = b.get("category", "other")
        row["categories"][cat] = row["categories"].get(cat, 0) + 1

    for row in by_source.values():
        resolved = row["n_confirmed"] + row["n_contradicted"]
        row["n_resolved"] = resolved
        if resolved >= MIN_RESOLVED_FOR_ACCURACY:
            row["accuracy"] = round(row["n_confirmed"] / resolved, 3)
        else:
            row["accuracy"] = None
        went_stale = resolved + row["n_expired"] + row["n_superseded"]
        row["stale_rate"] = (round(row["n_expired"] / went_stale, 3)
                              if went_stale else None)

    ranked = sorted(
        by_source.values(),
        key=lambda r: (r["accuracy"] is None, -(r["accuracy"] or 0), -r["n_bites"]),
    )
    return ranked, gw, len(bites), len(resolutions)


def write_scorecard(ranked):
    os.makedirs(os.path.dirname(SCORECARD_PATH), exist_ok=True)
    json.dump(
        {"generated_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
         "min_resolved_for_accuracy": MIN_RESOLVED_FOR_ACCURACY,
         "sources": ranked},
        open(SCORECARD_PATH, "w", encoding="utf-8"), indent=2)


def render_report(ranked, gw, n_bites, n_resolutions):
    lines = [
        "# Source reliability — generated, do not hand-edit",
        "",
        f"Regenerate with `python3 score_source_reliability.py`. Source: "
        f"`docs/data/intel_sweep_log.jsonl` ({n_bites} bites logged, "
        f"{n_resolutions} resolutions). Live gameweek: "
        f"{gw if gw is not None else 'unknown'}.",
        "",
        f"**Accuracy only reported at {MIN_RESOLVED_FOR_ACCURACY}+ resolved "
        f"bites** (confirmed + contradicted) — below that, the percentage "
        f"would be more noise than signal from two or three claims. Expired "
        f"and superseded bites count toward `stale_rate` (the check never "
        f"resolved either way) but not toward accuracy, since going stale is a "
        f"different failure mode from being wrong.",
        "",
        "| Source | Tier | n | Resolved | Accuracy | Stale rate | Open |",
        "|---|---|---|---|---|---|---|",
    ]
    if not ranked:
        lines.append("| *(no bites logged yet)* | | | | | | |")
    for r in ranked:
        acc = f"{r['accuracy']:.0%}" if r["accuracy"] is not None else f"n={r['n_resolved']}, need {MIN_RESOLVED_FOR_ACCURACY}"
        stale = f"{r['stale_rate']:.0%}" if r["stale_rate"] is not None else "—"
        lines.append(
            f"| {r['source_name']} | {r['source_tier']} | {r['n_bites']} | "
            f"{r['n_resolved']} | {acc} | {stale} | {r['n_open']} |"
        )
    lines += [
        "",
        "## By category, per source",
        "",
    ]
    for r in ranked:
        if not r["categories"]:
            continue
        cats = ", ".join(f"{k}: {v}" for k, v in sorted(r["categories"].items()))
        lines.append(f"- **{r['source_name']}** — {cats}")
    lines += [
        "",
        "---",
        "",
        "**How to read this.** A source with high accuracy on a small n is not",
        "yet proven — treat it the same way `predictive_backtest`'s own gating",
        "treats a thin sample. Tier 3 (named journalism/analytics outlets:",
        "Fantasy Football Scout, RotoWire, Il Margine, ESPN, OneFootball, club-",
        "official channels) and Tier 4 (community creator consensus: Let's Talk",
        "FPL, FPL Focal, FPL Mate, FPL Harry, Big Man Bakar, FPL Fran, The FPL",
        "Wire, FPL Blackbox) are scored on the same scale deliberately — the",
        "point of this table is to let the data say which tier label is doing",
        "real work, rather than assuming Tier 3 outranks Tier 4 by construction.",
        "",
        "**A high `stale_rate` is itself informative** — a source whose claims",
        "routinely go unconfirmed either makes vaguer claims than the falsifiable-",
        "check discipline wants, or reports things further out that take longer",
        "to resolve than the `check_by_gw` window allows. Either is worth knowing",
        "before weighting the source next time.",
    ]
    open(REPORT_PATH, "w", encoding="utf-8").write("\n".join(lines) + "\n")


def main():
    ranked, gw, n_bites, n_resolutions = score()
    write_scorecard(ranked)
    if "--json-only" not in sys.argv:
        render_report(ranked, gw, n_bites, n_resolutions)
        print(f"Wrote {SCORECARD_PATH} and {REPORT_PATH}")
    else:
        print(f"Wrote {SCORECARD_PATH}")
    if not ranked:
        print("No bites logged yet — nothing to score. "
              "See INTEL_SWEEP.md for the log format.")
        return
    print(f"\n{len(ranked)} source(s), {n_bites} bites, {n_resolutions} resolutions, "
          f"live GW {gw if gw is not None else 'unknown'}")
    for r in ranked:
        acc = f"{r['accuracy']:.0%}" if r["accuracy"] is not None else "insufficient data"
        print(f"  {r['source_name']:<28} n={r['n_bites']:<4} "
              f"resolved={r['n_resolved']:<4} accuracy={acc}")


if __name__ == "__main__":
    main()
