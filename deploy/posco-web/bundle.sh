#!/usr/bin/env bash
# bundle.sh <out-dir> [--images] — 서버에 들고 갈 묶음을 만든다. 저장소 안의 것은 안 바꾼다.
#
#   bash deploy/posco-web/bundle.sh /tmp/robo-posco-web            # 파일만
#   bash deploy/posco-web/bundle.sh /tmp/robo-posco-web --images   # + 이미지 tar
#
# 묶음 = compose 셋 + 로컬 시험용 overlay(docker-compose.local-test.yml) · .env.example · init-env.sh · check.sh · authority-init.py · make-split.py ·
#        analyzer-llm/*.yaml(openai_gpt41 · llm_pricing) · README.md · **서버-배포-가이드.md**
#        --images 면  images.tar · image-ids.txt(태그 → image ID) · SHA256SUMS
#
# ⓘ pdf2bpmn 을 뺐으므로(2026-11-11) `pdf2bpmn/facade.py` 를 더 넣지 않는다.
#   그 파일은 **바인드 마운트**였고, 저장소 폴더에서 compose 를 띄우면 도커가 그 자리에
#   빈 디렉터리를 만들어 서비스가 재시작을 반복했다(2026-11-10). 그 함정도 같이 사라졌다.
#   이제 묶음 폴더와 저장소 폴더 어디서 띄워도 결과가 같다.
#
# 서버가 인터넷(GHCR)에 닿지 못하면 --images 로 묶어 `docker load -i images.tar`.
# 받은 쪽은 image-ids.txt 와 `docker image inspect` 를 대조한다.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
OUT=${1:?usage: bundle.sh <out-dir> [--images]}
IMAGES=${2:-}
DOCKER=${DOCKER:-docker}

[[ ! -e $OUT || -z "$(ls -A "$OUT" 2>/dev/null)" ]] || { echo "비어 있지 않다: $OUT" >&2; exit 1; }
mkdir -p "$OUT"
cp "$HERE"/{docker-compose.yml,docker-compose.split.ap.yml,docker-compose.split.db.yml,docker-compose.local-test.yml} "$OUT/"
cp "$HERE"/{.env.example,init-env.sh,check.sh,authority-init.py,make-split.py,README.md} "$OUT/"
# 서버 관리자가 따라가는 가이드 — 묶음 안에 같이 넣는다(이것만 보고 올릴 수 있어야 한다).
cp "$HERE/서버-배포-가이드.md" "$OUT/"
mkdir -p "$OUT/analyzer-llm" && cp "$HERE/analyzer-llm/"*.yaml "$OUT/analyzer-llm/"
# tiktoken 사전 — compose 가 바인드로 붙인다. 없으면 그 장이 안 뜬다(2026-11-13).
cp -r "$HERE/tiktoken-cache" "$OUT/"
cp "$HERE"/{update.sh,운영-업데이트-가이드.md} "$OUT/"
echo "files → $OUT"

if [[ $IMAGES == --images ]]; then
  mapfile -t refs < <(sed -n 's/^    image: *//p' "$HERE/docker-compose.yml" | sort -u)
  : > "$OUT/image-ids.txt"
  for ref in "${refs[@]}"; do
    id=$($DOCKER image inspect "$ref" --format '{{.Id}}') ||
      { echo "이미지가 없다: $ref (docker pull / load 먼저)" >&2; exit 1; }
    echo "$ref $id" >> "$OUT/image-ids.txt"
  done
  echo "saving ${#refs[@]} images…"
  $DOCKER save -o "$OUT/images.tar" "${refs[@]}"
  (cd "$OUT" && sha256sum images.tar image-ids.txt > SHA256SUMS)
  echo "images → $OUT/images.tar ($(du -h "$OUT/images.tar" | cut -f1))"
fi
