# Verification: semantic-Python vs sealed-evidence Architect GWT A/B

검증일: 2026-08-10  
범위: `calc_discount`, `load_target_orders`, `get_code_name` 세 함수만. RULE 1,609개 전수로
일반화하지 않는다.

## 고정 조건

- 요구사항, 세 함수, Constitution, Architect skill, gold는 동일했다.
- Architect 모델은 네 유효 실행 모두 `claude-opus-4-8`이었다.
- A는 저장 run `20260810_100517_3f4850ec3def`의 105 RULE을 한 번만 의미-Python
  `given/then`으로 만들고, 검색 결과와 `node_detail(view=gwt)`의 RULE text만 교체했다.
- B는 같은 저장 run의 현행 RULE·좌표·CALL/RW·TABLE·sample payload를 그대로 사용했다.
- A/B 모두 Architect 프로세스 환경에
  `ROBO_CLUSTER_MCP_URL=http://127.0.0.1:15502/robo/mcp`를 주입했다. A는 그 주소에서 실험
  proxy가 조회 결과를 전달했고,
  proxy upstream은 조회 전용 analyzer였다.
- Simplified는 Proposal 생성 → intent → submit → plan, Detailed는 scope → 단계계획 → 6단계의
  draft/confirm → consolidate를 실행했다. accept/apply는 호출하지 않았다.
- `PRO-003`, `PRO-004`는 첫 A pilot에서 검색 결과에 B 자연어 RULE이 남은 것을 발견해
  무효화했다. 유효 A는 `PRO-006`, `PRO-007`; B는 `PRO-002`, `PRO-005`다.

## 전달 계약 대조

세 `node_detail(view=gwt)`를 한 번씩 조회해 RULE text를 마스킹한 뒤 구조를 대조하면 A/B가
완전히 같았다. 좌표, CALL/RW, TABLE, sample, 순서의 차이는 0이었다.

| 함수 | RULE/CALL/TABLE/sample row | A bytes | B bytes |
|---|---:|---:|---:|
| calc_discount | 31 / 5 / 0 / 0 | 6,866 | 6,279 |
| load_target_orders | 17 / 7 / 2 / 10 | 11,898 | 12,327 |
| get_code_name | 57 / 53 / 1 / 5 | 19,896 | 18,738 |
| 합계 | 105 / 65 / 3 / 15 | 38,660 | 37,344 |

A는 Python 표기가 parseable 105/105였지만 합계 bytes가 B보다 3.5% 컸다. A 입력 생산에는
별도로 `frentis-ai-model` 18콜, input 53,562/output 6,765 token, 19.222초가 들었다.

## 실제 Architect 측정

token은 Claude JSONL의 message id를 중복 제거해 집계했다. `effective input`은
input + cache creation + cache read다. MCP bytes는 Claude가 실제 받은 tool result UTF-8 bytes다.

| 경로 | 전략 | wall | effective input | output | MCP call(search/detail) | MCP bytes |
|---|---|---:|---:|---:|---:|---:|
| Simplified | A | 547.464초 | 955,426 | 38,118 | 13 (7/6) | 233,434 |
| Simplified | B | 468.079초 | 976,759 | 30,325 | 14 (7/7) | 224,964 |
| Detailed | A | 769.265초 | 1,418,501 | 53,487 | 19 (10/9) | 334,145 |
| Detailed | B | 760.105초 | 1,317,364 | 52,115 | 19 (10/9) | 323,207 |

- Simplified A는 input이 2.2% 작았지만 output 25.7%, wall 17.0%, MCP bytes 3.8%가 늘었다.
- Detailed A는 input 7.7%, output 2.6%, wall 1.2%, MCP bytes 3.4%가 늘었다.
- B Simplified의 detail 1회 추가는 요구 범위 밖 `coupon_face_value` 조회였다. 세 대상 함수는
  두 전략 모두 실제 search 후 `node_detail(view=gwt)`로 조회했다.

## GWT 판정

