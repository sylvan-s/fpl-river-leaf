#!/usr/bin/env python3
"""Convert FPL_PLAYER_BENCHMARKING.html into the Cowork-artifact variant.

The artifact sandbox has two hard requirements the standalone file does not:
  * light mode only - it renders inside Cowork's light UI
  * Chart.js must be the exact integrity-pinned jsdelivr tag; other CDNs are blocked

Points at the player-benchmarking page (not team-benchmarking) since that's
the one with the actual squad-facing panels this was built to share - see
build_dashboard.py's docstring for why analysis.html split into the two on
2 Sep 2026.

Run after build_player_benchmarking.py.  python3 make_artifact.py
"""
import os, re

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "FPL_PLAYER_BENCHMARKING.html")
OUT = os.path.join(HERE, "FPL_PLAYER_BENCHMARKING_artifact.html")

h = open(SRC, encoding="utf-8").read()

h = re.sub(r'<script src="https://cdnjs\.cloudflare\.com/ajax/libs/Chart\.js/[^"]+"></script>',
 '<script src="https://cdn.jsdelivr.net/npm/chart.js@4.5.0/dist/chart.umd.js" '
 'integrity="sha384-iU8HYtnGQ8Cy4zl7gbNMOhsDTTKX02BTXptVP/vqAWIaTfM7isw76iyZCsjL2eVi" '
 'crossorigin="anonymous"></script>', h)

h = h.replace(':root{--bg:#0f1216;--panel:#171c22;--line:#2a323c;--tx:#e6edf3;--dim:#8b98a5;',
              ':root{color-scheme:light;--bg:#f6f7f9;--panel:#fff;--line:#dde3ea;--tx:#1a1f26;--dim:#5b6673;')
h = h.replace('--e:#c792ea;--grid:#232b34}', '--e:#c792ea;--grid:#e8edf3}')
h = re.sub(r'@media\(prefers-color-scheme:light\)\{:root\{[^}]*\}\}', '', h)
h = h.replace("matchMedia('(prefers-color-scheme: dark)').matches", "false")
h = h.replace('body{margin:0;padding:28px;', 'body{margin:0;padding:20px;')
# The xP table uses --grid for row rules; in light mode that must stay visible.
h = h.replace("table.xp td{text-align:right;padding:5px 8px;border-bottom:1px solid var(--grid)}",
              "table.xp td{text-align:right;padding:5px 8px;border-bottom:1px solid #eef1f5}")

open(OUT, "w", encoding="utf-8").write(h)
assert "chart.js@4.5.0" in h and "integrity=" in h, "chart.js tag not pinned"
assert "color-scheme:light" in h, "light mode not forced"
assert "prefers-color-scheme" not in h, "a dark-mode branch survived"
print(f"written: {OUT}  ({os.path.getsize(OUT)/1024:.0f} KB)")
print("  chart.js pinned, light mode forced, no dark-mode branches")
