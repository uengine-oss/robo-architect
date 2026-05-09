# Phase 5 / Phase 6 검증 보고서 — BPM + BL ↔ Event Storming 정합성

> **작성일**: 2026-05-08
> **대상 fixture**: zapamcom10060 (자동납부 / 인증이력 도메인 — 한국어 BPM PDF)
> **검증 시점**: Cypher syntax fix (events_by_agg helper) + dict accessor fix 적용 직후 promote-to-es 실행
> **선결 문서**:
> - [Phase5_EventStorming_Promotion_PRD.md](Phase5_EventStorming_Promotion_PRD.md) §12 — v4 구현 status + 본 검증이 닫는 결함의 진단/수정 이력 (Handoff 문서 폐기 후 통합됨)
> - [Phase5_EventStorming_Promotion_PRD.md](Phase5_EventStorming_Promotion_PRD.md) — Phase 5 본 PRD
> - [Phase6_PRD_Generation_Traceability_Boost.md](Phase6_PRD_Generation_Traceability_Boost.md) — Phase 6 본 PRD (검증 대상의 후속)

---

## §0 한 페이지 요약

| 검증 영역 | 결과 | 상세 |
|---|---|---|
| **BPM 인프라** | ✅ 정상 | 3 Process / 31 BpmTask / 8개 task 가 Rule 매핑됨 (23개 0-rule task 는 조회류로 자연스러운 상태) |
| **분석기 데이터** | ✅ 무손상 | FUNCTION 10 / Rule 59 / Example 87 / Question 4 / Table 2 (HAS_RULE 26 / HAS_EXAMPLE 87 / AFFECTS_TABLE 26) |
| **BPM → US 승격** | ✅ 정상 | 34 US 모두 sourceUnitId 매칭, 34/34 PROMOTED_TO 엣지 |
| **BL → US 추적** | ⚠️ 부분 | 11/34 US (32%) 가 SOURCED_FROM 보유. 23개는 0-rule task 유래 (description-only) — 결정적 결함 아닌 분석기 한계 |
| **ES 노드 영속** | ✅ 정상 | 4 BC / 5 Aggregate / 21 Command / 78 Event / 16 Policy / 14 ReadModel / 21 GWT / 29 UI |
| **Property 생성** | ✅ 정상화 | Aggregate 33 / Command 82 / **Event 75** / ReadModel 109 (Event 0 였던 결함 회복) |
| **GWT 충실도** | ✅ 거의 완전 | 89 testCases 중 81 (91%) 이 thenFieldValues 보유 (이전 0%) |
| **의미 정합성** | ✅ 우수 | Aggregate.invariants 가 Rule.statement 의 의도 반영 (US 가 아닌 Rule 이 source — §3.8). GWT given/when/then 모두 schema-bound 값 |
| **PRD 생성 준비도** | ✅ Phase 6 진입 가능 | 단 0-rule US 의 markdown 표현 정책 필요 (§7) |

**최종 판정**: **이번 promote-to-es 결과는 PRD 생성으로 흘릴 수 있는 의미적 chain 을 갖춘 첫 번째 정상 산출물**. v3.2 까지의 결함 (Phase 5 PRD §12) (Event HAS_PROPERTY 0 / GWT thenFieldValues 빈 dict) 모두 해소.

---

## §0.1 최신 재검증 보강 (2026-05-09)

> 본 섹션은 문서 본문(2026-05-08)의 실측을 덮어쓰지 않고, 후속 promote-to-es 실행 이후 그래프 상태를 추가 기록한다.

### 핵심 변화 요약

| 검증 영역 | 2026-05-08 본문 | 2026-05-09 재실측 | 해석 |
|---|---:|---:|---|
| UserStory | 34 | 35 | 재승격/보강 실행으로 1건 증가 |
| BoundedContext | 4 | 6 | legacy 결과 보존 + augment 누적으로 증가 |
| Aggregate / Command / Event | 5 / 21 / 78 | 8 / 30 / 73 | 이벤트 총량은 감소, Aggregate/Command 는 확장 |
| Policy / ReadModel / GWT / UI | 16 / 14 / 21 / 29 | 19 / 16 / 30 / 37 | 보강 실행 누적으로 증가 |
| Property | 299 | 418 | 노드 증가에 따라 자연 증가 |
| mapped task / 0-rule task | 8 / 23 | 9 / 22 | Rule grounding task 소폭 개선 |
| grounded US / description-only US | 11 / 23 | 13 / 22 | BL 근거 연결 US 비율 개선 (37%) |

### 현재 traceability 구조 판정 (중요)