엄격 통과는 Given/When/Then의 값과 결과가 봉인 source/RULE/sample에 있고 전체 결과가 맞는
시나리오다. 임의 테스트 값, 실제 반환코드 대체, 잘못된 상태/flag를 하나라도 포함하면 실패로
셌다.

| 경로 | 전략 | intent AC | 최종 structured GWT | 함수 보존 | 엄격 통과 |
|---|---|---:|---:|---:|---:|
| Simplified | A | 19 | 7 | 2/3 | 4/7 |
| Simplified | B | 14 | 4 | 1/3 | 3/4 |
| Detailed | A | - | 9 | 3/3 | 6/9 |
| Detailed | B | - | 11 | 3/3 | 8/11 |

직접 대조에서 확인한 대표 결함:

- A 의미식은 형식상 105/105 parse됐지만 의미가 보장되지는 않았다.
  `load_target_orders` R327의 `rc == RET_OK and rc == RET_NOT_FOUND`는 도달 불가능하며,
  `calc_discount` 등급 거부 관계에 `FLAG_FREESHIP`이 섞였다. 후자는 Detailed GWT의
  비자격 G1 거부 결과에 실제로 전파됐다.
- A Simplified는 intent의 세 함수 19 AC 중 plan에서 두 함수 7 GWT만 남겼다.
  B Simplified는 세 함수 14 AC 중 한 함수 4 GWT만 남겼다. 둘 다 plan 수렴 누락이 있다.
- B Detailed는 빈 정산일의 실제 `RET_INVALID`를 `FAIL/EMPTY_SETTLE_DATE`로 바꿨다.
- A Detailed의 `20991231`, A/B Detailed의 `G7`, B Simplified의 `8000`, B Detailed의
  `MAX_COUNT_REACHED`는 봉인된 세 함수 source/sample에 없는 값이다.
- Detailed의 Tactical 산출물과 consolidate 후 GWT는 A 9/9, B 11/11로 byte-equivalent
  구조가 보존됐다.

## 역추적성 판정

- 실행 중에는 세 함수의 RULE 105개, CALL 65개, TABLE 3개, sample 15행이 MCP payload에
  존재했다.
- 최종 GWT의 `legacyRefs`는 함수 ID를 보존했지만 CALL/RW/sample을 GWT별로 연결하지 않았다.
  A Simplified 일부는 관계식을 보존했으나 RULE line이 사라졌고, Detailed A/B는 대체로
  함수 단위 ref로 축약됐다.
- Proposal 최상위 `legacyReferences[*].retrieves[*].inspections`는 source 좌표만 남기고
  GWT payload의 summary/rules/calls/tables/sample을 버렸다. 현재
  `legacy_provenance._compact_inspection`이 full-view shape를 기대하는 것이 원인이다.
- 따라서 “모델이 실제 근거를 조회했다”는 입증되지만, “최종 GWT에서 RULE·CALL/RW·TABLE·sample까지
  완전 역추적된다”는 통과하지 못했다.

## 결론

이 세 함수 표본에서는 A를 B의 대체 전략으로 채택할 근거가 없다. A는 parseability와
Simplified 함수 보존 수를 높였지만 의미 오류가 GWT로 전파됐고, Detailed 정확도·토큰·시간·bytes가
개선되지 않았다. B를 기준 경로로 유지하되 다음 두 결함을 먼저 고쳐야 한다.

1. Simplified plan에서 intent GWT/함수 보존 회계가 3/3이 되도록 한다.
2. 최종 `legacyRefs`와 Proposal provenance에 RULE line, CALL/RW, TABLE/sample 근거를 축약 손실 없이
   보존한다.

A는 v3 의미 골드와 표본 20함수 기준을 통과하기 전까지 실험 후보로만 보류한다.

## 회귀와 종료 상태

