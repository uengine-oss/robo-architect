# Stories 탭 — 통합 검증 (초안)

> 다음 세션이 이어서 진행할 수 있도록 만든 **인벤토리·시나리오 초안**. 결과는 모두 ⬜(미실행).
> 진행 방식은 [proposals.md](proposals.md) 참고(스펙+코드 인벤토리 → 시나리오 → 라이브 검증 → 이슈 기록).

- **activeTab 값**: `Stories` (구 `Requirements`)
- **패널 컴포넌트**: [`RequirementsPanel.vue`](../../../frontend/src/features/requirements/ui/RequirementsPanel.vue) (026)
- **프런트 store**: [`requirements.store.js`](../../../frontend/src/features/requirements/requirements.store.js)
- **백엔드**: [`api/features/requirements/routes/`](../../../api/features/requirements/routes/) + [`requirementsIngestion`](../../../api/features/) (인제스천)
- **관련 스펙**: 001(인제스천 SSE) · 008(US 플래닝 에이전트) · 019(US 속성 패널) · 026(Requirements 탭) · 030(명확화 에이전트) · 031(생성 언어 정책) · 033(편집 이력) · 034(Epic/Feature 단위·하위 US 생성·DDD 검증) · 035(DDD 발견 마법사)
- **상태**: ⬜ 미시작 (초안)

## 1. 탭의 의도/목표 (스펙 요약)

요구사항을 **Epic → Feature → UserStory** 계층으로 등록·조회·편집하는 파이프라인 **입구**. 자연어/문서를 **인제스천(SSE 진행 스트리밍)**으로 받아 트리화하고, **AI 플래닝**으로 Feature·하위 US를 생성하며, **명확화 에이전트**로 underspecified 항목을 보완하고, **DDD 적합성 검증**·**편집 이력**·**삭제 이력**을 제공한다. 이후 Design/Process/Data 탭이 이 요구사항을 전제로 동작.

> 주의: `Changes`(038, CHG-NNN) 관련 컴포넌트(`ChangesPanel`/`ChangeDetail` 등)는 **별도 탭(숨김)** 이므로 Stories 검증 범위에서 제외.

## 2. 보유 기능 목록 (코드 대조 초안)

| # | 기능 | 출처 스펙 | 컴포넌트 | 엔드포인트/액션 |
|---|---|---|---|---|
| 1 | Epic→Feature→US 트리 탐색·선택 | 026,034 | `RequirementsTree`, `EpicDetail`/`FeatureDetail`/`UserStoryDetail` | `fetchTree` |
| 2 | 요구사항 추가(자연어 → 인제스천) | 001 | `AddRequirementDialog` | 인제스천 SSE |
| 3 | 문서 업로드(인제스천 모달, 진행 스트리밍) | 001 | `RequirementsIngestionModal` | 인제스천 SSE |
| 4 | DDD 발견 마법사 | 035 | `DddWizardPanel` | `ddd_wizard` |
| 5 | 요구사항 명확화 — 전체/스코프(project/BC/Feature) | 030 | `ClarificationPanel`, `ClarityRadar`, `ClarificationSummary` | `fetchClarificationSession/Summary/Flags`, `fetchClarityScores`, `fetchClarificationLog` |
| 6 | 명확화 — UserStory 단위(상세 탭 내) | 030 | `UserStoryDetail`(명확화 탭) | clarification |
| 7 | Epic 생성/수정 | 034 | `EpicEditForm`, `EpicDetail` | `createEpic`, `updateEpic` |
| 8 | Feature 생성/수정 | 034 | `FeatureEditForm`, `FeatureDetail` | `createFeature`, `updateFeature` |
| 9 | Epic→Feature 자동 생성(각 Feature=spec.md) | 034 | `GeneratedFeaturesReview`, `FeatureGenStream` | `generateFeatures` |
| 10 | 하위 UserStory 자동 생성 | 008,034(US5) | `GeneratedStoriesReview` | `generateChildStories(scope, engine)` |
| 11 | UserStory 상세·속성 편집(통합 패널) | 019 | `UserStoryDetail` | `updateUserStory(fields, baseUpdatedAt)` |
| 12 | DDD 적합성 검증 | 034(US6) | `ValidationFindings` | `validateRequirement` |
| 13 | 편집 이력(직접 수정 추적) | 033 | `EditHistoryPanel` | `fetchItemHistory`, `fetchHistory` |
| 14 | 챗 편집(자연어 수정) + 로그 | — | `ChatEditPanel` | `chat_edit`, `fetchChatEditLog` |
| 15 | 삭제(US/Feature/Epic) + 디자인 동반 처리 옵션 | 034 | `DeleteConfirmDialog` | `deleteUserStory/Feature/Epic(removeDesign/disposition)` |
| 16 | 삭제 이력 | 034 | `DeletionHistoryPanel` | `fetchDeletionRecords` |
| 17 | 설계 미반영 US 식별 → 반영 요청 | 034(US7) | `DesignReflectPrompt`(App.vue) | `fetchPendingDesign`, `requestDesignForUserStories` |
| 18 | 설계 궤적(US→설계요소 trace) | 012,034 | `DesignTraceCanvas` | `fetchDesignTrace` |
| 19 | 임팩트 리포트 | — | `ImpactReportPanel` | `impact_report` |
| 20 | BC/Aggregate 캔버스 탭(상세 내) | — | `BcCanvasTab`, `AggregateCanvasTab` | `fetchBcCanvas` |
| 21 | 생성 출력 언어 정책 | 031 | (생성 경로 공통) | LLM 언어 정책 |
| 22 | 전체 요구사항 데이터 삭제 | 026 | `RequirementsPanel` 툴바 | reset/clear |

