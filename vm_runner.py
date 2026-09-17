#!/usr/bin/env python3
"""Cloud-only optimisation: the VM runner behind fpl-research's optimiser tools.

WHY. A cloud Cowork session could ask the VM's fpl-research server for fixtures,
injuries and prices, but the optimiser, the fixture-window refresh, the Trello
quarantine overlay and the repo state all still needed the Mac. This module
wraps those scripts so the VM can answer "run the transfer optimisation" on its
own. See VM_OPTIMISER_TOOLS.md for the plan it implements.

HOW IT IS WIRED. fpl_research_mcp.py calls register() only when FPL_RUNNER=1 is
set in the server's environment (the VM's systemd unit). The Mac's stdio server
never sets it, so these tools, and the git pull inside repo_sync(), can never
run against the Mac's working tree, where preflight.sh's per-file rules apply.

WHAT IT DOES NOT DO. It never commits or pushes, and never writes squad.json,
TEAM_CHANGE_LOG.md or ROLE_INTEL.md. It writes to the clone in exactly two places:
fixture_window.json (refresh_fixture_window) and whatever docs/data snapshots
the existing research tools already wrote. Those are the RUNNER_OWNED paths
below. Any other dirty file makes every tool refuse.

THE VM IS A RUNNER, NOT THE RECORD. The repo stays the record. repo_sync()
fetches and fast-forwards before every tool call. A runner-owned file that
origin has also changed is copied to BACKUP_DIR and reset to origin's copy
before the pull, never merged.

EVERY RESPONSE CARRIES: repo HEAD, window stamp, live GW, estimator, intel and
quarantine ON/OFF, the preference-cost lines, and the scripts' stderr verbatim
(the LIVE FETCH / PRICE / CLUB / STATUS / CONTAMINATED lines). A recommendation
that names an unavailable or contaminated player is an ERROR, never a footnote.
A tie is HOLD, never resolved here.

    python3 vm_runner.py --sync        # repo_sync() once, JSON to stdout (cron)
"""
from __future__ import annotations

import asyncio
import datetime as _dt
import fnmatch
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import uuid

import constants

HERE = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable
BRANCH = "main"
STATE_DIR = os.environ.get("FPL_RUNNER_STATE") or os.path.expanduser("~/.fpl-mcp")
BACKUP_DIR = os.path.join(STATE_DIR, "runner-backup")
JOBS_DIR = os.path.join(STATE_DIR, "jobs")

# Paths the runner (or the research tools it sits beside) legitimately writes
# into the clone. Dirty here is expected; dirty anywhere else is refused.
RUNNER_OWNED = ("fixture_window.json", "docs/data/", "logs/", "__pycache__/")

# Append-only logs (CLAUDE.md / preflight.sh). NEVER runner-owned: resetting one
# to origin would delete rows nothing can reconstruct. The VM's own
# log_predictions appends to fpl_calibration_log.jsonl, and until a write tool
# exists (C1-C3) those rows reach the repo only by being copied to the Mac - so
# when the local copy is a superset of origin's, say exactly that instead of
# reporting it as anonymous dirt (9 GW5 captaincy rows, 17 Sep 2026).
APPEND_ONLY = ("fpl_calibration_log.jsonl", "docs/data/intel_sweep_log.jsonl",
               "price_history.jsonl")

# repo_file() allow-list: exact paths, plus single-level globs. fnmatch's `*`
# also matches `/`, so glob hits are re-checked for depth below.
ALLOWED_FILES = ("ROLE_INTEL.md", "TEAM_CHANGE_LOG.md", "SELECTION_FRAMEWORK.md",
                 "METHODOLOGY_ALTERNATIVES.md", "fixture_window.json",
                 "VM_OPTIMISER_TOOLS.md", "squad.json")
ALLOWED_GLOBS = ("scenarios/*.txt", "docs/data/*.json")
MAX_FILE_CHARS = 200_000

# Files whose change means the RUNNING server is stale until restarted: the
# tool definitions live in the server process, the scripts run fresh each call.
SERVER_FILES = ("fpl_research_mcp.py", "vm_runner.py", "scoring.py", "constants.py")

# stderr lines worth lifting to the top of a response. The full stderr is
# always returned as well, verbatim.
ALARM_PREFIXES = ("LIVE FETCH", "PRICE", "CLUB", "STATUS", "CONTAMINATED",
                  "INTEL WARNING", "FIXTURE WINDOW", "QUARANTINE", "SHRUNK PRIORS",
                  "RAW:", "SHRUNK:", "PRIOR:", "STP")

UNAVAILABLE_STATUSES = ("u", "n", "i")
MIN_GAIN = 0.01          # optimise_squad.transfer_mode's HOLD threshold

_repo_lock = threading.RLock()
STARTED_HEAD = None      # set by register(); HEAD the server process loaded


# --------------------------------------------------------------------- git
def _git(*args, timeout=60, repo=None):
    return subprocess.run(["git", *args], cwd=repo or HERE, capture_output=True,
                          text=True, timeout=timeout)


def _out(*args, repo=None):
    r = _git(*args, repo=repo)
    if r.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {r.stderr.strip()}")
    return r.stdout.strip()


def is_runner_owned(path):
    return any(path == p or (p.endswith("/") and path.startswith(p)) for p in RUNNER_OWNED)


def _dirty(repo=None):
    """[(xy, path)] from porcelain status, untracked included. Not via _out():
    stripping the output would eat the leading space of the first ' M' line."""
    r = _git("status", "--porcelain", "--untracked-files=all", repo=repo)
    if r.returncode != 0:
        raise RuntimeError(f"git status failed: {r.stderr.strip()}")
    return [(ln[:2], ln[3:].strip().strip('"')) for ln in r.stdout.splitlines() if ln.strip()]


def _lines_ahead(path, repo):
    """(local_only, origin_only) line counts for an append-only file, or None
    if either side cannot be read."""
    try:
        with open(os.path.join(repo, path), encoding="utf-8") as fh:
            local = [l for l in fh.read().splitlines() if l.strip()]
    except OSError:
        return None
    r = _git("show", f"origin/{BRANCH}:{path}", repo=repo)
    if r.returncode != 0:
        return None
    theirs = [l for l in r.stdout.splitlines() if l.strip()]
    ls, ts = set(local), set(theirs)
    return len(ls - ts), len(ts - ls)


