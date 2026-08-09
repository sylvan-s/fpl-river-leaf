#!/bin/bash
# Installer for the FPL Research MCP (read-only).
# Safe to re-run: backs up your config and MERGES the entry rather than
# overwriting, so any other MCP servers you have are preserved.

set -uo pipefail

SERVER_DIR="/Users/sylvansitkey/Library/CloudStorage/GoogleDrive-sylvansitkey07@gmail.com/My Drive/FPL"
SERVER="$SERVER_DIR/fpl_research_mcp.py"
CONFIG_DIR="$HOME/Library/Application Support/Claude"
CONFIG="$CONFIG_DIR/claude_desktop_config.json"

echo "=============================================="
echo " FPL Research MCP - installer"
echo "=============================================="

# --- 1. python3 -------------------------------------------------------------
# The MCP SDK needs 3.10+. Do NOT just trust `command -v python3` - conda puts
# its own (often old) interpreter first on PATH. Scan for a suitable one.
echo
echo "[1/5] Finding a Python 3.10+ interpreter..."

is_ok() { [ -x "$1" ] && "$1" -c 'import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)' 2>/dev/null; }

# IMPORTANT: never reuse an arbitrary existing conda env. Doing so pollutes a
# project environment and inherits whatever broken packages it already has.
# Only ever use our own dedicated 'fpl-mcp' env, or a standalone system Python.
PY=""
CANDIDATES=""
# our own dedicated env first, so re-runs are idempotent
for base in "$HOME/opt/anaconda3" "$HOME/anaconda3" "$HOME/miniconda3" "$HOME/miniforge3"; do
  CANDIDATES="$CANDIDATES $base/envs/fpl-mcp/bin/python3"
done
for v in 3.13 3.12 3.11 3.10; do
  CANDIDATES="$CANDIDATES /opt/homebrew/bin/python$v /usr/local/bin/python$v"
  CANDIDATES="$CANDIDATES /Library/Frameworks/Python.framework/Versions/$v/bin/python3"
done
CANDIDATES="$CANDIDATES /opt/homebrew/bin/python3 /usr/local/bin/python3 /usr/bin/python3"

for c in $CANDIDATES; do
  if is_ok "$c"; then PY="$c"; break; fi
done

if [ -n "$PY" ]; then
  echo "  OK: $("$PY" --version) at $PY"
else
  echo "  No Python 3.10+ found on this machine."
  DEFAULT_PY=$(command -v python3 2>/dev/null)
  [ -n "$DEFAULT_PY" ] && echo "  (your default python3 is $("$DEFAULT_PY" --version 2>&1))"

  CONDA=""
  for c in "$HOME/opt/anaconda3/bin/conda" "$HOME/anaconda3/bin/conda" \
           "$HOME/miniconda3/bin/conda" "$(command -v conda 2>/dev/null)"; do
    [ -x "$c" ] && CONDA="$c" && break
  done

  if [ -n "$CONDA" ]; then
    echo
    echo "  Anaconda found at: $CONDA"
    echo "  Creating a dedicated environment 'fpl-mcp' with Python 3.12."
    echo "  This is additive - it does NOT touch your base environment."
    echo "  To undo later:  $CONDA env remove -n fpl-mcp"
    echo
    if ! "$CONDA" create -y -n fpl-mcp python=3.12 >/tmp/fpl_conda.log 2>&1; then
      echo "  ERROR: conda env creation failed. Last lines:"
      tail -15 /tmp/fpl_conda.log | sed 's/^/    /'
      exit 1
    fi
    ENV_PREFIX=$("$CONDA" run -n fpl-mcp python -c 'import sys; print(sys.prefix)' 2>/dev/null | tr -d '\r')
    PY="$ENV_PREFIX/bin/python3"
    if ! is_ok "$PY"; then
      echo "  ERROR: created the env but could not locate its python at $PY"
      exit 1
    fi
    echo "  OK: created. $("$PY" --version) at $PY"
  else
    echo
    echo "  ERROR: no Python 3.10+ and no conda to build one with."
    echo "  Easiest fix - install Homebrew Python, then re-run this script:"
    echo "    brew install python@3.12"
    exit 1
  fi
fi

# --- 2. server file ---------------------------------------------------------
echo
echo "[2/5] Checking server file..."
if [ ! -f "$SERVER" ]; then
  echo "  ERROR: not found at:"
  echo "  $SERVER"
  echo "  If it is cloud-only, open the FPL folder in Finder to download it."
  exit 1
fi
echo "  OK: $SERVER"

