---
name: robo-proposal-define
description: 영향 BC 마다 Bounded Context Canvas(책임·입출력·유비쿼터스 언어·비즈니스 결정)를 작성하는 Define 스테이지(ddd-starter Step 7). 기존 메모리의 언어를 재사용한다.
extends: ddd-starter
---

# Skill: robo-proposal-define (Define — Bounded Context Canvas)

## Purpose
ddd-starter Step 7(Define)을 적용한다. 영향 BC 마다 **Bounded Context Canvas** 를 작성한다. 유비쿼터스 언어와 자율 비즈니스 결정은 **지속 전략 결정**이므로, 입력의 기존 메모리에 있는 BC 는 그 언어/결정을 **재사용**하고 새 항목만 추가한다.

## 먼저 읽어라
- `~/.claude/skills/ddd-starter/references/07-define.md`

## BCC v5 구성 (ddd-crew/bounded-context-canvas 전 항목)
1. **Purpose** — 비즈니스 관점의 책임/제공 가치.
2. **Strategic Classification** — Domain(core/supporting/generic) + Business Model(revenue/engagement/compliance/cost reduction) + Evolution(genesis/custom built/product/commodity).
3. **Domain Roles** — draft/execution/analysis/gateway/other context.
4. **Inbound / Outbound Communication** — {collaborator, message, type: Query|Command|Event}, Connect 흐름과 일치.
5. **Ubiquitous Language** — 핵심 용어 **5개 이상**(각 정의 한 줄).
6. **Business Decisions** — 이 컨텍스트가 *다른 곳에 묻지 않고* 자율로 내리는 규칙/정책.
7. **Assumptions** — 검증되지 않은 설계 가정.
8. **Verification Metrics** — 이 BC 구조를 (in)validate 할 지표.
9. **Open Questions** — 미해결 질문.
10. **languageClashes** — 같은 단어가 다른 컨텍스트에서 다른 의미면 표기.

## 출력 (최종 JSON)
narration(`[BCC]`/`[언어]`/`[결정]`) 후 빈 줄, 그 다음:
```json
{
  "DefineArtifact": {
    "contexts": [{
      "name": "주문", "purpose": "주문 접수·확정·취소를 책임진다", "classification": "SUPPORTING",
      "businessModel": ["revenue"], "evolution": "custom_built",
      "domainRoles": ["execution"],
      "inbound": [{"collaborator": "User", "message": "PlaceOrder", "type": "Command"}],
      "outbound": [{"collaborator": "결제", "message": "ChargePayment", "type": "Command"}],
      "ubiquitousLanguage": [
        {"term": "Order", "definition": "한 회원이 한 번에 결제하기로 한 상품 묶음"},
        {"term": "Order Line", "definition": "주문 내 상품 한 줄"},
        {"term": "Order Status", "definition": "Pending→Confirmed→Shipped→Closed"},
        {"term": "Cancellation", "definition": "확정 전 자유, 확정 후 환불 동반"},
        {"term": "Customer", "definition": "주문을 한 사람(회원 컨텍스트의 '회원'과 다름)"}
      ],
      "businessDecisions": ["재고 부족 시 reject vs backorder 는 자율 결정"],
      "assumptions": ["Catalog 가 주문 시점 가격을 신선하게 제공"],
      "verificationMetrics": ["주문 확정 실패율 < 0.1%"],
      "openQuestions": ["부분 취소의 환불 정책 미확정"],
      "languageClashes": ["'Customer' 가 회원 컨텍스트와 의미 다름"]
    }]
  }
}
```

## Rules
1. 각 BC 의 ubiquitousLanguage 는 **5개 이상**.
2. Inbound/Outbound 는 Connect 의 메시지 흐름과 일치(type: Query|Command|Event).
3. Business Decisions 가 전부 "다른 컨텍스트가 결정" 이면 책임이 빈약한 신호 — 재검토.
4. 언어는 사용자/프롬프트 언어를 따른다.
