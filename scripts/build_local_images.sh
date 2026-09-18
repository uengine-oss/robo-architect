#!/usr/bin/env bash
# 설치본 스택 이미지 8종을 로컬에 준비한다 — Electron 없이 스택을 재기 위해.
#
# spec 058 T002.
#
# ## 종료 코드를 파이프에 태우지 않는다
#
# `docker build ... | tail` 은 **tail 의 종료 코드**를 낸다. 빌드가 죽어도 0 이다.
# 09-17 에 이걸로 넷이 전부 실패인데 "성공"으로 읽을 뻔했다. 그래서 여기서는
#   (a) 파이프 없이 돌리고
#   (b) 끝난 뒤 `docker image inspect` 로 **실재를 센다**
# 둘 다 한다. 빌드가 0 을 내도 이미지가 없으면 실패다.
#
# ## analyzer·catalog 의 Dockerfile 이 우리 브랜치에 없다
#
# 두 저장소의 Dockerfile 은 `origin/main` 에만 있다(전용 브랜치가 옛 main 에서
# 갈라졌다). 릴리스는 그 자리에서 `docker build <repo root>` 를 하므로 지금 구성으로는
# 못 굽는다. **이 스크립트는 그 사실을 숨기지 않는다** — 스크래치로 우회하되,
# 우회했다는 것을 출력에 남긴다. 근본 해결은 T006·T009 의 이식이다.
#
# 사용:
#   scripts/build_local_images.sh                 # 전부
#   scripts/build_local_images.sh --tag local-x   # 태그 지정
#   scripts/build_local_images.sh --verify-only   # 굽지 않고 실재만 센다

set -uo pipefail

TAG="local-$(date +%m%d)"
VERIFY_ONLY=0
while [ $# -gt 0 ]; do
  case "$1" in
    --tag) TAG="$2"; shift 2 ;;
    --verify-only) VERIFY_ONLY=1; shift ;;
    *) echo "모르는 인자: $1" >&2; exit 2 ;;
  esac
done

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SIBLINGS="$(dirname "$REPO_ROOT")"
SCRATCH="${TMPDIR:-/tmp}/robo-image-build"
mkdir -p "$SCRATCH"

# 상류에서 받는 것 — 태그가 고정이다 (desktop/runtime/runtime-manifest.template.json)
PULL_NEO4J="neo4j:5.26.0"
PULL_MINDSDB="mindsdb/mindsdb:v26.1.0"
PULL_PDF2BPMN="ghcr.io/uengine-oss/process-gpt-bpmn-extractor:8156f77"

FAILED=()
WORKAROUNDS=()

note()  { printf '  %s\n' "$*"; }
fail()  { FAILED+=("$1"); printf '  ✗ %s — %s\n' "$1" "$2"; }

# 이미지가 실제로 있는지 — 빌드 종료 코드가 아니라 이것으로 판정한다.
exists() { docker image inspect "$1" >/dev/null 2>&1; }

build_repo() {           # build_repo <이름> <컨텍스트> [-f <Dockerfile>]
  local name="$1" ctx="$2"; shift 2
  local image="uengine/$name:$TAG"
  if [ ! -d "$ctx" ]; then fail "$name" "컨텍스트 없음: $ctx"; return; fi
  printf '  %s … ' "$name"
  if docker build "$@" -t "$image" "$ctx" >"$SCRATCH/$name.log" 2>&1; then
    if exists "$image"; then
      printf '%s\n' "$(docker image inspect "$image" --format '{{.Architecture}} {{.Size}}')"
    else
      printf '\n'; fail "$name" "빌드는 0 인데 이미지가 없다 — $SCRATCH/$name.log"
    fi
  else
    printf '\n'; fail "$name" "빌드 실패 — $SCRATCH/$name.log (마지막 줄: $(tail -1 "$SCRATCH/$name.log"))"
  fi
}

