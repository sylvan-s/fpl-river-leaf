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
WANT = ["round", "minutes", "starts", "total_points", "goals_scored", "assists",
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
    """Lowercase, strip accents and punctuation — for name matching only."""
    import unicodedata
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^a-z ]", "", s.lower()).strip()


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

    by_norm = {}
    for r in rows:
        by_norm.setdefault(norm(r[namecol]), []).append(r)

    matched, unmatched = {}, []
    for p in pool:
        key = norm(p["name"])
        hit = by_norm.get(key)
        if not hit:                       # surname-token fallback
            cands = [k for k in by_norm if key and key.split()[-1] == k.split()[-1]]
            hit = by_norm[cands[0]] if len(cands) == 1 else None
        if hit:
            matched[p["name"]] = hit
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
        recs = matched.get(p["name"])
        if not recs:
            continue
        series = []
        for r in sorted(recs, key=lambda r: int(r["round"])):
            series.append({c: r[c] for c in have if r.get(c) not in (None, "")})
        slug = re.sub(r"[^a-z0-9]+", "-", norm(p["name"])).strip("-")
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
    }
    json.dump(prov, open(os.path.join(OUTDIR, "provenance.json"), "w",
                         encoding="utf-8"), indent=2, ensure_ascii=False)
    json.dump(index, open(os.path.join(OUTDIR, "index.json"), "w",
                          encoding="utf-8"), ensure_ascii=False)

    size = sum(os.path.getsize(os.path.join(pdir, f)) for f in os.listdir(pdir))
    print(f"\n  wrote {len(index)} player files ({size/1e6:.1f} MB) to docs/data/players/")
    print(f"  wrote index.json and provenance.json")
    print(f"\n  provenance stamped: fetched {prov['fetched_utc']}, "
          f"{prov['matched']}/{prov['pool_size']} matched")


if __name__ == "__main__":
    main()
