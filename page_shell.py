#!/usr/bin/env python3
"""Shared chrome for the dashboard pages: CSS, nav, and the pinned Chart.js tag.

WHY THE CSS IS INLINED RATHER THAN LINKED. A single `assets/style.css` gives one
place to edit; a `<link>` to it would give every page a runtime dependency on a
sibling file. The pages that carry decisions must keep working when opened
straight off disk, so the build INLINES the shared source into each page. One
source, self-contained outputs — not a compromise between them.

THE CHART.JS TAG IS LOAD-BEARING AND EXACT. The artifact sandbox only permits a
short allowlist of CDN URLs with matching integrity hashes. Point this anywhere
else and the page renders COMPLETELY BLANK while `node --check` and
`verify_dashboard.js` both pass, because they stub the DOM and never fetch.
`make_artifact.py` also performs exact string surgery on the `:root` rule and
the light-mode block in the CSS — edit those and check it still asserts.
"""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "assets")

CHARTJS = ('<script src="https://cdn.jsdelivr.net/npm/chart.js@4.5.0/dist/chart.umd.js" '
           'integrity="sha384-iU8HYtnGQ8Cy4zl7gbNMOhsDTTKX02BTXptVP/vqAWIaTfM7isw76iyZCsjL2eVi" '
           'crossorigin="anonymous"></script>')

PAGES = ["squad", "analysis", "player", "workflow", "news"]


def css():
    return open(os.path.join(ASSETS, "style.css"), encoding="utf-8").read()


def nav(active):
    """Shared nav with `active` marked. Unbuilt pages render as inert labels."""
    if active not in PAGES:
        raise ValueError(f"unknown page {active!r}; expected one of {PAGES}")
    html = open(os.path.join(ASSETS, "nav.html"), encoding="utf-8").read()
    return html.replace(f'data-page="{active}"', f'data-page="{active}" class="on"')


def shell(title, active, body, subtitle="", footer=""):
    """A complete self-contained page. Used by every builder except the
    diagnostics page, which has its own template with placeholders."""
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title>
{CHARTJS}
<style>
{css()}</style></head><body>
{nav(active)}
<h1>{title}</h1>
<p class="sub">{subtitle}</p>
{body}
<footer>{footer}</footer>
</body></html>
"""
