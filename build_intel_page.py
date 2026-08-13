#!/usr/bin/env python3
"""Build the availability & intel page — docs/news.html.

    python3 build_intel_page.py

RENDERS ROLE_INTEL.md — IT DOES NOT DUPLICATE IT. That file already enforces the
discipline this page needs: every entry dated, sourced, and carrying a
falsifiable check. Copying any of it into a second store would create exactly
the drift squad.json was written to end. So the machine-readable fences are
parsed, and the narrative entries are read from their headings.

WHAT THIS PAGE DELIBERATELY WILL NOT DO. It has no live injury or suspension
feed. Everything here is built from the repository at build time, and the page
says so in as many words. A page that implies live availability while showing a
static snapshot is worse than no page — the reader cannot tell the difference,
and the failure is silent.

THE DISCIPLINE SECTION IS A TRAP, HANDLED. The snapshot's yellow-card counts are
2025/26 totals. Premier League yellow cards RESET each season, so they are not a
current suspension risk — at GW1 every player is on zero. They are shown as a
booking TENDENCY, labelled as such, because that is the only honest reading.
"""
import importlib.util, os, re, datetime as dt

HERE = os.path.dirname(os.path.abspath(__file__))


def _load(mod, fn):
    spec = importlib.util.spec_from_file_location(mod, os.path.join(HERE, fn))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


page_shell = _load("page_shell", "page_shell.py")
squad_state = _load("squad_state", "squad_state.py")
intel_adjust = _load("intel_adjust", "intel_adjust.py")

OUT = os.environ.get("FPL_INTEL_OUT") or os.path.join(HERE, "docs", "news.html")
INTEL = os.path.join(HERE, "ROLE_INTEL.md")


def esc(s):
    """Escape for HTML, then render markdown `code` spans — ROLE_INTEL.md is a
    markdown file and its backticks would otherwise leak through as literals."""
    s = str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return re.sub(r"`([^`]+)`", r'<span class="mono">\1</span>', s)


def fence(txt, name):
    """Parse a ```name fenced block into a list of pipe-separated field lists."""
    m = re.search(r"```" + name + r"\n(.*?)```", txt, re.S)
    if not m:
        return []
    return [[c.strip() for c in ln.split("|")]
            for ln in m.group(1).strip().split("\n") if "|" in ln]


def narrative(txt):
    """The dated intel entries: '### N. Name (CLUB, £p, POS) — summary'."""
    out = []
    pat = re.compile(r"^### \d+\.\s+(.+?)\s+\((\w+), (£[\d.]+m), (\w+)\)\s+—\s+(.+)$", re.M)
    hits = list(pat.finditer(txt))
    for i, m in enumerate(hits):
        seg = txt[m.end(): hits[i + 1].start() if i + 1 < len(hits) else len(txt)]
        def grab(label):
            g = re.search(r"\*\*" + label + r":?\*\*\s*(.+?)(?=\n\n|\n\*\*|\Z)", seg, re.S)
            return re.sub(r"\s+", " ", g.group(1)).strip() if g else ""
        out.append({"name": m.group(1), "team": m.group(2), "price": m.group(3),
                    "pos": m.group(4), "summary": m.group(5),
                    "thesis": grab("Thesis"), "check": grab("Falsifiable check")})
    return out


