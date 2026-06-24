---
name: robo-proposal-scope
description: Detailed DDD 모드 진입 시 Proposal 의 영향 범위를 분류해 어떤 ddd-starter 스테이지를 적용/생략할지 stagePlan 을 제안한다.
extends: ddd-starter
---

# Skill: robo-proposal-scope

## Purpose
Detailed DDD 모드 Proposal 의 **스코프를 분류**하고, 6개 DDD 스테이지(Discover/Decompose/Strategize/Connect/Define/Tactical) 각각에 대해 **적용/생략 권고 + 한 줄 사유**를 담은 `stagePlan` 을 만든다. ddd-starter 의 오리엔테이션(`references/00-orientation.md`)의 필수/선택 판별 트리를 Proposal(증분 변경) 맥락에 적용한다.

## 먼저 읽어라
- `~/.claude/skills/ddd-starter/references/00-orientation.md` ← 필수/선택 판별 트리

## Input (Human Prompt)
원본 프롬프트 + 현재 도메인 노드 목록 + 기존 전략 메모리(JSON).

## 분류 절차
1. **영향 BC 수 추정** — 단일 기존 BC 한정인가, 다중인가, 신규 BC 인가.
2. **변경 성격** — 전략적 설계만(분류/경계) 바뀌는가, 전술(Aggregate/Command/Event)까지 생기는가.
3. **규모** — 마이크로/국지적(한 필드·한 정책)인가, 구조적인가.

## 스테이지 권고 규칙 (orientation 트리 적용)
- **DISCOVER**: 행위 변경이면 **완전 생략 금지**(brief 확인은 가능). `applies:true`.
- **DECOMPOSE**: 단일 BC 한정이면 `recommendSkip:true`(다중 서브도메인 분해 불필요).
- **STRATEGIZE**: 신규 BC/서브도메인이 없고 분류가 이미 메모리에 있으면 `recommendSkip:true`.
- **CONNECT**: 컨텍스트가 사실상 1개면 `recommendSkip:true`. 다중이면 `applies:true, recommendSkip:false`.
- **DEFINE**: 영향 BC 가 있으면 적용. 변화 없으면 `recommendSkip:true`.
- **TACTICAL**: 전략적 설계 변경만(신규 Aggregate/Command/Event 없음)이면 `recommendSkip:true`.
- **마이크로/국지적**이면 `classifiedReach` 에 그 사실을 적고, 대부분 스테이지를 `recommendSkip:true` 로(Simplified 에 가깝게) 권고한다.

## 출력 (최종 JSON)
narration(한국어 `[범위]`/`[권고]` 태그 줄) 후, 빈 줄, 그 다음:
```json
{
  "stagePlan": {
    "version": 1,
    "classifiedReach": "single-BC tactical change",
    "stages": [
      {"stage": "DISCOVER",   "applies": true,  "recommendSkip": false, "reason": "행위 변경이라 이벤트 발굴 필요"},
      {"stage": "DECOMPOSE",  "applies": true,  "recommendSkip": true,  "reason": "단일 BC 한정"},
      {"stage": "STRATEGIZE", "applies": true,  "recommendSkip": false, "reason": "신규 서브도메인 분류 필요"},
      {"stage": "CONNECT",    "applies": true,  "recommendSkip": true,  "reason": "컨텍스트 1개"},
      {"stage": "DEFINE",     "applies": true,  "recommendSkip": false, "reason": "BC 책임 명문화"},
      {"stage": "TACTICAL",   "applies": true,  "recommendSkip": false, "reason": "신규 Aggregate 도출"}
    ]
  }
}
```

## Rules
1. 6개 스테이지를 **모두** 포함한다(생략 권고도 항목으로 남긴다 — 사용자가 뒤집을 수 있게).
2. DISCOVER 는 절대 `recommendSkip:true` 로 두지 않는다(행위 변경 Proposal).
3. 사유는 한 줄, 사용자가 결정할 수 있는 근거를 담는다.
4. 언어는 사용자 설정/프롬프트 언어를 따른다.
