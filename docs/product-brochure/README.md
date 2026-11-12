# Robo Architect Lite 제품 소개서

**산출물**: `Robo-Architect-제품소개서-2026.10.pdf` (A4 · 25쪽)
**원본**: `robo-architect-lite-brochure.html` — 인쇄용 CSS(A4 페이지 단위)로 작성한 단일 HTML. 문구는 이 파일을 직접 고친다.
**이미지**: `assets/*.jpg` — 튜토리얼 촬영 원본(`demo/tutorial/shots/*.png`, 2560×1440 = 1280×720 창의 2배 밀도, 다크 테마)을 원본 해상도로 잘라 JPG(4:4:4, 품질 92)로 저장. 모두 데모 데이터(튜토리얼 실습) 화면이다.

이전 웹판 소개서(`robo-architect` 저장소 `docs/product-brochure/`, 2026.09, Neo4j · 스토리보드 · 프레임 편집기 기준)를 바탕으로 CSS · 표지/목차/배표지 형식 · 배경 3–5쪽 · 레퍼런스 · 도입 일정 쪽을 이어받고, 나머지는 Lite 데스크톱판과 튜토리얼에 맞춰 다시 썼다.

## 구성

| 쪽 | 내용 |
|---|---|
| 1 | 표지 (21종 스킬 · 7개 컨테이너 · Dual Merge) |
| 2 | 목차 · 한 장 요약 |
| 3 | 배경 ① — AI 코딩의 역설(METR) · 네 가지 문제와 Lite의 대응 |
| 4 | 배경 ② — 명세(SDD) · 시나리오(BDD) · 도메인(DDD), 제품에서 쓰이는 위치 |
| 5 | 배경 ③ — 여러 팀의 명세 관리 · 파일 기반과 그래프 기반 |
| 6 | Robo Architect Lite 소개 (입력/처리/출력 · 기존 방식 비교 · 상태 흐름) |
| 7 | 주요 산출물 ① — 프로젝트 설계 그래프 (노드 26종 · 관계 32종) |
| 8 | 주요 산출물 ② — 설계 원칙 · 계획 · 코드 · 검증 기록 |
| 9 | 제품 화면 한눈에 보기 (요구사항 · 프로세스 · 설계 캔버스 · 레거시, 홈 기능 카드 8개) |
| 10 | 특장점 ① 요구사항을 설계와 인수 조건으로 구체화 |
| 11 | 특장점 ② 프로젝트 설계 원칙(Constitution)을 근거로 계획 |
| 12 | 특장점 ③ 격리된 작업 공간(git worktree)에서 Claude Code가 구현 |
| 13 | 특장점 ④ 검증(구조 · 인수 조건)과 Dual Merge · 되돌리기 |
| 14 | 특장점 ⑤ 변경 영향(CREATE/MODIFY · 충돌 가능성) |
| 15 | 특장점 ⑥ 레거시 코드 · 데이터베이스를 설계 근거로 |
| 16 | 시스템 구성과 실행 환경 (컨테이너 8개) |
| 17 | 기술 스택과 스킬 체계 (스킬 21종) |
| 18–19 | 사용 절차 6단계 (실제 화면) |
| 20 | 보안 · 거버넌스 |
| 21 | 설치 및 납품 방식 |
| 22 | 제품 개발 및 품질 검증 체계 (시험 규모 · 실측 소요 시간) |
| 23 | 기반 제품 MSAEZ의 도입 실적 (포스코DX · DPG 통합테스트베드 · MSA School — 사용자 제공, 원문 유지) |
| 24 | 도입 절차 및 일정 |
| 25 | 배표지 |

## 다시 만들기

`@playwright/test` 가 있는 `frontend/` 에서 스킬의 렌더 스크립트를 돌린다. 넘침 검사가 함께 돈다(넘치면 종료 코드 1).

```bash
cd frontend
node ~/.claude/skills/brochure/assets/render.mjs \
  ../docs/product-brochure/robo-architect-lite-brochure.html \
  "../docs/product-brochure/Robo-Architect-제품소개서-2026.10.pdf"
```

마지막 렌더 결과: 쪽수 25 · 넘침 없음. 쪽별 하단 여유는 본문 쪽 모두 0–14mm(표지 · 배표지 제외).