# --- 3. dependencies --------------------------------------------------------
echo
echo "[3/5] Installing dependencies..."
# PINNED TO mcp<2 DELIBERATELY.
# SDK 2.x imports `cryptography` (mcp/server/request_state.py). Inside a conda
# env that build is often linked against an older OpenSSL than it needs, giving:
#   symbol not found in flat namespace '_EVP_DigestSqueeze'
# SDK 1.x imports no cryptography at all, so the problem cannot arise. The
# server supports both APIs via a shim and is tested against both.
if ! "$PY" -m pip install --quiet --upgrade "mcp<2" httpx; then
  echo "  ERROR: pip install failed. Try manually:"
  echo "    $PY -m pip install 'mcp<2' httpx"
  exit 1
fi
echo "  Installed mcp $("$PY" -m pip show mcp 2>/dev/null | awk '/^Version:/{print $2}') (pinned <2), httpx OK"

# Safety net: if anything still drags in a broken cryptography, repair it.
if ! "$PY" -c 'import mcp' 2>/dev/null; then
  echo "  mcp still not importable - attempting cryptography repair..."
  "$PY" -m pip install --quiet --force-reinstall --no-cache-dir cryptography || true
fi

# Hard gate: the server must actually import before we touch the config.
"$PY" - <<'EOF'
import sys
try:
    import httpx  # noqa: F401
except Exception as e:
    print(f"  ERROR: httpx unusable: {type(e).__name__}: {e}"); sys.exit(1)
try:
    try:
        from mcp.server.mcpserver import MCPServer  # noqa: F401
        api = "MCPServer (SDK 2.x)"
    except ImportError:
        from mcp.server.fastmcp import FastMCP  # noqa: F401
        api = "FastMCP (SDK 1.x)"
except Exception as e:
    print(f"  ERROR: mcp unusable: {type(e).__name__}: {e}")
    print("  The config was NOT changed. Send this message to Claude.")
    sys.exit(1)
print(f"  OK: httpx and mcp both import cleanly - using {api}")
EOF
if [ $? -ne 0 ]; then exit 1; fi

# --- 4. connectivity + selftest --------------------------------------------
echo
echo "[4/5] Testing live API access from this machine..."
if "$PY" "$SERVER" --selftest > /tmp/fpl_selftest.txt 2>&1; then
  echo "  OK: reached the FPL API. First lines:"
  head -6 /tmp/fpl_selftest.txt | sed 's/^/    /'
else
  echo "  WARNING: selftest failed. Details:"
  tail -15 /tmp/fpl_selftest.txt | sed 's/^/    /'
  echo
  echo "  Continuing with config anyway - you can re-run the selftest later:"
  echo "    $PY \"$SERVER\" --selftest"
fi

# --- 5. Claude Desktop config ----------------------------------------------
echo
echo "[5/5] Registering with Claude Desktop..."
mkdir -p "$CONFIG_DIR"
if [ -f "$CONFIG" ]; then
  BACKUP="$CONFIG.backup.$(date +%Y%m%d-%H%M%S)"
  cp "$CONFIG" "$BACKUP"
  echo "  Backed up existing config to:"
  echo "    $BACKUP"
fi

CONFIG="$CONFIG" SERVER="$SERVER" PY="$PY" "$PY" - <<'EOF'
import json, os, sys

cfg_path, server, py = os.environ["CONFIG"], os.environ["SERVER"], os.environ["PY"]

cfg = {}
if os.path.exists(cfg_path):
    try:
        with open(cfg_path) as fh:
            txt = fh.read().strip()
        cfg = json.loads(txt) if txt else {}
    except json.JSONDecodeError as e:
        print(f"  ERROR: existing config is not valid JSON ({e}).")
        print("  Fix or remove it, then re-run. Your backup is untouched.")
        sys.exit(1)

servers = cfg.setdefault("mcpServers", {})
existed = "fpl-research" in servers
servers["fpl-research"] = {"command": py, "args": [server]}

with open(cfg_path, "w") as fh:
    json.dump(cfg, fh, indent=2)
    fh.write("\n")

print(f"  {'Updated' if existed else 'Added'} 'fpl-research' entry.")
others = [k for k in servers if k != "fpl-research"]
print(f"  Preserved {len(others)} other server(s): {', '.join(others) if others else 'none'}")
EOF
[ $? -ne 0 ] && exit 1

echo
echo "=============================================="
echo " Done. NOW QUIT CLAUDE DESKTOP COMPLETELY"
echo " (Cmd+Q - closing the window is not enough)"
echo " and reopen it."
echo
echo " Then ask: \"what's the FPL deadline?\""
echo " It should answer via the fpl-research MCP."
echo "=============================================="
