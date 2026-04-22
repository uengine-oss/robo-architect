# Hybrid Phase 5 — Event Storming 승격 (B 구조: 기존 ingestion workflow 재사용)

> 문서 작성일: 2026-04-16 · 2차 개정 (B 구조 채택) · 3차 개정 2026-04-20 (Phase 2.5/2.6 태그 consume 경로 추가)
> 상위 문서: `Hybrid_Ingestion_Architecture.md` (Phase 1~4 완성된 BPM 입력 — BC·역할 태그 포함), `Analyzed_Code_ingestion.md §4.5` (스코프 분석)
> **핵심 결정**: Phase 5 는 별도 모듈로 작성하지 **않고**, `analyzer_graph` 가 ingestion workflow 에 통합된 패턴을 그대로 차용한다 — `source_type="hybrid"` 분기로 들어가 기존 phases (Event/BC/Aggregate/Command/ReadModel/Policy/Property/GWT/UI Wireframe) 1700+ 줄을 100% 재사용.
> **변경 사항 (2026-04-20)**: Phase 2.5 (`Rule.context_cluster`) + Phase 2.6 (`Rule.es_role`) 태그가 도입되어, 아래 downstream phase 들이 **태그를 primary input 으로 소비하도록 개선**하면 §9.1 BC=1 collapse / Policy=0 한계가 자연 해소. 아직 재실행 전 — 자세한 경로는 §11 참조.

---

## 0. 핵심 결정 한눈에

| 항목 | 값 |
|---|---|
| 트리거 | 캔버스 상단 "이벤트 스토밍" 탭 → "모델 생성" 버튼 → `POST /api/ingest/hybrid/{hsid}/promote-to-es` |
| 진입 패턴 | **`analyzer_graph` 와 동형** — `source_type="hybrid"` 로 새 IngestionSession 생성 후 `run_ingestion_workflow` 호출 |
| US 도출 | `(BpmTask × source_function 클러스터)` = 1 UserStory. DF 컷오프(>50% Task 매핑 fn 제외) + Top-1 attribution(같은 fn 의 다중-Task 매핑은 confidence 합 max 인 Task 로 통합) |
| 그 다음 단계 | Event/BC/Aggregate/Command/ReadModel/Property/References/Policy/GWT/UI 모두 **기존 ingestion phase 그대로** |
| 후처리 (hybrid 전용) | workflow 종료 직후 `hybrid_post_workflow_hook`: ES 노드 session_id 태깅 + `(BpmTask)→[:PROMOTED_TO]→(UserStory)` 부착 + orphan US fallback + Cross-BC Policy 자동 탐지 |
| 역추적 | `UserStory.sourceUnitId = BpmTask.id` (기존 analyzer_graph 와 동일 필드) + `(BpmTask)-[:PROMOTED_TO]->(UserStory)` 엣지 |
| 멱등성 | 모든 ES 노드에 `session_id = hsid` 태깅. `clear_promoted_nodes(hsid)` 가 wipe |

---

## 1. 트리거 흐름

```
[BPMN 탭 / Phase 1~4 완성]
         │
         ▼
[이벤트 스토밍 탭 진입] → "모델 생성" 버튼
         │
         ▼
POST /api/ingest/hybrid/{hsid}/promote-to-es
         │  ── 새 IngestionSession 생성
         │     · source_type = "hybrid"
         │     · hybrid_source_session_id = hsid
         │     · content = ""  (downstream phases 가 ctx.content 안 봄)
         ▼
응답: { ingestion_session_id }
         │
         ▼
프론트 → GET /api/ingest/stream/{ingestion_session_id}  (기존 SSE 라우트 그대로)
         │
         ▼
run_ingestion_workflow(session, "")
         │
         ├─ Phase 1 parsing (hybrid 메시지)
         ├─ Phase 2 user_stories ─┬─ source_type=="hybrid" 분기
         │                        │   build_grouped_unit_contexts_from_bpm(hsid)
         │                        │   → grouped_contexts: [(task_name, [task_id], context_text), ...]
         │                        │   → per group: extract_user_stories_from_bpm_group()
         │                        │   → us.sourceUnitId = task_id (역추적)
         │                        └─ normalize_and_dedup → ctx.user_stories
         ├─ Phase 3 user_story_sequencing  (기존 그대로)
         ├─ Phase 4 events_from_user_stories
         ├─ Phase 5 bounded_contexts
         ├─ Phase 6 aggregates
         ├─ Phase 7 commands
         ├─ Phase 8 readmodels
         ├─ Phase 10~14 properties / refs / policies / gwt / ui_wireframes
         │
         ▼
[hybrid 전용 후처리 hook]
         · _tag_es_nodes_with_session_id(hsid)        → 모든 ES 노드에 session_id 부착
         · _attach_promoted_to_bridges(hsid)          → (BpmTask)→[:PROMOTED_TO]→(UserStory)
         · _attach_orphan_us_to_first_bc(hsid)        → BC LLM 이 매핑 누락한 US 안전망
         · _create_cross_bc_policies(hsid)            → BpmTask.NEXT 흐름에서 BC 다른 인접쌍 → Policy LLM
         ▼
[완료]
```

