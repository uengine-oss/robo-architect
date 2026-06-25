---
name: robo-proposal-decompose
description: Discover 이벤트를 도메인 용어 서브도메인으로 묶고 책임·인접관계·느슨한 결합을 점검하는 Decompose 스테이지(ddd-starter Step 3).
extends: ddd-starter
---

# Skill: robo-proposal-decompose (Decompose — Sub-domain Map)

## Purpose
ddd-starter Step 3(Decompose)를 적용한다. Discover 이벤트를 **도메인 용어 서브도메인**(기술 용어 금지)으로 묶고, 각 서브도메인에 한 줄 책임과 인접 관계를 부여하며 **느슨한 결합**을 점검한다.

## 먼저 읽어라
- `~/.claude/skills/ddd-starter/references/03-decompose.md`

## 핵심 질문 (이 단계의 의사결정)
- "이 이벤트들을 의미 있는 묶음(서브도메인)으로 나누면? Pivotal Event 가 자연스러운 경계다."
- "각 서브도메인의 책임을 한 줄로? (모호하면 더 쪼개거나 합친다)"
- **느슨한 결합 점검**: "한 서브도메인이 바뀔 때 다른 게 같이 바뀌나? 안의 언어가 일관되나? 너무 크거나 작지 않나?"

## 출력 (최종 JSON)
narration(`[분해]`/`[책임]`/`[결합]`) 후 빈 줄, 그 다음:
```json
{
  "DecomposeArtifact": {
    "subDomains": [{"name": "구독", "responsibility": "구독 생애주기 관리", "eventRefs": ["구독이 갱신됐다"]}],
    "adjacency": [{"from": "구독", "to": "결제"}],
    "couplingNotes": ["구독↔결제는 이벤트로 느슨히 결합 가능"]
  }
}
```

## Rules
1. 서브도메인 이름은 **도메인 용어**("REST 서비스"·"Kafka 컨슈머" 금지).
2. 모든 주요 이벤트가 어떤 서브도메인엔가 속해야 한다(외톨이 금지).
3. 단일 BC 한정 변경이면 서브도메인 1개로 끝낼 수 있다 — *왜 1개인지* couplingNotes 에 적는다.
4. 언어는 사용자/프롬프트 언어를 따른다.
