# Research

- 활성 MCP 소비는 proposal intent skill과 `skill_runner.py` marker interception이다.
- collector는 현재 `LEGACYQ/LEGACYREF` 쌍만 처리하고 nodes를 id/name/label/summary/relevance/rulesCount로 축약한다.
- PLAN runner와 staged DDD base에는 collector hook이 없다.
- Proposal 목록 API는 이미 `legacyReferences`를 포함하므로 목록 배지를 위한 신규 backend endpoint는 필요 없다.
- 승인된 연결선 모드는 ②-B: 이름/컬럼이 생성 요소 텍스트에 실재할 때만 실선, search-only는 흐림·무선.
- 대형 file fallback은 과거 실제 CLI 형식 3종을 지원하므로 v2에서도 회귀 테스트로 보존한다.

## 2026-07-17 INTENT 실환경 원인 조사

- Workspace의 `ROBO_NEO4J_*`→`NEO4J_*` 강제 매핑과 제품의 `ROBO_CLUSTER_MCP_URL`을 동일하게 적용하고 `PRO-003`의 실제 입력을 `_build_intent_prompt`로 재구성해 `run_skill_lines`를 실행했다.
- 실행은 70.1초에 정상 종료했고 `PHASE:error`는 0이었다. Read 도구는 `output-schema.md`, `traceability.md`, `bounded-contexts.md`만 호출했으며 `legacy-reference.md`는 호출하지 않았다. MCP search/detail 요청·결과는 모두 0이었다.
- 별도 동일 CLI·동일 MCP 설정의 직접 호출에서는 `cluster_retrieve`와 `node_detail`이 성공했으므로 MCP 서버·주입·권한 자체는 원인이 아니다.
- `SKILL.md`는 전체 참조를 필수라고 선언하면서도 “최소 output-schema/traceability만 반드시, 나머지는 참고”라고 완화한다. 실제 실행은 이 완화 지시를 그대로 따랐다.
- 같은 문서는 INTENT를 Strategic-only라고 선언하지만 절차·출력 예시·`output-schema.md`는 Aggregate/Command/Event와 `tacticalDiff`를 요구한다. 실제 재현 출력에도 금지된 `tacticalDiff`가 포함됐다.
- 따라서 원인은 INTENT 스킬 내부의 상충하는 필수 참조·출력 계약이다. 해결은 MCP 재시도나 collector 변경이 아니라 INTENT 전용 Strategic 스키마를 분리하고 legacy 계약 Read/호출을 완화 불가능한 완료 게이트로 만드는 것이다.
- 계약 정리 후 실제 SSE `PRO-005`는 search 2회·detail 3회·done을 전달했지만 저장값은 searched 0, detail `RESULT_PARSE_FAILED`였다. 저장된 `rawHead`와 Analyzer 실응답을 대조하니 Claude stream-json의 인라인 MCP 결과는 `{"result":"<Analyzer JSON string>"}` envelope인데 `_tool_payload`는 이 envelope를 대형 파일 fallback에서만 해제하고 일반 인라인 결과에서는 해제하지 않았다. 따라서 호출·Analyzer·stream pairing이 아니라 collector의 인라인 envelope 누락이 두 번째 확정 원인이다.
