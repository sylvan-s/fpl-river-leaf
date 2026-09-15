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
    # NOT spend+bank<=100 — the £100m budget only binds at squad-construction
    # time. A held player's price can rise after that, and real FPL team
    # values routinely exceed £100m through organic appreciation; that is not
    # an error. The only thing that IS always invalid is spending cash you
    # don't have.
    if st.bank < -1e-6:
        errs.append(f"bank £{st.bank:.1f}m is negative — can't have spent more than owned")

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


def sell_price(bought_for: float, current_price: float) -> float:
    """What FPL actually pays out for selling a player — NOT current_price.

    The real rule: a fall passes through in full, but a rise is only ever
    HALF banked, rounded down to the nearest £0.1m. A player bought at £5.0m
    now worth £5.4m (+£0.4m) sells for £5.2m, not £5.4m — the other £0.2m is
    never realisable. optimise_transfers() used to treat owned players' full
    current price as spendable budget, which silently overstated how much a
    sale actually frees up on anyone who has risen (found 13 Sep 2026,
    prompted by João Pedro/Mbeumo/Thiago/Shaw all drifting off their
    bought_for price by GW4 — see squad.json's ledger-drift note and
    TEAM_CHANGE_LOG.md's GW2-4 entries).

    Compares in integer tenths of £1m, not raw floats — prices are always
    exact multiples of £0.1m, but 5.7 - 5.5 in float64 is
    0.19999999999999973, and floor-dividing THAT by 2 rounds the wrong way
    once in a while. Round-tripping through tenths sidesteps it entirely.
    Moved here from optimise_squad.py 15 Sep 2026 (which aliases it).
    """
    bought_tenths = round(bought_for * 10)
    now_tenths = round(current_price * 10)
    if now_tenths <= bought_tenths:
        return now_tenths / 10          # fall (or flat): full downside, no floor
    profit_tenths = now_tenths - bought_tenths
    return (bought_tenths + profit_tenths // 2) / 10


def live_drift(st, bootstrap):
    """bought_for vs live now_cost per owned player (roadmap B1's gap), from a
    bootstrap-static payload. Matched on web name + club; a player it cannot
    match is listed with now=None, never guessed. squad.json's ledger is
    bought_for-based by design, so the drift is reported, not reconciled."""
    teams = {t["id"]: t["short_name"] for t in bootstrap.get("teams", [])}
    live = {(e["web_name"], teams.get(e["team"])): e for e in bootstrap.get("elements", [])}
    rows = []
    for p in st.players:
        el = live.get((p["name"], p["team"]))
        now = el["now_cost"] / 10 if el else None
        bought = float(p["bought_for"])
        rows.append({"name": p["name"], "team": p["team"], "bought_for": bought,
                     "ledger_price": p["price"], "now_cost": now,
                     "sell_price": sell_price(bought, now) if now is not None else None,
                     "drift": round(now - bought, 1) if now is not None else None,
                     "status": el.get("status") if el else None,
                     "chance": el.get("chance_of_playing_next_round") if el else None})
    matched = [r for r in rows if r["now_cost"] is not None]
    return {"players": rows,
            "unmatched": [f"{r['name']}|{r['team']}" for r in rows if r["now_cost"] is None],
            "live_value": round(sum(r["now_cost"] for r in matched), 1),
            "sell_value": round(sum(r["sell_price"] for r in matched), 1),
            "ledger_value": st.value}


if __name__ == "__main__":
    import sys
    st = load()
    if "--json" in sys.argv:
        # Validated state as data - the VM runner's squad_state tool. Printed
        # only after load(), so an invalid squad.json still fails loudly.
        out = {
            "updated_utc": st.updated_utc, "gameweek": st.gameweek,
            "formation": st.formation, "bank": st.bank, "value": st.value,
            "squad_value_declared": st.raw.get("squad_value"),
            "captain": st.captain, "vice": st.vice,
            "xi": st.xi, "bench": st.bench, "chips": st.chips,
            "chips_remaining": {s: st.chips_remaining(s) for s in ("set1", "set2")},
        }
        if "--live" in sys.argv:
            # Opt-in network read; plain `--json` stays offline like the rest of this file.
            import urllib.request
            try:
                req = urllib.request.Request(
                    "https://fantasy.premierleague.com/api/bootstrap-static/",
                    headers={"User-Agent": "fpl-squad-state/1.0"})
                with urllib.request.urlopen(req, timeout=15) as resp:
                    out["live"] = live_drift(st, json.loads(resp.read().decode("utf-8")))
            except Exception as exc:
                out["live"] = {"error": f"bootstrap-static fetch failed: {exc}"}
        print(json.dumps(out, indent=1, ensure_ascii=False))
        sys.exit(0)
    print(f"squad.json valid · updated {st.updated_utc} · GW{st.gameweek}")
    print(f"  {st.formation}   value £{st.value:.1f}m   bank £{st.bank:.1f}m   "
          f"total £{st.value + st.bank:.1f}m")
    print(f"  captain {st.captain} · vice {st.vice}")
    print("  XI:    " + ", ".join(f"{p['name']}({p['pos']})" for p in st.xi))
    print("  bench: " + ", ".join(f"{p['bench_order']}:{p['name']}" for p in st.bench))
    for s in ("set1", "set2"):
        rem = st.chips_remaining(s)
        print(f"  {s}: {len(rem)} remaining — {', '.join(rem) if rem else 'none'}")