def repo_sync(fetch=True, repo=None):
    """Fetch, then fast-forward only. Returns a dict; `ok` False means refuse.

    Never merges, never rebases, never pushes. A runner-owned file dirty here
    AND changed on origin is backed up and reset to origin before the pull,
    because the VM is a runner, not the record. Anything else dirty stops the pull.

    DIRT IS JUDGED AGAINST origin/main, NOT HEAD (fixed 17 Sep 2026). git status
    compares with HEAD, so a file already holding origin's newer content reads as
    modified and blocked every pull - which is exactly what CLAUDE.md warns about
    ("the only meaningful question is how the tree differs from origin/main").
    It happened for real: fpl_calibration_log.jsonl, brought level with origin,
    then wedged the clone four commits behind. Such a file is reset to HEAD
    before the fast-forward, which restores it to that same content - no data
    moves, and nothing is discarded that origin does not already have.
    """
    repo = repo or HERE
    with _repo_lock:
        res = {"ok": True, "problems": [], "warnings": [], "backed_up": [], "pulled": False}
        if fetch:
            f = _git("fetch", "--quiet", "origin", BRANCH, timeout=45, repo=repo)
            if f.returncode != 0:
                res["warnings"].append(f"git fetch failed - origin state unknown, "
                                       f"clone may be behind: {f.stderr.strip()[:300]}")
        head = _out("rev-parse", "HEAD", repo=repo)
        try:
            origin = _out("rev-parse", f"origin/{BRANCH}", repo=repo)
            ahead, behind = (int(x) for x in _out(
                "rev-list", "--left-right", "--count", f"HEAD...origin/{BRANCH}", repo=repo).split())
        except RuntimeError as e:
            origin, ahead, behind = None, 0, 0
            res["warnings"].append(str(e))
        dirty = _dirty(repo)
        # Tracked paths that differ from origin/main - the real question.
        try:
            differs = set(_out("diff", "--name-only", f"origin/{BRANCH}", "--",
                               repo=repo).splitlines()) if origin else {p for _x, p in dirty}
        except RuntimeError:
            differs = {p for _x, p in dirty}
        untracked = {p for xy, p in dirty if xy.strip() == "??"}
        foreign, owned, already_origin = [], [], []
        for xy, p in dirty:
            if is_runner_owned(p):
                owned.append(p)
            elif p in differs or p in untracked:
                foreign.append(p)
            else:
                already_origin.append(p)     # dirty vs HEAD, identical to origin
        # An append-only log with rows origin has not got is not dirt to clear:
        # it is data with no way home until a write tool exists. Name it.
        for p in list(foreign):
            if p in APPEND_ONLY:
                counts = _lines_ahead(p, repo)
                if counts and counts[0]:
                    res["problems"].append(
                        f"{p} has {counts[0]} line(s) this clone holds and origin does not "
                        f"(the VM's own appends, e.g. log_predictions). Copy them into the "
                        f"repo from the Mac and push - never reset this file.")
                    foreign.remove(p)

        if ahead:
            res["problems"].append(f"clone is {ahead} commit(s) AHEAD of origin/{BRANCH} - "
                                   f"the runner never commits; someone did by hand. Refusing.")
        if foreign:
            res["problems"].append(f"clone has non-runner changes: {foreign[:10]} - "
                                   f"refusing to run on a tree that is not origin's.")
        if already_origin:
            res["warnings"].append(f"{already_origin[:10]} differ from this clone's HEAD but "
                                   f"already match origin/{BRANCH} - reset before the pull, "
                                   f"which restores the same content.")
        if behind and not ahead and not res["problems"]:
            for p in already_origin:
                _out("checkout", "--", p, repo=repo)
            upstream = set(_out("diff", "--name-only", "HEAD", f"origin/{BRANCH}",
                                repo=repo).splitlines())
            clash = [p for p in owned if p in upstream]
            if clash:
                stamp = _dt.datetime.now(_dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
                for p in clash:
                    src = os.path.join(repo, p)
                    if os.path.isfile(src):
                        dst = os.path.join(BACKUP_DIR, stamp, p)
                        os.makedirs(os.path.dirname(dst), exist_ok=True)
                        shutil.copy2(src, dst)
                        res["backed_up"].append(f"{p} -> {dst}")
                    tracked = _git("ls-files", "--error-unmatch", p, repo=repo).returncode == 0
                    if tracked:
                        _out("checkout", "--", p, repo=repo)
                    elif os.path.isfile(src):
                        os.remove(src)
            m = _git("merge", "--ff-only", f"origin/{BRANCH}", timeout=60, repo=repo)
            if m.returncode != 0:
                res["problems"].append(f"fast-forward failed: {m.stderr.strip()[:400]}")
            else:
                res["pulled"] = True
                changed = upstream
                stale = sorted(set(SERVER_FILES) & changed)
                if stale:
                    res["warnings"].append(
                        f"pulled changes to {stale} - the RUNNING server still has the old "
                        f"code for its tool definitions until fpl-mcp-http is restarted "
                        f"(scripts it runs are fresh).")
        new_head = _out("rev-parse", "HEAD", repo=repo)
        if STARTED_HEAD and repo == HERE and new_head != STARTED_HEAD:
            changed = set(_out("diff", "--name-only", STARTED_HEAD, new_head, repo=repo).splitlines())
            stale = sorted(set(SERVER_FILES) & changed)
            if stale and not any("RUNNING server" in w for w in res["warnings"]):
                res["warnings"].append(f"server process started at {STARTED_HEAD[:7]}; "
                                       f"{stale} changed since - restart fpl-mcp-http.")
        behind_now = int(_out("rev-list", "--count", f"HEAD..origin/{BRANCH}", repo=repo)) \
            if origin else 0
        if behind_now:
            res["problems"].append(f"clone is still {behind_now} commit(s) behind origin/{BRANCH}.")
        res.update(head=new_head, origin=origin, ahead=ahead, behind=behind_now,
                   dirty_runner_owned=[p for _xy, p in _dirty(repo) if is_runner_owned(p)],
                   ok=not res["problems"])
        return res


# ----------------------------------------------------------------- context
def window_stamp(repo=None):
    try:
        with open(os.path.join(repo or HERE, "fixture_window.json"), encoding="utf-8") as fh:
            w = json.load(fh)
        return {"generated_for_gw": w.get("generated_for_gw"), "horizon": w.get("horizon"),
                "gw_weights": w.get("gw_weights"), "generated_utc": w.get("generated_utc")}
    except Exception as e:
        return {"generated_for_gw": None, "error": str(e)}


def window_problem(stamp, live_gw, weights=None):
    """None when the window is usable; otherwise the reason to refuse."""
    want = list(constants.FIXTURE_GW_WEIGHTS if weights is None else weights)
    if live_gw is None:
        return "live gameweek unknown (bootstrap-static unreachable) - cannot judge the window."
    if stamp.get("generated_for_gw") is None:
        return f"no readable fixture_window.json ({stamp.get('error', 'no stamp')})."
    if stamp["generated_for_gw"] != live_gw:
        return (f"fixture window is stamped GW{stamp['generated_for_gw']} but the live GW is "
                f"GW{live_gw} - call refresh_fixture_window() first.")
    got = stamp.get("gw_weights")
    if not got or len(got) != len(want) or any(abs(a - b) > 1e-9 for a, b in zip(got, want)):
        return (f"fixture window was built with GW weights {got or 'equal'}, the optimiser "
                f"uses {want} - call refresh_fixture_window() first.")
    return None


def alarms(stderr):
    return [ln.strip() for ln in stderr.splitlines()
            if ln.strip().startswith(ALARM_PREFIXES)]


def header(tool, sync, stamp, live_gw, settings=None):
    h = stamp.get("horizon") or 4
    wts = stamp.get("gw_weights")
    win = (f"GW{stamp['generated_for_gw']}-{stamp['generated_for_gw'] + h - 1} "
           f"(stamped GW{stamp['generated_for_gw']}, GW weights "
           f"{'/'.join(f'{x * 100:g}' for x in wts) if wts else 'equal'}, "
           f"{stamp.get('generated_utc')})"
           if stamp.get("generated_for_gw") else "NO WINDOW")
    lines = [f"=== {tool} · fpl-research VM runner ===",
             f"repo HEAD {(sync.get('head') or '?')[:7]} · origin/{BRANCH} "
             f"{(sync.get('origin') or '?')[:7]} · behind {sync.get('behind')} · "
             f"{'clean' if not sync.get('dirty_runner_owned') else 'runner-owned dirty: ' + ', '.join(sync['dirty_runner_owned'][:5])}",
             f"window {win} · live GW{live_gw}"]
    if settings:
        lines.append(settings)
    for w in sync.get("warnings", []):
        lines.append(f"REPO WARNING: {w}")
    for b in sync.get("backed_up", []):
        lines.append(f"REPO: runner-owned file reset to origin, backup kept: {b}")
    return "\n".join(lines)


def refusal(tool, sync, stamp, live_gw, reasons):
    return (header(tool, sync, stamp, live_gw) + "\n\nREFUSED - nothing was run:\n"
            + "\n".join(f"  - {r}" for r in reasons))


# ------------------------------------------------------------------ scripts
def run_script(args, timeout=240, stdin=None, want_json=False, repo=None):
    """Run a repo script with the server's own interpreter. Returns a dict with
    returncode, stdout, stderr (verbatim), seconds and, with want_json, the
    parsed --json payload (None if the script exited before writing it)."""
    repo = repo or HERE
    tmp = None
    argv = [PY, *args]
    if want_json:
        fd, tmp = tempfile.mkstemp(prefix="fplrun-", suffix=".json")
        os.close(fd)
        os.remove(tmp)
        argv += ["--json", tmp]
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONDONTWRITEBYTECODE="1")
    t0 = time.monotonic()
    try:
        p = subprocess.run(argv, cwd=repo, capture_output=True, text=True,
                           timeout=timeout, input=stdin, env=env)
        rc, so, se = p.returncode, p.stdout, p.stderr
    except subprocess.TimeoutExpired as e:
        rc, so, se = -1, _txt(e.stdout), _txt(e.stderr) + f"\nTIMED OUT after {timeout}s"
    data = None
    if tmp and os.path.exists(tmp):
        try:
            with open(tmp, encoding="utf-8") as fh:
                data = json.load(fh)
        finally:
            os.remove(tmp)
    return {"argv": args, "returncode": rc, "stdout": so, "stderr": se,
            "seconds": round(time.monotonic() - t0, 1), "json": data}


