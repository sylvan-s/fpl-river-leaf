#!/usr/bin/env python3
"""Build the Team Benchmarking page — docs/team-benchmarking.html.

    python3 build_team_benchmarking.py

Split off analysis.html on 2 Sep 2026: the two team-level panels here
(fixture ATT×/DEF× and club xGC-vs-clean-sheets) ask "whose fixtures are
kind" and "which club's defence actually holds up" - club-level questions
with no player to filter by. The four player-level panels (defenders,
midfielders, xGI-vs-delta, xP explorer) went to build_player_benchmarking.py
instead, along with the page's global start% filter, which neither panel
here uses.

REUSES build_dashboard.py's payload RATHER THAN RECOMPUTING IT - same
pattern build_player_benchmarking.py and build_relationships_page.py use;
see build_dashboard.py's own docstring for why.

VERIFY AFTER EVERY CHANGE:
    python3 -c "h=open('FPL_TEAM_BENCHMARKING.html').read(); \
open('dash_team.js','w').write('const DATA'+h.split(chr(60)+'script'+chr(62)+chr(10)+'const DATA',1)[1].split(chr(60)+'/script'+chr(62))[0])"
    node --check dash_team.js && node verify_team_benchmarking.js
"""
import importlib.util, json, os

HERE = os.path.dirname(os.path.abspath(__file__))


def _load(mod, fn):
    spec = importlib.util.spec_from_file_location(mod, os.path.join(HERE, fn))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


page_shell = _load("page_shell", "page_shell.py")
bd = _load("bd_for_team_bench", "build_dashboard.py")   # runs build_dashboard.py; see its docstring
OUT = os.environ.get("FPL_TEAM_BENCH_OUT") or os.path.join(HERE, "FPL_TEAM_BENCHMARKING.html")

PAYLOAD_KEYS = ["fixtures", "club_xgc_cs", "fixture_info", "captured", "season", "generated"]
payload = {k: bd.payload[k] for k in PAYLOAD_KEYS}

HTML = open(os.path.join(HERE, "template_team_benchmarking.html"), encoding="utf-8").read()
HTML = (HTML.replace("/*__CSS__*/", page_shell.css())
            .replace("<!--__NAV__-->", page_shell.nav("teams")))
with open(OUT, "w", encoding="utf-8") as fh:
    fh.write(HTML.replace("/*__DATA__*/null", json.dumps(payload)))
print(f"written: {OUT}  ({os.path.getsize(OUT)/1024:.0f} KB)")
print(f"  {len(bd.club_xgc_cs)} clubs with xGC/CS data | {len(bd.FIXTURES)} fixture rows")
