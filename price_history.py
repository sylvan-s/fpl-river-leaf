#!/usr/bin/env python3
"""Nightly per-player price/transfer-flow snapshot — append-only.

WHY THIS EXISTS. METHODOLOGY_ALTERNATIVES.md §0 (price forecasting) and the
`price_movers` MCP tool (fpl-research server) both work off a single live
snapshot: net transfers this gameweek, scaled against ownership. That is
directional momentum, not a calibrated threshold — there is no data yet
connecting "pressure of +12% today" to "did the price actually move
tonight". This script is how that data gets collected: one row per player,
every night, forever appended, never rewritten. After a few weeks it can
answer the question price_movers can't: given today's pressure reading, how
often does a price actually move by tomorrow? Until then it is pure
data-gathering - it does not rank, predict, or recommend anything itself.

WHY NOT A SCHEDULED CLOUD SKILL (still true). This file is append-only - the
append-only guard is deliberately as important as the data itself (see
preflight.sh and docs/agents/sync.md). Cowork commits through
safe_git_commit.sh, which copies whole files over a fresh clone and pushes -
"last-writer-wins, no merge" by that script's own documented admission. A
Cowork-scheduled run of this script would risk silently dropping a night's
rows with no error, the exact failure mode the append-only guard exists to
catch AFTER the fact but cannot prevent. This script must never be wired
into a Cowork scheduled skill for that reason.

SCHEDULING - GitHub Actions (recommended, added 13 Sep 2026). See
.github/workflows/price-history-nightly.yml, which runs this script
nightly with NO dependency on any machine being on. This is safe in a way
a Cowork skill is not: an Actions runner does a fresh checkout and pushes
with ordinary git, not through safe_git_commit.sh's scratch-clone path -
same reasoning that workflow's own header gives, and the same reasoning
fpl-weekly-refresh.yml already established for the dashboard rebuild. That
workflow also retries a rejected push (fetch + rebase) rather than just
failing, since a missed night here can never be reconstructed later. This
is the recommended way to run this script - nothing further to set up.

SCHEDULING - local cron/launchd (alternative, not required). Still works
if you'd rather not depend on GitHub Actions, e.g.:
    crontab -e
    # run at 02:15 UK time, after FPL's ~01:30 GMT price update has landed
    15 2 * * * cd /Users/sylvansitkey/Projects/FPL && \\
        /usr/bin/python3 price_history.py --commit >> price_history.log 2>&1
(Confirm the python3 on PATH has httpx installed - the `base` conda env on
this Mac does; fpl-mcp does not.) DO NOT run this alongside the GitHub
Actions workflow - two writers appending the same night won't corrupt
anything (this script's own dedupe check makes even a duplicate run
harmless), but there's no reason to run the job twice. Pick one.

USAGE
    python3 price_history.py             fetch, append today's rows
    python3 price_history.py --force     append even if today is already logged
    python3 price_history.py --commit    also `git add price_history.jsonl &&
                                          git commit` (never pushes - see
                                          the local-cron note above for why;
                                          the GitHub Actions workflow above
                                          does NOT use this flag, it runs
                                          the script bare and owns the git
                                          add/commit/push itself so it can
                                          add retry-on-race logic a bare
                                          commit-then-push doesn't have)

READ-ONLY against FPL. Same GET-only, no-credentials design as
fpl_research_mcp.py - see that file's own docstring for the reasoning.
"""
from __future__ import annotations

import datetime as _dt
import json
import os
import subprocess
import sys
from typing import Any

import httpx

HERE = os.path.dirname(os.path.abspath(__file__))
LOG_PATH = os.path.join(HERE, "price_history.jsonl")

BASE = "https://fantasy.premierleague.com/api"
UA = {"User-Agent": "fpl-research-mcp/1.0"}
POS = {1: "GKP", 2: "DEF", 3: "MID", 4: "FWD"}


def _boot() -> Any:
    r = httpx.get(f"{BASE}/bootstrap-static/", headers=UA, timeout=30.0, follow_redirects=True)
    r.raise_for_status()
    return r.json()


