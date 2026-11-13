#!/usr/bin/env bash
# update.sh <release-tag> [asset] — **사내 서버에서** 새 판을 받아 바꿔 띄운다. 운영-업데이트-가이드.md §3
#
#   bash update.sh posco-web-images-2026-11-20            # images.tar 를 받는다
#   bash update.sh posco-web-images-2026-11-20 api.tar    # 자산 이름이 다르면
#   bash update.sh --no-images                            # yml·가이드만 바뀐 판 (git pull + up)
#
# ⚠ **sudo 없이** 돌린다. curl 이 일반 계정의 https_proxy 를 써야 github 에 닿는다(sudo 는 그것을 버린다).
#   docker 는 스크립트 안에서 sudo 로 부른다 — msa-ez 와 같은 root 저장소.
# ⚠ 지우는 일은 하지 않는다(volume·prune 없음). 받은 tar 는 끝나고 지운다.
#
# 하는 일
#   1 git pull         yml · 가이드 · tiktoken-cache · authority-init
#   2 받기 · 대조      Release 의 <asset> 과 <asset>.sha256 → sha256sum -c
#   3 적재             sudo docker load
#   4 이미지 대조      compose 가 찾는 이미지가 다 있나 (없으면 멈춘다)
#   5 바꿔 띄우기      init 다시 → architect-api 먼저(healthy 까지) → 나머지 → web
#                      podman 은 같은 태그를 load 로 덮어도 컨테이너를 안 바꾼다 → 강제로
#                      web(nginx) 은 architect-api 의 옛 IP 를 붙든다 → 마지막에 다시
#   6 상태
set -euo pipefail
cd "$(dirname "$0")"

REPO=uengine-oss/robo-architect
API=robo-posco-web-architect-api-1

[[ ${EUID:-$(id -u)} -ne 0 ]] || { echo "sudo 없이 돌린다 — bash update.sh …  (curl 이 프록시를 써야 한다)" >&2; exit 1; }
TAG=${1:?usage: bash update.sh <release-tag> [asset] | --no-images}
ASSET=${2:-images.tar}
# load 로 덮인 장은 강제로 다시 만든다. web 은 언제나 마지막에 다시(옛 IP).
if [[ $TAG == --no-images ]]; then FORCE=${FORCE:-web}; else FORCE=${FORCE:-"architect-api web"}; fi

health() {  # podman 판마다 필드 이름이 다르다
  sudo docker inspect "$1" --format '{{.State.Health.Status}}' 2>/dev/null ||
    sudo docker inspect "$1" --format '{{.State.Healthcheck.Status}}' 2>/dev/null || echo unknown
}

echo "[1] git pull"
git pull --ff-only
git log -1 --oneline

if [[ $TAG != --no-images ]]; then
  echo "[2] 받기 — $TAG/$ASSET"
  base=https://github.com/$REPO/releases/download/$TAG
  curl -fL -C - -o "$ASSET" "$base/$ASSET"
  curl -fsSL -o "$ASSET.sha256" "$base/$ASSET.sha256"
  sha256sum -c "$ASSET.sha256"

  echo "[3] 적재"
  sudo docker load -i "$ASSET"
fi

echo "[4] compose 가 찾는 이미지"
miss=0
for i in $(sudo docker compose config --images); do
  if sudo docker image inspect "$i" >/dev/null 2>&1; then echo "  O $i"; else echo "  X $i"; miss=$((miss+1)); fi
done
(( miss == 0 )) || { echo "X 가 $miss 장 — 그 장을 tar 에 넣어 다시 받는다" >&2; exit 1; }

echo "[5] 바꿔 띄우기"
sudo docker compose up -d --force-recreate --no-deps authority-init   # 권한 표 — 다시 돌려도 안전하다
if [[ " $FORCE " == *" architect-api "* ]]; then
  sudo docker compose up -d --force-recreate --no-deps --pull never architect-api
fi
printf '  architect-api 기다림'
for _ in $(seq 1 60); do
  s=$(health "$API"); [[ $s == healthy ]] && break
  printf ' .'; sleep 5
done
echo " → $s"
[[ $s == healthy ]] || { echo "architect-api 가 healthy 가 아니다 — sudo docker compose logs --tail 30 architect-api" >&2; exit 1; }
sudo docker compose up -d --pull never                                 # 설정이 바뀐 나머지
rest=${FORCE//architect-api/}
[[ -z ${rest// /} ]] || sudo docker compose up -d --force-recreate --no-deps --pull never $rest

echo "[6] 상태"
sleep 10
sudo docker compose ps -a
[[ $TAG == --no-images ]] || rm -f "$ASSET" "$ASSET.sha256"
echo "끝 — 11장 healthy · authority-init Exited (0) 인지 위에서 본다"
