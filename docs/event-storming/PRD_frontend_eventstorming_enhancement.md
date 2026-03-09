# Frontend PRD: EventStorming Generate Chain 대용량 요구사항 처리 & 채팅 UI를 통한 Element Modification

## 개요

기업과 조직의 분석가 및 설계자로서, 생성되는 EventStorming의 각 요소들이 필요한 구성요소를 모두 갖추고, 검증된 정보들을 포함했으면 한다. 이를 통해 각 비지니스 흐름에 정합성을 부여하고 Human in the loop를 통해 사용자가 개입하여도 모델에 반영되는 워크플로우로 반복 작업을 감소 시키고, 전체 시스템의 흐름 파악을 용이하게 하고, 설계 품질을 향상시킬 수 있다.

## 참고 문서

- [EventStorming Enhancement PRD](mdc:docs/PRD_event_storming_enhancement.md): Backend 대용량 요구사항 처리 전략
- [Model Modifier Architecture](mdc:docs/MODEL_MODIFIER_ARCHITECTURE.md): 채팅 기반 모델 수정 아키텍처
- [Chunking Strategy](mdc:docs/CHUNKING_STRATEGY.md): 대용량 요구사항 청킹 전략
- [Frontend PRD](mdc:docs/PRD_frontend.md): 기존 Frontend UI 컨셉

## DoD (Definition of Done)

### [ ] Human in the loop 안정화

#### [ ] Chat을 통한 Modifier의 영향도 분석 결과의 "상세보기" 정보 정리 및 가시성 개선

**현재 상태:**
- `ImpactDetailsModal.vue`에서 영향도 분석 상세 정보를 표시
- K-hop 그래프, Properties, UserStory 영향도 조회 기능 존재
- 정보가 많을 경우 가독성 저하 가능

**개선 방향:**
1. **영향도 요약 정보 개선**
   - `ChatPanel.vue`의 영향도 요약 섹션에 더 상세한 정보 표시
   - Propagation confirmed/review 노드 타입별 분류 표시
   - 영향받는 노드의 BC 컨텍스트 표시

2. **ImpactDetailsModal 정보 구조화**
   - Hop별 노드 그룹화 개선 (현재 구현됨)
   - 노드 선택 시 상세 정보 표시 개선
   - Properties/REFERENCES 정보 가독성 향상
   - UserStory 영향도 조회 결과 시각화 개선

3. **필요한 파일:**
   - `frontend/src/features/modelModifier/ui/ChatPanel.vue`: 영향도 요약 UI 개선
   - `frontend/src/features/modelModifier/ui/ImpactDetailsModal.vue`: 상세 정보 구조화 및 가시성 개선
   - `frontend/src/features/modelModifier/modelModifier.store.js`: 영향도 데이터 구조 개선

**구현 내용:**
- [ ] ChatPanel의 영향도 요약에 노드 타입별 카운트 추가 (Command: 5, Event: 3, Policy: 2 등)
- [ ] ImpactDetailsModal에서 노드 선택 시 BC 컨텍스트 명확히 표시
- [ ] Properties/REFERENCES 정보를 테이블 형태로 개선
- [ ] UserStory 영향도 조회 결과를 그래프 형태로 시각화
- [ ] 영향도 분석 결과 로딩 상태 개선 (스켈레톤 UI)

#### [ ] 생성 중, 일시중단 및 피드백을 통해 수정 기능 검증 및 보완

**현재 상태:**
- `RequirementsIngestionModal.vue`에서 생성 진행 중 일시정지 기능 존재
- `ChatPanel.vue`에서 일시정지 상태에서 수정 요청 가능
- 생성 중 수정 요청 시 제한 있음

**개선 방향:**
1. **생성 중 수정 요청 처리 개선**
   - 생성 진행 중에도 수정 요청 가능하도록 개선 (현재는 일시정지 후에만 가능)
   - 생성 중 수정 요청 시 충돌 감지 및 해결 UI
   - 생성 완료 후 수정 사항 자동 반영 확인

