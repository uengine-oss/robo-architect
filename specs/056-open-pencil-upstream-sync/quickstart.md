# Quickstart 056

## 브랜치/체크아웃
- robo-architect: `056-open-pencil-upstream-sync` (base `044-design-import`, worktree `.worktrees/056-open-pencil-upstream-sync`)
- open-pencil 서브모듈: 브랜치 `robo-upstream-sync` (= upstream master cb7ceea6 + 재이식 커밋). 이전 fork 는 `robo-fork-legacy`.

## 개발 스택 (워크트리)
```bash
# 1) open-pencil 패키지 빌드 (dist 는 wireframe-service 가 사용)
cd open-pencil && bun install && bun run build:packages
# 2) 컴포넌트 라이브러리 렌더 서비스 (기본 7610)
COMPONENT_LIBRARY_PATH=../input/common_only.fig bun packages/cli/src/wireframe-service.ts
# 3) 백엔드 (.env 의 API_PORT) / 프론트 (VITE_API_PROXY 로 백엔드 지정)
uv run uvicorn api.main:app --port 8310
cd frontend && VITE_API_PROXY=http://127.0.0.1:8310 npx vite --port 5174
```

## 검증
```bash
PYTHONPATH=. uv run --with pytest --with pytest-asyncio pytest \
  api/features/proposal_lifecycle/tests/test_storyboard.py api/features/figma_binding/tests/test_component_library.py
# 스토리보드 시연(영상 webm + 스크린샷 → frontend/tests/.artifacts/storyboard/)
uv run python scripts/seed_proposal_storyboard_demo.py --reset-storyboard
cd frontend && npx playwright test -c playwright.storyboard.config.ts
```

## wireframe-service API 변화
- `/render` JSX 에서 `<Instance component="Name" Size="lg" overrides={{ "label:text": "…" }} />` 네이티브 지원.
  속성명에 공백이 있으면 `variant={{ "Property 1": "Default" }}`.
- `$INSTANCE:Name|k=v` 마커 프레임은 서비스가 `<Instance>` 로 자동 변환(레거시 호환).
- `/components?format=prompt` 에 variant 속성·오버라이드 가능 텍스트 자식이 포함된다.
- 알 수 없는 `<Icon>` 은 렌더 실패 대신 같은 크기의 플레이스홀더로 대체된다.
