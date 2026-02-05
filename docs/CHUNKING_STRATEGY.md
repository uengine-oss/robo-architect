# 대용량 요구사항 처리 전략 (Chunking & Scanning)

## 1. 개요

### 1.1 목적
Event Storming 생성 프로세스에서 대용량 요구사항 문서, User Stories, Breakdown 결과 등을 안정적으로 처리하기 위한 청킹 및 스캐닝 전략을 수립합니다.

### 1.2 핵심 원칙
1. **단계별 독립 청킹**: 각 phase는 독립적으로 청킹 처리 (전체 프로세스를 청크 단위로 돌리지 않음)
2. **맥락 유지**: Overlapping을 통한 분할 지점의 앞뒤 문장 보존
3. **결과 병합**: 각 청크별 결과를 병합하고 중복 제거
4. **일관성 검증**: 병합된 결과의 일관성 보장

---

## 2. 청킹 전략

### 2.1 청킹이 필요한 Phase

| Phase | 입력 데이터 | 청킹 대상 | 우선순위 |
|-------|------------|----------|---------|
| `extract_user_stories_phase` | `ctx.content` (요구사항 문서) | 요구사항 텍스트 | 🔴 높음 |
| `identify_bounded_contexts_phase` | `ctx.user_stories` | User Stories 리스트 | 🔴 높음 |
| `extract_aggregates_phase` | `ctx.breakdowns` (per BC) | Breakdown 결과 | 🟡 중간 |
| `extract_commands_phase` | `ctx.user_stories` (per Aggregate) | User Stories 리스트 | 🟡 중간 |
| `extract_events_phase` | `ctx.content` + `ctx.commands` | 요구사항 텍스트 | 🟡 중간 |
| `identify_policies_phase` | `ctx.events` + `ctx.commands` | Event/Command 리스트 | 🟢 낮음 |
| `generate_gwt_phase` | `ctx.commands` + `ctx.policies` | Command/Policy 리스트 | 🟢 낮음 |

### 2.2 청킹 방식 결정

**❌ 전체 프로세스를 청크 단위로 돌리는 방식 (비추천)**
- 문제점:
  - 각 phase 간 의존성이 있어서 청크별로 전체 프로세스를 돌리면 일관성 문제 발생
  - 예: BC 추출 → Aggregate 추출 → Command 추출 순서가 중요한데, 청크별로 돌리면 BC 간 경계가 모호해짐
  - 결과 병합이 복잡해짐

**✅ 각 Phase별로 독립적으로 청킹 처리 (추천)**
- 장점:
  - 각 phase는 독립적으로 청킹 가능
  - 입력 데이터만 청킹하고, phase 로직은 그대로 유지
  - 결과 병합이 단순함
  - 기존 코드 구조 유지 가능

---

## 3. 공통 청킹 유틸리티

### 3.1 청킹 유틸리티 함수

**파일 위치**: `api/features/ingestion/workflow/utils/chunking.py` (신규 생성)

