# extensions/posco — POSCO 차이를 담는 자리

현장 판은 **아직 `posco-web` 브랜치**에서 굽는다(2026-11-17 · 금요일 11-20 현장 판 포함).
이 폴더는 그 차이를 main 의 확장 자리로 옮겨 오는 목적지다. 항목 하나를 옮길 때마다
아래 표의 "상태" 를 바꾸고, 같은 커밋에서 posco-web 쪽 코드를 지운다.
**모든 항목이 "옮김" 이 되고 골든 검사(설계 §3-3)가 통과한 뒤에만 posco-web 브랜치를 은퇴**한다.

| 포스코 항목 | posco-web 의 자리 | 옮길 자리 | 상태 |
|---|---|---|---|
| 탭 감춤(Proposals·Code) · 시작 탭 Legacy | `TopBar.vue` · `App.vue` | `frontend/index.js` shell | **자리 생김 · 코어가 읽음**(P3) |
| Proposals·헌장 감춤 | `featureVisibility.js` | `frontend/index.js` features | **옮김**(P5) |
| 레거시 = **폴더를 올려 분석**(경로 지정 모드 안 씀) | `AnalysisPanel.vue` `readRoot()` — 데스크톱이 아니면 projectRoot 를 넘기지 않는다 | `legacy.sourceMode: 'upload'` | **옮김**(P5) — 코어 `readRoot()` 는 기본 'auto'(데스크톱만 경로 모드), 'upload' 면 데스크톱이어도 경로를 안 넘긴다 |
| 새 프로젝트에 **폴더 경로 지정 없음**(Proposals 를 안 쓰므로) | `ProjectPicker.vue` — 이름만 받는다 | `projects.requireRoot: false` | 값만(P5) — ⚠ lite 데스크톱 런처(`LauncherView` · `project-root.ts`)는 폴더를 고르게 한다. P6 에서 desktop 판을 합칠 때 이 값을 읽게 해야 한다 |
| 내보내기 DOCX 만 | `ExportDocumentDialog.vue` | `deliverables.formats` / `allowed_formats` | **옮김**(P5, 화면) — 백엔드 `allowed_formats` 는 별도 |
| 정본화 문구 'ECM 등록' | `ExportDocumentDialog.vue` 스낵바 | `deliverables.ecm` | **옮김**(P5, 화면) |
| 서비스설계서 파일 이름 틀 | `exportDocument/fileName.js` | `deliverables.fileNameTemplate` / `file_name_template` | **옮김**(P5, 화면) — 백엔드 `file_name_template` 는 별도 |
| ECM 검사 | `docx_normalize.py` | `deliverable_policies.ecm_check` | 값만(P5) |
| 생성 모델 기본값 gpt-4.1 | `llm_model_choice.default_model()` · compose | `llm_overrides.default_model` | 값만(P5) |
| 코드 템플릿 세트 poscodx | `code_templates/*` · `fetch-templates.sh` | `template_sets` | 값만(P5) — 화면(`TemplatePanel.vue` 기본 묶음·설명·패키지 표시)은 `frontend/index.js` templates 로 **옮김** |
| SWP SSO(redirect · isValidSSO · 칸 순서 · 이메일 도메인) | `auth/config.py` · `swp.py` · `router.py` · authority | `auth_providers["swp"]` + 프로필 `SWP_*` | 옮길 것(P5) |
| 표준항목 MCP(searchDataDictionary 필드 매핑) | `standard_items/mcp_provider.py` | `standard_item_providers` + 프로필 `ROBO_STANDARD_MCP_URL` | 옮길 것(P5) |
| P-GPT 게이트웨이 | `ai_gateway.py` · `llm.py` | 프로필 `PGPT_*`(코어 LLM 덮어쓰기 자리) | 옮길 것(P5) — 화면 이름('P-GPT')은 `frontend/index.js` `ai.gatewayName` 으로 **옮김** |
| analyzer 가격표 · capabilities | `deploy/posco-web/analyzer-llm/*.yaml` | `profile/` | 옮길 것(P5) |
| Claude 터미널 끔 | web 이미지 `VITE_DISABLE_CLAUDE_TERMINAL=1` | 판(web) 기본값 — 고객 무관 | 판 정리(P6) |
| tiktoken 사전 · 서버 배포 스크립트 · healthcheck · SELinux `:z` | `deploy/posco-web/` | `deploy/web/` — 고객 무관 | 판 정리(P6) |

고객 코드가 기본 판에 새지 않는지는 `scripts/check-customer-leaks.mjs` 가 본다(기본 빌드 번들에
`poscodx` · `swpsso` · `searchDataDictionary` · `설계_` · `P-GPT` 가 0개여야 한다).