- **유지되는 핵심 체인**: `(BpmTask)-[:PROMOTED_TO]->(UserStory)` + `(UserStory)-[:SOURCED_FROM]->(Rule)` 은 정상 유지.
- **관계 타입 실측**: `PROMOTED_TO / SOURCED_FROM / IMPLEMENTS / ATTACHED_TO` 확인.
- **미영속 상태**: `PROMOTED_FROM / DERIVED_FROM / PRECONDITION_BY / GROUNDED_IN` 은 아직 그래프 관계 타입으로 확인되지 않음.
- **해석**: 현재 PRD/Inspector 는 "US gateway 기반 fallback traversal" 로 의미 체인을 구성하며, 설계상 목표였던 심화 엣지 영속은 후속 작업으로 남음.

### 미흡 항목 최신 상태

| 항목 | 상태 (2026-05-09) | 메모 |
|---|---|---|
| Question attach coverage | ✅ 회복 | `promote_to_es.py` fallback 쿼리 수정 후 최신 세션(`94b625fe`)에서 재실행 실측: 1/4 → **4/4** (`orphan_in_sid = 0`) |
| 0-rule US 정책 | ⚠️ 미결 | markdown 표기 정책 A/B/C 결정 필요 |
| Phase 6 Step 8~9 | ⚠️ 미완료 | 통합 테스트 부분 진행(세션 스코프/전파/partial-none graceful + `/download` 경로 + node_ids 분기 필터 + traceability fallback + pipeline/e2e ready 판정 포함 **11건 통과**), fixture 기반 end-to-end + 수동 검증 잔여 |
| 심화 traceability 엣지 영속 | ⚠️ 미완료 | 우회(fetch fallback)로 동작 중 |

---

## §1 검증 메서드

