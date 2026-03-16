# 레거시 시스템 분석 보고서

> **분석 대상**: 금융 융자(대출) EJB 레거시 애플리케이션
> **파이프라인**: Framework (Java EJB) | **생성일**: 2026-03-12
>
> 이 문서는 소스코드 정적 분석 파이프라인이 Neo4j 그래프 데이터를 기반으로 자동 생성한 결과물이다.
> 클린 아키텍처 전환 시 현행 시스템의 구조, 관계, 데이터 흐름을 파악하기 위한 입력 문서로 활용된다.

---

## 1. 시스템 전체 조감도

이 시스템은 금융 대출 심사와 실행을 처리하는 EJB 애플리케이션이다.
웹 요청이 **Servlet**으로 들어오면, **Session Bean**이 비즈니스 로직을 수행하고, **Entity Bean(CMP)** 이 데이터베이스 테이블과 1:1 매핑되어 데이터를 읽고 쓴다.

```
[Browser] → Servlet(3) → Session Bean(5) → Entity Bean(8) → DB Table(12)
                              ↓                                  ↑
                         비즈니스 규칙              CMP 자동 매핑
                     (심사/실행/알림)          (CUSTOMER, LOAN_APPLICATION, ...)
```

### 수치 요약

| 구분 | 항목 | 수량 |
|:-----|:-----|-----:|
| 코드 구조 | 패키지 | 5 |
| | 클래스 / 인터페이스 / 열거형 (INTERNAL) | 37 / 2 / 1 |
| | 외부 참조 (EXTERNAL) | 13 |
| | 메서드 | 320 |
| | 필드 | 180 |
| 데이터베이스 | 테이블 | 12 |
| | 컬럼 | 87 |
| 설정/쿼리 | 설정 파일 (NONTARGET_FILE) | 4 |
| | 쿼리 블록 (NONTARGET_BLOCK) | 15 |
| 관계 | 구조적 (HAS_METHOD, HAS_FIELD, BELONGS_TO_PACKAGE 등) | 662 |
| | UML (EXTENDS, IMPLEMENTS, ASSOCIATION, DEPENDENCY) | 42 |
| | 의존성 (CALLS, USES) | 142 |
| | DB (FROM, WRITES, FK_TO_TABLE, FK_TO, REFERS_TO) | 52 |
| | **총 관계** | **898** |

---

## 2. 패키지 구조와 아키텍처 계층

5개 패키지가 전형적인 EJB 3-tier 구조를 따른다. 아래 트리에서 각 패키지의 역할과 규모를 한 눈에 볼 수 있다.

```
com.banking.loan
│
├── servlet/      웹 계층          Servlet 3개 ─ HTTP 요청의 진입점
├── session/      비즈니스 계층     Session Bean 5개 + Interface 1개 ─ 핵심 업무 로직
├── entity/       데이터 계층       Entity Bean(CMP) 8개 ─ DB 테이블 1:1 매핑
├── util/         유틸리티          클래스 2개 + Interface 1개 + Enum 1개
└── common/       공통              클래스 2개
```

---

### 웹 계층: `com.banking.loan.servlet`

HTTP 요청을 받아 Session Bean으로 위임하는 진입점이다. 모든 Servlet이 `HttpServlet`(EXTERNAL)을 상속한다.

| 클래스 | 역할 | 위임 대상 |
|:-------|:-----|:---------|
| LoanScreeningServlet | 대출 심사 요청 | LoanScreeningSessionBean |
| LoanExecutionServlet | 대출 실행 요청 | LoanExecutionSessionBean |
| LoanApplicationServlet | 대출 신청 CRUD | LoanApplicationSessionBean |

---

### 비즈니스 계층: `com.banking.loan.session`

대출의 심사, 실행, 관리를 수행하는 핵심 계층이다.

| 클래스 | 스테레오타입 | 핵심 역할 |
|:-------|:-----------|:---------|
| **LoanScreeningSessionBean** | Stateless | 신용점수/DTI/LTV 기반 대출 심사 |
| **LoanExecutionSessionBean** | Stateless | 승인된 대출 실행, 상환 스케줄 생성 |
| LoanApplicationSessionBean | Stateful | 대출 신청 생성/수정/조회 |
| ReportSessionBean | Stateless | 대출 현황 보고서 생성 |
| NotificationSessionBean | Stateless | 심사 결과/실행 완료 알림 |
| LoanServiceLocal | Interface | 대출 서비스 로컬 인터페이스 |

---

### 데이터 계층: `com.banking.loan.entity`

CMP 방식으로 데이터베이스 테이블과 1:1 매핑되는 Entity Bean이다. 각 Bean이 어떤 테이블과 매핑되는지 함께 표기한다.

| 클래스 | 매핑 테이블 | 역할 |
|:-------|:-----------|:-----|
| CustomerBean | CUSTOMER | 고객 정보 (이름, 주민번호, 연락처, 소득) |
| LoanApplicationBean | LOAN_APPLICATION | 대출 신청 (금액, 상태, 심사 결과) |
| CollateralBean | COLLATERAL | 담보 (유형, 감정가, 담보비율) |
| CreditRatingBean | CREDIT_RATING | 신용등급 (점수, 등급 이력) |
| GuarantorBean | GUARANTOR | 보증인 (연대보증인 정보) |
| RepaymentScheduleBean | REPAYMENT_SCHEDULE | 상환 스케줄 (월별 계획/실적) |
| InterestRateBean | INTEREST_RATE | 금리 (대출 유형별 금리) |
| LoanProductBean | LOAN_PRODUCT | 대출 상품 (상품코드, 최대한도) |

---

## 3. 클래스 상세

