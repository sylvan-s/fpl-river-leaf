#!/usr/bin/env python3
"""Single source of truth for live squad state. Read `squad.json`, validate it.

WHY THIS EXISTS. The fifteen used to be hardcoded in three separate Python
files plus prose in TEAM_CHANGE_LOG.md. Keeping four copies in step was a
standing instruction in the weekly brief, and it still failed: on 9 Aug 2026
`fixture_adjust.py`'s copy was found listing a player transferred out two
changes earlier, because nothing had exercised `--squad` since. A copy that is
rarely read is a copy that drifts silently.

    from squad_state import load
    st = load()
    st.names, st.bank, st.xi, st.bench, st.captain, st.chips

DELIBERATE DIVERGENCE from the pattern in build_dashboard.py, which keeps its
own last16 loader "so this file still runs if build_squad.py's interface
changes". That decoupling is right for a derived input read two ways. It is
wrong here: the entire point is that there must be exactly one squad, so
coupling is the feature.

FAILS LOUDLY, ALWAYS. No default squad, no falling back to a hardcoded list, no
warning-and-continue. A missing or invalid squad.json stops the run. Every
alternative silently answers questions about a team that does not exist, which
is the failure this file was written to end.
"""
import json, os

HERE = os.path.dirname(os.path.abspath(__file__))
PATH = os.environ.get("FPL_SQUAD_JSON") or os.path.join(HERE, "squad.json")

SQUAD_COMP = {"GKP": 2, "DEF": 5, "MID": 5, "FWD": 3}
FORMATION = {"GKP": (1, 1), "DEF": (3, 5), "MID": (2, 5), "FWD": (1, 3)}
MAX_CLUB = 3
BUDGET = 100.0


class SquadError(Exception):
    """squad.json is missing, malformed, or describes an illegal squad."""


class SquadState:
    def __init__(self, raw):
        self.raw = raw
        self.players = raw["squad"]
        self.bank = float(raw["bank"])
        self.captain = raw.get("captain")
        self.vice = raw.get("vice")
        self.formation = raw.get("formation")
        self.gameweek = raw.get("gameweek")
        self.chips = raw.get("chips", {})
        self.updated_utc = raw.get("updated_utc")

    @property
    def names(self):
        """All fifteen, in file order. Matches the old CURRENT_SQUAD list."""
        return [p["name"] for p in self.players]

    @property
    def name_set(self):
        return {p["name"] for p in self.players}

    @property
    def xi(self):
        return [p for p in self.players if p["role"] == "XI"]

    @property
    def bench(self):
        """Bench in autosub order. bench_order 0 is the GK slot."""
        return sorted((p for p in self.players if p["role"] == "BENCH"),
                      key=lambda p: p["bench_order"])

    @property
    def value(self):
        return round(sum(p["price"] for p in self.players), 1)

    def chips_remaining(self, which="set1"):
        s = self.chips.get(which, {})
        return sorted(k for k in ("wildcard", "freehit", "benchboost", "triplecaptain")
                      if s.get(k) == "available")


def validate(st):
    """Every check here corresponds to a way the old copies could go wrong."""
    errs = []
    n = len(st.players)
    if n != 15:
        errs.append(f"squad has {n} players, expected 15")

    seen = [p["name"] for p in st.players]
    dupes = {x for x in seen if seen.count(x) > 1}
    if dupes:
        errs.append(f"duplicate players: {sorted(dupes)}")

    comp = {}
    for p in st.players:
        comp[p["pos"]] = comp.get(p["pos"], 0) + 1
    for pos, want in SQUAD_COMP.items():
        if comp.get(pos, 0) != want:
            errs.append(f"{pos}: {comp.get(pos, 0)} in squad, expected {want}")

    xi = st.xi
    if len(xi) != 11:
        errs.append(f"{len(xi)} players marked role=XI, expected 11")
    xi_comp = {}
    for p in xi:
        xi_comp[p["pos"]] = xi_comp.get(p["pos"], 0) + 1
    for pos, (lo, hi) in FORMATION.items():
        c = xi_comp.get(pos, 0)
        if not lo <= c <= hi:
            errs.append(f"illegal formation: {c} {pos} in the XI, allowed {lo}-{hi}")

    bench = [p for p in st.players if p["role"] == "BENCH"]
    orders = sorted(p.get("bench_order") for p in bench)
    if orders != [0, 1, 2, 3]:
        errs.append(f"bench_order must be exactly 0,1,2,3 — got {orders}")
    gk_bench = [p for p in bench if p["pos"] == "GKP"]
    if len(gk_bench) != 1 or gk_bench[0].get("bench_order") != 0:
        errs.append("the benched GK must hold bench_order 0 — a GK only ever "
                    "substitutes for a GK, so it is not an ordered outfield slot")

    clubs = {}
    for p in st.players:
        clubs[p["team"]] = clubs.get(p["team"], 0) + 1
    over = {k: v for k, v in clubs.items() if v > MAX_CLUB}
    if over:
        errs.append(f"club cap exceeded: {over}")

    spend = sum(p["price"] for p in st.players)
    if spend + st.bank > BUDGET + 1e-6:
        errs.append(f"squad £{spend:.1f}m + bank £{st.bank:.1f}m = "
                    f"£{spend + st.bank:.1f}m, over the £{BUDGET:.1f}m budget")

    for who, label in ((st.captain, "captain"), (st.vice, "vice")):
        if who and who not in st.name_set:
            errs.append(f"{label} '{who}' is not in the squad")
    if st.captain and st.captain == st.vice:
        errs.append("captain and vice are the same player")

    declared = st.raw.get("squad_value")
    if declared is not None and abs(declared - spend) > 0.05:
        errs.append(f"squad_value says £{declared:.1f}m but the players sum to "
                    f"£{spend:.1f}m")

    if errs:
        raise SquadError("squad.json is invalid:\n  - " + "\n  - ".join(errs))
    return st


def load(path=PATH):
    try:
        raw = json.load(open(path, encoding="utf-8"))
    except FileNotFoundError:
        raise SquadError(
            f"{path} not found. It is the single source of truth for the live "
            f"squad — there is deliberately no fallback. Restore it from git, "
            f"or rebuild it from TEAM_CHANGE_LOG.md CURRENT STATE.")
    except json.JSONDecodeError as e:
        raise SquadError(f"{path} is not valid JSON: {e}")
    return validate(SquadState(raw))


if __name__ == "__main__":
    st = load()
    print(f"squad.json valid · updated {st.updated_utc} · GW{st.gameweek}")
    print(f"  {st.formation}   value £{st.value:.1f}m   bank £{st.bank:.1f}m   "
          f"total £{st.value + st.bank:.1f}m")
    print(f"  captain {st.captain} · vice {st.vice}")
    print("  XI:    " + ", ".join(f"{p['name']}({p['pos']})" for p in st.xi))
    print("  bench: " + ", ".join(f"{p['bench_order']}:{p['name']}" for p in st.bench))
    for s in ("set1", "set2"):
        rem = st.chips_remaining(s)
        print(f"  {s}: {len(rem)} remaining — {', '.join(rem) if rem else 'none'}")
