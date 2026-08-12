# Verification: Analyzer-grounded Architect Strategy B

검증일: 2026-08-12

현재 판정: **Strategy B의 Simplified/Detailed 의미 생성 계약 완료**

범위: `calc_discount`, `load_target_orders`, `get_code_name` 세 함수 표본. 이 결과를 RULE
1,609개 전체나 다른 언어로 일반화하지 않는다.

## 고정 조건

- Analyzer 최종 보존 DB: `spec131fw1520260812` (read-only API `127.0.0.1:15502`).
- Architect 전용 격리 DB: `spec055b20260812`; 기본 DB와 기존 격리 DB는 변경하지 않았다.
- 실제 경로: Simplified Proposal Intent→Plan, Detailed DDD DEFINE→TACTICAL→consolidate.
- 실제 모델: `claude-opus-4-8`.
- Analyzer endpoint 계약:
  `ROBO_CLUSTER_MCP_URL=http://127.0.0.1:15502/robo/mcp/`.
- `accept`와 `apply`는 모든 실행에서 0회다.
- 비교 권위는 봉인 gold, 실제 legacy source, 실제 저장 provenance/Claude session/final Proposal이다.

## 최종 입력 계약

Intent/이전 상세 단계가 실제 성공 저장한 `node_detail(view="gwt")` inspection 중 nodeId별 가장
풍부한 한 건을 결정론적으로 선택한다. 이후 Plan/Define/Tactical에는 이를 하나의 구조화 packet으로
전달하며 같은 nodeId를 다시 조회하지 않는다. 결정론 코드는 업무 의미를 만들지 않고 다음만 한다.

- nodeId 중복 제거 및 원문 payload 운반
- source 파일/start/end와 RULE line/text 운반
- CALL/RW, 직접 TABLE/COLUMN, 존재하는 sample 운반
- Command의 `userStoryRefs`, 2~4개 구조화 GWT, 함수/RULE/TABLE refs 검증
- source 함수별 scalar 존재 여부 검증; 계산·추론 값은 생성하거나 교정하지 않고 거부
- Analyzer와 Architect가 별도 DB일 때 저장된 inspection을 권위 좌표로 사용해 RULE ref를
  `parentId + source.rule_line + statement + coordinateOnly:true`로 해석

현재 세 inspection packet은 40,433 bytes, RULE 118개, CALL/RW 65개, TABLE 3개,
COLUMN 27개다. 이 실행의 TABLE sample row는 실제 payload에서 0개였으므로 값을 만들지 않았다.

## 발견·수리한 공통 결함

1. Plan/Tactical의 목표·입력 의미·판정 규칙·출력 형상이 분산되어 모델이 GWT를 누락하거나
   category 객체/합성 필드/대표값으로 바꾸었다. TASK→INPUT MEANING→DECISION RULES→OUTPUT→FINAL
   CHECK 순서의 단일 계약으로 재구성했다.
2. Detailed DEFINE의 UserStory ID/acceptance criteria/legacyRefs와 TACTICAL의 GWT가 수렴 과정에서
   약해졌다. 생산자와 staged consolidator를 함께 수정해 그대로 운반한다.
3. `fieldValues`가 packet 전체의 우연히 같은 scalar로 통과할 수 있었다. 정확한 RULE을 인용한
   primary source 함수 범위에서만 검사한다.
4. CALL callee의 TABLE을 caller의 직접 READ로 오판할 수 있었다. 정확한 RULE을 인용한 primary
   함수의 직접 TABLE만 필수로 검사하고 `calls` role을 정식 운반한다.
5. 동일 함수의 RULE refs가 nodeId dedupe로 하나만 남고, Architect DB에는 Analyzer RULE 노드가
   없어 좌표가 사라졌다. dedupe 단위를 `(nodeId, content)`로 고치고 저장된 Analyzer inspection의
   실제 file/line/text를 별도 DB 경계에서 해석한다.