각 INTERNAL 클래스의 속성, 메서드, 필드, 관계, 요약 코드를 빠짐없이 기술한다.
모든 정보는 Neo4j 그래프 노드의 속성값에서 추출한 것이다.

---

### 3.1 LoanScreeningSessionBean

> 이 시스템의 핵심 &#8212; **대출 심사** 비즈니스 로직을 담당한다.
> 신용점수 < 700이면 거절, DTI >= 0.40이면 조건부 승인, LTV > 0.80이면 추가 심사를 요구한다.

**기본 정보**

| 속성 | 값 |
|:-----|:---|
| 타입 / 범위 | CLASS / INTERNAL |
| 패키지 | com.banking.loan.session |
| FQN | com.banking.loan.session.LoanScreeningSessionBean |
| 스테레오타입 | Session Bean (Stateless) |
| 파일 | LoanScreeningSessionBean.java (15 ~ 285 line, 2,450 token) |
| 수정자 / 어노테이션 | `public` / `@Stateless` |
| 구현 (implements) | SessionBean, LoanServiceLocal |
| 주석 | 대출 심사 비즈니스 로직을 담당하는 세션 빈 |

**클래스 요약** (`summary` 속성)

> 대출 심사 세션 빈. creditScore < 700이면 거절하고, dtiRatio >= 0.40이면 조건부 승인으로 처리한다.
> LTV 비율이 0.80을 초과하면 추가 담보 심사를 요구한다. 신용등급 조회, DTI 계산, LTV 검증을
> 순차적으로 수행하며, 각 단계의 결과를 LoanApplication 엔티티에 기록한다.

**메서드** (8개)

| # | 이름 | 시그니처 | 반환 | 역할 | 요약 |
|--:|:-----|:--------|:-----|:-----|:-----|
| 1 | performScreening | (Long applicationId) | ScreeningResult | command | 신용점수/DTI/LTV 기준으로 대출 신청을 심사한다. < 700이면 REJECTED, >= 0.40이면 CONDITIONAL, 모두 통과하면 APPROVED |
| 2 | approveApplication | (Long applicationId) | void | command | 심사 통과된 신청을 최종 승인. 상태 APPROVED, 승인일시 기록 |
| 3 | rejectApplication | (Long applicationId, String reason) | void | command | 심사 거절 처리. 상태 REJECTED, 거절 사유 기록 |
| 4 | calculateDTI | (Customer customer) | BigDecimal | query | 총 부채 / 연소득 = DTI 비율 계산 |
| 5 | validateLTV | (Collateral collateral, BigDecimal loanAmount) | boolean | query | 대출금액 / 감정가 <= 0.80 검증 |
| 6 | getCreditScore | (Long customerId) | int | query | CreditRatingBean 통해 최신 신용점수 조회 |
| 7 | ejbCreate | () | void | lifecycle | EJB 생성 시 홈 인터페이스 JNDI 조회 |
| 8 | ejbRemove | () | void | lifecycle | EJB 제거 시 정리 |

**필드** (9개)

| # | 이름 | 타입 | 수정자 | 어노테이션 | 설명 |
|--:|:-----|:-----|:-------|:----------|:-----|
| 1 | AUTO_APPROVE_CREDIT_SCORE | int | private static final | | 자동승인 기준값 = 700 |
| 2 | AUTO_APPROVE_DTI_LIMIT | BigDecimal | private static final | | DTI 한도 = 0.40 |
| 3 | MAX_LTV_RATIO | BigDecimal | private static final | | 최대 LTV = 0.80 |
| 4 | CONDITIONAL_CREDIT_SCORE | int | private static final | | 조건부 승인 기준 = 650 |
| 5 | customerHome | CustomerBeanHome | private | @EJB | 고객 엔티티 홈 |
| 6 | creditRatingHome | CreditRatingBeanHome | private | @EJB | 신용등급 엔티티 홈 |
| 7 | collateralHome | CollateralBeanHome | private | @EJB | 담보 엔티티 홈 |
| 8 | applicationHome | LoanApplicationBeanHome | private | @EJB | 대출신청 엔티티 홈 |
| 9 | sessionContext | SessionContext | private | @Resource | 세션 컨텍스트 |

**UML 관계**

| 방향 | 관계 | 대상 | 범위 | 비고 |
|:-----|:-----|:-----|:-----|:-----|
| -> | IMPLEMENTS | SessionBean | EXTERNAL | |
| -> | IMPLEMENTS | LoanServiceLocal | INTERNAL | |
| -> | ASSOCIATION | CustomerBean | INTERNAL | 필드: customerHome |
| -> | ASSOCIATION | LoanApplicationBean | INTERNAL | 필드: applicationHome |
| -> | ASSOCIATION | CreditRatingBean | INTERNAL | 필드: creditRatingHome |
| -> | ASSOCIATION | CollateralBean | INTERNAL | 필드: collateralHome |
| -> | DEPENDENCY | ScreeningResult | INTERNAL | 반환타입 |
| <- | DEPENDENCY | LoanScreeningServlet | INTERNAL | 호출자 |

**호출 관계** (CALLS)

이 클래스가 호출하는 메서드:

| 대상 | scope |
|:-----|:------|
| CustomerBean.findByPrimaryKey(Long) | internal |
| CreditRatingBean.getLatestRating(Long) | internal |
| CreditRatingBean.findByCustomer(Long) | internal |
| CollateralBean.findByApplication(Long) | internal |
| LoanApplicationBean.findByPrimaryKey(Long) | internal |
| LoanApplicationBean.setStatus(String) | internal |
| LoanApplicationBean.setApprovalDate(Date) | internal |
| LoanApplicationBean.setRejectionReason(String) | internal |

이 클래스를 호출하는 메서드:

| 호출자 | scope |
|:-------|:------|
| LoanScreeningServlet.doPost(HttpServletRequest, HttpServletResponse) | internal |

**테이블 접근** (FROM / WRITES)

| 테이블 | 접근 | 증거 (`evidence`) |
|:-------|:-----|:-----------------|
| LOAN_APPLICATION | FROM | `SELECT la.* FROM LOAN_APPLICATION la WHERE la.application_id = ?` |
| LOAN_APPLICATION | WRITES | `UPDATE LOAN_APPLICATION SET status = ?, approval_date = ? WHERE application_id = ?` |
| CUSTOMER | FROM | `SELECT c.* FROM CUSTOMER c WHERE c.customer_id = ?` |
| CREDIT_RATING | FROM | `SELECT cr.credit_score FROM CREDIT_RATING cr WHERE cr.customer_id = ? ORDER BY cr.rating_date DESC` |
| COLLATERAL | FROM | `SELECT col.* FROM COLLATERAL col WHERE col.application_id = ?` |

**요약 코드** (`summarized_code` 속성)

```java
public class LoanScreeningSessionBean implements SessionBean, LoanServiceLocal {
    // 상수: AUTO_APPROVE_CREDIT_SCORE=700, CONDITIONAL_CREDIT_SCORE=650,
    //       AUTO_APPROVE_DTI_LIMIT=0.40, MAX_LTV_RATIO=0.80
    // 필드: customerHome, creditRatingHome, collateralHome, applicationHome

    performScreening(applicationId):
        app = applicationHome.findByPrimaryKey(applicationId)
        customer = customerHome.findByPrimaryKey(app.customerId)
        creditScore = creditRatingBean.getLatestRating(customer)
        if creditScore < 650 -> rejectApplication(applicationId, "신용점수 미달")
        dtiRatio = calculateDTI(customer)
        if dtiRatio >= 0.40 -> app.status = "CONDITIONAL"
        collateral = collateralHome.findByApplication(applicationId)
        if !validateLTV(collateral, app.loanAmount) -> app.status = "ADDITIONAL_REVIEW"
        else -> approveApplication(applicationId)

    approveApplication(applicationId):
        app.status = "APPROVED", app.approvalDate = now()

    rejectApplication(applicationId, reason):
        app.status = "REJECTED", app.rejectionReason = reason

    calculateDTI(customer): return customer.totalDebt / customer.annualIncome
    validateLTV(collateral, loanAmount): return (loanAmount / collateral.appraisalValue) <= 0.80
}
```

---

### 3.2 LoanApplicationBean

> **대출 신청 데이터 모델** &#8212; 신청의 전체 생명주기를 관리한다.
> DRAFT -> SUBMITTED -> APPROVED / REJECTED -> ACTIVE -> CLOSED

**기본 정보**

| 속성 | 값 |
|:-----|:---|
| 타입 / 범위 | CLASS / INTERNAL |
| 패키지 | com.banking.loan.entity |
| FQN | com.banking.loan.entity.LoanApplicationBean |
| 스테레오타입 | Entity Bean (CMP) |
| 파일 | LoanApplicationBean.java (8 ~ 195 line, 1,820 token) |
| 수정자 / 어노테이션 | `public abstract` / `@Entity` |
| 구현 (implements) | EntityBean |
| 주석 | 대출 신청 정보를 관리하는 CMP 엔티티 빈 |

**클래스 요약** (`summary` 속성)

> 대출 신청 엔티티 빈. 신청ID, 고객ID, 대출금액, 상태(DRAFT->SUBMITTED->APPROVED/REJECTED),
> 신청일, 승인일 등을 CMP 방식으로 관리한다. 상태 전이 시 유효성을 검증하고, 거절 시 사유를 기록한다.

**메서드** (14개)

| # | 이름 | 시그니처 | 반환 | 역할 | 요약 |
|--:|:-----|:--------|:-----|:-----|:-----|
| 1 | getApplicationId | () | Long | getter | 신청 ID 반환 |
| 2 | setApplicationId | (Long) | void | setter | 신청 ID 설정 |
| 3 | getCustomerId | () | Long | getter | 고객 ID 반환 |
| 4 | setCustomerId | (Long) | void | setter | 고객 ID 설정 |
| 5 | getLoanAmount | () | BigDecimal | getter | 대출 금액 반환 |
| 6 | setLoanAmount | (BigDecimal) | void | setter | 대출 금액 설정 |
| 7 | getStatus | () | String | getter | 신청 상태 반환 |
| 8 | setStatus | (String) | void | command | 상태 변경. 유효한 전이인지 검증 후 반영 |
| 9 | getApprovalDate | () | Date | getter | 승인일시 반환 |
| 10 | setApprovalDate | (Date) | void | setter | 승인일시 설정 |
| 11 | getRejectionReason | () | String | getter | 거절 사유 반환 |
| 12 | setRejectionReason | (String) | void | setter | 거절 사유 설정 |
| 13 | ejbCreate | (Long customerId, BigDecimal loanAmount) | Long | lifecycle | 상태를 DRAFT로 초기화, 신청일 설정 |
| 14 | ejbPostCreate | (Long customerId, BigDecimal loanAmount) | void | lifecycle | 엔티티 생성 후 처리 |

**필드** (5개)

| # | 이름 | 타입 | 수정자 | 설명 |
|--:|:-----|:-----|:-------|:-----|
| 1 | STATUS_DRAFT | String | public static final | "DRAFT" |
| 2 | STATUS_SUBMITTED | String | public static final | "SUBMITTED" |
| 3 | STATUS_APPROVED | String | public static final | "APPROVED" |
| 4 | STATUS_REJECTED | String | public static final | "REJECTED" |
| 5 | entityContext | EntityContext | private | 엔티티 컨텍스트 |

