#!/usr/bin/env bash
# retag-delivery.sh — 임시 (2026-11-13 현장용)
#
# 납품판 robo-images.tar 로 이미 적재한 uengine/* 아홉 장에 posco-web 이 찾는 이름을 붙인다.
# 같은 이미지다(posco-web 의 아홉 장은 납품판을 그대로 다시 올린 것) — 받지 않고 이름만 붙인다.
#
#   sudo bash retag-delivery.sh          이름 붙이기 + 11장 O/X 대조
#
# ⚠ 이미지를 지우지 않는다. 옛 uengine/* 이름표는 그대로 둔다.
# ⚠ msa-ez 와 같은 root 저장소이므로 sudo 로 돌린다(일반 계정 저장소와 섞지 않는다).
set -uo pipefail
cd "$(dirname "$0")"

R=0.1.0-wde10ff6c-afff41f36-scda199-rdel-swp
G=ghcr.io/uengine-oss

# 납품판 이름 → posco-web 이름
MAP="
ontological-db:robo-posco-graph-db
ontological-bolt:robo-posco-graph-bolt
robo-authority:robo-posco-authority
robo-analyzer:robo-posco-analyzer
robo-data-catalog:robo-posco-catalog
robo-data-fabric:robo-posco-fabric
robo-antlr-parser:robo-posco-parser
robo-api-gateway:robo-posco-gateway
open-pencil:robo-posco-wireframe
"

echo "[1] 이름 붙이기"
for m in $MAP; do
  old=uengine/${m%%:*}:$R
  new=$G/${m##*:}:$R
  if docker image inspect "$new" >/dev/null 2>&1; then
    echo "  있음  $new"
  elif ! docker image inspect "$old" >/dev/null 2>&1; then
    echo "  없음  $old  ← 납품판 이미지가 이 저장소에 없다(sudo 로 돌렸나?)"
  elif docker tag "$old" "$new"; then
    echo "  붙임  $new"
  else
    echo "  실패  $new"
  fi
done

echo
echo "[2] compose 가 찾는 11장 대조"
imgs=$(docker compose config --images 2>/dev/null) || {
  echo "  compose config 실패 — .env 가 없으면 먼저: bash init-env.sh"; exit 1; }
miss=0
for i in $imgs; do
  if docker image inspect "$i" >/dev/null 2>&1; then echo "  O  $i"; else echo "  X  $i"; miss=$((miss+1)); fi
done
echo
if (( miss == 0 )); then
  echo "11장 모두 있다 — 다음: .env 네 값 → ⑤-1 모델 확인 → bash check.sh → sudo docker compose up -d --wait --pull never"
else
  echo "X $miss 장 — web·architect-api 면 two.tar 를 sudo docker load -i two.tar"
  exit 1
fi
