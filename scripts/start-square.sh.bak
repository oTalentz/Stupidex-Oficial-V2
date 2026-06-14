#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "$0")/.."
export PYTHONPATH="${PYTHONPATH:-$PWD/src}"
export STUPIDEX_SERVER=1
export STUPIDEX_HOST=0.0.0.0
export STUPIDEX_PORT="${PORT:-5000}"
export STUPIDEX_BIND="0.0.0.0:${PORT:-5000}"
export STUPIDEX_DATA_DIR="${STUPIDEX_DATA_DIR:-$PWD/data}"
mkdir -p "$STUPIDEX_DATA_DIR/workspaces"
python - <<'PY'
from stupidex.db import init_db
init_db()
print("Database initialized")
PY
exec gunicorn -c gunicorn.conf.py stupidex.web:app
