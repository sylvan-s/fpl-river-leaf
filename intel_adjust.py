#!/usr/bin/env python3
"""Adjustments layer — turns ROLE_INTEL.md narrative intel into model inputs.

WHY. ROLE_INTEL.md could STATE a thesis ("Szoboszlai now takes penalties") but
had no path from that sentence to a number build_squad.py actually uses. This
closes the gap: the `adjustments` fence in ROLE_INTEL.md is parsed here and,
only when the --intel flag is passed, mutates the pool BEFORE
expected_points() runs.

    python3 build_squad.py --intel                    # squad WITH intel applied
    python3 optimise_squad.py --intel --transfers 1    # weekly move, intel-aware
    python3 optimise_squad.py --compare-intel          # WITH vs WITHOUT, one run
    python3 intel_adjust.py                            # audit every entry
    python3 intel_adjust.py --report                   # per-player xP with vs without

Also consumed by fpl_research_mcp.py's captaincy_odds/_cap_rows via
with_intel=True (see _intel_entries() there) - SAME fence, SAME parser,
SAME 0.5x-1.5x cap. Do not fork a second parser there; import this file.

TWO KINDS OF ADJUSTMENT, DELIBERATELY DIFFERENT SHAPES. Agreed with Sylvan
10 Aug 2026.

  BOUNDED MULTIPLIER  (op=mult) — xg90, xa90, xgi90, cbit90, cbirt90
      Guardrailed to 0.5x-1.5x. A thesis is a probability-weighted guess, not a
      measurement; letting one line of narrative move a per-90 rate more than
      50% either way would let intel silently dominate a season of observed
      data. xgi90 is a convenience alias — screens report xGI first — and
      scales xg90 AND xa90 by the same factor, preserving the G/A split
      rather than inventing one.

  OVERRIDE  (op=set) — stp ONLY, NOT subject to the multiplier guardrail
      Unavailability is not a magnitude question. "Out for four weeks" is
      P(start) = 0, and a 0.5x floor would leave a nailed-on absentee at 37%
      when the true number is zero. stp gets its own mechanism precisely
      because the bounded multiplier is the wrong shape for a signal that is
      closer to binary than continuous. Also used the other way — Mosquera's
      minutes opening through injury is stp being SET UP, not just less down.

Any other field/op combination is REJECTED at parse time, not silently
reinterpreted — see the GUARDRAIL checks below. This is enforced in code, not
just documented, because a typo that let a mult entry land on stp would defeat
the entire reason the two are split.

FLAG-GATED, OFF BY DEFAULT. Mirrors USE_EMPIRICAL_DC / --legacy-dc in
build_squad.py: default behaviour (no --intel) must stay byte-identical to
before this file existed.

PROVENANCE. Every entry carries date, confidence and a why — the same
discipline ROLE_INTEL.md already applies to its narrative entries. `gws` is
informational plus a light staleness check: if fixture_window.json says the
live gameweek has passed the entry's end, a warning prints once. It does NOT
auto-expire the entry — ROLE_INTEL.md rule 6 ("prune on contact with
reality") is still a human call; this just makes it hard to miss.

UNMATCHED ENTRIES ARE A BUG, NOT A NO-OP. A typo'd name or team silently
matches nothing — build_squad.load() checks every applied entry against the
full fence and warns loudly on anything that never fired.
"""
import os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROLE_INTEL = os.path.join(HERE, "ROLE_INTEL.md")
FENCE = "adjustments"

MULT_FIELDS = {"xg90", "xa90", "xgi90", "cbit90", "cbirt90"}
SET_FIELDS = {"stp"}
MULT_LO, MULT_HI = 0.5, 1.5

_CACHE = None
_WARNED_STALE = set()


def _extract_fence(text, name):
    m = re.search(rf"```{name}\n(.*?)```", text, re.S)
    return m.group(1) if m else ""


def _current_gw():
    """Best-effort live gameweek, from fixture_window.json. None if unknown."""
    import json
    try:
        w = json.load(open(os.path.join(HERE, "fixture_window.json"), encoding="utf-8"))
        return w.get("generated_for_gw")
    except Exception:
        return None


def _parse_gws(s):
    s = s.strip()
    if not s or s.upper() == "ALL":
        return None
    if "-" in s:
        a, b = s.split("-", 1)
        return (int(a), int(b))
    return (int(s), int(s))