---

## 2. (Task × fn_cluster) → UserStory 매핑 (5.A 부분만 hybrid-specific)

### 2.1 입력 (Phase 1~4 산출물)

- `BpmTask` (id, name, description, sequence_index, source_section, source_page, conditions, actor_ids)
- `Rule` (id, given, when, then, source_function, source_module)
- `(BpmTask)-[:REALIZED_BY {confidence}]->(Rule)`
- `(BpmActor)-[:PERFORMS]->(BpmTask)`
- `(Rule)-[:EVALUATES {direction}]->(ExternalTable)`

### 2.2 전처리 — 두 단계 dedup

**(a) DF 컷오프** — `_FN_DF_THRESHOLD = 0.5` (env: `HYBRID_ES_FN_DF_THRESHOLD`)
- fn 이 전체 Task 의 50% 이상에 매핑되면 **전역 제외**
- 실데이터: `zapamcom10060` (4/7 = 57%) 제외, `b000_main_proc` (3/7 = 43%) 통과

**(b) Top-1 Attribution** — 같은 fn 이 여러 Task 에 매핑되면 confidence 합이 가장 높은 Task 1개로 통합
- `b000_main_proc` 14 Rule → "입력값 검증" Task 1개로 몰림

→ 90 REALIZED_BY → 약 60 edges 로 축소. UserStory 도출 시 중복 제거됨.

### 2.3 그룹 단위 = 하나의 BpmTask

- `build_grouped_unit_contexts_from_bpm(hsid)` 가 `[(task_name, [task_id], context_text), ...]` 반환
  - 한 그룹 = 하나의 BpmTask (fn 클러스터 모두 한 context 안에 표시)
  - `analyzer_graph.build_grouped_unit_contexts()` 와 정확히 같은 시그니처 → workflow 가 동일 코드 경로로 처리
- context_text 는 Task 헤더 + 각 fn 의 BL[N] 묶음 + GUIDELINES

### 2.4 LLM 호출 (Task 1개 = 1회)

`extract_user_stories_from_bpm_group(context)` (sync, `asyncio.to_thread` 로 호출)
- 시스템 프롬프트: "fn 묶음 단위 = 1 UserStory" 가이드
- 출력: `UserStoryList` (기존 `event_storming` 의 pydantic 스키마)
- 반환된 모든 US 에 `source_unit_id = primary_unit_id (=task_id)` 부착

**예상 카운트** (실데이터 7 Task / 52 Rule): ~9~12 UserStory.

---

## 3. 기존 phases 가 변경 없이 그대로 동작하는 이유

기존 ingestion 의 모든 downstream phase (`events_from_user_stories.py`, `bounded_contexts.py`, `aggregates.py`, `commands.py`, `readmodels.py`, `policies.py` 등) 는 `ctx.user_stories` / `ctx.events` / `ctx.bcs` 등 **ctx 에 채워진 데이터만 사용**한다 (확인 완료: `ctx.content` 직접 참조 없음). hybrid 도 ctx.user_stories 만 채우면 그 후는 동일하게 처리됨.