def _txt(b):
    if b is None:
        return ""
    return b.decode("utf-8", "replace") if isinstance(b, bytes) else b


def _pins(flag, pins):
    out = []
    for p in pins or []:
        if ":" not in p:
            raise ValueError(f"{flag} entry {p!r} must be Name:TEAM")
        out += [flag, p]
    return out


def optimiser_args(transfers=1, hits=False, estimator="shrunk", intel=True,
                   quarantine=True, fixtures=True, haaland=True,
                   max_attackers_per_club=2, free_transfers=None, gate=None,
                   force_in=(), force_out=(), role_rivals=(), allow_contaminated=False,
                   budget=None, stp_estimator="shrunk", start_weighted=True):
    """optimise_squad.py argv for one configuration. Raises ValueError on a
    combination the script would reject, so the tool can refuse up front.

    `hits` is informational in the script: every k up to `transfers` is shown
    with its hit cost. hits=False with transfers above the free allowance is
    refused rather than silently priced as a hit."""
    if estimator not in ("prior", "raw", "shrunk"):
        raise ValueError(f"estimator must be prior/raw/shrunk, got {estimator!r}")
    if quarantine and not intel:
        raise ValueError("quarantine layers ON TOP of the ROLE_INTEL fence; it needs intel=True")
    if transfers is None and (force_in or force_out):
        raise ValueError("force_in/force_out need transfers=N (rebuild mode has no squad to pin)")
    if budget is not None and transfers is not None:
        raise ValueError("budget applies to wildcard/rebuild mode (transfers=None) only - "
                         "transfer mode always spends sale proceeds plus the bank")
    free = 1 if free_transfers is None else int(free_transfers)
    if transfers is not None and not hits and int(transfers) > free:
        raise ValueError(f"transfers={transfers} exceeds free_transfers={free} and hits=False - "
                         f"pass hits=True to price the -4s, or free_transfers=N if banked.")
    if stp_estimator not in ("prior", "shrunk"):
        raise ValueError(f"stp_estimator must be prior/shrunk, got {stp_estimator!r}")
    # Always explicit, so a response never depends on the script's own default.
    a = ["optimise_squad.py", "--estimator", estimator, "--stp-estimator", stp_estimator]
    a.append("--start-weighted" if start_weighted else "--per90")   # always explicit
    if fixtures:
        a.append("--fixtures")
    if not intel:
        a.append("--no-intel")
    if quarantine:
        a.append("--quarantine")
    if not haaland:
        a.append("--no-haaland")
    if budget is not None:
        a += ["--budget", f"{float(budget):.1f}"]
    if max_attackers_per_club is None:
        a.append("--no-max-attackers-per-club")
    elif int(max_attackers_per_club) != 2:
        a += ["--max-attackers-per-club", str(int(max_attackers_per_club))]
    if gate is not None:
        a += ["--gate", str(float(gate))]
    if allow_contaminated:
        a.append("--allow-contaminated")
    for group in role_rivals or []:
        if isinstance(group, (list, tuple)):
            group = ",".join(group)
        a += ["--role-rivals", group]
    if transfers is not None:
        a += ["--transfers", str(int(transfers))]
        if free_transfers is not None:
            a += ["--free-transfers", str(free)]
        a += _pins("--force-in", force_in) + _pins("--force-out", force_out)
    return a


# ---------------------------------------------------------------- vetting
def vet_players(players):
    """(errors, warnings) for every player a result would have Sylvan BUY/own."""
    errors, warnings = [], []
    for p in players:
        tag = f"{p.get('name')}|{p.get('team')}"
        if p.get("contaminated"):
            errors.append(f"{tag} is a CONTAMINATED prior (Tier 1) - his rates describe "
                          f"the club he left.")
        if p.get("status") in UNAVAILABLE_STATUSES:
            errors.append(f"{tag} has live status '{p['status']}' "
                          f"(chance {p.get('chance')}) - unavailable.")
        elif p.get("ok") is False:
            errors.append(f"{tag} fails gate 3 (ok=False: hand list or low-chance 'd').")
        elif p.get("status") in ("d", "s"):
            warnings.append(f"{tag} has live status '{p['status']}' (chance "
                            f"{p.get('chance')}) - selectable, check before acting.")
        elif p.get("status") is None:
            warnings.append(f"{tag} has no live status (bootstrap fetch failed?).")
    return errors, warnings


def assess(result):
    """Vet a parsed optimise/scenario JSON in place. Returns (errors, warnings)."""
    errors, warnings = [], []
    if not result:
        return ["the script produced no structured result (it exited early - see stderr)."], []
    if result.get("mode") == "transfers":
        for rec in result.get("transfers", []):
            if rec.get("verdict") != "MOVE":
                continue
            e, w = vet_players(rec.get("in", []))
            if e:
                rec["verdict"] = "ERROR_FLAGGED_PLAYER"
                rec["errors"] = e
            errors += [f"{rec['k']} transfer(s): {x}" for x in e]
            warnings += [f"{rec['k']} transfer(s): {x}" for x in w]
    elif result.get("mode") == "rebuild":
        e, w = vet_players(result.get("xi", []) + result.get("bench", []))
        errors += e
        warnings += w
    return errors, warnings


def verdict_lines(result):
    lines = []
    if not result:
        return lines
    # A0.5: *_xp90-named fields hold xP per gameweek when the run was start-weighted.
    u = ((result.get("meta") or {}).get("unit")) or "xP/90"
    if result.get("mode") == "transfers":
        lines.append(f"current XI {u} {result.get('current_xi_xp')} · bank "
                     f"£{result.get('bank')}m · free transfers {result.get('free_transfers')}")
        for rec in result.get("transfers", []):
            k, v = rec["k"], rec.get("verdict")
            if v == "MOVE":
                cost = f" (hit -{rec['hits']})" if rec.get("hits") else " (free)"
                outs = [p["name"] for p in rec["out"]]
                ins = [p["name"] for p in rec["in"]]
                lines.append(
                    f"  {k} transfer(s): MOVE +{rec['gain_xp90']:.2f} {u}{cost}"
                    f" · OUT {outs} -> IN {ins}"
                    f" · 5-GW net {rec['net_5gw']:+.1f} · breakeven {rec['breakeven_gws']} GW"
                    f" · bank after £{rec['bank_after']:.1f}m")
            elif v == "HOLD":
                lines.append(f"  {k} transfer(s): HOLD (no gain above {MIN_GAIN} {u}"
                             + (f"; tie between OUT {[p['name'] for p in rec['out']]} and "
                                f"IN {[p['name'] for p in rec['in']]} - not resolved)"
                                if rec.get("in") else ")"))
            elif v == "ERROR_FLAGGED_PLAYER":
                lines.append(f"  {k} transfer(s): ERROR - recommendation names a flagged "
                             f"player, not returned as advice: {rec.get('errors')}")
            else:
                lines.append(f"  {k} transfer(s): {v}")
    elif result.get("mode") == "rebuild":
        lines.append(f"REBUILD (wildcard) XI {u} {result.get('xi_xp')} · squad "
                     f"£{result.get('squad_cost')}m")
        lines.append("  XI:    " + ", ".join(f"{p['name']}({p['pos']},{p['team']})"
                                            for p in result.get("xi", [])))
        lines.append("  bench: " + ", ".join(f"{p['name']}({p['pos']},{p['team']})"
                                            for p in result.get("bench", [])))
    pc = result.get("preference_costs") or {}
    for key, label in (("no_haaland", "no Haaland"),
                       ("max_attackers_per_club", "max attackers/club")):
        c = pc.get(key)
        if c is None:
            lines.append(f"PREFERENCE COST {label}: not reported")
        elif not c.get("active"):
            lines.append(f"PREFERENCE COST {label}: not active this run")
        else:
            lines.append(f"PREFERENCE COST {label}: {c.get('cost_xp90')} {u}")
    return lines


