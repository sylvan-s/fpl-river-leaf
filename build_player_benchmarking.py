#!/usr/bin/env python3
"""Build the Player Benchmarking page — docs/player-benchmarking.html.

    python3 build_player_benchmarking.py

Split off analysis.html on 2 Sep 2026: panels 1-4 here (defenders, midfielders,
xGI-vs-delta, xP explorer) all ask "which PLAYER should I pick" and all share
the page's one global start% filter. The two team-level panels (fixture runs,
club defensive solidity) went to build_team_benchmarking.py instead - they
answer a different question ("whose fixtures are kind") and had nothing to do
with that filter.

DATA-SOURCE SELECTOR (prior/raw/shrunk), added 2 Sep 2026 - same three
estimators as optimise_squad.py's --estimator flag, computed by
build_dashboard.py's `_build_estimator_variant()` and shipped as
DATA.estimators.{prior,raw,shrunk} so the page can switch which one every
chart reads from with no rebuild. Needs live network for raw/shrunk; degrades
to prior-only (with a banner) if unreachable - see DATA.estimator_live.

REUSES build_dashboard.py's payload RATHER THAN RECOMPUTING IT - same
"single pipeline, multiple consumers" pattern build_relationships_page.py
already established (see that file's docstring, and build_dashboard.py's own
docstring for why splitting the page must not mean splitting the pipeline).

VERIFY AFTER EVERY CHANGE:
    python3 -c "h=open('FPL_PLAYER_BENCHMARKING.html').read(); \
open('dash_player.js','w').write('const DATA'+h.split(chr(60)+'script'+chr(62)+chr(10)+'const DATA',1)[1].split(chr(60)+'/script'+chr(62))[0])"
    node --check dash_player.js && node verify_player_benchmarking.js

The extract MUST go to ./dash_player.js - verify_player_benchmarking.js does
`require('./dash_player.js')` (same /tmp-vs-cwd bug class build_dashboard.py's
docstring used to warn about; see publish_dashboard.sh for the real sequence).
"""
import importlib.util, json, os

HERE = os.path.dirname(os.path.abspath(__file__))


def _load(mod, fn):
    spec = importlib.util.spec_from_file_location(mod, os.path.join(HERE, fn))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


page_shell = _load("page_shell", "page_shell.py")
bd = _load("bd_for_player_bench", "build_dashboard.py")   # runs build_dashboard.py; see its docstring
OUT = os.environ.get("FPL_PLAYER_BENCH_OUT") or os.path.join(HERE, "FPL_PLAYER_BENCHMARKING.html")

# "rows"/"stats"/"med_xgc"/"med_xgi_m" dropped in favour of "estimators" (2 Sep
# 2026, the raw/prior/shrunk data-source selector) - estimators["prior"] is
# exactly what those used to be, just nested, so nothing here loses data;
# carrying both would just duplicate the prior rows a second time.
PAYLOAD_KEYS = ["estimators", "estimator_live", "kpanel", "med_xgi_mid",
                "captured", "season", "generated", "last16", "fixture_info"]
payload = {k: bd.payload[k] for k in PAYLOAD_KEYS}

HTML = open(os.path.join(HERE, "template_player_benchmarking.html"), encoding="utf-8").read()
# Shared chrome, inlined so the output stays a single self-contained file.
HTML = (HTML.replace("/*__CSS__*/", page_shell.css())
            .replace("<!--__NAV__-->", page_shell.nav("players")))
with open(OUT, "w", encoding="utf-8") as fh:
    fh.write(HTML.replace("/*__DATA__*/null", json.dumps(payload)))
print(f"written: {OUT}  ({os.path.getsize(OUT)/1024:.0f} KB)")
print(f"  players {len(bd.rows)} | DEF {len(bd.D)} MID {len(bd.M)} FWD {len(bd.F_)} GKP {len(bd.G)}")
