#!/usr/bin/env python3
"""Regression check for apply_intel_decisions.py — proves it doesn't disturb
score_source_reliability.py, which this task explicitly leaves unchanged.

Runs entirely against a throwaway copy of the real log (never touches
docs/data/intel_sweep_log.jsonl) by monkeypatching
score_source_reliability.LOG_PATH for the duration of each check.

Run:  python3 test_apply_intel_decisions.py
"""
import json
import os
import shutil
import sys
import tempfile

import score_source_reliability as ssr
import apply_intel_decisions as applier

FAILS = []


def check(label, cond, detail=""):
    if cond:
        print(f"  PASS  {label}")
    else:
        print(f"  FAIL  {label}  {detail}")
        FAILS.append(label)


REAL_LOG = ssr.LOG_PATH


def with_temp_log(fn):
    """Copies the real log to a temp file, points ssr.LOG_PATH at it for the
    duration of fn(temp_path), then restores the original path — even on
    failure."""
    tmpdir = tempfile.mkdtemp()
    tmp_path = os.path.join(tmpdir, "intel_sweep_log.jsonl")
    shutil.copyfile(REAL_LOG, tmp_path)
    orig = ssr.LOG_PATH
    try:
        ssr.LOG_PATH = tmp_path
        applier.LOG_PATH = tmp_path
        fn(tmp_path)
    finally:
        ssr.LOG_PATH = orig
        applier.LOG_PATH = orig
        shutil.rmtree(tmpdir, ignore_errors=True)


print("== score() is byte-identical before/after new-writer decisions ==")

baseline_ranked, baseline_gw, baseline_n_bites, baseline_n_res = ssr.score()
baseline_json = json.dumps(baseline_ranked, sort_keys=True)


def scenario_new_decision(tmp_path):
    bites, _res, _dec = ssr.load_log()
    some_bite_id = next(iter(bites))
    items = [{
        "bite_id": some_bite_id, "decision": "deferred",
        "date": "2099-01-01", "decided_by": "test", "note": "regression test",
    }]
    appended, skipped = applier.apply_decisions(items, log_path=tmp_path)
    check("apply_decisions appended exactly 1 new decision",
          len(appended) == 1 and len(skipped) == 0)

    ranked, gw, n_bites, n_res = ssr.score()
    check("score() ranked output unchanged after appending a decision",
          json.dumps(ranked, sort_keys=True) == baseline_json)
    check("score() bite/resolution counts unchanged (decisions aren't scored)",
          (n_bites, n_res) == (baseline_n_bites, baseline_n_res))
    check("live gameweek unchanged", gw == baseline_gw)

    # load_log() must still parse every line cleanly, including the new one
    ssr.load_log()
    check("log still parses cleanly after append (no malformed line)", True)


with_temp_log(scenario_new_decision)


print("\n== dedupe: re-applying the identical decision is a no-op ==")


def scenario_dedupe(tmp_path):
    bites, _res, _dec = ssr.load_log()
    some_bite_id = next(iter(bites))
    items = [{
        "bite_id": some_bite_id, "decision": "accepted",
        "date": "2099-02-02", "decided_by": "test", "note": "first pass",
    }]
    appended1, skipped1 = applier.apply_decisions(items, log_path=tmp_path)
    check("first application appends", len(appended1) == 1 and len(skipped1) == 0)
    with open(tmp_path, encoding="utf-8") as fh:
        lines_after_first = sum(1 for _ in fh)

    appended2, skipped2 = applier.apply_decisions(items, log_path=tmp_path)
    check("re-running the SAME decision (same bite_id+date+decision) skips it",
          len(appended2) == 0 and len(skipped2) == 1)
    with open(tmp_path, encoding="utf-8") as fh:
        lines_after_second = sum(1 for _ in fh)
    check("line count unchanged after the duplicate re-run",
          lines_after_second == lines_after_first,
          f"{lines_after_first} -> {lines_after_second}")

    # A genuinely changed decision for the same bite (Sylvan changing his
    # mind) must NOT be treated as a duplicate - latest wins, per
    # score_source_reliability.py's own documented contract.
    changed = [{
        "bite_id": some_bite_id, "decision": "rejected",
        "date": "2099-02-03", "decided_by": "test", "note": "changed my mind",
    }]
    appended3, skipped3 = applier.apply_decisions(changed, log_path=tmp_path)
    check("a genuinely changed decision (new date+value) is appended, not skipped",
          len(appended3) == 1 and len(skipped3) == 0)

    _bites, _res, decisions = ssr.load_log()
    check("latest decision for the bite now reflects the change",
          decisions[some_bite_id]["decision"] == "rejected")


with_temp_log(scenario_dedupe)


print("\n== validation: unknown bite_id is refused, nothing written ==")


def scenario_unknown_bite(tmp_path):
    with open(tmp_path, encoding="utf-8") as fh:
        lines_before = fh.readlines()
    items = [{
        "bite_id": "TotallyMadeUp-XXX-fake-20990101-1", "decision": "accepted",
        "date": "2099-01-01", "decided_by": "test", "note": "should be refused",
    }]
    raised = False
    try:
        applier.apply_decisions(items, log_path=tmp_path)
    except applier.ApplyError:
        raised = True
    check("ApplyError raised for a bite_id with no matching 'bite' record", raised)
    with open(tmp_path, encoding="utf-8") as fh:
        lines_after = fh.readlines()
    check("file untouched when validation fails (no partial write)",
          lines_before == lines_after)


with_temp_log(scenario_unknown_bite)


print("\n== validation: bad decision value is refused ==")


def scenario_bad_decision(tmp_path):
    bites, _res, _dec = ssr.load_log()
    some_bite_id = next(iter(bites))
    items = [{
        "bite_id": some_bite_id, "decision": "maybe",
        "date": "2099-01-01", "decided_by": "test",
    }]
    raised = False
    try:
        applier.apply_decisions(items, log_path=tmp_path)
    except applier.ApplyError:
        raised = True
    check("ApplyError raised for decision not in accepted/rejected/deferred", raised)


with_temp_log(scenario_bad_decision)


print(f"\n{'ALL PASS' if not FAILS else f'{len(FAILS)} FAILURE(S): ' + ', '.join(FAILS)}")
sys.exit(1 if FAILS else 0)