쪽을 넣거나 빼면 쪽 번호와 그림 번호를 다시 매기고, 목차 쪽수는 손으로 맞춘다.

```python
import re
f = 'robo-architect-lite-brochure.html'; s = open(f).read()
n = [1]
s = re.sub(r'(<div class="foot"><span>[^<]+</span><span>)\d+(</span></div>)',
           lambda m: (n.__setitem__(0, n[0] + 1), f'{m.group(1)}{n[0]}{m.group(2)}')[1], s)
c = [0]
s = re.sub(r'<b>그림 \d+\.', lambda m: (c.__setitem__(0, c[0] + 1), f'<b>그림 {c[0]}.')[1], s)
open(f, 'w').write(s)
```

### 그림 다시 자르기

앱을 다시 띄워 찍지 않는다. 튜토리얼 촬영 원본에서 아래 영역(원본 픽셀 `x0, y0, x1, y1`)을 잘라 같은 이름으로 저장한다. 촬영을 다시 했다면 화면 배치가 같은지 눈으로 확인한 뒤 자른다.

| 파일 | 원본(`demo/tutorial/shots/`) | 영역 | 쓰인 쪽 |
|---|---|---|---|
| cover-home.jpg | layout-01-home.png | 0, 0, 2560, 1040 | 1 |
| out-strategic.jpg | proposal-07-strategic-2.png | 1380, 650, 2520, 1062 | 7 |
| out-constitution.jpg | constitution-01-editor.png | 600, 160, 1960, 575 | 8 |
| g-stories.jpg | design-01-story-detail.png | 150, 85, 1320, 911 | 9 |
| g-process.jpg | design-02-event-modeling.png | 760, 130, 1960, 977 | 9 |
| g-design.jpg | design-03-design.png | 760, 212, 1960, 1059 | 9 |
| g-legacy.jpg | legacy-06-detail-rules.png | 1340, 268, 2540, 1115 | 9 |
| f1-intent.jpg | proposal-06-detail.png | 1385, 270, 2535, 1190 | 10 |
| f2-plan-grounds.jpg | plan-05-scroll-3.png | 1385, 228, 2535, 578 | 11 |
| f3-progress.jpg | impl-08-progress-05461.png | 1380, 620, 2530, 1350 | 12 |
| f4-verify-numbers.jpg | verify-03-result.png | 1380, 1180, 2530, 1330 | 13 |
| f4-verify-cards.jpg | verify-03-result-2.png | 1395, 300, 2530, 1150 | 13 |
| f5-tactical-modify.jpg | change-08-plan-modify.png | 1385, 770, 2535, 1125 | 14 |
| f6-evidence-head.jpg | legacy-13-evidence.png | 1375, 250, 2535, 800 | 15 |
| f6-evidence.jpg | legacy-14-evidence-pop.png | 1600, 200, 2540, 925 | 15 |
| u1-project.jpg | layout-02-switch.png | 600, 440, 2480, 860 | 18 |
| u2-new-proposal.jpg | proposal-02-create.png | 1385, 250, 2535, 770 | 18 |
| u3-analyzing.jpg | proposal-03-analyzing-2.png | 1385, 250, 2535, 930 | 18 |
| u4-plan-confirmed.jpg | plan-06-confirmed.png | 1385, 640, 2535, 1440 | 19 |
| u5-tasks.jpg | impl-03-sandbox.png | 1385, 620, 2535, 1400 | 19 |
| u6-accepted.jpg | verify-06-accepted.png | 1385, 230, 2535, 1000 | 19 |
| i-boot.jpg | install-boot.png | 620, 340, 2470, 760 | 21 |

```python
from PIL import Image
SHOTS = '../../demo/tutorial/shots/'          # docs/product-brochure 기준
MAP = {'cover-home': ('layout-01-home.png', (0, 0, 2560, 1040))}   # 위 표 그대로 채운다
for name, (src, box) in MAP.items():
    Image.open(SHOTS + src).convert('RGB').crop(box).save(
        f'assets/{name}.jpg', 'JPEG', quality=92, subsampling=0, optimize=True)
```

