#!/usr/bin/env python3
"""Offline tests for the 15 Sep 2026 live-status fix - no network required.

build_squad.load() set every row's availability as
`r["ok"] = r["name"] not in UNAVAILABLE` and never read FPL's live `status`
flag. Watkins left for Al-Hilal, but a player who leaves the league stays in
bootstrap-static with status 'u' and his OLD club, so the live CLUB pass could
not catch him either: bs.load(intel=False) returned Watkins AVL £7.8m ok=True
xP 4.89, and nothing but a since-removed ROLE_INTEL row had ever held him out.

load() normally fetches bootstrap-static; here that fetch is stubbed with a
fake payload built from the committed frozen snapshot, so the real load()
runs end to end against a controlled status flag.

Run:  python3 test_live_status.py
"""
import contextlib
import importlib.util
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
FAILS = []


def check(label, cond, detail=""):
    if cond:
        print(f"  PASS  {label}")
    else:
        print(f"  FAIL  {label}  {detail}")
        FAILS.append(label)


def _load_module(name, filename):
    spec = importlib.util.spec_from_file_location(name, os.path.join(HERE, filename))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


bs = _load_module("bs", "build_squad.py")

print("== is_available: hand list AND live status flag ==")
row = lambda name, status: {"name": name, "status": status}
check("'u' (left the league) is unavailable", not bs.is_available(row("Watkins", "u")))
check("'n' (loan / not available) is unavailable", not bs.is_available(row("X", "n")))
check("'s' (suspended) is NOT excluded automatically - reported instead",
      bs.is_available(row("X", "s")))
check("'a' is available", bs.is_available(row("X", "a")))
check("'i'/'d' unchanged - still left to the hand list",
      bs.is_available(row("X", "i")) and bs.is_available(row("X", "d")))
check("no live flag (fetch failed) falls back to the hand list alone",
      bs.is_available(row("X", None)))
hand = next(iter(bs.UNAVAILABLE))
check(f"hand list still overrides a live 'a' ({hand})", not bs.is_available(row(hand, "a")))
check("hand list still applies with no live flag", not bs.is_available(row(hand, None)))


# ---- load() end to end, with bootstrap-static stubbed ------------------------
snap = json.load(open(bs.SNAP, encoding="utf-8"))
teams = {int(k): v for k, v in snap["teams"].items()}
WATKINS = next(pid for pid, p in snap["players"].items()
               if p["web_name"] == "Watkins" and teams.get(p["team"]) == "AVL")
SUSP = next(pid for pid, p in snap["players"].items()
            if p["web_name"] == "Gabriel" and teams.get(p["team"]) == "ARS")
HAND = next(pid for pid, p in snap["players"].items()
            if p["web_name"] in bs.UNAVAILABLE and (p.get("minutes") or 0) >= bs.MIN_MINUTES)


def fake_live(overrides):
    """Every snapshot player listed live as 'a' on his snapshot club, then overrides."""
    elements = {pid: {"id": int(pid), "status": "a", "news": "",
                      "now_cost": p.get("now_cost")} for pid, p in snap["players"].items()}
    for pid, fields in overrides.items():
        elements[pid].update(fields)
    clubs = {pid: teams.get(p.get("team"), "?") for pid, p in snap["players"].items()}
    return elements, clubs


def run_load(elements, clubs):
    real = bs._fetch_current_season
    bs._fetch_current_season = lambda: elements
    bs._current_cache, bs._live_clubs_cache = elements, clubs
    err = io.StringIO()
    try:
        with contextlib.redirect_stderr(err):
            pool = bs.load(intel=False)
    finally:
        bs._fetch_current_season = real
        bs._current_cache = bs._live_clubs_cache = None
    return {r["name"]: r for r in pool}, err.getvalue()


print("\n== load(): live status 'u' excludes, loudly ==")
elements, clubs = fake_live({
    WATKINS: {"status": "u", "news": "Stub news: has joined a non-PL club"},
    SUSP: {"status": "s", "news": "Stub news: suspended until next GW"},
    HAND: {"status": "a"},
})
by_name, err = run_load(elements, clubs)
w = by_name.get("Watkins")
check("Watkins is still in the pool (excluded by ok, not dropped)", w is not None)
if w:
    check("Watkins AVL status 'u' -> ok=False", w["ok"] is False and w["status"] == "u",
          f"ok={w['ok']} status={w['status']}")
    check("his club is still the stale AVL - which is why CLUB could not catch him",
          w["team"] == "AVL", w["team"])
check("STATUS EXCLUDED is printed to stderr, naming him with FPL's news",
      "STATUS EXCLUDED" in err and "Watkins (AVL) [u: Stub news" in err, err[-600:])
g = by_name.get("Gabriel")
check("suspended ('s') Gabriel stays ok=True", g is not None and g["ok"] is True)
check("...but is reported as STATUS SUSPENDED, not silently kept",
      "STATUS SUSPENDED" in err and "Gabriel (ARS)" in err)
hname = snap["players"][HAND]["web_name"]
check(f"hand-list {hname} with live 'a' is still ok=False (override kept)",
      by_name[hname]["ok"] is False)
check("no 'no live status flags' fallback warning when the fetch worked",
      "no live status flags" not in err)

print("\n== load(): bootstrap-static unreachable degrades to the hand list ==")
by_name, err = run_load({}, {})
w = by_name.get("Watkins")
check("no crash, and every row's status is None",
      w is not None and all(r["status"] is None for r in by_name.values()))
check("Watkins falls back to the hand list (ok=True) - the known, reported gap",
      w is not None and w["ok"] is True)
check("...and load() says so on stderr",
      "STATUS: no live status flags this run" in err, err[-600:])
check(f"hand-list {hname} still ok=False with no live data", by_name[hname]["ok"] is False)

print("\n== scenario_squad.apply_scenario keeps the live exclusion ==")
# It recomputes `ok` for every row a scenario touches. It used to recompute
# from UNAVAILABLE alone, which re-admitted anyone load() excluded on status.
sc = _load_module("sc", "scenario_squad.py")
sc.bs = bs
by_name, _ = run_load(*fake_live({WATKINS: {"status": "u"}}))
pool = list(by_name.values())
sc.apply_scenario(pool, [{"player": "Watkins", "team": "AVL", "field": "stp",
                          "op": "set", "value": 0.9}])
check("a scenario touching Watkins does not flip him back to ok=True",
      by_name["Watkins"]["ok"] is False)

print("\n" + ("ALL TESTS PASSED" if not FAILS else f"{len(FAILS)} FAILURE(S): {FAILS}"))
sys.exit(1 if FAILS else 0)