2. **일시정지 상태 UI 개선**
   - 일시정지 상태에서 수정 요청 가능 여부 명확히 표시
   - 생성 진행 상태와 수정 요청 상태 분리 표시
   - 일시정지 후 재개 시 수정 사항 반영 확인

3. **필요한 파일:**
   - `frontend/src/features/requirementsIngestion/ui/RequirementsIngestionModal.vue`: 일시정지 UI 개선
   - `frontend/src/features/modelModifier/ui/ChatPanel.vue`: 생성 중 수정 요청 처리 개선
   - `frontend/src/features/modelModifier/modelModifier.store.js`: 상태 관리 개선
   - `frontend/src/features/requirementsIngestion/ingestion.store.js`: 생성 상태 관리 개선

**구현 내용:**
- [ ] 생성 중 수정 요청 시 경고 메시지 표시 및 확인 절차 추가
- [ ] 일시정지 상태에서 수정 요청 가능 여부를 UI에 명확히 표시
- [ ] 생성 완료 후 수정 사항 자동 반영 확인 다이얼로그
- [ ] 생성 진행 상태와 수정 요청 상태를 분리하여 표시
- [ ] 충돌 감지 시 해결 UI 제공

---

### [ ] UI 가시성 개선

#### [ ] Model Explorer의 요소가 많은 경우, 로딩이 더디거나 깨지는 오류 수정

**현재 상태:**
- `navigator.store.js`에서 BC 트리 구조 로딩
- 대용량 그래프(300+ 노드)에서 로딩 성능 저하 가능
- Vue Flow 캔버스에서 많은 노드 렌더링 시 성능 저하

**개선 방향:**
1. **Model Explorer 로딩 최적화**
   - 가상 스크롤링 적용 (현재 트리 구조에)
   - 지연 로딩 (Lazy Loading): 트리 노드 확장 시 하위 노드 로드
   - 로딩 상태 표시 개선 (스켈레톤 UI)

2. **캔버스 렌더링 최적화**
   - Vue Flow의 `minZoom`, `maxZoom` 설정
   - 노드 가시성 최적화 (화면 밖 노드 렌더링 제외)
   - 대용량 그래프에서 초기 로딩 시 필터링 옵션 제공

3. **필요한 파일:**
   - `frontend/src/features/navigator/navigator.store.js`: 로딩 최적화
   - `frontend/src/features/canvas/canvas.store.js`: 캔버스 렌더링 최적화
   - `frontend/src/features/canvas/ui/CanvasWorkspace.vue`: 가시성 최적화

**구현 내용:**
- [ ] Model Explorer에 가상 스크롤링 적용
- [ ] 트리 노드 확장 시 지연 로딩 구현
- [ ] 로딩 상태 스켈레톤 UI 추가
- [ ] Vue Flow 캔버스에서 노드 가시성 최적화
- [ ] 대용량 그래프 초기 로딩 시 필터링 옵션 제공
- [ ] 로딩 성능 모니터링 및 에러 핸들링 개선

#### [ ] Outbound가 존재하지 않는 Event의 visible option 추가

**현재 상태:**
- `EventNode.vue`에서 outbound policy count를 API로 조회
- Outbound가 없는 Event의 경우 시각적 표시 부족
- Canvas에서 Event의 outbound 관계 가시성 부족

**개선 방향:**
1. **Event Node 시각화 개선**
   - Outbound가 없는 Event에 대한 시각적 표시 추가
   - Event Node에 "no outbound" 상태 표시 옵션
   - Canvas에서 Event의 outbound 관계 명확히 표시

2. **필터링 옵션 추가**
   - Canvas에서 outbound가 없는 Event만 필터링하여 표시
   - Model Explorer에서 outbound가 없는 Event 표시 옵션

3. **필요한 파일:**
   - `frontend/src/features/canvas/ui/nodes/EventNode.vue`: outbound 상태 시각화 개선
   - `frontend/src/features/canvas/canvas.store.js`: 필터링 옵션 추가
   - `frontend/src/features/navigator/navigator.store.js`: Explorer 필터링 옵션