- Analyzer 권위 unittest: 951 OK, skipped 5.
- Parser Maven: 135 tests, failure 0, error 0, skipped 8.
- Architect 집중 회귀: staged GWT/legacyRefs 보존 3 passed.
- Architect 전체 `pytest api tests`: 1차 실행은 검사기가 UTF-8 소스를 Windows 기본 cp949로
  읽어 679건을 오판했다. 검사기의 세 `read_text()`를 UTF-8로 고정한 뒤 재실행하여
  1,381 passed, 2 skipped, 11 failed를 확인했다. 남은 11건은 ddd_spec 5건과
  Feature 031 direct `SystemMessage` 위반 6건으로, 이번 A/B 범위 밖이며 별도 수리가 필요하다.
- 종료 시 workspace `.env`는 `ROBO_NEO4J_DATABASE=neo4j`, analyzer는 15502에서 실행,
  Architect API/web과 실험 proxy/upstream은 중지했다. `shopmallgwt` DB는 보존했다.

## 2026-08-11 후속 수리·20함수 판정

- `legacy_provenance._compact_inspection`이 bounded GWT view를 인식하여 view/source 좌표,
  rules, calls, tables, samples를 그대로 보존하도록 수리했다.
- Simplified Plan은 Strategic 단계의 필수 legacyRefs를 하나라도 누락하면
  `PLAN_EVIDENCE_COVERAGE_FAILED`로 저장 전에 실패한다. 의미 자동 매핑이나 accept/apply는
  추가하지 않았다.
- 기존 세 함수와 겹치지 않는 20함수를 결과 열람 전에 봉인하고 108개 source behavior case를
  작성했다. B actual prompt 77건/519행을 source와 대조해 36개 진단 좌표를 기록했다. 이 수는
  진단 표본이며 519행이나 RULE 1,609개의 오류율로 일반화하지 않는다.
- A v3는 같은 77 evidence record를 세 번 실행했다. 231요청 중 227 JSON 성공,
  성공 JSON의 관계식 행 1,527개 중 1,267개(82.97%)만 Python parse를 통과했고, 완전한
  3-repeat record 75개 중 byte-identical은 34개(45.33%)였다. mutable `rc`의 서로 다른
  시점을 합쳐 `shipping_request:R967`, `member_authenticate:R730`을 거짓 unreachable로
  만든 사례도 확인했다. 따라서 A는 KEEP/실험이며 B를 대체하지 않는다.
- 전체 회귀: Architect 1,344 passed/2 skipped. 잘못된 root pytest 수집이 bundled runtime의
  `win32com` 테스트를 실행하던 검사기 결함을 `testpaths`로 고쳤고, Windows locale 의존
  `read_text()`를 UTF-8로 고쳤다. Feature 031의 direct `SystemMessage` 6곳도 공통
  `build_system_message` 경계로 복구했다.

## 2026-08-11 교차 노드 의미 후속

> 현재 재개 상태는 Analyzer spec131 `HANDOFF.md`가 소유한다. 아래는 수정 전 판정과 대표 replay의
> 역사 증거이며, Analyzer 전체 40 새 결과와 Architect 후속 재실행이 끝났다는 뜻이 아니다.

- 기존 A/B 네 실행과 GWT 판정은 KEEP했다. Architect 경로를 다시 실행하거나 accept/apply를
  호출하지 않았다.
- Analyzer B 입력의 FUNCTION summary/RULE/EXAMPLE/TABLE/COLUMN 40건을 별도 봉인해 직접
  판정했다. 검사 정답지 재감사 후 수정 전은 exact 27, 올바른 needs_context 2,
  omission 10, contradiction 1이다. `COMPUTE`와 `TAGSN`은 사용 근거가 있는데 빈 컬럼 설명이라
  Analyzer 누락으로 다시 열었다.
- 전체 흐름 summary와 입력 충분성 계약 수리 뒤 동일 저장 record의 Framework/DBMS 대표 2건
  replay가 통과했다. 이 결과는 새 Architect GWT 정확도 수치가 아니며 기존 세 함수/20함수
  판정과 합쳐 일반화하지 않는다.
- 현재 Architect 전체 회귀는 **1,344 passed, 2 skipped**다.
