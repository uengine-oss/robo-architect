#!/bin/bash
# 코드 생성 템플릿을 로컬로 가져온다.
#
# Git API 로 원격을 읽지 않는다 — 납품 환경은 내부망이고, 생성기는 로컬
# 경로에서 파일을 그대로 읽는다. 이 스크립트는 개발 머신에서 한 번 돌려
# `templates/` 를 채우는 용도다. 내부망에서는 이 디렉터리를 그대로 옮긴다.
set -e
cd "$(dirname "$0")/.."
DEST="templates/template-poscodx"
REPO="${TEMPLATE_REPO:-https://github.com/msa-ez/template-poscodx}"

if [ -d "$DEST/.git" ]; then
    echo "→ 이미 있음, 갱신: $DEST"
    git -C "$DEST" pull --ff-only
else
    echo "→ 클론: $REPO → $DEST"
    mkdir -p templates
    git clone --depth 1 "$REPO" "$DEST"
fi

n=$(find "$DEST" -type f -not -path '*/.git/*' | wc -l | tr -d ' ')
echo "완료 — 템플릿 파일 $n 개"
