#!/usr/bin/env python3
"""RETIRED 12 Aug 2026 — this script's one job is done.

It answered a single question once: does the shrunk empirical-Bayes posterior
actually beat raw and baseline on a season with a full 38 rounds of ground
truth to check against? Result: yes, on all seven metrics feeding
expected_points(). See "Shrinkage backtest — 2025/26 GW1-8 vs GW9-38" in
METHODOLOGY_ALTERNATIVES.md for the full method and numbers.

It is kept in git history rather than deleted outright — this sandbox's
filesystem would not permit an actual `rm` on this file when this retirement
was written, so it was overwritten with this stub instead of removed. It is
no longer called from publish_dashboard.sh, has no entry in page_shell.py's
PAGES, no nav link, and no verify_pages.js entry — running it does nothing
useful and it should not be un-retired without a reason.

docs/priors.html — the dashboard slot this script used to fill — is now built
by build_prediction_tracker.py instead: a live, walk-forward weekly tracker
for the season actually being played, not a one-off historical backtest. See
that file's docstring for why the methodology differs.
"""

if __name__ == "__main__":
    raise SystemExit(
        "build_priors_backtest.py is retired — see its module docstring and "
        "the 'Shrinkage backtest' section of METHODOLOGY_ALTERNATIVES.md. "
        "Use build_prediction_tracker.py for docs/priors.html instead.")
