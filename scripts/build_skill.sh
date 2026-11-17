#!/usr/bin/env bash
# 다른 Claude 에 설치할 스킬 패키지(ops-dashboard.skill)를 만든다.
#   bash scripts/build_skill.sh        → dist/ops-dashboard.skill
# 커밋된 소스(HEAD)를 압축해 스킬에 넣는다. 비밀 값(config/secrets.env)·DB·옛 스크린샷은 들어가지 않는다.
set -euo pipefail
cd "$(dirname "$0")/.."
SK=.claude/skills/ops-dashboard
mkdir -p "$SK/assets" dist
rm -f "$SK/assets/cafe24-ops-status-src.zip"
git archive --format=zip -o "$SK/assets/cafe24-ops-status-src.zip" HEAD \
  ':(exclude)docs/screenshots' ':(exclude).claude/skills/ops-dashboard' ':(exclude).claude/skills/sns-auto-operation'
OUT=dist/ops-dashboard.skill
rm -f "$OUT"
python3 - "$SK" "$OUT" <<'PY'
import sys, zipfile, pathlib
src, out = pathlib.Path(sys.argv[1]), sys.argv[2]
with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
    for p in sorted(src.rglob("*")):
        if p.is_file() and "__pycache__" not in p.parts:
            z.write(p, pathlib.Path(src.name) / p.relative_to(src))
print(f"✓ {out}  ({pathlib.Path(out).stat().st_size // 1024} KB)")
PY
