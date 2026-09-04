#!/usr/bin/env python3
"""Friday intel-review retrospective — what got decided, after the fact.

WHY THIS CHANGED (4 Sep 2026). Decisions used to be made by presenting this
report AS A QUEUE and waiting for Sylvan's reply in chat — this script ran
FIRST, before any decision existed, and Sylvan answered against it directly.
That's no longer how the Friday review works: decisions are now made on each
`Take action` card's own Trello checklist (see the "Modelling" section on
those cards), and `apply_intel_decisions.py` — the Applier — reads those
checklists and appends the `decision` records. This script now runs AFTER
that step, reads the decisions the Applier just wrote, and produces
`INTEL_REVIEW.md` as a RETROSPECTIVE RECORD of that week's outcomes. It is
not input to anyone's decision, and nothing here waits for a reply — by the
time this runs, the deciding already happened on Trello.

ORDER, every Friday:
    1. python3 apply_intel_decisions.py decisions.json   # writes decisions
    2. python3 score_source_reliability.py                # scorecard, weekly
    3. python3 build_intel_review.py                      # THIS - retrospective
See INTEL_SWEEP.md, "The Friday review" section, for the full flow.

WHAT IT SHOWS:
  - **Decided this review** — every `decision` record dated today (or
    --date), paired with its bite's claim and, if accepted with a
    `field_affected`, confirmation it's now live in ROLE_INTEL.md's fence.
  - **Still pending** — bites with no decision yet, or whose latest decision
    is "deferred" — informational context on what remains open on the
    Trello board's Take Action list, not a prompt to answer here.
  - **Source reliability, full picture** — same scorecard table as before,
    for convenience alongside this week's outcomes.

A decision whose bite_id has no matching bite record (should not happen
going forward — apply_intel_decisions.py refuses those before they're ever
written) is still rendered, flagged clearly, rather than silently dropped —
a report that hides a data problem is worse than one that shows it.

OUTPUT. docs/data/intel_review_queue.json (machine-readable) and
INTEL_REVIEW.md at the repo root. Regenerate weekly inside
fpl-friday-intel-review, after the Applier step; do not hand-edit either
output.

    python3 build_intel_review.py                # today's decisions
    python3 build_intel_review.py --date 2026-09-04
"""
import argparse
import datetime as dt
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
QUEUE_PATH = os.path.join(HERE, "docs", "data", "intel_review_queue.json")
REPORT_PATH = os.path.join(HERE, "INTEL_REVIEW.md")

sys.path.insert(0, HERE)
import score_source_reliability as ssr  # noqa: E402


def decided_this_review(review_date, bites, resolutions, decisions, gw):
    """Every bite whose LATEST decision record is dated review_date — i.e.
    what this run of the Friday review actually decided, not the whole
    history. `decisions` already holds only the latest record per bite_id
    (ssr.load_log()'s contract), so this is a straight date filter."""
    out = []
    for bid, d in decisions.items():
        if d.get("date") != review_date:
            continue
        b = bites.get(bid)
        out.append({
            "bite_id": bid,
            "bite": b,  # None if orphaned - rendered, flagged, not hidden
            "decision": d["decision"],
            "decided_by": d.get("decided_by"),
            "note": d.get("note", ""),
            "status": ssr._status(bid, resolutions, gw) if b else None,
        })
    out.sort(key=lambda x: (x["decision"] != "accepted", x["bite_id"]))
    return out


def still_pending(bites, decisions, gw, resolutions):
    """Bites with no decision, or whose latest decision is 'deferred' -
    what remains open on the Trello board, for context only."""
    out = []
    for bid, b in bites.items():
        d = decisions.get(bid)
        if d and d["decision"] in ("accepted", "rejected"):
            continue
        out.append({
            **b,
            "status": ssr._status(bid, resolutions, gw),
            "prior_decision": d["decision"] if d else None,
        })
    out.sort(key=lambda x: (x.get("check_by_gw") or 999, x.get("date", "")))
    return out


def write_queue(review_date, decided, pending, gw):
    os.makedirs(os.path.dirname(QUEUE_PATH), exist_ok=True)
    json.dump(
        {"generated_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
         "live_gw": gw, "review_date": review_date,
         "decided": decided, "still_pending": pending},
        open(QUEUE_PATH, "w", encoding="utf-8"), indent=2)


def _fmt_source(b):
    if b is None:
        return "UNKNOWN — no bite record found for this decision"
    return f"{b.get('source_name', 'UNKNOWN')} (tier {b.get('source_tier', '?')})"