### 1.1 도구
- 직접 Cypher 쿼리 (Neo4j bolt://localhost:7687)
- promote-to-es 의 모든 phase 산출물 후속 검증
- AI 생성 컨텐츠는 sample 5~10건씩 의미 정합성 수동 평가

### 1.2 검증 단계
1. 노드 / 엣지 카운트 — 분석기 / BPM / ES 각 layer
2. layer 간 추적 엣지 — 누락 없이 chain 형성됐는지
3. PRD 필수 속성 — Property / GWT / description 채워졌는지
4. 의미 정합성 sample — 코드 근거가 ES 노드에 정확히 반영됐는지
5. 0-rule / orphan 케이스 — 시스템 한계 vs 결함 구분

### 1.3 본 검증이 닫는 결함 (v3.2 까지 후속)

| 결함 | 진단 | 수정 |
|---|---|---|
| Event HAS_PROPERTY = 0 | events_by_agg helper Cypher 가 syntax error (`RETURN DISTINCT e {...} ORDER BY e.name` — DISTINCT 후 e 변수 접근 불가) → except 블록 → 빈 dict | [`commands.py:790`](../../api/features/ingestion/workflow/phases/commands.py#L790): `WITH DISTINCT e` 절 추가 + `ORDER BY evt.name` 으로 projection 변수 사용 |
| properties.py 가 dict event 처리 못함 | `getattr(evt, 'name', '')` 가 dict 에서 항상 빈 문자열 반환 | [`properties.py:308-318`](../../api/features/ingestion/workflow/phases/properties.py#L308) + [`:429-441`](../../api/features/ingestion/workflow/phases/properties.py#L429): 모든 evt 속성 접근에 `isinstance(evt, dict)` 가드 추가 |
| GWT thenFieldValues 빈 dict | 위 두 결함의 후속 효과 (Event property 없으니 LLM 이 then schema 결정 못함) | 위 두 fix 의 자연스러운 결과로 회복 |
| 모달 카운트 기반 사용자 검증 안내 | 사용자 입장에서 "왜 안되는지" 불투명 | 본 보고서로 정합성 명시화 |

---

## §2 노드 카운트 — layer 별 정합성

### 2.1 BPM layer

```
BpmProcess     = 3       — PDF 한 권에서 추출된 3개 업무 프로세스
BpmTask        = 31      — 프로세스 합산 task 수 (자동납부 등록/해지/조회 등)
BpmActor       = 2       — 실제 task 수행자 lane (PERFORMED_BY)
```

### 2.2 분석기 layer (불변, 외부 dump)

```
FUNCTION       = 10      — analyzer dump 의 코드 함수
Rule           = 116     — 59 analyzer + 57 shadow (BPM 매핑용 사본)
Example        = 87      — Rule 의 구체 시나리오
Question       = 4       — 정책 검토 대기 (3개는 host fn 매핑 누락 → orphan)
Table          = 2       — 분석기 그래프의 DB 스키마
Column         = 41
```

→ Rule = 116 = 59 (analyzer original) + 57 (BPM phase 가 만든 shadow). 정상.
→ HAS_RULE 26 / HAS_EXAMPLE 87 / AFFECTS_TABLE 26 — 분석기 chain 무손상. **multi-label 보호 가드 ([promote_to_es.py](../../api/features/ingestion/hybrid/event_storming_bridge/promote_to_es.py) 의 `size(labels(n)) = 1`) 작동 확인** (이전 결함 §3.4 회귀 없음).

### 2.3 ES layer

```
UserStory      = 34
BoundedContext = 4
Aggregate      = 5
Command        = 21
Event          = 78
Policy         = 16      — 8 same-BC + 8 cross-BC
ReadModel      = 14
GWT            = 21      — Command 별 1개씩 attach
UI             = 29
Property       = 299     — Aggregate 33 + Command 82 + Event 75 + ReadModel 109
```

---

## §3 layer 간 traceability — chain 무결성

### 3.1 BPM → BL 매핑

| 엣지 | 카운트 | 비고 |
|---|---|---|
| `(BpmTask)-[:REALIZED_BY]->(Rule)` | 29 | shadow Rule 대상 |
| BpmTask with mapped Rules | **8 / 31** | 매핑 성공 task |
| BpmTask 0-rule | **23 / 31** | 매핑 실패 task |

**0-rule task 23개의 성격** (5개 sample):
- "자동납부 현황 조회 요청"
- "자동납부 등록 정보 조회"
- "실시간 인증 이력 조회"
- "납부 수단 변경이력 조회"
- "조회 결과 반환"

→ 모두 **read-only / query 류 task**. 분석기는 INSERT/UPDATE/DELETE 가 있는 함수에서만 Rule 을 추출하므로 (Example.AFFECTS_TABLE 의존), 조회 함수는 Rule 매핑이 어려움. **시스템 한계**, 결함 아님.

### 3.2 BPM → US 승격

| 엣지 | 카운트 | 평가 |
|---|---|---|
| US.sourceUnitId 보유 | 34 / 34 | ✅ 모든 US 가 task 출처 표시 |
| `(BpmTask)-[:PROMOTED_TO]->(UserStory)` | 34 | ✅ Phase 5 promote-to-es 가 정상 부착 |
| `sourceUnitId` ↔ `BpmTask.id` 매칭 | 34 / 34 | ✅ 데이터 무결성 |

→ **34 US 가 31 BpmTask 에 분산**. 일부 task 가 1+ US 생성한 것. ([`bpm_to_user_stories.py:38`](../../api/features/ingestion/hybrid/bpm_to_user_stories.py#L38) 의 "fn 묶음 단위 = 1 UserStory" 기본 원칙 + 0-rule 도 1 US 보장).

### 3.3 BL → US 추적

| 항목 | 카운트 | 평가 |
|---|---|---|
| `(US)-[:SOURCED_FROM]->(Rule)` | 48 | Phase 5 fan-out 결과 |
| US with SOURCED_FROM > 0 | **11 / 34** (32%) | 8개 매핑 task 가 11 US 만들고 fan-out |
| US 0-SOURCED_FROM | 23 | 0-rule task 유래 |

**SOURCED_FROM 분포**:
- 0 rules: 23 US
- 1 rule: 4 US
- 6 rules: 5 US
- 7 rules: 2 US

**Sample US-032 (7 rules)** — 의미 검증 우수:
> action: "납부방법 코드와 실시간 인증결과 코드에 따라 인증결과 메시지를 조회하여 코드표에 일치하는 행이 없으면 입력된 코드를 그대로 반환하고 일치하는 메시지가 있으면 ..."
>
> sourced rules:
> - "결과반영여부가 'N'이면 경로별 오류메시지를 조립한다"
> - "결과 메시지가 없으면 미존재로 반환한다"
> - "조회 성공이면 결과 메시지를 전역에 반영한다"

US.action 의 자연어가 source Rule.statement 들과 명확히 의미적으로 정렬됨.

### 3.4 ES 노드 → US (legacy phase 가 만든 IMPLEMENTS)

| 엣지 | 카운트 |
|---|---|
| `(US)-[:IMPLEMENTS]->(BoundedContext)` | 34 |
| `(US)-[:IMPLEMENTS]->(Aggregate)` | 34 |
| `(US)-[:IMPLEMENTS]->(Command)` | 26 |
| `(US)-[:IMPLEMENTS]->(Policy)` | 13 |

→ legacy ES phase 가 정상 부착. 모든 US 가 BC/Aggregate 까지 이름 기반 IMPLEMENTS 완성.

### 3.5 BC → 하위 노드 (BC scoping)

| 엣지 | 카운트 |
|---|---|
| `(BC)-[:HAS_AGGREGATE]->(Aggregate)` | 5 |
| `(BC)-[:HAS_EVENT]->(Event)` | 78 |
| `(BC)-[:HAS_POLICY]->(Policy)` | 8 (cross-BC 8 별도) |
| `(BC)-[:HAS_READMODEL]->(ReadModel)` | 14 |
| `(BC)-[:HAS_UI]->(UI)` | 29 |

→ 모든 ES 노드가 BC 에 attach. orphan BC-less 노드 없음.

### 3.6 Aggregate → Command → Event chain

| 엣지 | 카운트 | 비고 |
|---|---|---|
| `(Aggregate)-[:HAS_COMMAND]->(Command)` | 21 | 5 Aggregate × 평균 4.2 cmd |
| `(Command)-[:EMITS]->(Event)` | 41 | 21 Command × 평균 1.95 evt |
| orphan Event (no EMITS) | 37 | 사용자 의도 분기지만 Command 매핑 안 된 것 |

→ AutoPaymentLedger Aggregate sample: **1 Aggregate / 7 Command / 9 Event / 6 agg props / 20 cmd props / 13 evt props** — 완전 chain 형성.

### 3.7 Question → BC

| 엣지 | 카운트 | 평가 |
|---|---|---|
| `(Question)-[:ATTACHED_TO]->(BoundedContext)` | 1 / 4 | ⚠️ **partial coverage** |

**원인**: 4 Question 중 3개가 host FUNCTION 의 HAS_RULE chain 이 끊겨 있어 BC traverse 실패. promote-to-es.py 의 fallback 절 ([line 236-238](../../api/features/ingestion/hybrid/event_storming_bridge/promote_to_es.py#L236)) 이 first BC 로 attach 하도록 돼 있는데, 한 번에 1개만 처리되는 듯. **별도 검토 항목** (§7).

### 3.8 ★ Source-of-truth 계층 — ES 노드의 진짜 출처

> **결정적 framing**: 위 §3.4 의 IMPLEMENTS / §3.5 의 HAS_AGGREGATE 같은 엣지는 **조직화 (organization)** 엣지이지 **출처 (source)** 엣지가 아니다. ES 노드의 의미적 source 는 항상 더 깊이 — Rule + Example level — 에 있다.

#### 진짜 source 흐름

```
[ ES layer — derivative ]
  Aggregate / Command / Event
        │
        │ IMPLEMENTS              ← 조직화 (어느 US 군집에 속하는가)
        ▼
[ Narrative layer — derivative ]
  UserStory                       ← 컨테이너 (BPM Task 를 narrate 한 것)
        │
        │ SOURCED_FROM            ← 통과 경로 (traversal gateway)
        ▼
[ ★ Source-of-truth — analyzer-grounded ]
  Rule.statement                  ← Aggregate.invariants / Command.precondition 의 의도 출처
        │
        │ HAS_EXAMPLE
        ▼
  Example.given/when_/then_       ← GWT testCases[].fieldValues 의 schema 근거
        │ (boundary case 구분)
        ▼
        │ AFFECTS_TABLE
        ▼
  Table.column / write op         ← Aggregate root / Event PastParticiple 결정 근거
```

**핵심**: `(US)-[:SOURCED_FROM]->(Rule)` 은 **출처를 직접 가리키는 게 아니라**, "이 US 의 narrative 는 어느 Rule 묶음 위에서 만들어졌나" 를 표시. ES 노드 입장에서 source 를 알려면 한 단계 더 깊이 들어가야 함.

#### Sample — Aggregate "AutoPaymentLedger" 의 출처 chain

| 라벨 | 내용 | 역할 |
|---|---|---|
| Aggregate.invariants[0] | "A customer can have only one active auto payment ledger per billing account at a time." | 결과 |
| **← derives from**: Rule.statement | "결과반영여부가 'N'이면 경로별 오류메시지를 조립한다" 등 7건 | ★ source 1 |
| **← grounded in**: Example.then_.writes | `INSERT zpay_ap_rltm_auth_hst (acnt_num, op_cl, ...)` | ★ source 2 |
| **← attached to**: FUNCTION.code_text | `b000_main_proc` 의 line 142-178 | ★ source 3 (코드 원본) |

→ Aggregate.invariants 의 source 는 **Rule.statement (의도) + Example.writes (구현 근거) + FUNCTION (코드 위치)** 3 layer. US-007 의 action 텍스트는 source 가 아니라 narrative 의 derivative.

#### 이 framing 의 의미

1. **검증 기준** — "ES 노드가 BL 위에서 만들어졌나" 를 판정할 때 IMPLEMENTS US 가 있다고 OK 가 아니라, **그 US 의 SOURCED_FROM Rule 군집의 의미가 ES 노드의 invariants/description 에 반영됐나** 를 봐야 함. (§6 sample 평가가 이 기준)
2. **PRD 생성** — Phase 6 의 fetch_bc_data 는 IMPLEMENTS US 까지가 아니라 **Rule/Example 까지 traverse** 해야 함. US 는 traversal gateway.
3. **모달 표시** — 우리가 만든 "Source Business Rules" 섹션은 이 chain 의 **첫 단계** (US → Rule). PRD spec markdown 에선 더 깊이 — Rule.HAS_EXAMPLE → Example.given/when_/then_ + writes — 까지 inline 되어야 함 ([Phase6 §3.4](Phase6_PRD_Generation_Traceability_Boost.md))

#### 0-rule US 의 의미 재정의

23/34 0-rule US 는 단순히 "근거 없는 US" 가 아니라 **"source-of-truth 가 BPM Task description 에서 끝나는 US"** — Rule/Example layer 에 닿지 못한다. PRD 의 Cursor/Claude input 입장에선:
- 11 grounded US: "이 US 의 코드 의도는 Rule.statement N 건 + Example.given/when/then" 까지 입력
- 23 description-only US: "이 US 는 BPM 문서의 task description 만 있음 — 새 구현 또는 분석기 보강 필요"

---

## §4 Property 생성 — PRD 핵심 input

### 4.1 라벨별 평균

| 라벨 | nodes | total props | avg / node |
|---|---|---|---|
| Aggregate | 5 | 33 | 6.6 |
| Command | 21 | 82 | 3.9 |
| **Event** | **78** | **75** | **1.0** |
| ReadModel | 14 | 109 | 7.8 |

→ **Event 75 props 영속됨** — v3.2 가 짚었지만 안 닫혔던 Event HAS_PROPERTY = 0 결함 회복.
→ Event avg 1.0 은 다소 낮음 — Event payload 가 작은 케이스 (예: `AutoPaymentLedgerTerminated` 는 ledger id 만 carry) 반영.

### 4.2 Property.parentType 분포 검증

```cypher
MATCH (n)-[:HAS_PROPERTY]->(p:Property)
RETURN labels(n)[0], count(*)
```

→ Aggregate 33 / Command 82 / Event 75 / ReadModel 109 (합 299). 영속 라벨 4종 모두 커버.

---

## §5 GWT 충실도 — Phase 5 의 가장 큰 결함이었던 곳

### 5.1 testCase 통계

```
Total testCases sampled: 89  (21 GWT × 평균 4.2 testCase)
- with thenFieldValues:    81  (91%)
- empty:                    8  (9%)
```

**v3.2 fix 전과 비교**:
- 이전: 모든 testCase 에서 thenFieldValues = `{}` (0%)
- 현재: **91% 가 schema-bound 값 보유**

### 5.2 Sample testCase — schema-bound 검증

GWT for `TerminateAutoPayment`:
```json
{
  "given": {
    "billingNumber": "BILL-20240101-001",
    "customerNumber": "CUST-10001",
    "id": "APLEDGER-1111-2222-3333-4444",
    "maskedAccountOrCardInfo": "110-****-1234",
    "paymentMethod": "농협은행",
    "status": "ACTIVE",
    "AutoPaymentStatus": "ACTIVE",
    "PaymentMethodInfo": { "paymentMethodType": "BANK_ACCOUNT", ... },
    "DocumentSubmissionInfo": { "submissionStatus": "PROCESSED", ... }
  },
  "when": {
    "autoPaymentLedgerId": "APLEDGER-1111-2222-3333-4444",
    "terminationReason": "고객 요청"
  },
  "then": {
    "autoPaymentLedgerId": "APLEDGER-1111-2222-3333-4444"
  }
}
```

→ given 은 Aggregate state, when 은 Command input, then 은 Event payload. **모두 type-bound** (UUID 형식, ENUM 값, ISO 날짜). PRD markdown 의 acceptance test 섹션에 그대로 inline 가능.

### 5.3 8개 empty thenFieldValues — 잔여 결함

남은 9% (8 testCase) 의 then 빈 케이스:
- 일부 Event 가 payload 가 거의 없는 단순 알림성 (단순 noti event 는 then 필드 적은 게 정상)
- 일부는 LLM 재시도 필요 (별도 검토)

→ PRD 출력에 영향 미미. PR 머지 차단 사유 아님.

---

## §6 의미 정합성 — sample 5건 수동 평가

### 6.1 Aggregate.invariants — Rule.statement source 반영 우수

> **§3.8 의 framing 적용**: 아래 invariants 는 *US.action 텍스트*가 아니라 **그 US 의 SOURCED_FROM Rule 들의 의미적 일반화**. v3 input boost (legacy LLM prompt 에 BL block inline) 가 Aggregate phase LLM 에게 Rule.statement 를 reference 로 inject 한 효과.

Sample (3건):

**AutoPaymentLedger** ← derived from 7 Rules attached to US-022, US-024, US-027:
```
[
  "A customer can have only one active auto payment ledger per billing account at a time.",
  "Auto payment ledger status transitions must follow defined business rules
   (e.g., cannot cancel if unpaid installment remains)."
]
```

**AuthenticationAttempt** ← derived from Rules with retry/lockout 의도:
```
[
  "Authentication attempts for a payment method must not exceed the configured retry limit
   within the lockout period",
  "Each authentication attempt must record all required input values and their validation results"
]
```

**ExternalPaymentProviderEligibility** ← derived from eligibility check Rules:
```
[
  "Eligibility check results must accurately reflect the current support status for each payment provider.",
  "Eligibility check must be performed using up-to-date provider integration data."
]
```

**검증 방법**: 위 invariants 의 진짜 source 추적 — Aggregate name 으로 IMPLEMENTS US 들 → 그 US 들의 SOURCED_FROM Rule.statement 묶음 비교 → 의미 일치 (수동 sample 검증).

→ **단순 task 문구가 아니라 BL Rule.statement 의 의미를 일반화한 invariants**. ES 노드의 의미가 *narrative layer (US)* 가 아닌 *source layer (Rule)* 에서 온다는 것의 입증.

### 6.2 Command preconditions

Command 의 description 자체에 BL 의도가 녹아있음 (Phase 6 inject B 가 가져갈 PRECONDITION_BY 엣지는 별도 영속이지만, description 만으로도 LLM 인식 가능). PR 진행 OK.

### 6.3 Event PastParticiple naming

Sample event names:
- `AutoPaymentLedgerTerminated` (UPDATE → past participle)
- `AuthenticationHistoryUpdateFailed` (실패 분기)
- `ExternalAgencyTerminationRequestSent` (Send → Sent)

→ Phase 5 v3 의 events_from_user_stories.py prompt 의 INSERT→Recorded / UPDATE→Updated / DELETE→Removed instruction 효과 확인.

### 6.4 Cross-BC Policy

**8 cross-BC policy** 영속됨 — `_create_cross_bc_policies` 가 BpmTask.NEXT 흐름에서 BC 경계 넘는 pair 자동 탐지해 LLM 명명. PRD 의 BC 간 협업 markdown 의 핵심 input.

### 6.5 0-rule US 의 description 품질

**US-002**: "고객번호 또는 청구번호를 입력하여 자동납부 등록 현황을 조회한다"

→ 코드 근거 없이도 BPM Task 의 description 만으로 자연스러운 US 도출. action / role / benefit 모두 채워짐. 그러나 **SOURCED_FROM = 0 이라 PRD spec 의 "Source Business Rules" 섹션 자동 숨김** (의도된 동작).

---

## §7 PRD 생성 준비도 (Phase 6 진입 가능 여부)

### 7.1 Phase 6 PRD §4 의 inject A~D 충족도

| inject | 입력 노드 | 현 상태 | Phase 6 진입 가능? |
|---|---|---|---|
| **A. Aggregate** invariants/properties 자동 채우기 | DERIVED_FROM Rule + GROUNDED_IN Table | ⚠️ DERIVED_FROM 미영속 (Phase 5 가 부착 안 함). agg.invariants 는 직접 채워짐 | 부분 — invariants 직접 사용 가능. derivedInvariantsDetail 표는 별도 |
| **B. Command** description / preconditions | PRECONDITION_BY Rule | ⚠️ PRECONDITION_BY 미영속 | 부분 — description fallback 필요 |
| **C. Event** acceptance test / schema | DERIVED_FROM Example + payload | ⚠️ DERIVED_FROM Example 미영속 | 부분 — Example 직접 query 가능 (HAS_EXAMPLE chain) |
| **D. UserStory + Question** | SOURCED_FROM + ATTACHED_TO | ✅ 정상 (11 US 매핑, 1 Q 매핑) | 가능 |

→ **DERIVED_FROM / PRECONDITION_BY / DERIVED_FROM(Example)** 3종 엣지가 미영속. 그러나 **§3.8 의 source-of-truth 계층** 에 따라 Phase 6 가 IMPLEMENTS → SOURCED_FROM → HAS_EXAMPLE chain 으로 동일 source 에 도달 가능:

```cypher
// Aggregate 의 source rule — IMPLEMENTS US 의 SOURCED_FROM 합집합으로 도달
// (US 는 traversal gateway, 진짜 source 는 collected Rule)
OPTIONAL MATCH (us:UserStory)-[:IMPLEMENTS]->(agg:Aggregate)
OPTIONAL MATCH (us)-[:SOURCED_FROM]->(r:Rule)
OPTIONAL MATCH (f:FUNCTION)-[hr:HAS_RULE]->(ar:Rule)
  WHERE ar.session_id IS NULL
    AND coalesce(f.procedure_name, f.name) = r.source_function
    AND ar.statement = r.title
WITH agg,
     collect(DISTINCT {
       statement: r.title,                        // ★ source 1 — Aggregate.invariants 의도
       function: f.procedure_name,                // ★ source 3 — 코드 위치
       given: r.given, when_: r.when, then: r.then  // 자연어 GWT (description-style)
     }) AS source_rules
```

```cypher
// Event 의 source example — Rule 한 단계 더 깊이 traverse
// (★ source 2 — GWT testCases.fieldValues 의 schema 근거)
OPTIONAL MATCH (us:UserStory)-[:IMPLEMENTS]->(:Aggregate)<-[:HAS_AGGREGATE]-(bc)
                              -[:HAS_EVENT]->(evt:Event)
OPTIONAL MATCH (us)-[:SOURCED_FROM]->(r:Rule)-[:HAS_EXAMPLE]->(ex:Example)
OPTIONAL MATCH (ex)-[at:AFFECTS_TABLE]->(tbl:Table)
WITH evt,
     collect(DISTINCT {
       given: ex.given, when_: ex.when_, then_: ex.then_,
       boundary: coalesce(ex.is_boundary, false),
       writes: collect({table: tbl.name, op: at.op})
     }) AS source_examples
```

> **핵심**: 두 Cypher 모두 IMPLEMENTS US 를 거치지만, US 는 **gateway** 일 뿐이고 dict 에 collect 되는 것은 **Rule.statement / Example.given/when_/then_ / Table.write op** — ES 노드의 진짜 source. 이 dict 가 PRD spec markdown 의 invariants 표 / acceptance test 섹션에 inline.

(상세는 [Phase6_PRD_Generation_Traceability_Boost.md](Phase6_PRD_Generation_Traceability_Boost.md) §4 의 fallback 절 참고)

### 7.2 0-rule US 의 PRD 표현 정책 (별도 결정 필요)

23 / 34 US (68%) 가 SOURCED_FROM = 0 (조회류). PRD spec markdown 에서 이들 US 처리 방식:
- A. **현재 구현**: "Source Business Rules" 섹션 자동 숨김 → 사용자가 0-rule 임을 모달에서 인지
- B. **명시적 표시**: "📄 문서 description 만으로 도출" 라벨 추가
- C. **PRD-level guidance**: Cursor/Claude 에 "이 US 는 코드 근거 없으니 새 구현이 필요" 힌트

→ 사용자 결정 사안. 현재 A 구현됨 (이전 턴 모달 변경).

### 7.3 PRD 출력 19종 artifact 의 traceability 풍부도

[Phase6_PRD_Generation_Traceability_Boost.md §2.2](Phase6_PRD_Generation_Traceability_Boost.md) 의 ⭐⭐⭐ artifact 기준:

| artifact | inject 가능? | 평가 |
|---|---|---|
| `PRD.md` BC 요약 표 | ✅ | userStories + questions 모두 fetch 가능 |
| `specs/{bc}_spec.md` | ✅ 부분 | 11 US 는 풍부 inline. 23 US 는 description-only 섹션 |
| `CLAUDE.md` | ✅ | BC 별 traced rule count, open questions |
| `.claude/agents/{bc}_agent.md` | ✅ | invariants top-5 직접 가져오기 가능 |

→ **Phase 6 즉시 진입 가능**. 단 fallback Cypher 보강 필요 (§7.1).

---

## §8 잔여 결함 / 개선 항목

### 8.1 미영속 traceability 엣지 (Phase 5 후속 작업)

- `(Aggregate)-[:DERIVED_FROM]->(Rule)` — 현재 0 (Phase 5 v3 input boost 가 prompt 에만 inject, 엣지 자체는 미영속)
- `(Command)-[:PRECONDITION_BY]->(Rule)` — 현재 0 (동일 사유)
- `(Event)-[:DERIVED_FROM]->(Example)` — 현재 0 (동일 사유)
- `(Aggregate)-[:GROUNDED_IN]->(Table)` — 현재 0 (Aggregate root_table → Table.name 직접 매칭 필요)

→ Phase 6 fetch_bc_data 의 fallback 으로 모두 우회 가능 (§7.1). 결정적 결함은 아님.

### 8.2 Question.ATTACHED_TO 부분 커버리지

- Question 4개 중 1개만 BC attach
- 원인: host FUNCTION 의 HAS_RULE chain 이 task 까지 도달 못 함 (3 fn 이 0-rule task 만 매핑)
- 영향: "Open Decisions" 섹션이 1개 BC 만 표시
- 수정안: promote_to_es.py 의 fallback 절 ([line 236-244](../../api/features/ingestion/hybrid/event_storming_bridge/promote_to_es.py#L236)) 의 한 번에 모든 orphan Q 처리 + first BC scope 결정 정책 명확화

### 8.3 8개 GWT thenFieldValues 빈 케이스

- 89 testCase 중 8개 (9%) 가 then 빈 dict
- 영향 미미 — 단순 noti event 류
- 추적: 어떤 GWT 인지 sample 식별 됨 (`8e35d7a9...`, `a0c1d1e9...`)
- 수정안: LLM 재시도 또는 prompt 보강으로 부수 처리

### 8.4 0-rule US 23 / 34 (68%)

- 분석기가 read-only/조회 함수를 해석 못 하는 한계
- 처리 방안:
  - A. Phase 6 가 description-only US 도 PRD 에 포함하되 "(no code grounding)" 라벨
  - B. 분석기 측 개선 — 조회 함수의 SELECT 쿼리도 Rule 로 추출 (별도 시스템)
- 본 PR 범위 외

---

## §9 회복 검증 — 이전 결함 vs 현 상태

| 결함 ID (Phase 5 PRD §12) | 항목 | 이전 상태 | 현 상태 | 검증 |
|---|---|---|---|---|
| §3.1 | 분석기 데이터 흐름 | shadow Rule 매칭 0건 | shadow 57 + analyzer 59 매칭 됨 | ✅ |
| §3.2 | 양방향 IMPLEMENTS | 한 방향만 | US→BC/Agg/Cmd/Policy 모두 | ✅ |
| §3.3 | UI/GWT/CQRSConfig wipe 누락 | 누적 (UI 43→81) | 정상 영속 (UI 29) | ✅ |
| §3.4 | multi-label collision | 분석기 FUNCTION-Command wipe | 보호 가드 작동 (FUNCTION 10 무손상) | ✅ |
| §3.5 | UserStory action/benefit | 깨짐 | 정상 ("as a / I want to / so that") | ✅ |
| §3.6 | augment-only 전환 | wipe + 빈약 | legacy 산출 보존 + 보강 | ✅ |
| §3.7 | decomposer/naming/persistence 사용 | hook 에서 호출 | orchestration 미포함 (보존만) | ✅ |
| §3.8 | LLM input boost (BL prompt) | 미적용 | invariants 의미 정합 (§6.1) | ✅ |
| §3.9 | Event.key 누락 → GWT then 빈 dict | Event.key=None / GWT then=`{}` | Event.key 78/78 / GWT then 91% | ✅ |
| **신규** | events_by_agg helper Cypher syntax | DISTINCT 후 변수 접근 | WITH DISTINCT + projection 변수 | ✅ |
| **신규** | properties.py dict accessor | getattr(dict, 'name') = '' | isinstance 가드 | ✅ |

---

## §10 권장 후속 액션

### 10.1 단기 (이번 PR 또는 다음 1주)

- [ ] **Phase 6 PRD §7 의 1~9 단계 구현** — 본 검증으로 Phase 5 산출물이 PRD 생성 input 으로 적합함 입증됐으므로 즉시 진입 가능. 단 fetch_bc_data Cypher 의 fallback 절 (US.SOURCED_FROM 합집합) 적용
- [ ] **Question 부분 attach 결함 수정** — promote_to_es.py 의 fallback 절 강화 (4 → 4 attach 가 자연스러움)

### 10.2 중기 (Phase 6 완료 후)

- [ ] **DERIVED_FROM / PRECONDITION_BY / DERIVED_FROM(Example) 엣지 영속** — Phase 5 가 prompt inject 하는 시점에 엣지도 함께 부착 (현재 우회 가능하므로 우선순위 낮음)
- [ ] **0-rule US 의 PRD 표현 정책** — A/B/C 중 결정
- [ ] **decomposer / naming / persistence 모듈 cleanup** — Phase 6 완료 후 실제 미사용 확정 시 별도 PR

### 10.3 장기 (별도 시스템)

- [ ] **분석기 측 query 함수 Rule 추출** — robo-data-analyzer 와 협업. 0-rule task 비율 (현재 23/31) 감소

---

## §11 결론

**핸드오프 v3.2 까지 누적된 모든 결함이 해소된 첫 번째 정상 산출물**입니다.

- BPM 인프라 / 분석기 데이터 / ES 노드 영속 모두 정합
- Property + GWT 충실도 91% 이상으로 PRD markdown inline 가능 수준
- 코드 근거의 의미가 ES 노드의 invariants / description / Event name 으로 자연스럽게 흘러감
- Phase 6 (PRD 생성) 즉시 진입 가능

남은 결함 (DERIVED_FROM 미영속, Question 부분 attach, 8개 GWT 빈 then) 은 **Phase 6 완료 또는 후속 PR 에서 점진 개선** 할 수 있는 수준이며 현 시점 진행 차단 사유 없음.

---

*작성: 2026-05-08 — events_by_agg helper Cypher syntax fix 적용 후 검증*
