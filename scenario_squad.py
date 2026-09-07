#!/usr/bin/env python3
"""Scenario exploration — what if a hypothesis played out, no decision implied.

WHY THIS EXISTS. The Friday review turns an agreed news bite into a
ROLE_INTEL.md `adjustments` fence row — a real, sourced-or-Sylvan's-own-
estimate input that governs the actual live weekly optimiser run. That is
the wrong tool for "just suppose X and see what falls out": writing a
speculative row into the real fence would contaminate the live model with
something nobody has agreed to act on, and remembering to remove it again
every time is exactly the kind of manual step ROLE_INTEL.md rule 6 ("prune
on contact with reality") was written for approved rows, not throwaway ones.

This applies the SAME two adjustment shapes intel_adjust.py already uses —
bounded mult (0.5x-1.5x) for xg90/xa90/xgi90/cbit90/cbirt90, unguardrailed
set for stp — to an IN-MEMORY scenario list that never touches
ROLE_INTEL.md, squad.json or TEAM_CHANGE_LOG.md. Real, already-approved
adjustments still apply underneath (a scenario STACKS a hypothesis on top of
current reality, not instead of it) — pass --no-base-intel for a clean-slate
run instead.

    python3 scenario_squad.py my_scenario.txt
    python3 scenario_squad.py my_scenario.txt --fixtures
    python3 scenario_squad.py my_scenario.txt --transfers 2
    python3 scenario_squad.py my_scenario.txt --no-base-intel

SCENARIO FILE FORMAT. Same 9-field pipe-delimited row as ROLE_INTEL.md's
`adjustments` fence — player|team|field|op|value|gws|confidence|date|why —
no fence markers, blank lines and #-comments skipped. `gws`/`confidence`/
`date` are carried through to the printed audit trail only; a scenario has
no live-gameweek staleness check because it is inherently a one-off, never
a standing fact.

DATA-HYGIENE CORRECTIONS, NOT HYPOTHESES. A brand-new transfer can still be
tagged under his old club (and at his old price) in the frozen prior-season
snapshot build_squad.py reads by default — that's a stale-data bug, not a
"what if". CORRECTIONS below fixes that BEFORE the scenario rows are
applied, and is reported separately in the output so a data fix is never
mistaken for one of the what-ifs being tested.

OUTPUT IS LABELLED, NEVER SILENT. Every run prints "SCENARIO — HYPOTHETICAL,
NOT A RECOMMENDATION" and lists every row actually applied (plus anything
that failed to match), so this can never be mistaken for a real weekly
optimiser run. Exit code is 0 whether or not every row matched — an
unmatched row is reported loudly, not silently dropped, but a scenario file
is allowed to reference an aspirational transfer target not yet in the pool.
"""
import importlib.util, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))


def _load_module(name, filename):
    spec = importlib.util.spec_from_file_location(name, os.path.join(HERE, filename))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


bs = _load_module("bs", "build_squad.py")
opt = _load_module("opt", "optimise_squad.py")
ia = _load_module("ia_ref", "intel_adjust.py")  # reused for the guardrail constants only
fa = _load_module("fa_ref", "fixture_adjust.py")  # reused for parse_fixture_output/adjust

MULT_FIELDS, SET_FIELDS = ia.MULT_FIELDS, ia.SET_FIELDS
MULT_LO, MULT_HI = ia.MULT_LO, ia.MULT_HI