→ **변경 0 줄**: `events_from_user_stories.py`, `bounded_contexts.py`, `aggregates.py`, `commands.py`, `readmodels.py`, `policies.py`, `properties.py`, `references.py`, `gwt.py`, `ui_wireframes.py`.

---

## 4. Hybrid 전용 후처리 hook (`hybrid_post_workflow_hook`)

`ingestion_workflow_runner.py:259-269` 에서 `if source_type == "hybrid":` 분기 추가, workflow 완료 직후 호출.

### 4.1 책임

1. **ES 노드 session_id 태깅** — 모든 신규 ES 노드 (UserStory/BC/Aggregate/Command/Event/Policy/ReadModel/CQRSConfig/CQRSOperation) 에 `session_id = hsid` 부착. 기존 ingestion 산출물(`session_id` 없음)과 분리.
2. **PROMOTED_TO 부착** — `MATCH (us:UserStory) WHERE us.sourceUnitId = t.id MERGE (t)-[:PROMOTED_TO]->(us)`.
3. **Orphan US 안전망** — BC LLM 이 user_story_ids 를 빈 리스트로 반환했을 때 `(UserStory)-[:IMPLEMENTS]->(BC)` 엣지가 누락됨. 이 경우 첫 BC (key 알파벳순) 에 강제 부착해서 Event Modeling 뷰어에서 사라지지 않도록.
4. **Cross-BC Policy 자동 탐지** — `BpmTask.NEXT` 엣지에서 인접한 두 Task 가 서로 다른 BC 에 속하면, "Event(BC1) → TRIGGERS → Policy → INVOKES → Command(BC2)" 패턴 생성. LLM 1회로 Policy 명명.

### 4.2 IMPLEMENTS 방향 주의

기존 event_storming 컨벤션: `(UserStory)-[:IMPLEMENTS]->(BoundedContext)` (US → BC). hybrid 측 모든 쿼리도 이 방향에 맞춤.

### 4.3 sourceUnitId (camelCase) 주의

Neo4j 에는 `sourceUnitId` (camelCase) 로 저장됨 — `event_storming/neo4j_ops/user_stories.py` 의 MERGE 쿼리. snake_case 로 검색하면 매칭 0.

---

## 5. 신규 / 수정 파일

### 5.1 신규
- `api/features/ingestion/hybrid/bpm_context_builder.py`
  - `build_grouped_unit_contexts_from_bpm(hsid)` — `analyzer_graph.build_grouped_unit_contexts` 와 동형 시그니처
  - `_dedup_task_fn_mapping` — DF 컷오프 + Top-1 attribution
  - `fetch_task_metadata_for_bpm(hsid)` — cross-BC 탐지용 NEXT 메타
- `api/features/ingestion/hybrid/bpm_to_user_stories.py`
  - `extract_user_stories_from_bpm_group(context)` — `graph_to_user_stories` 와 동형
  - `HYBRID_BPM_SYSTEM_PROMPT` (fn 묶음 단위 = 1 US 가이드)
- `api/features/ingestion/hybrid/event_storming_bridge/promote_to_es.py` (재작성)
  - `hybrid_post_workflow_hook(hsid)` — async generator (4단계 후처리)
  - `clear_promoted_nodes(hsid)`, `ALL_PROMOTED_LABELS` (router 가 reset 시 사용)
  - `_create_cross_bc_policies` — BpmTask.NEXT 기반 cross-BC pair 탐지 + LLM 명명

### 5.2 수정
- `api/features/ingestion/ingestion_sessions.py` — `source_type` 주석에 "hybrid" 추가, `hybrid_source_session_id: Optional[str]` 필드
- `api/features/ingestion/workflow/phases/parsing.py` — hybrid 메시지 분기
- `api/features/ingestion/workflow/phases/user_stories.py` — `source_type=="hybrid"` 분기 추가 (analyzer_graph 분기 직전)
- `api/features/ingestion/ingestion_workflow_runner.py` — workflow 종료 직전 hybrid hook 호출
- `api/features/ingestion/hybrid/router.py`
  - `POST /api/ingest/hybrid/{hsid}/promote-to-es` — IngestionSession 생성 후 ingestion_session_id 반환
  - `DELETE /api/ingest/hybrid/{hsid}/promote-to-es` — 해당 hsid 의 ES 노드 wipe
