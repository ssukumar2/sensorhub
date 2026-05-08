#!/usr/bin/env bash
# Start backend in background, then run simulator. Ctrl-C cleans up both.
set -euo pipefail

cd "$(dirname "$0")/.."

if [ -d .venv ]; then
    # shellcheck disable=SC1091
    source .venv/bin/activate
fi

uvicorn app.main:app --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!
trap "kill $BACKEND_PID 2>/dev/null || true" EXIT INT TERM

# Wait for backend to come up
for i in {1..20}; do
    if curl -sf http://localhost:8000/health >/dev/null; then
        break
    fi
    sleep 0.5
done

python -m app.simulator --count 5 --interval 2.0 --duration "${1:-60}"
