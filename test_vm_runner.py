#!/usr/bin/env python3
"""Offline tests for vm_runner.py - no network, no MCP SDK, no PuLP needed.

Covers the rules the VM runner exists to enforce: fast-forward-only sync that
refuses a tree that is not origin's, the repo_file allow-list, scenario row
validation, flag mapping onto optimise_squad.py, the window-stamp refusal, and
flagged-player vetting (a flagged name in a recommendation is an ERROR).

Run:  python3 test_vm_runner.py
"""
import json
import os
import subprocess
import sys
import tempfile

_tmp = tempfile.mkdtemp(prefix="vmrunner-test-")
os.environ["FPL_RUNNER_STATE"] = os.path.join(_tmp, "state")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vm_runner as vr  # noqa: E402

FAILS = []


def check(label, cond, detail=""):
    if cond:
        print(f"  PASS  {label}")
    else:
        print(f"  FAIL  {label}  {detail}")
        FAILS.append(label)


def raises(fn, *a, **kw):
    try:
        fn(*a, **kw)
    except ValueError as e:
        return str(e)
    return None


def sh(cwd, *args):
    r = subprocess.run(args, cwd=cwd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"{args}: {r.stderr}")
    return r.stdout.strip()


print("== runner-owned paths ==")
check("fixture_window.json is runner-owned", vr.is_runner_owned("fixture_window.json"))
check("docs/data/x.json is runner-owned", vr.is_runner_owned("docs/data/entry_summary.json"))
check("squad.json is NOT runner-owned", not vr.is_runner_owned("squad.json"))
check("a lookalike prefix is NOT runner-owned", not vr.is_runner_owned("docs/database.json"))

print("\n== repo_file allow-list ==")
repo = os.path.join(_tmp, "files")
os.makedirs(os.path.join(repo, "scenarios", "_live"))
os.makedirs(os.path.join(repo, "docs", "data", "players"))
for p in ("ROLE_INTEL.md", "scenarios/a.txt", "scenarios/_live/b.txt",
          "docs/data/entry_summary.json", "docs/data/players/p.json", "secrets.env"):
    open(os.path.join(repo, p), "w").write("x")
check("ROLE_INTEL.md allowed", vr.resolve_allowed("ROLE_INTEL.md", repo).endswith("ROLE_INTEL.md"))
check("scenarios/a.txt allowed", raises(vr.resolve_allowed, "scenarios/a.txt", repo) is None)
check("docs/data/entry_summary.json allowed",
      raises(vr.resolve_allowed, "docs/data/entry_summary.json", repo) is None)
check("scenarios/_live/b.txt refused (glob is one level)",
      raises(vr.resolve_allowed, "scenarios/_live/b.txt", repo) is not None)
check("docs/data/players/p.json refused (one level)",
      raises(vr.resolve_allowed, "docs/data/players/p.json", repo) is not None)
check("unlisted file refused", raises(vr.resolve_allowed, "secrets.env", repo) is not None)
check("traversal refused", raises(vr.resolve_allowed, "../etc/passwd", repo) is not None)
check("traversal dressed as an allowed glob refused",
      raises(vr.resolve_allowed, "scenarios/../secrets.env", repo) is not None)
os.symlink(os.path.join(repo, "secrets.env"), os.path.join(repo, "scenarios", "link.txt"))
check("symlink named like an allowed file, pointing at an unlisted one, refused",
      raises(vr.resolve_allowed, "scenarios/link.txt", repo) is not None)
listed = vr.list_allowed(repo)
check("list_allowed shows allowed files only",
      "scenarios/a.txt" in listed and "secrets.env" not in listed
      and "scenarios/_live/b.txt" not in listed, listed)

print("\n== scenario rows ==")
good = "O'Reilly | MCI | stp | set | 0.65 | 3-8 | medium | 2026-09-15 | ticked"
check("a 9-field row validates", vr.validate_rows([good]) == [good])
check("dict rows are accepted", vr.validate_rows([{
    "player": "Mosquera", "team": "ARS", "field": "stp", "op": "set", "value": 0.5,
    "gws": "5-6", "confidence": "high", "date": "2026-09-15", "why": "injured"}])[0]
      .startswith("Mosquera | ARS | stp | set | 0.5"))
check("8 fields refused", raises(vr.validate_rows, ["a|b|c|d|1|f|g|h"]) is not None)
check("bad op refused", raises(vr.validate_rows, [good.replace("| set |", "| add |")]) is not None)
check("non-numeric value refused",
      raises(vr.validate_rows, [good.replace("0.65", "lots")]) is not None)