- `api/features/ingestion/hybrid/ontology/neo4j_ops.py` — `fetch_session_snapshot` 응답에 `promoted` 카운트 필드 추가

### 5.3 폐기 (이전 1차 시도)
- `event_storming_bridge/userstory_extractor.py`
- `event_storming_bridge/event_extractor.py`
- `event_storming_bridge/bc_identifier.py`
- `event_storming_bridge/aggregate_extractor.py`
- `event_storming_bridge/command_extractor.py`
- `event_storming_bridge/readmodel_extractor.py`
- `event_storming_bridge/policy_extractor.py`
- `event_storming_bridge/persistence.py`
- `event_storming_bridge/structured_outputs.py`
- `event_storming_bridge/prompts.py`

→ 1500+ 줄 자체 구현을 폐기하고 200줄 글루로 통합.

---

## 6. API

### 6.1 트리거
```
POST /api/ingest/hybrid/{hsid}/promote-to-es
  → 200 { ingestion_session_id, hybrid_source_session_id }
  → 400 if BPM (BpmTask) not found for hsid
```

### 6.2 SSE 진행 (기존 라우트 재사용)
```
GET /api/ingest/stream/{ingestion_session_id}
  → ProgressEvent 스트림 (parsing → user_stories → ... → ui_wireframes → hybrid hook → complete)
```

### 6.3 Promotion wipe (재실행 전)
```
DELETE /api/ingest/hybrid/{hsid}/promote-to-es
  → { success: true, deleted: { UserStory: N, BoundedContext: N, ... } }
```

### 6.4 Snapshot (콜드 로드)
```
GET /api/ingest/hybrid/session/{hsid}/snapshot
  → { ..., promoted: { user_stories: N, events: N, bounded_contexts: N, aggregates: N, commands: N, readmodels: N, policies: N, policies_cross_bc: N } }
```

`promoted.user_stories > 0` 이면 프론트는 "이미 승격됨" → Event Modeling 뷰어 바로 마운트, 0 이면 "모델 생성" 버튼.

---

## 7. SSE 이벤트 추가분 (hybrid hook)

기존 ingestion SSE 이벤트에 다음이 추가됨:

| Type | 단계 | payload |
|---|---|---|
| `HybridTaggingStart` | hook 시작 | — |
| `HybridTagged` | hook 1단계 | `{ tagged: { UserStory: N, ... } }` |
| `HybridPromotedBridges` | hook 2단계 | `{ edge_count: N }` |
| `HybridOrphanUsBackfilled` | hook 3단계 (orphan 발견 시만) | `{ edge_count: N }` |
| `HybridCrossBcPolicies` | hook 4단계 | `{ policies: [{key, name, kind, trigger_event, invoke_command, from_bc, to_bc}, ...] }` |

---

## 8. 환경 변수

| Name | Default | Purpose |
|---|---|---|
| `HYBRID_ES_FN_DF_THRESHOLD` | `0.5` | fn 이 이 비율 이상 Task 에 매핑되면 노이즈로 제외 |

(다른 ES 관련 환경 변수는 기존 ingestion 의 것을 그대로 활용)

---

## 9. 알려진 한계 / 후속 개선

### 9.1 BC 가 1개로만 묶이는 경우 (실데이터 검증 시 발생)
기존 ingestion 의 BC LLM 이 hybrid US 9개를 모두 한 BoundedContext (`PaymentAuthorization`) 로 묶음. cross-BC Policy 가 자연스럽게 0개.

**원인**: hybrid US 가 모두 비슷한 도메인 (결제 인증) 이라 LLM 이 분리 못 함. 입력 rule 에 도메인 태그가 없어 LLM 이 유일한 판단 근거였음.

**해결 기반 마련 (2026-04-20)**: Phase 2.5 (`context_cluster`) + 2.6 (`es_role`) 도입으로 각 Rule 이 사전 분류됨. §11 의 경로대로 Phase 5.A (BC 식별) 가 `distinct(context_cluster)` 를 seed 로 받으면 BC 2~3개, Policy 4~5개 확보 예상. 구현은 `workflow/phases/bounded_contexts.py` 에 `source_type=="hybrid"` 분기 추가 + 태그 소비 로직.

