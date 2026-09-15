#!/usr/bin/env python3
"""Regression proof for trello_quarantine.py — no network, no Trello token.

The fixture below is the REAL `Take action` list as read from the FPL News
Management board on 15 Sep 2026 (via the Trello MCP connector), verbatim item
text included. The spec this module was built from guessed a different item
grammar ("stp → 50%, GWs 5-6") and a card-ID-based player; neither survives
contact with the actual board, and this file is what keeps that true.

    python3 test_trello_quarantine.py
"""
import importlib.util, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))


def _load(name, filename):
    spec = importlib.util.spec_from_file_location(name, os.path.join(HERE, filename))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


tq = _load("tq", "trello_quarantine.py")
ia = _load("ia", "intel_adjust.py")
M, S = ia.MULT_FIELDS, ia.SET_FIELDS

FAILS = []


def check(label, cond):
    print(f"  {'PASS' if cond else 'FAIL'}  {label}")
    if not cond:
        FAILS.append(label)


def item(name, complete):
    return {"name": name, "complete": complete}


APPROVE = "Required Decisions — tick to authorise"
LIVE = "Live in Model — applied (verified 14 Sep)"

BOARD = {"lists": [
    {"name": "Wait for more evidence", "cards": [
        {"name": "Calvert-Lewin (LEE) — rotating with Nmecha", "url": "https://trello.com/c/LNwiuBuz",
         "checklists": [{"name": APPROVE, "items": [
             item("Calvert-Lewin | LEE | stp | set → 80% | GWs 5-8 — would apply if this list were read", True)]}]},
    ]},
    {"name": "Take action", "cards": [
        {"name": "Enzo Fernandez (CHE→MCI) — deadline-day £125m signing", "url": "https://trello.com/c/enzo",
         "checklists": [
             {"name": APPROVE, "items": [
                 item("O'Reilly | MCI | stp | set → 65% | GWs 3-8 — REVISED 14 Sep: Sylvan comment \"revise O'Reilly starting % back down to 65%.\" Was 75% (applied 4 Sep review, effect ~−0.28 xP/GW). At 65% the effect reverts toward the original ~−0.75 xP/GW (3.75 → ~3.00) - exact figure to recompute at Friday review.", True),
                 item("END the O'Reilly xgi90/cbit90 pair early — SUPERSEDED 3 Sep by the GW6 extension. Dormant trigger: revisit only if Enzo actually displaces him to the back four", False),
                 item("DUPLICATE, CONSOLIDATED 14 Sep (curator) — this was the same Anderson | MCI | xgi90 | ×1.15 decision as on Anderson-MCI-xgi90-20260828-1 (card 5qOSpiim), split across two tick-boxes. Now lives solely there — tick it on that card, not here. Nothing to authorise on this line.", False),
             ]},
             {"name": "Live in Model — applied (verified 4 Sep)", "items": [
                 item("O'Reilly | MCI | stp | set → 75% | GWs 3-8 | LIVE in fence (accepted 4 Sep review, revised from 65% to 75%)", True)]},
         ]},
        {"name": "Szoboszlai (LIV) — xg90 mult 1.20 applied", "url": "https://trello.com/c/szob",
         "checklists": [{"name": APPROVE, "items": [
             item("Szoboszlai | LIV | xg90 | ×1.20 | GWs 3-8 — APPLIED 4 Sep review. Sized DOWN from 1.35 as a double-count hedge (penalties already inflate observed xG). Duty is API-CONFIRMED P1F1C1 — supersedes the \"pen order contested\" objection", True)]}]},
        {"name": "Villa (squad-wide) — xgi90 mult 0.70 applied", "url": "https://trello.com/c/villa",
         "checklists": [
             {"name": LIVE, "items": [item("Watkins | AVL | xgi90 | ×0.70 | GWs 1-6 | REMOVED 4 Sep review — dead, player left for Al-Hilal", False)]},
             {"name": APPROVE, "items": [
                 item("Remove the Watkins | AVL | xgi90 row — dead, left for Al-Hilal", True),
                 item("Remove the Martinez | AVL | xgi90 row — dead, left for Chelsea", True),
                 item("Add Ruggeri | AVL | xgi90 | ×0.70 | GWs 1-6 — APPROVED 3 Sep. Completes the squad-wide set at 14 so the thesis actually applies squad-wide", True)]},
         ]},
        {"name": "O'Reilly (MCI) — central-midfield role, both levers [merged]", "url": "https://trello.com/c/oreilly",
         "checklists": [{"name": APPROVE, "items": [
             item("Extend O'Reilly | MCI | cbit90 | ×0.80 → GWs 1-6 (was 1-4) — APPROVED 3 Sep. GW4 check RUN 3 Sep and CONFIRMED: raw CBIT/90 below 6.0", True),
             item("Extend O'Reilly | MCI | xgi90 | ×1.20 → GWs 1-6 (was 1-4) — APPROVED 3 Sep. Supported: xGI 0.31/90 vs Gabriel 0.11", True)]}]},
        {"name": "Mosquera (ARS) — minutes opening, Saliba/Timber out [merged]", "url": "https://trello.com/c/mosq",
         "checklists": [{"name": APPROVE, "items": [
             item("Mosquera | ARS | stp | set → 50% | GWs 5-6 — Sylvan, 13 Sep: \"konsa played ahead of mosquera - drop mosquera starting prob to 50% for 3 weeks\"; refined 14 Sep", True)]}]},
        {"name": "Dango (BRE) — dropped for GW2, start-rate risk", "url": "https://trello.com/c/dango",
         "checklists": [
             {"name": LIVE, "items": [item("Dango Ouattara | BRE | stp | NO ROW in fence (verified 14 Sep) — still running on the raw 81%-starts prior", False)]},
             {"name": APPROVE, "items": [item("Dango Ouattara | BRE | stp | set → 50% | GWs 5-6 — Sylvan, 13 Sep comment: \"take start rate prob to 50%, for two weeks until raw data presumably catches up.\"", True)]}]},
        {"name": "Justin (LEE) — possible shift to central defence", "url": "https://trello.com/c/justin",
         "checklists": [{"name": APPROVE, "items": [
             item("James Justin | LEE | cbit90 | ×1.15 | GWs 4-8 — CANDIDATE, drafted 14 Sep", False),
             item("James Justin | LEE | xgi90 | ×0.75 | GWs 4-8 — CANDIDATE, drafted 14 Sep", False)]}]},
    ]},
    {"name": "Reject / Expired", "cards": [
        {"name": "Old rejected card", "url": "https://trello.com/c/old",
         "checklists": [{"name": APPROVE, "items": [item("Thiago | BRE | stp | set → 10% | GWs 1-38 — rejected, tick left behind", True)]}]},
    ]},
]}

