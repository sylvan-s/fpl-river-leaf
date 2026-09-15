#!/usr/bin/env python3
"""Per-player estimates under every estimator, intel on and off, in one table.

    python3 player_estimates.py --squad
    python3 player_estimates.py --names "O'Reilly:MCI,Virgil,Hinshelwood" --candidates 5
    python3 player_estimates.py --squad --candidates 5 --quarantine --json out.json

WHY. The GW5 scenario run (15 Sep 2026) needed the "raw, priors, shrunk" view
for the squad and the transfer candidates side by side, and got it from an
ad-hoc dump script in scenarios/_live/. This is that script made permanent:
same build_squad.load() and fixture_adjust.adjust() calls, nothing re-derived.

WHAT IT REPORTS, per player: live price, status, chance of playing, the ok
flag gate 3 gives him, the contaminated flag, and for each of prior / raw /
shrunk x intel on / off: stp, xg90, xa90, cbit90, cbirt90, xP_flat and (with
the fixture window) xP_adj.

Contaminated movers are LOADED here, not excluded (exclude_contaminated=False),
so they appear with contaminated=true rather than silently missing - this is a
diagnostic view, never a selection. --quarantine layers ticked Trello
decisions onto the intel-ON columns only, and fails loudly without Trello
credentials (same rule as optimise_squad.py --quarantine).

--candidates N adds the top N per position by shrunk / intel-on xP (xP_adj
when the window is on) among players who are ok, not contaminated, clear the
XI start-rate gate and are not already owned.
"""
import contextlib, importlib.util, io, json, os, sys, unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))


def _load_module(name, filename):
    spec = importlib.util.spec_from_file_location(name, os.path.join(HERE, filename))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ESTIMATORS = ("prior", "raw", "shrunk")
RATE_FIELDS = ("stp", "xg90", "xa90", "cbit90", "cbirt90")


def _fold(s):
    return "".join(c for c in unicodedata.normalize("NFKD", s)
                   if not unicodedata.combining(c)).lower()


def select(rows, names, owned_keys, candidates, rank_key, gate_xi=0.0):
    """(chosen keys in order, unmatched name strings). A name matches a web
    name exactly (accent-folded), else as a substring; more than one hit is
    reported as ambiguous rather than guessed. "Name:TEAM" narrows by club."""
    chosen, unmatched = [], []
    keys = sorted({(r["name"], r["team"]) for r in rows})
    for raw in names:
        name, _, team = raw.strip().partition(":")
        pool = [k for k in keys if not team or k[1] == team.strip().upper()]
        hits = [k for k in pool if _fold(k[0]) == _fold(name)] \
            or [k for k in pool if _fold(name) in _fold(k[0])]
        if len(hits) == 1:
            chosen.append(hits[0])
        else:
            unmatched.append(f"{raw} ({'ambiguous: ' + ', '.join(f'{n}|{t}' for n, t in hits) if hits else 'no match'})")
    chosen += [k for k in owned_keys if k in set(keys)]
    if candidates:
        by_key = {(r["name"], r["team"]): r for r in rows}
        for pos in ("GKP", "DEF", "MID", "FWD"):
            pick = sorted((r for r in by_key.values()
                           if r["pos"] == pos and r["ok"] and not r.get("contaminated")
                           and r["stp"] >= gate_xi
                           and (r["name"], r["team"]) not in owned_keys),
                          key=rank_key, reverse=True)[:candidates]
            chosen += [(r["name"], r["team"]) for r in pick]
    seen, ordered = set(), []
    for k in chosen:
        if k not in seen:
            seen.add(k)
            ordered.append(k)
    return ordered, unmatched


