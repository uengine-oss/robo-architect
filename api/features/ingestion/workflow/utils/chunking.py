"""
Chunking utilities for large text and list processing.

Provides utilities for splitting large inputs into manageable chunks with overlap
to maintain context across boundaries.
"""

from __future__ import annotations

from typing import Any, Callable, List, Tuple

# LLM 토큰 제한 (안전 마진 포함)
# GPT-4의 경우 입력 토큰 제한이 128k이지만, 출력을 위한 여유를 두고 100k로 설정
DEFAULT_MAX_TOKENS = 100000  # 입력용 (출력 제외)
DEFAULT_CHUNK_SIZE = 80000   # 실제 청크 크기 (안전 마진 포함)
DEFAULT_OVERLAP_SIZE = 2000  # Overlapping 크기 (문자 단위)

# User Story 추출용 청크 크기 (출력 안정성 기준)
# 설계 원칙: 출력 안정성을 최우선으로 고려
# - 모델: gpt-4.1-2025-04-14
# - completion cap: 32,768 tokens
# - story 1개당 평균: 300~600 tokens
# - 한 번의 호출에서 안정적으로 생성 가능: 50~80개 (물리적 상한)
# - 3k 입력이면 보통 10~25 story 생성 (completion cap 32k에서 안전)
# - 형식 무관하게 모든 문서에 일관된 청킹 정책 적용
USER_STORY_CHUNK_SIZE = 3000  # User Story 추출용 청크 크기 (출력 안정성 기준)
USER_STORY_CHUNK_OVERLAP_RATIO = 0.05  # 5% overlap


def estimate_tokens(text: str, model: str = "gpt-4.1-2025-04-14") -> int:
    """
    텍스트의 토큰 수를 추정.
    
    Args:
        text: 토큰 수를 추정할 텍스트
        model: 사용할 모델명 (tiktoken encoding 결정)
    
    Returns:
        추정된 토큰 수
    """
    try:
        import tiktoken
        try:
            encoding = tiktoken.encoding_for_model(model)
        except KeyError:
            # 모델을 찾을 수 없는 경우, cl100k_base를 기본 인코딩으로 사용
            # (GPT-4 계열 모델의 표준 인코딩)
            encoding = tiktoken.get_encoding("cl100k_base")
        return len(encoding.encode(text))
    except ImportError:
        # tiktoken이 없는 경우, 대략적인 추정
        # 일반적으로 1 토큰 ≈ 4 문자 (영어 기준)
        return len(text) // 4


def should_chunk(text: str, max_tokens: int = DEFAULT_MAX_TOKENS) -> bool:
    """
    청킹이 필요한지 판단 (텍스트 기반).
    
    Args:
        text: 체크할 텍스트
        max_tokens: 최대 토큰 수 (이 값을 초과하면 청킹 필요)
    
    Returns:
        청킹이 필요하면 True, 아니면 False
    """
    return estimate_tokens(text) > max_tokens


def should_chunk_list(
    items: List[Any],
    item_to_text: Callable[[Any], str] | None = None,
    max_items: int = 50,
    max_tokens: int = DEFAULT_MAX_TOKENS,
) -> bool:
    """
    리스트 기반 청킹이 필요한지 판단.
    
    Args:
        items: 체크할 리스트
        item_to_text: 각 아이템을 텍스트로 변환하는 함수 (None이면 기본 변환 사용)
        max_items: 최대 아이템 수 (이 값을 초과하면 청킹 필요)
        max_tokens: 최대 토큰 수 (텍스트로 변환했을 때 이 값을 초과하면 청킹 필요)
    
    Returns:
        청킹이 필요하면 True, 아니면 False
    """
    # 아이템 개수 기준
    if len(items) > max_items:
        return True
    
    # 텍스트 길이 기준 (아이템을 텍스트로 변환)
    if item_to_text:
        items_text = "\n".join([item_to_text(item) for item in items])
    else:
        # 기본 변환: 아이템의 문자열 표현 사용
        items_text = "\n".join([str(item) for item in items])
    
    return estimate_tokens(items_text) > max_tokens


