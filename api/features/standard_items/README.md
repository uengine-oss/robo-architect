# 표준 항목(데이터 사전) — 설계 단계에 붙이기

## 어디에

속성 생성 단계 `generate_properties_phase`(`api/features/ingestion/workflow/phases/properties.py`)가
LLM 결과 행을 `upsert_properties_bulk` 로 저장하기 **직전**에 `annotate_property_rows(rows)` 를 부른다.
애그리거트 묶음·ReadModel 묶음 두 곳. 저장은 `neo4j_ops/properties.py` 가 표준 칸이 있는 행만
따로 한 번 더 쓴다(공급원이 꺼져 있으면 그 쿼리는 돌지 않고, 예전 값도 그대로다).

## 어떤 모양으로

```
StandardItemProvider.search(keyword) -> StandardLookup(items, source, checked_at, error)
   └ McpDataDictionaryProvider   POSCO 표준항목 MCP (포스코망)  ← 지금
   └ (그룹사망) KS 철강 표준 LLM 검색 공급원                     ← 나중에 같은 자리
```

공급원 고르기는 `annotate.get_standard_provider()` 한 곳. 지금은 `ROBO_STANDARD_MCP_URL` 이 있으면 MCP.

## 맞추는 규칙 (`matching.py`)

| 경우 | `standardMatch` | 표준 칸 |
|---|---|---|
| 이름(빈칸 무시)이 정확히 같은 것 1건 + 사용 중 | `matched` | 채운다 |
| 같은 것 여럿 · 같지만 사용 중 아님 · 비슷한 것만 | `candidates` | 비움, `standardCandidates` 에 `이름\|ID\|상태` |
| 0건 | `not_found` | 비움 |
| 연결 실패 · 시간 초과 | `unverified` | 비움, `standardNote` 에 이유 |

조회 키워드는 `displayName`(한글). 빈칸을 뺀 꼴(`주문 번호` → `주문번호`)을 먼저 묻는다.
"사용 중" 판정은 `is_active_status` 한 곳 — 기본 목록은 상수, `.env` `ROBO_STANDARD_ACTIVE_STATUSES` 로 덮는다.

## Property 노드에 생기는 칸

`standardMatch` `standardId` `standardName` `standardValueType` `standardDataLength`
`standardDecimalLength` `standardCodeItem` `standardCandidates` `standardNote` `standardSource` `standardCheckedAt`
— 신규 라벨·관계 없음.

## 미룬 것 — 화면 · 서비스설계서

- 속성 패널(Data 탭 `AggregatePanel` 의 속성 행)에 배지: `matched` = 표준ID, `candidates` = "후보 N",
  `unverified` = "표준 미확인". 후보를 골라 확정하는 동작은 사람 몫(지어내지 않는다).
- 서비스설계서(deliverables) 데이터 항목 표에 표준항목ID · 값유형 · 자리수 · 소수 · 코드항목 · 출처 열.
- 속성을 읽는 API 는 `Property` 노드 칸을 그대로 내므로 읽기 쪽은 칸 추가만으로 닿는다 — 확인 필요.
- 하이브리드(A2A→ES) 경로 등 `upsert_properties_bulk` 를 다른 곳에서 부르는 경로는 아직 붙이지 않았다.