**구현 내용:**
- [ ] EventNode에 outbound가 없는 경우 시각적 표시 추가 (예: 회색 테두리, 아이콘)
- [ ] Canvas 필터에서 "outbound 없는 Event" 옵션 추가
- [ ] Model Explorer에서 outbound가 없는 Event 표시 옵션 추가
- [ ] Event Node 툴팁에 outbound 상태 정보 표시
- [ ] API 응답 실패 시 fallback 처리 개선

---

### [ ] 텍스트를 기반으로 직접 입력해서 대용량 생성요청 진행 시, proxy 자체에서 걸리는 request 오류 확인

**현재 상태:**
- `RequirementsIngestionModal.vue`에서 텍스트 직접 입력 지원
- `api/features/ingestion/router.py`의 `/api/ingest/upload` 엔드포인트에서 텍스트 처리
- Starlette의 FormData 기본 제한(1024KB)으로 인한 대용량 텍스트 처리 제한

**개선 방향:**
1. **프론트엔드 대용량 텍스트 처리**
   - 텍스트 입력 크기 제한 사전 검증
   - 대용량 텍스트 입력 시 파일 업로드 권장 메시지 표시
   - 텍스트 크기 실시간 표시

2. **에러 핸들링 개선**
   - Proxy/서버 타임아웃 에러 명확한 메시지 표시
   - 대용량 텍스트 입력 시 자동으로 파일 업로드로 전환 제안
   - 요청 실패 시 재시도 옵션 제공

3. **필요한 파일:**
   - `frontend/src/features/requirementsIngestion/ui/RequirementsIngestionModal.vue`: 대용량 텍스트 처리 개선
   - `frontend/src/features/requirementsIngestion/ingestion.store.js`: 에러 핸들링 개선

**구현 내용:**
- [ ] 텍스트 입력 크기 실시간 표시 (예: "1,234 / 1,024 KB")
- [ ] 1024KB 초과 시 경고 메시지 및 파일 업로드 권장
- [ ] Proxy/서버 타임아웃 에러 명확한 메시지 표시
- [ ] 대용량 텍스트 입력 시 자동으로 파일 업로드로 전환 제안
- [ ] 요청 실패 시 재시도 옵션 제공
- [ ] 요청 진행 상태 표시 개선 (업로드 진행률)

---

## 기술적 고려사항

### 성능 최적화
- Vue 3의 `v-memo` 디렉티브 활용 (리스트 렌더링 최적화)
- 가상 스크롤링 라이브러리 검토 (vue-virtual-scroller 등)
- Vue Flow의 노드 가시성 최적화 옵션 활용

### 에러 핸들링
- 네트워크 에러, 타임아웃 에러 구분 처리
- 사용자 친화적인 에러 메시지 제공
- 에러 발생 시 복구 옵션 제공

### 접근성
- 키보드 네비게이션 지원
- 스크린 리더 지원
- 색상 대비 개선

---

## 참고 구현

### Backend 관련
- `api/features/ingestion/router.py`: 텍스트 업로드 처리
- `api/features/model_modifier/routes/chat_modify.py`: 수정 요청 처리
- `api/features/model_modifier/routes/chat_impact_details.py`: 영향도 상세 조회

### Frontend 관련
- `frontend/src/features/modelModifier/ui/ChatPanel.vue`: 채팅 UI
- `frontend/src/features/modelModifier/ui/ImpactDetailsModal.vue`: 영향도 상세 모달
- `frontend/src/features/requirementsIngestion/ui/RequirementsIngestionModal.vue`: 요구사항 업로드 모달
- `frontend/src/features/navigator/navigator.store.js`: Model Explorer 상태 관리
- `frontend/src/features/canvas/canvas.store.js`: Canvas 상태 관리

---

## 우선순위

1. **High**: Human in the loop 안정화 (영향도 분석 상세보기 개선)
2. **High**: UI 가시성 개선 (Model Explorer 로딩 최적화)
3. **Medium**: Outbound가 없는 Event visible option 추가
4. **Medium**: 대용량 텍스트 입력 처리 개선
5. **Low**: 생성 중 수정 기능 검증 및 보완 (현재 일시정지 후 수정 가능하므로)
