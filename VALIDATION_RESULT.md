# Legacy Report Ingestion 정합성 검증 결과 (3차 — SB-level US 생성 적용)

> **검증일**: 2026-03-13
> **입력**: `requirement_sample/analysis_report_final.report.md` (금융 융자 EJB 레거시 분석 보고서)
> **변경 사항**: Session Bean별 개별 US 생성, EJB lifecycle 필터, Command 중복방지, Query→Command 방지, 파일명 기반 자동 감지
> **비교 대상**: Neo4j에 생성된 Event Storming 모델 vs 보고서 원본 내용

---

## 1. 생성 요약

| 구성요소 | 2차 결과 | 3차 결과 | 변화 |
|:---------|-------:|-------:|:-----|
| UserStory | 20 | **80** | +300% |
| BoundedContext | 3 | **10** | +233% |
| Aggregate | 3 | **13** | +333% |
| Command | 17 | **37** | +118% |
| Event | 19 | **41** | +116% |
| Policy | 6 | **7** | +17% |
| ReadModel | 9 | **27** | +200% |
| GWT | 17 | **37** | +118% |
| UI | 0 | **53** | 신규 |
| Property | 190 | **735** | +287% |
| **TOTAL** | **284** | **1,040** | **+266%** |

---

## 2. 도메인 커버리지 검증

### 2.1 Session Bean → BC 매핑

| Report Session Bean | 비즈니스 CMD | 생성된 BC | 커버 |
|:-------------------|:------------|:---------|:-----|
| LoanApplicationSB | createApp, submit, cancel, update, registerCollateral | LoanApplicationManagement, LoanApplicationProcessing | ✅ |
| LoanExecutionSB | executeLoan | LoanExecutionAndLedgerManagement | ✅ |
| LoanLedgerSB | calculateSchedule, closeLedger | LoanLedgerManagement, LoanExecutionAndLedgerManagement | ✅ |
| LoanProcessSB | requestScreening, submitAndGetResult, cancelProcess | LoanApplicationProcess | ✅ |
| LoanScreeningSB | performScreening | LoanScreening, CreditEvaluation | ✅ |
| DelinquencyMgmtSB | registerDelinquency, resolveDelinquency | DelinquencyManagement | ✅ |
| DebtCollectionSB | initiateCollection, writeOff | DebtCollectionManagement | ✅ |

**도메인 커버리지: 7/7 Session Bean 전체 반영 (2차: 3/7 → 3차: 7/7)** ✅

### 2.2 Entity Bean → Aggregate 매핑

| Report Entity Bean | 테이블 | 생성된 Aggregate | 커버 |
|:-------------------|:-------|:----------------|:-----|
| LoanApplicationBean | LOAN_APPLICATION | LoanApplication (2개 BC) | ✅ |
| LoanLedgerBean | LOAN_LEDGER | LoanLedger (2개 BC) | ✅ |
| RepaymentBean | REPAYMENT | Repayment | ✅ |
| CollateralBean | COLLATERAL | Collateral | ✅ |
| CreditRatingBean | CREDIT_RATING_ENTITY | CreditRating | ✅ |
| DelinquencyBean | DELINQUENCY | DelinquencyCase, Delinquency | ✅ |
| CustomerBean | CUSTOMER | — | ⚠️ 독립 Aggregate 없음 (다른 Agg에서 참조) |

**Entity Bean 커버리지: 6/7 직접 매핑 (2차: 1/7 → 3차: 6/7)** ✅

---

## 3. UserStory 검증

### 3.1 수량 및 품질

- **총 80개 US 생성** (2차: 20개)
- 7개 Session Bean 전부에서 US가 생성됨
- EJB lifecycle US: **0개** (2차: 7개) ✅ 완전 제거

### 3.2 SB별 US 커버리지 (샘플)

| Session Bean | 주요 US 생성 확인 | 평가 |
|:------------|:-----------------|:-----|
| DebtCollectionSB | initiateCollection, writeOff, getCollectionTargets, getWrittenOffLedgers | ✅ |
| DelinquencyMgmtSB | registerDelinquency, resolveDelinquency, calculateTotalPenalty | ✅ |
| LoanApplicationSB | create, submit, cancel, update, registerCollateral, 조회들 | ✅ |
| LoanExecutionSB | executeLoan, getLedger, getLedgersByCustomer | ✅ |
| LoanLedgerSB | calculateSchedule, closeLedger, getActiveLedgers | ✅ |
| LoanProcessSB | requestScreening, submitAndGetResult, cancelProcess, initialize | ✅ |
| LoanScreeningSB | performScreening, getCreditScreening | ✅ |