def main():
    bs = _load_module("bs", "build_squad.py")
    fa = _load_module("fa", "fixture_adjust.py")
    st = _load_module("squad_state", "squad_state.py").load()

    names = []
    if "--names" in sys.argv:
        names = [n for n in sys.argv[sys.argv.index("--names") + 1].split(",") if n.strip()]
    use_squad = "--squad" in sys.argv
    candidates = int(sys.argv[sys.argv.index("--candidates") + 1]) if "--candidates" in sys.argv else 0
    use_fixtures = "--no-fixtures" not in sys.argv

    header = []
    if "--quarantine" in sys.argv:
        tq = _load_module("tq", "trello_quarantine.py")
        try:
            board = tq.fetch_board()
        except tq.QuarantineUnavailable as e:
            sys.exit(f"QUARANTINE UNAVAILABLE: {e}\nRefusing to report intel-ON "
                     f"columns as overlay numbers when they would be fence-only.")
        entries, warnings = tq.parse_board(board, bs.ia.MULT_FIELDS, bs.ia.SET_FIELDS)
        for w in warnings:
            print(f"  {w}", file=sys.stderr)
        bs.ia.set_overlay(entries, resolver=tq.resolve)
        header.append(f"QUARANTINE OVERLAY ACTIVE - {len(entries)} ticked Trello decision(s) "
                      f"on the intel-ON columns, this run only")

    pools, err = {}, io.StringIO()
    for est in ESTIMATORS:
        for intel in (True, False):
            with contextlib.redirect_stderr(err):
                pool = bs.load(intel=intel, estimator=est, exclude_contaminated=False)
            for r in pool:
                r["xp_flat"] = r["score"]
            if use_fixtures:
                fa.adjust(pool)
            pools[(est, intel)] = {(r["name"], r["team"]): r for r in pool}
    # Six loads print the same live-data warnings six times; keep each once, in order.
    seen = set()
    for line in err.getvalue().splitlines():
        if line not in seen:
            seen.add(line)
            print(line, file=sys.stderr)

    live_gw = bs.current_live_gw()
    window = fa.window_label() if use_fixtures else None
    stale = use_fixtures and live_gw is not None and fa.check_stale(live_gw)
    if stale:
        header.append(f"FIXTURE WINDOW STALE: {window} but live GW is {live_gw} - xP_adj "
                      f"describes the wrong fixtures. Refresh the window first.")

    base = pools[("shrunk", True)]
    owned_keys = [(p["name"], p["team"]) for p in st.players] if use_squad else []
    missing_owned = [f"{n}|{t}" for n, t in owned_keys if (n, t) not in base]
    rank = (lambda r: r.get("xp_adj", r["score"])) if use_fixtures else (lambda r: r["score"])
    keys, unmatched = select(list(base.values()), names, owned_keys, candidates, rank,
                             gate_xi=bs.GATE_XI)
    owned_set = set((p["name"], p["team"]) for p in st.players)

    players = []
    for key in keys:
        ref = next((pools[k][key] for k in pools if key in pools[k]), None)
        if ref is None:
            continue
        est = {}
        for (e, intel), pool in pools.items():
            r = pool.get(key)
            if r is None:
                continue
            cell = {f: round(r[f], 4) for f in RATE_FIELDS}
            cell["xp_flat"] = round(r["xp_flat"], 4)
            if use_fixtures:
                cell["xp_adj"] = round(r["xp_adj"], 4)
            cell["quarantine"] = sorted({a["field"] for a in r.get("intel_applied", [])
                                         if a.get("source") == "quarantine"})
            est.setdefault(e, {})["intel_on" if intel else "intel_off"] = cell
        players.append({"name": key[0], "team": key[1], "pos": ref["pos"],
                        "price": ref["price"], "status": ref["status"],
                        "chance": ref.get("chance"), "ok": ref["ok"],
                        "contaminated": bool(ref.get("contaminated")),
                        "owned": key in owned_set, "estimates": est})

    for h in header:
        print(h)
    col = "xp_adj" if use_fixtures else "xp_flat"
    print(f"{'player':<15}{'tm':<5}{'pos':<4}{'£':>5} {'st':<3}{'ch':>4} {'ok':<3}{'cont':<5}"
          f"| {col} intel ON: prior  raw shrunk | OFF: prior  raw shrunk | shrunk-ON stp xg90 xa90 cbit90")
    for p in players:
        def g(e, side):
            c = p["estimates"].get(e, {}).get(side)
            return f"{c[col]:6.2f}" if c else "   n/a"
        s = p["estimates"].get("shrunk", {}).get("intel_on") or {}
        print(f"{p['name'][:14]:<15}{p['team']:<5}{p['pos']:<4}{p['price']:>5.1f} "
              f"{(p['status'] or '?'):<3}{'' if p['chance'] is None else p['chance']:>4} "
              f"{'Y' if p['ok'] else 'N':<3}{'YES' if p['contaminated'] else '':<5}"
              f"| {g('prior', 'intel_on')}{g('raw', 'intel_on')}{g('shrunk', 'intel_on')} "
              f"| {g('prior', 'intel_off')}{g('raw', 'intel_off')}{g('shrunk', 'intel_off')} "
              f"| {s.get('stp', 0)*100:5.0f}% {s.get('xg90', 0):.2f} {s.get('xa90', 0):.2f} "
              f"{s.get('cbit90', 0):5.2f}" + (f"  (quarantine: {', '.join(s['quarantine'])})"
                                              if s.get("quarantine") else ""))
    for u in unmatched:
        print(f"  UNMATCHED: {u}")
    for m in missing_owned:
        print(f"  OWNED BUT NOT IN POOL (below the minutes gate?): {m}")

    if "--json" in sys.argv:
        with open(sys.argv[sys.argv.index("--json") + 1], "w", encoding="utf-8") as fh:
            json.dump({"meta": {"live_gw": live_gw, "window": window, "window_stale": stale,
                                "quarantine": "--quarantine" in sys.argv,
                                "estimators": list(ESTIMATORS)},
                       "players": players, "unmatched": unmatched,
                       "owned_not_in_pool": missing_owned}, fh, indent=1)


if __name__ == "__main__":
    main()