**UML 관계**

| 방향 | 관계 | 대상 | 범위 | 비고 |
|:-----|:-----|:-----|:-----|:-----|
| -> | IMPLEMENTS | EntityBean | EXTERNAL | |
| <- | ASSOCIATION | LoanScreeningSessionBean | INTERNAL | 필드: applicationHome |
| <- | ASSOCIATION | LoanExecutionSessionBean | INTERNAL | 필드: applicationHome |
| <- | ASSOCIATION | LoanApplicationSessionBean | INTERNAL | 필드: applicationHome |
| -> | ASSOCIATION | CollateralBean | INTERNAL | 1:N |
| -> | ASSOCIATION | CreditRatingBean | INTERNAL | N:1 (customer 경유) |

**이 클래스를 호출하는 메서드** (CALLS)

| 호출자 | scope |
|:-------|:------|
| LoanScreeningSessionBean.performScreening(Long) | internal |
| LoanScreeningSessionBean.approveApplication(Long) | internal |
| LoanScreeningSessionBean.rejectApplication(Long, String) | internal |
| LoanExecutionSessionBean.executeLoan(Long) | internal |
| LoanApplicationSessionBean.createApplication(Long, BigDecimal) | internal |
| LoanApplicationServlet.doGet(HttpServletRequest, HttpServletResponse) | internal |

**테이블 접근**

| 테이블 | 접근 | 증거 |
|:-------|:-----|:-----|
| LOAN_APPLICATION | FROM | CMP 매핑: 자동 SELECT |
| LOAN_APPLICATION | WRITES | CMP 매핑: 자동 INSERT/UPDATE |

**요약 코드** (`summarized_code` 속성)

```java
public abstract class LoanApplicationBean implements EntityBean {
    // 상수: STATUS_DRAFT="DRAFT", STATUS_SUBMITTED="SUBMITTED",
    //       STATUS_APPROVED="APPROVED", STATUS_REJECTED="REJECTED"
    // CMP 필드: applicationId, customerId, loanAmount, status,
    //           applicationDate, approvalDate, rejectionReason,
    //           creditScoreAtApply, dtiRatio, ltvRatio

    ejbCreate(customerId, loanAmount):
        this.customerId = customerId
        this.loanAmount = loanAmount
        this.status = "DRAFT"
        this.applicationDate = now()

    setStatus(newStatus):
        // 상태 전이 검증: DRAFT -> SUBMITTED -> APPROVED|REJECTED -> ACTIVE -> CLOSED
}
```

---

### 3.3 ~ 3.N 나머지 클래스

이하 모든 INTERNAL 클래스가 위와 동일한 구조(기본 정보 -> 요약 -> 메서드 -> 필드 -> 관계 -> 호출 -> 테이블 접근 -> 요약 코드)로 나열된다.

| # | 클래스 | 계층 | 역할 |
|--:|:-------|:-----|:-----|
| 3.3 | CustomerBean | entity | 고객 정보 관리 |
| 3.4 | CollateralBean | entity | 담보 정보 관리 |
| 3.5 | CreditRatingBean | entity | 신용등급 이력 관리 |
| 3.6 | GuarantorBean | entity | 보증인 정보 관리 |
| 3.7 | RepaymentScheduleBean | entity | 상환 스케줄 관리 |
| 3.8 | InterestRateBean | entity | 금리 정보 관리 |
| 3.9 | LoanProductBean | entity | 대출 상품 관리 |
| 3.10 | LoanExecutionSessionBean | session | 대출 실행 처리 |
| 3.11 | LoanApplicationSessionBean | session | 대출 신청 CRUD |
| 3.12 | ReportSessionBean | session | 보고서 생성 |
| 3.13 | NotificationSessionBean | session | 알림 발송 |
| 3.14 | LoanServiceLocal | session | 서비스 인터페이스 |
| 3.15 | LoanScreeningServlet | servlet | 심사 요청 진입점 |
| 3.16 | LoanExecutionServlet | servlet | 실행 요청 진입점 |
| 3.17 | LoanApplicationServlet | servlet | 신청 요청 진입점 |
| ... | ... | ... | ... |

---

## 4. 외부 의존성 (EXTERNAL)

프로젝트 밖에 있지만 INTERNAL 클래스들이 의존하는 외부 클래스/인터페이스다.
클린 아키텍처 전환 시 **이 목록이 곧 제거하거나 대체해야 할 프레임워크 의존성**이다.

| # | 외부 클래스 | 타입 | 관계 | 사용하는 INTERNAL 클래스 |
|--:|:-----------|:-----|:-----|:----------------------|
| 1 | **SessionBean** | INTERFACE | IMPLEMENTS | LoanScreeningSessionBean, LoanExecutionSessionBean, LoanApplicationSessionBean, ReportSessionBean, NotificationSessionBean |
| 2 | **EntityBean** | INTERFACE | IMPLEMENTS | CustomerBean, LoanApplicationBean, CollateralBean, CreditRatingBean, GuarantorBean, RepaymentScheduleBean, InterestRateBean, LoanProductBean |
| 3 | **HttpServlet** | CLASS | EXTENDS | LoanScreeningServlet, LoanExecutionServlet, LoanApplicationServlet |
| 4 | HttpServletRequest | INTERFACE | DEPENDENCY | LoanScreeningServlet, LoanExecutionServlet, LoanApplicationServlet |
| 5 | HttpServletResponse | INTERFACE | DEPENDENCY | LoanScreeningServlet, LoanExecutionServlet, LoanApplicationServlet |
| 6 | BigDecimal | CLASS | DEPENDENCY | LoanScreeningSessionBean, LoanApplicationBean, CollateralBean, InterestRateBean |
| 7 | EntityContext | INTERFACE | DEPENDENCY | CustomerBean, LoanApplicationBean, CollateralBean, CreditRatingBean |
| 8 | SessionContext | INTERFACE | DEPENDENCY | LoanScreeningSessionBean, LoanExecutionSessionBean |
| 9 | DataSource | INTERFACE | DEPENDENCY | ReportSessionBean |
| 10 | Connection | INTERFACE | DEPENDENCY | ReportSessionBean |
| 11 | PreparedStatement | INTERFACE | DEPENDENCY | ReportSessionBean |
| 12 | ResultSet | INTERFACE | DEPENDENCY | ReportSessionBean |
| 13 | NamingException | CLASS | DEPENDENCY | LoanScreeningSessionBean, LoanExecutionSessionBean |

