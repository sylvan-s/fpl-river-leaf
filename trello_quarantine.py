#!/usr/bin/env python3
"""Trello quarantine overlay — approved-but-not-yet-promoted news, for one run only.

    python3 trello_quarantine.py                          # = --quarantine-report
    python3 optimise_squad.py --quarantine-report         # same, from the optimiser
    python3 optimise_squad.py --fixtures --transfers 1 --quarantine
    python3 optimise_squad.py ... --quarantine --allow-fence-only-fallback

WHY. The Friday review is the only path from an approved Trello decision into
ROLE_INTEL.md's `adjustments` fence. That is deliberate, but it means a
decision Sylvan ticks on Tuesday has no effect on a Wednesday scenario run. At
12 Sep 2026 the fence covered one player in a fifteen-man squad while the
board held ticked start-rate decisions for three more.

WHAT THIS DOES. Reads the FPL News Management board live, takes every TICKED
row item on a `Rows in model` checklist on a card in `Live in model`, and every
TICKED row item on a `Decisions` checklist on a card in `Quarantined decisions`
(board reshaped 17 Sep 2026 - `Take action` / `Required Decisions` are gone),
turns each into a fence-shaped entry, and hands them to intel_adjust.set_overlay().
Nothing is written anywhere — not to Trello, not to ROLE_INTEL.md, not to the
repo. Without --quarantine the optimiser behaves exactly as before.

WHAT COUNTS. Only: lists `Live in model` and `Quarantined decisions`, checklist
name starting `Rows in model` or `Decisions`, item state complete. Everything
else is ignored by construction — Backlog / Wait / Reject-Expired cards are
never read, unticked items are not approvals (in `Live in model` an UNTICKED
row is Sylvan's instruction to PULL it at the next Friday write, which this
overlay does not model - the fence value stands until then), checklists named
`Archive ...` are pre-reshape history, an item wrapped in (parentheses) is a
note not a row, and the standing `Decline — no model change` quarantine item
is skipped silently. A ticked `Live in model` row that the fence already holds
is a no-op (REPLACE, below), which is exactly the 1:1 invariant the board
promises: ticked Live rows == fence rows.

THE ITEM GRAMMAR. Verified against the live board 15 Sep 2026, and it is not
the shape first guessed from outside the repo. The research-to-action skill
writes pipe-delimited rows, and the player comes from the ITEM, never the
card — the Enzo Fernandez card carries the O'Reilly stp decision:

    [Add |Extend ]<Player> | <TEAM> | <field> | <effect> [(|/→) GWs a-b] [note]
    Remove [the ]<Player> | <TEAM> | <field> row [note]

    effect:  set → 65%   set → 0.65   ×1.20   x1.20   mult 1.20

`set` is only legal on stp and a multiplier only on the MULT_FIELDS — the
same guardrail intel_adjust.py enforces on the fence, reused, not re-typed.
A ticked item that fails any of this is SKIPPED WITH A WARNING naming the
card and the raw text. Never guessed: a bite the optimiser does not see yet
is recoverable, a silently misread one is not.

REPLACE, NEVER STACK. Ticked items stay ticked after the Friday review
promotes them — Szoboszlai's x1.20 was ticked AND live in the fence on
15 Sep. Stacking would score him at x1.44. So an in-window overlay entry
REPLACES every fence entry for the same (player, team, field); an in-window
Remove suppresses them. Re-applying an already-promoted decision is therefore
a no-op, which is what makes it safe to leave old ticks on the board.

WINDOWS. An item's `GWs a-b` gates it against the run's target gameweek (the
window stamp in fixture_window.json). Outside it, the fence value stands. No
window means open-ended. Note this is STRICTER than the fence itself, whose
`gws` column is only a staleness warning — deliberate, because an overlay
decision is typically short-leash ("50% for two weeks").

NAMES. Items use full names ("Dango Ouattara", "James Justin"); the pool uses
FPL web names ("O.Dango", "Justin"). Resolved against the actual pool rows,
same team only: exact match first, else every word of the web name present in
the item and every initial matching one. Zero or several candidates is a
warning and the item is dropped — never a best guess.

AUTH. The board is private (unauthenticated API returns 401, checked 15 Sep
2026). Set TRELLO_API_KEY and TRELLO_TOKEN in the environment — a read-only
token is enough. Never commit either; this repo is public. With --quarantine
and Trello unreachable or unauthenticated, the run FAILS rather than quietly
producing a fence-only answer that looks like an overlay answer. Pass
--allow-fence-only-fallback to downgrade that to a loud warning.
"""
import json, os, re, sys, unicodedata, urllib.error, urllib.parse, urllib.request