def split_text_with_overlap(
    text: str,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    overlap_size: int = DEFAULT_OVERLAP_SIZE,
    split_by: str = "\n\n",  # 문단 단위로 분할
) -> List[Tuple[str, int, int]]:
    """
    텍스트를 overlapping을 포함하여 청크로 분할.
    
    문단 단위로 분할하여 의미 있는 경계를 유지하고, 이전 청크의 마지막 부분을
    다음 청크 시작에 포함시켜 맥락을 유지합니다.
    
    Args:
        text: 분할할 텍스트
        chunk_size: 각 청크의 최대 토큰 수 (추정)
        overlap_size: Overlapping 크기 (문자 단위)
        split_by: 텍스트 분할 기준 (기본: 문단 단위 "\n\n")
    
    Returns:
        List[Tuple[chunk_text, start_char, end_char]]
        - chunk_text: 청크 텍스트 (overlapping 포함)
        - start_char: 원본 텍스트에서의 시작 위치 (문자 인덱스)
        - end_char: 원본 텍스트에서의 끝 위치 (문자 인덱스)
    """
    if not text:
        return []
    
    # 1. 먼저 문단 단위로 분할
    paragraphs = text.split(split_by)
    
    if not paragraphs:
        return [(text, 0, len(text))]
    
    chunks = []
    current_chunk = []
    current_size = 0
    start_char = 0
    
    # Overlapping을 위한 문단 개수 계산 (대략적)
    # overlap_size를 문단 평균 크기로 나누어 필요한 문단 개수 추정
    avg_para_size = sum(len(p) for p in paragraphs) / len(paragraphs) if paragraphs else 0
    overlap_para_count = max(1, int(overlap_size / (avg_para_size + len(split_by)))) if avg_para_size > 0 else 2
    
    for i, para in enumerate(paragraphs):
        para_size = estimate_tokens(para)
        
        # 현재 청크에 추가하면 크기 초과하는 경우
        if current_size + para_size > chunk_size and current_chunk:
            # 현재 청크 저장
            chunk_text = split_by.join(current_chunk)
            end_char = start_char + len(chunk_text)
            chunks.append((chunk_text, start_char, end_char))
            
            # Overlapping: 이전 청크의 마지막 N개 문단을 다음 청크 시작에 포함
            overlap_paras = current_chunk[-overlap_para_count:] if len(current_chunk) >= overlap_para_count else current_chunk
            current_chunk = overlap_paras + [para]
            current_size = sum(estimate_tokens(p) for p in current_chunk)
            
            # start_char 업데이트: overlap 부분의 시작 위치
            overlap_text = split_by.join(overlap_paras)
            start_char = end_char - len(overlap_text)
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
    overlap_count: int = 2,
) -> List[List[Any]]:
    """
    리스트를 overlapping을 포함하여 청크로 분할.
    
    이전 청크의 마지막 N개 아이템을 다음 청크 시작에 포함시켜
    아이템 간 연관성을 유지합니다.
    
    Args:
        items: 분할할 리스트
        chunk_size: 각 청크의 최대 아이템 수
        overlap_count: 이전 청크의 마지막 N개 아이템을 다음 청크 시작에 포함
    
    Returns:
        List[List[Any]]: 청크 리스트
    """
    if len(items) <= chunk_size:
        return [items]
    
    if chunk_size <= overlap_count:
        # chunk_size가 overlap_count보다 작거나 같으면 의미 있는 청킹 불가
        return [items]
    
    chunks = []
    i = 0
    
    while i < len(items):
        chunk = items[i:i + chunk_size]
        chunks.append(chunk)
        
        # Overlapping: 다음 청크 시작 위치를 overlap_count만큼 앞당김
        i += chunk_size - overlap_count
        
        # 마지막 청크가 이미 포함되었으면 종료
        if i >= len(items):
            break
    
    return chunks


def merge_chunk_results(
    chunk_results: List[List[Any]],
    dedupe_key: Callable[[Any], str] | None = None,
    merge_strategy: str = "union",  # "union" | "intersection" | "append"
) -> List[Any]:
    """
    청크별 결과를 병합.
    
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
    if not chunk_results:
        return []
    
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
        
        if not dedupe_key:
            raise ValueError("intersection strategy requires dedupe_key")
        
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


def calculate_chunk_progress(
    phase_start: int,
    phase_end: int,
    chunk_index: int,
    total_chunks: int,
    merge_progress_ratio: float = 0.1,  # 병합 작업이 차지하는 비율 (10%)
) -> int:
    """
    청크별 진행 상황 계산.
    
    Args:
        phase_start: Phase 시작 진행률 (0-100)
        phase_end: Phase 종료 진행률 (0-100)
        chunk_index: 현재 청크 인덱스 (0-based)
        total_chunks: 전체 청크 수
        merge_progress_ratio: 결과 병합이 차지하는 진행률 비율 (0.0-1.0)
    
    Returns:
        현재 진행률 (0-100)
    """
    if total_chunks == 0:
        return phase_start
    
    phase_range = phase_end - phase_start
    processing_range = phase_range * (1 - merge_progress_ratio)  # 처리 작업 범위
    
    # 청크 처리 진행률
    chunk_progress = (chunk_index + 1) / total_chunks
    current_progress = phase_start + (processing_range * chunk_progress)
    
    return int(current_progress)
