#!/usr/bin/env python3
"""Offline tests for price_history.py — no network, no writes to the real log.

Run:  python3 test_price_history.py
"""
import json
import os
import tempfile

import price_history as ph

FAILS = []


def check(label, cond, detail=""):
    if cond:
        print(f"  PASS  {label}")
    else:
        print(f"  FAIL  {label}  {detail}")
        FAILS.append(label)


BOOT = {
    "total_players": 1000000,
    "teams": [{"id": 1, "short_name": "ARS"}, {"id": 2, "short_name": "LIV"}],
    "elements": [
        {"id": 11, "web_name": "Rice", "team": 1, "element_type": 3,
         "now_cost": 65, "selected_by_percent": "20.5", "transfers_in_event": 5000,
         "transfers_out_event": 1200, "cost_change_event": 0, "cost_change_start": 1,
         "status": "a"},
        {"id": 22, "web_name": "Salah", "team": 2, "element_type": 3,
         "now_cost": 130, "selected_by_percent": "45.0", "transfers_in_event": 200,
         "transfers_out_event": 9000, "cost_change_event": -1, "cost_change_start": -3,
         "status": "d"},
        # missing selected_by_percent entirely — must not crash
        {"id": 33, "web_name": "NoOwn", "team": 1, "element_type": 1,
         "now_cost": 40, "transfers_in_event": 0, "transfers_out_event": 0,
         "cost_change_event": 0, "cost_change_start": 0, "status": "a"},
    ],
}

print("== build_rows ==")
rows = ph.build_rows(BOOT, "2026-09-13", "2026-09-13T02:15:00+00:00")
check("one row per element", len(rows) == 3, len(rows))
by_id = {r["id"]: r for r in rows}
check("price converts from now_cost tenths", by_id[11]["price"] == 6.5, by_id[11])
check("team short_name resolved", by_id[11]["team"] == "ARS", by_id[11])
check("pos resolved from element_type", by_id[11]["pos"] == "MID", by_id[11])
check("own_pct cast to float", by_id[11]["own_pct"] == 20.5, by_id[11])
check("total_players carried on every row", by_id[22]["total_players"] == 1000000)
check("transfers_in/out_event passed through", by_id[22]["transfers_in_event"] == 200
      and by_id[22]["transfers_out_event"] == 9000)
check("cost_change_event/start passed through (already-fell player)",
      by_id[22]["cost_change_event"] == -1 and by_id[22]["cost_change_start"] == -3)
check("status flag carried", by_id[22]["status"] == "d")
check("missing selected_by_percent defaults to 0.0, no crash", by_id[33]["own_pct"] == 0.0)
check("date and logged_utc stamped on every row",
      all(r["date"] == "2026-09-13" for r in rows)
      and all(r["logged_utc"] == "2026-09-13T02:15:00+00:00" for r in rows))

print("\n== append-only / dedupe (offline — _boot monkeypatched) ==")
_real_boot = ph._boot
ph._boot = lambda: BOOT  # no network in tests, matching test_fpl_mcp.py's convention
tmp = tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False)
tmp.close()
path = tmp.name
try:
    check("no file yet -> no last-logged date", ph._last_logged_date(path) is None)

    n1 = ph.run(force=False, commit=False, path=path)
    check("first run logs every player in the synthetic payload", n1 == len(BOOT["elements"]), n1)
    lines_after_1 = sum(1 for _ in open(path))
    check("file has one line per player after run 1", lines_after_1 == n1, (lines_after_1, n1))

    n2 = ph.run(force=False, commit=False, path=path)
    check("same-day re-run without --force logs nothing", n2 == 0, n2)
    lines_after_2 = sum(1 for _ in open(path))
    check("file did not grow on the skipped re-run", lines_after_2 == lines_after_1,
          (lines_after_2, lines_after_1))

    n3 = ph.run(force=True, commit=False, path=path)
    check("--force logs again even though today is already present", n3 == len(BOOT["elements"]), n3)
    lines_after_3 = sum(1 for _ in open(path))
    check("forced re-run appends, does not overwrite (file only grows)",
          lines_after_3 == lines_after_1 + n3, (lines_after_3, lines_after_1, n3))

    last = json.loads(ph._tail_line(path))
    check("tail line is well-formed JSON with today's date",
          "date" in last and "id" in last, last)
finally:
    os.unlink(path)
    ph._boot = _real_boot

print("\n== _tail_line on a synthetic file (no network) ==")
tmp2 = tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False, mode="w")
for i in range(50):
    tmp2.write(json.dumps({"date": "2026-09-01", "id": i}) + "\n")
tmp2.write(json.dumps({"date": "2026-09-02", "id": 999}) + "\n")
tmp2.close()
try:
    check("empty file -> None", ph._last_logged_date(
        os.path.join(tempfile.gettempdir(), "definitely-does-not-exist.jsonl")) is None)
    check("tail line is the LAST row, not an earlier one",
          json.loads(ph._tail_line(tmp2.name))["id"] == 999)
    check("_last_logged_date reads the date off that last row",
          ph._last_logged_date(tmp2.name) == "2026-09-02")
    # Force the read window smaller than the whole file to prove it still
    # finds the true last line rather than an earlier one caught by a small
    # tail window landing mid-file.
    check("tail_line correct even with a deliberately tiny read chunk",
          json.loads(ph._tail_line(tmp2.name, chunk=40))["id"] == 999)
finally:
    os.unlink(tmp2.name)

print("\n" + ("ALL TESTS PASSED" if not FAILS else f"{len(FAILS)} FAILURE(S): {FAILS}"))
import sys
sys.exit(1 if FAILS else 0)
