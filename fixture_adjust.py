#!/usr/bin/env python3
"""xP_adj — expected points adjusted for the opposition, over a fixture window.

Flat xP asks "what does this player do in an average match". xP_adj asks "what
will he do against the sides he is actually about to face". Same scoring table,
same coefficients — the only change is that each term is scaled by who the
opponent is.

TWO CHANNELS, AND THEY ARE NOT THE SAME NUMBER
  ATT x  how leaky the opponents are   -> scales what YOU score
  DEF x  how potent the opponents are  -> scales what you CONCEDE

The best attacking run and the best defensive run belong to different teams.
That is the whole reason FDR was dropped: one integer cannot carry both.

WHERE THE MULTIPLIERS COME FROM
`fixture_difficulty(next_n=N)` in the MCP, which derives them from opponent
xG/xGC with home/away applied, shrunk toward the prior season. They are pasted
in below rather than recomputed, so this file and captaincy_odds can never
disagree about how hard a fixture is.

    python3 fixture_adjust.py            # show the adjustment per player (intel ON by default)
    python3 fixture_adjust.py --squad    # only the current squad
    python3 fixture_adjust.py --no-intel # ROLE_INTEL.md adjustments OFF

--no-intel is read by build_squad.load() (same sys.argv, one process) - nothing
here duplicates that logic. See intel_adjust.py. ROLE_INTEL.md adjustments are
ON BY DEFAULT since 13 Aug 2026.

    # WEEKLY REFRESH - paste the raw fixture_difficulty output and stamp the GW:
    python3 fixture_adjust.py --update --gw 3 < window.txt

REFRESHING IS NOT OPTIONAL. The multipliers describe a SPECIFIC window of
fixtures. Left unrefreshed they quietly optimise for matches already played,
and nothing in the output would look wrong. The window is therefore stamped
with the gameweek it was generated for, and every run prints that stamp; the
weekly brief compares it against get_deadline and refuses to quote the
optimiser if they disagree.

--update PARSES the tool output rather than asking anyone to retype 40 numbers.
Transcribing them by hand is exactly the kind of silent error this project has
already been bitten by twice.
"""
import importlib.util, os, sys

import scoring

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("bs", os.path.join(HERE, "build_squad.py"))
bs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bs)

WINDOW_PATH = os.path.join(HERE, "fixture_window.json")


def parse_fixture_output(text):
    """Parse the fixture_difficulty table. Returns {TEAM: (att, def, games)}.

    Expects rows shaped like:   TOT       1.08    0.99    4
    Anything that does not match that shape is ignored, so headers, notes and
    the trailing commentary pass through harmlessly.
    """
    import re
    out = {}
    for line in text.splitlines():
        m = re.match(r"^([A-Z]{3})\s+([\d.]+)\s+([\d.]+)\s+(\d+)", line.strip())
        if m:
            out[m.group(1)] = (float(m.group(2)), float(m.group(3)), int(m.group(4)))
    return out


def save_window(fixtures, gw, horizon):
    import json, datetime as dt
    payload = {"generated_for_gw": gw, "horizon": horizon,
               "generated_utc": dt.datetime.now(dt.timezone.utc).isoformat()[:19],
               "teams": {k: list(v) for k, v in fixtures.items()}}
    with open(WINDOW_PATH, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=1)
    return payload


def load_window():
    """Return (fixtures, stamp) - stamp is None when falling back to the constant."""
    import json
    try:
        with open(WINDOW_PATH, encoding="utf-8") as fh:
            w = json.load(fh)
        return ({k: tuple(v) for k, v in w["teams"].items()}, w)
    except Exception:
        return (None, None)


# ---- FALLBACK ONLY. The live window lives in fixture_window.json ------------
# Kept so the module still runs before the first refresh, and so there is a
# committed record of what GW1-4 looked like. Do NOT hand-edit this to update
# the window - use --update, which parses and stamps.
# team: (ATT x, DEF x, fixtures in window)
# REFRESH THIS AFTER EVERY GAMEWEEK - a stale window silently optimises for
# fixtures that have already been played.
HORIZON = 4
FIXTURES = {
    "TOT": (1.08, 0.99, 4), "BRE": (1.07, 0.99, 4), "ARS": (1.05, 1.03, 4),
    "LIV": (1.05, 0.69, 4), "BHA": (1.05, 1.19, 4), "NFO": (1.05, 0.99, 4),
    "LEE": (1.05, 0.96, 4), "BOU": (1.04, 1.20, 4), "EVE": (1.04, 1.10, 4),
    "HUL": (1.03, 1.22, 4), "NEW": (1.03, 1.05, 4), "CRY": (1.02, 0.88, 4),
    "MCI": (1.02, 1.14, 4), "FUL": (1.01, 1.11, 4), "MUN": (1.01, 1.00, 4),
    "IPS": (1.00, 1.07, 4), "CHE": (0.91, 0.93, 4), "SUN": (0.90, 0.85, 4),
    "AVL": (0.90, 0.99, 4), "COV": (0.88, 1.23, 4),
}

# Scale the defensive-workload terms by opponent attack strength?
# A defender facing a potent side makes MORE clearances, blocks and
# interceptions, and a keeper faces MORE shots. Both are directionally obvious
# and both are second-order. Set False to price only the two primary channels.
SCALE_WORKLOAD = True


def active_window():
    """The window actually in force, plus a human-readable provenance line."""
    fx, stamp = load_window()
    if fx:
        return fx, (f"fixture_window.json · generated for GW{stamp['generated_for_gw']}"
                    f" · horizon {stamp['horizon']} · {stamp['generated_utc']}"), stamp
    return FIXTURES, ("BUILT-IN FALLBACK (GW1-4, 9 Aug 2026) — no "
                      "fixture_window.json found, run --update"), None