def build():
    txt = open(INTEL, encoding="utf-8").read()
    state = squad_state.load()
    owned = state.name_set

    contam = fence(txt, "contaminated")
    setp = fence(txt, "setpieces")
    comp = fence(txt, "competition")
    intel = narrative(txt)
    adjustments = intel_adjust.load_adjustments()

    def own_tag(n):
        return ' <span class="tag ok">in squad</span>' if n in owned else ""

    # --- headline counts --------------------------------------------------
    def kpi(v, label, note=""):
        n = f'<div class="kn">{note}</div>' if note else ""
        return (f'<div class="kpi"><div class="kv mono">{v}</div>'
                f'<div class="kl">{label}</div>{n}</div>')

    n_contam_owned = sum(1 for r in contam if r[0] in owned)
    n_comp_owned = sum(1 for r in comp if r[0] in owned)
    n_adj_owned = sum(1 for e in adjustments if e["player"] in owned)
    kpis = "".join([
        kpi(len(contam), "Contaminated priors", f"{n_contam_owned} in your squad"),
        kpi(len(comp), "Contested places", f"{n_comp_owned} in your squad"),
        kpi(len(setp), "Set-piece claims", "all unconfirmed pre-season"),
        kpi(len(intel), "Active intel entries", "each with a check"),
        kpi(len(adjustments), "Modelled-input adjustments", f"{n_adj_owned} in your squad"),
    ])

    # --- role intel (narrative cards, folded into the summary panel below) -
    cards_html = ""
    for e in intel:
        cards_html += f"""<div class="pc">
  <div class="pc-h"><b>{esc(e['name'])}</b>{own_tag(e['name'])}</div>
  <div class="pc-m mono">{esc(e['team'])} · {esc(e['price'])} · {esc(e['pos'])}</div>
  <div class="pc-w"><b>{esc(e['summary'])}</b></div>
  {f"<div class='pc-w'>{esc(e['thesis'])}</div>" if e['thesis'] else ""}
  {f"<div class='pc-w chk'><b>Check:</b> {esc(e['check'])}</div>" if e['check'] else ""}
</div>"""

    # --- modelled-input adjustments -----------------------------------------
    # The `adjustments` fence in ROLE_INTEL.md is the ONLY thing on this page
    # that actually changes a number build_squad.py uses (applied by default
    # since 13 Aug 2026 - previously required --intel, which the documented
    # weekly command never passed, so these rows were silently inert in the
    # real weekly run); every other block here is descriptive. Rendering it is
    # what turns "intel summary" into "intel summary AND its effect on the
    # model", not just a second description of the same narrative.
    def adj_value(e):
        if e["op"] == "mult":
            c = min(max(e["value"], intel_adjust.MULT_LO), intel_adjust.MULT_HI)
            flag = ' <span class="tag bad">clamped</span>' if not (
                intel_adjust.MULT_LO <= e["value"] <= intel_adjust.MULT_HI) else ""
            return f"&times;{c:.2f}{flag}"
        c = min(max(e["value"], 0.0), 1.0)
        flag = ' <span class="tag bad">clamped</span>' if not (0.0 <= e["value"] <= 1.0) else ""
        return f"&rarr; {c:.0%}{flag}"

    adj_rows = "".join(
        f"<tr><td><b>{esc(e['player'])}</b>{own_tag(e['player'])}</td>"
        f"<td class='mono'>{esc(e['team'])}</td>"
        f"<td class='mono'>{esc(e['field'])}</td>"
        f"<td class='mono'>{adj_value(e)}</td>"
        f"<td class='mono'>{esc(e['gws_raw'])}</td>"
        f"<td class='mono'>{esc(e['confidence'])}</td>"
        f"<td class='mono'>{esc(e['date'])}</td>"
        f"<td style='text-align:left'>{esc(e['why'])}</td></tr>"
        for e in adjustments)
    adj_html = f"""
  <h3 style="margin:22px 0 6px;font-size:14px">Adjustments to modelled inputs</h3>
  <p class="tests">Every row here mutates a rate <span class="mono">expected_points()</span>
  reads, and is applied <b>by default</b> in every squad or transfer run since 13 Aug 2026
  (pass <span class="mono">--no-intel</span> to see the raw, unadjusted numbers). Before that
  date this fence required an explicit <span class="mono">--intel</span> flag that the weekly
  brief's documented command never passed, so these rows were silently inert in the actual
  weekly optimiser run — fixed after review found a start-weighted objective would otherwise
  rank transferred/new-signing players on a stale, pre-transfer number this fence exists to
  correct. <span class="mono">mult</span> is guardrailed to 0.5&times;&ndash;1.5&times; so one
  line of narrative can never out-weigh a season of observed data; <span class="mono">set</span>
  (start probability only) is an override, not a multiplier, because unavailability is closer
  to binary than continuous.</p>
  <table><thead><tr><th>Player</th><th>Team</th><th>Field</th><th>Effect</th>
  <th>GWs</th><th>Confidence</th><th>Logged</th><th style="text-align:left">Why</th></tr></thead>
  <tbody>{adj_rows if adj_rows else '<tr><td colspan="8" style="text-align:center;color:var(--dim)">none logged</td></tr>'}</tbody></table>
  <div class="find">An adjustment without a falsifiable check above it is an unexplained number.
  Every row here should trace back to a dated entry in the cards above — <span class="mono">see
  entry N above</span> in its <i>why</i> column is deliberate, not filler.</div>"""

    summary_html = f"""
<div class="panel">
  <h2>Intel summary &amp; modelled-input adjustments</h2>
  <p class="tests">What the screens structurally cannot see: a new penalty taker, a
  tactical shift, a berth opening through injury. Every entry carries a check that
  the opening gameweeks will confirm or kill — and, where an entry is confident enough
  to move a number, exactly what it moved and by how much.</p>
  <div class="row">{cards_html}</div>
  <div class="find">An entry without a falsifiable check is folklore. Anything
  still unproven after roughly five gameweeks gets deleted, not archived.</div>
  {adj_html}
</div>"""

    extra_css = """
<style>
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin-bottom:18px}
.kpi{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:12px 14px}
.kv{font-size:22px;font-weight:700} .kl{font-size:12px;color:var(--dim);margin-top:2px}
.kn{font-size:11px;color:var(--dim);opacity:.75;margin-top:3px}
.row{display:flex;gap:10px;flex-wrap:wrap}
.pc{flex:1 1 300px;background:var(--bg);border:1px solid var(--line);
border-radius:9px;padding:10px 12px}
.pc-h{font-size:14px;margin-bottom:3px} .pc-m{font-size:11.5px;color:var(--dim)}
.pc-w{font-size:12px;margin-top:7px;padding-top:7px;border-top:1px solid var(--line)}
.pc-w.chk{color:var(--dim)}
@media(max-width:700px){.pc{flex:1 1 100%}}
</style>"""

    body = f'<div class="kpis">{kpis}</div>' + summary_html

    html = page_shell.shell(
        title="Availability & intel",
        active="news",
        subtitle=f"Rendered from ROLE_INTEL.md · GW{state.gameweek} · "
                 f"page generated {dt.datetime.now():%Y-%m-%d %H:%M}",
        body=body,
        footer="Built by <span class='mono'>build_intel_page.py</span>, which reads "
               "<span class='mono'>ROLE_INTEL.md</span> rather than copying it. Every "
               "entry there carries a date, a source and a falsifiable check.")
    html = html.replace("</head>", extra_css + "\n</head>")

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    open(OUT, "w", encoding="utf-8").write(html)
    return html, dict(contaminated=len(contam), competition=len(comp),
                      setpieces=len(setp), intel=len(intel),
                      adjustments=len(adjustments))


if __name__ == "__main__":
    h, counts = build()
    print(f"written: {OUT}  ({len(h)/1024:.0f} KB)")
    for k, v in counts.items():
        if v == 0 and k != "adjustments":   # a genuinely empty fence is a valid state
            raise SystemExit(f"nothing parsed for '{k}' — ROLE_INTEL.md format changed?")
        print(f"  {k}: {v}")
    assert "Modelled-input adjustments" in h, "adjustments panel missing"
    print("  adjustments panel present")
