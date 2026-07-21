# Skill: robo-proposal-intent

## Purpose

자연어 요구사항을 **Strategic Diff(BoundedContext(=Epic)/Feature/UserStory/Process)만**으로 분해한다.
이 단계는 무엇을 만들지 확정한다. 전술 설계와 아키텍처 구현 계획은 후속 PLAN 단계가 담당한다.
요구사항이 모호할 때는 최대 5개의 선택형 명확화 질문을 제시한다.

## 완료 전에 반드시 읽고 실행할 계약

아래 세 파일을 모두 Read 도구로 직접 읽기 전에는 분석이나 최종 JSON 출력을 시작하지 마라.

1. `skills/robo-proposals/robo-proposal-intent/references/strategic-output-schema.md`
2. `skills/robo-proposals/robo-proposal-intent/references/bounded-contexts.md`
3. `skills/robo-proposals/robo-proposal-intent/references/legacy-reference.md`

특히 `legacy-reference.md`를 Read 도구로 반드시 직접 읽어라. 문서의 목록→선택 ID 상세조회와
호출 완료 게이트를 통과하기 전에는 최종 JSON을 출력하지 않는다. 도구가 주입된 실행에서 검색을
추측으로 생략하지 않는다. 검색 목록만 보고 원문·라인·컬럼을 보았다고 주장하지 않는다.

사용자 화면 흐름을 `journeys`에 담아야 할 때만 다음 파일도 읽는다.

- `skills/robo-proposals/robo-proposal-intent/references/journeys.md`

## Input (Human Prompt)

```text
Proposal ID: PRO-NNN
원본 프롬프트: <user's natural language requirement>

현재 도메인 구성 요소 목록:
- id: US-001, type: UserStory, name: 결제 처리
...

사용자 명확화 답변: (있을 경우) Q0: ... → A: ...
이전 분석 결과 / 사용자 피드백(재생성): (있을 경우)
```

## 분해 절차

1. 세 필수 참조 파일을 Read하고 레거시 조회 완료 게이트를 실행한다.
2. 요구사항의 액터, 목표, 기대 가치, 정상·예외 인수조건을 파악한다.
3. 유비쿼터스 언어와 업무 능력 경계로 BoundedContext를 식별하고 core/supporting/generic으로 분류한다.
4. 각 BoundedContext 아래에 응집된 Feature를 만들고 각 UserStory를 정확히 하나의 Feature와 BoundedContext에 연결한다.
5. 사용자 흐름이 명확하면 Process와 선택적 Journey를 만든다.
6. 출력 전 모든 tempId와 부모 참조, 필수 UserStory 필드, 레거시 근거 표현을 자가 검증한다.
7. 모든 요소에 `legacyRefs`를 기록한다 — 이 실행에서 실제 검색·검토한 nodeId만.
8. **S3 배분(필수)**: 요소 초안을 만든 뒤 검색 후보 목록을 다시 훑으며 **후보 → 요소** 방향으로
   근거를 배분한다(추가 호출 없음). 이름이 아니라 요약으로 판단한다. 그래도 빈 요소만 S4 로
   1회 재검색한다. narration 에 `[근거 커버리지]` 를 남기고, 이 단계 없이 최종 JSON 을
   출력하지 않는다(`references/legacy-reference.md` S3/S4).

기존 노드는 입력의 실제 id를 사용해 `op:"MODIFY"`로 표현하고 신규 노드만 `op:"CREATE"`와
고유 `tempId`를 사용한다. 기술 계층이나 구현 상세를 요구사항 노드로 만들지 않는다.

## Output Format

`strategic-output-schema.md`의 형상을 정확히 따른다. 명확화가 필요하면 `action:"clarify"`,
명확하면 `action:"done"`을 반환한다. 최종 JSON에 후속 PLAN 소유 산출물을 추가하지 않는다.

## 스트리밍 출력 방식

필수 참조 Read와 레거시 조회를 먼저 끝낸 뒤 JSON 전에 분석 과정을 한국어 4~8줄로 서술한다.
각 줄은 `[태그] 내용` 형식이다.

- `[요구사항]`: 액터·목표·가치
- `[레거시 참조]`: 상세 검토에 성공한 핵심 함수·테이블과 실제 줄 범위, 또는 빈 결과/오류 사실
- `[도메인 검토]`: 기존 구성 요소 재사용 여부
- `[BC 분해]`: 경계와 분류 근거
- `[추적성]`: Epic→Feature→UserStory 참조 검증
- `[판단]`: 모호성 또는 최종 분해 판단

서술 후 빈 줄을 두고 JSON 코드 블록을 출력한다.

## Rules

1. 레거시 구현은 현실 근거로 사용하되 사용자 요구사항보다 우선하거나 그대로 복사하지 않는다.
2. 검색 후보와 상세 검토를 구분하고 상세 조회하지 않은 원문·라인·컬럼을 주장하지 않는다.
3. 모든 CREATE는 고유 tempId와 유효한 부모 참조를 갖는다. 고아 노드를 만들지 않는다.
4. 모든 UserStory는 role, action, benefit, acceptanceCriteria를 갖는다.
5. 기존 도메인 구성 요소와 일치하면 입력의 실제 id를 재사용한다.
6. 명확화 질문은 최대 5개이며 요구가 명확하면 바로 done으로 반환한다.
7. 출력 언어는 원본 프롬프트의 언어를 따른다.
8. 피드백 재생성에서는 피드백을 최우선 반영하고 지적되지 않은 부분을 유지하며 추가 명확화를 만들지 않는다.
