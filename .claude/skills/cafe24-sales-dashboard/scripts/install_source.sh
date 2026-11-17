#!/usr/bin/env bash
# 동봉 소스를 풀고 데모 데이터로 대시보드가 열리는지까지 확인한다. 외부 키 불필요.
#   bash install_source.sh [설치할 폴더]      (기본: ./cafe24-ops-status)
set -euo pipefail
SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ZIP="$SKILL_DIR/assets/cafe24-ops-status-src.zip"
DEST="${1:-$PWD/cafe24-ops-status}"

[ -f "$ZIP" ] || { echo "소스 압축 파일이 없습니다: $ZIP"; exit 1; }
if [ -e "$DEST/cafe24_ops" ]; then
  echo "이미 소스가 있습니다: $DEST (덮어쓰지 않음). 다른 폴더를 지정하거나 그 폴더에서 작업하세요."; exit 1
fi
mkdir -p "$DEST"
python3 - "$ZIP" "$DEST" <<'PY'
import sys, zipfile
zipfile.ZipFile(sys.argv[1]).extractall(sys.argv[2])
PY
chmod +x "$DEST"/scripts/*.sh 2>/dev/null || true
cd "$DEST"
echo "① 소스 풀기 완료: $DEST"

python3 -m venv .venv
.venv/bin/pip install -q -r requirements.txt
echo "② 가상환경·패키지 설치 완료"

export CAFE24_OPS_MODE=demo DASHBOARD_PASSWORD=
.venv/bin/python scripts/run_all.py --reset --mode demo --days 75 | tail -1
echo "③ 데모 데이터 75일 생성 완료"

.venv/bin/python -m pytest -q | tail -1
mkdir -p dist
.venv/bin/python scripts/export_static.py --out dist/index.html | tail -1
echo "④ 완료 — 브라우저로 열어 확인하세요: $DEST/dist/index.html"
echo "   (동봉 설정은 GA4·경쟁사 탭을 숨겨 6탭입니다. 8탭 전부 보려면 config/sources.yaml 의 hidden_tabs 를 [] 로 바꾸고 export_static.py 를 다시 실행)"
echo "   다음 단계: 스킬의 references/build-procedure.md (새 업체) 또는 references/channels.md (채널 연결)"
