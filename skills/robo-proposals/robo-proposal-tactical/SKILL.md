---
name: robo-proposal-tactical
description: BCC 에서 Aggregate 경계·불변식·상태전이·명령/이벤트·처리량을 도출하는 Tactical 스테이지(ddd-starter Step 8 + robo-proposal-plan 전술 규칙).
extends: robo-proposal-plan
---

# Skill: robo-proposal-tactical (Tactical — Aggregate Design Canvas)

## Purpose
ddd-starter Step 8(Code)의 Aggregate Design 을 적용한다. Define(BCC)을 입력으로 각 **Aggregate** 의 경계·불변식·상태전이·명령/이벤트·처리량을 도출한다. `robo-proposal-plan` 의 전술 분해 규칙(레퍼런스)을 상속하되, 여기서는 **스테이지 산출물(TacticalArtifact)** 형태로 낸다 — 아키텍처 결정은 이후 plan 단계가 수행한다.

## 먼저 읽어라
- `~/.claude/skills/ddd-starter/references/08-code.md`
- `skills/robo-proposals/robo-proposal-intent/references/aggregates.md`, `commands-events.md`, `invariants-ui.md`

## Aggregate 경계 결정 (이 단계의 핵심)
- **함께 변해야 하는가? / 한 트랜잭션에서 일관성이 필요한가?** → Yes 면 한 Aggregate.
- 작게 유지(큰 Aggregate = 동시성 충돌·로딩 비용). **Value Object 는 Aggregate 로 모델링하지 않는다.**

## 채울 항목
State Transitions · Enforced Invariants(**2개 이상**) · Corrective Policies · Handled Commands · Created Events · Throughput.

## 출력 (최종 JSON)
narration(`[Aggregate]`/`[경계]`/`[불변식]`) 후 빈 줄, 그 다음:
```json
{
  "TacticalArtifact": {
    "aggregates": [{
      "name": "Order", "description": "한 회원의 한 번 결제 상품 묶음", "boundaryRationale": "Order+OrderLine 은 한 트랜잭션 일관성 필요",
      "stateTransitions": [{"from": "Pending", "to": "Confirmed", "trigger": "ConfirmOrder"}],
      "invariants": ["totalAmount = Σ(line.price×qty)", "Confirmed 이후 라인 변경 불가"],
      "correctivePolicies": ["결제 실패 60초 → 자동 Canceled"],
      "handledCommands": ["PlaceOrder", "ConfirmOrder", "CancelOrder"],
      "createdEvents": ["OrderPlaced", "OrderConfirmed", "OrderCanceled"],
      "throughput": {"commandHandlingRate": {"avg": "50/s", "max": "100/s"}, "totalClients": {"avg": "1k", "max": "5k"}, "concurrencyConflictChance": {"avg": "low", "max": "med"}},
      "size": {"eventGrowthRate": {"avg": "5/order", "max": "20/order"}, "lifetime": {"avg": "7d", "max": "90d"}, "eventsPersisted": {"avg": "12", "max": "60"}}
    }]
  }
}
```

## Rules
1. 각 Aggregate 의 invariant 은 **2개 이상**.
2. Value Object(Money, Address)는 Aggregate 가 아니다.
3. Commands/Events 는 Define 의 Inbound/Outbound 와 일치.
4. 코드를 작성하지 말 것 — 전술 설계 산출물만.
5. 언어는 사용자/프롬프트 언어를 따른다.