BOARD = "AEOlxhen"                       # FPL News Management (shortLink; stable across renames)
LIST_NAMES = ("live in model", "quarantined decisions")     # board reshape 17 Sep 2026
APPROVAL_PREFIXES = ("rows in model", "decisions")          # "Rows in model — ticked = authorised" / "Decisions — tick to approve"
LIST_NAME = LIST_NAMES[0]                                    # kept for callers that print it
_NOTE_ITEM = re.compile(r"^\s*\(")                         # "(note, not a row: ...)"
_DECLINE_ITEM = re.compile(r"^\s*decline\b", re.I)         # "Decline — no model change, let the data speak"
TIMEOUT = 20

HERE = os.path.dirname(os.path.abspath(__file__))


class QuarantineUnavailable(RuntimeError):
    """Trello could not be read. Distinct from 'read fine, nothing ticked'."""


# ------------------------------------------------------------------- fetch
def _get(path, params):
    key, token = os.environ.get("TRELLO_API_KEY"), os.environ.get("TRELLO_TOKEN")
    if not key or not token:
        raise QuarantineUnavailable(
            "TRELLO_API_KEY and TRELLO_TOKEN are not set. The board is private, "
            "so the overlay cannot be read. Generate a read-only token at "
            "https://trello.com/power-ups/admin and export both in your shell "
            "(never commit them - this repo is public).")
    q = urllib.parse.urlencode({**params, "key": key, "token": token})
    url = f"https://api.trello.com/1/{path}?{q}"
    try:
        with urllib.request.urlopen(url, timeout=TIMEOUT) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as e:
        raise QuarantineUnavailable(f"Trello returned HTTP {e.code} for {path} "
                                    f"({'bad or expired credentials' if e.code in (401, 403) else e.reason})")
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise QuarantineUnavailable(f"Trello unreachable: {e}")


def fetch_board():
    """Return the board in the plain shape parse_board() takes:
    {"lists": [{"name", "cards": [{"name", "url", "checklists": [{"name", "items": [{"name", "complete"}]}]}]}]}
    """
    lists = _get(f"boards/{BOARD}/lists",
                 {"cards": "open", "card_fields": "name,shortUrl", "fields": "name"})
    checklists = _get(f"boards/{BOARD}/checklists",
                      {"fields": "name,idCard", "checkItem_fields": "name,state"})
    by_card = {}
    for cl in checklists:
        by_card.setdefault(cl["idCard"], []).append({
            "name": cl["name"],
            "items": [{"name": it["name"], "complete": str(it.get("state", "")).lower() == "complete"}
                      for it in cl.get("checkItems", [])]})
    return {"lists": [{"name": lst["name"],
                       "cards": [{"name": c["name"], "url": c.get("shortUrl", ""),
                                  "checklists": by_card.get(c["id"], [])}
                                 for c in lst.get("cards", [])]}
                      for lst in lists]}


# ------------------------------------------------------------------- parse
_WS = r"\s*"
_WINDOW = r"(?:(?:\||→)\s*GWs?\s*(?P<a>\d+)\s*[-–]\s*(?P<b>\d+))?"
_EFFECT = (r"(?P<effect>set\s*→\s*(?P<setv>\d+(?:\.\d+)?)\s*(?P<pct>%)?"
           r"|(?:[×x]|mult)\s*(?P<multv>\d+(?:\.\d+)?))")
_ROW = re.compile(
    r"^(?:(?P<verb>Add|Extend)\s+)?(?P<player>[^|]+?)\s*\|\s*(?P<team>[A-Z]{3})\s*\|\s*"
    r"(?P<field>[a-z0-9]+)\s*\|\s*" + _EFFECT + r"\s*" + _WINDOW + r"(?P<rest>.*)$", re.S)
_REMOVE = re.compile(
    r"^Remove\s+(?:the\s+)?(?P<player>[^|]+?)\s*\|\s*(?P<team>[A-Z]{3})\s*\|\s*"
    r"(?P<field>[a-z0-9]+)\s+row\b(?P<rest>.*)$", re.S)
# A note may follow, but only after a real separator — otherwise a malformed
# effect ("×1.20abc") would parse as ×1.20 with junk quietly swallowed.
_REST_OK = re.compile(r"^\s*(?:$|[—–\-|(;:,])", re.S)


