#!/bin/bash
# Diagnostics for the FPL Research MCP. Read-only - changes nothing.
# Paste the entire output back to Claude.

CONFIG="$HOME/Library/Application Support/Claude/claude_desktop_config.json"
SERVER_DIR="/Users/sylvansitkey/Library/CloudStorage/GoogleDrive-sylvansitkey07@gmail.com/My Drive/FPL"
SERVER="$SERVER_DIR/fpl_research_mcp.py"

echo "================ FPL MCP DIAGNOSTICS ================"
date

echo
echo "--- 1. Config entry ---"
if [ -f "$CONFIG" ]; then
  python3 - "$CONFIG" <<'EOF' 2>/dev/null || cat "$CONFIG"
import json,sys
d=json.load(open(sys.argv[1]))
s=d.get("mcpServers",{})
print("servers configured:", list(s.keys()))
print("fpl-research entry:", json.dumps(s.get("fpl-research","MISSING"), indent=2))
EOF
else
  echo "NO CONFIG FILE at $CONFIG"
fi

echo
echo "--- 2. Interpreter named in the config ---"
PY=$(python3 -c "
import json,os
p=os.path.expanduser('$CONFIG')
try:
    print(json.load(open(p))['mcpServers']['fpl-research']['command'])
except Exception as e:
    print('')
" 2>/dev/null)
if [ -n "$PY" ] && [ -x "$PY" ]; then
  echo "path:    $PY"
  echo "version: $("$PY" --version 2>&1)"
else
  echo "PROBLEM: interpreter '$PY' missing or not executable"
fi

echo
echo "--- 3. Dependencies inside THAT interpreter ---"
if [ -n "$PY" ] && [ -x "$PY" ]; then
  "$PY" - <<'EOF'
import importlib.util as u
for m in ("mcp","httpx"):
    spec=u.find_spec(m)
    if spec is None:
        print(f"  {m}: MISSING")
    else:
        try:
            mod=__import__(m)
            print(f"  {m}: OK  version={getattr(mod,'__version__','?')}  at {spec.origin}")
        except Exception as e:
            print(f"  {m}: IMPORT ERROR {type(e).__name__}: {e}")
try:
    from mcp.server.mcpserver import MCPServer
    print("  API: MCPServer (SDK 2.x)")
except ImportError:
    try:
        from mcp.server.fastmcp import FastMCP
        print("  API: FastMCP (SDK 1.x)")
    except ImportError as e:
        print("  API: NEITHER FastMCP NOR MCPServer FOUND ->", e)
EOF
fi

echo
echo "--- 4. Server file ---"
if [ -f "$SERVER" ]; then
  echo "exists, $(wc -c < "$SERVER") bytes"
else
  echo "MISSING at $SERVER"
  echo "(if the FPL folder is cloud-only, open it in Finder to download)"
fi

echo
echo "--- 5. Import the server module ---"
if [ -n "$PY" ] && [ -x "$PY" ] && [ -f "$SERVER" ]; then
  "$PY" -c "
import importlib.util,sys
spec=importlib.util.spec_from_file_location('fpl','$SERVER')
m=importlib.util.module_from_spec(spec)
try:
    spec.loader.exec_module(m); print('  import OK')
except Exception as e:
    import traceback; print('  IMPORT FAILED:'); traceback.print_exc()
"
fi

echo
echo "--- 6. Live API selftest ---"
if [ -n "$PY" ] && [ -x "$PY" ] && [ -f "$SERVER" ]; then
  "$PY" "$SERVER" --selftest 2>&1 | head -25
  echo "(exit: $?)"
fi

echo
echo "--- 7. Claude Desktop MCP logs (last 30 lines each) ---"
shopt -s nullglob
FOUND=0
for f in "$HOME/Library/Logs/Claude/"mcp*.log; do
  FOUND=1
  echo
  echo ">>> $f"
  tail -30 "$f"
done
[ $FOUND -eq 0 ] && echo "no mcp*.log files in ~/Library/Logs/Claude/"

echo
echo "================ END ================"
