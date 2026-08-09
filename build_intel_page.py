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
import importlib.util, json, os, re, datetime as dt

HERE = os.path.dirname(os.path.abspath(__file__))


def _load(mod, fn):
    spec = importlib.util.spec_from_file_location(mod, os.path.join(HERE, fn))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


page_shell = _load("page_shell", "page_shell.py")
squad_state = _load("squad_state", "squad_state.py")

OUT = os.environ.get("FPL_INTEL_OUT") or os.path.join(HERE, "docs", "news.html")
INTEL = os.path.join(HERE, "ROLE_INTEL.md")
SNAP = os.path.join(HERE, "fpl_priors_2025_26_v2.json")

# A yellow-card count that would matter IF it were this season's. Shown only to
# rank booking tendency, never as a live suspension risk.
BOOKING_HEAVY = 6


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
    snap = json.load(open(SNAP, encoding="utf-8"))
    teams = snap["teams"]
    cards = {p["web_name"]: (p.get("yellow_cards", 0) or 0, p.get("red_cards", 0) or 0,
                             teams[str(p["team"])])
             for p in snap["players"].values()}

    contam = fence(txt, "contaminated")
    setp = fence(txt, "setpieces")
    comp = fence(txt, "competition")
    intel = narrative(txt)

    def own_tag(n):
        return ' <span class="tag ok">in squad</span>' if n in owned else ""

    # --- headline counts --------------------------------------------------
    def kpi(v, label, note=""):
        n = f'<div class="kn">{note}</div>' if note else ""
        return (f'<div class="kpi"><div class="kv mono">{v}</div>'
                f'<div class="kl">{label}</div>{n}</div>')

    n_contam_owned = sum(1 for r in contam if r[0] in owned)
    n_comp_owned = sum(1 for r in comp if r[0] in owned)
    kpis = "".join([
        kpi(len(contam), "Contaminated priors", f"{n_contam_owned} in your squad"),
        kpi(len(comp), "Contested places", f"{n_comp_owned} in your squad"),
        kpi(len(setp), "Set-piece claims", "all unconfirmed pre-season"),
        kpi(len(intel), "Active intel entries", "each with a check"),
    ])

    # --- contamination ----------------------------------------------------
    rows = "".join(
        f"<tr><td><b>{esc(r[0])}</b>{own_tag(r[0])}</td>"
        f"<td style='text-align:left'>{esc(r[1])}</td></tr>" for r in contam)
    contam_html = f"""
<div class="panel">
  <h2>Prior belongs to a different club</h2>
  <p class="tests">The snapshot records each player's <b>current</b> club against
  <b>last season's</b> statistics. A summer transfer therefore reads as new badge,
  old numbers — and nothing in the data flags it.</p>
  <table><thead><tr><th>Player</th><th style="text-align:left">Why the number misleads</th></tr></thead>
  <tbody>{rows}</tbody></table>
  <div class="find bad">The automatic club-change check <b>cannot fire</b> for
  anyone who moved before the snapshot was captured on 8 Aug 2026 — which is the
  whole summer window. This list is maintained by hand; a name missing from it is
  not evidence of a clean prior.</div>
</div>"""

    # --- contested places -------------------------------------------------
    comp_html = ""
    if comp:
        rows = "".join(
            f"<tr><td><b>{esc(r[0])}</b>{own_tag(r[0])}</td>"
            f"<td><span class='tag bad'>{esc(r[1])}</span></td>"
            f"<td class='mono'>{esc(r[2])}</td>"
            f"<td style='text-align:left'>{esc(r[3])}</td></tr>" for r in comp)
        comp_html = f"""
<div class="panel">
  <h2>Place in the side contested</h2>
  <p class="tests">Distinct from a contaminated prior: there the numbers belong to
  another club, here they belong to another <b>role</b>. The history is right and
  the conclusion is wrong.</p>
  <table><thead><tr><th>Player</th><th>Status</th><th>Logged</th>
  <th style="text-align:left">Detail</th></tr></thead><tbody>{rows}</tbody></table>
  <div class="find">Start rate is the most load-bearing number in the model — it
  gates selection today and will weight the objective under roadmap item A0.5. A
  player who was first choice and is now second is invisible to the data, because
  last season he did start.</div>
</div>"""

    # --- role intel -------------------------------------------------------
    cards_html = ""
    for e in intel:
        cards_html += f"""<div class="pc">
  <div class="pc-h"><b>{esc(e['name'])}</b>{own_tag(e['name'])}</div>
  <div class="pc-m mono">{esc(e['team'])} · {esc(e['price'])} · {esc(e['pos'])}</div>
  <div class="pc-w"><b>{esc(e['summary'])}</b></div>
  {f"<div class='pc-w'>{esc(e['thesis'])}</div>" if e['thesis'] else ""}
  {f"<div class='pc-w chk'><b>Check:</b> {esc(e['check'])}</div>" if e['check'] else ""}
</div>"""
    intel_html = f"""
<div class="panel">
  <h2>Role and minutes intel</h2>
  <p class="tests">What the screens structurally cannot see: a new penalty taker, a
  tactical shift, a berth opening through injury. Every entry carries a check that
  the opening gameweeks will confirm or kill.</p>
  <div class="row">{cards_html}</div>
  <div class="find">An entry without a falsifiable check is folklore. Anything
  still unproven after roughly five gameweeks gets deleted, not archived.</div>
</div>"""

    # --- set pieces -------------------------------------------------------
    rows = "".join(
        f"<tr><td><b>{esc(r[0])}</b>{own_tag(r[0])}</td><td class='mono'>{esc(r[1])}</td>"
        f"<td class='mono'>{esc(r[2])}</td>"
        f"<td style='text-align:left'>{esc(r[3])}</td></tr>" for r in setp)
    setp_html = f"""
<div class="panel">
  <h2>Set-piece duty — claimed, not confirmed</h2>
  <p class="tests">P = penalties, F = direct free kicks, C = corners; the number is
  the order. A penalty is worth roughly 0.79 xG, so this is among the largest
  single adjustments available.</p>
  <table><thead><tr><th>Player</th><th>Codes</th><th>Added</th>
  <th style="text-align:left">Source</th></tr></thead><tbody>{rows}</tbody></table>
  <div class="find">These exist only to cover the pre-season gap before the FPL API
  populates its own fields. Where both exist the <b>API always wins</b>, and a line
  is deleted the moment the API confirms or contradicts it.</div>
</div>"""

    # --- discipline -------------------------------------------------------
    mine = sorted(((n,) + cards.get(n, (0, 0, "?")) for n in owned),
                  key=lambda r: -r[1])
    HEAVY_TAG = '<span class="tag bad">books often</span>'
    rows = "".join(
        f"<tr><td><b>{esc(n)}</b></td><td class='mono'>{tm}</td>"
        f"<td class='mono'>{y}</td><td class='mono'>{r if r else ''}</td>"
        f"<td>{HEAVY_TAG if y >= BOOKING_HEAVY else ''}</td></tr>"
        for n, y, r, tm in mine)
    disc_html = f"""
<div class="panel">
  <h2>Booking tendency — <i>not</i> a live suspension risk</h2>
  <p class="tests">Yellow cards from 2025/26, for every player in the squad.</p>
  <div class="find bad"><b>These do not carry over.</b> Premier League yellow-card
  counts reset each season, so at the GW1 2026/27 deadline every player below is on
  <b>zero</b>. Treat this as a tendency to be booked, which is a mild prior on
  future suspension risk — never as a current one. The thresholds that matter
  (5 by GW19, 10 by GW32, 15 by GW38) apply to <i>this</i> season's count, which
  the repository does not yet hold.</div>
  <table><thead><tr><th>Player</th><th>Club</th><th>YC 25/26</th><th>RC</th><th></th></tr></thead>
  <tbody>{rows}</tbody></table>
</div>"""

    limits_html = """
<div class="panel">
  <h2>What this page cannot tell you</h2>
  <p class="tests">Stated plainly, because a page that looks live and is not is
  worse than no page at all.</p>
  <ul style="margin:6px 0 0 18px;padding:0;font-size:13px">
    <li><b>No live injury or availability feed.</b> Everything here is built from
    the repository at build time. Current status, doubtful flags and this season's
    card counts come from the FPL API and are not in this page.</li>
    <li><b>Absence is not evidence.</b> The contaminated and contested lists are
    maintained by hand. A player missing from them has not been cleared — he may
    simply not have been checked.</li>
    <li><b>Set-piece claims are community consensus</b>, explicitly unconfirmed,
    and are superseded by the API the moment it populates.</li>
  </ul>
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

    body = (f'<div class="kpis">{kpis}</div>' + contam_html + comp_html +
            intel_html + setp_html + disc_html + limits_html)

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
                      setpieces=len(setp), intel=len(intel))


if __name__ == "__main__":
    h, counts = build()
    print(f"written: {OUT}  ({len(h)/1024:.0f} KB)")
    for k, v in counts.items():
        if v == 0:
            raise SystemExit(f"nothing parsed for '{k}' — ROLE_INTEL.md format changed?")
        print(f"  {k}: {v}")
    assert "reset each season" in h, "the yellow-card reset caveat is missing"
    print("  yellow-card reset caveat present")
