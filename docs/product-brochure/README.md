# Robo Architect 제품 소개서

**산출물**: `Robo-Architect-제품소개서-2026.09.pdf` (A4 · 25쪽)
**원본**: `robo-architect-brochure.html` — 인쇄용 CSS(A4 페이지 단위)로 작성된 단일 HTML
**이미지**: `assets/` — 모두 실제 구동 인스턴스에서 캡처(데모 데이터 기준)

## 구성

| 쪽 | 내용 |
|---|---|
| 1 | 표지 |
| 2 | 목차 · 한 장 요약 |
| 3 | 배경 ① — AI 코딩의 역설 (METR 실험 · 느려지는 네 가지 원인) |
| 4 | 배경 ② — 해법의 방향: 명세(SDD) · 행동(BDD) · 도메인(DDD) |
| 5 | 배경 ③ — 파일 명세가 조직 규모에서 깨지는 지점 → 그래프 기반 명세 |
| 6 | Robo Architect 소개 |
| 7–8 | 주요 산출물 ①② (도메인 그래프 / 화면과 코드) |
| 9 | 제품 화면 한눈에 보기 (Stories · Design · Processes · Data) |
| 10–15 | 특장점 ①~⑥ |
| 16–17 | 시스템 구성과 실행 환경 · 기술 스택 |
| 18–19 | 사용 절차 6단계 |
| 20–21 | 보안 · 거버넌스 · 납품 |
| 22 | 검증 체계 |
| 23 | 도입 실적 — 포스코DX · DPG 통합테스트베드 · MSA School |
| 24 | 도입 절차 및 일정 |
| 25 | 배표지 |

## 다시 만들기

이미지를 갱신하거나 문구를 고친 뒤 PDF를 다시 뽑는다.

스킬의 렌더 스크립트를 쓰면 넘침 검사가 함께 돌아간다.

```bash
cd frontend
node ~/.claude/skills/brochure/assets/render.mjs \
  ../docs/product-brochure/robo-architect-brochure.html \
  "../docs/product-brochure/Robo-Architect-제품소개서-2026.09.pdf"
```

직접 돌리려면:

```bash
cd frontend
node - <<'JS'
import { chromium } from '@playwright/test'
import { pathToFileURL } from 'node:url'; import { resolve } from 'node:path'
const b = await chromium.launch(); const page = await b.newPage()
await page.goto(pathToFileURL(resolve('../docs/product-brochure/robo-architect-brochure.html')).href, { waitUntil: 'networkidle' })
await page.waitForTimeout(2500)
await page.pdf({ path: resolve('../docs/product-brochure/Robo-Architect-제품소개서-2026.09.pdf'),
  format: 'A4', printBackground: true, margin: {top:0,right:0,bottom:0,left:0}, preferCSSPageSize: true })
await b.close()
JS
```

페이지 넘침은 각 `.page`의 마지막 자식 하단이 `.foot` 상단을 넘는지로 검사한다
(위 스크립트에 검사 코드를 넣어 쓰면 된다).

## 화면 캡처를 다시 찍으려면

데모 그래프와 데모 제안이 있어야 한다.

```bash
env -u NEO4J_PASSWORD PYTHONPATH=. uv run python scripts/seed_demo_model.py
env -u NEO4J_PASSWORD PYTHONPATH=. uv run python scripts/seed_proposal_storyboard_demo.py
```

Design · Data 탭은 네비게이터에서 항목을 캔버스에 올려야 내용이 보인다
(Design은 더블클릭, Data는 드래그).

## 사실관계 근거

- 배경(3–5쪽)의 논리와 수치: `/Users/uengine/PMO협회/ToBeAINativeSWEngineer-PMO템플릿버전.pptx`
  — METR 2025 무작위 대조 실험(예상 +24% / 실제 −19%), 모호성과 재작업, SDD 3단계,
  BDD 양방향 읽기, 파일 기반 명세가 조직에서 깨지는 네 지점, 파일 vs 그래프 비교
- 레퍼런스 수치(교육 325회 · 수강생 9,655명 · 17,864시간): MSA School 공개 집계
- 그래프 노드 22종 · 관계 32종: `docs/cypher/schema/01_constraints.cypher`
- 인제스트 21단계: `api/features/ingestion/ingestion_contracts.py`의 `IngestionPhase`
- 헌장 원칙: `.specify/memory/constitution.md`