def load_adjustments():
    """Parse the `adjustments` fence in ROLE_INTEL.md. Returns a list of dicts.

    Tolerant of a MISSING fence (returns []) so the module still runs before
    anyone has added one. NOT tolerant of a malformed row inside a fence that
    exists — a silently-dropped adjustment is worse than a loud crash, because
    nothing else would ever show the researcher their entry never fired.
    """
    global _CACHE
    if _CACHE is not None:
        return _CACHE
    try:
        text = open(ROLE_INTEL, encoding="utf-8").read()
    except Exception:
        _CACHE = []
        return _CACHE
    block = _extract_fence(text, FENCE)
    out = []
    for lineno, line in enumerate(block.splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = [p.strip() for p in line.split("|")]
        if len(parts) != 9:
            raise SystemExit(
                f"ROLE_INTEL.md `adjustments` fence, line {lineno}: expected 9 "
                f"fields (player|team|field|op|value|gws|confidence|date|why), "
                f"got {len(parts)}: {line!r}")
        player, team, field, op, value, gws, conf, date, why = parts
        try:
            value = float(value)
        except ValueError:
            raise SystemExit(f"ROLE_INTEL.md `adjustments` line {lineno}: "
                              f"value {value!r} is not a number")
        entry = dict(player=player, team=team, field=field, op=op, value=value,
                     gws=_parse_gws(gws), gws_raw=gws, confidence=conf, date=date,
                     why=why, line=lineno)
        # GUARDRAIL — structurally enforced, not just documented.
        if field in SET_FIELDS:
            if op != "set":
                raise SystemExit(f"ROLE_INTEL.md `adjustments` line {lineno}: "
                                  f"field '{field}' must use op=set — "
                                  f"unavailability is an override, not a "
                                  f"bounded multiplier")
        elif field in MULT_FIELDS:
            if op != "mult":
                raise SystemExit(f"ROLE_INTEL.md `adjustments` line {lineno}: "
                                  f"field '{field}' must use op=mult, "
                                  f"guardrailed to {MULT_LO}x-{MULT_HI}x")
        else:
            raise SystemExit(f"ROLE_INTEL.md `adjustments` line {lineno}: "
                              f"unknown field '{field}' — must be one of "
                              f"{sorted(MULT_FIELDS | SET_FIELDS)}")
        out.append(entry)
    _CACHE = out
    return out


def _stale_warn(entry):
    gw = _current_gw()
    if gw is None or entry["gws"] is None:
        return
    _, end = entry["gws"]
    key = (entry["player"], entry["team"], entry["field"])
    if gw > end and key not in _WARNED_STALE:
        _WARNED_STALE.add(key)
        print(f"  INTEL STALE: {entry['player']} ({entry['field']}) was scoped "
              f"to GW{entry['gws_raw']}, live GW is {gw} — review ROLE_INTEL.md",
              file=sys.stderr)


def entries_for(name, team):
    return [e for e in load_adjustments() if e["player"] == name and e["team"] == team]


def apply(r):
    """Mutate pool row r in place per its matching entries. Returns entries applied.

    Called from build_squad.load() only when --intel is active, and must run
    BEFORE expected_points(r), which reads xg90/xa90/cbit90/cbirt90 at call time.
    """
    applied = []
    for e in entries_for(r["name"], r["team"]):
        _stale_warn(e)
        if e["op"] == "mult":
            factor = min(max(e["value"], MULT_LO), MULT_HI)
            if e["field"] == "xgi90":
                r["xg90"] *= factor
                r["xa90"] *= factor
                r["xgi90"] *= factor
            else:
                r[e["field"]] *= factor
        elif e["op"] == "set" and e["field"] == "stp":
            r["stp"] = min(max(e["value"], 0.0), 1.0)
        applied.append(e)
    if applied:
        r["intel_applied"] = applied
    return applied


def _clamped_str(e):
    if e["op"] == "mult":
        c = min(max(e["value"], MULT_LO), MULT_HI)
        flag = " (CLAMPED)" if not (MULT_LO <= e["value"] <= MULT_HI) else ""
        return f"x{c:.2f}{flag}"
    c = min(max(e["value"], 0.0), 1.0)
    flag = " (CLAMPED)" if not (0.0 <= e["value"] <= 1.0) else ""
    return f"-> {c:.2f}{flag}"


def report():
    """Per-player xP with vs without intel, for every player the fence touches."""
    import importlib.util as _il
    spec = _il.spec_from_file_location("bs", os.path.join(HERE, "build_squad.py"))
    bs = _il.module_from_spec(spec); spec.loader.exec_module(bs)
    entries = load_adjustments()
    if not entries:
        print("No entries in the `adjustments` fence — nothing to report.")
        return
    off = {r["name"]: r for r in bs.load(intel=False)}
    on = {r["name"]: r for r in bs.load(intel=True)}
    affected = sorted({e["player"] for e in entries})
    print(f"{'player':<14}{'pos':<5}{'stp off':>8}{'stp on':>8}"
          f"{'xP off':>8}{'xP on':>8}{'delta':>8}   fields")
    for name in affected:
        r0 = off.get(name)
        r1 = on.get(name)
        if not r0 or not r1:
            print(f"  {name:<14} not in the pool (below the minutes gate?)")
            continue
        fields = sorted({e["field"] for e in entries_for(r0["name"], r0["team"])})
        print(f"{name:<14}{r0['pos']:<5}{r0['stp']*100:>7.0f}%{r1['stp']*100:>7.0f}%"
              f"{r0['score']:>8.2f}{r1['score']:>8.2f}{r1['score']-r0['score']:>+8.2f}"
              f"   {', '.join(fields)}")


def main():
    if "--report" in sys.argv:
        report()
        return
    entries = load_adjustments()
    if not entries:
        print("No entries in the `adjustments` fence — ROLE_INTEL.md has "
              "nothing for intel_adjust.py to parse yet.")
        return
    print(f"{len(entries)} adjustment entr{'y' if len(entries) == 1 else 'ies'} "
          f"in ROLE_INTEL.md\n")
    print(f"{'player':<14}{'team':<5}{'field':<9}{'op':<15}{'gws':<8}"
          f"{'conf':<8}{'date':<12}why")
    for e in entries:
        print(f"{e['player']:<14}{e['team']:<5}{e['field']:<9}{_clamped_str(e):<15}"
              f"{e['gws_raw']:<8}{e['confidence']:<8}{e['date']:<12}{e['why']}")


if __name__ == "__main__":
    main()