```python
from typing import List, Tuple
import tiktoken  # 또는 다른 토큰 카운터

# LLM 토큰 제한 (안전 마진 포함)
DEFAULT_MAX_TOKENS = 100000  # 입력용 (출력 제외)
DEFAULT_CHUNK_SIZE = 80000   # 실제 청크 크기 (안전 마진 포함)
DEFAULT_OVERLAP_SIZE = 2000  # Overlapping 크기 (문자 단위)

def estimate_tokens(text: str, model: str = "gpt-4") -> int:
    """텍스트의 토큰 수를 추정"""
    encoding = tiktoken.encoding_for_model(model)
    return len(encoding.encode(text))

def should_chunk(text: str, max_tokens: int = DEFAULT_MAX_TOKENS) -> bool:
    """청킹이 필요한지 판단"""
    return estimate_tokens(text) > max_tokens

def split_text_with_overlap(
    text: str,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    overlap_size: int = DEFAULT_OVERLAP_SIZE,
    split_by: str = "\n\n"  # 문단 단위로 분할
) -> List[Tuple[str, int, int]]:
    """
    텍스트를 overlapping을 포함하여 청크로 분할
    
    Returns:
        List[Tuple[chunk_text, start_char, end_char]]
        - chunk_text: 청크 텍스트 (overlapping 포함)
        - start_char: 원본 텍스트에서의 시작 위치
        - end_char: 원본 텍스트에서의 끝 위치
    """
    # 1. 먼저 문단 단위로 분할
    paragraphs = text.split(split_by)
    
    chunks = []
    current_chunk = []
    current_size = 0
    start_char = 0
    
    for i, para in enumerate(paragraphs):
        para_size = len(para)
        
        # 현재 청크에 추가하면 크기 초과하는 경우
        if current_size + para_size > chunk_size and current_chunk:
            # 현재 청크 저장
            chunk_text = split_by.join(current_chunk)
            end_char = start_char + len(chunk_text)
            chunks.append((chunk_text, start_char, end_char))
            
            # Overlapping: 이전 청크의 마지막 N개 문단을 다음 청크 시작에 포함
            overlap_paras = current_chunk[-overlap_size // (len(current_chunk[-1]) + len(split_by)):]
            current_chunk = overlap_paras + [para]
            current_size = sum(len(p) for p in current_chunk)
            start_char = end_char - len(split_by.join(overlap_paras))
        else:
            current_chunk.append(para)
            current_size += para_size
    
    # 마지막 청크 추가
    if current_chunk:
        chunk_text = split_by.join(current_chunk)
        end_char = start_char + len(chunk_text)
        chunks.append((chunk_text, start_char, end_char))
    
    return chunks

def split_list_with_overlap(
    items: List[Any],
    chunk_size: int,
    overlap_count: int = 2
) -> List[List[Any]]:
    """
    리스트를 overlapping을 포함하여 청크로 분할
    
    Args:
        items: 분할할 리스트
        chunk_size: 각 청크의 최대 아이템 수
        overlap_count: 이전 청크의 마지막 N개 아이템을 다음 청크 시작에 포함
    
    Returns:
        List[List[Any]]: 청크 리스트
    """
    if len(items) <= chunk_size:
        return [items]
    
    chunks = []
    i = 0
    
    while i < len(items):
        chunk = items[i:i + chunk_size]
        chunks.append(chunk)
        
        # Overlapping: 다음 청크 시작 위치를 overlap_count만큼 앞당김
        i += chunk_size - overlap_count
    
    return chunks
```

### 3.2 결과 병합 유틸리티

```python
from typing import List, Dict, Any, Callable

def merge_chunk_results(
    chunk_results: List[List[Any]],
    dedupe_key: Callable[[Any], str] = None,
    merge_strategy: str = "union"  # "union" | "intersection" | "append"
) -> List[Any]:
    """
    청크별 결과를 병합
    
    Args:
        chunk_results: 각 청크의 결과 리스트
        dedupe_key: 중복 제거를 위한 키 함수 (예: lambda x: x.id)
        merge_strategy: 병합 전략
            - "union": 모든 결과 합치기 (중복 제거)
            - "intersection": 모든 청크에 공통으로 나타나는 결과만
            - "append": 단순 연결 (중복 제거만)
    
    Returns:
        병합된 결과 리스트
    """
    if merge_strategy == "union":
        all_results = []
        for results in chunk_results:
            all_results.extend(results)
        
        if dedupe_key:
            seen = set()
            merged = []
            for item in all_results:
                key = dedupe_key(item)
                if key not in seen:
                    seen.add(key)
                    merged.append(item)
            return merged
        return all_results
    
    elif merge_strategy == "intersection":
        if not chunk_results:
            return []
        
        # 첫 번째 청크 결과를 기준으로
        common = {dedupe_key(item): item for item in chunk_results[0]}
        
        # 나머지 청크에서 공통 항목만 유지
        for results in chunk_results[1:]:
            chunk_keys = {dedupe_key(item) for item in results}
            common = {k: v for k, v in common.items() if k in chunk_keys}
        
        return list(common.values())
    
    else:  # append
        all_results = []
        seen = set()
        for results in chunk_results:
            for item in results:
                if dedupe_key:
                    key = dedupe_key(item)
                    if key in seen:
                        continue
                    seen.add(key)
                all_results.append(item)
        return all_results
```

---

## 4. Phase별 청킹 구현 계획

### 4.0 진행 상황 업데이트 전략

