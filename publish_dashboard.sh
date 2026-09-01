#!/bin/bash
# Rebuild every dashboard page, verify them all, and stage them for GitHub Pages.
#
#   bash publish_dashboard.sh   then   git add docs && git commit && git push
#
# Pages serves main:/docs → https://sylvan-s.github.io/fpl-river-leaf/
#
# THREE LAYERS OF VERIFICATION, ALL REQUIRED:
#   verify_dashboard.js — DEEP, diagnostics page only. Runs its script against a
#                         stubbed DOM and asserts every panel and filter works.
#   verify_priors.js    — DEEP, priors page only. Same trade, different reason:
#                         priors.html is the one page that FETCHES its data
#                         (docs/adr/0002) instead of carrying it inline, so
#                         "the script parses" no longer implies "the page
#                         renders". Runs it against a stubbed DOM and a real
#                         payload, and checks the URLs it asks for are files
#                         that actually ship.
#   verify_pages.js     — SHALLOW, every page. Size, pinned CDN tag, integrity
#                         hash, one active nav tab, no leftover placeholders,
#                         and that all inline scripts parse.
#
# None is optional. A syntax error leaves the HTML looking complete, the
# right size, and rendering nothing; a CDN drift renders the page blank while
# every local check passes, because stubs never fetch; and a mistyped data path
# on priors.html has no local symptom whatsoever until it is deployed.

set -euo pipefail
cd "$(dirname "$0")"

echo "==> Validating squad.json"
python3 squad_state.py

echo
echo "==> Building"
python3 build_dashboard.py
python3 build_relationships_page.py
python3 build_squad_page.py
python3 build_intel_page.py
python3 build_player_page.py
python3 build_prediction_tracker.py

echo
echo "==> Deep verify: diagnostics page"
python3 -c "h=open('FPL_DIAGNOSTICS.html').read(); \
open('dash.js','w').write('const DATA'+h.split(chr(60)+'script'+chr(62)+chr(10)+'const DATA',1)[1].split(chr(60)+'/script'+chr(62))[0])"
node --check dash.js
node verify_dashboard.js

echo
echo "==> Deep verify: priors page (fetched data)"
node verify_priors.js

echo
echo "==> Staging for Pages"
mkdir -p docs
# build_squad_page.py writes docs/index.html directly — the squad page is now
# the landing page, so the already-shared root URL opens on the team rather
# than on the methodology diagnostics. The diagnostics live at analysis.html.
cp FPL_DIAGNOSTICS.html docs/analysis.html

echo
echo "==> Structural verify: all pages"
node verify_pages.js

echo
echo "Published pages:"
for f in docs/*.html; do printf "  %-22s %s\n" "$f" "$(du -h "$f" | cut -f1)"; done
cat <<'EOF'

Commit and push, then live at:
  https://sylvan-s.github.io/fpl-river-leaf/                    squad — the landing page
  https://sylvan-s.github.io/fpl-river-leaf/analysis.html       methodology diagnostics
  https://sylvan-s.github.io/fpl-river-leaf/relationships.html  statistical relationships
  https://sylvan-s.github.io/fpl-river-leaf/news.html           availability & intel
  https://sylvan-s.github.io/fpl-river-leaf/player.html         player timeseries
  https://sylvan-s.github.io/fpl-river-leaf/priors.html         prior vs reality (live weekly tracker)

Note: priors.html reads docs/data/*.json at load, so it needs to be SERVED, not
opened off disk. Locally:  (cd docs && python3 -m http.server)  then
http://localhost:8000/priors.html — a file:// URL will show its "Data not
loaded" panel, which is the page working correctly, not a build failure.
EOF