---

## 5. 설정 파일과 쿼리 블록

Java 소스 외에 파이프라인이 분석한 설정 파일과 SQL 파일이다.
각 파일에서 의미 있는 블록을 추출하고, 블록이 참조하는 테이블을 `REFERS_TO` 관계로 연결했다.

---

### ejb-jar.xml

> `src/main/webapp/WEB-INF/ejb-jar.xml` | 8개 블록

EJB 배포 서술자. Entity Bean의 CMP 매핑과 Session Bean 구성, 보안 역할을 정의한다.

**블록 목록**

| # | 블록명 | 종류 | 라인 | 요약 |
|--:|:-------|:-----|:-----|:-----|
| 1 | CustomerBean-descriptor | entity-descriptor | 12-45 | CustomerBean의 CMP 필드와 JNDI 이름 정의 |
| 2 | LoanApplicationBean-descriptor | entity-descriptor | 46-85 | LoanApplicationBean의 CMP 필드 정의 |
| 3 | CollateralBean-descriptor | entity-descriptor | 86-115 | CollateralBean의 CMP 필드 정의 |
| 4 | CreditRatingBean-descriptor | entity-descriptor | 116-145 | CreditRatingBean의 CMP 필드 정의 |
| 5 | LoanScreeningSession-descriptor | session-descriptor | 146-170 | Stateless 세션 빈 서술자 |
| 6 | LoanExecutionSession-descriptor | session-descriptor | 171-195 | Stateless 세션 빈 서술자 |
| 7 | LoanApplicationSession-descriptor | session-descriptor | 196-220 | Stateful 세션 빈 서술자 |
| 8 | security-constraints | security | 221-250 | 보안 역할 및 메서드 권한 정의 |

**테이블 참조** (REFERS_TO)

| 블록 | 테이블 | 역할 | 신뢰도 | 증거 |
|:-----|:-------|:-----|:-------|:-----|
| CustomerBean-descriptor | CUSTOMER | mapping | HIGH | `<abstract-schema-name>CUSTOMER</abstract-schema-name>` |
| LoanApplicationBean-descriptor | LOAN_APPLICATION | mapping | HIGH | `<abstract-schema-name>LOAN_APPLICATION</abstract-schema-name>` |
| CollateralBean-descriptor | COLLATERAL | mapping | HIGH | `<abstract-schema-name>COLLATERAL</abstract-schema-name>` |
| CreditRatingBean-descriptor | CREDIT_RATING | mapping | HIGH | `<abstract-schema-name>CREDIT_RATING</abstract-schema-name>` |

---

### loan-queries.sql

> `src/main/resources/sql/loan-queries.sql` | 4개 블록

Entity Bean CMP 외에 직접 SQL로 수행하는 쿼리들이다.

**블록 목록**

| # | 블록명 | 라인 | 요약 |
|--:|:-------|:-----|:-----|
| 1 | findOverdueLoans | 1-15 | 연체 대출 목록 조회. 상환예정일 경과 + 상태 ACTIVE |
| 2 | calculateTotalExposure | 17-30 | 고객별 총 대출 노출액 계산 |
| 3 | insertRepaymentRecord | 32-40 | 상환 실적 기록 |
| 4 | updateLoanStatus | 42-50 | 대출 상태 변경 |

**테이블 참조** (REFERS_TO)

| 블록 | 테이블 | 역할 | 증거 |
|:-----|:-------|:-----|:-----|
| findOverdueLoans | LOAN_APPLICATION | source | `SELECT la.* FROM LOAN_APPLICATION la` |
| findOverdueLoans | REPAYMENT_SCHEDULE | source | `JOIN REPAYMENT_SCHEDULE rs ON la.application_id = rs.application_id` |
| calculateTotalExposure | LOAN_APPLICATION | source | `SELECT SUM(loan_amount) FROM LOAN_APPLICATION` |
| insertRepaymentRecord | REPAYMENT_SCHEDULE | target | `INSERT INTO REPAYMENT_SCHEDULE` |
| updateLoanStatus | LOAN_APPLICATION | target | `UPDATE LOAN_APPLICATION SET status = ?` |

---

## 6. 데이터베이스 스키마

Entity Bean이 CMP로 매핑하는 테이블과 SQL에서 직접 접근하는 테이블의 상세 스키마다.
각 테이블마다 컬럼, FK, 그리고 **누가 이 테이블을 읽고 쓰는지** 까지 한 곳에 모았다.

---

### LOAN_APPLICATION

> 대출 신청 정보를 관리하는 핵심 테이블. 신청부터 승인/거절까지 전체 생명주기를 추적한다.

| 속성 | 값 |
|:-----|:---|
| 스키마 | BANKING |
| 매핑 엔티티 / 타입 | LoanApplicationBean / CMP |

**컬럼** (13개)