### 3.3 US 이슈

| 이슈 | 건수 | 설명 |
|:-----|-----:|:-----|
| 과도한 세분화 | ~15건 | LoanLedgerSB의 repayment 로직이 세부 단계별로 쪼개짐 (e.g., "generate repayment id", "record timestamp", "calculate total") |
| 에러 처리 US | ~8건 | "rollback transaction and display exception message" 류의 기술 US |
| 비즈니스 핵심 | ~57건 | 실제 비즈니스 가치를 반영하는 US |

**비즈니스 US 비율: ~71% (2차: 65%)** — 개선됨

---

## 4. BoundedContext 검증

### 4.1 생성된 BC 목록

| BC | displayName | 평가 |
|:---|:-----------|:-----|
| LoanApplicationManagement | 대출 신청 관리 | ✅ 핵심 |
| LoanApplicationProcessing | 대출 신청 처리 | ⚠️ LoanApplicationManagement와 중복 가능 |
| LoanApplicationProcess | 대출 신청 프로세스 | ⚠️ LoanProcessSB 대응이나 위 2개와 유사 |
| LoanApproval | 대출 승인 | ✅ 승인/거절 분리 |
| LoanScreening | 대출 심사 | ✅ 핵심 |
| CreditEvaluation | 신용 평가 | ⚠️ LoanScreening과 유사 |
| LoanExecutionAndLedgerManagement | 대출 실행 및 원장 관리 | ✅ 핵심 |
| LoanLedgerManagement | 대출 원장 관리 | ⚠️ 위와 중복 가능 |
| DelinquencyManagement | 연체 관리 | ✅ 핵심 |
| DebtCollectionManagement | 채권 추심 관리 | ✅ 핵심 |

### 4.2 BC 이슈

| 이슈 | 설명 |
|:-----|:-----|
| **BC 과다 분할** | 10개 BC는 보고서 규모 대비 많음. 이상적으로는 5-6개 (LoanApplication, LoanExecution/Ledger, Screening/Approval, Delinquency, Collection) |
| **유사 BC 중복** | LoanApplicationManagement / LoanApplicationProcessing / LoanApplicationProcess 3개가 유사 도메인 |
| **EJB 인프라 BC** | 0개 ✅ (2차: InfrastructureResourceManagement 있었음) |

**원인**: SB별 개별 US 생성으로 각 SB가 독립 BC를 형성하는 경향. BC 병합 로직이 충분히 강하지 않음.

---

## 5. Aggregate 검증

### 5.1 생성된 Aggregate

| BC | Aggregate | displayName | 평가 |
|:---|:----------|:-----------|:-----|
| LoanApplicationManagement | LoanApplication | 여신신청 | ✅ |
| LoanApplicationProcessing | LoanApplication | 여신신청 | ⚠️ 위와 중복 이름 |
| LoanApplicationProcess | LoanApplicationProcess | 여신신청 프로세스 | ✅ Stateful SB 대응 |
| LoanApproval | LoanApproval | 여신 승인 | ✅ |
| LoanScreening | ScreeningResult | 심사 결과 | ✅ |
| CreditEvaluation | CreditRating | 신용등급 | ✅ CreditRatingBean 대응 |
| LoanExecutionAndLedgerMgmt | LoanLedger | 여신 원장 | ✅ LoanLedgerBean 대응 |
| LoanExecutionAndLedgerMgmt | Repayment | 상환 내역 | ✅ RepaymentBean 대응 |
| LoanExecutionAndLedgerMgmt | Collateral | 담보 정보 | ✅ CollateralBean 대응 |
| LoanExecutionAndLedgerMgmt | Delinquency | 연체 정보 | ⚠️ DelinquencyManagement BC에도 있어야 |
| LoanLedgerManagement | LoanLedger | 여신원장 | ⚠️ 위와 중복 |
| DelinquencyManagement | DelinquencyCase | 연체 건 | ✅ DelinquencyBean 대응 |
| DebtCollectionManagement | CollectionCase | 추심 사례 | ✅ |

**Aggregate 커버리지: 13개 생성 (2차: 3개). 보고서 Entity Bean 6/7 직접 매핑됨.**

### 5.2 Aggregate 이슈

| 이슈 | 건수 | 설명 |
|:-----|-----:|:-----|
| 동일 이름 다른 BC | 2건 | LoanApplication(2개 BC), LoanLedger(2개 BC) |
| Delinquency 분산 | 2건 | Delinquency + DelinquencyCase가 다른 BC에 배치 |
| CustomerBean 누락 | 1건 | 독립 Aggregate로 생성되지 않음 |

---

