#!/usr/bin/env bash
# bundle.sh <out-dir> [--images] — 서버에 들고 갈 묶음을 만든다. 저장소 안의 것은 안 바꾼다.
#
#   bash deploy/posco-web/bundle.sh /tmp/robo-posco-web            # 파일만
#   bash deploy/posco-web/bundle.sh /tmp/robo-posco-web --images   # + 이미지 tar
#
# 묶음 = compose 셋 · .env.example · check.sh · authority-init.py · make-split.py ·
#        pdf2bpmn/facade.py(설치본과 **같은 파일**을 복사한다) · README.md
#        --images 면  images.tar · image-ids.txt(태그 → image ID) · SHA256SUMS
#
# 서버가 인터넷(GHCR)에 닿지 못하면 --images 로 묶어 `docker load -i images.tar`.
# 받은 쪽은 image-ids.txt 와 `docker image inspect` 를 대조한다.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
OUT=${1:?usage: bundle.sh <out-dir> [--images]}
IMAGES=${2:-}
DOCKER=${DOCKER:-docker}

[[ ! -e $OUT || -z "$(ls -A "$OUT" 2>/dev/null)" ]] || { echo "비어 있지 않다: $OUT" >&2; exit 1; }
mkdir -p "$OUT/pdf2bpmn"
cp "$HERE"/{docker-compose.yml,docker-compose.split.ap.yml,docker-compose.split.db.yml} "$OUT/"
cp "$HERE"/{.env.example,check.sh,authority-init.py,make-split.py,README.md} "$OUT/"
cp "$ROOT/desktop/runtime/pdf2bpmn/facade.py" "$OUT/pdf2bpmn/facade.py"
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