| # | 컬럼명 | 데이터 타입 | Nullable | PK | 설명 |
|--:|:-------|:----------|:--------:|:--:|:-----|
| 1 | application_id | NUMBER(15) | N | PK | 대출 신청 고유 ID |
| 2 | customer_id | NUMBER(15) | N | | 고객 ID |
| 3 | product_id | NUMBER(10) | N | | 대출 상품 ID |
| 4 | loan_amount | NUMBER(15,2) | N | | 신청 금액 |
| 5 | interest_rate | NUMBER(5,4) | Y | | 적용 금리 |
| 6 | term_months | NUMBER(3) | N | | 기간 (개월) |
| 7 | status | VARCHAR2(20) | N | | DRAFT / SUBMITTED / APPROVED / REJECTED / ACTIVE / CLOSED |
| 8 | application_date | DATE | N | | 신청일 |
| 9 | approval_date | DATE | Y | | 승인일 |
| 10 | rejection_reason | VARCHAR2(500) | Y | | 거절 사유 |
| 11 | credit_score_at_apply | NUMBER(4) | Y | | 신청 시점 신용점수 |
| 12 | dti_ratio | NUMBER(5,4) | Y | | 신청 시점 DTI |
| 13 | ltv_ratio | NUMBER(5,4) | Y | | 신청 시점 LTV |

**FK 관계**

| 방향 | 대상 테이블 | FK 타입 | 신뢰도 | 증거 |
|:-----|:-----------|:--------|:-------|:-----|
| -> | CUSTOMER | entity_reference | HIGH | customer_id -> CUSTOMER.customer_id |
| -> | LOAN_PRODUCT | entity_reference | HIGH | product_id -> LOAN_PRODUCT.product_id |
| <- | COLLATERAL | entity_reference | HIGH | COLLATERAL.application_id -> application_id |
| <- | REPAYMENT_SCHEDULE | entity_reference | HIGH | REPAYMENT_SCHEDULE.application_id -> application_id |
| <- | GUARANTOR | entity_reference | MEDIUM | GUARANTOR.application_id -> application_id |

**접근 관계** (FROM / WRITES)

| 접근 | 접근자 | 증거 |
|:-----|:-------|:-----|
| FROM | LoanScreeningSessionBean | `SELECT la.* FROM LOAN_APPLICATION la WHERE ...` |
| FROM | LoanExecutionSessionBean | `SELECT la.* FROM LOAN_APPLICATION la WHERE ...` |
| FROM | LoanApplicationSessionBean | `SELECT la.* FROM LOAN_APPLICATION la WHERE ...` |
| FROM | ReportSessionBean | `SELECT la.*, c.* FROM LOAN_APPLICATION la JOIN CUSTOMER c ...` |
| FROM | findOverdueLoans (SQL) | `SELECT la.* FROM LOAN_APPLICATION la` |
| FROM | calculateTotalExposure (SQL) | `SELECT SUM(loan_amount) FROM LOAN_APPLICATION` |
| WRITES | LoanScreeningSessionBean | `UPDATE LOAN_APPLICATION SET status = ? ...` |
| WRITES | LoanApplicationSessionBean | `INSERT INTO LOAN_APPLICATION ...` |
| WRITES | updateLoanStatus (SQL) | `UPDATE LOAN_APPLICATION SET status = ?` |

---

### CUSTOMER

> 고객 기본 정보를 관리하는 테이블.

| 속성 | 값 |
|:-----|:---|
| 스키마 | BANKING |
| 매핑 엔티티 / 타입 | CustomerBean / CMP |

**컬럼** (8개)

| # | 컬럼명 | 데이터 타입 | Nullable | PK | 설명 |
|--:|:-------|:----------|:--------:|:--:|:-----|
| 1 | customer_id | NUMBER(15) | N | PK | 고객 고유 ID |
| 2 | name | VARCHAR2(100) | N | | 고객명 |
| 3 | resident_no | VARCHAR2(20) | N | | 주민등록번호 |
| 4 | phone | VARCHAR2(20) | Y | | 연락처 |
| 5 | email | VARCHAR2(100) | Y | | 이메일 |
| 6 | annual_income | NUMBER(15,2) | Y | | 연소득 |
| 7 | total_debt | NUMBER(15,2) | Y | | 총 부채 |
| 8 | employment_type | VARCHAR2(20) | Y | | SALARY / SELF / FREELANCE |

**FK 관계**

| 방향 | 대상 테이블 | FK 타입 | 신뢰도 | 증거 |
|:-----|:-----------|:--------|:-------|:-----|
| <- | LOAN_APPLICATION | entity_reference | HIGH | LOAN_APPLICATION.customer_id -> customer_id |
| <- | CREDIT_RATING | entity_reference | HIGH | CREDIT_RATING.customer_id -> customer_id |

**접근 관계**

| 접근 | 접근자 | 증거 |
|:-----|:-------|:-----|
| FROM | LoanScreeningSessionBean | `SELECT c.* FROM CUSTOMER c WHERE c.customer_id = ?` |
| FROM | ReportSessionBean | `JOIN CUSTOMER c ON la.customer_id = c.customer_id` |

---

### 나머지 테이블

이하 모든 테이블이 위와 동일한 구조(컬럼 -> FK -> 접근 관계)로 나열된다.

| 테이블 | 매핑 엔티티 | 역할 |
|:-------|:-----------|:-----|
| COLLATERAL | CollateralBean | 담보 정보 |
| CREDIT_RATING | CreditRatingBean | 신용등급 이력 |
| GUARANTOR | GuarantorBean | 보증인 정보 |
| REPAYMENT_SCHEDULE | RepaymentScheduleBean | 상환 스케줄 |
| INTEREST_RATE | InterestRateBean | 금리 정보 |
| LOAN_PRODUCT | LoanProductBean | 대출 상품 |

---

### 컬럼 레벨 FK 전체 (`FK_TO` 관계)

