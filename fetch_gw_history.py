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
    matched, unmatched, moved = {}, [], []
    for p in pool:
        want = {t for t in norm(p["name"]) if len(t) > 1}
        cands = [a for a in arch if want and want <= a["tok"]]
        if len(cands) > 1:
            cands = [a for a in cands if p["pos"] in a["pos"]] or cands
        if len(cands) > 1:
            byteam = [a for a in cands if club_of(a) == p["team"]]
            played = [a for a in cands if a["mins"]]
            cands = byteam if len(byteam) == 1 else (played if len(played) == 1 else cands)
        if len(cands) == 1:
            a = cands[0]
            matched[p["name"] + "|" + p["team"]] = [r for r in rows if r[namecol] == a["name"]]
            was = club_of(a)
            if was and was != p["team"]:
                moved.append({"player": p["name"], "was": was, "now": p["team"],
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
    }
    json.dump(sorted(moved, key=lambda m: (m["now"], m["player"])),
              open(os.path.join(OUTDIR, "club_changes.json"), "w", encoding="utf-8"),
              indent=2, ensure_ascii=False)
    json.dump(prov, open(os.path.join(OUTDIR, "provenance.json"), "w",
                         encoding="utf-8"), indent=2, ensure_ascii=False)
    json.dump(index, open(os.path.join(OUTDIR, "index.json"), "w",
                          encoding="utf-8"), ensure_ascii=False)

    size = sum(os.path.getsize(os.path.join(pdir, f)) for f in os.listdir(pdir))
    print(f"\n  wrote {len(index)} player files ({size/1e6:.1f} MB) to docs/data/players/")
    print(f"  wrote index.json, provenance.json and club_changes.json")
    print(f"\n  CLUB CHANGES DETECTED: {len(moved)} — these priors describe another club")
    for m in sorted(moved, key=lambda m: (m["now"], m["player"])):
        print(f"     {m['player']:<16} {m['was']:<4} -> {m['now']}")
    print(f"\n  provenance stamped: fetched {prov['fetched_utc']}, "
          f"{prov['matched']}/{prov['pool_size']} matched")


if __name__ == "__main__":
    main()