**전체 진행 범위 (0-100%):**
각 phase는 전체 진행의 특정 범위를 담당합니다. 청킹이 발생하면 그 범위 내에서 세부 진행 상황을 업데이트합니다.

**진행 상황 업데이트 패턴:**
```python
# Phase 전체 진행 범위 예시
PHASE_PROGRESS_RANGES = {
    "EXTRACTING_USER_STORIES": (10, 20),      # 10% → 20%
    "IDENTIFYING_BC": (20, 30),                # 20% → 30%
    "EXTRACTING_AGGREGATES": (30, 45),         # 30% → 45%
    "EXTRACTING_COMMANDS": (45, 60),           # 45% → 60%
    "EXTRACTING_EVENTS": (60, 75),             # 60% → 75%
    "IDENTIFYING_POLICIES": (75, 85),          # 75% → 85%
    "GENERATING_GWT": (85, 95),                # 85% → 95%
}

# 청킹 시 세부 진행 상황 계산
def calculate_chunk_progress(
    phase_start: int,
    phase_end: int,
    chunk_index: int,
    total_chunks: int,
    merge_progress_ratio: float = 0.1  # 병합 작업이 차지하는 비율 (10%)
) -> int:
    """
    청크별 진행 상황 계산
    
    Args:
        phase_start: Phase 시작 진행률
        phase_end: Phase 종료 진행률
        chunk_index: 현재 청크 인덱스 (0-based)
        total_chunks: 전체 청크 수
        merge_progress_ratio: 결과 병합이 차지하는 진행률 비율
    
    Returns:
        현재 진행률 (0-100)
    """
    phase_range = phase_end - phase_start
    processing_range = phase_range * (1 - merge_progress_ratio)  # 처리 작업 범위
    
    # 청크 처리 진행률
    chunk_progress = (chunk_index + 1) / total_chunks
    current_progress = phase_start + (processing_range * chunk_progress)
    
    return int(current_progress)
```

**진행 상황 업데이트 시점:**
1. **스캐닝 시작**: Phase 시작 진행률
2. **청킹 완료**: Phase 시작 + 2%
3. **각 청크 처리 시작**: 청크별 진행률 계산
4. **각 청크 처리 완료**: 다음 청크 시작 전 업데이트
5. **결과 병합 시작**: Phase 종료 - 3%
6. **결과 병합 완료**: Phase 종료 진행률

---

### 4.1 `extract_user_stories_phase` (우선순위: 높음)

**현재 구조:**
- `ctx.content` (요구사항 문서)를 한 번에 처리
- **전체 진행 범위**: 10% → 20%

**청킹 전략:**
1. **스캐닝**: `ctx.content`의 토큰 수 측정
2. **청킹**: 필요 시 `split_text_with_overlap()` 사용
3. **처리**: 각 청크별로 User Story 추출
4. **병합**: `merge_chunk_results()`로 결과 병합 (중복 제거: `user_story.id` 또는 `user_story.action`)