테이블 간 FK를 컬럼 단위로 정리한 전체 목록이다.

| # | 소스 컬럼 | 대상 컬럼 | FK 타입 | 신뢰도 |
|--:|:---------|:---------|:--------|:-------|
| 1 | LOAN_APPLICATION.customer_id | CUSTOMER.customer_id | entity_reference | HIGH |
| 2 | LOAN_APPLICATION.product_id | LOAN_PRODUCT.product_id | entity_reference | HIGH |
| 3 | COLLATERAL.application_id | LOAN_APPLICATION.application_id | entity_reference | HIGH |
| 4 | CREDIT_RATING.customer_id | CUSTOMER.customer_id | entity_reference | HIGH |
| 5 | GUARANTOR.application_id | LOAN_APPLICATION.application_id | entity_reference | MEDIUM |
| 6 | GUARANTOR.guarantor_customer_id | CUSTOMER.customer_id | entity_reference | MEDIUM |
| 7 | REPAYMENT_SCHEDULE.application_id | LOAN_APPLICATION.application_id | entity_reference | HIGH |

---

## 7. 데이터 흐름과 호출 체인

시스템 전체에서 "누가 어떤 테이블을 읽고 쓰는지", "요청이 어떤 경로로 흐르는지"를 보여준다.
클린 아키텍처 전환 시 데이터 접근 계층의 경계를 정의하는 핵심 정보다.

### 7.1 테이블 접근 매트릭스

| 테이블 | 읽기 (FROM) | 쓰기 (WRITES) |
|:-------|:-----------|:-------------|
| LOAN_APPLICATION | LoanScreeningSB, LoanExecutionSB, LoanApplicationSB, ReportSB, findOverdueLoans, calculateTotalExposure | LoanScreeningSB, LoanApplicationSB, updateLoanStatus |
| CUSTOMER | LoanScreeningSB, ReportSB | |
| COLLATERAL | LoanScreeningSB | LoanApplicationSB |
| CREDIT_RATING | LoanScreeningSB | |
| GUARANTOR | LoanExecutionSB | LoanApplicationSB |
| REPAYMENT_SCHEDULE | findOverdueLoans | LoanExecutionSB, insertRepaymentRecord |
| LOAN_PRODUCT | LoanApplicationSB | |
| INTEREST_RATE | LoanExecutionSB | |

> SB = SessionBean (가독성을 위해 약어 사용)

### 7.2 호출 체인

웹 요청이 들어올 때 **Servlet -> Session Bean -> Entity Bean** 으로 이어지는 호출 흐름이다.

```
[대출 심사 흐름]
LoanScreeningServlet.doPost()
  -> LoanScreeningSessionBean.performScreening()
       -> LoanApplicationBean.findByPrimaryKey()
       -> CustomerBean.findByPrimaryKey()
       -> CreditRatingBean.getLatestRating()
       -> CreditRatingBean.findByCustomer()
       -> CollateralBean.findByApplication()
       -> LoanApplicationBean.setStatus()       // 승인 or 거절
       -> LoanApplicationBean.setApprovalDate() // 승인 시
       -> LoanApplicationBean.setRejectionReason() // 거절 시

[대출 실행 흐름]
LoanExecutionServlet.doPost()
  -> LoanExecutionSessionBean.executeLoan()
       -> LoanApplicationBean.findByPrimaryKey()
       -> InterestRateBean.findByProduct()
       -> RepaymentScheduleBean.create()
       -> NotificationSessionBean.sendApprovalNotice()
            -> CustomerBean.findByPrimaryKey()

[대출 신청 흐름]
LoanApplicationServlet.doPost()
  -> LoanApplicationSessionBean.createApplication()
       -> CustomerBean.findByPrimaryKey()
       -> LoanApplicationBean.ejbCreate()
LoanApplicationServlet.doGet()
  -> LoanApplicationSessionBean.findApplication()
```

### 7.3 호출 관계 전체 목록 (CALLS)

| # | 호출자 | 피호출자 | scope |
|--:|:-------|:--------|:------|
| 1 | LoanScreeningServlet.doPost() | LoanScreeningSessionBean.performScreening() | internal |
| 2 | LoanScreeningSessionBean.performScreening() | LoanApplicationBean.findByPrimaryKey() | internal |
| 3 | LoanScreeningSessionBean.performScreening() | CustomerBean.findByPrimaryKey() | internal |
| 4 | LoanScreeningSessionBean.performScreening() | CreditRatingBean.getLatestRating() | internal |
| 5 | LoanScreeningSessionBean.performScreening() | CreditRatingBean.findByCustomer() | internal |
| 6 | LoanScreeningSessionBean.performScreening() | CollateralBean.findByApplication() | internal |
| 7 | LoanScreeningSessionBean.approveApplication() | LoanApplicationBean.setStatus() | internal |
| 8 | LoanScreeningSessionBean.approveApplication() | LoanApplicationBean.setApprovalDate() | internal |
| 9 | LoanScreeningSessionBean.rejectApplication() | LoanApplicationBean.setStatus() | internal |
| 10 | LoanScreeningSessionBean.rejectApplication() | LoanApplicationBean.setRejectionReason() | internal |
| 11 | LoanExecutionServlet.doPost() | LoanExecutionSessionBean.executeLoan() | internal |
| 12 | LoanExecutionSessionBean.executeLoan() | LoanApplicationBean.findByPrimaryKey() | internal |
| 13 | LoanExecutionSessionBean.executeLoan() | RepaymentScheduleBean.create() | internal |
| 14 | LoanExecutionSessionBean.executeLoan() | InterestRateBean.findByProduct() | internal |
| 15 | LoanExecutionSessionBean.executeLoan() | NotificationSessionBean.sendApprovalNotice() | internal |
| 16 | LoanApplicationServlet.doPost() | LoanApplicationSessionBean.createApplication() | internal |
| 17 | LoanApplicationServlet.doGet() | LoanApplicationSessionBean.findApplication() | internal |
| 18 | LoanApplicationSessionBean.createApplication() | LoanApplicationBean.ejbCreate() | internal |
| 19 | LoanApplicationSessionBean.createApplication() | CustomerBean.findByPrimaryKey() | internal |
| 20 | NotificationSessionBean.sendApprovalNotice() | CustomerBean.findByPrimaryKey() | internal |