def render_report(review_date, decided, pending, gw, ranked):
    n_acc = sum(1 for d in decided if d["decision"] == "accepted")
    n_rej = sum(1 for d in decided if d["decision"] == "rejected")
    n_def = sum(1 for d in decided if d["decision"] == "deferred")
    lines = [
        "# Intel review — Friday decision record",
        "",
        "Generated by `build_intel_review.py`, regenerate weekly — do not "
        "hand-edit. **Retrospective, not an input queue**: decisions are made "
        "on each `Take action` Trello card's own checklist, applied by "
        "`apply_intel_decisions.py`, and this report documents the outcome "
        "afterward. Nothing here is waiting for a reply.",
        "",
        f"Live gameweek: {gw if gw is not None else 'unknown'}. Review date: "
        f"**{review_date}** — {len(decided)} bite(s) decided "
        f"({n_acc} accepted, {n_rej} rejected, {n_def} deferred).",
        "",
    ]

    lines.append("## Decided this review")
    lines.append("")
    if not decided:
        lines.append(f"*(no decision records dated {review_date} — the "
                      "Applier step may not have run yet, or nothing was "
                      "decided today)*")
    for d in decided:
        b = d["bite"]
        orphan_flag = " — **NO BITE RECORD FOUND, data problem, needs investigating**" if b is None else ""
        lines += [
            f"### `{d['bite_id']}` — {d['decision'].upper()}{orphan_flag}",
            "",
        ]
        if b:
            lines += [
                f"**{b.get('player', '?')}** ({b.get('team', '?')}) — "
                f"{b.get('category', 'other')}, confidence {b.get('confidence', '?')}",
                "",
                f"> {b.get('hypothesis', '')}",
                "",
                f"- Source: {_fmt_source(b)} · Resolution status: **{d['status']}**",
            ]
            if d["decision"] == "accepted" and b.get("field_affected"):
                lines.append(
                    f"- Live in the fence: `{b['field_affected']}` "
                    f"{b.get('suggested_op', '?')} {b.get('suggested_value', '?')} "
                    f"(see ROLE_INTEL.md's `adjustments` fence)")
            elif d["decision"] == "accepted":
                lines.append("- Accepted without a `field_affected` — logged "
                              "as confirmed intel in ROLE_INTEL.md's narrative "
                              "section, does not touch the fence")
        else:
            lines.append(f"- Decision: {d['decision']} by {d['decided_by']} "
                          f"— no matching `bite` record in "
                          f"docs/data/intel_sweep_log.jsonl")
        if d["note"]:
            lines.append(f"- Note: {d['note']}")
        lines.append("")

    lines += ["---", "", "## Still pending", ""]
    lines.append(
        f"**{len(pending)} bite(s)** with no decision yet, or previously "
        "deferred — open on the Trello board's `Take action` list. Shown "
        "for context; decide them there, not here.")
    lines.append("")
    for b in pending:
        deferred_note = " — *previously deferred*" if b.get("prior_decision") == "deferred" else ""
        lines.append(
            f"- `{b['id']}`{deferred_note} — **{b.get('player', '?')}** "
            f"({b.get('team', '?')}), {b.get('category', 'other')}, "
            f"status {b['status']}, check by GW{b.get('check_by_gw', '?')}")
    lines.append("")

    lines += [
        "---",
        "",
        "## Source reliability, full picture",
        "",
        "See `SOURCE_RELIABILITY.md` for the complete per-source track "
        "record (all sources, not just those decided this week).",
        "",
    ]
    if ranked:
        lines += ["| Source | Tier | Accuracy | Resolved | Stale rate |",
                   "|---|---|---|---|---|"]
        for r in ranked:
            acc = f"{r['accuracy']:.0%}" if r["accuracy"] is not None else "insufficient data"
            stale = f"{r['stale_rate']:.0%}" if r["stale_rate"] is not None else "—"
            lines.append(f"| {r['source_name']} | {r['source_tier']} | {acc} | "
                          f"{r['n_resolved']} | {stale} |")
    open(REPORT_PATH, "w", encoding="utf-8").write("\n".join(lines) + "\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=None,
                     help="Review date, YYYY-MM-DD. Defaults to today (UTC).")
    args = ap.parse_args()
    review_date = args.date or dt.date.today().isoformat()

    bites, resolutions, decisions = ssr.load_log()
    gw = ssr._current_gw()
    decided = decided_this_review(review_date, bites, resolutions, decisions, gw)
    pending = still_pending(bites, decisions, gw, resolutions)
    ranked, _gw2, _n_bites, _n_res = ssr.score()

    write_queue(review_date, decided, pending, gw)
    render_report(review_date, decided, pending, gw, ranked)
    print(f"Wrote {QUEUE_PATH} and {REPORT_PATH}")
    print(f"Review date {review_date}: {len(decided)} decided, "
          f"{len(pending)} still pending, live GW {gw if gw is not None else 'unknown'}")


if __name__ == "__main__":
    main()