check("newline smuggling refused", raises(vr.validate_rows, [good + "\n" + good]) is not None)
check("empty rows refused", raises(vr.validate_rows, []) is not None)

print("\n== optimiser_args ==")
a = vr.optimiser_args()
check("weekly defaults: shrunk, fixtures, quarantine, 1 transfer",
      a == ["optimise_squad.py", "--estimator", "shrunk", "--fixtures", "--quarantine",
            "--transfers", "1"], a)
check("rebuild mode omits --transfers", "--transfers" not in vr.optimiser_args(transfers=None))
check("quarantine without intel refused",
      raises(vr.optimiser_args, intel=False) is not None)
check("intel=False with quarantine=False passes --no-intel",
      "--no-intel" in vr.optimiser_args(intel=False, quarantine=False))
check("2 transfers with 1 free and hits=False refused",
      raises(vr.optimiser_args, transfers=2) is not None)
a = vr.optimiser_args(transfers=2, free_transfers=2)
check("2 banked free transfers passes --free-transfers 2",
      a[-2:] == ["--free-transfers", "2"], a)
a = vr.optimiser_args(transfers=2, hits=True, haaland=True, max_attackers_per_club=None,
                      gate=0.7, force_in=["O'Reilly:MCI"], force_out=["Virgil:LIV"],
                      role_rivals=[["Enzo:MCI", "O'Reilly:MCI"]], allow_contaminated=True)
check("every override maps to its flag",
      all(x in a for x in ("--haaland", "--no-max-attackers-per-club", "--gate",
                           "--allow-contaminated", "--force-in", "O'Reilly:MCI",
                           "--force-out", "Virgil:LIV", "--role-rivals",
                           "Enzo:MCI,O'Reilly:MCI")), a)
check("max_attackers_per_club=3 maps to the flag",
      "3" in vr.optimiser_args(max_attackers_per_club=3))
check("force_in without Name:TEAM refused",
      raises(vr.optimiser_args, force_in=["O'Reilly"]) is not None)
check("force_in in rebuild mode refused",
      raises(vr.optimiser_args, transfers=None, force_in=["X:ARS"]) is not None)
check("bad estimator refused", raises(vr.optimiser_args, estimator="vibes") is not None)

print("\n== window stamp ==")
W = [0.4, 0.3, 0.2, 0.1]
check("matching GW and weights is fine",
      vr.window_problem({"generated_for_gw": 5, "gw_weights": W}, 5) is None)
check("stale stamp refused", "refresh_fixture_window" in
      (vr.window_problem({"generated_for_gw": 4, "gw_weights": W}, 5) or ""))
check("right GW but old equal-mean window refused",
      "GW weights" in (vr.window_problem({"generated_for_gw": 5}, 5) or ""))
check("right GW but different weights refused",
      vr.window_problem({"generated_for_gw": 5, "gw_weights": [0.25] * 4}, 5) is not None)
check("unknown live GW refused", vr.window_problem({"generated_for_gw": 5}, None) is not None)
check("missing window refused", vr.window_problem({"generated_for_gw": None}, 5) is not None)

print("\n== vetting ==")
ok_p = {"name": "O'Reilly", "team": "MCI", "status": "a", "ok": True, "contaminated": False}
inj = {"name": "Hinshelwood", "team": "BHA", "status": "i", "chance": 0, "ok": False}
cont = {"name": "Enzo", "team": "MCI", "status": "a", "ok": True, "contaminated": True}
dbt = {"name": "Shaw", "team": "MUN", "status": "d", "chance": 75, "ok": True}
e, w = vr.vet_players([ok_p])
check("an available, clean player passes", not e and not w)
e, _ = vr.vet_players([inj])
check("injured player is an error", len(e) == 1 and "Hinshelwood" in e[0], e)
e, _ = vr.vet_players([cont])
check("contaminated player is an error even when ok=True", len(e) == 1, e)
e, w = vr.vet_players([dbt])
check("75% doubtful is a warning, not an error", not e and len(w) == 1, (e, w))
res = {"mode": "transfers", "transfers": [
    {"k": 1, "verdict": "MOVE", "in": [inj], "out": [ok_p]},
    {"k": 2, "verdict": "HOLD", "in": [inj], "out": [ok_p]}]}
e, w = vr.assess(res)
check("MOVE naming a flagged player becomes ERROR_FLAGGED_PLAYER",
      res["transfers"][0]["verdict"] == "ERROR_FLAGGED_PLAYER" and len(e) == 1, e)
