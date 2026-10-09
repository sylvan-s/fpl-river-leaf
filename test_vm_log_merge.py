"""Tests for vm_log_merge.py. Run: python3 test_vm_log_merge.py"""
import os
import tempfile

import vm_log_merge as m
import vm_runner

fails = []


def check(name, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else f"  {detail}"))
    if not ok:
        fails.append(name)


def raises(payload, root):
    try:
        m.merge(payload, root)
    except ValueError:
        return True
    return False


check("allow-list equals vm_runner.APPEND_ONLY", tuple(m.ALLOWED) == tuple(vm_runner.APPEND_ONLY))

with tempfile.TemporaryDirectory() as d:
    f = os.path.join(d, "fpl_calibration_log.jsonl")
    with open(f, "w") as fh:
        fh.write('{"gw": 1}')                            # no trailing newline
    ok = lambda rows, p="fpl_calibration_log.jsonl": {"ok": True, "delta": {p: rows}}
    check("appends new rows, repairs a missing final newline",
          m.merge(ok(['{"gw": 2}', '{"gw": 2}']), d) == {"fpl_calibration_log.jsonl": 1}
          and open(f).read() == '{"gw": 1}\n{"gw": 2}\n', open(f).read())
    check("idempotent: a row already present is not added again",
          m.merge(ok(['{"gw": 1}', '{"gw": 2}']), d) == {}
          and open(f).read().count("\n") == 2)
    before = open(f).read()
    check("path outside the allow-list refused", raises(ok(['{"a": 1}'], "squad.json"), d))
    check("path traversal refused", raises(ok(['{"a": 1}'], "../x.jsonl"), d))
    check("non-JSON row refused", raises(ok(["not json"]), d))
    check("non-object row refused", raises(ok(["[1]"]), d))
    check("multi-line row refused", raises(ok(['{"a": 1}\n{"b": 2}']), d))
    check("payload not ok refused", raises({"ok": False, "error": "x"}, d))
    check("one bad row writes nothing (all-or-nothing)",
          raises(ok(['{"gw": 5}', "oops"]), d) and open(f).read() == before)
    check("missing target file is created",
          m.merge(ok(['{"p": 1}'], "price_history.jsonl"), d) == {"price_history.jsonl": 1})

print("\n%d failure(s)" % len(fails))
raise SystemExit(1 if fails else 0)