전폭 그림은 원본 폭 2,000px 이하, 반폭(2열) 그림은 1,200px 안팎으로 잘라 인쇄 크기에서 글자가 읽히게 했다.

## 사실관계 근거

수치는 모두 2026-10-31 기준 `feat/lite-project-graphs`(6b305f00) 작업 트리에서 세거나, 튜토리얼 원고(`ra-docs/src/*.md`)의 실측값을 옮겼다.

### 저장소에서 센 것

| 수치 | 근거 |
|---|---|
| 스킬 21종 (robo-proposals 15 · robo-spec 4 · robo-changes 2) | `skills/*/*/SKILL.md` (앱 묶음 `desktop/resources/runtime/architect/app/skills/` 도 같은 21개) |
| 컨테이너 8개 (graph-db · graph-bolt · fabric · catalog · analyzer · parser · gateway · wireframe) | `desktop/runtime/compose.yml`, 이미지 이름은 `desktop/runtime/runtime-manifest.template.json` |
| 포트는 루프백(127.0.0.1)에만 공개 | `compose.yml` 의 `ports` |
| 설계 graph 와 분석 graph 이름이 같으면 기동 거부 | `compose.yml` graph-db 주석(`OG_GRAPH_DESIGN` / `OG_GRAPH_ANALYSIS`) |
| 노드 유형 26종 | `docs/cypher/schema/*.cypher` 의 `CREATE CONSTRAINT/INDEX … FOR (x:Label)` 라벨 수 |
| 관계 유형 32종 | `docs/cypher/schema/*.cypher` 의 `[:REL]` 관계 이름 수 |
| 백엔드 시험 파일 85개 · 시험 함수 725개 | `api/**/test_*.py` 84개 + `tests/platform` 1개, `def test_` 개수 (pytest 수집 패턴은 `pyproject.toml`) |
| 화면 시험 파일 72개 | `frontend/tests/*.spec.ts` 69개 + `frontend/tests-analyzer` 3개 |
| 회귀 시험 14개 | `frontend/playwright.regression.config.ts` 의 모킹 화면 spec 12개 + `playwright.unit.config.ts` 단위 spec 2개(`npm run test:regression`) |
| 데스크톱 시험 파일 4개 | `desktop/tests/**/*.spec.ts` |
| 기능 폴더 59개 · spec.md 58 · plan.md 42 · tasks.md 39 | `specs/[0-9]*/` |
| 기술 스택 버전 | `desktop/package.json`(Electron ^33.4, electron-builder ^25, TypeScript ^5.5), `frontend/package.json`(Vue ^3.5, Vite ^5, Pinia ^2, Vue Flow ^1.33, bpmn-js ^18, Mermaid ^11, Tailwind ^4, CodeMirror 6, xterm ^6, Playwright ^1.60), `pyproject.toml`(Python ≥3.11, FastAPI ≥0.115, Uvicorn, Pydantic ≥2, sse-starlette, mcp, ruff) |
| 설치 형태 Windows NSIS(사용자 단위) · macOS DMG(arm64) | `desktop/electron-builder.yml` |
| 이미지 묶음 SHA256 확인 후 적재 | `desktop/src/main/docker-images.ts` (`docker.image_archive_checksum_mismatch`) |
| Dual Merge: 그래프 반영 실패 시 git reset + MERGE_FAILED | `api/features/proposal_lifecycle/services/dual_merge.py` |
| 같은 노드를 구현 중인 프로포절이 있으면 제출 거부(409) | `api/features/proposal_lifecycle/routes/proposals_crud.py` `submit_proposal` |
| 자기 승인 허용(기본 PO) — 그래서 "자기 승인 금지"는 쓰지 않음 | `api/features/proposal_lifecycle/routes/proposals_acceptance.py` |
| 레거시 분석기의 AI 호출 → Claude Code(도구 없음, 빈 임시 폴더) | `api/features/llm_bridge/router.py` 머리 주석 |
| 프로포절 스킬 실행: 기본 Claude Code CLI, 선택 OpenAI 호환 | `api/platform/skill_runner.py`, `api/platform/skill_execution_strategy.py`(`SKILL_RUNNER_PROVIDER`) |
| 비밀 값 보관(사용자 전용 파일 · OS 암호화) | `desktop/src/main/secret-store.ts` |
| 요청 추적 번호 | `api/platform/observability/request_logging.py` |

