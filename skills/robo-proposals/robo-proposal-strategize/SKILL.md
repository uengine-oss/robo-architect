---
name: robo-proposal-strategize
description: 영향 서브도메인을 Core/Supporting/Generic 으로 분류하고 차별성·build-vs-buy 를 판단하는 Strategize 스테이지(ddd-starter Step 4). 기존 전략 메모리를 재사용한다.
extends: ddd-starter
---

# Skill: robo-proposal-strategize (Strategize — Core Domain Chart)

## Purpose
ddd-starter Step 4(Strategize)를 적용한다. 영향 서브도메인을 **Core / Supporting / Generic** 으로 분류한다. 이 분류는 **지속 전략 결정**이므로, 입력으로 주어진 기존 전략 메모리에 이미 분류된 BC 는 **재질문하지 말고 그대로 사용**하고(confirm), 새로 필요한 것만 분류한다.

## 먼저 읽어라
- `~/.claude/skills/ddd-starter/references/04-strategize.md`

## 핵심 질문 (이 단계의 의사결정)
- **차별성 질문**: "이 도메인을 우리가 직접 만들 때와 외부 SaaS 살 때의 차이를 *고객이 느끼나?*" → 느낀다 = Core.
- **시장 성숙도 질문**: "이 문제를 푸는 좋은 외부 솔루션이 이미 있나?" → 있고 충분 = Generic.
- "이 변경의 *진짜 차별점*(가장 비즈니스적으로 차별적인 것)은 무엇인가?" — 있으면 `differentiation` 으로 함께 출력.
- Generic 이면 build-vs-buy 후보(외부 솔루션)를 적는다.

## 출력 (최종 JSON)
narration(`[분류]`/`[차별성]`/`[build-vs-buy]`) 후 빈 줄, 그 다음:
```json
{
  "StrategizeArtifact": {
    "classifications": [
      {"subDomain": "추천", "kind": "CORE", "rationale": "체류시간 좌우, 경쟁 차별점", "buildVsBuy": null,
       "legacyRefs": [{"nodeId": "code:<project>/<file>:<function>", "role": "derived-from"}]},
      {"subDomain": "결제", "kind": "GENERIC", "rationale": "표준 PG로 충분", "buildVsBuy": "Toss Payments",
       "legacyRefs": []}
    ],
    "differentiation": {"valueProposition": "...", "differentiator": "추천 정확도", "personas": ["..."]}
  }
}
```
`differentiation` 은 프로젝트 차별성이 새로 드러났을 때만 포함(없으면 생략 — 기존 메모리 유지).

## Rules
0. **모든 classification 은 `legacyRefs` 배열을 가진다** — 입력(Decompose 서브도메인)의 근거를
   승계하고, 대응 없으면 `[]`. 새 nodeId 를 지어내지 않는다.
1. 모든 영향 서브도메인은 CORE/SUPPORTING/GENERIC 중 하나로 분류(빈 분류 금지).
2. 전부 Core 거나 전부 Generic 이면 의심하고 재검토.
3. 메모리에 이미 있는 분류와 **다르게** 판단하면 그 사유를 rationale 에 분명히 적는다(백엔드가 충돌로 surface 한다).
4. 언어는 사용자/프롬프트 언어를 따른다.
