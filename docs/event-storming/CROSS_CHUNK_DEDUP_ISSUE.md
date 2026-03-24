# 청킹 간 중복 생성 문제 및 개선 방안

## 1. 문제 정의

### 1.1 현상
같은 Phase 내에서 청킹이 발생할 경우, 이전 청크에서 생성된 요소 이름 목록을 다음 청크의 프롬프트에 주입하여 중복 생성을 방지하고 있다.
그러나 **누적된 이름 목록이 많아지면 50개 상한(`ACCUMULATED_NAMES_MAX`)에 의해 잘리며**, 51번째 이후 이름은 LLM이 볼 수 없어 중복 방어가 무력화된다.

### 1.2 전체 Phase 현황

| Phase | 반복 단위 | 이전 결과 전달 방식 | 현재 수량 | 중복 위험도 |
|:------|:---------|:-------------------|----------:|:-----------|
| **UserStory** | SB별 독립 호출 | **전달 없음** (완전 독립) | 42 | **높음** — SB 간 유사 US 중복 방어 불가 |
| **BoundedContext** | 청크별 | 리스트업 없음 | 5 | 중 — 유사 BC 병합 로직으로 대응 |
| **Aggregate** | BC별 | `existing_aggregates_text` (이름만) | 9 | 중 — BC 수에 비례 |
| **Command** | Aggregate별 | `_existing_command_names` (50 cap) | 26 | **높음** — Aggregate 수 × 평균 CMD |
| **Event** | Command에 종속 | 전달 없음 (Command별 생성) | 27 | 중 — Command 중복이 연쇄 |
| **ReadModel** | BC별 | `_existing_readmodel_names` (50 cap) | 16 | **높음** — cross-BC 동일 조회 |
| **Policy** | 청크별 | `_accumulated_policy_names` (50 cap) | 2 | 낮 — 수량 자체가 적음 |
| **GWT** | Command별 | 전달 없음 | 26 | 낮 — Command별 독립 시나리오 |
| **UI** | Command/RM별 | 전달 없음 | 38 | 낮 — 1:1 대응 생성 |
| **Property** | Aggregate별 | 전달 없음 | 472 | 낮 — 테이블 컬럼 기반 |

**가장 심각한 Phase**: UserStory — 이전 SB 결과를 아예 전달하지 않으므로, SB 간 유사한 US가 중복 생성되는 걸 막을 방법이 전혀 없다.

### 1.3 현재 방어 메커니즘

```python
# chunking.py
ACCUMULATED_NAMES_MAX = 50

def format_accumulated_names(names, max_items=50):
    if len(names) <= max_items:
        return ", ".join(names)
    shown = ", ".join(names[:max_items])
    return f"{shown} ... and {len(names) - max_items} more"
```

- 50개 이하: 전체 이름 나열 → LLM이 중복 확인 가능
- 50개 초과: 앞 50개만 보여주고 나머지는 `"... and N more"` → **LLM이 잘린 이름 모름 → 중복 생성 가능**

---

## 2. 문제가 발생하는 시나리오

### 2.1 현재 규모 (금융 융자 EJB, 58 클래스)
- Command 26개, ReadModel 16개 → 50개 미만으로 **문제 없음**

### 2.2 대규모 시스템 (클래스 200+, Session Bean 20+)
- Aggregate 30개 × 평균 5 Commands = 150 Commands
- 마지막 Aggregate 처리 시 이전 145개 참조 필요
- 50개 cap → **95개 이름이 잘림** → 중복 방어 실패

### 2.3 근본적 한계
리스트업 방식 자체의 딜레마:
> **전체 리스트를 봐야 중복을 막는데, 전체 리스트를 보면 토큰이 넘친다**

재귀적 청킹(청크 내에서 또 청킹)을 해도 **전체 리스트를 한 번에 보지 않으면 의미적 중복은 잡을 수 없다.**

---

## 3. 토큰 예산 분석

현재 프롬프트 구성 요소별 토큰 사용량:

```
프롬프트 템플릿              ≈    500 tokens
report_context (하드캡)      ≤ 20,000 tokens
accumulated_names (50개 cap) ≈    350 tokens (최대)
────────────────────────────────────────────
고정 오버헤드 합계           ≈ 20,850 tokens
전체 한도 (DEFAULT_MAX_TOKENS) = 100,000 tokens
컨텐츠 여유                  ≈ 79,000 tokens
```

- accumulated_names 자체는 전체 예산의 0.35%로 토큰 범람 원인이 아님
- 문제는 토큰이 아니라 **잘린 이름을 LLM이 모른다**는 것

---

## 4. 개선 방안: 사후 Semantic Dedup

### 4.1 핵심 아이디어
이전 결과 리스트업을 LLM에게 사전 주입하는 방식(사전 방어)에서,
**생성은 자유롭게 하고 병합 시점에 의미적 중복을 제거하는 방식(사후 검증)**으로 전환한다.

### 4.2 처리 흐름

