#!/bin/bash
# Rebuild the dashboard, verify it, and stage it for GitHub Pages.
#
#   bash publish_dashboard.sh   then   git add docs && git commit && git push
#
# Pages serves main:/docs, so docs/index.html is the published page at
#   https://sylvan-s.github.io/fpl-river-leaf/
#
# The verify step is not optional. A syntax error in the inline script leaves
# the HTML looking complete, the right size, and renders nothing at all.

set -euo pipefail
cd "$(dirname "$0")"

echo "==> Rebuilding"
python3 build_dashboard.py

echo "==> Verifying"
python3 -c "h=open('FPL_DIAGNOSTICS.html').read(); \
open('dash.js','w').write('const DATA'+h.split(chr(60)+'script'+chr(62)+chr(10)+'const DATA',1)[1].split(chr(60)+'/script'+chr(62))[0])"
node --check dash.js
node verify_dashboard.js

echo "==> Staging for Pages"
mkdir -p docs
cp FPL_DIAGNOSTICS.html docs/index.html

# The published page is loaded over https, so the CDN tag must be intact —
# this is the one failure local verification cannot catch. See the project
# notes on the blank-render bug.
grep -q 'cdn.jsdelivr.net/npm/chart.js@4.5.0' docs/index.html \
  || { echo "ABORT: Chart.js CDN tag missing or changed — the page will render blank."; exit 1; }

echo
echo "docs/index.html updated ($(du -h docs/index.html | cut -f1))."
echo "Commit and push, then it is live at:"
echo "  https://sylvan-s.github.io/fpl-river-leaf/"