check("a HOLD tie is left as HOLD, never resolved or vetted into a move",
      res["transfers"][1]["verdict"] == "HOLD")
e, _ = vr.assess({"mode": "rebuild", "xi": [ok_p], "bench": [cont]})
check("rebuild squads are vetted too (bench included)", len(e) == 1, e)
e, _ = vr.assess(None)
check("no structured result is an error, not an empty success", len(e) == 1)
lines = "\n".join(vr.verdict_lines({"mode": "transfers", "current_xi_xp": 56.1, "bank": 1.3,
                                    "free_transfers": 1, "transfers": [], "preference_costs": {
                                        "no_haaland": {"active": True, "cost_xp90": 0.0},
                                        "max_attackers_per_club": {"active": False}}}))
check("both preference-cost lines always present",
      "PREFERENCE COST no Haaland: 0.0" in lines
      and "PREFERENCE COST max attackers/club: not active" in lines, lines)
check("alarm lines are lifted from stderr",
      vr.alarms("  LIVE FETCH: failed\n  noise\n  STATUS EXCLUDED — 3") ==
      ["LIVE FETCH: failed", "STATUS EXCLUDED — 3"])

print("\n== run_script ==")
sdir = os.path.join(_tmp, "scripts")
os.makedirs(sdir)
open(os.path.join(sdir, "echo.py"), "w").write(
    "import sys, json\nprint('out'); print('LIVE FETCH: x', file=sys.stderr)\n"
    "json.dump({'mode': 'rebuild', 'xi': [], 'bench': []}, open(sys.argv[sys.argv.index('--json')+1], 'w'))\n")
open(os.path.join(sdir, "boom.py"), "w").write("import sys\nsys.exit('refused loudly')\n")
r = vr.run_script(["echo.py"], want_json=True, repo=sdir)
check("stdout, stderr and --json payload captured separately",
      r["stdout"].strip() == "out" and "LIVE FETCH" in r["stderr"]
      and r["json"]["mode"] == "rebuild", r)
r = vr.run_script(["boom.py"], want_json=True, repo=sdir)
check("an early exit returns its message and json=None",
      r["returncode"] == 1 and "refused loudly" in r["stderr"] and r["json"] is None, r)
body = vr.render("t", {"head": "abc1234", "origin": "abc1234", "behind": 0, "warnings": []},
                 {"generated_for_gw": 5, "horizon": 4}, 5,
                 vr.run_script(["echo.py"], want_json=True, repo=sdir))
check("render flags a failed live fetch as an ERROR, and keeps stderr verbatim",
      "LIVE FETCH FAILED" in body and "--- stderr (verbatim) ---\nLIVE FETCH: x" in body, body)

print("\n== repo_sync against a real origin ==")
origin = os.path.join(_tmp, "origin.git")
seed = os.path.join(_tmp, "seed")
clone = os.path.join(_tmp, "clone")
sh(_tmp, "git", "init", "-q", "--bare", "-b", "main", origin)
sh(_tmp, "git", "clone", "-q", origin, seed)
for d in (seed,):
    sh(d, "git", "config", "user.email", "t@example.com")
    sh(d, "git", "config", "user.name", "t")
os.makedirs(os.path.join(seed, "docs", "data"))
open(os.path.join(seed, "fixture_window.json"), "w").write('{"generated_for_gw": 4}')
open(os.path.join(seed, "squad.json"), "w").write("{}")
open(os.path.join(seed, "docs", "data", "entry_summary.json"), "w").write('{"gw": 3}')
sh(seed, "git", "add", "-A")
sh(seed, "git", "commit", "-qm", "seed")
sh(seed, "git", "push", "-q", "origin", "HEAD:main")
sh(_tmp, "git", "clone", "-q", origin, clone)
sh(clone, "git", "config", "user.email", "t@example.com")
sh(clone, "git", "config", "user.name", "t")


def push(path, text, msg):
    open(os.path.join(seed, path), "w").write(text)
    sh(seed, "git", "commit", "-qam", msg)
    sh(seed, "git", "push", "-q", "origin", "HEAD:main")


s = vr.repo_sync(repo=clone)
check("in-sync clean clone is ok, nothing pulled", s["ok"] and not s["pulled"], s)

push("squad.json", '{"v": 2}', "squad v2")
s = vr.repo_sync(repo=clone)
check("clean clone behind origin fast-forwards", s["ok"] and s["pulled"] and s["behind"] == 0, s)

