#!/usr/bin/env bash
# pin-images.sh <tag> — 이 저장소에서 굽는 두 이미지(architect-api · web)의 태그를
# 세 compose 파일에 **같이** 박는다. CI 가 굽고 나서 부르고, 사람이 불러도 된다.
#
#   bash pin-images.sh posco-web-1a2b3c4
#
# ## 평소에는 부를 일이 없다 — compose 는 `:delivery` 를 박고 있다
#
# CI 가 커밋마다 태그 **둘**을 올린다(`.github/workflows/posco-web-images.yml`):
#   :posco-web-<sha7>  불변 — 되돌리기·대조용
#   :delivery          움직인다 — compose 가 박는 태그
# 그래서 고칠 때마다 yml 을 손대지 않아도 되고, 폐쇄망은 새 tar 를 `docker load` 한 뒤
# `up -d --wait` 만 치면 된다(compose 가 image ID 가 달라진 것을 보고 다시 만든다).
#
# 이 스크립트는 **한 판을 못 박아 둘 때** 쓴다 —
#   · 되돌리기: `bash pin-images.sh posco-web-6d59fdb`
#   · 다시 `:delivery` 로: `bash pin-images.sh delivery`
#
# 통합 파일만 고치고 분할 둘은 make-split.py 로 다시 만든다 — 태그가 세 곳에 따로
# 적히는 일이 없게 한다(같은 값을 여러 곳에 두면 한 곳이 뒤처진다).
set -euo pipefail
cd "$(dirname "$0")"
tag=${1:?usage: pin-images.sh <tag>}
[[ $tag =~ ^[A-Za-z0-9_][A-Za-z0-9_.-]{0,127}$ ]] || { echo "bad tag: $tag" >&2; exit 2; }
[[ $tag != latest ]] || { echo "latest 는 박지 않는다" >&2; exit 2; }
for name in robo-posco-architect-api robo-posco-web; do
  grep -q "image: ghcr.io/uengine-oss/$name:" docker-compose.yml ||
    { echo "docker-compose.yml 에 $name 가 없다" >&2; exit 1; }
  sed -i -E "s#(image: ghcr.io/uengine-oss/$name:)[A-Za-z0-9_.-]+#\1$tag#" docker-compose.yml
done
PY=python3; command -v python3 >/dev/null && python3 -c 'import sys' 2>/dev/null || PY=python
"$PY" -I make-split.py
grep -n "robo-posco-\(architect-api\|web\):" docker-compose*.yml