## 6. Command 검증

### 6.1 보고서 비즈니스 메서드 → Command 매핑

| Session Bean | 보고서 CMD 메서드 | 생성된 Command | 매핑 |
|:------------|:-----------------|:-------------|:-----|
| LoanApplicationSB | createApplication | CreateLoanApplication | ✅ |
| | submitApplication | SubmitLoanApplication | ✅ |
| | cancelApplication | CancelLoanApplication | ✅ |
| | updateApplication | UpdateLoanApplication | ✅ |
| | registerCollateral | RegisterCollateral, AddCollateral | ✅ (1건 중복) |
| LoanExecutionSB | executeLoan | ExecuteLoan | ✅ |
| LoanLedgerSB | calculateRemainingSchedule | UpdateLedgerRepaymentSchedule | ✅ |
| | closeLedger | CloseLoanLedger | ✅ |
| LoanProcessSB | requestScreening | RequestLoanScreening | ✅ |
| | submitAndGetResult | SubmitAndRetrieveResult | ✅ |
| | cancelProcess | CancelLoanApplicationProcess | ✅ |
| LoanScreeningSB | performScreening | PerformScreening | ✅ |
| DelinquencyMgmtSB | registerDelinquency | RegisterDelinquency (2건) | ✅ (중복) |
| | resolveDelinquency | ResolveDelinquency (2건) | ✅ (중복) |
| DebtCollectionSB | initiateCollection | InitiateCollection, InitiateCollectionCase | ✅ (중복) |
| | writeOff | WriteOffDelinquency, WriteOffCollectionCase | ✅ |

**비즈니스 CMD 매핑: 16/16 (100%)** ✅ (2차: ~8/16)

### 6.2 Command 이슈

| 이슈 | 건수 | 설명 |
|:-----|-----:|:-----|
| Cross-aggregate 중복 | 5건 | RegisterDelinquency(2), ResolveDelinquency(2), RegisterCollateral/AddCollateral, InitiateCollection/InitiateCollectionCase, ProcessCollectionPayment/ReceiveCollectionPayment |
| EJB lifecycle Command | **0건** | ✅ 완전 제거 (2차: 3건) |
| Query→Command 오분류 | **0건** | ✅ 완전 제거 (2차: 3건) |
| 추가 생성 Command | ~10건 | 보고서에 직접 대응 없으나 비즈니스적으로 유의미 (ApplyRepaymentToLedger, RecordCreditRating 등) |

---

## 7. Event 검증

- **41개 Event 생성** (2차: 19개)
- Command 37개 대비 41개 → 일부 Command가 2개 Event(성공/실패) 생성
- 이름 규칙(과거분사) 준수 ✅

| 이슈 | 건수 | 설명 |
|:-----|-----:|:-----|
| 중복 Event 이름 | 2건 | DelinquencyStatusUpdated(2), LoanApplicationSubmitted(2) — cross-aggregate 중복 Command 때문 |
| 실패 Event | 3건 | RepaymentApplicationFailed, LoanLedgerClosureFailed, LedgerRepaymentScheduleUpdateFailed — 비즈니스적으로 유의미 ✅ |
| EJB Event | **0건** | ✅ 완전 제거 |

---

## 8. Policy 검증

| Policy | displayName | 평가 |
|:-------|:-----------|:-----|
| InitiateCollectionCaseOnCollectionInitiated | 추심 개시 시 추심 케이스 생성 | ✅ |
| ProcessCollectionPaymentOnCollectionPaymentReceived | 추심 결제 수령 시 결제 처리 | ✅ |
| RegisterDelinquencyCaseOnDelinquencyRegistered | 연체 등록 시 연체 케이스 생성 | ✅ |
| ResolveDelinquencyCaseOnDelinquencyResolved | 연체 해결 시 케이스 해결 처리 | ✅ |
| UpdateDelinquencyCaseStatusOnDelinquencyStatusUpdated | 연체 상태 변경 시 케이스 상태 갱신 | ✅ |
| WriteOffCollectionCaseOnDelinquencyWrittenOff | 연체 상각 시 추심 케이스 상각 | ✅ |
| WriteOffDelinquencyOnCollectionCaseWrittenOff | 추심 케이스 상각 시 연체 상각 처리 | ✅ |

**Policy 7개 모두 비즈니스적으로 유의미.** ✅
특히 Delinquency ↔ Collection 간 cross-BC 연계가 잘 모델링됨.

---

## 9. ReadModel 검증

- **27개 ReadModel 생성** (2차: 9개)

### 9.1 보고서 Query 메서드 → ReadModel 매핑 (주요)