**구현 예시:**
```python
async def extract_user_stories_phase(ctx: IngestionWorkflowContext) -> AsyncGenerator[ProgressEvent, None]:
    from api.features.ingestion.workflow.utils.chunking import (
        should_chunk, split_text_with_overlap, merge_chunk_results
    )
    
    PHASE_START = 10
    PHASE_END = 20
    MERGE_RATIO = 0.1  # 병합 작업이 10% 차지
    
    # Phase 시작
    yield ProgressEvent(
        phase=IngestionPhase.EXTRACTING_USER_STORIES,
        message="User Story 추출 시작...",
        progress=PHASE_START
    )
    
    # 스캐닝
    if should_chunk(ctx.content):
        yield ProgressEvent(
            phase=IngestionPhase.EXTRACTING_USER_STORIES,
            message="대용량 요구사항 스캐닝 중...",
            progress=PHASE_START + 1
        )
        
        chunks = split_text_with_overlap(ctx.content)
        total_chunks = len(chunks)
        
        yield ProgressEvent(
            phase=IngestionPhase.EXTRACTING_USER_STORIES,
            message=f"요구사항을 {total_chunks}개 청크로 분할 완료",
            progress=PHASE_START + 2
        )
        
        chunk_results = []
        processing_range = (PHASE_END - PHASE_START) * (1 - MERGE_RATIO)
        
        for i, (chunk_text, start_char, end_char) in enumerate(chunks):
            # 청크 처리 시작
            chunk_progress = PHASE_START + 2 + int((processing_range * (i / total_chunks)))
            yield ProgressEvent(
                phase=IngestionPhase.EXTRACTING_USER_STORIES,
                message=f"청크 {i+1}/{total_chunks} 처리 중... ({start_char:,}~{end_char:,} 문자)",
                progress=chunk_progress
            )
            
            # 임시 context로 청크 처리
            chunk_ctx = IngestionWorkflowContext(
                session=ctx.session,
                content=chunk_text,  # 청크만 사용
                client=ctx.client,
                llm=ctx.llm
            )
            
            # 기존 로직 재사용 (청크별로)
            stories = await extract_user_stories_from_chunk(chunk_ctx)
            chunk_results.append(stories)
            
            # 청크 처리 완료
            chunk_complete_progress = PHASE_START + 2 + int((processing_range * ((i + 1) / total_chunks)))
            yield ProgressEvent(
                phase=IngestionPhase.EXTRACTING_USER_STORIES,
                message=f"청크 {i+1}/{total_chunks} 완료 ({len(stories)}개 User Story 추출)",
                progress=chunk_complete_progress
            )
        
        # 결과 병합 시작
        yield ProgressEvent(
            phase=IngestionPhase.EXTRACTING_USER_STORIES,
            message=f"{total_chunks}개 청크 결과 병합 중...",
            progress=PHASE_END - 3
        )
        
        # 결과 병합
        ctx.user_stories = merge_chunk_results(
            chunk_results,
            dedupe_key=lambda s: f"{s.role}:{s.action}"  # 중복 제거 키
        )
        
        # 결과 병합 완료
        yield ProgressEvent(
            phase=IngestionPhase.EXTRACTING_USER_STORIES,
            message=f"User Story 추출 완료 (총 {len(ctx.user_stories)}개)",
            progress=PHASE_END
        )
    else:
        # 기존 로직 (청킹 불필요)
        yield ProgressEvent(
            phase=IngestionPhase.EXTRACTING_USER_STORIES,
            message="User Story 추출 중...",
            progress=PHASE_START + 5
        )
        
        ctx.user_stories = await extract_user_stories_normal(ctx)
        
        yield ProgressEvent(
            phase=IngestionPhase.EXTRACTING_USER_STORIES,
            message=f"User Story 추출 완료 (총 {len(ctx.user_stories)}개)",
            progress=PHASE_END
        )
```

### 4.2 `identify_bounded_contexts_phase` (우선순위: 높음)

**현재 구조:**
- `ctx.user_stories`를 한 번에 처리
- **전체 진행 범위**: 20% → 30%

**청킹 전략:**
1. **스캐닝**: User Stories 리스트 크기 및 텍스트 길이 측정
2. **청킹**: `split_list_with_overlap()` 사용 (User Story 단위로 분할)
3. **처리**: 각 청크별로 BC 추출
4. **병합**: `merge_chunk_results()`로 결과 병합 (중복 제거: `bc.name` 또는 `bc.key`)

