#!/usr/bin/env bash
# 로컬 실행: API + 대시보드 (http://localhost:8000)
set -euo pipefail
cd "$(dirname "$0")/.."
PY=.venv/bin/python; [ -x "$PY" ] || PY=python
if [ ! -f config/secrets.env ]; then
  echo "config/secrets.env 없음 → 예시 복사 (데모 모드로 시작)"; cp config/secrets.env.example config/secrets.env
fi
if ! $PY -c "from cafe24_ops.store import Store; import sys; sys.exit(0 if Store().date_bounds()[1] else 1)" 2>/dev/null; then
  echo "수집 데이터 없음 → 데모 30일 생성"; $PY scripts/run_all.py --mode demo --days 30
fi
exec $PY -m uvicorn api.main:app --host "${HOST:-0.0.0.0}" --port "${PORT:-8000}" --reload