def settings_line(meta, quarantine_requested=None):
    if not meta:
        return None
    prefs = meta.get("preferences", {})
    q = meta.get("quarantine")
    qtxt = (f"ON ({meta.get('quarantine_entries', 0)} ticked item(s))" if q
            else ("REQUESTED BUT NOT ACTIVE" if quarantine_requested else "OFF"))
    intel = meta.get("intel", meta.get("base_intel"))
    return (f"objective {'START-WEIGHTED xP/GW' if meta.get('objective') == 'per_gw' else 'xP/90'} · "
            f"estimator {meta.get('estimator')} · start rate {meta.get('stp_estimator', '?')} · "
            f"intel {'ON' if intel else 'OFF'} · "
            f"quarantine {qtxt} · fixtures {'ON' if meta.get('fixtures') else 'OFF'} · "
            f"no Haaland {'ON' if prefs.get('no_haaland') else 'OFF'} · max attackers/club "
            f"{prefs.get('max_attackers_per_club') or 'OFF'} · contaminated "
            f"{'ADMITTED' if meta.get('allow_contaminated') else 'excluded'}")


def render(tool, sync, stamp, live_gw, run, extra_top=(), quarantine_requested=None,
           verbose=True):
    """The standard response body: header, verdict, errors, alarms, stderr, stdout, JSON.

    verbose=False drops the three bulk blocks - verbatim stderr, the script's
    own output and the JSON - which are most of the response (a transfer run is
    ~16k characters, ~4k tokens, and ~13k of that is those blocks). What it
    NEVER drops is the header, the verdict, ERRORS, WARNINGS and the LIVE-DATA
    lines lifted from stderr: the rule that a live-fetch failure or a flagged
    player cannot be hidden is not a verbosity setting. The response says what
    was omitted and how to get it."""
    data = run.get("json")
    errors, warnings = assess(data)
    if run["returncode"] != 0:
        errors.insert(0, f"script exited {run['returncode']} - output below is not a result.")
    stderr = run["stderr"]
    if "QUARANTINE UNAVAILABLE" in stderr:
        errors.insert(0, "quarantine=True but Trello could not be read, so nothing was run. "
                         "Put TRELLO_API_KEY/TRELLO_TOKEN in /etc/fpl-mcp/runner.env on the "
                         "VM, or pass quarantine=False for an explicitly fence-only comparison.")
    if "LIVE FETCH:" in stderr:
        errors.insert(0, "LIVE FETCH FAILED - prices, clubs, status and raw/shrunk rates fell "
                         "back to the frozen snapshot. Do not act on this run.")
    parts = [header(tool, sync, stamp, live_gw,
                    settings_line((data or {}).get("meta"), quarantine_requested))]
    parts += list(extra_top)
    parts.append(f"ran: {' '.join(run['argv'])}  ({run['seconds']}s, exit {run['returncode']})")
    if data and data.get("hypothetical"):
        parts.append("SCENARIO — HYPOTHETICAL, NOT A RECOMMENDATION")
    parts += ["", "\n".join(verdict_lines(data))]
    if errors:
        parts += ["", "ERRORS (the result is not advice until these are resolved):"]
        parts += [f"  - {e}" for e in errors]
    if warnings:
        parts += ["", "WARNINGS:"] + [f"  - {w}" for w in warnings]
    al = alarms(stderr)
    if al:
        parts += ["", "LIVE-DATA LINES (from stderr):"] + [f"  {a}" for a in al]
    if not verbose:
        parts += ["", f"(verbose=False: verbatim stderr ({len(stderr)} chars), the script's own "
                      f"output ({len(run['stdout'])} chars) and the JSON omitted. Every error, "
                      f"warning and live-data line above is still complete. Call again with "
                      f"verbose=True for the full record.)"]
        return "\n".join(parts)
    parts += ["", "--- stderr (verbatim) ---", stderr.rstrip() or "(empty)",
              "", "--- script output ---", run["stdout"].rstrip() or "(empty)"]
    if data is not None:
        parts += ["", "--- structured result (JSON) ---",
                  json.dumps({"errors": errors, "warnings": warnings, "head": sync.get("head"),
                              "window": stamp, "live_gw": live_gw, **data},
                             indent=1, ensure_ascii=False, default=list)]
    return "\n".join(parts)


# ------------------------------------------------------------- scenario rows
def validate_rows(rows):
    """9-field ROLE_INTEL-shaped rows, as strings or dicts. Returns the text lines."""
    fields = ("player", "team", "field", "op", "value", "gws", "confidence", "date", "why")
    out = []
    for i, r in enumerate(rows or []):
        if isinstance(r, dict):
            missing = [f for f in fields if f not in r]
            if missing:
                raise ValueError(f"row {i}: missing {missing}")
            r = " | ".join(str(r[f]) for f in fields)
        if "\n" in r:
            raise ValueError(f"row {i}: one row per entry, no newlines")
        parts = [p.strip() for p in r.split("|")]
        if len(parts) != 9:
            raise ValueError(f"row {i}: expected 9 fields "
                             f"(player|team|field|op|value|gws|confidence|date|why), got {len(parts)}")
        if parts[3] not in ("set", "mult"):
            raise ValueError(f"row {i}: op must be set or mult, got {parts[3]!r}")
        float(parts[4])
        out.append(" | ".join(parts))
    if not out:
        raise ValueError("no scenario rows given")
    return out


# ------------------------------------------------------------------ files
def resolve_allowed(path, repo=None):
    """Absolute path for an allow-listed repo file, or raise ValueError."""
    repo = os.path.realpath(repo or HERE)

    def allowed(rel):
        return rel in ALLOWED_FILES or any(
            fnmatch.fnmatch(rel, g) and rel.count("/") == g.count("/") for g in ALLOWED_GLOBS)

    rel = os.path.normpath(str(path).strip().lstrip("/"))
    if rel.startswith("..") or os.path.isabs(rel):
        raise ValueError(f"{path!r} is outside the repo")
    if not allowed(rel):
        raise ValueError(f"{path!r} is not allow-listed. Allowed: {list(ALLOWED_FILES)} "
                         f"and {list(ALLOWED_GLOBS)}")
    full = os.path.realpath(os.path.join(repo, rel))
    # The resolved target must itself be allow-listed: a symlink named like an
    # allowed file must not reach any other file, inside the repo or out.
    if not full.startswith(repo + os.sep) or not allowed(os.path.relpath(full, repo)):
        raise ValueError(f"{path!r} resolves to a file outside the allow-list")
    return full


def list_allowed(repo=None):
    repo = repo or HERE
    found = [f for f in ALLOWED_FILES if os.path.isfile(os.path.join(repo, f))]
    for g in ALLOWED_GLOBS:
        d = os.path.join(repo, os.path.dirname(g))
        if os.path.isdir(d):
            found += sorted(os.path.join(os.path.dirname(g), n) for n in os.listdir(d)
                            if fnmatch.fnmatch(n, os.path.basename(g)))
    return found


# ------------------------------------------------------------------- jobs
_jobs = {}
_jobs_lock = threading.Lock()


def _job_path(job_id):
    return os.path.join(JOBS_DIR, f"{job_id}.json")