def parse_item(text, mult_fields, set_fields):
    """One checklist item -> (entry, None) or (None, reason). Pure function."""
    t = " ".join(text.split())
    m = _REMOVE.match(t)
    if m:
        field = m["field"]
        if field not in mult_fields | set_fields:
            return None, f"unknown field '{field}'"
        if not _REST_OK.match(m["rest"]):
            return None, "unexpected text after 'row'"
        return dict(action="remove", item_player=m["player"].strip(), team=m["team"],
                    field=field, op=None, value=None, gws=None, gws_raw="ALL"), None
    m = _ROW.match(t)
    if not m:
        return None, "does not match 'Player | TEAM | field | effect [| GWs a-b]'"
    field = m["field"]
    if field in set_fields:
        if m["setv"] is None:
            return None, f"'{field}' must use 'set → value' (an override, not a multiplier)"
        value = float(m["setv"])
        if m["pct"]:
            value /= 100.0
        elif value > 1.0:
            return None, f"set value {m['setv']} > 1 without '%' is ambiguous"
        op = "set"
    elif field in mult_fields:
        if m["multv"] is None:
            return None, f"'{field}' must use a multiplier (×n), not 'set'"
        value, op = float(m["multv"]), "mult"
    else:
        return None, f"unknown field '{field}' (allowed: {sorted(mult_fields | set_fields)})"
    if not _REST_OK.match(m["rest"]):
        return None, f"unexpected text straight after the effect: {m['rest'][:30]!r}"
    gws = None
    if m["a"]:
        a, b = int(m["a"]), int(m["b"])
        if a > b:
            return None, f"window GWs {a}-{b} runs backwards"
        gws = (a, b)
    return dict(action="set", item_player=m["player"].strip(), team=m["team"], field=field,
                op=op, value=value, gws=gws, gws_raw=f"{gws[0]}-{gws[1]}" if gws else "ALL",
                note=m["rest"].strip(" —–-|")), None


def parse_board(board, mult_fields, set_fields):
    """Board dict -> (entries, warnings). Ticked row items on `Rows in model` (Live in model)
    and `Decisions` (Quarantined decisions) checklists; notes and Decline items skipped."""
    entries, warnings = [], []
    lists = [l for l in board.get("lists", []) if l["name"].strip().lower() in LIST_NAMES]
    if not lists:
        warnings.append(f"QUARANTINE: none of {LIST_NAMES} found on the board — nothing read")
    for lst in lists:
        for card in lst["cards"]:
            for cl in card.get("checklists", []):
                if not cl["name"].strip().lower().startswith(APPROVAL_PREFIXES):
                    continue
                for it in cl["items"]:
                    if not it["complete"]:
                        continue
                    if _NOTE_ITEM.match(it["name"]) or _DECLINE_ITEM.match(it["name"]):
                        continue
                    e, why = parse_item(it["name"], mult_fields, set_fields)
                    if e is None:
                        warnings.append(f"QUARANTINE SKIPPED (ticked, unparseable: {why}) "
                                        f"card '{card['name']}' {card['url']}: {it['name'][:120]!r}")
                        continue
                    e.update(card_name=card["name"], card_url=card["url"], raw=it["name"],
                             source="quarantine", confidence="quarantine", date="",
                             why=f"Trello approval: {card['url']}", line=None)
                    e["player"] = e["item_player"]
                    entries.append(e)
    return entries, warnings


# ------------------------------------------------------------ name resolve
def _norm_tokens(s):
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch)).lower()
    s = s.replace("'", "").replace("’", "")
    return [t for t in re.split(r"[\s.\-]+", s) if t]


def name_matches(item_name, pool_name):
    """Exact (normalised) or web-name-within-full-name. Pure; ambiguity is the caller's job."""
    it, pn = _norm_tokens(item_name), _norm_tokens(pool_name)
    if not pn:
        return False
    if it == pn:
        return True
    words = [t for t in pn if len(t) > 1]
    initials = [t for t in pn if len(t) == 1]
    if not words or not all(w in it for w in words):
        return False
    return all(any(t.startswith(i) for t in it if t not in words) for i in initials)