| Session Bean Query | 생성된 ReadModel | 매핑 |
|:------------------|:----------------|:-----|
| getApplication | LoanApplicationDetail (3건) | ✅ (중복) |
| getAllApplications | LoanApplicationList (2건) | ✅ (중복) |
| getApplicationsByStatus | LoanApplicationListByStatus | ✅ |
| getLedger | LoanLedgerDetail (2건) | ✅ (중복) |
| getActiveLedgers | ActiveLoanLedgerList | ✅ |
| getLedgersByCustomer | CustomerLoanLedgerList, LoanLedgerListByCustomer | ✅ |
| getDelinquency | DelinquencyDetail | ✅ |
| getDelinquenciesByCustomer | CustomerDelinquencyList | ✅ |
| getActiveDelinquencies | ActiveDelinquencyList | ✅ |
| calculateTotalPenalty | LedgerPenaltySummary | ✅ |
| getCollectionTargets | CollectionTargetList | ✅ |
| getCollectionDetail | CollectionDetail | ✅ |
| getWrittenOffLedgers | WrittenOffLedgerList | ✅ |
| getCreditScreening | CreditScreeningResult, CustomerCreditRating | ✅ |

**Query 메서드 커버리지: 14/14 (100%)** ✅

### 9.2 ReadModel 이슈

| 이슈 | 건수 | 설명 |
|:-----|-----:|:-----|
| 동일 이름 중복 | 3건 | LoanApplicationDetail(3), LoanApplicationList(2), LoanLedgerDetail(2) — BC 분산 때문 |
| 비즈니스 외 RM | **0건** | ✅ (2차: ResourceSessionStatus 1건 있었음) |

---

## 10. UI 검증

- **53개 UI 생성** (2차: 0개 표시)
- Command UI 37개 중 다수 + ReadModel UI 전체에 대해 와이어프레임 생성
- Policy에 의해 호출되는 Command는 자동 UI 제외 처리됨 ✅

---

## 11. 종합 평가

### 2차 → 3차 개선 현황

| 항목 | 2차 | 3차 | 변화 |
|:-----|:----|:----|:-----|
| 도메인 커버리지 | 3/7 SB (43%) | **7/7 SB (100%)** | ✅ 완전 해결 |
| Entity Bean → Aggregate | 1/7 (14%) | **6/7 (86%)** | ✅ 대폭 개선 |
| 비즈니스 CMD 매핑 | ~8/16 (50%) | **16/16 (100%)** | ✅ 완전 해결 |
| Query→ReadModel 매핑 | ~5/14 (36%) | **14/14 (100%)** | ✅ 완전 해결 |
| EJB lifecycle US | 7건 (35%) | **0건 (0%)** | ✅ 완전 제거 |
| EJB lifecycle Command | 3건 | **0건** | ✅ 완전 제거 |
| Query→Command 오분류 | 3건 | **0건** | ✅ 완전 제거 |
| 총 노드 수 | 284 | **1,040** | +266% |

### 잔존 이슈

| 우선순위 | 이슈 | 근본 원인 | 영향 |
|:---------|:-----|:---------|:-----|
| **P2** | BC 과다 분할 (10개 → 이상적 5-6개) | SB별 개별 US가 독립 BC를 형성하는 경향 | BC 병합 로직 강화 필요 |
| **P2** | Cross-aggregate Command 중복 5건 | BC 중복으로 동일 도메인이 2개 BC에 배치 | BC 병합 시 자동 해소 예상 |
| **P2** | ReadModel 동일 이름 중복 3건 | BC 중복의 파생 이슈 | BC 병합 시 자동 해소 예상 |
| **P3** | US 과도한 세분화 (~15건) | LLM이 메서드 내부 단계를 개별 US로 분리 | US 생성 프롬프트에 granularity 지침 추가 |
| **P3** | 에러 처리 US (~8건) | exception handling 로직이 US로 생성 | 프롬프트에 에러 처리 US 제외 규칙 추가 |
| **P3** | CustomerBean 독립 Aggregate 미생성 | Customer가 다른 Aggregate에서 참조만 됨 | 비즈니스 판단에 따라 허용 가능 |

### 핵심 성과

**SB-level US 생성이 cascading data starvation 문제를 근본적으로 해결.**
모든 하위 phase (BC → Aggregate → Command → Event → Policy → ReadModel → UI → Property)가 풍부한 입력을 받아 보고서의 전체 비즈니스 도메인을 커버하는 모델을 생성함.

다음 개선 우선순위는 **BC 병합 로직 강화** (P2) — 이를 해결하면 cross-aggregate 중복 Command/ReadModel도 자동으로 해소됨.