> store ↔ 백엔드 라우트 1:1 대조는 **다음 세션에서 확정**(proposals 방식). 위 매핑은 컴포넌트 import·store 함수·스펙 기준 초안.

## 3. 검증 시나리오 (설계 — 다음 세션 실행)

> 전제: 백엔드/프런트 기동(`./dev.sh`), LLM·`CLAUDE_CODE_PATH` 설정. **인제스천이 핵심 입구라 빈 그래프에서 시작 가능**(다른 탭과 달리 Stories는 시드 불필요).

### S1. 트리 로드·탐색·빈 상태
- Stories 탭 진입 → Epic/Feature/US 트리 렌더, 빈 그래프면 빈 상태. 노드 선택 시 상세(Epic/Feature/US Detail) 표시. → ⬜

### S2. 요구사항 추가(자연어 인제스천)
- "+ 요구사항 추가" → 자연어 입력 → **인제스천 SSE 진행**(phase 스트리밍) → 완료 시 트리에 Epic/Feature/US 반영. → ⬜

### S3. 문서 업로드 인제스천
- "문서 업로드" → 파일 → 인제스천 모달 진행률 → 트리 반영. (017/018 토큰·서스펜드·배치 영속 포함 확인) → ⬜

### S4. Epic→Feature 자동 생성
- Epic 선택 → "Feature 자동 생성" → `FeatureGenStream` 진행 → `GeneratedFeaturesReview`로 후보 검토·반영. → ⬜

### S5. 하위 UserStory 자동 생성
- Feature/Epic 스코프 → "하위 US 생성" → `GeneratedStoriesReview` 후보 → 반영. (008 플래닝 에이전트) → ⬜

### S6. UserStory 속성 편집(019)
- US 선택 → 속성 패널에서 필드 편집·저장(`updateUserStory`, `baseUpdatedAt` 낙관적 잠금) → 반영·충돌 처리. → ⬜

### S7. 편집 이력(033)
- 직접 편집 후 `EditHistoryPanel`에 이력 표시(`fetchItemHistory`/`fetchHistory`). → ⬜

### S8. 챗 편집
- `ChatEditPanel`에서 자연어 수정 → 적용 → 로그(`fetchChatEditLog`). → ⬜

### S9. 요구사항 명확화(030)
- "🔍 요구사항 명확화(전체)" → 세션 시작 → 트리 배지(flags) + `ClarityRadar` 점수. US 단위 명확화(상세 탭)도 확인. → ⬜

### S10. DDD 적합성 검증(034 US6)
- "DDD 검증" → `validateRequirement` → `ValidationFindings` 결과. → ⬜

### S11. DDD 발견 마법사(035)
- "🧭 DDD 마법사" → `DddWizardPanel` 인터뷰 → 도메인 캔버스 산출. → ⬜

### S12. 삭제 + 디자인 동반 + 삭제 이력
- US/Feature/Epic 삭제(`removeDesign`/disposition 옵션) → `DeletionHistoryPanel` 기록. → ⬜

### S13. 설계 미반영 US 반영(034 US7)
- Design/Process 탭 진입 시 `DesignReflectPrompt`(미반영 US 감지) → "반영" → `requestDesignForUserStories` 인제스천 진행. (App.vue 오케스트레이션) → ⬜

### S14. 생성 언어 정책(031)
- 생성(Feature/US/명확화) 출력 언어가 정책대로(한국어 등) 나오는지. → ⬜

### S15. 설계 궤적·임팩트·캔버스 탭
- US 상세에서 `DesignTraceCanvas`(설계 궤적), `ImpactReportPanel`, `BcCanvasTab`/`AggregateCanvasTab` 동작. → ⬜

## 4. 발견 이슈

| # | 심각도 | 증상 | 원인(추정) | 후속 |
|---|---|---|---|---|

## 5. 결론

- (초안) 다음 세션에서 §2 인벤토리를 store↔라우트로 확정하고 S1~S15 라이브 검증.
- **핵심 회귀 위험**: S2/S3 인제스천(파이프라인 입구, 017/018 토큰·배치 포함), S4/S5 AI 생성(008/034), S9 명확화(030), S13 설계 반영(034 US7 — 인제스천 재사용).
- 횡단 확인: 031 언어 정책은 모든 생성 경로에서.