def _save_job(job):
    os.makedirs(JOBS_DIR, exist_ok=True)
    tmp = _job_path(job["id"]) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(job, fh, indent=1, ensure_ascii=False, default=list)
    os.replace(tmp, _job_path(job["id"]))


def get_job(job_id):
    with _jobs_lock:
        if job_id in _jobs:
            return json.loads(json.dumps(_jobs[job_id], default=list))
    try:
        with open(_job_path(os.path.basename(job_id)), encoding="utf-8") as fh:
            job = json.load(fh)
    except (OSError, ValueError):
        return None
    if job.get("state") == "running":
        # On disk but not in this process: the server restarted mid-job.
        job["state"] = "interrupted (server restarted) - re-run optimise_matrix"
    return job


def matrix_cells(estimators, overlays, transfers, extra_rows):
    cells = []
    for est in estimators:
        for ov in overlays:
            if ov not in ("fence", "quarantine", "nointel"):
                raise ValueError(f"overlay must be fence/quarantine/nointel, got {ov!r}")
            for t in transfers:
                cells.append({"estimator": est, "overlay": ov, "transfers": int(t)})
        if extra_rows:
            for t in transfers:
                cells.append({"estimator": est, "overlay": "scenario", "transfers": int(t)})
    return cells


def _cell_args(cell, scenario_path, free_transfers):
    t = cell["transfers"]
    ft = free_transfers if free_transfers is not None else 1
    if cell["overlay"] == "scenario":
        a = ["scenario_squad.py", scenario_path, "--estimator", cell["estimator"],
             "--stp-estimator", cell.get("stp", "shrunk"), "--fixtures", "--transfers", str(t)]
        if free_transfers is not None:
            a += ["--free-transfers", str(ft)]
        return a
    return optimiser_args(transfers=t, hits=True, estimator=cell["estimator"],
                          intel=cell["overlay"] != "nointel",
                          quarantine=cell["overlay"] == "quarantine",
                          free_transfers=free_transfers, stp_estimator=cell.get("stp", "shrunk"))


def run_matrix_job(job, scenario_rows=None, free_transfers=None, workers=2):
    """Runs every cell (two at a time - the VM has two cores) and stores each
    cell's verdict. Called on a background thread by start_matrix()."""
    scen = None
    try:
        if scenario_rows:
            fd, scen = tempfile.mkstemp(prefix="fplscen-", suffix=".txt")
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write("# matrix extra_rows - HYPOTHETICAL\n" + "\n".join(scenario_rows) + "\n")
        cells = job["cells"]

        def work(i):
            cell = cells[i]
            run = run_script(_cell_args(cell, scen, free_transfers), want_json=True)
            errors, warnings = assess(run["json"])
            if run["returncode"] != 0:
                errors.insert(0, f"exit {run['returncode']}: "
                                 f"{(run['stderr'].strip().splitlines() or [''])[-1][:300]}")
            if "LIVE FETCH:" in run["stderr"]:
                errors.insert(0, "LIVE FETCH FAILED")
            with _jobs_lock:
                cell.update(state="done", seconds=run["seconds"], errors=errors,
                            warnings=warnings, result=run["json"],
                            alarms=alarms(run["stderr"]))
                _save_job(job)

        idx = list(range(len(cells)))
        lock = threading.Lock()

        def worker():
            while True:
                with lock:
                    if not idx:
                        return
                    i = idx.pop(0)
                try:
                    work(i)
                except Exception as e:     # one bad cell must not kill the grid
                    with _jobs_lock:
                        cells[i].update(state="done", errors=[f"runner error: {e}"])
        threads = [threading.Thread(target=worker, daemon=True) for _ in range(max(1, workers))]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        with _jobs_lock:
            job["state"] = "done"
    except Exception as e:
        with _jobs_lock:
            job.update(state="failed", error=str(e))
    finally:
        if scen and os.path.exists(scen):
            os.remove(scen)
        with _jobs_lock:
            job["finished_utc"] = _dt.datetime.now(_dt.timezone.utc).isoformat()[:19]
            _save_job(job)


def start_matrix(cells, context, scenario_rows=None, free_transfers=None):
    job = {"id": "mx-" + uuid.uuid4().hex[:10], "state": "running", "context": context,
           "started_utc": _dt.datetime.now(_dt.timezone.utc).isoformat()[:19],
           "cells": [dict(c, state="queued") for c in cells]}
    with _jobs_lock:
        _jobs[job["id"]] = job
        _save_job(job)
    threading.Thread(target=run_matrix_job, args=(job, scenario_rows, free_transfers),
                     daemon=True).start()
    return job["id"]


def matrix_table(job):
    rows = [f"{'est.':<9}{'overlay':<11}{'T':<3}{'verdict':<22}{'gain':>6}  "
            f"{'5-GW net':>8}  {'bank':>5}  move / notes"]
    for c in job["cells"]:
        if c.get("state") != "done":
            rows.append(f"{c['estimator']:<9}{c['overlay']:<11}{c['transfers']:<3}{c.get('state')}")
            continue
        res = c.get("result") or {}
        recs = [r for r in res.get("transfers", []) if r.get("k") == c["transfers"]]
        rec = recs[0] if recs else {}
        v = rec.get("verdict", "NO RESULT")
        move = (f"OUT {[p['name'] for p in rec.get('out', [])]} -> IN "
                f"{[p['name'] for p in rec.get('in', [])]}" if rec.get("in") else "")
        notes = "; ".join((c.get("errors") or [])[:2])
        rows.append(f"{c['estimator']:<9}{c['overlay']:<11}{c['transfers']:<3}{v:<22}"
                    f"{rec.get('gain_xp90', 0):>6.2f}  {rec.get('net_5gw', 0):>+8.1f}  "
                    f"{rec.get('bank_after', 0):>5.1f}  {move}"
                    + (f"  !! {notes}" if notes else ""))
    return "\n".join(rows)