6. 모델이 `properties/userStoryRefs/gwt/legacyRefs`를 `fields` 안에 둘 때 의미가 통째로 누락됐다.
   값을 해석하지 않고 표준 위치로 한 번만 이동해 중복을 제거한다.

## 최종 실제 실행

| 경로 | Proposal | 영향 단계 wall | 새 MCP 호출 | 함수 | Command/GWT | model output |
|---|---|---:|---:|---:|---:|---:|
| Simplified | PRO-004 | Plan 296.242초 | 0 | 3/3 | 3 / 9 | 21,674 token |
| Detailed | PRO-003 | Tactical 165.962초 | 0 | 3/3 | 3 / 12 | 14,038 token |

새 MCP 호출 0은 조회 생략이 아니라 이전 단계가 실제 조회·저장한 동일 packet의 재사용이다.
PRO-004 provenance에는 INTENT inspection 3건, PRO-003에는 DISCOVER/DEFINE/TACTICAL의 실제 검색·
inspection 이력이 남아 있다. 최종 재생성 세션에는 tool call이 없고 packet의 세 nodeId를 재조회하지
않았다.

## 엄격 의미 판정

- Simplified 9/9, Detailed 12/12 GWT가 봉인 source/RULE의 입력 검증·분기·반환/상태 변화와
  모순되지 않았다.
- 세 함수 모두 정상과 근거 있는 경계/실패를 포함하고 `userStoryRefs`가 비어 있지 않다.
- `RET_INVALID/RET_FAIL`을 `cnt/status`에 대입한 것처럼 표현하지 않았고, source에 없는 합성 필드·
  대표값·설계 상태를 `fieldValues`에 넣지 않았다.
- `"(미지정)"`, `GRADE`, `FLAG_FREESHIP`, `90`, `99`, `20`, `CPN5000` 등은 해당 함수 packet의
  실제 원문/RULE에서 확인된다.
- fabrication 0건, contradiction 0건이다. 이는 이 세 함수/21 GWT의 직접 판정이며 봉인40의
  전체 의미 정확도 수치와 합산하지 않는다.
- Detailed Tactical 산출물과 consolidate 후 GWT는 12/12 그대로 보존됐다.

좌표 예:

- `calc_discount` 공백 쿠폰 RULE → `promotion.c` line 311
- `load_target_orders` 입력 버퍼/max count RULE → `settlement.c` line 261,
  직접 READ `db:orders`, `db:payment`
- `get_code_name` 공백 입력 RULE → `common_util.c` line 294,
  직접 READ `db:comm_code`

Simplified planDraft의 refs에 같은 좌표 해석 관문을 dry-run한 결과 warning 0건이었다. Detailed
consolidate 저장 결과에는 위 `parentId/source/rule_line/statement`가 실제 보존됐다.

## 회귀·산출물

- Architect 전체: **1,362 passed, 2 skipped, 3 warnings**.
- 최종 최소 보존 산출물:
  - `D:\work\robo\docs\작업보고내용\2026-08-12-evidence\architect\simplified-proposal-final.json`
  - `D:\work\robo\docs\작업보고내용\2026-08-12-evidence\architect\detailed-proposal-final.json`
  - 같은 폴더의 실행 manifest 2개
- 중간·실패 output과 logs는 최종 검증 및 보고 자료 작성 후 정리했다. 기존 DB는 덮어쓰지 않았다.
- Python 의미식 A는 KEEP이며 수정·재실험하지 않았다.

## 종료 판정

현재 표본에서 Analyzer 입력은 의미 판단에 충분했고, 남은 결함은 Architect 소비 계약·검증·좌표
운반이었다. 공통 생산자와 Simplified/Detailed 소비자를 함께 수리했으며 Strategy B를 기준 경로로
유지한다. 추가 Architect 재실행은 새 공통 결함이나 표본 확대 요구가 있기 전에는 필요하지 않다.
