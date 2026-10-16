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
# **커밋을 고정한다.** 종전에는 `clone --depth 1` 로 그 순간의 HEAD 를 집어왔다.
# 그러면 같은 릴리스 핀을 받아도 템플릿이 달라질 수 있는데, 템플릿은 납품
# 이미지 안으로 들어가는 제품의 일부다(authority 의 `COPY templates`).
# 이 값은 2026-10-13 납품본 이미지에 실제로 들어 있던 커밋이다.
TEMPLATE_REF="${TEMPLATE_REF:-339a555401f0326e7c5955c0d3a5e984a1874a0b}"

fetch_at_ref() {
    git -C "$DEST" fetch --depth 1 origin "$TEMPLATE_REF"
    git -C "$DEST" checkout --quiet --detach FETCH_HEAD
}

if [ -d "$DEST/.git" ]; then
    have=$(git -C "$DEST" rev-parse HEAD)
    if [ "$have" = "$TEMPLATE_REF" ]; then
        echo "→ 이미 핀에 있음: $DEST"
    else
        echo "→ 핀으로 맞춤: $have → $TEMPLATE_REF"
        fetch_at_ref
    fi
else
    echo "→ 클론: $REPO → $DEST @ $TEMPLATE_REF"
    mkdir -p templates
    git init --quiet "$DEST"
    git -C "$DEST" remote add origin "$REPO"
    fetch_at_ref
fi

got=$(git -C "$DEST" rev-parse HEAD)
if [ "$got" != "$TEMPLATE_REF" ]; then
    echo "핀과 다르다: $got != $TEMPLATE_REF" >&2
    exit 1
fi
echo "커밋 $got"

n=$(find "$DEST" -type f -not -path '*/.git/*' | wc -l | tr -d ' ')
echo "완료 — 템플릿 파일 $n 개"