def parse_scenario(path):
    rows = []
    with open(path, encoding="utf-8") as f:
        for lineno, line in enumerate(f, 1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = [p.strip() for p in line.split("|")]
            if len(parts) != 9:
                sys.exit(f"{path}:{lineno}: expected 9 fields "
                         f"(player|team|field|op|value|gws|confidence|date|why), "
                         f"got {len(parts)}: {line!r}")
            player, team, field, op, value, gws, conf, date, why = parts
            try:
                value = float(value)
            except ValueError:
                sys.exit(f"{path}:{lineno}: value {value!r} is not a number")
            if field in SET_FIELDS and op != "set":
                sys.exit(f"{path}:{lineno}: field '{field}' must use op=set")
            if field in MULT_FIELDS and op != "mult":
                sys.exit(f"{path}:{lineno}: field '{field}' must use op=mult "
                         f"(guardrailed {MULT_LO}x-{MULT_HI}x)")
            if field not in MULT_FIELDS | SET_FIELDS:
                sys.exit(f"{path}:{lineno}: unknown field '{field}' — must be one "
                         f"of {sorted(MULT_FIELDS | SET_FIELDS)}")
            rows.append(dict(player=player, team=team, field=field, op=op, value=value,
                              gws=gws, confidence=conf, date=date, why=why))
    return rows


def apply_corrections(pool, corrections):
    """Fix stale team/price tags BEFORE the scenario runs. Returns an audit list.

    corrections: {(name, old_team): {"team": new_team, "price": new_price}}
    """
    by_key = {(r["name"], r["team"]): r for r in pool}
    audit = []
    for (name, old_team), fix in corrections.items():
        r = by_key.get((name, old_team))
        if r is None:
            audit.append(f"CORRECTION {name}|{old_team} — not found in pool, skipped")
            continue
        bits = []
        if "team" in fix and fix["team"] != r["team"]:
            bits.append(f"team {r['team']}->{fix['team']}")
            r["team"] = fix["team"]
        if "price" in fix and fix["price"] != r["price"]:
            bits.append(f"price £{r['price']:.1f}m->£{fix['price']:.1f}m")
            r["price"] = fix["price"]
        if bits:
            audit.append(f"CORRECTION {name}: " + ", ".join(bits))
    return audit


def apply_scenario(pool, rows):
    """Mutate pool rows per the scenario rows; recompute score for anything touched."""
    by_key = {(r["name"], r["team"]): r for r in pool}
    touched, applied, unmatched = set(), [], []

    for e in rows:
        r = by_key.get((e["player"], e["team"]))
        if r is None:
            unmatched.append(f"{e['player']}|{e['team']} ({e['field']}) — not in the "
                              f"pool (name/team mismatch, or below the 900-min gate)")
            continue
        if e["op"] == "mult":
            factor = min(max(e["value"], MULT_LO), MULT_HI)
            clamp = "" if MULT_LO <= e["value"] <= MULT_HI else f" (CLAMPED from x{e['value']})"
            if e["field"] == "xgi90":
                r["xg90"] *= factor; r["xa90"] *= factor
            else:
                r[e["field"]] *= factor
            r["xgi90"] = r["xg90"] + r["xa90"]  # display-only; not read by expected_points()
        else:
            clamp = "" if 0.0 <= e["value"] <= 1.0 else f" (CLAMPED from {e['value']})"
            r["stp"] = min(max(e["value"], 0.0), 1.0)
        touched.add(id(r))
        applied.append((e, clamp))

    for r in pool:
        if id(r) in touched:
            r["ok"] = r["name"] not in bs.UNAVAILABLE
            r["score"] = bs.scoring.expected_points(r, empirical=bs.USE_EMPIRICAL_DC)
    return applied, unmatched


# Data-hygiene fixes applied before every scenario — not hypotheses, just
# correcting a stale club or price on a pool row.
#
# EMPTY SINCE 7 Sep 2026, DELIBERATELY, and the mechanism is kept rather than
# deleted. It used to hold Enzo (CHE->MCI, £6.9m) and Muñoz (CRY->NFO, £5.4m),
# and that was the bug: this file is the SCENARIO tool, and it was the only
# thing in the repo applying either correction. optimise_squad.py — the actual
# weekly tool — had no equivalent and never applied them, so the live weekly
# run kept scoring Muñoz on Crystal Palace's fixture run while he played for
# Nottingham Forest. A correction that only one consumer applies is worse than
# no correction, because the two tools disagree and only one of them is right.
#
# Both are now fixed for EVERY consumer at the source: build_squad.load()
# reads club and price from live bootstrap-static on every call (see its
# "CLUB" and "PRICE" comments), which covered these two and 14 other pool
# players nobody had hand-listed. A hand-maintained dict could only ever hold
# the movers somebody had already noticed.
#
# Keep this for what live data genuinely cannot supply — a correction Sylvan
# is making against the API rather than in step with it. Anything the API
# already knows belongs in load(), not here.
KNOWN_CORRECTIONS = {}

# Players to exclude from consideration this run — NOT a hypothesis, a
# caution flag Sylvan raised that injury_report doesn't (yet) carry as a
# status flag. Printed distinctly so it's never mistaken for a scenario row.
KNOWN_EXCLUSIONS = {
    ("Canvot", "CRY"): "Sylvan flagged an injury warning 6 Sep 2026; "
                       "injury_report still shows him available with no "
                       "odds/news — unconfirmed by the live flag, excluded "
                       "out of caution pending confirmation.",
}


def apply_exclusions(pool, exclusions):
    by_key = {(r["name"], r["team"]): r for r in pool}
    audit = []
    for (name, team), reason in exclusions.items():
        r = by_key.get((name, team))
        if r is None:
            audit.append(f"EXCLUSION {name}|{team} — not found in pool, skipped")
            continue
        r["ok"] = False
        audit.append(f"EXCLUDED {name} ({team}): {reason}")
    return audit


def main():
    if len(sys.argv) < 2 or sys.argv[1].startswith("--"):
        sys.exit("usage: python3 scenario_squad.py SCENARIO_FILE [--fixtures] "
                 "[--transfers N] [--no-base-intel] [--haaland]")
    path = sys.argv[1]
    use_base_intel = "--no-base-intel" not in sys.argv
    allow_haaland = "--haaland" in sys.argv
    estimator = (sys.argv[sys.argv.index("--estimator") + 1]
                 if "--estimator" in sys.argv else "prior")
    if estimator not in bs.ESTIMATOR_CHOICES:
        sys.exit(f"--estimator must be one of {bs.ESTIMATOR_CHOICES}, got {estimator!r}")

    # Role rivals - see optimise_squad.py's ROLE_RIVALS_DEFAULT comment.
    # Same "--role-rivals Name:TEAM,Name2:TEAM2" syntax, repeatable per group.
    role_rivals = []
    for i, a in enumerate(sys.argv):
        if a == "--role-rivals":
            group = set()
            for entry in sys.argv[i + 1].split(","):
                pname, _, pteam = entry.strip().partition(":")
                if not pteam:
                    sys.exit(f"--role-rivals entry {entry!r} must be Name:TEAM")
                group.add((pname, pteam))
            role_rivals.append(group)

    def _parse_pins(flag):
        out = []
        for i, a in enumerate(sys.argv):
            if a == flag:
                pname, _, pteam = sys.argv[i + 1].partition(":")
                if not pteam:
                    sys.exit(f"{flag} entry {sys.argv[i+1]!r} must be Name:TEAM")
                out.append((pname, pteam))
        return out

    pin_in = _parse_pins("--force-in")
    pin_out = _parse_pins("--force-out")

    print("=" * 70)
    print("SCENARIO — HYPOTHETICAL, NOT A RECOMMENDATION")
    print("Explores a what-if. Writes nothing to ROLE_INTEL.md, squad.json or")
    print("TEAM_CHANGE_LOG.md. Not a proposal for the Friday review.")
    print("=" * 70)
    print(f"\nbase: real ROLE_INTEL.md adjustments {'ON' if use_base_intel else 'OFF'} "
          f"(this scenario stacks on top of {'current reality' if use_base_intel else 'a clean slate'})\n")

    pool = bs.load(intel=use_base_intel, estimator=estimator)
    print(f"estimator: {estimator}"
          + ("  (needs live network; degrades to prior-only if unreachable — "
             "check for a fetch-failed warning above)" if estimator != "prior" else "")
          + "\n")

    corr_audit = apply_corrections(pool, KNOWN_CORRECTIONS)
    if corr_audit:
        print("DATA FIXES (not hypotheses):")
        for line in corr_audit:
            print(f"  {line}")
        print()

    excl_audit = apply_exclusions(pool, KNOWN_EXCLUSIONS)
    if excl_audit:
        print("CAUTION EXCLUSIONS (unconfirmed, not a status flag):")
        for line in excl_audit:
            print(f"  {line}")
        print()

    rows = parse_scenario(path)
    applied, unmatched = apply_scenario(pool, rows)

    print(f"SCENARIO ROWS APPLIED ({len(applied)}/{len(rows)}):")
    for e, clamp in applied:
        val = f"x{e['value']}" if e["op"] == "mult" else f"-> {e['value']}"
        print(f"  {e['player']:<12}{e['team']:<5}{e['field']:<9}{val}{clamp:<12}"
              f"GW{e['gws']:<6}{e['why']}")
    if unmatched:
        print("\nUNMATCHED (not applied):")
        for u in unmatched:
            print(f"  {u}")
    print()

    if "--fixtures-file" in sys.argv:
        # Custom-horizon fixture pull (e.g. next 5 rather than the standing
        # 4-GW window) - parses a raw fixture_difficulty(next_n=N) paste
        # directly, via fa.adjust()'s explicit `fixtures` param, WITHOUT
        # touching fixture_window.json (that file is the standing weekly
        # process's window; a one-off scenario query has no business
        # overwriting it).
        fpath = sys.argv[sys.argv.index("--fixtures-file") + 1]
        fx = fa.parse_fixture_output(open(fpath, encoding="utf-8").read())
        if len(fx) < 20:
            sys.exit(f"--fixtures-file {fpath}: parsed only {len(fx)} teams, expected 20")
        games = sorted({g for _a, _d, g in fx.values()})
        fa.adjust(pool, fixtures=fx)
        for r in pool:
            r["score"] = r["xp_adj"]
        print(f"objective: xP_adj (opponent-adjusted, {fpath}, "
              f"{games[0] if len(games)==1 else games} fixture(s)/team)\n")
    elif "--fixtures" in sys.argv:
        opt._fixture_scale(pool)
        print(f"objective: xP_adj (opponent-adjusted, standing GW1-{fa.HORIZON} window)\n")

    if "--transfers" in sys.argv:
        n = int(sys.argv[sys.argv.index("--transfers") + 1])
        free_transfers = (int(sys.argv[sys.argv.index("--free-transfers") + 1])
                           if "--free-transfers" in sys.argv else 1)
        print(f"=== SCENARIO — best moves FROM the current squad, under this what-if ===")
        opt.transfer_mode(pool, n, allow_haaland, free_transfers=free_transfers,
                          role_rivals=role_rivals, pin_in=pin_in, pin_out=pin_out)
    else:
        print("=== SCENARIO — best 15 from scratch (£100m), under this what-if ===")
        xi, bench, obj = opt.optimise(pool, allow_haaland, role_rivals=role_rivals)
        opt.show(xi, bench, obj)


if __name__ == "__main__":
    main()