**즉시 우회 방법** (§11 구현 전): BC Rules Modal (Architecture §6.5) 에서 사용자가 수동으로 rule 을 재분배하거나 `es_role` 을 조정하면 Phase 5 가 다음 실행 때 더 나은 결과를 낸다.

### 9.2 BC LLM 이 user_story_ids 를 누락하는 경우
fix 됨 — `_attach_orphan_us_to_first_bc` fallback 으로 안전망. 단, 의미 있는 분류가 아닌 임시 부착이라 BC LLM prompt 개선이 본질적 해결.

### 9.3 Event Modeling 뷰어가 session_id 필터를 안 함
`/api/graph/event-modeling` 라우트가 라벨로만 조회 → hybrid-tagged 노드와 기존 ingestion 노드가 혼재 노출 가능. 동시 사용 시 오염. 단일 세션 가정에서는 문제 없음.

후속: 뷰어 라우트에 `?session_id={hsid}` optional 필터 파라미터 추가.

---

## 10. 검증

```bash
# 1. BPM 완료 후
curl -X POST http://localhost:8000/api/ingest/hybrid/{hsid}/promote-to-es
# → { ingestion_session_id: "abc12345" }

# 2. SSE
curl -N http://localhost:8000/api/ingest/stream/abc12345

# 3. Neo4j 결과
MATCH (n) WHERE n.session_id = $hsid
RETURN labels(n)[0] AS label, count(n) AS c ORDER BY c DESC

# 4. Cross-BC Policy
MATCH (e:Event)-[:TRIGGERS]->(p:Policy {kind:'cross_bc', session_id:$hsid})-[:INVOKES]->(c:Command)
RETURN p.name, e.name, c.name

# 5. 멱등성
curl -X DELETE http://localhost:8000/api/ingest/hybrid/{hsid}/promote-to-es
curl -X POST   http://localhost:8000/api/ingest/hybrid/{hsid}/promote-to-es
# → 결과 노드 카운트 동일
```

### 10.1 실데이터 검증 결과 (7 Task / 52 Rule)

| 측정 | 값 |
|---|---|
| User Story | 9 |
| Event | (기존 ingestion phase 가 생성) |
| BoundedContext | **1** (LLM 도메인 분류 한계 — §9.1) |
| Aggregate | **8** ⭐ |
| Command | **9** + EMITS edges |
| ReadModel | 8 |
| Policy | 0 (BC가 1개라 LLM이 자동 트리거 패턴 미식별) |
| BpmTask → US PROMOTED_TO | **9 edges** ⭐ (역추적 정상) |
| Cross-BC Policy | 0 (BC가 1개라 자연스러운 결과) |

PROMOTED_TO 부착 + 역추적 + Aggregate 풍부 — 핵심 Phase 5 책임은 모두 동작. BC 분류 개선만 §9.1 후속.

> **주의**: 위 실측은 Phase 2.5 (`context_cluster`) / 2.6 (`es_role`) 도입 **이전** 결과. 새 태그 기반 재실행을 수행하지 않은 상태. 재실행 경로는 §11 참조.

---

## 11. Phase 2.5/2.6 태그 소비 경로 (재설계, 2026-04-20)

> Phase 2.5 (BC 태깅) + Phase 2.6 (역할 태깅) + 부모 노드 탐색이 완료된 후, 기존 Phase 5 의 LLM-heavy 경로를 **결정론 + LLM 이름 확정** 으로 재편. BC=1 collapse / Policy=0 을 근본 해소.

### 11.1 태그가 Phase 5 도달 시점의 보증

각 `Rule` 노드는 Phase 5 입력 시점에 이미 아래 속성을 보유 (rehydrate 시 snapshot 에도 포함):

| 필드 | 출처 | 의미 |
|---|---|---|
| `context_cluster` | Phase 2.5 | 도메인 범주 (8 클러스터 예시) |
| `es_role` | Phase 2.6 | ES 승격 대상 (aggregate/validation/policy/query/external) |
| `es_role_confidence` | Phase 2.6 | 1.0 이면 사용자 수동 확정 |
| `title` | Phase 2 | BL.title (의미적 신호 최고) |