**구현 예시:**
```python
async def identify_bounded_contexts_phase(ctx: IngestionWorkflowContext) -> AsyncGenerator[ProgressEvent, None]:
    from api.features.ingestion.workflow.utils.chunking import (
        should_chunk, split_list_with_overlap, merge_chunk_results
    )
    
    PHASE_START = 20
    PHASE_END = 30
    MERGE_RATIO = 0.1
    
    # Phase 시작
    yield ProgressEvent(
        phase=IngestionPhase.IDENTIFYING_BC,
        message="Bounded Context 식별 시작...",
        progress=PHASE_START
    )
    
    # User Stories를 텍스트로 변환하여 크기 측정
    stories_text = "\n".join([f"{us.role}: {us.action}" for us in ctx.user_stories])
    
    if should_chunk(stories_text) or len(ctx.user_stories) > 50:  # 리스트 크기 기준
        yield ProgressEvent(
            phase=IngestionPhase.IDENTIFYING_BC,
            message=f"대용량 User Stories 스캐닝 중... ({len(ctx.user_stories)}개)",
            progress=PHASE_START + 1
        )
        
        # User Story 리스트를 청크로 분할 (overlap: 3개)
        story_chunks = split_list_with_overlap(ctx.user_stories, chunk_size=30, overlap_count=3)
        total_chunks = len(story_chunks)
        
        yield ProgressEvent(
            phase=IngestionPhase.IDENTIFYING_BC,
            message=f"User Stories를 {total_chunks}개 청크로 분할 완료",
            progress=PHASE_START + 2
        )
        
        chunk_results = []
        processing_range = (PHASE_END - PHASE_START) * (1 - MERGE_RATIO)
        
        for i, story_chunk in enumerate(story_chunks):
            # 청크 처리 시작
            chunk_progress = PHASE_START + 2 + int((processing_range * (i / total_chunks)))
            yield ProgressEvent(
                phase=IngestionPhase.IDENTIFYING_BC,
                message=f"청크 {i+1}/{total_chunks} 처리 중... ({len(story_chunk)}개 User Stories)",
                progress=chunk_progress
            )
            
            # 청크별 BC 추출
            bcs = await identify_bcs_from_stories(story_chunk, ctx)
            chunk_results.append(bcs)
            
            # 청크 처리 완료
            chunk_complete_progress = PHASE_START + 2 + int((processing_range * ((i + 1) / total_chunks)))
            yield ProgressEvent(
                phase=IngestionPhase.IDENTIFYING_BC,
                message=f"청크 {i+1}/{total_chunks} 완료 ({len(bcs)}개 BC 식별)",
                progress=chunk_complete_progress
            )
        
        # 결과 병합 시작
        yield ProgressEvent(
            phase=IngestionPhase.IDENTIFYING_BC,
            message=f"{total_chunks}개 청크 결과 병합 중...",
            progress=PHASE_END - 3
        )
        
        # 결과 병합
        ctx.bounded_contexts = merge_chunk_results(
            chunk_results,
            dedupe_key=lambda bc: bc.key or bc.name
        )
        
        # 결과 병합 완료
        yield ProgressEvent(
            phase=IngestionPhase.IDENTIFYING_BC,
            message=f"Bounded Context 식별 완료 (총 {len(ctx.bounded_contexts)}개)",
            progress=PHASE_END
        )
    else:
        # 기존 로직
        yield ProgressEvent(
            phase=IngestionPhase.IDENTIFYING_BC,
            message="Bounded Context 식별 중...",
            progress=PHASE_START + 5
        )
        
        ctx.bounded_contexts = await identify_bcs_normal(ctx)
        
        yield ProgressEvent(
            phase=IngestionPhase.IDENTIFYING_BC,
            message=f"Bounded Context 식별 완료 (총 {len(ctx.bounded_contexts)}개)",
            progress=PHASE_END
        )
```

### 4.3 `extract_aggregates_phase` (우선순위: 중간)

**현재 구조:**
- BC별로 Breakdown 결과를 처리

**청킹 전략:**
1. **스캐닝**: Breakdown 결과 텍스트 길이 측정
2. **청킹**: BC별로 Breakdown이 대용량이면 청킹
3. **처리**: 각 청크별로 Aggregate 추출
4. **병합**: BC별로 결과 병합 (중복 제거: `agg.name`)

### 4.4 `extract_commands_phase` (우선순위: 중간)

**현재 구조:**
- Aggregate별로 User Stories를 처리

**청킹 전략:**
1. **스캐닝**: Aggregate별 User Stories 텍스트 길이 측정
2. **청킹**: Aggregate별로 User Stories가 대용량이면 청킹
3. **처리**: 각 청크별로 Command 추출
4. **병합**: Aggregate별로 결과 병합 (중복 제거: `cmd.name`)

### 4.5 `extract_events_phase` (우선순위: 중간)

**현재 구조:**
- Command별로 요구사항을 처리

**청킹 전략:**
1. **스캐닝**: 요구사항 텍스트 길이 측정
2. **청킹**: 요구사항이 대용량이면 청킹
3. **처리**: 각 청크별로 Event 추출
4. **병합**: Command별로 결과 병합 (중복 제거: `evt.name`)

### 4.6 `identify_policies_phase` (우선순위: 낮음)

**현재 구조:**
- 모든 Event와 Command를 한 번에 처리