# --------------------------------------------------------------- MCP tools
def register(mcp, live_gw, fixture_table):
    """Add the runner tools to the server. live_gw() -> int|None (the live next
    GW from the server's own bootstrap cache); fixture_table(next_n) -> the
    fixture_difficulty text table fixture_adjust.py --update parses."""
    global STARTED_HEAD
    try:
        STARTED_HEAD = _out("rev-parse", "HEAD")
    except Exception:
        STARTED_HEAD = None

    def _gw():
        try:
            return live_gw()
        except Exception:
            return None

    def _pre(tool, need_window=True):
        """Sync + window check. Returns (sync, stamp, gw, refusal_text|None)."""
        stamp, gw = window_stamp(), _gw()
        try:
            sync = repo_sync()
        except Exception as e:           # git itself broken: refuse, never run blind
            sync = {"head": None, "problems": [f"repo_sync failed: {e}"], "warnings": []}
            return sync, stamp, gw, refusal(tool, sync, stamp, gw, sync["problems"])
        reasons = list(sync["problems"])
        if need_window:
            wp = window_problem(stamp, gw)
            if wp:
                reasons.append(wp)
        return sync, stamp, gw, (refusal(tool, sync, stamp, gw, reasons) if reasons else None)

    async def _thread(fn, *a, **kw):
        return await asyncio.to_thread(fn, *a, **kw)

    # Inner names end in _tool where they would otherwise shadow a module-level
    # function _pre() calls (repo_sync, squad_state) - a closure would pick up
    # the async tool instead.
    @mcp.tool(name="repo_sync", description=(
        "VM runner: fetch + fast-forward-only pull of the VM's repo clone. Returns HEAD, "
        "ahead/behind origin/main, and dirty files. Every other runner tool calls this "
        "first and refuses on a clone that is ahead, diverged or has non-runner changes. "
        "Never commits or pushes."))
    async def repo_sync_tool() -> str:
        def go():
            s = repo_sync()
            return (header("repo_sync", s, window_stamp(), _gw()) + "\n\n"
                    + ("OK" if s["ok"] else "PROBLEMS:\n" + "\n".join(f"  - {p}" for p in s["problems"]))
                    + f"\npulled this call: {s['pulled']}\n"
                    + json.dumps(s, indent=1))
        return await _thread(go)

    @mcp.tool(name="refresh_fixture_window", description=(
        "VM runner: regenerate fixture_window.json from fixture_difficulty(next_n=4) and "
        "stamp it with the live next gameweek (fixture_adjust.py --update --gw N), "
        "replacing the paste-the-table step. gw defaults to the live next GW and may "
        "only equal it: the table always starts at the live GW, so any other stamp "
        "would be a lie. Returns the stamp and the 20 rows."))
    async def refresh_fixture_window(gw: int | None = None) -> str:
        def go():
            sync, stamp, live, refused = _pre("refresh_fixture_window", need_window=False)
            if refused:
                return refused
            if live is None:
                return refusal("refresh_fixture_window", sync, stamp, live,
                               ["live gameweek unknown - bootstrap-static unreachable."])
            if gw is not None and int(gw) != live:
                return refusal("refresh_fixture_window", sync, stamp, live,
                               [f"gw={gw} but the live next GW is {live}; fixture_difficulty "
                                f"always starts at the live GW."])
            table = fixture_table(4)
            with _repo_lock:
                run = run_script(["fixture_adjust.py", "--update", "--gw", str(live)],
                                 stdin=table, timeout=60)
            new = window_stamp()
            rows = [ln for ln in table.splitlines()
                    if len(ln.split()) >= 4 and ln.split()[0].isalpha()
                    and ln.split()[0].isupper() and len(ln.split()[0]) == 3]
            return "\n".join([
                header("refresh_fixture_window", repo_sync(fetch=False), new, live),
                f"was: {stamp}", f"now: {new}",
                f"fixture_adjust.py exit {run['returncode']}",
                run["stdout"].rstrip(), run["stderr"].rstrip(),
                "", "--- fixture_difficulty(next_n=4) ---", table.rstrip(),
                "", f"({len(rows)} team rows)"])
        return await _thread(go)

    @mcp.tool(name="optimise_transfers", description=(
        "VM runner: the weekly transfer optimisation (optimise_squad.py) with no Mac. "
        "Defaults are the weekly configuration: estimator shrunk, ROLE_INTEL intel ON, "
        "Trello quarantine ON (fails loudly if Trello is unreachable), fixture window ON, "
        "max 2 attackers/club, Haaland allowed (haaland=False excludes him) - state these "
        "before running. transfers=None is wildcard/rebuild mode, budgeted at the squad's "
        "selling value plus the bank (budget=100.0 overrides, for comparison only). force_in/force_out/role_rivals take 'Name:TEAM' "
        "strings (role_rivals: one comma-joined group per string). hits=False refuses "
        "transfers above free_transfers. Refuses if the repo clone is not origin's or "
        "the window stamp is not the live GW. Returns the verdict per move count (MOVE / "
        "HOLD - ties are HOLD, never resolved), 5-GW net, breakeven, bank after, both "
        "preference costs, live-data stderr lines verbatim, the script text and JSON. A "
        "move naming an unavailable or contaminated player is returned as an ERROR. "
        "The objective is START-WEIGHTED by default since 16 Sep 2026 (roadmap A0.5): stp x "
        "xP per GAMEWEEK with a 50% XI floor; start_weighted=False gives the old xP/90 behind "
        "a 75% gate - figures are not comparable across the two. "
        "Start rate is shrunk by default (2025/26 last-16 blended with 2026/27 starts per "
        "team match, roadmap A0.2, since GW5); stp_estimator='prior' to compare. It moves "
        "the 75% XI / 60% bench gates, not xP. "
        "verbose=False returns the header, verdict, errors, warnings and live-data lines only, "
        "dropping the verbatim stderr, script output and JSON (about four fifths of the reply); "
        "nothing that could hide a bad run is dropped."))
    async def optimise_transfers(transfers: int | None = 1, hits: bool = False,
                                 estimator: str = "shrunk", intel: bool = True,
                                 quarantine: bool = True, fixtures: bool = True,
                                 haaland: bool = True, max_attackers_per_club: int | None = 2,
                                 free_transfers: int | None = None, gate: float | None = None,
                                 force_in: list[str] | None = None,
                                 force_out: list[str] | None = None,
                                 role_rivals: list[str] | None = None,
                                 allow_contaminated: bool = False,
                                 budget: float | None = None,
                                 stp_estimator: str = "shrunk",
                                 start_weighted: bool = True,
                                 verbose: bool = True) -> str:
        def go():
            sync, stamp, live, refused = _pre("optimise_transfers", need_window=fixtures)
            if refused:
                return refused
            try:
                args = optimiser_args(transfers, hits, estimator, intel, quarantine, fixtures,
                                      haaland, max_attackers_per_club, free_transfers, gate,
                                      force_in, force_out, role_rivals, allow_contaminated,
                                      budget, stp_estimator, start_weighted)
            except ValueError as e:
                return refusal("optimise_transfers", sync, stamp, live, [str(e)])
            run = run_script(args, want_json=True)
            top = []
            if not fixtures:
                top.append("NOTE: fixtures=False - scored on flat xP, not the weekly xP_adj objective.")
            if estimator != "shrunk" or not intel or not quarantine:
                top.append("NOTE: not the weekly configuration (shrunk + intel + quarantine) - "
                           "a comparison, not the answer.")
            return render("optimise_transfers", sync, stamp, live, run, top, quarantine,
                          verbose=verbose)
        return await _thread(go)

    @mcp.tool(name="optimise_scenario", description=(
        "VM runner: a HYPOTHETICAL what-if (scenario_squad.py) - rows are ROLE_INTEL-shaped "
        "'player|team|field|op|value|gws|confidence|date|why' strings (op set on stp, mult "
        "on xg90/xa90/xgi90/cbit90/cbirt90), stacked on the real fence unless "
        "base_intel=False. Nothing is written to the repo. transfers=None is rebuild "
        "(wildcard) mode, budgeted at selling value plus bank unless budget is given. "
        "Haaland is allowed unless haaland=False. "
        "Output keeps the HYPOTHETICAL banner and the applied/unmatched audit; flagged "
        "players in a result are ERRORS. Same repo/window refusals as optimise_transfers. "
        "verbose=False trims the bulk blocks, as on optimise_transfers."))
    async def optimise_scenario(rows: list[str], transfers: int | None = 1,
                                estimator: str = "shrunk", base_intel: bool = True,
                                fixtures: bool = True, free_transfers: int | None = None,
                                force_in: list[str] | None = None,
                                force_out: list[str] | None = None,
                                haaland: bool = True, budget: float | None = None,
                                stp_estimator: str = "shrunk",
                                start_weighted: bool = True,
                                verbose: bool = True) -> str:
        def go():
            sync, stamp, live, refused = _pre("optimise_scenario", need_window=fixtures)
            if refused:
                return refused
            try:
                lines = validate_rows(rows)
                if estimator not in ("prior", "raw", "shrunk"):
                    raise ValueError(f"estimator must be prior/raw/shrunk, got {estimator!r}")
                if transfers is None and (force_in or force_out):
                    raise ValueError("force_in/force_out need transfers=N")
                if budget is not None and transfers is not None:
                    raise ValueError("budget applies to rebuild mode (transfers=None) only")
                if stp_estimator not in ("prior", "shrunk"):
                    raise ValueError(f"stp_estimator must be prior/shrunk, got {stp_estimator!r}")
                pins = _pins("--force-in", force_in) + _pins("--force-out", force_out)
            except ValueError as e:
                return refusal("optimise_scenario", sync, stamp, live, [str(e)])
            fd, path = tempfile.mkstemp(prefix="fplscen-", suffix=".txt")
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as fh:
                    fh.write("# inline scenario via optimise_scenario - HYPOTHETICAL\n"
                             + "\n".join(lines) + "\n")
                args = ["scenario_squad.py", path, "--estimator", estimator,
                        "--stp-estimator", stp_estimator]
                args.append("--start-weighted" if start_weighted else "--per90")
                if fixtures:
                    args.append("--fixtures")
                if not base_intel:
                    args.append("--no-base-intel")
                if not haaland:
                    args.append("--no-haaland")
                if budget is not None:
                    args += ["--budget", f"{float(budget):.1f}"]
                if transfers is not None:
                    args += ["--transfers", str(int(transfers))]
                    if free_transfers is not None:
                        args += ["--free-transfers", str(int(free_transfers))]
                    args += pins
                run = run_script(args, want_json=True)
            finally:
                os.remove(path)
            top = ["rows sent:"] + [f"  {ln}" for ln in lines]
            return render("optimise_scenario", sync, stamp, live, run, top, verbose=verbose)
        return await _thread(go)

    @mcp.tool(name="optimise_matrix", description=(
        "VM runner: run a grid of optimiser configurations in the BACKGROUND and return a "
        "job id immediately (a 12-run grid takes about a minute; a single MCP call would "
        "time out). estimators x overlays ('fence' = intel, 'quarantine' = intel + ticked "
        "Trello items, 'nointel') x transfers, plus an optional HYPOTHETICAL 'scenario' "
        "overlay per estimator from extra_rows. Poll with optimise_job(job_id)."))
    async def optimise_matrix(estimators: list[str] | None = None,
                              overlays: list[str] | None = None,
                              transfers: list[int] | None = None,
                              extra_rows: list[str] | None = None,
                              free_transfers: int | None = None,
                              stp_estimator: str = "shrunk") -> str:
        def go():
            sync, stamp, live, refused = _pre("optimise_matrix")
            if refused:
                return refused
            try:
                ests = estimators or ["prior", "raw", "shrunk"]
                for e in ests:
                    if e not in ("prior", "raw", "shrunk"):
                        raise ValueError(f"estimator must be prior/raw/shrunk, got {e!r}")
                rows = validate_rows(extra_rows) if extra_rows else None
                if stp_estimator not in ("prior", "shrunk"):
                    raise ValueError(f"stp_estimator must be prior/shrunk, got {stp_estimator!r}")
                cells = [dict(c, stp=stp_estimator) for c in
                         matrix_cells(ests, overlays or ["fence", "quarantine"],
                                      transfers or [1, 2], rows)]
            except ValueError as e:
                return refusal("optimise_matrix", sync, stamp, live, [str(e)])
            ctx = {"head": sync["head"], "window": stamp, "live_gw": live}
            job_id = start_matrix(cells, ctx, rows, free_transfers)
            return (header("optimise_matrix", sync, stamp, live) +
                    f"\n\nSTARTED job {job_id}: {len(cells)} run(s), two at a time. "
                    f"Poll optimise_job(job_id='{job_id}').")
        return await _thread(go)

    @mcp.tool(name="optimise_job", description=(
        "VM runner: status and result table of an optimise_matrix job. Every cell is "
        "vetted like optimise_transfers (flagged players are ERRORS, ties are HOLD). "
        "detail=True appends each cell's JSON."))
    async def optimise_job(job_id: str, detail: bool = False) -> str:
        def go():
            job = get_job(job_id)
            if not job:
                return f"no job {job_id!r} (jobs survive restarts on disk under {JOBS_DIR})."
            done = sum(1 for c in job["cells"] if c.get("state") == "done")
            ctx = job.get("context", {})
            out = [f"=== optimise_job {job['id']} · {job['state']} · {done}/{len(job['cells'])} done ===",
                   f"repo HEAD {str(ctx.get('head'))[:7]} · window {ctx.get('window')} · "
                   f"live GW{ctx.get('live_gw')} · started {job.get('started_utc')}",
                   "weekly defaults per cell: fixtures ON, Haaland allowed, max 2 attackers/club, "
                   "hits priced", "", matrix_table(job)]
            al = sorted({a for c in job["cells"] for a in c.get("alarms", [])})
            if al:
                out += ["", "LIVE-DATA LINES (deduplicated across cells):"] + [f"  {a}" for a in al]
            pcs = [(c["estimator"], c["overlay"], c["transfers"], (c.get("result") or {}).get("preference_costs"))
                   for c in job["cells"] if c.get("result")]
            if pcs:
                out += ["", "PREFERENCE COSTS (xP/90, no Haaland / max attackers/club):"]
                out += [f"  {e:<7}{o:<11}T{t}: "
                        f"{(pc or {}).get('no_haaland', {}).get('cost_xp90')} / "
                        f"{(pc or {}).get('max_attackers_per_club', {}).get('cost_xp90')}"
                        for e, o, t, pc in pcs]
            if job.get("error"):
                out.append(f"\nJOB ERROR: {job['error']}")
            if detail:
                out += ["", json.dumps(job, indent=1, ensure_ascii=False, default=list)]
            return "\n".join(out)
        return await _thread(go)

    @mcp.tool(name="quarantine_report", description=(
        "VM runner: every ticked row item on 'Rows in model' (Live in model) and 'Decisions' (Quarantined decisions) Trello checklists, as "
        "the optimiser would read it (optimise_squad.py --quarantine-report): parsed rows, "
        "what each does vs ROLE_INTEL (NEW / CHANGES / REMOVES / same as fence = no-op / "
        "OUT OF WINDOW / DROPPED), and skipped items with reasons. Never optimises. Needs "
        "TRELLO_API_KEY/TRELLO_TOKEN in the server environment."))
    async def quarantine_report() -> str:
        def go():
            sync, stamp, live, refused = _pre("quarantine_report", need_window=False)
            if refused:
                return refused
            run = run_script(["optimise_squad.py", "--quarantine-report"], timeout=120)
            wp = window_problem(stamp, live)
            return "\n".join([header("quarantine_report", sync, stamp, live),
                              f"WINDOW WARNING: {wp} (in-window checks use this stamp)" if wp else "",
                              f"exit {run['returncode']} ({run['seconds']}s)", "",
                              run["stdout"].rstrip(), "", "--- stderr (verbatim: skipped/unmatched items) ---",
                              run["stderr"].rstrip() or "(empty)"])
        return await _thread(go)

    @mcp.tool(name="intel_report", description=(
        "VM runner: the ROLE_INTEL.md adjustments fence (intel_adjust.py) - every row, then "
        "stp and xP with intel OFF vs ON per affected player, with stale-window and "
        "unmatched-name warnings verbatim."))
    async def intel_report() -> str:
        def go():
            sync, stamp, live, refused = _pre("intel_report", need_window=False)
            if refused:
                return refused
            rows = run_script(["intel_adjust.py"], timeout=60)
            rep = run_script(["intel_adjust.py", "--report"], timeout=120)
            return "\n".join([header("intel_report", sync, stamp, live), "",
                              "--- fence rows ---", rows["stdout"].rstrip(), rows["stderr"].rstrip(),
                              "", "--- intel OFF vs ON ---", rep["stdout"].rstrip(),
                              "", "--- stderr (verbatim) ---", rep["stderr"].rstrip() or "(empty)"])
        return await _thread(go)

    @mcp.tool(name="player_estimates", description=(
        "VM runner: the 'raw, priors, shrunk' view (player_estimates.py). Per player: live "
        "price, status, chance of playing, gate-3 ok flag, contaminated flag, and stp, "
        "xg90, xa90, cbit90, cbirt90, xP_flat and xP_adj under prior / raw / shrunk x intel "
        "on/off. names take 'Name' or 'Name:TEAM'; squad=True adds the fifteen; candidates "
        "adds the top N per position (ok, uncontaminated, XI start gate, not owned). "
        "quarantine=True puts ticked Trello items on the intel-ON columns and fails "
        "loudly without Trello. A diagnostic view, never a selection. verbose=False drops the "
        "verbatim stderr and the JSON, keeping the table and the flagged list."))
    async def player_estimates(names: list[str] | None = None, squad: bool = True,
                               candidates: int = 5, quarantine: bool = True,
                               fixtures: bool = True, verbose: bool = True) -> str:
        def go():
            sync, stamp, live, refused = _pre("player_estimates", need_window=fixtures)
            if refused:
                return refused
            args = ["player_estimates.py", "--candidates", str(int(candidates))]
            if names:
                args += ["--names", ",".join(n.replace(",", " ") for n in names)]
            if squad:
                args.append("--squad")
            if quarantine:
                args.append("--quarantine")
            if not fixtures:
                args.append("--no-fixtures")
            run = run_script(args, want_json=True, timeout=240)
            al = alarms(run["stderr"])
            flagged = [f"{p['name']}|{p['team']} status {p['status']} chance {p['chance']}"
                       + (" CONTAMINATED" if p["contaminated"] else "")
                       for p in (run["json"] or {}).get("players", [])
                       if not p["ok"] or p["contaminated"] or p["status"] in ("d", "s")]
            parts = [header("player_estimates", sync, stamp, live,
                            f"quarantine {'ON' if quarantine else 'OFF'} · fixtures "
                            f"{'ON' if fixtures else 'OFF'}"),
                     f"ran: {' '.join(args)} ({run['seconds']}s, exit {run['returncode']})"]
            if "LIVE FETCH:" in run["stderr"]:
                parts.append("ERROR: LIVE FETCH FAILED - estimates fell back to the frozen snapshot.")
            if flagged:
                parts += ["FLAGGED (unavailable, doubtful, suspended or contaminated):"] + [f"  {f}" for f in flagged]
            if al:
                parts += ["", "LIVE-DATA LINES:"] + [f"  {a}" for a in al]
            parts += ["", run["stdout"].rstrip()]      # the table is the answer here
            if verbose:
                parts += ["", "--- stderr (verbatim) ---", run["stderr"].rstrip() or "(empty)"]
                if run["json"] is not None:
                    parts += ["", "--- structured (JSON) ---",
                              json.dumps(run["json"], indent=1, ensure_ascii=False)]
            else:
                parts += ["", f"(verbose=False: verbatim stderr ({len(run['stderr'])} chars) and "
                              f"the JSON omitted; the flagged list and live-data lines above are "
                              f"complete.)"]
            return "\n".join(parts)
        return await _thread(go)

    @mcp.tool(name="squad_state", description=(
        "VM runner: squad.json from the repo clone, validated by squad_state.py - the "
        "fifteen, roles, bench order, captain/vice, bank, chips, selected_on - plus a live "
        "price column: bought_for vs now_cost, realisable sell price (half of any rise) "
        "and total drift, so a cloud brief never spends a phantom surplus."))
    async def squad_state_tool() -> str:
        def go():
            sync, stamp, live, refused = _pre("squad_state", need_window=False)
            if refused:
                return refused
            run = run_script(["squad_state.py", "--json", "--live"], timeout=60)
            if run["returncode"] != 0:
                return (header("squad_state", sync, stamp, live) + "\n\nsquad.json INVALID:\n"
                        + run["stderr"].rstrip() + run["stdout"].rstrip())
            d = json.loads(run["stdout"])
            lv = d.get("live", {})
            lines = [header("squad_state", sync, stamp, live), "",
                     f"squad.json valid · updated {d['updated_utc']} · GW{d['gameweek']} · "
                     f"{d['formation']} · captain {d['captain']} · vice {d['vice']}",
                     f"bank £{d['bank']:.1f}m · ledger value £{d['value']:.1f}m (bought_for-based)"]
            if "error" in lv:
                lines.append(f"LIVE PRICES UNAVAILABLE: {lv['error']}")
            else:
                gap = round(lv["ledger_value"] - lv["sell_value"], 1)
                lines.append(f"live value £{lv['live_value']:.1f}m · realisable sell value "
                             f"£{lv['sell_value']:.1f}m · ledger minus sell value £{gap:+.1f}m"
                             + ("  <- NOT spendable: do not plan against the ledger" if gap > 0 else ""))
                lines += ["", f"{'role':<7}{'player':<15}{'pos':<4}{'tm':<5}{'bought':>7}"
                              f"{'now':>6}{'sell':>6}{'drift':>6}  st  ch  selected_on"]
                live_by = {p["name"]: p for p in lv["players"]}
                for p in d["xi"] + d["bench"]:
                    L = live_by.get(p["name"], {})
                    role = "XI" if p["role"] == "XI" else f"B{p['bench_order']}"
                    if p["name"] == d["captain"]:
                        role += " C"
                    elif p["name"] == d["vice"]:
                        role += " V"
                    lines.append(f"{role:<7}{p['name'][:14]:<15}{p['pos']:<4}{p['team']:<5}"
                                 f"{p['bought_for']:>7.1f}{_f(L.get('now_cost')):>6}"
                                 f"{_f(L.get('sell_price')):>6}{_f(L.get('drift'), '+'):>6}  "
                                 f"{L.get('status') or '?':<3}{'' if L.get('chance') is None else L['chance']:>3}  "
                                 f"{(p.get('selected_on') or '')[:90]}")
                if lv.get("unmatched"):
                    lines.append(f"UNMATCHED in live data: {lv['unmatched']}")
            lines += ["", f"chips remaining: {d['chips_remaining']}", "",
                      "--- structured (JSON) ---", json.dumps(d, indent=1, ensure_ascii=False)]
            return "\n".join(lines)
        return await _thread(go)

    @mcp.tool(name="repo_file", description=(
        "VM runner: read-only text of one allow-listed repo file: ROLE_INTEL.md, "
        "TEAM_CHANGE_LOG.md, SELECTION_FRAMEWORK.md, METHODOLOGY_ALTERNATIVES.md, "
        "VM_OPTIMISER_TOOLS.md, fixture_window.json, squad.json, scenarios/*.txt, "
        "docs/data/*.json. path='' lists what is available. No globbing outside the list."))
    async def repo_file(path: str = "") -> str:
        def go():
            sync = repo_sync()
            head = f"repo HEAD {sync['head'][:7]} ({'ok' if sync['ok'] else 'NOT ORIGIN: ' + '; '.join(sync['problems'])})"
            if not path:
                return head + "\n\n" + "\n".join(list_allowed())
            try:
                full = resolve_allowed(path)
            except ValueError as e:
                return head + f"\n\nREFUSED: {e}"
            if not os.path.isfile(full):
                return head + f"\n\n{path} does not exist in the clone."
            with open(full, encoding="utf-8", errors="replace") as fh:
                text = fh.read(MAX_FILE_CHARS + 1)
            more = len(text) > MAX_FILE_CHARS
            return (head + f"\n--- {path} ---\n" + text[:MAX_FILE_CHARS]
                    + (f"\n--- TRUNCATED at {MAX_FILE_CHARS} chars ---" if more else ""))
        return await _thread(go)

    @mcp.tool(name="bench_value", description=(
        "VM runner: size_bench_value.py --fixtures - an UPPER BOUND on autosub bench value, "
        "in expected points PER GAMEWEEK. Never add it to an optimiser XI xP/90 figure: "
        "that sum is invalid and reverses reliability upgrades (the unit trap)."))
    async def bench_value() -> str:
        def go():
            sync, stamp, live, refused = _pre("bench_value")
            if refused:
                return refused
            run = run_script(["size_bench_value.py", "--fixtures"], timeout=180)
            return "\n".join([
                header("bench_value", sync, stamp, live),
                "UNIT TRAP: bench value below is xP per GAMEWEEK (start-weighted). The optimiser's "
                "XI figure is xP per 90 (not start-weighted). Adding them is INVALID - see "
                "size_bench_value.py's docstring, 'THE UNIT TRAP'.", "",
                run["stdout"].rstrip(), "", "--- stderr (verbatim) ---", run["stderr"].rstrip() or "(empty)"])
        return await _thread(go)


def _f(v, sign=""):
    if v is None:
        return "?"
    return f"{v:{sign}.1f}"


if __name__ == "__main__":
    if "--sync" in sys.argv:
        s = repo_sync()
        print(json.dumps(s, indent=1))
        sys.exit(0 if s["ok"] else 1)
    print(__doc__)
