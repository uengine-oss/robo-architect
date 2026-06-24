# Constitution 인터뷰 — 의존성 인지 + 최소 질문

목표: **같은 헌장을 만들되 질문 수를 최소화**한다. 질문들은 독립적이지 않다 — 한 답이 뒤따르는 질문 묶음을 **열거나 닫는다**. 각 영역은 **(a) 프롬프트 시드 → (b) 적합성 추천 → (c) 정말 분기가 있을 때만 질문** 순으로 처리한다.

## 질문 의존 트리

```
[Q1] 아키텍처 스타일?  MONOLITH | MICROSERVICES   ← 가장 상위 분기(복잡성 게이트)
  │
  ├─ MONOLITH ──────────────────────────────────────────────┐
  │     · ingress/게이트웨이 질문   → 생략 (단일 진입)         │
  │     · service mesh 질문         → 생략 (앱 프레임워크로 수렴)│
  │     · repo-per-service 질문     → 생략 (단일 레포 고정)     │
  │     · 배포 대상                 → 단일 배포로 추천, 보통 생략 │
  │     ⇒ 남는 실질 질문: 기술스택(1) + 설계원칙(있으면)        │
  │
  └─ MICROSERVICES ──────────────────────────────────────────┐
        [Q2] 배포 대상?  (k8s | VM | serverless | …)           │
        [Q3] 진입/게이트웨이?  (ingress | API gateway | …)      │
        [Q4] 서비스 간 통신/메시?  (mesh | 프레임워크 | 직접호출)│
        [Q5] 레포 전략?  MONOREPO | REPO_PER_SERVICE            │
              └─ REPO_PER_SERVICE 이면만 → [Q5b] split-git | reuse-existing
        ⇒ 단, Q2~Q4 중 프롬프트/추천으로 확정되는 것은 질문하지 않음
```

## 최소화 규칙
1. **상위 분기 먼저** — Q1(아키텍처 스타일)을 가장 먼저 가늠한다. 이게 닫히면 하위 질문 묶음 전체가 사라진다.
2. **시드로 건너뛰기** — 프롬프트에 이미 답이 있으면(예: "nginx ingress", "Kafka", "Vue") 질문하지 말고 `[제안]` 으로 표시.
3. **추천으로 건너뛰기** — 의도상 합리적 기본값이 명확하면 `[추천]` 으로 제시하고 수락받는다(질문 1회를 추천 수락 1회로 대체).
4. **조건부 후속만** — repoMode 는 REPO_PER_SERVICE 일 때만, Q2~Q4 는 MICROSERVICES 일 때만.
5. **복잡성 최소점 존중** — 사용자가 단순하게 가려 하면(작은 BC·CRUD·소규모 팀 신호) MONOLITH 를 추천해 전체 질문을 최소화. 사용자가 분명히 분산/확장을 원할 때만 MICROSERVICES 분기를 연다.

## 4개 필수 결정 영역 (수렴 목표)
- **designPrinciples** — 핵심 설계 원칙. 도메인 위험도(결제/의료→보안·감사) 기반 추천.
- **techStack** — 백엔드/프론트/스토어. 프롬프트 시드 + 기존 레포 스택 우선.
- **architectureStyle** — MONOLITH | MICROSERVICES (Q1, 복잡성 게이트).
- **repoStrategy (+repoMode)** — MONOREPO | REPO_PER_SERVICE; 후자만 split-git/reuse-existing.

## 진행 규칙
- 한 번에 한 질문(`event: question`), 선택지 제공. 추천 항목은 기본 선택으로 강조.
- 묶음이 닫힌 영역(예: 모놀리스의 ingress)은 헌장 본문에 "N/A (monolith)" 로만 남기고 묻지 않는다.
- 4개 영역이 (질문/시드/추천 어떤 경로로든) 확정되면 `action:"done"` + `raw` 출력.