print("parse_board — what counts as accepted")
entries, warns = tq.parse_board(BOARD, M, S)
keys = sorted((e["item_player"], e["field"], e["action"]) for e in entries)
check("exactly 9 ticked Take-action approval items parse",
      len(entries) == 9)
check("Wait-list card ignored even though ticked", not any(e["item_player"] == "Calvert-Lewin" for e in entries))
check("Reject/Expired card ignored even though ticked", not any(e["item_player"] == "Thiago" for e in entries))
check("unticked candidates ignored (Justin)", not any("Justin" in e["item_player"] for e in entries))
check("Live in Model lists ignored (no 75% O'Reilly entry)",
      not any(e["item_player"] == "O'Reilly" and e["field"] == "stp" and abs(e["value"] - 0.75) < 1e-9 for e in entries))
check("no warnings - every ticked approval item on the real board is parseable", warns == [])

by = {(e["item_player"], e["field"], e["action"]): e for e in entries}
e = by[("O'Reilly", "stp", "set")]
check("player comes from the ITEM: O'Reilly stp read off the Enzo card", e["card_url"].endswith("/enzo"))
check("set → 65% -> 0.65, GWs 3-8", e["op"] == "set" and abs(e["value"] - 0.65) < 1e-9 and e["gws"] == (3, 8))
e = by[("Szoboszlai", "xg90", "set")]
check("×1.20 -> mult 1.20", e["op"] == "mult" and abs(e["value"] - 1.2) < 1e-9 and e["gws"] == (3, 8))
e = by[("O'Reilly", "cbit90", "set")]
check("'Extend ... ×0.80 → GWs 1-6 (was 1-4)' -> mult 0.80, window 1-6 (not the old 1-4)",
      e["op"] == "mult" and abs(e["value"] - 0.8) < 1e-9 and e["gws"] == (1, 6))
