#!/usr/bin/env python3
"""Append the VM's own log rows (served by vm_runner.append_only_delta) to the
repo's append-only files. Used by .github/workflows/vm-log-sync.yml.

    python3 vm_log_merge.py delta.json

The payload comes over the network, so it is treated as untrusted: only the
files in ALLOWED are ever written (must equal vm_runner.APPEND_ONLY - a test
checks), every row must be a JSON object on one line, and a row already in the
file is never added twice. Prints one `merged <path> <n>` line per file that
changed, or `merged 0` when nothing did. Exit 1 on a malformed payload, writing
nothing.
"""
import json
import os
import sys

ALLOWED = ("fpl_calibration_log.jsonl", "docs/data/intel_sweep_log.jsonl",
           "price_history.jsonl")


def merge(payload, root="."):
    """Apply payload to files under root. Returns {path: rows_added}."""
    if not isinstance(payload, dict) or payload.get("ok") is not True:
        raise ValueError(f"payload not ok: {str(payload)[:200]}")
    delta = payload.get("delta")
    if not isinstance(delta, dict):
        raise ValueError("payload has no delta object")
    plan = {}
    for path, rows in delta.items():
        if path not in ALLOWED:
            raise ValueError(f"path not allowed: {path!r}")
        if not isinstance(rows, list):
            raise ValueError(f"rows for {path} not a list")
        for r in rows:
            if not isinstance(r, str) or "\n" in r or not isinstance(json.loads(r), dict):
                raise ValueError(f"bad row for {path}: {str(r)[:80]!r}")
        plan[path] = rows
    added = {}
    for path, rows in plan.items():
        full = os.path.join(root, path)
        have, text = set(), ""
        if os.path.exists(full):
            with open(full, encoding="utf-8") as fh:
                text = fh.read()
            have = {l for l in text.splitlines() if l.strip()}
        new = []
        for r in rows:
            if r not in have:
                have.add(r)
                new.append(r)
        if new:
            with open(full, "a", encoding="utf-8") as fh:
                if text and not text.endswith("\n"):
                    fh.write("\n")
                fh.write("\n".join(new) + "\n")
            added[path] = len(new)
    return added


if __name__ == "__main__":
    try:
        with open(sys.argv[1], encoding="utf-8") as fh:
            added = merge(json.load(fh))
    except Exception as e:
        print(f"vm_log_merge: refused: {e}", file=sys.stderr)
        sys.exit(1)
    for p, n in added.items():
        print(f"merged {p} {n}")
    if not added:
        print("merged 0")
