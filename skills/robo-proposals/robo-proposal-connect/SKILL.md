---
name: robo-proposal-connect
description: 컨텍스트 간 상호작용을 Event/Command/Query 로 분류하고 pub/sub vs 동기 결합을 결정하며 결합 위험을 점검하는 Connect 스테이지(ddd-starter Step 5).
extends: ddd-starter
---

# Skill: robo-proposal-connect (Connect — Domain Message Flow)

## Purpose
ddd-starter Step 5(Connect)를 적용한다. 분해된 컨텍스트를 다시 합칠 때 **느슨하게 결합**되도록 각 상호작용을 **Event(pub/sub) / Command / Query** 로 분류하고, 기본을 **이벤트 드리븐 pub/sub** 으로 두되 즉시 응답이 꼭 필요할 때만 동기로 한다. 결합 위험을 점검한다.

## 먼저 읽어라
- `~/.claude/skills/ddd-starter/references/05-connect.md`

## 통신 패턴 의사결정 가이드
| 상황 | 패턴 |
|------|------|
| 발신자가 누가 들을지 모르고 즉시 응답 불필요 | **Event (pub/sub)** ← 기본 |
| 특정 컨텍스트에 작업 지시 | **Command** |
| 즉시 신선한 값 필요 | **Query (sync)** |

## 결합 점검 (경고로 surface)
- 양방향 동기 의존 → **금지**(분해 재검토).
- 동기 호출 체인 깊이 > 3 → 위험(어딘가 비동기화).
- 한 컨텍스트가 5개 이상과 직접 통신 → 노란불(중개자 검토).

## 출력 (최종 JSON)
narration(`[연동]`/`[분류]`/`[결합경고]`) 후 빈 줄, 그 다음:
```json
{
  "ConnectArtifact": {
    "interactions": [
      {"from": "주문", "to": "결제", "message": "ChargePayment", "kind": "COMMAND", "sync": true, "rationale": "외부 PG 동기 호출"},
      {"from": "결제", "to": "주문", "message": "PaymentConfirmed", "kind": "EVENT", "sync": false, "rationale": "비동기 pub/sub"}
    ],
    "couplingWarnings": ["주문→결제→배송 동기 체인 주의"],
    "messagingChannel": "Kafka"
  }
}
```

## Rules
1. 특별한 동기 요구가 없으면 **EVENT(pub/sub)** 가 기본. 입력의 프로젝트 결합 posture 를 존중한다.
2. 메시징 채널 기본은 Kafka(Constitution 기술스택이 다른 브로커를 지정하면 그걸 따른다).
3. 결합 위반은 숨기지 말고 couplingWarnings 에 명시.
4. 언어는 사용자/프롬프트 언어를 따른다.