check("'Add Ruggeri' verb stripped", ("Ruggeri", "xgi90", "set") in by)
check("'Remove the Watkins | AVL | xgi90 row' -> remove action", by[("Watkins", "xgi90", "remove")]["gws"] is None)
check("full name kept as written for resolution", ("Dango Ouattara", "stp", "set") in by)

print("\nparse_item — strictness (a bad silent parse is worse than a skip)")
bad = [
    ("free text, ticked", "END the O'Reilly xgi90/cbit90 pair early"),
    ("set on a mult field", "Justin | LEE | cbit90 | set → 50% | GWs 5-6"),
    ("multiplier on stp", "Mosquera | ARS | stp | ×0.50 | GWs 5-6"),
    ("unknown field", "Justin | LEE | xp90 | ×1.10 | GWs 5-6"),
    ("set > 1 with no %", "Mosquera | ARS | stp | set → 50 | GWs 5-6"),
    ("junk glued to the effect", "Szoboszlai | LIV | xg90 | ×1.20abc | GWs 3-8"),
    ("backwards window", "Mosquera | ARS | stp | set → 50% | GWs 6-5"),
    ("lowercase team code", "Mosquera | ars | stp | set → 50% | GWs 5-6"),
]
for label, text in bad:
    got, why = tq.parse_item(text, M, S)
    check(f"rejects {label} ({why})", got is None and why)
got, _ = tq.parse_item("Mosquera | ARS | stp | set → 0.5", M, S)
check("set → 0.5 without % and without window -> 0.5, open-ended", got and got["value"] == 0.5 and got["gws"] is None)
got, _ = tq.parse_item("Justin | LEE | cbit90 | mult 1.15 | GWs 4-8", M, S)
check("'mult 1.15' accepted as a multiplier", got and got["op"] == "mult" and got["value"] == 1.15)

print("\nwarning surfaces a ticked-but-unparseable item, naming card and text")
b2 = {"lists": [{"name": "Take action", "cards": [{"name": "X card", "url": "https://trello.com/c/x",
      "checklists": [{"name": APPROVE, "items": [item("END the O'Reilly pair early", True)]}]}]}]}
e2, w2 = tq.parse_board(b2, M, S)
check("no entry, one warning", e2 == [] and len(w2) == 1 and "X card" in w2[0] and "END the O'Reilly" in w2[0])

print("\nname resolution against pool rows (same team only)")
ROWS = [{"name": n, "team": t} for n, t in [
    ("O'Reilly", "MCI"), ("Szoboszlai", "LIV"), ("Mosquera", "ARS"), ("O.Dango", "BRE"),
    ("Ruggeri", "AVL"), ("Justin", "LEE"), ("Gabriel", "ARS"), ("Martinelli", "ARS"),
    ("B.Fernandes", "MUN"), ("Van de Ven", "TOT"), ("Pau", "AVL"), ("Thiago", "BRE")]]
entries, _ = tq.parse_board(BOARD, M, S)
w = tq.resolve(entries, ROWS)
res = {(e["item_player"], e["field"], e["action"]): e for e in entries}
check("'Dango Ouattara' -> O.Dango (initial + word)",
      res[("Dango Ouattara", "stp", "set")]["player"] == "O.Dango" and res[("Dango Ouattara", "stp", "set")]["resolved"])