open(os.path.join(clone, "docs", "data", "entry_summary.json"), "w").write('{"gw": 4, "vm": 1}')
push("docs/data/entry_summary.json", '{"gw": 4, "origin": 1}', "entry summary from elsewhere")
s = vr.repo_sync(repo=clone)
backup = s["backed_up"][0].split(" -> ")[1] if s["backed_up"] else ""
check("runner-owned clash: backed up, reset to origin, pulled",
      s["ok"] and s["pulled"] and backup and json.load(open(backup)) == {"gw": 4, "vm": 1}
      and json.load(open(os.path.join(clone, "docs/data/entry_summary.json"))) == {"gw": 4, "origin": 1},
      s)

open(os.path.join(clone, "fixture_window.json"), "w").write('{"generated_for_gw": 5}')
push("squad.json", '{"v": 3}', "squad v3")
s = vr.repo_sync(repo=clone)
check("runner-owned dirty file origin did NOT touch survives the pull",
      s["ok"] and s["pulled"] and "fixture_window.json" in s["dirty_runner_owned"]
      and json.load(open(os.path.join(clone, "fixture_window.json"))) == {"generated_for_gw": 5}, s)

open(os.path.join(clone, "squad.json"), "w").write('{"hand": "edit"}')
push("squad.json", '{"v": 4}', "squad v4")
s = vr.repo_sync(repo=clone)
check("foreign dirty file: refused, NOT pulled, edit untouched",
      not s["ok"] and not s["pulled"] and s["behind"] == 1
      and json.load(open(os.path.join(clone, "squad.json"))) == {"hand": "edit"}, s)
sh(clone, "git", "checkout", "--", "squad.json")

s = vr.repo_sync(repo=clone)
sh(clone, "git", "commit", "-q", "--allow-empty", "-m", "hand commit on the VM")
s = vr.repo_sync(repo=clone)
check("clone AHEAD of origin is refused", not s["ok"] and s["ahead"] == 1, s)

print("\n== matrix ==")
cells = vr.matrix_cells(["prior", "shrunk"], ["fence", "quarantine"], [1, 2], ["row"])
check("grid is estimators x overlays x transfers, plus one scenario row set per estimator",
      len(cells) == 2 * 2 * 2 + 2 * 2, len(cells))
check("bad overlay refused", raises(vr.matrix_cells, ["prior"], ["vibes"], [1], None) is not None)
a = vr._cell_args({"estimator": "raw", "overlay": "fence", "transfers": 2}, None, None)
check("fence cell prices hits and keeps intel without quarantine",
      "--no-intel" not in a and "--quarantine" not in a and a[-2:] == ["--transfers", "2"], a)
a = vr._cell_args({"estimator": "raw", "overlay": "scenario", "transfers": 1}, "/tmp/s.txt", None)
check("scenario cell runs scenario_squad.py on the temp file",
      a[:2] == ["scenario_squad.py", "/tmp/s.txt"], a)
job = {"cells": [dict(estimator="shrunk", overlay="quarantine", transfers=1, state="done",
                      errors=[], result={"transfers": [{"k": 1, "verdict": "MOVE",
                                                        "gain_xp90": 1.42, "net_5gw": 7.1,
                                                        "bank_after": 1.4,
                                                        "out": [{"name": "Virgil"}],
                                                        "in": [{"name": "Botman"}]}]}),
                 dict(estimator="prior", overlay="fence", transfers=2, state="queued")]}
t = vr.matrix_table(job)
check("matrix table shows the move and queued cells",
      "Virgil" in t and "Botman" in t and "queued" in t, t)

print("\n== register() with a stub server ==")


class StubMCP:
    def __init__(self):
        self.names = []

    def tool(self, name=None, description=""):
        def deco(fn):
            self.names.append(name or fn.__name__)
            return fn
        return deco


stub = StubMCP()
vr.register(stub, live_gw=lambda: 5, fixture_table=lambda n: "")
want = {"repo_sync", "refresh_fixture_window", "optimise_transfers", "optimise_scenario",
        "optimise_matrix", "optimise_job", "quarantine_report", "intel_report",
        "player_estimates", "squad_state", "repo_file", "bench_value"}
check("all runner tools register under their spec names", set(stub.names) == want,
      sorted(set(stub.names) ^ want))
check("module-level repo_sync is still the function, not a tool closure",
      vr.repo_sync.__module__ == "vm_runner" and not vr.repo_sync.__name__.endswith("_tool"))

print("\n" + ("ALL TESTS PASSED" if not FAILS else f"{len(FAILS)} FAILURE(S): {FAILS}"))
sys.exit(1 if FAILS else 0)
