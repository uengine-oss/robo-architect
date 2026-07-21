# Skill: robo-proposal-oda

## Purpose
Proposal 의 **ODA 표준 분해 모드**(043) 본문. 자연어 요청을 **TM Forum ODA 표준 지식 베이스**에
근거해 분해/설계하고, 결과를 robo-architect 표준 **strategicDiff / tacticalDiff** 로 수렴시키면서
ODA 전용 메타(정합성 매핑·적합성 리포트·표준 산출물)를 함께 산출한다.

이 스킬은 두 전역 스킬을 **계승(superset)** 한다 — 같은 거버넌스/지식맵을 적용한다:
- `~/.claude/skills/oda-specify/SKILL.md` (표준 정합성 + REUSE/EXTEND/NEW + 적합성 게이트 + BDD)
- `~/.claude/skills/oda-plan/SKILL.md` (SID 데이터 모델 + TMF 계약 + ODA Component/Canvas 아키텍처)

> **역할 경계(Principle X)**: 이 스킬은 *에이전트*다 — 표준 매핑/분류/설계를 만든다.
> 차단 권위(게이트 PASS/FAIL 강제)와 영속은 **백엔드**(`oda_conformance.py`/`oda_runner.py`)가
> 가진다. 너는 `violations[]` 를 사실대로 보고하면 되고, 게이트 결과 강제는 백엔드가 한다.

## Step 0 — ODA 지식 베이스 해석 (먼저)
실행 시 `--add-dir` 로 ODA 지식 루트가 주입된다. 그 루트에서:
- `oda-specify/references/oda-knowledge-map.md` 규칙대로 `sid/` + `repo/usecase-library/` 보유
  디렉터리를 지식 루트로 본다(없으면 그 사실을 `notes` 에 적고 표준 근거 불가를 알린다).
- `sid/json/_index.json`, `sid/markdown/<Domain>.md` — SID 엔티티.
- `repo/usecase-library/` — Use Case(UCxxx).
- `repo/source/tmf-services/` + 지식맵 §2 치트시트 — TMF Open API.
- `repo/feature-definition-and-test-kit/` — BDD feature-kit 방언/스텝.

## Input (Human Prompt)
호출자가 다음을 준다:
- `Proposal ID`, `Phase`(intent|plan), `원본 프롬프트`.

`Phase` 값에 따라 아래 둘 중 하나를 수행한다.

---

## Phase = intent  (표준 정합성 + 전략 분해 + 1차 적합성)

`oda-specify` 의 Override 1·3·5 를 적용한다:
1. **표준 정합성 매핑** — 요청을 가장 가까운 UC(UCxxx)·SID 도메인/엔티티·기준 TMF API·ODA
   Component 블록(coreFunction|managementFunction|securityFunction)에 매핑. 출처를 인용한다.
2. **전략 분해** — 표준에 정렬된 Strategic Diff(BoundedContext(=Epic)/Feature/UserStory)를
   `robo-proposal-intent` 의 `references/output-schema.md`·`traceability.md` 형식(tempId+참조)대로
   산출한다. **수렴 핵심**: 다운스트림이 무분기로 동작하도록 표준 diff 형태를 깨지 마라.
3. **1차 적합성** — 식별된 엔티티/속성을 REUSE/EXTEND/NEW 로 분류하고, "준수 후 확장" 하드 규칙
   위반(표준 필드 제거/재타이핑, 표준 계약 파괴, 비인가 확장 메커니즘)을 `violations[]` 에 적는다.

### 출력 (JSON 한 덩어리, 코드펜스 없이 또는 ```json 펜스로)
```json
{
  "phase": "intent",
  "alignment": {
    "useCases": [{"id": "UC003", "intent": "...", "source": "repo/usecase-library/..."}],
    "sidEntities": [{"name": "Customer", "domain": "Customer", "source": "sid/markdown/Customer.md"}],
    "tmfApis": [{"id": "TMF629", "name": "Customer Management", "version": "v4"}],
    "componentBlock": "coreFunction",
    "notes": ""
  },
  "conformance": {
    "baseline": "SID v22 / TMF629 v4",
    "items": [
      {"element": "Customer", "kind": "entity", "classification": "REUSE", "source": "sid/.../Customer.md"},
      {"element": "Customer.loyaltyTier", "kind": "attribute", "classification": "EXTEND",
       "mechanism": "characteristic", "justification": "비표준 필드 → Characteristic 패턴"}
    ],
    "violations": []
  },
  "strategicDiff": { "...": "robo-proposal-intent output-schema 형식(version, boundedContexts/features/userStories, tempId+refs)" },
  "journeys": []
}
```

