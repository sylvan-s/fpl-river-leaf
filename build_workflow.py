#!/usr/bin/env python3
"""Build the weekly-workflow page — docs/workflow.html.

    python3 build_workflow.py

The diagram itself is WEEKLY_WORKFLOW.svg, authored by hand and already the
canonical picture of the week. This page wraps it in the shared chrome and adds
the things a static SVG cannot carry: where the deadline is, what the squad
currently is, and which files each phase actually touches.

DELIBERATELY THE SIMPLEST PAGE IN THE SET. It exists to prove the shared CSS,
the shared nav and the multi-page verify harness on a surface small enough that
a mistake is obvious, before any of that scaffolding is trusted with the squad
page or the timeseries page.

The SVG carries its own light palette, so it is wrapped in a `.diagram` panel
rather than recoloured — a diagram is a figure, not chrome, and inverting it
would fight its own contrast choices.
"""
import importlib.util, os, datetime as dt

HERE = os.path.dirname(os.path.abspath(__file__))


def _load(mod, fn):
    spec = importlib.util.spec_from_file_location(mod, os.path.join(HERE, fn))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


page_shell = _load("page_shell", "page_shell.py")
squad_state = _load("squad_state", "squad_state.py")

OUT = os.environ.get("FPL_WORKFLOW_OUT") or os.path.join(HERE, "docs", "workflow.html")

# Phase -> (what it decides, which files it touches). Kept beside the diagram so
# the picture and the file list cannot drift apart unnoticed.
PHASES = [
    ("0 · READ", "What is the squad, and what does the data not know?",
     ["TEAM_CHANGE_LOG.md", "ROLE_INTEL.md", "squad.json"]),
    ("1 · SCREEN", "Rank players by position, on three different models.",
     ["build_squad.py", "SELECTION_FRAMEWORK.md", "last16_starts.json"]),
    ("2 · ADJUST", "Reconcile intel against history; price the fixtures.",
     ["fixture_adjust.py", "fixture_window.json", "ROLE_INTEL.md"]),
    ("3 · DECIDE", "Chips, then captaincy — captaincy last, it is free.",
     ["TEAM_CHANGE_LOG.md", "captaincy_odds (MCP)"]),
    ("4 · RUN THE OPTIMISER", "Never propose a transfer the exact solver has not seen.",
     ["optimise_squad.py", "size_bench_value.py"]),
    ("5 · RECORD", "Log predictions BEFORE the deadline — a missed week is lost.",
     ["log_predictions (MCP)", "TEAM_CHANGE_LOG.md", "publish_dashboard.sh"]),
]


def build():
    svg = open(os.path.join(HERE, "WEEKLY_WORKFLOW.svg"), encoding="utf-8").read()
    st = squad_state.load()

    rows = "".join(
        f"<tr><td><b>{p}</b></td><td>{what}</td>"
        f"<td class='mono' style='text-align:left'>{' · '.join(files)}</td></tr>"
        for p, what, files in PHASES)

    chips1 = st.chips_remaining("set1")
    body = f"""
<div class="panel">
  <h2>The week</h2>
  <p class="tests">Teal marks where the method branches by position or by distribution.</p>
  <div class="diagram">{svg}</div>
</div>

<div class="panel">
  <h2>What each phase touches</h2>
  <p class="tests">If the diagram and this table disagree, one of them is stale — fix both.</p>
  <table><thead><tr><th>Phase</th><th>Decides</th><th>Files</th></tr></thead>
  <tbody>{rows}</tbody></table>
</div>

<div class="panel">
  <h2>Current state</h2>
  <table><tbody>
    <tr><td>Gameweek</td><td class="mono">{st.gameweek}</td></tr>
    <tr><td>Formation</td><td class="mono">{st.formation}</td></tr>
    <tr><td>Squad value · bank</td>
        <td class="mono">£{st.value:.1f}m · £{st.bank:.1f}m</td></tr>
    <tr><td>Captain · vice</td><td class="mono">{st.captain} · {st.vice}</td></tr>
    <tr><td>Chips left (set 1)</td>
        <td class="mono">{len(chips1)} — {', '.join(chips1) if chips1 else 'none'}</td></tr>
  </tbody></table>
  <div class="find">Squad state is read from <b>squad.json</b>, the single source of
  truth. It was hardcoded in three Python files until 9 Aug 2026, and one of those
  copies had already gone stale.</div>
</div>
"""
    html = page_shell.shell(
        title="FPL weekly workflow",
        active="workflow",
        subtitle=f"River Leaf FC · squad.json updated {st.updated_utc} · "
                 f"page generated {dt.datetime.now():%Y-%m-%d %H:%M}",
        body=body,
        footer="The diagram is WEEKLY_WORKFLOW.svg. Regenerate this page with "
               "<span class='mono'>python3 build_workflow.py</span>.")

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    open(OUT, "w", encoding="utf-8").write(html)
    return html


if __name__ == "__main__":
    h = build()
    print(f"written: {OUT}  ({len(h)/1024:.0f} KB)")
    assert "cdn.jsdelivr.net/npm/chart.js@4.5.0" in h, "Chart.js tag missing"
    assert "<svg" in h, "diagram did not inline"
    assert 'class="on"' in h, "nav has no active page"
    print("  chart.js pinned, diagram inlined, nav active state set")
