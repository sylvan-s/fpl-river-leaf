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
import importlib.util, os, re, json, datetime as dt

HERE = os.path.dirname(os.path.abspath(__file__))
TRELLO_SNAPSHOT = os.path.join(HERE, "docs", "data", "trello_snapshot.json")
INTEL_LOG = os.path.join(HERE, "docs", "data", "intel_sweep_log.jsonl")

# Matches a bite id like "OReilly-MCI-cbit90-20260826-1", including the
# shorthand "-1/-2" a `why` field uses when one line cites two sibling bites
# sharing everything but the trailing sequence number.
BITE_ID_RE = re.compile(r"([A-Za-z][\w']*-[A-Z]{2,4}-[a-z0-9]+-\d{8})-(\d+)((?:/-\d+)*)")


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


def load_trello_snapshot():
    """Read the static Trello board snapshot written by the intel-sweep /
    intel-review pipeline (via the Trello MCP, which this offline script has
    no access to). A missing or unreadable file is a valid state — the panel
    just says so rather than failing the whole page build."""
    try:
        with open(TRELLO_SNAPSHOT, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return None


def extract_bite_ids(text):
    """Pull bite ids out of a free-text `why`/hypothesis field. Handles the
    shorthand a fence row uses for sibling bites, e.g.
    'OReilly-MCI-cbit90-20260826-1/-2' -> both full ids, and a comma-separated
    list like '(Mosquera-ARS-stp-20260821-1, Saliba-ARS-stp-20260820-1)'."""
    ids = []
    for m in BITE_ID_RE.finditer(text or ""):
        base, first, extras = m.group(1), m.group(2), m.group(3)
        cand = f"{base}-{first}"
        if cand not in ids:
            ids.append(cand)
        for e in re.findall(r"/-(\d+)", extras):
            cand = f"{base}-{e}"
            if cand not in ids:
                ids.append(cand)
    return ids


def load_intel_log():
    """Read docs/data/intel_sweep_log.jsonl — the append-only bite/resolution/
    decision/run_meta log. Returns (bites, resolutions, decisions), each a
    dict keyed by bite id (resolutions/decisions map to a list, since a bite
    can be updated more than once). A missing or unreadable file is a valid
    state, same discipline as load_trello_snapshot()."""
    bites, resolutions, decisions = {}, {}, {}
    try:
        with open(INTEL_LOG, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                d = json.loads(line)
                k = d.get("kind")
                if k == "bite":
                    bites[d["id"]] = d
                elif k == "resolution":
                    resolutions.setdefault(d["bite_id"], []).append(d)
                elif k == "decision":
                    decisions.setdefault(d["bite_id"], []).append(d)
    except (OSError, json.JSONDecodeError):
        pass
    return bites, resolutions, decisions


def bite_card_map(snap):
    """bite id -> {url, list, name} for whatever Trello card currently
    represents it, built from the same snapshot the triage-board panel
    renders. Lets the adjustments table link a live model input straight
    back to the card that got it approved."""
    m = {}
    if not snap:
        return m
    for lst in snap.get("lists", []):
        for c in lst.get("cards", []):
            for bid in (c.get("bite_ids") or []):
                m[bid] = {"url": c.get("url"), "list": lst.get("name"), "name": c.get("name")}
    return m


def trello_panel_html(snap):
    """Render the Trello snapshot as a static kanban-style panel. This is a
    SNAPSHOT, not a live embed — the board can stay private, and a static site
    has no way to keep an iframe current anyway. Regenerated by re-fetching the
    board via the Trello MCP each time the pipeline runs (see INTEL_SWEEP.md)."""
    if not snap:
        return """
<div class="panel">
  <h2>Intel triage board</h2>
  <p class="tests">No Trello snapshot found (<span class="mono">docs/data/trello_snapshot.json</span>
  missing or unreadable) — this page hasn't been rebuilt since the snapshot pipeline was added,
  or the last snapshot write failed.</p>
</div>"""

    gen = snap.get("generated_utc", "unknown")
    board_url = snap.get("board_url", "#")
    board_name = snap.get("board_name", "Trello board")

    def card_html(c):
        note = f"<div class='tc-note'>{esc(c['note'])}</div>" if c.get("note") else ""
        ids = c.get("bite_ids") or []
        ids_html = (f"<div class='tc-ids mono'>{esc(', '.join(ids))}</div>" if ids else "")
        return f"""<a class="tc" href="{esc(c.get('url', board_url))}" target="_blank" rel="noopener">
  <div class="tc-name">{esc(c['name'])}</div>
  {ids_html}{note}
</a>"""

    lists_html = ""
    for lst in snap.get("lists", []):
        cards = lst.get("cards", [])
        lists_html += f"""<div class="tl">
  <div class="tl-h">{esc(lst['name'])} <span class="tl-n mono">{len(cards)}</span></div>
  <div class="tl-b">{''.join(card_html(c) for c in cards) if cards else '<div class="tl-empty">empty</div>'}</div>
</div>"""

    return f"""
<div class="panel">
  <h2>Intel triage board <a class="trello-link" href="{esc(board_url)}" target="_blank" rel="noopener">Open on Trello &#8599;</a></h2>
  <p class="tests">Every news bite the daily sweep gathers becomes a Trello card the moment it's
  logged — this replaces the old per-bite card list below with a snapshot of that board itself, so
  triage happens in one place instead of two. A card that updates or supersedes an earlier story is
  flagged as such on the card (see its description) rather than silently replacing it. This is a
  point-in-time render, generated {esc(gen)} — it does not update itself; open the board on Trello
  for the live state.</p>
  <div class="tboard">{lists_html}</div>
</div>"""


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

    # --- news-bite log + Trello snapshot, loaded once and shared by the KPI
    # row, the adjustments table's Source bite(s) column, and the
    # narrative-only-accepted section below.
    bites, resolutions, decisions = load_intel_log()
    snap = load_trello_snapshot()
    bite_map = bite_card_map(snap)

    def bid_chip(bid):
        info = bite_map.get(bid)
        if info:
            return (f'<a class="bid" href="{esc(info["url"])}" target="_blank" '
                     f'rel="noopener" title="{esc(info["list"])}">{esc(bid)}</a>')
        return f'<span class="bid mono">{esc(bid)}</span>'

    def source_bites_html(why):
        ids = extract_bite_ids(why)
        return " ".join(bid_chip(i) for i in ids) if ids else \
            '<span style="color:var(--dim)">&mdash;</span>'

    # --- headline counts ---------------------------------------------------
    # Replaced 28 Aug 2026: the old five (contaminated/contested/setpiece/
    # intel-entry/adjustment counts) described the file's *content*. Sylvan
    # asked for the news-bite *pipeline's* current state instead — how much
    # has come in, how much of it is actually live in the model, and what's
    # about to go stale unresolved.
    def kpi(v, label, note=""):
        n = f'<div class="kn">{note}</div>' if note else ""
        return (f'<div class="kpi"><div class="kv mono">{v}</div>'
                f'<div class="kl">{label}</div>{n}</div>')

    today = dt.date.today()
    this_week = today.isocalendar()[:2]  # (ISO year, ISO week) - Mon-Sun

    def in_this_week(datestr):
        try:
            d = dt.date.fromisoformat(datestr)
        except (TypeError, ValueError):
            return False
        return d.isocalendar()[:2] == this_week

    n_total = len(bites)
    n_this_week = sum(1 for b in bites.values() if in_this_week(b.get("date", "")))

    # "Live & being actioned": bites actually cited by name in a currently-live
    # adjustments-fence row's `why` field - i.e. the bites behind a number
    # build_squad.py is using right now, not just anything sorted into
    # Take Action. Computed by running the same bite-id extraction the
    # Source bite(s) column below uses, over every live fence row.
    live_bite_ids = set()
    for e in adjustments:
        live_bite_ids.update(extract_bite_ids(e["why"]))
    n_live = len(live_bite_ids)

    # "Lapsing this week": open bites (no resolution, no Friday-review
    # decision either way) whose own check_by_gw has already arrived at or
    # before the live gameweek - due for a resolution or, per Reconciliation
    # rule 6, due to be pruned rather than left to rot unresolved.
    cur_gw = state.gameweek
    n_lapsing = sum(
        1 for bid, b in bites.items()
        if bid not in resolutions and bid not in decisions
        and isinstance(b.get("check_by_gw"), int) and b["check_by_gw"] <= cur_gw
    )

    kpis = "".join([
        kpi(n_total, "News bites ingested", "all time"),
        kpi(n_this_week, "Ingested this week", f"week of {today:%d %b}"),
        kpi(n_live, "Live &amp; being actioned",
            "source bites behind a live adjustments-fence row"),
        kpi(n_lapsing, "Lapsing this week",
            f"open past their GW{cur_gw} check, unresolved"),
    ])

    # --- role intel: KPI count only now. The per-bite card panel that used to
    # render here has been replaced by the Trello snapshot panel (trello_html
    # below) — triage now happens on the board, not in two places at once.
    trello_html = trello_panel_html(snap)

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
        f"<td>{source_bites_html(e['why'])}</td>"
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
  to binary than continuous. <b>Source bite(s)</b> links each row back to the Trello card that
  got it approved — every id here was sorted into Take Action and accepted at a Friday review;
  see <span class="mono">INTEL_SWEEP.md</span> step 3a for the gate.</p>
  <table><thead><tr><th>Player</th><th>Team</th><th>Field</th><th>Effect</th>
  <th>GWs</th><th>Confidence</th><th>Logged</th><th>Source bite(s)</th>
  <th style="text-align:left">Why</th></tr></thead>
  <tbody>{adj_rows if adj_rows else '<tr><td colspan="9" style="text-align:center;color:var(--dim)">none logged</td></tr>'}</tbody></table>
  <div class="find">An adjustment without a falsifiable check above it is an unexplained number.
  Every row here should trace back to a dated entry in the cards above — <span class="mono">see
  entry N above</span> in its <i>why</i> column is deliberate, not filler.</div>"""

    # --- accepted, but no fence row --------------------------------------
    # A bite can be accepted at a Friday review without ever appearing above:
    # if it has no `field_affected`, there's nothing for the fence to set —
    # most commonly because the information already flows through a live
    # feed (injury_report) that updates on its own, so a hand-set override
    # would just go stale. Surfacing these separately closes the loop: every
    # accepted bite is shown SOMEWHERE on this page, not just the ones that
    # happened to move a number.
    narrative_accepted = []
    for bid, decs in decisions.items():
        if any(d.get("decision") == "accepted" for d in decs):
            b = bites.get(bid)
            if b and not b.get("field_affected"):
                accept_date = next(d["date"] for d in decs if d.get("decision") == "accepted")
                narrative_accepted.append((bid, accept_date, b))
    narrative_accepted.sort(key=lambda t: t[1])

    if narrative_accepted:
        na_rows = "".join(
            f"<tr><td><b>{esc(b.get('player','?'))}</b>{own_tag(b.get('player',''))}</td>"
            f"<td class='mono'>{esc(b.get('team',''))}</td>"
            f"<td>{bid_chip(bid)}</td>"
            f"<td class='mono'>{esc(date)}</td>"
            f"<td style='text-align:left'>{esc((b.get('hypothesis') or '')[:220])}</td></tr>"
            for bid, date, b in narrative_accepted)
        na_html = f"""
  <h3 style="margin:22px 0 6px;font-size:14px">Accepted, no model row (narrative-only)</h3>
  <p class="tests">Accepted at a Friday review but deliberately absent from the table above —
  no <span class="mono">field_affected</span>, so there's nothing for the adjustments fence to
  set. Usually because the fact already flows through a live feed (e.g.
  <span class="mono">injury_report</span>, sourced from the FPL API and refreshed on every
  call) rather than needing a hand-maintained override that could go stale.</p>
  <table><thead><tr><th>Player</th><th>Team</th><th>Source bite</th><th>Accepted</th>
  <th style="text-align:left">Why</th></tr></thead><tbody>{na_rows}</tbody></table>"""
    else:
        na_html = ""

    summary_html = f"""
<div class="panel">
  <h2>Intel summary &amp; modelled-input adjustments</h2>
  <p class="tests">What the screens structurally cannot see: a new penalty taker, a
  tactical shift, a berth opening through injury. Every entry carries a check that
  the opening gameweeks will confirm or kill — and, where an entry is confident enough
  to move a number, exactly what it moved and by how much. Per-bite triage now lives on
  the Trello board above; this panel covers what's actually confirmed into the narrative
  and, below, what it changed in the model.</p>
  <div class="find">An entry without a falsifiable check is folklore. Anything
  still unproven after roughly five gameweeks gets deleted, not archived.</div>
  {adj_html}
  {na_html}
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
.trello-link{float:right;font-size:12px;font-weight:400;color:var(--dim);text-decoration:none;
border:1px solid var(--line);border-radius:6px;padding:3px 9px}
.trello-link:hover{color:inherit;border-color:currentColor}
.tboard{display:flex;gap:12px;overflow-x:auto;padding-bottom:4px}
.tl{flex:1 1 220px;min-width:200px;background:var(--bg);border:1px solid var(--line);
border-radius:9px;padding:8px}
.tl-h{font-size:12px;font-weight:700;text-transform:uppercase;letter-spacing:.02em;
padding:4px 6px 8px;display:flex;justify-content:space-between}
.tl-n{color:var(--dim);font-weight:400}
.tl-b{display:flex;flex-direction:column;gap:6px}
.tl-empty{font-size:11.5px;color:var(--dim);padding:8px 6px;text-align:center}
.tc{display:block;background:var(--panel);border:1px solid var(--line);border-radius:7px;
padding:8px 9px;text-decoration:none;color:inherit}
.tc:hover{border-color:currentColor}
.tc-name{font-size:12.5px;line-height:1.35}
.tc-ids{font-size:10px;color:var(--dim);margin-top:4px;word-break:break-word}
.tc-note{font-size:10.5px;color:var(--dim);margin-top:4px;font-style:italic}
@media(max-width:700px){.tboard{flex-direction:column}.tl{min-width:0}}
.bid{display:inline-block;font-size:10.5px;font-family:var(--mono,monospace);
padding:2px 6px;border:1px solid var(--line);border-radius:5px;margin:1px 3px 1px 0;
color:inherit;text-decoration:none;white-space:nowrap}
a.bid:hover{border-color:currentColor}
</style>"""

    body = f'<div class="kpis">{kpis}</div>' + trello_html + summary_html

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
    assert "Adjustments to modelled inputs" in h, "adjustments panel missing"
    print("  adjustments panel present")
