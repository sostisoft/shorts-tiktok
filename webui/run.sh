#!/bin/bash
# Lanzar la web UI de VideoBot
cd "$(dirname "$0")/.."
source venv/bin/activate
export PROJECT_DIR="$(pwd)"
export DB_PATH="$(pwd)/db/videobot.db"
export LOG_PATH="$(pwd)/logs/videobot.log"
exec python webui/app.py
