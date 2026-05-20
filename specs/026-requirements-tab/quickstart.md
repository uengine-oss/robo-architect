# Quickstart: Requirements Tab — Manual Smoke Test

전제: 백엔드 `uvicorn api.main:app --reload --host 127.0.0.1 --port 8000`, 프런트 `npm run dev`. 인제스트된 요구사항 데이터가 1건 이상 존재.

## S1. 4단계 트리 드릴다운 (US1)

1. 상단 탭 맨 앞 **Requirements** 탭을 연다.
2. 좌측 트리에 Epic(BoundedContext) 목록이 보인다.
3. Epic 하나를 펼치면 Feature → User Story → Acceptance Criteria 순으로 드릴다운된다.
4. User Story를 클릭 → 우측에 "As a {role} I want {action} so that {benefit}" 문장과 인수조건(연결 Command의 GWT)이 가독성 있게 표시.
- ✅ 기대: 4단계가 모두 펼쳐지고, US 본문·인수조건이 렌더된다.

## S2. 설계 괘적 탭 내부 캔버스 (US2)

1. Command에 연결된 User Story를 클릭.
2. 탭 내부 캔버스 영역에 command-aggregate-event-policy-command-aggregate 괘적만 로딩(2초 이내, SC-003).
3. Command 미연결 User Story를 클릭 → 캔버스가 "연결된 설계 없음" 안내.
4. 다른 User Story 클릭 → 캔버스가 새 괘적으로 교체.
- ✅ 기대: 무관 노드 제외, 괘적만 간략 렌더. 교체 정상.

## S3. 증분 업로드 — 기존 데이터 보존 (US3)

1. 현재 트리의 User Story 개수를 기록.
2. Requirements 탭 내 **문서 업로드** 버튼으로 새 문서 업로드.
3. 업로드 시작 시 기존 데이터 삭제 확인 다이얼로그가 **나타나지 않는다**.
4. 인제스트 완료 후 트리를 본다.
- ✅ 기대: 기존 User Story 100% 보존(SC-004) + 신규 US가 BC/Feature로 분류되어 추가.

## S4. 자연어 추가 — propose → confirm (US3)

1. **요구사항 추가** → 자연어 입력란에 새 요구사항 문장 입력 → propose.
2. LLM이 분해한 초안 User Story + 제안 BC/Feature가 검토 화면에 표시(아직 그래프 미반영).
3. 값을 검토·수정 후 confirm.
- ✅ 기대: confirm 후에만 트리에 신규 US 추가. propose 단계에서는 그래프 불변.

## S5. drag-n-drop 재배치 + 삭제 (US4)

1. 트리에서 User Story를 다른 Feature 노드로 드래그.
- ✅ 기대: 소속 Feature 변경·영속화. 다른 BC의 Feature로 옮기면 Epic 소속도 변경.
2. Feature 하나를 삭제 → 하위 US 처리(미분류 이동/함께 삭제) 선택 프롬프트.
- ✅ 기대: 선택대로 처리. 확인 절차 존재.

## S6. 백그라운드 영향도 분석 (US5)

1. 기존 User Story와 의도적으로 유사한 User Story를 추가(S4 절차).
2. 추가 직후 다른 작업(트리 탐색 등)을 계속한다 — 분석 대기로 막히지 않음.
3. 잠시 후 영향도 리포트 패널/배지에 중복 가능성 경고가 비차단으로 나타난다.
4. 문제 없는 User Story 추가 시 → 별도 경고 미표시.
- ✅ 기대: 작업 비차단, 중복/충돌/설계영향 findings가 사후 리포트.

## S7. 명시적 데이터 삭제 (US6)

1. Requirements 탭의 별도 **데이터 삭제** 버튼 클릭.
2. 확인 절차 후 요구사항 데이터 삭제.
- ✅ 기대: 업로드와 무관한 별도 액션으로만 전체 삭제 가능.

## 회귀 체크

- 기존 Design / Event Modeling / BPMN 탭 정상 동작(Requirements 탭은 별도 모드).
- `docs/cypher/schema/` 03·04·01·02 파일에 `Feature` 노드·`HAS_FEATURE`/`HAS_USER_STORY` 반영 확인.
- Swagger `/docs`에 `/api/requirements/*` 엔드포인트 노출 확인.