def check_stale(current_gw):
    """True if the stored window is for a different gameweek. Cheap tripwire."""
    _fx, _prov, stamp = active_window()
    if stamp is None:
        return True
    return stamp["generated_for_gw"] != current_gw


def adjust(pool, fixtures=None, scale_workload=SCALE_WORKLOAD, empirical=None):
    """Add xp_adj (per 90, opponent-adjusted) and xp_adj_win (over the window).

    Applies the SAME scoring table as scoring.expected_points; only the
    inputs are scaled — scoring.expected_points_scaled() is that formula
    (architecture review candidate #1: this function used to reassemble the
    scoring table term-by-term itself, a second hand-written copy of the
    same formula build_squad.py and build_dashboard.py each also carried).
    """
    if fixtures is None:
        fixtures, _prov, _stamp = active_window()
    use_empirical_dc = bs.USE_EMPIRICAL_DC if empirical is None else empirical
    for r in pool:
        att_x, def_x, games = fixtures.get(r["team"], (1.0, 1.0, HORIZON))
        xp = scoring.expected_points_scaled(
            r, att_x, def_x, scale_workload=scale_workload, empirical=use_empirical_dc)

        r["att_x"], r["def_x"], r["games"] = att_x, def_x, games
        r["xp_flat"] = r["score"]
        r["xp_adj"] = xp
        r["xp_adj_win"] = xp * games      # every side plays 4 times in GW1-4
        r["fx_swing"] = xp - r["score"]
    return pool


def main():
    if "--update" in sys.argv:
        gw = None
        if "--gw" in sys.argv:
            gw = int(sys.argv[sys.argv.index("--gw") + 1])
        if gw is None:
            sys.exit("--update needs --gw N (the gameweek the window starts at)")
        text = sys.stdin.read()
        fx = parse_fixture_output(text)
        if len(fx) < 20:
            sys.exit(f"parsed only {len(fx)} teams — expected 20. "
                     f"Paste the whole fixture_difficulty table.")
        games = {g for _a, _d, g in fx.values()}
        w = save_window(fx, gw, HORIZON)
        print(f"window saved: {len(fx)} teams, generated for GW{gw}, "
              f"horizon {HORIZON}")
        print(f"  fixtures per team in window: {sorted(games)}"
              + ("  (uneven — a double or blank is in range)" if len(games) > 1 else ""))
        best_att = max(fx.items(), key=lambda kv: kv[1][0])
        best_def = min(fx.items(), key=lambda kv: kv[1][1])
        print(f"  best for attackers: {best_att[0]} {best_att[1][0]:.2f}x")
        print(f"  best for defenders: {best_def[0]} {best_def[1][1]:.2f}x conceded")
        return

    # This file parses its OWN argv now (architecture review candidate #3)
    # rather than relying on build_squad's ambient USE_INTEL/USE_EMPIRICAL_DC
    # defaults — those are only for callers that don't have an opinion.
    use_intel = "--no-intel" not in sys.argv
    use_empirical_dc = "--legacy-dc" not in sys.argv

    _fx, prov, _stamp = active_window()
    print(f"window source: {prov}\n")
    if use_intel:
        print("INTEL: ROLE_INTEL.md `adjustments` fence is ACTIVE (default since "
              "13 Aug 2026 - pass --no-intel to disable)\n")
    else:
        print("INTEL: DISABLED (--no-intel)\n")
    pool = adjust(bs.load(intel=use_intel, empirical=use_empirical_dc),
                  empirical=use_empirical_dc)
    only_squad = "--squad" in sys.argv
    # From squad.json via squad_state.py. This copy was the one that went stale
    # on 9 Aug 2026 — it listed a player transferred out two changes earlier,
    # because --squad is rarely run and nothing had exercised it. That is
    # precisely why there is now one source instead of three.
    import importlib.util as _iu
    _s = _iu.spec_from_file_location("squad_state",
                                     os.path.join(HERE, "squad_state.py"))
    _m = _iu.module_from_spec(_s); _s.loader.exec_module(_m)
    SQ = _m.load().name_set
    rows = [r for r in pool if (r["name"] in SQ) or not only_squad]
    rows.sort(key=lambda r: -r["fx_swing"])
    print(f"xP_adj over GW1-{HORIZON}  (workload scaling: "
          f"{'on' if SCALE_WORKLOAD else 'off'})\n")
    print(f"{'player':<15}{'pos':<5}{'tm':<5}{'ATT x':>7}{'DEF x':>7}"
          f"{'xP flat':>9}{'xP adj':>8}{'swing':>8}{'4-GW':>8}")
    print("-" * 72)
    show = rows if only_squad else rows[:12] + [None] + rows[-8:]
    for r in show:
        if r is None:
            print(f"{'...':<15}"); continue
        print(f"{r['name'][:14]:<15}{r['pos']:<5}{r['team']:<5}{r['att_x']:>7.2f}"
              f"{r['def_x']:>7.2f}{r['xp_flat']:>9.2f}{r['xp_adj']:>8.2f}"
              f"{r['fx_swing']:>+8.2f}{r['xp_adj_win']:>8.1f}")
    sw = [r["fx_swing"] for r in pool]
    print(f"\nswing across the whole pool: {min(sw):+.2f} to {max(sw):+.2f} xP/90")
    print(f"  mean |swing| {sum(abs(s) for s in sw)/len(sw):.2f} — "
          f"over {HORIZON} GWs that is {sum(abs(s) for s in sw)/len(sw)*HORIZON:.1f} pts")


if __name__ == "__main__":
    main()