**청킹 전략:**
1. **스캐닝**: Event/Command 리스트 크기 측정
2. **청킹**: 리스트가 대용량이면 청킹
3. **처리**: 각 청크별로 Policy 추출
4. **병합**: 결과 병합 (중복 제거: `policy.name`)

### 4.7 `generate_gwt_phase` (우선순위: 낮음)

**현재 구조:**
- Command/Policy를 순차적으로 처리 (이미 개별 처리)

**청킹 전략:**
- 현재 구조상 개별 처리하므로 청킹 불필요
- 다만, Command/Policy가 매우 많을 경우 배치 처리 고려

---

## 5. Overlapping 전략

### 5.1 텍스트 기반 청킹

**Overlapping 방식:**
- **문단 단위 분할**: `\n\n` 기준으로 문단 분할
- **Overlap 크기**: 이전 청크의 마지막 2-3개 문단을 다음 청크 시작에 포함
- **이유**: 문맥 유지 및 경계에서 놓치는 정보 방지

**예시:**
```
원본 텍스트:
[문단1] [문단2] [문단3] [문단4] [문단5] [문단6] [문단7] [문단8]

청크 1: [문단1] [문단2] [문단3] [문단4]
청크 2: [문단3] [문단4] [문단5] [문단6]  ← 문단3,4가 overlap
청크 3: [문단5] [문단6] [문단7] [문단8]  ← 문단5,6이 overlap
```

### 5.2 리스트 기반 청킹

**Overlapping 방식:**
- **아이템 단위 분할**: 리스트 아이템 기준으로 분할
- **Overlap 개수**: 이전 청크의 마지막 2-3개 아이템을 다음 청크 시작에 포함
- **이유**: 아이템 간 연관성 유지

**예시:**
```
원본 리스트: [US1, US2, US3, US4, US5, US6, US7, US8]

청크 1: [US1, US2, US3, US4]
청크 2: [US3, US4, US5, US6]  ← US3,4가 overlap
청크 3: [US5, US6, US7, US8]  ← US5,6이 overlap
```

### 5.3 Overlap 크기 결정

**텍스트 기반:**
- **기본 overlap**: 2000자 또는 2-3개 문단
- **조정**: 청크 크기의 10-20% 수준

**리스트 기반:**
- **기본 overlap**: 2-3개 아이템
- **조정**: 청크 크기의 10% 수준

---

## 6. 구현 순서

### Phase 1: 공통 유틸리티 구현 (1주)
1. `api/features/ingestion/workflow/utils/chunking.py` 생성
2. `split_text_with_overlap()` 구현
3. `split_list_with_overlap()` 구현
4. `merge_chunk_results()` 구현
5. 단위 테스트 작성

### Phase 2: 우선순위 높은 Phase 구현 (2주)
1. `extract_user_stories_phase` 청킹 적용
2. `identify_bounded_contexts_phase` 청킹 적용
3. 통합 테스트

### Phase 3: 우선순위 중간 Phase 구현 (2주)
1. `extract_aggregates_phase` 청킹 적용
2. `extract_commands_phase` 청킹 적용
3. `extract_events_phase` 청킹 적용
4. 통합 테스트

### Phase 4: 우선순위 낮은 Phase 구현 (1주)
1. `identify_policies_phase` 청킹 적용 (필요 시)
2. `generate_gwt_phase` 최적화 (필요 시)

---

## 7. 진행 상황 업데이트 상세 가이드

### 7.1 진행 상황 업데이트 패턴

**기본 구조:**
```python
PHASE_START = 10  # Phase 시작 진행률
PHASE_END = 20    # Phase 종료 진행률
MERGE_RATIO = 0.1 # 병합 작업 비율 (10%)

# 1. Phase 시작
yield ProgressEvent(phase=..., message="시작...", progress=PHASE_START)

# 2. 스캐닝 (1%)
yield ProgressEvent(phase=..., message="스캐닝 중...", progress=PHASE_START + 1)

# 3. 청킹 완료 (1%)
yield ProgressEvent(phase=..., message="청킹 완료", progress=PHASE_START + 2)

# 4. 각 청크 처리 (청크 수에 따라 분배)
processing_range = (PHASE_END - PHASE_START - 2) * (1 - MERGE_RATIO)
for i, chunk in enumerate(chunks):
    # 청크 시작
    start_progress = PHASE_START + 2 + int((processing_range * (i / total_chunks)))
    yield ProgressEvent(phase=..., message=f"청크 {i+1}/{total_chunks} 처리 중...", progress=start_progress)
    
    # 청크 처리...
    
    # 청크 완료
    complete_progress = PHASE_START + 2 + int((processing_range * ((i + 1) / total_chunks)))
    yield ProgressEvent(phase=..., message=f"청크 {i+1}/{total_chunks} 완료", progress=complete_progress)

# 5. 결과 병합 시작 (3% 전)
yield ProgressEvent(phase=..., message="결과 병합 중...", progress=PHASE_END - 3)

# 6. 결과 병합 완료
yield ProgressEvent(phase=..., message="완료", progress=PHASE_END)
```

