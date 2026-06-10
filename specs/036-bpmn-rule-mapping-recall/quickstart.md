# Quickstart: 골든 픽스처 A/B 측정 & 검증

목표: 용어 정규화가 **회귀 0건 + 어휘갭 누락 ≥1건 회복**(SC-001), **사용자 노출 항목 불변**(SC-002), **소요시간 ≤1.2x**(SC-003)를 만족하는지 확인.

## 전제: 골든 픽스처

- 평문 입력: `/Users/seongwon/Desktop/robo/input_resource/업무Flow_초안_자동납부_본인확인_요청처리.pdf`, `..._결과처리.pdf`
- 분석 그래프: 동일 도메인 레거시 C(`zapamcom10060.c`, `zapamcom10140.c`)가 분석되어 적재된 neo4j (`analyzer-2026-05-11T12-41-12.dump` 복원).
- 이 도메인은 평문("본인확인")↔코드 약어("zapamcom") 어휘갭이 실재 → 정규화 효과가 드러나는 픽스처.

## Q1. 분석 그래프 적재 (1회)

```bash
# analyzer dump를 분석 DB로 복원 (기존 운영 절차에 따름)
# 결과: neo4j ANALYZER DB에 FUNCTION/Rule/Table 노드 존재
```

## Q2. 베이스라인(off) 매핑

```bash
HYBRID_GLOSSARY_NORMALIZE=0 python3 specs/036-bpmn-rule-mapping-recall/manual/run_mapping.py \
  --pdf input_resource/...요청처리.pdf input_resource/...결과처리.pdf \
  --out /tmp/036_baseline.json
```
- 산출: 활동별 accept 매핑 + 사용자 노출 항목 수 + wall-clock.

## Q3. 정규화(on) 매핑

```bash
HYBRID_GLOSSARY_NORMALIZE=1 python3 specs/036-bpmn-rule-mapping-recall/manual/run_mapping.py \
  --pdf input_resource/...요청처리.pdf input_resource/...결과처리.pdf \
  --out /tmp/036_normalized.json
```

## Q4. diff & 판정

```bash
python3 specs/036-bpmn-rule-mapping-recall/manual/compare.py \
  --baseline /tmp/036_baseline.json --normalized /tmp/036_normalized.json
```
판정 기준:
- **회복(recovered) ≥ 1**: on에만 있는 (task, rule) 쌍 ≥ 1 → SC-001 충족.
- **회귀(regressed) = 0**: off에 있던 매핑이 on에서 사라진 쌍 0 → SC-001/SC-004 충족.
- **user_visible_delta ≤ 0**: 사용자 노출 항목 수 증가 없음 → SC-002 충족.
- **wall_clock_ratio ≤ 1.2** → SC-003 충족.

## Q5. 폴백 회귀 (glossary 빈 경우)

```bash
# glossary 추출을 강제로 빈 목록으로 만든 경로(또는 LLM 키 미설정)에서 실행
HYBRID_GLOSSARY_NORMALIZE=1 ... run_mapping.py   # glossary=[] → 정규화 미적용
```
- 기대: 오류 없이 완료, baseline(off)과 매핑 결과 동일(회귀 0) → SC-004.

## Q6. 단위 테스트

```bash
cd api && python3 -m pytest features/ingestion/hybrid/mapper/tests/test_term_normalizer.py -q
```
- normalize_query/normalize_rule_blob: 매칭 시 토큰 덧붙임, 미매칭/빈 glossary 시 원문·`applied=False`, 토큰 상한 준수, 결정성.

## Q7. 회귀 가드 (전체 매퍼)

```bash
cd api && python3 -m pytest features/ingestion/hybrid/mapper/tests/ -q
```
- `HYBRID_GLOSSARY_NORMALIZE=0`에서 기존 테스트 전부 통과(바이트 동일 경로 보장).

## Out-of-band

- 언어 정책(spec 031), 신규 노드/관계 스키마 diff 0건 회귀, SSE 이벤트 형태 불변(프런트 무변경) 확인.
