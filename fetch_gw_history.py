#!/usr/bin/env python3
"""Fetch 2025/26 per-gameweek history and split it into per-player files.

    python3 fetch_gw_history.py           # fetch, match, write
    python3 fetch_gw_history.py --inspect # fetch and REPORT ONLY, write nothing

Feeds the player timeseries page. Source is the same community archive that
`last16_starts.json` already uses.

DECIDED 9 Aug 2026: FETCH, DO NOT VENDOR. Keeps megabytes of someone else's data
out of the repo. The cost is that the build becomes network-dependent and can go
quietly stale, so provenance is stamped and rendered, and this script FAILS
rather than falling back to a cached copy without saying so.

    THIS IS NOT THE OFFICIAL FPL API. It is a community archive that mirrors it
    gameweek by gameweek. Treat it as well-sourced but externally derived, and
    re-verify before leaning on it for a close call.

NAME MATCHING IS THE HARD PART, AND IT IS NOT NEW. Element ids are reassigned
every season, so last season's id cannot address this season's player. Matching
must go through names — exactly the problem `last16_starts.json` solved, where
262 of 267 matched and the 5 failures were listed rather than hidden. Same rule
here: every unmatched player is reported. A silent match rate is worthless.

RUN --inspect FIRST. It prints the columns actually present in the archive
rather than the ones this script hopes for, and writes nothing.
"""
import argparse, csv, io, json, os, re, sys, urllib.request, datetime as dt

HERE = os.path.dirname(os.path.abspath(__file__))
SEASON = "2025-26"
BASE = "https://raw.githubusercontent.com/vaastav/Fantasy-Premier-League/master"
MERGED = f"{BASE}/data/{SEASON}/gws/merged_gw.csv"
OUTDIR = os.path.join(HERE, "docs", "data")
CACHE = os.path.join(HERE, ".cache_merged_gw.csv")      # gitignored

# Columns worth keeping if present. Absent ones are reported, never faked.
# defensive_contribution and xP were not asked for but are present and matter:
# the first IS the DC metric the defender/midfielder screens threshold on, the
# second is FPL's own expected points — a free external benchmark for our model.
WANT = ["round", "position", "team", "kickoff_time", "opponent_team",
        "defensive_contribution", "xP",
        "minutes", "starts", "total_points", "goals_scored", "assists",
        "expected_goals", "expected_assists", "expected_goal_involvements",
        "expected_goals_conceded", "clean_sheets", "goals_conceded", "saves",
        "bonus", "bps", "yellow_cards", "red_cards", "value", "was_home",
        "opponent_team", "team_h_score", "team_a_score", "clearances_blocks_interceptions",
        "tackles", "recoveries"]


def fetch(url, use_cache=True):
    if use_cache and os.path.exists(CACHE):
        age = (dt.datetime.now() -
               dt.datetime.fromtimestamp(os.path.getmtime(CACHE))).total_seconds()
        print(f"  using local cache ({os.path.getsize(CACHE)/1e6:.1f} MB, "
              f"{age/3600:.1f}h old) — delete .cache_merged_gw.csv to force a refetch")
        return open(CACHE, encoding="utf-8", errors="replace").read()
    print(f"  GET {url}")
    try:
        with urllib.request.urlopen(url, timeout=120) as r:
            raw = r.read().decode("utf-8", errors="replace")
    except Exception as e:
        raise SystemExit(
            f"FETCH FAILED: {e}\n"
            f"  This script does not fall back to stale data — a page built from a\n"
            f"  silently old archive is the same failure class as a stale fixture\n"
            f"  window: it looks right and is wrong. Fix the network and re-run.")
    open(CACHE, "w", encoding="utf-8").write(raw)
    print(f"  {len(raw)/1e6:.1f} MB cached to {os.path.basename(CACHE)}")
    return raw


def norm(s):
    """Lowercase, strip accents and punctuation, return tokens."""
    import unicodedata
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    return [t for t in re.sub(r"[^a-z ]", " ", s.lower()).split() if t]