check("exact names resolve to themselves", res[("Mosquera", "stp", "set")]["player"] == "Mosquera")
check("Watkins/Martinez (left the league) unmatched -> dropped with a warning",
      not res[("Watkins", "xgi90", "remove")]["resolved"] and any("Watkins" in x for x in w))
check("name_matches: 'James Justin' -> Justin", tq.name_matches("James Justin", "Justin"))
check("name_matches: 'Bruno Fernandes' -> B.Fernandes", tq.name_matches("Bruno Fernandes", "B.Fernandes"))
check("name_matches: 'Micky van de Ven' -> Van de Ven", tq.name_matches("Micky van de Ven", "Van de Ven"))
check("name_matches: 'Pau Torres' -> Pau", tq.name_matches("Pau Torres", "Pau"))
check("name_matches rejects 'Bruno Fernandes' -> O.Dango", not tq.name_matches("Bruno Fernandes", "O.Dango"))
amb = [dict(action="set", item_player="Gabriel Martinelli", team="ARS", field="stp", op="set",
            value=0.5, gws=None, card_url="u")]
wa = tq.resolve(amb, ROWS)
check("'Gabriel Martinelli' hits Gabriel AND Martinelli -> ambiguous, dropped, never a guess",
      not amb[0]["resolved"] and "ambiguous" in wa[0])
wrong_team = [dict(action="set", item_player="Justin", team="AVL", field="stp", op="set",
                   value=0.5, gws=None, card_url="u")]
tq.resolve(wrong_team, ROWS)
check("right name, wrong team -> unmatched", not wrong_team[0]["resolved"])

print("\nconflicts and duplicates")
c = [dict(action="set", item_player="Mosquera", team="ARS", field="stp", op="set", value=v,
          gws=(5, 6), card_url=u) for v, u in ((0.5, "a"), (0.6, "b"))]
wc = tq.resolve(c, ROWS)
check("same key ticked with two values -> both dropped, CONFLICT warning",
      not any(x["resolved"] for x in c) and "CONFLICT" in wc[0])
d = [dict(action="set", item_player="Mosquera", team="ARS", field="stp", op="set", value=0.5,
          gws=(5, 6), card_url=u) for u in ("a", "b")]
tq.resolve(d, ROWS)
check("identical duplicate ticks -> applied once", sum(1 for x in d if x["resolved"]) == 1)

print("\nstatus against a fence")
FENCE = [dict(player="Szoboszlai", team="LIV", field="xg90", op="mult", value=1.2),
         dict(player="O'Reilly", team="MCI", field="stp", op="set", value=0.75),
         dict(player="Mosquera", team="ARS", field="stp", op="set", value=0.85)]
st = {k: tq.status(v, FENCE, 5) for k, v in res.items()}
check("Szoboszlai x1.20 = fence -> 'same as fence (already promoted)'", st[("Szoboszlai", "xg90", "set")].startswith("same as fence"))
check("O'Reilly 0.65 vs fence 0.75 -> CHANGES", st[("O'Reilly", "stp", "set")].startswith("CHANGES"))
check("O.Dango 0.50, no fence row -> NEW", st[("Dango Ouattara", "stp", "set")].startswith("NEW"))
check("Mosquera GWs 5-6 at GW7 -> OUT OF WINDOW", tq.status(res[("Mosquera", "stp", "set")], FENCE, 7).startswith("OUT OF WINDOW"))

print("\nintel_adjust overlay seam - replace, never stack")
ia2 = _load("ia2", "intel_adjust.py")          # fresh instance, fence stubbed, no ROLE_INTEL.md read
def fe(player, team, field, op, value):
    return dict(player=player, team=team, field=field, op=op, value=value, gws=None, gws_raw="ALL")
ia2._CACHE = [fe("Szoboszlai", "LIV", "xg90", "mult", 1.2), fe("O'Reilly", "MCI", "stp", "set", 0.75),
              fe("O'Reilly", "MCI", "cbit90", "mult", 0.8), fe("Mosquera", "ARS", "stp", "set", 0.85),
              fe("Watkins", "AVL", "xgi90", "mult", 0.7)]
