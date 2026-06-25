# 아키텍처 계획 계약 (Architecture Plan)

Constitution 에 일관되게 5개 **필수 항목**을 결정한다. 각 항목은 결정되거나 `constitutionGaps` 에 명시되어야 한다(조용한 누락 금지, SC-003).

| aspect | 무엇 | MONOLITH 일 때 |
|--------|------|----------------|
| `DEPLOYMENT_ENV` | 배포 환경(예: Kubernetes, VM, serverless, 단일 호스트) | 단일 배포 대상으로 결정 |
| `INGRESS` | 외부 진입(예: nginx ingress, ALB, API gateway) | 보통 "N/A (monolith)" 또는 단일 리버스 프록시 |
| `SERVICE_MESH_FRAMEWORK` | 서비스 간 통신/프레임워크(예: Istio, Spring Cloud, gRPC; 모놀리스면 앱 프레임워크) | 앱 프레임워크만(메시 불필요 → "N/A") |
| `FRONTEND` | 프론트엔드 스택(예: Vue 3 + Vite, React, 없음) | 동일 |
| `REPO_MAPPING` | 서비스↔레포 매핑(`repoStrategy`/`repoMode` 존중) | 단일 레포/모듈 매핑 |

## 추적성 (FR-014)
각 결정의 `constitutionRef` 는 그 결정을 정당화하는 Constitution 섹션을 가리킨다. 정당화할 섹션이 없으면(=헌장이 침묵) `constitutionRef:null` 로 두고 그 aspect 를 `constitutionGaps` 에도 추가한다.

## 모놀리스 규칙 (FR-012)
`architectureStyle == MONOLITH` 이면 마이크로서비스 전용 인프라(독립 ingress per service, service mesh)를 **지어내지 않는다**. 불필요한 항목은 `decision: "N/A (monolith)"` 로 명시한다 — 빈 값으로 누락하지 말 것.

## 마이크로서비스 의존 항목
`architectureStyle == MICROSERVICES` 이면 INGRESS(게이트웨이)·SERVICE_MESH_FRAMEWORK·REPO_MAPPING 이 실질적 결정이 되어야 한다. 이들은 Constitution 의 배포환경/레포전략과 모순되지 않아야 한다.

## 완전성 판정
`{각 decision.aspect} ∪ {constitutionGaps}` 가 5개 필수 항목을 모두 포함하면 plan 은 complete. 백엔드 `ImplementationPlan.is_complete()` 와 일치한다.
