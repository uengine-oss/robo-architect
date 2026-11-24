#!/usr/bin/env bash
# update.sh <release-tag> [asset] — **사내 서버에서** 새 판을 받아 바꿔 띄운다. 운영-업데이트-가이드.md §3
#
#   bash update.sh posco-web-images-2026-11-20            # images.tar 를 받는다
#   bash update.sh posco-web-images-2026-11-20 api.tar    # 자산 이름이 다르면
#   bash update.sh --no-images                            # yml·가이드만 바뀐 판 (git pull + up)
#   bash update.sh split.db posco-web-images-2026-11-24   # 분할(포스코망) — DB 서버 먼저
#   bash update.sh split.ap posco-web-images-2026-11-24   #               — 그다음 AP 서버
#
#   OFFLINE=1 bash update.sh split.db posco-web-images-…  # github 에 못 닿는 서버 — 아래
#
# OFFLINE=1: git pull · curl 을 하지 않는다. 인터넷 되는 PC 에서 저장소 폴더(최신 main)와 Release 의
#   images.tar(조각이면 이어 붙인 것) · images.tar.sha256 을 이 폴더로 옮겨 온 뒤 돌린다. 대조 · 적재부터 같다.
#
# 분할에서는 서버마다 자기 파일(docker-compose.split.db.yml · .ap.yml)만 띄운다. 묶음은 같은 것을 받는다
# (DB 서버는 안 쓰는 장도 load 되지만 compose 가 찾는 장만 띄운다). 순서는 DB → AP —
# AP 의 architect-api 는 DB 서버의 authority · graph-bolt 에 붙어야 healthy 가 된다.
#
# ⚠ **sudo 없이** 돌린다. curl 이 일반 계정의 https_proxy 를 써야 github 에 닿는다(sudo 는 그것을 버린다).
#   docker 는 스크립트 안에서 sudo 로 부른다 — msa-ez 와 같은 root 저장소.
# ⚠ 지우는 일은 하지 않는다(volume·prune 없음). 받은 tar 는 끝나고 지운다.
#
# 하는 일
#   1 git pull         yml · 가이드 · tiktoken-cache · authority-init
#                      (posco-web 가지로 받은 서버면 main 으로 옮긴다 — 통합 2026-11-18, posco-web 은 은퇴)
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
# 분할이면 첫 인자로 어느 서버인지 — check.sh 와 같은 이름(split.db · split.ap)
ROLE=all
case ${1:-} in
  split.db) ROLE=db; shift ;;
  split.ap) ROLE=ap; shift ;;
esac
case $ROLE in
  db) DC=(sudo docker compose -f docker-compose.split.db.yml); HEALTH_OF=robo-posco-web-authority-1 ;;
  ap) DC=(sudo docker compose -f docker-compose.split.ap.yml); HEALTH_OF=$API ;;
  *)  DC=(sudo docker compose); HEALTH_OF=$API ;;
esac
TAG=${1:?usage: bash update.sh [split.db|split.ap] <release-tag> [asset] | --no-images}
ASSET=${2:-images.tar}
# load 로 덮인 장은 강제로 다시 만든다. web 은 언제나 마지막에 다시(옛 IP).
# analyzer 도 묶음에 들어간다(2026-11-17~) — 빼면 podman 이 옛 analyzer 를 그대로 돌린다.
# load 로 같은 태그(:delivery)를 덮은 장 — podman 은 그 컨테이너를 스스로 안 바꾼다. CI 가 main 에서 굽는 넷.
# (일곱 장은 태그만 옮긴 납품판이라 내용이 안 바뀐다 · authority 는 2026-11-19 부터 CI 가 굽는다)
# parser 도 2026-11-23 부터 저장소 main 에서 굽는다(업로드 한도) — 같은 태그로 덮이므로 강제 목록에 든다.
case $ROLE in
  db) ALL_FORCE="authority" ;   NOIMG_FORCE="" ;;
  ap) ALL_FORCE="architect-api analyzer parser web" ; NOIMG_FORCE="web" ;;
  *)  ALL_FORCE="architect-api analyzer authority parser web" ; NOIMG_FORCE="web" ;;
esac
if [[ $TAG == --no-images ]]; then FORCE=${FORCE-$NOIMG_FORCE}; else FORCE=${FORCE:-$ALL_FORCE}; fi

health() {  # podman 판마다 필드 이름이 다르다
  sudo docker inspect "$1" --format '{{.State.Health.Status}}' 2>/dev/null ||
    sudo docker inspect "$1" --format '{{.State.Healthcheck.Status}}' 2>/dev/null || echo unknown
}

OFFLINE=${OFFLINE:-}
echo "[1] git pull"
if [[ -n $OFFLINE ]]; then
  echo "  OFFLINE — 건너뛴다(옮겨 온 폴더를 그대로 쓴다)"
  git log -1 --oneline 2>/dev/null || true
