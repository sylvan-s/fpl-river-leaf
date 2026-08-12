#!/usr/bin/env python3
"""REMOVED 12 Aug 2026 — the weekly-workflow page was removed from the site.

It used to wrap WEEKLY_WORKFLOW.svg (still present, untouched) in the shared
dashboard chrome at docs/workflow.html. Removed on request; the diagram it
wrapped carried nothing the rest of the site doesn't already say elsewhere
(the squad page's chip-strategy panel now covers the weekly review checklist).

Kept in git history rather than deleted outright — this sandbox's filesystem
would not permit an actual `rm`/`git rm` on this file when the removal was
made, so it was overwritten with this stub instead (same situation as
build_priors_backtest.py's retirement). It is no longer called from
publish_dashboard.sh, has no entry in page_shell.py's PAGES, no nav link, and
no verify_pages.js entry - running it does nothing useful.
"""

if __name__ == "__main__":
    raise SystemExit(
        "build_workflow.py is removed - the weekly workflow page is no longer "
        "part of the site. See this file's module docstring.")