# The archive names clubs in full; our pool uses FPL short codes.
FULL2CODE = {'Arsenal':'ARS','Aston Villa':'AVL','Bournemouth':'BOU','Brentford':'BRE',
 'Brighton':'BHA','Burnley':'BUR','Chelsea':'CHE','Crystal Palace':'CRY','Everton':'EVE',
 'Fulham':'FUL','Leeds':'LEE','Liverpool':'LIV','Man City':'MCI','Man Utd':'MUN',
 'Newcastle':'NEW',"Nott'm Forest":'NFO','Spurs':'TOT','Sunderland':'SUN',
 'West Ham':'WHU','Wolves':'WOL'}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--inspect", action="store_true",
                    help="report the archive's shape and write nothing")
    ap.add_argument("--no-cache", action="store_true")
    args = ap.parse_args()

    print(f"Archive: {SEASON} · vaastav/Fantasy-Premier-League")
    raw = fetch(MERGED, use_cache=not args.no_cache)
    rdr = csv.DictReader(io.StringIO(raw))
    rows = list(rdr)
    cols = rdr.fieldnames or []

    print(f"\n  rows: {len(rows):,}")
    print(f"  columns present ({len(cols)}):")
    for c in cols:
        print(f"     {c}")
    have = [c for c in WANT if c in cols]
    missing = [c for c in WANT if c not in cols]
    print(f"\n  of the {len(WANT)} wanted: {len(have)} present, {len(missing)} MISSING")
    if missing:
        print(f"     missing: {', '.join(missing)}")
        print("     (missing columns are omitted, never fabricated)")

    namecol = "name" if "name" in cols else None
    if not namecol:
        raise SystemExit("no 'name' column — archive layout has changed, stop and look")
    gws = sorted({int(r["round"]) for r in rows if r.get("round", "").isdigit()})
    print(f"  gameweeks: {min(gws)}–{max(gws)} ({len(gws)} distinct)")
    print(f"  distinct players: {len({r[namecol] for r in rows}):,}")

    if args.inspect:
        print("\n--inspect: nothing written. Re-run without it to build the files.")
        return

    # --- match archive names to our pool ---------------------------------
    import importlib.util
    spec = importlib.util.spec_from_file_location("bs", os.path.join(HERE, "build_squad.py"))
    bs = importlib.util.module_from_spec(spec); spec.loader.exec_module(bs)
    pool = bs.load()

    from collections import Counter, defaultdict
    agg = defaultdict(lambda: {"mins": Counter(), "pos": set()})
    for r in rows:
        m = int(r.get("minutes") or 0)
        agg[r[namecol]]["pos"].add(r.get("position", ""))
        if m:
            agg[r[namecol]]["mins"][r.get("team", "")] += m
    arch = [{"name": n, "tok": set(norm(n)), "pos": v["pos"], "mins": v["mins"]}
            for n, v in agg.items()]
    club_of = lambda a: FULL2CODE.get(a["mins"].most_common(1)[0][0]) if a["mins"] else None

    # web_name is often a nickname ("Virgil", "Raya"), so an exact name match
    # fails constantly. Token-SUBSET matching handles it: every token of the
    # short name must appear in the archive's full name. Ties are broken by
    # position first and club only as a last resort — club is precisely what is
    # unreliable here, so leaning on it would defeat the purpose.
    #
    # TWO CLUBS PER ROW SINCE 7 Sep 2026, and the distinction is the whole
    # point of this sweep:
    #
    #   p["team_prior"] — the frozen 8 Aug 2026 snapshot's club. Contemporary
    #                     with THIS archive, so it is the right key for
    #                     breaking an archive name tie.
    #   p["team"]       — the live club from bootstrap-static. What the player
    #                     actually plays for now, so it is the right thing to
    #                     compare the archive's club AGAINST when asking
    #                     "does this prior describe another club?".
    #
    # WHY THIS CHANGED. Until now both sides of that comparison came from the
    # same frozen snapshot, so the sweep could only ever see a move that had
    # already completed BEFORE the snapshot was captured on 8 Aug — which is
    # why the 9 Aug run found exactly the 19 summer moves and has been blind
    # to every deadline-day one since. It did not fail loudly on Konsa
    # (AVL->ARS): it matched him cleanly to "Ezri Konsa Ngoyo", read AVL from
    # the archive, read AVL from the pool, and correctly concluded nothing had
    # changed. Both fields were stale in the same direction, so there was no
    # disagreement left for the sweep to detect and nothing landed in either
    # club_changes.json or the unmatched list. The name matching was never
    # the problem. See build_squad.py's "CLUB" comment in load().
    matched, unmatched, moved = {}, [], []
    for p in pool:
        prior = p.get("team_prior") or p["team"]
        want = {t for t in norm(p["name"]) if len(t) > 1}
        cands = [a for a in arch if want and want <= a["tok"]]
        if len(cands) > 1:
            cands = [a for a in cands if p["pos"] in a["pos"]] or cands
        if len(cands) > 1:
            byteam = [a for a in cands if club_of(a) == prior]
            played = [a for a in cands if a["mins"]]
            cands = byteam if len(byteam) == 1 else (played if len(played) == 1 else cands)
        if len(cands) == 1:
            a = cands[0]
            matched[p["name"] + "|" + p["team"]] = [r for r in rows if r[namecol] == a["name"]]
            was = club_of(a)
            if was and was != p["team"]:
                moved.append({"player": p["name"], "was": was, "now": p["team"],
                              # The snapshot's club, so a reader can tell a
                              # move the frozen pool already knew about
                              # (snapshot == now) from one it missed
                              # (snapshot == was) — the second kind is what
                              # was invisible before 7 Sep 2026.
                              "snapshot": prior,
                              "seen_by_snapshot": prior == p["team"],
                              "archive_name": a["name"]})
        else:
            unmatched.append(f"{p['name']}|{p['team']}")

    print(f"\n  matched {len(matched)} of {len(pool)} pool players")
    if unmatched:
        print(f"  UNMATCHED ({len(unmatched)}) — listed, not hidden:")
        for u in sorted(unmatched):
            print(f"     {u}")

    # --- write ------------------------------------------------------------
    pdir = os.path.join(OUTDIR, "players")
    os.makedirs(pdir, exist_ok=True)
    index = []
    for p in pool:
        recs = matched.get(p["name"] + "|" + p["team"])
        if not recs:
            continue
        series = []
        for r in sorted(recs, key=lambda r: int(r["round"])):
            series.append({c: r[c] for c in have if r.get(c) not in (None, "")})
        slug = "-".join(norm(p["name"])) + "-" + p["team"].lower()
        json.dump({"name": p["name"], "team": p["team"], "pos": p["pos"],
                   "season": SEASON, "gw": series},
                  open(os.path.join(pdir, f"{slug}.json"), "w", encoding="utf-8"),
                  ensure_ascii=False)
        index.append({"name": p["name"], "team": p["team"], "pos": p["pos"],
                      "slug": slug, "gws": len(series)})

    prov = {
        "source": "vaastav/Fantasy-Premier-League",
        "source_url": MERGED,
        "caveat": ("Community archive mirroring the official FPL API gameweek by "
                   "gameweek. NOT the official API. Externally derived."),
        "season": SEASON,
        "fetched_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "rows_in_source": len(rows),
        "gameweeks": [min(gws), max(gws)],
        "columns_kept": have,
        "columns_missing": missing,
        "pool_size": len(pool),
        "matched": len(matched),
        "unmatched": sorted(unmatched),
        "club_changes": len(moved),
        # Which side of each comparison is live. Before 7 Sep 2026 both were
        # the frozen snapshot, which is why this sweep could not see a move
        # made after 8 Aug — see the comment above the matching loop.
        "pool_club_source": "live bootstrap-static via build_squad.load()",
        "club_changes_missed_by_snapshot": sum(1 for m in moved
                                               if not m["seen_by_snapshot"]),
    }
    json.dump(sorted(moved, key=lambda m: (m["now"], m["player"])),
              open(os.path.join(OUTDIR, "club_changes.json"), "w", encoding="utf-8"),
              indent=2, ensure_ascii=False)
    json.dump(prov, open(os.path.join(OUTDIR, "provenance.json"), "w",
                         encoding="utf-8"), indent=2, ensure_ascii=False)
    json.dump(index, open(os.path.join(OUTDIR, "index.json"), "w",
                          encoding="utf-8"), ensure_ascii=False)

    # A slug carries the club (konsa-avl -> konsa-ars), so correcting a club
    # renames the file. The old one is not overwritten, it is ORPHANED: still
    # committed, no longer referenced by index.json, and describing a player
    # at a club he has left. Deleted here, by name, rather than left to rot —
    # every one of these is regenerated by re-running this script.
    keep = {e["slug"] + ".json" for e in index}
    orphans = sorted(f for f in os.listdir(pdir)
                     if f.endswith(".json") and f not in keep)
    for f in orphans:
        os.remove(os.path.join(pdir, f))

    size = sum(os.path.getsize(os.path.join(pdir, f)) for f in os.listdir(pdir))
    print(f"\n  wrote {len(index)} player files ({size/1e6:.1f} MB) to docs/data/players/")
    print(f"  wrote index.json, provenance.json and club_changes.json")
    if orphans:
        print(f"  removed {len(orphans)} orphaned player file(s) no longer in "
              f"the index: {', '.join(orphans)}")
    print(f"\n  CLUB CHANGES DETECTED: {len(moved)} — these priors describe another club")
    for m in sorted(moved, key=lambda m: (m["now"], m["player"])):
        flag = "" if m["seen_by_snapshot"] else "   <- MISSED BY THE FROZEN SNAPSHOT"
        print(f"     {m['player']:<16} {m['was']:<4} -> {m['now']}{flag}")
    late = [m for m in moved if not m["seen_by_snapshot"]]
    if late:
        print(f"\n  {len(late)} of those moved AFTER the 8 Aug snapshot was frozen, so "
              f"nothing in this repo\n  knew about them until now. Each one needs a "
              f"`contaminated` fence line in ROLE_INTEL.md\n  before its prior can be "
              f"trusted — the corrected club fixes the FIXTURE RUN, not\n  the rates, "
              f"which still describe the old club:")
        for m in sorted(late, key=lambda m: m["player"]):
            print(f"     {m['player']:<16} | {m['was']} -> {m['now']}; "
                  f"2025/26 record is a {m['was']} record")
    print(f"\n  provenance stamped: fetched {prov['fetched_utc']}, "
          f"{prov['matched']}/{prov['pool_size']} matched")


if __name__ == "__main__":
    main()