```
[현재]
chunk 1 → 결과 (이전 이름 참조)
chunk 2 → 결과 (이전 이름 참조, 50개 cap)
chunk 3 → 결과 (이전 이름 참조, 50개 cap)
  ↓
merge_chunk_results (이름 exact match만 dedup)
  ↓
저장

[개선]
chunk 1 → 결과 (자유 생성)
chunk 2 → 결과 (자유 생성)
chunk 3 → 결과 (자유 생성)
  ↓
merge_chunk_results (이름 exact match dedup)
  ↓
semantic_dedup (LLM 1회 호출: 의미적 중복 판별)  ← 추가
  ↓
저장
```

### 4.3 semantic_dedup 설계

```python
async def semantic_dedup(
    items: list,
    name_key: Callable,          # 이름 추출 함수
    display_key: Callable,       # displayName 추출 함수
    llm,                         # LLM 인스턴스
    element_type: str = "Command"  # 요소 타입 (프롬프트용)
) -> list:
    """
    생성된 요소 목록에서 의미적으로 중복인 항목을 식별하고 병합한다.

    LLM에게 이름 + displayName 목록만 전달하므로 토큰 부담 최소.
    (200개 × ~5 tokens = ~1,000 tokens)
    """
```

**LLM 프롬프트 예시:**
```
다음 Command 목록에서 의미적으로 동일하거나 매우 유사한 것들을 그룹핑하세요.
각 그룹에서 대표 이름 하나를 선택하고, 나머지는 제거 대상으로 표시하세요.

목록:
1. RegisterCollateral (담보 등록)
2. AddCollateral (담보 추가)
3. CreateLoanApplication (대출 신청 생성)
4. InitiateCollection (추심 개시)
5. InitiateCollectionCase (추심 케이스 개시)
...
```

**LLM 응답 예시:**
```json
{
  "duplicates": [
    {"keep": "RegisterCollateral", "remove": ["AddCollateral"], "reason": "동일 의도"},
    {"keep": "InitiateCollection", "remove": ["InitiateCollectionCase"], "reason": "동일 의도"}
  ]
}
```

### 4.4 토큰 부담 분석

| 항목 | 토큰 수 |
|:-----|-------:|
| dedup 프롬프트 템플릿 | ~200 |
| 이름 200개 (이름 + displayName) | ~1,000 |
| LLM 응답 | ~500 |
| **합계** | **~1,700** |

전체 리스트를 이름만 넘기므로 **200개라도 ~1,000 토큰**. 토큰 범람 위험 없음.

### 4.5 적용 대상 Phase

| Phase | 적용 필요성 | 이유 |
|:------|:-----------|:-----|
| **UserStory** | **최고** | 이전 SB 결과 전달 자체가 없음 — SB 간 의미 중복 US 완전 무방비 |
| **Command** | **높음** | cross-aggregate 의미 중복 가능성 가장 높음 (RegisterCollateral vs AddCollateral) |
| **ReadModel** | **높음** | cross-BC 동일 조회 모델 생성 가능 (LoanApplicationDetail × 3) |
| **Aggregate** | 중간 | 이전 BC의 Aggregate 이름을 넘기나, 의미 중복은 잡지 못함 |
| Event | 중간 | Command에 종속되므로 Command dedup이 해결되면 자동 해소 |
| Policy | 낮음 | 수량 자체가 적음 |
| GWT / UI / Property | 낮음 | 1:1 대응 생성이므로 구조적 중복 위험 낮음 |

---

## 5. 기존 사전 주입 방식과의 관계

### 5.1 사전 주입 유지 여부
- 50개 이하인 경우 사전 주입은 여전히 유효 (LLM이 처음부터 중복 안 만듦)
- **사전 주입(best effort) + 사후 검증(safety net)** 2단 구조가 이상적

### 5.2 최종 구조
```
사전 방어 (기존): accumulated_names → 프롬프트 주입 (50개 cap 유지)
  ↓
생성
  ↓
사후 검증 (신규): merge → semantic_dedup → 저장
```

사전 방어로 대부분 잡고, 빠져나온 것을 사후 검증에서 최종 포착.

---

## 6. 구현 우선순위

| 순서 | 작업 | 대상 Phase | 난이도 |
|:-----|:-----|:----------|:------|
| 1 | `semantic_dedup` 유틸 함수 구현 | chunking.py | 중 |
| 2 | **UserStory phase에 semantic_dedup 적용** | user_stories.py | 중 |
| 3 | Command phase에 semantic_dedup 적용 | commands.py | 낮 |
| 4 | ReadModel phase에 semantic_dedup 적용 | readmodels.py | 낮 |
| 5 | Aggregate phase에 semantic_dedup 적용 | aggregates.py | 낮 |
| 6 | Event phase에 연쇄 적용 (Command dedup 결과 반영) | events.py | 낮 |

---

## 7. 관련 파일

| 파일 | 역할 |
|:-----|:-----|
| `api/features/ingestion/workflow/utils/chunking.py` | 청킹 유틸 + `format_accumulated_names` |
| `api/features/ingestion/workflow/phases/commands.py` | `_existing_command_names` 누적 로직 |
| `api/features/ingestion/workflow/phases/readmodels.py` | `_existing_readmodel_names` 누적 로직 |
| `api/features/ingestion/workflow/phases/policies.py` | `_accumulated_policy_names` 누적 로직 |
| `api/features/ingestion/workflow/utils/report_context.py` | report context 빌더 (20k 하드캡) |