def resolve(entries, rows):
    """Map each entry's item_player to exactly one pool row on the same team.
    Mutates entries (player, resolved); returns warnings. Also drops conflicts."""
    warnings = []
    by_team = {}
    for r in rows:
        by_team.setdefault(r["team"], []).append(r["name"])
    for e in entries:
        names = by_team.get(e["team"], [])
        exact = [n for n in names if _norm_tokens(n) == _norm_tokens(e["item_player"])]
        cands = exact or [n for n in names if name_matches(e["item_player"], n)]
        cands = sorted(set(cands))
        if len(cands) == 1:
            e["player"], e["resolved"] = cands[0], True
        else:
            e["resolved"] = False
            what = "matched no player" if not cands else f"is ambiguous ({', '.join(cands)})"
            warnings.append(f"QUARANTINE UNMATCHED: {e['item_player']}|{e['team']} ({e['field']}) "
                            f"{what} in the pool - dropped. Below the minutes gate, or a "
                            f"name/team to fix on {e['card_url']}")
    # Same (player, team, field) approved twice with different effects: refuse both.
    seen = {}
    for e in entries:
        if e.get("resolved"):
            seen.setdefault((e["player"], e["team"], e["field"]), []).append(e)
    for key, group in seen.items():
        sigs = {(g["action"], g["op"], g["value"], g["gws"]) for g in group}
        if len(sigs) > 1:
            for g in group:
                g["resolved"] = False
            warnings.append(f"QUARANTINE CONFLICT: {key[0]}|{key[1]} {key[2]} is ticked with "
                            f"{len(sigs)} different effects across "
                            f"{', '.join(sorted({g['card_url'] for g in group}))} - all dropped, "
                            f"untick the stale one")
        elif len(group) > 1:
            for g in group[1:]:
                g["resolved"] = False
                g["duplicate"] = True
    return warnings


# ------------------------------------------------------------------ report
def _effect_str(e):
    if e.get("action") == "remove":      # fence entries carry no action key
        return "REMOVE row"
    if e["op"] == "set":
        return f"-> {e['value']:.2f}"
    return f"x{e['value']:.2f}"


def status(e, fence, gw):
    """What the overlay entry does to this run, relative to the committed fence."""
    if not e.get("resolved"):
        return "DUPLICATE (identical tick elsewhere)" if e.get("duplicate") else "DROPPED"
    if e["gws"] and (gw is None or not (e["gws"][0] <= gw <= e["gws"][1])):
        return f"OUT OF WINDOW (GW{gw}) - fence stands"
    same = [f for f in fence if f["player"] == e["player"] and f["team"] == e["team"]
            and f["field"] == e["field"]]
    if e["action"] == "remove":
        return f"REMOVES {len(same)} fence row(s)" if same else "no-op (no fence row)"
    if not same:
        return "NEW - not in fence"
    if len(same) == 1 and same[0]["op"] == e["op"] and abs(same[0]["value"] - e["value"]) < 1e-9:
        return "same as fence (already promoted)"
    was = ", ".join(_effect_str(f) for f in same)
    return f"CHANGES fence ({was})"


def report(ia, bs):
    """--quarantine-report: fetch, parse, resolve, print. Never optimises."""
    board = fetch_board()
    entries, warnings = parse_board(board, ia.MULT_FIELDS, ia.SET_FIELDS)
    rows = bs.load(intel=False)
    warnings += resolve(entries, rows)
    fence, gw = ia.load_adjustments(), ia._current_gw()
    print(f"QUARANTINE OVERLAY — board {BOARD}, lists {LIST_NAMES}, ticked "
          f"'Rows in model' / 'Decisions' items · target GW{gw} (fixture_window.json)\n")
    if not entries:
        print("No ticked, parseable approval items. The overlay would change nothing.")
    else:
        print(f"{'player':<15}{'team':<5}{'field':<8}{'effect':<12}{'GWs':<6}{'this run':<38}card")
        for e in entries:
            print(f"{e['player'][:14]:<15}{e['team']:<5}{e['field']:<8}{_effect_str(e):<12}"
                  f"{e['gws_raw']:<6}{status(e, fence, gw)[:37]:<38}{e['card_url']}")
    for w in warnings:
        print(f"  {w}", file=sys.stderr)
    live = [e for e in entries if status(e, fence, gw).startswith(("NEW", "CHANGES", "REMOVES"))]
    print(f"\n{len(live)} item(s) would change the model relative to ROLE_INTEL.md this run.")


def _load(name, filename):
    import importlib.util
    spec = importlib.util.spec_from_file_location(name, os.path.join(HERE, filename))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


if __name__ == "__main__":
    bs = _load("bs", "build_squad.py")
    try:
        report(bs.ia, bs)
    except QuarantineUnavailable as e:
        sys.exit(f"QUARANTINE UNAVAILABLE: {e}")
