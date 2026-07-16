# Plan: 052 레거시 참조 프로버넌스

## 현재 흐름(조사 확정)

skill_runner 는 문자열 라인만 yield — tool_use 는 `TOOL:{name}:{file_path}`(query 소실),
tool_result(evt `user`)는 **미파싱 소실**. 저장은 Proposal 노드 속성(JSON 문자열, `SET p.x`).
응답 직렬화는 `proposals_crud.py`(clean) 의 pydantic 모델 + `_parse_json`.

## 목표 흐름

```
skill_runner(추가 hunk): tool_use(robo-cluster) → "LEGACYQ::{query json}"
                         user/tool_result(id→name 매핑) → "LEGACYREF::{원문 result text}"
      │ (다른 스킬/도구엔 라인 미발생 — robo-cluster 한정)
intent_runner.stream_intent: 마커 라인 가로채기 → Collector.feed
      ├─ SSE: log_line "🔍 레거시 그래프 검색: \"q\"" / "→ 함수 N·규칙 M 참조" (스트림 표면 = 프론트 무수정)
      └─ 완료 시 Collector.save → SET p.legacyReferences (append, stage=INTENT)
proposals_crud: 응답 모델 `legacyReferences` + _parse_json (additive)
frontend: LegacyRefChip.vue(칩+팝오버) → ProposalDetail 헤더(v1) / 목록·연결선(후속 태스크)
```

## 책임/파일

| 파일 | 상태 | 변경 |
|---|---|---|
| `services/legacy_provenance.py` | 신규 | 마커 파싱·압축(nodes[{id,name,label,relevance,rulesCount}])·append 저장 |
| `platform/skill_runner.py` | **WIP-공유** | tool_use 분기에 robo-cluster query yield + `user`/tool_result elif 신규 — **additive hunk 1개**, 기존 라인 무수정 |
| `services/intent_runner.py` | clean | stream_intent 루프에 마커 분기 + 완료 시 save |
| `routes/proposals_crud.py` | clean | 모델 필드+파싱 (additive) |
| `frontend .../LegacyRefChip.vue` | 신규 | 칩+팝오버(050 토큰) |
| `frontend .../ProposalDetail.vue` | clean | 헤더에 칩 1줄 |

## 검증

새 주제 proposal 1건 intent 스트림 실행(accept 금지 — 동일도메인 merge 갭 회피) →
(a) SSE 에 🔍 검색 라인, (b) GET proposal.legacyReferences 에 query+nodes 실데이터,
(c) ProposalDetail 칩+팝오버 스크린샷. 회귀: 기존 intent 흐름(라인 프로토콜)·타 러너 무영향
(마커는 robo-cluster 호출시에만 발생).

## 한계(명시)

run_skill_once(비스트림) 경로는 캡처 없음(UI 는 stream 경로 사용). PLAN/DDD 스테이지 러너
확장·목록 배지·연결선 모드는 tasks 후속(패턴 동일).