---

## 8. UML 관계 전체

클래스 간의 모든 UML 관계를 타입별로 정리한다.

### EXTENDS &#8212; 상속 (3건)

| 소스 | 대상 | 소스 범위 | 대상 범위 |
|:-----|:-----|:---------|:---------|
| LoanScreeningServlet | HttpServlet | INTERNAL | EXTERNAL |
| LoanExecutionServlet | HttpServlet | INTERNAL | EXTERNAL |
| LoanApplicationServlet | HttpServlet | INTERNAL | EXTERNAL |

### IMPLEMENTS &#8212; 구현 (13건)

| 소스 | 대상 | 소스 범위 | 대상 범위 |
|:-----|:-----|:---------|:---------|
| CustomerBean | EntityBean | INTERNAL | EXTERNAL |
| LoanApplicationBean | EntityBean | INTERNAL | EXTERNAL |
| CollateralBean | EntityBean | INTERNAL | EXTERNAL |
| CreditRatingBean | EntityBean | INTERNAL | EXTERNAL |
| GuarantorBean | EntityBean | INTERNAL | EXTERNAL |
| RepaymentScheduleBean | EntityBean | INTERNAL | EXTERNAL |
| InterestRateBean | EntityBean | INTERNAL | EXTERNAL |
| LoanProductBean | EntityBean | INTERNAL | EXTERNAL |
| LoanScreeningSessionBean | SessionBean | INTERNAL | EXTERNAL |
| LoanScreeningSessionBean | LoanServiceLocal | INTERNAL | INTERNAL |
| LoanExecutionSessionBean | SessionBean | INTERNAL | EXTERNAL |
| LoanApplicationSessionBean | SessionBean | INTERNAL | EXTERNAL |
| ReportSessionBean | SessionBean | INTERNAL | EXTERNAL |

### ASSOCIATION &#8212; 연관 (12건)

| 소스 | 대상 | 비고 |
|:-----|:-----|:-----|
| LoanScreeningSessionBean | CustomerBean | 필드: customerHome |
| LoanScreeningSessionBean | LoanApplicationBean | 필드: applicationHome |
| LoanScreeningSessionBean | CreditRatingBean | 필드: creditRatingHome |
| LoanScreeningSessionBean | CollateralBean | 필드: collateralHome |
| LoanExecutionSessionBean | LoanApplicationBean | 필드: applicationHome |
| LoanExecutionSessionBean | RepaymentScheduleBean | 필드: repaymentHome |
| LoanExecutionSessionBean | InterestRateBean | 필드: interestRateHome |
| LoanExecutionSessionBean | NotificationSessionBean | 필드: notificationBean |
| LoanApplicationSessionBean | LoanApplicationBean | 필드: applicationHome |
| LoanApplicationSessionBean | CustomerBean | 필드: customerHome |
| LoanApplicationBean | CollateralBean | 1:N |
| LoanApplicationBean | CreditRatingBean | N:1 (customer 경유) |

### DEPENDENCY &#8212; 의존 (8건)

| 소스 | 대상 | 대상 범위 | 비고 |
|:-----|:-----|:---------|:-----|
| LoanScreeningSessionBean | ScreeningResult | INTERNAL | 반환타입 |
| LoanScreeningServlet | LoanScreeningSessionBean | INTERNAL | 호출 |
| LoanExecutionServlet | LoanExecutionSessionBean | INTERNAL | 호출 |
| LoanApplicationServlet | LoanApplicationSessionBean | INTERNAL | 호출 |
| ReportSessionBean | DataSource | EXTERNAL | JNDI 조회 |
| ReportSessionBean | Connection | EXTERNAL | JDBC |
| ReportSessionBean | PreparedStatement | EXTERNAL | JDBC |
| ReportSessionBean | ResultSet | EXTERNAL | JDBC |

---

## 9. 관계 타입별 집계

그래프에 존재하는 모든 관계를 타입별로 집계한 전체 현황이다.

| 관계 타입 | 카테고리 | 수량 |
|:---------|:--------|-----:|
| HAS_METHOD | 구조적 | 320 |
| HAS_FIELD | 구조적 | 180 |
| CALLS | 의존성 | 140 |
| HAS_COLUMN | 구조적 | 87 |
| BELONGS_TO_PACKAGE | 구조적 | 55 |
| FROM | DB | 22 |
| ASSOCIATION | UML | 18 |
| CONTAINS | 구조적 | 15 |
| IMPLEMENTS | UML | 13 |
| WRITES | DB | 13 |
| REFERS_TO | DB | 10 |
| DEPENDENCY | UML | 8 |
| FK_TO_TABLE | DB | 7 |
| FK_TO | DB | 7 |
| CONTAINS_PACKAGE | 구조적 | 5 |
| EXTENDS | UML | 3 |
| USES | 의존성 | 2 |
| **합계** | | **905** |

---

> 이 문서는 레거시 시스템 정적 분석 파이프라인에 의해 자동 생성되었습니다.
> 클린 아키텍처 전환 시 현행 시스템의 구조를 파악하기 위한 참조 문서로 활용하십시오.
