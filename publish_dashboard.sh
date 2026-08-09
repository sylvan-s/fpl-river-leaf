#!/bin/bash
# Rebuild every dashboard page, verify them all, and stage them for GitHub Pages.
#
#   bash publish_dashboard.sh   then   git add docs && git commit && git push
#
# Pages serves main:/docs → https://sylvan-s.github.io/fpl-river-leaf/
#
# TWO LAYERS OF VERIFICATION, BOTH REQUIRED:
#   verify_dashboard.js — DEEP, diagnostics page only. Runs its script against a
#                         stubbed DOM and asserts every panel and filter works.
#   verify_pages.js     — SHALLOW, every page. Size, pinned CDN tag, integrity
#                         hash, one active nav tab, no leftover placeholders,
#                         and that all inline scripts parse.
#
# Neither is optional. A syntax error leaves the HTML looking complete, the
# right size, and rendering nothing; a CDN drift renders the page blank while
# every local check passes, because stubs never fetch.

set -euo pipefail
cd "$(dirname "$0")"

echo "==> Validating squad.json"
python3 squad_state.py

echo
echo "==> Building"
python3 build_dashboard.py
python3 build_workflow.py

echo
echo "==> Deep verify: diagnostics page"
python3 -c "h=open('FPL_DIAGNOSTICS.html').read(); \
open('dash.js','w').write('const DATA'+h.split(chr(60)+'script'+chr(62)+chr(10)+'const DATA',1)[1].split(chr(60)+'/script'+chr(62))[0])"
node --check dash.js
node verify_dashboard.js

echo
echo "==> Staging for Pages"
mkdir -p docs
# index.html stays the diagnostics page until the Squad page exists — the live
# URL is already shared, so it must not 404 mid-build-out. analysis.html is its
# permanent home, and index.html becomes Squad when that page lands.
cp FPL_DIAGNOSTICS.html docs/index.html
cp FPL_DIAGNOSTICS.html docs/analysis.html

echo
echo "==> Structural verify: all pages"
node verify_pages.js

echo
echo "Published pages:"
for f in docs/*.html; do printf "  %-22s %s\n" "$f" "$(du -h "$f" | cut -f1)"; done
cat <<'EOF'

Commit and push, then live at:
  https://sylvan-s.github.io/fpl-river-leaf/            (diagnostics, for now)
  https://sylvan-s.github.io/fpl-river-leaf/analysis.html
  https://sylvan-s.github.io/fpl-river-leaf/workflow.html
EOF