def _f(v: Any, default: float = 0.0) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def build_rows(boot: dict, date: str, logged_utc: str) -> list[dict]:
    """Pure transform: bootstrap-static JSON -> one flat row per player.

    Split out from run() so it can be tested against a small synthetic
    payload with no network and no filesystem writes.
    """
    teams = {t["id"]: t["short_name"] for t in boot["teams"]}
    total_players = boot.get("total_players") or 0
    rows = []
    for el in boot["elements"]:
        rows.append({
            "date": date,
            "logged_utc": logged_utc,
            "id": el["id"],
            "name": el["web_name"],
            "team": teams.get(el["team"], "?"),
            "pos": POS.get(el["element_type"], "?"),
            "price": el["now_cost"] / 10,
            "own_pct": _f(el.get("selected_by_percent")),
            "total_players": total_players,
            "transfers_in_event": el.get("transfers_in_event", 0),
            "transfers_out_event": el.get("transfers_out_event", 0),
            "cost_change_event": el.get("cost_change_event", 0),
            "cost_change_start": el.get("cost_change_start", 0),
            "status": el.get("status", "a"),
        })
    return rows


def _tail_line(path: str, chunk: int = 8192) -> str | None:
    """Last non-empty line of an append-only file, read from the end so this
    stays cheap once the file has months of history (one seek + one small
    read, never loading the whole file). Safe as long as no single line
    exceeds `chunk` bytes - true here, rows are flat single-player JSON,
    a couple hundred bytes each."""
    if not os.path.exists(path) or os.path.getsize(path) == 0:
        return None
    with open(path, "rb") as fh:
        fh.seek(0, os.SEEK_END)
        size = fh.tell()
        fh.seek(max(0, size - chunk))
        data = fh.read()
    lines = [ln for ln in data.split(b"\n") if ln.strip()]
    if not lines:
        return None
    return lines[-1].decode("utf-8")


def _last_logged_date(path: str) -> str | None:
    line = _tail_line(path)
    if not line:
        return None
    try:
        return json.loads(line).get("date")
    except json.JSONDecodeError:
        return None


def append_rows(path: str, rows: list[dict]) -> None:
    """Append-only, by construction: always mode 'a', never 'w'. Never call
    this with an empty path or truncate path first - if you find yourself
    wanting to "fix up" a bad night's rows, append a correction row rather
    than editing history; see docs/agents/sync.md for why this file's
    integrity depends on append-only being absolute, not a convention."""
    with open(path, "a", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, separators=(",", ":")) + "\n")


def run(force: bool = False, commit: bool = False, path: str = LOG_PATH) -> int:
    today = _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%d")
    existing = _last_logged_date(path)
    if existing == today and not force:
        print(f"{path} already has {today} logged (last row's date) - "
              f"skipping. Pass --force to log again anyway.")
        return 0

    boot = _boot()
    now = _dt.datetime.now(_dt.timezone.utc).isoformat()
    rows = build_rows(boot, today, now)
    append_rows(path, rows)
    print(f"Logged {len(rows)} players for {today} -> {path}")

    if commit:
        # Runs under whatever git identity is already configured on this
        # Mac (Sylvan Sitkey) - this is his cron job running his own script,
        # not a Claude Code session, so Claude commit-attribution rules
        # don't apply here. No --author override: a distinct bot identity
        # would only make `git blame`/GitHub's contribution graph murkier
        # for no real benefit, since this script is already self-describing
        # via its commit message.
        rel = os.path.relpath(path, HERE)
        subprocess.run(["git", "add", rel], cwd=HERE, check=True)
        msg = f"Price history: log {today} ({len(rows)} players)"
        result = subprocess.run(["git", "commit", "-m", msg],
                                 cwd=HERE, capture_output=True, text=True)
        if result.returncode == 0:
            print(f"Committed: {msg}")
        elif "nothing to commit" in (result.stdout + result.stderr).lower():
            print("Nothing to commit (unexpected - rows were just appended).")
        else:
            sys.exit(f"git commit failed:\n{result.stdout}\n{result.stderr}")

    return len(rows)


if __name__ == "__main__":
    run(force="--force" in sys.argv, commit="--commit" in sys.argv)
