# Robo Architect 제품 소개서

**산출물**: `Robo-Architect-제품소개서-2026.09.pdf` (A4 · 23쪽)
**원본**: `robo-architect-brochure.html` — 인쇄용 CSS(A4 페이지 단위)로 작성된 단일 HTML
**이미지**: `assets/` — 모두 실제 구동 인스턴스에서 캡처(데모 데이터 기준)

## 구성

| 쪽 | 내용 |
|---|---|
| 1 | 표지 |
| 2 | 목차 · 한 장 요약 |
| 3–6 | 배경 · 제품 정의 · 산출물(도메인 그래프 / 화면과 코드) |
| 7 | 제품 화면 한눈에 보기 (Stories · Design · Processes · Data) |
| 8–13 | 특장점 ①~⑥ |
| 14–15 | 아키텍처 · 기술 스택 |
| 16–17 | 사용 흐름 6단계 |
| 18–19 | 보안 · 거버넌스 · 납품 |
| 20 | 검증 체계 |
| 21 | 레퍼런스 — 포스코DX · DPG 통합테스트베드 · MSA School |
| 22 | 도입 절차 및 일정 |
| 23 | 배표지 |

## 다시 만들기

이미지를 갱신하거나 문구를 고친 뒤 PDF를 다시 뽑는다.

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

- 레퍼런스 수치(교육 325회 · 수강생 9,655명 · 17,864시간): MSA School 공개 집계
- 그래프 노드 22종 · 관계 32종: `docs/cypher/schema/01_constraints.cypher`
- 인제스트 21단계: `api/features/ingestion/ingestion_contracts.py`의 `IngestionPhase`
- 헌장 원칙: `.specify/memory/constitution.md`
