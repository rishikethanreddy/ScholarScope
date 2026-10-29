#!/usr/bin/env sh
# Rebuild the offline demo database and its admin account. Stop the demo API first (the DB file is replaced).
set -e
cd "$(dirname "$0")/../backend"
PY=.venv/Scripts/python; [ -x "$PY" ] || PY=.venv/bin/python
HERE=$(pwd -W 2>/dev/null || pwd)  # Windows-style path under Git Bash
export DATABASE_URL="sqlite:///$HERE/data/demo/demo.db" DATA_DIR="$HERE/data/demo" DEMO_MODE=true SCHEDULER_ENABLED=false
"$PY" -m app.cli demo-setup
ADMIN_PASSWORD="${ADMIN_PASSWORD:-demo-admin-pass-1}" "$PY" -m app.cli create-admin --email admin@demo.local
echo "Start the demo API with:"
echo "  DATABASE_URL=$DATABASE_URL DATA_DIR=$DATA_DIR DEMO_MODE=true SCHEDULER_ENABLED=false $PY -m uvicorn app.main:app --port 8000"
