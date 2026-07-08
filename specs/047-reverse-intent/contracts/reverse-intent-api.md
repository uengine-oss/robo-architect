# Contract: Reverse Intent API (신규)

기존 `/api/proposals` 라우터에 추가되는 라우트. 기존 계약은 무변경(신규만 추가).

## GET /api/proposals/reverse/sources
분석된 그래프 목록(FR-003). 읽기 전용.
- **200**: `{ "sources": [ { "db": "test", "operationCount": 11, "label": "test" }, ... ] }`
- 프로브 실패 시 `[ANALYZER_NEO4J_DATABASE]` 단일 폴백. 목록 0개면 빈 배열(프론트가 "분석된 그래프 없음" 안내).

## POST /api/proposals/reverse
역추출 Proposal 생성. 자연어 대신 code-scope 수신.
- **Body**: `{ "db": "test", "title": "(선택)" }`
- 동작: Proposal 노드 생성(`decompositionMode="REVERSE_INTENT"`, `reverseScope={db}`, `originalPrompt="역방향 도출: <db>"`, `status="DRAFT"`).
- **201**: `ProposalResponse`(기존 스키마).
- **400**: db 미제공 또는 해당 db에 오퍼레이션 0(명시적 에러, 헌법 IV).

## GET /api/proposals/{id}/stream/reverse
역추출 실행 SSE. 기존 intent 스트림과 형태 호환(프론트 로그/결과 렌더 재사용).
- **이벤트**:
  - `phase` `{phase, message}` — "그룹핑 중"/"요구사항 도출 중(3/8)" 등
  - `groups` `{groups:[{table, tableLogicalName, kind, opCount, dominantStereotype, ops:[{logicalName}]}]}` — 그룹 카드용(1회, US2)
  - `log_line` `{text}` — narration 실시간
  - `brief_result` `{table, part, total}` — 브리프 1건 완료 진행
  - `strategic_diff` `{strategicDiff}` — 병합 최종(기존 intent와 동일 키)
  - `done` `{proposalId, status:"DRAFT", nextStage:"plan"}`
  - `error` `{code, message}`
- 저장: 최종 `strategicDiff`를 Proposal 노드에 기록(기존 intent 저장 경로 재사용). analyzer 그래프는 읽기 전용.

## 하류(무변경, 재사용)
- 결과 표시 = 기존 `IntentDecompositionView`(strategicDiff 동일 형태).
- 이후 `POST /stream/plan` → tasks → implement = 기존 그대로. Proposal 노드의 `strategicDiff`만 소비.

## enum
- `DecompositionMode`에 `REVERSE_INTENT` 추가(기존 3값 뒤). 기존 소비처(plan/oda 분기)는 새 값에서 기본 경로 유지.