# origin/main 의 Dockerfile 을 스크래치로 뽑는다. 저장소는 건드리지 않는다.
borrow_dockerfile() {    # borrow_dockerfile <저장소> <이름>  → 경로를 stdout 으로
  local repo="$1" name="$2" out="$SCRATCH/$name.Dockerfile"
  git -C "$repo" show origin/main:Dockerfile >"$out" 2>/dev/null || return 1
  printf '%s' "$out"
}

echo "태그: $TAG"
echo

if [ "$VERIFY_ONLY" -eq 0 ]; then
  echo "받는 것 (3종)"
  for spec in "$PULL_NEO4J" "$PULL_MINDSDB"; do
    printf '  %s … ' "$spec"
    if docker pull "$spec" >"$SCRATCH/pull.log" 2>&1 && exists "$spec"; then echo "ok"; else echo; fail "$spec" "pull 실패"; fi
  done
  printf '  %s … ' "$PULL_PDF2BPMN"
  # amd64 전용 상류 이미지. compose 도 같은 platform 을 선언한다.
  if docker pull --platform linux/amd64 "$PULL_PDF2BPMN" >"$SCRATCH/pull.log" 2>&1 && exists "$PULL_PDF2BPMN"; then echo "ok (amd64)"; else echo; fail "$PULL_PDF2BPMN" "pull 실패"; fi

  echo
  echo "굽는 것 (5종)"
  build_repo "robo-data-fabric"  "$REPO_ROOT/robo-analyzer/robo-data-fabric"
  build_repo "robo-antlr-parser" "$SIBLINGS/antlr-code-parser"
  build_repo "robo-api-gateway"  "$SIBLINGS/robo-api-gateway"

  # analyzer·catalog — 우리 브랜치에 Dockerfile 이 없다 (T006·T009 가 해소한다)
  for pair in "robo-data-catalog:robo-data-catalog" "robo-analyzer:robo-data-analyzer"; do
    image_name="${pair%%:*}"; dir_name="${pair##*:}"
    ctx="$REPO_ROOT/robo-analyzer/$dir_name"
    if [ -f "$ctx/Dockerfile" ]; then
      build_repo "$image_name" "$ctx"
    else
      df="$(borrow_dockerfile "$ctx" "$image_name")" || { fail "$image_name" "origin/main 에도 Dockerfile 이 없다"; continue; }
      WORKAROUNDS+=("$image_name: 저장소에 Dockerfile 이 없어 origin/main 것을 빌려 썼다")
      build_repo "$image_name" "$ctx" -f "$df"
    fi
  done
fi

echo
echo "실재 확인 (빌드 종료 코드가 아니라 이것으로 판정한다)"
MISSING=0
for image in "$PULL_NEO4J" "$PULL_MINDSDB" "$PULL_PDF2BPMN" \
             "uengine/robo-analyzer:$TAG" "uengine/robo-data-catalog:$TAG" \
             "uengine/robo-data-fabric:$TAG" "uengine/robo-antlr-parser:$TAG" \
             "uengine/robo-api-gateway:$TAG"; do
  if exists "$image"; then
    printf '  ✓ %-56s %s\n' "$image" "$(docker image inspect "$image" --format '{{.Architecture}}')"
  else
    printf '  ✗ %-56s 없음\n' "$image"; MISSING=$((MISSING + 1))
  fi
done

if [ ${#WORKAROUNDS[@]} -gt 0 ]; then
  echo
  echo "우회한 것 — 릴리스에서는 이렇게 못 한다"
  for w in "${WORKAROUNDS[@]}"; do note "$w"; done
fi

echo
if [ "$MISSING" -gt 0 ] || [ ${#FAILED[@]} -gt 0 ]; then
  echo "실패: 없는 이미지 $MISSING 종 · 실패한 단계 ${#FAILED[@]} 건"
  echo "  디스크가 찼으면: docker builder prune -f && docker image prune -f"
  echo "  **볼륨은 건드리지 마라** — 저장소 데이터가 거기 있다"
  exit 1
fi
echo "이미지 8종 준비 완료"
