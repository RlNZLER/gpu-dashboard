#!/usr/bin/env bash
# GPU Monitor launcher
# Starts the FastAPI server and opens the dashboard in the browser.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PORT=8000
URL="http://localhost:$PORT"
PIDFILE="$SCRIPT_DIR/.gpu-monitor.pid"
LOG="$SCRIPT_DIR/.gpu-monitor.log"

# ── Activate venv if present ──
if [ -f "$SCRIPT_DIR/venv/bin/activate" ]; then
    source "$SCRIPT_DIR/venv/bin/activate"
elif [ -f "$SCRIPT_DIR/.venv/bin/activate" ]; then
    source "$SCRIPT_DIR/.venv/bin/activate"
fi

# ── Kill any previous instance ──
if [ -f "$PIDFILE" ]; then
    OLD_PID=$(cat "$PIDFILE")
    kill "$OLD_PID" 2>/dev/null
    rm -f "$PIDFILE"
fi

# ── Start server in background ──
cd "$SCRIPT_DIR"
nohup python3 app.py > "$LOG" 2>&1 &
SERVER_PID=$!
echo $SERVER_PID > "$PIDFILE"

# ── Wait for server to be ready (up to 8s) ──
for i in $(seq 1 16); do
    sleep 0.5
    if curl -sf "$URL/api/metrics" > /dev/null 2>&1; then
        break
    fi
done

# ── Open browser ──
if command -v xdg-open &>/dev/null; then
    xdg-open "$URL"
elif command -v firefox &>/dev/null; then
    firefox "$URL" &
elif command -v chromium-browser &>/dev/null; then
    chromium-browser "$URL" &
fi

echo "GPU Monitor running (PID $SERVER_PID). Close this terminal or press Ctrl+C to stop."

# ── Optional: trap to kill server when terminal closes ──
trap "kill $SERVER_PID 2>/dev/null; rm -f $PIDFILE; exit" SIGINT SIGTERM EXIT
wait $SERVER_PID