ia2._current_gw = lambda: 5
def row(name, team):
    return dict(name=name, team=team, stp=0.9, xg90=0.30, xa90=0.10, xgi90=0.40, cbit90=5.0, cbirt90=6.0)
def applied(name, team):
    r = row(name, team); ia2.apply(r); return r

base = {n: applied(n, t) for n, t in [("Szoboszlai", "LIV"), ("O'Reilly", "MCI"), ("Mosquera", "ARS"), ("O.Dango", "BRE")]}
check("overlay OFF: fence applies exactly as before (Mosquera stp 0.85, O.Dango untouched)",
      base["Mosquera"]["stp"] == 0.85 and base["O.Dango"]["stp"] == 0.9 and not ia2.overlay_active())

entries, _ = tq.parse_board(BOARD, ia2.MULT_FIELDS, ia2.SET_FIELDS)
entries.append(dict(action="remove", item_player="Watkins", team="AVL", field="xgi90", op=None, value=None,
                    gws=None, gws_raw="ALL", source="quarantine", card_url="u", player="Watkins"))
ia2.set_overlay(entries, resolver=tq.resolve)
ia2.resolve_overlay(ROWS + [{"name": "Watkins", "team": "AVL"}])
on = {n: applied(n, t) for n, t in [("Szoboszlai", "LIV"), ("O'Reilly", "MCI"), ("Mosquera", "ARS"),
                                    ("O.Dango", "BRE"), ("Watkins", "AVL"), ("Thiago", "BRE")]}
check("Szoboszlai x1.20 ticked AND in fence -> xg90 0.36, NOT 0.432 (no stacking)",
      abs(on["Szoboszlai"]["xg90"] - 0.36) < 1e-9)
check("O'Reilly stp: overlay 0.65 replaces fence 0.75", abs(on["O'Reilly"]["stp"] - 0.65) < 1e-9)
check("O'Reilly cbit90: 'Extend x0.80' replaces fence x0.80 -> 4.0, not 3.2", abs(on["O'Reilly"]["cbit90"] - 4.0) < 1e-9)
check("Mosquera stp 0.50 in window GW5 (5-6) replaces fence 0.85", abs(on["Mosquera"]["stp"] - 0.5) < 1e-9)
check("O.Dango stp 0.50 - NEW, via 'Dango Ouattara' name resolution", abs(on["O.Dango"]["stp"] - 0.5) < 1e-9)
check("Remove suppresses the Watkins fence row (xgi90 untouched)", abs(on["Watkins"]["xg90"] - 0.30) < 1e-9)
check("suppressed fence row is flagged so the unmatched warning stays quiet",
      ia2.overlay_suppressed(fe("Watkins", "AVL", "xgi90", "mult", 0.7)))
check("un-ticked-on player (Thiago) untouched", on["Thiago"]["stp"] == 0.9)
check("overlay rows tagged source=quarantine for the (quarantine) marker",
      any(e.get("source") == "quarantine" for e in on["O.Dango"]["intel_applied"]))

ia2._current_gw = lambda: 7
out = applied("Mosquera", "ARS")
check("outside its window (GW7 vs 5-6): fence value 0.85 stands", abs(out["stp"] - 0.85) < 1e-9)
ia2._current_gw = lambda: None
check("unknown GW: a windowed item does NOT apply (never guess)", abs(applied("Mosquera", "ARS")["stp"] - 0.85) < 1e-9)
ia2._current_gw = lambda: 5
ia2.set_overlay([], resolver=tq.resolve); ia2.resolve_overlay(ROWS)
check("overlay ON but nothing ticked: identical to fence-only", applied("Mosquera", "ARS")["stp"] == 0.85)


print(f"\n{'ALL PASS' if not FAILS else f'{len(FAILS)} FAILURE(S): ' + ', '.join(FAILS)}")
sys.exit(1 if FAILS else 0)