### 11.2 Phase 별 재설계 (hybrid 분기 추가)

| 서브단계 | 기존 (pre-tag) | 재설계 (tag-aware) | LLM 호출 변화 |
|---|---|---|---|
| **5.A BoundedContext** | 전체 Task+Rule raw LLM 판단 → 1개로 collapse | `distinct(r.context_cluster)` 8개를 seed 로 "2~3 BC 로 묶어라" | 1회 유지 (입력 품질↑) |
| **5.B Aggregate** | Table WRITES 기반 휴리스틱 + LLM 이름 | `es_role='aggregate'` Rule 을 `source_function` + WRITES Table 공유로 결정론 group, LLM 은 이름만 | Context 당 1회 → **LLM 생략 가능** |
| **5.C Command** | Task × Aggregate LLM 배치 | `es_role='validation'` Rule 을 gating Command 로 묶어 배치 | 배치 1회 (변함) |
| **5.D Policy** | 모든 Rule 50+ 중 LLM 이 policy 패턴 탐색 | `es_role='policy'` Rule 만 source_function 별 group → 계열당 1 Policy | 계열당 1회 — 노이즈 급감 |
| **5.E ReadModel** | 선택 | `es_role='query'` Rule + READS Table → 결정론 | **LLM 생략 가능** |
| **5.F UserStory** | Task × fn_cluster 기반 (현행) | 변경 없음 | 변경 없음 |

**예상 LLM 호출량**: 현행 ~20회 → 재설계 후 ~8회 (~60% 감소)

**예상 산출물 변화**: BC 1 → 2~3 · Policy 0 → 4~5 · 나머지 동등 또는 개선

### 11.3 manual override 존중

사용자가 BL Inspector / BC Rules Modal 로 수동 조작한 매핑은 아래 흔적으로 식별:

| 속성 | 의미 |
|---|---|
| `REALIZED_BY.method = 'manual'` | 사용자 직접 assign/move |
| `REALIZED_BY.reviewed = true` | 사용자 승인 또는 수동 연결 |
| `Rule.es_role_confidence = 1.0` | 사용자 역할 변경 |

Phase 5 는 이 흔적이 있는 Rule 을 **재분석 없이 선언적 소스** 로 채택. 휴리스틱 재실행해도 manual 결과를 덮어쓰지 않음.

### 11.4 미매핑 / Review Queue 잔존 Rule 의 처리

- **미매핑 Rule (REALIZED_BY 없음)**: Phase 5 승격 **제외**. "잉여 business logic" 으로 보고서에 별도 기록만.
- **Review Queue (ActivityMapping without edge)**: 같은 규칙. 사용자가 명시 승인 안 하면 비결정적 제안 상태로 간주.

통합 "미매핑 / Review" 풀(Architecture §6.2) 에서 사용자가 수동 정리 후 재실행해야 반영.

### 11.5 재실행 멱등성

- 모든 Phase 5 쓰기는 `MERGE` + `session_id` 태그 → 재실행 시 중복 생성 없이 덮어쓰기
- Phase 2.5 LLM naming 은 비결정적 (cluster 이름) 이지만, cluster *멤버십* 자체는 결정론 → 이름만 달라질 수 있음
- manual override 는 항상 우선

### 11.6 구현 체크리스트 (다음 PR)

- [ ] `workflow/phases/bounded_contexts.py` — hybrid 분기 + `context_cluster` seed 기반 prompt
- [ ] `workflow/phases/aggregates.py` — hybrid 분기 + `es_role='aggregate'` 필터링 + 결정론 grouping
- [ ] `workflow/phases/policies.py` — hybrid 분기 + `es_role='policy'` 필터링
- [ ] `workflow/phases/readmodels.py` — hybrid 분기 + `es_role='query'` 필터링
- [ ] `workflow/phases/commands.py` — `es_role='validation'` Rule 을 Command precondition 에 주입
- [ ] 재실행 1회 + §10.1 표 재측정하여 "BC ≥ 2, Policy ≥ 1" 확인
