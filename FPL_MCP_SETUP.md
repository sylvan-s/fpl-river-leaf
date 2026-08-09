# FPL Research MCP — setup

Read-only Fantasy Premier League research server for River Leaf FC (entry 1041614).

## What it is

A local MCP server that turns the FPL API into seven purpose-built research
tools. It exists to make the weekly brief cheaper and more reliable — it does
not know anything the API doesn't.

**It cannot change your team.** There is no write path in the source. It makes
only HTTP GET requests to public endpoints, stores no credentials, and is
unaffected by the PingOne/OIDC login migration that broke older FPL MCP servers.

## Install

Requires Python 3.10+.

```bash
pip3 install mcp httpx
```

Then add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "fpl-research": {
      "command": "python3",
      "args": [
        "/Users/sylvansitkey/Library/CloudStorage/GoogleDrive-sylvansitkey07@gmail.com/My Drive/FPL/fpl_research_mcp.py"
      ]
    }
  }
}
```

If that file already has an `mcpServers` block, add the `fpl-research` entry
inside it rather than replacing the block.

Restart Claude Desktop completely (quit, don't just close the window).

## Verify

Before restarting, confirm it can reach the API from your machine:

```bash
python3 "/Users/sylvansitkey/Library/CloudStorage/GoogleDrive-sylvansitkey07@gmail.com/My Drive/FPL/fpl_research_mcp.py" --selftest
```

You should see the GW1 deadline, a fixture difficulty table, and the injury
list. If that works, the MCP will work.

To re-run the logic tests (no network needed):

```bash
cd "/Users/sylvansitkey/Library/CloudStorage/GoogleDrive-sylvansitkey07@gmail.com/My Drive/FPL"
python3 test_fpl_mcp.py
```

## Tools

| Tool | Use |
|---|---|
| `get_deadline` | Gameweek, exact deadline, countdown, chip-set-1 expiry |
| `xgi_delta` | **Core.** Delta = (G+A) − xGI. Ranked buy/sell lists |
| `fixture_difficulty` | Avg FDR per team over next N GWs; flags doubles and blanks |
| `injury_report` | Status flags, % chance of playing, news text |
| `get_squad` | Squad for a locked gameweek (post-deadline only) |
| `compare_players` | Side-by-side underlying metrics |
| `analyze_players` | Filter/rank by points, form, value, xGI, ownership |

### The delta rule, as encoded

`Delta = (goals + assists) − xGI`

- **Negative** → underperforming xG → regression **BUY**
- **Positive** → overperforming → **SELL/avoid** unless an elite finisher

`xgi_delta` defaults to season-to-date (one API call). Pass `season=False,
last_n=4` for a rolling window — more accurate, but it makes one call per
player, so narrow the filters first.

## Known limits

- **Undocumented API.** Field names can change without notice. If output goes
  strange, run `--selftest` first.
- **Doesn't cover your whole framework.** Understat and FBref xGI aren't in the
  FPL API and aren't here. Neither is creator consensus (Let's Talk FPL, Focal,
  Blackbox). Those still need web search.
- **`get_squad` is post-deadline only.** A team you're still editing stays
  private. That's an FPL constraint, not a gap in this server.
- **Early season.** With few matches played, `min_minutes` filters out nearly
  everyone. Pass `min_minutes=0` until a few gameweeks are done, and treat
  small-sample deltas with suspicion.