규칙: 모든 `items[]` 는 `classification` 이 REUSE/EXTEND/NEW 중 하나여야 한다(미분류 금지). 표준이
이미 정의한 것은 **REUSE 우선**(REUSE > EXTEND > NEW). 확장은 인가 메커니즘
(`characteristic`/`@type` 서브타이핑/추가형 enum)만 쓰고 `mechanism`+`justification` 을 채워라.
하드 규칙을 깨면 그것을 `violations` 에 `{rule, element, detail}` 로 보고하라(게이트 FAIL 유발).

---

## Phase = plan  (전술 설계 + 표준 산출물 + 최종 게이트)

`oda-plan` 의 Override 2·3·4·5·6 을 적용한다. intent 단계의 alignment/strategicDiff 는 이미
Proposal 에 저장되어 있다고 가정한다.
1. **SID 데이터 모델** — 표준 엔티티/속성 재사용(+출처), 추가 속성마다 인가 확장 메커니즘+사유.
2. **TMF Open API 계약** — API 별, 오퍼레이션 REUSE/EXTEND/NEW, 표준 오퍼레이션 재작성 없이
   추가형 단편만.
3. **ODA Component/Canvas 아키텍처** — core/management/security 블록, exposed/dependent API,
   eventNotification(TMF688), 참여 Canvas 오퍼레이터(+UC 참조).
4. **BDD `.feature`** — ODA feature-kit 방언(UCxxx-Fyyy, Scenario Outline/Examples, 기존 스텝 재사용).
5. **전술 수렴** — 위 설계를 robo-architect 표준 **tacticalDiff**(Aggregate/Command/Event/VO,
   tempId+refs)로 수렴시킨다.
6. **최종 적합성** — 데이터모델/계약이 구체화된 상태로 게이트를 재평가, `violations[]` 갱신.

### 출력 (JSON 한 덩어리)
```json
{
  "phase": "plan",
  "conformance": {
    "baseline": "...",
    "items": [{"element": "...", "classification": "REUSE|EXTEND|NEW", "...": "..."}],
    "violations": []
  },
  "tacticalDiff": [ {"...": "robo-proposal-plan 전술 형식(tempId+refs)"} ],
  "artifacts": {
    "dataModel": {"entities": [{"name": "...", "reuseOf": "SID:...", "addedAttributes": [{"name": "...", "mechanism": "characteristic", "justification": "..."}]}]},
    "contracts": [{"api": "TMF629", "operations": [{"name": "GET /customer", "classification": "REUSE"}]}],
    "architecture": {"coreFunction": [], "managementFunction": [], "securityFunction": [],
                     "exposedAPIs": [], "dependentAPIs": [], "events": [], "canvasOperators": []},
    "featureFiles": [{"filename": "UC003-F001-Loyalty.feature", "content": "@UC003\nFeature: ..."}]
  }
}
```

## 절대 규칙
- **모든 diff 요소는 `legacyRefs` 배열을 가진다** — `robo-proposal-intent` 의
  `references/legacy-reference.md`·`output-schema.md` "요소별 레거시 근거 불변식"과
  "내용 단위 인용" 절을 그대로 적용(실제 검색·검토한 nodeId 만, 없으면 `[]`,
  규칙 유래는 `rule:"<본 문장 그대로>"`).
- 표준이 커버하는 것을 새로 발명하지 마라(REUSE 우선).
- 표준 계약을 깨지 마라 — 확장은 추가형(additive)·인가 메커니즘만.
- 깨지는 변경이 불가피하면 숨기지 말고 `violations` 로 보고하라(백엔드가 차단/면제 처리).
- strategicDiff/tacticalDiff 는 robo-architect 표준 형식을 유지하라(다운스트림 무분기, 수렴).
- 출력은 JSON 한 덩어리. 분석 서술은 JSON 앞에 두고, JSON 은 마지막에 한 번만.
