# extensions/posco — POSCO 차이를 담는 자리

현장 판은 **아직 `posco-web` 브랜치**에서 굽는다(2026-11-17 · 금요일 11-20 현장 판 포함).
이 폴더는 그 차이를 main 의 확장 자리로 옮겨 오는 목적지다. 항목 하나를 옮길 때마다
아래 표의 "상태" 를 바꾸고, 같은 커밋에서 posco-web 쪽 코드를 지운다.
**모든 항목이 "옮김" 이 되고 골든 검사(설계 §3-3)가 통과한 뒤에만 posco-web 브랜치를 은퇴**한다.

| 포스코 항목 | posco-web 의 자리 | 옮길 자리 | 상태 |
|---|---|---|---|
| 탭 감춤(Proposals·Code) · 시작 탭 Legacy | `TopBar.vue` · `App.vue` | `frontend/index.js` shell | **자리 생김 · 코어가 읽음**(P3) |
| Proposals·헌장 감춤 | `featureVisibility.js` | `frontend/index.js` features | 값만(P5) |
| 내보내기 DOCX 만 | `ExportDocumentDialog.vue` | `deliverables.formats` / `allowed_formats` | 값만(P5) |
| 서비스설계서 파일 이름 틀 | `exportDocument/fileName.js` | `deliverables.fileNameTemplate` / `file_name_template` | 값만(P5) |
| ECM 검사 | `docx_normalize.py` | `deliverable_policies.ecm_check` | 값만(P5) |
| 생성 모델 기본값 gpt-4.1 | `llm_model_choice.default_model()` · compose | `llm_overrides.default_model` | 값만(P5) |
| 코드 템플릿 세트 poscodx | `code_templates/*` · `fetch-templates.sh` | `template_sets` | 값만(P5) |
| SWP SSO(redirect · isValidSSO · 칸 순서 · 이메일 도메인) | `auth/config.py` · `swp.py` · `router.py` · authority | `auth_providers["swp"]` + 프로필 `SWP_*` | 옮길 것(P5) |
| 표준항목 MCP(searchDataDictionary 필드 매핑) | `standard_items/mcp_provider.py` | `standard_item_providers` + 프로필 `ROBO_STANDARD_MCP_URL` | 옮길 것(P5) |
| P-GPT 게이트웨이 | `ai_gateway.py` · `llm.py` | 프로필 `PGPT_*`(코어 LLM 덮어쓰기 자리) | 옮길 것(P5) |
| analyzer 가격표 · capabilities | `deploy/posco-web/analyzer-llm/*.yaml` | `profile/` | 옮길 것(P5) |
| Claude 터미널 끔 | web 이미지 `VITE_DISABLE_CLAUDE_TERMINAL=1` | 판(web) 기본값 — 고객 무관 | 판 정리(P6) |
| tiktoken 사전 · 서버 배포 스크립트 · healthcheck · SELinux `:z` | `deploy/posco-web/` | `deploy/web/` — 고객 무관 | 판 정리(P6) |

고객 코드가 기본 판에 새지 않는지는 `scripts/check-customer-leaks.mjs` 가 본다(기본 빌드 번들에
`poscodx` · `swpsso` · `searchDataDictionary` · `설계_` 가 0개여야 한다).