### 7.2 Phase별 진행 범위

| Phase | 시작 | 종료 | 범위 | 비고 |
|-------|------|------|------|------|
| `EXTRACTING_USER_STORIES` | 10 | 20 | 10% | User Story 추출 |
| `IDENTIFYING_BC` | 20 | 30 | 10% | BC 식별 |
| `EXTRACTING_AGGREGATES` | 30 | 45 | 15% | Aggregate 추출 (BC별 처리) |
| `EXTRACTING_COMMANDS` | 45 | 60 | 15% | Command 추출 (Aggregate별 처리) |
| `EXTRACTING_EVENTS` | 60 | 75 | 15% | Event 추출 (Command별 처리) |
| `IDENTIFYING_POLICIES` | 75 | 85 | 10% | Policy 식별 |
| `GENERATING_GWT` | 85 | 95 | 10% | GWT 생성 (Command/Policy별 처리) |
| `SAVING` | 95 | 100 | 5% | Neo4j 저장 |

### 7.3 메시지 템플릿

**청킹 없을 때:**
- `"{Phase} 시작..."`
- `"{Phase} 중..."`
- `"{Phase} 완료 (총 N개)"`

**청킹 있을 때:**
- `"대용량 {데이터} 스캐닝 중... (N개)"`
- `"{데이터}를 {N}개 청크로 분할 완료"`
- `"청크 {i}/{total} 처리 중... ({detail})"`
- `"청크 {i}/{total} 완료 ({N}개 {결과} 추출)"`
- `"{N}개 청크 결과 병합 중..."`
- `"{Phase} 완료 (총 {N}개)"`

### 7.4 진행 상황 업데이트 빈도

- **최소 업데이트**: 각 청크 시작/완료 시
- **권장 업데이트**: 청크 내부에서도 주요 단계마다 (LLM 호출 전/후 등)
- **최대 업데이트**: 너무 빈번한 업데이트는 피함 (UI 부하)

---

## 8. 테스트 전략

### 8.1 단위 테스트
- 청킹 유틸리티 함수 테스트
- Overlapping 정확성 검증
- 결과 병합 로직 검증
- 진행 상황 계산 로직 검증

### 8.2 통합 테스트
- 대용량 요구사항 문서로 전체 워크플로우 테스트
- 각 phase별 청킹 동작 검증
- 결과 일관성 검증
- 진행 상황 업데이트 정확성 검증

### 8.3 성능 테스트
- 청킹 전/후 처리 시간 비교
- 메모리 사용량 측정
- LLM 호출 횟수 측정
- 진행 상황 업데이트 오버헤드 측정

---

## 8. 주의사항

### 8.1 Traceability 유지
- 각 청크 결과에 원본 위치 정보 보존
- `user_story_ids`, `refs` 등 추적 정보 유지

### 8.2 일관성 보장
- 청크 간 결과 일관성 검증
- 중복 제거 시 우선순위 결정 (첫 번째 청크 우선 또는 마지막 청크 우선)

### 8.3 에러 처리
- 일부 청크 실패 시에도 나머지 청크 처리 계속
- 부분 실패 결과도 병합 (사용자에게 알림)

---

## 9. 향후 개선 사항

1. **동적 청크 크기 조정**: LLM 응답 속도에 따라 청크 크기 조정
2. **병렬 처리**: 독립적인 청크는 병렬 처리 고려
3. **캐싱**: 동일한 청크 재처리 방지
4. **프로그레스 추적**: 청크별 진행 상황 실시간 업데이트
