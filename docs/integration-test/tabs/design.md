# Design 탭 — 통합 검증 (초안)

> 본 문서는 아직 **전체 인벤토리 미완성** 상태이며, 우선 2026-06-15~17 라운드에서 Proposals 작업 중 발견·수정한 **GWT(Given-When-Then) 편집/생성 관련 Design 탭 이슈**를 기록한다(중복 수정 방지 목적). 진행 방식은 [proposals.md](proposals.md)·[stories.md](stories.md) 참고.

- **activeTab 값**: `Design`
- **패널 컴포넌트**: [`CanvasWorkspace.vue`](../../../frontend/src/features/canvas/ui/CanvasWorkspace.vue) (Command 인스펙터 = [`InspectorPanel.vue`](../../../frontend/src/features/canvas/ui/InspectorPanel.vue))
- **관련 스펙**: 002 · 003 · 004 · 005 · 027 · 035 (+ GWT는 Command 설계 산출물)
- **백엔드(GWT)**: [`canvas_graph/routes/gwt.py`](../../../api/features/canvas_graph/routes/gwt.py)
- **상태**: 🟡 초안 (GWT 이슈만 기록, 전체 인벤토리·시나리오 대기)

## 1. 탭의 의도/목표 (스펙 요약)

전략(Epic/Feature/UserStory)에서 도출된 도메인을 **전술 설계 캔버스**(Aggregate·Command·Event·Policy·ReadModel·VO·Enum)로 시각화·편집한다. Command에는 **GWT(Given-When-Then) 시나리오**가 인스펙터를 통해 부착되며, 자연어 입력으로 GWT를 생성할 수도 있다.

> 이 라운드의 수정은 모두 **Command 인스펙터의 GWT 편집/생성** 영역. Proposals 미리보기 작업 중 발견됐으나, GWT 자체는 라이브 Design 탭의 일반 기능이라 본 문서로 분리한다.

## 2. 보유 기능 목록 (이번 라운드 관련분)

| # | 기능 | 핵심 컴포넌트/엔드포인트 |
|---|---|---|
| 1 | Command 인스펙터에서 GWT 시나리오 셋(Given/When/Then) 추가·삭제·수정·저장 | `InspectorPanel.vue` (`snapshotFromNode`/`addGWTSet`/`removeGWTSet`/`dirtyFields`/`save`) |
| 2 | 자연어 → GWT 필드 자동 채움(파싱) | `InspectorPanel.vue` (`applyParsedValues`/`applyAllSections`) ← `gwt.py` `parse_gwt_nl` |

## 3. 검증 시나리오

> 라이브 구동 시 실행할 시나리오 설계(전제→조작→기대). 결과는 라이브 검증 단계에서 채움.

### S1. 기존 Command의 GWT 수정·추가·삭제 저장
- **전제(Given)**: Design 캔버스에 Command 노드 존재, GWT 시나리오 1개 이상
- **조작(When)**: 인스펙터에서 ①기존 시나리오의 Given/When/Then 필드를 in-place 수정 ②시나리오 셋 추가/삭제 → "저장"
- **기대(Then)**: 변경 시 "저장" 버튼 활성(dirty 감지), 저장 후 그래프 반영, **편집 중 캔버스 원본 노드 미오염**
- **결과**: ⬜ (D1 수정 반영 후 라이브 확인 필요)

### S2. 모호한 자연어로 GWT 생성
- **전제(Given)**: Command 인스펙터 GWT 자연어 입력창
- **조작(When)**: 구체 값 없는 모호한 문장 입력 → 생성
- **기대(Then)**: 무응답이 아니라, 추출 0건이면 카탈로그 기반 **구체화 추천 시나리오** 제시("추천 시나리오로 생성할까요? 네/아니오"), 한글 입력이면 한국어로
- **결과**: ⬜ (D2 수정 반영 후 라이브 확인 필요)

## 4. 발견 이슈

> 커밋 매핑: **D1** ← `d4da991`(시나리오 추가/삭제 dirty) + `472a6d3`(필드 in-place 수정·deepClone) · **D2** ← `472a6d3`(모호 시나리오 추천)

| # | 심각도 | 증상 | 원인 | 수정 |
|---|---|---|---|---|
| D1 | **수정됨** | ①GWT 시나리오 셋 추가/삭제 시 "저장" 버튼이 비활성(변경 미감지) ②이미 생성된 Command의 GWT 필드(Given/When/Then)를 in-place 수정해도 저장이 안 되고, 편집이 **캔버스 원본 노드를 직접 오염** | [`InspectorPanel.vue`](../../../frontend/src/features/canvas/ui/InspectorPanel.vue) `snapshotFromNode`가 `gwtSets`/given/when/then을 `node.data`와 **공유 참조**로 `form`·`initial`에 담음 → 제자리 수정·`push`/`splice`가 `initial`까지 함께 바꿔 `dirtyFields` 비교가 항상 동일(저장 비활성) + 원본 노드 직접 변경 | `deepClone()`(structuredClone, JSON 폴백) 추가. `snapshotFromNode`의 `gwtSets`/given/when/then을 deepClone으로 복제하고 `initial.value` 할당을 전부 `{...snap}`→`deepClone(snap)`으로 교체(resetToNode/save/savePreviewDesign 등 전 경로). `addGWTSet`/`removeGWTSet`을 `push`/`splice` → **새 배열 재할당**으로 변경(참조 분리 → dirty 감지) |
| D2 | **수정됨** | GWT 자연어 생성창에 모호한(구체 값 없는) 문장 입력 시 아무 필드도 안 채워지고 **피드백 없이 무응답** | [`gwt.py`](../../../api/features/canvas_graph/routes/gwt.py) `parse_gwt_nl`이 추출 결과가 비어도 빈 결과만 반환, 프런트 `applyParsedValues`도 적용 수를 반환하지 않아 "0개 적용"을 구분 못 함 | `gwt.py`: 추출이 전부 비면 `_suggest_concrete_scenario(catalog, text, request)` 1회 호출 → 카탈로그 기반 **구체화 추천 시나리오**(문장+필드값)를 LLM 생성, 응답에 `suggestion` 포함(`_SUGGEST_SYSTEM_PROMPT` + `_scenario_language_directive` — 한글 음절 있으면 한국어 강제, 실패는 non-fatal). 프런트 `applyParsedValues`/`applyAllSections`가 적용 필드 수 반환 → 적용>0이면 "N개 필드 채움", 적용=0+`suggestion` 있으면 "추천 시나리오로 생성할까요?" 패널(`acceptNlSuggestion`/`declineNlSuggestion`) |

## 5. 결론

- **이번 라운드(2026-06-15~17, ShinSeongJin2)**: Command 인스펙터 GWT 편집/생성 이슈 **2건 수정**(D1 공유참조로 인한 dirty 미감지·원본 오염, D2 모호 시나리오 무응답 → 추천 제시). 모두 Proposals 전술적 미리보기 작업 중 발견됐으나 라이브 Design 탭의 일반 GWT 기능이라 본 문서로 분리.
- **후속**: Design 탭 **전체 인벤토리·시나리오 미작성** — Aggregate/Command/Event/Policy/VO/Enum 편집, 전략→전술 연결, model_modifier 챗 등은 다음 세션에서. D1·D2 라이브 검증(S1/S2) 미실행.
