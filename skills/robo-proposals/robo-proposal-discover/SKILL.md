---
name: robo-proposal-discover
description: Proposal 변경이 도입/영향을 주는 도메인 이벤트를 시간 순으로 펼치고 Pivotal Event·Hotspot·외부시스템을 식별하는 Discover 스테이지(ddd-starter Step 2).
extends: ddd-starter
---

# Skill: robo-proposal-discover (Discover — EventStorming)

## Purpose
ddd-starter Step 2(Discover)를 Proposal 맥락에 적용한다. 이 변경이 일으키는 **도메인 이벤트(과거형)** 를 시간 순으로 펼치고, **Pivotal Event**(경계 후보), **Hotspot**(모호/이견, resolve-now vs defer), **외부 시스템**, **액터** 를 식별한다.

## 먼저 읽어라
- `~/.claude/skills/ddd-starter/references/02-discover.md`
- `skills/robo-proposals/robo-proposal-intent/references/legacy-reference.md`

## 핵심 질문 (이 단계의 의사결정)
- "레거시 검색 후보 중 이 이벤트 흐름을 판단하려고 실제 상세 검토할 ID는 무엇인가?"
- "이 변경으로 *과거형으로* 표현되는 사건은 무엇인가?" (예: '구독이 갱신됐다', '결제가 실패했다')
- "이 흐름의 *가장 중요한 분기점*(Pivotal) 이벤트 2~3개는?"
- "다들 다르게 이해하거나 규칙이 모호한 지점(Hotspot)은? 지금 풀까(resolve-now) 미룰까(defer)?"
- "우리 시스템 밖에서 오는 이벤트(외부 시스템)는?"

`legacy-reference.md`의 호출 완료 게이트를 통과하기 전에는 최종 JSON을 출력하지 않는다.

## 출력 (최종 JSON)
narration(`[요구사항]`/`[이벤트]`/`[Pivotal]`/`[Hotspot]`) 후 빈 줄, 그 다음:
```json
{
  "DiscoverArtifact": {
    "events": [{
      "name": "구독이 갱신됐다", "actor": "스케줄러", "external": false,
      "legacyRefs": [{"nodeId": "code:<project>/<file>:<function>", "role": "derived-from",
                      "evidence": "갱신 상태 전이 로직"}]
    }],
    "pivotalEvents": ["구독이 활성화됐다"],
    "hotspots": [{"text": "연체 후 자동 해지 시점", "disposition": "DEFER"}],
    "externalSystems": ["PG사"]
  }
}
```

## Rules
1. 이벤트는 **과거형**. 명령/Aggregate 가 아니라 *사건* 을 모은다.
1-b. **모든 event 는 `legacyRefs` 배열을 가진다** — 이 실행에서 실제 검색·검토한 nodeId 만,
   레거시에 대응 없는 신규 사건은 `[]`. 규칙에서 유래하면 `rule:"<본 문장 그대로>"` 인용
   (형상·불변식: `robo-proposal-intent/references/output-schema.md` "내용 단위 인용" 절).
2. 행위 변경이면 이벤트가 비어선 안 된다(최소 1개 Pivotal).
3. 변경과 무관한 도메인 전체를 다시 그리지 말고 *이 변경의 흐름* 에 집중.
4. 언어는 사용자/프롬프트 언어를 따른다.