else
# 이 판은 통합(2026-11-18) 뒤로 main 에서 나온다. posco-web 으로 받은 서버는 한 번 main 으로 옮긴다.
# posco-web 은 main 의 조상이라 빨리감기다. -b posco-web --depth 1 로 받았어도 된다(받을 가지를 main 으로 바꾼다).
if [[ $(git rev-parse --abbrev-ref HEAD) == posco-web ]]; then
  echo "  가지 posco-web → main"
  git remote set-branches origin main
  if [[ -f $(git rev-parse --git-dir)/shallow ]]; then git fetch --depth 1 origin main; else git fetch origin main; fi
  git checkout -B main origin/main
  git branch --set-upstream-to=origin/main main
fi
git pull --ff-only
git log -1 --oneline
fi

if [[ $TAG != --no-images ]]; then
  echo "[2] 받기 — $TAG/$ASSET"
  if [[ -n $OFFLINE ]]; then
    [[ -f $ASSET && -f $ASSET.sha256 ]] || { echo "OFFLINE 인데 $ASSET · $ASSET.sha256 이 이 폴더에 없다" >&2; exit 1; }
    echo "  OFFLINE — 옮겨 온 파일을 쓴다"
  else
  base=https://github.com/$REPO/releases/download/$TAG
  # 2 GiB 를 넘는 묶음은 조각으로 올라온다(<asset>.parts 에 조각 이름) — 있으면 조각을 받아 잇는다
  if curl -fsSL -o "$ASSET.parts" "$base/$ASSET.parts" 2>/dev/null; then
    echo "  조각 $(wc -l < "$ASSET.parts")개"
    while read -r part; do
      [[ -n $part ]] || continue
      curl -fL -C - -o "$part" "$base/$part"
    done < "$ASSET.parts"
    : > "$ASSET"
    while read -r part; do [[ -n $part ]] && cat "$part" >> "$ASSET"; done < "$ASSET.parts"
    while read -r part; do [[ -n $part ]] && rm -f "$part"; done < "$ASSET.parts"
    rm -f "$ASSET.parts"
  else
    rm -f "$ASSET.parts"
    curl -fL -C - -o "$ASSET" "$base/$ASSET"
  fi
  curl -fsSL -o "$ASSET.sha256" "$base/$ASSET.sha256"
  fi
  sha256sum -c "$ASSET.sha256"

  echo "[3] 적재"
  sudo docker load -i "$ASSET"
fi

echo "[4] compose 가 찾는 이미지"
miss=0
for i in $("${DC[@]}" config --images); do
  if sudo docker image inspect "$i" >/dev/null 2>&1; then echo "  O $i"; else echo "  X $i"; miss=$((miss+1)); fi
done
(( miss == 0 )) || { echo "X 가 $miss 장 — 그 장을 tar 에 넣어 다시 받는다" >&2; exit 1; }

echo "[5] 바꿔 띄우기 ($ROLE)"
# 권한 표(authority-init) — 권한 서버가 있는 쪽(통합 · DB)에서만. 다시 돌려도 안전하다
[[ $ROLE == ap ]] || "${DC[@]}" up -d --force-recreate --no-deps authority-init
# 먼저 띄워 기다릴 장 — 통합 · AP 는 architect-api, DB 는 authority
first=architect-api; [[ $ROLE == db ]] && first=authority
if [[ " $FORCE " == *" $first "* ]]; then
  "${DC[@]}" up -d --force-recreate --no-deps --pull never "$first"
else
  "${DC[@]}" up -d --no-deps --pull never "$first"
fi
printf '  %s 기다림' "$first"
for _ in $(seq 1 60); do
  s=$(health "$HEALTH_OF"); [[ $s == healthy ]] && break
  printf ' .'; sleep 5
done
echo " → $s"
[[ $s == healthy ]] || { echo "$first 가 healthy 가 아니다 — ${DC[*]} logs --tail 30 $first" >&2
  [[ $ROLE == ap ]] && echo "  분할 AP 면 DB 서버를 먼저 올렸는지 · DB 서버 방화벽이 이 AP 를 들이는지 본다" >&2
  exit 1; }
"${DC[@]}" up -d --pull never                                          # 설정이 바뀐 나머지
rest=" $FORCE "; rest=${rest// $first / }
[[ -z ${rest// /} ]] || "${DC[@]}" up -d --force-recreate --no-deps --pull never $rest

echo "[6] 상태"
sleep 10
"${DC[@]}" ps -a
[[ $TAG == --no-images ]] || rm -f "$ASSET" "$ASSET.sha256"
case $ROLE in
  db) echo "끝 — DB 3장 healthy · authority-init Exited (0) 인지 본다 → 이제 AP 서버에서 bash update.sh split.ap $TAG" ;;
  ap) echo "끝 — AP 8장 healthy 인지 본다" ;;
  *)  echo "끝 — 11장 healthy · authority-init Exited (0) 인지 위에서 본다" ;;
esac