### 튜토리얼 실측(데모 데이터)

원고: 튜토리얼 사이트 원본 `tools/ra-docs/src/*.md`(홈페이지 작업 트리). 화면은 macOS(Apple Silicon)에서 Lite 앱을 실제로 실행해 찍었다.

| 수치 | 장 |
|---|---|
| INTENT 132초 · 프로세스 2 · 컨텍스트 2(주문 Core · 메뉴 관리 Supporting) · 기능 6 · 스토리 7 | 3장 proposal.md |
| 설계 원칙 인터뷰 질문 2개 → 원칙 7개 | 4장 constitution.md |
| Plan 598초(약 10분) · 전술 설계 20개 항목 · 「헌장 공백」 IDENTITY_AND_STORE_OWNERSHIP_SOURCE | 5장 plan.md |
| 작업 15개(Phase 6) · 구현 약 22분 · 커밋 15건 · 69개 파일 3,622줄(잠금 파일 제외) | 6장 implement.md |
| 검증 49건: PASS 44 · FAIL 0 · SKIP 5(통과율 90%), 인수 조건 18/18, 구조 31(PASS 26 · SKIP 5), 검증~수락 약 7분, 병합 후 `npm test` 45건 통과 | 7장 verify.md |
| PRO-002 INTENT 80초 · Plan 395초 · Order MODIFY · 충돌 가능성 HIGH | 9장 change.md |
| 스킬 규칙 한 줄 추가 → 앱 재시작 없이 다음 분석부터 영문 병기 | 10장 skills.md |
| 데이터 소스 유형 PostgreSQL · MySQL · MariaDB | 11장 fabric.md |
| 요구사항 문서 171초 · 컨텍스트 5 · 기능 10 · 스토리 17 · 프로세스 3 | 12장 ingest.md |
| 레거시 분석 141초 · 클래스 6 · 메서드 18 · 테이블 7(컬럼 32) · 호출 46 · 업무 규칙 53(다른 실행 35) · 근거 15 · 근거 연결 11/11 | 13장 legacy.md |
| 첫 기동 약 50초(설치본 첫 실행 4~5분) · 설치 프로그램 약 100MB · 이미지 묶음 약 1.5GB · 권장 사양 16GB/20GB | 1장 install.md |

### 그대로 옮긴 것

