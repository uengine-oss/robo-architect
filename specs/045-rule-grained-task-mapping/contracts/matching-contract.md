# Contract: Phase 3 Task↔Rule 매칭 (소비자 내부 계약)

**성격**: 서비스 간 계약 아님(생산자/프론트 영향 0). architect 하이브리드 매퍼 **내부**의 입출력·불변식 계약. 044 `graph-consumer-contract.md` C4(매칭 단위=루틴)를 Rule 단위로 확장.

## M1. 입력
- `process`(BpmProcess), 그 `tasks`(BpmTaskDTO[]), 세션 `rules`(RuleDTO[]), `contexts`(RuleContext[] = `build_rule_contexts(rules)`).
- task 질의 텍스트 = `process.name + domain_keywords + task.name + task.description`(기존 `_build_query`).

## M2. 비교 단위 = Rule blob (★ 본 계약의 핵심)
- 각 Rule의 비교 텍스트(blob) = `"규칙: {title}\nGIVEN:{given}\nWHEN:{when}\nTHEN:{then}\n[함수요약]{function_summary}"`.
  - `function_summary` 없으면 그 줄 생략(빈 줄 금지).
  - 테이블/모듈/패키지는 blob에 **넣지 않는다**(research Q2: 효과 미미·커버리지 낮음).
- **금지**: 코드 컨테이너(FILE/CLASS/MODULE) 요약을 task와의 1차 비교 대상으로 삼는 것.

## M3. 후보 선정 (recall 프리필터)
- task 질의 벡터 vs 전 Rule blob 벡터 코사인 → 상위 top-K(기존 cap, 예 ≤20).
- floor(`MIN_BL_INCLUSION`)는 **약한 하한**으로만(현 배포 모델은 동일도메인을 0.79~0.82로 군집 → floor가 거의 못 거름). 최종 선별은 M5 검증기.
- **모듈 컨테이너 점수가 낮다는 이유만으로 그 안의 Rule을 후보에서 제외하지 않는다(FR-002).** 모듈 검색 결과는 약신호/로그로만 쓸 수 있다(하드 게이트 금지).

## M4. 전략 무관 (헌법 II)
- framework(룰=루틴 직속)·dbms(룰=구문→owner_resolver 루틴 복원) 모두 동일 경로. `source_function`/`function_summary`가 채워지는 한 매칭 코드에 전략 분기 0.

## M5. 정밀도 (불변 — 기존 재사용)
- top-K 후보 → 기존 LLM 검증기(`agent_validator`)가 수락/거부 → 수락분만 `(:BpmTask)-[:REALIZED_BY]->(:Rule)` upsert(기존 `explore_service`).
- 교차 프로세스/태스크 경합은 기존 중재(arbitration)가 한 곳으로 정리.

## M6. 비용/견고성
- 임베딩 호출은 **≤30개 청크**로 분할(엔드포인트 배치 상한 32·대배치 OOM). 세션 rule 전수 임베딩 비용 무시 가능(91개 ≈ 3.4s).
- 하드 비용 상한 없음. 안전망으로 세션 rule 수 soft-cap(초과 시 top-K) 정도만(정밀도/recall 무저하).

## M7. 관측성 (헌법 IV / 044 C7)
- 매핑 결과가 0건이거나 후보가 0이면 **경고 로그**(조용한 no-op 금지). "모듈 0개라 전탈락" 같은 silent empty 경로 제거.

## 불변(이 계약이 바꾸지 않는 것)
- 생산자(analyzer) 그래프/스키마, `REALIZED_BY` 관계, 검증기/중재/SSE/저장 인터페이스, 프론트.
