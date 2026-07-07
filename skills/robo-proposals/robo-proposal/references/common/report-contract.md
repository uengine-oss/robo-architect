# Report Contract — 산출물 표시 표준 (013-report-mcda)

서버가 각 단계 산출물을 **결정론적으로 렌더**해 응답에 실어 준다. 당신(스킬)은 그 결과를
**그대로 출력하는 얇은 렌더러**다. 표시 형식을 스스로 재요약/재작성하지 말라.

## 1. reportMarkdown 우선 (SSOT)

대상 MCP 도구 응답에는 `reportMarkdown`(서버 렌더 본문)이 포함된다:

- `proposal_save_draft`, `proposal_confirm_draft`, `proposal_save_stage_artifact`,
  `proposal_save_diff`, `proposal_generate_tasks`, `proposal_save_test_result`,
  `proposal_get`, `proposal_resume` (+ clarify 질문·validation 오류 응답).

규칙: **응답에 `reportMarkdown`이 있으면 그 문자열을 그대로(바이트 동일) 사용자에게 출력**한다.
직접 표를 다시 만들거나 필드를 골라 요약하지 않는다(형식 드리프트·누락 방지).

## 2. 진행 헤더 (progressMeta)

`proposal_next_step` 응답의 `nextStep.progressMeta` 를 진행 헤더로 렌더한다:

```
progressMeta = { stepIndex, stepTotal, phaseLabel, stageLabel, choices[], headerMarkdown }
choices[] 원소 = { id, label, hint, kind: approve|amend|rollback|skip }
```

- `headerMarkdown` 이 있으면 **그대로 출력**한다(서버 SSOT). 헤더는 `📍 (N/M)` + 현재 단계 +
  "가능한 선택지" 표를 포함한다.
- `staleArtifacts` 가 있으면 헤더에 `⚠️ 무효화 대상` 이 함께 표시된다.
- 매 턴 **헤더(progressMeta) + 본문(reportMarkdown)** 을 함께 보인다.

### 표시 스타일(한국어 고정, FR-10)

- 이모지 라벨: `📍` 진행 · `✅` 승인 · `✏️` 수정 · `↩️` 되돌리기 · `⏭️` 건너뛰기 · `⚠️` 경고.
- 스텝 번호 `(N/M)`, 리스트 아티팩트는 고정 컬럼 표.

## 3. 경량 폴백 (reportMarkdown 부재 시)

서버가 아직 배포되지 않았거나 `reportMarkdown` 이 비어 있으면 **경량 안전망**으로만 표시한다:

1. 저장 artifact 의 **모든 top-level 키를 표(키 → 값)로 기계 나열**한다(누락 0 유지).
2. 그 위에 progressMeta 헤더(있으면)를 얹는다.
3. **흐름을 중단하지 않는다** — 다음 선택지를 제시하고 계속 진행한다.

폴백은 서식 품질을 포기하는 대신 **누락 0·중단 없음**만 보장한다. 전체 템플릿을 이중으로
유지하지 말라(SSOT 는 서버). 서버 참조 구현: `report_render.render_fallback`.

## 4. 금지 사항

- `reportMarkdown` 이 있는데 무시하고 스스로 요약하는 것.
- 저장 JSON 계약(`output-contracts.md`)을 표시 목적으로 변형하는 것.
- 진행 헤더를 임의 형식으로 재작성하는 것(progressMeta/headerMarkdown 을 우회).
