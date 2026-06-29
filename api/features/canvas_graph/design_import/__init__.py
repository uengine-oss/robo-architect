"""044 완성 설계 Import — 완성된 이벤트스토밍 설계 문서를 LLM 없이 결정론적으로
파싱(parser)하여 도메인 모델 그래프에 그대로 적재(importer)한다. Design 탭의
빅픽처/캔버스 스키마(BC-HAS_AGGREGATE->Aggregate-HAS_COMMAND->Command-EMITS->Event,
BC-HAS_POLICY->Policy, Event-TRIGGERS->Policy-INVOKES->Command)로 수렴한다.
"""
