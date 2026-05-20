"""
Ollama qwen3-embedding 모델을 이용한 텍스트 임베딩 & 유사도 검색 예제

사전 준비:
  ollama pull qwen3-embedding

실행:
  python examples/ollama_embedding_example.py
"""

import json
import urllib.request
import math

OLLAMA_URL = "http://localhost:11434/api/embed"
MODEL = "qwen3-embedding"


def get_embeddings(texts: list[str]) -> list[list[float]]:
    """Ollama /api/embed 엔드포인트로 임베딩 벡터를 가져온다."""
    payload = json.dumps({"model": MODEL, "input": texts}).encode()
    req = urllib.request.Request(OLLAMA_URL, data=payload, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read())
    return data["embeddings"]


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """두 벡터의 코사인 유사도를 계산한다."""
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def main():
    # 1) 문서 코퍼스
    documents = [
        "Python은 데이터 과학과 머신러닝에 널리 사용되는 프로그래밍 언어입니다.",
        "커피는 전 세계에서 가장 인기 있는 음료 중 하나입니다.",
        "딥러닝 모델은 대규모 데이터셋으로 학습하여 패턴을 인식합니다.",
        "서울의 봄 날씨는 벚꽃이 피면서 관광객이 많아집니다.",
        "벡터 데이터베이스는 임베딩을 저장하고 유사도 검색을 수행합니다.",
        "React와 Vue는 인기 있는 프론트엔드 JavaScript 프레임워크입니다.",
    ]

    print(f"📦 {len(documents)}개 문서를 임베딩합니다 (model: {MODEL})...\n")
    doc_embeddings = get_embeddings(documents)
    print(f"✅ 임베딩 완료 — 벡터 차원: {len(doc_embeddings[0])}\n")

    # 2) 쿼리로 유사도 검색
    queries = [
        "인공지능과 머신러닝",
        "날씨와 여행",
        "웹 개발 프레임워크",
    ]

    for query in queries:
        query_emb = get_embeddings([query])[0]

        # 유사도 계산 & 정렬
        scored = [(cosine_similarity(query_emb, doc_emb), doc) for doc_emb, doc in zip(doc_embeddings, documents)]
        scored.sort(key=lambda x: x[0], reverse=True)

        print(f"🔍 쿼리: \"{query}\"")
        print("-" * 60)
        for rank, (score, doc) in enumerate(scored[:3], 1):
            print(f"  {rank}. [{score:.4f}] {doc}")
        print()


if __name__ == "__main__":
    main()
