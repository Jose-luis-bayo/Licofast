#!/usr/bin/env bash
# LicoFast - arranque rápido en Linux/macOS (requiere MySQL/MariaDB en marcha y Python 3.11+)
set -e
cd "$(dirname "$0")/backend"
[ -d .venv ] || python3 -m venv .venv
source .venv/bin/activate
pip install -q -r requirements.txt
[ -f .env ] || cp .env.example .env
python scripts/init_db.py
echo "LicoFast en http://localhost:5000"
python run.py