- 3쪽 연구 수치: [METR 2025년 무작위 대조 실험](https://metr.org/blog/2025-07-10-early-2025-ai-experienced-os-dev-study/) — 이전 소개서와 동일.
- 23쪽 레퍼런스(포스코DX · DPG 통합테스트베드 · MSA School 325회 · 9,655명 · 17,864시간): 사용자 제공, 이전 소개서 원문. 바꾼 곳은 맺음 콜아웃의 신제품 기능 나열(Lite가 하지 않는 "화면 초안 생성 · 폐쇄망 설치"를 빼고 Lite 기능으로 교체)과, 기반 제품과 신제품을 구분하는 한 줄 표.

## 확인이 필요한 것

- macOS(Apple Silicon) 설치 파일은 배포 준비 중으로만 적었다. 공개되면 21쪽 표를 고친다.
- 프로포절 스킬의 OpenAI 호환 실행(`SKILL_RUNNER_PROVIDER=openai_compatible`)은 코드와 단위 시험으로만 확인했고 튜토리얼에서는 쓰지 않았다(20쪽).
- 도입 일정(24쪽)은 이전 소개서의 표준 예시 그대로다.

## English edition

**Output**: `Robo-Architect-Brochure-2026.10.pdf` (A4 · 25 pages)
**Source**: `robo-architect-lite-brochure-en.html` — same pages, layout and CSS rules as the Korean HTML (only the CSS comments are translated). Edit the wording in this file directly.
**Images**: `assets-en/*.jpg` — same file names as `assets/`, cropped from the English-mode captures `demo/tutorial/shots-en/*.png` (2560×1440, JPG quality 92, 4:4:4). The Korean `assets/` and PDF are untouched.

### Rebuild

```bash
cd frontend
node ~/.claude/skills/brochure/assets/render.mjs \
  ../docs/product-brochure/robo-architect-lite-brochure-en.html \
  ../docs/product-brochure/Robo-Architect-Brochure-2026.10.pdf
```

Last render (2026-11-01): 25 pages, no overflow. Bottom slack on body pages 0–10 mm (cover and back cover 16 mm, as in the Korean edition). English runs longer than Korean, so the copy was shortened page by page; type sizes were not changed. A few figure heights (`--h`) differ from the Korean HTML to fit the English crops.

Korean check: macOS Vision OCR (ko-KR + en-US) over the PDF rendered at 300 dpi and over every `assets-en` crop at full resolution, plus `pdftotext` on the text layer. Result: no Korean text. The only OCR hits were icons and punctuation misread at confidence 0.3 (an em dash in the page-21 table, ↗ arrows, the Design Canvas icon, actor icons on the design canvas).

### Crop table (English)

Shots marked * differ from the Korean table: either the Korean shot does not exist in `shots-en/` or the English shot shows the same moment under another name. Boxes differ where the English layout moved (longer text).

| File | Source (`demo/tutorial/shots-en/`) | Box (x0, y0, x1, y1) | Page |
|---|---|---|---|
| cover-home.jpg | install-home-project.png * | 0, 0, 2560, 1040 | 1 |
| out-strategic.jpg | proposal-07-strategic-3.png * | 1410, 615, 2530, 1020 | 7 |
| out-constitution.jpg | constitution-01-editor.png | 600, 160, 1960, 575 | 8 |
| g-stories.jpg | design-01-story-detail.png | 200, 85, 1370, 911 | 9 |
| g-process.jpg | design-02-event-modeling.png | 800, 205, 1960, 905 | 9 |
| g-design.jpg | design-03-design.png | 200, 170, 1560, 985 | 9 |
| g-legacy.jpg | legacy-06-detail-rules.png | 1340, 268, 2540, 1115 | 9 |
| f1-intent.jpg | proposal-06-detail.png | 1385, 270, 2535, 1190 | 10 |
| f2-plan-grounds.jpg | plan-05-scroll-3.png | 1420, 282, 2515, 625 | 11 |
| f3-progress.jpg | impl-08-progress-03437.png * | 1410, 580, 2530, 1440 | 12 |
| f4-verify-numbers.jpg | verify-03-result-retake.png * | 1405, 900, 2535, 1050 | 13 |
| f4-verify-cards.jpg | verify-03-result-retake-1.png * | 1395, 395, 2530, 1245 | 13 |
| f5-tactical-modify.jpg | change-08-plan-modify.png | 1410, 795, 2530, 1135 | 14 |
| f6-evidence-head.jpg | legacy-13-evidence.png | 1395, 250, 2555, 800 | 15 |
| f6-evidence.jpg | legacy-14-evidence-pop.png | 1600, 200, 2540, 925 | 15 |
| u1-project.jpg | install-project-folder.png * | 640, 465, 2450, 870 | 18 |
| u2-new-proposal.jpg | proposal-02-create.png | 1385, 250, 2535, 770 | 18 |
| u3-analyzing.jpg | proposal-03-analyzing-1.png * | 1395, 255, 2535, 820 | 18 |
| u4-plan-confirmed.jpg | plan-06-confirmed.png | 1415, 660, 2535, 1420 | 19 |
| u5-tasks.jpg | impl-05-tasks.png * | 1410, 660, 2530, 1440 | 19 |
| u6-accepted.jpg | verify-06-accepted.png | 1405, 262, 2535, 1085 | 19 |
| i-boot.jpg | install-boot.png | 620, 350, 2470, 770 | 21 |

Why the replacements: `layout-01-home` / `layout-02-switch` were not captured in English (Home with the project open and the project panel come from the install chapter); the Ordering (Core) block is in `proposal-07-strategic-3` in the English layout; `impl-05-tasks`, `impl-08-progress-03437` and `verify-03-result-retake(-1)` are the known English equivalents (`to-webp.py` `EN_SHOT`); `proposal-03-analyzing-2` shows a Korean search query written by the model, so `proposal-03-analyzing-1` is used with a box that stops above its Korean line. Chapter 8–9 crops use the current captures only (`design-*` 16:07–16:08 UTC, `change-08-plan-modify` 16:05 UTC on 2026-10-31).

```python
from PIL import Image
SHOTS = '../../demo/tutorial/shots-en/'      # from docs/product-brochure
MAP = {'cover-home': ('install-home-project.png', (0, 0, 2560, 1040))}   # fill in from the table above
for name, (src, box) in MAP.items():
    Image.open(SHOTS + src).convert('RGB').crop(box).save(
        f'assets-en/{name}.jpg', 'JPEG', quality=92, subsampling=0, optimize=True)
```

### Numbers that differ from the Korean edition

Tutorial demo figures come from the English run (`tools/ra-docs/src-en/*.md` in the homepage work tree, and `shots-en/` logs and facts where the chapter 8–9 text is not yet reconciled). Code-derived numbers, METR figures, MSAEZ figures and installation figures are the same as in the Korean edition.

| Page | Korean edition | English edition | Source |
|---|---|---|---|
| 8, 12 | 15 tasks · 15 commits · 6 phases | 18 tasks · 18 commits · 8 phases | implement.md |
| 8, 12 | 69 files · 3,622 lines | 125 files · 9,290 lines | implement.md |
| 8 | 45 tests passed after merge | 296 (274 backend + 22 frontend) | verify.md |
| 10, 22 | INTENT 132 s · 6 features · 7 stories (owner 4, customer 3) | 127 s · 7 features · 9 stories (owner 4, customer 5) | proposal.md |
| 10, 22 | Requirements document 171 s · 3 processes | 161 s · 2 processes (5 contexts · 10 features · 17 stories unchanged) | ingest.md |
| 11 | Constitution gap IDENTITY_AND_STORE_OWNERSHIP_SOURCE; decisions deployment · data access · test strategy | AUTHENTICATION; decisions deployment · data access · API errors | plan.md |
| 12 | Progress shot 7/15 · about 22 min | 2/18 · about 35 min | implement.md, shot |
| 13, 22 | 49 checks: 44 PASS · 0 FAIL · 5 SKIP (90%); criteria 18, structural 31 | 52 checks: 52 PASS · 0 FAIL · 0 SKIP (100%); criteria 24, structural 28 | verify.md |
| 13, 22 | Validation to acceptance about 7 min | about 8 min | verify.md |
| 22 | Plan 598 s · 20 tactical items | 693 s · 28 items (3 aggregates) | plan.md |
| 14, 22 | PRO-002 INTENT 80 s + Plan 395 s (about 6 min) | 70 s + 404 s (about 7 min) | `shots-en/change-log.txt` (change.md still shows the Korean run) |
| 14 | Two features added; read model CustomerOrderView; Order with 2 invariants | One feature, Store Order Rejection, with two stories; read model MyOrderStatus; Order with 3 invariants | `facts-09-change.json`, `facts-09-plan.json`, `change-08-plan*.png` |
| 15, 22 | Business rules 53 (runs: 35 · 53) | 35–53 (runs: 35 · 52 · 53) | legacy.md |
| 15 | Evidence cited by 5 elements; criterion “no reason recorded before the feature” | Evidence detail with placeOrder and rejectOrder; criterion “I am told that 3 orders were rejected” | legacy.md, shot |
| 17 | Skill rule: English name next to each context name | Short code in parentheses: Menu Management (MENU), Ordering (ORD) | skills.md |
| 7, 9 | Trace / Event Modeling UI “주문하기 화면” | “Place order button” (UI name in the English graph) | design-02/03 shots |

### Notes

- Figure 2 (Constitution editor) does not show the document title: in the English capture the editor opens on a Sync Impact Report, so the caption describes the editor only.
- Figure 13 shows two pieces of evidence (placeOrder, rejectOrder); the “Cited by n elements” line is below the visible area and is explained in the table next to it.
- The home screenshot on the cover has the Design Canvas card in its hover state (as captured).
- macOS (Apple Silicon) installer: stated as being prepared for release, as in the Korean edition.
