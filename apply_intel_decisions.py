#!/usr/bin/env python3
"""The Applier — writes Friday-review decisions to the intel log, safely.

WHY. `INTEL_SWEEP.md`'s "Friday review" step 3 says the review "appends one
decision record per bite to docs/data/intel_sweep_log.jsonl". Until now that
happened by hand, inline in conversation, with no validation and no guard
against a re-run duplicating a line. This script is that step, made safe:
Trello card checklists are the ONLY input (see below) — this script never
reads Trello itself, matching every other offline script in this repo
(build_intel_page.py, build_intel_review.py, score_source_reliability.py all
say the same thing: no MCP access, static input only).

WHO CALLS THIS AND HOW. The `fpl-friday-intel-review` flow, driven by an
agent with Trello MCP access, reads each `Take action` card's checklist
(accept/reject/defer per bite), then calls this script with one JSON object
per decided bite:

    [{"bite_id": "Sarr-CRY-injury-20260826-1", "decision": "accepted",
      "date": "2026-09-04", "decided_by": "Sylvan",
      "note": "Sorted via Trello Take Action checklist"}, ...]

    python3 apply_intel_decisions.py decisions.json
    python3 apply_intel_decisions.py -   # read the same JSON from stdin

THE BITE ID MUST BE COPIED VERBATIM from the card's `ID:` line — Trello and
this log already share one ID scheme (see INTEL_SWEEP.md step 3a), and this
script's own existence check (below) is exactly what catches a typo or an
invented ID before it corrupts the log. A decision whose bite_id has no
matching `bite` record is refused, not written — this is not theoretical:
`EnzoFernandez-MCI-transfer-20260901-1` reached `decision` on 4 Sep 2026 with
no `bite` record ever logged behind it, invisible to score_source_reliability.
py's scoring because score() only iterates logged bites. This script's
existence check is what stops that recurring.

DEDUPE, NOT REWRITE. `decision` is deliberately NOT first-write-stands (see
score_source_reliability.py's docstring) — Sylvan can change his mind, and
the latest decision for a given bite_id wins. But a re-run of the same
review with nothing new must not pad the log with identical duplicate lines.
So: before appending, this script loads the log's CURRENT latest decision
for that bite_id (via score_source_reliability.load_log(), unchanged) and
skips the write only if bite_id + date + decision all already match the
latest record on file — an exact repeat. Anything else (a new bite_id, a
changed decision, a later date) is a genuine event and gets appended. The
file itself is opened in append ("a") mode only — this script never seeks,
truncates or rewrites a byte of an existing line.

SCHEMA — UNCHANGED, on purpose. Every field name and the `kind: "decision"`
shape below is copied verbatim from score_source_reliability.py's own
docstring, which is the one score() actually parses. Do not add, rename or
reorder fields here without updating that docstring and re-running the
regression check in test_apply_intel_decisions.py — score_source_reliability.
py is not touched by this script and must not need to be.

    python3 test_apply_intel_decisions.py   # regression: proves score()'s
                                             # output is identical whether a
                                             # decision came from this script
                                             # or was hand-appended, same as
                                             # every existing decision record
"""
import datetime as dt
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import score_source_reliability as ssr  # noqa: E402

LOG_PATH = ssr.LOG_PATH
VALID_DECISIONS = ssr.VALID_DECISIONS
DECISION_FIELDS = ["bite_id", "date", "decision", "decided_by", "note"]


class ApplyError(Exception):
    pass


def _validate(item, known_bite_ids):
    missing = [f for f in ("bite_id", "date", "decision", "decided_by") if not item.get(f)]
    if missing:
        raise ApplyError(f"decision record missing required field(s) {missing}: {item}")
    if item["decision"] not in VALID_DECISIONS:
        raise ApplyError(
            f"bite {item['bite_id']!r}: decision {item['decision']!r} not one "
            f"of {sorted(VALID_DECISIONS)}")
    if item["bite_id"] not in known_bite_ids:
        raise ApplyError(
            f"bite {item['bite_id']!r} has no matching 'bite' record in "
            f"{LOG_PATH} — refusing to write a decision for a bite that was "
            f"never logged. Reuse the ID from the Trello card's 'ID:' line "
            f"verbatim; if the card genuinely predates a logged bite, log "
            f"the bite first (see INTEL_SWEEP.md step 2).")


def _is_duplicate(item, latest_decisions):
    prior = latest_decisions.get(item["bite_id"])
    if not prior:
        return False
    return (prior.get("date") == item["date"]
            and prior.get("decision") == item["decision"])


def apply_decisions(items, log_path=LOG_PATH, now=None):
    """items: list of dicts with bite_id/date/decision/decided_by/note(optional).
    Returns (appended, skipped_duplicate) — lists of the input items in each
    bucket. Raises ApplyError (nothing written) if any item is invalid — a
    partially-applied review is worse than one that fails loudly up front."""
    bites, _resolutions, decisions = ssr.load_log()
    known_bite_ids = set(bites.keys())
    latest_decisions = decisions  # already "latest wins" per bite_id

    for item in items:
        _validate(item, known_bite_ids)

    appended, skipped = [], []
    now = now or dt.datetime.now(dt.timezone.utc)
    logged_utc = now.strftime("%Y-%m-%dT%H:%M:%SZ")

    to_write = []
    for item in items:
        if _is_duplicate(item, latest_decisions):
            skipped.append(item)
            continue
        record = {
            "kind": "decision",
            "bite_id": item["bite_id"],
            "date": item["date"],
            "decision": item["decision"],
            "decided_by": item["decided_by"],
            "note": item.get("note", ""),
            "logged_utc": logged_utc,
        }
        to_write.append(record)
        appended.append(item)
        # Keep our own in-memory view current so two decisions for the same
        # bite_id in one batch dedupe/override correctly against each other,
        # not just against what was already on disk.
        latest_decisions = dict(latest_decisions)
        latest_decisions[item["bite_id"]] = record

    if to_write:
        with open(log_path, "a", encoding="utf-8") as fh:
            for record in to_write:
                fh.write(json.dumps(record) + "\n")

    return appended, skipped


def main():
    if len(sys.argv) != 2:
        print(__doc__)
        raise SystemExit(2)
    src = sys.argv[1]
    raw = sys.stdin.read() if src == "-" else open(src, encoding="utf-8").read()
    try:
        items = json.loads(raw)
    except json.JSONDecodeError as e:
        raise SystemExit(f"invalid JSON input: {e}")
    if not isinstance(items, list):
        raise SystemExit("input must be a JSON array of decision objects")

    try:
        appended, skipped = apply_decisions(items)
    except ApplyError as e:
        raise SystemExit(f"REFUSED, nothing written: {e}")

    print(f"Appended {len(appended)} decision(s), skipped {len(skipped)} "
          f"exact duplicate(s) already on file.")
    for item in appended:
        print(f"  + {item['bite_id']}: {item['decision']}")
    for item in skipped:
        print(f"  = {item['bite_id']}: {item['decision']} (already logged, same date)")


if __name__ == "__main__":
    main()
