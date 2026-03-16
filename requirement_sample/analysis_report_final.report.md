# 레거시 시스템 분석 보고서


## 1. 시스템 개요

### 1.1. 노드 통계

| 노드 타입 | 개수 |
| --- | --- |
| METHOD | 786 |
| FIELD | 220 |
| CLASS | 66 |
| Column | 66 |
| ARTIFACT_CHUNK | 14 |
| PACKAGE | 9 |
| Table | 7 |

### 1.2. 관계 통계

| 관계 타입 | 개수 |
| --- | --- |
| HAS_METHOD | 785 |
| REFER_TO | 525 |
| CALLS | 484 |
| DEPENDENCY | 261 |
| HAS_FIELD | 220 |
| BELONGS_TO_PACKAGE | 66 |
| HAS_COLUMN | 66 |
| USES | 65 |
| READS | 59 |
| WRITES | 24 |
| ASSOCIATION | 23 |
| COMPOSITION | 1 |

### 1.3. 스테레오타입 분포

| 스테레오타입 | 개수 |
| --- | --- |
| COMMAND/READMODEL | 44 |
| 미분류 | 8 |
| READMODEL | 5 |
| COMMAND | 5 |

## 2. 패키지 구조

### com

| 이름 | 타입 | 스테레오타입 | 범위 |
| --- | --- | --- | --- |
| - | - | - | - |

### com.banking

| 이름 | 타입 | 스테레오타입 | 범위 |
| --- | --- | --- | --- |
| - | - | - | - |

### com.banking.loan

| 이름 | 타입 | 스테레오타입 | 범위 |
| --- | --- | --- | --- |
| - | - | - | - |

### com.banking.loan.dto

| 이름 | 타입 | 스테레오타입 | 범위 |
| --- | --- | --- | --- |
| CollateralDTO | CLASS | COMMAND/READMODEL | INTERNAL |
| CreditRatingDTO | CLASS | COMMAND/READMODEL | INTERNAL |
| CustomerDTO | CLASS | COMMAND/READMODEL | INTERNAL |
| DelinquencyDTO | CLASS | COMMAND/READMODEL | INTERNAL |
| LoanApplicationDTO | CLASS | COMMAND/READMODEL | INTERNAL |
| LoanLedgerDTO | CLASS | COMMAND/READMODEL | INTERNAL |
| RepaymentDTO | CLASS | COMMAND/READMODEL | INTERNAL |
| ScreeningResultDTO | CLASS | COMMAND/READMODEL | INTERNAL |

### com.banking.loan.entity

| 이름 | 타입 | 스테레오타입 | 범위 |
| --- | --- | --- | --- |
| CollateralBean | CLASS | COMMAND/READMODEL | INTERNAL |
| CollateralLocal | CLASS | COMMAND/READMODEL | INTERNAL |
| CollateralLocalHome | CLASS | COMMAND/READMODEL | INTERNAL |
| CreditRatingBean | CLASS | COMMAND/READMODEL | INTERNAL |
| CreditRatingLocal | CLASS | COMMAND/READMODEL | INTERNAL |
| CreditRatingLocalHome | CLASS | COMMAND/READMODEL | INTERNAL |
| CustomerBean | CLASS | COMMAND/READMODEL | INTERNAL |
| CustomerLocal | CLASS | COMMAND/READMODEL | INTERNAL |
| CustomerLocalHome | CLASS | COMMAND/READMODEL | INTERNAL |
| DelinquencyBean | CLASS | COMMAND/READMODEL | INTERNAL |
| DelinquencyLocal | CLASS | COMMAND/READMODEL | INTERNAL |
| DelinquencyLocalHome | CLASS | COMMAND/READMODEL | INTERNAL |
| LoanApplicationBean | CLASS | COMMAND/READMODEL | INTERNAL |
| LoanApplicationLocal | CLASS | COMMAND/READMODEL | INTERNAL |
| LoanApplicationLocalHome | CLASS | COMMAND/READMODEL | INTERNAL |
| LoanLedgerBean | CLASS | COMMAND/READMODEL | INTERNAL |
| LoanLedgerLocal | CLASS | COMMAND/READMODEL | INTERNAL |
| LoanLedgerLocalHome | CLASS | COMMAND/READMODEL | INTERNAL |
| RepaymentBean | CLASS | COMMAND/READMODEL | INTERNAL |
| RepaymentLocal | CLASS | COMMAND/READMODEL | INTERNAL |
| RepaymentLocalHome | CLASS | COMMAND/READMODEL | INTERNAL |

### com.banking.loan.exception

| 이름 | 타입 | 스테레오타입 | 범위 |
| --- | --- | --- | --- |
| DelinquencyException | CLASS | - | INTERNAL |
| LoanApplicationException | CLASS | - | INTERNAL |
| LoanExecutionException | CLASS | - | INTERNAL |
| LoanScreeningException | CLASS | - | INTERNAL |

### com.banking.loan.session

| 이름 | 타입 | 스테레오타입 | 범위 |
| --- | --- | --- | --- |
| DebtCollectionSession | CLASS | COMMAND/READMODEL | INTERNAL |
| DebtCollectionSessionBean | CLASS | COMMAND/READMODEL | INTERNAL |
| DebtCollectionSessionHome | CLASS | READMODEL | INTERNAL |
| DelinquencyMgmtSession | CLASS | COMMAND/READMODEL | INTERNAL |
| DelinquencyMgmtSessionBean | CLASS | COMMAND/READMODEL | INTERNAL |
| DelinquencyMgmtSessionHome | CLASS | READMODEL | INTERNAL |
| LoanApplicationSession | CLASS | COMMAND/READMODEL | INTERNAL |
| LoanApplicationSessionBean | CLASS | COMMAND/READMODEL | INTERNAL |
| LoanApplicationSessionHome | CLASS | COMMAND | INTERNAL |
| LoanExecutionSession | CLASS | COMMAND/READMODEL | INTERNAL |
| LoanExecutionSessionBean | CLASS | COMMAND/READMODEL | INTERNAL |
| LoanExecutionSessionHome | CLASS | COMMAND | INTERNAL |
| LoanLedgerSession | CLASS | COMMAND/READMODEL | INTERNAL |
| LoanLedgerSessionBean | CLASS | COMMAND/READMODEL | INTERNAL |
| LoanLedgerSessionHome | CLASS | COMMAND | INTERNAL |
| LoanProcessSession | CLASS | COMMAND/READMODEL | INTERNAL |
| LoanProcessSessionBean | CLASS | COMMAND/READMODEL | INTERNAL |
| LoanProcessSessionHome | CLASS | COMMAND | INTERNAL |
| LoanScreeningSession | CLASS | COMMAND/READMODEL | INTERNAL |
| LoanScreeningSessionBean | CLASS | COMMAND/READMODEL | INTERNAL |
| LoanScreeningSessionHome | CLASS | COMMAND | INTERNAL |

### com.banking.loan.util

| 이름 | 타입 | 스테레오타입 | 범위 |
| --- | --- | --- | --- |
| InterestCalculator | CLASS | READMODEL | INTERNAL |
| LoanConstants | CLASS | READMODEL | INTERNAL |
| ServiceLocator | CLASS | READMODEL | INTERNAL |

### com.banking.loan.web

| 이름 | 타입 | 스테레오타입 | 범위 |
| --- | --- | --- | --- |
| LoanServlet | CLASS | COMMAND/READMODEL | INTERNAL |


## 3. 엔티티 상세 (INTERNAL)

### CollateralDTO

#### 기본 정보

| 항목 | 값 |
| --- | --- |
| 이름 | CollateralDTO |
| 타입 | CLASS |
| FQN | com.banking.loan.dto.CollateralDTO |
| 패키지 | com.banking.loan.dto |
| 스테레오타입 | COMMAND/READMODEL |
| 파일 | - |
| 라인 | - |
| 토큰 | - |

#### 요약

> com.banking.loan.dto.CollateralDTO는 대출 신청(applicationId)과 연관된 담보 정보를 전달·보관하기 위한 DTO로, collateralId, applicationId, collateralType, description, appraisedValue, appraisalDate, ltvRatio(LTV 비율), registrationStatus(등록상태) 등의 속성을 한 객체에 묶어 후속 처리에서 참조할 수 있게 한다. 감정일자(appraisalDate), LTV 비율(ltvRatio), 등록상태(registrationStatus) 등 외부에서 받은 값을 별도 검증·변환 없이 그대로 저장·조회하는 성격을 가진다. 또한 현재 담보 데이터 상태를 사람이 읽을 수 있는 문자열로 출력(toString)해 로그/디버깅에 활용하며, 직렬화 호환을 위한 serialVersionUID=1L을 포함한다.

#### 메서드

| 이름 | 시그니처 | 반환타입 | 수정자 | 요약 |
| --- | --- | --- | --- | --- |
| getCollateralId | public String getCollateralId() | - | - | 이 코드는 담보 식별 및 평가 관련 데이터(예: collateralId, applicationId, appraisedValue, ltvRatio, registrationStatus)를 보유하는 객체에서 collateralId(담보 식별자)를 외부로 제공하기 위한 조회 동작이다. 내부에 저장된 collateralId 값을 그대로 반환하여, 담보 건을 식별하거나 다른 처리 흐름에서 참조할 수 있게 한다. 값의 변경, 검증, 변환, 저장 요청 등 부수효과는 발생하지 않으며 단순 읽기만 수행한다. |
| setCollateralId | public void setCollateralId(String collateralId) | - | - | 이 코드는 담보(collateral) 관련 데이터를 보관하는 객체에서 담보 식별자 값인 collateralId를 갱신하기 위한 설정 동작을 수행한다. 외부에서 전달된 값을 collateralId 필드에 그대로 대입하여 기존 값이 있으면 이를 덮어쓴다. 이로써 이후 담보 정보의 식별 기준이 되는 collateralId가 객체 상태에 반영되며, 저장/전송/검증 등의 후속 처리에서 일관된 식별값으로 사용될 수 있다. |
| getApplicationId | public String getApplicationId() | - | - | 담보 관련 정보가 보유한 applicationId(신청 식별자)를 조회하여 호출자에게 그대로 반환한다. 내부 상태를 변경하지 않고, 저장되어 있는 신청 식별자 값의 외부 접근을 허용하는 목적의 읽기 동작이다. 반환되는 값은 별도 변환이나 검증 없이 현재 보관 중인 applicationId 원본이다. |
| setApplicationId | public void setApplicationId(String applicationId) | - | - | 이 코드는 담보(collateralId, collateralType, appraisedValue, ltvRatio 등)와 연관된 식별 정보를 보관하는 객체에서, 담보가 속한 신청/접수 단위를 나타내는 applicationId(신청 ID)를 내부 상태로 확정 설정한다. 외부에서 전달된 applicationId 값을 그대로 대입하여 기존에 저장돼 있던 applicationId가 있으면 그 값을 새로운 값으로 덮어쓴다. 값의 형식 검증, 공백/NULL 체크, 상태(registrationStatus)와의 정합성 확인 같은 방어 로직 없이 단순히 속성 값을 갱신한다. |
| getCollateralType | public String getCollateralType() | - | - | 이 코드는 담보(collateral) 정보를 구성하는 데이터에서 collateralType(담보유형) 값을 외부로 제공하기 위한 조회 동작을 수행한다. 내부에 보관 중인 collateralType 값을 그대로 반환하여, 담보의 분류/구분 정보를 화면 표시나 후속 검증 로직에서 참조할 수 있게 한다. 값의 변환, 검증, 상태 변경 없이 현재 저장된 담보유형을 읽기 전용으로 노출한다. |
| setCollateralType | public void setCollateralType(String collateralType) | - | - | 이 클래스는 담보 식별자(collateralId), 신청 식별자(applicationId), 담보 유형(collateralType), 담보 설명(description), 감정가(appraisedValue), 감정일(appraisalDate), LTV 비율(ltvRatio), 등록 상태(registrationStatus) 같은 담보 관련 정보를 보관한다. 이 범위의 로직은 입력으로 받은 담보 유형(collateralType) 값을 객체의 담보 유형(collateralType) 필드에 반영한다. 이를 통해 해당 담보가 어떤 유형인지(예: 부동산/예금/보증 등으로 분류될 수 있는 값)를 이후 처리에서 일관되게 참조할 수 있게 상태를 갱신한다. |
| getDescription | public String getDescription() | - | - | 이 코드는 담보 정보 객체가 보유한 description(설명) 값을 외부에서 확인할 수 있도록 그대로 반환한다. 내부 상태를 변경하거나 추가 계산을 수행하지 않고, 현재 저장된 설명 텍스트를 조회하는 용도에 집중한다. 따라서 담보의 세부 설명을 화면 표시나 검증/출력 등 읽기 흐름에서 재사용하기 위한 접근 지점으로 동작한다. |
| setDescription | public void setDescription(String description) | - | - | 이 객체는 collateralId, applicationId, collateralType, appraisedValue, appraisalDate, ltvRatio, registrationStatus 등 담보 관련 속성을 보관하는 데이터 구조이며, 그중 description(설명) 값을 관리한다. 외부에서 전달된 description(설명)을 현재 객체의 description 필드에 대입하여 담보 설명 내용을 갱신한다. 이 갱신된 description은 이후 객체가 저장되거나 다른 계층으로 전달될 때 최신 담보 설명으로 사용되도록 내부 상태를 변경한다. |
| getAppraisedValue | public BigDecimal getAppraisedValue() | - | - | 이 코드는 담보 관련 정보 중 appraisedValue(감정가액)를 외부에서 조회할 수 있도록 값을 그대로 반환한다. 내부 상태를 변경하거나 추가 계산·검증을 수행하지 않고, 보관 중인 감정가액(BigDecimal)을 읽기 전용으로 노출하는 역할이다. 이를 통해 담보의 평가 금액을 다른 처리 흐름에서 참조할 수 있게 한다. |
| setAppraisedValue | public void setAppraisedValue(BigDecimal appraisedValue) | - | - | 이 객체는 담보 관련 식별자(collateralId, applicationId)와 평가 정보(appraisedValue, appraisalDate, ltvRatio, registrationStatus 등)를 보관하는 역할을 한다. 전달받은 평가금액을 appraisedValue에 그대로 반영하여 담보의 평가가치를 내부 상태로 갱신한다. 별도의 검증이나 변환 없이 값을 대입하므로, 유효한 평가금액인지(예: null 여부, 음수 여부 등)는 이 값을 제공하는 쪽에서 보장해야 한다. |
| getAppraisalDate | public Date getAppraisalDate() | - | - | 이 코드는 담보 관련 정보(예: collateralId, applicationId, appraisedValue 등) 중 appraisalDate(감정일자) 값을 외부에서 조회할 수 있도록 반환한다. 내부에 보관 중인 appraisalDate를 그대로 돌려주며, 값의 변환·검증·보정 로직은 수행하지 않는다. 따라서 감정일자를 읽기 전용으로 노출해 다른 처리(화면 표시, 보고, 후속 계산)의 입력으로 사용하게 하는 역할을 한다. |
| setAppraisalDate | public void setAppraisalDate(Date appraisalDate) | - | - | 이 클래스는 담보(collateralId, applicationId, collateralType 등) 정보와 함께 감정가(appraisedValue) 및 appraisalDate(감정일자) 같은 평가 관련 속성을 보관한다. 이 코드는 외부에서 전달된 감정일자를 appraisalDate(감정일자) 필드에 그대로 반영하여, 해당 담보의 감정 기준일을 갱신한다. 추가 검증이나 변환 없이 객체 내부 상태(appraisalDate)만 변경하며, 다른 시스템 조회나 저장 호출은 수행하지 않는다. |
| getLtvRatio | public BigDecimal getLtvRatio() | - | - | 담보 정보에 포함된 ltvRatio(LTV 비율) 값을 외부에서 조회할 수 있도록 그대로 반환한다. 내부 상태를 변경하거나 값을 가공하지 않고, 현재 객체에 저장된 ltvRatio의 최신 값을 읽어 제공하는 목적이다. 이로써 담보의 담보인정비율을 계산·표시·검증 등의 후속 로직에서 일관되게 참조할 수 있게 한다. |
| setLtvRatio | public void setLtvRatio(BigDecimal ltvRatio) | - | - | 이 코드는 담보 관련 정보에서 ltvRatio(LTV 비율)를 갱신하기 위해, 입력으로 받은 LTV 비율 값을 해당 객체의 ltvRatio 필드에 그대로 반영한다. 값의 유효성 검사나 변환 로직 없이 전달된 값을 즉시 저장하므로, LTV 비율을 외부에서 설정·수정하는 용도로 사용된다. 이 변경은 객체 내부 상태를 갱신하는 쓰기 동작이며, 다른 데이터 조회나 외부 자원 접근은 수행하지 않는다. |
| getRegistrationStatus | public String getRegistrationStatus() | - | - | 이 코드는 담보(collateral) 관련 정보를 보유하는 객체에서 registrationStatus(등록상태) 값을 조회해 반환한다. 내부에 저장된 등록상태 문자열을 그대로 외부로 제공하여, 담보의 등록 진행 여부/상태를 확인할 수 있게 한다. 값의 변환, 검증, 상태 변경 로직 없이 단순 조회만 수행한다. |
| setRegistrationStatus | public void setRegistrationStatus(String registrationStatus) | - | - | 담보 정보가 보유한 registrationStatus(등록상태) 값을 외부에서 전달된 값으로 갱신한다. 이로써 해당 담보의 등록 진행 상태(예: 등록 여부/처리 단계 등)를 객체 내부 상태로 확정적으로 반영한다. 값 검증, 형식 변환, 다른 리소스 조회·저장 같은 부수 동작 없이 단순 대입만 수행한다. |
| toString | public String toString() | - | - | 담보 정보를 사람이 읽을 수 있는 단일 문자열로 직렬화해 표현한다. 출력 문자열에는 collateralId, applicationId, collateralType, description, appraisedValue, appraisalDate, ltvRatio, registrationStatus 값을 고정된 라벨과 함께 순서대로 포함한다. 각 필드 값은 인용부호 처리 규칙을 달리해 문자열 계열은 작은따옴표로 감싸고, 금액/비율/일자 계열은 값 자체를 그대로 붙여 넣는다. 이를 통해 로그 출력이나 디버깅 시 담보 데이터의 현재 상태를 한눈에 확인할 수 있게 한다. |

#### 필드

| 이름 | 타입 | 수정자 | 요약 |
| --- | --- | --- | --- |
| serialVersionUID | long | - | 자바 직렬화(Serializable) 시 클래스 버전 호환성을 식별하기 위한 고정 상수로, 역직렬화 과정에서 클래스 구조 변경 여부를 검증하는 데 사용된다(값: 1L). |
| collateralId | String | - | 담보(콜래터럴)를 식별하기 위한 고유 ID 값을 저장하는 문자열 필드입니다. |
| applicationId | String | - | 애플리케이션(또는 신청/요청) 단위를 식별하기 위한 고유 ID 문자열을 저장하는 필드입니다. |
| collateralType | String | - | 담보의 종류(유형)를 문자열로 저장하는 필드로, 거래나 계약에서 어떤 형태의 담보가 적용되는지 구분하는 데 사용됩니다. |
| description | String | - | 객체나 항목에 대한 설명(상세 내용)을 텍스트로 저장하는 문자열 필드입니다. |
| appraisedValue | BigDecimal | - | 자산이나 대상의 감정(평가) 금액을 고정소수점으로 정밀하게 저장하는 필드입니다. |
| appraisalDate | Date | - | 객체의 평가가 수행되거나 평가 결과가 확정된 날짜(시점)를 저장하는 Date 타입 필드입니다. |
| ltvRatio | BigDecimal | - | 담보 가치 대비 대출 금액의 비율(LTV, Loan-To-Value ratio)을 BigDecimal로 보관하는 필드로, 대출 한도 산정이나 담보 평가 기준 계산에 사용되는 비율 값을 담습니다. |
| registrationStatus | String | - | 등록(가입/신청 등) 처리의 현재 상태를 문자열로 저장하는 필드로, 등록이 완료/대기/거부 등 어떤 단계에 있는지 나타내는 값을 담는다. |

#### 구조 관계

| 방향 | 관계 | 대상 | 속성 |
| --- | --- | --- | --- |
| ← | DEPENDENCY | LoanApplicationSession | source_member=registerCollateral, usage=parameter |
| ← | DEPENDENCY | LoanApplicationSessionBean | source_member=registerCollateral, usage=parameter |
| ← | DEPENDENCY | LoanProcessSessionBean | source_member=requestScreening, usage=cast |
| ← | COMPOSITION | LoanProcessSessionBean | source_member=addCollateral |

#### 호출 관계

| 방향 | 대상 | 호출코드 |
| --- | --- | --- |
| ← | LoanProcessSessionBean | - |

#### 데이터 접근

| 대상 | 관계 | 근거 | 신뢰도 |
| --- | --- | --- | --- |
| CollateralDTO | REFER_TO | - | 1.0 |

#### 요약 코드

```
없음
```

### CreditRatingDTO

#### 기본 정보

| 항목 | 값 |
| --- | --- |
| 이름 | CreditRatingDTO |
| 타입 | CLASS |
| FQN | com.banking.loan.dto.CreditRatingDTO |
| 패키지 | com.banking.loan.dto |
| 스테레오타입 | COMMAND/READMODEL |
| 파일 | - |
| 라인 | - |
| 토큰 | - |

#### 요약

> com.banking.loan.dto.CreditRatingDTO는 고객의 신용평가 결과를 전달·보관하는 데이터 전송 객체로, ratingId, customerId, creditScore, creditGrade, ratingAgency, ratingDate와 함께 annualIncome(연간 소득), totalDebt(전체 부채), dti(부채 대비 소득 비율), isValid(유효 여부) 같은 재무·검증 관련 속성을 포함합니다. annualIncome/totalDebt/dti는 BigDecimal로 정밀하게 저장되며, dti와 isValid는 외부에서 전달된 값을 별도의 검증·계산·보정 없이 그대로 필드에 대입해 갱신하고 isValid도 저장된 값을 그대로 반환해 외부 로직이 유효성을 판단하도록 합니다. 또한 ratingId~isValid 전 필드를 키=값 형태로 문자열 직렬화해 로그/디버깅에 활용할 수 있고, Serializable 버전 호환을 위해 serialVersionUID=1L을 가집니다.

#### 메서드

| 이름 | 시그니처 | 반환타입 | 수정자 | 요약 |
| --- | --- | --- | --- | --- |
| getRatingId | public String getRatingId() | - | - | 이 클래스는 고객의 신용평가 정보를 나타내며 ratingId, customerId, creditScore, creditGrade, ratingAgency, ratingDate, annualIncome, totalDebt, dti, isValid 같은 속성을 보유한다. 이 코드는 그중 ratingId(평가 식별자)를 외부에서 확인할 수 있도록 값을 그대로 반환한다. 반환 과정에서 계산, 검증, 형변환이나 상태 변경은 수행하지 않는다. |
| setRatingId | public void setRatingId(String ratingId) | - | - | 신용평가 정보를 담는 객체가 보유한 ratingId(평가 식별자) 값을 외부 입력으로 갱신한다. 전달받은 ratingId를 현재 인스턴스의 ratingId 필드에 그대로 대입하여 이후 customerId, creditScore, creditGrade, ratingAgency, ratingDate 등 다른 평가 속성과 함께 식별 가능한 상태로 유지되도록 한다. 검증, 변환, 조건 분기 없이 단순 대입만 수행하므로 값의 유효성 판단이나 isValid 변경은 여기서 발생하지 않는다. |
| getCustomerId | public String getCustomerId() | - | - | 신용평가 관련 정보(예: ratingId, creditScore, creditGrade, ratingAgency, ratingDate 등)를 보관하는 데이터에서 customerId(고객 식별자) 값을 조회해 호출자에게 그대로 반환한다. 내부 상태를 변경하거나 추가 계산·검증을 수행하지 않고, 저장된 customerId의 현재 값을 읽기 전용으로 노출하는 역할이다. 이 반환값은 특정 신용평가 레코드가 어떤 고객에 속하는지 식별하는 데 사용될 수 있다. |
| setCustomerId | public void setCustomerId(String customerId) | - | - | 이 클래스는 신용평가 결과와 관련된 데이터(ratingId, customerId, creditScore, creditGrade 등)를 보관하며, 그중 customerId(고객식별자)를 설정하는 역할을 수행한다. 외부에서 전달된 고객식별자 값을 객체 내부 상태인 customerId 필드에 그대로 반영하여 이후 신용평가 정보가 특정 고객과 연결되도록 한다. 조회나 계산 로직 없이 필드 값만 갱신하므로, 객체의 상태를 변경하는 목적이 명확하다. |
| getCreditScore | public int getCreditScore() | - | - | 이 객체는 고객의 신용평가 정보(ratingId, customerId, creditGrade, ratingAgency, ratingDate, annualIncome, totalDebt, dti, isValid 등) 중 정수형 creditScore(신용점수)를 보유한다. 해당 범위의 로직은 현재 인스턴스에 저장된 creditScore 값을 그대로 반환하여, 외부에서 신용점수를 조회할 수 있게 한다. 입력값 검증, 계산, 상태 변경은 수행하지 않으며 내부 값의 읽기 전용 접근만 제공한다. |
| setCreditScore | public void setCreditScore(int creditScore) | - | - | 이 코드는 신용평가 정보(creditScore, creditGrade, ratingAgency, ratingDate 등)를 보유하는 객체에서 creditScore(신용점수) 값을 외부 입력값으로 갱신한다. 전달받은 정수 값을 그대로 creditScore 필드에 대입해 내부 상태를 변경하며, 추가 검증(범위 체크)이나 다른 필드 연동 계산(dti 등)은 수행하지 않는다. 그 결과 이후 신용등급 산정, 유효성(isValid) 판단, 부채/소득 기반 지표 계산 등에 사용할 기준 점수가 최신 값으로 유지되도록 한다. |
| getCreditGrade | public String getCreditGrade() | - | - | 이 코드는 신용평가/등급 정보를 보관하는 객체에서 creditGrade(신용등급) 값을 외부로 제공하기 위한 조회용 접근자이다. 내부에 저장된 creditGrade 필드를 그대로 반환하며, 값의 변환·검증·계산 같은 추가 로직은 수행하지 않는다. 이를 통해 다른 처리 흐름에서 신용등급 기반의 판단(예: 신용평가 결과 표시, 리스크 분류, 유효성 확인 등)에 사용할 수 있도록 한다. |
| setCreditGrade | public void setCreditGrade(String creditGrade) | - | - | 이 코드는 고객 신용평가 정보 묶음에서 creditGrade(신용등급) 값을 갱신하는 동작을 수행한다. 외부에서 전달된 신용등급 값을 내부 상태의 creditGrade 필드에 그대로 반영해, 이후 creditScore(신용점수), ratingAgency(평가기관), ratingDate(평가일) 등과 함께 사용될 신용평가 결과를 최신화한다. 별도의 유효성 검증이나 등급 변환 규칙 없이 단순 대입만 수행하므로, 입력값의 적합성은 다른 흐름에서 보장되어야 한다. |
| getRatingAgency | public String getRatingAgency() | - | - | 이 클래스는 고객 신용평가 정보를 다루며 ratingId, customerId, creditScore, creditGrade, ratingAgency, ratingDate, annualIncome, totalDebt, dti, isValid 같은 속성을 보유한다. 이 코드는 그중 ratingAgency(평가기관) 값을 변경 없이 그대로 반환해, 외부에서 평가기관 정보를 조회할 수 있게 한다. 추가 검증이나 변환, 상태 변경 없이 단순 조회만 수행한다. |
| setRatingAgency | public void setRatingAgency(String ratingAgency) | - | - | 신용평가 관련 정보를 담는 객체에서 ratingAgency 값을 갱신해 내부 상태를 변경한다. 외부에서 전달된 기관 식별/명칭 정보를 ratingAgency 필드에 그대로 반영하여 이후 평가 출처를 표현할 수 있게 한다. 별도의 검증, 변환, 부가 계산 없이 단순 대입만 수행한다. |
| getRatingDate | public Date getRatingDate() | - | - | 이 코드는 고객의 신용평가 정보(예: ratingId, customerId, creditScore, creditGrade, ratingAgency, ratingDate 등) 중 ratingDate(평가일)를 외부에서 조회할 수 있도록 제공한다. 저장된 ratingDate 값을 가공이나 검증 없이 그대로 반환해, 신용평가가 수행된 기준 일자를 확인하는 데 사용된다. 내부 상태를 변경하지 않고 읽기만 수행하므로 조회 목적의 동작이다. |
| setRatingDate | public void setRatingDate(Date ratingDate) | - | - | 이 코드는 고객의 신용평가 정보를 담는 객체에서 ratingDate(신용평가일자) 값을 갱신하기 위한 설정 로직이다. 입력으로 받은 평가일자를 객체 내부의 ratingDate 필드에 그대로 저장하여 이후 신용평가 시점 기반의 처리(예: 평가 최신성 판단, 이력 관리)에서 사용될 수 있도록 상태를 변경한다. 별도의 검증이나 변환 없이 값 대입만 수행하므로, 유효성 판단은 다른 위치에서 이루어지는 전제에 가깝다. |
| getAnnualIncome | public BigDecimal getAnnualIncome() | - | - | 이 코드는 신용평가 정보에 포함된 annualIncome(연소득) 값을 외부에서 조회할 수 있도록 반환한다. 별도의 계산, 변환, 검증 없이 현재 객체에 저장된 annualIncome을 그대로 돌려주므로 상태 변경은 발생하지 않는다. 연소득은 totalDebt(총부채), dti(부채상환비율) 등과 함께 신용 관련 지표를 확인하거나 표시하는 읽기 흐름에서 사용될 수 있다. |
| setAnnualIncome | public void setAnnualIncome(BigDecimal annualIncome) | - | - | 이 코드는 신용평가/등급, 연소득(annualIncome), 부채(totalDebt), DTI(dti) 등 개인의 신용 관련 정보를 보관하는 데이터 구조에서 연소득(annualIncome) 값을 갱신하는 역할을 한다. 외부에서 전달된 연소득 값을 내부 상태인 annualIncome 필드에 그대로 반영하여 이후 신용평가 산정이나 적정성(isValid) 판단에 활용될 수 있게 한다. 별도의 검증, 계산, 변환 없이 값 저장만 수행하므로 입력 값의 유효성은 다른 로직에서 보장된다는 전제를 가진 단순 상태 변경 동작이다. |
| getTotalDebt | public BigDecimal getTotalDebt() | - | - | 이 코드는 고객의 신용평가 정보(creditScore, creditGrade, annualIncome, totalDebt, dti 등)를 보관하는 객체에서 totalDebt(총부채) 값을 외부에 제공하기 위한 조회 동작이다. 내부에 저장된 totalDebt 값을 그대로 반환하며, 계산·검증·정규화 같은 추가 로직은 수행하지 않는다. 따라서 호출자는 해당 고객의 부채 규모를 다른 신용 지표(annualIncome, dti 등)와 함께 판단하기 위한 입력 데이터로 사용할 수 있다. |
| setTotalDebt | public void setTotalDebt(BigDecimal totalDebt) | - | - | 이 코드는 고객 신용평가 정보를 구성하는 데이터에서 totalDebt(총부채) 값을 갱신하는 역할을 한다. 입력으로 받은 BigDecimal 금액을 그대로 totalDebt에 대입하여 기존 총부채 값을 새 값으로 덮어쓴다. 값의 유효성 검증이나 dti(부채상환비율) 재계산, isValid(유효 여부) 갱신 같은 후속 처리 없이 단순히 상태만 변경한다. |
| getDti | public BigDecimal getDti() | - | - | 이 클래스는 ratingId, customerId, creditScore, creditGrade, annualIncome, totalDebt, dti 등 고객의 신용평가 및 재무 지표를 보관한다. 이 범위의 로직은 현재 객체에 저장된 dti(부채 대비 소득 비율) 값을 그대로 반환하여, 외부에서 해당 비율을 조회하거나 후속 계산/판단에 활용할 수 있게 한다. 내부 상태를 갱신하지 않고 읽기 전용으로 값만 노출한다. |
| setDti | public void setDti(BigDecimal dti) | - | - | 이 클래스는 고객의 신용평가 정보를 보관하며 ratingId, customerId, creditScore, annualIncome, totalDebt, dti 같은 값을 내부 상태로 유지한다. 이 구간은 외부에서 전달된 dti(부채상환비율) 값을 객체의 dti 필드에 그대로 반영해 해당 신용평가 정보의 비율 값을 갱신한다. 별도의 검증, 계산, 보정 로직 없이 입력값을 그대로 저장하므로 dti 값의 정합성 보장은 호출자 또는 다른 검증 흐름에 의존한다. 이 변경은 객체의 내부 상태를 수정하는 쓰기 동작이다. |
| getIsValid | public boolean getIsValid() | - | - | 이 클래스는 ratingId, customerId, creditScore, creditGrade, ratingAgency, ratingDate, annualIncome, totalDebt, dti와 함께 신용평가 관련 정보의 유효성 상태를 보관한다. 이 구간은 현재 객체에 저장된 isValid(유효 여부) 값을 그대로 반환해, 외부 로직이 해당 신용평가 데이터가 유효한지 판단할 수 있도록 한다. 값의 계산이나 검증, 상태 변경은 수행하지 않고 기존 상태를 조회만 한다. |
| setIsValid | public void setIsValid(boolean isValid) | - | - | 이 코드는 ratingId, customerId, creditScore, creditGrade, ratingAgency, ratingDate, annualIncome, totalDebt, dti 같은 신용평가 관련 데이터를 함께 보유하는 객체에서, 해당 데이터가 유효한지 여부를 나타내는 isValid 값을 갱신한다. 입력으로 받은 참/거짓 값을 isValid(유효여부)에 그대로 반영하여 이후 처리에서 유효성 판단 기준으로 사용할 수 있게 한다. 외부 조회나 저장 없이 객체 내부 상태만 변경한다. |
| toString | public String toString() | - | - | 신용평가 정보를 담고 있는 데이터의 현재 값을 사람이 읽을 수 있는 문자열 형태로 직렬화해 반환한다. 반환 문자열에는 ratingId, customerId, creditScore, creditGrade, ratingAgency, ratingDate, annualIncome, totalDebt, dti, isValid 필드 값이 모두 포함되며, 각 항목은 키=값 형태로 나열된다. 이를 통해 로그 출력이나 디버깅 시 객체 상태를 한눈에 확인할 수 있게 한다. |

#### 필드

| 이름 | 타입 | 수정자 | 요약 |
| --- | --- | --- | --- |
| serialVersionUID | long | - | 자바 직렬화(Serializable) 시 클래스 버전 호환성을 식별하기 위한 고정 상수로, 역직렬화 과정에서 클래스 구조 변경 여부를 검증하는 데 사용된다(값: 1L). |
| ratingId | String | - | 평가(레이팅) 정보를 식별하기 위한 고유 ID 값을 문자열로 저장하는 필드입니다. |
| customerId | String | - | 고객을 식별하기 위한 고유한 고객 ID 값을 문자열로 보관하는 필드입니다. |
| creditScore | int | - | 개인의 신용 점수를 정수값으로 저장하는 필드로, 신용도 평가나 대출·한도·금리 산정 등 신용 관련 판단 로직에 활용된다. |
| creditGrade | String | - | 개인의 신용 등급(크레딧 그레이드)을 문자열로 저장하는 필드입니다. |
| ratingAgency | String | - | 신용등급을 평가한 기관(평가사)의 명칭 또는 식별자를 저장하는 문자열 필드입니다. |
| ratingDate | Date | - | 평가가 이루어진 날짜 및 시간을 저장하는 필드로, 해당 객체의 평가 시점을 기록하는 데 사용됩니다. |
| annualIncome | BigDecimal | - | 연간 소득 금액을 정밀한 수치(BigDecimal)로 저장하는 필드로, 개인 또는 대상의 1년 기준 소득 수준을 나타내는 데 사용됩니다. |
| totalDebt | BigDecimal | - | 전체 부채(총 채무) 금액을 BigDecimal로 보관하는 필드로, 클래스가 다루는 대상의 누적 부채 규모를 표현한다. |
| dti | BigDecimal | - | 부채 대비 소득 비율(DTI, Debt-to-Income)을 금액/비율 계산에 적합한 BigDecimal 형태로 저장하는 필드입니다. |
| isValid | boolean | - | 객체나 특정 처리 결과가 유효한 상태인지(검증을 통과했는지)를 나타내는 불리언 플래그를 저장하는 필드입니다. |

#### 구조 관계

| 방향 | 관계 | 대상 | 속성 |
| --- | --- | --- | --- |
| - | - | - | - |

#### 호출 관계

| 방향 | 대상 | 호출코드 |
| --- | --- | --- |
| - | - | - |

#### 데이터 접근

| 대상 | 관계 | 근거 | 신뢰도 |
| --- | --- | --- | --- |
| CreditRatingDTO | REFER_TO | - | 1.0 |

#### 요약 코드

```
없음
```

### CustomerDTO

#### 기본 정보

| 항목 | 값 |
| --- | --- |
| 이름 | CustomerDTO |
| 타입 | CLASS |
| FQN | com.banking.loan.dto.CustomerDTO |
| 패키지 | com.banking.loan.dto |
| 스테레오타입 | COMMAND/READMODEL |
| 파일 | - |
| 라인 | - |
| 토큰 | - |

#### 요약

> com.banking.loan.dto.CustomerDTO는 대출/금융 도메인에서 고객 정보를 계층 간에 전달하기 위한 데이터 전송 객체로, customerId, customerName, residentId, customerType, address, phoneNumber, email 등 식별·연락 정보를 보관합니다. 또한 annualIncome(연간소득), employerName(고용주명), creditGrade(신용등급), registrationDate(등록일) 등 재무·직장·신용 및 등록 정보를 함께 담아 조회·전달하는 책임을 가집니다. 별도의 비즈니스 로직이나 검증/변환 없이 각 속성 값을 그대로 저장해 필요 시 사용할 수 있도록 구성됩니다.

#### 메서드

| 이름 | 시그니처 | 반환타입 | 수정자 | 요약 |
| --- | --- | --- | --- | --- |
| getCustomerId | public String getCustomerId() | - | - | 이 코드는 고객의 기본 정보(예: customerId, customerName, residentId 등)를 보관하는 구성에서, 고객 식별자인 customerId 값을 외부로 제공하기 위한 읽기 동작을 수행한다. 내부에 저장된 customerId를 그대로 반환하여, 호출 측이 고객을 유일하게 식별하거나 다른 고객 정보와 연계할 때 사용할 수 있게 한다. 값의 변환, 검증, 포맷 변경 없이 현재 보관 중인 값을 조회만 하며 상태를 변경하지 않는다. |
| setCustomerId | public void setCustomerId(String customerId) | - | - | 이 코드는 고객 기본정보를 보관하는 객체에서 customerId(고객식별자) 값을 갱신하기 위한 설정 동작을 수행한다. 외부에서 전달된 customerId 값을 내부 필드 customerId에 그대로 대입하여 해당 객체가 표현하는 고객의 식별자를 확정한다. 이 변경은 객체의 상태를 바꾸는 쓰기 동작이며, 별도의 검증·변환·부가 처리나 다른 구성요소 호출 없이 단순 할당만 수행한다. |
| getCustomerName | public String getCustomerName() | - | - | 고객의 기본 정보를 보관하는 데이터에서 customerName(고객명) 값을 외부로 제공한다. 내부에 저장된 customerName 필드를 그대로 반환하며, 값 변환이나 검증 같은 추가 처리는 수행하지 않는다. 호출자는 이 반환값을 이용해 고객을 표시하거나 customerId, residentId 등 다른 고객 속성과 함께 식별 정보를 구성할 수 있다. |
| setCustomerName | public void setCustomerName(String customerName) | - | - | 고객 기본 정보를 보관하는 객체에서 customerName(고객명) 값을 갱신하는 설정 로직이다. 외부에서 전달된 고객명을 내부 customerName 필드에 그대로 대입하여, 이후 조회나 직렬화 시 최신 고객명이 반영되도록 한다. 검증, 변환, 추가 연산 없이 값 저장만 수행하므로 이 범위의 효과는 객체 상태 변경으로 한정된다. |
| getResidentId | public String getResidentId() | - | - | 고객의 기본 정보( customerId, customerName, residentId, customerType, address, phoneNumber, email 등)를 보관하는 객체에서 residentId(주민등록번호)를 외부로 제공하기 위한 조회용 접근자이다. 내부에 저장된 residentId 값을 그대로 반환하며, 값의 변환·검증·마스킹 같은 추가 규칙은 적용하지 않는다. 데이터 저장/수정/삭제 등 상태 변경은 수행하지 않고 현재 보관 중인 값을 읽기만 한다. |
| setResidentId | public void setResidentId(String residentId) | - | - | 이 코드는 고객의 기본정보(예: customerId, customerName, residentId, address, phoneNumber 등)를 보관하는 객체에서 residentId(주민등록번호)를 갱신하기 위한 설정 동작을 수행한다. 외부에서 전달된 residentId 값을 내부 상태의 residentId 필드에 그대로 반영하여 이후 고객 식별 및 관련 처리에서 사용할 수 있게 한다. 별도의 형식 검증, 마스킹, 공백/널 검사나 변환 로직 없이 단순 대입만 수행한다. |
| getCustomerType | public String getCustomerType() | - | - | 이 코드는 고객 식별 및 연락처, 소득 정보 등과 함께 보관되는 customerType(고객유형) 값을 외부에서 조회할 수 있도록 제공한다. 내부에 저장된 customerType 필드를 그대로 반환하며, 값의 변환·검증·정규화 같은 추가 처리는 수행하지 않는다. 이를 통해 호출자는 해당 고객이 어떤 유형으로 분류되어 있는지(예: 개인/법인 등)를 읽기 용도로 확인할 수 있다. |
| setCustomerType | public void setCustomerType(String customerType) | - | - | 이 코드는 고객 식별 및 연락처, 소득 정보 등 여러 고객 속성(customerId, customerName, residentId, customerType, address, phoneNumber, email, annualIncome, employerName, creditGrade, registrationDate)을 보유하는 객체의 상태를 갱신하기 위한 일부이다. 입력으로 받은 customerType(고객유형) 값을 객체 내부의 customerType 필드에 그대로 반영해 고객 분류 정보를 변경한다. 유효성 검사, 변환, 조건 분기 없이 단순 대입만 수행하므로 값의 정합성은 호출 측 또는 다른 검증 로직에 의존한다. 그 결과 이후 로직에서 고객유형 기반의 처리(예: 고객 분류별 정책 적용)를 가능하게 하는 상태 업데이트가 이루어진다. |
| getAddress | public String getAddress() | - | - | 이 코드는 고객의 식별정보(customerId, residentId), 연락처(phoneNumber, email), 소득(annualIncome) 등과 함께 주소(address)를 보관하는 데이터 구조의 일부로, 보관 중인 주소 값을 외부에 제공하기 위한 접근 지점을 구현한다. 별도의 입력값 없이 현재 객체에 저장된 address를 그대로 반환하여, 화면 표시나 후속 처리에서 고객 주소를 조회할 수 있게 한다. 데이터 저장·수정·검증 같은 부수효과 없이 읽기만 수행하므로, 객체 상태를 변경하지 않는다. |
| setAddress | public void setAddress(String address) | - | - | 고객 기본정보를 담는 객체에서 address(주소) 값을 갱신하기 위한 설정 로직이다. 외부에서 전달된 주소 값을 내부의 address 필드에 그대로 저장하여, 이후 고객의 주소 정보를 최신 상태로 유지하도록 한다. 검증, 포맷 변환, 다른 저장소 반영 없이 메모리 상의 객체 상태만 변경한다. |
| getPhoneNumber | public String getPhoneNumber() | - | - | 고객의 연락처 정보 중 phoneNumber(전화번호) 값을 외부에서 조회할 수 있도록 반환한다. 내부 상태를 변경하거나 추가 계산을 수행하지 않고, 저장되어 있는 phoneNumber를 그대로 제공하는 읽기 동작이다. 이를 통해 고객 기본정보(주소, 이메일 등)와 함께 전화번호를 화면 표시나 후속 검증/연락 처리에 활용할 수 있게 한다. |
| setPhoneNumber | public void setPhoneNumber(String phoneNumber) | - | - | 이 코드는 고객의 기본 정보(예: customerId, customerName, address, email 등) 중 연락처를 나타내는 phoneNumber(전화번호) 값을 갱신하기 위한 동작을 수행한다. 외부에서 전달된 전화번호 값을 객체 내부의 phoneNumber 필드에 그대로 반영하여, 이후 고객 연락처 정보가 최신 상태로 유지되도록 한다. 별도의 형식 검증, 정규화, 중복 확인이나 다른 시스템 조회 없이 단순히 값 대입만 수행한다. |
| getEmail | public String getEmail() | - | - | 고객의 기본 식별/연락 정보(예: customerId, customerName, phoneNumber, email 등)를 보관하는 데이터에서, email(이메일) 값을 외부로 제공하기 위한 조회 동작이다. 별도의 검증, 변환, 포맷팅 없이 현재 보관 중인 email 값을 그대로 반환한다. 데이터 저장/수정 같은 상태 변경은 수행하지 않으며, 고객 이메일 조회 목적의 읽기 전용 접근을 제공한다. |
| setEmail | public void setEmail(String email) | - | - | 이 코드는 고객 식별 및 연락처 정보(customerId, customerName, phoneNumber, email 등)를 보관하는 객체에서 email(이메일) 값을 갱신하는 역할을 한다. 외부에서 전달된 이메일 문자열을 해당 객체의 email 필드에 그대로 대입하여 내부 상태를 변경한다. 별도의 형식 검증, 정규화(트림/소문자화), 중복 확인 같은 비즈니스 규칙 없이 값 설정만 수행한다. |
| getAnnualIncome | public BigDecimal getAnnualIncome() | - | - | 이 코드는 고객의 재무 정보 중 연간 소득(annualIncome)을 외부에서 조회할 수 있도록 값을 그대로 반환한다. 반환 시 연간 소득은 BigDecimal 타입으로 제공되어 금액/소득처럼 소수점 정밀도가 필요한 수치를 안전하게 다룰 수 있게 한다. 내부 상태를 변경하거나 추가 검증·가공 없이 저장된 annualIncome 값을 읽기 전용으로 노출하는 역할을 한다. |
| setAnnualIncome | public void setAnnualIncome(BigDecimal annualIncome) | - | - | 고객의 연소득(annualIncome) 값을 외부에서 전달받아 현재 객체의 annualIncome 필드에 그대로 반영한다. 이 과정에서 값의 범위, null 여부, 통화/단위 등 도메인 규칙에 대한 검증이나 정규화는 수행하지 않는다. 결과적으로 고객 정보 객체 내부 상태 중 연소득 값만 갱신하여 이후 신용등급(creditGrade) 산정, 소득 기반 심사, 고객 프로파일 표시 등 후속 처리에서 최신 값을 사용하도록 한다. |
| getEmployerName | public String getEmployerName() | - | - | 이 코드는 고객 식별 및 연락처, 소득, 직장 정보 등을 보관하는 객체의 속성 중 employerName(직장명)을 외부에서 조회할 수 있도록 값을 반환한다. 내부에 저장된 employerName을 그대로 돌려주며, 값에 대한 가공·검증·변환이나 기본값 보정은 수행하지 않는다. 따라서 호출자는 등록된 직장명 정보를 읽기 전용으로 획득하는 용도로 사용한다. |
| setEmployerName | public void setEmployerName(String employerName) | - | - | 이 코드는 고객 프로필 정보 중 employerName(고용주명)을 내부 상태로 보관하는 데이터 구조에서, 외부로부터 전달된 고용주명을 employerName에 반영한다. 이를 통해 고객의 직장/소득 관련 정보(예: annualIncome, creditGrade 등)와 함께 활용될 수 있는 고용주명 값이 최신 입력으로 갱신된다. 별도의 검증, 변환, 조회 동작 없이 전달받은 값을 그대로 저장하는 단순 상태 변경만 수행한다. |
| getCreditGrade | public String getCreditGrade() | - | - | 고객 정보 전반(식별자, 연락처, 소득, 직장, 등록일 등)을 보관하는 객체에서 creditGrade(신용등급) 값을 외부로 제공하기 위한 조회 로직이다. 내부에 저장된 creditGrade 필드를 그대로 반환하며, 값의 변환·검증·정규화 같은 추가 처리는 수행하지 않는다. 이 반환값은 화면 표시, 조회 응답 구성, 또는 이후 신용 관련 판단 로직에서 재사용될 수 있도록 읽기 전용으로 노출된다. |
| setCreditGrade | public void setCreditGrade(String creditGrade) | - | - | 고객의 신용 관련 정보 중 creditGrade(신용등급) 값을 외부 입력으로 받아 현재 객체의 creditGrade 필드에 그대로 반영한다. 별도의 형식 검증, 값 변환, 범위 체크 없이 전달된 문자열을 즉시 상태로 저장한다. 그 결과 이후 동일 객체를 참조하는 로직에서 갱신된 creditGrade 값을 기준으로 판단이나 출력이 이뤄질 수 있다. |
| getRegistrationDate | public Date getRegistrationDate() | - | - | 이 코드는 고객 정보에 포함된 registrationDate(등록일자)를 외부에서 조회할 수 있도록 값을 그대로 반환한다. 내부 상태를 변경하거나 추가 계산·검증을 수행하지 않고, 현재 보관 중인 등록일자 값을 읽기 전용으로 제공하는 역할이다. 이를 통해 고객의 등록 시점을 다른 흐름에서 참조할 수 있게 한다. |
| setRegistrationDate | public void setRegistrationDate(Date registrationDate) | - | - | 고객 정보 객체가 보유한 registrationDate(등록일)를 외부에서 전달된 날짜 값으로 갱신한다. 이 값은 고객의 등록 시점을 객체 상태로 확정해 보관하기 위한 것으로, 이후 등록일 기반의 조회·정렬·유효성 판단 등에 활용될 수 있다. 별도의 검증이나 변환 없이 전달된 값을 그대로 저장하므로, 등록일의 형식/범위 검증 책임은 호출 측 또는 다른 검증 로직에 의존한다. |
| toString | public String toString() | - | - | 고객 정보를 담는 객체의 현재 상태를 사람이 읽기 쉬운 문자열로 직렬화해 반환한다. 반환 문자열에는 customerId, customerName, residentId, customerType, address, phoneNumber, email, annualIncome, employerName, creditGrade, registrationDate 값을 모두 포함해 한 눈에 식별 가능하게 구성한다. 필드 값을 변경하거나 저장소에 반영하지 않고, 디버깅·로그 출력 등 조회 목적의 표현만 수행한다. |

#### 필드

| 이름 | 타입 | 수정자 | 요약 |
| --- | --- | --- | --- |
| serialVersionUID | long | - | 자바 직렬화(Serializable) 시 클래스 버전 호환성을 식별하기 위한 고정 상수로, 역직렬화 과정에서 클래스 구조 변경 여부를 검증하는 데 사용된다(값: 1L). |
| customerId | String | - | 고객을 식별하기 위한 문자열 형태의 고객 ID를 저장하는 필드입니다. |
| customerName | String | - | 고객의 이름을 문자열로 저장하는 멤버 변수입니다. |
| residentId | String | - | 거주자(입주민)를 식별하기 위한 고유 ID 값을 문자열로 저장하는 필드입니다. |
| customerType | String | - | 고객의 유형(예: 개인/법인, 일반/VIP 등)을 문자열로 저장하는 필드입니다. |
| address | String | - | 객체(또는 엔티티)의 주소 정보를 문자열로 저장하는 필드입니다. |
| phoneNumber | String | - | 사용자의 전화번호(연락처)를 문자열로 저장하는 필드입니다. |
| email | String | - | 이 필드는 이메일 주소를 문자열로 저장하여 사용자의 연락처나 계정 식별 정보로 활용된다. |
| annualIncome | BigDecimal | - | 개인의 연간 소득 금액을 BigDecimal로 저장하는 필드로, 소득 관련 계산이나 금융 데이터 처리 시 정밀한 금액 표현을 위해 사용됩니다. |
| employerName | String | - | 고용주(또는 회사/기관)의 이름을 문자열로 저장하는 필드로, 해당 객체가 참조하는 근무처의 명칭 정보를 담는다. |
| creditGrade | String | - | 신용 등급(credit grade)을 문자열로 저장하는 필드로, 대상의 신용 수준을 나타내는 등급값(예: A/B/C 또는 1~10 등)을 보관하는 데 사용됩니다. |
| registrationDate | Date | - | 해당 객체(또는 엔티티)가 시스템에 등록된 날짜/시간을 저장하는 필드입니다. |

#### 구조 관계

| 방향 | 관계 | 대상 | 속성 |
| --- | --- | --- | --- |
| - | - | - | - |

#### 호출 관계

| 방향 | 대상 | 호출코드 |
| --- | --- | --- |
| - | - | - |

#### 데이터 접근

| 대상 | 관계 | 근거 | 신뢰도 |
| --- | --- | --- | --- |
| CustomerDTO | REFER_TO | - | 1.0 |

#### 요약 코드

```
없음
```

### DelinquencyDTO

#### 기본 정보

| 항목 | 값 |
| --- | --- |
| 이름 | DelinquencyDTO |
| 타입 | CLASS |
| FQN | com.banking.loan.dto.DelinquencyDTO |
| 패키지 | com.banking.loan.dto |
| 스테레오타입 | COMMAND/READMODEL |
| 파일 | - |
| 라인 | - |
| 토큰 | - |

#### 요약

> com.banking.loan.dto.DelinquencyDTO는 대출/채무 연체 건을 계층 간 전달·보관하기 위한 데이터 전송 객체로, delinquencyId와 함께 ledgerId(원장 ID), customerId(고객 ID)로 연체 건의 식별·연결 정보를 담습니다. 또한 delinquencyStartDate(연체 시작일), delinquencyAmount(연체 금액), delinquencyDays(연체 일수), delinquencyGrade(연체 등급), penaltyRate(패널티율), penaltyAmount(패널티 금액), status(상태), resolutionDate(해소일자) 등 연체 산정 및 처리 상태 데이터를 보유합니다. penaltyAmount, status, resolutionDate는 별도 검증·변환 없이 설정된 값을 그대로 저장·조회하며, toString은 주요 필드를 키-값 형태로 직렬화해 로깅/디버깅에 활용하고 Serializable 호환을 위해 serialVersionUID=1L을 가집니다.

#### 메서드

| 이름 | 시그니처 | 반환타입 | 수정자 | 요약 |
| --- | --- | --- | --- | --- |
| getDelinquencyId | public String getDelinquencyId() | - | - | 이 코드는 연체 정보를 담는 객체가 보유한 delinquencyId(연체 식별자)를 외부로 제공하기 위한 조회 동작이다. 내부에 저장된 delinquencyId 값을 그대로 반환하며, 값의 변환이나 검증 로직은 수행하지 않는다. 데이터 저장, 상태 변경, 부수효과 없이 현재 보유 중인 연체 식별자를 읽는 용도로 사용된다. |
| setDelinquencyId | public void setDelinquencyId(String delinquencyId) | - | - | 연체 정보를 담는 객체에서 delinquencyId(연체 식별자)를 외부에서 전달받은 값으로 갱신한다. 이 갱신은 해당 연체 건을 다른 속성들(ledgerId, customerId 등)과 함께 식별·추적하기 위한 기준 값을 설정하는 목적을 가진다. 별도의 검증이나 변환 없이 입력 값을 그대로 내부 상태에 반영한다. |
| getLedgerId | public String getLedgerId() | - | - | 이 코드는 연체 정보에 포함된 식별자들 중 ledgerId(원장 식별자)를 외부에서 조회할 수 있도록 값을 반환한다. 내부 상태를 변경하지 않고, 현재 객체가 보유한 ledgerId를 그대로 제공하는 읽기 전용 동작이다. 이를 통해 원장(ledger)과 연체 정보 간의 연결 키를 다른 처리 흐름에서 재사용할 수 있게 한다. |
| setLedgerId | public void setLedgerId(String ledgerId) | - | - | 연체 정보를 담는 객체에서 ledgerId(원장 식별자)를 외부 입력값으로 갱신해, 해당 연체 건이 어떤 원장에 속하는지 연결 정보를 설정한다. 입력으로 받은 ledgerId를 그대로 내부 필드 ledgerId에 대입하며, 값의 형식 검증이나 null/공백 처리 같은 추가 규칙은 적용하지 않는다. 이로써 이후 연체 처리에서 ledgerId를 기준으로 원장 단위의 조회·정산·상태 변경 로직이 가능하도록 식별자를 확정한다. |
| getCustomerId | public String getCustomerId() | - | - | 이 코드는 연체(Delinquency) 관련 정보(예: delinquencyId, ledgerId, customerId, delinquencyStartDate, delinquencyAmount, delinquencyDays, delinquencyGrade, penaltyRate, penaltyAmount, status, resolutionDate)를 보유하는 객체에서 고객 식별자(customerId)를 조회해 반환한다. 외부 입력을 받거나 내부 상태를 변경하지 않고, 이미 보관 중인 customerId 값을 그대로 제공하는 읽기 전용 동작이다. 반환된 customerId는 특정 연체 건이 어떤 고객에 속하는지 식별하거나, 다른 처리 단계에서 고객 기준으로 연체 정보를 연결하는 데 사용될 수 있다. |
| setCustomerId | public void setCustomerId(String customerId) | - | - | 이 클래스는 연체(미해결 채무) 정보를 다루며, delinquencyId, ledgerId, customerId, delinquencyStartDate, delinquencyAmount 같은 식별자/금액/일자 속성을 보관한다. 이 범위의 로직은 외부에서 전달된 고객 식별자 값을 customerId(고객식별자) 필드에 그대로 반영해, 해당 연체 정보가 어떤 고객에 속하는지 확정한다. 별도의 검증, 변환, 조회 작업 없이 내부 상태(customerId)만 변경한다. |
| getDelinquencyStartDate | public Date getDelinquencyStartDate() | - | - | 이 코드는 연체 정보를 담는 객체가 보유한 delinquencyStartDate(연체 시작일)를 외부에서 조회할 수 있도록 그대로 반환한다. 추가적인 계산, 형식 변환, 검증 없이 현재 객체 상태에 저장된 날짜 값을 읽기 전용으로 노출하는 역할이다. 이를 통해 연체 기간 산정이나 후속 조회 화면/리포트 구성에 필요한 기준일을 제공한다. |
| setDelinquencyStartDate | public void setDelinquencyStartDate(Date delinquencyStartDate) | - | - | 연체 정보를 보관하는 객체에서 delinquencyStartDate(연체 시작일)를 외부 입력값으로 갱신한다. 전달된 날짜 값을 내부 상태로 그대로 반영하여, 이후 연체 기간(delinquencyDays) 산정이나 delinquencyAmount(연체금액) 등의 연체 관련 판단에 사용될 기준 시점을 확정한다. 별도의 검증, 변환, 부수효과 없이 값 설정만 수행한다. |
| getDelinquencyAmount | public BigDecimal getDelinquencyAmount() | - | - | 이 코드는 연체 관련 정보(예: delinquencyId, ledgerId, delinquencyStartDate, delinquencyAmount 등)를 보관하는 객체에서 delinquencyAmount(연체금액)를 외부로 제공하기 위한 조회 로직이다. 내부에 저장된 delinquencyAmount 값을 가공하거나 검증하지 않고 그대로 반환하여, 연체 금액을 계산·표시·후속 판단에 활용할 수 있게 한다. 데이터 변경이나 상태 전이 없이 값 조회만 수행하므로 읽기 목적에 해당한다. |
| setDelinquencyAmount | public void setDelinquencyAmount(BigDecimal delinquencyAmount) | - | - | 이 코드는 연체 관련 정보(식별자, 시작일, 연체금액, 연체일수, 등급, 패널티, 상태, 해소일 등)를 보관하는 객체에서 연체금액(delinquencyAmount)을 갱신하기 위한 동작이다. 외부에서 전달된 연체금액 값을 객체 내부의 delinquencyAmount 필드에 그대로 대입하여 현재 인스턴스가 들고 있는 연체금액 상태를 변경한다. 값의 유효성 검증이나 변환, 반올림/정규화 같은 추가 규칙은 적용하지 않고 입력 값을 그대로 확정 반영한다. |
| getDelinquencyDays | public int getDelinquencyDays() | - | - | 이 코드는 연체 관련 정보를 담는 객체에서 delinquencyDays(연체일수) 값을 조회해 반환한다. 외부 입력을 받거나 내부 상태를 변경하지 않고, 현재 보관 중인 연체일수 값을 그대로 제공하는 읽기 동작이다. 호출자 입장에서는 연체 기간을 계산·표시·판단 로직에 활용하기 위해 연체일수 값을 가져오는 용도로 사용된다. |
| setDelinquencyDays | public void setDelinquencyDays(int delinquencyDays) | - | - | 연체 정보를 담는 객체에서 delinquencyDays(연체일수) 값을 갱신해 내부 상태를 변경한다. 입력으로 받은 연체일수를 그대로 delinquencyDays 필드에 대입하여 이후 연체 기간 기반의 등급(delinquencyGrade), 패널티율(penaltyRate), 패널티 금액(penaltyAmount) 산정이나 상태(status) 판단에 활용될 수 있도록 한다. 별도의 검증, 변환, 조건 분기 없이 단순 값 설정만 수행한다. |
| getDelinquencyGrade | public String getDelinquencyGrade() | - | - | 이 클래스는 연체(delinquency)와 관련된 식별자, 금액, 기간, 등급, 상태, 해소일자 등의 정보를 보관하는 구조로 보이며, 이 범위는 그중 delinquencyGrade(연체등급) 값을 외부에서 조회할 수 있도록 제공한다. 내부에 이미 저장되어 있는 delinquencyGrade를 그대로 반환하며, 값의 변환·검증·정규화 같은 추가 로직은 수행하지 않는다. 따라서 연체등급의 현재 상태를 읽기 전용으로 노출하는 목적의 동작이다. |
| setDelinquencyGrade | public void setDelinquencyGrade(String delinquencyGrade) | - | - | 연체 관련 정보를 담는 객체에서 delinquencyGrade(연체 등급) 값을 외부 입력으로 갱신한다. 전달받은 연체 등급을 별도 검증이나 변환 없이 그대로 내부 상태에 반영해, 이후 연체 상태 분류/표시에 사용할 수 있게 한다. 이 동작은 객체의 연체 등급 필드를 변경하는 순수한 상태 변경이며, 다른 외부 자원이나 계산 로직을 수반하지 않는다. |
| getPenaltyRate | public BigDecimal getPenaltyRate() | - | - | 이 코드는 연체/원장/고객 식별자, 연체 시작일, 연체 금액, 연체 일수 및 등급, penaltyRate(연체 가산/패널티율), 패널티 금액, status(상태), 해소일자를 보유하는 데이터에서 penaltyRate 값을 외부로 제공한다. 내부에 저장된 penaltyRate를 그대로 반환하며, 값의 계산·검증·변환 로직은 포함하지 않는다. 따라서 연체 관련 패널티율을 조회하려는 목적의 읽기 동작만 수행하고 어떤 상태도 변경하지 않는다. |
| setPenaltyRate | public void setPenaltyRate(BigDecimal penaltyRate) | - | - | 이 코드는 연체(delinquency) 관련 정보를 담는 객체에서 penaltyRate(연체/지연에 대한 가산 금리율) 값을 갱신하는 동작을 수행한다. 외부에서 전달된 금리율 값을 해당 객체의 penaltyRate 필드에 그대로 반영해, 이후 penaltyAmount(가산금액) 산정이나 상태 판단에 사용할 수 있도록 내부 상태를 변경한다. 값의 유효성 검증, 범위 체크, 반올림 규칙 적용 같은 추가 규칙은 포함하지 않으며 단순 대입만 수행한다. |
| getPenaltyAmount | public BigDecimal getPenaltyAmount() | - | - | 이 코드는 연체/패널티 관련 정보를 보관하는 객체가 가진 penaltyAmount(패널티 금액)를 외부에 제공하기 위한 조회 동작이다. 내부에 이미 계산·저장되어 있는 penaltyAmount 값을 그대로 반환하며, 값의 변환이나 검증, 추가 계산은 수행하지 않는다. 따라서 penaltyAmount의 현재 상태를 읽어 전달하는 용도로 사용된다. |
| setPenaltyAmount | public void setPenaltyAmount(BigDecimal penaltyAmount) | - | - | 이 코드는 연체 정보(예: delinquencyAmount, penaltyRate, penaltyAmount 등)를 보관하는 객체에서 penaltyAmount(지연/연체에 따른 가산 금액)를 갱신하는 역할을 한다. 전달된 penaltyAmount 값을 객체의 penaltyAmount 필드에 그대로 설정하여 기존 값이 있으면 덮어쓴다. 값의 범위(음수 여부 등)나 상태(status)와의 정합성 검증 없이 단순히 금액 상태를 변경하는 동작만 수행한다. |
| getStatus | public String getStatus() | - | - | 이 코드는 연체 정보(예: delinquencyId, ledgerId, delinquencyAmount, delinquencyDays 등)를 보관하는 객체에서 status 값을 외부에 제공한다. 현재 저장되어 있는 status를 그대로 반환하며, 값의 변경이나 검증 로직은 수행하지 않는다. 따라서 연체 건의 처리 상태를 조회하거나 화면/응답에 표시하기 위한 읽기 목적의 동작이다. |
| setStatus | public void setStatus(String status) | - | - | 연체(delinqeuncy) 관련 정보를 보관하는 객체에서 status(상태) 값을 외부 입력으로 갱신한다. 전달받은 상태 문자열을 별도 검증이나 변환 없이 그대로 status 필드에 설정해, 현재 연체 처리 단계(예: 진행/해결 등)를 객체 내부 상태로 확정한다. 이 동작은 delinquencyId, ledgerId, customerId, delinquencyStartDate, delinquencyAmount 등 다른 연체 속성과 함께 관리되는 상태값을 변경하는 쓰기 성격의 처리다. |
| getResolutionDate | public Date getResolutionDate() | - | - | 이 코드는 연체(delinquency) 관련 데이터 중 resolutionDate(해소일자)를 외부에서 조회할 수 있도록 제공한다. 내부에 보관 중인 resolutionDate 값을 그대로 반환하며, 값의 변환이나 검증, 상태 변경은 수행하지 않는다. 따라서 해소일자의 확인/표시 등 읽기 목적의 접근 지점으로 사용된다. |
| setResolutionDate | public void setResolutionDate(Date resolutionDate) | - | - | 이 코드는 연체/해결 처리와 관련된 데이터 중 resolutionDate(해결일)를 객체 내부 상태로 확정 저장한다. 외부에서 전달된 해결일 값을 현재 인스턴스의 resolutionDate 필드에 그대로 반영하여, 이후 연체 상태 해소 시점 정보를 보관할 수 있게 한다. 별도의 검증, 변환, 조건 분기 없이 입력 값을 그대로 적용하므로, 해결일의 유효성 판단은 다른 흐름에서 수행되는 것을 전제로 한다. |
| toString | public String toString() | - | - | 연체 정보 묶음의 현재 값을 사람이 읽을 수 있는 한 줄 문자열로 직렬화해 반환한다. 반환 문자열에는 delinquencyId, ledgerId, customerId, delinquencyStartDate, delinquencyAmount, delinquencyDays, delinquencyGrade, penaltyRate, penaltyAmount, status, resolutionDate가 각각의 키-값 형태로 포함된다. 이 표현은 내부 상태를 변경하지 않고, 로깅/디버깅 또는 메시지 출력 시 연체 관련 핵심 필드를 한눈에 확인할 수 있게 하는 목적이다. |

#### 필드

| 이름 | 타입 | 수정자 | 요약 |
| --- | --- | --- | --- |
| serialVersionUID | long | - | 자바 직렬화(Serializable) 시 클래스 버전 호환성을 식별하기 위한 고정 상수로, 역직렬화 과정에서 클래스 구조 변경 여부를 검증하는 데 사용된다(값: 1L). |
| delinquencyId | String | - | 연체(Delinquency) 항목을 식별하기 위한 고유 ID 값을 저장하는 문자열 필드입니다. |
| ledgerId | String | - | 원장(ledger)을 식별하기 위한 고유 ID 문자열을 저장하는 필드입니다. |
| customerId | String | - | 고객을 식별하기 위한 문자열 형태의 고객 ID를 저장하는 필드입니다. |
| delinquencyStartDate | Date | - | 연체(채무 불이행)가 시작된 날짜/시점을 저장하는 필드입니다. |
| delinquencyAmount | BigDecimal | - | 연체 금액(미납 또는 기한 초과로 발생한 금액)을 BigDecimal로 저장하는 필드입니다. |
| delinquencyDays | int | - | 연체(지연)된 일수를 정수로 보관하는 필드로, 어떤 대상(예: 결제·대출·채무 등)이 기한을 얼마나 초과했는지를 일(day) 단위로 나타내는 값이다. |
| delinquencyGrade | String | - | 연체(지연 납부) 등급을 문자열로 저장하는 필드로, 대상의 연체 상태를 등급 형태로 구분해 관리하는 데 사용됩니다. |
| penaltyRate | BigDecimal | - | 벌금 또는 지연에 따른 페널티를 계산할 때 적용되는 비율(율)을 BigDecimal로 저장하는 필드입니다. |
| penaltyAmount | BigDecimal | - | 벌금(패널티)으로 부과되는 금액을 정밀한 금액 계산을 위해 BigDecimal 형태로 저장하는 필드입니다. |
| status | String | - | 객체나 처리 과정의 현재 상태를 문자열로 보관하는 필드로, 예를 들어 진행 단계나 결과 상태(예: ACTIVE/INACTIVE, SUCCESS/FAIL 등)를 표현하는 값을 담습니다. |
| resolutionDate | Date | - | 어떤 이슈나 요청이 해결(처리 완료)된 날짜/시간을 저장하는 필드입니다. |

#### 구조 관계

| 방향 | 관계 | 대상 | 속성 |
| --- | --- | --- | --- |
| ← | DEPENDENCY | LoanServlet | source_member=handleGetDelinquencies, usage=cast |
| ← | DEPENDENCY | LoanServlet | source_member=handleGetCollectionTargets, usage=cast |
| ← | DEPENDENCY | DebtCollectionSession | source_member=getCollectionDetail, usage=return |
| ← | DEPENDENCY | DebtCollectionSessionBean | source_member=delinquencyEntityToDTO, usage=local_new |
| ← | DEPENDENCY | DelinquencyMgmtSession | source_member=registerDelinquency, usage=return |
| ← | DEPENDENCY | DelinquencyMgmtSession | source_member=getDelinquency, usage=return |
| ← | DEPENDENCY | DelinquencyMgmtSessionBean | source_member=getDelinquency, usage=return |
| ← | DEPENDENCY | DelinquencyMgmtSessionBean | source_member=entityToDTO, usage=local_new |

#### 호출 관계

| 방향 | 대상 | 호출코드 |
| --- | --- | --- |
| ← | LoanServlet | - |
| ← | DebtCollectionSessionBean | - |
| ← | DelinquencyMgmtSessionBean | - |

#### 데이터 접근

| 대상 | 관계 | 근거 | 신뢰도 |
| --- | --- | --- | --- |
| DelinquencyDTO | REFER_TO | - | 1.0 |

#### 요약 코드

```
없음
```

### LoanApplicationDTO

#### 기본 정보

| 항목 | 값 |
| --- | --- |
| 이름 | LoanApplicationDTO |
| 타입 | CLASS |
| FQN | com.banking.loan.dto.LoanApplicationDTO |
| 패키지 | com.banking.loan.dto |
| 스테레오타입 | COMMAND/READMODEL |
| 파일 | - |
| 라인 | - |
| 토큰 | - |

#### 요약

> com.banking.loan.dto.LoanApplicationDTO는 대출 신청 건의 데이터를 전달·보관하는 DTO로, applicationId, customerId, applicationDate, requestedAmount, loanType와 함께 loanPurpose(대출 목적), term(기간), interestRate(금리), status(상태) 등 신청 조건을 담는다. 또한 screeningResult(심사 결과), screeningDate(심사일), approvedAmount(승인 금액), approverEmployeeId(승인자 사번), remarks(비고)로 심사/승인 및 메모 정보를 함께 운반한다. approverEmployeeId와 remarks는 외부 입력을 별도 검증·가공 없이 그대로 필드에 대입해 갱신하며, remarks는 현재 값을 그대로 조회할 수 있고, serialVersionUID(1L) 및 전체 정보를 한 줄로 합치는 toString을 제공해 직렬화와 로그/디버깅을 지원한다.

#### 메서드

| 이름 | 시그니처 | 반환타입 | 수정자 | 요약 |
| --- | --- | --- | --- | --- |
| getApplicationId | public String getApplicationId() | - | - | 이 코드는 대출 신청 정보에서 applicationId(신청 식별자)를 외부로 제공하기 위한 조회 동작이다. 내부에 저장된 applicationId 값을 그대로 반환하여, 호출자가 해당 신청 건을 식별하거나 다른 처리(조회/연결/표시)의 키로 사용할 수 있게 한다. 값의 가공, 검증, 상태 변경 없이 보관 중인 식별자만 읽어 반환하므로 부수효과가 없다. |
| setApplicationId | public void setApplicationId(String applicationId) | - | - | 이 코드는 대출 신청 정보에 포함되는 applicationId(신청ID)를 외부에서 전달받아 객체 내부 상태에 반영한다. 전달된 신청ID 값을 applicationId 필드에 그대로 저장함으로써, 이후 신청 건을 식별하거나 연계 처리할 때 사용할 기준 값을 확정한다. 별도의 검증, 변환, 조회 로직 없이 단순 대입만 수행한다. |
| getCustomerId | public String getCustomerId() | - | - | 이 코드는 대출/신청 정보와 함께 관리되는 고객 식별자(customerId)를 외부에서 조회할 수 있도록 반환한다. 내부에 저장된 customerId 값을 그대로 돌려주며, 값의 변환·검증·가공은 수행하지 않는다. 상태를 변경하지 않고 현재 보유 중인 customerId를 읽기 전용으로 제공하는 목적이다. |
| setCustomerId | public void setCustomerId(String customerId) | - | - | 대출 신청 정보를 담는 객체에서 customerId(고객 식별자)를 설정해 내부 상태를 갱신한다. 외부에서 전달된 customerId 값을 그대로 보관 필드에 반영하여, 이후 신청자 식별 및 관련 처리 흐름에서 사용할 수 있게 한다. 별도의 검증, 변환, 조건 분기 없이 값 할당만 수행하며 영속화나 조회 같은 외부 작업은 포함하지 않는다. |
| getApplicationDate | public Date getApplicationDate() | - | - | 이 코드는 대출 신청 정보가 포함된 객체에서 applicationDate(신청일자)를 외부로 제공하기 위해, 내부에 보관 중인 신청일자 값을 그대로 반환한다. 값의 변환, 검증, 포맷 변경 없이 현재 저장된 applicationDate를 조회 용도로 노출하는 동작이다. 어떤 상태값도 변경하지 않으므로 데이터 갱신이나 부수효과 없이 읽기만 수행한다. |
| setApplicationDate | public void setApplicationDate(Date applicationDate) | - | - | 이 코드는 대출 신청 정보가 보유한 applicationDate(신청일자) 값을 외부에서 전달받은 값으로 갱신한다. 입력된 날짜를 별도 검증이나 변환 없이 그대로 내부 상태에 반영하여, 이후 심사일자(screeningDate)나 신청 상태(status) 등 다른 처리에서 신청일자 기준을 사용할 수 있게 한다. 결과적으로 객체의 신청일자 상태를 변경하는 쓰기 성격의 동작이다. |
| getRequestedAmount | public BigDecimal getRequestedAmount() | - | - | 이 코드는 대출 신청 정보에 포함된 금액 관련 속성인 requestedAmount(요청금액)를 외부에서 읽을 수 있도록 제공한다. 저장되어 있는 requestedAmount 값을 변경하지 않고 그대로 반환하여, 신청 시 요청된 금액을 조회하는 용도로 사용된다. 반환값은 금액 표현에 적합한 BigDecimal 형태로 제공된다. |
| setRequestedAmount | public void setRequestedAmount(BigDecimal requestedAmount) | - | - | 대출 신청과 관련된 정보(applicationId, customerId, applicationDate 등)를 보관하는 객체에서 requestedAmount(요청금액) 값을 갱신한다. 외부에서 전달된 금액을 내부 상태로 그대로 반영하여 이후 심사(screeningResult)나 승인금액(approvedAmount) 산정 등 후속 처리의 기준 값으로 사용될 수 있게 한다. 유효성 검증, 반올림/단위 변환, 한도 제한 같은 추가 규칙 없이 단순 대입만 수행한다. |
| getLoanType | public String getLoanType() | - | - | 이 코드는 대출 신청과 관련된 여러 속성(applicationId, customerId, requestedAmount, interestRate, status 등)을 보관하는 객체의 일부로, 대출 상품/구분을 나타내는 loanType 값을 외부로 제공한다. 내부에 저장된 loanType을 그대로 반환하여, 화면 표시나 후속 심사·조건 판단 등에서 대출 유형 값을 일관되게 참조할 수 있게 한다. 값 변환, 검증, 상태 변경 없이 단순 조회만 수행하므로 데이터의 변경을 유발하지 않는다. |
| setLoanType | public void setLoanType(String loanType) | - | - | 대출 신청 정보가 보유한 loanType(대출유형) 값을 외부 입력으로 전달된 값으로 갱신한다. 이를 통해 해당 신청 건이 어떤 대출 상품/유형으로 접수되었는지의 분류 정보를 객체 상태에 반영한다. 검증, 변환, 조회 로직 없이 전달받은 값을 그대로 설정하여 이후 심사/승인 등 후속 처리에서 참조될 수 있도록 한다. |
| getLoanPurpose | public String getLoanPurpose() | - | - | 대출 신청 정보를 구성하는 데이터 집합에서 loanPurpose(대출목적) 값을 외부로 제공하기 위해, 현재 객체에 저장된 loanPurpose를 그대로 반환한다. 계산, 검증, 포맷 변환 없이 보관 중인 값을 조회하는 동작만 수행한다. 이로써 대출목적이 화면 표시, 심사/보고, 후속 처리 흐름에서 일관되게 참조될 수 있도록 한다. |
| setLoanPurpose | public void setLoanPurpose(String loanPurpose) | - | - | 대출 신청 정보를 담는 객체에서 loanPurpose(대출 목적) 값을 외부 입력으로 받아 내부 상태에 반영한다. 전달된 대출 목적 문자열을 현재 객체의 loanPurpose 필드에 그대로 저장하여, 이후 심사(screeningResult)나 상태(status) 판단에 활용될 신청 데이터의 일부를 확정한다. 별도의 검증, 변환, 조회/저장 호출 없이 해당 속성 값만 갱신한다. |
| getTerm | public int getTerm() | - | - | 이 코드는 대출 신청과 관련된 여러 속성(applicationId, customerId, requestedAmount, interestRate, status 등)을 보유하는 객체에서 term(대출 기간) 값을 조회할 수 있도록 제공한다. 내부에 저장된 term을 그대로 반환하여, 대출 기간을 기준으로 상환 기간 산정이나 상품 조건 검증 등의 후속 처리가 가능하게 한다. 데이터 저장이나 status 변경 같은 상태 변경은 수행하지 않고, 보유 중인 값의 읽기만 수행한다. |
| setTerm | public void setTerm(int term) | - | - | 이 코드는 신청 정보에 포함되는 term(기간) 값을 외부 입력으로 받아 객체의 내부 상태에 반영한다. 전달된 기간 값을 term 필드에 그대로 대입하여 이후 심사, 승인금액 산정, 상환기간 계산 등 기간 기반 로직에서 일관되게 사용될 수 있도록 한다. 별도의 유효성 검증, 범위 체크, 변환 처리 없이 값 설정만 수행하므로 기간 값의 검증 책임은 호출 측 또는 다른 검증 단계에 있다. |
| getInterestRate | public BigDecimal getInterestRate() | - | - | 대출 신청 및 심사 관련 정보를 보유하는 객체에서 interestRate(이자율) 값을 조회하기 위해 제공되는 접근자이다. 현재 객체에 저장된 interestRate 값을 그대로 반환하여, 이자율 확인이나 후속 계산(예: 금리 기반 상환/이자 산정)에 활용될 수 있게 한다. 내부 데이터의 변경이나 검증, 외부 자원 접근 없이 읽기만 수행한다. |
| setInterestRate | public void setInterestRate(BigDecimal interestRate) | - | - | 대출 신청 정보에 포함되는 interestRate(이자율)를 외부에서 전달받은 값으로 갱신한다. 전달된 이자율 값이 현재 객체의 interestRate 필드에 그대로 저장되어 이후 승인 금액 산정, 심사 결과 기록 등 관련 처리에서 참조될 수 있게 한다. 값 검증, 범위 체크, 반올림 규칙 적용 같은 추가 비즈니스 규칙은 수행하지 않고 단순 대입만 수행한다. |
| getStatus | public String getStatus() | - | - | 이 코드는 대출 신청과 관련된 여러 속성(applicationId, customerId, requestedAmount, interestRate 등)을 보유하는 객체에서 status(상태) 값을 외부로 제공하기 위한 조회 로직이다. 현재 객체에 저장되어 있는 status 값을 그대로 반환하며, 값의 변환이나 검증, 보정 처리는 수행하지 않는다. 저장소 접근이나 다른 객체 호출 없이 메모리에 이미 존재하는 상태 문자열을 읽기만 하므로 부수효과가 없다. |
| setStatus | public void setStatus(String status) | - | - | 대출 신청 정보로 보이는 객체가 보유한 status(상태) 값을 외부에서 전달된 상태값으로 갱신해, 신청의 현재 처리 상태를 확정한다. 이 로직은 검증, 변환, 추가 계산 없이 전달된 값 그대로를 status에 반영한다. 그 결과 이후 심사(screeningResult, screeningDate)나 승인(approvedAmount) 등 다른 처리 단계에서 참조될 신청 상태가 변경된다. |
| getScreeningResult | public String getScreeningResult() | - | - | 이 코드는 대출 신청 정보가 담긴 데이터에서 screeningResult(심사결과) 값을 외부에 제공하기 위한 조회 동작을 수행한다. 별도의 계산이나 검증, 상태 변경 없이 이미 보관된 screeningResult를 그대로 반환한다. 이를 통해 대출 심사 결과의 현재 값을 다른 처리 흐름(표시, 후속 판단 등)에서 참조할 수 있게 한다. |
| setScreeningResult | public void setScreeningResult(String screeningResult) | - | - | 대출 신청 정보를 담는 객체에서 screeningResult(심사결과)를 외부 입력값으로 갱신해, 이후 심사 상태 판단이나 승인금액(approvedAmount) 확정 같은 후속 흐름에서 사용할 수 있도록 한다. 입력으로 받은 screeningResult(심사결과)를 별도 검증이나 변환 없이 그대로 내부 상태에 반영한다. 이로써 해당 객체의 심사 관련 상태가 변경되며, 조회 목적이 아니라 값 설정(상태 변경) 목적의 동작이다. |
| getScreeningDate | public Date getScreeningDate() | - | - | 이 코드는 대출 신청 전반의 상태값(예: status, screeningResult 등)과 함께 보관되는 screeningDate(심사일자)를 외부에서 확인할 수 있도록 제공한다. 내부에 저장된 screeningDate 값을 변경하거나 가공하지 않고 그대로 반환해, 심사가 수행된 시점을 조회하는 용도로 사용된다. 이 범위에서는 조건 분기, 반복, 예외 처리, 외부 호출 없이 단순히 보관 중인 날짜 정보를 읽기 전용으로 노출한다. |
| setScreeningDate | public void setScreeningDate(Date screeningDate) | - | - | 이 클래스는 대출 신청 건의 진행 상태와 심사 관련 정보를 함께 보관하며, screeningDate(심사일자)를 통해 심사가 수행된 시점을 기록한다. 입력으로 받은 날짜 값을 screeningDate에 그대로 반영하여, 해당 신청 건의 심사 일자를 갱신(상태 변경)한다. 별도의 검증, 변환, 부수효과 없이 값 할당만 수행하므로 호출 흐름이나 외부 연동은 발생하지 않는다. |
| getApprovedAmount | public BigDecimal getApprovedAmount() | - | - | 대출 신청/심사 정보를 담는 객체에서 approvedAmount(승인금액) 값을 외부로 제공하기 위해, 현재 보관 중인 approvedAmount를 그대로 반환한다. 반환 과정에서 값 변환이나 검증, 계산 로직은 수행하지 않으며 상태 변경도 없다. 따라서 승인금액을 조회해 화면 표시나 후속 계산에 사용하도록 하는 읽기 전용 접근 동작이다. |
| setApprovedAmount | public void setApprovedAmount(BigDecimal approvedAmount) | - | - | 대출 심사/승인 정보를 담는 객체에서 approvedAmount(승인금액) 값을 외부 입력으로 받아 내부 상태에 반영한다. 전달받은 승인금액으로 approvedAmount 필드를 즉시 갱신하여 이후 승인 결과 저장, 화면 표시, 후속 처리에서 일관된 승인금액을 사용할 수 있게 한다. 별도의 검증, 계산, 조건 분기 없이 값 설정만 수행하므로 승인금액 확정/수정 의도를 표현하는 단순한 상태 변경 동작이다. |
| getApproverEmployeeId | public String getApproverEmployeeId() | - | - | 이 코드는 대출 신청 관련 데이터 객체가 보유한 approverEmployeeId(승인자 직원 식별자) 값을 외부에서 조회할 수 있도록 제공한다. 내부 상태를 변경하지 않고, 현재 저장된 approverEmployeeId를 그대로 반환한다. 승인 프로세스에서 누가 승인자인지 식별하거나 화면/응답에 표시하기 위한 읽기 전용 접근 지점으로 사용된다. |
| setApproverEmployeeId | public void setApproverEmployeeId(String approverEmployeeId) | - | - | 이 코드는 대출 신청/심사·승인 흐름과 관련된 데이터(예: applicationId, customerId, status, approvedAmount 등)를 보관하는 객체에서 approverEmployeeId(승인자 사번)를 갱신하기 위한 동작이다. 외부에서 전달받은 승인자 식별 값을 해당 객체의 approverEmployeeId 필드에 그대로 반영하여, 이후 승인 이력 추적이나 승인 책임자 식별에 사용될 수 있게 한다. 데이터베이스 저장, 검증, 상태(status) 변경 같은 추가 로직은 수행하지 않고 필드 값만 변경한다. |
| getRemarks | public String getRemarks() | - | - | 대출 신청 정보 전반(applicationId, customerId, requestedAmount, status 등)을 담는 객체에서 remarks(비고) 값을 외부에 제공하기 위해 remarks 필드를 그대로 반환한다. 별도의 가공, 검증, 포맷 변환 없이 현재 보관 중인 비고 내용을 조회하는 용도다. 이 동작은 데이터의 생성/수정/삭제를 수행하지 않으며 상태 변경 없이 읽기만 수행한다. |
| setRemarks | public void setRemarks(String remarks) | - | - | 이 코드는 대출 신청과 관련된 데이터 묶음에서 추가 메모를 나타내는 remarks(비고) 값을 갱신하기 위한 설정 동작이다. 외부에서 전달된 비고 문자열을 현재 객체의 remarks 필드에 그대로 대입하여 기존 값을 새 값으로 덮어쓴다. 값의 공백/길이/형식 등에 대한 검증이나 정규화 없이 단순 대입만 수행한다. 데이터베이스 저장이나 다른 후속 처리 없이 객체 내부 상태만 변경한다. |
| toString | public String toString() | - | - | 대출 신청 정보를 사람이 읽을 수 있는 단일 문자열로 직렬화해 표현하며, 주로 로그/디버깅에서 객체 내용을 빠르게 확인하기 위한 목적이다. 반환 문자열에는 applicationId, customerId, applicationDate, requestedAmount, loanType, loanPurpose, term, interestRate, status가 포함되어 신청의 식별자·신청일·금액·상품/목적·기간·금리·진행상태를 한 번에 확인할 수 있게 한다. 또한 screeningResult, screeningDate, approvedAmount, approverEmployeeId, remarks까지 함께 포함해 심사/승인 결과와 승인자, 비고를 추적 가능하게 만든다. 내부 상태를 변경하지 않고 현재 보유한 값들을 조합해 문자열만 생성해 반환한다. |

#### 필드

| 이름 | 타입 | 수정자 | 요약 |
| --- | --- | --- | --- |
| serialVersionUID | long | - | 자바 직렬화(Serializable) 시 클래스 버전 호환성을 식별하기 위한 고정 상수로, 역직렬화 과정에서 클래스 구조 변경 여부를 검증하는 데 사용된다(값: 1L). |
| applicationId | String | - | 애플리케이션을 식별하기 위한 ID 값을 저장하는 문자열 필드입니다. |
| customerId | String | - | 고객을 식별하기 위한 고유한 고객 ID 값을 문자열로 보관하는 필드입니다. |
| applicationDate | Date | - | 신청이 접수되거나 제출된 날짜/시각을 나타내는 Date 타입의 값으로, 해당 신청이 언제 이루어졌는지 기록·조회하는 데 사용됩니다. |
| requestedAmount | BigDecimal | - | 요청된 금액을 BigDecimal 타입으로 저장하는 필드로, 금전적 계산에서의 정밀도를 유지하기 위해 사용된다. |
| loanType | String | - | 대출의 유형(상품/종류)을 문자열로 저장하는 필드입니다. |
| loanPurpose | String | - | 대출 신청 또는 계약에서 자금이 사용될 목적(예: 주택구입, 전세자금, 사업자금 등)을 문자열로 저장하는 필드입니다. |
| term | int | - | 이 필드는 객체가 다루는 기간(텀/회차/학기 등) 값을 정수로 저장하기 위한 멤버 변수입니다. |
| interestRate | BigDecimal | - | 금리(이자율) 값을 BigDecimal로 보관하는 필드로, 이자 계산이나 금융 조건 설정에 사용되는 비율 데이터를 담는다. |
| status | String | - | 객체의 현재 상태를 나타내는 문자열 값을 저장하는 필드로, 처리 진행 여부나 상태 코드/라벨 등의 상태 정보를 담습니다. |
| screeningResult | String | - | 대상에 대한 스크리닝(검사/심사) 수행 결과를 문자열로 저장하는 필드로, 통과·불합격 같은 판정 값이나 결과 설명/코드를 담는 용도로 사용된다. |
| screeningDate | Date | - | 객체의 스크리닝(검사/심사) 수행 날짜를 나타내는 날짜(Date) 값을 저장하는 필드입니다. |
| approvedAmount | BigDecimal | - | 승인된 금액을 BigDecimal로 저장하는 필드로, 거래나 결제 등의 승인 결과로 확정된 금액 값을 나타낸다. |
| approverEmployeeId | String | - | 승인(결재) 담당자인 직원의 식별자(ID)를 저장하는 문자열 필드입니다. |
| remarks | String | - | 비고 또는 추가 설명을 자유롭게 기록하기 위한 문자열 필드입니다. |

#### 구조 관계

| 방향 | 관계 | 대상 | 속성 |
| --- | --- | --- | --- |
| ← | DEPENDENCY | LoanServlet | source_member=handleGetApplications, usage=cast |
| ← | DEPENDENCY | LoanServlet | source_member=handleCreateApplication, usage=local_new |
| ← | DEPENDENCY | LoanServlet | source_member=handleGetApplication, usage=local_var |
| ← | DEPENDENCY | LoanApplicationSession | source_member=createApplication, usage=parameter |
| ← | DEPENDENCY | LoanApplicationSession | source_member=updateApplication, usage=parameter |
| ← | DEPENDENCY | LoanApplicationSession | source_member=getApplication, usage=return |
| ← | DEPENDENCY | LoanApplicationSessionBean | source_member=getApplication, usage=return |
| ← | DEPENDENCY | LoanApplicationSessionBean | source_member=updateApplication, usage=parameter |
| ← | DEPENDENCY | LoanApplicationSessionBean | source_member=createApplication, usage=parameter |
| ← | DEPENDENCY | LoanProcessSession | source_member=getCurrentApplicationStatus, usage=return |
| ← | DEPENDENCY | LoanProcessSession | source_member=submitAndGetResult, usage=return |
| ← | DEPENDENCY | LoanProcessSessionBean | source_member=getCurrentApplicationStatus, usage=return |
| ← | DEPENDENCY | LoanProcessSessionBean | source_member=submitAndGetResult, usage=return |

#### 호출 관계

| 방향 | 대상 | 호출코드 |
| --- | --- | --- |
| ← | LoanServlet | - |
| ← | LoanApplicationSessionBean | - |
| ← | LoanProcessSessionBean | - |

#### 데이터 접근

| 대상 | 관계 | 근거 | 신뢰도 |
| --- | --- | --- | --- |
| LoanApplicationDTO | REFER_TO | - | 1.0 |

#### 요약 코드

```
없음
```

### LoanLedgerDTO

#### 기본 정보

| 항목 | 값 |
| --- | --- |
| 이름 | LoanLedgerDTO |
| 타입 | CLASS |
| FQN | com.banking.loan.dto.LoanLedgerDTO |
| 패키지 | com.banking.loan.dto |
| 스테레오타입 | COMMAND/READMODEL |
| 파일 | - |
| 라인 | - |
| 토큰 | - |

#### 요약

> com.banking.loan.dto.LoanLedgerDTO는 대출 원장 정보를 다른 계층으로 전달하기 위한 DTO로, ledgerId, applicationId, customerId와 principalAmount(원금), outstandingBalance(미상환잔액), interestRate(이자율), monthlyPayment(월별 결제/지급액) 같은 금액·이율 정보를 BigDecimal로 보관합니다. 또한 loanStartDate(대출 시작일), maturityDate(만기일), lastRepaymentDate(마지막 상환일), nextRepaymentDate(다음 상환 예정일) 등 주요 일자와 repaymentMethod(상환방식), status(상태) 같은 속성을 함께 담아 원장의 현재 상황을 표현합니다. 전반적으로 계산·검증 같은 비즈니스 로직 없이 값의 조회/갱신과 전달에 집중하는 데이터 컨테이너 역할을 수행합니다.

#### 메서드

| 이름 | 시그니처 | 반환타입 | 수정자 | 요약 |
| --- | --- | --- | --- | --- |
| getLedgerId | public String getLedgerId() | - | - | 이 코드는 대출/원장 정보를 보유하는 객체에서 ledgerId(원장 식별자) 값을 외부로 제공하기 위한 조회용 접근을 수행한다. 내부에 저장된 ledgerId를 그대로 반환하며, 값의 가공·검증·변환 로직은 포함하지 않는다. 데이터 저장이나 상태 변경 없이, 현재 객체가 보유한 원장 식별자를 읽기 전용으로 노출하는 목적에 집중한다. |
| setLedgerId | public void setLedgerId(String ledgerId) | - | - | 이 코드는 대출/원장 성격의 도메인 객체가 보유한 ledgerId(원장 식별자)를 외부 입력값으로 갱신한다. 전달받은 원장 식별자 값을 내부 필드 ledgerId에 그대로 대입하여 객체의 상태를 변경한다. 값의 형식 검증, 공백/널 처리, 중복 확인 등의 추가 규칙 없이 단순 설정만 수행한다. |
| getApplicationId | public String getApplicationId() | - | - | 이 코드는 대출/원장 관련 정보(예: ledgerId, customerId, principalAmount 등)를 보유하는 객체에서 applicationId(신청 ID)를 외부로 제공하기 위한 조회 동작을 수행한다. 내부에 저장된 applicationId 값을 그대로 반환하며, 값의 변환이나 검증, 상태 변경은 수행하지 않는다. 따라서 호출자는 해당 객체가 현재 들고 있는 신청 식별자를 읽어가며, 이 동작 자체로는 데이터의 확정/갱신이 발생하지 않는다. |
| setApplicationId | public void setApplicationId(String applicationId) | - | - | 이 코드는 대출/원장 관련 정보를 담는 객체가 보유한 여러 식별자 및 금액/기간 속성 중 applicationId 값을 갱신하는 역할을 한다. 외부에서 전달된 applicationId(애플리케이션 식별자)를 객체 내부의 applicationId 필드에 그대로 대입하여 현재 인스턴스의 상태를 변경한다. 값의 유효성 검증, 형 변환, 부가 계산, 다른 구성요소 호출 없이 단순히 필드 값만 업데이트한다. |
| getCustomerId | public String getCustomerId() | - | - | 이 코드는 대출 원장/신청 정보를 구성하는 데이터 중 customerId(고객 식별자)를 외부에서 조회할 수 있도록 값을 반환한다. 내부에 보관 중인 customerId를 그대로 돌려주며, 값의 변환이나 검증, 상태 변경은 수행하지 않는다. 그 결과, 대출 계약/원장 데이터가 어떤 고객에 속하는지 식별하기 위한 읽기 전용 접근 지점으로 사용된다. |
| setCustomerId | public void setCustomerId(String customerId) | - | - | 이 코드는 원장 식별자(ledgerId), 신청 식별자(applicationId), 금액(principalAmount) 등 대출/원장 관련 속성을 보유하는 객체에서 고객 식별자(customerId)를 갱신하기 위한 동작이다. 외부에서 전달된 고객 식별자 값을 해당 객체의 customerId 필드에 그대로 대입하여 현재 인스턴스의 상태를 변경한다. 별도의 검증, 변환, 조회/저장 호출 없이 메모리 상의 값만 설정하므로 이 설정 결과는 이후 로직에서 고객 기준으로 데이터를 식별·처리하는 데 사용될 수 있다. |
| getPrincipalAmount | public BigDecimal getPrincipalAmount() | - | - | 이 코드는 대출/원장성 데이터 객체가 보유한 principalAmount(원금) 값을 외부에 제공하기 위한 조회용 접근자이다. 내부에 저장된 principalAmount를 그대로 반환하며, 계산·검증·형변환 같은 추가 로직은 수행하지 않는다. 반환 값은 금액 정밀도를 보존하기 위해 BigDecimal 형태로 제공된다. |
| setPrincipalAmount | public void setPrincipalAmount(BigDecimal principalAmount) | - | - | 이 코드는 대출/원장 식별정보(ledgerId, applicationId, customerId)와 금액·이자·기간 정보(principalAmount, outstandingBalance, interestRate, loanStartDate, maturityDate 등)를 보유하는 객체에서 principalAmount(원금) 값을 갱신한다. 외부에서 전달된 원금 값을 내부 상태로 그대로 반영하여 이후 상환액(monthlyPayment) 산정이나 잔액(outstandingBalance) 관리 같은 금액 관련 로직이 최신 원금 기준으로 동작하도록 만든다. 값의 유효성(음수 여부, null 여부 등) 검증이나 보정은 수행하지 않으므로, 입력값의 적정성은 호출자 또는 다른 검증 단계에 의존한다. |
| getOutstandingBalance | public BigDecimal getOutstandingBalance() | - | - | 대출/원장 정보에서 outstandingBalance(미상환잔액)를 외부로 제공하기 위한 조회용 접근자이다. 내부에 보관 중인 outstandingBalance 값을 그대로 반환하며, 값의 계산·보정·검증이나 상태 변경은 수행하지 않는다. 호출자는 반환된 금액을 통해 현재 남아 있는 상환 잔액을 확인하는 용도로 사용할 수 있다. |
| setOutstandingBalance | public void setOutstandingBalance(BigDecimal outstandingBalance) | - | - | 이 코드는 대출/원장성 데이터로 보이는 객체가 보유한 outstandingBalance(미상환잔액) 값을 외부에서 전달받은 값으로 갱신한다. 전달된 금액을 별도 검증이나 변환 없이 그대로 내부 상태에 반영하여, 이후 이 객체를 사용하는 로직에서 최신 잔액을 기준으로 계산(예: 상환 스케줄, 이자 산정, 상태 판단)이 가능하게 한다. 결과적으로 해당 객체의 금액 관련 상태(outstandingBalance)를 쓰기 방식으로 변경하는 역할을 수행한다. |
| getInterestRate | public BigDecimal getInterestRate() | - | - | 이 코드는 대출/원장성 데이터 객체가 보유한 interestRate(이자율) 값을 외부에서 조회할 수 있도록 그대로 반환한다. 계산, 변환, 검증 없이 현재 객체 상태에 저장된 interestRate를 읽기 전용으로 노출하는 역할이다. 따라서 이자율이 설정된 이후 다른 로직에서 이 값을 참조해 이자 계산이나 조건 판단에 활용할 수 있게 한다. |
| setInterestRate | public void setInterestRate(BigDecimal interestRate) | - | - | 대출/원장 정보를 담는 객체에서 interestRate(이자율) 값을 갱신하기 위한 변경 동작을 수행한다. 외부에서 전달된 이자율 값을 현재 객체의 interestRate 필드에 그대로 반영하여, 이후 이자 계산이나 상환 조건 산정에 사용될 기준을 최신화한다. 별도의 검증, 변환, 부가 계산 없이 입력 값을 즉시 상태로 확정한다. |
| getLoanStartDate | public Date getLoanStartDate() | - | - | 이 코드는 대출 원장/계약 정보를 담는 객체가 보유한 loanStartDate(대출 시작일)를 외부에 제공하기 위한 조회 동작이다. 내부에 저장된 loanStartDate 값을 그대로 반환하며, 값의 변환·검증·보정 로직은 수행하지 않는다. 대출 기간 산정, 이자 계산, 만기(maturityDate)와의 비교 등 다른 처리에서 기준일로 활용할 수 있도록 읽기 전용으로 노출한다. |
| setLoanStartDate | public void setLoanStartDate(Date loanStartDate) | - | - | 대출 정보를 담는 객체에서 loanStartDate(대출 시작일)를 외부 입력값으로 갱신한다. 전달된 날짜 값을 별도 검증이나 변환 없이 그대로 내부 상태에 반영해, 이후 이 대출의 기간 산정이나 만기일 계산 등에서 기준이 되는 시작일을 확정한다. 결과적으로 loanStartDate 필드의 값이 변경되는 상태 변경 동작을 수행한다. |
| getMaturityDate | public Date getMaturityDate() | - | - | 이 코드는 대출/원장 성격의 객체가 보유한 만기일(maturityDate) 값을 외부에서 조회할 수 있도록 제공한다. 내부 상태를 변경하지 않고, 이미 설정되어 있는 만기일(Date)을 그대로 반환해 만기 도래 여부 판단이나 스케줄 산정 등 조회 목적의 흐름에서 활용되게 한다. 반환되는 값은 별도 가공이나 검증 없이 저장된 만기일 자체이며, 값이 미설정인 경우에는 그대로 null이 반환될 수 있다. |
| setMaturityDate | public void setMaturityDate(Date maturityDate) | - | - | 이 코드는 대출/원장성 데이터에서 만기일(maturityDate) 값을 관리하기 위한 갱신 동작을 수행한다. 외부에서 전달된 만기일 값을 객체 내부의 maturityDate(만기일) 필드에 그대로 반영해, 이후 만기 판단이나 상환 관련 계산에서 최신 만기일을 사용할 수 있게 한다. 값의 유효성 검증, 포맷 변환, 다른 리소스 저장/조회 같은 부수효과는 포함하지 않는다. |
| getRepaymentMethod | public String getRepaymentMethod() | - | - | 이 코드는 대출(또는 여신) 정보를 담는 객체가 보유한 상환 방식(repaymentMethod)을 외부에서 조회할 수 있도록 값을 반환한다. 입력값이나 추가 연산 없이 현재 객체의 repaymentMethod 필드에 저장된 문자열을 그대로 돌려준다. 상태 변경, 검증, 포맷 변환, 계산 로직이 없으므로 데이터 읽기 목적의 단순 조회 동작이다. |
| setRepaymentMethod | public void setRepaymentMethod(String repaymentMethod) | - | - | 이 코드는 원장/대출 식별자와 금액, 이자율, 기간, 상환 관련 속성들을 보관하는 객체에서 repaymentMethod(상환방식) 값을 갱신한다. 외부에서 전달된 상환방식 문자열을 그대로 repaymentMethod 필드에 대입하여, 이후 월 상환액(monthlyPayment) 계산이나 상태(status) 판단 등 상환 조건을 참조하는 로직이 최신 값을 사용하도록 한다. 값의 형식 검증, 허용 값 체크, 상태 전이 같은 추가 규칙은 수행하지 않고 단순히 상태(필드)를 변경한다. |
| getMonthlyPayment | public BigDecimal getMonthlyPayment() | - | - | 이 코드는 원장/대출과 관련된 여러 속성(ledgerId, principalAmount, outstandingBalance, interestRate, maturityDate 등)을 보관하는 객체 안에서, 월별 상환액을 나타내는 monthlyPayment(월 상환액) 값을 외부로 제공한다. 별도의 계산이나 검증 없이 현재 객체에 저장된 monthlyPayment 값을 그대로 반환해, 상환 계획 표시나 월 납입금 확인 같은 조회 목적에 사용되도록 한다. 내부 상태를 변경하지 않으며, 조회용 접근만 수행한다. |
| setMonthlyPayment | public void setMonthlyPayment(BigDecimal monthlyPayment) | - | - | 이 코드는 대출 원장/계약의 상환 관련 정보를 보관하는 구조에서 monthlyPayment(월 상환금) 값을 갱신하기 위한 동작을 수행한다. 입력으로 받은 월 상환금을 객체의 monthlyPayment 필드에 그대로 저장해 기존 값이 있으면 새 값으로 덮어쓴다. 값의 유효성 검증(예: 0 이하 여부)이나 principalAmount, interestRate, repaymentMethod에 따른 재계산 로직 없이, 월 상환금 확정을 위한 단순 상태 변경만 수행한다. |
| getStatus | public String getStatus() | - | - | 이 코드는 대출/원장 식별 정보와 금액, 이자율, 기간, 상환 방식 같은 속성을 함께 보유하는 객체에서 status(상태) 값을 외부로 제공하기 위한 읽기 전용 접근을 수행한다. 내부에 저장된 status를 가공하거나 변환하지 않고 그대로 반환한다. 이 동작은 상태 변경 없이 현재 상태 값을 조회하는 목적이며, 다른 구성요소 호출이나 외부 자원 접근은 발생하지 않는다. |
| setStatus | public void setStatus(String status) | - | - | 대출/원장성 정보를 보유한 객체에서 status(상태) 값을 외부 입력으로 갱신해 현재 상태를 내부에 확정한다. 입력으로 전달된 상태 문자열을 검증이나 변환 없이 그대로 status 필드에 대입한다. 이로 인해 이후 원금(principalAmount), 미상환잔액(outstandingBalance), 이자율(interestRate), 상환방식(repaymentMethod) 등과 함께 해석되는 대출의 진행 상태가 변경된 것으로 취급될 수 있다. |
| getLastRepaymentDate | public Date getLastRepaymentDate() | - | - | 대출(또는 원장) 정보에 포함된 lastRepaymentDate(마지막 상환일자) 값을 외부에서 확인할 수 있도록 그대로 반환한다. 계산, 변환, 검증 없이 현재 객체가 보유한 마지막 상환일자 상태를 읽기 전용으로 노출하는 역할이다. 이 값은 상환 이력의 최신 시점을 조회하거나 만기일, 연체 판단 등 후속 로직에서 기준일로 활용될 수 있다. |
| setLastRepaymentDate | public void setLastRepaymentDate(Date lastRepaymentDate) | - | - | 이 코드는 대출/원장성 데이터에서 상환 관련 시점을 나타내는 lastRepaymentDate(마지막 상환일)를 갱신하기 위한 설정 로직이다. 입력으로 전달된 날짜 값을 객체 내부의 lastRepaymentDate 필드에 그대로 반영하여, 이후 상태 판단이나 이자/상환 스케줄 계산에 사용될 기준 값을 최신화한다. 별도의 검증, 변환, 조건 분기 없이 전달값을 저장함으로써 마지막 상환일을 명시적으로 변경하는 의도를 갖는다. |
| getNextRepaymentDate | public Date getNextRepaymentDate() | - | - | 이 코드는 대출/상환 정보 객체가 보유한 nextRepaymentDate(다음 상환일) 값을 외부에 제공하기 위해 조회한다. 내부 상태를 변경하거나 계산을 수행하지 않고, 현재 저장된 다음 상환일을 그대로 반환한다. 이를 통해 다른 로직에서 상환 스케줄 확인, 만기일 대비 일정 점검 등 읽기 목적의 날짜 정보를 사용할 수 있게 한다. |
| setNextRepaymentDate | public void setNextRepaymentDate(Date nextRepaymentDate) | - | - | 이 클래스는 대출/원장 식별자와 금액, 금리, 기간, 상환 관련 일자 및 상태 등의 정보를 보관하는 구조로 보이며, 이 범위의 코드는 그중 상환 일정 관리에 필요한 nextRepaymentDate(다음 상환일)를 갱신한다. 입력으로 받은 날짜 값을 객체의 nextRepaymentDate 필드에 그대로 반영하여, 이후 상환 스케줄 계산이나 상태 판단에서 최신 다음 상환일을 사용하도록 한다. 별도의 검증, 변환, 부수효과 없이 필드 값만 변경한다. |
| toString | public String toString() | - | - | 이 코드는 대출 원장 정보가 담긴 객체의 현재 값을 사람이 읽을 수 있는 문자열로 직렬화해 반환한다. 반환 문자열에는 ledgerId, applicationId, customerId 같은 식별자와 principalAmount, outstandingBalance, interestRate, monthlyPayment 같은 금액·이율 정보가 함께 포함된다. 또한 loanStartDate, maturityDate, lastRepaymentDate, nextRepaymentDate 등 주요 일자 정보와 repaymentMethod, status 상태/방식 값도 동일한 형식으로 나열한다. 결과적으로 로그 출력이나 디버깅 시 한 번에 전체 대출 원장 상태를 확인할 수 있도록 고정된 포맷(예: "...{필드=값, ...}")을 구성한다. |

#### 필드

| 이름 | 타입 | 수정자 | 요약 |
| --- | --- | --- | --- |
| serialVersionUID | long | - | 자바 직렬화(Serializable) 시 클래스 버전 호환성을 식별하기 위한 고정 상수로, 역직렬화 과정에서 클래스 구조 변경 여부를 검증하는 데 사용된다(값: 1L). |
| ledgerId | String | - | 원장(ledger)을 식별하기 위한 문자열 ID를 저장하는 필드입니다. |
| applicationId | String | - | 애플리케이션(또는 신청/요청) 단위를 식별하기 위한 고유 ID 문자열을 저장하는 필드입니다. |
| customerId | String | - | 고객을 식별하기 위한 문자열 형태의 고객 ID를 저장하는 필드입니다. |
| principalAmount | BigDecimal | - | 원금(Principal) 금액을 나타내는 값을 BigDecimal로 저장하는 필드입니다. |
| outstandingBalance | BigDecimal | - | 미지급(미결제) 잔액을 금액 단위로 저장하는 필드로, 현재까지 남아 있는 채무나 결제되지 않은 금액을 나타낸다. |
| interestRate | BigDecimal | - | 이 필드는 이자율(금리) 값을 소수점 오차 없이 정밀하게 표현하기 위해 BigDecimal로 보관합니다. |
| loanStartDate | Date | - | 대출이 시작된 날짜(대출 개시일)를 저장하는 날짜 필드입니다. |
| maturityDate | Date | - | 만기일을 나타내는 날짜 정보를 저장하는 필드로, 해당 객체가 표현하는 항목(예: 상품·계약·증권 등)이 언제 만료되는지를 기록하는 데 사용됩니다. |
| repaymentMethod | String | - | 상환 방식(예: 원리금균등, 원금균등, 만기일시상환 등)을 문자열로 저장하는 필드입니다. |
| monthlyPayment | BigDecimal | - | 매달 지급되거나 납부해야 하는 금액(월별 결제/지급액)을 정밀한 금액 계산을 위해 BigDecimal로 저장하는 필드입니다. |
| status | String | - | 객체의 현재 상태를 나타내는 문자열 값을 저장하는 필드입니다. |
| lastRepaymentDate | Date | - | 마지막 상환이 이루어진 날짜/시점을 저장하는 날짜(Date) 필드입니다. |
| nextRepaymentDate | Date | - | 다음 상환(대출/채무) 예정일을 나타내는 날짜 값을 저장하는 필드입니다. |

#### 구조 관계

| 방향 | 관계 | 대상 | 속성 |
| --- | --- | --- | --- |
| ← | DEPENDENCY | LoanServlet | source_member=handleExecuteLoan, usage=local_var |
| ← | DEPENDENCY | LoanServlet | source_member=handleGetLedger, usage=local_var |
| ← | DEPENDENCY | DebtCollectionSessionBean | source_member=getWrittenOffLedgers, usage=local_new |
| ← | DEPENDENCY | LoanExecutionSession | source_member=getLedger, usage=return |
| ← | DEPENDENCY | LoanExecutionSession | source_member=executeLoan, usage=return |
| ← | DEPENDENCY | LoanExecutionSessionBean | source_member=getLedger, usage=return |
| ← | DEPENDENCY | LoanExecutionSessionBean | source_member=ledgerEntityToDTO, usage=local_new |
| ← | DEPENDENCY | LoanExecutionSessionBean | source_member=executeLoan, usage=return |
| ← | DEPENDENCY | LoanLedgerSession | source_member=calculateRemainingSchedule, usage=return |
| ← | DEPENDENCY | LoanLedgerSession | source_member=getLedger, usage=return |
| ← | DEPENDENCY | LoanLedgerSessionBean | source_member=getLedger, usage=return |
| ← | DEPENDENCY | LoanLedgerSessionBean | source_member=entityToDTO, usage=local_new |
| ← | DEPENDENCY | LoanLedgerSessionBean | source_member=calculateRemainingSchedule, usage=return |

#### 호출 관계

| 방향 | 대상 | 호출코드 |
| --- | --- | --- |
| ← | LoanServlet | - |
| ← | DebtCollectionSessionBean | - |
| ← | LoanExecutionSessionBean | - |
| ← | LoanLedgerSessionBean | - |

#### 데이터 접근

| 대상 | 관계 | 근거 | 신뢰도 |
| --- | --- | --- | --- |
| LoanLedgerDTO | REFER_TO | - | 1.0 |

#### 요약 코드

```
없음
```

### RepaymentDTO

#### 기본 정보

| 항목 | 값 |
| --- | --- |
| 이름 | RepaymentDTO |
| 타입 | CLASS |
| FQN | com.banking.loan.dto.RepaymentDTO |
| 패키지 | com.banking.loan.dto |
| 스테레오타입 | COMMAND/READMODEL |
| 파일 | - |
| 라인 | - |
| 토큰 | - |

#### 요약

> com.banking.loan.dto.RepaymentDTO는 대출 상환 정보를 외부 계층 간에 전달하기 위한 DTO로, repaymentId(상환 식별자), ledgerId(원장 식별자), repaymentDate(상환일자), principalAmount(원금), interestAmount(이자), penaltyAmount(위약금), totalAmount(총액), repaymentType(상환유형), transactionId(거래 식별자) 같은 식별/일자/금액/유형 속성을 보관한다. transactionId는 외부 입력값을 별도의 검증·변환 없이 그대로 저장(set)하여 상환 정보와 특정 거래를 매칭하는 데 사용되므로, 호출 측이 형식과 존재성을 보장해야 한다. 또한 객체의 현재 상태를 사람이 읽기 쉬운 문자열로 반환하는 기능을 제공해 로깅/디버깅/표시에서 모든 필드 값을 확인할 수 있으며, 직렬화 호환을 위한 serialVersionUID=1L을 가진다. 유효성 검증, 포맷 변환, 저장 처리, 또는 principalAmount/interestAmount/penaltyAmount 변경에 따른 totalAmount 재계산 같은 부수효과는 수행하지 않는다.

#### 메서드

| 이름 | 시그니처 | 반환타입 | 수정자 | 요약 |
| --- | --- | --- | --- | --- |
| getRepaymentId | public String getRepaymentId() | - | - | 상환 정보를 표현하는 데이터에서 repaymentId(상환 식별자)를 외부로 제공하기 위한 조회 동작이다. 내부에 보관 중인 repaymentId 값을 그대로 반환하여 상환 건을 식별하거나 다른 처리 흐름에서 참조할 수 있게 한다. 계산, 검증, 변환, 저장 등의 부수효과는 없으며 객체 상태를 변경하지 않는다. |
| setRepaymentId | public void setRepaymentId(String repaymentId) | - | - | 이 코드는 상환 정보 묶음에서 repaymentId(상환 식별자)를 갱신하기 위한 값 설정 로직이다. 외부에서 전달된 상환 식별자 값을 객체 내부의 repaymentId 필드에 그대로 반영해, 이후 ledgerId, repaymentDate, totalAmount 등 다른 상환 관련 데이터와 함께 동일 상환 건을 추적할 수 있게 한다. 별도의 검증, 변환, 조건 분기 없이 단순 대입만 수행하므로 입력 값이 무엇이든 현재 객체 상태를 해당 값으로 덮어쓴다. |
| getLedgerId | public String getLedgerId() | - | - | 이 코드는 상환 내역을 구성하는 식별 정보들(repaymentId, ledgerId, transactionId 등) 중 ledgerId(원장 식별자)를 외부에서 조회할 수 있도록 값을 반환한다. 호출자는 반환된 ledgerId를 통해 해당 상환 건이 어떤 원장(ledger)에 연결되어 있는지 식별하고, 후속 조회나 연계 처리의 키로 활용할 수 있다. 내부 상태를 변경하거나 계산을 수행하지 않고, 이미 보관된 ledgerId 값을 그대로 읽어 제공하는 읽기 동작이다. |
| setLedgerId | public void setLedgerId(String ledgerId) | - | - | 이 코드는 상환 정보(예: repaymentId, repaymentDate, principalAmount, totalAmount 등)를 담는 객체에서 ledgerId(원장 식별자)를 갱신하는 역할을 한다. 외부에서 전달된 원장 식별자 값을 해당 객체의 ledgerId 필드에 그대로 저장하여, 상환 내역이 어떤 원장(ledgerId)에 속하는지 연결관계를 확정한다. 유효성 검증이나 형식 변환 없이 값 할당만 수행하므로, 이후 처리에서 ledgerId 기반의 연계/조회/정합성 판단을 가능하게 하는 상태 변경 지점이 된다. |
| getRepaymentDate | public Date getRepaymentDate() | - | - | 이 코드는 상환 정보가 보유한 repaymentDate(상환일자) 값을 외부에서 조회할 수 있도록 그대로 반환한다. 내부 상태를 변경하거나 계산을 수행하지 않고, 저장된 repaymentDate를 읽기 전용으로 노출하는 목적이다. 따라서 상환일자 확인이나 화면/응답 구성 등 후속 처리에서 날짜 값을 참조할 수 있게 한다. |
| setRepaymentDate | public void setRepaymentDate(Date repaymentDate) | - | - | 이 코드는 상환 정보에서 repaymentDate(상환일자)를 객체 내부 상태로 확정하기 위해 값을 갱신한다. 입력으로 받은 Date 값을 그대로 repaymentDate 필드에 저장하여, 이후 상환 내역의 기준 일자가 일관되게 참조되도록 한다. 검증, 변환, 조건 분기 없이 전달된 값으로 상태만 변경한다. |
| getPrincipalAmount | public BigDecimal getPrincipalAmount() | - | - | 이 코드는 상환 내역에서 금액 구성 요소를 보관하는 값들(예: principalAmount, interestAmount, penaltyAmount, totalAmount) 중 principalAmount(원금금액)를 외부로 제공하기 위한 조회 동작이다. 현재 객체에 저장되어 있는 principalAmount 값을 그대로 반환하여, 원금금액을 화면 표시나 합계 계산 등 후속 처리에서 재사용할 수 있게 한다. 내부 상태를 변경하거나 추가 계산·검증을 수행하지 않고, 보관 중인 값을 읽기 전용으로 노출한다. |
| setPrincipalAmount | public void setPrincipalAmount(BigDecimal principalAmount) | - | - | 상환 내역을 표현하는 객체에서 principalAmount(원금금액) 값을 외부 입력으로 받아 내부 상태에 반영한다. 전달된 금액을 그대로 principalAmount 필드에 대입하며, 유효성 검증이나 금액 계산(예: totalAmount 갱신)은 수행하지 않는다. 그 결과 이 객체의 원금 관련 상태가 변경되어 이후 이자/연체료/총액 계산 또는 거래 식별(transactionId)과 함께 상환 처리 흐름에서 사용될 수 있는 값을 확정한다. |
| getInterestAmount | public BigDecimal getInterestAmount() | - | - | 이 코드는 상환 내역을 나타내는 데이터에서 이자 금액(interestAmount)을 외부에서 조회할 수 있도록 값을 그대로 반환한다. principalAmount(원금), penaltyAmount(연체/벌금), totalAmount(총액) 등과 함께 구성되는 상환 금액 정보 중 ‘이자’ 항목을 읽기 전용으로 제공하는 역할이다. 별도의 계산, 검증, 포맷 변환 없이 현재 보관 중인 interestAmount 값을 그대로 돌려주므로 상태 변경은 발생하지 않는다. |
| setInterestAmount | public void setInterestAmount(BigDecimal interestAmount) | - | - | 상환(또는 상환내역) 정보를 표현하는 객체에서 interestAmount(이자금액) 값을 외부 입력으로 받아 내부 상태에 반영한다. 전달받은 이자금액을 그대로 interestAmount 필드에 저장하여 이후 totalAmount(총액) 계산이나 원장 반영 등 후속 처리에서 사용할 수 있게 한다. 값의 유효성 검증, 금액 정규화, 부가 계산 로직은 수행하지 않으며 단순히 상태를 갱신하는 역할에 집중한다. |
| getPenaltyAmount | public BigDecimal getPenaltyAmount() | - | - | 이 코드는 상환 정보(원금, 이자, 연체/패널티, 합계 등) 중 penaltyAmount(연체/패널티 금액) 값을 외부에서 조회할 수 있도록 반환한다. 내부에 저장된 penaltyAmount를 가공하거나 계산하지 않고 그대로 돌려준다. 따라서 상환 내역에서 연체/패널티 금액을 화면 표시나 후속 계산에 사용하기 위한 읽기 전용 접근 지점 역할을 한다. |
| setPenaltyAmount | public void setPenaltyAmount(BigDecimal penaltyAmount) | - | - | 이 클래스는 상환 내역에서 repaymentId, ledgerId, repaymentDate, principalAmount, interestAmount, penaltyAmount, totalAmount, repaymentType, transactionId 같은 금액/식별 정보를 보관한다. 이 범위의 코드는 외부에서 전달된 연체/지연에 따른 penaltyAmount(벌금/지연손해금 금액)를 현재 객체의 penaltyAmount 필드에 그대로 반영해 금액 구성 요소를 갱신한다. 값의 유효성 검증이나 totalAmount 등 다른 금액 필드 재계산은 수행하지 않으며, 단순히 penaltyAmount 상태만 변경한다. |
| getTotalAmount | public BigDecimal getTotalAmount() | - | - | 이 코드는 상환 정보에서 totalAmount(총액)을 외부로 제공하기 위해, 현재 객체가 보유 중인 totalAmount 값을 그대로 반환한다. 반환 과정에서 계산, 검증, 변환 같은 추가 처리는 수행하지 않으며 저장된 총액 값을 단순 조회한다. 따라서 호출 측은 상환 원금·이자·연체료 등의 합산 결과로 관리되는 totalAmount를 읽어가는 용도로 사용할 수 있다. |
| setTotalAmount | public void setTotalAmount(BigDecimal totalAmount) | - | - | 이 코드는 상환 정보를 담는 객체에서 totalAmount(총금액) 값을 외부에서 전달받아 내부 상태로 반영한다. 전달된 총금액을 객체의 totalAmount 필드에 그대로 대입해, 이후 상환 레코드의 금액 표현이 최신 값으로 유지되도록 한다. principalAmount(원금), interestAmount(이자), penaltyAmount(연체/벌금) 등의 금액 구성요소와 별개로, 합산 결과로서의 totalAmount를 확정적으로 갱신하는 동작이다. |
| getRepaymentType | public String getRepaymentType() | - | - | 이 코드는 상환 정보를 담는 객체가 보유한 여러 속성(예: repaymentId, ledgerId, repaymentDate, principalAmount, interestAmount, penaltyAmount, totalAmount, transactionId) 중 repaymentType(상환유형)을 외부에서 조회할 수 있도록 값을 반환한다. 내부에 저장된 repaymentType 값을 그대로 돌려주며, 값의 변환·검증·계산이나 상태 변경은 수행하지 않는다. 결과적으로 상환유형을 화면 표시, 분기 처리, 보고서/전표 생성 등 후속 로직에서 참조할 수 있게 읽기 전용으로 제공한다. |
| setRepaymentType | public void setRepaymentType(String repaymentType) | - | - | 이 코드는 상환 정보를 담는 객체에서 repaymentType(상환유형) 값을 외부 입력으로 받아 내부 상태에 반영한다. 전달된 상환유형 문자열을 검증하거나 변환하지 않고 그대로 저장하므로, 이후 totalAmount(총액) 등 다른 상환 관련 값들과 함께 상환 처리 흐름에서 구분 기준으로 사용될 수 있다. 결과적으로 이 범위는 조회가 아니라 repaymentType 필드 값을 변경하는 상태 변경 동작에 해당한다. |
| getTransactionId | public String getTransactionId() | - | - | 이 코드는 상환(Repayment) 관련 데이터 모델이 보유한 거래 식별 정보 중 transactionId 값을 외부에서 조회할 수 있도록 제공한다. 내부에 저장된 transactionId를 그대로 반환하며, 값의 변환이나 검증, 포맷팅 같은 추가 규칙은 적용하지 않는다. 데이터 저장이나 상태 변경 없이 읽기 목적의 접근만 수행하므로, 상환 건이 어떤 거래와 연결되는지 식별하기 위한 조회 용도로 사용된다. |
| setTransactionId | public void setTransactionId(String transactionId) | - | - | 이 코드는 상환 내역을 표현하는 데이터 구조에서 transactionId(거래식별자)를 외부 입력값으로 갱신한다. 이를 통해 상환 정보(repaymentId, ledgerId, repaymentDate, principalAmount, interestAmount, penaltyAmount, totalAmount, repaymentType)와 특정 거래를 매칭할 수 있도록 거래 추적 식별자를 확정한다. 별도의 검증이나 변환 없이 전달받은 값을 그대로 저장하므로, 호출 측이 올바른 거래식별자 형식/존재성을 보장해야 한다. |
| toString | public String toString() | - | - | 상환 정보를 담고 있는 객체의 현재 상태를 사람이 읽기 쉬운 문자열 형태로 직렬화해 반환한다. 반환 문자열에는 repaymentId, ledgerId, repaymentDate, principalAmount, interestAmount, penaltyAmount, totalAmount, repaymentType, transactionId 값이 모두 포함되며, 각 항목이 어떤 키에 대응하는지 식별 가능한 형태로 구성된다. 이 로직은 필드 값을 변경하거나 외부 저장소에 반영하지 않고, 디버깅/로깅/화면 표시 등 조회 목적의 표현을 제공하는 데 초점이 있다. |

#### 필드

| 이름 | 타입 | 수정자 | 요약 |
| --- | --- | --- | --- |
| serialVersionUID | long | - | 자바 직렬화(Serializable) 시 클래스 버전 호환성을 식별하기 위한 고정 상수로, 역직렬화 과정에서 클래스 구조 변경 여부를 검증하는 데 사용된다(값: 1L). |
| repaymentId | String | - | 상환 건(상환 거래/요청)을 식별하기 위한 고유한 문자열 ID를 저장하는 필드입니다. |
| ledgerId | String | - | 원장(ledger)을 식별하기 위한 고유 ID 문자열을 저장하는 필드입니다. |
| repaymentDate | Date | - | 상환(대출/채무) 금액을 실제로 갚은 날짜 또는 상환 예정일을 나타내는 날짜 정보이다. |
| principalAmount | BigDecimal | - | 원금(Principal) 금액을 나타내는 값을 BigDecimal로 저장하는 필드입니다. |
| interestAmount | BigDecimal | - | 이 필드는 이자 금액을 나타내는 값을 고정소수점(BigDecimal)으로 저장한다. |
| penaltyAmount | BigDecimal | - | 위약금(패널티) 금액을 BigDecimal로 저장하는 필드로, 계약 위반이나 조건 불이행 시 부과되는 금전적 페널티의 값을 정밀한 금액 단위로 관리한다. |
| totalAmount | BigDecimal | - | 전체 금액(총 합계)을 고정소수점 방식으로 정확하게 저장하기 위한 금액 필드입니다. |
| repaymentType | String | - | 상환 유형을 나타내는 문자열로, 해당 거래나 계약에서 원금·이자 상환이 어떤 방식(예: 원리금균등, 원금균등, 만기일시 등)으로 이루어지는지를 저장한다. |
| transactionId | String | - | 각 거래(트랜잭션)를 고유하게 식별하기 위한 문자열 식별자 값을 저장하는 필드입니다. |

#### 구조 관계

| 방향 | 관계 | 대상 | 속성 |
| --- | --- | --- | --- |
| ← | DEPENDENCY | LoanServlet | source_member=handleProcessRepayment, usage=local_var |
| ← | DEPENDENCY | LoanLedgerSession | source_member=processRepayment, usage=return |
| ← | DEPENDENCY | LoanLedgerSessionBean | source_member=processRepayment, usage=return |

#### 호출 관계

| 방향 | 대상 | 호출코드 |
| --- | --- | --- |
| ← | LoanServlet | - |
| ← | LoanLedgerSessionBean | - |

#### 데이터 접근

| 대상 | 관계 | 근거 | 신뢰도 |
| --- | --- | --- | --- |
| RepaymentDTO | REFER_TO | - | 1.0 |

#### 요약 코드

```
없음
```

### ScreeningResultDTO

#### 기본 정보

| 항목 | 값 |
| --- | --- |
| 이름 | ScreeningResultDTO |
| 타입 | CLASS |
| FQN | com.banking.loan.dto.ScreeningResultDTO |
| 패키지 | com.banking.loan.dto |
| 스테레오타입 | COMMAND/READMODEL |
| 파일 | - |
| 라인 | - |
| 토큰 | - |

#### 요약

> com.banking.loan.dto.ScreeningResultDTO는 대출 신청에 대한 스크리닝/심사 결과를 전달·보관하기 위한 DTO로, customerId(고객 ID)와 creditScore(신용점수), creditGrade(신용등급), dtiRatio(DTI 비율), ltvRatio(LTV 비율) 등 심사 지표를 함께 담습니다. 또한 approved(승인 여부)와 approvedAmount(승인금액), approvedRate(승인비율/금리)로 승인 결과를 표현하고, screeningDate(심사일시)로 심사가 수행된 시점을 기록합니다. reasons(사유 목록)와 screenedBy(심사 수행자)를 포함해 승인/거절 판단의 근거와 담당 주체를 함께 전달합니다.

#### 메서드

| 이름 | 시그니처 | 반환타입 | 수정자 | 요약 |
| --- | --- | --- | --- | --- |
| getApplicationId | public String getApplicationId() | - | - | 이 코드는 신청 심사/승인 결과와 관련된 여러 속성(applicationId, customerId, creditScore, approvedAmount 등)을 보관하는 객체에서 applicationId(신청 식별자) 값을 외부로 제공하기 위한 조회 동작을 수행한다. 내부에 저장된 applicationId를 가공하거나 검증하지 않고 그대로 반환한다. 이를 통해 다른 처리 흐름에서 특정 신청 건을 식별하고 연계(조회·로깅·후속 처리)할 수 있도록 한다. |
| setApplicationId | public void setApplicationId(String applicationId) | - | - | 이 코드는 신용평가/심사 결과(creditScore, creditGrade, dtiRatio, ltvRatio, approved 등)와 함께 신청 건의 식별 정보를 보관하는 객체에서, applicationId(신청 식별자)를 설정하기 위한 동작이다. 외부에서 전달된 신청 식별자 값을 내부 상태의 applicationId 필드에 그대로 반영하여 이후 심사일(screeningDate)이나 승인금액(approvedAmount) 같은 다른 판단/결과 정보와 동일한 신청 건으로 연결될 수 있게 한다. 별도의 검증, 변환, 조건 분기 없이 단순 대입만 수행하며 다른 객체 호출이나 외부 리소스 접근은 발생하지 않는다. |
| getCustomerId | public String getCustomerId() | - | - | 이 클래스는 신청 식별자, 고객 식별자(customerId), 신용 관련 지표(creditScore, creditGrade, dtiRatio, ltvRatio)와 승인 여부 및 승인 조건(approved, approvedAmount, approvedRate), 심사 정보(screeningDate, reasons, screenedBy) 등을 보관한다. 이 범위의 로직은 내부에 저장된 customerId(고객 식별자) 값을 그대로 반환하여 외부에서 고객 식별자를 조회할 수 있게 한다. 계산, 검증, 상태 변경 없이 단순 조회만 수행한다. |
| setCustomerId | public void setCustomerId(String customerId) | - | - | 이 클래스는 applicationId, customerId, creditScore, approved 등 신용심사 결과/상태를 구성하는 여러 속성을 보유하며, 그중 customerId(고객식별자)를 외부 입력으로 갱신할 수 있게 한다. 전달받은 customerId 값을 내부 속성 customerId에 그대로 저장하여 이후 심사 사유(reasons)나 승인 여부(approved) 등과 함께 동일 고객 기준으로 상태를 유지하도록 한다. 별도의 검증, 변환, 조회 로직 없이 값 대입만 수행하므로, 호출 시점에 제공된 고객식별자를 객체의 현재 상태로 확정하는 역할을 한다. |
| getCreditScore | public int getCreditScore() | - | - | 이 클래스는 신청 식별자, 신용평가 결과(creditScore, creditGrade), 비율 지표(dtiRatio, ltvRatio), 승인 여부와 승인 조건(approvedAmount, approvedRate) 등을 보관하는 데이터를 다룬다. 이 범위의 로직은 creditScore(신용점수) 값을 외부에서 조회할 수 있도록 그대로 반환한다. 내부 상태를 변경하거나 추가 계산을 수행하지 않고, 현재 보관 중인 신용점수의 단순 조회만 제공한다. |
| setCreditScore | public void setCreditScore(int creditScore) | - | - | 이 코드는 신용심사/승인 결과를 담는 객체에서 creditScore(신용점수) 값을 갱신하기 위한 설정 로직이다. 외부에서 전달된 정수값을 그대로 creditScore 필드에 저장하여, 이후 approved(승인 여부), creditGrade(신용등급), approvedAmount(승인금액) 같은 판단/결과 정보의 기반 데이터로 활용되도록 한다. 별도의 검증, 변환, 부가 계산 없이 현재 객체의 상태만 변경한다. |
| getCreditGrade | public String getCreditGrade() | - | - | 이 클래스는 신용평가/심사 결과를 나타내는 여러 속성(applicationId, customerId, creditScore, creditGrade, dtiRatio, ltvRatio, approved 등)을 보유한다. 이 범위의 로직은 저장된 creditGrade(신용등급) 값을 그대로 반환하여, 외부에서 신용등급을 조회할 수 있게 한다. 입력값 검증, 변환, 계산 또는 승인 여부(approved) 변경과 같은 상태 변경은 수행하지 않는다. 따라서 현재 객체에 기록된 신용등급을 읽기 용도로 제공하는 단순 조회 동작이다. |
| setCreditGrade | public void setCreditGrade(String creditGrade) | - | - | 이 클래스는 신청 건의 심사 결과(creditScore, creditGrade, dtiRatio, ltvRatio, approved 등)를 보관하는 데이터 구조이며, 이 범위의 코드는 그중 creditGrade(신용등급)를 외부에서 전달받은 값으로 갱신한다. 전달된 등급 값을 객체 내부 상태에 그대로 반영하여 이후 승인 여부(approved)나 승인 한도/금리(approvedAmount, approvedRate) 결정 로직에서 참조될 수 있도록 한다. 별도의 검증, 변환, 부수효과 없이 creditGrade 필드만 변경한다. |
| getDtiRatio | public BigDecimal getDtiRatio() | - | - | 이 코드는 신용평가/심사 결과를 담는 데이터에서 dtiRatio(총부채상환비율)를 외부로 제공하기 위해, 현재 객체에 저장된 dtiRatio 값을 그대로 반환한다. 계산, 변환, 검증 같은 추가 로직 없이 저장된 값을 조회하는 목적의 접근자이다. 이 반환값은 이후 승인 여부(approved), 승인금액(approvedAmount)·승인금리(approvedRate) 등 다른 심사 결과와 함께 화면 표시나 후속 판단을 위한 입력으로 사용될 수 있다. |
| setDtiRatio | public void setDtiRatio(BigDecimal dtiRatio) | - | - | 이 클래스는 신청 건의 신용평가 및 심사 결과(creditScore, creditGrade, dtiRatio, ltvRatio, approved 등)를 보관하는 데이터를 관리하며, 이 구간은 그중 dtiRatio(DTI 비율)를 갱신하는 역할을 한다. 외부에서 전달된 DTI 비율 값을 객체 내부의 dtiRatio 필드에 그대로 반영하여 이후 승인 여부(approved)나 승인 조건(approvedAmount, approvedRate) 판단에 활용될 수 있는 상태를 업데이트한다. 별도의 검증, 계산, 변환 없이 값 대입만 수행하므로 입력 값의 유효성 보장은 호출 측에 위임된다. |
| getLtvRatio | public BigDecimal getLtvRatio() | - | - | 이 객체는 신청/심사 결과와 관련된 여러 지표(creditScore, dtiRatio, ltvRatio 등)를 보관하는 구조를 전제로 한다. 이 범위의 로직은 보관 중인 ltvRatio(담보인정비율) 값을 그대로 반환하여, 외부에서 해당 비율을 조회할 수 있게 한다. 값의 계산, 보정, 검증이나 상태 변경은 수행하지 않으며 단순 조회만 제공한다. |
| setLtvRatio | public void setLtvRatio(BigDecimal ltvRatio) | - | - | 이 클래스는 대출/신용 심사 결과를 구성하는 다양한 속성(applicationId, creditScore, dtiRatio, ltvRatio 등)을 보관하며, 그중 ltvRatio(LTV 비율)를 외부 입력값으로 갱신하는 역할을 한다. 전달받은 LTV 비율 값을 객체 내부의 ltvRatio 필드에 그대로 반영하여 이후 승인 여부(approved), 승인 한도(approvedAmount) 같은 심사 결과 판단/표시에 사용될 수 있게 한다. 값 검증, 범위 체크, 변환 로직 없이 단순 대입만 수행하므로 입력값의 유효성은 호출 측 또는 다른 검증 로직에 의해 보장된다는 전제를 가진다. |
| isApproved | public boolean isApproved() | - | - | 이 객체는 applicationId, customerId, creditScore, creditGrade, dtiRatio, ltvRatio, approved, approvedAmount, approvedRate, screeningDate, reasons, screenedBy 등 심사 결과와 관련된 정보를 보관한다. 이 범위의 로직은 approved(승인여부) 필드 값을 그대로 반환하여 현재 심사 결과가 승인인지 여부를 조회할 수 있게 한다. 내부 상태를 변경하지 않고 저장/외부 연동도 수행하지 않는 순수 조회 동작이다. |
| setApproved | public void setApproved(boolean approved) | - | - | 이 코드는 신용심사 결과를 나타내는 데이터에서 approved(승인여부) 상태를 외부 입력값으로 갱신한다. 전달된 승인 여부를 그대로 내부 approved 필드에 반영하여, 이후 approvedAmount(승인금액), approvedRate(승인금리), screeningDate(심사일자) 등 후속 판단/표시에 사용될 승인 상태의 기준을 확정한다. 검증, 조건 분기, 연관 데이터 동기화 없이 단일 플래그 값을 변경하는 목적의 상태 변경 동작이다. |
| getApprovedAmount | public BigDecimal getApprovedAmount() | - | - | 이 클래스는 신청(applicationId)과 고객(customerId)의 심사 결과로 산출된 승인 여부(approved), 승인 금액(approvedAmount), 승인 금리(approvedRate) 등 핵심 판단 값을 보관한다. 이 범위의 로직은 승인된 금액을 나타내는 approvedAmount 값을 그대로 반환하여, 외부에서 심사 결과의 승인 한도를 조회할 수 있게 한다. 값의 계산, 검증, 갱신은 수행하지 않으며 이미 확정·저장된 승인 결과 수치를 읽기 전용으로 제공한다. |
| setApprovedAmount | public void setApprovedAmount(BigDecimal approvedAmount) | - | - | 이 코드는 신용심사 결과 데이터 중 approvedAmount(승인금액)을 외부에서 전달된 값으로 갱신한다. 승인 여부(approved)나 승인금리(approvedRate)와 함께 심사 결과를 구성하는 핵심 값인 승인금액을 객체 내부 상태로 확정해 이후 처리(예: 결과 조회/저장/출력)에 사용되도록 한다. 별도의 검증, 계산, 조건 분기 없이 입력으로 받은 금액을 그대로 반영한다. |
| getApprovedRate | public BigDecimal getApprovedRate() | - | - | 이 코드는 신용 심사 결과 객체가 보유한 승인 관련 정보를 제공하기 위한 조회 동작의 일부로, approvedRate(승인 금리)를 외부로 노출한다. 별도의 계산이나 검증 없이 이미 저장되어 있는 approvedRate 값을 그대로 반환한다. 이 반환값은 승인 조건을 화면 표시, 후속 판단, 또는 보고 목적으로 조회할 때 사용될 수 있다. |
| setApprovedRate | public void setApprovedRate(BigDecimal approvedRate) | - | - | 이 코드는 대출 심사/스크리닝 결과로 관리되는 여러 값들(예: approved, approvedAmount, approvedRate 등) 중 approvedRate(승인금리)를 갱신하기 위한 변경 처리이다. 외부에서 전달된 승인금리 값을 객체 내부의 approvedRate 필드에 그대로 반영하여, 이후 승인 결과 산출이나 화면/보고서 출력에 사용할 수 있도록 상태를 확정한다. 검증, 계산, 조회 로직 없이 단순 대입만 수행하므로 값의 유효성 판단은 이 범위 밖에서 이뤄진다는 전제를 가진다. |
| getScreeningDate | public Date getScreeningDate() | - | - | 이 클래스는 신청/심사 결과와 관련된 식별자(applicationId, customerId), 신용정보(creditScore, creditGrade), 비율값(dtiRatio, ltvRatio), 승인 여부/조건(approved, approvedAmount, approvedRate) 및 사유(reasons) 등을 함께 보관한다. 이 범위의 로직은 심사가 수행된 시점인 screeningDate(심사일자)를 외부에서 조회할 수 있도록 그대로 반환한다. 내부 상태를 변경하지 않고, 저장된 심사일자 값을 읽기 전용으로 노출하는 목적의 동작이다. |
| setScreeningDate | public void setScreeningDate(Date screeningDate) | - | - | 이 코드는 신청/심사 결과 정보를 담는 객체가 보유한 screeningDate(심사일자) 값을 외부에서 전달받아 내부 상태로 확정 반영한다. 입력으로 받은 Date 값이 그대로 screeningDate 필드에 대입되며, 추가 검증이나 변환 로직은 수행하지 않는다. 이를 통해 이후 승인 여부(approved), 승인 금액(approvedAmount), 승인 금리(approvedRate) 등 심사 결과 데이터와 함께 심사 기준 시점을 일관되게 기록할 수 있게 한다. |
| getReasons | public List getReasons() | - | - | 이 클래스는 applicationId, customerId, creditScore, creditGrade, dtiRatio, ltvRatio, approved, approvedAmount, approvedRate, screeningDate 등의 심사 결과 정보와 함께 심사 사유 목록(reasons)을 보관한다. 이 범위의 로직은 현재 인스턴스에 저장된 reasons(심사 사유 목록)을 외부로 그대로 제공해, 심사 결과에 대한 설명/근거를 조회할 수 있게 한다. 목록을 가공하거나 추가·삭제하지 않으며, 어떤 값도 변경하지 않는 순수 조회 동작이다. |
| setReasons | public void setReasons(List reasons) | - | - | 이 코드는 신청 심사 결과를 나타내는 정보 묶음에서, reasons(사유 목록) 값을 외부 입력으로 갱신하기 위해 사용된다. 전달받은 사유 목록을 그대로 내부 상태의 reasons에 대입하여 이후 승인 여부(approved)나 승인 금액(approvedAmount) 같은 판단 결과에 대한 근거를 함께 보관할 수 있게 한다. 별도의 검증이나 변환 없이 값을 설정만 수행하므로, 입력된 사유 목록의 유효성은 호출 측 또는 다른 검증 로직에 의해 보장된다는 전제를 가진다. |
| getScreenedBy | public String getScreenedBy() | - | - | 이 코드는 신용/대출 심사 결과를 담는 객체 내에서, 심사를 수행한 담당자 식별 정보(screenedBy)를 외부로 제공하기 위한 조회 동작이다. 내부에 저장된 screenedBy 값을 가공이나 검증 없이 그대로 반환하여, 심사 이력(누가 심사했는지)을 조회할 수 있게 한다. 객체의 상태를 변경하지 않고 읽기만 수행하므로 조회 목적의 접근자 역할을 한다. |
| setScreenedBy | public void setScreenedBy(String screenedBy) | - | - | 이 클래스는 신청/심사 결과와 관련된 다양한 속성(applicationId, customerId, creditScore, approved, screeningDate 등)을 보관하며, 그중 screenedBy 값을 관리한다. 이 코드는 외부에서 전달된 screenedBy(심사 수행자) 값을 객체 내부 상태에 그대로 반영해 저장한다. 별도의 검증, 변환, 조건 분기 없이 단순 대입만 수행하여 이후 심사 이력/담당자 추적에 사용될 screenedBy를 갱신한다. |
| toString | public String toString() | - | - | 이 코드는 대출 심사 결과 정보를 사람이 읽을 수 있는 단일 문자열로 직렬화해 반환한다. 반환 문자열에는 applicationId, customerId, creditScore, creditGrade, dtiRatio, ltvRatio, approved, approvedAmount, approvedRate, screeningDate, reasons, screenedBy 값이 모두 포함되어 심사 결과의 전체 스냅샷을 한 번에 확인할 수 있게 한다. 각 속성은 '키=값' 형태로 이어 붙여 중괄호로 감싼 출력 형식을 만들며, 승인 여부(approved)와 승인 조건(approvedAmount, approvedRate)까지 함께 노출해 디버깅/로그 기록에 활용되도록 구성한다. |

#### 필드

| 이름 | 타입 | 수정자 | 요약 |
| --- | --- | --- | --- |
| serialVersionUID | long | - | Java 직렬화(Serializable) 시 클래스 버전 호환성을 확인하기 위한 고정 식별자이며, 역직렬화 과정에서 클래스 구조 변경 여부를 판단하는 데 사용된다(값: 1L). |
| applicationId | String | - | 애플리케이션(신청/접수) 건을 식별하기 위한 문자열 ID를 저장하는 필드입니다. |
| customerId | String | - | 고객을 식별하기 위한 고유한 고객 ID(문자열)를 저장하는 필드입니다. |
| creditScore | int | - | 개인 또는 계정의 신용도를 정수형 점수로 저장하는 필드로, 대출·결제 한도 산정이나 신용 관련 의사결정에 활용될 수 있습니다. |
| creditGrade | String | - | 개인의 신용등급(크레딧 그레이드)을 문자열로 저장하는 필드로, 신용평가 결과를 등급 형태로 보관하거나 다른 로직에서 신용 수준을 판단하는 데 사용된다. |
| dtiRatio | BigDecimal | - | 차주의 DTI(총부채상환비율, Debt-to-Income) 비율 값을 소수점까지 정밀하게 저장하는 필드입니다. |
| ltvRatio | BigDecimal | - | 담보가치 대비 대출금액의 비율(LTV, Loan-to-Value ratio)을 BigDecimal로 보관하는 필드입니다. |
| approved | boolean | - | 해당 필드는 객체나 요청이 승인(approved) 상태인지 여부를 나타내는 불리언 플래그로, 승인되었으면 true, 그렇지 않으면 false 값을 저장합니다. |
| approvedAmount | BigDecimal | - | 승인된 금액(결제·대출·거래 등에서 승인 처리된 금액)을 BigDecimal로 저장하는 필드입니다. |
| approvedRate | BigDecimal | - | 승인된 비율(승인율)을 정밀한 소수 계산이 가능한 BigDecimal로 보관하는 필드입니다. |
| screeningDate | Date | - | 객체의 스크리닝(검사/상영) 날짜와 시간을 담는 Date 타입 필드로, 해당 이벤트가 언제 수행되었거나 예정되어 있는지를 기록하는 데 사용됩니다. |
| reasons | List | - | 여러 개의 사유(이유) 항목을 담아두는 목록으로, 하나의 사건·결과·상태에 대해 적용되는 복수의 이유/근거를 저장하는 역할을 합니다. |
| screenedBy | String | - | 이 필드는 해당 대상(예: 신청/검사/심사 등)을 스크리닝(선별·검토)한 담당자(사람 또는 시스템)의 이름이나 식별자를 문자열로 저장합니다. |

#### 구조 관계

| 방향 | 관계 | 대상 | 속성 |
| --- | --- | --- | --- |
| ← | DEPENDENCY | LoanServlet | source_member=handlePerformScreening, usage=local_var |
| ← | DEPENDENCY | LoanProcessSession | source_member=requestScreening, usage=return |
| ← | DEPENDENCY | LoanProcessSessionBean | source_member=requestScreening, usage=return |
| ← | DEPENDENCY | LoanScreeningSession | source_member=getCreditScreening, usage=return |
| ← | DEPENDENCY | LoanScreeningSession | source_member=performScreening, usage=return |
| ← | DEPENDENCY | LoanScreeningSessionBean | source_member=getCreditScreening, usage=return |

#### 호출 관계

| 방향 | 대상 | 호출코드 |
| --- | --- | --- |
| ← | LoanServlet | - |
| ← | LoanScreeningSessionBean | - |

#### 데이터 접근

| 대상 | 관계 | 근거 | 신뢰도 |
| --- | --- | --- | --- |
| ScreeningResultDTO | REFER_TO | - | 1.0 |

#### 요약 코드

```
없음
```

### CollateralBean

#### 기본 정보

| 항목 | 값 |
| --- | --- |
| 이름 | CollateralBean |
| 타입 | CLASS |
| FQN | com.banking.loan.entity.CollateralBean |
| 패키지 | com.banking.loan.entity |
| 스테레오타입 | COMMAND/READMODEL |
| 파일 | - |
| 라인 | - |
| 토큰 | - |

#### 요약

> com.banking.loan.entity.CollateralBean은 담보 CMP 엔티티 빈 구현 클래스로, 컨테이너가 영속성을 관리하며 담보 정보를 저장·조회한다. 신규 담보 생성 시 collateralId, applicationId, collateralType, description, appraisedValue를 반영하고 appraisalDate(감정일자)는 현재 시스템 시각으로, registrationStatus(등록 상태)는 "PENDING"으로 초기화한다. 컨테이너가 주입하는 EntityContext(entityContext)를 보관해 생명주기 처리 및 컨테이너 관리 기능 접근에 활용하며, 저장·삭제 콜백(저장/제거 시점)과 활성화/패시베이션/로드 등 주요 콜백 구현은 비어 있어 검증·변환·정리 같은 추가 로직 없이 실제 저장·삭제 책임을 컨테이너의 CMP 메커니즘에 위임한다.

#### 메서드

| 이름 | 시그니처 | 반환타입 | 수정자 | 요약 |
| --- | --- | --- | --- | --- |
| getCollateralId | - | - | - | 이 코드는 컨테이너가 영속성을 관리하는 담보 정보 저장·조회 목적의 구성요소에서, 담보를 식별하는 ID 값을 외부로 제공하기 위한 조회 인터페이스를 정의한다. 구현은 하위 구현체에 위임되며, 호출자는 담보의 고유 식별자를 문자열로 얻는 것만을 기대한다. 메서드 본문이 없고 계산·검증·저장 동작을 수행하지 않으므로, 상태를 변경하지 않는 읽기 성격의 계약(계약된 반환값 제공)으로 기능한다. |
| setCollateralId | - | - | - | 이 코드는 컨테이너가 영속성을 관리하는 담보 정보 CMP 엔티티 빈 구현에서, 담보 레코드를 식별하는 collateralId(담보 식별자)를 엔티티 상태에 반영하기 위한 설정 동작을 정의한다. 입력으로 전달된 담보 식별자 문자열을 해당 엔티티의 식별 값으로 설정하는 책임을 가지며, 실제 저장·조회 대상 담보 정보를 특정하기 위한 기반 데이터가 된다. 메서드가 추상으로 선언되어 있어, 구체 구현체가 영속 필드에 값을 기록하는 방식(컨테이너 관리 규약에 따른 상태 변경)을 제공하도록 강제한다. |
| getApplicationId | - | - | - | 이 클래스는 컨테이너가 영속성을 관리하는 담보 정보 저장·조회 목적의 CMP 구현을 전제로 하며, 그 흐름에서 담보 데이터가 어느 업무 신청(또는 처리 단위)에 속하는지를 식별할 수 있는 값을 제공해야 한다. 이 코드는 해당 식별자를 문자열로 돌려주는 규약만 선언하고, 실제로 어떤 값이 반환되는지는 하위 구현에서 결정하도록 비워 둔다. 따라서 여기서는 데이터 변경이나 영속 처리 없이, 담보 정보의 연계·추적에 필요한 신청 식별자 조회 역할만 담당한다. |
| setApplicationId | - | - | - | 담보 정보를 저장·조회하는 CMP 엔티티 빈 구현에서, 담보 데이터가 어떤 신청(업무) 건에 속하는지 식별하기 위한 applicationId 값을 설정하도록 강제하는 추상 동작을 선언한다. 구현체는 전달받은 applicationId를 엔티티의 해당 식별 속성에 반영해, 이후 영속화 및 조회 시 신청 건 단위로 담보를 구분·연결할 수 있게 한다. 메서드 본문이 없으므로 실제 저장 방식(필드 갱신, 검증, 예외 등)은 구체 구현에 위임된다. |
| getCollateralType | - | - | - | 컨테이너가 영속성을 관리하며 담보 정보를 저장·조회하는 구성요소에서, 담보의 종류를 나타내는 문자열 값을 조회하기 위한 계약(추상 동작)을 정의한다. 구현체는 담보 레코드에 저장된 담보 유형(예: 유형 코드/구분값)을 반환하도록 구체화되어야 하며, 이를 통해 담보를 유형별로 분류하거나 화면/업무 로직에서 식별할 수 있게 한다. 이 범위에서는 값을 변경하거나 저장을 수행하지 않고, 담보 유형 값의 제공(조회)에만 초점이 있다. |
| setCollateralType | - | - | - | 이 클래스는 컨테이너가 영속성을 관리하는 담보 정보를 저장·조회하는 컴포넌트이며, 그중 담보 정보의 한 속성인 collateralType(담보 유형)을 설정하기 위한 동작을 정의한다. 문자열로 전달된 담보 유형 값을 해당 담보 데이터에 반영해 이후 저장/조회 시 담보 유형이 일관되게 유지되도록 한다. 구현은 추상화되어 있어 실제 값 검증, 정규화, 영속 상태 반영 방식은 구현체가 결정한다. |
| getDescription | - | - | - | 담보 정보를 저장·조회하는 영속성 관리 구성요소의 일부로, 담보 항목에 대한 설명 문자열을 제공하기 위한 조회용 계약을 정의한다. 구현체는 담보의 상태나 속성에 기반해 사람이 읽을 수 있는 설명을 구성해 문자열로 반환하도록 의도되어 있다. 메서드 본문이 없는 추상 선언이므로, 실제 설명 생성 규칙과 포맷은 구체 구현에서 결정된다. 반환값은 단순 텍스트로, 이 선언 자체는 저장소나 엔티티 상태를 변경하지 않는다. |
| setDescription | - | - | - | 이 코드는 컨테이너가 영속성을 관리하는 담보 정보 저장·조회용 구현체에서, 담보의 설명(비고/설명 문구)에 해당하는 값을 변경하기 위한 동작을 추상으로 선언한다. 문자열로 전달된 설명 내용을 담보 데이터의 설명 속성에 반영하도록 구현체에 책임을 부여한다. 실제 구현에서는 이 변경이 영속 상태의 갱신으로 이어져, 담보 정보가 저장될 때 해당 설명 값이 함께 유지되도록 하는 목적을 가진다. |
| getAppraisedValue | - | - | - | 이 구성요소는 컨테이너가 영속성을 관리하는 담보 정보 저장·조회 책임의 일부로, 담보의 감정가(appraised value)에 해당하는 값을 읽어오기 위한 접근 지점을 정의한다. 감정가를 금액 계산에 적합한 정밀 숫자 타입으로 반환하도록 규정하며, 구체적인 조회/매핑 방식은 구현체(또는 컨테이너의 CMP 매핑)에 의해 결정된다. 자체적으로 상태를 변경하거나 추가 연산을 수행하지 않고, 담보 정보의 특정 속성 값을 조회하는 목적에 집중한다. |
| setAppraisedValue | - | - | - | 이 코드는 컨테이너가 영속성을 관리하는 담보 정보의 저장·조회 책임을 가진 CMP 구현 맥락에서, 담보의 appraisedValue(감정가)를 설정하기 위한 추상 인터페이스를 정의한다. 입력으로 전달된 감정가(BigDecimal)를 담보 데이터의 appraisedValue 속성에 반영하도록 의도되어 있으며, 실제 값 저장/갱신 동작은 컨테이너 또는 구체 구현체가 수행한다. 따라서 담보의 감정가라는 영속 상태를 변경(수정)하는 목적의 쓰기 작업 진입점 역할을 한다. |
| getAppraisalDate | - | - | - | 이 클래스는 컨테이너가 영속성을 관리하는 담보 정보를 저장·조회하는 구성요소이며, 그중 담보의 평가일 정보를 제공하기 위한 조회 지점을 정의한다. 구현체가 평가일을 어떤 저장소/영속 상태에서 가져올지는 여기서 결정하지 않고, 반드시 날짜 값을 반환하도록 계약만 선언한다. 이 조회는 담보 정보의 특정 속성(평가일)을 외부로 노출해 화면 표시나 후속 계산·검증에 활용할 수 있게 한다. |
| setAppraisalDate | - | - | - | 이 구성요소는 컨테이너가 영속성을 관리하는 담보 정보를 저장·조회하는 구현을 전제로 하며, 그 중 appraisalDate(감정일자)를 설정하는 동작을 계약으로 정의한다. 입력으로 전달된 날짜 값을 담보 정보의 appraisalDate에 반영하도록 요구하며, 구체적인 저장 방식이나 검증 규칙은 구현 클래스에서 결정된다. 반환값이 없는 설정 동작이므로, 담보 정보의 상태를 변경하는 목적의 연산으로 해석된다. |
| getLtvRatio | - | - | - | 담보 정보를 컨테이너가 영속성으로 관리하는 구성에서, 담보의 LTV 비율 값을 조회하기 위한 반환 규약을 정의한다. 반환값은 숫자 정밀도가 필요한 비율 값으로, 담보 평가·한도 산정 등에서 사용할 수 있는 읽기 전용 데이터로 취급된다. 구현은 제공되지 않으며, 실제 값 조회 방식은 하위 구현(또는 컨테이너/매핑 설정)에 의해 결정되도록 추상화되어 있다. |
| setLtvRatio | - | - | - | 이 클래스는 컨테이너가 영속성을 관리하는 담보 CMP 엔티티 빈 구현으로서, 담보 정보를 저장·조회할 수 있도록 상태를 보관한다. 이 선언은 담보의 ltvRatio(LTV 비율) 값을 엔티티 상태에 반영(변경)하기 위한 설정 동작을 정의한다. 메서드 본문이 없는 추상 선언이므로, 실제 값 반영과 영속화 방식은 컨테이너/구현체가 담당하며 호출 시 담보의 LTV 비율 상태가 갱신되는 의도를 가진다. |
| getRegistrationStatus | - | - | - | 이 클래스는 컨테이너가 영속성을 관리하는 담보 CMP 엔티티 빈 구현의 일부로서, 담보 정보를 저장·조회하는 책임 맥락에 놓여 있다. 이 추상 동작은 담보의 등록 상태(예: 등록/미등록/말소 등과 같은 상태 코드 또는 상태 문자열)를 문자열로 조회해 반환하도록 계약만 정의한다. 실제 상태 산정/매핑 규칙이나 조회 방식은 하위 구현에서 결정되며, 이 범위 자체에서는 상태 변경 없이 결과 문자열을 제공하는 역할에 집중한다. |
| setRegistrationStatus | - | - | - | 담보 정보를 저장·조회하는 컨테이너 관리 영속성 구성요소에서, 담보의 등록 상태(registrationStatus)를 설정하기 위한 추상 동작을 정의한다. 입력으로 전달된 registrationStatus 값을 엔티티의 등록 상태로 반영해 이후 영속 저장 및 조회 시 해당 상태가 기준이 되도록 하는 의도를 가진다. 구현은 제공되지 않으며, 실제 상태 반영 및 저장 처리 방식은 구현 클래스/컨테이너에 의해 결정된다. |
| ejbCreate | public String ejbCreate(String collateralId, String applicationId,                             String collateralType, String description,                             BigDecimal appraisedValue) throws CreateException | - | - | 컨테이너가 영속성을 관리하는 담보 정보 저장·조회 컴포넌트에서, 신규 담보 레코드를 생성할 때 필요한 초기 상태를 구성한다. 입력으로 받은 collateralId(담보 식별자), applicationId(신청/업무 식별자), collateralType(담보 유형), description(설명), appraisedValue(감정가)를 엔티티의 영속 상태에 반영해 생성 직후 조회·연결에 필요한 기준 값을 확정한다. 추가로 appraisalDate(감정일자)를 현재 시스템 시각으로 설정해 생성 시점의 감정일자를 기록하고, registrationStatus(등록 상태)를 "PENDING"으로 고정해 초기 등록 처리 단계임을 명시한다. CMP 생성 규약에 따라 생성 메서드는 기본키를 직접 반환하지 않으므로 null을 반환한다. |
| ejbPostCreate | public void ejbPostCreate(String collateralId, String applicationId,                               String collateralType, String description,                               BigDecimal appraisedValue) | - | - | 이 코드는 컨테이너가 영속성을 관리하는 담보 정보 저장·조회 구성요소에서, 생성 직후 호출되는 후처리 단계의 훅을 제공한다. 입력으로 담보ID, 신청ID, 담보유형, description(설명), appraisedValue(평가금액)를 받아 생성 직후 추가 초기화나 연관 데이터 설정을 수행할 수 있도록 설계된 자리다. 그러나 현재 본문이 비어 있어, 전달받은 값에 대한 검증·변환·추가 저장 등 어떤 후속 동작도 수행하지 않는다. 따라서 생성 후 처리 로직은 컨테이너의 기본 영속성 처리에만 의존하도록 남겨져 있다. |
| setEntityContext | public void setEntityContext(EntityContext ctx) | - | - | 컨테이너가 영속성을 관리하는 담보 정보 저장·조회 구성요소에서, 실행 컨텍스트를 외부로부터 전달받아 내부에 보관하도록 설정한다. 전달된 컨텍스트 참조를 내부 상태로 대입해 이후 영속성 관련 작업에서 동일한 컨텍스트를 사용할 수 있게 한다. 이 범위에서는 조회나 저장 로직을 수행하지 않고, 컨테이너 연동을 위한 컨텍스트 주입만 처리한다. |
| unsetEntityContext | public void unsetEntityContext() | - | - | 이 코드는 컨테이너가 영속성을 관리하는 담보 정보 저장·조회 구성요소에서, 컨테이너가 제공하는 엔티티 실행 컨텍스트 참조를 정리하는 역할을 한다. 내부에 보관 중이던 실행 컨텍스트를 null로 설정해 더 이상 해당 컨텍스트에 의존하지 않도록 해제한다. 이를 통해 인스턴스가 더 이상 컨텍스트에 묶이지 않게 하여 생명주기 전환(반환/소멸 등) 시 불필요한 참조를 제거한다. |
| ejbActivate | public void ejbActivate() | - | - | 컨테이너가 영속성을 관리하는 담보 정보 저장·조회 구성요소의 생명주기 콜백 중, 비활성화되어 있던 인스턴스가 다시 활성화될 때 호출되는 구간이다. 현재 구현은 본문이 비어 있어 활성화 시점에 추가 초기화, 리소스 재연결, 상태 복원과 같은 작업을 수행하지 않는다. 따라서 담보 데이터의 저장·수정·삭제 같은 상태 변경도 발생하지 않고, 조회를 위한 준비 작업도 별도로 수행하지 않는다. |
| ejbPassivate | public void ejbPassivate() | - | - | 담보 정보를 저장·조회하는 CMP 기반 영속 컴포넌트에서, 컨테이너가 인스턴스를 패시베이션(비활성화) 상태로 전환할 때 호출되는 생명주기 콜백 구간이다. 현재 구현은 본문이 비어 있어 패시베이션 시점에 자원 해제, 캐시 정리, 컨텍스트 정리 같은 추가 동작을 수행하지 않는다. 따라서 이 구간 자체는 조회나 저장 등 도메인 데이터 처리에 관여하지 않고, 컨테이너 생명주기 흐름을 위한 빈 훅으로만 존재한다. |
| ejbLoad | public void ejbLoad() | - | - | 이 코드는 컨테이너가 영속성을 관리하는 담보 정보 저장·조회용 구현에서, 데이터 로딩 시점에 호출되는 생명주기 훅을 제공한다. 그러나 본 범위에서는 로딩 시 수행해야 할 초기화, 검증, 파생값 계산 등의 처리가 전혀 구현되어 있지 않아 실제 동작은 ‘아무 것도 하지 않음’이다. 그 결과 컨테이너가 담보 정보를 읽어와 인스턴스에 반영하는 기본 동작 외에, 추가적인 부가 처리나 상태 변경은 발생하지 않는다. |
| ejbStore | public void ejbStore() | - | - | 이 구성요소는 컨테이너가 영속성을 관리하는 담보 정보의 저장·조회 책임을 가지며, 저장 라이프사이클에 맞춰 호출되는 저장 콜백 지점을 제공한다. 해당 범위의 구현은 비어 있어, 저장 시점에 추가로 검증·변환·이력 기록 같은 전처리를 수행하지 않는다. 따라서 실제 담보 정보의 저장 동작은 컨테이너 관리 영속성 메커니즘에 전적으로 위임되며, 이 구간에서는 상태 변경을 위한 명시적 로직이 없다. |
| ejbRemove | public void ejbRemove() throws RemoveException | - | - | 담보 정보를 컨테이너 관리 영속성으로 저장·조회하는 엔티티 빈 구현에서, 인스턴스 제거 시점에 호출되는 제거 콜백을 정의한다. 본문이 비어 있어 제거 과정에서 추가적인 정리 작업(연관 데이터 해제, 후처리 로직 등)은 수행하지 않으며, 삭제/정리 책임을 컨테이너의 영속성 관리에 맡긴다. 제거 과정에서 발생할 수 있는 오류를 호출자에게 전파할 수 있도록 제거 예외를 던지도록 선언만 되어 있다. |

#### 필드

| 이름 | 타입 | 수정자 | 요약 |
| --- | --- | --- | --- |
| entityContext | EntityContext | - | 컨테이너가 제공하는 엔티티 빈의 실행 컨텍스트(EntityContext)를 보관하여, CMP 담보 엔티티 빈이 생명주기 처리와 트랜잭션/보안 정보 접근, 엔티티 식별자 조회 등 컨테이너 관리 기능을 수행할 때 사용한다. |

#### 구조 관계

| 방향 | 관계 | 대상 | 속성 |
| --- | --- | --- | --- |
| → | ASSOCIATION | EntityContext | source_member=setEntityContext |
| → | ASSOCIATION | EntityContext | source_member=unsetEntityContext |
| → | DEPENDENCY | EntityContext | source_member=setEntityContext, usage=parameter |

#### 호출 관계

| 방향 | 대상 | 호출코드 |
| --- | --- | --- |
| → | CollateralBean | 49:         setCollateralId(collateralId); |
| → | CollateralBean | 50:         setApplicationId(applicationId); |
| → | CollateralBean | 51:         setCollateralType(collateralType); |
| → | CollateralBean | 52:         setDescription(description); |
| → | CollateralBean | 53:         setAppraisedValue(appraisedValue); |
| → | CollateralBean | 54:         setAppraisalDate(new Date(System.currentTimeMillis())); |
| → | CollateralBean | 55:         setRegistrationStatus("PENDING"); |

#### 데이터 접근

| 대상 | 관계 | 근거 | 신뢰도 |
| --- | --- | --- | --- |
| - | - | - | - |

#### 요약 코드

```
없음
```

### CollateralLocal

#### 기본 정보

| 항목 | 값 |
| --- | --- |
| 이름 | CollateralLocal |
| 타입 | CLASS |
| FQN | com.banking.loan.entity.CollateralLocal |
| 패키지 | com.banking.loan.entity |
| 스테레오타입 | COMMAND/READMODEL |
| 파일 | - |
| 라인 | - |
| 토큰 | - |

#### 요약

> com.banking.loan.entity.CollateralLocal은 담보 엔티티 빈 로컬 컴포넌트 인터페이스로, 담보 정보에 대한 컨테이너 관리 영속성(CMP) 필드 접근자(조회/설정)를 정의한다. 담보의 collateralId(담보 ID), applicationId(신청 식별자), collateralType(담보유형), description(설명), appraisedValue(감정가), appraisalDate(감정일자) 등의 속성을 일관된 방식으로 읽고/변경할 수 있게 하며, 추가로 ltvRatio(LTV 비율)와 registrationStatus(등록상태)도 조회(get) 및 갱신(set)하는 계약을 제공한다. 이 인터페이스 자체는 계산·검증·상태 전이 로직 없이, 저장된 담보 속성 값을 읽거나 설정해 영속 상태에 반영되도록 하는 책임만 가진다.

#### 메서드

| 이름 | 시그니처 | 반환타입 | 수정자 | 요약 |
| --- | --- | --- | --- | --- |
| getCollateralId | String getCollateralId() | - | - | 이 구성요소는 담보 정보에 대한 CMP 필드 접근자를 정의하여, 담보 관련 데이터의 속성 값을 일관된 방식으로 읽을 수 있게 한다. 이 범위의 선언은 담보 식별자에 해당하는 collateralId(담보 ID)를 문자열로 반환하도록 규정한다. 호출자 측에서는 반환된 collateralId를 담보 레코드 식별, 연관 데이터 조회, 화면/전문 출력 등의 목적으로 활용할 수 있다. 값의 생성·변경·저장 같은 상태 변경은 수행하지 않고, 담보 ID 값을 조회하는 역할에 집중한다. |
| getApplicationId | String getApplicationId() | - | - | 이 코드는 담보 정보에 대한 CMP 필드 접근자를 정의하는 로컬 컴포넌트 인터페이스의 일부로, 담보 데이터가 어떤 신청 건에 속하는지를 식별하는 applicationId(신청 식별자)를 조회하기 위한 접근자 계약을 제공한다. 호출자는 이 접근자를 통해 담보 레코드와 연계된 신청 식별자 값을 문자열로 읽어올 수 있다. 값을 조회해 반환하는 목적만 가지며, 담보 정보나 신청 정보의 상태를 변경하거나 저장을 수행하지 않는다. |
| setApplicationId | void setApplicationId(String applicationId) | - | - | 이 코드는 담보 정보에 대한 CMP 필드 접근자를 정의하는 로컬 컴포넌트 인터페이스의 일부로, 담보 데이터의 특정 식별값을 갱신하기 위한 설정 동작을 제공한다. 입력으로 전달된 applicationId(신청 ID)를 담보 정보의 해당 필드에 저장해, 이후 담보 엔티티의 상태가 신청 건과 연계되도록 한다. 조회나 계산 로직 없이 값의 변경(쓰기)만을 의도하며, 영속 필드에 반영되는 갱신 지점을 인터페이스 수준에서 명시한다. |
| getCollateralType | String getCollateralType() | - | - | 이 코드는 담보 정보에 대한 CMP 필드 접근자를 정의하는 로컬 컴포넌트 인터페이스의 일부로, 담보의 유형을 나타내는 collateralType 값을 읽기 위한 접근자를 제공한다. 호출자는 이 접근자를 통해 담보 엔티티에 저장된 담보유형 값을 문자열로 조회할 수 있다. 입력 파라미터 없이 현재 엔티티 상태에서 해당 속성 값을 반환하는 읽기 전용 성격의 동작이다. |
| setCollateralType | void setCollateralType(String collateralType) | - | - | 이 구성요소는 담보 정보에 대한 CMP 필드 접근자를 정의하는 로컬 컴포넌트 인터페이스이며, 담보 엔티티의 영속 상태를 직접 갱신하기 위한 계약을 제공한다. 이 선언은 담보의 collateralType(담보유형) 값을 입력받아 해당 담보 정보의 담보유형 필드를 설정(변경)하도록 한다. 구현체에서는 이 값 변경이 담보 엔티티의 CMP 필드에 반영되어 저장 상태가 수정되는 것을 전제로 한다. 조회 목적이 아니라 담보 정보의 속성 값을 바꾸는 쓰기(수정) 동작을 명확히 표현한다. |
| getDescription | String getDescription() | - | - | 이 구성요소는 담보 정보에 대한 CMP 필드 접근자를 정의하는 로컬 컴포넌트 인터페이스의 일부이다. 이 범위의 기능은 담보 정보 중 description(설명) 값을 조회해 문자열로 반환하도록 계약을 선언한다. 구현체는 저장된 담보 설명 데이터를 읽기 전용으로 제공하며, 이 선언 자체는 데이터의 생성·수정·삭제 같은 상태 변경을 수행하지 않는다. |
| setDescription | void setDescription(String description) | - | - | 담보 정보에 대한 CMP 필드 접근자를 정의하는 로컬 컴포넌트 인터페이스의 일부로, 담보의 description(설명) 값을 변경하기 위한 설정 동작을 선언한다. 입력으로 전달된 문자열을 담보 정보의 description 필드에 반영해 저장 값이 갱신되도록 의도한다. 구현 로직은 없으며, 컨테이너 관리 영속성(CMP) 환경에서 해당 필드의 변경이 영속 상태에 적용되는 계약만 제공한다. |
| getAppraisedValue | BigDecimal getAppraisedValue() | - | - | 이 코드는 담보 정보에 대한 CMP 필드 접근자를 정의하는 로컬 컴포넌트 인터페이스의 일부로, 담보의 감정가(appraisedValue)를 조회할 수 있는 읽기용 계약을 제공한다. 호출자는 담보에 저장된 감정가 값을 BigDecimal 형태로 반환받아 담보 가치 산정, 한도/여신 판단 등 후속 처리에서 사용할 수 있다. 인터페이스에 선언된 조회 전용 접근자이므로 값의 생성·수정·삭제 같은 상태 변경은 수행하지 않는다. |
| setAppraisedValue | void setAppraisedValue(BigDecimal appraisedValue) | - | - | 이 코드는 담보 정보에 대한 CMP 필드 접근자를 정의하는 로컬 컴포넌트 인터페이스의 일부로, 담보의 appraisedValue(감정가) 값을 설정하기 위한 계약을 제공한다. 호출자는 감정가에 해당하는 금액 값을 전달하며, 구현체는 이 값을 담보 정보의 영속 상태에 반영하는 변경 동작을 수행하게 된다. 반환값이 없으므로 설정 결과를 직접 돌려주지 않고, 담보 정보의 상태를 갱신하는 목적에 집중한다. |
| getAppraisalDate | Date getAppraisalDate() | - | - | 이 코드는 담보 정보에 대한 CMP 필드 접근자를 제공하는 로컬 컴포넌트 인터페이스의 일부로, 담보의 appraisalDate(감정일자)를 조회하기 위한 반환 규격을 정의한다. 호출자는 이 계약에 따라 담보가 감정된 기준 일자를 Date 형태로 읽어올 수 있으며, 값의 계산이나 변환 로직 없이 단순 조회 목적이다. 담보 평가/감정 시점의 기준 정보를 다른 로직에서 활용할 수 있도록 날짜 필드를 노출하는 역할을 한다. |
| setAppraisalDate | void setAppraisalDate(Date appraisalDate) | - | - | 이 코드는 담보 정보에 대한 CMP 필드 접근자를 제공하는 로컬 컴포넌트 인터페이스의 일부로, 담보 관련 엔티티 상태를 갱신하기 위한 쓰기 동작을 정의한다. 입력으로 받은 appraisalDate(감정일자)를 담보 정보의 해당 필드에 설정하여, 이후 영속 상태에 반영될 수 있도록 한다. 즉 감정일자 값을 변경(수정)하는 목적의 계약(시그니처)만 제공하며, 이 범위 내에서 추가 검증이나 조회 로직은 포함하지 않는다. |
| getLtvRatio | BigDecimal getLtvRatio() | - | - | 이 구성요소는 담보 정보에 대한 CMP 필드 접근자를 정의하는 로컬 컴포넌트 인터페이스이며, 담보 관련 속성을 조회할 수 있도록 계약을 제공한다. 이 범위의 선언은 담보 정보의 ltvRatio(LTV 비율) 값을 조회해 숫자형(BigDecimal)으로 반환하도록 규정한다. 값의 계산·변환·검증이나 저장/갱신 같은 상태 변경은 수행하지 않고, 저장된 담보 비율 값을 읽어오는 목적의 조회 전용 접근자이다. |
| setLtvRatio | void setLtvRatio(BigDecimal ltvRatio) | - | - | 이 구성요소는 담보 정보에 대한 CMP 필드 접근자를 정의하는 로컬 컴포넌트 인터페이스이며, 담보 엔티티의 상태를 읽고/갱신하기 위한 계약을 제공한다. 이 범위의 동작은 담보 정보에 포함된 ltvRatio(담보인정비율) 값을 BigDecimal 형태로 설정하여, 해당 담보의 비율 정보를 변경하도록 의도된다. 본 선언 자체에는 계산·검증·조회 로직이 없고, 값 갱신(상태 변경)을 수행하는 접근자 수준의 책임만 갖는다. |
| getRegistrationStatus | String getRegistrationStatus() | - | - | 이 구성요소는 담보 정보에 대한 CMP 필드 접근자를 정의하는 로컬 컴포넌트 인터페이스의 일부이며, 담보 데이터의 필드 값을 외부에서 일관되게 읽을 수 있도록 계약을 제공한다. 이 범위의 선언은 담보 정보의 registrationStatus(등록상태) 값을 문자열로 조회해 반환하는 용도의 읽기 전용 접근자를 정의한다. 구현 로직이나 상태 변경은 포함하지 않으며, 실제 값의 저장·갱신은 구현체(컨테이너 관리 필드 매핑)에 의해 처리된다. |
| setRegistrationStatus | void setRegistrationStatus(String registrationStatus) | - | - | 이 컴포넌트 인터페이스는 담보 정보에 대한 CMP 필드 접근자를 정의하며, 담보 데이터의 상태를 직접 갱신할 수 있도록 한다. 이 범위의 기능은 담보의 registrationStatus(등록상태) 값을 외부에서 전달받은 문자열로 설정해 저장 상태를 변경하는 역할을 한다. 이를 통해 담보 등록/처리 흐름에서 현재 등록 진행 상태나 완료 여부 같은 상태 정보가 엔티티에 반영된다. |

#### 필드

| 이름 | 타입 | 수정자 | 요약 |
| --- | --- | --- | --- |
| - | - | - | - |

#### 구조 관계

| 방향 | 관계 | 대상 | 속성 |
| --- | --- | --- | --- |
| ← | DEPENDENCY | CollateralLocalHome | source_member=findByPrimaryKey, usage=return |
| ← | DEPENDENCY | CollateralLocalHome | source_member=create, usage=return |
| ← | DEPENDENCY | LoanScreeningSessionBean | source_member=calculateLtvRatio, usage=cast |

#### 호출 관계

| 방향 | 대상 | 호출코드 |
| --- | --- | --- |
| ← | LoanScreeningSessionBean | - |

#### 데이터 접근

| 대상 | 관계 | 근거 | 신뢰도 |
| --- | --- | --- | --- |
| - | - | - | - |

#### 요약 코드

```
없음
```

### CollateralLocalHome

#### 기본 정보

| 항목 | 값 |
| --- | --- |
| 이름 | CollateralLocalHome |
| 타입 | CLASS |
| FQN | com.banking.loan.entity.CollateralLocalHome |
| 패키지 | com.banking.loan.entity |
| 스테레오타입 | COMMAND/READMODEL |
| 파일 | - |
| 라인 | - |
| 토큰 | - |

#### 요약

> 이 클래스는 담보 엔티티 빈의 로컬 홈 인터페이스로서, 담보의 생성 및 조회를 위한 메서드 계약을 정의한다. collateralId(담보 식별자), applicationId(신청 식별자), collateralType(담보 유형), description(설명), appraisedValue(감정가)를 입력받아 신규 담보를 등록하고, 생성된 담보에 대한 로컬 접근 핸들을 반환한다. 또한 담보 식별자 기반 단건 조회, 전체 담보 목록 조회, applicationId 기준 담보 다건 조회를 제공하며, 생성 실패 시 CreateException, 조회 실패 시 조회 관련 예외로 오류를 전달한다.

#### 메서드

| 이름 | 시그니처 | 반환타입 | 수정자 | 요약 |
| --- | --- | --- | --- | --- |
| create | CollateralLocal create(String collateralId, String applicationId,                            String collateralType, String description,                            BigDecimal appraisedValue) throws CreateException | - | - | 이 인터페이스는 담보 정보를 생성·조회하기 위한 계약을 정의하며, 이 범위의 선언은 담보를 신규로 등록(생성)하기 위한 연산을 규정한다. 입력으로 collateralId(담보 식별자), applicationId(신청 식별자), collateralType(담보 유형), description(설명), appraisedValue(감정가)를 받아 담보의 기본 속성을 갖춘 신규 담보를 생성하는 것을 의도한다. 생성이 성공하면 담보의 로컬 접근 핸들을 반환하여 이후 CMP 필드 접근 등 담보 정보 접근이 가능하도록 한다. 생성 과정에서 필요한 조건을 만족하지 못하거나 생성에 실패하면 CreateException을 통해 실패를 호출자에게 알리도록 정의한다. |
| findByPrimaryKey | CollateralLocal findByPrimaryKey(String collateralId) throws FinderException | - | - | 이 코드는 담보 엔티티 빈의 생성 및 조회 기능을 제공하는 로컬 홈 인터페이스 맥락에서, 담보 정보를 기본키로 조회하기 위한 조회 계약을 정의한다. 입력으로 담보를 식별하는 문자열 값을 받아, 해당 식별자에 대응하는 담보의 로컬 컴포넌트 인터페이스를 반환하도록 설계되어 있다. 조회 대상이 존재하지 않거나 조회 과정에서 문제가 발생하면 조회 실패 예외를 통해 호출자에게 오류를 전달한다. |
| findAll | Collection findAll() throws FinderException | - | - | 담보의 생성 및 조회를 위한 로컬 홈 인터페이스에서, 저장소에 존재하는 담보 엔티티들을 전체 목록으로 조회하기 위한 조회 계약을 선언한다. 호출자는 별도의 입력 없이 모든 담보를 컬렉션 형태로 반환받는 것을 기대한다. 조회 과정에서 엔티티 탐색이 실패하거나 조회 규약을 만족하지 못하는 경우 조회 관련 예외가 발생할 수 있음을 명시한다. |
| findByApplicationId | Collection findByApplicationId(String applicationId) throws FinderException | - | - | 이 로컬 홈 인터페이스는 담보의 생성 및 조회를 위한 기능을 정의하며, 이 범위의 선언은 그중 특정 신청 건을 기준으로 담보를 조회하는 역할을 맡는다. 입력으로 받은 신청 식별자에 해당하는 담보들을 여러 건 묶음 형태로 반환하도록 계약을 정의한다. 조회 과정에서 대상이 없거나 조회 조건이 유효하지 않은 경우에 대비해 조회 실패 예외를 호출자에게 전달하도록 명시한다. 이 선언 자체는 조회 규약만 정의하며, 데이터 변경(등록/수정/삭제) 의도는 드러나지 않는다. |

#### 필드

| 이름 | 타입 | 수정자 | 요약 |
| --- | --- | --- | --- |
| - | - | - | - |

#### 구조 관계

| 방향 | 관계 | 대상 | 속성 |
| --- | --- | --- | --- |
| → | DEPENDENCY | CollateralLocal | source_member=findByPrimaryKey, usage=return |
| → | DEPENDENCY | CollateralLocal | source_member=create, usage=return |
| ← | DEPENDENCY | LoanApplicationSessionBean | source_member=registerCollateral, usage=cast |
| ← | DEPENDENCY | LoanScreeningSessionBean | source_member=calculateLtvRatio, usage=local_var |

#### 호출 관계

| 방향 | 대상 | 호출코드 |
| --- | --- | --- |
| ← | LoanApplicationSessionBean | - |
| ← | LoanScreeningSessionBean | - |

#### 데이터 접근

| 대상 | 관계 | 근거 | 신뢰도 |
| --- | --- | --- | --- |
| CollateralLocal | REFER_TO | - | 1.0 |
| CollateralLocal | REFER_TO | - | 1.0 |

#### 요약 코드

```
없음
```

### CreditRatingBean

#### 기본 정보

| 항목 | 값 |
| --- | --- |
| 이름 | CreditRatingBean |
| 타입 | CLASS |
| FQN | com.banking.loan.entity.CreditRatingBean |
| 패키지 | com.banking.loan.entity |
| 스테레오타입 | COMMAND/READMODEL |
| 파일 | - |
| 라인 | - |
| 토큰 | - |

#### 요약

> com.banking.loan.entity.CreditRatingBean은 신용등급 BMP(Bean Managed Persistence) 엔티티 빈 구현체로, JDBC를 사용해 CREDIT_RATING 테이블의 영속성을 직접 관리하며 ratingId, customerId, creditScore, creditGrade, ratingAgency, ratingDate(평가일), annualIncome(연간 소득), totalDebt(총부채), dti(부채대비소득비율), isValid(유효여부) 등의 도메인 데이터를 보관한다. 데이터베이스 작업을 위해 JNDI 이름 "java:comp/env/jdbc/LoanDS"(DS_JNDI)로 DataSource를 조회해 연결을 얻고, NamingException 발생 시 "DataSource 룩업 실패: " 메시지를 포함한 SQLException으로 변환하며, ResultSet/Statement/Connection은 null 체크 후 개별적으로 닫고 닫기 중 SQLException은 무시한다. 생성/저장 시 ratingDate는 현재 시각, isValid는 true로 두며 creditScore가 >=900이면 "AAA", >=800이면 "AA", >=700이면 "A", >=600이면 "BBB", >=500이면 "BB", 그 미만(<500)은 "B"로 creditGrade를 재산정해 INSERT한다. 또한 annualIncome이 null이 아니고 0 초과(>0)이며 totalDebt가 null이 아닐 때 totalDebt/annualIncome을 소수 2자리 반올림으로 dti를 계산하고, 그 외에는 0으로 두며, "SELECT RATING_ID FROM CREDIT_RATING WHERE RATING_ID = ?"로 기본키 존재 여부를 확인한다.

#### 메서드

| 이름 | 시그니처 | 반환타입 | 수정자 | 요약 |
| --- | --- | --- | --- | --- |
| getRatingId | public String getRatingId() | - | - | 이 코드는 JDBC로 CREDIT_RATING 테이블의 영속성을 직접 관리하는 신용등급 BMP 엔티티 빈 구현체 내에서, 현재 인스턴스가 보유한 ratingId(신용등급 식별자)를 외부에 제공하는 읽기 동작이다. 내부 상태로 저장돼 있는 ratingId 값을 그대로 반환하며, 별도의 변환·검증·DB 조회는 수행하지 않는다. 호출자는 이 값을 통해 해당 신용등급 레코드(또는 엔티티 인스턴스)를 식별하는 데 사용한다. |
| getCustomerId | public String getCustomerId() | - | - | 이 코드는 JDBC로 CREDIT_RATING 테이블에 대한 영속성을 직접 관리하는 신용등급 BMP 구현체에서, 신용등급 데이터가 어떤 고객에 속하는지 식별하는 customerId(고객 식별자)를 외부에 제공하기 위한 조회 동작이다. 내부에 보관 중인 customerId 값을 그대로 반환하여, 신용등급 레코드와 고객 간의 연결 관계를 확인하거나 상위 로직에서 고객 기준으로 처리할 수 있게 한다. 상태 변경이나 검증/가공 없이 단순히 현재 객체가 가진 고객 식별자를 읽어오는 목적에 집중한다. |
| setCustomerId | public void setCustomerId(String customerId) | - | - | 이 코드는 JDBC로 CREDIT_RATING 테이블 영속성을 직접 관리하는 신용등급 BMP 구현체의 상태를 구성하기 위한 일부로, 신용등급 산정/보관 대상 고객을 식별하는 customerId(고객식별자)를 객체 내부에 반영한다. 외부에서 전달받은 고객식별자 값을 그대로 customerId 필드에 저장하여, 이후 영속화나 신용등급 데이터 조립 시 해당 고객 기준으로 처리될 수 있게 한다. 이 범위에서는 유효성 검사, 변환, 부가 계산 없이 입력 값을 즉시 상태로 확정한다. |
| getCreditScore | public int getCreditScore() | - | - | 이 코드는 JDBC로 CREDIT_RATING 테이블의 영속성을 직접 관리하는 신용등급 BMP 구현체 내에서, 현재 인스턴스가 보유한 creditScore(신용점수) 값을 외부로 제공하기 위한 조회 동작을 수행한다. 내부 상태에 저장된 creditScore를 그대로 반환하며, 값의 계산·변환·검증 로직은 포함하지 않는다. 데이터베이스 갱신이나 다른 필드 변경 없이 읽기만 수행하므로 호출자는 로딩된 신용점수 스냅샷을 확인하는 용도로 사용한다. |
| setCreditScore | public void setCreditScore(int creditScore) | - | - | 이 코드는 JDBC로 CREDIT_RATING 테이블에 대한 영속성을 직접 관리하는 신용등급 BMP 엔티티 빈 구현체에서, 신용평가 결과의 핵심 값인 creditScore(신용점수)를 내부 상태로 반영하기 위한 갱신 동작을 수행한다. 외부에서 전달된 신용점수 값을 객체의 creditScore 필드에 그대로 대입하여 이후 영속화(저장/수정) 시점에 반영될 수 있도록 준비한다. 검증, 변환, 범위 체크 없이 값 설정만 수행하므로 입력 값의 유효성은 다른 처리 단계에서 보장된다는 전제에 가깝다. |
| getCreditGrade | public String getCreditGrade() | - | - | 이 코드는 JDBC로 CREDIT_RATING 테이블의 영속성을 직접 관리하는 신용등급 관련 BMP 구현체에서, creditGrade(신용등급 구간/등급) 값을 외부로 제공하기 위한 조회용 접근자이다. 내부에 보관 중인 creditGrade 값을 그대로 반환하여, 해당 신용등급 평가 결과를 다른 처리 흐름에서 확인할 수 있게 한다. 데이터베이스 조회나 갱신 로직은 수행하지 않으며, 객체 상태도 변경하지 않는다. |
| setCreditGrade | public void setCreditGrade(String creditGrade) | - | - | 이 코드는 JDBC로 CREDIT_RATING 테이블 영속성을 직접 관리하는 신용등급 BMP 구현체의 상태 중 creditGrade(신용등급 등급)를 갱신하기 위해 사용된다. 외부에서 전달된 신용등급 값을 내부 creditGrade 필드에 그대로 대입하여 현재 인스턴스의 신용등급 등급 상태를 변경한다. 이 변경된 creditGrade 값은 이후 영속화 로직에서 신용등급 정보로 저장·갱신될 수 있는 입력값으로 유지된다. |
| getRatingAgency | public String getRatingAgency() | - | - | 이 코드는 JDBC로 CREDIT_RATING 테이블에 대한 영속성을 직접 관리하는 신용등급 BMP 엔티티 빈 구현체의 일부로, 신용평가 정보의 구성 요소를 외부로 제공하기 위한 접근 기능을 담당한다. 그중 ratingAgency(평가사) 값을 조회해 호출자에게 그대로 반환한다. 내부 상태를 변경하거나 추가 계산·검증을 수행하지 않고, 저장된 평가사 문자열을 읽기 전용으로 노출한다. |
| setRatingAgency | public void setRatingAgency(String ratingAgency) | - | - | 이 코드는 JDBC로 CREDIT_RATING 테이블의 영속성을 직접 관리하는 신용등급 BMP 엔티티 빈 구현체에서, 신용평가기관 정보인 ratingAgency 값을 갱신하기 위한 동작이다. 입력으로 받은 신용평가기관 문자열을 인스턴스의 ratingAgency(평가기관) 필드에 그대로 반영하여 내부 상태를 변경한다. 이렇게 설정된 값은 이후 엔티티의 영속화/업데이트 과정에서 신용등급 데이터의 일부로 저장될 수 있도록 준비된다. |
| getRatingDate | public Date getRatingDate() | - | - | 이 코드는 JDBC로 CREDIT_RATING 테이블의 영속성을 직접 관리하는 신용등급 관련 구현체에서, 신용평가의 기준일자를 나타내는 ratingDate(평가일자) 값을 외부에 제공하기 위한 조회 동작이다. 내부에 보관 중인 ratingDate를 그대로 반환하여, 신용등급 산정 시점이나 유효성 판단에 필요한 날짜 정보를 확인할 수 있게 한다. 날짜 값의 변환, 검증, 보정 없이 현재 상태의 값을 단순 반환하므로 데이터는 변경되지 않는다. |
| setRatingDate | public void setRatingDate(Date ratingDate) | - | - | 이 코드는 JDBC로 CREDIT_RATING 테이블의 영속성을 직접 관리하는 신용등급 BMP 구현체의 상태 중 ratingDate(평가일자)를 갱신하는 역할을 한다. 외부에서 전달된 평가일자 값을 내부에 보관되는 ratingDate 필드에 그대로 반영하여, 해당 신용등급 정보가 어느 날짜 기준으로 평가되었는지를 확정한다. 이로써 이후 데이터 저장/갱신 로직이 수행될 때 평가일자 값이 일관되게 사용될 수 있도록 엔티티의 상태를 변경한다. |
| getAnnualIncome | public BigDecimal getAnnualIncome() | - | - | 이 코드는 JDBC로 CREDIT_RATING 테이블에 대한 영속성을 직접 관리하는 신용등급 BMP 엔티티 빈 구현체의 일부로, 신용평가 정보 중 소득 관련 값을 외부에 제공하기 위한 조회 동작을 수행한다. 저장되어 있는 annualIncome(연소득) 값을 가공이나 검증 없이 그대로 반환한다. 데이터베이스 갱신이나 상태 변경 없이, 이미 로드·보관 중인 연소득 값을 읽어 전달하는 목적이다. |
| setAnnualIncome | public void setAnnualIncome(BigDecimal annualIncome) | - | - | 이 코드는 JDBC로 CREDIT_RATING 테이블 영속성을 직접 관리하는 신용등급 BMP 엔티티 빈 구현체의 상태를 구성하기 위한 일부이다. 입력으로 받은 연소득 값(BigDecimal)을 annualIncome(연소득) 필드에 그대로 반영하여, 이후 신용등급 산정/검증 또는 저장 시 사용할 엔티티 내부 값을 갱신한다. 별도의 유효성 검증, 계산, 정규화 로직은 수행하지 않으며, 데이터베이스 반영도 이 구간에서 직접 수행하지 않는다. |
| getTotalDebt | public BigDecimal getTotalDebt() | - | - | 이 코드는 JDBC로 CREDIT_RATING 테이블의 영속성을 직접 관리하는 신용등급 BMP 엔티티 빈 구현체의 데이터 접근 일부로, 신용평가에 사용되는 재무 지표를 외부에서 읽을 수 있게 한다. 현재 인스턴스에 보관 중인 totalDebt(총부채) 값을 그대로 반환하여, 부채 규모를 조회할 수 있도록 한다. 계산이나 검증, 저장 동작 없이 단순 조회만 수행하므로 상태 변경은 발생하지 않는다. |
| setTotalDebt | public void setTotalDebt(BigDecimal totalDebt) | - | - | 신용등급 정보를 JDBC로 직접 영속화하는 BMP 구현체에서, 부채 총액(totalDebt) 값을 현재 객체 상태에 반영한다. 외부에서 전달된 부채 총액을 내부 필드 totalDebt에 그대로 대입하여 이후 신용등급 관련 데이터의 저장/갱신에 사용될 값을 준비한다. 검증, 계산, 변환 로직 없이 단순 상태 변경만 수행한다. |
| getDti | public BigDecimal getDti() | - | - | 이 코드는 JDBC로 CREDIT_RATING 테이블 영속성을 직접 관리하는 신용등급 BMP 구현체 내에서, 신용평가 데이터의 dti(총부채상환비율)를 조회하기 위한 읽기 전용 접근을 제공한다. 현재 객체가 보유하고 있는 dti 값을 그대로 반환하며, 계산·검증·정규화 같은 추가 로직은 수행하지 않는다. 따라서 호출자는 저장소 접근 없이 메모리에 적재된 신용평가 상태에서 dti 값을 확인할 수 있다. |
| setDti | public void setDti(BigDecimal dti) | - | - | 이 코드는 JDBC로 CREDIT_RATING 테이블에 대한 영속성을 직접 관리하는 신용등급 관련 BMP 구현체의 일부로, 신용평가 데이터 중 dti(총부채상환비율)를 객체 상태에 반영하는 역할을 한다. 외부에서 전달된 dti 값을 내부 필드 dti에 그대로 저장하여, 이후 신용평가 적정성 판단이나 영속화 시 해당 비율이 사용될 수 있도록 한다. 값 검증, 변환, 보정 로직은 수행하지 않으며 단순 상태 갱신만 수행한다. |
| getIsValid | public boolean getIsValid() | - | - | 이 코드는 JDBC로 CREDIT_RATING 테이블에 대한 영속성을 직접 관리하는 신용등급 BMP 구현체의 상태 중, 유효성 여부를 나타내는 isValid 값을 외부에 제공한다. 호출자는 반환된 불리언 값을 통해 현재 신용등급 데이터(예: creditScore, creditGrade, ratingDate 등으로 구성된 평가 정보)가 유효한 상태로 판단되었는지 확인할 수 있다. 내부 상태를 변경하거나 추가 검증을 수행하지 않고, 이미 저장된 유효성 플래그를 그대로 반환하는 조회 성격의 동작이다. |
| setIsValid | public void setIsValid(boolean isValid) | - | - | 이 코드는 JDBC로 CREDIT_RATING 테이블의 영속성을 직접 관리하는 신용등급 정보를 다루는 구성요소에서, 신용등급 데이터의 유효 상태를 나타내는 isValid(유효여부) 값을 갱신한다. 외부에서 전달된 유효/무효 판단 결과를 내부 상태로 확정 반영하여 이후 영속화 처리나 업무 판단에 사용할 수 있게 한다. 별도의 검증, 변환, 부수효과 없이 불리언 값 자체를 저장된 상태로 덮어쓴다. |
| recalculateGrade | public void recalculateGrade() | - | - | 신용등급 BMP 엔티티의 내부 상태 중 creditScore(신용점수)를 기준으로 creditGrade(신용등급) 값을 재산정해 갱신한다. creditScore가 900 이상이면 "AAA", 800 이상이면 "AA", 700 이상이면 "A", 600 이상이면 "BBB", 500 이상이면 "BB"로 설정한다. 위 조건에 해당하지 않는 500 미만 구간은 "B"로 등급을 설정한다. 외부 조회나 저장 없이, 점수 구간 규칙에 따라 등급 문자열을 확정하여 객체 필드 상태를 변경한다. |
| invalidate | public void invalidate() | - | - | 이 코드는 JDBC로 CREDIT_RATING 테이블에 대한 영속성을 직접 관리하는 신용등급 BMP 구현체의 내부 상태를 무효화하기 위해 사용된다. 호출되면 객체가 보유한 유효성 플래그인 isValid를 false로 변경하여, 현재 인스턴스의 데이터가 더 이상 유효하지 않음을 명시적으로 표시한다. 이를 통해 이후 처리에서 해당 신용등급 정보(ratingId, customerId, creditScore, creditGrade 등)가 재사용되거나 신뢰되는 것을 방지하는 상태 전이를 만든다. |
| ejbCreate | public String ejbCreate(String ratingId, String customerId, int creditScore,                              String ratingAgency, BigDecimal annualIncome, BigDecimal totalDebt)                              throws CreateException | - | - | 신용등급 BMP 영속성 구현에서, 입력된 ratingId, customerId, creditScore, ratingAgency, annualIncome, totalDebt를 엔티티 상태(ratingDate는 현재 시각, isValid는 true)로 확정하고 신규 신용등급을 생성한다. creditScore를 기준으로 creditGrade를 재산정하며, 900 이상은 "AAA", 800 이상은 "AA", 700 이상은 "A", 600 이상은 "BBB", 500 이상은 "BB", 500 미만은 "B"로 등급을 확정한다. 연소득(annualIncome)이 null이 아니고 0 초과이며 총부채(totalDebt)가 null이 아닐 때는 totalDebt/annualIncome을 소수 2자리(반올림)로 계산해 dti를 설정하고, 그 외에는 dti를 0으로 둔다. 이후 JDBC로 CREDIT_RATING 테이블에 (RATING_ID, CUSTOMER_ID, CREDIT_SCORE, CREDIT_GRADE, RATING_AGENCY, RATING_DATE, ANNUAL_INCOME, TOTAL_DEBT, DTI, IS_VALID) 값을 INSERT하여 저장을 확정하며, SQLException 발생 시 "신용등급 생성 실패" 메시지로 생성 예외를 던진다. 저장 성공 여부와 관계없이 사용한 PreparedStatement/Connection은 종료 처리로 정리한 뒤 ratingId를 반환한다. |
| ejbPostCreate | public void ejbPostCreate(String ratingId, String customerId, int creditScore,                                String ratingAgency, BigDecimal annualIncome, BigDecimal totalDebt) | - | - | 이 코드는 JDBC로 CREDIT_RATING 테이블의 영속성을 직접 관리하는 신용등급 BMP 엔티티 빈의 생성 후 라이프사이클 단계에서 실행되는 후처리 구간이다. 생성 요청에서 전달된 ratingId, customerId, creditScore, ratingAgency, annualIncome, totalDebt 값을 추가로 가공하거나 엔티티 필드에 반영하는 로직이 구현되어 있지 않다. 그 결과 생성 직후 필요한 보정, 연관 데이터 설정, 검증, 추가 저장과 같은 후처리는 수행되지 않고, 실제 등록/초기화는 앞선 생성 단계의 처리 결과에만 의존한다. 외부 설정 키나 테이블/SQL을 직접 참조하거나 다른 구성요소를 호출하는 동작도 없다. |
| ejbFindByPrimaryKey | public String ejbFindByPrimaryKey(String ratingId) throws FinderException | - | - | 신용등급 BMP 구현체에서, 입력받은 RATING_ID(신용등급 식별자)가 CREDIT_RATING 테이블에 실제로 존재하는지 확인하기 위한 기본키 조회를 수행한다. 데이터베이스 연결을 얻은 뒤 "SELECT RATING_ID FROM CREDIT_RATING WHERE RATING_ID = ?"를 준비하고, 조건값으로 전달된 식별자를 바인딩해 조회를 실행한다. 조회 결과가 한 건도 없으면 "신용등급을 찾을 수 없음: {식별자}" 메시지로 미존재 오류를 발생시켜, 이후 흐름에서 유효하지 않은 기본키로 엔티티를 다루지 못하게 차단한다. SQL 실행 중 오류가 발생하면 "신용등급 PK 조회 실패"로 포장해 조회 실패로 보고하며, 성공 시에는 입력받은 식별자를 그대로 반환한다. 마지막에는 조회 결과/SQL 실행 객체/연결을 예외 여부와 무관하게 정리하여 리소스 누수를 방지한다. |
| ejbFindAll | public Collection ejbFindAll() throws FinderException | - | - | JDBC로 CREDIT_RATING 테이블의 영속성을 직접 관리하는 신용등급 BMP 구현체에서, 전체 신용등급 목록을 식별자 기준으로 조회하기 위한 처리이다. 데이터베이스 연결을 획득한 뒤 "SELECT RATING_ID FROM CREDIT_RATING"를 실행하여 결과 집합을 순회하면서 각 행의 RATING_ID 값을 수집하고, 수집된 식별자 목록을 반환한다. 조회 중 SQL 예외가 발생하면 "신용등급 전체 조회 실패" 메시지로 검색 예외로 변환해 호출자에게 전달한다. 정상/예외 여부와 무관하게 마지막에는 조회 결과, SQL 실행 객체, 연결 객체를 안전하게 정리한다. |
| ejbFindByCustomerId | public Collection ejbFindByCustomerId(String customerId) throws FinderException | - | - | JDBC로 CREDIT_RATING 테이블의 영속성을 직접 관리하는 신용등급 BMP 구현체에서, 특정 고객에 대한 신용등급 식별자 목록을 조회한다. 데이터베이스 연결을 얻은 뒤 "SELECT RATING_ID FROM CREDIT_RATING WHERE CUSTOMER_ID = ?" 쿼리를 준비하고, 입력받은 CUSTOMER_ID 값을 바인딩하여 조회를 수행한다. 조회 결과를 순회하면서 각 행의 RATING_ID 값을 수집해 컬렉션으로 반환한다. 조회 과정에서 SQLException이 발생하면 메시지를 포함해 FinderException으로 변환하여 조회 실패로 보고하며, 마지막에는 결과/구문/연결 리소스를 정리 로직으로 안전하게 닫는다. |
| ejbLoad | public void ejbLoad() | - | - | JDBC로 CREDIT_RATING 테이블에서 기본키에 해당하는 RATING_ID 조건으로 단건을 조회해, 영속 상태의 신용등급 정보를 메모리 상태로 다시 적재한다. 조회 결과가 존재하면 RATING_ID, CUSTOMER_ID, CREDIT_SCORE, CREDIT_GRADE, RATING_AGENCY, RATING_DATE, ANNUAL_INCOME, TOTAL_DEBT, DTI, IS_VALID 컬럼 값을 각각 ratingId, customerId, creditScore, creditGrade, ratingAgency, ratingDate, annualIncome, totalDebt, dti, isValid 필드에 반영한다. 데이터베이스 처리 중 SQLException이 발생하면 "ejbLoad 실패: " 메시지를 포함한 EJBException으로 감싸 예외를 상위로 전달한다. 처리 종료 시에는 조회 결과/SQL 실행 객체/연결을 정리하는 종료 처리를 호출해 리소스가 누수되지 않도록 한다. |
| ejbStore | public void ejbStore() | - | - | JDBC로 CREDIT_RATING 테이블의 신용등급 데이터를 직접 관리하는 BMP 구현 흐름 중, 현재 메모리에 유지된 신용등급 정보를 데이터베이스에 '수정 확정'하는 갱신 처리를 수행한다. CREDIT_RATING에 대해 UPDATE를 실행하며, CUSTOMER_ID, CREDIT_SCORE, CREDIT_GRADE, RATING_AGENCY, RATING_DATE, ANNUAL_INCOME, TOTAL_DEBT, DTI, IS_VALID 값을 현재 상태 값으로 설정하고 RATING_ID가 일치하는 행만 변경한다. SQL 실행 중 SQLException이 발생하면 "ejbStore 실패: ..." 메시지로 EJBException을 발생시켜 상위로 실패를 명확히 전파한다. 처리 종료 시에는 성공/실패와 무관하게 SQL 실행 객체와 DB 연결을 정리하는 종료 처리를 호출해 리소스 누수를 방지한다. |
| ejbRemove | public void ejbRemove() throws RemoveException | - | - | 이 코드는 JDBC로 신용등급 정보를 직접 영속화하는 구성에서, 신용등급 레코드를 물리적으로 삭제하는 종료 처리이다. 데이터베이스 연결을 획득한 뒤 "DELETE FROM CREDIT_RATING WHERE RATING_ID = ?"를 준비하고, 엔티티의 기본키 값을 바인딩하여 CREDIT_RATING 테이블에서 RATING_ID가 일치하는 행을 삭제한다. 삭제 중 SQL 오류가 발생하면 원인 메시지를 포함해 삭제 실패로 간주되는 제거 예외를 발생시켜 상위 호출 흐름에 전달한다. 성공/실패와 무관하게 finally에서 조회 결과 없이도 준비된 SQL 실행 객체와 연결을 정리하여 리소스 누수를 방지한다. |
| setEntityContext | public void setEntityContext(EntityContext ctx) | - | - | 이 코드는 JDBC로 CREDIT_RATING 테이블 영속성을 직접 관리하는 신용등급 BMP 엔티티 빈 구현체에서, 컨테이너가 제공하는 엔티티 실행 환경 정보를 주입받아 내부 상태로 보관한다. 이후 영속성 처리(예: 로딩, 저장, 삭제) 과정에서 해당 실행 환경 정보를 활용할 수 있도록 참조를 설정해 둔다. 별도의 검증, 변환, 예외 처리 없이 전달받은 값을 그대로 저장하므로, 초기화/환경 설정 단계의 역할에 집중한다. |
| unsetEntityContext | public void unsetEntityContext() | - | - | 이 코드는 JDBC로 CREDIT_RATING 테이블 영속성을 직접 관리하는 BMP 방식 구현에서, 컨테이너가 제공하던 실행 컨텍스트 참조를 해제하는 역할을 한다. 보관 중이던 컨텍스트 값을 null로 설정하여 더 이상 컨테이너 컨텍스트에 의존하지 않도록 만들고, 이후 생명주기에서 잘못된 참조가 사용되는 것을 방지한다. 이 과정은 creditScore, creditGrade 등 신용등급 도메인 데이터 자체를 조회하거나 변경하지 않고, 내부 상태 중 컨텍스트 참조만 정리한다. |
| ejbActivate | public void ejbActivate() | - | - | 이 구성요소는 JDBC로 CREDIT_RATING 테이블에 대한 영속성을 직접 관리하는 신용등급 BMP 구현체의 생명주기 일부를 담당한다. 인스턴스가 비활성 상태에서 다시 활성 상태로 전환될 때 호출되는 콜백 지점이지만, 본 범위에서는 아무 동작도 수행하지 않는다. 따라서 활성화 시점에 별도의 리소스 재획득, 필드 재초기화, 데이터 재조회, 유효성 갱신 같은 처리를 하지 않고 컨테이너의 기본 동작에 위임한다. |
| ejbPassivate | public void ejbPassivate() | - | - | 이 코드는 JDBC로 CREDIT_RATING 테이블의 영속성을 직접 관리하는 신용등급 BMP 엔티티의 수명주기 중, 인스턴스가 패시베이션될 때 실행되는 콜백 지점에 해당한다. 그러나 본문이 비어 있어 패시베이션 직전에 ratingId, customerId, creditScore, creditGrade, ratingAgency, ratingDate, annualIncome, totalDebt, dti, isValid 등의 상태를 정리하거나 외부 자원을 해제하는 작업을 수행하지 않는다. 따라서 데이터 조회나 변경, JNDI 데이터소스("java:comp/env/jdbc/LoanDS") 접근, 컨텍스트 처리 같은 부수효과가 발생하지 않는 무동작 구현이다. |
| getConnection | private Connection getConnection() throws SQLException | - | - | 이 코드는 JDBC로 CREDIT_RATING 테이블의 영속성을 직접 관리하는 구현에서, 데이터베이스 작업에 사용할 연결을 확보하기 위한 공통 절차를 제공한다. JNDI 이름 "java:comp/env/jdbc/LoanDS"로 데이터 소스를 조회한 뒤, 그 데이터 소스로부터 데이터베이스 연결을 획득해 반환한다. 이름 기반 조회 과정에서 NamingException이 발생하면, 이를 SQL 처리 실패로 통일해 다루기 위해 SQLException으로 변환하고 "DataSource 룩업 실패: " 메시지를 포함해 상위 로직에 전달한다. 결과적으로 이후 조회/저장/갱신/삭제 로직이 동일한 연결 획득 방식을 재사용할 수 있게 한다. |
| closeResources | private void closeResources(ResultSet rs, PreparedStatement ps, Connection conn) | - | - | 신용등급 정보를 JDBC로 직접 영속화하는 BMP 구현체 내부에서, 데이터베이스 작업 중 사용한 리소스를 안전하게 정리하기 위한 종료 처리를 수행한다. 조회 결과, SQL 실행 객체, 데이터베이스 연결 객체가 각각 null이 아닐 때만 닫기를 시도하며, 각 닫기 과정은 예외가 발생해도 이후 정리 단계가 중단되지 않도록 개별적으로 처리된다. 닫기 과정에서 발생하는 SQLException은 별도 조치 없이 무시하여, 정리 실패가 상위 흐름(신용등급 조회/저장 로직)의 주요 예외로 전파되지 않게 한다. |

#### 필드

| 이름 | 타입 | 수정자 | 요약 |
| --- | --- | --- | --- |
| serialVersionUID | long | - | 직렬화(Serializable) 시 클래스 버전 호환성을 검증하기 위한 고정 식별자이며, 값은 1L로 설정된 상수다. |
| ctx | EntityContext | - | 이 필드는 BMP(Entity Bean Managed Persistence) 방식의 신용등급 엔티티 빈에서 EJB 컨테이너가 주입하는 엔티티 컨텍스트를 보관하며, 빈의 라이프사이클/트랜잭션 및 보안 정보 접근이나 기본키 조회 등 컨테이너 관련 기능을 수행할 때 사용된다. |
| ratingId | String | - | 신용등급 BMP 엔티티 빈에서 CREDIT_RATING 테이블의 특정 신용등급 레코드를 식별하기 위한 등급 ID(식별자) 값을 저장하는 필드이다. |
| customerId | String | - | 신용등급 BMP 엔티티가 CREDIT_RATING 테이블에서 특정 레코드를 식별하고 조회·저장할 때 사용하는 고객 식별자(ID)를 담는 필드입니다. |
| creditScore | int | - | 신용등급 엔티티에서 한 개인(또는 대상)의 신용 점수를 정수값으로 보관하는 필드이며, JDBC로 CREDIT_RATING 테이블과 직접 매핑·영속화되는 핵심 데이터이다. |
| creditGrade | String | - | 신용등급 엔티티가 CREDIT_RATING 테이블과 연동될 때, 한 개체의 신용등급(등급 코드/값)을 문자열로 보관하는 필드입니다. |
| ratingAgency | String | - | 신용등급 BMP 엔티티에서 해당 신용등급을 부여한 평가기관(신용평가사)의 이름 또는 식별자를 저장하는 문자열 필드입니다. |
| ratingDate | Date | - | 신용등급(CREDIT_RATING) 정보를 JDBC로 직접 영속화하는 엔티티에서, 해당 신용등급이 산정·적용된 일자(평가일/등급일)를 저장하는 날짜 값이다. |
| annualIncome | BigDecimal | - | 신용등급 BMP 엔티티에서 신용등급 정보를 관리하기 위해 개인(또는 고객)의 연간 소득 금액을 BigDecimal로 보관하는 필드이며, CREDIT_RATING 테이블에 저장·조회되는 영속 데이터로 사용된다. |
| totalDebt | BigDecimal | - | 신용등급 BMP 엔티티에서 CREDIT_RATING 테이블에 저장·조회되는 총 부채 금액(전체 채무 규모)을 담는 BigDecimal 필드입니다. |
| dti | BigDecimal | - | 신용등급 정보를 CREDIT_RATING 테이블에 직접 JDBC로 영속화하는 BMP 엔티티에서, 부채 대비 소득 비율(DTI)을 BigDecimal로 보관하는 필드이다. |
| isValid | boolean | - | 신용등급 정보를 나타내는 BMP 엔티티 빈 인스턴스가 현재 유효한 상태인지(데이터가 정상적으로 존재/사용 가능한지)를 표시하는 불리언 플래그이다. |
| DS_JNDI | String | - | JDBC로 CREDIT_RATING 테이블을 직접 영속화하는 BMP 엔티티 빈이 사용할 데이터소스의 JNDI 이름(\"java:comp/env/jdbc/LoanDS\")을 보관하는 정적 상수 설정값이다. |

#### 구조 관계

| 방향 | 관계 | 대상 | 속성 |
| --- | --- | --- | --- |
| → | DEPENDENCY | EntityContext | source_member=setEntityContext, usage=parameter |

#### 호출 관계

| 방향 | 대상 | 호출코드 |
| --- | --- | --- |
| → | CreditRatingBean | 165:         recalculateGrade(); |
| → | CreditRatingBean | 195:             closeResources(null, ps, conn); |
| → | CreditRatingBean | 223:             closeResources(rs, ps, conn); |
| → | CreditRatingBean | 243:             closeResources(rs, ps, conn); |
| → | CreditRatingBean | 264:             closeResources(rs, ps, conn); |
| → | CreditRatingBean | 295:             closeResources(rs, ps, conn); |
| → | CreditRatingBean | 322:             closeResources(null, ps, conn); |
| → | CreditRatingBean | 337:             closeResources(null, ps, conn); |

#### 데이터 접근

| 대상 | 관계 | 근거 | 신뢰도 |
| --- | --- | --- | --- |
| CREDIT_RATING_ENTITY | READS | - | - |
| ejb-jar.xml | REFER_TO | - | 0.9 |
| CREDIT_RATING_ENTITY | READS | - | - |
| ejb-jar.xml | REFER_TO | - | 0.9 |
| CREDIT_RATING_ENTITY | READS | - | - |
| ejb-jar.xml | REFER_TO | - | 0.9 |
| CREDIT_RATING_ENTITY | READS | - | - |
| ejb-jar.xml | REFER_TO | - | 0.9 |
| CREDIT_RATING_ENTITY | READS | - | - |
| ejb-jar.xml | REFER_TO | - | 0.9 |
| CREDIT_RATING_ENTITY | READS | - | - |
| ejb-jar.xml | REFER_TO | - | 0.9 |
| CREDIT_RATING_ENTITY | READS | - | - |
| ejb-jar.xml | REFER_TO | - | 0.9 |

#### 요약 코드

```
없음
```

### CreditRatingLocal

#### 기본 정보

| 항목 | 값 |
| --- | --- |
| 이름 | CreditRatingLocal |
| 타입 | CLASS |
| FQN | com.banking.loan.entity.CreditRatingLocal |
| 패키지 | com.banking.loan.entity |
| 스테레오타입 | COMMAND/READMODEL |
| 파일 | - |
| 라인 | - |
| 토큰 | - |

#### 요약

> com.banking.loan.entity.CreditRatingLocal은 신용등급 BMP 엔티티 빈의 로컬 컴포넌트 인터페이스로, 고객의 신용등급 정보에 대한 접근자와 비즈니스 메서드를 정의한다. ratingId, customerId, creditScore, creditGrade, ratingAgency, ratingDate(평가일자), annualIncome(연간소득), totalDebt(총부채), dti 같은 핵심 속성과 isValid(true/false) 상태를 통해 특정 고객의 신용평가 레코드를 식별하고 내용·출처·기준 시점 및 유효성을 관리한다. 또한 저장된 등급 결과가 최신 기준/요인 변화로 더 이상 유효하지 않을 수 있음을 전제로, 신용등급을 다시 산정해 내부 상태에 반영(recalculateGrade)하거나 현재 상태를 무효 처리(invalidate)하는 동작을 제공하며, 전형적으로 유효 → 무효 → 재산정의 상태 갱신 흐름을 지원한다.

#### 메서드

| 이름 | 시그니처 | 반환타입 | 수정자 | 요약 |
| --- | --- | --- | --- | --- |
| getRatingId | String getRatingId() | - | - | 이 컴포넌트는 고객의 신용등급 정보에 대한 접근자와 비즈니스 기능을 정의하기 위해 제공된다. 이 범위의 코드는 고객 신용등급 정보 중 신용등급을 식별하기 위한 ID 값을 문자열로 조회해 반환하는 접근자 역할을 한다. 반환된 식별자는 신용등급 레코드/상태를 구분하거나 다른 처리에서 참조 키로 사용될 수 있다. 값 조회만 수행하며 데이터의 생성·수정·삭제 등 상태 변경 의도는 없다. |
| getCustomerId | String getCustomerId() | - | - | 이 로컬 컴포넌트 인터페이스는 고객의 신용등급 정보에 접근하기 위한 접근자와 비즈니스 기능을 정의한다. 이 범위의 선언은 해당 신용등급 정보가 어떤 고객에 속하는지 식별하기 위해 customerId(고객식별자)를 문자열로 제공한다. 반환된 고객식별자는 신용등급 정보 조회·연계 시 대상 고객을 특정하는 키로 사용되며, 내부 상태를 변경하는 동작은 포함하지 않는다. |
| setCustomerId | void setCustomerId(String customerId) | - | - | 이 컴포넌트는 고객의 신용등급 정보에 접근하고 관련 비즈니스 동작을 수행하기 위한 로컬 인터페이스를 정의한다. 여기서는 신용등급 정보가 귀속되는 고객을 식별할 수 있도록 고객 식별자 값을 설정하는 동작을 규정한다. 반환값 없이 입력으로 받은 고객 식별자를 엔티티의 상태로 반영하는 성격이므로, 이후 신용등급 정보 조회/갱신 시 기준 키로 사용되도록 준비한다. |
| getCreditScore | int getCreditScore() | - | - | 이 구성요소는 고객의 신용등급 정보에 접근하기 위한 인터페이스로, 신용등급 관련 접근자와 비즈니스 메서드를 정의한다. 이 범위의 기능은 현재 보유한 신용등급 점수를 정수 형태로 조회해 반환하는 읽기 전용 접근자이다. 외부 입력을 받거나 내부 상태를 변경하는 동작 없이, 저장된 신용등급 점수 값을 호출자에게 제공하는 목적을 가진다. |
| setCreditScore | void setCreditScore(int creditScore) | - | - | 이 컴포넌트 인터페이스는 고객의 신용등급 정보를 다루기 위한 접근자와 비즈니스 동작을 정의하며, 그중 신용등급(creditScore)을 갱신하는 설정 동작을 제공한다. 입력으로 전달된 정수 값을 엔티티가 보유하는 신용등급(creditScore)에 반영하도록 규약을 정해, 이후 신용등급 기반 판단이나 조회에서 최신 값이 사용되게 한다. 반환값은 없으며, 신용등급 값 자체를 변경하는 목적의 동작이다. |
| getCreditGrade | String getCreditGrade() | - | - | 이 로컬 컴포넌트 인터페이스는 고객의 신용등급 정보에 접근하기 위한 접근자와 비즈니스 동작을 정의한다. 이 선언은 고객 신용정보 중 신용등급을 문자열 형태로 조회해 반환하는 접근자 역할을 한다. 입력값 없이 현재 엔티티가 보유한 신용등급 값을 읽어 제공하는 목적이며, 상태 변경이나 저장 동작은 포함하지 않는다. |
| setCreditGrade | void setCreditGrade(String creditGrade) | - | - | 이 구성요소는 고객의 신용등급 정보에 대한 접근자와 비즈니스 동작을 정의하는 로컬 컴포넌트 인터페이스의 일부다. 이 범위의 선언은 고객 신용등급 정보에서 creditGrade(신용등급) 값을 외부 입력으로 받아 해당 엔티티의 신용등급을 변경하도록 규약을 제공한다. 조회가 아니라 신용등급 값을 갱신하는 목적이므로, 호출되는 측에서는 고객 신용등급 상태를 업데이트하는 명령 성격으로 사용된다. |
| getRatingAgency | String getRatingAgency() | - | - | 이 컴포넌트는 고객의 신용등급 정보에 대한 접근자와 비즈니스 동작을 정의하는 로컬 인터페이스이며, 이 구문은 그 중 신용평가 정보를 제공한 ratingAgency(평가기관/신용평가사) 값을 조회해 반환하기 위한 접근자이다. 반환값은 텍스트(String)로, 신용등급이 어떤 평가기관 기준으로 산정되었는지 식별하거나 표시하는 데 사용된다. 선언만 존재하며 외부 자원 접근이나 다른 객체 호출 없이 값의 조회 의도만을 나타낸다. |
| setRatingAgency | void setRatingAgency(String ratingAgency) | - | - | 이 컴포넌트는 고객의 신용등급 정보에 대한 접근자와 업무 동작을 정의하며, 이 범위의 기능은 신용등급 정보에 포함되는 평가기관 식별값을 변경하도록 규정한다. 입력으로 전달된 ratingAgency(평가기관) 값을 해당 신용등급 정보에 설정해, 이후 신용평가 출처를 일관되게 관리할 수 있게 한다. 조회 목적이 아니라 속성 값을 갱신하는 의도가 명확한 쓰기 동작이다. |
| getRatingDate | Date getRatingDate() | - | - | 이 컴포넌트는 고객의 신용등급 정보에 대한 접근자와 관련 비즈니스 동작을 정의하기 위한 인터페이스이며, 여기서는 신용등급 정보의 기준 시점을 제공하는 역할을 한다. 호출자는 반환되는 날짜 값을 통해 신용등급이 언제 산정·갱신되었는지(평가/적용일)를 확인하고, 최신성 판단이나 유효기간 검증 같은 후속 판단에 활용할 수 있다. 단순 조회 성격으로, 내부 상태를 변경하거나 외부 자원을 갱신하는 동작은 포함하지 않는다. |
| setRatingDate | void setRatingDate(Date ratingDate) | - | - | 이 구성요소는 고객의 신용등급 정보에 대한 접근자와 비즈니스 동작을 정의하며, 그중 신용등급 산정 시점 정보를 갱신하는 역할을 포함한다. 이 선언은 입력으로 받은 ratingDate(평가일자)를 신용등급 정보에 설정하여 해당 기록의 평가 기준일을 변경한다. 따라서 이후 신용등급 정보가 조회되거나 다른 비즈니스 규칙이 적용될 때, 최신 평가일자가 반영되도록 상태를 갱신하는 목적을 가진다. |
| getAnnualIncome | BigDecimal getAnnualIncome() | - | - | 이 구성요소는 고객의 신용등급 정보에 대한 접근자와 비즈니스 동작을 정의하는 로컬 컴포넌트 인터페이스의 일부이다. 여기서는 고객의 annualIncome(연간소득) 값을 조회하여 숫자형(정밀 소수)으로 반환하는 접근자를 제공한다. 입력 파라미터 없이 기존에 보유한 고객 신용 관련 데이터에서 연간소득 값을 읽어오는 용도이며, 데이터의 생성·수정·삭제 같은 상태 변경 의도는 없다. |
| setAnnualIncome | void setAnnualIncome(BigDecimal annualIncome) | - | - | 신용등급 BMP 엔티티 빈의 로컬 컴포넌트 인터페이스에서 고객 신용등급 정보에 대한 접근자/비즈니스 동작을 정의하는 일부이다. 이 범위는 annualIncome(연간소득) 값을 엔티티의 신용등급 관련 정보에 반영(갱신)하기 위한 설정 동작을 제공한다. 결과적으로 연간소득 값이 변경되도록 의도된 인터페이스 계약이며, 이후 신용등급 산정/검증 등에서 해당 값이 활용될 수 있다. |
| getTotalDebt | BigDecimal getTotalDebt() | - | - | 이 컴포넌트는 고객의 신용등급 정보에 접근하기 위한 조회·업무 기능을 정의하며, 그중 이 범위는 고객의 총부채(전체 부채 규모)를 조회해 반환하는 계약을 제공한다. 반환값은 금액 계산에 적합한 임의정밀도 수치로 표현되어, 신용평가에서 부채 총액을 정밀하게 다루려는 목적을 가진다. 입력 파라미터 없이 현재 대상 고객(또는 현재 엔티티 인스턴스)에 연결된 총부채 값을 읽어오는 형태로 설계되어 있다. |
| setTotalDebt | void setTotalDebt(BigDecimal totalDebt) | - | - | 신용등급 정보에 대한 접근자/비즈니스 메서드를 제공하는 로컬 컴포넌트 인터페이스의 일부로, 고객의 부채 규모를 나타내는 totalDebt(총부채) 값을 설정하기 위한 계약을 정의한다. 입력으로 전달된 totalDebt 값을 엔티티의 상태로 반영해 이후 신용평가/등급 산정에 활용될 수 있도록 한다. 반환값이 없으므로 설정 행위 자체가 목적이며, 구현체에서는 해당 값이 실제 저장 상태로 갱신되는 흐름을 전제한다. |
| getDti | BigDecimal getDti() | - | - | 이 컴포넌트는 고객의 신용등급 정보에 접근하기 위한 로컬 인터페이스로서, 신용평가에 필요한 값들의 접근자를 제공한다. 이 구문은 고객의 DTI 값을 BigDecimal 형태로 반환하도록 정의된 조회용 접근자이다. 내부 계산이나 저장·갱신 로직 없이, 이미 보유한 신용등급 관련 데이터 중 DTI를 외부에 제공하는 목적을 가진다. |
| setDti | void setDti(BigDecimal dti) | - | - | 이 컴포넌트는 고객의 신용등급 정보에 대한 접근자와 비즈니스 동작을 제공하며, 그중 dti 값을 갱신하는 입력 지점을 정의한다. 호출자는 정밀한 수치 타입으로 전달된 dti(부채상환비율로 해석되는 값)를 신용등급 정보에 반영하도록 요청한다. 이 동작은 조회가 아니라 신용등급 관련 데이터의 특정 속성을 변경하는 목적을 가진다. |
| getIsValid | boolean getIsValid() | - | - | 이 구성요소는 고객의 신용등급 정보에 접근하기 위한 로컬 컴포넌트 인터페이스의 일부이며, 신용등급 관련 상태를 조회하는 역할을 가진다. 이 구간은 신용등급 정보가 현재 유효한 상태인지 여부를 불리언 값으로 반환하도록 계약을 정의한다. 반환값이 true이면 해당 신용등급 정보가 유효함을, false이면 유효하지 않음을 의미하도록 사용될 수 있다. |
| setIsValid | void setIsValid(boolean isValid) | - | - | 이 컴포넌트는 고객의 신용등급 정보에 대한 접근자와 비즈니스 동작을 제공하는 계약의 일부이며, 여기서는 신용등급 정보의 유효 여부를 나타내는 플래그를 갱신하는 역할을 한다. 입력으로 전달된 참/거짓 값에 따라 해당 신용등급 정보가 정상적으로 사용할 수 있는 상태인지, 또는 유효하지 않아 업무 처리에서 배제되어야 하는 상태인지를 내부 상태로 반영한다. 이를 통해 이후 신용등급 관련 조회/판단 로직이 유효성 상태를 기준으로 동작할 수 있도록 상태를 변경한다. |
| recalculateGrade | void recalculateGrade() | - | - | 이 구성요소는 고객의 신용등급 정보에 대한 접근자와 업무 동작을 정의하는 로컬 인터페이스이며, 그중 이 동작은 고객의 신용등급을 다시 산정하도록 규정한다. 재산정은 기존에 저장되어 있던 신용등급 결과가 최신 기준이나 평가 요인 변화로 인해 더 이상 유효하지 않을 수 있다는 전제를 반영해, 등급 산정 결과를 갱신하기 위한 목적을 가진다. 반환값이 없으므로 계산 결과는 내부에 보관된 신용등급 정보에 반영(갱신)되는 형태의 상태 변경을 전제로 한다. 다만 인터페이스 선언만 제공되므로, 어떤 입력 데이터로 어떤 규칙을 적용하는지와 실제 저장 방식은 구현체에 위임된다. |
| invalidate | void invalidate() | - | - | 이 구성요소는 고객의 신용등급 정보에 대한 접근자와 비즈니스 동작을 정의하는 로컬 컴포넌트 인터페이스 맥락에 속한다. 여기서 이 동작은 현재 보유 중인 신용등급 관련 상태(예: 조회·계산 결과, 캐시된 값, 유효성 플래그 등)를 더 이상 유효하지 않은 것으로 처리하도록 계약을 제공한다. 반환값과 입력값이 없는 선언으로, 구현체가 내부 상태를 무효화하거나 이후 접근 시 재조회·재계산이 발생하도록 만드는 상태 변경 성격의 처리를 수행하도록 의도된다. |

#### 필드

| 이름 | 타입 | 수정자 | 요약 |
| --- | --- | --- | --- |
| - | - | - | - |

#### 구조 관계

| 방향 | 관계 | 대상 | 속성 |
| --- | --- | --- | --- |
| ← | DEPENDENCY | CreditRatingLocalHome | source_member=create, usage=return |
| ← | DEPENDENCY | CreditRatingLocalHome | source_member=findByPrimaryKey, usage=return |
| ← | DEPENDENCY | LoanScreeningSessionBean | source_member=findLatestValidCreditRating, usage=return |
| ← | DEPENDENCY | LoanScreeningSessionBean | source_member=getCreditScreening, usage=local_var |

#### 호출 관계

| 방향 | 대상 | 호출코드 |
| --- | --- | --- |
| ← | LoanScreeningSessionBean | - |

#### 데이터 접근

| 대상 | 관계 | 근거 | 신뢰도 |
| --- | --- | --- | --- |
| - | - | - | - |

#### 요약 코드

```
없음
```

### CreditRatingLocalHome

#### 기본 정보

| 항목 | 값 |
| --- | --- |
| 이름 | CreditRatingLocalHome |
| 타입 | CLASS |
| FQN | com.banking.loan.entity.CreditRatingLocalHome |
| 패키지 | com.banking.loan.entity |
| 스테레오타입 | COMMAND/READMODEL |
| 파일 | - |
| 라인 | - |
| 토큰 | - |

#### 요약

> com.banking.loan.entity.CreditRatingLocalHome은 신용등급 BMP 엔티티 빈의 로컬 홈 인터페이스로, 신용등급의 생성 및 조회를 위한 계약을 정의한다. ratingId, customerId, creditScore, ratingAgency, annualIncome, totalDebt를 입력받아 신용등급 정보를 생성하고, 생성 성공 시 해당 신용등급 로컬 컴포넌트 참조를 반환하며 실패 시 예외를 전파한다. 또한 기본키로 단건 조회, 전체 목록 조회, customerId로 연관 신용등급 컬렉션 조회 기능을 제공하고, 조회 대상 부재나 조회 오류는 FinderException 등으로 호출자에게 전달한다.

#### 메서드

| 이름 | 시그니처 | 반환타입 | 수정자 | 요약 |
| --- | --- | --- | --- | --- |
| create | CreditRatingLocal create(String ratingId, String customerId, int creditScore,                               String ratingAgency, BigDecimal annualIncome, BigDecimal totalDebt)                               throws CreateException | - | - | 이 코드는 신용등급 정보를 생성하기 위한 로컬 홈 인터페이스 수준의 생성 계약을 정의한다. 입력으로 ratingId(등급 식별자), customerId(고객 식별자), creditScore(신용점수), ratingAgency(평가기관), annualIncome(연간소득), totalDebt(총부채)를 받아 신용등급 레코드의 신규 등록을 요청하는 의도를 가진다. 생성이 성공하면 생성된 신용등급 로컬 컴포넌트에 접근할 수 있는 참조를 반환하여, 이후 신용등급 정보의 접근자/업무 메서드 사용이 가능해진다. 생성 과정에서 문제가 발생하면 생성 실패를 나타내는 예외를 호출자에게 전파하도록 선언되어 있다. |
| findByPrimaryKey | CreditRatingLocal findByPrimaryKey(String ratingId) throws FinderException | - | - | 이 코드는 신용등급 BMP 엔티티의 생성 및 조회 기능 중, 특정 신용등급을 기본키로 조회하기 위한 계약을 정의한다. 입력으로 신용등급을 식별하는 문자열 값을 받아, 해당 식별자에 대응하는 신용등급 정보를 로컬 컴포넌트 형태로 반환하도록 되어 있다. 조회 대상이 없거나 조회 과정에서 문제가 발생하면 찾기 실패 성격의 예외를 상위 호출자에게 전달해 후속 처리(미존재/오류 구분)를 가능하게 한다. |
| findAll | Collection findAll() throws FinderException | - | - | 이 코드는 신용등급 정보를 생성·조회하기 위한 로컬 홈 인터페이스에서, 저장소에 존재하는 신용등급 데이터를 전체 목록으로 조회하기 위한 조회 연산을 선언한다. 호출자는 반환값으로 신용등급 엔티티들의 집합을 받아, 일괄 조회 결과를 순회하거나 후속 조회/선택에 활용할 수 있다. 조회 과정에서 대상 데이터를 찾지 못했거나 조회 규칙을 만족하지 못하는 등 식별/검색 실패 상황이 발생할 수 있으므로, 이러한 실패를 조회 예외로 전달하도록 계약되어 있다. |
| findByCustomerId | Collection findByCustomerId(String customerId) throws FinderException | - | - | 이 인터페이스는 신용등급 BMP 엔티티 빈에 대해 신용등급 정보를 생성·조회하기 위한 조회 규약을 정의한다. 이 선언은 고객을 식별하는 문자열을 입력으로 받아, 해당 고객과 연관된 신용등급 엔티티(들)를 컬렉션 형태로 조회해 반환하는 용도다. 조회 과정에서 엔티티를 찾지 못했거나 조회 중 오류가 발생하면 FinderException을 통해 예외를 호출자에게 전달한다. |

#### 필드

| 이름 | 타입 | 수정자 | 요약 |
| --- | --- | --- | --- |
| - | - | - | - |

#### 구조 관계

| 방향 | 관계 | 대상 | 속성 |
| --- | --- | --- | --- |
| → | DEPENDENCY | CreditRatingLocal | source_member=create, usage=return |
| → | DEPENDENCY | CreditRatingLocal | source_member=findByPrimaryKey, usage=return |
| ← | DEPENDENCY | LoanScreeningSessionBean | source_member=getCreditRatingHome, usage=return |
| ← | DEPENDENCY | LoanScreeningSessionBean | source_member=findLatestValidCreditRating, usage=local_var |

#### 호출 관계

| 방향 | 대상 | 호출코드 |
| --- | --- | --- |
| ← | LoanScreeningSessionBean | - |

#### 데이터 접근

| 대상 | 관계 | 근거 | 신뢰도 |
| --- | --- | --- | --- |
| CreditRatingLocal | REFER_TO | - | 1.0 |
| CreditRatingLocal | REFER_TO | - | 1.0 |

#### 요약 코드

```
없음
```

### CustomerBean

#### 기본 정보

| 항목 | 값 |
| --- | --- |
| 이름 | CustomerBean |
| 타입 | CLASS |
| FQN | com.banking.loan.entity.CustomerBean |
| 패키지 | com.banking.loan.entity |
| 스테레오타입 | COMMAND/READMODEL |
| 파일 | - |
| 라인 | - |
| 토큰 | - |

#### 요약

> com.banking.loan.entity.CustomerBean은 컨테이너 관리 영속성(CMP)으로 고객 정보를 저장·조회하는 고객 엔티티 빈 구현이다. 신규 고객 생성 시 customerId(고객 식별자), customerName(고객명), residentId(주민등록번호), customerType(고객유형)을 초기화하고 registrationDate(등록일자)를 현재 시스템 시간 기반의 일자로 설정한 뒤, CMP 규약에 따라 생성 결과로 null을 반환한다. annualIncome(연간소득), employerName(고용주명), creditGrade(신용등급), registrationDate(등록일자) 등 속성의 조회/변경 계약을 제공하지만 실제 반영은 컨테이너에 위임하며, 컨테이너가 제공하는 entityContext(실행/라이프사이클 컨텍스트)를 보관했다가 필요 시 해제한다. 저장(ejbStore)·제거(ejbRemove) 등 생명주기 훅은 제공하되 구현이 비어 있어 별도 저장 로직이나 삭제 시 정리/검증 없이 컨테이너 기본 처리에 맡기고, 제거 단계에서는 예외 발생 가능성만 선언해 확장 지점으로 남겨둔다.

#### 메서드

| 이름 | 시그니처 | 반환타입 | 수정자 | 요약 |
| --- | --- | --- | --- | --- |
| getCustomerId | - | - | - | 고객 정보를 컨테이너가 영속성으로 관리하는 구성에서, 고객을 식별하기 위한 customerId(고객 식별자)를 문자열로 제공하는 조회용 계약을 정의한다. 실제 값의 저장·조회 방식은 구현체에 위임되며, 이 범위의 코드는 고객 식별자를 읽어오는 역할만 규정한다. 데이터 변경이나 영속성 갱신을 수행하지 않고, 호출자가 고객을 구분·연결하는 데 필요한 식별값을 반환하는 데 목적이 있다. |
| setCustomerId | - | - | - | 컨테이너가 영속성을 관리하는 고객 정보 저장·조회 목적의 CMP 엔티티 빈 구현 맥락에서, 고객을 식별하는 customerId(고객 식별자) 값을 설정하기 위한 동작을 정의한다. 문자열로 전달된 고객 식별자를 엔티티의 해당 속성에 반영함으로써, 이후 영속 상태에 저장되거나 갱신될 수 있는 변경 지점을 만든다. 실제 설정 로직은 추상으로 선언되어 있어 구체 구현(컨테이너/구현체)에 위임되며, 이 범위 내에서는 검증·조회·저장 호출을 수행하지 않는다. |
| getCustomerName | - | - | - | 이 코드는 컨테이너가 영속성을 관리하는 고객 정보 저장·조회 구성요소에서, 고객의 이름을 문자열로 제공하기 위한 조회용 계약을 정의한다. 구현체는 고객 레코드에 저장된 이름 값을 반환해야 하며, 호출 측은 이를 통해 고객 식별/표시에 필요한 텍스트 정보를 얻는다. 메서드 본문이 없고 반환 타입만 선언되어 있어, 실제 조회 방식(CMP 필드 매핑, 로딩 시점 등)은 컨테이너 및 구현 클래스에 위임된다. 값 반환 외에 데이터 저장·수정 같은 상태 변경 의도는 드러나지 않는다. |
| setCustomerName | - | - | - | 이 코드는 컨테이너가 영속성을 관리하는 고객 정보 저장·조회용 CMP 구현에서 고객의 customerName(고객명)을 변경하기 위한 추상 동작을 정의한다. 호출자는 새로운 customerName 값을 전달해 고객 엔티티의 이름 속성을 갱신하도록 의도되어 있다. 실제로 값이 어떻게 저장소에 반영되는지(필드 갱신 방식, 영속화 시점 등)는 구현 클래스/컨테이너 설정에 의해 결정된다. 조회가 아니라 고객 정보의 상태 변경을 전제로 하는 갱신 계약이므로 변경 작업의 일부로 사용된다. |
| getResidentId | - | - | - | 고객 정보를 컨테이너가 영속적으로 관리하는 CMP 엔티티 빈 구현에서, residentId(주민등록 식별자)를 조회하기 위한 반환 계약을 추상으로 선언한다. 실제로 이 값이 어디에서 어떻게 취득되는지는 구현체나 컨테이너의 영속성 처리에 의해 결정되며, 호출자는 문자열 형태의 식별값을 얻는 것만 전제한다. 이 선언은 데이터의 등록·수정·삭제를 수행하지 않고, 고객 식별 정보를 읽어오는 목적의 인터페이스를 정의한다. |
| setResidentId | - | - | - | 이 클래스는 컨테이너가 영속성을 관리하는 고객 CMP 엔티티 빈 구현을 전제로 고객 정보를 저장·조회하는 역할을 가진다. 이 범위의 코드는 고객 정보의 residentId(주민등록번호) 값을 변경하기 위한 추상 동작을 선언하여, 실제 구현에서 해당 속성이 어떻게 저장/갱신될지(컨테이너 관리 영속성 포함)를 위임한다. 즉, 고객 식별에 활용되는 residentId를 설정(상태 변경)하는 계약만 정의하고 구체 로직은 하위 구현이 담당한다. |
| getCustomerType | - | - | - | 이 클래스는 컨테이너가 영속성을 관리하는 고객 CMP 엔티티 빈 구현으로, 고객 정보를 저장·조회하는 책임을 가진다. 이 범위의 코드는 고객의 유형을 나타내는 값을 문자열로 제공하도록 강제하는 추상 동작을 선언한다. 구현체는 고객 분류 기준에 따라 고객 유형 값을 결정해 반환해야 하며, 이 선언 자체는 영속 상태를 변경하지 않고 값 조회 성격만 가진다. |
| setCustomerType | - | - | - | 고객 정보를 저장·조회하는 CMP 기반의 엔티티 구현에서 customerType(고객유형)을 변경하기 위한 추상 설정 지점을 정의한다. 호출자는 문자열로 전달된 고객유형 값을 엔티티의 해당 속성에 반영하도록 구현해야 하며, 이 변경은 컨테이너가 관리하는 영속성 범위 안에서 저장 대상으로 취급될 수 있다. 구현체에서는 유효하지 않은 고객유형 값 처리(예: 허용 코드 검증, null/공백 처리)와 같은 정책을 이 지점에 포함시킬 수 있다. |
| getAddress | - | - | - | 고객 정보를 컨테이너가 영속적으로 관리하는 CMP 엔티티 빈 구현에서, 고객의 address(주소) 값을 조회하기 위한 반환 규약을 선언한다. 구현체는 저장된 고객 레코드로부터 주소 문자열을 제공해야 하며, 이 선언 자체는 데이터 변경을 수행하지 않는다. 호출 측에서는 고객의 주소 정보를 표시하거나 다른 조회 로직에 활용하기 위해 이 값을 읽어 간다. |
| setAddress | - | - | - | 이 코드는 컨테이너가 영속성을 관리하는 고객 정보 저장·조회용 구성요소에서, 고객의 address(주소) 값을 변경하기 위한 계약(추상 선언)을 정의한다. 문자열로 전달된 주소를 해당 고객 데이터의 주소 속성에 반영하도록 구현체가 제공되어야 하며, 여기서는 실제 저장/검증/갱신 로직이 포함되지 않는다. 즉, 주소 변경이라는 상태 변경 의도만 명시하고 구체적인 변경 방식은 구현 클래스에 위임한다. |
| getPhoneNumber | - | - | - | 이 코드는 컨테이너가 영속성을 관리하는 고객 정보 구성요소에서, 고객의 연락처 중 전화번호 값을 조회하기 위한 추상 조회 지점을 정의한다. 구현체는 저장·조회되는 고객 정보에서 전화번호가 어떻게 보관되는지에 맞춰 문자열 형태의 전화번호를 반환해야 한다. 이 선언 자체는 데이터를 생성·수정·삭제하지 않고, 고객 정보의 특정 속성을 읽어 제공하는 목적에 집중한다. |
| setPhoneNumber | - | - | - | 이 클래스는 컨테이너가 영속성을 관리하는 고객 정보 저장·조회용 CMP 엔티티 빈 구현을 전제로 하며, 그중 고객의 연락처 정보를 갱신하는 동작을 계약으로 정의한다. 입력으로 전달된 phoneNumber(전화번호) 값을 고객 데이터의 phoneNumber(전화번호) 속성에 반영하도록 강제하지만, 현재 범위에서는 추상 선언만 제공되어 실제 저장/반영 방식은 구현체에 위임된다. 결과적으로 고객의 전화번호를 변경하는 쓰기(상태 변경) 작업의 진입점 역할을 한다. |
| getEmail | - | - | - | 이 코드는 컨테이너가 영속성을 관리하는 고객 정보 구성요소에서, 고객의 email 값을 조회하기 위한 추상 접근 지점을 정의한다. 실제 저장소 접근 및 값 반환 방식은 구현체(또는 컨테이너 생성 코드)에 위임되어 있으며, 여기서는 조회 계약만 제공한다. 호출자 관점에서는 고객 정보 중 email을 읽어오기 위한 표준화된 인터페이스로 사용된다. |
| setEmail | - | - | - | 고객 정보를 저장·조회하는 CMP 엔티티 빈 구현 맥락에서, 고객의 연락처 정보 중 email 값을 변경하기 위한 설정 동작을 정의한다. 입력으로 전달된 email 문자열을 고객 정보의 email 속성에 반영해 영속 상태의 값이 갱신되도록 하는 목적을 가진다. 다만 구현부가 없는 추상 선언이므로, 실제 값 반영 방식(저장 시점/검증/정규화)은 구체 구현 또는 컨테이너의 영속성 관리 메커니즘에 의해 결정된다. |
| getAnnualIncome | - | - | - | 고객 정보를 영속적으로 저장·조회하는 CMP 엔티티 빈 구현의 일부로, 고객의 annualIncome(연간소득)을 금액 타입으로 제공하기 위한 조회용 계약을 정의한다. 구현체는 고객 레코드에 저장된 연간소득 값을 반환해야 하며, 이 선언 자체는 값을 변경하거나 저장하지 않는다. 메서드 본문이 없는 추상 선언이므로 조회 로직의 구체적인 데이터 접근 방식은 컨테이너/구현 클래스에서 결정된다. |
| setAnnualIncome | - | - | - | 고객 정보를 영속적으로 저장·조회하는 CMP 엔티티 빈 구현에서, 고객의 annualIncome(연간소득) 값을 변경하기 위한 설정 지점을 정의한다. 입력으로 전달된 연간소득 값을 해당 고객 레코드의 연간소득 속성에 반영하는 것이 목적이며, 실제 저장 동작은 컨테이너가 관리하는 영속성 메커니즘에 의해 처리된다. 이 코드는 추상 선언이므로 구체적인 값 대입/검증 로직은 하위 구현에 위임된다. |
| getEmployerName | - | - | - | 고객 정보를 컨테이너가 영속성으로 관리하는 CMP 엔티티 빈 구현에서, 고객의 고용주명(employerName)을 문자열로 제공하기 위한 조회용 계약을 정의한다. 이 범위는 구현을 가지지 않는 추상 선언이므로, 실제 값은 구체 구현체가 영속 상태(저장된 고객 정보)로부터 읽어 반환하도록 강제한다. 입력 파라미터 없이 고용주명만을 반환하므로, 상태 변경 없이 고객 정보의 특정 속성을 조회하는 목적에 집중한다. |
| setEmployerName | - | - | - | 고객 정보를 컨테이너 관리 영속성 방식으로 저장·조회하는 CMP 구현에서, 고객의 employerName(고용주명) 값을 변경하기 위한 설정 동작을 정의한다. 입력으로 전달된 employerName을 고객 레코드의 해당 속성에 반영하도록 하는 계약이며, 실제 저장/동기화 방식은 구현 클래스나 컨테이너의 CMP 매핑에 의해 결정된다. 구현이 제공되면 employerName 변경은 고객 정보의 상태를 갱신하는 쓰기 동작으로 취급된다. |
| getCreditGrade | - | - | - | 이 클래스는 컨테이너가 영속성을 관리하는 고객 정보의 저장·조회 책임을 가지며, 그중 고객의 신용등급 정보를 제공하는 동작을 정의한다. 이 코드는 신용등급을 문자열로 반환해야 한다는 계약만 선언하고 실제 조회/산정 방식은 하위 구현에 위임한다. 호출자 관점에서는 고객의 현재 신용등급을 읽기 목적으로 얻는 인터페이스로 사용된다. |
| setCreditGrade | - | - | - | 이 클래스는 컨테이너가 영속성을 관리하는 고객 정보 저장·조회용 CMP 구현으로, 고객의 상태를 구성하는 데이터가 변경될 수 있도록 정의된다. 이 범위는 고객의 creditGrade(신용등급) 값을 외부에서 전달받아 해당 고객 레코드에 반영하기 위한 변경 동작을 추상 계약으로 선언한다. 구현체에서는 creditGrade 변경이 고객 정보의 영속 상태에 적용되어 이후 조회 시 반영되도록 처리되는 것이 전제된다. |
| getRegistrationDate | - | - | - | 이 코드는 컨테이너가 영속성을 관리하는 고객 정보 구성요소에서, 고객의 registrationDate(등록일자)를 조회해 반환하기 위한 계약을 정의한다. 반환값은 날짜/시간을 표현하는 값이며, 고객이 시스템에 등록된 시점을 나타내는 용도로 사용된다. 구현은 하위 구현체에 위임되어 있어, 실제 등록일 저장 방식이나 조회 방식은 여기에서 고정하지 않는다. |
| setRegistrationDate | - | - | - | 이 코드는 고객 정보를 저장·조회하는 영속 객체 구현에서, 고객의 registrationDate(등록일자)를 변경하기 위한 설정 동작을 정의한다. 입력으로 받은 등록일자를 고객 데이터의 해당 속성에 반영하도록 하는 계약(추상 선언)만 제공하며, 실제 저장 반영 방식은 구현체가 결정한다. 따라서 호출 측은 고객의 등록일자를 수정하려는 의도로 이 동작을 사용하게 된다. |
| ejbCreate | public String ejbCreate(String customerId, String customerName,                             String residentId, String customerType) throws CreateException | - | - | 컨테이너가 영속성을 관리하는 고객 정보 저장·조회 목적의 CMP 구현 맥락에서, 신규 고객 인스턴스를 생성할 때 필요한 기본 속성들을 초기화한다. 입력으로 받은 customerId(고객 식별자), customerName(고객명), residentId(주민등록번호), customerType(고객유형)을 각각 엔티티의 해당 속성에 반영하여 생성 직후의 영속 상태 변경 지점을 만든다. 또한 registrationDate(등록일자)를 현재 시스템 시간 기반의 일자로 설정해 신규 등록 시점을 기록한다. 생성 결과로는 CMP 생성 규약에 따라 null을 반환하며, 생성 과정에서 문제가 발생하면 생성 예외를 상위로 전달한다. |
| ejbPostCreate | public void ejbPostCreate(String customerId, String customerName,                               String residentId, String customerType) | - | - | 이 코드는 컨테이너가 영속성을 관리하는 고객 정보 저장·조회용 CMP 구성요소의 생성 이후 단계에서 호출되는 후처리 훅에 해당한다. 입력으로 customerId(고객식별자), customerName(고객명), residentId(주민등록번호), customerType(고객유형)을 전달받지만, 본문이 비어 있어 추가 초기화·검증·연관 데이터 설정 같은 후처리를 수행하지 않는다. 따라서 고객 생성 흐름의 일부로서 호출되기는 하나, 이 범위 내에서는 어떤 상태 변경이나 외부 자원 접근도 발생하지 않는다. |
| setEntityContext | public void setEntityContext(EntityContext ctx) | - | - | 고객 정보를 저장·조회하는 CMP 방식의 구현에서, 컨테이너가 전달하는 엔티티 실행 문맥을 내부에 보관하도록 설정한다. 전달받은 문맥 객체를 현재 인스턴스의 보관 필드에 그대로 대입해 이후 영속성/트랜잭션 관련 작업에서 사용할 수 있게 한다. 별도의 검증, 분기, 예외 처리 없이 문맥 참조를 갱신하는 단순한 상태 변경 동작만 수행한다. |
| unsetEntityContext | public void unsetEntityContext() | - | - | 이 코드는 컨테이너가 영속성을 관리하는 고객 정보 저장·조회 구성요소의 일부로, 컨테이너로부터 제공받아 보관하던 영속성/실행 문맥 참조를 명시적으로 해제한다. 내부에 유지하던 엔티티 처리 컨텍스트를 null로 만들어 이후 해당 컨텍스트를 통해 수행되는 접근이 더 이상 발생하지 않도록 한다. 결과적으로 컨텍스트의 연결 상태를 종료(초기화)하여 인스턴스의 내부 상태를 변경한다. |
| ejbActivate | public void ejbActivate() | - | - | 고객 정보를 컨테이너가 영속성으로 관리하는 CMP 구현 클래스에서, 인스턴스가 활성화되는 시점에 컨테이너가 호출하는 생명주기 콜백을 제공한다. 다만 본문이 비어 있어 활성화 시점에 추가 초기화, 리소스 재연결, 상태 복구 같은 작업을 수행하지 않는다. 그 결과 이 구간은 데이터 조회나 저장을 유발하지 않으며, 외부 구성/SQL/다른 구성요소와의 상호작용도 없다. |
| ejbPassivate | public void ejbPassivate() | - | - | 이 구현체는 컨테이너가 영속성을 관리하는 고객 정보 저장·조회용 CMP 빈이며, 인스턴스가 패시베이션될 때 호출되는 생명주기 콜백을 제공한다. 패시베이션 시점에는 보통 컨텍스트 참조 해제나 캐시/자원 정리 같은 준비 작업을 수행할 수 있다. 그러나 해당 범위의 구현은 비어 있어 어떤 자원 정리도 수행하지 않으며, 고객 데이터나 영속 상태를 변경하는 동작도 발생하지 않는다. |
| ejbLoad | public void ejbLoad() | - | - | 이 코드는 고객 정보를 저장·조회하는 CMP 방식의 엔티티 빈 구현 맥락에서, 영속 상태를 저장소에서 다시 적재하는 생명주기 훅을 제공한다. 구현 내용이 비어 있어, 실제 적재 동작은 컨테이너가 제공하는 기본 영속성 관리에 전적으로 위임된다. 따라서 이 구간에서는 고객 데이터의 조회·동기화에 해당하는 추가 로직(필드 매핑, 검증, 후처리 등)을 수행하지 않는다. |
| ejbStore | public void ejbStore() | - | - | 이 구성요소는 컨테이너가 영속성을 관리하는 고객 정보 저장·조회 책임을 전제로 하며, 이 구간은 저장 단계에서 호출되는 저장 훅을 제공한다. 구현 내용이 비어 있어, 고객 정보의 변경 사항을 직접 데이터 저장 로직으로 기록하지 않고 컨테이너 관리 영속성에 저장 처리를 위임한다. 따라서 애플리케이션 코드 관점에서는 명시적인 필드 반영, 검증, 예외 처리 없이 저장 동작을 ‘아무 것도 하지 않는’ 방식으로 통과시킨다. |
| ejbRemove | public void ejbRemove() throws RemoveException | - | - | 이 코드는 컨테이너가 영속성을 관리하며 고객 정보를 저장·조회하는 구성요소 안에서, 고객 정보가 제거(삭제)될 때 호출되는 생명주기 훅을 제공한다. 현재 구현은 본문이 비어 있어, 제거 시점에 추가 정리 작업, 연관 데이터 처리, 감사 로그 기록 등 어떤 부가 동작도 수행하지 않는다. 대신 제거 과정에서 발생할 수 있는 오류를 호출자/컨테이너로 전달할 수 있도록 예외 발생 가능성을 선언해 둔다. 결과적으로 실제 삭제 동작은 컨테이너의 기본 처리에 맡기고, 필요한 경우 이 지점에 삭제 전후의 보조 로직을 확장할 수 있는 형태로 남겨져 있다. |

#### 필드

| 이름 | 타입 | 수정자 | 요약 |
| --- | --- | --- | --- |
| entityContext | EntityContext | - | 컨테이너가 제공하는 엔티티 실행/라이프사이클 정보를 담는 컨텍스트로, 고객 CMP 엔티티 빈이 영속성 처리 및 콜백 수행 시 필요한 환경 객체를 보관한다. |

#### 구조 관계

| 방향 | 관계 | 대상 | 속성 |
| --- | --- | --- | --- |
| → | ASSOCIATION | EntityContext | source_member=unsetEntityContext |
| → | DEPENDENCY | EntityContext | source_member=setEntityContext, usage=parameter |

#### 호출 관계

| 방향 | 대상 | 호출코드 |
| --- | --- | --- |
| → | CustomerBean | 57:         setCustomerId(customerId); |
| → | CustomerBean | 58:         setCustomerName(customerName); |
| → | CustomerBean | 59:         setResidentId(residentId); |
| → | CustomerBean | 60:         setCustomerType(customerType); |
| → | CustomerBean | 61:         setRegistrationDate(new Date(System.currentTimeMillis())); |

#### 데이터 접근

| 대상 | 관계 | 근거 | 신뢰도 |
| --- | --- | --- | --- |
| - | - | - | - |

#### 요약 코드

```
없음
```

### CustomerLocal

#### 기본 정보

| 항목 | 값 |
| --- | --- |
| 이름 | CustomerLocal |
| 타입 | CLASS |
| FQN | com.banking.loan.entity.CustomerLocal |
| 패키지 | com.banking.loan.entity |
| 스테레오타입 | COMMAND/READMODEL |
| 파일 | - |
| 라인 | - |
| 토큰 | - |

#### 요약

> com.banking.loan.entity.CustomerLocal은 고객 엔티티 빈의 로컬 컴포넌트 인터페이스로, 고객 정보에 대한 CMP 필드 접근자(조회/설정) 계약을 정의한다. customerId, customerName(고객명), residentId(주민등록번호), customerType(고객유형), address(주소), phoneNumber(전화번호), email(이메일), annualIncome(연간소득), employerName(고용주명), creditGrade(신용등급), registrationDate(등록일) 등 고객 속성을 컨테이너 관리 영속성(CMP)을 통해 읽고 변경할 수 있도록 한다. 특히 등록일자 registrationDate(등록일자)를 Date 타입 값으로 설정하는 쓰기 동작을 제공해 고객 엔티티의 등록일자 상태 갱신을 인터페이스 수준에서 규정하며, 별도의 비즈니스 로직이나 검증은 포함하지 않는다.

#### 메서드

| 이름 | 시그니처 | 반환타입 | 수정자 | 요약 |
| --- | --- | --- | --- | --- |
| getCustomerId | String getCustomerId() | - | - | 이 코드는 고객 정보를 표현하는 로컬 컴포넌트 인터페이스에서 고객 정보에 대한 CMP 필드 접근자를 제공하기 위한 것이다. 그중 고객을 식별하는 값인 customerId를 문자열로 반환하는 조회용 접근자 역할을 한다. 입력 파라미터 없이 현재 고객 엔티티에 저장된 customerId 값을 읽어 외부에 제공하는 목적이며, 데이터의 생성·수정·삭제 같은 상태 변경은 수행하지 않는다. |
| getCustomerName | String getCustomerName() | - | - | 이 구성요소는 고객 정보에 대한 CMP 필드 접근자를 정의하는 로컬 컴포넌트 인터페이스의 일부이다. 여기서는 고객의 이름(customerName, 고객명)을 조회하기 위한 접근자 계약을 제공한다. 호출자는 이 계약을 통해 고객 엔티티에 저장된 고객명을 문자열로 읽어올 수 있다. 상태 변경이나 저장 동작 없이 고객명 값의 반환에 목적이 있다. |
| setCustomerName | void setCustomerName(String customerName) | - | - | 이 코드는 고객 정보에 대한 CMP 필드 접근자를 정의하는 로컬 컴포넌트 인터페이스의 일부로, 고객 엔티티의 customerName(고객명) 값을 변경하기 위한 설정 동작을 제공한다. 입력으로 전달된 customerName(고객명)을 고객 정보의 영속 상태에 반영하여 저장된 고객명을 수정하는 목적을 가진다. 반환값은 없으며, 조회가 아니라 고객명 상태를 갱신하는 변경(쓰기) 의도를 나타낸다. |
| getResidentId | String getResidentId() | - | - | 이 코드는 고객 정보에 대한 CMP 필드 접근자를 정의하는 로컬 컴포넌트 인터페이스의 일부로, 고객 엔티티가 보유한 residentId(주민등록번호) 값을 외부에서 읽을 수 있도록 한다. 호출자는 별도 입력 없이 문자열 형태의 식별값을 반환받아 고객 본인 식별/확인 등 후속 처리에 활용할 수 있다. 선언만 존재하며 내부 계산, 검증, 상태 변경 로직은 포함하지 않는다. |
| setResidentId | void setResidentId(String residentId) | - | - | 이 구성요소는 고객 정보에 대한 CMP 필드 접근자를 정의하는 로컬 컴포넌트 인터페이스이며, 고객 엔티티의 상태를 필드 단위로 갱신할 수 있도록 한다. 여기서는 residentId 값을 외부에서 전달받아 고객 정보에 반영(설정)하는 쓰기 작업을 선언한다. 구현체는 전달된 residentId를 고객 정보의 해당 필드에 저장해 이후 조회나 업무 처리에서 일관되게 사용될 수 있도록 한다. |
| getCustomerType | String getCustomerType() | - | - | 이 코드는 고객 정보에 대한 CMP 필드 접근자를 정의하는 로컬 컴포넌트 인터페이스의 일부로, 고객 엔티티가 보유한 고객 유형 값을 읽어오기 위한 조회용 접근자를 선언한다. 호출자는 이 접근자를 통해 고객의 분류/유형 정보를 문자열 형태로 획득할 수 있다. 구현 로직은 포함되지 않으며, 고객 유형 값 제공을 위한 계약만 정의한다. |
| setCustomerType | void setCustomerType(String customerType) | - | - | 고객 정보에 대한 CMP 필드 접근자를 제공하는 로컬 컴포넌트 인터페이스의 일부로, 고객의 유형을 나타내는 customerType(고객유형) 값을 외부에서 전달받아 갱신하도록 정의한다. 반환값 없이 문자열로 전달된 고객유형을 해당 고객 엔티티의 상태로 설정하는 쓰기 동작에 해당한다. 구현체(컨테이너 관리 퍼시스턴스)가 이 변경을 영속 상태에 반영할 수 있도록, 고객유형 변경 지점을 인터페이스 수준에서 명확히 노출한다. |
| getAddress | String getAddress() | - | - | 이 코드는 고객 정보에 대한 CMP 필드 접근자를 정의하는 로컬 컴포넌트 인터페이스의 일부로, 고객의 address(주소) 값을 조회하기 위한 계약을 선언한다. 호출자는 별도의 입력 없이 현재 고객 레코드에 저장된 주소 문자열을 반환받아 화면 표시나 후속 처리에 사용할 수 있다. 인터페이스 선언만 존재하므로 여기서 값의 생성·검증·저장 같은 상태 변경은 수행하지 않으며, 구현체가 실제 저장소에서 address를 읽어오는 역할을 맡는다. |
| setAddress | void setAddress(String address) | - | - | 이 코드는 고객 정보에 대한 CMP 필드 접근자를 제공하는 로컬 컴포넌트 인터페이스 맥락에서, 고객의 address(주소) 값을 변경하기 위한 설정 동작을 선언한다. 외부에서 전달된 문자열 주소 값을 고객 정보의 address 필드에 반영하도록 계약을 정의하여, 구현체가 고객 주소 정보를 갱신할 수 있게 한다. 반환값이 없으므로 처리 결과를 돌려주기보다는 주소 상태를 변경하는 목적이 중심이다. |
| getPhoneNumber | String getPhoneNumber() | - | - | 이 코드는 고객 정보에 대한 CMP 필드 접근자를 정의하는 로컬 컴포넌트 인터페이스의 일부로, 고객의 연락처 데이터 중 phoneNumber(전화번호)를 읽기 위해 사용된다. 호출자는 별도의 입력 없이 고객 엔티티에 저장된 phoneNumber 값을 문자열로 반환받는다. 데이터의 등록·수정·삭제 같은 상태 변경은 수행하지 않고, 고객의 현재 전화번호 값을 조회하는 목적에 집중한다. |
| setPhoneNumber | void setPhoneNumber(String phoneNumber) | - | - | 이 코드는 고객 정보에 대한 CMP 필드 접근자를 정의하는 로컬 컴포넌트 인터페이스의 일부로, 고객의 연락처 정보를 갱신하기 위한 쓰기 동작을 제공한다. 입력으로 전달된 phoneNumber(전화번호) 값을 고객 엔티티의 phoneNumber 필드에 설정하여 이후 저장/영속화 대상 데이터로 반영되도록 한다. 구현은 인터페이스 밖에서 제공되며, 이 선언 자체는 전화번호 값의 검증이나 형식 정규화 같은 추가 규칙을 포함하지 않는다. |
| getEmail | String getEmail() | - | - | 이 컴포넌트 인터페이스는 고객 정보에 대한 CMP 필드 접근자를 정의하는 목적을 가지며, 이 범위는 그중 이메일(email) 값을 읽기 위해 제공되는 접근자 선언이다. 호출자 입장에서는 저장된 고객 레코드에 매핑된 email 값을 문자열로 반환받아 화면 표시, 연락처 확인, 알림 발송 대상 식별 등의 읽기 용도로 사용할 수 있다. 구현은 인터페이스 수준에서 선언만 되어 있으며, 값의 조회·매핑 책임은 컨테이너/퍼시스턴스 계층에 위임된다. |
| setEmail | void setEmail(String email) | - | - | 이 코드는 고객 엔티티 빈의 로컬 컴포넌트 인터페이스에서 고객 정보에 대한 CMP 필드 접근자 중 하나로, email(이메일) 값을 변경하기 위한 쓰기 계약을 정의한다. 호출자는 문자열 형태의 이메일 값을 전달하며, 해당 값은 고객 정보의 email 필드에 반영되는 것을 전제로 한다. 선언부만 존재하므로 실제 저장/반영 시점과 영속화 동작은 구현체 및 컨테이너의 CMP 처리에 의해 수행된다. |
| getAnnualIncome | BigDecimal getAnnualIncome() | - | - | 고객 정보에 대한 CMP 필드 접근자를 정의하는 로컬 컴포넌트 인터페이스에서, 고객의 annualIncome(연간소득) 값을 조회하기 위한 읽기 전용 계약을 제공한다. 호출 시 저장된 고객 레코드의 annualIncome 값을 정밀한 수치 타입으로 반환하여, 소득 기반의 화면 표시나 심사/분석 로직에서 재사용할 수 있게 한다. 이 범위에는 값 계산, 검증, 저장/수정 같은 상태 변경 로직이 포함되지 않으며 단순 조회 목적에 초점이 있다. |
| setAnnualIncome | void setAnnualIncome(BigDecimal annualIncome) | - | - | 이 컴포넌트 인터페이스는 고객 정보에 대한 CMP 필드 접근자를 정의하며, 고객 엔티티의 상태를 외부에서 조작할 수 있도록 한다. 이 범위의 동작은 고객의 annualIncome(연간소득) 값을 입력받아 해당 고객 정보에 반영(갱신)하는 것을 목적로 한다. 반환값이 없으므로, 처리 결과는 연간소득 필드의 값 변경이라는 상태 변화로 나타난다. |
| getEmployerName | String getEmployerName() | - | - | 고객 정보에 대한 CMP 필드 접근자를 정의하는 로컬 컴포넌트 인터페이스의 일부로, 고객 레코드에 저장된 employerName(고용주명) 값을 조회하기 위한 읽기 전용 접근 지점을 제공한다. 호출자는 이 반환값을 통해 고객의 고용주 이름을 화면 표시, 조회 결과 조합, 또는 후속 검증 로직의 입력값으로 사용할 수 있다. 메서드 시그니처만 존재하며 입력 파라미터, 내부 계산, 상태 변경이나 외부 자원 접근은 포함하지 않는다. |
| setEmployerName | void setEmployerName(String employerName) | - | - | 고객 정보에 대한 CMP 필드 접근자를 정의하는 로컬 컴포넌트 인터페이스의 일부로, 고객의 employerName(고용주명) 값을 갱신하기 위한 설정 기능을 선언한다. 문자열로 전달된 고용주명 값을 고객 정보의 해당 필드에 반영하도록 계약을 제공하며, 구현체에서는 이 값이 지속 저장되는 상태 변경으로 이어진다. 본 범위는 인터페이스 메서드 선언만 포함하므로 조건 분기, 반복, 예외 처리나 외부 자원 참조는 없다. |
| getCreditGrade | String getCreditGrade() | - | - | 이 코드는 고객 정보에 대한 CMP 필드 접근자를 정의하는 로컬 컴포넌트 인터페이스의 일부로, 고객의 creditGrade(신용등급) 값을 조회하기 위한 계약을 제공한다. 호출자는 이 연산을 통해 고객에 저장된 신용등급을 문자열 형태로 받아 고객 신용 수준을 확인하거나 후속 판단 로직에 활용할 수 있다. 값을 변경하거나 저장을 확정하는 동작은 포함하지 않고, 특정 필드 값을 읽어오는 목적에 집중한다. |
| setCreditGrade | void setCreditGrade(String creditGrade) | - | - | 이 코드는 고객 정보에 대한 CMP 필드 접근자를 제공하는 로컬 컴포넌트 인터페이스의 일부로, 고객의 creditGrade(신용등급) 값을 갱신하기 위한 쓰기 동작을 정의한다. 외부에서 전달된 신용등급 문자열을 고객 엔티티의 creditGrade 필드에 반영하도록 계약(시그니처)만 선언하며, 구현체에서 실제 저장/반영이 수행되는 것을 전제로 한다. 반환값은 없고, 신용등급 값 변경 자체가 목적이므로 고객 정보의 상태 변경에 해당한다. |
| getRegistrationDate | Date getRegistrationDate() | - | - | 이 구성요소는 고객 정보에 대한 CMP 필드 접근자를 정의하는 로컬 컴포넌트 인터페이스이며, 그중 고객의 registrationDate(등록일)를 제공하는 읽기 전용 접근자를 선언한다. 호출자는 고객 엔티티에 저장된 등록일 값을 Date 형태로 조회하여 고객의 가입/등록 시점을 확인하는 데 사용한다. 이 선언은 값의 조회만을 목적으로 하며, 고객 정보의 생성·수정·삭제 같은 상태 변경 동작은 포함하지 않는다. |
| setRegistrationDate | void setRegistrationDate(Date registrationDate) | - | - | 이 구성요소는 고객 정보에 대한 CMP 필드 접근자를 정의하며, 이 범위는 고객의 registrationDate(등록일자)를 설정하기 위한 쓰기 동작을 제공한다. 외부에서 전달된 날짜 값을 고객 정보의 등록일자 필드에 반영하도록 계약(인터페이스) 수준에서 규정한다. 이를 통해 고객 엔티티의 등록일자 상태가 갱신되며, 값은 Date 타입의 날짜/시간 정보로 표현된다. |

#### 필드

| 이름 | 타입 | 수정자 | 요약 |
| --- | --- | --- | --- |
| - | - | - | - |

#### 구조 관계

| 방향 | 관계 | 대상 | 속성 |
| --- | --- | --- | --- |
| ← | DEPENDENCY | CustomerLocalHome | source_member=findByPrimaryKey, usage=return |
| ← | DEPENDENCY | CustomerLocalHome | source_member=create, usage=return |

#### 호출 관계

| 방향 | 대상 | 호출코드 |
| --- | --- | --- |
| - | - | - |

#### 데이터 접근

| 대상 | 관계 | 근거 | 신뢰도 |
| --- | --- | --- | --- |
| - | - | - | - |

#### 요약 코드

```
없음
```

### CustomerLocalHome

#### 기본 정보

| 항목 | 값 |
| --- | --- |
| 이름 | CustomerLocalHome |
| 타입 | CLASS |
| FQN | com.banking.loan.entity.CustomerLocalHome |
| 패키지 | com.banking.loan.entity |
| 스테레오타입 | COMMAND/READMODEL |
| 파일 | - |
| 라인 | - |
| 토큰 | - |

#### 요약

> com.banking.loan.entity.CustomerLocalHome은 고객 엔티티 빈의 로컬 홈 인터페이스로, 고객의 생성 및 조회를 위한 메서드 계약을 정의한다. customerId, customerName, residentId, customerType(고객 유형)으로 신규 고객을 생성하며, 생성 조건 미충족이나 실패는 생성 실패 예외로 전달한다. 또한 customerId로 단건 조회, customerName 또는 customerType으로 조건 조회, 전체 목록 조회를 제공하고, 대상 부재·규칙 미충족 등 조회 실패는 FinderException 등 조회 실패 예외로 호출자에게 알린다.

#### 메서드

| 이름 | 시그니처 | 반환타입 | 수정자 | 요약 |
| --- | --- | --- | --- | --- |
| create | CustomerLocal create(String customerId, String customerName,                          String residentId, String customerType) throws CreateException | - | - | 이 구성요소는 고객 엔티티를 생성·조회하기 위한 계약을 정의하며, 이 선언은 그중 고객 정보를 신규로 등록하는 작업을 담당한다. 입력으로 customerId(고객 식별자), customerName(고객명), residentId(주민/식별번호), customerType(고객유형)을 받아 새 고객 레코드에 해당하는 엔티티 인스턴스를 생성해 반환하도록 요구한다. 생성 과정에서 필요한 조건을 만족하지 못하거나 생성이 실패하면 생성 실패 예외를 통해 호출자에게 오류를 전달하도록 정의되어 있다. 반환되는 값은 생성된 고객 엔티티의 로컬 접근 인터페이스로, 이후 고객 정보의 CMP 필드 접근에 사용될 수 있다. |
| findByPrimaryKey | CustomerLocal findByPrimaryKey(String customerId) throws FinderException | - | - | 이 코드는 고객 엔티티 빈을 생성·조회하기 위한 로컬 홈 인터페이스의 일부로, 고객을 식별하는 값(고객 식별자, customerId)을 기준으로 고객 정보를 조회하는 계약을 정의한다. 호출자는 고객 식별자를 전달하면, 해당 식별자에 대응하는 고객의 로컬 컴포넌트 인터페이스를 돌려받아 고객 정보의 CMP 필드 접근자를 통해 데이터를 읽을 수 있다. 지정한 고객 식별자에 해당하는 데이터가 없거나 조회 과정에서 문제가 발생하면 조회 실패 예외를 통해 오류를 상위로 전달한다. |
| findAll | Collection findAll() throws FinderException | - | - | 이 인터페이스는 고객 정보를 생성하고 조회하기 위한 로컬 홈 수준의 기능을 정의하며, 이 선언은 저장된 고객 전체를 한 번에 조회하는 용도를 가진다. 호출자는 별도 입력값 없이 전체 고객 목록을 요청하고, 결과로 여러 고객을 나타내는 객체들의 집합을 받는다. 조회 과정에서 고객 검색(조회) 단계에서 오류가 발생할 수 있음을 명시적으로 예외로 알리며, 호출자는 이를 처리해야 한다. |
| findByCustomerName | Collection findByCustomerName(String customerName) throws FinderException | - | - | 이 구성요소는 고객의 생성 및 조회를 위한 로컬 홈 계약을 제공하며, 그중 고객 조회 기능의 한 형태를 정의한다. 입력으로 전달된 고객명 값을 기준으로 동일한 이름을 가진 고객들을 검색해 결과 목록을 반환하도록 의도되어 있다. 조회 과정에서 대상 식별 실패 또는 조회 처리 오류가 발생하면 조회 관련 예외를 호출자에게 전달하도록 선언되어 있다. |
| findByCustomerType | Collection findByCustomerType(String customerType) throws FinderException | - | - | 고객 엔티티 빈의 로컬 홈 인터페이스에서, 고객을 생성·조회하기 위한 조회 기능 중 하나로 특정 고객 유형 값에 해당하는 고객들을 찾는 계약을 정의한다. 입력으로 고객 유형을 나타내는 문자열을 받아, 해당 조건에 부합하는 고객 집합을 컬렉션 형태로 반환하도록 되어 있다. 조회 과정에서 대상이 존재하지 않거나 조회 규칙을 만족하지 못하는 등 검색 실패 상황은 FinderException으로 호출자에게 전달한다. 이 선언은 인터페이스 수준의 시그니처만 제공하며, 실제 조회 조건 적용과 데이터 접근 방식은 구현체에 위임된다. |

#### 필드

| 이름 | 타입 | 수정자 | 요약 |
| --- | --- | --- | --- |
| - | - | - | - |

#### 구조 관계

| 방향 | 관계 | 대상 | 속성 |
| --- | --- | --- | --- |
| → | DEPENDENCY | CustomerLocal | source_member=findByPrimaryKey, usage=return |
| → | DEPENDENCY | CustomerLocal | source_member=create, usage=return |
| ← | DEPENDENCY | LoanProcessSessionBean | source_member=getCustomerHome, usage=return |
| ← | DEPENDENCY | LoanProcessSessionBean | source_member=initializeProcess, usage=local_var |

#### 호출 관계

| 방향 | 대상 | 호출코드 |
| --- | --- | --- |
| ← | LoanProcessSessionBean | - |

#### 데이터 접근

| 대상 | 관계 | 근거 | 신뢰도 |
| --- | --- | --- | --- |
| CustomerLocal | REFER_TO | - | 1.0 |
| CustomerLocal | REFER_TO | - | 1.0 |

#### 요약 코드

```
없음
```

### DelinquencyBean

#### 기본 정보

| 항목 | 값 |
| --- | --- |
| 이름 | DelinquencyBean |
| 타입 | CLASS |
| FQN | com.banking.loan.entity.DelinquencyBean |
| 패키지 | com.banking.loan.entity |
| 스테레오타입 | COMMAND/READMODEL |
| 파일 | - |
| 라인 | - |
| 토큰 | - |

#### 요약

> com.banking.loan.entity.DelinquencyBean은 컨테이너가 영속성을 관리하는 CMP 방식의 연체 엔티티 빈으로, 연체 정보를 저장·조회하고 delinquencyId, ledgerId, customerId, delinquencyStartDate, delinquencyAmount, delinquencyDays, delinquencyGrade, penaltyRate, penaltyAmount, status, resolutionDate 같은 속성을 영속 상태로 유지·갱신한다. 컨테이너가 주입하는 엔티티 컨텍스트(entityContext)를 보관해 생명주기 및 영속성 관리와 연동된다. 신규 생성 시 delinquencyDays=0, delinquencyGrade="GRADE_1", status="ACTIVE"를 기본값으로 두고, 연체일수 갱신 시 delinquencyDays < 30이면 "GRADE_1", 30 이상 60 미만이면 "GRADE_2", 60 이상 90 미만이면 "GRADE_3", 90 이상이면 "GRADE_4"로 등급을 산정하며 delinquencyAmount×penaltyRate÷365(소수점 2자리, HALF_UP)로 일 단위 패널티를 계산한 뒤 delinquencyDays를 곱해 penaltyAmount를 업데이트한다. 연체 해소 처리에서는 status가 "ACTIVE" → "RESOLVED"로 전환되고 resolutionDate를 기록하며, 활성화/패시베이션/적재/저장/제거 콜백은 비어 있어 컨테이너 기본 동작에 의존한다.

#### 메서드

| 이름 | 시그니처 | 반환타입 | 수정자 | 요약 |
| --- | --- | --- | --- | --- |
| getDelinquencyId | - | - | - | 이 코드는 컨테이너가 영속성을 관리하며 연체 정보를 저장·조회하는 구성요소에서, 연체 정보의 식별자 값을 문자열로 제공하기 위한 추상 접근 계약을 정의한다. 실제 값의 조회 방식(필드 접근, 영속 컨텍스트 로딩 등)은 구현체에 위임되며, 호출자는 이를 통해 연체 레코드를 식별하는 delinquencyId 값을 일관된 방식으로 얻을 수 있다. 상태를 변경하지 않고 식별자 값을 반환하는 조회 성격의 동작만을 표현한다. |
| setDelinquencyId | - | - | - | 이 클래스는 컨테이너가 영속성을 관리하는 연체 정보를 저장·조회하는 빈 구현을 전제로 하며, 그 안에서 연체 건을 식별하는 delinquencyId 값을 설정하는 동작을 추상적으로 규정한다. 호출자는 문자열로 전달된 연체 식별자를 해당 연체 정보의 식별자 속성(delinquencyId)에 반영하도록 구현체에 요구한다. 구현체는 이 값 설정을 통해 이후 영속성 컨텍스트에서 특정 연체 레코드를 식별하거나 갱신 대상으로 삼는 흐름을 가능하게 한다. |
| getLedgerId | - | - | - | 이 코드는 컨테이너가 영속성을 관리하는 연체 정보 저장·조회 구성요소에서, 연체 정보가 속한 원장을 식별하는 ledgerId(원장 식별자)를 제공하기 위한 조회용 계약을 정의한다. 반환값은 문자열 형태의 원장 식별자이며, 호출자는 이를 통해 연체 레코드를 특정 원장과 연계해 식별·분류할 수 있다. 구현이 비어 있는 추상 선언이므로, 실제 원장 식별자 조회 방식(필드 매핑/계산/외부 조회 등)은 하위 구현에서 결정된다. |
| setLedgerId | - | - | - | 이 코드는 컨테이너가 영속성을 관리하는 연체 정보 저장·조회용 구성요소에서, 연체 데이터가 속할 원장 식별자(ledgerId)를 변경하기 위한 설정 동작의 계약을 정의한다. 입력으로 전달된 ledgerId 값을 해당 연체 정보의 속성으로 반영하도록 강제하며, 구체적인 저장 방식이나 검증 규칙은 구현체에 위임된다. 결과적으로 연체 정보가 어떤 원장에 귀속되는지를 갱신할 수 있도록 하는 쓰기 성격의 인터페이스 역할을 한다. |
| getCustomerId | - | - | - | 연체 정보를 저장·조회하는 영속 객체에서, 연체 레코드에 연관된 customerId(고객 식별자)를 문자열로 제공하기 위한 조회용 접근자 선언이다. 메서드 본문이 없는 추상 선언이므로, 실제 값의 로딩/제공은 컨테이너가 관리하는 영속성 메커니즘(CMP)에 의해 수행되는 것을 전제로 한다. 호출자는 이 값을 통해 특정 고객의 연체 정보를 식별하거나 연관 데이터를 조회하는 키로 활용할 수 있다. |
| setCustomerId | - | - | - | 이 코드는 컨테이너가 영속성을 관리하며 연체 정보를 저장·조회하는 엔티티 빈 구현에서, 연체 정보에 포함되는 customerId(고객식별자)를 설정하기 위한 동작을 정의한다. 입력으로 전달된 고객식별자를 엔티티의 상태로 반영하는 목적이며, 실제 저장/갱신 방식은 구현체에 위임된다. 즉, 연체 정보 레코드가 어떤 고객에 속하는지 식별하는 값을 변경(설정)하는 계약을 제공한다. |
| getDelinquencyStartDate | - | - | - | 이 코드는 컨테이너가 영속성을 관리하는 연체 정보 저장·조회 구성요소에서, 연체 정보 중 연체 시작일을 조회하기 위한 추상 접근 지점을 정의한다. 구현은 하위 구현체 또는 CMP 컨테이너가 제공하며, 호출자는 연체 시작일 값을 Date 형태로 받아 연체 기간 산정 등 후속 처리를 수행할 수 있다. 자체적으로 상태를 변경하거나 추가 로직을 수행하지 않고, 연체 시작일 값의 제공(조회)에 목적이 있다. |
| setDelinquencyStartDate | - | - | - | 이 구성요소는 컨테이너가 영속성을 관리하는 연체 정보의 저장·조회 책임을 가지며, 그중 연체 정보의 시작 시점을 나타내는 delinquencyStartDate(연체 시작일)를 변경하기 위한 설정 지점을 제공한다. 입력으로 전달된 날짜 값을 연체 시작일 속성에 반영하도록 정의되어, 이후 연체 정보가 저장되거나 갱신될 때 해당 시작일이 상태로 포함될 수 있게 한다. 구현이 비어 있는 추상 선언이므로, 실제 값 반영 방식과 저장 시점의 연계는 구체 구현에서 결정된다. |
| getDelinquencyAmount | - | - | - | 이 구현 클래스는 컨테이너가 영속성을 관리하는 연체 정보 저장·조회 책임 범위 안에서, 연체 정보 중 ‘연체 금액’을 제공하기 위한 반환 규약을 선언한다. 구현체는 연체 금액을 정밀한 금액 표현이 가능한 BigDecimal 형태로 반환해야 하며, 금액 계산/표현에서의 오차를 줄이려는 의도를 담는다. 본 범위에는 실제 조회 로직이나 저장소 접근은 포함되지 않고, 연체 금액을 어떻게 산출·보관하든 외부에는 금액 값만 노출하도록 인터페이스 역할을 한다. |
| setDelinquencyAmount | - | - | - | 이 코드는 컨테이너가 영속성을 관리하는 연체 정보 저장·조회 구성요소에서, 연체금액(delinquencyAmount)을 변경하기 위한 설정 동작을 정의한다. 입력으로 받은 금액 값을 연체 정보의 연체금액 속성에 반영해 이후 영속 저장 시 해당 값이 기록되도록 하는 목적이다. 다만 구현은 추상으로 선언되어 있어, 실제 값 대입 및 영속성 반영 방식은 구체 구현에서 결정된다. |
| getDelinquencyDays | - | - | - | 이 구성요소는 컨테이너가 영속성을 관리하는 연체 정보 저장·조회 목적의 CMP 기반 엔티티 빈 구현 맥락에 속한다. 여기서는 연체 상태를 나타내는 핵심 값인 연체일수(일 단위)를 정수로 조회해 제공하는 동작을 정의한다. 구현이 본문 없이 추상으로 선언되어 있어, 실제 연체일수의 계산/매핑 방식은 영속성 설정이나 구체 구현에 의해 결정된다. 상태 변경이나 저장 동작 없이 값 조회에 초점이 맞춰져 있다. |
| setDelinquencyDays | - | - | - | 이 클래스는 컨테이너가 영속성을 관리하는 연체 정보 저장·조회 구성요소이며, 그중 연체일수(delinquencyDays)를 변경하기 위한 동작을 정의한다. 입력으로 받은 정수 값을 연체일수(delinquencyDays)에 반영하도록 하는 추상 계약만 제공하고, 실제 저장 방식과 검증 규칙은 구현체에 위임한다. 이 설정은 연체 정보의 상태를 갱신하는 목적이므로 이후 영속화 시점에 반영될 수 있는 변경 작업에 해당한다. |
| getDelinquencyGrade | - | - | - | 이 코드는 컨테이너가 영속성을 관리하는 연체 정보 저장·조회 구성요소의 일부로, 저장된 연체 정보를 외부에서 읽어갈 수 있도록 값을 제공하는 역할을 한다. 연체 수준을 나타내는 ‘연체 등급’을 문자열로 반환하도록 정의되어 있으며, 구체적인 반환 방식은 구현체(또는 컨테이너/서브클래스)에 의해 결정된다. 선언만 존재하는 추상 형태이므로 이 범위 자체에서는 계산, 검증, 저장 같은 부수 효과가 발생하지 않는다. |
| setDelinquencyGrade | - | - | - | 이 구성요소는 컨테이너가 영속성을 관리하는 연체 정보 저장·조회 대상이며, 연체 관련 속성 값을 유지하도록 설계되어 있다. 이 구간은 연체 등급(delinquencyGrade)을 외부에서 전달받아 엔티티의 해당 값을 변경하는 동작을 정의한다. 구현은 추상화되어 있어 실제로 값이 어떻게 저장·반영되는지는 하위 구현에 위임되지만, 목적은 연체 등급의 갱신(상태 변경)을 가능하게 하는 것이다. |
| getPenaltyRate | - | - | - | 이 코드는 컨테이너가 영속성을 관리하는 연체 정보 저장·조회 구성요소에서, 연체에 대한 페널티(가산) 비율 값을 제공하기 위한 조회용 계약을 정의한다. 반환값은 고정소수점 기반의 수치 타입으로, 비율 계산 및 금액 산정에 사용할 정밀한 값을 외부에 노출하는 목적이다. 구현은 제공되지 않으며, 실제 페널티 비율 산정 규칙과 값의 출처(저장된 연체 정보 또는 계산 로직)는 하위 구현에서 결정된다. |
| setPenaltyRate | - | - | - | 이 구성요소는 컨테이너가 영속성을 관리하는 연체 정보 저장·조회 목적의 구현체로서, 연체 관련 속성들을 상태로 보관한다. 이 동작은 penaltyRate 값을 입력으로 받아 연체 정보의 penaltyRate(패널티율/연체 가산율) 속성을 설정하도록 강제하는 추상 선언이다. 실제 저장 방식이나 유효성 검증 규칙은 여기에는 없고, 구체 구현에서 영속 상태에 반영되도록 위임된다. 결과적으로 연체 정보의 상태를 변경하는 쓰기 동작을 정의한다. |
| getPenaltyAmount | - | - | - | 이 코드는 연체 정보를 저장·조회하는 영속성 관리 대상 컴포넌트에서, 연체에 따른 페널티 금액을 조회하기 위한 추상 조회 계약을 정의한다. 호출자는 이 계약을 통해 연체 페널티 금액을 임의 정밀도의 금액 타입으로 받아 후속 계산이나 화면/전문 출력에 사용할 수 있다. 구현은 컨테이너 관리 영속성 매핑에 의해 실제 저장소의 값과 연결되며, 본 선언 자체는 데이터 변경이나 부수효과를 발생시키지 않는다. |
| setPenaltyAmount | - | - | - | 이 클래스는 컨테이너가 영속성을 관리하는 연체 정보 저장·조회 목적의 구현체이며, 여기서는 연체 정보의 penaltyAmount(벌금/패널티 금액)를 변경하기 위한 설정 계약을 정의한다. 입력으로 받은 금액 값을 연체 정보에 반영하도록 요구하지만, 추상 선언이므로 실제로 어떤 필드에 어떻게 저장·검증하는지는 구현체에서 결정된다. 결과적으로 연체 정보의 상태(금액 값)를 바꾸는 쓰기 성격의 동작을 나타낸다. |
| getStatus | - | - | - | 이 클래스는 컨테이너가 영속성을 관리하는 연체 정보 저장·조회 목적의 엔티티 빈 구현을 전제로 하며, 그 안에서 연체 상태를 나타내는 값을 외부에 제공하기 위한 조회용 계약을 정의한다. 호출자는 문자열 형태의 상태 값을 얻기 위해 이 추상 연산을 사용하며, 실제 상태 값이 무엇인지는 하위 구현에서 결정된다. 입력은 없고 반환값만 존재하므로, 상태를 변경하거나 저장을 수행하지 않고 현재 상태 표현을 읽어오는 용도로만 사용된다. |
| setStatus | - | - | - | 이 코드는 컨테이너가 영속성을 관리하는 연체 정보 저장·조회 구성요소 안에서, 연체 정보의 status(상태) 값을 변경하기 위한 설정 동작의 계약을 정의한다. 호출자는 상태를 나타내는 문자열을 전달하며, 구현체는 이를 연체 정보의 상태 속성에 반영해 이후 영속성 변경 감지 및 저장 대상이 되도록 한다. 본문이 없는 추상 선언이므로 실제 상태 반영 방식(필드 갱신, 검증, 상태 전이 규칙 적용 등)은 구현체에 위임된다. |
| getResolutionDate | - | - | - | 이 코드는 컨테이너가 영속성을 관리하는 연체 정보 저장·조회 기능의 일부로, 연체 건의 해소일(해결된 날짜)을 제공하기 위한 조회 지점을 정의한다. 반환값은 날짜 타입이며, 호출자는 이를 통해 해당 연체가 언제 해소(정리)되었는지 확인할 수 있다. 구현이 본문에 없으므로 실제 값의 조회·산출 방식은 하위 구현에서 영속 상태를 기반으로 결정되며, 이 선언 자체는 상태 변경 없이 값 제공에 목적이 있다. |
| setResolutionDate | - | - | - | 이 코드는 컨테이너가 영속성을 관리하는 연체 정보의 저장·조회 책임을 가진 구성요소에서, 연체가 해소된 날짜(resolutionDate)를 변경하기 위한 설정 동작을 정의한다. 입력으로 받은 날짜 값을 연체 정보의 해소일로 반영하여, 이후 영속 상태에 저장될 값으로 취급되도록 한다. 구현이 추상으로 선언되어 있어 실제 값 반영 및 영속화 연계는 컨테이너가 제공하는 구현을 통해 처리되는 것을 전제로 한다. |
| updateDelinquencyDays | public void updateDelinquencyDays(int days) | - | - | 컨테이너가 영속성을 관리하는 연체 정보 저장·조회 구성요소에서, 입력된 delinquencyDays(연체일수)를 반영하고 이에 따른 연체 상태 값을 갱신한다. 연체일수가 30 미만이면 delinquencyGrade를 "GRADE_1", 30 이상 60 미만이면 "GRADE_2", 60 이상 90 미만이면 "GRADE_3", 90 이상이면 "GRADE_4"로 설정한다. 이어서 delinquencyAmount(연체 금액)에 penaltyRate(패널티 비율)를 곱한 뒤 365로 나누어(소수점 2자리, HALF_UP 반올림) 일 단위 패널티 금액을 계산한다. 계산된 일 단위 패널티 금액에 연체일수를 곱한 값을 penaltyAmount(벌금/패널티 금액)로 설정해 연체 정보의 금액 상태를 업데이트한다. |
| resolve | public void resolve(Date resolutionDate) | - | - | 컨테이너가 영속성을 관리하는 연체 정보 저장·조회 구성요소 안에서, 연체가 해소되었음을 도메인 상태로 확정하기 위한 변경을 수행한다. 먼저 status(상태) 값을 문자열 "RESOLVED"로 설정하여 연체 상태가 해소됨으로 전이되었음을 명시한다. 이어서 입력으로 받은 resolutionDate(해소일) 값을 resolutionDate 속성에 반영해 해소 시점을 기록한다. 이렇게 갱신된 status와 resolutionDate는 컨테이너의 변경 감지 대상이 되어 이후 영속 상태에 저장될 값으로 취급된다. |
| ejbCreate | public String ejbCreate(String delinquencyId, String ledgerId, String customerId,                             Date delinquencyStartDate, BigDecimal delinquencyAmount,                             BigDecimal penaltyRate) throws CreateException | - | - | 컨테이너가 영속성을 관리하는 연체 정보 레코드를 신규로 생성하기 위해, 외부에서 전달된 delinquencyId(연체 식별자), ledgerId(원장 식별자), customerId(고객 식별자), delinquencyStartDate(연체 시작일), delinquencyAmount(연체금액), penaltyRate(패널티율)를 엔티티 상태로 확정 설정한다. 생성 직후 초기 상태를 정규화하기 위해 delinquencyDays(연체일수)를 0으로, delinquencyGrade(연체등급)를 "GRADE_1"로, status(상태)를 "ACTIVE"로 기본값 설정한다. CMP 생성 규약에 따라 생성 결과로 null을 반환하며, 실제 영속 반영은 컨테이너의 관리 하에 이후 진행될 수 있도록 초기 상태를 갖춘다. |
| ejbPostCreate | public void ejbPostCreate(String delinquencyId, String ledgerId, String customerId,                               Date delinquencyStartDate, BigDecimal delinquencyAmount,                               BigDecimal penaltyRate) | - | - | 컨테이너가 영속성을 관리하는 연체 정보 저장·조회용 구성요소에서, 생성 직후 후처리를 수행하기 위한 생명주기 훅으로 정의된 구간이다. 입력으로 delinquencyId, ledgerId, customerId, delinquencyStartDate, delinquencyAmount, penaltyRate를 받지만, 본문이 비어 있어 추가적인 검증·보정·연관 설정·상태 변경을 수행하지 않는다. 따라서 생성 흐름에서 필요한 데이터 확정이나 파생값 계산은 다른 단계(예: 생성 시점)에서 처리되도록 의도되었거나, 현재는 확장 포인트로만 남겨진 형태이다. |
| setEntityContext | public void setEntityContext(EntityContext ctx) | - | - | 이 클래스는 컨테이너가 영속성을 관리하는 연체 정보용 CMP 엔티티 빈 구현으로서, 저장·조회 과정에서 필요한 실행 컨텍스트를 유지한다. 이 코드는 외부에서 전달된 엔티티 실행 컨텍스트를 받아 인스턴스에 보관해, 이후 컨테이너 주도 생명주기/영속성 처리에서 해당 컨텍스트를 사용할 수 있게 한다. 데이터베이스 접근이나 연체 정보의 값 변경 로직은 포함하지 않고, 컨테이너 연동을 위한 참조 설정만 수행한다. |
| unsetEntityContext | public void unsetEntityContext() | - | - | 이 코드는 컨테이너가 영속성을 관리하며 연체 정보를 저장·조회하는 CMP 엔티티 빈 구현에서, 컨테이너가 주입해 둔 실행 컨텍스트 참조를 해제하는 역할을 한다. 빈 생명주기 종료나 컨텍스트 교체 시점에 내부에 보관하던 컨텍스트를 null로 만들어 더 이상 사용되지 않도록 정리한다. 이를 통해 이전 요청/트랜잭션과 연결된 컨텍스트가 남아 오동작하거나 불필요하게 참조가 유지되는 상황을 방지한다. 외부 저장소 접근이나 추가 연산 없이, 내부 상태(컨텍스트 참조)만 변경한다. |
| ejbActivate | public void ejbActivate() | - | - | 이 코드는 컨테이너가 영속성을 관리하는 연체 정보 저장·조회용 CMP 기반 엔티티 빈의 생명주기 단계 중 ‘활성화’ 시점에 호출되도록 마련된 콜백이다. 다만 현재 구현은 본문이 비어 있어, 활성화 시점에 캐시 복원, 상태 초기화, 리소스 재연결 같은 추가 동작을 수행하지 않는다. 따라서 이 범위는 데이터 조회나 변경을 직접 수행하지 않고, 컨테이너의 호출을 수용하는 빈 껍데기 역할만 한다. |
| ejbPassivate | public void ejbPassivate() | - | - | 이 코드는 컨테이너가 영속성을 관리하며 연체 정보를 저장·조회하는 CMP 기반 엔티티 빈 구현 클래스의 생명주기 단계 중, 인스턴스가 패시베이션될 때 호출되는 훅을 정의한다. 그러나 본문이 비어 있어 패시베이션 시점에 엔티티 상태 정리, 컨텍스트 해제, 캐시/자원 반납 등의 추가 처리를 수행하지 않는다. 따라서 컨테이너 기본 동작에만 의존하며, 데이터 조회나 저장을 포함한 어떤 비즈니스 로직도 실행하지 않는다. |
| ejbLoad | public void ejbLoad() | - | - | 이 구성요소는 컨테이너가 영속성을 관리하며 연체 정보를 저장·조회하는 역할을 가지며, 이 구간은 영속 상태를 다시 적재할 때 호출되는 생명주기 콜백에 해당한다. 다만 구현이 비어 있어, 데이터 재적재 과정에서 애플리케이션 차원의 추가 조회·변환·검증 로직을 수행하지 않는다. 결과적으로 연체 정보의 적재는 컨테이너 관리 영속성 메커니즘에 전적으로 위임되며, 이 메서드 자체는 상태 변경이나 외부 자원 접근을 발생시키지 않는다. |
| ejbStore | public void ejbStore() | - | - | 연체 정보를 저장·조회하는 영속성 관리 구성요소에서, 저장 시점에 호출되는 저장 훅을 제공하지만 실제 구현은 비어 있다. 따라서 이 범위에서는 연체 정보의 상태를 갱신하거나 외부 저장소에 기록하기 위한 추가 로직을 수행하지 않는다. 결과적으로 영속성 반영은 컨테이너의 기본 동작(자동 동기화)에 의존하도록 남겨진 형태다. |
| ejbRemove | public void ejbRemove() throws RemoveException | - | - | 연체 정보를 컨테이너가 영속성으로 관리하는 CMP 구성요소에서, 인스턴스가 제거될 때 실행되는 생명주기 훅을 제공한다. 구현이 비어 있어 제거 시 추가 정리 작업, 연관 데이터 정합성 처리, 외부 자원 해제 등을 애플리케이션 코드에서 수행하지 않는다. 결과적으로 삭제/제거 자체는 컨테이너의 기본 제거 처리에 위임되며, 제거 과정에서 예외가 발생할 가능성만 선언적으로 드러낸다. |

#### 필드

| 이름 | 타입 | 수정자 | 요약 |
| --- | --- | --- | --- |
| entityContext | EntityContext | - | 컨테이너가 이 연체 정보 CMP 엔티티 빈을 관리(생명주기, 영속성 등)하기 위해 주입·제공하는 엔티티 컨텍스트를 보관하는 필드이다. |

#### 구조 관계

| 방향 | 관계 | 대상 | 속성 |
| --- | --- | --- | --- |
| → | ASSOCIATION | EntityContext | source_member=unsetEntityContext |
| → | DEPENDENCY | EntityContext | source_member=setEntityContext, usage=parameter |

#### 호출 관계

| 방향 | 대상 | 호출코드 |
| --- | --- | --- |
| → | DelinquencyBean | 73:         BigDecimal dailyPenalty = getDelinquencyAmount() 74:                 .multiply(getPenaltyRate()) 75:                 .divide(BigDecimal.valueOf(365), 2, RoundingMode.HALF_UP); |
| → | DelinquencyBean | 61:         setDelinquencyDays(days); |
| → | DelinquencyBean | 64:             setDelinquencyGrade("GRADE_1"); |
| → | DelinquencyBean | 76:         setPenaltyAmount(dailyPenalty.multiply(BigDecimal.valueOf(days))); |
| → | DelinquencyBean | 83:         setStatus("RESOLVED"); |
| → | DelinquencyBean | 84:         setResolutionDate(resolutionDate); |
| → | DelinquencyBean | 92:         setDelinquencyId(delinquencyId); |
| → | DelinquencyBean | 93:         setLedgerId(ledgerId); |
| → | DelinquencyBean | 94:         setCustomerId(customerId); |
| → | DelinquencyBean | 95:         setDelinquencyStartDate(delinquencyStartDate); |
| → | DelinquencyBean | 96:         setDelinquencyAmount(delinquencyAmount); |
| → | DelinquencyBean | 98:         setDelinquencyDays(0); |
| → | DelinquencyBean | 99:         setDelinquencyGrade("GRADE_1"); |
| → | DelinquencyBean | 97:         setPenaltyRate(penaltyRate); |
| → | DelinquencyBean | 100:         setStatus("ACTIVE"); |

#### 데이터 접근

| 대상 | 관계 | 근거 | 신뢰도 |
| --- | --- | --- | --- |
| - | - | - | - |

#### 요약 코드

```
없음
```

### DelinquencyLocal

#### 기본 정보

| 항목 | 값 |
| --- | --- |
| 이름 | DelinquencyLocal |
| 타입 | CLASS |
| FQN | com.banking.loan.entity.DelinquencyLocal |
| 패키지 | com.banking.loan.entity |
| 스테레오타입 | COMMAND/READMODEL |
| 파일 | - |
| 라인 | - |
| 토큰 | - |

#### 요약

> com.banking.loan.entity.DelinquencyLocal은 연체 엔티티 빈의 로컬 컴포넌트 인터페이스로, 연체 정보에 대한 CMP 필드 접근자와 관련 비즈니스 메서드의 계약을 정의한다. delinquencyId(연체 식별자)는 조회로 제공하고, ledgerId, customerId, delinquencyStartDate(연체 시작일), delinquencyAmount(연체금액), delinquencyDays(연체일수), delinquencyGrade(연체등급), penaltyRate(패널티 비율), penaltyAmount(패널티 금액), status(상태) 등을 조회/설정하여 연체 상태를 관리한다. 또한 updateDelinquencyDays로 delinquencyDays를 갱신하고, resolve를 통해 전달된 해소일자를 기준으로 연체를 해소 처리하며, setResolutionDate로 resolutionDate(해결일자)를 기록·갱신해 연체 해소 시점을 반영한다.

#### 메서드

| 이름 | 시그니처 | 반환타입 | 수정자 | 요약 |
| --- | --- | --- | --- | --- |
| getDelinquencyId | String getDelinquencyId() | - | - | 이 구성 요소는 연체 정보에 대한 CMP 필드 접근자와 비즈니스 기능을 정의하며, 그중 연체 식별자(delinquencyId)를 제공하는 조회용 접근자를 선언한다. 호출자는 이 접근자를 통해 현재 연체 레코드를 식별하는 문자열 값을 읽어올 수 있다. 이 선언은 값 조회 목적만 가지며, 연체 정보의 등록/변경/삭제 같은 상태 변경 동작은 포함하지 않는다. |
| getLedgerId | String getLedgerId() | - | - | 이 구성요소는 연체 정보에 대한 CMP 필드 접근자와 비즈니스 기능을 정의하기 위한 로컬 컴포넌트 인터페이스의 일부이다. 그중 이 선언은 연체 정보가 연결되는 ledgerId(원장 식별자)를 문자열로 조회해 반환하는 접근자 역할을 한다. 반환된 ledgerId는 연체 레코드가 어떤 원장에 속하는지 식별·연계하는 데 사용될 수 있다. 조회용 인터페이스 선언이므로 데이터 저장/수정/삭제 같은 상태 변경은 수행하지 않는다. |
| setLedgerId | void setLedgerId(String ledgerId) | - | - | 이 구성요소는 연체 정보에 대한 CMP 필드 접근자와 비즈니스 동작을 정의하며, 그중 이 범위는 연체 정보가 참조하는 ledgerId(원장 식별자) 값을 변경하기 위한 설정 동작을 제공한다. 호출자는 원장 식별자 문자열을 전달해 연체 데이터가 어떤 원장과 연결되는지를 갱신할 수 있다. 반환값 없이 상태를 변경하는 형태로, 컨테이너 관리 영속(CMP) 환경에서는 해당 필드 변경이 엔티티의 저장 상태에 반영되는 것을 전제로 한다. |
| getCustomerId | String getCustomerId() | - | - | 이 구성요소는 연체 정보에 대한 CMP 필드 접근자와 비즈니스 동작을 정의하는 로컬 인터페이스 맥락에 속한다. 그중 이 선언은 연체 정보에 연결된 customerId(고객식별자) 값을 문자열로 반환하도록 규정한다. 호출자는 이 값을 통해 연체 레코드가 어떤 고객에 속하는지 식별할 수 있으며, 이 범위에서는 상태 변경 없이 값 조회만 수행한다. |
| setCustomerId | void setCustomerId(String customerId) | - | - | 이 컴포넌트 인터페이스는 연체 정보에 대한 CMP 필드 접근자와 비즈니스 동작을 정의하며, 그중 이 선언은 연체 엔티티의 customerId(고객식별자) 값을 설정하기 위한 쓰기 동작을 제공한다. 호출자는 문자열 형태의 customerId를 전달해 연체 정보가 어떤 고객에 귀속되는지를 엔티티 상태로 반영할 수 있다. 조회나 계산 로직 없이 식별자 값을 갱신하는 목적에 집중된 선언이다. |
| getDelinquencyStartDate | Date getDelinquencyStartDate() | - | - | 이 코드는 연체 정보에 대한 CMP 필드 접근자와 비즈니스 동작을 정의하는 로컬 컴포넌트 인터페이스의 일부로, 연체 정보 중 delinquencyStartDate(연체 시작일)를 조회하기 위한 읽기 전용 접근자를 제공한다. 호출자는 이 반환값을 통해 해당 연체가 언제 시작되었는지(시작 시점)를 도메인 판단이나 화면/보고서 표시의 기준으로 사용할 수 있다. 선언만 존재하며, 입력값을 받지 않고 연체 시작일을 그대로 반환하는 형태로 설계되어 상태를 변경하지 않는다. |
| setDelinquencyStartDate | void setDelinquencyStartDate(Date delinquencyStartDate) | - | - | 이 인터페이스는 연체 정보에 대한 CMP 필드 접근자와 비즈니스 동작을 정의하며, 그중 연체 시작일(delinquencyStartDate) 값을 설정하는 계약을 제공한다. 외부에서 전달된 날짜 값을 연체 정보의 연체 시작일 필드에 반영하여 해당 엔티티 상태를 갱신하는 용도다. 실제 저장/반영 방식은 구현체(EJB 컨테이너/CMP 구현)에 의해 처리되며, 여기서는 연체 시작일을 변경하기 위한 입력만 명시한다. |
| getDelinquencyAmount | BigDecimal getDelinquencyAmount() | - | - | 이 코드는 연체 정보에 대한 CMP 필드 접근자와 관련 비즈니스 기능을 정의하는 로컬 컴포넌트 인터페이스의 한 항목으로, 연체금액을 조회해 반환하도록 계약을 선언한다. 구현체는 연체 정보에 저장된 금액 값을 임의정밀도 금액 타입으로 제공해야 하며, 이 시그니처 자체는 상태 변경을 수행하지 않는다. 따라서 호출자는 연체금액을 읽기 목적으로 얻기 위해 이 접근자를 사용한다. |
| setDelinquencyAmount | void setDelinquencyAmount(BigDecimal delinquencyAmount) | - | - | 이 구성요소는 연체 정보에 대한 CMP 필드 접근자와 비즈니스 동작을 정의하는 로컬 인터페이스이며, 그중 연체 금액(delinquencyAmount)을 갱신하기 위한 쓰기 동작을 제공한다. 호출 측에서 전달한 금액 값을 연체 정보에 반영하도록 설정하여, 이후 연체 관련 상태/데이터가 해당 금액 기준으로 관리되도록 한다. 조회가 아니라 연체 정보의 특정 속성 값을 변경하는 목적의 동작이다. |
| getDelinquencyDays | int getDelinquencyDays() | - | - | 이 컴포넌트 인터페이스는 연체 정보에 대한 CMP 필드 접근자와 비즈니스 기능을 정의하며, 그 중 이 구문은 연체 정보에서 delinquencyDays(연체일수) 값을 조회하기 위한 접근자를 선언한다. 반환값은 정수형으로, 특정 시점의 연체가 며칠인지(연체일수)를 호출자에게 제공하는 용도다. 상태를 변경하거나 저장을 수행하지 않고, 저장된 연체 속성 값을 읽어오는 목적의 조회 계약이다. |
| setDelinquencyDays | void setDelinquencyDays(int delinquencyDays) | - | - | 이 코드는 연체 정보에 대한 CMP 필드 접근자와 비즈니스 동작을 정의하는 로컬 컴포넌트 인터페이스의 일부로, 연체 관련 데이터 중 delinquencyDays(연체일수)를 갱신하기 위한 설정 동작을 선언한다. 정수로 전달된 연체일수를 해당 연체 정보의 상태값으로 반영하도록 하는 쓰기 목적의 계약(구현은 별도)에 해당한다. 반환값이 없으므로, 호출 측은 연체일수 변경 자체가 목적이며 조회 결과를 기대하지 않는다. |
| getDelinquencyGrade | String getDelinquencyGrade() | - | - | 이 컴포넌트 인터페이스는 연체 정보에 대한 CMP 필드 접근자와 비즈니스 동작을 정의하며, 그중 연체등급(delinquencyGrade)을 조회하는 접근자를 제공한다. 호출자는 연체 정보에 저장된 delinquencyGrade 값을 문자열 형태로 받아, 연체 수준을 식별하거나 화면/보고서 표시용으로 활용할 수 있다. 입력 파라미터 없이 현재 보유한 연체 데이터의 등급 값만 반환하는 조회 성격의 계약을 나타낸다. |
| setDelinquencyGrade | void setDelinquencyGrade(String delinquencyGrade) | - | - | 이 컴포넌트 인터페이스는 연체 정보에 대한 CMP 필드 접근자와 비즈니스 동작을 정의하며, 그중 이 범위는 연체 정보를 구성하는 delinquencyGrade(연체등급) 값을 갱신하도록 지정한다. 외부에서 전달된 연체등급 문자열을 엔티티의 해당 필드에 설정해, 이후 영속 상태에 반영될 수 있는 변경을 표현한다. 조회 목적이 아니라 연체 정보의 상태(등급)를 변경하는 의도를 가진 쓰기 성격의 동작이다. |
| getPenaltyRate | BigDecimal getPenaltyRate() | - | - | 이 컴포넌트 인터페이스는 연체 정보에 대한 CMP 필드 접근자와 비즈니스 동작을 정의하며, 그중 연체 관련 비율 값을 읽어오는 역할을 포함한다. 이 범위의 코드는 연체 정보에 저장된 penaltyRate(연체 가산/패널티 비율)를 BigDecimal 형태로 반환하도록 규약을 선언한다. 입력값을 받지 않으며, 계산·검증·상태 변경 없이 현재 보관된 값을 조회하는 목적이다. 구현은 외부에서 제공되므로 이 선언 자체는 부수효과 없이 읽기 계약만 제공한다. |
| setPenaltyRate | void setPenaltyRate(BigDecimal penaltyRate) | - | - | 이 코드는 연체 정보에 대한 CMP 필드 접근자와 비즈니스 동작을 정의하는 로컬 컴포넌트 인터페이스의 일부로, 연체 관련 상태를 변경하기 위한 입력 지점을 제공한다. 외부에서 전달된 penaltyRate(연체 가산금리/연체 이율에 해당하는 값)를 연체 정보의 영속 필드에 설정해, 이후 연체 계산이나 연체 조건 판단에 사용될 기준 값을 갱신한다. 반환값 없이 값 설정만 수행하는 형태로, 조회가 아니라 연체 정보의 속성 값을 변경하는 목적이 명확하다. |
| getPenaltyAmount | BigDecimal getPenaltyAmount() | - | - | 이 구성요소는 연체 정보에 대한 CMP 필드 접근자와 업무 기능을 정의하는 로컬 컴포넌트 인터페이스의 일부이다. 이 선언은 연체에 대해 산정·보관되는 패널티 금액(벌금/추가부담 금액)을 임의정밀도 숫자 값으로 조회해 반환하도록 규정한다. 구현체의 내부 상태를 변경하지 않고, 저장된 연체 관련 금액 정보를 읽어 제공하는 목적의 조회 계약이다. |
| setPenaltyAmount | void setPenaltyAmount(BigDecimal penaltyAmount) | - | - | 이 컴포넌트 인터페이스는 연체 정보에 대한 CMP 필드 접근자와 업무 동작을 정의하며, 그중 penaltyAmount(패널티 금액)를 변경하기 위한 설정 동작을 제공한다. 외부에서 전달된 금액 값을 연체 정보의 penaltyAmount 필드에 반영하도록 계약을 명시해, 연체에 따른 패널티 금액을 갱신할 수 있게 한다. 반환값이 없으므로 설정 수행 자체가 목적이며, 값 검증이나 계산 로직은 이 선언만으로는 포함되지 않는다. |
| getStatus | String getStatus() | - | - | 이 컴포넌트 인터페이스는 연체 정보에 대한 CMP 필드 접근자와 비즈니스 동작을 정의하는 목적을 가진다. 이 선언은 연체 정보에서 현재 상태(status)를 문자열로 조회하기 위한 접근자를 제공한다. 호출자는 이 값을 통해 연체 상태를 식별하거나 이후 처리 흐름(표시, 분기 판단 등)에 활용할 수 있다. |
| setStatus | void setStatus(String status) | - | - | 이 컴포넌트 인터페이스는 연체 정보에 대한 CMP 필드 접근자와 비즈니스 동작을 정의하며, 여기서는 연체 정보의 status(상태) 값을 변경하기 위한 쓰기 동작을 선언한다. 입력으로 전달된 상태 문자열을 연체 레코드의 status에 반영하도록 계약을 제공해, 이후 영속 상태나 처리 단계가 갱신될 수 있도록 한다. 구현체는 이 값을 설정함으로써 연체 정보의 현재 상태를 외부 호출 흐름에 맞게 확정하도록 의도된다. |
| getResolutionDate | Date getResolutionDate() | - | - | 연체 정보에 대한 CMP 필드 접근자와 비즈니스 메서드를 정의하는 로컬 컴포넌트 인터페이스의 일부로, 연체가 해소된 시점을 나타내는 resolutionDate(해소일자)를 조회하기 위한 접근자를 선언한다. 호출자는 이 값을 통해 연체 해소 여부나 해소 처리 시점을 판단하는 데 활용할 수 있다. 입력은 없고 날짜/시간 값을 반환하며, 해소되지 않은 상태라면 값이 비어 있을 가능성이 있다. 조회 목적의 선언으로 상태 변경은 수행하지 않는다. |
| setResolutionDate | void setResolutionDate(Date resolutionDate) | - | - | 연체 정보에 대한 CMP 필드 접근자와 비즈니스 메서드를 정의하는 로컬 컴포넌트 인터페이스의 일부로, 연체 정보의 resolutionDate(해결일자) 값을 설정하기 위한 계약을 제공한다. 입력으로 전달된 날짜 값을 resolutionDate 필드에 반영하여, 연체 건의 해결(해소) 시점을 기록·갱신하는 용도로 사용된다. 이 범위에는 검증, 변환, 예외 처리 로직이 포함되어 있지 않으며 값 설정 자체의 책임만 나타난다. |
| updateDelinquencyDays | void updateDelinquencyDays(int days) | - | - | 이 인터페이스는 연체 정보에 대한 CMP 필드 접근자와 비즈니스 동작을 정의하는 로컬 컴포넌트 계약을 제공한다. 여기서 이 시그니처는 연체 정보의 연체일수 값을 입력받아 해당 값을 갱신하는 동작을 나타낸다. 반환값이 없으므로, 호출자는 연체일수의 변경(상태 업데이트) 자체를 수행하는 목적으로 사용한다. |
| resolve | void resolve(Date resolutionDate) | - | - | 이 컴포넌트 인터페이스는 연체 정보에 대한 CMP 필드 접근자와 비즈니스 동작을 정의하며, 그중 하나로 연체 상태를 해소 처리하는 동작을 제공한다. 입력으로 전달된 해소일자를 기준으로 연체가 종료(해소)되었음을 시스템에 반영하도록 의도된 선언이다. 반환값이 없으므로, 연체 관련 상태/해소일자 등의 내부 정보가 갱신되는 형태의 업무 처리로 사용되는 것을 전제로 한다. |

#### 필드

| 이름 | 타입 | 수정자 | 요약 |
| --- | --- | --- | --- |
| - | - | - | - |

#### 구조 관계

| 방향 | 관계 | 대상 | 속성 |
| --- | --- | --- | --- |
| ← | DEPENDENCY | DelinquencyLocalHome | source_member=create, usage=return |
| ← | DEPENDENCY | DelinquencyLocalHome | source_member=findByPrimaryKey, usage=return |
| ← | DEPENDENCY | DebtCollectionSessionBean | source_member=delinquencyEntityToDTO, usage=parameter |
| ← | DEPENDENCY | DebtCollectionSessionBean | source_member=processCollectionPayment, usage=local_var |
| ← | DEPENDENCY | DebtCollectionSessionBean | source_member=delinquencyEntitiesToDTOs, usage=cast |
| ← | DEPENDENCY | DelinquencyMgmtSessionBean | source_member=getDelinquency, usage=local_var |
| ← | DEPENDENCY | DelinquencyMgmtSessionBean | source_member=calculateTotalPenalty, usage=local_var |
| ← | DEPENDENCY | DelinquencyMgmtSessionBean | source_member=entityToDTO, usage=parameter |
| ← | DEPENDENCY | DelinquencyMgmtSessionBean | source_member=entitiesToDTOs, usage=cast |

#### 호출 관계

| 방향 | 대상 | 호출코드 |
| --- | --- | --- |
| ← | DebtCollectionSessionBean | - |
| ← | DelinquencyMgmtSessionBean | - |

#### 데이터 접근

| 대상 | 관계 | 근거 | 신뢰도 |
| --- | --- | --- | --- |
| - | - | - | - |

#### 요약 코드

```
없음
```

### DelinquencyLocalHome

#### 기본 정보

| 항목 | 값 |
| --- | --- |
| 이름 | DelinquencyLocalHome |
| 타입 | CLASS |
| FQN | com.banking.loan.entity.DelinquencyLocalHome |
| 패키지 | com.banking.loan.entity |
| 스테레오타입 | COMMAND/READMODEL |
| 파일 | - |
| 라인 | - |
| 토큰 | - |

#### 요약

> 이 클래스는 연체 엔티티 빈의 로컬 홈 인터페이스로서, 연체의 생성 및 조회를 위한 메서드 계약을 정의한다. delinquencyId, ledgerId, customerId, delinquencyStartDate, delinquencyAmount, penaltyRate를 받아 연체 정보를 신규 등록하고 생성된 연체 건의 로컬 컴포넌트 접근자를 반환하며, 생성 실패 시 CreateException을 전달한다. 또한 Primary Key 단건 조회, 전체 목록 조회, customerId 또는 status 기준 다건 조회에 더해, 문자열 형태의 ledgerId(원장 식별자)로 연체 엔티티 컬렉션을 조회하는 기능을 제공하고, 조회 실패는 FinderException으로 알린다.

#### 메서드

| 이름 | 시그니처 | 반환타입 | 수정자 | 요약 |
| --- | --- | --- | --- | --- |
| create | DelinquencyLocal create(String delinquencyId, String ledgerId, String customerId,                             Date delinquencyStartDate, BigDecimal delinquencyAmount,                             BigDecimal penaltyRate) throws CreateException | - | - | 이 코드는 연체의 생성 및 조회를 위한 로컬 홈 인터페이스 책임 중, 연체 정보를 신규로 등록하는 계약을 정의한다. 입력으로 delinquencyId, ledgerId, customerId를 통해 연체 건의 식별과 원장/고객 연계를 지정하고, delinquencyStartDate로 연체 시작일을 확정한다. 또한 delinquencyAmount(연체금액)과 penaltyRate(가산금리/연체이율)를 받아 연체 산정의 핵심 값을 함께 등록하도록 요구한다. 생성이 성공하면 생성된 연체 건에 대한 로컬 컴포넌트 접근자를 반환하며, 생성 과정에서 문제가 발생하면 생성 예외를 통해 실패를 호출자에게 전달한다. |
| findByPrimaryKey | DelinquencyLocal findByPrimaryKey(String delinquencyId) throws FinderException | - | - | 이 코드는 연체 정보를 생성·조회하기 위한 로컬 홈 인터페이스의 조회 기능 중 하나로, 연체 엔티티를 고유 식별값으로 찾아 반환하는 계약을 정의한다. 입력으로 문자열 형태의 연체 식별자를 받아, 해당 식별자에 대응하는 연체 정보를 나타내는 로컬 컴포넌트를 결과로 돌려준다. 지정된 식별자에 해당하는 연체 정보를 찾지 못하거나 조회 과정에서 문제가 발생하면 조회 실패 예외를 호출자에게 전달하도록 선언되어 있다. |
| findAll | Collection findAll() throws FinderException | - | - | 이 로컬 홈 인터페이스는 연체 데이터를 생성하거나 조회하기 위한 진입점을 정의하며, 이 선언은 저장된 연체 항목 전체를 한 번에 조회하는 용도를 가진다. 별도의 입력 조건 없이 연체 항목들의 목록을 컬렉션 형태로 반환하도록 계약을 명시한다. 조회 과정에서 식별/탐색에 실패할 수 있으므로, 탐색 실패 성격의 예외가 발생할 수 있음을 함께 선언한다. |
| findByCustomerId | Collection findByCustomerId(String customerId) throws FinderException | - | - | 이 구성요소는 연체 정보를 생성하거나 조회하기 위한 로컬 홈 인터페이스의 역할을 가지며, 그중 고객 식별자(customerId)를 기준으로 연체 정보를 찾는 조회 기능을 정의한다. 입력으로 받은 고객ID에 해당하는 연체 관련 항목들을 여러 건 반환할 수 있도록 컬렉션 형태로 결과를 제공한다. 조회 과정에서 엔티티 탐색이 실패하거나 탐색 규약에 맞지 않는 상황이 발생하면 FinderException을 통해 호출자에게 조회 실패를 전달한다. |
| findByStatus | Collection findByStatus(String status) throws FinderException | - | - | 연체의 생성 및 조회를 담당하는 로컬 홈 인터페이스에서, 입력된 상태값(문자열)에 해당하는 연체 항목들을 조회해 컬렉션으로 반환하는 조회용 계약을 정의한다. 조회 기준은 상태값이며, 일치하는 연체 데이터가 없거나 조회 과정에서 문제가 발생하면 조회 실패 예외를 통해 호출자에게 오류를 전달하도록 되어 있다. 이 범위는 구현이 아닌 인터페이스 선언이므로 데이터 변경 로직은 포함하지 않고, 상태 기반 조회 요구사항만 명시한다. |
| findByLedgerId | Collection findByLedgerId(String ledgerId) throws FinderException | - | - | 연체의 생성 및 조회를 위한 로컬 홈 인터페이스에서, 원장 식별자(ledgerId)를 기준으로 연체 관련 엔티티들을 조회하기 위한 조회 계약을 정의한다. 호출자는 문자열 형태의 원장 식별자를 전달하며, 구현체는 이에 대응하는 연체 데이터 집합을 컬렉션으로 반환해야 한다. 조회 과정에서 대상 데이터를 찾지 못하거나 조회 규약을 만족하지 못하는 경우 조회 예외(FinderException)를 통해 실패를 알리도록 한다. |

#### 필드

| 이름 | 타입 | 수정자 | 요약 |
| --- | --- | --- | --- |
| - | - | - | - |

#### 구조 관계

| 방향 | 관계 | 대상 | 속성 |
| --- | --- | --- | --- |
| → | DEPENDENCY | DelinquencyLocal | source_member=create, usage=return |
| → | DEPENDENCY | DelinquencyLocal | source_member=findByPrimaryKey, usage=return |
| ← | DEPENDENCY | DebtCollectionSessionBean | source_member=getDelinquencyHome, usage=return |
| ← | DEPENDENCY | DebtCollectionSessionBean | source_member=getCollectionTargets, usage=local_var |
| ← | DEPENDENCY | DebtCollectionSessionBean | source_member=processCollectionPayment, usage=local_var |
| ← | DEPENDENCY | DelinquencyMgmtSessionBean | source_member=getDelinquencyHome, usage=return |
| ← | DEPENDENCY | DelinquencyMgmtSessionBean | source_member=getDelinquency, usage=local_var |
| ← | DEPENDENCY | DelinquencyMgmtSessionBean | source_member=getDelinquenciesByCustomer, usage=local_var |
| ← | DEPENDENCY | DelinquencyMgmtSessionBean | source_member=registerDelinquency, usage=local_var |

#### 호출 관계

| 방향 | 대상 | 호출코드 |
| --- | --- | --- |
| ← | DebtCollectionSessionBean | - |
| ← | DelinquencyMgmtSessionBean | - |

#### 데이터 접근

| 대상 | 관계 | 근거 | 신뢰도 |
| --- | --- | --- | --- |
| DelinquencyLocal | REFER_TO | - | 1.0 |
| DelinquencyLocal | REFER_TO | - | 1.0 |

#### 요약 코드

```
없음
```

### LoanApplicationBean

#### 기본 정보

| 항목 | 값 |
| --- | --- |
| 이름 | LoanApplicationBean |
| 타입 | CLASS |
| FQN | com.banking.loan.entity.LoanApplicationBean |
| 패키지 | com.banking.loan.entity |
| 스테레오타입 | COMMAND/READMODEL |
| 파일 | - |
| 라인 | - |
| 토큰 | - |

#### 요약

> com.banking.loan.entity.LoanApplicationBean은 컨테이너가 영속성을 관리하는 여신 신청 CMP 엔티티 빈으로, 여신 신청 정보를 저장·조회하며 applicationId, customerId, applicationDate, requestedAmount, loanType, loanPurpose, term, interestRate, status, screeningResult, screeningDate, approvedAmount, approverEmployeeId, remarks 같은 속성을 접근자/설정자로 노출해 조회·갱신한다. 신규 생성 시 applicationId~interestRate를 영속 상태로 초기화하고 status를 "DRAFT"로 설정하되, CMP 규약에 따라 생성 결과는 null로 반환하고 실제 저장/식별 처리는 컨테이너에 위임한다. 또한 컨테이너가 주입하는 EntityContext(entityContext)를 보관해 생명주기 및 컨테이너 서비스 접근에 사용하며, 저장(ejbStore)·삭제(ejbRemove) 같은 라이프사이클 훅은 정의돼 있지만 구현이 비어 있어 추가 검증/정리/연관 처리 없이 컨테이너 기본 동작에만 의존한다.

#### 메서드

| 이름 | 시그니처 | 반환타입 | 수정자 | 요약 |
| --- | --- | --- | --- | --- |
| getApplicationId | - | - | - | 컨테이너가 영속성을 관리하는 여신 신청 정보 저장·조회용 구성요소에서, 여신 신청을 식별하는 값(applicationId)을 문자열로 조회하기 위한 접근자 계약을 선언한다. 구현을 제공하지 않는 추상 선언이므로, 실제 값의 획득 방식(영속 저장소에서 로딩되거나 컨테이너가 주입하는 방식 등)은 구체 구현에 위임된다. 이 선언은 상태를 변경하지 않고 여신 신청 식별자 값을 제공하는 조회 목적의 인터페이스 역할을 한다. |
| setApplicationId | - | - | - | 여신 신청 정보를 저장·조회하는 CMP 엔티티 빈 구현 맥락에서, 여신 신청을 식별하는 applicationId(신청 ID)를 엔티티 상태에 반영하기 위한 설정 동작을 정의한다. 입력으로 전달된 신청 ID 값을 해당 엔티티의 신청 식별 값으로 저장하도록 하는 계약(추상 선언)이며, 실제 저장 방식은 구현체/컨테이너가 결정한다. 이 동작은 조회가 아니라 엔티티의 상태를 변경하는 목적을 가진다. |
| getCustomerId | - | - | - | 이 구성요소는 컨테이너가 영속성을 관리하는 여신 신청 정보의 저장·조회 책임 맥락에서 동작한다. 그중 이 선언은 여신 신청 데이터에 연계된 고객 식별자(customerId)를 문자열로 제공하도록 강제하는 조회용 계약을 정의한다. 구현이 추상화되어 있어, 실제 customerId의 취득 방식(영속 상태에서 읽기, 파생 값 계산 등)은 구체 구현에 위임된다. 이를 통해 여신 신청을 조회하거나 연계 고객을 식별해야 하는 흐름에서 customerId를 일관된 방식으로 얻을 수 있게 한다. |
| setCustomerId | - | - | - | 여신 신청 정보를 저장·조회하는 CMP 엔티티 빈 구현 맥락에서, 신청 정보의 식별을 위해 customerId(고객 식별자)를 엔티티 상태에 반영하도록 규정하는 추상 설정 동작이다. 입력으로 전달된 customerId 값을 내부 영속 상태에 기록하는 것을 목적에 두며, 실제 저장 방식과 검증 규칙은 구현 클래스에서 구체화된다. 이 설정은 이후 컨테이너가 관리하는 영속성 저장/조회 과정에서 해당 여신 신청 레코드를 식별하거나 연계하는 기준값으로 사용될 수 있다. |
| getApplicationDate | - | - | - | 이 구성요소는 컨테이너가 영속성을 관리하는 여신 신청 정보 저장·조회 책임을 가지며, 그중 신청 정보를 조회할 때 사용될 신청일자를 제공하기 위한 접근 지점을 정의한다. 신청일자(applicationDate)를 날짜 타입으로 반환하도록만 규정되어 있고, 실제 반환 값의 획득 방식(영속 저장소에서 로딩, 계산, 캐시 등)은 구현체에 위임된다. 입력 파라미터가 없으므로 현재 인스턴스가 보유한 여신 신청 상태로부터 신청일자 값을 읽어오는 용도로 사용된다. 상태 변경이나 저장 작업은 수행하지 않고, 신청일자 값을 조회하는 목적에 집중한다. |
| setApplicationDate | - | - | - | 여신 신청 정보를 컨테이너가 영속적으로 관리·저장하는 구성요소에서, 신청일자(applicationDate)를 설정하기 위한 추상 동작을 선언한다. 입력으로 전달된 날짜 값을 여신 신청 정보의 신청일자 속성에 반영하도록 의도되어 있다. 구현은 제공되지 않으며, 실제 구현체에서 해당 값이 엔티티의 영속 상태 변경으로 연결되도록 확장 지점을 제공한다. |
| getRequestedAmount | - | - | - | 이 구성요소는 컨테이너가 영속성을 관리하는 여신 신청 정보를 저장·조회하는 목적을 가지며, 그 중 신청 시 요청된 금액을 읽어오는 접근 지점을 제공한다. 반환값은 BigDecimal로, 요청금액을 정밀한 숫자 타입으로 조회해 이후 한도/심사/계산 로직에서 금액 기준 값을 일관되게 사용하도록 한다. 추상 선언만 존재하므로 실제 값의 로딩 방식은 구현체(또는 컨테이너의 영속성 처리)에 위임되며, 이 지점 자체는 상태를 변경하지 않는다. |
| setRequestedAmount | - | - | - | 이 클래스는 컨테이너가 영속성을 관리하는 여신 신청 정보의 저장·조회 책임을 가지며, 그 중 requestedAmount(요청금액)를 변경하기 위한 값 설정 규약을 제공한다. 외부에서 전달된 금액(BigDecimal)을 requestedAmount에 반영하도록 정의되어 있어, 여신 신청 데이터의 상태를 갱신하는 목적을 가진다. 구현은 추상화되어 있어 실제 값 반영 방식(필드 저장 및 영속화 반영 여부)은 구현체에 위임된다. |
| getLoanType | - | - | - | 여신 신청 정보를 컨테이너가 영속성으로 관리하는 CMP 엔티티 빈 구현 맥락에서, 여신(대출) 종류를 식별하는 값을 문자열로 반환하기 위한 조회용 접근자 계약을 정의한다. 구현이 추상화되어 있어 실제 반환 값은 구체 구현체 또는 컨테이너가 제공하는 영속 필드 매핑을 통해 결정된다. 이 반환 값은 여신 신청 데이터의 분류/구분에 활용될 수 있도록, 신청 정보에 저장된 ‘여신 종류’ 값을 외부로 읽어내는 목적을 가진다. |
| setLoanType | - | - | - | 이 클래스는 컨테이너가 영속성을 관리하는 여신 신청 정보를 저장·조회하기 위한 CMP 엔티티 빈 구현을 전제로 한다. 이 범위의 선언은 여신 신청 정보 중 loanType(대출유형)을 외부 입력값으로 설정(변경)하기 위한 추상 동작을 정의한다. 실제로 값이 어떻게 검증·정규화되거나 영속 상태에 반영되는지는 구현 클래스에서 결정되며, 여기서는 대출유형 변경이라는 상태 갱신 계약만 명시한다. |
| getLoanPurpose | - | - | - | 여신 신청 정보를 컨테이너가 영속성으로 관리하는 구성 요소에서, 여신 신청 건의 loanPurpose(대출목적) 값을 조회해 문자열로 제공하도록 인터페이스(계약)를 정의한다. 구현은 하위 구현체에 위임되어 있으며, 이 범위 자체에서는 값의 계산·변환이나 저장소 갱신 같은 부수효과를 수행하지 않는다. 따라서 호출자는 여신 신청의 대출목적을 읽기 용도로 일관되게 취득할 수 있다. |
| setLoanPurpose | - | - | - | 이 구성요소는 컨테이너가 영속성을 관리하는 여신 신청 정보 저장·조회 기능의 일부로, 여신 신청 데이터의 특정 속성을 갱신할 수 있도록 설계되어 있다. 입력으로 전달된 loanPurpose(대출목적) 값을 여신 신청 정보에 설정(갱신)하는 동작을 정의하지만, 실제 저장 방식이나 검증 규칙은 여기에서 구현하지 않고 하위 구현에 위임한다. 따라서 호출자는 대출목적 변경 의도를 명확히 표현할 수 있고, 구현체는 변경된 값이 영속 상태에 반영되도록 처리하게 된다. |
| getTerm | - | - | - | 이 구성요소는 컨테이너가 영속성을 관리하는 여신 신청 정보를 저장·조회하는 구현을 전제로 하며, 그 중 신청 조건의 핵심 값 중 하나인 기간(term)을 정수로 제공하는 계약을 정의한다. 실제 값의 산출·조회 방식은 구현체에 위임되어, 여신 신청 정보가 어디에 저장되어 있든 동일한 방식으로 기간 값을 얻을 수 있게 한다. 반환값은 기간을 나타내는 정수이며, 이 선언 자체는 상태 변경이나 저장 처리를 수행하지 않는다. |
| setTerm | - | - | - | 이 클래스는 컨테이너가 영속성을 관리하는 여신 신청 정보의 저장·조회 책임을 가지며, 그 중 여신 신청의 기간(term) 값을 설정하기 위한 동작을 규정한다. 입력으로 정수 형태의 기간 값을 받아 해당 여신 신청 정보에 반영하도록 강제하지만, 실제 저장 방식이나 검증 규칙은 구현 클래스에서 결정된다. 즉, 기간(term) 변경이라는 상태 변경 의도를 가진 설정 계약만 제공하고 구체 구현은 외부에 위임한다. |
| getInterestRate | - | - | - | 이 클래스는 컨테이너가 영속성을 관리하는 여신 신청 정보 저장·조회 목적의 CMP 엔티티 빈 구현이며, 이 메서드는 여신 신청 정보에 포함된 interestRate(이자율)를 조회하기 위한 추상 접근자이다. 반환값은 BigDecimal로 표현되는 이자율 값이며, 호출자는 이를 이용해 신청 건의 조건(이자율)을 읽어간다. 메서드 본문이 없으므로 실제 값의 로딩/매핑은 컨테이너 또는 하위 구현에 의해 제공되는 영속성 처리에 위임된다. |
| setInterestRate | - | - | - | 여신 신청 정보를 컨테이너가 영속성으로 관리·저장/조회하는 구성에서, 여신 신청 데이터의 interestRate(이자율) 값을 설정하기 위한 추상 계약을 정의한다. 이자율은 숫자형(정밀 소수) 값으로 입력되며, 구체 구현(또는 컨테이너 생성 코드)이 실제 저장 대상 속성에 반영하는 책임을 가진다. 메서드 본문이 없으므로 검증, 변환, 영속화 호출 여부는 이 선언만으로는 확인되지 않지만, 목적 자체는 여신 신청의 이자율 상태를 변경하는 설정 동작이다. |
| getStatus | - | - | - | 여신 신청 정보를 컨테이너가 영속성으로 관리하는 구성요소 안에서, 신청 건의 상태값을 문자열로 조회하기 위한 추상 조회 계약을 정의한다. 실제 상태값이 어디에 저장되어 있는지(영속 필드/계산 값 등)와 어떤 형식으로 반환할지는 구현체에 위임된다. 이 선언 자체는 데이터를 변경하거나 저장하지 않으며, 상태를 읽어 반환하는 목적에만 초점을 둔다. |
| setStatus | - | - | - | 컨테이너가 영속성을 관리하며 여신 신청 정보를 저장·조회하는 CMP 엔티티 빈에서, 여신 신청의 status(상태) 값을 변경하기 위한 추상 동작을 정의한다. 입력으로 전달된 상태 문자열을 엔티티의 상태 속성에 반영하도록 하위 구현이 책임지며, 이를 통해 신청 상태 전이를 표현할 수 있게 한다. 구현부가 없으므로 실제 저장 반영 방식(컨테이너 관리 필드 갱신, 검증, 상태 코드 정합성 등)은 구체 클래스에서 결정된다. |
| getScreeningResult | - | - | - | 여신 신청 정보를 컨테이너가 영속적으로 관리·조회하는 구성요소에서, 신청 건의 심사 결과를 문자열로 제공하기 위한 조회용 계약(추상 메서드)을 정의한다. 구체적인 심사 결과 산출 방식이나 저장소 접근 방식은 이 선언부에 포함되지 않으며, 실제 반환 값은 구현체에서 결정된다. 이 기능은 심사 결과를 화면 표시나 후속 처리 판단에 사용할 수 있도록 읽기 형태로 노출하는 역할을 한다. |
| setScreeningResult | - | - | - | 이 클래스는 컨테이너 관리 영속성으로 여신 신청 정보를 저장·조회하는 컴포넌트이며, 이 코드는 여신 신청의 심사 결과(screeningResult)를 설정하기 위한 계약을 정의한다. 입력으로 받은 screeningResult 값을 엔티티의 영속 상태에 반영해 이후 저장 및 조회 시 심사 결과가 유지되도록 하는 목적을 가진다. 구현이 추상화되어 있어 실제 값 반영 방식(필드 매핑/영속화 처리)은 하위 구현 또는 컨테이너에 위임된다. |
| getScreeningDate | - | - | - | 이 코드는 컨테이너가 영속성을 관리하는 여신 신청 정보 저장·조회 구성요소 안에서, 여신 신청의 심사일자(screeningDate)를 제공하기 위한 조회용 접근 규약을 정의한다. 구현은 제공하지 않고 반환값의 타입만 날짜로 지정하여, 실제 구현 클래스가 영속 저장된 여신 신청 정보로부터 심사일자를 조회해 돌려주도록 강제한다. 즉, 여신 신청의 심사 시점을 외부 로직이 일관된 방식으로 읽을 수 있게 하는 인터페이스 역할을 한다. |
| setScreeningDate | - | - | - | 이 코드는 컨테이너가 영속성을 관리하는 여신 신청 정보 구성요소에서, screeningDate(심사일자)를 갱신하기 위한 설정 동작의 계약을 정의한다. 입력으로 받은 심사일자를 내부 상태에 반영하도록 요구하며, 이를 통해 여신 신청 정보에 심사 수행(또는 심사 기준) 일자를 기록·수정할 수 있게 한다. 메서드 본문이 없는 추상 선언이므로, 실제 값 저장 및 영속화 반영 방식은 구체 구현과 컨테이너의 관리 정책에 의해 결정된다. |
| getApprovedAmount | - | - | - | 이 클래스는 컨테이너가 영속성을 관리하는 여신 신청 정보의 저장·조회 책임을 가지며, 여기서는 그중 승인된 금액 정보를 외부로 제공하는 조회 동작을 정의한다. 승인금액(approvedAmount)을 금액형 값으로 반환하도록 선언되어, 영속화된 여신 신청 데이터에서 승인 결과 금액을 읽어오는 용도로 사용된다. 구현 내용이 없는 추상 선언이므로, 실제로 어떤 저장소에서 어떻게 값을 가져오는지는 하위 구현에서 결정된다. 이 동작은 값을 변경하거나 저장하지 않고, 승인금액을 읽어 반환하는 목적에 집중한다. |
| setApprovedAmount | - | - | - | 여신 신청 정보를 저장·조회하도록 영속성이 컨테이너에 의해 관리되는 구성요소 안에서, 승인금액(approvedAmount)을 설정하기 위한 변경 작업의 계약을 선언한다. 승인금액 값은 금액 연산 정밀도가 필요한 타입으로 전달되며, 구현체는 이를 내부 상태에 반영해 이후 저장 대상 데이터로 만들 의도를 가진다. 이 구간은 구현 코드가 없는 추상 선언이므로, 실제 값 검증/정규화/영속화 시점과 방식은 하위 구현에 위임된다. |
| getApproverEmployeeId | - | - | - | 이 클래스는 컨테이너가 영속성을 관리하는 여신 신청 정보를 저장·조회하기 위한 구현을 제공하며, 그 중 결재자 식별 정보를 읽어오는 역할이 필요하다. 이 코드는 여신 신청 건에 연결된 결재자 직원 식별자(approverEmployeeId)를 문자열로 반환하도록 계약만 정의하고, 실제 값의 취득 방식은 구현체에 위임한다. 따라서 호출자는 내부 저장 상태나 조회 경로를 알 필요 없이 결재자 직원 식별자를 일관된 방식으로 획득할 수 있다. 반환되는 식별자는 승인/결재 흐름에서 결재자 지정이나 조회 목적으로 사용될 수 있다. |
| setApproverEmployeeId | - | - | - | 여신 신청 정보를 저장·조회하는 영속성 관리 구성요소에서, approverEmployeeId(승인자 사원번호)를 설정하기 위한 추상 동작을 선언한다. 입력으로 전달된 승인자 사원번호 문자열을 해당 여신 신청 데이터에 반영(갱신)하기 위한 계약이며, 실제 저장 방식과 검증/정규화 여부는 구현체가 결정한다. 이 설정은 여신 신청의 승인자 식별 정보를 변경하는 쓰기 성격의 동작을 모델링한다. |
| getRemarks | - | - | - | 여신 신청 정보를 컨테이너가 영속성으로 관리하는 CMP 엔티티 빈 구현 맥락에서, 여신 신청 건의 remarks(비고) 값을 조회해 문자열로 반환하기 위한 접근자 계약을 정의한다. 구현은 추상화되어 있어 실제 값 제공 방식은 컨테이너/구현 클래스에 의해 결정되며, 호출자는 비고 정보를 읽기 용도로 사용할 수 있다. 데이터의 생성·수정·삭제 같은 상태 변경은 수행하지 않고, 비고 속성의 조회 결과만 제공하는 읽기 성격의 동작이다. |
| setRemarks | - | - | - | 이 클래스는 컨테이너가 영속성을 관리하는 여신 신청 정보 저장·조회용 엔티티 빈 구현을 전제로 한다. 이 코드는 여신 신청 정보에 대한 비고(remarks) 값을 설정하기 위한 변경 지점을 정의하며, 문자열 형태의 비고 내용을 입력으로 받는다. 구현은 추상화되어 있어 실제로 어떤 저장 필드에 어떻게 반영할지는 하위 구현에서 결정된다. 결과적으로 영속 상태의 여신 신청 정보 중 비고 값이 갱신될 수 있는 쓰기 동작(상태 변경)을 나타낸다. |
| ejbCreate | public String ejbCreate(String applicationId, String customerId, Date applicationDate,                             BigDecimal requestedAmount, String loanType, String loanPurpose,                             int term, BigDecimal interestRate) throws CreateException | - | - | 컨테이너가 영속성을 관리하는 여신 신청 정보를 신규로 등록하는 시점에, 입력으로 전달된 신청 식별 정보와 조건들을 엔티티의 영속 상태로 초기화한다. applicationId(신청 ID), customerId(고객 식별자), applicationDate(신청일자), requestedAmount(요청금액), loanType(대출유형), loanPurpose(대출목적), term(기간), interestRate(이자율)을 각각 엔티티 속성에 반영해 이후 저장·조회 기준이 되도록 만든다. 초기 상태값으로 status를 "DRAFT"로 설정하여 신청이 임시 작성 단계임을 명시한다. CMP 생성 규약에 따라 생성 결과로는 null을 반환하며, 실제 식별/저장 처리는 컨테이너의 관리 범위에 맡긴다. |
| ejbPostCreate | public void ejbPostCreate(String applicationId, String customerId, Date applicationDate,                               BigDecimal requestedAmount, String loanType, String loanPurpose,                               int term, BigDecimal interestRate) | - | - | 여신 신청 정보를 컨테이너가 영속성으로 관리하는 구성요소 안에서, 생성 직후 후처리를 수행하기 위해 마련된 생명주기 훅이지만 실제 구현은 비어 있다. 입력으로 applicationId(신청ID), customerId(고객ID), applicationDate(신청일자), requestedAmount(요청금액), loanType(대출유형), loanPurpose(대출목적), term(기간), interestRate(이자율)을 전달받으나, 이 범위 내에서는 이를 검증하거나 저장/연관관계 설정 등 어떤 상태 변경도 수행하지 않는다. 결과적으로 생성 과정에서 추가로 확정해야 할 후처리 로직이 현재는 정의되지 않은 상태이며, 영속화 및 기본 생성 처리는 컨테이너/외부 흐름에 위임된 형태다. |
| setEntityContext | public void setEntityContext(EntityContext ctx) | - | - | 이 클래스는 컨테이너가 영속성을 관리하는 여신 신청 정보의 저장·조회 흐름에 참여하며, 그 수행에 필요한 실행 컨텍스트를 내부에 유지한다. 이 코드는 외부(컨테이너)에서 전달된 엔티티 실행 컨텍스트를 받아 클래스 내부 상태로 저장해, 이후 영속성 처리나 생명주기 콜백에서 해당 컨텍스트를 사용할 수 있게 한다. 별도의 검증이나 부가 처리 없이 전달받은 참조를 그대로 보관하는 설정 단계 역할을 한다. |
| unsetEntityContext | public void unsetEntityContext() | - | - | 컨테이너가 영속성을 관리하는 여신 신청 정보 저장·조회 구성요소에서, 컨테이너가 주입해 두었던 엔티티 실행 컨텍스트 참조를 명시적으로 해제한다. 내부에 보관 중인 실행 컨텍스트를 null로 설정해 이후 이 인스턴스가 컨텍스트에 의존한 처리를 수행하지 않도록 만든다. 이는 생명주기 종료나 정리 단계에서 불필요한 참조를 끊어 자원/상태를 정리하려는 의도를 가진다. |
| ejbActivate | public void ejbActivate() | - | - | 컨테이너가 영속성을 관리하며 여신 신청 정보를 저장·조회하는 CMP 엔티티 빈 구현에서, 패시베이션 이후 다시 활성화될 때 호출되는 생명주기 훅을 제공한다. 그러나 본문이 비어 있어 활성화 시점에 추가로 수행하는 초기화, 상태 복구, 외부 자원 재연결 등의 처리가 없다. 따라서 엔티티의 영속 상태나 여신 신청 데이터에 대한 조회·변경을 발생시키지 않으며, 컨테이너 기본 동작에만 의존한다. |
| ejbPassivate | public void ejbPassivate() | - | - | 컨테이너가 영속성을 관리하며 여신 신청 정보를 저장·조회하는 CMP 엔티티 빈에서, 인스턴스가 메모리에서 비활성화(패시베이션)될 때 호출되는 생명주기 훅을 제공한다. 해당 구간은 구현이 비어 있어 패시베이션 시점에 자원 해제, 상태 정리, 컨텍스트 처리 등의 추가 작업을 수행하지 않는다. 따라서 이 훅은 동작 확장 지점만 마련되어 있으며, 현재 상태 변경이나 조회 로직은 포함하지 않는다. |
| ejbLoad | public void ejbLoad() | - | - | 여신 신청 정보를 컨테이너가 영속성으로 관리하는 구성에서, 저장소의 현재 상태를 인스턴스에 반영하는 로딩 시점에 실행되도록 마련된 구간이다. 그러나 본문이 비어 있어, 로딩 과정에서 추가 검증·변환·파생값 계산 같은 후처리를 수행하지 않는다. 결과적으로 데이터 적재/동기화는 컨테이너의 기본 로딩 동작에만 의존하며, 이 구간 자체는 외부 조회나 상태 변경을 일으키지 않는다. |
| ejbStore | public void ejbStore() | - | - | 여신 신청 정보를 컨테이너가 영속성 컨텍스트에 반영할 때 호출되는 저장 단계의 훅이지만, 실제로 수행하는 로직이 비어 있어 상태 동기화나 저장 처리를 직접 실행하지 않는다. 따라서 저장 시점에 추가 검증, 값 보정, 관련 데이터 갱신 같은 부가 동작을 의도적으로 생략하거나 컨테이너 기본 동작에 전적으로 위임하는 형태다. 결과적으로 이 구간만으로는 여신 신청 정보의 변경·저장에 대한 명시적 처리 흐름을 확인할 수 없다. |
| ejbRemove | public void ejbRemove() throws RemoveException | - | - | 여신 신청 정보를 저장·조회하는 CMP 기반 엔티티 빈에서, 엔티티 삭제 라이프사이클에 대응하는 제거 콜백이 정의되어 있다. 다만 본문 구현이 비어 있어 삭제 시점에 추가 정리 작업, 검증, 연관 데이터 처리 같은 애플리케이션 레벨 동작을 수행하지 않는다. 결과적으로 삭제는 컨테이너의 기본 영속성/라이프사이클 처리에만 의존하며, 삭제 과정에서 발생할 수 있는 제거 예외만 인터페이스 계약 차원에서 선언한다. |

#### 필드

| 이름 | 타입 | 수정자 | 요약 |
| --- | --- | --- | --- |
| entityContext | EntityContext | - | 컨테이너가 관리하는 CMP 엔티티 빈의 실행 컨텍스트(EntityContext)를 보관하여, 엔티티 생명주기(생성·로딩·제거 등)와 컨테이너 서비스 접근에 사용되는 참조를 유지한다. |

#### 구조 관계

| 방향 | 관계 | 대상 | 속성 |
| --- | --- | --- | --- |
| → | ASSOCIATION | EntityContext | source_member=setEntityContext |
| → | ASSOCIATION | EntityContext | source_member=unsetEntityContext |

#### 호출 관계

| 방향 | 대상 | 호출코드 |
| --- | --- | --- |
| → | LoanApplicationBean | 67:         setApplicationId(applicationId); |
| → | LoanApplicationBean | 68:         setCustomerId(customerId); |
| → | LoanApplicationBean | 69:         setApplicationDate(applicationDate); |
| → | LoanApplicationBean | 70:         setRequestedAmount(requestedAmount); |
| → | LoanApplicationBean | 71:         setLoanType(loanType); |
| → | LoanApplicationBean | 72:         setLoanPurpose(loanPurpose); |
| → | LoanApplicationBean | 73:         setTerm(term); |
| → | LoanApplicationBean | 74:         setInterestRate(interestRate); |
| → | LoanApplicationBean | 75:         setStatus("DRAFT"); |

#### 데이터 접근

| 대상 | 관계 | 근거 | 신뢰도 |
| --- | --- | --- | --- |
| - | - | - | - |

#### 요약 코드

```
없음
```

### LoanApplicationLocal

#### 기본 정보

| 항목 | 값 |
| --- | --- |
| 이름 | LoanApplicationLocal |
| 타입 | CLASS |
| FQN | com.banking.loan.entity.LoanApplicationLocal |
| 패키지 | com.banking.loan.entity |
| 스테레오타입 | COMMAND/READMODEL |
| 파일 | - |
| 라인 | - |
| 토큰 | - |

#### 요약

> com.banking.loan.entity.LoanApplicationLocal은 여신 신청 엔티티 빈의 로컬 컴포넌트 인터페이스로, 여신 신청 정보에 대한 CMP 필드 접근자(조회/설정) 계약을 정의한다. applicationId, customerId, applicationDate, requestedAmount, loanType, loanPurpose, term, interestRate, status(상태), screeningResult(심사결과), screeningDate(심사일자), approvedAmount(승인금액), approverEmployeeId(승인자 사원ID), remarks(비고) 등의 영속 속성을 읽고 일부를 갱신하며, status는 접수 → 심사 → 승인/거절 흐름으로 처리 상태를 조회/변경할 수 있게 한다. 특히 비고(remarks)는 외부에서 값 변경 의도를 전달할 수 있도록 설정(갱신)용 접근자를 제공하며, 실제 영속화는 구현체와 컨테이너에 위임한다.

#### 메서드

| 이름 | 시그니처 | 반환타입 | 수정자 | 요약 |
| --- | --- | --- | --- | --- |
| getApplicationId | String getApplicationId() | - | - | 여신 신청 정보에 대한 CMP 필드 접근자를 정의하는 로컬 컴포넌트 인터페이스의 일부로, 여신 신청의 식별자(applicationId)를 문자열로 조회해 반환한다. 이 접근자는 저장된 여신 신청 레코드의 고유 식별 값을 외부에서 읽을 수 있도록 제공하며, 데이터의 변경 없이 읽기 용도로만 사용된다. 반환되는 값은 여신 신청을 다른 처리 단계나 연관 데이터와 연결할 때 기준 키로 활용될 수 있다. |
| getCustomerId | String getCustomerId() | - | - | 이 코드는 여신 신청 정보에 대한 CMP 필드 접근자를 정의하는 로컬 컴포넌트 인터페이스의 일부로, 여신 신청 데이터에 포함된 customerId(고객 식별자)를 외부에서 조회할 수 있도록 한다. 호출자는 이 반환값을 통해 특정 여신 신청 레코드가 어떤 고객과 연계되어 있는지 식별하고, 이후 고객 기준의 검증·조회·연계 처리를 수행하는 데 활용할 수 있다. 입력 파라미터 없이 현재 엔티티 인스턴스의 저장된 값을 그대로 반환하는 형태이며, 데이터 생성/수정/삭제 등 상태 변경 의도는 없다. |
| setCustomerId | void setCustomerId(String customerId) | - | - | 여신 신청 정보에 대한 CMP 필드 접근자를 정의하는 로컬 컴포넌트 인터페이스의 일부로, customerId(고객식별자) 값을 엔티티의 상태로 설정하기 위한 쓰기 동작을 선언한다. 입력으로 받은 customerId 문자열을 해당 신청 정보에 반영하도록 계약(시그니처)만 제공하며, 구현체가 실제 저장/반영 책임을 가진다. 이 선언 자체에는 검증, 분기, 조회, 외부 호출 로직이 포함되지 않으며, 상태 변경 의도가 명확한 필드 설정 인터페이스 역할에 집중한다. |
| getApplicationDate | Date getApplicationDate() | - | - | 여신 신청 정보에 대한 CMP 필드 접근자를 정의하는 로컬 컴포넌트 인터페이스의 일부로, 여신 신청 건의 applicationDate(신청일자)를 조회하기 위한 접근자이다. 호출자는 이 값을 통해 해당 신청이 언제 접수/등록되었는지의 기준 일자를 확인할 수 있다. 데이터를 생성·수정·삭제하지 않고, 저장된 신청일자 값을 반환하는 읽기 전용 성격의 동작이다. |
| setApplicationDate | void setApplicationDate(Date applicationDate) | - | - | 이 구성요소는 여신 신청 정보에 대한 CMP 필드 접근자를 정의하는 로컬 컴포넌트 인터페이스이며, 여신 신청 엔티티의 상태를 다루기 위한 계약을 제공한다. 이 범위의 동작은 여신 신청 정보의 applicationDate(신청일자)를 외부에서 전달받은 값으로 설정하는 것이다. 신청일자를 변경함으로써 여신 신청 정보의 저장 대상 상태가 갱신되는 의도를 갖는다. 반환값이 없고 입력으로 받은 일자 값만을 반영하는 설정(변경) 성격의 작업이다. |
| getRequestedAmount | BigDecimal getRequestedAmount() | - | - | 이 코드는 여신 신청 정보에 대한 CMP 필드 접근자를 제공하는 로컬 컴포넌트 인터페이스의 일부로, 신청 정보의 조회를 목적으로 한다. 여신 신청 데이터 중 requestedAmount(신청금액)를 외부에서 읽을 수 있도록 금액 값을 반환한다. 입력 파라미터 없이 현재 보관된 신청금액 상태를 그대로 돌려주며, 데이터 변경이나 저장을 수행하지 않는다. |
| setRequestedAmount | void setRequestedAmount(BigDecimal requestedAmount) | - | - | 여신 신청 정보에 대한 CMP 필드 접근자를 제공하는 로컬 컴포넌트 인터페이스의 일부로, 여신 신청 데이터의 requestedAmount(신청금액)를 설정하기 위한 쓰기 동작을 정의한다. 입력으로 전달된 금액 값을 requestedAmount 필드에 반영하여, 해당 신청 건의 신청금액 상태를 변경하는 목적을 가진다. 반환값이 없으며, 금액 필드의 갱신 자체가 주요 책임이다. |
| getLoanType | String getLoanType() | - | - | 여신 신청 정보에 대한 CMP 필드 접근자를 제공하는 로컬 컴포넌트 인터페이스의 일부로, 신청 데이터에서 loanType(대출/여신 유형) 값을 읽어오기 위한 조회용 접근자이다. 호출자는 반환된 문자열 값을 통해 해당 신청 건의 여신 유형을 식별하고, 화면 표시나 후속 업무 규칙 판단에 활용할 수 있다. 이 범위에서는 값을 설정하거나 상태를 변경하는 동작 없이, 저장된 신청 정보의 특정 속성을 반환하는 목적에 집중한다. |
| setLoanType | void setLoanType(String loanType) | - | - | 이 인터페이스는 여신 신청 정보에 대한 CMP 필드 접근자를 정의해, 여신 신청 엔티티의 영속 필드를 다루는 계약을 제공한다. 이 선언은 여신 신청 정보의 loanType(대출유형) 값을 입력으로 받아 해당 CMP 필드에 반영(설정)하도록 요구한다. 조회가 아니라 값 변경을 목적으로 하며, 구현체에서는 영속 상태의 loanType을 갱신하는 동작으로 연결된다. |
| getLoanPurpose | String getLoanPurpose() | - | - | 여신 신청 정보에 대한 CMP 필드 접근자 중 하나로, 여신 신청에 기록된 loanPurpose(대출 목적) 값을 조회하기 위한 계약을 정의한다. 호출자는 저장된 loanPurpose 값을 문자열 형태로 받아, 신청 건의 목적을 화면 표시나 후속 판단 로직에 활용할 수 있다. 값 조회만 수행하며 데이터의 생성·수정·삭제 등 상태 변경 의도는 없다. |
| setLoanPurpose | void setLoanPurpose(String loanPurpose) | - | - | 이 컴포넌트 인터페이스는 여신 신청 정보에 대한 CMP 필드 접근자를 정의하며, 그중 하나로 loanPurpose(대출목적)를 변경하기 위한 쓰기 동작을 제공한다. 외부에서 전달된 대출목적 값을 여신 신청 정보에 저장될 loanPurpose 필드에 설정하여 이후 영속 상태에 반영되도록 한다. 조회 목적이 아니라 신청 정보의 내용(대출목적)을 갱신하는 의도가 중심인 동작이다. |
| getTerm | int getTerm() | - | - | 여신 신청 정보에 대한 CMP 필드 접근자 중, term(기간/회차에 해당하는 값)을 정수로 조회하기 위한 선언이다. 호출자는 저장된 여신 신청 데이터에서 해당 기간 정보를 읽어 후속 심사/계산 등의 판단 자료로 활용한다. 이 선언은 값을 갱신하거나 상태를 변경하지 않고, 읽기 목적의 조회 인터페이스만 제공한다. |
| setTerm | void setTerm(int term) | - | - | 이 코드는 여신 신청 정보에 대한 CMP 필드 접근자를 정의하는 로컬 컴포넌트 인터페이스의 일부로, 여신 신청 데이터의 term(기간/회차 등으로 해석되는 값)을 설정하기 위한 변경용 계약을 제공한다. 정수 값으로 전달된 term을 해당 신청 정보의 저장 대상 필드에 반영하도록 정의되어, 이후 영속 상태가 갱신되는 흐름에 사용된다. 구현은 포함되어 있지 않으며, 호출 측이 term 값을 지정해 신청 정보의 상태를 변경하는 용도로 사용된다. |
| getInterestRate | BigDecimal getInterestRate() | - | - | 여신 신청 정보에 대한 CMP 필드 접근자를 정의하는 로컬 컴포넌트 인터페이스의 일부로, 여신 신청 데이터에서 interestRate(이자율) 값을 읽기 위해 제공되는 조회용 접근자 선언이다. 호출자는 별도 입력 없이 저장된 interestRate 값을 숫자형으로 획득해 이자 산정, 금리 표시, 심사/약정 조건 확인 등의 후속 처리에 활용할 수 있다. 구현체는 엔티티의 영속 상태로부터 해당 필드 값을 반환하는 것을 전제로 하며, 이 선언 자체는 상태를 변경하지 않는다. |
| setInterestRate | void setInterestRate(BigDecimal interestRate) | - | - | 여신 신청 정보를 표현하는 로컬 컴포넌트 인터페이스에서, CMP 방식으로 관리되는 interestRate(이자율) 값을 갱신하기 위한 쓰기 접근자를 정의한다. 입력으로 전달된 이자율 값을 해당 여신 신청 정보의 상태로 반영하여 이후 저장/영속화 대상 필드 값으로 사용되도록 한다. 반환값 없이 값 설정만 수행하는 형태로, 여신 신청 정보의 이자율을 변경하는 목적이 명확하다. |
| getStatus | String getStatus() | - | - | 여신 신청 정보에 대한 CMP 필드 접근자를 제공하는 로컬 컴포넌트 인터페이스의 일부로, 신청 건의 status(상태) 값을 조회해 문자열로 반환한다. 이 접근자는 저장된 여신 신청 레코드의 현재 처리 상태(예: 접수/심사/승인/거절 등으로 표현될 수 있는 상태)를 외부에서 읽을 수 있도록 하기 위한 목적이다. 입력 파라미터 없이 동작하며, 상태 값을 변경하거나 추가 로직을 수행하지 않고 단순 조회 결과만 제공한다. |
| setStatus | void setStatus(String status) | - | - | 여신 신청 정보에 대한 CMP 필드 접근자를 정의하는 로컬 컴포넌트 인터페이스의 일부로, 여신 신청의 처리 상태를 나타내는 status 값을 변경하기 위한 쓰기 동작을 제공한다. 외부에서 전달된 상태 문자열을 status(상태) 필드에 설정하여, 신청 건의 현재 진행 상태를 갱신할 수 있게 한다. 이 설정은 엔티티의 상태 변경 의도를 가지므로, 저장 대상 데이터의 값이 업데이트되는 전제의 동작이다. |
| getScreeningResult | String getScreeningResult() | - | - | 이 구성요소는 여신 신청 정보에 대한 CMP 필드 접근자를 제공하는 로컬 컴포넌트 인터페이스의 일부이다. 이 항목은 여신 신청 건에 대해 사전에 산출되거나 저장된 심사 결과를 문자열 형태로 조회해 반환하는 역할을 한다. 입력 파라미터 없이 호출되며, 조회된 심사 결과 값 자체를 그대로 반환하는 읽기 목적의 접근자에 해당한다. |
| setScreeningResult | void setScreeningResult(String screeningResult) | - | - | 여신 신청 정보에 대한 CMP 필드 접근자를 정의하는 로컬 컴포넌트 인터페이스의 일부로, 여신 신청 건의 screeningResult(심사결과) 값을 변경하기 위한 쓰기용 계약을 선언한다. 호출 측은 심사 처리 결과를 문자열로 전달하여 해당 신청 건에 반영하도록 의도되어 있다. 구현체에서는 전달된 screeningResult가 엔티티의 지속 상태에 기록되어 이후 조회나 후속 업무 판단에 사용될 수 있다. |
| getScreeningDate | Date getScreeningDate() | - | - | 여신 신청 정보에 대한 CMP 필드 접근자를 정의하는 로컬 컴포넌트 인터페이스의 일부로, screeningDate(심사일자) 값을 조회하기 위한 읽기 전용 접근을 제공한다. 호출자는 이 값을 통해 해당 여신 신청 건의 심사가 수행되었거나 기준이 되는 일자를 확인할 수 있다. 반환값은 날짜/시간을 표현하는 Date 형태이며, 상태 변경이나 저장 동작은 포함하지 않는다. |
| setScreeningDate | void setScreeningDate(Date screeningDate) | - | - | 이 인터페이스는 여신 신청 정보에 대한 CMP 필드 접근자를 정의하며, 그중 screeningDate(심사일자) 값을 기록하기 위한 설정 동작을 제공한다. 호출자가 전달한 심사일자를 screeningDate 필드에 반영하여, 이후 처리에서 심사 수행 시점을 기준으로 판단하거나 이력성 정보로 활용할 수 있게 한다. 별도의 검증이나 변환 로직 없이 입력으로 받은 날짜 값을 그대로 상태에 설정하는 성격이다. |
| getApprovedAmount | BigDecimal getApprovedAmount() | - | - | 이 인터페이스는 여신 신청 정보에 대한 CMP 필드 접근자를 정의하여, 여신 신청 엔티티의 주요 속성을 외부에서 일관되게 조회할 수 있도록 한다. 이 범위의 선언은 여신 신청 정보 중 approvedAmount(승인금액)을 숫자형(BigDecimal)으로 반환해 승인된 금액 값을 읽어갈 수 있게 한다. 별도의 계산, 검증, 상태 변경 없이 승인금액 값을 조회하는 목적의 접근자다. |
| setApprovedAmount | void setApprovedAmount(BigDecimal approvedAmount) | - | - | 이 코드는 여신 신청 정보에 대한 CMP 필드 접근자를 정의하는 로컬 컴포넌트 인터페이스의 일부로, 여신 신청 엔티티의 상태를 갱신하기 위한 설정 동작을 제공한다. 입력으로 전달된 금액 값을 approvedAmount(승인금액) 필드에 반영하도록 정의되어, 승인된 여신 금액을 엔티티 상태로 확정하는 데 사용된다. 반환값은 없으며, 승인금액 변경이라는 상태 변경 의도를 갖는 쓰기 작업이다. |
| getApproverEmployeeId | String getApproverEmployeeId() | - | - | 여신 신청 정보에 대한 CMP 필드 접근자를 제공하는 로컬 컴포넌트 인터페이스의 일부로, 결재자 사번(approverEmployeeId)을 조회하기 위한 반환 전용 접근자이다. 호출자는 여신 신청 건에 설정된 결재자 직원 식별값을 문자열로 받아, 결재 라인 확인이나 승인 처리 흐름에서 결재 담당자 식별에 활용할 수 있다. 입력 파라미터 없이 현재 엔티티에 저장된 approverEmployeeId 값을 그대로 반환하며, 저장/갱신 같은 상태 변경은 수행하지 않는다. |
| setApproverEmployeeId | void setApproverEmployeeId(String approverEmployeeId) | - | - | 이 컴포넌트 인터페이스는 여신 신청 정보에 대한 CMP 필드 접근자를 정의하며, 해당 범위는 approverEmployeeId(승인자 사원ID) 값을 엔티티의 상태로 반영하기 위한 설정 동작을 제공한다. 외부에서 전달된 승인자 식별자를 여신 신청 정보에 기록(갱신)함으로써, 해당 신청 건의 승인 담당자를 변경하거나 지정하는 목적을 가진다. 반환값이 없고 값 설정 자체가 목적이므로 조회가 아닌 상태 변경 성격의 동작이다. |
| getRemarks | String getRemarks() | - | - | 여신 신청 정보에 대한 CMP 필드 접근자를 제공하는 로컬 컴포넌트 인터페이스의 일부로, 여신 신청 정보에 포함된 remarks(비고) 값을 읽어오는 용도의 접근자이다. 입력 파라미터 없이 호출 시 비고에 해당하는 문자열 값을 반환하며, 조회 목적의 읽기 동작만 수행한다. 데이터 저장·수정·삭제와 같은 상태 변경은 수행하지 않고, 비고 필드의 현재 값을 외부에 제공하는 역할에 집중한다. |
| setRemarks | void setRemarks(String remarks) | - | - | 이 구성요소는 여신 신청 정보에 대한 CMP 필드 접근자를 정의하여, 엔티티에 저장되는 신청 데이터를 조작할 수 있도록 한다. 이 구간은 비고(remarks) 값을 입력받아 여신 신청 정보의 해당 필드를 설정(갱신)하기 위한 쓰기용 접근자 계약을 선언한다. 실제 저장/영속화 동작은 구현체 및 컨테이너가 처리하며, 여기서는 비고 값 변경 의도를 인터페이스 수준에서 명확히 규정한다. |

#### 필드

| 이름 | 타입 | 수정자 | 요약 |
| --- | --- | --- | --- |
| - | - | - | - |

#### 구조 관계

| 방향 | 관계 | 대상 | 속성 |
| --- | --- | --- | --- |
| ← | DEPENDENCY | LoanApplicationLocalHome | source_member=findByPrimaryKey, usage=return |
| ← | DEPENDENCY | LoanApplicationLocalHome | source_member=create, usage=return |
| ← | DEPENDENCY | LoanApplicationSessionBean | source_member=entitiesToDTOs, usage=cast |
| ← | DEPENDENCY | LoanApplicationSessionBean | source_member=getApplication, usage=local_var |
| ← | DEPENDENCY | LoanApplicationSessionBean | source_member=submitApplication, usage=local_var |
| ← | DEPENDENCY | LoanApplicationSessionBean | source_member=updateApplication, usage=local_var |
| ← | DEPENDENCY | LoanApplicationSessionBean | source_member=createApplication, usage=local_var |
| ← | DEPENDENCY | LoanExecutionSessionBean | source_member=executeLoan, usage=local_var |
| ← | DEPENDENCY | LoanScreeningSessionBean | source_member=rejectApplication, usage=local_var |
| ← | DEPENDENCY | LoanScreeningSessionBean | source_member=performScreening, usage=local_var |

#### 호출 관계

| 방향 | 대상 | 호출코드 |
| --- | --- | --- |
| ← | LoanApplicationSessionBean | - |
| ← | LoanExecutionSessionBean | - |
| ← | LoanScreeningSessionBean | - |

#### 데이터 접근

| 대상 | 관계 | 근거 | 신뢰도 |
| --- | --- | --- | --- |
| - | - | - | - |

#### 요약 코드

```
없음
```

### LoanApplicationLocalHome

#### 기본 정보

| 항목 | 값 |
| --- | --- |
| 이름 | LoanApplicationLocalHome |
| 타입 | CLASS |
| FQN | com.banking.loan.entity.LoanApplicationLocalHome |
| 패키지 | com.banking.loan.entity |
| 스테레오타입 | COMMAND/READMODEL |
| 파일 | - |
| 라인 | - |
| 토큰 | - |

#### 요약

> com.banking.loan.entity.LoanApplicationLocalHome는 여신 신청 엔티티 빈의 로컬 홈 인터페이스로서, 여신 신청의 생성 및 조회를 위한 메서드 계약을 정의한다. applicationId(신청 식별자), customerId(고객 식별자), applicationDate(신청일자), requestedAmount(요청금액), loanType(대출유형), loanPurpose(대출목적), term(기간), interestRate(이자율)로 여신 신청을 생성하고, 생성 실패 시 생성 예외로 처리하도록 한다. 또한 신청 식별자(기본키)로 단건 조회, 전체 목록 조회, customerId 기준 다건 조회, status(상태) 기준 다건 조회를 제공하며, 조회 실패는 FinderException으로 호출자에게 전달한다.

#### 메서드

| 이름 | 시그니처 | 반환타입 | 수정자 | 요약 |
| --- | --- | --- | --- | --- |
| create | LoanApplicationLocal create(String applicationId, String customerId, Date applicationDate,                                 BigDecimal requestedAmount, String loanType, String loanPurpose,                                 int term, BigDecimal interestRate) throws CreateException | - | - | 이 구성요소는 주석에서 설명하듯 여신 신청의 생성 및 조회를 위한 인터페이스를 제공하며, 해당 범위는 여신 신청을 신규로 생성하는 계약을 정의한다. applicationId(신청 식별자), customerId(고객 식별자), applicationDate(신청일자), requestedAmount(요청금액), loanType(대출유형), loanPurpose(대출목적), term(기간), interestRate(이자율)를 입력으로 받아 여신 신청을 생성하고, 생성된 여신 신청 정보에 대한 필드 접근이 가능한 로컬 컴포넌트 인터페이스를 반환한다. 생성 과정에서 문제가 발생하면 생성 예외를 발생시켜 호출자가 생성 실패를 처리할 수 있게 한다. |
| findByPrimaryKey | LoanApplicationLocal findByPrimaryKey(String applicationId) throws FinderException | - | - | 여신 신청 엔티티 빈의 생성 및 조회를 제공하는 로컬 홈 수준에서, 입력으로 받은 신청 식별자(기본키)에 해당하는 여신 신청 정보를 찾아 반환한다. 조회 결과는 여신 신청 정보의 CMP 필드 접근자를 제공하는 로컬 컴포넌트 형태로 제공되어, 호출 측이 해당 신청 데이터에 접근할 수 있게 한다. 지정한 기본키에 해당하는 대상이 없거나 조회 과정에서 문제가 발생하면 FinderException을 통해 조회 실패를 알린다. |
| findAll | Collection findAll() throws FinderException | - | - | 이 로컬 홈 인터페이스는 여신 신청에 대해 생성 및 조회를 위한 기능을 정의하며, 이 선언은 그중 전체 목록 조회 역할을 담당한다. 저장된 모든 여신 신청을 한 번에 조회해 컬렉션 형태로 반환하도록 계약을 제공한다. 조회 과정에서 대상이 없거나 조회에 실패하는 등 탐색 관련 문제가 발생하면 FinderException으로 호출자에게 예외를 전달한다. |
| findByCustomerId | Collection findByCustomerId(String customerId) throws FinderException | - | - | 여신 신청 엔티티의 생성 및 조회 기능을 제공하는 로컬 홈 인터페이스에서, 고객ID(customerId)를 기준으로 여신 신청 정보를 조회하기 위한 조회 계약을 정의한다. 입력으로 받은 고객ID에 매칭되는 여신 신청 레코드들을 여러 건 반환할 수 있도록 컬렉션 형태로 결과를 돌려주는 것을 전제로 한다. 조회 과정에서 대상 식별 실패 또는 조회 처리 오류가 발생하면 FinderException을 통해 예외를 호출자에게 전파하도록 명시한다. |
| findByStatus | Collection findByStatus(String status) throws FinderException | - | - | 여신 신청의 생성 및 조회를 위한 로컬 홈 인터페이스에서, 특정 상태값을 조건으로 여신 신청들을 조회하기 위한 조회 연산을 정의한다. 입력으로 전달된 status(상태)에 해당하는 여신 신청들을 묶음 형태로 반환하도록 계약이 정해져 있다. 조회 과정에서 대상 식별/검색에 실패하는 경우 조회 실패 예외를 통해 호출자에게 오류를 전달한다. 이 연산은 데이터를 변경하지 않고 기존 여신 신청을 상태 기준으로 검색하는 목적에 집중한다. |

#### 필드

| 이름 | 타입 | 수정자 | 요약 |
| --- | --- | --- | --- |
| - | - | - | - |

#### 구조 관계

| 방향 | 관계 | 대상 | 속성 |
| --- | --- | --- | --- |
| → | DEPENDENCY | LoanApplicationLocal | source_member=findByPrimaryKey, usage=return |
| → | DEPENDENCY | LoanApplicationLocal | source_member=create, usage=return |
| ← | DEPENDENCY | LoanApplicationSessionBean | source_member=getLoanApplicationHome, usage=return |
| ← | DEPENDENCY | LoanApplicationSessionBean | source_member=getApplicationsByCustomer, usage=local_var |
| ← | DEPENDENCY | LoanApplicationSessionBean | source_member=submitApplication, usage=local_var |
| ← | DEPENDENCY | LoanApplicationSessionBean | source_member=updateApplication, usage=local_var |
| ← | DEPENDENCY | LoanApplicationSessionBean | source_member=getApplicationsByStatus, usage=local_var |
| ← | DEPENDENCY | LoanExecutionSessionBean | source_member=getLoanApplicationHome, usage=return |
| ← | DEPENDENCY | LoanExecutionSessionBean | source_member=executeLoan, usage=local_var |
| ← | DEPENDENCY | LoanScreeningSessionBean | source_member=rejectApplication, usage=local_var |
| ← | DEPENDENCY | LoanScreeningSessionBean | source_member=performScreening, usage=local_var |
| ← | DEPENDENCY | LoanScreeningSessionBean | source_member=getLoanApplicationHome, usage=return |

#### 호출 관계

| 방향 | 대상 | 호출코드 |
| --- | --- | --- |
| ← | LoanApplicationSessionBean | - |
| ← | LoanExecutionSessionBean | - |
| ← | LoanScreeningSessionBean | - |

#### 데이터 접근

| 대상 | 관계 | 근거 | 신뢰도 |
| --- | --- | --- | --- |
| LoanApplicationLocal | REFER_TO | - | 1.0 |
| LoanApplicationLocal | REFER_TO | - | 1.0 |

#### 요약 코드

```
없음
```

### LoanLedgerBean

#### 기본 정보

| 항목 | 값 |
| --- | --- |
| 이름 | LoanLedgerBean |
| 타입 | CLASS |
| FQN | com.banking.loan.entity.LoanLedgerBean |
| 패키지 | com.banking.loan.entity |
| 스테레오타입 | COMMAND/READMODEL |
| 파일 | - |
| 라인 | - |
| 토큰 | - |

#### 요약

> com.banking.loan.entity.LoanLedgerBean은 컨테이너가 영속성을 관리하는 CMP 기반의 여신 원장 엔티티 빈 구현으로, 여신 원장 정보를 저장·조회하고 계약/상환 조건을 엔티티 속성(ledgerId, applicationId, customerId, principalAmount(원금금액), interestRate(이자율), loanStartDate(대출시작일), maturityDate(만기일), repaymentMethod(상환방식), monthlyPayment(월별 납입금액) 등)으로 유지한다. 신규 생성 시 outstandingBalance(미지급잔액)는 principalAmount와 동일한 초기값으로 두고 status(상태)는 "ACTIVE"로 설정하며, 상환 시 상환 원금 금액만큼 outstandingBalance를 차감하고 lastRepaymentDate(최종상환일자)를 시스템 현재 시각으로 갱신하는 흐름을 가진다. 수동화/로딩/저장/삭제 등 엔티티 생명주기 훅(ejbPassivate/ejbLoad/ejbStore/ejbRemove)은 모두 비어 있어 추가 검증·변환·정리 없이 컨테이너의 기본 동작에 위임하고, 컨테이너와의 상호작용을 위해 EntityContext 참조(entityContext)를 보관한다.

#### 메서드

| 이름 | 시그니처 | 반환타입 | 수정자 | 요약 |
| --- | --- | --- | --- | --- |
| getLedgerId | - | - | - | 컨테이너가 영속성을 관리하는 여신 원장 정보 저장·조회 컴포넌트에서, 여신 원장을 식별하는 ledgerId를 문자열로 제공하도록 강제하는 추상 접근자 선언이다. 구현체는 영속 상태에 저장된 여신 원장 식별값을 읽어 반환해야 하며, 이를 통해 외부 로직이 해당 원장 레코드를 구분해 조회·연계할 수 있게 된다. 이 범위에는 값 변경이나 저장 동작이 없고 식별자 조회 목적만 가지므로 읽기 성격이 중심이다. |
| setLedgerId | - | - | - | 컨테이너가 영속성을 관리하는 여신 원장 정보 저장·조회 컴포넌트에서, 원장 식별자인 ledgerId(원장ID)를 엔티티 상태에 설정하는 동작의 계약을 정의한다. 입력으로 받은 ledgerId 값을 내부에 반영함으로써 이후 저장(영속화) 또는 갱신 시 해당 원장 레코드를 식별할 수 있게 한다. 구현은 추상으로 선언되어 있어, 실제 값 반영 방식과 영속성 연동은 구체 구현(또는 컨테이너 제공 구현)에 위임된다. |
| getApplicationId | - | - | - | 이 구성요소는 컨테이너가 영속성을 관리하는 여신 원장 정보를 저장·조회하기 위한 CMP 기반 구현에 속하며, 그 중 여신 원장 레코드를 식별하는 applicationId(신청 ID) 값을 읽어오기 위한 접근 지점을 정의한다. 구현이 추상으로 선언되어 있어, 실제 값의 로딩과 저장은 컨테이너가 영속성 매핑을 통해 처리하도록 의도되어 있다. 반환되는 값은 문자열 형태의 식별자이며, 조회 목적의 읽기 동작만 수행하고 데이터 상태를 변경하지 않는다. |
| setApplicationId | - | - | - | 컨테이너가 영속성을 관리하는 여신 원장 정보를 저장·조회하는 구성요소에서, 원장 데이터의 applicationId(신청 식별자)를 설정하기 위한 변경 계약을 선언한다. 구현체는 전달받은 applicationId 값을 해당 원장 레코드의 상태로 반영하여 이후 저장/조회 시 일관되게 사용되도록 해야 한다. 추상 선언만 존재하므로 이 범위에서는 값 검증, 변환, 외부 호출 없이 설정 동작의 책임만 규정한다. |
| getCustomerId | - | - | - | 여신 원장 정보를 저장·조회하는 CMP 엔티티 빈 구현의 일부로, 고객을 식별하기 위한 customerId(고객식별자)를 문자열로 반환하는 조회용 접근 지점을 선언한다. 구현은 추상으로만 정의되어 있어 실제 customerId 값을 어디에서 어떻게 제공할지는 구체 구현체에 위임된다. 이 선언 자체는 영속 상태를 변경하지 않으며, 고객 식별자 값을 외부에서 읽어갈 수 있도록 계약(인터페이스)을 제공하는 목적이다. |
| setCustomerId | - | - | - | 여신 원장 정보를 컨테이너가 영속성으로 관리하는 구성요소에서, 고객을 식별하는 customerId 값을 엔티티 상태에 반영(설정)하기 위한 추상 동작을 선언한다. 구현체는 입력으로 받은 customerId를 내부 저장 대상(여신 원장 정보)의 해당 속성에 기록하여 이후 저장·조회 시 고객 식별 기준으로 활용되도록 한다. 이 범위에서는 값의 검증, 조회, 외부 호출 없이 customerId 변경이라는 상태 갱신 의도만을 정의한다. |
| getPrincipalAmount | - | - | - | 컨테이너가 영속성을 관리하는 여신 원장 정보 저장·조회 구성요소에서, 원장에 기록되는 principalAmount(원금금액)을 외부에 제공하기 위한 조회용 접근 계약을 정의한다. 금액은 BigDecimal로 반환되도록 규정되어 통화/정밀도 손실 없이 원금 규모를 표현할 수 있게 한다. 구현은 하위 구현체(또는 컨테이너 생성 프록시)에 위임되며, 이 선언 자체는 상태 변경 없이 값 조회 목적만 가진다. |
| setPrincipalAmount | - | - | - | 여신 원장 정보를 영속적으로 저장·조회하는 컴포넌트의 일부로, 원장 데이터 중 principalAmount(원금금액)를 설정하기 위한 추상 계약을 정의한다. 호출자는 원금금액을 나타내는 값을 전달하며, 구현체는 이를 해당 원장 인스턴스의 상태에 반영하도록 설계되어 있다. 메서드가 추상으로 선언되어 있어 실제 저장 방식이나 변경 반영 시점은 구현 클래스/컨테이너의 영속성 관리 규칙에 의해 결정된다. |
| getOutstandingBalance | - | - | - | 여신 원장 정보를 저장·조회하는 영속 객체의 계약으로서, 미결(미상환) 잔액을 조회하기 위한 값을 제공하도록 정의한다. 반환값은 금액 계산에 적합한 BigDecimal 형태의 잔액이며, 실제 산정/조회 방식은 구현체에 위임된다. 이 선언 자체는 상태를 변경하지 않고, 여신 원장에 대한 현재 잔액 값을 읽어오는 목적의 조회 인터페이스 역할을 한다. |
| setOutstandingBalance | - | - | - | 이 클래스는 컨테이너가 영속성을 관리하는 여신 원장 정보를 저장·조회하기 위한 엔티티 빈 구현을 전제로 한다. 이 추상 메서드는 outstandingBalance(미지급잔액/미결제잔액)에 해당하는 값을 외부에서 전달받아 엔티티의 해당 속성에 반영하도록 계약을 정의한다. 구현체는 전달된 금액을 엔티티 상태로 설정함으로써, 이후 영속화 과정에서 여신 원장 잔액 정보가 갱신되도록 한다. 조회가 아니라 특정 금액 속성을 변경하는 쓰기 동작을 표현한다. |
| getInterestRate | - | - | - | 여신 원장 정보를 저장·조회하는 컴포넌트의 일부로, 여신 원장 데이터에 포함된 이자율 값을 조회하기 위한 접근 지점을 정의한다. 반환값은 금액/비율 계산에 적합한 고정소수 정밀도의 숫자 타입으로 제공되며, 이자율 산정·표시 등 후속 처리에서 정밀도 손실을 줄이려는 의도가 반영되어 있다. 구현은 선언되어 있지 않아, 실제 이자율의 영속 저장소 연동 및 값 제공 방식은 구체 구현 클래스에 위임된다. |
| setInterestRate | - | - | - | 이 코드는 컨테이너가 영속성을 관리하는 여신 원장 정보의 저장·조회 책임을 가진 구성요소에서, 여신 원장 데이터의 interestRate(이자율) 값을 변경하기 위한 설정 동작을 정의한다. 입력으로 받은 이자율 값을 해당 원장 레코드의 이자율 속성에 반영하도록 의도되어 있으며, 실제 반영 방식은 구현체에 위임된다. 메서드 본문이 없는 추상 선언이므로 검증, 계산, 조회 같은 부가 로직 없이 ‘이자율 값을 갱신한다’는 계약만 제공한다. |
| getLoanStartDate | - | - | - | 여신 원장 정보를 컨테이너가 영속성으로 관리하는 구성요소에서, 저장된 원장 레코드의 대출 개시일을 제공하기 위한 추상 조회 인터페이스를 정의한다. 호출자는 영속 상태에 있는 원장 정보로부터 대출 시작일을 Date 형태로 읽어갈 수 있다. 실제 값의 로딩/반환 방식은 구체 구현(컨테이너 또는 하위 구현)에 위임되어, 저장된 데이터에서 대출 개시일을 조회하는 역할에 집중한다. |
| setLoanStartDate | - | - | - | 이 클래스는 컨테이너가 영속성을 관리하는 여신 원장 정보를 저장·조회하기 위한 CMP 구현을 담당하며, 그중 원장 속성 값을 갱신하는 계약을 제공한다. 이 코드는 loanStartDate(대출시작일)를 입력받아 해당 엔티티의 상태에 반영하도록 정의된 추상 설정자이다. 구현체에서는 이 값이 원장 데이터의 영속 상태로 저장되도록 연결되어, 대출 시작일의 변경을 엔티티 수준에서 표현할 수 있게 한다. 메서드 본문이 없으므로 검증, 변환, 예외 처리 없이 값 설정 책임만 인터페이스 형태로 분리되어 있다. |
| getMaturityDate | - | - | - | 이 구성요소는 컨테이너가 영속성을 관리하는 여신 원장 정보의 저장·조회 책임을 전제로 하며, 그 중 만기일 정보를 제공하기 위한 조회용 계약을 정의한다. 호출자는 원장 레코드에 설정된 만기일을 Date 형태로 받아 상환/만기 도래 여부 판단, 만기 기준 조회 조건 구성 등의 용도로 활용할 수 있다. 구현은 하위 구현체에 위임되며, 이 선언 자체는 상태 변경 없이 만기일 값을 반환하는 읽기 동작만을 의도한다. |
| setMaturityDate | - | - | - | 이 클래스는 컨테이너가 영속성을 관리하는 여신 원장 정보를 저장·조회하기 위한 CMP 엔티티 빈 구현을 전제로 하며, 여기서는 여신 원장 데이터의 maturityDate(만기일)를 변경하기 위한 설정 동작을 정의한다. 입력으로 받은 만기일 값을 엔티티의 해당 속성에 반영하도록 강제하여, 이후 영속성 컨테이너가 변경 내용을 저장 대상으로 인식할 수 있게 한다. 메서드가 추상으로 선언되어 있어 실제 값 반영과 영속화 동작은 구체 구현 클래스/컨테이너 규약에 따라 수행된다. |
| getRepaymentMethod | - | - | - | 이 구성요소는 컨테이너가 영속성을 관리하는 여신 원장 정보를 저장·조회하기 위한 구현에서 사용되며, 여기서는 상환 방식 값을 제공하기 위한 조회용 접근 지점을 정의한다. 상환 방식은 문자열 형태로 반환되며, 실제 값의 제공 방식(영속 저장소에서 로딩되는지, 계산되는지 등)은 하위 구현에서 결정된다. 본 범위에는 상태 변경 로직이 없고, 특정 상환 방식 값을 읽어 외부에 제공하는 목적만 갖는다. |
| setRepaymentMethod | - | - | - | 이 구성요소는 컨테이너가 영속성을 관리하는 여신 원장 정보의 저장·조회 책임 맥락에서 동작한다. 이 선언은 여신 원장 레코드에 대한 repaymentMethod(상환방식)를 외부 입력 문자열로 설정(변경)하기 위한 동작을 정의하며, 구체적인 저장 방식은 구현체에 위임한다. 구현 시에는 repaymentMethod 값이 변경되어 이후 영속 상태에 반영될 수 있도록 하는 것이 목적이다. |
| getMonthlyPayment | - | - | - | 여신 원장 정보를 컨테이너가 영속성으로 관리하는 구성요소에서, 월별 납입금액을 조회하기 위한 반환 계약을 선언한다. 구현체가 월별 납입금액을 금액형으로 계산하거나 저장된 값을 읽어 반환하도록 강제하며, 이 선언 자체는 계산/조회 로직을 포함하지 않는다. 반환값은 월별 납입금액을 정밀한 금액 표현으로 제공하는 것을 전제로 한다. |
| setMonthlyPayment | - | - | - | 컨테이너가 영속성을 관리하는 여신 원장 정보에서 월별 납입금액(monthlyPayment)을 변경하기 위한 설정 동작을 정의한다. 입력으로 전달된 금액을 해당 속성에 반영하는 것을 목표로 하지만, 구현은 제공되지 않고 추상 계약만 선언되어 있다. 따라서 실제 값의 저장·반영 방식은 이를 구현하는 쪽(컨테이너 또는 구체 구현 클래스)에 위임된다. |
| getStatus | - | - | - | 컨테이너가 영속성을 관리하는 여신 원장 정보의 저장·조회 책임을 가진 구성요소에서, 원장 정보의 현재 상태값을 문자열로 제공하기 위한 조회용 계약(추상 동작)을 선언한다. 실제 상태값이 어떤 형식으로 계산·보관되는지는 구현체가 결정하며, 이 선언 자체는 상태를 변경하거나 영속화 작업을 수행하지 않는다. 조회된 상태 문자열은 원장 정보의 상태를 외부 로직이 판단하거나 표시하는 데 사용될 수 있다. |
| setStatus | - | - | - | 이 구성요소는 컨테이너가 영속성을 관리하는 여신 원장 정보를 저장·조회하는 구현의 일부이며, 원장 레코드의 status(상태) 값을 변경하기 위한 계약을 선언한다. 외부에서 전달된 상태 문자열을 해당 원장 정보에 반영해 상태 전이를 표현하도록 의도되어 있다. 구현은 추상화되어 있어 실제로 어떤 저장 규칙(검증, 상태코드 정규화, 영속 반영)을 적용할지는 하위 구현에서 결정된다. |
| getLastRepaymentDate | - | - | - | 여신 원장 정보를 컨테이너가 영속적으로 관리하는 구성요소에서, 여신 원장에 기록된 최종 상환일을 조회해 날짜로 반환하는 계약을 정의한다. 구현은 제공되지 않은 추상 선언이므로, 실제 값은 구체 구현에서 영속 저장소에 보관된 여신 원장 데이터로부터 읽어와야 한다. 반환된 날짜는 상환 이력의 최신 시점을 나타내어 이후 이자 계산이나 연체 판정 등 조회성 판단에 활용될 수 있다. |
| setLastRepaymentDate | - | - | - | 이 코드는 컨테이너가 영속성을 관리하는 여신 원장 정보를 저장·조회하는 구성요소 안에서, lastRepaymentDate(최종상환일자) 값을 변경하기 위한 설정 동작을 정의한다. 입력으로 받은 날짜 값을 lastRepaymentDate에 반영하여 여신 원장 정보의 상태(최종 상환일자)를 갱신하는 목적을 가진다. 구현이 추상으로 선언되어 있어, 실제로 영속 저장소에 어떻게 반영되는지는 구체 구현(또는 컨테이너 제공 구현)에 의해 결정된다. |
| getNextRepaymentDate | - | - | - | 컨테이너가 영속성을 관리하는 여신 원장 정보에서 ‘다음 상환일’을 조회하기 위한 접근자를 선언한다. 반환값은 날짜 타입이며, 호출자는 원장에 저장된 다음 상환 예정일 정보를 읽어 상환 스케줄 확인이나 후속 업무 판단에 활용할 수 있다. 구현이 추상으로 선언되어 있어, 실제 값의 조회·매핑 방식(예: 영속 필드/컬럼 매핑)은 컨테이너 또는 구체 구현에 의해 제공된다. 데이터 변경이나 저장을 수행하지 않고, 읽기 목적의 값 제공에 집중한다. |
| setNextRepaymentDate | - | - | - | 이 클래스는 컨테이너가 영속성을 관리하는 여신 원장 정보를 저장·조회하기 위한 구성요소이며, 그중 다음 상환일(nextRepaymentDate) 값을 변경할 수 있도록 하는 설정 동작을 정의한다. 외부에서 전달된 날짜 값을 여신 원장 레코드의 다음 상환일 속성에 반영하는 것이 목적이며, 이를 통해 상환 일정 변경이나 갱신 결과를 원장 상태에 기록할 수 있게 한다. 구현은 추상으로 선언되어 있어 실제 저장 반영 방식은 컨테이너/구현체가 제공하고, 이 선언 자체에는 추가 검증·분기·호출 로직이 포함되지 않는다. |
| applyRepayment | public void applyRepayment(BigDecimal principalPaid, BigDecimal interestPaid) | - | - | 컨테이너가 영속성을 관리하는 여신 원장 정보를 저장·조회하는 구성요소 안에서, 상환 발생 시 원장 상태를 갱신하는 처리를 수행한다. 입력으로 받은 상환 원금 금액만큼 outstandingBalance(미지급잔액/미결제잔액)를 현재 잔액에서 차감하여 outstandingBalance를 감소시킨다. 이어서 lastRepaymentDate(최종상환일자)를 시스템 현재 시각으로 설정해 최종 상환 시점을 갱신한다. 이 과정에서 상환 이자 금액 입력은 잔액/일자 갱신에 사용되지 않아, 원금 기준으로만 잔액이 조정된다. |
| ejbCreate | public String ejbCreate(String ledgerId, String applicationId, String customerId,                             BigDecimal principalAmount, BigDecimal interestRate,                             Date loanStartDate, Date maturityDate,                             String repaymentMethod, BigDecimal monthlyPayment) throws CreateException | - | - | 컨테이너가 영속성을 관리하는 여신 원장 정보를 신규로 생성할 때, 입력으로 받은 원장 식별값(ledgerId), 신청 식별자(applicationId), 고객 식별자(customerId)와 금액·기간·상환 조건을 엔티티 상태로 확정 설정한다. principalAmount(원금금액)를 등록하면서 outstandingBalance(미지급잔액)는 초기값으로 principalAmount와 동일하게 설정해 최초 생성 시점의 잔액을 원금 기준으로 맞춘다. 이어서 interestRate(이자율), loanStartDate(대출시작일), maturityDate(만기일), repaymentMethod(상환방식), monthlyPayment(월별 납입금액)을 저장 대상 상태로 반영한다. 마지막으로 status(상태)를 "ACTIVE"로 설정해 생성 직후 원장을 활성 상태로 시작하도록 하고, 생성 결과로는 식별자 객체를 별도로 반환하지 않는다(null 반환). |
| ejbPostCreate | public void ejbPostCreate(String ledgerId, String applicationId, String customerId,                               BigDecimal principalAmount, BigDecimal interestRate,                               Date loanStartDate, Date maturityDate,                               String repaymentMethod, BigDecimal monthlyPayment) | - | - | 이 코드는 컨테이너가 영속성을 관리하는 여신 원장 정보 저장·조회 컴포넌트의 생성 라이프사이클 후처리 구간으로, 생성 직후 추가 작업을 수행하기 위한 진입점이다. 입력으로 원장 식별자(ledgerId), 신청 식별자(applicationId), 고객 식별자(customerId), principalAmount(원금), interestRate(이자율), loanStartDate(대출 시작일), maturityDate(만기일), repaymentMethod(상환방법), monthlyPayment(월 상환액) 등 원장 등록에 필요한 핵심 속성들을 전달받는다. 그러나 본문이 비어 있어, 전달된 값에 대한 검증, 상태 확정, 추가 영속화, 외부 호출 등 어떤 후처리도 수행하지 않는다. 결과적으로 생성 직후 후속 로직이 필요 없거나 다른 구간에서 처리된다는 설계를 반영한다. |
| setEntityContext | public void setEntityContext(EntityContext ctx) | - | - | 여신 원장 정보를 저장·조회하는 CMP 엔티티 빈 구현체에서, 컨테이너가 제공하는 영속성 실행 컨텍스트를 인스턴스에 주입해 이후 영속성 관련 처리에서 사용할 수 있도록 보관한다. 입력으로 전달된 컨텍스트 참조를 내부 보관 영역에 그대로 대입하며, 별도의 검증이나 변환은 수행하지 않는다. 이 설정을 통해 컨테이너가 관리하는 영속성 리소스에 접근하기 위한 준비 상태를 갖춘다. |
| unsetEntityContext | public void unsetEntityContext() | - | - | 여신 원장 정보를 영속성으로 저장·조회하는 컴포넌트에서, 컨테이너가 주입·관리하던 영속성 컨텍스트 참조를 명시적으로 해제한다. 내부에 보관 중인 컨텍스트 객체를 null로 설정해 더 이상 해당 실행 흐름에서 컨텍스트에 접근하지 못하게 만든다. 이를 통해 인스턴스가 들고 있던 컨테이너 컨텍스트 연결을 끊어, 생명주기 종료나 재설정 시 잔존 참조로 인한 오동작을 방지하는 목적의 상태 변경을 수행한다. |
| ejbActivate | public void ejbActivate() | - | - | 컨테이너가 패시베이션 상태의 인스턴스를 다시 메모리에 올려 활성화할 때 호출되는 생명주기 콜백을 제공한다. 본문이 비어 있어 활성화 시점에 수행하는 초기화, 리소스 재연결, 상태 복구 같은 처리가 정의되어 있지 않다. 따라서 여신 원장 정보를 저장·조회하는 영속성 관리 흐름이나 엔티티 컨텍스트 접근에도 영향을 주지 않는다. |
| ejbPassivate | public void ejbPassivate() | - | - | 이 구성요소는 컨테이너가 영속성을 관리하는 여신 원장 정보의 저장·조회 책임을 가지며, 여기서는 세션/인스턴스가 수동화(passivation)될 때 호출되는 생명주기 훅을 제공한다. 수동화 시점에 필요한 자원 정리, 컨텍스트 해제, 캐시 플러시 등의 처리를 수행할 수 있는 위치이지만, 실제 구현은 비어 있어 어떤 동작도 하지 않는다. 따라서 수동화 과정에서 추가적인 상태 변경이나 외부 자원 접근 없이 컨테이너의 기본 동작에만 의존한다. |
| ejbLoad | public void ejbLoad() | - | - | 이 코드는 컨테이너가 영속성을 관리하며 여신 원장 정보를 저장·조회하는 CMP 기반 구현의 생명주기 단계 중, 저장소로부터 데이터가 적재되는 시점에 호출되는 로딩 훅에 해당한다. 구현은 비어 있어, 로딩 시 추가 검증·변환·연관 데이터 조회 같은 후처리를 수행하지 않고 컨테이너의 자동 매핑/적재에 전적으로 의존한다. 따라서 이 범위에서는 상태 변경이나 조회 로직을 직접 실행하지 않으며, 외부 자원 접근도 발생하지 않는다. |
| ejbStore | public void ejbStore() | - | - | 여신 원장 정보를 저장·조회하는 CMP 기반 엔티티 빈 구현에서, 컨테이너가 영속화(저장)를 수행하는 시점에 호출되는 저장 콜백을 제공한다. 다만 본문이 비어 있어, 저장 시점에 추가 검증·변환·부가 저장 같은 별도 동작을 수행하지 않는다. 결과적으로 실제 데이터 반영은 컨테이너가 관리하는 영속성 메커니즘에 전적으로 위임되며, 애플리케이션 코드 수준의 상태 변경 로직은 포함되지 않는다. |
| ejbRemove | public void ejbRemove() throws RemoveException | - | - | 여신 원장 정보를 컨테이너가 영속성으로 관리·저장·조회하는 구성요소에서, 인스턴스 제거(삭제) 수명주기 시점에 호출되는 제거 처리 구간이다. 구현 내용이 비어 있어, 삭제 시 추가적인 정리 작업(연관 리소스 해제, 부가 검증, 로그 기록 등)은 수행하지 않고 컨테이너의 기본 제거/영속성 처리에 동작을 위임한다. 제거 과정에서 문제가 발생하면 제거 실패 예외가 호출자에게 그대로 전달될 수 있도록 선언되어 있다. |

#### 필드

| 이름 | 타입 | 수정자 | 요약 |
| --- | --- | --- | --- |
| entityContext | EntityContext | - | 컨테이너가 관리하는 CMP 엔티티 빈에서 엔티티의 실행·생명주기 컨텍스트를 보관해, 영속성 처리와 콜백 등 컨테이너와의 상호작용에 사용되는 EntityContext 참조를 담는다. |

#### 구조 관계

| 방향 | 관계 | 대상 | 속성 |
| --- | --- | --- | --- |
| → | ASSOCIATION | EntityContext | source_member=unsetEntityContext |
| → | DEPENDENCY | EntityContext | source_member=setEntityContext, usage=parameter |

#### 호출 관계

| 방향 | 대상 | 호출코드 |
| --- | --- | --- |
| → | LoanLedgerBean | 65:         setOutstandingBalance(getOutstandingBalance().subtract(principalPaid)); |
| → | LoanLedgerBean | 66:         setLastRepaymentDate(new Date(System.currentTimeMillis())); |
| → | LoanLedgerBean | 75:         setLedgerId(ledgerId); |
| → | LoanLedgerBean | 76:         setApplicationId(applicationId); |
| → | LoanLedgerBean | 77:         setCustomerId(customerId); |
| → | LoanLedgerBean | 78:         setPrincipalAmount(principalAmount); |
| → | LoanLedgerBean | 79:         setOutstandingBalance(principalAmount); |
| → | LoanLedgerBean | 80:         setInterestRate(interestRate); |
| → | LoanLedgerBean | 81:         setLoanStartDate(loanStartDate); |
| → | LoanLedgerBean | 82:         setMaturityDate(maturityDate); |
| → | LoanLedgerBean | 83:         setRepaymentMethod(repaymentMethod); |
| → | LoanLedgerBean | 84:         setMonthlyPayment(monthlyPayment); |
| → | LoanLedgerBean | 85:         setStatus("ACTIVE"); |

#### 데이터 접근

| 대상 | 관계 | 근거 | 신뢰도 |
| --- | --- | --- | --- |
| - | - | - | - |

#### 요약 코드

```
없음
```

### LoanLedgerLocal

#### 기본 정보

| 항목 | 값 |
| --- | --- |
| 이름 | LoanLedgerLocal |
| 타입 | CLASS |
| FQN | com.banking.loan.entity.LoanLedgerLocal |
| 패키지 | com.banking.loan.entity |
| 스테레오타입 | COMMAND/READMODEL |
| 파일 | - |
| 라인 | - |
| 토큰 | - |

#### 요약

> com.banking.loan.entity.LoanLedgerLocal은 여신 원장 엔티티 빈의 로컬 컴포넌트 인터페이스로, 여신 원장 정보에 대한 CMP 필드 접근자와 비즈니스 메서드 계약을 정의한다. 원장 레코드의 식별/연계 속성(ledgerId, applicationId, customerId), 금액 속성(principalAmount(원금금액), outstandingBalance(미결제/미상환 잔액), monthlyPayment(월 납입금)), 조건/기간(interestRate(이자율), loanStartDate(대출 시작일), maturityDate(만기일)), 상환조건(repaymentMethod(상환방식)), 상태(status(상태)) 및 상환 일정(lastRepaymentDate(최종상환일), nextRepaymentDate(다음 상환일))을 조회·갱신할 수 있도록 한다. 또한 상환 시 상환 원금 금액과 상환 이자 금액을 입력으로 받아 원장 내부 상태(잔액/상환 관련 정보)를 반영하는 상환 처리 동작을 제공하며, 다음 상환일(nextRepaymentDate)을 설정하는 쓰기 동작을 통해 상환 스케줄을 갱신한다.

#### 메서드

| 이름 | 시그니처 | 반환타입 | 수정자 | 요약 |
| --- | --- | --- | --- | --- |
| getLedgerId | String getLedgerId() | - | - | 여신 원장 정보에 대한 CMP 필드 접근자와 비즈니스 기능을 정의하는 로컬 컴포넌트 인터페이스의 일부로, 여신 원장의 식별자 값인 ledgerId를 조회해 반환한다. 호출자 입장에서는 현재 엔티티에 매핑된 원장 식별자를 읽어 도메인 식별 및 연계 처리에 활용할 수 있다. 반환 타입은 문자열이며, 내부 상태를 변경하거나 저장을 수행하지 않는 읽기 전용 성격의 동작이다. |
| getApplicationId | String getApplicationId() | - | - | 이 컴포넌트 인터페이스는 여신 원장 정보에 대한 CMP 필드 접근자와 업무 동작을 정의하는 목적을 가진다. 해당 선언은 여신 원장 레코드에 연계된 applicationId(애플리케이션 식별자)를 문자열로 조회해 반환하는 읽기 전용 접근자를 제공한다. 입력 파라미터 없이 현재 엔티티 상태에 저장된 식별자 값을 외부로 노출하는 역할이며, 상태 변경이나 저장/갱신 동작은 포함하지 않는다. |
| setApplicationId | void setApplicationId(String applicationId) | - | - | 여신 원장 정보에 대한 CMP 필드 접근자를 제공하는 로컬 컴포넌트 인터페이스의 일부로, 원장 데이터에 applicationId 값을 설정하기 위한 입력 지점을 정의한다. 외부에서 전달된 applicationId(애플리케이션 식별자)를 해당 원장 레코드의 필드로 반영하여, 이후 영속 상태에 저장될 값으로 확정하는 목적을 갖는다. 반환값 없이 값 설정만 수행하도록 계약을 명시해, 여신 원장 정보의 식별/연계 정보가 변경될 수 있음을 전제한다. |
| getCustomerId | String getCustomerId() | - | - | 이 컴포넌트 인터페이스는 여신 원장 정보에 대한 CMP 필드 접근자와 업무 메서드를 정의하며, 그중 이 선언은 여신 원장 레코드에 매핑된 customerId(고객식별자) 값을 조회하기 위한 읽기용 접근자를 제공한다. 호출자는 반환된 문자열을 통해 해당 원장 정보가 어떤 고객에 속하는지 식별할 수 있다. 입력 파라미터나 추가 로직 없이 저장된 customerId 값을 그대로 반환하는 형태로 사용된다. |
| setCustomerId | void setCustomerId(String customerId) | - | - | 이 컴포넌트는 여신 원장 정보에 대한 CMP 필드 접근자와 비즈니스 동작을 정의하며, 그중 고객 식별 정보인 customerId를 설정하기 위한 쓰기 접근자를 제공한다. 외부에서 전달된 customerId 값을 여신 원장 엔티티의 customerId 필드에 반영하도록 계약을 정의해, 엔티티 상태 변경을 가능하게 한다. 구현체에서는 이 값이 영속 상태로 관리되는 CMP 필드에 기록되는 것을 전제로 한다. |
| getPrincipalAmount | BigDecimal getPrincipalAmount() | - | - | 여신 원장 정보에 대한 CMP 필드 접근자와 비즈니스 기능을 정의하는 로컬 컴포넌트 인터페이스의 일부로, 여신 원장의 원금(principalAmount) 값을 조회하기 위한 읽기 전용 접근자를 선언한다. 호출자는 이 선언을 통해 원장에 저장된 원금 금액을 금액형으로 반환받아 화면 표시, 계산, 검증 등 후속 처리에 활용할 수 있다. 이 범위에는 상태 변경이나 외부 자원 접근 로직이 없으며, 값 조회 의도만을 가진다. |
| setPrincipalAmount | void setPrincipalAmount(BigDecimal principalAmount) | - | - | 여신 원장 정보에 대한 CMP 필드 접근자를 제공하는 로컬 컴포넌트 인터페이스의 일부로, 원장 데이터의 principalAmount(원금금액)을 변경하기 위한 설정 동작을 정의한다. 호출자는 원금에 해당하는 금액 값을 전달하며, 이 값은 해당 원장 레코드의 principalAmount 필드에 반영되는 것을 의도한다. 조회가 아니라 원장 엔티티의 상태(금액 속성)를 갱신하는 목적의 계약(시그니처)이다. |
| getOutstandingBalance | BigDecimal getOutstandingBalance() | - | - | 여신 원장 정보에 대해 CMP 필드 접근자 및 비즈니스 메서드를 제공하는 로컬 컴포넌트 인터페이스의 일부로, 여신 거래에서 아직 정리되지 않은 잔액(미상환/미결제 성격의 잔액)을 조회하기 위한 계약을 정의한다. 호출자는 이 연산을 통해 현재 시점의 미정산 잔액 값을 숫자형(소수 포함)으로 받아, 한도 관리·채권 관리·정산 판단 등에 활용할 수 있다. 이 범위에서는 계산 방식이나 데이터 소스는 노출되지 않으며, 구현체가 여신 원장 상태를 기반으로 잔액을 산출해 반환한다는 점만 인터페이스로 고정한다. |
| setOutstandingBalance | void setOutstandingBalance(BigDecimal outstandingBalance) | - | - | 여신 원장 정보에 대한 CMP 필드 접근자를 제공하는 로컬 컴포넌트 인터페이스의 일부로, outstandingBalance(미결제/미상환 잔액) 값을 외부에서 전달받아 엔티티 상태에 반영하도록 정의된 설정자 계약이다. 입력으로 주어진 잔액 금액을 기준으로 해당 원장 레코드의 outstandingBalance 필드를 갱신하는 목적을 가진다. 구현체에서는 이 값 변경이 영속 필드 변경으로 연결되어 원장 잔액 상태가 업데이트되도록 사용된다. |
| getInterestRate | BigDecimal getInterestRate() | - | - | 여신 원장 정보에 대한 CMP 필드 접근자와 비즈니스 동작을 정의하는 로컬 컴포넌트 인터페이스의 일부로, 여신 원장에 저장된 이자율 값을 조회하기 위한 접근자를 제공한다. 입력 파라미터 없이 호출되며, 원장에 등록된 이자율을 정밀한 수치형으로 반환해 이자 계산이나 조건 판단에 활용되도록 한다. 이 범위 내에서는 값의 계산·변환·검증이나 저장/갱신 같은 상태 변경은 수행하지 않고, 보관된 속성 값을 읽어 전달하는 역할에 집중한다. |
| setInterestRate | void setInterestRate(BigDecimal interestRate) | - | - | 여신 원장 정보에 대한 CMP 필드 접근자와 비즈니스 동작을 정의하는 로컬 컴포넌트 인터페이스의 일부로, 원장에 저장되는 이자율(interestRate) 값을 변경하기 위한 설정 동작을 제공한다. 호출자는 금리 값을 정밀한 소수 표현으로 전달하며, 구현체는 해당 값을 원장 엔티티의 interestRate 필드에 반영해 상태를 갱신하는 의도를 가진다. 반환값이 없으므로 설정(쓰기) 행위 자체가 목적이며, 조회 결과를 생성하지 않는다. |
| getLoanStartDate | Date getLoanStartDate() | - | - | 이 코드는 여신 원장 정보에 대한 CMP 필드 접근자와 비즈니스 메서드를 정의하는 로컬 컴포넌트 인터페이스의 일부로, 여신 원장에 기록된 loanStartDate(대출 시작일)를 조회하기 위한 접근자를 제공한다. 호출자는 이 값을 통해 해당 여신(대출)이 언제 시작되었는지를 날짜(Date)로 확인할 수 있다. 입력 파라미터 없이 현재 엔티티에 저장된 값을 그대로 반환하는 조회 성격의 계약(시그니처)만 정의하며, 상태 변경이나 저장 동작은 포함하지 않는다. |
| setLoanStartDate | void setLoanStartDate(Date loanStartDate) | - | - | 여신 원장 정보에 대한 CMP 필드 접근자와 비즈니스 메서드를 정의하는 로컬 컴포넌트 인터페이스의 일부로, 여신 원장의 loanStartDate(대출 시작일)를 설정하기 위한 쓰기용 계약을 제공한다. 입력으로 전달된 날짜 값을 여신 원장 상태에 반영하는 목적이며, 구현체에서는 해당 필드가 영속 상태(CMP)로 갱신되도록 처리된다. 반환값 없이 설정만 수행하도록 정의되어, 대출 시작일 변경이라는 상태 변경 의도를 명확히 한다. |
| getMaturityDate | Date getMaturityDate() | - | - | 이 코드는 여신 원장 정보에 대한 CMP 필드 접근자와 비즈니스 동작을 정의하는 로컬 컴포넌트 인터페이스의 일부이다. 여기서는 여신 원장에 저장된 만기일(maturityDate)을 조회하기 위해, 만기일 값을 Date 형태로 반환하도록 계약을 선언한다. 입력 파라미터 없이 현재 엔티티에 보관된 만기일을 읽어 제공하는 용도로, 데이터의 생성·수정·삭제 같은 상태 변경 의도는 없다. |
| setMaturityDate | void setMaturityDate(Date maturityDate) | - | - | 이 구성요소는 여신 원장 정보에 대한 CMP 필드 접근자와 비즈니스 동작을 정의하는 로컬 컴포넌트 인터페이스의 일부이다. 이 선언은 여신 원장에 속한 maturityDate(만기일) 값을 외부에서 전달받아 해당 원장 데이터에 설정(갱신)하기 위한 쓰기용 접근을 제공한다. 구현 로직은 포함하지 않으며, 검증/변환/부가 처리 없이 만기일 값을 엔티티의 상태로 반영하도록 계약만 정의한다. |
| getRepaymentMethod | String getRepaymentMethod() | - | - | 여신 원장 정보에 대한 CMP 필드 접근자를 정의하는 로컬 컴포넌트 인터페이스에서, 상환방식(repaymentMethod) 값을 조회해 문자열로 반환하도록 계약을 제공한다. 구현체는 저장된 여신 원장 레코드에 설정된 상환 방식 코드/명칭 등의 표현값을 그대로 돌려주는 용도로 사용된다. 이 범위에서는 상태를 변경하거나 추가 처리를 수행하지 않고, 상환방식 값의 읽기 접근만을 목적으로 한다. |
| setRepaymentMethod | void setRepaymentMethod(String repaymentMethod) | - | - | 여신 원장 정보에 대한 CMP 필드 접근자와 비즈니스 메서드를 정의하는 로컬 컴포넌트 인터페이스의 일부로, 상환방법(repaymentMethod) 값을 엔티티 상태에 반영하기 위한 설정 동작을 선언한다. 외부에서 전달된 상환방법 문자열을 해당 엔티티의 상환방법 필드에 저장(갱신)할 의도를 갖는다. 구현은 인터페이스 밖에 있으며, 이 선언 자체는 상환방법 값 변경을 통해 원장 정보의 상태를 변경하는 역할을 담당한다. |
| getMonthlyPayment | BigDecimal getMonthlyPayment() | - | - | 여신 원장 정보에 대한 CMP 필드 접근자와 비즈니스 메서드를 정의하는 로컬 컴포넌트 인터페이스의 일부로, 월 납입금(또는 월 상환액)에 해당하는 금액 값을 조회해 제공한다. 입력 파라미터 없이 금액을 반환하며, 반환 타입이 금액 정밀도를 보장하는 수치형이므로 통화/이자 계산 결과를 안전하게 전달하는 목적이다. 인터페이스 선언만 존재하므로 이 범위에서는 계산 로직이나 저장/수정 같은 상태 변경은 수행하지 않는다. |
| setMonthlyPayment | void setMonthlyPayment(BigDecimal monthlyPayment) | - | - | 이 코드는 여신 원장 정보에 대한 CMP 필드 접근자와 비즈니스 동작을 정의하는 로컬 컴포넌트 인터페이스의 일부로, 원장 데이터 중 monthlyPayment(월 납입금) 값을 설정하기 위한 쓰기용 계약을 제공한다. 호출자는 월 납입금을 나타내는 금액 값을 전달하여 해당 원장 레코드의 월 납입금 상태를 변경하도록 의도된다. 구현은 인터페이스 외부에 존재하며, 이 선언 자체는 계산이나 검증 로직 없이 값 설정 행위의 시그니처만 규정한다. |
| getStatus | String getStatus() | - | - | 이 구성요소는 여신 원장 정보에 대한 CMP 필드 접근자와 비즈니스 기능을 정의하는 로컬 컴포넌트 인터페이스의 일부이다. 이 범위는 여신 원장 정보 중 status(상태) 값을 문자열로 조회해 반환하는 읽기 전용 접근자를 선언한다. 구현 로직은 포함하지 않으며, 호출자는 이 반환값을 통해 여신 원장의 현재 상태를 확인하는 데 사용한다. |
| setStatus | void setStatus(String status) | - | - | 이 구성요소는 여신 원장 정보에 대한 CMP 필드 접근자와 비즈니스 동작을 정의하는 로컬 컴포넌트 인터페이스의 일부이다. 여기서는 여신 원장 정보의 status 값을 외부에서 전달된 문자열 값으로 갱신하도록 규약을 제공한다. 이를 통해 원장 상태를 변경(설정)하는 동작을 인터페이스 수준에서 명시하여, 구현체가 상태 변경을 반영하도록 한다. |
| getLastRepaymentDate | Date getLastRepaymentDate() | - | - | 이 코드는 여신 원장 정보에 대한 CMP 필드 접근자 및 비즈니스 기능을 정의하는 로컬 컴포넌트 인터페이스의 일부이다. 그중에서 상환 이력과 관련된 핵심 값인 최종 상환일을 조회하기 위한 읽기 전용 접근 지점을 제공한다. 반환값은 날짜/시간 정보로, 여신 원장 관점에서 가장 최근에 발생한 상환의 기준일을 외부에서 확인할 수 있게 한다. 인터페이스 선언만 존재하므로 이 범위 내에서 데이터 갱신이나 부수효과는 발생하지 않는다. |
| setLastRepaymentDate | void setLastRepaymentDate(Date lastRepaymentDate) | - | - | 이 컴포넌트는 여신 원장 정보에 대한 CMP 필드 접근자와 관련 비즈니스 동작을 정의하며, 그중 이 구문은 여신 원장의 lastRepaymentDate(최종상환일)를 갱신하기 위한 설정 동작을 제공한다. 호출자는 최종 상환이 발생한 일자를 Date 형태로 전달하고, 이 값이 엔티티의 해당 필드에 반영되어 이후 원장 정보에 저장/유지되도록 한다. 별도의 계산, 검증, 조회 로직 없이 상태값(최종상환일) 자체를 변경하는 목적에 집중한다. |
| getNextRepaymentDate | Date getNextRepaymentDate() | - | - | 여신 원장 정보에 대한 CMP 필드 접근자와 업무용 메서드를 정의하는 로컬 컴포넌트 인터페이스의 일부로, 원장에 저장된 상환 일정 정보를 기반으로 '다음 상환일'을 날짜로 반환한다. 입력 파라미터 없이 다음 상환 예정 시점을 조회해 호출 측에서 일정 표시, 상환 안내, 연체 판단 등의 후속 처리를 할 수 있게 한다. 데이터 생성·수정·삭제 없이 원장 상태를 읽어 반환하는 조회 성격의 동작이다. |
| setNextRepaymentDate | void setNextRepaymentDate(Date nextRepaymentDate) | - | - | 여신 원장 정보에 대한 CMP 필드 접근자와 비즈니스 메서드를 정의하는 로컬 컴포넌트 인터페이스의 일부로, nextRepaymentDate(다음 상환일) 값을 설정하기 위한 쓰기 동작을 제공한다. 호출자는 Date로 표현된 다음 상환일을 전달하며, 구현체는 이를 여신 원장 레코드의 해당 필드에 반영하도록 의도된다. 조회가 아니라 원장 정보의 상태(다음 상환일)를 갱신하는 목적이므로 상태 변경 성격이 명확하다. |
| applyRepayment | void applyRepayment(BigDecimal principalPaid, BigDecimal interestPaid) | - | - | 여신 원장 정보에 대한 CMP 필드 접근자와 비즈니스 동작을 정의하는 로컬 컴포넌트 인터페이스의 일부로, 상환 처리 시 원장 상태를 갱신하기 위한 동작을 선언한다. 입력으로 상환된 원금 금액과 상환된 이자 금액(금액 정밀도를 갖는 수치 타입)을 받아, 해당 금액만큼 원장에 상환 반영이 이루어지도록 의도된다. 반환값이 없으므로 조회 결과를 제공하기보다는 원장 잔액/상환 누계 등 내부 상태를 변경하는 목적의 연산임을 전제로 한다. 구현은 이 선언을 따르는 실제 컴포넌트에서 수행된다. |

#### 필드

| 이름 | 타입 | 수정자 | 요약 |
| --- | --- | --- | --- |
| - | - | - | - |

#### 구조 관계

| 방향 | 관계 | 대상 | 속성 |
| --- | --- | --- | --- |
| ← | DEPENDENCY | LoanLedgerLocalHome | source_member=findByPrimaryKey, usage=return |
| ← | DEPENDENCY | LoanLedgerLocalHome | source_member=create, usage=return |
| ← | DEPENDENCY | DebtCollectionSessionBean | source_member=writeOff, usage=local_var |
| ← | DEPENDENCY | DebtCollectionSessionBean | source_member=processCollectionPayment, usage=local_var |
| ← | DEPENDENCY | DelinquencyMgmtSessionBean | source_member=resolveDelinquency, usage=local_var |
| ← | DEPENDENCY | DelinquencyMgmtSessionBean | source_member=registerDelinquency, usage=local_var |
| ← | DEPENDENCY | LoanLedgerSessionBean | source_member=getLedger, usage=local_var |
| ← | DEPENDENCY | LoanLedgerSessionBean | source_member=closeLedger, usage=local_var |
| ← | DEPENDENCY | LoanLedgerSessionBean | source_member=entityToDTO, usage=parameter |
| ← | DEPENDENCY | LoanLedgerSessionBean | source_member=processRepayment, usage=local_var |
| ← | DEPENDENCY | LoanLedgerSessionBean | source_member=entitiesToDTOs, usage=cast |

#### 호출 관계

| 방향 | 대상 | 호출코드 |
| --- | --- | --- |
| ← | DebtCollectionSessionBean | - |
| ← | DelinquencyMgmtSessionBean | - |
| ← | LoanLedgerSessionBean | - |

#### 데이터 접근

| 대상 | 관계 | 근거 | 신뢰도 |
| --- | --- | --- | --- |
| - | - | - | - |

#### 요약 코드

```
없음
```

### LoanLedgerLocalHome

#### 기본 정보

| 항목 | 값 |
| --- | --- |
| 이름 | LoanLedgerLocalHome |
| 타입 | CLASS |
| FQN | com.banking.loan.entity.LoanLedgerLocalHome |
| 패키지 | com.banking.loan.entity |
| 스테레오타입 | COMMAND/READMODEL |
| 파일 | - |
| 라인 | - |
| 토큰 | - |

#### 요약

> 이 클래스는 여신 원장 엔티티 빈의 로컬 홈 인터페이스로서, 여신 원장의 생성 및 다양한 조건에 따른 조회 계약을 정의한다. ledgerId, applicationId, customerId를 식별자로 하여 principalAmount, interestRate, loanStartDate, maturityDate, repaymentMethod, monthlyPayment 조건으로 여신 원장을 생성하며, 생성 실패는 CreateException으로 통지한다. 또한 ledgerId 기반 기본키 조회, customerId/신청 식별자(applicationId)/특정 상태값(status) 기준의 목록 조회, 전체 목록 조회를 제공하고, 조회 실패나 대상 부재 등은 FinderException으로 전달한다.

#### 메서드

| 이름 | 시그니처 | 반환타입 | 수정자 | 요약 |
| --- | --- | --- | --- | --- |
| create | LoanLedgerLocal create(String ledgerId, String applicationId, String customerId,                            BigDecimal principalAmount, BigDecimal interestRate,                            Date loanStartDate, Date maturityDate,                            String repaymentMethod, BigDecimal monthlyPayment) throws CreateException | - | - | 이 인터페이스는 주석에 명시된 대로 여신 원장 엔티티 빈의 생성 및 조회를 위한 계약을 정의하며, 이 범위의 선언은 그중 ‘생성’ 책임을 담당한다. ledgerId, applicationId, customerId로 식별되는 여신 원장을 신규로 등록하기 위해 principalAmount(원금), interestRate(이자율), loanStartDate(대출시작일), maturityDate(만기일)과 같은 핵심 조건을 함께 입력받는다. 또한 repaymentMethod(상환방식)와 monthlyPayment(월상환금)까지 받아 상환 구조가 포함된 원장 생성 요청을 표현한다. 생성 과정에서 문제가 발생하면 CreateException으로 실패를 통지하며, 성공 시 생성된 여신 원장에 접근할 수 있는 로컬 컴포넌트 참조를 반환한다. |
| findByPrimaryKey | LoanLedgerLocal findByPrimaryKey(String ledgerId) throws FinderException | - | - | 여신 원장의 생성 및 조회를 위한 로컬 홈 인터페이스 맥락에서, 입력된 원장 식별자(ledgerId)에 해당하는 여신 원장 정보를 기본키 기준으로 조회해 로컬 컴포넌트 접근용 결과를 반환한다. 조회 대상이 존재하지 않거나 조회 과정에서 문제가 발생하면 FinderException을 통해 조회 실패를 호출자에게 알린다. 이 동작은 여신 원장 데이터의 상태를 변경하지 않고, 특정 식별자에 대한 엔티티 접근 핸들을 얻는 목적의 조회 행위에 해당한다. |
| findAll | Collection findAll() throws FinderException | - | - | 여신 원장의 생성 및 조회를 위한 로컬 홈 인터페이스 맥락에서, 현재 저장소에 존재하는 여신 원장 전체 목록을 한 번에 조회해 컬렉션 형태로 반환하기 위한 계약을 정의한다. 조회 과정에서 검색(조회) 실패나 조회 규칙 위반 등의 상황이 발생할 수 있음을 명시적으로 선언하고, 그 경우 조회 관련 예외를 호출자에게 전달하도록 설계되어 있다. 입력 파라미터 없이 전체를 대상으로 하므로, 필터 조건이나 페이징 같은 제약 없이 전량 조회 의도가 중심이다. |
| findByCustomerId | Collection findByCustomerId(String customerId) throws FinderException | - | - | 이 코드는 여신 원장의 생성 및 조회를 위한 로컬 홈 인터페이스에서, 고객 식별자(customerId)를 기준으로 여신 원장 데이터를 찾아 반환하기 위한 조회 계약을 정의한다. 입력으로 전달된 customerId에 해당하는 여신 원장(또는 그에 준하는 조회 결과)들을 묶음 형태로 돌려주도록 되어 있다. 조회 과정에서 대상이 없거나 조회 수행 중 문제가 발생하면 FinderException을 통해 검색 실패/오류를 호출자에게 알리도록 설계되어 있다. |
| findByStatus | Collection findByStatus(String status) throws FinderException | - | - | 여신 원장의 생성 및 조회를 위한 로컬 홈 인터페이스 맥락에서, 특정 상태값을 입력받아 그 상태에 해당하는 여신 원장들을 조회해 모아서 반환한다. 조회 결과는 여러 건일 수 있으므로 컬렉션 형태로 제공된다. 조회 과정에서 조건에 맞는 엔티티를 찾지 못하거나 조회 규약을 만족하지 못하는 경우 조회 실패 예외를 통해 오류를 호출자에게 전달한다. |
| findByApplicationId | Collection findByApplicationId(String applicationId) throws FinderException | - | - | 여신 원장의 생성 및 조회를 위한 로컬 홈 인터페이스에서, 특정 신청 식별자에 해당하는 여신 원장들을 조회하기 위한 조회 기능을 선언한다. 입력으로 신청 식별자 값을 받아, 그 값과 연관된 여신 원장 결과들을 컬렉션 형태로 반환하도록 계약을 정의한다. 조회 과정에서 대상 식별자에 대한 검색 실패 등 조회 관련 문제가 발생할 수 있음을 예외로 명시해 호출 측에서 처리하도록 한다. |

#### 필드

| 이름 | 타입 | 수정자 | 요약 |
| --- | --- | --- | --- |
| - | - | - | - |

#### 구조 관계

| 방향 | 관계 | 대상 | 속성 |
| --- | --- | --- | --- |
| → | DEPENDENCY | LoanLedgerLocal | source_member=findByPrimaryKey, usage=return |
| → | DEPENDENCY | LoanLedgerLocal | source_member=create, usage=return |
| ← | DEPENDENCY | DebtCollectionSessionBean | source_member=getLoanLedgerHome, usage=return |
| ← | DEPENDENCY | DebtCollectionSessionBean | source_member=writeOff, usage=local_var |
| ← | DEPENDENCY | DebtCollectionSessionBean | source_member=processCollectionPayment, usage=local_var |
| ← | DEPENDENCY | DelinquencyMgmtSessionBean | source_member=getLoanLedgerHome, usage=return |
| ← | DEPENDENCY | DelinquencyMgmtSessionBean | source_member=resolveDelinquency, usage=local_var |
| ← | DEPENDENCY | DelinquencyMgmtSessionBean | source_member=registerDelinquency, usage=local_var |
| ← | DEPENDENCY | LoanLedgerSessionBean | source_member=getLoanLedgerHome, usage=return |
| ← | DEPENDENCY | LoanLedgerSessionBean | source_member=getLedger, usage=local_var |
| ← | DEPENDENCY | LoanLedgerSessionBean | source_member=getActiveLedgers, usage=local_var |
| ← | DEPENDENCY | LoanLedgerSessionBean | source_member=processRepayment, usage=local_var |
| ← | DEPENDENCY | LoanLedgerSessionBean | source_member=calculateRemainingSchedule, usage=local_var |

#### 호출 관계

| 방향 | 대상 | 호출코드 |
| --- | --- | --- |
| ← | DebtCollectionSessionBean | - |
| ← | DelinquencyMgmtSessionBean | - |
| ← | LoanLedgerSessionBean | - |

#### 데이터 접근

| 대상 | 관계 | 근거 | 신뢰도 |
| --- | --- | --- | --- |
| LoanLedgerLocal | REFER_TO | - | 1.0 |
| LoanLedgerLocal | REFER_TO | - | 1.0 |

#### 요약 코드

```
없음
```

### RepaymentBean

#### 기본 정보

| 항목 | 값 |
| --- | --- |
| 이름 | RepaymentBean |
| 타입 | CLASS |
| FQN | com.banking.loan.entity.RepaymentBean |
| 패키지 | com.banking.loan.entity |
| 스테레오타입 | COMMAND/READMODEL |
| 파일 | - |
| 라인 | - |
| 토큰 | - |

#### 요약

> com.banking.loan.entity.RepaymentBean은 상환 CMP 엔티티 빈 구현 클래스로, 컨테이너가 영속성을 관리하며 상환 정보를 저장·조회한다. repaymentId, ledgerId, repaymentDate, principalAmount, interestAmount, penaltyAmount, totalAmount, repaymentType, transactionId 등의 속성을 다루고, 신규 생성 시 principalAmount + interestAmount + penaltyAmount로 totalAmount를 계산해 설정한 뒤 생성 메서드는 null을 반환한다. 엔티티 컨텍스트(entityContext)를 보관·해제하며, 패시베이션 → 활성화 전환 및 로드/스토어/삭제(제거) 생명주기 콜백과 생성 직후 후처리 훅이 모두 비어 있어 추가 검증·정리·매핑 없이 컨테이너 기본 동작에 전적으로 의존한다.

#### 메서드

| 이름 | 시그니처 | 반환타입 | 수정자 | 요약 |
| --- | --- | --- | --- | --- |
| getRepaymentId | - | - | - | 컨테이너가 영속성을 관리하는 상환 정보 저장·조회 구성요소에서, 상환 건을 식별하는 repaymentId(상환 식별자)를 반환하도록 정의된 추상 접근자이다. 구현체는 영속 상태에 저장된 상환 정보에서 repaymentId 값을 읽어 호출자에게 제공해야 한다. 입력 파라미터 없이 식별자 문자열만 제공하므로, 상태 변경 없이 조회 목적의 계약을 형성한다. |
| setRepaymentId | - | - | - | 이 코드는 컨테이너가 영속성을 관리하는 상환 정보 저장·조회 구성요소에서, 상환 레코드를 식별하는 repaymentId(상환 식별자) 값을 설정하기 위한 추상 설정 동작을 정의한다. 호출자는 상환 건을 생성하거나 기존 상환 건을 갱신하는 흐름에서 이 값을 지정함으로써, 이후 영속 계층에서 해당 상환 정보를 올바르게 매핑·식별할 수 있게 한다. 구현은 추상화되어 있어 구체적인 저장 방식은 컨테이너/구현체에 위임되지만, 결과적으로 repaymentId의 상태 변경(세팅)을 의도하는 쓰기 성격의 동작이다. |
| getLedgerId | - | - | - | 컨테이너가 영속성을 관리하며 상환 정보를 저장·조회하는 CMP 엔티티 빈 구현 맥락에서, 상환 정보가 연결되는 원장 식별자(ledgerId)를 문자열로 제공하기 위한 조회용 계약을 정의한다. 구현은 추상화되어 있어 이 코드 범위 자체에서는 값을 계산하거나 저장소에 반영하는 로직이 없다. 호출자는 반환된 ledgerId를 사용해 상환 레코드를 특정 원장과 연계하거나 조회 키로 활용할 수 있다. |
| setLedgerId | - | - | - | 이 클래스는 컨테이너가 영속성을 관리하는 상환 정보 저장·조회용 CMP 구현의 일부이며, 상환 데이터의 속성 값을 갱신할 수 있는 계약을 정의한다. 이 메서드는 ledgerId(원장 식별자)를 입력으로 받아 해당 상환 정보의 원장 식별자 값을 설정하도록 요구한다. 구현은 추상으로 선언되어 있어 실제 저장/갱신 방식은 구현체(또는 컨테이너 생성 코드)에 의해 결정되며, 호출 시점에 엔티티의 상태 변경을 유도한다. |
| getRepaymentDate | - | - | - | 이 구성요소는 컨테이너가 영속성을 관리하는 상환 정보 저장·조회 목적의 CMP 기반 구현에서 사용되는 상환 데이터를 다룬다. 이 선언은 상환 정보 중 상환일자(repaymentDate)를 날짜 타입으로 제공하기 위한 조회용 접근 지점을 정의한다. 구현은 하위 구현체/컨테이너가 영속 상태에 저장된 상환일자를 반환하도록 위임되며, 이 범위 자체에서는 값 변경이나 저장을 수행하지 않는다. |
| setRepaymentDate | - | - | - | 이 코드는 컨테이너가 영속성을 관리하는 상환 정보 저장·조회 구성요소에서, 상환 정보의 repaymentDate(상환일자)를 변경하기 위한 설정 동작을 정의한다. 입력으로 받은 날짜 값을 상환일자 속성에 반영하도록 계약(추상 선언)만 제공하며, 실제 저장 반영 방식은 구현체/컨테이너 쪽에서 처리되도록 되어 있다. 결과적으로 상환 레코드의 핵심 속성인 상환일자를 갱신하는 목적의 쓰기 동작이다. |
| getPrincipalAmount | - | - | - | 이 코드는 컨테이너가 영속성을 관리하는 상환 정보의 저장·조회 흐름에서, 상환 데이터 중 principalAmount(원금금액)을 읽어 반환하기 위한 추상 접근자를 정의한다. 구현은 제공하지 않으며, 실제 원금금액을 어디에서 어떻게 가져올지는 구현체(또는 컨테이너 매커니즘)가 결정하도록 계약만 고정한다. 이를 통해 상환 정보 조회나 금액 산출 로직에서 원금금액을 일관된 방식으로 참조할 수 있게 한다. |
| setPrincipalAmount | - | - | - | 이 코드는 컨테이너가 영속성을 관리하는 상환 정보에서 principalAmount(원금 금액)을 변경하기 위한 설정 동작의 인터페이스를 정의한다. 입력으로 원금에 해당하는 금액 값을 받아, 구현체가 이를 상환 정보의 영속 필드에 반영하도록 요구한다. 조회 목적이 아니라 원금 금액을 갱신해 이후 저장·조회 시 동일 값이 유지되게 하는 상태 변경 성격의 동작이다. |
| getInterestAmount | - | - | - | 상환 정보를 저장·조회하는 CMP 방식의 영속 객체 구현에서, 상환 정보 중 이자금액을 외부로 제공하기 위한 조회용 계약을 정의한다. 이 구현은 실제 계산이나 값 설정을 수행하지 않고, 영속 계층에 저장된 이자금액을 그대로 반환하는 것을 기대한다. 메서드가 추상으로 선언되어 있어, 구체 클래스/컨테이너가 이자금액의 조회 방식(저장소 필드 매핑 등)을 제공하도록 강제한다. |
| setInterestAmount | - | - | - | 이 클래스는 컨테이너가 영속성을 관리하는 상환 정보 저장·조회 컴포넌트이며, 이 구문은 그 상환 정보 중 interestAmount(이자금액)를 변경하기 위한 설정 동작의 계약을 정의한다. 금액 타입 값을 입력으로 받아 해당 상환 레코드의 이자금액 속성을 갱신하도록 구현체에 위임한다. 메서드 본문이 없는 추상 선언이므로, 실제로 어떤 방식으로 저장 상태가 반영되는지는 이를 구현하는 하위 구현에서 결정된다. |
| getPenaltyAmount | - | - | - | 이 코드는 컨테이너가 영속성을 관리하는 상환 정보 저장·조회 구성요소 안에서, 상환과 관련된 연체/지체에 따른 페널티 금액을 제공하기 위한 조회용 계약을 정의한다. 금액은 고정소수점 기반의 수치 타입으로 반환되며, 호출자는 이 값을 통해 상환 정보의 비용(페널티) 요소를 읽을 수 있다. 구현이 비어 있는 추상 선언이므로 실제 계산 규칙(예: 이자율, 경과일수, 상태)에 따라 금액을 산정하는 책임은 하위 구현에 위임된다. |
| setPenaltyAmount | - | - | - | 상환 정보를 저장·조회하는 CMP 구성요소에서, 상환 데이터 중 penaltyAmount(패널티 금액)를 변경하기 위한 설정 동작을 계약 형태로 선언한다. 입력으로 전달된 금액 값을 상환 정보의 해당 속성에 반영해 이후 영속 상태에 저장될 수 있도록 하는 목적이다. 구현은 추상화되어 있어 실제 저장 방식(컨테이너 관리 영속성 등)은 구현체에 의해 결정된다. |
| getTotalAmount | - | - | - | 이 클래스는 컨테이너가 영속성을 관리하는 상환 정보 저장·조회 목적의 CMP 엔티티 빈 구현을 전제로 한다. 이 범위의 코드는 상환 데이터 중 총 금액에 해당하는 totalAmount(합계금액)를 반환하는 접근자를 추상 메서드로 선언해, 실제 값의 조회/매핑 구현을 컨테이너 또는 구체 구현체에 위임한다. 반환 타입이 금액 표현에 적합한 BigDecimal로 정의되어 정밀한 금액 조회를 의도한다. 본 선언 자체는 데이터 변경을 수행하지 않으며 총 금액 값을 읽는 용도로만 사용된다. |
| setTotalAmount | - | - | - | 이 코드는 컨테이너가 영속성을 관리하는 상환 정보 저장·조회 구성요소에서, 상환 데이터의 totalAmount(총액)을 갱신하기 위한 설정 동작을 추상 메서드로 정의한다. 호출자는 고정소수점 기반의 금액 값을 전달해 totalAmount를 변경하도록 요구하며, 실제 저장 방식과 필드 반영 로직은 구현체에 위임된다. 결과적으로 상환 레코드의 금액 상태를 변경(수정)하는 목적의 계약을 제공한다. |
| getRepaymentType | - | - | - | 이 코드는 컨테이너가 영속성을 관리하는 상환 정보 저장·조회 컴포넌트에서, 상환 정보의 핵심 속성 중 하나인 상환 유형을 문자열로 제공하도록 요구한다. 구현을 제공하지 않는 추상 선언이므로, 실제 상환 유형 값의 저장 방식과 조회 방식은 구체 구현체가 결정해 반환해야 한다. 호출자는 이 반환값을 통해 상환 정보를 분류하거나 표시하는 등 읽기 중심의 처리를 수행하며, 선언 자체는 상태 변경을 일으키지 않는다. |
| setRepaymentType | - | - | - | 이 코드는 컨테이너가 영속성을 관리하는 상환 정보 구성 요소에서, 상환 정보의 한 속성인 repaymentType(상환유형)을 변경하기 위한 설정 동작을 정의한다. 호출자는 상환유형을 나타내는 문자열 값을 전달하며, 구현체는 이를 해당 상환 레코드의 상태로 반영해 저장 대상 데이터에 포함되도록 해야 한다. 메서드 본문이 없는 추상 선언이므로 실제 저장/갱신 방식과 유효성 검증 여부는 구현 클래스에 위임된다. |
| getTransactionId | - | - | - | 이 코드는 컨테이너가 영속성을 관리하며 상환 정보를 저장·조회하는 구성요소에서, 상환 정보와 연관된 거래 식별자(transactionId)를 문자열로 제공하기 위한 조회용 인터페이스를 정의한다. 구현부가 없는 추상 선언이므로 여기서는 값을 계산하거나 저장소의 상태를 변경하지 않고, 실제 반환 규칙은 구현 클래스(또는 컨테이너 생성 구현)에 위임된다. 결과적으로 외부에서는 이 식별자를 이용해 상환 레코드를 구분하거나 연계 거래를 추적하는 읽기 동작만 수행할 수 있다. |
| setTransactionId | - | - | - | 이 코드는 컨테이너가 영속성을 관리하는 상환 정보 저장·조회 구성요소에서, 상환 데이터에 연계되는 거래 식별자(transactionId)를 설정하기 위한 변경 지점을 정의한다. 입력으로 전달된 transactionId 값을 해당 상환 레코드의 거래 식별자 속성에 반영하도록 강제하며, 구체적인 저장 방식이나 검증 규칙은 구현체에 위임된다. 조회 목적이 아니라 상환 정보의 상태(거래 식별자 값)를 갱신하는 의도가 중심이므로, 데이터 변경을 위한 계약에 해당한다. |
| ejbCreate | public String ejbCreate(String repaymentId, String ledgerId, Date repaymentDate,                             BigDecimal principalAmount, BigDecimal interestAmount,                             BigDecimal penaltyAmount, String repaymentType,                             String transactionId) throws CreateException | - | - | 컨테이너가 영속성을 관리하는 상환 정보 저장·조회 구성요소에서, 신규 상환 레코드를 생성할 때 필요한 핵심 속성들을 초기 상태로 확정하기 위한 생성 처리이다. 입력으로 받은 repaymentId, ledgerId, repaymentDate, principalAmount, interestAmount, penaltyAmount, repaymentType, transactionId를 각각 상환 레코드의 속성으로 반영해 영속 상태에 저장될 준비를 한다. 또한 totalAmount(총액)는 principalAmount + interestAmount + penaltyAmount의 합으로 계산해 설정함으로써, 금액 구성요소와 합계가 일관되게 기록되도록 한다. 생성 결과로 식별자 값을 직접 반환하지 않고 null을 반환하는 형태로, 식별자는 repaymentId 설정을 통해 레코드 매핑에 사용되도록 구성된다. |
| ejbPostCreate | public void ejbPostCreate(String repaymentId, String ledgerId, Date repaymentDate,                               BigDecimal principalAmount, BigDecimal interestAmount,                               BigDecimal penaltyAmount, String repaymentType,                               String transactionId) | - | - | 이 코드는 컨테이너가 영속성을 관리하며 상환 정보를 저장·조회하는 구성요소에서, 신규 생성 직후 추가 후처리를 수행하기 위한 생명주기 훅에 해당한다. 입력으로 repaymentId, ledgerId, repaymentDate, principalAmount, interestAmount, penaltyAmount, repaymentType, transactionId 등 상환 등록에 필요한 핵심 속성들을 전달받는다. 그러나 본문이 비어 있어 전달된 값에 대한 검증, 상태 변경, 추가 연관 설정, 부가 데이터 기록과 같은 후속 작업을 수행하지 않는다. 결과적으로 생성 이후의 별도 비즈니스 후처리는 없고, 생성 단계에서의 영속화는 컨테이너/기본 생성 로직에만 의존한다. |
| setEntityContext | public void setEntityContext(EntityContext ctx) | - | - | 이 구현은 컨테이너가 영속성을 관리하는 상환 정보 저장·조회 구성요소의 일부로, 실행 시점의 엔티티 처리 환경을 보관하기 위한 준비 동작을 수행한다. 컨테이너로부터 전달된 엔티티 실행 컨텍스트를 입력으로 받아 내부에 유지하도록 설정한다. 이를 통해 이후 생명주기 콜백이나 영속성/트랜잭션 처리 과정에서 필요한 컨텍스트에 접근할 수 있게 한다. |
| unsetEntityContext | public void unsetEntityContext() | - | - | 이 클래스는 컨테이너가 영속성을 관리하는 상환 정보 저장·조회용 구성요소이며, 실행 컨텍스트를 보관해 생명주기 동안 컨테이너와 상호작용한다. 이 구간의 로직은 보관 중이던 실행 컨텍스트 참조를 비워 더 이상 컨테이너 컨텍스트에 의존하지 않도록 정리한다. 결과적으로 인스턴스 내부 상태를 변경해 컨텍스트 해제/종료 단계에서 자원 참조를 끊고 이후 오사용 가능성을 줄인다. |
| ejbActivate | public void ejbActivate() | - | - | 이 코드는 컨테이너가 영속성을 관리하는 상환 정보 저장·조회 구성요소의 생명주기에서, 인스턴스가 비활성(패시베이션) 상태에서 다시 활성 상태로 전환될 때 호출되는 훅을 제공한다. 다만 본문이 비어 있어, 활성화 시점에 엔티티 컨텍스트 재연결, 캐시 복구, 자원 재초기화 같은 추가 동작을 수행하지 않는다. 따라서 활성화 이벤트를 수신하되 시스템 상태를 변경하거나 외부 자원을 참조하는 부수효과는 발생하지 않는다. |
| ejbPassivate | public void ejbPassivate() | - | - | 이 코드는 컨테이너가 영속성을 관리하는 상환 정보 저장·조회용 CMP 엔티티 빈에서, 인스턴스가 패시베이션(비활성화) 단계로 전환될 때 호출되는 생명주기 콜백을 정의한다. 패시베이션 시점에 보통은 보유 중인 자원 정리나 컨텍스트 참조 해제 같은 후처리를 수행할 수 있지만, 여기서는 아무 작업도 하지 않도록 비어 있다. 따라서 이 범위의 로직은 상환 데이터의 저장·수정·삭제 같은 상태 변경이나 조회를 수행하지 않고, 컨테이너 이벤트에 대한 ‘무처리’ 응답만 제공한다. |
| ejbLoad | public void ejbLoad() | - | - | 이 구성요소는 컨테이너가 영속성을 관리하는 상환 정보 저장·조회 목적의 CMP 구현에 속하며, 영속 저장소로부터 현재 인스턴스의 상태를 적재하는 생명주기 단계에서 실행될 수 있는 진입점을 제공한다. 그러나 본문이 비어 있어, 상태 적재를 위해 별도의 조회 로직이나 값 매핑을 수행하지 않고 컨테이너의 기본 동작에 전적으로 위임한다. 그 결과 이 범위에서는 상환 정보의 읽기/조회에 해당하는 의도만 존재하며, 데이터 변경이나 외부 자원 접근은 발생하지 않는다. |
| ejbStore | public void ejbStore() | - | - | 상환 정보를 영속 저장소에 반영하기 위한 저장 시점에 컨테이너가 호출하는 콜백 지점이다. 이 구현은 본문이 비어 있어, 상환 정보의 저장·동기화 처리를 애플리케이션 코드에서 직접 수행하지 않는다. 그 결과 영속성 반영은 컨테이너가 관리하는 기본 동작(컨테이너 관리 영속성)에 전적으로 위임된다. 추가 검증, 부가 갱신, 외부 연계 호출 없이 저장 단계에서의 커스터마이징이 없는 형태다. |
| ejbRemove | public void ejbRemove() throws RemoveException | - | - | 이 클래스는 컨테이너 관리 영속성을 통해 상환 정보를 저장·조회하는 구현이며, 여기의 코드는 상환 정보가 제거되는 생명주기 시점에 호출되는 제거 콜백을 제공한다. 본문이 비어 있어 상환 정보 삭제 과정에서 별도의 정리 작업(추가 검증, 연관 자원 해제, 후처리 로직 등)을 수행하지 않고 컨테이너의 기본 제거 처리에 전적으로 의존한다. 따라서 코드 레벨에서는 상태 변경 로직이 없지만, 엔티티 제거 이벤트 자체는 영속 데이터 삭제를 수반하는 명령 성격의 동작으로 해석된다. |

#### 필드

| 이름 | 타입 | 수정자 | 요약 |
| --- | --- | --- | --- |
| entityContext | EntityContext | - | 상환 정보를 저장·조회하는 CMP 엔티티 빈에서 컨테이너가 주입·관리하는 엔티티 컨텍스트를 보관하는 필드로, 빈의 생명주기 및 트랜잭션/보안 등 실행 환경 정보에 접근할 때 사용된다. |

#### 구조 관계

| 방향 | 관계 | 대상 | 속성 |
| --- | --- | --- | --- |
| → | ASSOCIATION | EntityContext | source_member=unsetEntityContext |
| → | DEPENDENCY | EntityContext | source_member=setEntityContext, usage=parameter |

#### 호출 관계

| 방향 | 대상 | 호출코드 |
| --- | --- | --- |
| → | RepaymentBean | 53:         setRepaymentId(repaymentId); |
| → | RepaymentBean | 54:         setLedgerId(ledgerId); |
| → | RepaymentBean | 55:         setRepaymentDate(repaymentDate); |
| → | RepaymentBean | 56:         setPrincipalAmount(principalAmount); |
| → | RepaymentBean | 57:         setInterestAmount(interestAmount); |
| → | RepaymentBean | 58:         setPenaltyAmount(penaltyAmount); |
| → | RepaymentBean | 59:         setTotalAmount(principalAmount.add(interestAmount).add(penaltyAmount)); |
| → | RepaymentBean | 60:         setRepaymentType(repaymentType); |
| → | RepaymentBean | 61:         setTransactionId(transactionId); |

#### 데이터 접근

| 대상 | 관계 | 근거 | 신뢰도 |
| --- | --- | --- | --- |
| - | - | - | - |

#### 요약 코드

```
없음
```

### RepaymentLocal

#### 기본 정보

| 항목 | 값 |
| --- | --- |
| 이름 | RepaymentLocal |
| 타입 | CLASS |
| FQN | com.banking.loan.entity.RepaymentLocal |
| 패키지 | com.banking.loan.entity |
| 스테레오타입 | COMMAND/READMODEL |
| 파일 | - |
| 라인 | - |
| 토큰 | - |

#### 요약

> com.banking.loan.entity.RepaymentLocal은 상환 엔티티 빈의 로컬 컴포넌트 인터페이스로, 상환 정보에 대한 CMP 필드 접근자(조회·설정) 계약을 정의한다. 이 클래스는 repaymentId, ledgerId, repaymentDate, principalAmount, interestAmount, penaltyAmount, totalAmount, repaymentType, transactionId 등 상환 관련 속성을 로컬에서 일관되게 읽고 갱신하는 데 책임이 있다. 특히 외부에서 전달받은 transactionId를 엔티티 필드로 반영(갱신)하여 상환 레코드의 거래 연계 식별을 가능하게 한다.

#### 메서드

| 이름 | 시그니처 | 반환타입 | 수정자 | 요약 |
| --- | --- | --- | --- | --- |
| getRepaymentId | String getRepaymentId() | - | - | 이 로컬 컴포넌트 인터페이스는 상환 정보에 대한 CMP 필드 접근자를 정의하며, 그중 상환 건을 식별하는 repaymentId 값을 조회하기 위한 읽기용 접근을 제공한다. 호출자는 이를 통해 현재 상환 레코드의 식별자를 문자열로 얻어 다른 처리(연관 데이터 조회, 참조 연결 등)에 활용할 수 있다. 입력 파라미터 없이 내부 상태를 변경하지 않고, 저장/갱신 같은 부수효과 없이 값 조회만 수행하는 계약을 나타낸다. |
| getLedgerId | String getLedgerId() | - | - | 상환 정보에 대한 CMP 필드 접근자를 정의하는 로컬 컴포넌트 인터페이스의 일부로, 상환 레코드가 참조하는 ledgerId(원장 식별자) 값을 반환한다. 호출자는 이 값을 통해 상환 정보가 연결된 원장 기록을 식별하거나 연관 데이터 조회의 키로 활용할 수 있다. 입력값 없이 현재 인스턴스에 보관된 값을 읽기만 하며, 데이터 저장·수정 같은 상태 변경은 수행하지 않는다. |
| setLedgerId | void setLedgerId(String ledgerId) | - | - | 이 구성요소는 상환 정보에 대한 CMP 필드 접근자를 정의하는 로컬 컴포넌트 인터페이스이며, 그중 원장 식별값(ledgerId)을 변경하기 위한 쓰기 동작을 제공한다. 외부에서 전달된 문자열 값을 상환 정보의 ledgerId 필드에 설정하여, 해당 상환 레코드가 어떤 원장(ledger)에 속하는지의 연결 정보를 갱신한다. 이 동작 자체는 조회가 아니라 데이터의 상태(필드 값)를 변경하는 목적을 가진다. |
| getRepaymentDate | Date getRepaymentDate() | - | - | 상환 정보에 대한 CMP 필드 접근자를 제공하는 로컬 컴포넌트 인터페이스의 일부로, repaymentDate(상환일자) 값을 조회해 반환하는 선언이다. 호출자 입장에서는 상환 기록에 저장된 상환일자를 읽어오기 위한 읽기 전용 계약을 제공한다. 입력 파라미터 없이 현재 엔티티가 보유한 상환일자 상태를 그대로 반환하며, 저장/수정/삭제 같은 상태 변경 의도는 없다. |
| setRepaymentDate | void setRepaymentDate(Date repaymentDate) | - | - | 상환 정보에 대한 CMP 필드 접근자를 정의하는 로컬 컴포넌트 인터페이스의 일부로, 상환 정보에 포함된 repaymentDate(상환일자)를 갱신하기 위한 쓰기 동작을 선언한다. 입력으로 전달된 날짜 값을 상환 데이터의 상환일자 필드에 반영하도록 구현체에 위임한다. 조회나 계산 로직 없이, 상환일자 값의 변경 자체를 목적로 한다. |
| getPrincipalAmount | BigDecimal getPrincipalAmount() | - | - | 이 구성요소는 상환 정보에 대한 CMP 필드 접근자를 정의하는 로컬 컴포넌트 인터페이스의 일부이다. 이 범위의 선언은 상환 정보 중 principalAmount(원금 금액) 값을 조회하기 위한 읽기 전용 접근 지점을 제공한다. 호출자에게 원금 금액을 BigDecimal 형태로 반환하도록 계약만 정의하며, 내부 계산이나 저장/갱신 동작은 포함하지 않는다. |
| setPrincipalAmount | void setPrincipalAmount(BigDecimal principalAmount) | - | - | 상환 정보에 대한 CMP 필드 접근자를 정의하는 로컬 컴포넌트 인터페이스의 일부로, 상환 데이터의 principalAmount(원금금액)를 설정하기 위한 쓰기용 계약을 제공한다. 호출자는 원금에 해당하는 금액 값을 전달하며, 구현 측에서는 해당 상환 레코드의 원금금액 상태를 갱신하는 데 사용된다. 이 동작은 조회가 아니라 상환 정보의 내부 상태(원금금액)를 변경하는 목적을 가진다. |
| getInterestAmount | BigDecimal getInterestAmount() | - | - | 이 인터페이스는 상환 정보에 대한 CMP 필드 접근자를 정의하며, 그중 한 항목으로 이자금액(interestAmount)을 조회할 수 있는 읽기 전용 접근을 제공한다. 호출자는 상환 정보에 저장된 이자금액 값을 금액 계산에 적합한 정밀 수치 타입으로 받아 후속 정산/표시 로직에 활용할 수 있다. 이 범위에는 입력값을 받거나 상태를 변경하는 로직이 없고, 단순히 이자금액을 반환하는 계약만 선언되어 있다. |
| setInterestAmount | void setInterestAmount(BigDecimal interestAmount) | - | - | 이 구성요소는 상환 정보에 대한 CMP 필드 접근자를 정의하는 로컬 컴포넌트 인터페이스의 일부로, 상환 데이터의 영속 상태를 다루기 위한 계약을 제공한다. 이 범위의 선언은 이자금액(interestAmount)을 외부 입력값으로 받아 해당 상환 정보의 이자금액 필드에 값을 설정(갱신)하도록 요구한다. 설정되는 값은 금액 연산의 정밀도를 유지하기 위해 임의정밀도 숫자 타입으로 전달되며, 호출 측은 이 값이 상환 정보에 반영되어 저장 상태가 변경될 수 있음을 전제로 사용한다. |
| getPenaltyAmount | BigDecimal getPenaltyAmount() | - | - | 이 구성요소는 상환 정보에 대한 CMP 필드 접근자를 정의하는 로컬 컴포넌트 인터페이스이며, 그중 이 선언은 상환과 연관된 penaltyAmount(연체/위약금 성격의 금액)를 조회하기 위한 접근자 역할을 한다. 외부에서 별도의 입력 없이 현재 상환 레코드에 저장된 금액 값을 반환하도록 계약만 정의되어 있다. 반환값은 금액 정밀도를 보장하기 위한 값 타입으로 표현되며, 계산이나 저장을 수행하지 않고 읽기 목적만 가진다. |
| setPenaltyAmount | void setPenaltyAmount(BigDecimal penaltyAmount) | - | - | 상환 정보에 대한 CMP 필드 접근자를 정의하는 로컬 컴포넌트 인터페이스에서, penaltyAmount(위약금/연체 페널티 금액) 값을 상환 정보에 반영하기 위한 쓰기용 접근자 계약을 선언한다. 입력으로 받은 금액은 정밀한 금액 표현을 전제로 상환 정보의 penaltyAmount 필드 값을 갱신하는 목적을 가진다. 반환값이 없으므로, 호출 측은 설정 동작 자체가 상환 정보의 상태 변경을 발생시키는 것으로 취급한다. |
| getTotalAmount | BigDecimal getTotalAmount() | - | - | 이 인터페이스는 상환 정보에 대한 CMP 필드 접근자를 정의하며, 상환 엔티티의 핵심 금액 데이터를 조회할 수 있도록 한다. 이 범위의 선언은 상환 정보의 totalAmount(총금액)를 정밀한 금액 타입으로 반환하는 읽기 전용 접근자를 제공한다. 입력 파라미터 없이 현재 저장된 총금액 값을 그대로 돌려주는 형태로, 상태 변경이나 저장 동작은 포함하지 않는다. |
| setTotalAmount | void setTotalAmount(BigDecimal totalAmount) | - | - | 상환 정보에 대한 CMP 필드 접근자를 제공하는 로컬 컴포넌트 인터페이스의 일부로, 상환 데이터의 totalAmount(총금액)를 갱신하기 위한 설정 동작을 정의한다. 호출자는 금액 값을 전달해 해당 상환 레코드/엔티티의 totalAmount를 변경하도록 의도되어 있다. 이 설정은 조회가 아니라 데이터 상태를 변경하는 목적이며, 이후 컨테이너 관리 영속성 흐름에서 변경 내용이 반영될 수 있는 형태의 계약을 제공한다. |
| getRepaymentType | String getRepaymentType() | - | - | 이 코드는 상환 정보에 대한 CMP 필드 접근자를 정의하는 로컬 컴포넌트 인터페이스의 일부로, 상환 데이터 중 ‘repaymentType(상환유형)’ 값을 읽어오기 위한 조회용 계약을 제공한다. 호출자는 상환유형을 문자열로 받아 상환 방식/구분을 판별하거나 화면·전문 출력, 분기 처리에 활용할 수 있다. 선언만 존재하며 입력값 없이 값을 반환하므로, 이 범위 자체에는 저장·수정·삭제 같은 상태 변경 동작이 포함되지 않는다. |
| setRepaymentType | void setRepaymentType(String repaymentType) | - | - | 이 인터페이스는 상환 정보에 대한 CMP 필드 접근자를 정의하여, 상환 관련 데이터를 컨테이너 관리 영속 상태로 다루기 위한 계약을 제공한다. 이 범위의 선언은 상환 정보의 repaymentType(상환유형) 값을 외부에서 전달받아 해당 CMP 필드에 기록(설정)하는 역할을 한다. 반환값이 없으며, 영속 필드의 값이 갱신되는 쓰기 목적의 동작을 나타낸다. |
| getTransactionId | String getTransactionId() | - | - | 이 구성요소는 상환 정보에 대한 CMP 필드 접근자를 정의하는 로컬 컴포넌트 인터페이스이며, 상환 데이터의 주요 속성을 외부에서 읽을 수 있게 한다. 이 선언은 상환 건이 어떤 거래에 의해 생성·연결되는지 식별하기 위한 transactionId(거래 식별자)를 문자열로 반환하도록 규정한다. 이를 통해 상환 정보 조회 시 거래 단위로 연계/추적이 가능하도록 읽기 전용 접근 경로를 제공한다. |
| setTransactionId | void setTransactionId(String transactionId) | - | - | 이 구성요소는 상환 정보에 대한 CMP 필드 접근자를 정의하여 상환 엔티티의 주요 속성을 읽고 쓸 수 있게 한다. 이 범위의 선언은 상환 데이터에 연관된 transactionId를 외부에서 전달받아 엔티티의 해당 필드 값으로 반영(갱신)하기 위한 설정 동작을 나타낸다. 즉, 특정 상환 레코드를 식별하거나 연계 처리에 필요한 거래 식별자를 엔티티 상태에 저장해 이후 조회·처리 흐름에서 일관되게 사용하도록 한다. |

#### 필드

| 이름 | 타입 | 수정자 | 요약 |
| --- | --- | --- | --- |
| - | - | - | - |

#### 구조 관계

| 방향 | 관계 | 대상 | 속성 |
| --- | --- | --- | --- |
| ← | DEPENDENCY | RepaymentLocalHome | source_member=findByPrimaryKey, usage=return |
| ← | DEPENDENCY | LoanLedgerSessionBean | source_member=processRepayment, usage=local_var |

#### 호출 관계

| 방향 | 대상 | 호출코드 |
| --- | --- | --- |
| - | - | - |

#### 데이터 접근

| 대상 | 관계 | 근거 | 신뢰도 |
| --- | --- | --- | --- |
| - | - | - | - |

#### 요약 코드

```
없음
```

### RepaymentLocalHome

#### 기본 정보

| 항목 | 값 |
| --- | --- |
| 이름 | RepaymentLocalHome |
| 타입 | CLASS |
| FQN | com.banking.loan.entity.RepaymentLocalHome |
| 패키지 | com.banking.loan.entity |
| 스테레오타입 | COMMAND/READMODEL |
| 파일 | - |
| 라인 | - |
| 토큰 | - |

#### 요약

> com.banking.loan.entity.RepaymentLocalHome은 상환 엔티티 빈의 로컬 홈 인터페이스로서, 상환 데이터의 생성 및 조회를 위한 메서드 계약을 정의한다. repaymentId, ledgerId, repaymentDate와 함께 principalAmount(원금), interestAmount(이자), penaltyAmount(연체/벌금), repaymentType(상환유형), transactionId(거래식별자)를 입력받아 상환 건을 생성하고, 생성된 상환을 다룰 수 있는 로컬 컴포넌트 접근자를 반환한다. 또한 상환 식별자 기반 단건 조회, ledgerId 기반 다건 조회, 전체 목록 조회를 제공하며, 생성/조회 과정의 실패는 CreateException 또는 FinderException으로 호출자에게 전달한다.

#### 메서드

| 이름 | 시그니처 | 반환타입 | 수정자 | 요약 |
| --- | --- | --- | --- | --- |
| create | RepaymentLocal create(String repaymentId, String ledgerId, Date repaymentDate,                           BigDecimal principalAmount, BigDecimal interestAmount,                           BigDecimal penaltyAmount, String repaymentType,                           String transactionId) throws CreateException | - | - | 이 구성요소는 상환 정보의 생성 및 조회를 위한 계약을 정의하며, 이 범위는 상환을 신규로 생성하는 요청을 선언한다. repaymentId, ledgerId, repaymentDate를 포함해 principalAmount(원금), interestAmount(이자), penaltyAmount(연체/벌금), repaymentType(상환유형), transactionId(거래식별자)로 상환 건을 등록하는 데 필요한 핵심 속성을 입력으로 받는다. 생성이 성공하면 생성된 상환을 다룰 수 있는 로컬 컴포넌트 접근자를 반환해 이후 CMP 필드 접근이 가능하게 한다. 생성 과정에서 오류가 발생하면 생성 예외를 통해 실패를 호출자에게 전달한다. |
| findByPrimaryKey | RepaymentLocal findByPrimaryKey(String repaymentId) throws FinderException | - | - | 이 구성요소는 상환 정보에 대한 생성 및 조회 기능을 제공하는 계약 중, 특정 상환 건을 식별자로 조회하기 위한 항목을 정의한다. 입력으로 전달된 상환 식별자에 해당하는 상환 정보를 로컬 컴포넌트 형태로 반환하여, 이후 상환 정보의 CMP 필드 접근자들을 사용할 수 있게 한다. 조회 대상이 존재하지 않거나 조회 과정에서 문제가 발생하면 조회 실패 예외를 통해 호출자에게 조회 불가 상황을 전달하도록 선언되어 있다. |
| findAll | Collection findAll() throws FinderException | - | - | 이 구성요소는 상환 정보를 생성하고 조회하기 위한 로컬 홈 인터페이스이며, 여기서는 상환 데이터 전체 목록을 조회하는 동작을 정의한다. 호출자는 반환된 컬렉션을 통해 시스템에 존재하는 상환 레코드들을 일괄적으로 접근할 수 있다. 조회 과정에서 대상 데이터가 없거나 조회 규약을 만족하지 못하는 경우 조회 실패 예외를 통해 오류 상황을 호출자에게 전달하도록 계약한다. |
| findByLedgerId | Collection findByLedgerId(String ledgerId) throws FinderException | - | - | 이 인터페이스는 상환 데이터를 생성·조회하기 위한 계약을 제공하며, 이 범위의 선언은 원장 식별자(ledgerId)를 기준으로 상환 관련 대상을 찾아 반환하는 조회 동작을 정의한다. 입력으로 전달된 원장 식별자에 해당하는 조회 결과를 여러 건으로 돌려줄 수 있도록 컬렉션 형태로 반환하도록 되어 있다. 조회 과정에서 대상이 없거나 조회 규칙을 만족하지 못하는 등 식별 실패 상황이 발생하면 FinderException을 통해 호출자에게 오류를 전달하도록 설계되어 있다. |

#### 필드

| 이름 | 타입 | 수정자 | 요약 |
| --- | --- | --- | --- |
| - | - | - | - |

#### 구조 관계

| 방향 | 관계 | 대상 | 속성 |
| --- | --- | --- | --- |
| → | DEPENDENCY | RepaymentLocal | source_member=findByPrimaryKey, usage=return |
| ← | DEPENDENCY | DebtCollectionSessionBean | source_member=getRepaymentHome, usage=return |
| ← | DEPENDENCY | DebtCollectionSessionBean | source_member=processCollectionPayment, usage=local_var |
| ← | DEPENDENCY | LoanLedgerSessionBean | source_member=getRepaymentHome, usage=return |
| ← | DEPENDENCY | LoanLedgerSessionBean | source_member=processRepayment, usage=local_var |

#### 호출 관계

| 방향 | 대상 | 호출코드 |
| --- | --- | --- |
| ← | DebtCollectionSessionBean | - |
| ← | LoanLedgerSessionBean | - |

#### 데이터 접근

| 대상 | 관계 | 근거 | 신뢰도 |
| --- | --- | --- | --- |
| RepaymentLocal | REFER_TO | - | 1.0 |
| RepaymentLocal | REFER_TO | - | 1.0 |

#### 요약 코드

```
없음
```

### DelinquencyException

#### 기본 정보

| 항목 | 값 |
| --- | --- |
| 이름 | DelinquencyException |
| 타입 | CLASS |
| FQN | com.banking.loan.exception.DelinquencyException |
| 패키지 | com.banking.loan.exception |
| 스테레오타입 | - |
| 파일 | - |
| 라인 | - |
| 토큰 | - |

#### 요약

> com.banking.loan.exception.DelinquencyException은 대출(loan) 도메인에서 연체(delinquency) 상황을 표현하고 상위 계층으로 전달하기 위한 예외 클래스입니다. 예외 객체의 직렬화 호환성을 유지하기 위해 serialVersionUID를 정의하고 있습니다.

#### 메서드

| 이름 | 시그니처 | 반환타입 | 수정자 | 요약 |
| --- | --- | --- | --- | --- |
| - | - | - | - | - |

#### 필드

| 이름 | 타입 | 수정자 | 요약 |
| --- | --- | --- | --- |
| serialVersionUID | long | - | serialVersionUID; lines 5-5 |

#### 구조 관계

| 방향 | 관계 | 대상 | 속성 |
| --- | --- | --- | --- |
| ← | DEPENDENCY | DebtCollectionSession | source_member=processCollectionPayment, usage=return |
| ← | DEPENDENCY | DebtCollectionSession | source_member=writeOff, usage=parameter |
| ← | DEPENDENCY | DebtCollectionSession | source_member=getCollectionDetail, usage=parameter |
| ← | DEPENDENCY | DebtCollectionSession | source_member=initiateCollection, usage=parameter |
| ← | DEPENDENCY | DebtCollectionSession | source_member=getWrittenOffLedgers, usage=parameter |
| ← | DEPENDENCY | DebtCollectionSession | source_member=getCollectionTargets, usage=parameter |
| ← | DEPENDENCY | DebtCollectionSessionBean | source_member=getCollectionTargets, usage=local_new |
| ← | DEPENDENCY | DebtCollectionSessionBean | source_member=processCollectionPayment, usage=local_new |
| ← | DEPENDENCY | DelinquencyMgmtSession | source_member=updateDelinquencyStatus, usage=parameter |
| ← | DEPENDENCY | DelinquencyMgmtSession | source_member=registerDelinquency, usage=local_var |
| ← | DEPENDENCY | DelinquencyMgmtSession | source_member=resolveDelinquency, usage=parameter |
| ← | DEPENDENCY | DelinquencyMgmtSession | source_member=getDelinquency, usage=parameter |
| ← | DEPENDENCY | DelinquencyMgmtSession | source_member=getActiveDelinquencies, usage=parameter |
| ← | DEPENDENCY | DelinquencyMgmtSessionBean | source_member=getDelinquenciesByCustomer, usage=local_new |
| ← | DEPENDENCY | DelinquencyMgmtSessionBean | source_member=registerDelinquency, usage=return |

#### 호출 관계

| 방향 | 대상 | 호출코드 |
| --- | --- | --- |
| - | - | - |

#### 데이터 접근

| 대상 | 관계 | 근거 | 신뢰도 |
| --- | --- | --- | --- |
| - | - | - | - |

#### 요약 코드

```
없음
```

### LoanApplicationException

#### 기본 정보

| 항목 | 값 |
| --- | --- |
| 이름 | LoanApplicationException |
| 타입 | CLASS |
| FQN | com.banking.loan.exception.LoanApplicationException |
| 패키지 | com.banking.loan.exception |
| 스테레오타입 | - |
| 파일 | - |
| 라인 | - |
| 토큰 | - |

#### 요약

> com.banking.loan.exception.LoanApplicationException은 대출 신청 처리 과정에서 발생하는 오류 상황을 표현하기 위한 예외 클래스입니다. 직렬화 호환성을 유지하기 위해 serialVersionUID를 보유하여, 예외 객체가 직렬화/역직렬화될 때 버전 불일치로 인한 문제를 방지합니다.

#### 메서드

| 이름 | 시그니처 | 반환타입 | 수정자 | 요약 |
| --- | --- | --- | --- | --- |
| - | - | - | - | - |

#### 필드

| 이름 | 타입 | 수정자 | 요약 |
| --- | --- | --- | --- |
| serialVersionUID | long | - | serialVersionUID; lines 5-5 |

#### 구조 관계

| 방향 | 관계 | 대상 | 속성 |
| --- | --- | --- | --- |
| ← | DEPENDENCY | LoanApplicationSession | source_member=getAllApplications, usage=parameter |
| ← | DEPENDENCY | LoanApplicationSession | source_member=cancelApplication, usage=local_var |
| ← | DEPENDENCY | LoanApplicationSession | source_member=submitApplication, usage=local_var |
| ← | DEPENDENCY | LoanApplicationSession | source_member=getApplication, usage=parameter |
| ← | DEPENDENCY | LoanApplicationSession | source_member=getApplicationsByCustomer, usage=return |
| ← | DEPENDENCY | LoanApplicationSession | source_member=getApplicationsByStatus, usage=parameter |
| ← | DEPENDENCY | LoanApplicationSessionBean | source_member=getApplicationsByCustomer, usage=return |
| ← | DEPENDENCY | LoanApplicationSessionBean | source_member=submitApplication, usage=local_new |
| ← | DEPENDENCY | LoanApplicationSessionBean | source_member=registerCollateral, usage=local_new |
| ← | DEPENDENCY | LoanApplicationSessionBean | source_member=getApplicationsByStatus, usage=local_new |
| ← | DEPENDENCY | LoanProcessSession | source_member=addCollateral, usage=parameter |
| ← | DEPENDENCY | LoanProcessSession | source_member=cancelProcess, usage=parameter |
| ← | DEPENDENCY | LoanProcessSession | source_member=getCurrentApplicationStatus, usage=parameter |
| ← | DEPENDENCY | LoanProcessSession | source_member=initializeProcess, usage=parameter |
| ← | DEPENDENCY | LoanProcessSession | source_member=setLoanDetails, usage=parameter |
| ← | DEPENDENCY | LoanProcessSessionBean | source_member=setLoanDetails, usage=local_new |
| ← | DEPENDENCY | LoanProcessSessionBean | source_member=addCollateral, usage=local_new |
| ← | DEPENDENCY | LoanProcessSessionBean | source_member=cancelProcess, usage=return |
| ← | DEPENDENCY | LoanProcessSessionBean | source_member=submitAndGetResult, usage=local_new |

#### 호출 관계

| 방향 | 대상 | 호출코드 |
| --- | --- | --- |
| - | - | - |

#### 데이터 접근

| 대상 | 관계 | 근거 | 신뢰도 |
| --- | --- | --- | --- |
| - | - | - | - |

#### 요약 코드

```
없음
```

### LoanExecutionException

#### 기본 정보

| 항목 | 값 |
| --- | --- |
| 이름 | LoanExecutionException |
| 타입 | CLASS |
| FQN | com.banking.loan.exception.LoanExecutionException |
| 패키지 | com.banking.loan.exception |
| 스테레오타입 | - |
| 파일 | - |
| 라인 | - |
| 토큰 | - |

#### 요약

> com.banking.loan.exception.LoanExecutionException는 대출(loan) 실행 과정에서 발생하는 오류 상황을 표현하기 위한 커스텀 예외 클래스입니다. 예외 객체의 직렬화/역직렬화 시 버전 호환성을 유지하기 위해 serialVersionUID를 정의하고 있습니다. 이를 통해 대출 실행 로직에서 발생한 실패 원인을 상위 계층으로 명확하게 전달하는 책임을 가집니다.

#### 메서드

| 이름 | 시그니처 | 반환타입 | 수정자 | 요약 |
| --- | --- | --- | --- | --- |
| - | - | - | - | - |

#### 필드

| 이름 | 타입 | 수정자 | 요약 |
| --- | --- | --- | --- |
| serialVersionUID | long | - | serialVersionUID; lines 5-5 |

#### 구조 관계

| 방향 | 관계 | 대상 | 속성 |
| --- | --- | --- | --- |
| ← | DEPENDENCY | LoanExecutionSession | source_member=getLedgersByCustomer, usage=parameter |
| ← | DEPENDENCY | LoanExecutionSessionBean | source_member=getLedgersByCustomer, usage=local_new |
| ← | DEPENDENCY | LoanLedgerSession | source_member=getLedgersByCustomer, usage=parameter |
| ← | DEPENDENCY | LoanLedgerSession | source_member=processRepayment, usage=parameter |
| ← | DEPENDENCY | LoanLedgerSession | source_member=getActiveLedgers, usage=parameter |
| ← | DEPENDENCY | LoanLedgerSessionBean | source_member=getLedger, usage=return |
| ← | DEPENDENCY | LoanLedgerSessionBean | source_member=getActiveLedgers, usage=local_new |
| ← | DEPENDENCY | LoanLedgerSessionBean | source_member=processRepayment, usage=local_var |
| ← | DEPENDENCY | LoanLedgerSessionBean | source_member=calculateRemainingSchedule, usage=local_new |

#### 호출 관계

| 방향 | 대상 | 호출코드 |
| --- | --- | --- |
| - | - | - |

#### 데이터 접근

| 대상 | 관계 | 근거 | 신뢰도 |
| --- | --- | --- | --- |
| - | - | - | - |

#### 요약 코드

```
없음
```

### LoanScreeningException

#### 기본 정보

| 항목 | 값 |
| --- | --- |
| 이름 | LoanScreeningException |
| 타입 | CLASS |
| FQN | com.banking.loan.exception.LoanScreeningException |
| 패키지 | com.banking.loan.exception |
| 스테레오타입 | - |
| 파일 | - |
| 라인 | - |
| 토큰 | - |

#### 요약

> com.banking.loan.exception.LoanScreeningException은 대출 심사(loan screening) 과정에서 발생하는 오류 상황을 표현하기 위한 예외 클래스입니다. 예외 객체의 직렬화/역직렬화 호환성을 유지하기 위해 serialVersionUID를 정의하고 있습니다. 이를 통해 대출 심사 로직에서 오류를 명확히 구분해 상위 계층으로 전파하거나 처리할 수 있도록 책임집니다.

#### 메서드

| 이름 | 시그니처 | 반환타입 | 수정자 | 요약 |
| --- | --- | --- | --- | --- |
| - | - | - | - | - |

#### 필드

| 이름 | 타입 | 수정자 | 요약 |
| --- | --- | --- | --- |
| serialVersionUID | long | - | serialVersionUID; lines 5-5 |

#### 구조 관계

| 방향 | 관계 | 대상 | 속성 |
| --- | --- | --- | --- |
| ← | DEPENDENCY | LoanProcessSession | source_member=requestScreening, usage=local_var |
| ← | DEPENDENCY | LoanProcessSessionBean | source_member=requestScreening, usage=local_var |
| ← | DEPENDENCY | LoanScreeningSession | source_member=approveApplication, usage=parameter |
| ← | DEPENDENCY | LoanScreeningSession | source_member=rejectApplication, usage=local_var |
| ← | DEPENDENCY | LoanScreeningSessionBean | source_member=rejectApplication, usage=local_new |
| ← | DEPENDENCY | LoanScreeningSessionBean | source_member=getCreditScreening, usage=local_new |

#### 호출 관계

| 방향 | 대상 | 호출코드 |
| --- | --- | --- |
| - | - | - |

#### 데이터 접근

| 대상 | 관계 | 근거 | 신뢰도 |
| --- | --- | --- | --- |
| - | - | - | - |

#### 요약 코드

```
없음
```

### DebtCollectionSession

#### 기본 정보

| 항목 | 값 |
| --- | --- |
| 이름 | DebtCollectionSession |
| 타입 | CLASS |
| FQN | com.banking.loan.session.DebtCollectionSession |
| 패키지 | com.banking.loan.session |
| 스테레오타입 | COMMAND/READMODEL |
| 파일 | - |
| 라인 | - |
| 토큰 | - |

#### 요약

> 이 클래스는 채권 회수(추심) 업무를 원격으로 제공하는 세션 빈 리모트 컴포넌트 인터페이스로, 추심 대상 조회부터 추심 개시, 추심 입금, 대손(상각) 처리까지의 전반 흐름을 다룬다(추심 대상 조회 → 추심 개시 → 추심 입금 처리 → 대손 처리). 그중에서도 연체/추심 건 식별자를 기준으로 추심 상세 정보를 조회하고, 대손 처리된 원장 내역 목록을 조회하는 책임을 가진다. 원격 호출 특성상 통신/리모트 실행 과정에서 예외가 발생할 수 있으며, 식별자 오류·미존재 등 도메인 규칙 위반이나 처리 불가 상황은 연체/추심 관련 업무 예외로 호출자에게 전달되도록 계약이 정의되어 있다.

#### 메서드

| 이름 | 시그니처 | 반환타입 | 수정자 | 요약 |
| --- | --- | --- | --- | --- |
| getCollectionTargets | Collection getCollectionTargets()             throws RemoteException, DelinquencyException | - | - | 채권 회수 업무를 원격으로 제공하는 계약 중, 추심 대상으로 삼을 항목들의 목록을 조회해 컬렉션 형태로 반환하는 기능을 정의한다. 이 기능은 실제 구현에서 원격 통신 계층의 장애가 발생하면 원격 호출 예외를 호출자에게 전달할 수 있다. 또한 연체/추심 도메인 규칙 위반이나 처리 불가 상황이 발생하면 도메인 예외를 호출자에게 전달하도록 선언되어 있다. 즉, 상태를 변경하기보다 추심 대상 조회 결과를 제공하는 읽기 중심의 인터페이스다. |
| initiateCollection | void initiateCollection(String delinquencyId)             throws RemoteException, DelinquencyException | - | - | 채권 회수 관련 원격 컴포넌트 인터페이스에서, 지정된 연체/추심 대상 식별자를 기준으로 추심 절차를 개시하도록 요청하는 계약(시그니처)이다. 호출 측은 이 요청을 통해 추심이 ‘시작됨’에 해당하는 업무 상태 변경이 발생할 수 있음을 전제로 한다. 원격 호출 특성상 통신/원격 처리 실패에 해당하는 예외가 발생할 수 있고, 연체/추심 도메인 규칙 위반이나 처리 불가 상황을 나타내는 도메인 예외도 함께 전달될 수 있다. |
| processCollectionPayment | void processCollectionPayment(String delinquencyId, BigDecimal amount)             throws RemoteException, DelinquencyException | - | - | 이 컴포넌트 인터페이스는 채권 회수 업무(추심 대상 처리, 추심 개시, 입금, 대손 처리 등) 중에서, 특정 연체/추심 건을 식별하는 값과 입금 금액을 입력으로 받아 회수 입금 처리를 수행하도록 정의한다. 처리 결과로 별도의 값을 돌려주지 않으며, 원격 호출 환경에서의 통신 오류가 발생할 수 있음을 전제로 예외를 외부로 전파한다. 또한 연체/추심 도메인 규칙 위반이나 처리 실패 상황을 나타내는 도메인 예외를 발생시켜, 입금 처리의 실패 원인을 호출자에게 명확히 전달하도록 한다. |
| writeOff | void writeOff(String ledgerId, String reason)             throws RemoteException, DelinquencyException | - | - | 채권 회수 관련 원격 컴포넌트 인터페이스의 계약으로, 특정 원장 항목을 대손(상각) 처리하기 위한 요청을 정의한다. 호출자는 원장 항목을 식별하는 값과 대손 처리 사유를 함께 전달하며, 처리 결과는 반환값 없이 수행 성공/실패로 구분된다. 업무 규칙 위반이나 연체 상태 불일치 등으로 처리가 불가능한 경우에는 연체/추심 도메인 예외가 발생할 수 있다. 또한 원격 호출 환경에서 통신/전송 오류가 발생할 수 있음을 예외 선언으로 명시한다. |
| getWrittenOffLedgers | Collection getWrittenOffLedgers()             throws RemoteException, DelinquencyException | - | - | 이 리모트 컴포넌트 인터페이스는 채권 회수 업무(추심 대상 조회, 추심 개시, 추심 입금, 대손 처리 등) 중에서 대손(상각) 처리된 원장 내역들을 조회하기 위한 기능을 제공한다. 호출자는 대손 처리된 원장들의 목록을 컬렉션 형태로 전달받아, 후속 추심/정산/대손 관리 흐름에서 참조할 수 있다. 원격 호출 환경이므로 통신·리모트 실행 과정에서 원격 예외가 발생할 수 있으며, 연체/추심 도메인 규칙 위반이나 처리 불가 상황은 연체 관련 업무 예외로 전달된다. |
| getCollectionDetail | DelinquencyDTO getCollectionDetail(String delinquencyId)             throws RemoteException, DelinquencyException | - | - | 이 인터페이스는 채권 회수 업무(추심 대상 조회, 추심 개시, 추심 입금, 대손 처리 등)를 원격으로 제공하며, 이 범위의 기능은 그중 추심/연체 건의 상세 정보를 조회하는 역할을 맡는다. 입력으로 전달된 연체(추심) 식별자를 기준으로 해당 건의 상세 내용을 조회해, 상세 정보를 담은 전송용 데이터로 반환한다. 원격 호출 과정에서 통신 문제로 실패할 수 있으며, 식별자 오류·미존재 등 도메인 규칙 위반 상황에서는 업무 예외로 조회가 중단될 수 있음을 계약으로 명시한다. |

#### 필드

| 이름 | 타입 | 수정자 | 요약 |
| --- | --- | --- | --- |
| - | - | - | - |

#### 구조 관계

| 방향 | 관계 | 대상 | 속성 |
| --- | --- | --- | --- |
| → | DEPENDENCY | DelinquencyDTO | source_member=getCollectionDetail, usage=return |
| → | DEPENDENCY | DelinquencyException | source_member=processCollectionPayment, usage=return |
| → | DEPENDENCY | DelinquencyException | source_member=writeOff, usage=parameter |
| → | DEPENDENCY | DelinquencyException | source_member=getCollectionDetail, usage=parameter |
| → | DEPENDENCY | DelinquencyException | source_member=initiateCollection, usage=parameter |
| → | DEPENDENCY | DelinquencyException | source_member=getWrittenOffLedgers, usage=parameter |
| → | DEPENDENCY | DelinquencyException | source_member=getCollectionTargets, usage=parameter |
| ← | DEPENDENCY | LoanServlet | source_member=handleCollectionPayment, usage=local_var |
| ← | DEPENDENCY | DebtCollectionSessionHome | source_member=create, usage=return |

#### 호출 관계

| 방향 | 대상 | 호출코드 |
| --- | --- | --- |
| ← | LoanServlet | - |

#### 데이터 접근

| 대상 | 관계 | 근거 | 신뢰도 |
| --- | --- | --- | --- |
| DelinquencyException | REFER_TO | - | 1.0 |
| DelinquencyException | REFER_TO | - | 1.0 |
| DelinquencyException | REFER_TO | - | 1.0 |
| DelinquencyException | REFER_TO | - | 1.0 |
| DelinquencyException | REFER_TO | - | 1.0 |
| DelinquencyDTO | REFER_TO | - | 1.0 |
| DelinquencyException | REFER_TO | - | 1.0 |

#### 요약 코드

```
없음
```

### DebtCollectionSessionBean

#### 기본 정보

| 항목 | 값 |
| --- | --- |
| 이름 | DebtCollectionSessionBean |
| 타입 | CLASS |
| FQN | com.banking.loan.session.DebtCollectionSessionBean |
| 패키지 | com.banking.loan.session |
| 스테레오타입 | COMMAND/READMODEL |
| 파일 | - |
| 라인 | - |
| 토큰 | - |

#### 요약

> 이 클래스는 채권 회수 Stateless 세션 빈 구현체로서 추심 대상 관리, 추심 입금 처리, 대손상각(write-off) 등 채권 회수 업무 전반을 처리하며, 연체등급(delinquencyGrade)이 DELINQUENCY_GRADE_3/4/5 중 하나인 경우에만 ‘3등급 이상(악화)’(>= GRADE_3)으로 판정해 추심/상각 의사결정 조건에 활용한다. 추심 개시 시 연체 status를 … → LoanConstants.DELINQUENCY_COLLECTION로 전이시키고, 회수 입금 후 remaining(= delinquencyAmount - 입금금액)이 0 이하(<= 0)이면 연체를 … → LoanConstants.DELINQUENCY_RESOLVED로 해소하며, 원장(outstandingBalance)이 0 이하(<= 0)면 … → LoanConstants.LEDGER_COMPLETED로 종료하고 잔액이 남더라도 다른 연체가 없을 때만 … → LoanConstants.LEDGER_ACTIVE로 복귀시킨다. 대손상각 확정 시 원장 status를 … → LoanConstants.LEDGER_WRITTEN_OFF로 변경하고, 연결된 연체 중 LoanConstants.DELINQUENCY_RESOLVED가 아닌 건만 … → LoanConstants.DELINQUENCY_WRITTEN_OFF로 전이시킨다. 한편 생성/제거/활성화/패시베이션 생명주기 콜백(ejbCreate/ejbRemove/ejbActivate/ejbPassivate)은 모두 no-op로 구현되어 별도 초기화나 정리 작업을 하지 않으며, 컨테이너 기능 접근을 위한 세션 컨텍스트(ctx)와 직렬화 호환성을 위한 serialVersionUID=1L만을 가진다.

#### 메서드

| 이름 | 시그니처 | 반환타입 | 수정자 | 요약 |
| --- | --- | --- | --- | --- |
| getCollectionTargets | public Collection getCollectionTargets() throws DelinquencyException | - | - | 채권 회수 업무에서 추심 대상 관리를 지원하기 위해, 런타임에 연체 정보에 접근할 수 있는 로컬 홈을 확보한 뒤 연체 상태가 LoanConstants.DELINQUENCY_COLLECTION 인 항목들을 조회한다. 조회 결과로 얻은 연체 항목 컬렉션은 화면/응답에 적합한 전송 객체 컬렉션으로 변환하여 반환한다. 상태 기반 조회 과정에서 조회 실패 예외가 발생하면 '추심 대상 조회 실패' 메시지로 업무 예외를 감싸 상위로 전달한다. JNDI 이름 조회 과정에서 네이밍 예외가 발생하면 'JNDI 조회 실패: {원인 메시지}' 형태로 원인 메시지를 포함해 동일한 업무 예외로 변환하여 전달한다. |
| initiateCollection | public void initiateCollection(String delinquencyId) throws DelinquencyException | - | - | 채권 회수 업무 흐름에서 입력된 연체 식별자로 연체 정보를 조회한 뒤, 해당 연체의 delinquencyGrade(연체등급)가 GRADE_3 이상인 경우에만 추심을 개시하도록 비즈니스 규칙을 강제한다. 등급이 기준에 미달하면 "추심 개시 불가: 현재 등급 {등급} (GRADE_3 이상만 추심 가능)" 메시지로 업무 예외를 발생시켜 상태 전이를 차단한다. 기준을 통과하면 연체 정보의 status(상태)를 LoanConstants.DELINQUENCY_COLLECTION 값으로 변경하여 추심 단계로 상태를 확정한다. 조회 실패(FinderException), JNDI 조회 실패(NamingException), 또는 업무 예외가 발생하면 트랜잭션을 rollback-only로 마킹한 후 원인 정보를 포함해 업무 예외로 재전달한다. |
| processCollectionPayment | public void processCollectionPayment(String delinquencyId, BigDecimal amount)             throws DelinquencyException | - | - | 채권 회수 업무 맥락에서 연체 식별자와 입금 금액을 받아, 연체가 연결된 ledgerId(원장 식별자)를 기준으로 여신 원장과 연체 정보를 조회한 뒤 회수 입금('COLLECTION') 상환 기록을 신규 생성하고 원장에 원금 상환을 반영한다. 이후 delinquencyAmount(연체금액)에서 입금 금액을 차감해 remaining이 0 이하(<= 0)이면 연체를 repaymentDate(해소일자)로 해소 처리하고, 원장의 outstandingBalance가 0 이하(<= 0)이면 status를 LoanConstants.LEDGER_COMPLETED로 변경한다. 원장 잔액이 남아 있으면 동일 ledgerId에 대해 다른 연체 목록을 조회해, 현재 건을 제외한 다른 건 중 status가 LoanConstants.DELINQUENCY_ACTIVE 또는 LoanConstants.DELINQUENCY_COLLECTION인 항목이 없을 때에만 원장 status를 LoanConstants.LEDGER_ACTIVE로 되돌린다. remaining이 0 초과(> 0)인 경우에는 연체금액을 remaining으로 갱신해 부분 상환 상태를 확정한다. 조회(FinderException)·상환 생성(CreateException)·JNDI 조회(NamingException) 실패 시에는 트랜잭션 롤백 마킹 후 업무 예외로 변환해 실패 원인을 포함해 재전파한다. |
| writeOff | public void writeOff(String ledgerId, String reason) throws DelinquencyException | - | - | 채권 회수 업무 맥락에서 특정 원장 식별자(ledgerId)에 대해 대손상각(write-off)을 확정하기 위해, 먼저 원장 정보를 기본키로 조회한 뒤 status를 LoanConstants.LEDGER_WRITTEN_OFF로 변경해 원장 상태를 상각 상태로 확정한다. 이어서 같은 원장 식별자에 연결된 연체 목록을 조회하고, 각 연체 건의 status가 LoanConstants.DELINQUENCY_RESOLVED가 아닌 경우에만 LoanConstants.DELINQUENCY_WRITTEN_OFF로 변경하여 미해결 연체를 상각 상태로 전이시킨다. 조회 과정에서 FinderException(원장/연체 조회 실패) 또는 NamingException(JNDI 조회 실패)이 발생하면 트랜잭션을 롤백 전용으로 표시한 뒤, 원장 식별자 또는 예외 메시지를 포함한 도메인 예외로 감싸 상위로 전달한다. 두 번째 입력값인 reason(사유)은 메서드 내부 로직에서 실제 상태 변경이나 메시지 구성에 사용되지 않는다. |
| getWrittenOffLedgers | public Collection getWrittenOffLedgers() throws DelinquencyException | - | - | 채권 회수 업무를 담당하는 구성요소에서, 대손상각(write-off) 상태로 분류된 여신 원장 목록을 조회해 반환한다. 로컬 홈을 통해 상태값이 LoanConstants.LEDGER_WRITTEN_OFF 인 원장들을 조회한 뒤, 조회된 각 원장에 대해 ledgerId, applicationId, customerId, principalAmount, outstandingBalance, interestRate, loanStartDate, maturityDate, repaymentMethod, monthlyPayment, status, lastRepaymentDate, nextRepaymentDate 값을 복사해 전송용 데이터 묶음을 구성한다. 조회 결과 엔티티 컬렉션을 순회하면서 새 전송 객체를 반복 생성해 리스트에 누적하고, 최종적으로 그 리스트를 반환한다. 조회 과정에서 FinderException 또는 NamingException 이 발생하면 각각 '대손 처리 원장 조회 실패', 'JNDI 조회 실패: ...' 메시지로 감싼 도메인 예외를 발생시켜 상위 흐름에 오류를 전달한다. |
| getCollectionDetail | public DelinquencyDTO getCollectionDetail(String delinquencyId) throws DelinquencyException | - | - | 이 코드는 채권 회수 업무(추심 대상 관리, 추심 입금 처리, 대손상각 등) 중에서 특정 연체 건의 추심 상세 정보를 조회해 반환하는 역할을 한다. 입력으로 받은 연체 식별값을 이용해 런타임에 확보한 로컬 홈 인터페이스를 통해 해당 식별값의 연체 정보를 단건 조회한다. 조회된 연체 로컬 컴포넌트를 화면/응답에 쓰기 위한 전송용 객체 형태로 변환하여 반환함으로써, 조회 결과를 도메인 내부 표현과 분리해 제공한다. 조회 과정에서 대상이 없거나 조회 실패가 발생하면 조회 실패 메시지에 식별값을 포함해 업무 예외로 감싸 던지고, 이름 서비스(JNDI) 조회 실패도 별도 메시지로 업무 예외로 전환해 호출자가 처리하도록 한다. |
| isGrade3OrWorse | private boolean isGrade3OrWorse(String grade) | - | - | 채권 회수 업무 흐름에서 연체(또는 추심) 등급 문자열이 특정 기준 이상으로 악화되었는지 판정하기 위한 불리언 검증 로직이다. 입력된 등급 값이 DELINQUENCY_GRADE_3, DELINQUENCY_GRADE_4, DELINQUENCY_GRADE_5 중 하나와 동일하면 true를 반환하고, 그 외에는 false를 반환한다. 비교는 상수에 대해 equals로 수행되어 기준 값이 null이더라도 안전하게 비교되도록 구성되어 있다. 이 판정 결과는 이후 추심 처리나 대손상각(write-off) 같은 후속 의사결정에서 ‘3등급 이상(악화)’ 여부 조건으로 활용될 수 있다. |
| getLoanLedgerHome | private LoanLedgerLocalHome getLoanLedgerHome() throws NamingException | - | - | 채권 회수 업무를 수행하는 구성요소에서, 여신 원장 엔티티에 접근하기 위한 로컬 홈 참조를 확보하는 역할을 한다. JNDI 룩업 결과를 캐싱하는 로케이터를 통해 LoanConstants.JNDI_LOAN_LEDGER_ENTITY로 지정된 자원을 로컬 홈 타입으로 조회해 반환한다. 조회 과정에서 이름 해석 실패 가능성이 있으므로 NamingException을 호출자에게 전달해 상위 흐름에서 오류 처리를 강제한다. 이 로직은 데이터 변경 없이 접근 경로(핸들)만 조회·제공한다. |
| getDelinquencyHome | private DelinquencyLocalHome getDelinquencyHome() throws NamingException | - | - | 채권 회수 업무에서 연체 정보를 다루기 위해, 연체 엔티티에 접근할 수 있는 로컬 홈 인터페이스를 런타임에 확보한다. JNDI 룩업 결과를 캐싱하는 패턴 구현체를 통해 단일 인스턴스를 얻은 뒤, 연체 엔티티에 대응하는 JNDI 이름 상수를 사용해 로컬 홈을 조회한다. 조회 결과는 연체 엔티티 로컬 홈 타입으로 변환해 반환하며, 이름 조회 실패 시 NamingException을 상위로 전달해 호출자가 처리하도록 한다. |
| getRepaymentHome | private RepaymentLocalHome getRepaymentHome() throws NamingException | - | - | 채권 회수 업무에서 상환 정보에 접근하기 위한 로컬 홈 인터페이스를 획득하는 조회성 유틸리티 동작이다. JNDI 룩업 결과를 캐싱하는 로케이터를 통해, 상환 엔티티를 가리키는 JNDI 이름 상수로 로컬 홈을 조회해 반환한다. 네이밍 룩업 과정에서 JNDI 해석 문제가 발생할 수 있으므로 네이밍 예외를 호출자에게 전파한다. |
| delinquencyEntityToDTO | private DelinquencyDTO delinquencyEntityToDTO(DelinquencyLocal entity) | - | - | 채권 회수 업무 처리 흐름에서, 연체 정보를 담고 있는 로컬 컴포넌트로부터 조회한 값을 외부 전달용 연체 정보 객체 형태로 변환해 반환한다. 변환 과정에서 delinquencyId, ledgerId, customerId, delinquencyStartDate, delinquencyAmount, delinquencyDays, delinquencyGrade, penaltyRate, penaltyAmount, status, resolutionDate를 로컬 컴포넌트에서 읽어 동일한 속성으로 그대로 복사해 채운다. 값에 대한 검증, 변환, 계산, 상태 변경은 수행하지 않고 데이터 매핑만 수행하므로, 이후 단계에서 연체 건을 식별·표시·전달하기 위한 일관된 출력 형태를 만드는 목적을 가진다. |
| delinquencyEntitiesToDTOs | private Collection delinquencyEntitiesToDTOs(Collection entities) | - | - | 채권 회수 업무 흐름에서 조회된 연체 정보 로컬 컴포넌트들의 묶음을, 외부 전달에 적합한 연체 정보 객체 묶음으로 일괄 변환해 반환한다. 입력으로 받은 컬렉션을 끝까지 순회하면서 각 항목을 연체 정보 로컬 컴포넌트로 해석한 뒤, 단건 변환 로직을 통해 연체 정보 객체로 바꿔 결과 목록에 누적한다. 이렇게 생성된 결과 목록을 반환하여, 연체 관련 데이터를 화면/타 시스템 전달용 구조로 정리하는 역할을 수행한다. |
| generateId | private String generateId() | - | - | 이 클래스는 채권 회수 업무(추심 대상 관리, 추심 입금 처리, 대손상각 등)를 처리하는 맥락에서, 내부 처리에 사용할 고유 식별자 문자열을 생성하는 보조 기능을 제공한다. 무작위 UUID를 생성한 뒤, 하이픈("-")을 제거하여 연속된 문자열로 정규화한다. 그 결과의 앞 20자리만 잘라 길이를 고정하고, 알파벳 문자를 대문자로 통일해 저장·전달 시 형식이 흔들리지 않도록 한다. 생성된 값은 외부 저장소나 상태를 변경하지 않고 호출자에게 그대로 반환된다. |
| setSessionContext | public void setSessionContext(SessionContext ctx) | - | - | 이 코드는 채권 회수 업무를 수행하는 Stateless 세션 빈 구현체가 런타임에 사용할 세션 컨텍스트를 외부로부터 전달받아 내부에 보관하도록 한다. 전달된 컨텍스트 참조를 인스턴스의 필드에 저장함으로써, 이후 처리에서 트랜잭션/보안/롤백 표시 등 컨테이너가 제공하는 실행 환경 정보에 접근할 수 있게 준비한다. 별도의 검증, 분기, 예외 처리 없이 입력으로 받은 값을 그대로 내부 상태로 반영한다. |
| ejbCreate | public void ejbCreate() throws CreateException | - | - | 이 코드는 채권 회수 업무를 담당하는 Stateless 세션 빈의 생성 시점에 호출되는 생명주기 초기화 훅을 정의한다. 다만 본문이 비어 있어 생성 시 별도의 초기화, 검증, 외부 자원 조회/저장 같은 처리를 수행하지 않는다. 생성 과정에서 오류가 발생할 수 있음을 고려해 생성 예외를 선언하지만, 실제로 예외를 발생시키거나 처리하는 로직은 포함되어 있지 않다. |
| ejbRemove | public void ejbRemove() | - | - | 이 구성요소는 채권 회수 업무(추심 대상 관리, 추심 입금 처리, 대손상각 등)를 처리하는 무상태 세션 빈 구현체의 일부이며, 여기서는 인스턴스 제거 시점에 호출되는 생명주기 훅을 제공한다. 그러나 제거 시 수행해야 할 정리 작업(자원 해제, 상태 저장, 세션 컨텍스트 처리 등)이 구현되어 있지 않아 실제로는 아무 동작도 하지 않는다. 따라서 채권 회수 도메인 데이터의 변경이나 조회, 외부 리소스 접근 없이 종료되는 빈 구현이다. |
| ejbActivate | public void ejbActivate() | - | - | 이 코드는 채권 회수 업무를 처리하는 Stateless 세션 빈의 생명주기 중, 인스턴스가 활성화될 때 호출되는 콜백 지점에 해당한다. 현재 구현은 본문이 비어 있어 활성화 시점에 추가 초기화, 상태 복원, 자원 확보 등의 처리를 수행하지 않는다. 따라서 채권 추심 대상 관리, 추심 입금 처리, 대손상각 등 도메인 상태를 변경하거나 조회하는 로직이 이 범위에는 포함되어 있지 않다. |
| ejbPassivate | public void ejbPassivate() | - | - | 이 컴포넌트는 채권 회수 업무(추심 대상 관리, 추심 입금 처리, 대손상각 등)를 처리하는 Stateless 세션 빈 구현체이며, 이 구간은 컨테이너 생명주기에서 인스턴스가 패시베이션될 때 호출되는 콜백 지점이다. 그러나 본문이 비어 있어 패시베이션 시점에 자원 정리, 상태 스냅샷 저장, 컨텍스트 처리 같은 추가 동작을 수행하지 않는다. 따라서 이 콜백은 의도적으로 무동작(no-op)으로 두어, 생명주기 이벤트를 수용하되 업무 데이터나 외부 자원에 영향을 주지 않도록 구성되어 있다. |

#### 필드

| 이름 | 타입 | 수정자 | 요약 |
| --- | --- | --- | --- |
| serialVersionUID | long | - | 이 클래스가 직렬화(Serializable)될 때 버전 호환성을 확인하기 위한 고정 식별자(Serial Version UID)로, 값은 1L로 설정되어 있습니다. |
| ctx | SessionContext | - | 채권 회수 업무를 수행하는 Stateless 세션 빈에서 EJB 실행 환경 정보를 제공하는 세션 컨텍스트를 보관하는 필드로, 트랜잭션·보안·호출자 정보 조회나 컨테이너 제공 기능 접근 등에 사용된다. |

#### 구조 관계

| 방향 | 관계 | 대상 | 속성 |
| --- | --- | --- | --- |
| → | ASSOCIATION | SessionContext | source_member=initiateCollection |
| → | DEPENDENCY | DelinquencyDTO | source_member=delinquencyEntityToDTO, usage=local_new |
| → | DEPENDENCY | LoanLedgerDTO | source_member=getWrittenOffLedgers, usage=local_new |
| → | DEPENDENCY | DelinquencyLocal | source_member=delinquencyEntityToDTO, usage=parameter |
| → | DEPENDENCY | DelinquencyLocal | source_member=processCollectionPayment, usage=local_var |
| → | DEPENDENCY | DelinquencyLocal | source_member=delinquencyEntitiesToDTOs, usage=cast |
| → | DEPENDENCY | DelinquencyLocalHome | source_member=getDelinquencyHome, usage=return |
| → | DEPENDENCY | DelinquencyLocalHome | source_member=getCollectionTargets, usage=local_var |
| → | DEPENDENCY | DelinquencyLocalHome | source_member=processCollectionPayment, usage=local_var |
| → | DEPENDENCY | LoanLedgerLocal | source_member=writeOff, usage=local_var |
| → | DEPENDENCY | LoanLedgerLocal | source_member=processCollectionPayment, usage=local_var |
| → | DEPENDENCY | LoanLedgerLocalHome | source_member=getLoanLedgerHome, usage=return |
| → | DEPENDENCY | LoanLedgerLocalHome | source_member=writeOff, usage=local_var |
| → | DEPENDENCY | LoanLedgerLocalHome | source_member=processCollectionPayment, usage=local_var |
| → | DEPENDENCY | RepaymentLocalHome | source_member=getRepaymentHome, usage=return |
| → | DEPENDENCY | RepaymentLocalHome | source_member=processCollectionPayment, usage=local_var |
| → | DEPENDENCY | DelinquencyException | source_member=getCollectionTargets, usage=local_new |
| → | DEPENDENCY | DelinquencyException | source_member=processCollectionPayment, usage=local_new |
| → | DEPENDENCY | LoanConstants | source_member=getLoanLedgerHome, usage=local_var |
| → | DEPENDENCY | LoanConstants | source_member=isGrade3OrWorse, usage=local_var |
| → | DEPENDENCY | LoanConstants | source_member=getRepaymentHome, usage=field_call |
| → | DEPENDENCY | LoanConstants | source_member=getCollectionTargets, usage=field_call |
| → | DEPENDENCY | LoanConstants | source_member=processCollectionPayment, usage=local_var |
| → | DEPENDENCY | ServiceLocator | source_member=getLoanLedgerHome, usage=local_var |
| → | DEPENDENCY | ServiceLocator | source_member=getRepaymentHome, usage=field_call |
| → | DEPENDENCY | SessionContext | source_member=setSessionContext, usage=parameter |

#### 호출 관계

| 방향 | 대상 | 호출코드 |
| --- | --- | --- |
| → | DelinquencyDTO | - |
| → | LoanLedgerDTO | - |
| → | DelinquencyLocal | - |
| → | DelinquencyLocalHome | - |
| → | LoanLedgerLocal | - |
| → | LoanLedgerLocalHome | - |
| → | RepaymentLocalHome | - |
| → | DelinquencyLocalHome | 40:             Collection entities = home.findByStatus(LoanConstants.DELINQUENCY_COLLECTION); |
| → | DebtCollectionSessionBean | 39:             DelinquencyLocalHome home = getDelinquencyHome(); |
| → | DelinquencyLocal | 54:             String grade = entity.getDelinquencyGrade(); |
| → | DelinquencyLocal | 60:             entity.setStatus(LoanConstants.DELINQUENCY_COLLECTION); |
| → | DelinquencyLocalHome | 52:             DelinquencyLocal entity = home.findByPrimaryKey(delinquencyId); |
| → | DebtCollectionSessionBean | 51:             DelinquencyLocalHome home = getDelinquencyHome(); |
| → | DelinquencyLocal | 79:             String ledgerId = delinquency.getLedgerId(); |
| → | DelinquencyLocal | 96:             BigDecimal delinquencyAmount = delinquency.getDelinquencyAmount(); |
| → | DelinquencyLocal | 121:                 delinquency.setDelinquencyAmount(remaining); |
| → | DelinquencyLocal | 99:                 delinquency.resolve(repaymentDate); |
| → | DelinquencyLocalHome | 77:             DelinquencyLocal delinquency = delinquencyHome.findByPrimaryKey(delinquencyId); |
| → | DelinquencyLocalHome | 105:                     Collection others = delinquencyHome.findByLedgerId(ledgerId); |
| → | LoanLedgerLocal | 102:                     ledger.setStatus(LoanConstants.LEDGER_COMPLETED); |
| → | LoanLedgerLocal | 94:             ledger.applyRepayment(amount, BigDecimal.ZERO); |
| → | LoanLedgerLocalHome | 82:             LoanLedgerLocal ledger = ledgerHome.findByPrimaryKey(ledgerId); |
| → | RepaymentLocalHome | 89:             repaymentHome.create( 90:                     repaymentId, ledgerId, repaymentDate, 91:                     amount, BigDecimal.ZERO, BigDecimal.ZERO, 92:                     "COLLECTIO |
| → | DebtCollectionSessionBean | 81:             LoanLedgerLocalHome ledgerHome = getLoanLedgerHome(); |
| → | DebtCollectionSessionBean | 76:             DelinquencyLocalHome delinquencyHome = getDelinquencyHome(); |
| → | DebtCollectionSessionBean | 88:             RepaymentLocalHome repaymentHome = getRepaymentHome(); |
| → | DebtCollectionSessionBean | 84:             String repaymentId = generateId(); |
| → | DelinquencyLocal | 148:                     d.setStatus(LoanConstants.DELINQUENCY_WRITTEN_OFF); |
| → | DelinquencyLocalHome | 143:             Collection delinquencies = delinquencyHome.findByLedgerId(ledgerId); |
| → | LoanLedgerLocal | 140:             ledger.setStatus(LoanConstants.LEDGER_WRITTEN_OFF); |
| → | LoanLedgerLocalHome | 138:             LoanLedgerLocal ledger = ledgerHome.findByPrimaryKey(ledgerId); |
| → | DebtCollectionSessionBean | 137:             LoanLedgerLocalHome ledgerHome = getLoanLedgerHome(); |
| → | DebtCollectionSessionBean | 142:             DelinquencyLocalHome delinquencyHome = getDelinquencyHome(); |
| → | LoanLedgerDTO | 170:                 dto.setLedgerId(entity.getLedgerId()); |
| → | LoanLedgerDTO | 171:                 dto.setApplicationId(entity.getApplicationId()); |
| → | LoanLedgerDTO | 172:                 dto.setCustomerId(entity.getCustomerId()); |
| → | LoanLedgerDTO | 173:                 dto.setPrincipalAmount(entity.getPrincipalAmount()); |
| → | LoanLedgerDTO | 174:                 dto.setOutstandingBalance(entity.getOutstandingBalance()); |
| → | LoanLedgerDTO | 175:                 dto.setInterestRate(entity.getInterestRate()); |
| → | LoanLedgerDTO | 176:                 dto.setLoanStartDate(entity.getLoanStartDate()); |
| → | LoanLedgerDTO | 177:                 dto.setMaturityDate(entity.getMaturityDate()); |
| → | LoanLedgerDTO | 178:                 dto.setRepaymentMethod(entity.getRepaymentMethod()); |
| → | LoanLedgerDTO | 179:                 dto.setMonthlyPayment(entity.getMonthlyPayment()); |
| → | LoanLedgerDTO | 180:                 dto.setStatus(entity.getStatus()); |
| → | LoanLedgerDTO | 181:                 dto.setLastRepaymentDate(entity.getLastRepaymentDate()); |
| → | LoanLedgerDTO | 182:                 dto.setNextRepaymentDate(entity.getNextRepaymentDate()); |
| → | LoanLedgerLocalHome | 163:             Collection entities = home.findByStatus(LoanConstants.LEDGER_WRITTEN_OFF); |
| → | DebtCollectionSessionBean | 162:             LoanLedgerLocalHome home = getLoanLedgerHome(); |
| → | DelinquencyLocalHome | 196:             DelinquencyLocal entity = home.findByPrimaryKey(delinquencyId); |
| → | DebtCollectionSessionBean | 195:             DelinquencyLocalHome home = getDelinquencyHome(); |
| → | DelinquencyDTO | 230:         dto.setDelinquencyId(entity.getDelinquencyId()); |
| → | DelinquencyDTO | 231:         dto.setLedgerId(entity.getLedgerId()); |
| → | DelinquencyDTO | 232:         dto.setCustomerId(entity.getCustomerId()); |
| → | DelinquencyDTO | 233:         dto.setDelinquencyStartDate(entity.getDelinquencyStartDate()); |
| → | DelinquencyDTO | 234:         dto.setDelinquencyAmount(entity.getDelinquencyAmount()); |
| → | DelinquencyDTO | 235:         dto.setDelinquencyDays(entity.getDelinquencyDays()); |
| → | DelinquencyDTO | 236:         dto.setDelinquencyGrade(entity.getDelinquencyGrade()); |
| → | DelinquencyDTO | 237:         dto.setPenaltyRate(entity.getPenaltyRate()); |
| → | DelinquencyDTO | 238:         dto.setPenaltyAmount(entity.getPenaltyAmount()); |
| → | DelinquencyDTO | 239:         dto.setStatus(entity.getStatus()); |
| → | DelinquencyDTO | 240:         dto.setResolutionDate(entity.getResolutionDate()); |
| → | DebtCollectionSessionBean | 249:             dtos.add(delinquencyEntityToDTO(entity)); |

#### 데이터 접근

| 대상 | 관계 | 근거 | 신뢰도 |
| --- | --- | --- | --- |
| DELINQUENCY | READS | - | - |
| DelinquencyLocal | REFER_TO | - | 1.0 |
| DelinquencyLocalHome | REFER_TO | - | 1.0 |
| DelinquencyException | REFER_TO | - | 1.0 |
| LoanConstants | REFER_TO | - | 1.0 |
| ejb-jar.xml | REFER_TO | - | 0.9 |
| DELINQUENCY | WRITES | - | - |
| DELINQUENCY | READS | - | - |
| DelinquencyLocal | REFER_TO | - | 1.0 |
| DelinquencyLocalHome | REFER_TO | - | 1.0 |
| DelinquencyException | REFER_TO | - | 1.0 |
| LoanConstants | REFER_TO | - | 1.0 |
| ejb-jar.xml | REFER_TO | - | 0.9 |
| REPAYMENT | WRITES | - | - |
| DELINQUENCY | WRITES | - | - |
| LOAN_LEDGER | WRITES | - | - |
| REPAYMENT | READS | - | - |
| DELINQUENCY | READS | - | - |
| LOAN_LEDGER | READS | - | - |
| DelinquencyLocal | REFER_TO | - | 1.0 |
| DelinquencyLocalHome | REFER_TO | - | 1.0 |
| LoanLedgerLocal | REFER_TO | - | 1.0 |
| LoanLedgerLocalHome | REFER_TO | - | 1.0 |
| RepaymentLocal | REFER_TO | - | 1.0 |
| RepaymentLocalHome | REFER_TO | - | 1.0 |
| DelinquencyException | REFER_TO | - | 1.0 |
| LoanConstants | REFER_TO | - | 1.0 |
| ejb-jar.xml | REFER_TO | - | 0.9 |
| ejb-jar.xml | REFER_TO | - | 0.9 |
| ejb-jar.xml | REFER_TO | - | 0.9 |
| DELINQUENCY | WRITES | - | - |
| LOAN_LEDGER | WRITES | - | - |
| DELINQUENCY | READS | - | - |
| LOAN_LEDGER | READS | - | - |
| DelinquencyLocal | REFER_TO | - | 1.0 |
| DelinquencyLocalHome | REFER_TO | - | 1.0 |
| LoanLedgerLocal | REFER_TO | - | 1.0 |
| LoanLedgerLocalHome | REFER_TO | - | 1.0 |
| DelinquencyException | REFER_TO | - | 1.0 |
| LoanConstants | REFER_TO | - | 1.0 |
| ejb-jar.xml | REFER_TO | - | 0.9 |
| ejb-jar.xml | REFER_TO | - | 0.9 |
| LOAN_LEDGER | READS | - | - |
| LoanLedgerDTO | REFER_TO | - | 1.0 |
| LoanLedgerLocal | REFER_TO | - | 1.0 |
| LoanLedgerLocalHome | REFER_TO | - | 1.0 |
| DelinquencyException | REFER_TO | - | 1.0 |
| LoanConstants | REFER_TO | - | 1.0 |
| ejb-jar.xml | REFER_TO | - | 0.9 |
| DELINQUENCY | READS | - | - |
| DelinquencyDTO | REFER_TO | - | 1.0 |
| DelinquencyLocal | REFER_TO | - | 1.0 |
| DelinquencyLocalHome | REFER_TO | - | 1.0 |
| DelinquencyException | REFER_TO | - | 1.0 |
| ejb-jar.xml | REFER_TO | - | 0.9 |
| LoanConstants | REFER_TO | - | 1.0 |
| LoanLedgerLocal | REFER_TO | - | 1.0 |
| LoanLedgerLocalHome | REFER_TO | - | 1.0 |
| LoanConstants | REFER_TO | - | 1.0 |
| ServiceLocator | REFER_TO | - | 1.0 |
| DelinquencyLocal | REFER_TO | - | 1.0 |
| DelinquencyLocalHome | REFER_TO | - | 1.0 |
| LoanConstants | REFER_TO | - | 1.0 |
| ServiceLocator | REFER_TO | - | 1.0 |
| REPAYMENT | READS | - | - |
| RepaymentLocal | REFER_TO | - | 1.0 |
| RepaymentLocalHome | REFER_TO | - | 1.0 |
| LoanConstants | REFER_TO | - | 1.0 |
| ServiceLocator | REFER_TO | - | 1.0 |
| ejb-jar.xml | REFER_TO | - | 0.9 |
| DelinquencyDTO | REFER_TO | - | 1.0 |
| DelinquencyLocal | REFER_TO | - | 1.0 |
| DelinquencyLocal | REFER_TO | - | 1.0 |

#### 요약 코드

```
없음
```

### DebtCollectionSessionHome

#### 기본 정보

| 항목 | 값 |
| --- | --- |
| 이름 | DebtCollectionSessionHome |
| 타입 | CLASS |
| FQN | com.banking.loan.session.DebtCollectionSessionHome |
| 패키지 | com.banking.loan.session |
| 스테레오타입 | READMODEL |
| 파일 | - |
| 라인 | - |
| 토큰 | - |

#### 요약

> 이 클래스는 채권 회수 업무를 수행하는 세션 빈을 원격으로 사용할 수 있게 해주는 리모트 홈 인터페이스이다. 원격 접근용 세션 인스턴스(원격 인터페이스 참조)를 생성해 반환하는 진입점(create)을 제공하며, 이를 통해 호출자는 추심 대상 조회, 추심 개시, 추심 입금, 대손 처리 등 채권 회수 기능을 원격으로 수행할 수 있다. 생성 과정에서 원격 호출 환경이나 생성 조건 문제를 대비해 생성 예외와 원격 통신 예외를 호출자에게 전달하도록 정의한다.

#### 메서드

| 이름 | 시그니처 | 반환타입 | 수정자 | 요약 |
| --- | --- | --- | --- | --- |
| create | DebtCollectionSession create() throws CreateException, RemoteException | - | - | 이 코드는 채권 회수 업무를 수행하는 원격 세션 컴포넌트를 사용하기 위해, 원격 접근용 세션 인스턴스(원격 인터페이스 참조)를 생성해 반환하는 진입점을 정의한다. 호출자는 이 반환값을 통해 추심 대상 조회, 추심 개시, 추심 입금, 대손 처리 등 채권 회수 관련 기능을 원격으로 수행할 수 있게 된다. 생성 과정에서 원격 호출 환경 또는 생성 조건 문제를 대비해 생성 예외와 원격 통신 예외를 호출자에게 전달하도록 선언한다. |

#### 필드

| 이름 | 타입 | 수정자 | 요약 |
| --- | --- | --- | --- |
| - | - | - | - |

#### 구조 관계

| 방향 | 관계 | 대상 | 속성 |
| --- | --- | --- | --- |
| → | DEPENDENCY | DebtCollectionSession | source_member=create, usage=return |
| ← | ASSOCIATION | LoanServlet | source_member=init |
| ← | ASSOCIATION | LoanServlet | source_member=handleCollectionPayment |

#### 호출 관계

| 방향 | 대상 | 호출코드 |
| --- | --- | --- |
| ← | LoanServlet | - |

#### 데이터 접근

| 대상 | 관계 | 근거 | 신뢰도 |
| --- | --- | --- | --- |
| DebtCollectionSession | REFER_TO | - | 1.0 |
| ejb-jar.xml | REFER_TO | - | 1.0 |

#### 요약 코드

```
없음
```

### DelinquencyMgmtSession

#### 기본 정보

| 항목 | 값 |
| --- | --- |
| 이름 | DelinquencyMgmtSession |
| 타입 | CLASS |
| FQN | com.banking.loan.session.DelinquencyMgmtSession |
| 패키지 | com.banking.loan.session |
| 스테레오타입 | COMMAND/READMODEL |
| 파일 | - |
| 라인 | - |
| 토큰 | - |

#### 요약

> 이 클래스는 연체 관리 세션 빈의 리모트 컴포넌트 인터페이스로서, 연체 등록·조회·상태변경·해소·가산이자 산출 등 연체 관리 업무를 원격 호출로 제공하는 진입점을 정의한다. 연체 식별자와 현재 연체일수(일 단위)를 받아 해당 연체 건의 상태를 현재 연체일수 기준으로 갱신하고, 연체 식별자(ID)로 특정 연체 건을 해소 상태로 전환하는 처리를 수행하도록 계약을 명시한다. 또한 원장 식별자 기준으로 연체 관련 가산이자(패널티) 총액을 계산해 금액으로 반환한다. 원격 통신/호출 실패는 RemoteException으로, 업무 규칙 위반·상태변경 불가·산출 불가 등 도메인 오류는 연체 관련 전용 예외로 호출자에게 전달하도록 되어 있다.

#### 메서드

| 이름 | 시그니처 | 반환타입 | 수정자 | 요약 |
| --- | --- | --- | --- | --- |
| registerDelinquency | DelinquencyDTO registerDelinquency(String ledgerId)             throws RemoteException, DelinquencyException | - | - | 연체 관리 리모트 컴포넌트 인터페이스의 계약으로서, 특정 원장 식별자를 입력받아 해당 원장에 대한 연체를 신규로 등록하는 처리를 정의한다. 처리 결과로는 등록된 연체의 주요 정보를 담은 데이터 전달 객체를 반환하여, 등록 직후 상태를 호출자에게 전달할 수 있게 한다. 원격 호출 환경에서 발생할 수 있는 통신 오류는 원격 예외로, 연체 등록 업무 규칙/검증 실패 등 도메인 오류는 연체 관련 예외로 호출자에게 전파하도록 선언되어 있다. |
| getDelinquency | DelinquencyDTO getDelinquency(String delinquencyId)             throws RemoteException, DelinquencyException | - | - | 연체 관리 원격 컴포넌트 인터페이스의 조회 기능으로, 연체 건을 식별하는 문자열 값을 입력받아 해당 연체 정보를 반환한다. 반환값은 연체 업무 데이터를 전달하기 위한 전송 객체 형태이며, 이를 통해 연체 등록/조회/상태변경/해소 등 연체 관리 흐름 중 ‘조회’에 해당하는 결과를 제공한다. 원격 호출 특성상 통신/원격 처리 실패를 나타내는 예외가 발생할 수 있고, 도메인 규칙 위반이나 조회 실패 등 연체 업무 오류를 나타내는 예외도 함께 선언되어 있다. |
| getDelinquenciesByCustomer | Collection getDelinquenciesByCustomer(String customerId)             throws RemoteException, DelinquencyException | - | - | 연체 등록/조회/상태변경/해소 및 가산이자 산출을 다루는 원격 컴포넌트 인터페이스에서, 특정 고객ID(customerId)에 해당하는 연체 내역들을 묶음 형태로 조회해 반환하는 계약을 정의한다. 호출자는 고객 단위로 연체 목록을 가져와 화면 표시나 후속 업무 판단에 활용할 수 있다. 원격 호출 과정에서 통신 계층 오류가 발생하면 RemoteException으로 실패할 수 있으며, 연체 도메인 규칙 위반이나 처리 불가 상황은 연체 관련 업무 예외로 전달될 수 있음을 명시한다. |
| getActiveDelinquencies | Collection getActiveDelinquencies()             throws RemoteException, DelinquencyException | - | - | 연체 등록·조회·상태변경·해소 및 가산이자 산출을 다루는 원격 컴포넌트 계약 중, 현재 활성 상태로 관리되는 연체 건들을 모아 반환하는 조회성 연산이다. 입력값 없이 활성 연체 목록을 컬렉션 형태로 제공하여, 후속 처리(예: 상태 확인, 관리 대상 선정)의 기준 데이터를 얻는 데 사용된다. 원격 호출 특성상 통신/원격 실행 문제는 원격 예외로 전달될 수 있으며, 연체 조회 과정의 업무 규칙 위반이나 처리 실패는 도메인 예외로 보고하도록 계약에 명시한다. |
| updateDelinquencyStatus | void updateDelinquencyStatus(String delinquencyId, int currentDays)             throws RemoteException, DelinquencyException | - | - | 이 인터페이스는 연체의 등록·조회·상태변경·해소·가산이자 산출 등 연체 관리 업무를 원격으로 제공하며, 이 범위의 선언은 연체 건의 상태를 변경하는 기능을 정의한다. 입력으로 연체 식별자와 현재 연체일수(일 단위)를 받아, 해당 연체 건의 상태를 현재 연체일수 기준으로 갱신하는 처리를 수행하도록 계약을 명시한다. 원격 호출 과정에서 통신/호출 오류가 발생할 수 있음을 전제로 하며, 업무 규칙 위반이나 상태변경 불가 등의 도메인 오류는 전용 예외로 호출자에게 전달한다. |
| resolveDelinquency | void resolveDelinquency(String delinquencyId)             throws RemoteException, DelinquencyException | - | - | 연체 등록·조회·상태변경·해소 등을 다루는 원격 컴포넌트 인터페이스의 일부로, 특정 연체 건을 해소 상태로 전환하는 처리를 요청하는 계약을 정의한다. 입력으로 연체 건을 식별하는 문자열 ID를 받아 해당 연체의 해소(해결) 처리가 수행되도록 한다. 원격 호출 과정의 통신/원격 처리 오류는 원격 예외로, 연체 처리 중 업무 규칙 위반이나 처리 실패는 연체 관련 도메인 예외로 호출자에게 전달되도록 선언한다. |
| calculateTotalPenalty | BigDecimal calculateTotalPenalty(String ledgerId)             throws RemoteException, DelinquencyException | - | - | 이 구성요소는 연체 등록, 조회, 상태변경, 해소, 가산이자 산출 등 연체 관리 업무를 원격으로 제공하기 위한 인터페이스이며, 이 범위의 기능은 그 중 특정 원장에 대한 가산이자(연체 패널티) 총액을 산출해 금액으로 돌려주는 역할을 정의한다. 입력으로 원장 식별자를 받아 해당 원장의 연체 관련 패널티 합계를 계산한 결과를 고정소수 금액 타입으로 반환하도록 계약을 제공한다. 원격 호출 환경에서의 통신/호출 실패 상황을 호출자에게 전달할 수 있으며, 연체 도메인 규칙 위반이나 산출 불가 등 업무 오류는 연체 관련 예외로 구분해 전달하도록 되어 있다. |

#### 필드

| 이름 | 타입 | 수정자 | 요약 |
| --- | --- | --- | --- |
| - | - | - | - |

#### 구조 관계

| 방향 | 관계 | 대상 | 속성 |
| --- | --- | --- | --- |
| → | DEPENDENCY | DelinquencyDTO | source_member=registerDelinquency, usage=return |
| → | DEPENDENCY | DelinquencyDTO | source_member=getDelinquency, usage=return |
| → | DEPENDENCY | DelinquencyException | source_member=updateDelinquencyStatus, usage=parameter |
| → | DEPENDENCY | DelinquencyException | source_member=registerDelinquency, usage=local_var |
| → | DEPENDENCY | DelinquencyException | source_member=resolveDelinquency, usage=parameter |
| → | DEPENDENCY | DelinquencyException | source_member=getDelinquency, usage=parameter |
| → | DEPENDENCY | DelinquencyException | source_member=getActiveDelinquencies, usage=parameter |
| ← | DEPENDENCY | LoanServlet | source_member=handleGetDelinquencies, usage=local_var |
| ← | DEPENDENCY | DelinquencyMgmtSessionHome | source_member=create, usage=return |

#### 호출 관계

| 방향 | 대상 | 호출코드 |
| --- | --- | --- |
| ← | LoanServlet | - |

#### 데이터 접근

| 대상 | 관계 | 근거 | 신뢰도 |
| --- | --- | --- | --- |
| DelinquencyDTO | REFER_TO | - | 1.0 |
| DelinquencyException | REFER_TO | - | 1.0 |
| DelinquencyDTO | REFER_TO | - | 1.0 |
| DelinquencyException | REFER_TO | - | 1.0 |
| DelinquencyException | REFER_TO | - | 1.0 |
| DelinquencyException | REFER_TO | - | 1.0 |
| DelinquencyException | REFER_TO | - | 1.0 |
| DelinquencyException | REFER_TO | - | 1.0 |
| DelinquencyException | REFER_TO | - | 1.0 |

#### 요약 코드

```
없음
```

### DelinquencyMgmtSessionBean

#### 기본 정보

| 항목 | 값 |
| --- | --- |
| 이름 | DelinquencyMgmtSessionBean |
| 타입 | CLASS |
| FQN | com.banking.loan.session.DelinquencyMgmtSessionBean |
| 패키지 | com.banking.loan.session |
| 스테레오타입 | COMMAND/READMODEL |
| 파일 | - |
| 라인 | - |
| 토큰 | - |

#### 요약

> 이 클래스는 연체 관리 Stateless 세션 빈 구현체로서, 연체 등록·등급 갱신·연체 해소·가산이자(패널티) 산출 등 연체 관련 업무 로직을 여신 원장(loan ledger)과 연계해 처리한다. 연체 등록 시 원장 상태를 "정상 → 연체 등록 → LoanConstants.LEDGER_DELINQUENT"로 전이시키고, 연체 해소 시 같은 ledgerId에 다른 "DELINQUENCY_ACTIVE" 연체가 하나도 없을 때에만 LoanConstants.LEDGER_ACTIVE로 복귀시킨다. 연체 목록에서는 status가 "DELINQUENCY_ACTIVE" 또는 "DELINQUENCY_COLLECTION"인 건 중 penaltyAmount가 null이 아닌 경우를 합산해 총 패널티 금액을 계산하며, 엔티티 조회/생성은 JNDI(LoanConstants.JNDI_LOAN_LEDGER_ENTITY, LoanConstants.JNDI_DELINQUENCY_ENTITY) 기반으로 수행하고 결과를 외부 전달용 DTO 목록으로 변환한다. 식별자는 UUID에서 하이픈("-")을 제거한 뒤 앞 20자리만 사용하고 알파벳은 대문자로 통일하며, 컨테이너 제공 세션 컨텍스트(ctx)를 보관해 트랜잭션/보안/리소스 접근에 활용하는 한편 활성화/패시베이션/제거 생명주기 훅은 모두 무동작(빈 구현)이다.

#### 메서드

| 이름 | 시그니처 | 반환타입 | 수정자 | 요약 |
| --- | --- | --- | --- | --- |
| registerDelinquency | public DelinquencyDTO registerDelinquency(String ledgerId) throws DelinquencyException | - | - | 입력된 여신 원장 식별자로 원장 정보를 조회한 뒤, 해당 원장의 outstandingBalance(미정산 잔액)와 customerId(고객식별자)를 읽어 연체 등록에 필요한 값으로 사용한다. 기본 가산금리(LoanConstants.DEFAULT_PENALTY_RATE)와 현재 시각을 연체 시작일로 확정하고, 신규 연체 식별자를 생성해 원장·고객·금액·이율·시작일을 묶어 연체 정보를 실제로 생성(등록)한다. 연체가 생성되면 원장 상태를 LoanConstants.LEDGER_DELINQUENT로 변경해 연체 상태 전이를 확정한 뒤, 생성된 연체 정보를 반환용 데이터로 변환해 돌려준다. 원장 조회 실패(FinderException), 연체 생성 실패(CreateException), JNDI 조회 실패(NamingException)가 발생하면 트랜잭션을 롤백 처리로 표시하고, 각각 '원장 조회 실패', '연체 등록 실패', 'JNDI 조회 실패' 메시지로 도메인 예외로 감싸 재던진다. |
| getDelinquency | public DelinquencyDTO getDelinquency(String delinquencyId) throws DelinquencyException | - | - | 연체 관리 기능의 일부로, 입력된 연체 식별자에 해당하는 연체 정보를 조회해 전송용 정보로 변환하여 반환한다. 먼저 JNDI 룩업을 통해 연체 정보 생성·조회를 위한 로컬 홈 인터페이스를 확보한 뒤, 해당 홈을 사용해 기본키(연체 식별자)로 연체 데이터를 조회한다. 조회된 연체 데이터를 전송용 객체 형태로 변환해 호출자에게 돌려준다. 조회 과정에서 엔티티 조회 실패 예외가 발생하면 "연체 조회 실패: {식별자}" 메시지로, JNDI 조회 예외가 발생하면 "JNDI 조회 실패: {원인 메시지}"로 업무 예외로 포장해 전파한다. |
| getDelinquenciesByCustomer | public Collection getDelinquenciesByCustomer(String customerId) throws DelinquencyException | - | - | 연체 관리 로직의 일부로, 입력된 customerId(고객 식별자)를 기준으로 해당 고객의 연체 목록을 조회해 반환한다. 먼저 JNDI 이름 'LoanConstants.JNDI_DELINQUENCY_ENTITY'로 연체 정보 접근을 위한 로컬 홈을 확보한 뒤, 고객 식별자로 연체 항목들을 다건 조회한다. 조회된 연체 엔티티 컬렉션은 호출자에게 직접 노출하지 않도록 DTO 컬렉션으로 변환해 반환한다. 조회 과정에서 FinderException이 발생하면 "고객별 연체 조회 실패: {customerId}" 메시지로, JNDI 조회 과정에서 NamingException이 발생하면 "JNDI 조회 실패: {원인 메시지}"로 업무 예외로 감싸 상위로 전달한다. |
| getActiveDelinquencies | public Collection getActiveDelinquencies() throws DelinquencyException | - | - | 연체 관리 로직의 일부로, 현재 상태가 'DELlNQUENCY_ACTIVE'인 활성 연체 목록을 조회해 반환한다. 조회를 위해 연체 정보를 생성·조회하는 로컬 홈을 확보한 뒤, 상태값을 조건으로 연체 항목들을 컬렉션으로 가져오고 이를 외부로 전달 가능한 형태로 변환해 돌려준다. 조회 과정에서 엔티티 조회 예외가 발생하면 "활성 연체 조회 실패" 메시지로 도메인 예외로 감싸 상위로 전달한다. JNDI 조회 과정에서 예외가 발생하면 "JNDI 조회 실패: ..." 형태로 원인 메시지를 포함해 동일한 도메인 예외로 변환하여 전파한다. |
| updateDelinquencyStatus | public void updateDelinquencyStatus(String delinquencyId, int currentDays)             throws DelinquencyException | - | - | 연체 관리 업무 흐름에서, 입력으로 받은 연체 식별자에 해당하는 연체 정보를 로컬 홈 조회를 통해 찾은 뒤 연체일수 값을 현재 일수로 갱신하여 연체 상태를 업데이트한다. 조회 과정에서 엔티티를 찾지 못하는 예외가 발생하면 트랜잭션을 롤백 전용으로 표시하고, "연체 조회 실패: {연체식별자}" 메시지로 업무 예외를 감싸 재전달한다. JNDI 조회 실패가 발생해도 동일하게 롤백 전용 처리 후 "JNDI 조회 실패: {원인메시지}" 형태로 업무 예외를 발생시켜 호출자가 실패 원인을 구분할 수 있게 한다. |
| resolveDelinquency | public void resolveDelinquency(String delinquencyId) throws DelinquencyException | - | - | 입력된 delinquencyId(연체 식별자)로 연체 정보를 조회한 뒤, 현재 시스템 시각을 해소일자(resolutionDate)로 생성해 연체 상태를 해소 처리한다. 이어서 해당 연체가 연결된 ledgerId(원장 식별자)를 가져와, 같은 ledgerId에 속한 연체 목록을 조회하고 반복 순회하면서 (1) 현재 해소 중인 delinquencyId가 아니고 (2) status가 LoanConstants.DELINQUENCY_ACTIVE인 다른 연체가 존재하는지 검사한다. 다른 활성 연체가 하나도 없을 때에만 원장 정보를 조회해 원장 status를 LoanConstants.LEDGER_ACTIVE로 변경하여, 연체가 모두 해소된 원장은 정상 활성 상태로 복귀시키는 규칙을 적용한다. 조회 과정에서 FinderException 또는 NamingException이 발생하면 트랜잭션을 롤백 전용으로 표시하고, 원인 예외를 포함한 DelinquencyException으로 변환해 상위로 전달한다. |
| calculateTotalPenalty | public BigDecimal calculateTotalPenalty(String ledgerId) throws DelinquencyException | - | - | 연체 관리 업무 로직의 일부로, 원장 식별자(ledgerId)에 연결된 연체 목록을 조회한 뒤 상태(status)가 DELINQUENCY_ACTIVE 또는 DELINQUENCY_COLLECTION인 건들만 대상으로 패널티 금액(penaltyAmount)을 합산해 총액을 반환한다. 연체 엔티티 조회는 JNDI로 확보한 로컬 홈을 통해 원장 기준 조회를 수행하며, 조회 결과 컬렉션을 순회하면서 건별 penaltyAmount가 null이 아닌 경우에만 누적 합계에 더한다. 조회 과정에서 FinderException이 발생하면 "원장별 연체 조회 실패: {ledgerId}" 메시지로, JNDI 조회 과정에서 NamingException이 발생하면 "JNDI 조회 실패: {원인메시지}"로 감싸 연체 도메인 예외로 변환해 던진다. |
| getLoanLedgerHome | private LoanLedgerLocalHome getLoanLedgerHome() throws NamingException | - | - | 연체 관련 업무 로직에서 여신 원장 엔티티에 접근하기 위해, JNDI 이름으로 로컬 홈 객체를 조회해 반환한다. 조회 시 JNDI 키로 LoanConstants.JNDI_LOAN_LEDGER_ENTITY를 사용하며, JNDI 룩업 결과 캐싱을 수행하는 로케이터를 통해 로컬 홈을 얻는다. 조회 결과는 여신 원장 엔티티의 로컬 홈 인터페이스 타입으로 캐스팅되어 호출 측에서 생성/조회 기능을 사용할 수 있게 한다. JNDI 조회 과정에서 이름 해석 문제가 발생할 수 있으므로 NamingException을 호출자에게 전파한다. |
| getDelinquencyHome | private DelinquencyLocalHome getDelinquencyHome() throws NamingException | - | - | 연체 관련 업무 로직에서 연체 정보를 생성·조회하기 위한 로컬 홈 인터페이스를 확보하기 위해, JNDI 이름 'LoanConstants.JNDI_DELINQUENCY_ENTITY'로 로컬 홈을 조회한다. 이 조회는 JNDI 룩업 결과를 캐싱하는 로케이터를 통해 수행되어 반복 룩업 비용을 줄이려는 의도를 가진다. 조회 결과는 연체 엔티티의 로컬 홈 인터페이스 타입으로 캐스팅되어 반환되며, 룩업 실패 시 NamingException을 호출자에게 전파한다. |
| entityToDTO | private DelinquencyDTO entityToDTO(DelinquencyLocal entity) | - | - | 연체 관리 기능에서 연체 엔티티에 보관된 값을 외부 전달용 연체 정보로 변환해 반환한다. 입력으로 받은 연체 데이터에서 delinquencyId, ledgerId, customerId, delinquencyStartDate, delinquencyAmount, delinquencyDays, delinquencyGrade, penaltyRate, penaltyAmount, status, resolutionDate를 각각 읽어 동일한 항목에 그대로 채워 넣는다. 값의 검증·변환·계산 없이 필드 단위로 복사만 수행하여, 이후 로직이 연체 건을 조회/표시하거나 후속 처리를 할 수 있도록 데이터 표현 형태를 맞춘다. 최종적으로 모든 속성이 채워진 연체 정보를 반환한다. |
| entitiesToDTOs | private Collection entitiesToDTOs(Collection entities) | - | - | 이 클래스는 연체 등록·등급 갱신·연체 해소·가산이자 산출 등 연체 관련 업무 로직을 처리하며, 이 범위의 로직은 연체 정보 목록을 외부 전달용 목록으로 변환하는 보조 변환 흐름을 담당한다. 입력으로 받은 연체 정보들의 묶음을 순회하면서, 각 요소를 연체 엔티티 로컬 컴포넌트 타입으로 해석한 뒤 외부 전달용 연체 정보로 변환한다. 변환된 각 결과를 새로운 목록에 순서대로 누적해 최종적으로 반환한다. 이 과정은 값 계산이나 저장 없이, 엔티티→전달 객체 변환을 반복 적용해 목록 형태로 제공하는 데 목적이 있다. |
| generateId | private String generateId() | - | - | 연체 관련 업무 로직을 처리하는 구성요소 내부에서, 이후 연체 등록이나 이력 식별 등에 사용할 임의의 식별자 문자열을 생성해 반환한다. 무작위 UUID를 생성한 뒤 하이픈("-")을 제거해 순수 영숫자 형태로 정규화한다. 그 결과 문자열의 앞 20자리만 잘라 길이를 고정하고, 알파벳 문자가 포함될 경우 대문자로 통일해 저장/전달 시 형식 차이로 인한 비교 문제를 줄인다. 외부 저장소나 설정을 참조하지 않고, 호출 시마다 새로운 값이 만들어지도록 설계되어 있다. |
| setSessionContext | public void setSessionContext(SessionContext ctx) | - | - | 이 코드는 연체 관련 업무 로직을 처리하는 Stateless 세션 빈 구현체가 런타임 컨테이너로부터 실행 컨텍스트를 전달받아 내부에 보관하는 역할을 한다. 외부에서 전달된 세션 컨텍스트를 인스턴스의 멤버 상태로 설정하여, 이후 연체 등록·등급 갱신·연체 해소·가산이자 산출 등의 처리 과정에서 트랜잭션/보안/리소스 접근 같은 컨테이너 기능을 사용할 수 있게 한다. 별도의 검증이나 분기 없이 전달된 참조를 그대로 저장하며, 저장 이후 내부 상태가 변경된다. |
| ejbCreate | public void ejbCreate() throws CreateException | - | - | 연체 등록, 등급 갱신, 연체 해소, 가산이자 산출 등 연체 관련 업무 로직을 처리하는 구성요소에서, EJB 인스턴스 생성 시점에 호출되는 생성 콜백을 제공한다. 현재 구현은 본문이 비어 있어 생성 시 별도의 초기화 작업(컨텍스트 접근, 상태값 설정, 외부 자원 준비 등)을 수행하지 않는다. 다만 생성 단계에서 문제가 발생할 수 있음을 고려해, 생성 과정의 예외를 호출자에게 전파할 수 있도록 예외 발생 가능성을 선언해 둔다. |
| ejbRemove | public void ejbRemove() | - | - | 이 구성요소는 연체 등록, 등급 갱신, 연체 해소, 가산이자 산출 등 연체 관련 업무 로직을 처리하는 무상태 세션 빈의 구현체이다. 이 범위의 코드는 빈 인스턴스 제거 시점에 호출되는 생명주기 훅으로, 제거 단계에서 수행할 정리 작업을 넣기 위한 자리를 제공한다. 현재 구현은 본문이 비어 있어 세션 컨텍스트 해제, 자원 반납, 상태 기록 등 어떤 후처리도 수행하지 않는다. 따라서 호출되더라도 시스템 상태나 데이터에 영향을 주지 않는 무동작 처리로 동작한다. |
| ejbActivate | public void ejbActivate() | - | - | 이 구성요소는 연체 등록, 등급 갱신, 연체 해소, 가산이자 산출 등 연체 관련 업무 로직을 처리하는 세션 빈 구현체의 일부이며, 활성화 시점에 호출되는 생명주기 훅을 제공한다. 다만 해당 훅의 본문이 비어 있어, 활성화 시 추가 초기화나 상태 복구를 수행하지 않는다. 그 결과 외부 자원 접근, 데이터 조회/저장, 내부 상태 변경 같은 부수효과가 발생하지 않으며, 호출되더라도 동작은 즉시 종료된다. |
| ejbPassivate | public void ejbPassivate() | - | - | 이 구성요소는 연체 등록, 등급 갱신, 연체 해소, 가산이자 산출 등 연체 관련 업무 로직을 처리하는 무상태 세션 빈 구현체의 일부이다. 이 범위는 컨테이너가 인스턴스를 패시베이션(비활성화/저장) 단계로 전환할 때 호출되는 생명주기 콜백을 제공하지만, 실제 처리 로직은 비어 있어 아무 동작도 수행하지 않는다. 따라서 패시베이션 시점에 자원 정리, 상태 저장, 컨텍스트 갱신 같은 부수 처리를 의도적으로 하지 않도록 설계된 상태이다. |

#### 필드

| 이름 | 타입 | 수정자 | 요약 |
| --- | --- | --- | --- |
| serialVersionUID | long | - | 이 필드는 직렬화 가능한 객체에서 클래스 버전 호환성을 관리하기 위한 직렬화 버전 식별자이며, 고정값 1L로 설정되어 역직렬화 시 클래스 변경 여부를 판단하는 기준으로 사용된다. |
| ctx | SessionContext | - | 연체 관리 Stateless 세션 빈에서 컨테이너가 제공하는 세션 컨텍스트를 보관하여 트랜잭션/보안 정보 접근, 호출자 정보 확인, 리소스 조회 등 EJB 실행 환경과 연동하는 데 사용된다. |

#### 구조 관계

| 방향 | 관계 | 대상 | 속성 |
| --- | --- | --- | --- |
| → | DEPENDENCY | DelinquencyDTO | source_member=getDelinquency, usage=return |
| → | DEPENDENCY | DelinquencyDTO | source_member=entityToDTO, usage=local_new |
| → | DEPENDENCY | DelinquencyLocal | source_member=getDelinquency, usage=local_var |
| → | DEPENDENCY | DelinquencyLocal | source_member=calculateTotalPenalty, usage=local_var |
| → | DEPENDENCY | DelinquencyLocal | source_member=entityToDTO, usage=parameter |
| → | DEPENDENCY | DelinquencyLocal | source_member=entitiesToDTOs, usage=cast |
| → | DEPENDENCY | DelinquencyLocalHome | source_member=getDelinquencyHome, usage=return |
| → | DEPENDENCY | DelinquencyLocalHome | source_member=getDelinquency, usage=local_var |
| → | DEPENDENCY | DelinquencyLocalHome | source_member=getDelinquenciesByCustomer, usage=local_var |
| → | DEPENDENCY | DelinquencyLocalHome | source_member=registerDelinquency, usage=local_var |
| → | DEPENDENCY | LoanLedgerLocal | source_member=resolveDelinquency, usage=local_var |
| → | DEPENDENCY | LoanLedgerLocal | source_member=registerDelinquency, usage=local_var |
| → | DEPENDENCY | LoanLedgerLocalHome | source_member=getLoanLedgerHome, usage=return |
| → | DEPENDENCY | LoanLedgerLocalHome | source_member=resolveDelinquency, usage=local_var |
| → | DEPENDENCY | LoanLedgerLocalHome | source_member=registerDelinquency, usage=local_var |
| → | DEPENDENCY | DelinquencyException | source_member=getDelinquenciesByCustomer, usage=local_new |
| → | DEPENDENCY | DelinquencyException | source_member=registerDelinquency, usage=return |
| → | DEPENDENCY | LoanConstants | source_member=getLoanLedgerHome, usage=local_var |
| → | DEPENDENCY | LoanConstants | source_member=getDelinquencyHome, usage=local_var |
| → | DEPENDENCY | LoanConstants | source_member=calculateTotalPenalty, usage=local_var |
| → | DEPENDENCY | LoanConstants | source_member=registerDelinquency, usage=local_var |
| → | DEPENDENCY | ServiceLocator | source_member=getLoanLedgerHome, usage=local_var |
| → | DEPENDENCY | ServiceLocator | source_member=getDelinquencyHome, usage=local_var |
| → | DEPENDENCY | SessionContext | source_member=setSessionContext, usage=parameter |

#### 호출 관계

| 방향 | 대상 | 호출코드 |
| --- | --- | --- |
| → | DelinquencyDTO | - |
| → | DelinquencyLocal | - |
| → | DelinquencyLocalHome | - |
| → | LoanLedgerLocal | - |
| → | LoanLedgerLocalHome | - |
| → | SessionContext | - |
| → | DelinquencyLocalHome | 49:             DelinquencyLocal entity = delinquencyHome.create( 50:                     delinquencyId, ledgerId, customerId, 51:                     startDate, outstandingBalance, penaltyRate); |
| → | LoanLedgerLocal | 42:             String customerId = ledger.getCustomerId(); |
| → | LoanLedgerLocal | 41:             BigDecimal outstandingBalance = ledger.getOutstandingBalance(); |
| → | LoanLedgerLocal | 53:             ledger.setStatus(LoanConstants.LEDGER_DELINQUENT); |
| → | LoanLedgerLocalHome | 39:             LoanLedgerLocal ledger = ledgerHome.findByPrimaryKey(ledgerId); |
| → | DelinquencyMgmtSessionBean | 38:             LoanLedgerLocalHome ledgerHome = getLoanLedgerHome(); |
| → | DelinquencyMgmtSessionBean | 48:             DelinquencyLocalHome delinquencyHome = getDelinquencyHome(); |
| → | DelinquencyMgmtSessionBean | 45:             String delinquencyId = generateId(); |
| → | SessionContext | 57:             ctx.setRollbackOnly(); |
| → | DelinquencyLocalHome | 71:             DelinquencyLocal entity = home.findByPrimaryKey(delinquencyId); |
| → | DelinquencyMgmtSessionBean | 70:             DelinquencyLocalHome home = getDelinquencyHome(); |
| → | DelinquencyLocalHome | 83:             Collection entities = home.findByCustomerId(customerId); |
| → | DelinquencyMgmtSessionBean | 82:             DelinquencyLocalHome home = getDelinquencyHome(); |
| → | DelinquencyLocalHome | 95:             Collection entities = home.findByStatus(LoanConstants.DELINQUENCY_ACTIVE); |
| → | DelinquencyMgmtSessionBean | 94:             DelinquencyLocalHome home = getDelinquencyHome(); |
| → | DelinquencyLocal | 110:             entity.updateDelinquencyDays(currentDays); |
| → | DelinquencyLocalHome | 108:             DelinquencyLocal entity = home.findByPrimaryKey(delinquencyId); |
| → | DelinquencyMgmtSessionBean | 107:             DelinquencyLocalHome home = getDelinquencyHome(); |
| → | DelinquencyLocal | 128:             String ledgerId = entity.getLedgerId(); |
| → | DelinquencyLocal | 126:             entity.resolve(resolutionDate); |
| → | DelinquencyLocalHome | 123:             DelinquencyLocal entity = delinquencyHome.findByPrimaryKey(delinquencyId); |
| → | DelinquencyLocalHome | 130:             Collection ledgerDelinquencies = delinquencyHome.findByLedgerId(ledgerId); |
| → | LoanLedgerLocal | 144:                 ledger.setStatus(LoanConstants.LEDGER_ACTIVE); |
| → | LoanLedgerLocalHome | 143:                 LoanLedgerLocal ledger = ledgerHome.findByPrimaryKey(ledgerId); |
| → | DelinquencyMgmtSessionBean | 142:                 LoanLedgerLocalHome ledgerHome = getLoanLedgerHome(); |
| → | DelinquencyMgmtSessionBean | 122:             DelinquencyLocalHome delinquencyHome = getDelinquencyHome(); |
| → | DelinquencyLocal | 166:                     BigDecimal penalty = d.getPenaltyAmount(); |
| → | DelinquencyLocalHome | 158:             Collection delinquencies = home.findByLedgerId(ledgerId); |
| → | DelinquencyMgmtSessionBean | 157:             DelinquencyLocalHome home = getDelinquencyHome(); |
| → | DelinquencyDTO | 195:         dto.setDelinquencyId(entity.getDelinquencyId()); |
| → | DelinquencyDTO | 196:         dto.setLedgerId(entity.getLedgerId()); |
| → | DelinquencyDTO | 197:         dto.setCustomerId(entity.getCustomerId()); |
| → | DelinquencyDTO | 198:         dto.setDelinquencyStartDate(entity.getDelinquencyStartDate()); |
| → | DelinquencyDTO | 199:         dto.setDelinquencyAmount(entity.getDelinquencyAmount()); |
| → | DelinquencyDTO | 200:         dto.setDelinquencyDays(entity.getDelinquencyDays()); |
| → | DelinquencyDTO | 201:         dto.setDelinquencyGrade(entity.getDelinquencyGrade()); |
| → | DelinquencyDTO | 202:         dto.setPenaltyRate(entity.getPenaltyRate()); |
| → | DelinquencyDTO | 203:         dto.setPenaltyAmount(entity.getPenaltyAmount()); |
| → | DelinquencyDTO | 204:         dto.setStatus(entity.getStatus()); |
| → | DelinquencyDTO | 205:         dto.setResolutionDate(entity.getResolutionDate()); |
| → | DelinquencyMgmtSessionBean | 214:             dtos.add(entityToDTO(entity)); |

#### 데이터 접근

| 대상 | 관계 | 근거 | 신뢰도 |
| --- | --- | --- | --- |
| DELINQUENCY | WRITES | - | - |
| LOAN_LEDGER | WRITES | - | - |
| DELINQUENCY | READS | - | - |
| LOAN_LEDGER | READS | - | - |
| DelinquencyDTO | REFER_TO | - | 1.0 |
| DelinquencyLocal | REFER_TO | - | 1.0 |
| DelinquencyLocalHome | REFER_TO | - | 1.0 |
| LoanLedgerLocal | REFER_TO | - | 1.0 |
| LoanLedgerLocalHome | REFER_TO | - | 1.0 |
| DelinquencyException | REFER_TO | - | 1.0 |
| LoanConstants | REFER_TO | - | 1.0 |
| ejb-jar.xml | REFER_TO | - | 0.9 |
| ejb-jar.xml | REFER_TO | - | 0.9 |
| DELINQUENCY | READS | - | - |
| DelinquencyDTO | REFER_TO | - | 1.0 |
| DelinquencyLocal | REFER_TO | - | 1.0 |
| DelinquencyLocalHome | REFER_TO | - | 1.0 |
| DelinquencyException | REFER_TO | - | 1.0 |
| ejb-jar.xml | REFER_TO | - | 0.9 |
| DELINQUENCY | READS | - | - |
| DelinquencyLocal | REFER_TO | - | 1.0 |
| DelinquencyLocalHome | REFER_TO | - | 1.0 |
| DelinquencyException | REFER_TO | - | 1.0 |
| ejb-jar.xml | REFER_TO | - | 0.9 |
| DELINQUENCY | READS | - | - |
| DelinquencyLocal | REFER_TO | - | 1.0 |
| DelinquencyLocalHome | REFER_TO | - | 1.0 |
| DelinquencyException | REFER_TO | - | 1.0 |
| LoanConstants | REFER_TO | - | 1.0 |
| ejb-jar.xml | REFER_TO | - | 0.9 |
| DELINQUENCY | WRITES | - | - |
| DELINQUENCY | READS | - | - |
| DelinquencyLocal | REFER_TO | - | 1.0 |
| DelinquencyLocalHome | REFER_TO | - | 1.0 |
| DelinquencyException | REFER_TO | - | 1.0 |
| ejb-jar.xml | REFER_TO | - | 0.9 |
| DELINQUENCY | WRITES | - | - |
| LOAN_LEDGER | WRITES | - | - |
| DELINQUENCY | READS | - | - |
| LOAN_LEDGER | READS | - | - |
| DelinquencyLocal | REFER_TO | - | 1.0 |
| DelinquencyLocalHome | REFER_TO | - | 1.0 |
| LoanLedgerLocal | REFER_TO | - | 1.0 |
| LoanLedgerLocalHome | REFER_TO | - | 1.0 |
| DelinquencyException | REFER_TO | - | 1.0 |
| LoanConstants | REFER_TO | - | 1.0 |
| ejb-jar.xml | REFER_TO | - | 0.9 |
| ejb-jar.xml | REFER_TO | - | 0.9 |
| DelinquencyLocal | REFER_TO | - | 1.0 |
| DelinquencyLocalHome | REFER_TO | - | 1.0 |
| DelinquencyException | REFER_TO | - | 1.0 |
| LoanConstants | REFER_TO | - | 1.0 |
| LoanLedgerLocal | REFER_TO | - | 1.0 |
| LoanLedgerLocalHome | REFER_TO | - | 1.0 |
| LoanConstants | REFER_TO | - | 1.0 |
| ServiceLocator | REFER_TO | - | 1.0 |
| DelinquencyLocal | REFER_TO | - | 1.0 |
| DelinquencyLocalHome | REFER_TO | - | 1.0 |
| LoanConstants | REFER_TO | - | 1.0 |
| ServiceLocator | REFER_TO | - | 1.0 |
| DelinquencyDTO | REFER_TO | - | 1.0 |
| DelinquencyLocal | REFER_TO | - | 1.0 |
| DelinquencyLocal | REFER_TO | - | 1.0 |

#### 요약 코드

```
없음
```

### DelinquencyMgmtSessionHome

#### 기본 정보

| 항목 | 값 |
| --- | --- |
| 이름 | DelinquencyMgmtSessionHome |
| 타입 | CLASS |
| FQN | com.banking.loan.session.DelinquencyMgmtSessionHome |
| 패키지 | com.banking.loan.session |
| 스테레오타입 | READMODEL |
| 파일 | - |
| 라인 | - |
| 토큰 | - |

#### 요약

> 이 클래스는 연체 관리 기능을 제공하는 세션 빈의 리모트 홈 인터페이스로서, 클라이언트가 원격 연체 업무에 접근할 수 있는 진입점을 정의한다. 주요 책임은 원격 세션 객체를 생성(또는 할당)해 반환하는 것이며, 생성 실패 시 생성 예외를, 네트워크/원격 호출 문제 시 원격 예외를 호출자에게 전달하도록 계약을 명시한다. 이렇게 획득한 원격 세션은 연체 등록, 조회, 상태변경, 해소, 가산이자 산출 등 연체 관련 업무 처리를 수행하는 데 사용된다.

#### 메서드

| 이름 | 시그니처 | 반환타입 | 수정자 | 요약 |
| --- | --- | --- | --- | --- |
| create | DelinquencyMgmtSession create() throws CreateException, RemoteException | - | - | 연체 관리 기능을 제공하는 세션 빈의 리모트 홈 인터페이스에서, 클라이언트가 원격 업무 기능에 접근할 수 있도록 원격 세션 객체를 생성(또는 할당)받아 반환하는 계약을 정의한다. 생성 과정에서 빈 생성에 실패하면 생성 예외로, 네트워크/원격 호출 문제로 실패하면 원격 예외로 호출자에게 오류를 전달하도록 명시한다. 이렇게 획득한 원격 세션은 연체 등록, 조회, 상태변경, 해소, 가산이자 산출 등 연체 관련 업무 처리를 수행하는 진입점으로 사용된다. |

#### 필드

| 이름 | 타입 | 수정자 | 요약 |
| --- | --- | --- | --- |
| - | - | - | - |

#### 구조 관계

| 방향 | 관계 | 대상 | 속성 |
| --- | --- | --- | --- |
| → | DEPENDENCY | DelinquencyMgmtSession | source_member=create, usage=return |
| ← | ASSOCIATION | LoanServlet | source_member=init |

#### 호출 관계

| 방향 | 대상 | 호출코드 |
| --- | --- | --- |
| ← | LoanServlet | - |

#### 데이터 접근

| 대상 | 관계 | 근거 | 신뢰도 |
| --- | --- | --- | --- |
| DelinquencyMgmtSession | REFER_TO | - | 1.0 |
| ejb-jar.xml | REFER_TO | - | 1.0 |

#### 요약 코드

```
없음
```

### LoanApplicationSession

#### 기본 정보

| 항목 | 값 |
| --- | --- |
| 이름 | LoanApplicationSession |
| 타입 | CLASS |
| FQN | com.banking.loan.session.LoanApplicationSession |
| 패키지 | com.banking.loan.session |
| 스테레오타입 | COMMAND/READMODEL |
| 파일 | - |
| 라인 | - |
| 토큰 | - |

#### 요약

> com.banking.loan.session.LoanApplicationSession은 여신 신청을 원격으로 관리하는 세션 빈 리모트 컴포넌트 인터페이스로, 여신 신청의 생성, 조회, 정보 수정 및 상태변경 업무에 대한 계약을 정의한다. 신청 ID/고객 식별자(customer) 기반 조회와 전체 목록 조회, 그리고 상태 문자열을 조건으로 해당 상태의 신청 목록 조회를 지원하며, 처리 단계 진행을 위해 신청을 ‘신청 제출’ 처리하거나 상태를 ‘취소’로 전환하는 등 상태 전이를 외부에서 호출 가능하게 한다. 또한 여신 신청에 연계될 담보 정보를 전달 객체로 받아 담보를 등록하는 기능을 제공하며, 원격 통신 오류는 원격 예외로, 업무 규칙 위반·처리 실패는 여신 신청 도메인 예외로 호출자에게 전달되도록 한다.

#### 메서드

| 이름 | 시그니처 | 반환타입 | 수정자 | 요약 |
| --- | --- | --- | --- | --- |
| createApplication | LoanApplicationDTO createApplication(LoanApplicationDTO dto)             throws RemoteException, LoanApplicationException | - | - | 여신 신청의 생성·조회·상태변경을 처리하는 원격 컴포넌트 인터페이스의 기능 중, 여신 신청 생성 요청을 받아 신규 신청을 등록하는 계약을 정의한다. 입력으로 여신 신청에 필요한 정보 묶음을 전달받아, 처리 결과로 생성(등록)된 여신 신청 정보를 다시 반환하도록 되어 있다. 원격 호출 환경에서 발생할 수 있는 통신 오류는 원격 예외로, 업무 처리 과정의 규칙 위반·검증 실패 등은 도메인 예외로 호출자에게 전달하도록 선언되어 있다. |
| getApplication | LoanApplicationDTO getApplication(String applicationId)             throws RemoteException, LoanApplicationException | - | - | 여신 신청 관리 목적의 리모트 컴포넌트에서, 여신 신청을 식별하는 값(신청 ID)을 입력받아 해당 신청의 상세 정보를 반환하기 위한 조회 계약을 정의한다. 조회 결과는 여신 신청의 데이터 묶음을 담는 반환 객체 형태로 제공되어, 호출자는 여신 신청의 현재 상태와 관련 속성을 읽을 수 있다. 원격 호출 환경을 전제로 하므로 통신/호출 과정에서 발생하는 원격 예외가 전파될 수 있으며, 여신 신청 조회 처리 중 업무 규칙 위반이나 도메인 오류 상황은 별도의 업무 예외로 전달되도록 명세되어 있다. |
| getAllApplications | Collection getAllApplications()             throws RemoteException, LoanApplicationException | - | - | 여신 신청의 생성·조회·상태변경 등을 다루는 원격 컴포넌트 인터페이스에서, 현재 존재하는 여신 신청 전체 목록을 한 번에 조회해 컬렉션 형태로 반환한다. 호출자는 반환된 컬렉션을 통해 여러 건의 여신 신청을 일괄 열람하는 용도로 사용한다. 원격 호출 특성상 통신/원격 처리 실패는 원격 예외로 전달되며, 여신 신청 도메인 처리 중 발생한 업무 오류는 여신 신청 관련 예외로 호출자에게 전파된다. |
| getApplicationsByCustomer | Collection getApplicationsByCustomer(String customerId)             throws RemoteException, LoanApplicationException | - | - | 여신 신청의 생성·조회·상태변경을 다루는 리모트 컴포넌트 인터페이스의 기능 중, 특정 고객 식별자를 기준으로 해당 고객의 여신 신청 목록을 조회해 컬렉션으로 돌려주는 계약을 정의한다. 조회 대상 고객은 문자열 형태의 고객 식별자로 전달되며, 결과는 고객에게 매핑된 여러 건의 신청 정보를 묶어 반환하는 형태를 전제한다. 원격 호출 환경에서 통신 문제로 인한 예외가 발생할 수 있고, 조회 과정에서 업무 규칙 위반이나 조회 실패가 발생하면 도메인 예외를 통해 오류를 호출자에게 전달한다. |
| getApplicationsByStatus | Collection getApplicationsByStatus(String status)             throws RemoteException, LoanApplicationException | - | - | 여신 신청의 생성·조회·상태변경을 다루는 리모트 컴포넌트 인터페이스에서, 특정 상태값을 입력받아 해당 상태에 속한 여신 신청들을 조회해 컬렉션 형태로 반환하는 계약을 정의한다. 호출자는 조회 조건으로 상태 문자열을 제공하며, 구현체는 그 상태에 매칭되는 신청 목록을 수집해 반환해야 한다. 원격 호출 환경에서 발생할 수 있는 통신 오류는 원격 예외로, 도메인 규칙 위반이나 조회 불가 상황 등 업무 오류는 여신 신청 예외로 호출자에게 전달하도록 선언한다. |
| submitApplication | void submitApplication(String applicationId)             throws RemoteException, LoanApplicationException | - | - | 여신 신청의 생성, 조회, 상태변경 등을 다루는 리모트 컴포넌트 인터페이스에서, 특정 여신 신청을 식별하는 ID를 입력받아 ‘신청 제출’ 처리를 수행하도록 정의된 작업이다. 이 작업은 신청 건의 처리 단계가 진행되는 성격을 가지며, 제출 과정에서 업무 규칙 위반이나 처리 실패가 발생하면 도메인 예외를 통해 오류를 호출자에게 전달한다. 또한 원격 호출 환경에서 통신/인프라 문제로 원격 예외가 발생할 수 있음을 계약으로 명시한다. |
| cancelApplication | void cancelApplication(String applicationId)             throws RemoteException, LoanApplicationException | - | - | 이 컴포넌트는 여신 신청의 생성, 조회, 상태변경을 다루는 리모트 인터페이스이며, 그중 특정 여신 신청을 취소하는 작업을 계약으로 정의한다. 입력으로 여신 신청 식별자를 받아 해당 신청 건의 처리 상태를 ‘취소’로 전환하는 등 업무상 상태 변경을 수행하는 것이 목적이다. 원격 호출 환경에서 발생할 수 있는 통신/호출 오류는 원격 예외로, 도메인 규칙 위반이나 처리 실패는 여신 신청 관련 업무 예외로 호출자에게 전달되도록 선언되어 있다. |
| updateApplication | void updateApplication(LoanApplicationDTO dto)             throws RemoteException, LoanApplicationException | - | - | 이 컴포넌트는 여신 신청의 생성, 조회, 상태변경 등 관리 업무를 원격으로 제공하며, 이 구간은 그중 기존 여신 신청 정보를 변경하는 요청을 정의한다. 호출자는 여신 신청의 변경에 필요한 값들을 담은 전달 객체를 넘겨 변경 처리를 요청하고, 정상 처리 시 별도의 반환값은 없다. 처리 과정에서 원격 호출 환경에서의 통신/호출 실패는 원격 예외로 보고되며, 여신 신청 도메인 규칙 위반이나 처리 불가 상황은 업무 예외로 보고되어 호출자가 오류를 구분해 대응할 수 있게 한다. |
| registerCollateral | void registerCollateral(CollateralDTO dto)             throws RemoteException, LoanApplicationException | - | - | 여신 신청 관리 리모트 컴포넌트 인터페이스에서, 여신 신청에 연계될 담보 정보를 전달받아 담보를 등록하는 동작을 정의한다. 호출자는 담보 등록에 필요한 정보를 담은 전달 객체를 제공하며, 이 동작은 반환값 없이 등록 처리의 성공/실패로 결과가 구분된다. 원격 호출 특성상 통신 오류가 발생할 수 있고, 담보 등록이 여신 신청 처리 규칙에 위배되거나 업무 처리 중 문제가 생기면 업무 예외로 실패를 알린다. 결과적으로 여신 신청의 상태 변경/업무 처리 흐름에서 담보 등록 단계가 외부에서 호출 가능하도록 계약을 제공한다. |

#### 필드

| 이름 | 타입 | 수정자 | 요약 |
| --- | --- | --- | --- |
| - | - | - | - |

#### 구조 관계

| 방향 | 관계 | 대상 | 속성 |
| --- | --- | --- | --- |
| → | DEPENDENCY | CollateralDTO | source_member=registerCollateral, usage=parameter |
| → | DEPENDENCY | LoanApplicationDTO | source_member=createApplication, usage=parameter |
| → | DEPENDENCY | LoanApplicationDTO | source_member=updateApplication, usage=parameter |
| → | DEPENDENCY | LoanApplicationDTO | source_member=getApplication, usage=return |
| → | DEPENDENCY | LoanApplicationException | source_member=getAllApplications, usage=parameter |
| → | DEPENDENCY | LoanApplicationException | source_member=cancelApplication, usage=local_var |
| → | DEPENDENCY | LoanApplicationException | source_member=submitApplication, usage=local_var |
| → | DEPENDENCY | LoanApplicationException | source_member=getApplication, usage=parameter |
| → | DEPENDENCY | LoanApplicationException | source_member=getApplicationsByCustomer, usage=return |
| → | DEPENDENCY | LoanApplicationException | source_member=getApplicationsByStatus, usage=parameter |
| ← | DEPENDENCY | LoanServlet | source_member=handleSubmitApplication, usage=local_var |
| ← | DEPENDENCY | LoanServlet | source_member=handleCreateApplication, usage=local_var |
| ← | DEPENDENCY | LoanServlet | source_member=handleGetApplication, usage=local_var |
| ← | DEPENDENCY | LoanApplicationSessionHome | source_member=create, usage=return |
| ← | DEPENDENCY | LoanProcessSessionBean | source_member=cancelProcess, usage=local_var |
| ← | DEPENDENCY | LoanProcessSessionBean | source_member=submitAndGetResult, usage=local_var |

#### 호출 관계

| 방향 | 대상 | 호출코드 |
| --- | --- | --- |
| ← | LoanServlet | - |
| ← | LoanProcessSessionBean | - |

#### 데이터 접근

| 대상 | 관계 | 근거 | 신뢰도 |
| --- | --- | --- | --- |
| LoanApplicationDTO | REFER_TO | - | 1.0 |
| LoanApplicationException | REFER_TO | - | 1.0 |
| LoanApplicationDTO | REFER_TO | - | 1.0 |
| LoanApplicationException | REFER_TO | - | 1.0 |
| LoanApplicationException | REFER_TO | - | 1.0 |
| LoanApplicationException | REFER_TO | - | 1.0 |
| LoanApplicationException | REFER_TO | - | 1.0 |
| LoanApplicationException | REFER_TO | - | 1.0 |
| LoanApplicationException | REFER_TO | - | 1.0 |
| LoanApplicationDTO | REFER_TO | - | 1.0 |
| LoanApplicationException | REFER_TO | - | 1.0 |
| CollateralDTO | REFER_TO | - | 1.0 |
| LoanApplicationException | REFER_TO | - | 1.0 |

#### 요약 코드

```
없음
```

### LoanApplicationSessionBean

#### 기본 정보

| 항목 | 값 |
| --- | --- |
| 이름 | LoanApplicationSessionBean |
| 타입 | CLASS |
| FQN | com.banking.loan.session.LoanApplicationSessionBean |
| 패키지 | com.banking.loan.session |
| 스테레오타입 | COMMAND/READMODEL |
| 파일 | - |
| 라인 | - |
| 토큰 | - |

#### 요약

> 이 클래스는 여신 신청 관리 Stateless 세션 빈 구현체로서, 여신 신청의 생성·조회(단건/전체, customerId/status 조건)·변경·상태변경·담보등록 업무 로직을 처리한다. 신규 생성 시 applicationId를 UUID 기반(하이픈 제거 후 20자리 절단, 대문자)으로 만들고 applicationDate를 현재 시각으로 설정한 뒤 status를 STATUS_DRAFT로 초기화하며, 접수는 DRAFT 상태에서만 허용해 STATUS_DRAFT → STATUS_SUBMITTED로 전이시키고 DRAFT가 아니면 "DRAFT 상태만 접수 가능"으로 차단한다. 취소는 status가 STATUS_EXECUTED이면 "취소 불가: 이미 실행된 여신입니다."로 막고 그 외에는 STATUS_CANCELLED로 변경하며, 신청 변경은 applicationId로 기존 데이터를 찾은 뒤 customerId/requestedAmount/loanType/loanPurpose/interestRate/remarks는 null이 아닐 때만, term은 0 초과(> 0)일 때만 선택적으로 갱신한다. 또한 담보 등록 시에도 동일한 20자리 대문자 ID 규칙을 적용하고, EJB 생명주기 콜백(생성/제거/활성화/패시베이션)은 구현이 비어 있어 별도 초기화·정리 없이 컨테이너 기본 동작에 의존하되, 세션 컨텍스트(ctx)로 보안/트랜잭션 등 컨테이너 기능 제어가 가능한 구조를 갖는다.

#### 메서드

| 이름 | 시그니처 | 반환타입 | 수정자 | 요약 |
| --- | --- | --- | --- | --- |
| createApplication | public LoanApplicationDTO createApplication(LoanApplicationDTO dto) throws LoanApplicationException | - | - | 여신 신청 관리 기능의 일부로, 입력으로 받은 여신 신청 정보를 바탕으로 신규 신청을 시스템에 등록하고 등록 결과를 반환용 형태로 변환해 돌려준다. 등록을 위해 고유한 applicationId를 생성하고, applicationDate를 현재 시각으로 설정하며, 신청 상태를 STATUS_DRAFT로 초기화하기 위한 값을 준비하지만 실제 생성 요청 인자에는 상태값이 전달되지 않는다. 생성 요청에는 customerId, requestedAmount, loanType, loanPurpose, term, interestRate가 포함되어 신규 신청 레코드(또는 엔티티)가 만들어지도록 위임한다. 생성 과정에서 생성 실패 또는 이름 해석(JNDI) 실패가 발생하면 트랜잭션을 롤백 전용으로 표시한 뒤, 원인 예외 메시지를 포함해 도메인 예외로 감싸 호출자에게 전달한다. |
| getApplication | public LoanApplicationDTO getApplication(String applicationId) throws LoanApplicationException | - | - | 여신 신청 관리 기능에서, 입력으로 받은 여신 신청 식별자에 해당하는 신청 정보를 조회해 반환한다. 먼저 JNDI 조회를 통해 여신 신청 정보의 생성/조회 기능을 제공하는 로컬 홈 객체를 확보한 뒤, 기본키(신청 식별자)로 여신 신청 데이터를 찾아온다. 조회된 신청 데이터는 외부 전달을 위한 전송 객체 형태로 변환하여 호출자에게 돌려준다. 조회 대상이 없거나 조회 과정에서 문제가 발생하면 조회 실패로 간주해 식별자를 포함한 메시지로 업무 예외로 감싸서 던지며, JNDI 이름 해석 문제가 생기면 JNDI 조회 실패 메시지로 동일하게 업무 예외로 변환해 전달한다. |
| getAllApplications | public Collection getAllApplications() throws LoanApplicationException | - | - | 여신 신청의 생성·조회·상태변경 등을 처리하는 구성요소 안에서, 저장된 여신 신청을 전체 목록으로 조회해 반환하는 역할을 수행한다. 먼저 JNDI 조회를 통해 여신 신청 정보에 대한 생성/조회 기능을 제공하는 로컬 홈 접근자를 확보한 뒤, 전체 목록 조회를 요청해 결과 컬렉션을 가져온다. 조회 결과로 얻은 엔티티 컬렉션은 외부로 전달 가능한 DTO 컬렉션 형태로 변환해 반환한다. 전체 목록 탐색 과정에서 조회 실패가 발생하면 ‘여신 신청 전체 조회 실패’로 포장해 도메인 예외로 변환하고, JNDI 이름 해석 실패는 ‘JNDI 조회 실패: <원인 메시지>’로 메시지를 구성해 동일하게 도메인 예외로 변환한다. |
| getApplicationsByCustomer | public Collection getApplicationsByCustomer(String customerId) throws LoanApplicationException | - | - | 이 클래스는 여신 신청의 생성·조회·상태변경 등을 관리하며, 이 구간은 고객ID를 기준으로 여신 신청 목록을 조회하는 역할을 수행한다. 먼저 JNDI 조회를 통해 여신 신청 정보의 생성/조회 기능을 제공하는 로컬 홈 객체를 확보한 뒤, 고객ID로 여러 건의 여신 신청 레코드를 조회한다. 조회 결과로 얻은 엔티티 컬렉션은 화면/호출자 전달을 위한 전송 객체 컬렉션으로 변환하여 반환한다. 조회 과정에서 검색 실패가 발생하면 고객ID를 포함한 메시지로 도메인 예외로 감싸 전달하고, JNDI 이름 해석 실패도 동일하게 도메인 예외로 변환해 전파한다. |
| getApplicationsByStatus | public Collection getApplicationsByStatus(String status) throws LoanApplicationException | - | - | 여신 신청 관리 기능에서 입력으로 받은 상태값(status)에 해당하는 여신 신청들을 조회해 목록 형태로 반환한다. 이를 위해 여신 신청 엔티티에 접근할 수 있는 로컬 홈을 JNDI 기반으로 획득한 뒤, 상태 조건 조회 연산을 통해 대상들을 찾는다. 조회된 엔티티 컬렉션은 화면/호출자 전달을 위해 DTO 컬렉션으로 변환하여 반환한다. 조회 과정에서 검색 실패가 발생하면 해당 상태값을 포함해 ‘상태별 여신 신청 조회 실패’로 감싼 업무 예외로 변환하고, JNDI 이름 해석 실패도 ‘JNDI 조회 실패’ 메시지로 업무 예외로 변환해 전달한다. |
| submitApplication | public void submitApplication(String applicationId) throws LoanApplicationException | - | - | 여신 신청 관리 기능에서 입력으로 받은 신청 식별자(기본키)로 여신 신청 정보를 조회한 뒤, 현재 status(상태)를 확인하여 접수 가능 여부를 검증하고 상태를 변경한다. 조회된 status가 DRAFT와 같지 않으면 "DRAFT 상태만 접수 가능" 규칙에 따라 현재 상태값을 포함한 오류를 발생시켜 접수를 차단한다. 검증을 통과한 경우 status를 SUBMITTED로 변경하여 접수 상태 전이를 확정한다. 조회(Finder) 실패 또는 JNDI 조회 실패가 발생하면 트랜잭션을 롤백 처리로 표시하고, 실패 원인과 신청 식별자/오류 메시지를 포함해 업무 예외로 변환해 다시 던진다. |
| cancelApplication | public void cancelApplication(String applicationId) throws LoanApplicationException | - | - | 입력으로 받은 여신 신청 식별자에 대해, JNDI로 조회한 생성/조회 컴포넌트를 통해 해당 여신 신청 정보를 기본키로 찾아온다. 조회된 신청의 status(상태)를 확인하여, 현재 상태가 STATUS_EXECUTED인 경우에는 "취소 불가: 이미 실행된 여신입니다."라는 업무 규칙 위반 예외로 취소를 차단한다. 위 조건에 해당하지 않으면 status를 STATUS_CANCELLED로 변경하여 여신 신청의 취소 상태를 확정한다. 조회(FinderException) 또는 JNDI 조회(NamingException) 실패 시에는 트랜잭션을 롤백 전용으로 표시한 뒤, 식별자/원인 메시지를 포함해 도메인 예외로 감싸 다시 발생시킨다. |
| updateApplication | public void updateApplication(LoanApplicationDTO dto) throws LoanApplicationException | - | - | 여신 신청 관리 기능의 일부로, 입력으로 받은 여신 신청 정보에서 applicationId(신청식별자)에 해당하는 기존 신청 데이터를 찾아 선택적으로 갱신한다. customerId, requestedAmount, loanType, loanPurpose, interestRate, remarks는 값이 null이 아닐 때만 각각의 필드를 변경하고, term은 0 초과(> 0)일 때만 기간(term) 값을 변경해 불필요한 덮어쓰기를 방지한다. 신청 데이터 조회 과정에서 FinderException이 발생하면 트랜잭션을 롤백 전용으로 표시한 뒤 "여신 신청 조회 실패: {applicationId}" 메시지로 업무 예외로 변환해 던진다. JNDI 조회 과정에서 NamingException이 발생해도 동일하게 롤백 전용 처리 후 "JNDI 조회 실패: {원인메시지}" 형태로 업무 예외로 감싸 전달한다. |
| registerCollateral | public void registerCollateral(CollateralDTO dto) throws LoanApplicationException | - | - | 여신 신청 관리 기능의 일부로, 입력으로 받은 담보 등록 정보에서 applicationId, collateralType, description, appraisedValue를 추출해 신규 담보를 등록한다. 등록을 위해 JNDI_COLLATERAL_ENTITY로 지정된 로컬 홈을 JNDI에서 조회한 뒤, UUID 기반으로 하이픈을 제거하고 20자리로 자른 대문자 식별자를 생성해 담보 식별자로 사용한다. 이후 담보 식별자와 함께 applicationId 및 담보 속성들을 전달해 생성(저장)을 요청한다. 생성 실패(CreateException) 또는 JNDI 조회 실패(NamingException)가 발생하면 트랜잭션을 롤백 전용으로 표시하고, 실패 사유를 포함한 업무 예외로 감싸서 재전파한다. |
| getLoanApplicationHome | private LoanApplicationLocalHome getLoanApplicationHome() throws NamingException | - | - | 여신 신청 관리 기능에서 여신 신청 정보를 생성/조회하기 위해 필요한 로컬 홈 객체를 JNDI로 찾아 반환한다. JNDI 조회는 서비스 로케이터 패턴을 통해 수행되며, 미리 정의된 JNDI 식별자(LoanConstants.JNDI_LOAN_APPLICATION_ENTITY)를 키로 사용해 조회 결과를 가져온다. 조회된 로컬 홈은 여신 신청 엔티티에 대한 생성 및 조회 기능을 제공하는 컴포넌트로 사용될 것을 전제로 한다. JNDI 조회 과정에서 이름 해석 실패가 발생할 수 있어 NamingException을 호출자에게 그대로 전달한다. |
| entityToDTO | private LoanApplicationDTO entityToDTO(LoanApplicationLocal entity) | - | - | 여신 신청 관리 기능에서, 저장된 여신 신청 정보를 외부 전달/표시 목적의 데이터 묶음으로 변환하기 위해 입력으로 받은 여신 신청 컴포넌트의 값을 그대로 복사해 새 객체를 구성한다. applicationId, customerId, applicationDate, requestedAmount, loanType, loanPurpose, term, interestRate 같은 기본 신청 정보와 status, screeningResult, screeningDate, approvedAmount, approverEmployeeId, remarks 등 진행/심사·승인 관련 속성을 빠짐없이 1:1로 옮긴다. 값 변환, 유효성 검증, 상태 변경 같은 추가 규칙 없이 각 속성을 단순 대입으로 채우며, 최종적으로 구성된 데이터 묶음을 반환한다. |
| entitiesToDTOs | private Collection entitiesToDTOs(Collection entities) | - | - | 여신 신청 관리 기능의 일부로, 입력으로 받은 여신 신청 목록을 화면/전달용 데이터 목록으로 변환해 반환한다. 전달받은 컬렉션을 끝까지 순회하면서 각 원소를 여신 신청 정보로 간주해 변환 로직에 전달하고, 변환 결과를 새 목록에 누적한다. 이렇게 만들어진 변환 결과 목록을 호출자에게 돌려주어, 조회된 여신 신청들을 일괄로 동일한 형식으로 제공할 수 있게 한다. 이 과정에서 저장/수정 같은 상태 변경은 수행하지 않고, 데이터 표현 형태만 바꾼다. |
| generateId | private String generateId() | - | - | 여신 신청의 생성·조회·상태변경·담보등록 등 여러 업무 로직을 수행하는 구성요소 안에서, 내부적으로 사용할 고유 식별자 문자열을 만들어 반환한다. 임의로 생성된 UUID 값을 기반으로 하이픈('-')을 제거해 연속된 문자열로 정규화한 뒤, 앞에서 20자리만 잘라 길이를 고정한다. 마지막으로 영문을 대문자로 변환해 식별자 형식을 일관되게 맞춘다. 이 과정은 데이터 저장이나 상태 변경 없이, 이후 등록/연계 시 사용할 키 값을 준비하기 위한 목적의 값 생성이다. |
| setSessionContext | public void setSessionContext(SessionContext ctx) | - | - | 여신 신청 관리용 Stateless 세션 빈에서 컨테이너가 제공하는 세션 실행 컨텍스트를 전달받아 내부 필드에 보관한다. 이후 다른 업무 로직에서 트랜잭션 제어(예: 롤백 요청)나 보안/호출자 정보 접근 등 컨테이너 기능을 사용할 수 있도록 준비하는 역할을 한다. 데이터 조회나 저장 같은 외부 자원 접근은 수행하지 않고, 전달된 컨텍스트 참조만 내부 상태로 갱신한다. |
| ejbCreate | public void ejbCreate() throws CreateException | - | - | 여신 신청의 생성, 조회, 상태변경, 담보등록 등 업무 로직을 담당하는 컴포넌트에서, 인스턴스 생성 시점에 호출되는 생명주기 초기화 구간을 정의한다. 현재 구현은 비어 있어 생성 시 추가 초기화, 리소스 준비, 상태 설정을 수행하지 않고 컨테이너의 기본 생성 흐름에만 의존한다. 생성 단계에서 문제가 발생할 가능성은 예외 선언으로만 표현되며, 이 범위 내에서는 예외를 발생시키거나 처리하는 로직은 없다. |
| ejbRemove | public void ejbRemove() | - | - | 여신 신청의 생성·조회·상태변경·담보등록 등 업무 로직을 처리하는 Stateless 세션 빈에서, 컨테이너가 빈 인스턴스를 제거할 때 호출되는 생명주기 종료 콜백을 정의한다. 다만 본문이 비어 있어 제거 시점에 정리 작업(리소스 해제, 상태 저장/정리, 컨텍스트 기반 후처리 등)을 수행하지 않는다. 그 결과, 빈 제거 이벤트를 명시적으로 수용하되 실제 동작은 ‘아무 것도 하지 않음’으로 고정되어 있다. |
| ejbActivate | public void ejbActivate() | - | - | 이 구성요소는 여신 신청의 생성, 조회, 상태변경, 담보등록 등의 업무 로직을 처리하는 세션 빈 구현체이며, 이 구간은 인스턴스가 활성화(activate)될 때 호출되는 생명주기 진입 지점에 해당한다. 그러나 본문이 비어 있어 활성화 시점에 수행하는 초기화, 자원 재연결, 상태 복구 같은 처리가 전혀 없다. 따라서 외부 자원 접근이나 내부 상태 변경 없이 단순히 훅(hook)만 제공하는 형태로 동작한다. |
| ejbPassivate | public void ejbPassivate() | - | - | 이 클래스는 여신 신청의 생성·조회·상태변경·담보등록 등 업무 로직을 처리하는 Stateless 세션 빈 구현체이며, 본 범위는 EJB 생명주기에서 패시베이션 시점에 호출되는 훅을 제공한다. 현재 구현은 본문이 비어 있어 패시베이션 시 리소스 정리, 상태 저장, 컨텍스트 해제 등 어떤 추가 동작도 수행하지 않는다. 따라서 패시베이션과 관련된 처리 책임을 컨테이너 기본 동작에 전적으로 맡기며, 별도의 상태 변경이나 외부 연동은 발생하지 않는다. |

#### 필드

| 이름 | 타입 | 수정자 | 요약 |
| --- | --- | --- | --- |
| serialVersionUID | long | - | 이 값은 직렬화 가능한 세션 빈(여신 신청 관리 로직 구현체)의 클래스 버전 식별자로, 직렬화/역직렬화 시 호환성을 확인하기 위해 1L로 고정된 상수이다. |
| ctx | SessionContext | - | 여신 신청 관리용 Stateless 세션 빈에서 컨테이너가 제공하는 세션 컨텍스트를 보관하는 필드로, 현재 호출의 보안/트랜잭션/호출자 정보 등에 접근하거나 롤백 처리 등 컨테이너 기능을 제어하는 데 사용된다. |

#### 구조 관계

| 방향 | 관계 | 대상 | 속성 |
| --- | --- | --- | --- |
| → | ASSOCIATION | SessionContext | source_member=setSessionContext |
| → | DEPENDENCY | CollateralDTO | source_member=registerCollateral, usage=parameter |
| → | DEPENDENCY | LoanApplicationDTO | source_member=getApplication, usage=return |
| → | DEPENDENCY | LoanApplicationDTO | source_member=updateApplication, usage=parameter |
| → | DEPENDENCY | LoanApplicationDTO | source_member=createApplication, usage=parameter |
| → | DEPENDENCY | CollateralLocalHome | source_member=registerCollateral, usage=cast |
| → | DEPENDENCY | LoanApplicationLocal | source_member=entitiesToDTOs, usage=cast |
| → | DEPENDENCY | LoanApplicationLocal | source_member=getApplication, usage=local_var |
| → | DEPENDENCY | LoanApplicationLocal | source_member=submitApplication, usage=local_var |
| → | DEPENDENCY | LoanApplicationLocal | source_member=updateApplication, usage=local_var |
| → | DEPENDENCY | LoanApplicationLocal | source_member=createApplication, usage=local_var |
| → | DEPENDENCY | LoanApplicationLocalHome | source_member=getLoanApplicationHome, usage=return |
| → | DEPENDENCY | LoanApplicationLocalHome | source_member=getApplicationsByCustomer, usage=local_var |
| → | DEPENDENCY | LoanApplicationLocalHome | source_member=submitApplication, usage=local_var |
| → | DEPENDENCY | LoanApplicationLocalHome | source_member=updateApplication, usage=local_var |
| → | DEPENDENCY | LoanApplicationLocalHome | source_member=getApplicationsByStatus, usage=local_var |
| → | DEPENDENCY | LoanApplicationException | source_member=getApplicationsByCustomer, usage=return |
| → | DEPENDENCY | LoanApplicationException | source_member=submitApplication, usage=local_new |
| → | DEPENDENCY | LoanApplicationException | source_member=registerCollateral, usage=local_new |
| → | DEPENDENCY | LoanApplicationException | source_member=getApplicationsByStatus, usage=local_new |
| → | DEPENDENCY | LoanConstants | source_member=getLoanApplicationHome, usage=local_var |
| → | DEPENDENCY | LoanConstants | source_member=submitApplication, usage=local_var |
| → | DEPENDENCY | LoanConstants | source_member=registerCollateral, usage=local_var |
| → | DEPENDENCY | LoanConstants | source_member=createApplication, usage=field_call |
| → | DEPENDENCY | ServiceLocator | source_member=getLoanApplicationHome, usage=cast |
| → | DEPENDENCY | ServiceLocator | source_member=registerCollateral, usage=local_var |
| → | DEPENDENCY | SessionContext | source_member=setSessionContext, usage=parameter |

#### 호출 관계

| 방향 | 대상 | 호출코드 |
| --- | --- | --- |
| → | LoanApplicationDTO | - |
| → | CollateralLocalHome | - |
| → | LoanApplicationLocal | - |
| → | LoanApplicationLocalHome | - |
| → | ServiceLocator | - |
| → | SessionContext | - |
| → | LoanApplicationLocalHome | 41:             LoanApplicationLocal entity = home.create( 42:                     applicationId, 43:                     dto.getCustomerId(), 44:                     applicationDate, 45:              |
| → | LoanApplicationSessionBean | 36:             LoanApplicationLocalHome home = getLoanApplicationHome(); |
| → | LoanApplicationSessionBean | 37:             String applicationId = generateId(); |
| → | SessionContext | 54:             ctx.setRollbackOnly(); |
| → | LoanApplicationLocalHome | 65:             LoanApplicationLocal entity = home.findByPrimaryKey(applicationId); |
| → | LoanApplicationSessionBean | 64:             LoanApplicationLocalHome home = getLoanApplicationHome(); |
| → | LoanApplicationLocalHome | 77:             Collection entities = home.findAll(); |
| → | LoanApplicationSessionBean | 76:             LoanApplicationLocalHome home = getLoanApplicationHome(); |
| → | LoanApplicationLocalHome | 89:             Collection entities = home.findByCustomerId(customerId); |
| → | LoanApplicationSessionBean | 88:             LoanApplicationLocalHome home = getLoanApplicationHome(); |
| → | LoanApplicationLocalHome | 101:             Collection entities = home.findByStatus(status); |
| → | LoanApplicationSessionBean | 100:             LoanApplicationLocalHome home = getLoanApplicationHome(); |
| → | LoanApplicationLocal | 115:             String currentStatus = entity.getStatus(); |
| → | LoanApplicationLocal | 121:             entity.setStatus(LoanConstants.STATUS_SUBMITTED); |
| → | LoanApplicationLocalHome | 113:             LoanApplicationLocal entity = home.findByPrimaryKey(applicationId); |
| → | LoanApplicationSessionBean | 112:             LoanApplicationLocalHome home = getLoanApplicationHome(); |
| → | LoanApplicationLocal | 136:             String currentStatus = entity.getStatus(); |
| → | LoanApplicationLocal | 142:             entity.setStatus(LoanConstants.STATUS_CANCELLED); |
| → | LoanApplicationLocalHome | 134:             LoanApplicationLocal entity = home.findByPrimaryKey(applicationId); |
| → | LoanApplicationSessionBean | 133:             LoanApplicationLocalHome home = getLoanApplicationHome(); |
| → | LoanApplicationLocal | 158:                 entity.setCustomerId(dto.getCustomerId()); |
| → | LoanApplicationLocal | 161:                 entity.setRequestedAmount(dto.getRequestedAmount()); |
| → | LoanApplicationLocal | 164:                 entity.setLoanType(dto.getLoanType()); |
| → | LoanApplicationLocal | 167:                 entity.setLoanPurpose(dto.getLoanPurpose()); |
| → | LoanApplicationLocal | 170:                 entity.setTerm(dto.getTerm()); |
| → | LoanApplicationLocal | 173:                 entity.setInterestRate(dto.getInterestRate()); |
| → | LoanApplicationLocal | 176:                 entity.setRemarks(dto.getRemarks()); |
| → | LoanApplicationLocalHome | 155:             LoanApplicationLocal entity = home.findByPrimaryKey(dto.getApplicationId()); |
| → | LoanApplicationSessionBean | 154:             LoanApplicationLocalHome home = getLoanApplicationHome(); |
| → | CollateralLocalHome | 194:             collateralHome.create( 195:                     collateralId, 196:                     dto.getApplicationId(), 197:                     dto.getCollateralType(), 198:                   |
| → | LoanApplicationSessionBean | 193:             String collateralId = generateId(); |
| → | ServiceLocator | 189:             com.banking.loan.entity.CollateralLocalHome collateralHome = 190:                     (com.banking.loan.entity.CollateralLocalHome) ServiceLocator.getInstance() 191:                   |
| → | LoanApplicationDTO | 218:         dto.setApplicationId(entity.getApplicationId()); |
| → | LoanApplicationDTO | 219:         dto.setCustomerId(entity.getCustomerId()); |
| → | LoanApplicationDTO | 220:         dto.setApplicationDate(entity.getApplicationDate()); |
| → | LoanApplicationDTO | 221:         dto.setRequestedAmount(entity.getRequestedAmount()); |
| → | LoanApplicationDTO | 222:         dto.setLoanType(entity.getLoanType()); |
| → | LoanApplicationDTO | 223:         dto.setLoanPurpose(entity.getLoanPurpose()); |
| → | LoanApplicationDTO | 224:         dto.setTerm(entity.getTerm()); |
| → | LoanApplicationDTO | 225:         dto.setInterestRate(entity.getInterestRate()); |
| → | LoanApplicationDTO | 226:         dto.setStatus(entity.getStatus()); |
| → | LoanApplicationDTO | 227:         dto.setScreeningResult(entity.getScreeningResult()); |
| → | LoanApplicationDTO | 228:         dto.setScreeningDate(entity.getScreeningDate()); |
| → | LoanApplicationDTO | 229:         dto.setApprovedAmount(entity.getApprovedAmount()); |
| → | LoanApplicationDTO | 230:         dto.setApproverEmployeeId(entity.getApproverEmployeeId()); |
| → | LoanApplicationDTO | 231:         dto.setRemarks(entity.getRemarks()); |

#### 데이터 접근

| 대상 | 관계 | 근거 | 신뢰도 |
| --- | --- | --- | --- |
| LOAN_APPLICATION | WRITES | - | - |
| LOAN_APPLICATION | READS | - | - |
| LoanApplicationDTO | REFER_TO | - | 1.0 |
| LoanApplicationLocal | REFER_TO | - | 1.0 |
| LoanApplicationLocalHome | REFER_TO | - | 1.0 |
| LoanApplicationException | REFER_TO | - | 1.0 |
| LoanConstants | REFER_TO | - | 1.0 |
| ejb-jar.xml | REFER_TO | - | 0.9 |
| LOAN_APPLICATION | READS | - | - |
| LoanApplicationDTO | REFER_TO | - | 1.0 |
| LoanApplicationLocal | REFER_TO | - | 1.0 |
| LoanApplicationLocalHome | REFER_TO | - | 1.0 |
| LoanApplicationException | REFER_TO | - | 1.0 |
| ejb-jar.xml | REFER_TO | - | 0.9 |
| LOAN_APPLICATION | READS | - | - |
| LoanApplicationLocal | REFER_TO | - | 1.0 |
| LoanApplicationLocalHome | REFER_TO | - | 1.0 |
| LoanApplicationException | REFER_TO | - | 1.0 |
| ejb-jar.xml | REFER_TO | - | 0.9 |
| LOAN_APPLICATION | READS | - | - |
| LoanApplicationLocal | REFER_TO | - | 1.0 |
| LoanApplicationLocalHome | REFER_TO | - | 1.0 |
| LoanApplicationException | REFER_TO | - | 1.0 |
| ejb-jar.xml | REFER_TO | - | 0.9 |
| LOAN_APPLICATION | READS | - | - |
| LoanApplicationLocal | REFER_TO | - | 1.0 |
| LoanApplicationLocalHome | REFER_TO | - | 1.0 |
| LoanApplicationException | REFER_TO | - | 1.0 |
| ejb-jar.xml | REFER_TO | - | 0.9 |
| LOAN_APPLICATION | WRITES | - | - |
| LOAN_APPLICATION | READS | - | - |
| LoanApplicationLocal | REFER_TO | - | 1.0 |
| LoanApplicationLocalHome | REFER_TO | - | 1.0 |
| LoanApplicationException | REFER_TO | - | 1.0 |
| LoanConstants | REFER_TO | - | 1.0 |
| ejb-jar.xml | REFER_TO | - | 0.9 |
| LOAN_APPLICATION | WRITES | - | - |
| LOAN_APPLICATION | READS | - | - |
| LoanApplicationLocal | REFER_TO | - | 1.0 |
| LoanApplicationLocalHome | REFER_TO | - | 1.0 |
| LoanApplicationException | REFER_TO | - | 1.0 |
| LoanConstants | REFER_TO | - | 1.0 |
| ejb-jar.xml | REFER_TO | - | 0.9 |
| LOAN_APPLICATION | WRITES | - | - |
| LOAN_APPLICATION | READS | - | - |
| LoanApplicationDTO | REFER_TO | - | 1.0 |
| LoanApplicationLocal | REFER_TO | - | 1.0 |
| LoanApplicationLocalHome | REFER_TO | - | 1.0 |
| LoanApplicationException | REFER_TO | - | 1.0 |
| ejb-jar.xml | REFER_TO | - | 0.9 |
| COLLATERAL | WRITES | - | - |
| COLLATERAL | READS | - | - |
| CollateralDTO | REFER_TO | - | 1.0 |
| CollateralLocal | REFER_TO | - | 1.0 |
| CollateralLocalHome | REFER_TO | - | 1.0 |
| LoanApplicationException | REFER_TO | - | 1.0 |
| LoanConstants | REFER_TO | - | 1.0 |
| ServiceLocator | REFER_TO | - | 1.0 |
| ejb-jar.xml | REFER_TO | - | 0.9 |
| LOAN_APPLICATION | READS | - | - |
| LoanApplicationLocal | REFER_TO | - | 1.0 |
| LoanApplicationLocalHome | REFER_TO | - | 1.0 |
| LoanConstants | REFER_TO | - | 1.0 |
| ServiceLocator | REFER_TO | - | 1.0 |
| ejb-jar.xml | REFER_TO | - | 0.9 |
| LoanApplicationDTO | REFER_TO | - | 1.0 |
| LoanApplicationLocal | REFER_TO | - | 1.0 |
| LoanApplicationLocal | REFER_TO | - | 1.0 |

#### 요약 코드

```
없음
```

### LoanApplicationSessionHome

#### 기본 정보

| 항목 | 값 |
| --- | --- |
| 이름 | LoanApplicationSessionHome |
| 타입 | CLASS |
| FQN | com.banking.loan.session.LoanApplicationSessionHome |
| 패키지 | com.banking.loan.session |
| 스테레오타입 | COMMAND |
| 파일 | - |
| 라인 | - |
| 토큰 | - |

#### 요약

> 이 클래스는 ‘여신 신청 관리’ 기능을 제공하는 세션 빈을 원격에서 사용할 수 있도록 하는 리모트 홈 인터페이스 역할을 한다. 원격 호출자가 세션 컴포넌트 인스턴스 생성을 요청해 참조를 획득하고, 이후 여신 신청의 생성·조회·상태변경 등 업무 처리를 원격으로 수행할 수 있게 하는 계약을 정의한다. 또한 생성 과정에서의 실패와 원격 통신 오류를 예외로 선언해 호출 측이 생성/통신 실패를 구분하여 처리하도록 한다.

#### 메서드

| 이름 | 시그니처 | 반환타입 | 수정자 | 요약 |
| --- | --- | --- | --- | --- |
| create | LoanApplicationSession create() throws CreateException, RemoteException | - | - | 여신 신청 관리를 위한 세션 빈의 리모트 홈 인터페이스에서, 원격으로 사용할 세션 컴포넌트 인스턴스 획득(생성)을 요청하는 계약을 정의한다. 호출자는 이 생성 요청을 통해 세션 컴포넌트 참조를 받아, 이후 여신 신청의 생성·조회·상태변경 같은 업무 처리를 원격으로 수행할 수 있다. 생성 과정에서 발생할 수 있는 생성 실패와 원격 통신 오류를 예외로 선언하여, 호출 측이 생성/통신 실패를 구분해 처리하도록 한다. |

#### 필드

| 이름 | 타입 | 수정자 | 요약 |
| --- | --- | --- | --- |
| - | - | - | - |

#### 구조 관계

| 방향 | 관계 | 대상 | 속성 |
| --- | --- | --- | --- |
| → | DEPENDENCY | LoanApplicationSession | source_member=create, usage=return |
| ← | ASSOCIATION | LoanServlet | source_member=handleSubmitApplication |
| ← | ASSOCIATION | LoanServlet | source_member=init |
| ← | ASSOCIATION | LoanServlet | source_member=handleCreateApplication |
| ← | ASSOCIATION | LoanServlet | source_member=handleGetApplication |
| ← | DEPENDENCY | LoanProcessSessionBean | source_member=cancelProcess, usage=local_var |
| ← | DEPENDENCY | LoanProcessSessionBean | source_member=submitAndGetResult, usage=local_var |

#### 호출 관계

| 방향 | 대상 | 호출코드 |
| --- | --- | --- |
| ← | LoanServlet | - |
| ← | LoanProcessSessionBean | - |

#### 데이터 접근

| 대상 | 관계 | 근거 | 신뢰도 |
| --- | --- | --- | --- |
| LoanApplicationSession | REFER_TO | - | 1.0 |
| ejb-jar.xml | REFER_TO | - | 1.0 |

#### 요약 코드

```
없음
```

### LoanExecutionSession

#### 기본 정보

| 항목 | 값 |
| --- | --- |
| 이름 | LoanExecutionSession |
| 타입 | CLASS |
| FQN | com.banking.loan.session.LoanExecutionSession |
| 패키지 | com.banking.loan.session |
| 스테레오타입 | COMMAND/READMODEL |
| 파일 | - |
| 라인 | - |
| 토큰 | - |

#### 요약

> com.banking.loan.session.LoanExecutionSession은 승인된 여신을 실행해 대출 원장을 생성하고, 생성된 원장을 다양한 기준으로 조회하는 기능을 원격으로 제공하는 세션 빈 리모트 컴포넌트 인터페이스이다. 대출신청을 식별하는 값 1건을 입력받아 여신 실행(대출 원장 생성)을 수행한 뒤 원장 정보를 반환하며, 원장 식별자 또는 고객 식별자(문자열)로 원장 정보/목록을 조회해 전달 객체 형태로 돌려준다. 원격 호출 자체의 통신 문제는 원격 예외로, 여신 실행·원장 조회 처리 중 업무 규칙 위반이나 처리 실패는 전용 실행 실패 예외로 호출자에게 전파되도록 계약을 정의한다.

#### 메서드

| 이름 | 시그니처 | 반환타입 | 수정자 | 요약 |
| --- | --- | --- | --- | --- |
| executeLoan | LoanLedgerDTO executeLoan(String applicationId)             throws RemoteException, LoanExecutionException | - | - | 이 원격 컴포넌트 인터페이스는 승인된 여신을 실행해 대출 원장을 생성하고, 생성된 원장 정보를 반환하는 역할을 가진다. 이 작업은 대출신청을 식별하는 값 1건을 입력으로 받아 해당 신청 건의 실행(대출 원장 생성)을 수행한 결과를 원장 정보로 돌려준다. 실행 과정에서 원격 호출 자체가 실패하면 원격 통신 오류가 발생할 수 있고, 여신 실행(원장 생성) 처리 중 업무 규칙/처리 실패가 발생하면 실행 실패 예외로 중단된다. |
| getLedger | LoanLedgerDTO getLedger(String ledgerId)             throws RemoteException, LoanExecutionException | - | - | 이 리모트 컴포넌트 인터페이스는 승인된 여신의 실행 결과로 생성되는 대출 원장을 조회하는 업무를 다루며, 여기서는 특정 원장 식별자를 입력받아 해당 원장 정보를 조회해 반환하는 역할을 맡는다. 호출자는 원장 식별자를 전달하면, 원장 조회 결과를 원장 정보 전달 객체 형태로 돌려받는다. 원장 조회 과정에서 원격 호출 계층의 통신 문제는 원격 예외로, 여신 실행/원장 조회 도메인 규칙이나 처리 실패는 전용 예외로 호출자에게 전달되도록 선언되어 있다. |
| getLedgersByCustomer | Collection getLedgersByCustomer(String customerId)             throws RemoteException, LoanExecutionException | - | - | 이 인터페이스는 승인된 대출의 실행(대출 원장 생성) 및 원장 조회 업무를 원격 호출로 제공하는 계약을 정의하며, 이 범위의 기능은 그 중 고객 기준 원장 조회를 담당한다. 입력으로 고객을 식별하는 문자열을 받아 해당 고객과 연관된 대출 원장들의 목록을 컬렉션 형태로 반환한다. 원격 호출 과정에서 통신 오류가 발생할 수 있어 원격 예외를 계약에 포함하며, 대출 실행/조회 도메인 처리 중 오류가 발생하면 대출 실행 관련 예외를 호출자에게 전파한다. |

#### 필드

| 이름 | 타입 | 수정자 | 요약 |
| --- | --- | --- | --- |
| - | - | - | - |

#### 구조 관계

| 방향 | 관계 | 대상 | 속성 |
| --- | --- | --- | --- |
| → | DEPENDENCY | LoanLedgerDTO | source_member=getLedger, usage=return |
| → | DEPENDENCY | LoanLedgerDTO | source_member=executeLoan, usage=return |
| → | DEPENDENCY | LoanExecutionException | source_member=getLedgersByCustomer, usage=parameter |
| ← | DEPENDENCY | LoanServlet | source_member=handleExecuteLoan, usage=local_var |
| ← | DEPENDENCY | LoanExecutionSessionHome | source_member=create, usage=return |

#### 호출 관계

| 방향 | 대상 | 호출코드 |
| --- | --- | --- |
| ← | LoanServlet | - |

#### 데이터 접근

| 대상 | 관계 | 근거 | 신뢰도 |
| --- | --- | --- | --- |
| LoanLedgerDTO | REFER_TO | - | 1.0 |
| LoanExecutionException | REFER_TO | - | 1.0 |
| LoanLedgerDTO | REFER_TO | - | 1.0 |
| LoanExecutionException | REFER_TO | - | 1.0 |
| LoanExecutionException | REFER_TO | - | 1.0 |

#### 요약 코드

```
없음
```

### LoanExecutionSessionBean

#### 기본 정보

| 항목 | 값 |
| --- | --- |
| 이름 | LoanExecutionSessionBean |
| 타입 | CLASS |
| FQN | com.banking.loan.session.LoanExecutionSessionBean |
| 패키지 | com.banking.loan.session |
| 스테레오타입 | COMMAND/READMODEL |
| 파일 | - |
| 라인 | - |
| 토큰 | - |

#### 요약

> 이 클래스는 ‘여신 실행’ Stateless 세션 빈 구현체로서, 승인된 여신 신청의 status가 APPROVED가 아니면 “실행 불가 상태”로 중단하고 실행 가능 시 approvedAmount, interestRate, term, customerId를 바탕으로 monthlyPayment를 계산해 원장을 생성한 뒤 신청 상태를 APPROVED → STATUS_EXECUTED로 전이시키며 원장 상태는 LEDGER_ACTIVE, 상환방식은 REPAYMENT_EQUAL_INSTALLMENT로 설정한다. 또한 JNDI로 여신 신청/원장 엔티티의 로컬 홈을 찾아 리플렉션으로 findByPrimaryKey(String) 또는 findByCustomerId를 호출해 단건/고객별 원장을 조회하고, ledgerId, applicationId, customerId, principalAmount, outstandingBalance, interestRate, loanStartDate, maturityDate, repaymentMethod, monthlyPayment, status, lastRepaymentDate, nextRepaymentDate를 DTO로 반환한다. 처리 중 예외(예: “고객별 원장 조회 실패: {customerId}”) 발생 시 세션 컨텍스트(ctx)를 통해 트랜잭션을 롤백 전용으로 표시한 뒤 식별자를 포함한 도메인 예외로 래핑해 재전파하며, serialVersionUID=1L로 직렬화 호환성을 유지한다.

#### 메서드

| 이름 | 시그니처 | 반환타입 | 수정자 | 요약 |
| --- | --- | --- | --- | --- |
| executeLoan | public LoanLedgerDTO executeLoan(String applicationId) throws LoanExecutionException | - | - | 승인된 여신 신청에 대해서만 대출 실행과 원장 생성을 수행하며, 입력받은 신청 식별자로 신청 정보를 조회한 뒤 status가 APPROVED가 아니면 "실행 불가 상태"로 중단한다. 실행 가능하면 신청 데이터에서 approvedAmount, interestRate, term, customerId를 읽어 월 상환금(매월 상환액)을 계산하고, 대출 시작일(현재 시각), 만기일(시작일 + term개월), 다음 상환일(시작일 + 1개월)을 확정한다. 새 원장 식별자를 생성한 뒤 JNDI로 로컬 홈을 조회하여 원장 생성(create)을 반영하고, 여신 신청의 status를 STATUS_EXECUTED로 변경해 실행 상태를 확정한다. 마지막으로 원장 식별자/신청 식별자/고객 식별자/원금(principalAmount)/미상환잔액(outstandingBalance)/금리(interestRate)/대출 시작일(loanStartDate)/만기일(maturityDate)/상환방식(REPAYMENT_EQUAL_INSTALLMENT)/월 상환금(monthlyPayment)/상태(LEDGER_ACTIVE)/다음 상환일(nextRepaymentDate)을 포함한 반환용 정보를 구성해 돌려준다. 조회 실패, JNDI 조회 실패, 실행 규칙 위반 또는 기타 예외가 발생하면 트랜잭션을 롤백 전용으로 표시하고 도메인 예외로 래핑해 재전파한다. |
| getLedger | public LoanLedgerDTO getLedger(String ledgerId) throws LoanExecutionException | - | - | 승인된 대출 신청에 대해 대출 실행과 원장 생성/조회를 담당하는 구성요소에서, 이 로직은 입력된 원장 식별자로 원장 정보를 조회해 전달용 데이터로 반환한다. 먼저 JNDI_LOAN_LEDGER_ENTITY에 해당하는 로컬 홈 객체를 서비스 로케이터 방식(룩업 결과 캐싱)으로 획득해 원장 조회 진입점을 준비한다. 이후 리플렉션으로 "findByPrimaryKey"(String 인자)를 찾아 실행하여 원장 식별자에 해당하는 원장 엔티티를 가져오고, 이를 전달용 데이터로 변환해 반환한다. 조회 과정에서 발생하는 모든 예외는 "원장 조회 실패: {원장식별자}" 메시지로 감싸 동일한 업무 예외로 재던져 호출자에게 실패 원인과 식별자를 함께 전달한다. |
| getLedgersByCustomer | public Collection getLedgersByCustomer(String customerId) throws LoanExecutionException | - | - | 이 클래스는 승인된 여신 신청에 대해 대출 실행과 원장 생성/조회 책임을 가지며, 이 구간은 특정 고객(customerId)에 연결된 대출 원장 목록을 조회해 반환하는 역할을 한다. JNDI로 등록된 원장 조회 대상을 식별하는 값을 사용해 로컬 홈을 찾은 뒤, 리플렉션으로 "findByCustomerId" 조회를 실행하여 고객별 원장 엔티티 컬렉션을 획득한다. 조회된 각 엔티티를 순회하면서 전송/반환에 적합한 형태로 변환해 목록으로 누적한 후 그 목록을 반환한다. 처리 중 어떤 예외가 발생하든 모두 포괄적으로 잡아 "고객별 원장 조회 실패: " + customerId 메시지로 도메인 예외로 감싸 다시 던진다. |
| getLoanApplicationHome | private LoanApplicationLocalHome getLoanApplicationHome() throws NamingException | - | - | 이 코드는 승인된 여신 신청을 처리하는 흐름에서, 여신 신청 정보를 생성·조회할 수 있는 로컬 홈 접근점을 확보하기 위한 준비 단계 역할을 한다. J2EE 서비스 로케이터 패턴을 통해 JNDI에 등록된 여신 신청 엔티티의 로컬 홈을 'JNDI_LOAN_APPLICATION_ENTITY' 식별자로 조회해 반환한다. JNDI 조회가 실패하면 NamingException을 호출자에게 그대로 전파하여, 이후 여신 실행/원장 생성·조회 과정이 잘못된 리소스 참조 상태로 진행되지 않도록 한다. 결과적으로 이후 로직이 여신 신청 엔티티에 대한 생성/조회 작업을 수행할 수 있는 진입점을 제공한다. |
| ledgerEntityToDTO | private LoanLedgerDTO ledgerEntityToDTO(Object entity) throws Exception | - | - | 승인된 여신 신청에 대한 원장 정보를 다루는 흐름에서, 입력으로 받은 임의의 도메인 객체로부터 대출 원장 정보를 읽어 원장 정보 전달 객체로 변환한다. 리플렉션을 사용해 입력 객체의 getter들을 동적으로 호출하여 ledgerId, applicationId, customerId, principalAmount, outstandingBalance, interestRate, loanStartDate, maturityDate, repaymentMethod, monthlyPayment, status, lastRepaymentDate, nextRepaymentDate 값을 추출한다. 추출된 값들은 별도 검증이나 변환 없이 그대로 원장 정보 전달 객체의 각 필드에 설정되어, 이후 대출 실행/원장 생성·조회 로직에서 일관된 형태로 참조될 수 있게 한다. 처리 중 리플렉션 호출 과정의 예외 가능성을 상위로 전달하기 위해 예외를 그대로 던진다. |
| generateId | private String generateId() | - | - | 여신 실행 과정에서 내부적으로 사용할 식별자 값을 생성하기 위한 보조 로직이다. 무작위 UUID를 문자열로 만든 뒤 '-' 문자를 제거하여 구분자가 없는 형태로 정규화한다. 그 결과에서 앞 20자리만 잘라 고정 길이로 맞추고, 영문 문자를 모두 대문자로 변환해 저장·전달 시 형식을 일관되게 한다. 외부 저장소나 설정을 참조하지 않고, 입력값 없이 매 호출마다 새로운 식별자 문자열을 반환한다. |
| setSessionContext | public void setSessionContext(SessionContext ctx) | - | - | 여신 실행을 담당하는 무상태 세션 빈 구현체에서, 컨테이너로부터 제공받는 세션 컨텍스트를 내부 보관 영역에 연결한다. 이를 통해 이후 처리에서 보안/트랜잭션 등 실행 환경 정보에 접근할 수 있는 기반을 마련한다. 별도의 검증이나 분기 없이 입력으로 받은 세션 컨텍스트 참조를 그대로 저장하여 기존 참조를 대체한다. |
| ejbCreate | public void ejbCreate() throws CreateException | - | - | 이 클래스는 승인된 여신 신청에 대해 대출 실행과 원장 생성/조회까지 담당하는 Stateless 세션 빈 구현체이며, 여기의 코드는 빈 인스턴스 생성 시점에 호출되는 생성 라이프사이클 훅에 해당한다. 현재 구현은 본문이 비어 있어 생성 시 추가 초기화 작업(컨텍스트 설정, 자원 확보, 검증 등)을 수행하지 않는다. 다만 생성 과정에서 문제가 생길 수 있음을 전제로 생성 관련 예외를 상위로 전달할 수 있도록 선언되어 있다. |
| ejbRemove | public void ejbRemove() | - | - | 승인된 여신 신청에 대해 대출 실행과 원장 생성/조회를 수행하는 구성요소에서, 인스턴스가 제거되는 생명주기 시점에 호출되는 콜백을 제공한다. 그러나 이 구간에서는 제거 시점에 수행해야 할 정리 작업(자원 해제, 상태 정리, 후처리 등)을 구현하지 않아 즉시 반환한다. 따라서 제거 이벤트를 수신하는 역할만 형태적으로 갖고 있으며, 내부 상태 변경이나 외부 시스템과의 상호작용은 발생하지 않는다. |
| ejbActivate | public void ejbActivate() | - | - | 이 구성요소는 승인된 여신 신청에 대해 대출 실행 및 원장 생성/조회를 담당하는 Stateless 세션 빈 구현체이며, 여기서는 활성화 시점에 호출되는 생명주기 콜백을 제공한다. 활성화 이벤트가 발생해도 별도의 초기화, 자원 재연결, 상태 복원 처리를 수행하지 않고 즉시 종료한다. 이는 인스턴스가 활성화될 때 재설정해야 할 내부 상태나 외부 자원이 없다는 전제 하에 빈 동작으로 두어 생명주기 인터페이스 요구사항만 충족하려는 의도로 해석된다. |
| ejbPassivate | public void ejbPassivate() | - | - | 여신 실행을 담당하는 Stateless 세션 빈에서 인스턴스가 패시베이션(비활성화)될 때 호출되는 생명주기 훅을 제공하지만, 본문이 비어 있어 실제로 수행되는 작업은 없다. 따라서 승인된 여신 신청에 대한 대출 실행이나 원장 생성/조회와 직접 연결되는 처리, 상태 변경, 자원 정리/저장 같은 동작을 하지 않는다. 결과적으로 컨테이너 호출에 응답하기 위한 형식적 엔트리 포인트이며, 현재 구현에서는 의도적으로 무처리(no-op)로 남겨져 있다. |

#### 필드

| 이름 | 타입 | 수정자 | 요약 |
| --- | --- | --- | --- |
| serialVersionUID | long | - | 직렬화 가능한 세션 빈에서 클래스 버전 호환성을 유지하기 위한 직렬화 버전 식별자이며, 값은 1L로 고정된 상수이다. |
| ctx | SessionContext | - | 여신 실행을 담당하는 Stateless 세션 빈에서 컨테이너가 제공하는 세션 컨텍스트를 보관하여, 승인된 여신 신청의 대출 실행 및 원장 생성/조회 과정에서 호출자 보안/트랜잭션 등 실행 환경 정보를 참조하는 데 사용된다. |

#### 구조 관계

| 방향 | 관계 | 대상 | 속성 |
| --- | --- | --- | --- |
| → | DEPENDENCY | LoanLedgerDTO | source_member=getLedger, usage=return |
| → | DEPENDENCY | LoanLedgerDTO | source_member=ledgerEntityToDTO, usage=local_new |
| → | DEPENDENCY | LoanLedgerDTO | source_member=executeLoan, usage=return |
| → | DEPENDENCY | LoanApplicationLocal | source_member=executeLoan, usage=local_var |
| → | DEPENDENCY | LoanApplicationLocalHome | source_member=getLoanApplicationHome, usage=return |
| → | DEPENDENCY | LoanApplicationLocalHome | source_member=executeLoan, usage=local_var |
| → | DEPENDENCY | LoanExecutionException | source_member=getLedgersByCustomer, usage=local_new |
| → | DEPENDENCY | InterestCalculator | source_member=executeLoan, usage=local_var |
| → | DEPENDENCY | LoanConstants | source_member=getLoanApplicationHome, usage=field_call |
| → | DEPENDENCY | LoanConstants | source_member=getLedgersByCustomer, usage=local_var |
| → | DEPENDENCY | LoanConstants | source_member=executeLoan, usage=local_var |
| → | DEPENDENCY | ServiceLocator | source_member=getLoanApplicationHome, usage=cast |
| → | DEPENDENCY | ServiceLocator | source_member=getLedgersByCustomer, usage=local_var |
| → | DEPENDENCY | ServiceLocator | source_member=executeLoan, usage=local_var |
| → | DEPENDENCY | SessionContext | source_member=setSessionContext, usage=parameter |

#### 호출 관계

| 방향 | 대상 | 호출코드 |
| --- | --- | --- |
| → | LoanLedgerDTO | - |
| → | LoanApplicationLocal | - |
| → | LoanApplicationLocalHome | - |
| → | InterestCalculator | - |
| → | ServiceLocator | - |
| → | LoanLedgerDTO | 94:             dto.setLedgerId(ledgerId); |
| → | LoanLedgerDTO | 95:             dto.setApplicationId(applicationId); |
| → | LoanLedgerDTO | 96:             dto.setCustomerId(customerId); |
| → | LoanLedgerDTO | 97:             dto.setPrincipalAmount(approvedAmount); |
| → | LoanLedgerDTO | 98:             dto.setOutstandingBalance(approvedAmount); |
| → | LoanLedgerDTO | 99:             dto.setInterestRate(interestRate); |
| → | LoanLedgerDTO | 100:             dto.setLoanStartDate(loanStartDate); |
| → | LoanLedgerDTO | 101:             dto.setMaturityDate(maturityDate); |
| → | LoanLedgerDTO | 102:             dto.setRepaymentMethod(LoanConstants.REPAYMENT_EQUAL_INSTALLMENT); |
| → | LoanLedgerDTO | 103:             dto.setMonthlyPayment(monthlyPayment); |
| → | LoanLedgerDTO | 104:             dto.setStatus(LoanConstants.LEDGER_ACTIVE); |
| → | LoanLedgerDTO | 105:             dto.setNextRepaymentDate(nextRepaymentDate); |
| → | LoanApplicationLocal | 50:             String customerId = application.getCustomerId(); |
| → | LoanApplicationLocal | 49:             int term = application.getTerm(); |
| → | LoanApplicationLocal | 48:             BigDecimal interestRate = application.getInterestRate(); |
| → | LoanApplicationLocal | 41:             String currentStatus = application.getStatus(); |
| → | LoanApplicationLocal | 91:             application.setStatus(LoanConstants.STATUS_EXECUTED); |
| → | LoanApplicationLocal | 47:             BigDecimal approvedAmount = application.getApprovedAmount(); |
| → | LoanApplicationLocalHome | 39:             LoanApplicationLocal application = appHome.findByPrimaryKey(applicationId); |
| → | LoanExecutionSessionBean | 38:             LoanApplicationLocalHome appHome = getLoanApplicationHome(); |
| → | LoanExecutionSessionBean | 67:             String ledgerId = generateId(); |
| → | InterestCalculator | 52:             BigDecimal monthlyPayment = InterestCalculator.calculateMonthlyPayment( 53:                     approvedAmount, interestRate, term); |
| → | ServiceLocator | 69:             EJBLocalHome ledgerHome = ServiceLocator.getInstance() 70:                     .getLocalHome(LoanConstants.JNDI_LOAN_LEDGER_ENTITY); |
| → | ServiceLocator | 125:             EJBLocalHome ledgerHome = ServiceLocator.getInstance() 126:                     .getLocalHome(LoanConstants.JNDI_LOAN_LEDGER_ENTITY); |
| → | ServiceLocator | 140:             EJBLocalHome ledgerHome = ServiceLocator.getInstance() 141:                     .getLocalHome(LoanConstants.JNDI_LOAN_LEDGER_ENTITY); |
| → | LoanLedgerDTO | 169:         dto.setLedgerId((String) clazz.getMethod("getLedgerId").invoke(entity)); |
| → | LoanLedgerDTO | 170:         dto.setApplicationId((String) clazz.getMethod("getApplicationId").invoke(entity)); |
| → | LoanLedgerDTO | 171:         dto.setCustomerId((String) clazz.getMethod("getCustomerId").invoke(entity)); |
| → | LoanLedgerDTO | 172:         dto.setPrincipalAmount((BigDecimal) clazz.getMethod("getPrincipalAmount").invoke(entity)); |
| → | LoanLedgerDTO | 173:         dto.setOutstandingBalance((BigDecimal) clazz.getMethod("getOutstandingBalance").invoke(entity)); |
| → | LoanLedgerDTO | 174:         dto.setInterestRate((BigDecimal) clazz.getMethod("getInterestRate").invoke(entity)); |
| → | LoanLedgerDTO | 175:         dto.setLoanStartDate((Date) clazz.getMethod("getLoanStartDate").invoke(entity)); |
| → | LoanLedgerDTO | 176:         dto.setMaturityDate((Date) clazz.getMethod("getMaturityDate").invoke(entity)); |
| → | LoanLedgerDTO | 177:         dto.setRepaymentMethod((String) clazz.getMethod("getRepaymentMethod").invoke(entity)); |
| → | LoanLedgerDTO | 178:         dto.setMonthlyPayment((BigDecimal) clazz.getMethod("getMonthlyPayment").invoke(entity)); |
| → | LoanLedgerDTO | 179:         dto.setStatus((String) clazz.getMethod("getStatus").invoke(entity)); |
| → | LoanLedgerDTO | 180:         dto.setLastRepaymentDate((Date) clazz.getMethod("getLastRepaymentDate").invoke(entity)); |
| → | LoanLedgerDTO | 181:         dto.setNextRepaymentDate((Date) clazz.getMethod("getNextRepaymentDate").invoke(entity)); |

#### 데이터 접근

| 대상 | 관계 | 근거 | 신뢰도 |
| --- | --- | --- | --- |
| LOAN_APPLICATION | WRITES | - | - |
| LOAN_LEDGER | WRITES | - | - |
| LOAN_APPLICATION | READS | - | - |
| LOAN_LEDGER | READS | - | - |
| LoanLedgerDTO | REFER_TO | - | 1.0 |
| LoanApplicationLocal | REFER_TO | - | 1.0 |
| LoanApplicationLocalHome | REFER_TO | - | 1.0 |
| LoanExecutionException | REFER_TO | - | 1.0 |
| InterestCalculator | REFER_TO | - | 1.0 |
| LoanConstants | REFER_TO | - | 1.0 |
| ServiceLocator | REFER_TO | - | 1.0 |
| ejb-jar.xml | REFER_TO | - | 0.9 |
| ejb-jar.xml | REFER_TO | - | 0.9 |
| LOAN_LEDGER | READS | - | - |
| LoanLedgerDTO | REFER_TO | - | 1.0 |
| LoanExecutionException | REFER_TO | - | 1.0 |
| LoanConstants | REFER_TO | - | 1.0 |
| ServiceLocator | REFER_TO | - | 1.0 |
| ejb-jar.xml | REFER_TO | - | 0.9 |
| LOAN_LEDGER | READS | - | - |
| LoanExecutionException | REFER_TO | - | 1.0 |
| LoanConstants | REFER_TO | - | 1.0 |
| ServiceLocator | REFER_TO | - | 1.0 |
| ejb-jar.xml | REFER_TO | - | 0.9 |
| LOAN_APPLICATION | READS | - | - |
| LoanApplicationLocal | REFER_TO | - | 1.0 |
| LoanApplicationLocalHome | REFER_TO | - | 1.0 |
| LoanConstants | REFER_TO | - | 1.0 |
| ServiceLocator | REFER_TO | - | 1.0 |
| ejb-jar.xml | REFER_TO | - | 0.9 |
| LoanLedgerDTO | REFER_TO | - | 1.0 |

#### 요약 코드

```
없음
```

### LoanExecutionSessionHome

#### 기본 정보

| 항목 | 값 |
| --- | --- |
| 이름 | LoanExecutionSessionHome |
| 타입 | CLASS |
| FQN | com.banking.loan.session.LoanExecutionSessionHome |
| 패키지 | com.banking.loan.session |
| 스테레오타입 | COMMAND |
| 파일 | - |
| 라인 | - |
| 토큰 | - |

#### 요약

> 이 클래스는 승인된 여신의 실행(대출 원장 생성)과 원장 조회 업무를 수행하는 원격 세션 빈에 접근하기 위한 리모트 홈 인터페이스이다. 호출자가 해당 원격 컴포넌트 인스턴스를 얻을 수 있도록 생성 진입점(create)을 제공하며, 이를 통해 여신 실행/원장 처리 기능을 제공하는 원격 인터페이스를 획득하게 한다. 생성 과정에서 인스턴스 생성 실패 또는 원격 통신 문제를 예외로 구분해 선언함으로써, 호출자가 생성 실패와 원격 호출 실패를 분리해 처리하도록 한다.

#### 메서드

| 이름 | 시그니처 | 반환타입 | 수정자 | 요약 |
| --- | --- | --- | --- | --- |
| create | LoanExecutionSession create() throws CreateException, RemoteException | - | - | 이 구성요소는 승인된 여신의 실행(대출 원장 생성) 및 원장 조회 업무를 처리하는 원격 세션 빈에 접근하기 위한 리모트 홈 인터페이스이며, 여기서는 그 원격 세션 접근 인스턴스를 생성해 반환하는 진입점을 정의한다. 호출자는 이 생성 동작을 통해 여신 실행/원장 처리 기능을 제공하는 원격 컴포넌트 인터페이스를 획득한다. 생성 과정에서 인스턴스 생성 자체가 실패하거나 원격 통신 과정에서 문제가 발생할 수 있음을 예외로 선언해, 호출자가 생성 실패 및 원격 호출 실패 상황을 구분해 처리하도록 강제한다. |

#### 필드

| 이름 | 타입 | 수정자 | 요약 |
| --- | --- | --- | --- |
| - | - | - | - |

#### 구조 관계

| 방향 | 관계 | 대상 | 속성 |
| --- | --- | --- | --- |
| → | DEPENDENCY | LoanExecutionSession | source_member=create, usage=return |
| ← | ASSOCIATION | LoanServlet | source_member=init |

#### 호출 관계

| 방향 | 대상 | 호출코드 |
| --- | --- | --- |
| ← | LoanServlet | - |

#### 데이터 접근

| 대상 | 관계 | 근거 | 신뢰도 |
| --- | --- | --- | --- |
| LoanExecutionSession | REFER_TO | - | 1.0 |
| ejb-jar.xml | REFER_TO | - | 1.0 |

#### 요약 코드

```
없음
```

### LoanLedgerSession

#### 기본 정보

| 항목 | 값 |
| --- | --- |
| 이름 | LoanLedgerSession |
| 타입 | CLASS |
| FQN | com.banking.loan.session.LoanLedgerSession |
| 패키지 | com.banking.loan.session |
| 스테레오타입 | COMMAND/READMODEL |
| 파일 | - |
| 라인 | - |
| 토큰 | - |

#### 요약

> com.banking.loan.session.LoanLedgerSession은 여신 원장 관리 세션 빈의 리모트 컴포넌트 인터페이스로, 원격 호출로 여신 원장 조회와 상환 처리뿐 아니라 잔여 상환 스케줄 계산 및 원장 마감 업무까지 제공하는 계약을 정의한다. 원장 식별자(또는 고객 식별자)를 기반으로 원장 상세/목록을 조회하고, 특정 원장에 대해 잔여 스케줄을 계산한 결과가 반영된 원장 정보를 반환하며, 지정한 원장을 마감 처리하도록 요청할 수 있다. 모든 기능은 원격 통신/호출 실패에 따른 Remote 예외와 업무 처리 실패에 따른 여신 원장 도메인 실행 예외를 호출자에게 그대로 전파하도록 명시한다.

#### 메서드

| 이름 | 시그니처 | 반환타입 | 수정자 | 요약 |
| --- | --- | --- | --- | --- |
| getLedger | LoanLedgerDTO getLedger(String ledgerId)             throws RemoteException, LoanExecutionException | - | - | 이 원장 관리용 리모트 컴포넌트 인터페이스는 여신 원장 조회, 상환 처리, 잔여 스케줄 계산, 원장 마감 등 원장 관련 업무를 다루며, 이 선언은 그중 원장 조회 역할을 담당한다. 입력으로 원장을 식별하는 문자열 값을 받아 해당 원장의 상세 정보를 담은 전송 객체 형태로 반환하도록 계약을 정의한다. 원격 호출 환경에서 통신 문제로 인한 원격 예외가 발생할 수 있음을 전제하며, 원장 조회 수행 중 업무 규칙/처리 실패에 해당하는 도메인 예외도 호출자에게 전달되도록 설계되어 있다. |
| getActiveLedgers | Collection getActiveLedgers()             throws RemoteException, LoanExecutionException | - | - | 원장 관리 리모트 컴포넌트 인터페이스에서, 현재 활성 상태로 간주되는 원장 목록을 조회해 컬렉션 형태로 반환하는 계약을 정의한다. 호출자는 이 결과를 여신 원장 조회나 원장 마감 등 후속 처리의 입력으로 사용할 수 있다. 네트워크 원격 호출 과정에서 발생할 수 있는 통신 오류는 원격 예외로, 업무 처리 중단이나 실행 실패는 여신 원장 업무 실행 예외로 호출자에게 전파하도록 선언한다. 이 시그니처만으로는 활성 원장 판단 기준이나 필터 조건은 드러나지 않으며, 실제 조회 규칙은 구현체에 위임된다. |
| getLedgersByCustomer | Collection getLedgersByCustomer(String customerId)             throws RemoteException, LoanExecutionException | - | - | 원장 관리 리모트 컴포넌트 인터페이스에서 특정 고객을 기준으로 여신 원장 목록을 조회해 반환하도록 정의된 계약이다. 입력으로 고객을 식별하는 문자열을 받아, 해당 고객과 연관된 원장들을 컬렉션 형태로 돌려주는 조회 중심 기능을 제공한다. 원격 호출 과정에서 통신 계층 오류가 발생할 수 있으며, 원장 조회 수행 중 대출 업무 실행 과정의 실패를 도메인 예외로 신호할 수 있도록 예외 전파를 명시한다. |
| processRepayment | RepaymentDTO processRepayment(String ledgerId, BigDecimal principalAmount,                                    BigDecimal interestAmount, BigDecimal penaltyAmount,                                    String repaymentType)             throws RemoteException, LoanExecutionException | - | - | 원장 관리 리모트 컴포넌트 인터페이스의 기능 중 하나로, 특정 원장(원장 식별자)을 대상으로 원금·이자·연체료 금액과 상환 유형을 입력받아 상환 처리를 수행하고 그 결과를 반환하도록 계약을 정의한다. 반환값은 상환 처리 결과(예: 반영된 상환 내역/계산 결과 등)를 담는 응답 객체로 제공되어 호출 측이 후속 처리에 활용할 수 있게 한다. 처리 과정에서 업무 수행 실패나 규칙 위반 등 실행 오류가 발생하면 도메인 예외를 통해 실패 사유를 호출자에게 전달하며, 리모트 호출 특성상 원격 통신 오류도 함께 전파될 수 있다. |
| calculateRemainingSchedule | LoanLedgerDTO calculateRemainingSchedule(String ledgerId)             throws RemoteException, LoanExecutionException | - | - | 이 인터페이스는 여신 원장 관리 업무(원장 조회, 상환 처리, 잔여 스케줄 계산, 마감 등)를 원격으로 제공하기 위한 계약을 정의한다. 여기서는 원장 식별자를 입력받아 해당 원장의 잔여 상환(또는 잔여 스케줄) 계산 결과가 포함된 원장 정보를 반환하도록 정의한다. 원격 호출 과정에서 통신/원격 실행 문제가 발생할 수 있음을 예외로 노출하며, 업무 처리 중 실행 오류도 별도의 예외로 호출자에게 전달해 오류 처리를 위임한다. |
| closeLedger | void closeLedger(String ledgerId)             throws RemoteException, LoanExecutionException | - | - | 원장 관리 리모트 컴포넌트 인터페이스에서, 특정 원장 식별자를 입력받아 해당 원장을 마감(클로징) 처리하도록 요청하는 계약을 정의한다. 이 작업은 여신 원장 업무의 마감 단계에 해당하며, 마감 대상은 입력으로 전달된 원장 식별자로 특정된다. 원격 호출 환경에서 통신/호출 실패가 발생할 수 있음을 전제로 원격 호출 관련 예외를 외부로 전달하며, 업무 처리 중 실행 실패는 별도의 도메인 예외로 호출자에게 전파한다. |

#### 필드

| 이름 | 타입 | 수정자 | 요약 |
| --- | --- | --- | --- |
| - | - | - | - |

#### 구조 관계

| 방향 | 관계 | 대상 | 속성 |
| --- | --- | --- | --- |
| → | DEPENDENCY | LoanLedgerDTO | source_member=calculateRemainingSchedule, usage=return |
| → | DEPENDENCY | LoanLedgerDTO | source_member=getLedger, usage=return |
| → | DEPENDENCY | RepaymentDTO | source_member=processRepayment, usage=return |
| → | DEPENDENCY | LoanExecutionException | source_member=getLedgersByCustomer, usage=parameter |
| → | DEPENDENCY | LoanExecutionException | source_member=processRepayment, usage=parameter |
| → | DEPENDENCY | LoanExecutionException | source_member=getActiveLedgers, usage=parameter |
| ← | DEPENDENCY | LoanServlet | source_member=handleGetLedger, usage=local_var |
| ← | DEPENDENCY | LoanLedgerSessionHome | source_member=create, usage=return |

#### 호출 관계

| 방향 | 대상 | 호출코드 |
| --- | --- | --- |
| ← | LoanServlet | - |

#### 데이터 접근

| 대상 | 관계 | 근거 | 신뢰도 |
| --- | --- | --- | --- |
| LoanLedgerDTO | REFER_TO | - | 1.0 |
| LoanExecutionException | REFER_TO | - | 1.0 |
| LoanExecutionException | REFER_TO | - | 1.0 |
| LoanExecutionException | REFER_TO | - | 1.0 |
| RepaymentDTO | REFER_TO | - | 1.0 |
| LoanExecutionException | REFER_TO | - | 1.0 |
| LoanLedgerDTO | REFER_TO | - | 1.0 |
| LoanExecutionException | REFER_TO | - | 1.0 |
| LoanExecutionException | REFER_TO | - | 1.0 |

#### 요약 코드

```
없음
```

### LoanLedgerSessionBean

#### 기본 정보

| 항목 | 값 |
| --- | --- |
| 이름 | LoanLedgerSessionBean |
| 타입 | CLASS |
| FQN | com.banking.loan.session.LoanLedgerSessionBean |
| 패키지 | com.banking.loan.session |
| 스테레오타입 | COMMAND/READMODEL |
| 파일 | - |
| 라인 | - |
| 토큰 | - |

#### 요약

> 이 클래스는 여신 원장 관리용 Stateless 세션 빈으로, 여신 원장 조회, 상환 처리, 잔여 스케줄 산출, 원장 마감 업무를 수행한다. JNDI(LoanConstants.JNDI_LOAN_LEDGER_ENTITY, LoanConstants.JNDI_REPAYMENT_ENTITY) 룩업을 서비스 로케이터 캐싱으로 수행해 원장/상환 엔티티 로컬 홈을 확보하고, 원장 로컬 컴포넌트를 ledgerId, applicationId, customerId, principalAmount, outstandingBalance(미상환잔액), interestRate, loanStartDate, maturityDate, repaymentMethod, monthlyPayment, status, lastRepaymentDate, nextRepaymentDate 등의 DTO로 변환해 단건/목록 조회 결과로 반환한다. 상환은 status가 LEDGER_ACTIVE가 아니면 차단하고, 상환금(principalAmount+interestAmount+penaltyAmount)을 반영한 뒤 outstandingBalance <= 0이면 상태를 LEDGER_ACTIVE → LEDGER_COMPLETED로 전이한다. 잔여 스케줄은 monthlyPayment != null && monthlyPayment > 0 && outstandingBalance > 0일 때 remainingMonths를 올림(ROUND_CEILING)으로 계산하며, 처리 과정에서 컨테이너의 호출자/트랜잭션/보안 정보 접근 및 롤백 등 기능을 위해 세션 컨텍스트(ctx)를 활용한다.

#### 메서드

| 이름 | 시그니처 | 반환타입 | 수정자 | 요약 |
| --- | --- | --- | --- | --- |
| getLedger | public LoanLedgerDTO getLedger(String ledgerId) throws LoanExecutionException | - | - | 원장 관리 기능 맥락에서, 입력으로 받은 원장 식별자에 해당하는 여신 원장 정보를 조회해 전송용 데이터로 변환하여 반환한다. 먼저 JNDI를 통해 여신 원장 엔티티에 접근 가능한 로컬 홈을 획득한 뒤, 기본키(원장 식별자) 기준 조회로 원장 레코드에 대한 접근 핸들을 얻는다. 조회된 원장 정보를 전송용 구조로 매핑해 호출자에게 돌려주며, 이 과정에서 저장/상태 변경은 수행하지 않는다. 조회 대상이 없거나 조회에 실패하면 조회 실패 메시지에 원장 식별자를 포함해 업무 예외로 감싸 던지고, JNDI 이름 해석/룩업 실패도 별도 메시지로 동일한 업무 예외로 변환해 전파한다. |
| getActiveLedgers | public Collection getActiveLedgers() throws LoanExecutionException | - | - | 원장 관리 기능의 일부로, 상태값이 LEDGER_ACTIVE(활성)인 여신 원장 목록을 조회해 반환한다. 먼저 여신 원장 엔티티에 접근하기 위한 로컬 홈을 획득한 뒤, 활성 상태 조건으로 원장들을 검색해 컬렉션으로 가져온다. 조회된 엔티티 컬렉션은 호출자가 사용하기 쉬운 전송/응답용 데이터 형태로 변환하여 반환한다. 조회 과정에서 조회 실패 예외가 발생하면 "활성 원장 조회 실패"로, 이름 해석(JNDI) 과정에서 오류가 나면 "JNDI 조회 실패" 메시지로 업무 예외로 감싸 상위로 전달한다. |
| getLedgersByCustomer | public Collection getLedgersByCustomer(String customerId) throws LoanExecutionException | - | - | 원장 관리 업무를 처리하는 구성요소에서, 입력된 고객 식별자에 해당하는 여신 원장 목록을 조회해 반환한다. 먼저 JNDI에 등록된 여신 원장 엔티티의 로컬 홈 인터페이스를 획득한 뒤, 고객 식별자 기준 조회 계약을 사용해 원장 엔티티 묶음을 찾는다. 조회된 엔티티 컬렉션은 외부로 전달 가능한 DTO 컬렉션으로 변환해 돌려준다. 조회 대상이 없거나 조회 과정에서 문제가 발생하면 검색 실패 예외를, JNDI 이름 해석/룩업에 실패하면 네이밍 예외를 각각 잡아 고객 식별자 또는 오류 메시지를 포함한 도메인 예외로 감싸서 전파한다. |
| processRepayment | public RepaymentDTO processRepayment(String ledgerId, BigDecimal principalAmount,                                           BigDecimal interestAmount, BigDecimal penaltyAmount,                                           String repaymentType) throws LoanExecutionException | - | - | 원장 관리 기능의 일부로, 입력된 ledgerId에 해당하는 원장을 조회한 뒤 status가 LEDGER_ACTIVE가 아니면 "ACTIVE 상태만 상환 가능" 규칙에 따라 상환을 차단하고 업무 예외를 발생시킨다. 상환을 진행할 수 있으면 상환 식별자와 거래 식별자를 새로 만들고, 상환일자를 현재 시각으로 확정한 다음 principalAmount + interestAmount + penaltyAmount로 totalAmount를 산출한다. 이어서 상환 내역을 영속 생성하고, 원장에 원금/이자 상환을 반영한 후 outstandingBalance가 0 이하(<= 0)면 원장 status를 LEDGER_COMPLETED로 상태 전이시킨다. 마지막으로 repaymentId, ledgerId, repaymentDate, principalAmount, interestAmount, penaltyAmount, totalAmount, repaymentType, transactionId를 담은 반환용 정보를 구성해 반환하며, 원장 조회/상환 생성/JNDI 조회/업무 예외 발생 시에는 트랜잭션을 롤백 전용으로 표시하고 적절한 메시지로 감싼 업무 예외로 전파한다. |
| calculateRemainingSchedule | public LoanLedgerDTO calculateRemainingSchedule(String ledgerId) throws LoanExecutionException | - | - | 원장 식별자(ledgerId)로 원장 정보를 조회한 뒤 outstandingBalance(미상환잔액), interestRate(이자율), monthlyPayment(월 납입금)을 읽어 남은 상환기간과 예상 만기일을 산출해 반환용 데이터 형태로 제공한다. monthlyPayment가 null이 아니고 0보다 크며(outstandingBalance도 0보다 큰 경우) outstandingBalance·interestRate·12개월을 기준으로 월 상환금을 재산출하고, 재산출 결과가 0보다 크면 outstandingBalance ÷ 재산출월상환금의 올림(ROUND_CEILING) 정수값을 remainingMonths로 계산한다. 현재 시점에 remainingMonths만큼 월을 더해 projectedMaturity(Date)를 구하고, 조회한 원장 정보를 변환한 반환 객체의 maturityDate(만기일)를 이 projectedMaturity로 덮어써 예상 만기일로 갱신하며 monthlyPayment도 설정한다. 조회 단계에서 FinderException이 발생하면 "원장 조회 실패: ledgerId"로, JNDI 관련 NamingException이 발생하면 "JNDI 조회 실패: ..."로 도메인 예외로 감싸 상위 호출자에게 전달한다. |
| closeLedger | public void closeLedger(String ledgerId) throws LoanExecutionException | - | - | 원장 마감 업무의 일부로, 입력된 원장 식별자로 원장 정보를 기본키 기준으로 조회한 뒤 마감 가능 여부를 검증한다. outstandingBalance(잔여 잔액)가 0보다 초과(> 0)하면 “원장 마감 불가”로 처리하며, 잔여 금액을 포함한 메시지로 예외를 발생시켜 마감을 차단한다. 잔여 잔액이 없으면 status(상태)를 LEDGER_COMPLETED로 변경하여 원장을 ‘마감 완료’ 상태로 확정한다. 조회 실패(FinderException)나 JNDI 조회 실패(NamingException), 또는 마감 불가로 발생한 업무 예외가 발생하면 트랜잭션을 롤백 전용으로 표시한 후 원인과 함께 업무 예외로 전달한다. |
| getLoanLedgerHome | private LoanLedgerLocalHome getLoanLedgerHome() throws NamingException | - | - | 원장 관리 업무를 수행하는 구성요소 내부에서, 여신 원장 엔티티에 접근하기 위한 로컬 홈 인터페이스를 획득하는 보조 로직이다. JNDI에 등록된 여신 원장 엔티티의 식별자(LoanConstants.JNDI_LOAN_LEDGER_ENTITY)를 사용해, 룩업 결과를 캐싱하는 로케이터를 통해 로컬 홈을 조회한다. 조회 결과는 여신 원장 로컬 홈 타입으로 캐스팅하여 반환하며, JNDI 이름 해석/룩업 과정에서 발생할 수 있는 NamingException을 호출자에게 전파한다. |
| getRepaymentHome | private RepaymentLocalHome getRepaymentHome() throws NamingException | - | - | 이 코드는 원장 관리 기능에서 상환 정보를 다루는 엔티티 빈에 접근하기 위한 조회용 진입점을 제공한다. 서비스 로케이터 패턴을 통해 JNDI 이름(LoanConstants.JNDI_REPAYMENT_ENTITY)으로 로컬 홈 객체를 조회해 반환하며, 조회 실패 시 NamingException을 호출자에게 그대로 전파한다. 반환된 로컬 홈은 이후 상환 정보의 생성/조회 등 엔티티 접근에 필요한 기반 객체로 사용되도록 의도되어 있다. |
| entityToDTO | private LoanLedgerDTO entityToDTO(LoanLedgerLocal entity) | - | - | 원장 관리 기능 흐름에서, 여신 원장 정보가 들어있는 로컬 컴포넌트로부터 화면/호출자에게 전달하기 적합한 데이터 형태를 구성하기 위해 변환을 수행한다. 입력으로 받은 원장 데이터에서 ledgerId, applicationId, customerId, principalAmount, outstandingBalance, interestRate, loanStartDate, maturityDate, repaymentMethod, monthlyPayment, status, lastRepaymentDate, nextRepaymentDate 값을 각각 읽어 동일한 속성들로 채워 넣는다. 이 과정에서 값의 검증·가공·계산이나 저장 처리는 없고, 원장 조회/응답을 위한 데이터 복제에 해당한다. 최종적으로 속성들이 채워진 여신 원장 정보를 반환하여 이후 조회 결과 구성에 활용되도록 한다. |
| entitiesToDTOs | private Collection entitiesToDTOs(Collection entities) | - | - | 원장 관리 기능 흐름에서, 원장 정보가 들어있는 로컬 컴포넌트들의 모음을 화면/호출자 전달에 적합한 데이터 형태의 목록으로 변환해 반환한다. 입력으로 받은 컬렉션을 순회하면서 각 요소를 여신 원장 로컬 컴포넌트로 해석한 뒤, 단건 변환 로직을 적용해 변환 결과를 누적한다. 이렇게 누적된 변환 결과 컬렉션을 최종 결과로 반환하며, 데이터 저장/갱신 같은 상태 변경은 수행하지 않는다. |
| generateId | private String generateId() | - | - | 원장 관리 기능을 수행하는 구성요소 내부에서, 신규 처리에 사용할 식별자 문자열을 생성하는 역할을 한다. 무작위 UUID 값을 기반으로 하되, 하이픈("-")을 제거해 연속된 문자열로 정규화한다. 정규화된 결과에서 앞 20자만 사용하여 길이를 고정하고, 영문을 대문자로 변환해 표기 규칙을 통일한다. 그 결과 외부 입력 없이 항상 20자리의 대문자 식별자 문자열을 반환한다. |
| setSessionContext | public void setSessionContext(SessionContext ctx) | - | - | 원장 관리 업무를 수행하는 Stateless 세션 빈에서, 컨테이너가 제공하는 세션 컨텍스트를 외부로부터 전달받아 내부에 보관한다. 이렇게 보관된 컨텍스트는 이후 처리 과정에서 보안, 트랜잭션, 호출자 정보 등 컨테이너 기능에 접근하기 위한 기반으로 활용될 수 있다. 메서드 자체는 검증이나 추가 로직 없이 전달받은 컨텍스트 참조를 그대로 저장하는 역할만 수행한다. |
| ejbCreate | public void ejbCreate() throws CreateException | - | - | 원장 관리용 Stateless 세션 빈이 생성될 때 컨테이너가 호출하는 생성 단계 훅으로, 빈 인스턴스 초기화 시점에 실행된다. 구현은 비어 있어 생성 시점에 수행할 별도의 초기화 작업(자원 준비, 상태 설정, 검증 등)을 하지 않는다. 따라서 생성 과정에서 추가적인 도메인 처리나 원장 조회·상환 처리·마감 처리 로직으로의 위임은 발생하지 않는다. |
| ejbRemove | public void ejbRemove() | - | - | 원장 관리 업무를 수행하는 Stateless 세션 빈에서, 컨테이너가 인스턴스를 제거하는 시점에 호출되는 생명주기 훅을 제공한다. 그러나 본 구현은 본문이 비어 있어 인스턴스 제거 시 별도의 정리 작업(자원 해제, 상태 초기화, 후처리 로깅 등)을 수행하지 않는다. 그 결과 제거 시점의 동작은 컨테이너 기본 동작에 전적으로 의존하며, 이 범위 내에서는 데이터 조회나 갱신을 포함한 어떠한 업무 처리도 발생하지 않는다. |
| ejbActivate | public void ejbActivate() | - | - | 원장 관리 기능을 담당하는 무상태 세션 빈 구현체의 생명주기 단계 중, 인스턴스가 활성화될 때 호출되는 훅에 해당한다. 현재 범위에서는 활성화 시점에 수행할 초기화, 상태 복구, 자원 연결 등의 처리가 구현되어 있지 않아 실제 동작이 없다. 외부 자원 조회나 갱신, 내부 필드 조작 또한 수행하지 않는다. 결과적으로 활성화 이벤트를 수신하되 별도 처리를 하지 않는 빈 구현으로 동작한다. |
| ejbPassivate | public void ejbPassivate() | - | - | 원장 관리용 Stateless 세션 빈에서, 컨테이너가 인스턴스를 패시베이션(passivation)할 때 호출되는 생명주기 훅을 제공한다. 구현은 비어 있어 패시베이션 시점에 세션 컨텍스트 정리, 자원 해제, 상태 보존/복원 같은 추가 작업을 수행하지 않는다. 따라서 이 구간만으로는 여신 원장 조회·상환 처리·잔여 스케줄 산출·원장 마감과 같은 업무 데이터의 조회나 변경이 발생하지 않는다. |

#### 필드

| 이름 | 타입 | 수정자 | 요약 |
| --- | --- | --- | --- |
| serialVersionUID | long | - | 이 필드는 직렬화 가능한 원장 관리 Stateless 세션 빈의 클래스 버전 식별자(serialVersionUID)로, 직렬화/역직렬화 시 호환성을 보장하기 위해 1L로 고정된 상수이다. |
| ctx | SessionContext | - | 이 필드는 원장 관리용 Stateless 세션 빈에서 EJB 컨테이너가 제공하는 세션 컨텍스트를 보관하며, 여신 원장 조회·상환 처리·원장 마감 등의 업무 수행 중 호출자/트랜잭션/보안 정보 접근이나 롤백 처리 같은 컨테이너 기능을 사용하기 위한 참조로 활용된다. |

#### 구조 관계

| 방향 | 관계 | 대상 | 속성 |
| --- | --- | --- | --- |
| → | DEPENDENCY | LoanLedgerDTO | source_member=getLedger, usage=return |
| → | DEPENDENCY | LoanLedgerDTO | source_member=entityToDTO, usage=local_new |
| → | DEPENDENCY | LoanLedgerDTO | source_member=calculateRemainingSchedule, usage=return |
| → | DEPENDENCY | RepaymentDTO | source_member=processRepayment, usage=return |
| → | DEPENDENCY | LoanLedgerLocal | source_member=getLedger, usage=local_var |
| → | DEPENDENCY | LoanLedgerLocal | source_member=closeLedger, usage=local_var |
| → | DEPENDENCY | LoanLedgerLocal | source_member=entityToDTO, usage=parameter |
| → | DEPENDENCY | LoanLedgerLocal | source_member=processRepayment, usage=local_var |
| → | DEPENDENCY | LoanLedgerLocal | source_member=entitiesToDTOs, usage=cast |
| → | DEPENDENCY | LoanLedgerLocalHome | source_member=getLoanLedgerHome, usage=return |
| → | DEPENDENCY | LoanLedgerLocalHome | source_member=getLedger, usage=local_var |
| → | DEPENDENCY | LoanLedgerLocalHome | source_member=getActiveLedgers, usage=local_var |
| → | DEPENDENCY | LoanLedgerLocalHome | source_member=processRepayment, usage=local_var |
| → | DEPENDENCY | LoanLedgerLocalHome | source_member=calculateRemainingSchedule, usage=local_var |
| → | DEPENDENCY | RepaymentLocal | source_member=processRepayment, usage=local_var |
| → | DEPENDENCY | RepaymentLocalHome | source_member=getRepaymentHome, usage=return |
| → | DEPENDENCY | RepaymentLocalHome | source_member=processRepayment, usage=local_var |
| → | DEPENDENCY | LoanExecutionException | source_member=getLedger, usage=return |
| → | DEPENDENCY | LoanExecutionException | source_member=getActiveLedgers, usage=local_new |
| → | DEPENDENCY | LoanExecutionException | source_member=processRepayment, usage=local_var |
| → | DEPENDENCY | LoanExecutionException | source_member=calculateRemainingSchedule, usage=local_new |
| → | DEPENDENCY | InterestCalculator | source_member=calculateRemainingSchedule, usage=local_var |
| → | DEPENDENCY | LoanConstants | source_member=getLoanLedgerHome, usage=local_var |
| → | DEPENDENCY | LoanConstants | source_member=getRepaymentHome, usage=cast |
| → | DEPENDENCY | LoanConstants | source_member=getActiveLedgers, usage=field_call |
| → | DEPENDENCY | ServiceLocator | source_member=getLoanLedgerHome, usage=local_var |
| → | DEPENDENCY | ServiceLocator | source_member=getRepaymentHome, usage=cast |
| → | DEPENDENCY | SessionContext | source_member=setSessionContext, usage=parameter |

#### 호출 관계

| 방향 | 대상 | 호출코드 |
| --- | --- | --- |
| → | LoanLedgerDTO | - |
| → | RepaymentDTO | - |
| → | LoanLedgerLocal | - |
| → | LoanLedgerLocalHome | - |
| → | RepaymentLocalHome | - |
| → | InterestCalculator | - |
| → | LoanLedgerLocalHome | 41:             LoanLedgerLocal entity = home.findByPrimaryKey(ledgerId); |
| → | LoanLedgerSessionBean | 40:             LoanLedgerLocalHome home = getLoanLedgerHome(); |
| → | LoanLedgerLocalHome | 53:             Collection entities = home.findByStatus(LoanConstants.LEDGER_ACTIVE); |
| → | LoanLedgerSessionBean | 52:             LoanLedgerLocalHome home = getLoanLedgerHome(); |
| → | LoanLedgerLocalHome | 65:             Collection entities = home.findByCustomerId(customerId); |
| → | LoanLedgerSessionBean | 64:             LoanLedgerLocalHome home = getLoanLedgerHome(); |
| → | RepaymentDTO | 105:             dto.setRepaymentId(repaymentId); |
| → | RepaymentDTO | 106:             dto.setLedgerId(ledgerId); |
| → | RepaymentDTO | 107:             dto.setRepaymentDate(repaymentDate); |
| → | RepaymentDTO | 108:             dto.setPrincipalAmount(principalAmount); |
| → | RepaymentDTO | 109:             dto.setInterestAmount(interestAmount); |
| → | RepaymentDTO | 110:             dto.setPenaltyAmount(penaltyAmount); |
| → | RepaymentDTO | 111:             dto.setTotalAmount(totalAmount); |
| → | RepaymentDTO | 112:             dto.setRepaymentType(repaymentType); |
| → | RepaymentDTO | 113:             dto.setTransactionId(transactionId); |
| → | LoanLedgerLocal | 101:                 ledger.setStatus(LoanConstants.LEDGER_COMPLETED); |
| → | LoanLedgerLocal | 98:             ledger.applyRepayment(principalAmount, interestAmount); |
| → | LoanLedgerLocalHome | 79:             LoanLedgerLocal ledger = ledgerHome.findByPrimaryKey(ledgerId); |
| → | RepaymentLocalHome | 93:             RepaymentLocal repayment = repaymentHome.create( 94:                     repaymentId, ledgerId, repaymentDate, 95:                     principalAmount, interestAmount, penaltyAmount, 9 |
| → | LoanLedgerSessionBean | 78:             LoanLedgerLocalHome ledgerHome = getLoanLedgerHome(); |
| → | LoanLedgerSessionBean | 92:             RepaymentLocalHome repaymentHome = getRepaymentHome(); |
| → | LoanLedgerSessionBean | 86:             String repaymentId = generateId(); |
| → | LoanLedgerDTO | 156:             dto.setMaturityDate(projectedMaturity); |
| → | LoanLedgerDTO | 157:             dto.setMonthlyPayment(monthlyPayment); |
| → | LoanLedgerLocal | 136:             BigDecimal outstandingBalance = ledger.getOutstandingBalance(); |
| → | LoanLedgerLocal | 137:             BigDecimal interestRate = ledger.getInterestRate(); |
| → | LoanLedgerLocal | 138:             BigDecimal monthlyPayment = ledger.getMonthlyPayment(); |
| → | LoanLedgerLocalHome | 134:             LoanLedgerLocal ledger = home.findByPrimaryKey(ledgerId); |
| → | LoanLedgerSessionBean | 133:             LoanLedgerLocalHome home = getLoanLedgerHome(); |
| → | LoanLedgerSessionBean | 155:             LoanLedgerDTO dto = entityToDTO(ledger); |
| → | InterestCalculator | 143:                 BigDecimal recalculated = InterestCalculator.calculateMonthlyPayment( 144:                         outstandingBalance, interestRate, 12); |
| → | LoanLedgerLocal | 177:             ledger.setStatus(LoanConstants.LEDGER_COMPLETED); |
| → | LoanLedgerLocalHome | 170:             LoanLedgerLocal ledger = home.findByPrimaryKey(ledgerId); |
| → | LoanLedgerSessionBean | 169:             LoanLedgerLocalHome home = getLoanLedgerHome(); |
| → | LoanLedgerDTO | 204:         dto.setLedgerId(entity.getLedgerId()); |
| → | LoanLedgerDTO | 205:         dto.setApplicationId(entity.getApplicationId()); |
| → | LoanLedgerDTO | 206:         dto.setCustomerId(entity.getCustomerId()); |
| → | LoanLedgerDTO | 207:         dto.setPrincipalAmount(entity.getPrincipalAmount()); |
| → | LoanLedgerDTO | 208:         dto.setOutstandingBalance(entity.getOutstandingBalance()); |
| → | LoanLedgerDTO | 209:         dto.setInterestRate(entity.getInterestRate()); |
| → | LoanLedgerDTO | 210:         dto.setLoanStartDate(entity.getLoanStartDate()); |
| → | LoanLedgerDTO | 211:         dto.setMaturityDate(entity.getMaturityDate()); |
| → | LoanLedgerDTO | 212:         dto.setRepaymentMethod(entity.getRepaymentMethod()); |
| → | LoanLedgerDTO | 213:         dto.setMonthlyPayment(entity.getMonthlyPayment()); |
| → | LoanLedgerDTO | 214:         dto.setStatus(entity.getStatus()); |
| → | LoanLedgerDTO | 215:         dto.setLastRepaymentDate(entity.getLastRepaymentDate()); |
| → | LoanLedgerDTO | 216:         dto.setNextRepaymentDate(entity.getNextRepaymentDate()); |
| → | LoanLedgerSessionBean | 225:             dtos.add(entityToDTO(entity)); |

#### 데이터 접근

| 대상 | 관계 | 근거 | 신뢰도 |
| --- | --- | --- | --- |
| LOAN_LEDGER | READS | - | - |
| LoanLedgerDTO | REFER_TO | - | 1.0 |
| LoanLedgerLocal | REFER_TO | - | 1.0 |
| LoanLedgerLocalHome | REFER_TO | - | 1.0 |
| LoanExecutionException | REFER_TO | - | 1.0 |
| ejb-jar.xml | REFER_TO | - | 0.9 |
| LOAN_LEDGER | READS | - | - |
| LoanLedgerLocal | REFER_TO | - | 1.0 |
| LoanLedgerLocalHome | REFER_TO | - | 1.0 |
| LoanExecutionException | REFER_TO | - | 1.0 |
| LoanConstants | REFER_TO | - | 1.0 |
| ejb-jar.xml | REFER_TO | - | 0.9 |
| LOAN_LEDGER | READS | - | - |
| LoanLedgerLocal | REFER_TO | - | 1.0 |
| LoanLedgerLocalHome | REFER_TO | - | 1.0 |
| LoanExecutionException | REFER_TO | - | 1.0 |
| ejb-jar.xml | REFER_TO | - | 0.9 |
| REPAYMENT | WRITES | - | - |
| LOAN_LEDGER | WRITES | - | - |
| REPAYMENT | READS | - | - |
| LOAN_LEDGER | READS | - | - |
| RepaymentDTO | REFER_TO | - | 1.0 |
| LoanLedgerLocal | REFER_TO | - | 1.0 |
| LoanLedgerLocalHome | REFER_TO | - | 1.0 |
| RepaymentLocal | REFER_TO | - | 1.0 |
| RepaymentLocalHome | REFER_TO | - | 1.0 |
| LoanExecutionException | REFER_TO | - | 1.0 |
| LoanConstants | REFER_TO | - | 1.0 |
| ejb-jar.xml | REFER_TO | - | 0.9 |
| ejb-jar.xml | REFER_TO | - | 0.9 |
| LOAN_LEDGER | READS | - | - |
| LoanLedgerDTO | REFER_TO | - | 1.0 |
| LoanLedgerLocal | REFER_TO | - | 1.0 |
| LoanLedgerLocalHome | REFER_TO | - | 1.0 |
| LoanExecutionException | REFER_TO | - | 1.0 |
| InterestCalculator | REFER_TO | - | 1.0 |
| ejb-jar.xml | REFER_TO | - | 0.9 |
| LOAN_LEDGER | WRITES | - | - |
| LOAN_LEDGER | READS | - | - |
| LoanLedgerLocal | REFER_TO | - | 1.0 |
| LoanLedgerLocalHome | REFER_TO | - | 1.0 |
| LoanExecutionException | REFER_TO | - | 1.0 |
| LoanConstants | REFER_TO | - | 1.0 |
| ejb-jar.xml | REFER_TO | - | 0.9 |
| LoanLedgerLocal | REFER_TO | - | 1.0 |
| LoanLedgerLocalHome | REFER_TO | - | 1.0 |
| LoanConstants | REFER_TO | - | 1.0 |
| ServiceLocator | REFER_TO | - | 1.0 |
| REPAYMENT | READS | - | - |
| RepaymentLocal | REFER_TO | - | 1.0 |
| RepaymentLocalHome | REFER_TO | - | 1.0 |
| LoanConstants | REFER_TO | - | 1.0 |
| ServiceLocator | REFER_TO | - | 1.0 |
| ejb-jar.xml | REFER_TO | - | 0.9 |
| LoanLedgerDTO | REFER_TO | - | 1.0 |
| LoanLedgerLocal | REFER_TO | - | 1.0 |
| LoanLedgerLocal | REFER_TO | - | 1.0 |

#### 요약 코드

```
없음
```

### LoanLedgerSessionHome

#### 기본 정보

| 항목 | 값 |
| --- | --- |
| 이름 | LoanLedgerSessionHome |
| 타입 | CLASS |
| FQN | com.banking.loan.session.LoanLedgerSessionHome |
| 패키지 | com.banking.loan.session |
| 스테레오타입 | COMMAND |
| 파일 | - |
| 라인 | - |
| 토큰 | - |

#### 요약

> 이 클래스는 ‘원장 관리 세션 빈’의 리모트 홈 인터페이스로서, 원격 환경에서 원장 관리 기능을 제공하는 세션 빈 인스턴스를 생성(획득)하는 책임을 가진다. 이를 통해 호출자는 여신 원장 조회, 상환 처리, 잔여 스케줄 계산, 원장 마감 등의 업무 기능을 수행할 수 있는 원격 컴포넌트 인터페이스에 접근한다. 생성 과정에서 발생할 수 있는 생성 실패는 CreateException으로, 분산/원격 통신 관련 문제는 RemoteException으로 호출자에게 전달해 예외 처리를 강제한다.

#### 메서드

| 이름 | 시그니처 | 반환타입 | 수정자 | 요약 |
| --- | --- | --- | --- | --- |
| create | LoanLedgerSession create() throws CreateException, RemoteException | - | - | 이 코드는 원장 관리 기능을 제공하는 세션 빈을 원격에서 사용하기 위한 홈 인터페이스의 생성 계약을 정의한다. 호출자는 이 계약을 통해 원격 컴포넌트 인터페이스 인스턴스를 생성(획득)하여, 여신 원장 조회, 상환 처리, 잔여 스케줄 계산, 원장 마감 등의 업무 기능을 사용할 수 있게 된다. 생성 과정에서 생성 실패 상황은 CreateException으로, 원격 통신/분산 환경의 문제는 RemoteException으로 호출자에게 전달되어 호출 측에서 적절히 처리하도록 강제한다. |

#### 필드

| 이름 | 타입 | 수정자 | 요약 |
| --- | --- | --- | --- |
| - | - | - | - |

#### 구조 관계

| 방향 | 관계 | 대상 | 속성 |
| --- | --- | --- | --- |
| → | DEPENDENCY | LoanLedgerSession | source_member=create, usage=return |
| ← | ASSOCIATION | LoanServlet | source_member=init |
| ← | ASSOCIATION | LoanServlet | source_member=handleGetLedger |

#### 호출 관계

| 방향 | 대상 | 호출코드 |
| --- | --- | --- |
| ← | LoanServlet | - |

#### 데이터 접근

| 대상 | 관계 | 근거 | 신뢰도 |
| --- | --- | --- | --- |
| LoanLedgerSession | REFER_TO | - | 1.0 |
| ejb-jar.xml | REFER_TO | - | 1.0 |

#### 요약 코드

```
없음
```

### LoanProcessSession

#### 기본 정보

| 항목 | 값 |
| --- | --- |
| 이름 | LoanProcessSession |
| 타입 | CLASS |
| FQN | com.banking.loan.session.LoanProcessSession |
| 패키지 | com.banking.loan.session |
| 스테레오타입 | COMMAND/READMODEL |
| 파일 | - |
| 라인 | - |
| 토큰 | - |

#### 요약

> 이 클래스는 여신(대출) 신청부터 심사, 제출까지의 전체 프로세스를 원격에서 Stateful(대화형) 상태로 유지하며 관리하는 세션 빈 리모트 인터페이스로, 신청 → 심사 → 제출 흐름을 단계적으로 진행시키고 결과를 반환하는 책임을 가진다. 진행 중인 여신 프로세스의 현재 상태를 문자열로 확인하거나, 상세한 여신 신청 상태 정보를 조회해 화면 표시 및 다음 단계 판단에 활용할 수 있게 한다. 또한 세션에 누적된 신청 정보를 ‘제출’ 단계로 확정 처리한 뒤 여신 신청 결과 데이터를 반환하고, 필요 시 진행 중인 프로세스를 취소하여 후속 처리가 진행되지 않도록 중단한다. 모든 동작은 원격 통신 실패에 따른 예외 가능성을 전제하며, 제출/조회/취소 과정의 업무 규칙 위반이나 처리 실패는 여신 신청 관련 도메인 예외로 구분해 전달한다.

#### 메서드

| 이름 | 시그니처 | 반환타입 | 수정자 | 요약 |
| --- | --- | --- | --- | --- |
| initializeProcess | void initializeProcess(String customerId)             throws RemoteException, LoanApplicationException | - | - | 이 인터페이스는 대출(여신) 신청부터 심사, 제출까지의 전체 절차를 대화형 상태로 관리하는 상태 유지형 원격 컴포넌트를 정의하며, 여기서는 특정 고객을 기준으로 프로세스 대화를 시작할 수 있도록 초기 상태를 준비하는 동작을 선언한다. 입력으로 전달된 고객 식별자를 바탕으로 해당 고객의 대출 프로세스를 진행할 수 있는 세션/상태를 초기화하는 것이 목적이다. 원격 호출 환경에서 실행되므로 통신/원격 처리 실패 가능성을 전제로 하며, 초기화 과정에서 대출 신청 프로세스 규칙 위반이나 준비 실패가 발생하면 도메인 예외로 실패를 알리도록 계약한다. |
| setLoanDetails | void setLoanDetails(String loanType, BigDecimal amount, int term, String purpose)             throws RemoteException, LoanApplicationException | - | - | 이 인터페이스는 여신 신청부터 심사, 제출까지의 전체 절차를 대화형 상태로 관리하는 Stateful 세션 빈의 리모트 컴포넌트 계약을 정의한다. 그중 이 작업은 대출 신청의 진행 상태에 필요한 여신 정보로서 loanType(대출유형), amount(신청금액), term(기간), purpose(자금용도)를 입력받아 현재 세션의 신청 상세를 설정하는 역할을 한다. 입력값이 업무 규칙에 맞지 않거나 여신 프로세스의 상태상 반영이 불가한 경우에는 업무 예외가 발생할 수 있으며, 원격 호출 과정의 통신/접근 문제는 원격 예외로 보고된다. |
| addCollateral | void addCollateral(String collateralType, String description, BigDecimal value)             throws RemoteException, LoanApplicationException | - | - | 여신 신청부터 심사, 제출까지의 전체 프로세스를 대화형 상태로 관리하는 리모트 컴포넌트에서, 여신 신청 건에 담보 정보를 추가 등록하기 위한 인터페이스 선언이다. 입력으로 담보의 유형과 담보 설명, 그리고 담보 평가금액을 받아 현재 진행 중인 신청 프로세스의 상태에 담보 항목을 반영하는 쓰기 성격의 동작을 수행하도록 의도된다. 원격 호출 환경에서의 통신/호출 실패는 원격 예외로 전달되며, 담보 추가 과정에서 여신 신청 규칙 위반이나 처리 불가 상황은 여신 신청 관련 도메인 예외로 보고된다. |
| requestScreening | ScreeningResultDTO requestScreening()             throws RemoteException, LoanScreeningException | - | - | 여신 신청부터 심사, 제출까지의 전체 프로세스를 대화형 상태로 관리하는 리모트 컴포넌트의 계약으로서, 심사 단계를 수행하도록 요청하는 기능을 정의한다. 호출자는 원격 호출을 통해 심사를 요청하며, 처리 결과는 심사 결과 정보 형태로 반환된다. 원격 통신 문제로 인한 예외가 발생할 수 있고, 심사 업무 규칙 또는 처리 과정에서의 오류는 별도의 심사 예외로 전달되어 호출자가 실패 사유를 구분해 처리할 수 있게 한다. |
| submitAndGetResult | LoanApplicationDTO submitAndGetResult()             throws RemoteException, LoanApplicationException | - | - | 대화형 상태로 관리되는 여신 신청~심사~제출의 전체 프로세스 흐름에서, 현재 세션에 누적된 신청 정보를 ‘제출’ 단계로 확정 처리한 뒤 그 결과를 여신 신청 결과 데이터로 반환하는 원격 호출용 계약을 정의한다. 처리 과정에서 원격 통신 문제로 인한 오류가 발생할 수 있음을 명시하고, 제출/처리 실패나 업무 규칙 위반 등 도메인 오류는 별도의 여신 신청 예외로 전달하도록 선언한다. 즉, 조회만 수행하는 것이 아니라 제출이라는 업무 이벤트를 발생시키고 그 결과 상태를 반환하는 형태의 인터페이스다. |
| getCurrentApplicationStatus | LoanApplicationDTO getCurrentApplicationStatus()             throws RemoteException, LoanApplicationException | - | - | 여신 신청부터 심사, 제출까지의 전체 프로세스를 대화형 상태로 관리하는 Stateful 세션 빈의 리모트 컴포넌트 인터페이스에서, 현재 진행 중인 여신 신청의 상태 정보를 조회해 반환한다. 호출자는 반환된 여신 신청 상태 정보를 통해 현재 단계와 처리 현황을 화면 표시 또는 후속 절차 판단에 활용할 수 있다. 원격 호출 환경에서 통신/인프라 문제로 인한 예외가 발생할 수 있으며, 도메인 규칙이나 상태 조회 과정에서 여신 신청 처리 관련 예외가 발생할 수 있음을 시그니처로 선언한다. |
| cancelProcess | void cancelProcess()             throws RemoteException, LoanApplicationException | - | - | 이 인터페이스는 여신 신청부터 심사, 제출까지의 전체 프로세스를 대화형 상태로 관리하는 원격 Stateful 세션 빈의 계약을 정의하며, 이 범위는 진행 중인 프로세스를 취소하기 위한 동작을 선언한다. 호출이 수행되면 현재 대화 상태로 이어지던 여신 처리 흐름을 중단하고 더 이상 후속 단계가 진행되지 않도록 취소 의도를 전달한다. 원격 호출 환경에서 통신/호출 자체가 실패할 수 있으며, 업무적으로 여신 신청 처리 과정의 오류 상황이 발생하면 해당 오류를 예외로 상위 호출자에게 전달하도록 명시한다. |
| getProcessState | String getProcessState()             throws RemoteException | - | - | 이 컴포넌트는 여신 신청부터 심사, 제출까지의 전체 프로세스를 대화형 상태로 관리하며, 원격 호출을 통해 현재 진행 상태를 확인할 수 있도록 한다. 이 범위의 동작은 현재 여신 프로세스의 상태를 문자열 형태로 반환하여, 호출 측이 다음 처리 단계 판단에 활용하게 한다. 원격 통신 과정에서 발생할 수 있는 오류를 호출자에게 예외로 전달하도록 선언되어 있다. 상태를 변경하거나 저장을 확정하는 동작은 포함하지 않는다. |

#### 필드

| 이름 | 타입 | 수정자 | 요약 |
| --- | --- | --- | --- |
| - | - | - | - |

#### 구조 관계

| 방향 | 관계 | 대상 | 속성 |
| --- | --- | --- | --- |
| → | DEPENDENCY | LoanApplicationDTO | source_member=getCurrentApplicationStatus, usage=return |
| → | DEPENDENCY | LoanApplicationDTO | source_member=submitAndGetResult, usage=return |
| → | DEPENDENCY | ScreeningResultDTO | source_member=requestScreening, usage=return |
| → | DEPENDENCY | LoanApplicationException | source_member=addCollateral, usage=parameter |
| → | DEPENDENCY | LoanApplicationException | source_member=cancelProcess, usage=parameter |
| → | DEPENDENCY | LoanApplicationException | source_member=getCurrentApplicationStatus, usage=parameter |
| → | DEPENDENCY | LoanApplicationException | source_member=initializeProcess, usage=parameter |
| → | DEPENDENCY | LoanApplicationException | source_member=setLoanDetails, usage=parameter |
| → | DEPENDENCY | LoanScreeningException | source_member=requestScreening, usage=local_var |
| ← | DEPENDENCY | LoanProcessSessionHome | source_member=create, usage=return |

#### 호출 관계

| 방향 | 대상 | 호출코드 |
| --- | --- | --- |
| - | - | - |

#### 데이터 접근

| 대상 | 관계 | 근거 | 신뢰도 |
| --- | --- | --- | --- |
| LoanApplicationException | REFER_TO | - | 1.0 |
| LoanApplicationException | REFER_TO | - | 1.0 |
| LoanApplicationException | REFER_TO | - | 1.0 |
| ScreeningResultDTO | REFER_TO | - | 1.0 |
| LoanScreeningException | REFER_TO | - | 1.0 |
| LoanApplicationDTO | REFER_TO | - | 1.0 |
| LoanApplicationException | REFER_TO | - | 1.0 |
| LoanApplicationDTO | REFER_TO | - | 1.0 |
| LoanApplicationException | REFER_TO | - | 1.0 |
| LoanApplicationException | REFER_TO | - | 1.0 |

#### 요약 코드

```
없음
```

### LoanProcessSessionBean

#### 기본 정보

| 항목 | 값 |
| --- | --- |
| 이름 | LoanProcessSessionBean |
| 타입 | CLASS |
| FQN | com.banking.loan.session.LoanProcessSessionBean |
| 패키지 | com.banking.loan.session |
| 스테레오타입 | COMMAND/READMODEL |
| 파일 | - |
| 라인 | - |
| 토큰 | - |

#### 요약

> 이 클래스는 여신 신청의 초기화부터 상세정보 설정, 담보(collaterals) 추가, 심사 요청, 제출까지를 Stateful 세션 빈으로 구현해 대화형 상태(Conversational State)로 관리하며, customerId·applicationId·loanType·requestedAmount·term·purpose(용도)와 processState를 세션 범위에서 유지한다. 프로세스 상태는 "INITIALIZED" → "DETAILS_SET" → "COLLATERAL_ADDED" → "SCREENING_REQUESTED" → "SUBMITTED"로 전이하고 "CANCELLED"도 정의하며, 이를 레벨로 환산해 INITIALIZED=1, DETAILS_SET=2, COLLATERAL_ADDED=3, SCREENING_REQUESTED=4, SUBMITTED=5, CANCELLED=-1, 알 수 없음=0으로 관리하면서 현재 레벨 >= 요구 레벨인 단계만 허용한다. 다음 단계 진행 전 requestedAmount가 null 또는 <= 0이거나 term이 <= 0이면 진행을 차단하고, 심사 요청 시 JNDI(LoanConstants.JNDI_LOAN_APPLICATION_SESSION)로 원격 세션을 찾아 customerId/loanType/requestedAmount/term/loanPurpose로 신청(interestRate=0.05)을 생성한 뒤 각 담보에 applicationId를 설정해 등록하고 상태를 "SCREENING_REQUESTED"로 전이한다. 또한 컨테이너 실행 환경 접근을 위한 SessionContext(ctx)를 보관하며 패시베이션/활성화 콜백(ejbPassivate/ejbActivate)은 제공하되 별도 처리는 하지 않는다.

#### 메서드

| 이름 | 시그니처 | 반환타입 | 수정자 | 요약 |
| --- | --- | --- | --- | --- |
| initializeProcess | public void initializeProcess(String customerId) throws LoanApplicationException | - | - | 대화형으로 관리되는 여신 신청 프로세스를 시작하기 위해, 입력받은 customerId(고객 식별자)가 실제로 존재하는지 고객 엔티티를 기본키 기준으로 조회하여 사전 검증한다. 검증이 통과하면 customerId를 현재 대화 상태에 고정하고, applicationId·loanType·requestedAmount·purpose는 null로, term은 0으로 초기화하며, collaterals(담보 목록)은 빈 목록으로 재구성한다. 이어서 프로세스 상태를 "INITIALIZED"로 설정해, 이후 상세정보 설정/담보 추가/심사 요청/제출 등의 다음 단계로 진행할 수 있는 초기 상태를 확정한다. 고객 조회 실패(FinderException)나 JNDI 조회 실패(NamingException)가 발생하면 각각의 원인과 식별자를 포함한 메시지로 LoanApplicationException으로 감싸 상위로 전달한다. |
| setLoanDetails | public void setLoanDetails(String loanType, BigDecimal amount, int term, String purpose)             throws LoanApplicationException | - | - | 대화형으로 진행되는 여신 신청 프로세스에서 상세 정보를 확정하기 위한 단계로, 현재 processState가 "INITIALIZED"가 아니면 "INITIALIZED 상태에서만 가능"하다는 메시지로 예외를 발생시켜 단계 순서를 강제한다. 신청 금액은 null이거나 0 이하(<= 0)면 오류로 중단하고, 여신 기간(월)도 0 이하(<= 0)면 오류로 중단해 입력값의 유효성을 보장한다. 모든 검증을 통과하면 loanType, requestedAmount, term, purpose 값을 실제 필드에 기록해 상세정보를 확정한다. 마지막으로 processState를 "DETAILS_SET"으로 변경하여 다음 프로세스 단계로의 진행 가능 상태를 명시한다. |
| addCollateral | public void addCollateral(String collateralType, String description, BigDecimal value)             throws LoanApplicationException | - | - | 여신 신청의 대화형 상태를 관리하는 흐름에서, 담보 정보를 추가하기 전에 현재 processState(프로세스 상태)가 "DETAILS_SET" 이상인지 확인한다. 상태가 "DETAILS_SET" 이상이 아니면 "담보 추가 불가: 현재 상태 ... (DETAILS_SET 이상에서만 가능)" 메시지로 예외를 발생시켜 담보 추가를 차단한다. 조건을 만족하면 담보 정보 객체를 새로 구성하면서 collateralType, description, appraisedValue(평가금액), appraisalDate(현재 시각), registrationStatus="PENDING" 값을 확정적으로 세팅한다. 구성된 담보를 내부 담보 목록에 추가하고, processState를 "COLLATERAL_ADDED"로 변경하여 상태 전이를 확정한다. |
| requestScreening | public ScreeningResultDTO requestScreening() throws LoanScreeningException | - | - | 대화형 여신 프로세스에서 ‘DETAILS_SET’ 이상 상태가 아니면 심사 요청을 금지하고, 현재 상태값을 포함한 메시지로 업무 예외를 발생시켜 흐름을 즉시 중단한다. 조건을 만족하면 원격 홈을 JNDI로 조회해 여신 신청 생성 처리를 수행하며, customerId, loanType, requestedAmount, term, loanPurpose, interestRate=0.05 값을 채운 신청 정보를 등록하고 반환된 applicationId를 확정 저장한다. 이어서 보유한 담보 목록을 순회하며 각 담보에 applicationId를 설정한 뒤 담보 등록을 반복 수행하고, 최종적으로 해당 신청을 ‘제출’ 단계로 진행시킨다. 그 다음 원격 심사 컴포넌트를 통해 applicationId 기준으로 심사를 수행해 심사 결과를 반환하며, 내부 프로세스 상태를 ‘SCREENING_REQUESTED’로 전이시킨다. 처리 중 심사 예외 또는 기타 예외가 발생하면 트랜잭션 롤백 전용으로 표시하고, 기타 예외는 메시지를 포함한 심사 예외로 감싸 재전파한다. |
| submitAndGetResult | public LoanApplicationDTO submitAndGetResult() throws LoanApplicationException | - | - | 대화형으로 관리되는 여신 신청 프로세스에서, 현재 진행상태(processState)가 "SCREENING_REQUESTED"가 아닐 경우에는 "SCREENING_REQUESTED 상태에서만 가능" 규칙을 위반한 것으로 보고 업무 예외를 발생시켜 제출을 차단한다. 제출이 가능한 상태이면 JNDI 이름(LoanConstants.JNDI_LOAN_APPLICATION_SESSION)을 사용해 원격 홈을 조회한 뒤 원격 세션을 생성하고, 신청 ID(applicationId)로 여신 신청 상세 정보를 조회해 결과 데이터를 받아온다. 조회가 성공하면 진행상태(processState)를 "SUBMITTED"로 상태 전이시킨 후 조회된 여신 신청 정보를 반환한다. 처리 중 업무 예외는 그대로 재전파하고, 그 외 예외는 "제출 결과 조회 실패" 메시지로 감싼 업무 예외로 변환해 전달한다. |
| getCurrentApplicationStatus | public LoanApplicationDTO getCurrentApplicationStatus() throws LoanApplicationException | - | - | 대화형 상태로 여신 신청 프로세스를 관리하는 흐름에서, 현재 여신 신청의 상태/상세 정보를 조회해 반환한다. 먼저 여신 신청 식별자가 없으면(아직 신청이 생성되지 않은 상태) "아직 신청이 생성되지 않았습니다." 메시지로 예외를 발생시켜 조회 자체를 차단한다. 식별자가 있으면 JNDI 이름(LoanConstants.JNDI_LOAN_APPLICATION_SESSION)으로 원격 홈을 조회한 뒤 원격 세션을 생성하고, 해당 식별자로 여신 신청 정보를 조회해 반환한다. 조회 과정에서 이미 정의된 도메인 예외는 그대로 재전파하고, 그 외 예외는 "신청 상태 조회 실패: ..."로 감싸 원인 예외와 함께 전달한다. |
| cancelProcess | public void cancelProcess() throws LoanApplicationException | - | - | 대화형 상태로 관리되는 여신 신청 프로세스에서, 현재 상태가 이미 "CANCELLED"이면 중복 취소를 금지하기 위해 업무 예외를 발생시킨다. 취소 대상 식별자(applicationId)가 존재하는 경우에만 JNDI 이름(LoanConstants.JNDI_LOAN_APPLICATION_SESSION)으로 원격 홈을 조회해 원격 세션을 생성한 뒤, 해당 여신 신청 건을 ‘취소’ 상태로 전환하도록 취소 요청을 전달한다. 원격 취소 요청의 성공/실패와 무관하게 이 프로세스의 내부 상태(processState)는 최종적으로 "CANCELLED"로 확정되며, 업무 예외가 발생한 경우에는 상태를 "CANCELLED"로 설정한 뒤 예외를 그대로 재전파한다. 그 외 예기치 못한 예외는 동일하게 상태를 "CANCELLED"로 설정하고, "프로세스 취소 실패: ..." 메시지로 래핑하여 업무 예외로 변환해 던진다. |
| getProcessState | public String getProcessState() | - | - | 여신 신청의 전체 대화형 상태(Conversational State)로 관리되는 프로세스에서, 현재 진행 상태 값을 외부에 제공하기 위해 저장된 상태 문자열을 그대로 반환한다. 이를 통해 호출자는 초기화(INITIALIZED), 상세정보 설정(DETAILS_SET), 담보 추가(COLLATERAL_ADDED), 심사 요청(SCREENING_REQUESTED), 제출(SUBMITTED), 취소(CANCELLED) 등 현재 단계가 무엇인지 확인할 수 있다. 상태 값을 변경하거나 검증·전이를 수행하지 않고, 보관 중인 값의 조회만 수행한다. |
| getCustomerHome | private CustomerLocalHome getCustomerHome() throws NamingException | - | - | 여신 신청의 대화형 상태를 관리하는 세션 빈 구현체 내부에서, 고객 정보 엔티티에 접근하기 위한 로컬 홈 인터페이스를 획득하는 역할을 한다. J2EE 서비스 로케이터를 통해 로컬 홈을 JNDI로 조회하며, 조회에 사용되는 식별자는 JNDI_CUSTOMER_ENTITY 상수값이다. 조회 결과는 고객 엔티티 로컬 홈 타입으로 캐스팅되어 반환된다. JNDI 조회 과정에서 이름 해석 실패가 발생할 수 있으므로 NamingException을 호출자에게 전파한다. |
| isStateAtLeast | private boolean isStateAtLeast(String requiredState) | - | - | 여신 신청 프로세스를 대화형 상태로 관리하는 흐름에서, 현재 상태가 특정 요구 상태 이상으로 진행되었는지 판정한다. 현재 프로세스 상태 값이 없으면 진행 단계 비교 자체가 불가능하므로 즉시 false를 반환해 후속 단계 처리(예: 담보 추가, 심사 요청, 제출 등)를 차단한다. 현재 상태와 요구 상태를 각각 단계 비교가 가능한 정수 레벨로 환산한 뒤, 현재 레벨이 요구 레벨 이상(>=)이면 true를 반환한다. 이를 통해 'INITIALIZED'→'DETAILS_SET'→'COLLATERAL_ADDED'→'SCREENING_REQUESTED'→'SUBMITTED'처럼 단계가 누적되는 프로세스에서 최소 선행 조건 충족 여부를 일관되게 확인한다. |
| getStateLevel | private int getStateLevel(String state) | - | - | 여신 신청의 대화형 상태(Conversational State)로 관리되는 프로세스에서, 현재 상태 문자열을 진행 단계 비교가 가능한 정수 레벨로 환산한다. 상태가 'INITIALIZED'이면 1, 'DETAILS_SET'이면 2, 'COLLATERAL_ADDED'이면 3, 'SCREENING_REQUESTED'이면 4, 'SUBMITTED'이면 5로 매핑한다. 취소 상태인 'CANCELLED'는 예외적으로 -1을 반환해 정상 진행 단계와 구분한다. 위에 해당하지 않는 알 수 없는 상태 값은 0을 반환해 미정/초기값 성격으로 처리한다. |
| setSessionContext | public void setSessionContext(SessionContext ctx) | - | - | 이 구현체는 여신 신청의 대화형 상태를 관리하는 Stateful 세션 빈이며, 이후 프로세스 단계에서 컨테이너 자원에 접근하기 위한 기반 정보를 유지한다. 이 범위의 로직은 외부에서 전달된 세션 컨테이너 컨텍스트를 내부 보관 필드에 저장해, 후속 처리에서 트랜잭션/보안/롤백 등 컨테이너 기능을 사용할 수 있도록 준비한다. 별도의 검증, 분기, 예외 처리 없이 전달값을 그대로 보관하는 단순 설정 동작이다. |
| ejbCreate | public void ejbCreate() throws CreateException | - | - | 여신 신청의 초기화부터 제출까지를 대화형 상태로 관리하는 Stateful 세션 빈에서, 인스턴스 생성 시점에 내부 대화 상태를 초기 조건으로 되돌린다. 담보를 누적 관리하기 위한 담보 목록을 비어 있는 상태로 새로 준비해, 이전 대화에서 남아 있을 수 있는 담보 정보가 섞이지 않도록 한다. 또한 프로세스 진행 상태 값을 미설정(null)으로 초기화하여, 이후 단계에서 초기화·상세 설정·담보 추가·심사 요청·제출 같은 상태 전이가 새로 시작되도록 기반을 만든다. |
| ejbRemove | public void ejbRemove() | - | - | 여신 신청의 대화형 상태(Conversational State)를 유지하는 Stateful 세션 빈이 종료(제거)될 때, 남아 있는 상태 정보를 정리하기 위한 종료 처리이다. customerId, applicationId 같은 식별자와 collaterals(담보 목록) 참조를 모두 null로 초기화해 세션에 남아 있는 신청 진행 맥락을 끊는다. 또한 processState도 null로 설정하여 INITIALIZED, DETAILS_SET, COLLATERAL_ADDED, SCREENING_REQUESTED, SUBMITTED, CANCELLED 등 어떤 진행 상태도 더 이상 유지되지 않도록 한다. 결과적으로 빈 인스턴스가 제거되는 시점에 내부 필드 참조를 해제해 메모리/상태 누수를 방지하고 프로세스를 종료 상태로 정리한다. |
| ejbActivate | public void ejbActivate() | - | - | 이 코드는 여신 신청의 대화형 상태를 유지하는 Stateful 세션 빈의 생명주기 중, 패시베이션 이후 다시 활성화될 때 호출되는 콜백 지점을 제공한다. 활성화 시점에 복원/재초기화/검증 등의 처리를 넣을 수 있도록 정의되어 있으나, 현재 구현은 비어 있어 컨테이너 기본 동작 외에 추가로 수행하는 작업이 없다. 따라서 'INITIALIZED', 'DETAILS_SET', 'COLLATERAL_ADDED', 'SCREENING_REQUESTED', 'SUBMITTED', 'CANCELLED' 같은 상태값을 변경하거나 외부 리소스를 조회·갱신하지 않는다. |
| ejbPassivate | public void ejbPassivate() | - | - | 대화형 상태로 여신 신청 전 과정을 관리하는 상태 유지형 세션 빈에서, 인스턴스가 패시베이션(비활성화되어 저장)될 때 호출되는 생명주기 콜백을 제공한다. 현재 구현은 본문이 비어 있어, 패시베이션 시점에 대화 상태나 자원(예: 연결, 캐시 등)에 대해 정리·직렬화 준비 같은 추가 처리를 수행하지 않는다. 따라서 패시베이션 이벤트를 수신하되 시스템 동작이나 업무 상태(예: INITIALIZED, DETAILS_SET, COLLATERAL_ADDED, SCREENING_REQUESTED, SUBMITTED, CANCELLED)에 영향을 주지 않는다. |

#### 필드

| 이름 | 타입 | 수정자 | 요약 |
| --- | --- | --- | --- |
| serialVersionUID | long | - | 직렬화 가능한 상태ful 세션 빈 인스턴스의 직렬화/역직렬화 호환성을 보장하기 위한 고정 버전 식별자이며, 값은 1L로 설정된 클래스 수준의 상수이다. |
| STATE_INITIALIZED | String | - | 여신 신청 프로세스를 대화형 상태로 관리하는 세션 빈에서, 프로세스가 초기화된 상태를 나타내는 문자열 상수("INITIALIZED")를 정의한다. |
| STATE_DETAILS_SET | String | - | 여신 신청 프로세스를 대화형 상태로 관리하는 세션 빈에서, 상세정보가 설정된 상태를 나타내기 위한 상태 식별자 상수로 "DETAILS_SET" 값을 담는다. |
| STATE_COLLATERAL_ADDED | String | - | 여신 신청 프로세스를 대화형 상태로 관리하는 과정에서, 담보가 추가된 단계임을 나타내는 상태 식별자 상수(String)로 "COLLATERAL_ADDED" 값을 갖는다. |
| STATE_SCREENING_REQUESTED | String | - | 여신 신청 프로세스를 대화형 상태로 관리하는 과정에서, 심사 요청 단계에 진입했음을 나타내는 상태 식별자 상수이며 값은 "SCREENING_REQUESTED"이다. |
| STATE_SUBMITTED | String | - | 여신 신청 프로세스를 대화형 상태로 관리하는 세션 빈에서, 신청/프로세스가 최종 제출된 상태임을 나타내는 문자열 상수로 "SUBMITTED" 값을 가진다. |
| STATE_CANCELLED | String | - | 여신 프로세스를 대화형 상태로 관리하는 세션 빈에서, 신청 흐름의 상태가 취소되었음을 나타내는 상태 코드 상수("CANCELLED")를 정의한다. |
| ctx | SessionContext | - | 여신 신청 프로세스를 대화형 상태로 관리하는 Stateful 세션 빈에서, 컨테이너가 제공하는 세션 실행 환경(EJB SessionContext)을 보관해 트랜잭션/보안/호출 정보 접근 및 컨테이너 서비스 연동에 사용되는 컨텍스트 필드이다. |
| customerId | String | - | 여신(대출) 신청 프로세스를 대화형 상태로 관리하는 Stateful 세션 빈에서, 현재 처리 중인 고객을 식별하기 위한 고객 ID를 보관하는 상태값이다. |
| applicationId | String | - | 여신 신청 프로세스를 대화형 상태로 관리하는 세션 빈에서, 현재 처리 중인 여신 신청(애플리케이션)의 식별자(ID)를 보관하는 필드이다. |
| loanType | String | - | 여신 신청 전체 프로세스를 대화형 상태로 관리하는 세션 빈에서, 진행 중인 신청 건에 적용되는 대출(여신) 유형을 저장하는 문자열 상태값이다. |
| requestedAmount | BigDecimal | - | 여신 신청 프로세스 전반에서 사용자가 요청한 여신(대출) 금액을 BigDecimal로 보관하는 필드로, 초기화부터 심사 요청·제출까지 대화형 상태로 유지되는 신청 데이터의 핵심 금액 정보를 담는다. |
| term | int | - | 여신 신청 프로세스를 대화형 상태로 관리하는 과정에서, 대출(여신)의 기간(기간/만기 등)을 정수값으로 보관하는 필드이다. |
| purpose | String | - | 여신 신청 프로세스를 대화형 상태로 관리하는 동안, 해당 신청의 목적(용도)을 문자열로 보관하는 필드이다. |
| collaterals | List | - | 여신 신청 프로세스 진행 중 추가되거나 설정되는 담보 정보를 담보 목록 형태로 대화형 상태로 보관하는 필드이다. |
| processState | String | - | 여신 신청의 초기화부터 상세정보 설정, 담보 추가, 심사 요청, 제출까지 진행되는 전체 프로세스의 현재 진행 상태를 대화형(Conversational) 세션 범위에서 관리하기 위한 문자열 상태값을 저장한다. |

#### 구조 관계

| 방향 | 관계 | 대상 | 속성 |
| --- | --- | --- | --- |
| → | DEPENDENCY | CollateralDTO | source_member=requestScreening, usage=cast |
| → | DEPENDENCY | LoanApplicationDTO | source_member=getCurrentApplicationStatus, usage=return |
| → | DEPENDENCY | LoanApplicationDTO | source_member=submitAndGetResult, usage=return |
| → | DEPENDENCY | ScreeningResultDTO | source_member=requestScreening, usage=return |
| → | DEPENDENCY | CustomerLocalHome | source_member=getCustomerHome, usage=return |
| → | DEPENDENCY | CustomerLocalHome | source_member=initializeProcess, usage=local_var |
| → | DEPENDENCY | LoanApplicationException | source_member=setLoanDetails, usage=local_new |
| → | DEPENDENCY | LoanApplicationException | source_member=addCollateral, usage=local_new |
| → | DEPENDENCY | LoanApplicationException | source_member=cancelProcess, usage=return |
| → | DEPENDENCY | LoanApplicationException | source_member=submitAndGetResult, usage=local_new |
| → | DEPENDENCY | LoanScreeningException | source_member=requestScreening, usage=local_var |
| → | DEPENDENCY | LoanApplicationSession | source_member=cancelProcess, usage=local_var |
| → | DEPENDENCY | LoanApplicationSession | source_member=submitAndGetResult, usage=local_var |
| → | DEPENDENCY | LoanApplicationSessionHome | source_member=cancelProcess, usage=local_var |
| → | DEPENDENCY | LoanApplicationSessionHome | source_member=submitAndGetResult, usage=local_var |
| → | DEPENDENCY | LoanScreeningSession | source_member=requestScreening, usage=local_var |
| → | DEPENDENCY | LoanScreeningSessionHome | source_member=requestScreening, usage=cast |
| → | DEPENDENCY | LoanConstants | source_member=getCustomerHome, usage=local_var |
| → | DEPENDENCY | LoanConstants | source_member=cancelProcess, usage=field_call |
| → | DEPENDENCY | LoanConstants | source_member=submitAndGetResult, usage=local_var |
| → | DEPENDENCY | ServiceLocator | source_member=getCustomerHome, usage=local_var |
| → | DEPENDENCY | ServiceLocator | source_member=cancelProcess, usage=local_var |
| → | DEPENDENCY | ServiceLocator | source_member=submitAndGetResult, usage=local_var |
| → | DEPENDENCY | SessionContext | source_member=setSessionContext, usage=parameter |
| → | COMPOSITION | CollateralDTO | source_member=addCollateral |

#### 호출 관계

| 방향 | 대상 | 호출코드 |
| --- | --- | --- |
| → | CollateralDTO | - |
| → | LoanApplicationDTO | - |
| → | CustomerLocalHome | - |
| → | LoanApplicationSession | - |
| → | LoanApplicationSessionHome | - |
| → | LoanScreeningSession | - |
| → | LoanScreeningSessionHome | - |
| → | ServiceLocator | - |
| → | CustomerLocalHome | 57:             customerHome.findByPrimaryKey(customerId); |
| → | LoanProcessSessionBean | 56:             CustomerLocalHome customerHome = getCustomerHome(); |
| → | CollateralDTO | 103:         collateral.setCollateralType(collateralType); |
| → | CollateralDTO | 104:         collateral.setDescription(description); |
| → | CollateralDTO | 105:         collateral.setAppraisedValue(value); |
| → | CollateralDTO | 106:         collateral.setAppraisalDate(new Date(System.currentTimeMillis())); |
| → | CollateralDTO | 107:         collateral.setRegistrationStatus("PENDING"); |
| → | CollateralDTO | 139:                 c.setApplicationId(applicationId); |
| → | LoanApplicationDTO | 127:             appDto.setCustomerId(customerId); |
| → | LoanApplicationDTO | 129:             appDto.setRequestedAmount(requestedAmount); |
| → | LoanApplicationDTO | 128:             appDto.setLoanType(loanType); |
| → | LoanApplicationDTO | 131:             appDto.setLoanPurpose(purpose); |
| → | LoanApplicationDTO | 130:             appDto.setTerm(term); |
| → | LoanApplicationDTO | 132:             appDto.setInterestRate(new BigDecimal("0.05")); |
| → | LoanApplicationSession | 134:             LoanApplicationDTO created = appSession.createApplication(appDto); |
| → | LoanApplicationSession | 143:             appSession.submitApplication(applicationId); |
| → | LoanApplicationSession | 140:                 appSession.registerCollateral(c); |
| → | LoanApplicationSessionHome | 124:             LoanApplicationSession appSession = appSessionHome.create(); |
| → | LoanScreeningSession | 151:             ScreeningResultDTO result = screeningSession.performScreening(applicationId); |
| → | LoanScreeningSessionHome | 149:             LoanScreeningSession screeningSession = screeningHome.create(); |
| → | ServiceLocator | 120:             LoanApplicationSessionHome appSessionHome = (LoanApplicationSessionHome) 121:                     ServiceLocator.getInstance().getRemoteHome( 122:                             LoanCons |
| → | LoanApplicationSession | 177:             LoanApplicationDTO result = appSession.getApplication(applicationId); |
| → | LoanApplicationSessionHome | 175:             LoanApplicationSession appSession = appSessionHome.create(); |
| → | ServiceLocator | 171:             LoanApplicationSessionHome appSessionHome = (LoanApplicationSessionHome) 172:                     ServiceLocator.getInstance().getRemoteHome( 173:                             LoanCons |
| → | LoanApplicationSessionHome | 198:             LoanApplicationSession appSession = appSessionHome.create(); |
| → | ServiceLocator | 194:             LoanApplicationSessionHome appSessionHome = (LoanApplicationSessionHome) 195:                     ServiceLocator.getInstance().getRemoteHome( 196:                             LoanCons |
| → | LoanApplicationSession | 219:                 appSession.cancelApplication(applicationId); |
| → | LoanApplicationSessionHome | 218:                 LoanApplicationSession appSession = appSessionHome.create(); |
| → | ServiceLocator | 214:                 LoanApplicationSessionHome appSessionHome = (LoanApplicationSessionHome) 215:                         ServiceLocator.getInstance().getRemoteHome( 216:                              |
| → | LoanProcessSessionBean | 248:         int currentLevel = getStateLevel(processState); |

#### 데이터 접근

| 대상 | 관계 | 근거 | 신뢰도 |
| --- | --- | --- | --- |
| CUSTOMER | READS | - | - |
| CustomerLocal | REFER_TO | - | 1.0 |
| CustomerLocalHome | REFER_TO | - | 1.0 |
| LoanApplicationException | REFER_TO | - | 1.0 |
| ejb-jar.xml | REFER_TO | - | 0.9 |
| LoanApplicationException | REFER_TO | - | 1.0 |
| CollateralDTO | REFER_TO | - | 1.0 |
| LoanApplicationException | REFER_TO | - | 1.0 |
| CollateralDTO | REFER_TO | - | 1.0 |
| LoanApplicationDTO | REFER_TO | - | 1.0 |
| ScreeningResultDTO | REFER_TO | - | 1.0 |
| LoanScreeningException | REFER_TO | - | 1.0 |
| LoanApplicationSession | REFER_TO | - | 1.0 |
| LoanApplicationSessionHome | REFER_TO | - | 1.0 |
| LoanScreeningSession | REFER_TO | - | 1.0 |
| LoanScreeningSessionHome | REFER_TO | - | 1.0 |
| LoanConstants | REFER_TO | - | 1.0 |
| ServiceLocator | REFER_TO | - | 1.0 |
| ejb-jar.xml | REFER_TO | - | 1.0 |
| ejb-jar.xml | REFER_TO | - | 1.0 |
| LoanApplicationDTO | REFER_TO | - | 1.0 |
| LoanApplicationException | REFER_TO | - | 1.0 |
| LoanApplicationSession | REFER_TO | - | 1.0 |
| LoanApplicationSessionHome | REFER_TO | - | 1.0 |
| LoanConstants | REFER_TO | - | 1.0 |
| ServiceLocator | REFER_TO | - | 1.0 |
| ejb-jar.xml | REFER_TO | - | 1.0 |
| LoanApplicationDTO | REFER_TO | - | 1.0 |
| LoanApplicationException | REFER_TO | - | 1.0 |
| LoanApplicationSession | REFER_TO | - | 1.0 |
| LoanApplicationSessionHome | REFER_TO | - | 1.0 |
| LoanConstants | REFER_TO | - | 1.0 |
| ServiceLocator | REFER_TO | - | 1.0 |
| ejb-jar.xml | REFER_TO | - | 1.0 |
| LoanApplicationException | REFER_TO | - | 1.0 |
| LoanApplicationSession | REFER_TO | - | 1.0 |
| LoanApplicationSessionHome | REFER_TO | - | 1.0 |
| LoanConstants | REFER_TO | - | 1.0 |
| ServiceLocator | REFER_TO | - | 1.0 |
| ejb-jar.xml | REFER_TO | - | 1.0 |
| CUSTOMER | READS | - | - |
| CustomerLocal | REFER_TO | - | 1.0 |
| CustomerLocalHome | REFER_TO | - | 1.0 |
| LoanConstants | REFER_TO | - | 1.0 |
| ServiceLocator | REFER_TO | - | 1.0 |
| ejb-jar.xml | REFER_TO | - | 0.9 |

#### 요약 코드

```
없음
```

### LoanProcessSessionHome

#### 기본 정보

| 항목 | 값 |
| --- | --- |
| 이름 | LoanProcessSessionHome |
| 타입 | CLASS |
| FQN | com.banking.loan.session.LoanProcessSessionHome |
| 패키지 | com.banking.loan.session |
| 스테레오타입 | COMMAND |
| 파일 | - |
| 라인 | - |
| 토큰 | - |

#### 요약

> 이 클래스는 여신 프로세스를 대화형 상태로 처리하는 Stateful 세션 빈의 원격 홈 인터페이스로서, 원격 클라이언트가 해당 세션을 생성·획득하기 위한 진입점을 제공한다. 여신 신청 → 심사 → 제출로 이어지는 전체 업무 흐름을 동일한 세션 상태 맥락에서 단계적으로 진행할 수 있도록 새로운 프로세스 대화 상태를 시작하는 생성을 정의한다. 생성 과정에서 EJB 생성 실패는 생성 관련 예외로, 원격 통신 문제는 원격 호출 예외로 호출자에게 전달하도록 계약한다.

#### 메서드

| 이름 | 시그니처 | 반환타입 | 수정자 | 요약 |
| --- | --- | --- | --- | --- |
| create | LoanProcessSession create() throws CreateException, RemoteException | - | - | 이 인터페이스는 여신 신청부터 심사, 제출까지의 전체 프로세스를 대화형 상태로 관리하는 Stateful 세션 빈을 원격으로 생성·획득하기 위한 계약을 제공한다. 이 선언은 원격 클라이언트가 새로운 프로세스 대화 상태를 시작하기 위해 세션 인스턴스를 생성(또는 할당)받아, 이후 단계별 업무 진행을 동일한 상태 맥락에서 이어가도록 한다. 생성 과정에서 EJB 생성 실패 상황은 생성 관련 예외로, 원격 통신 계층의 문제는 원격 호출 예외로 호출자에게 전달하도록 정의한다. |

#### 필드

| 이름 | 타입 | 수정자 | 요약 |
| --- | --- | --- | --- |
| - | - | - | - |

#### 구조 관계

| 방향 | 관계 | 대상 | 속성 |
| --- | --- | --- | --- |
| → | DEPENDENCY | LoanProcessSession | source_member=create, usage=return |

#### 호출 관계

| 방향 | 대상 | 호출코드 |
| --- | --- | --- |
| - | - | - |

#### 데이터 접근

| 대상 | 관계 | 근거 | 신뢰도 |
| --- | --- | --- | --- |
| LoanProcessSession | REFER_TO | - | 1.0 |
| ejb-jar.xml | REFER_TO | - | 1.0 |

#### 요약 코드

```
없음
```

### LoanScreeningSession

#### 기본 정보

| 항목 | 값 |
| --- | --- |
| 이름 | LoanScreeningSession |
| 타입 | CLASS |
| FQN | com.banking.loan.session.LoanScreeningSession |
| 패키지 | com.banking.loan.session |
| 스테레오타입 | COMMAND/READMODEL |
| 파일 | - |
| 라인 | - |
| 토큰 | - |

#### 요약

> com.banking.loan.session.LoanScreeningSession은 여신 신청에 대한 신용심사 수행과 그 결과에 따른 승인/거절 처리를 원격으로 제공하는 여신 심사 세션 빈 리모트 컴포넌트 인터페이스이다. 여신 신청 식별자 또는 고객 식별자를 입력으로 받아 심사 결과 정보를 조회·반환하고, 심사 흐름에서 신청을 승인 또는 거절로 확정(심사 → 승인/거절)하는 업무를 담당한다. 승인 시에는 신청 식별자, 승인자 직원 식별자, 최종 승인금액, 최종 승인금리를 받아 반영하며, 거절 시에는 신청 식별자, 승인자 직원 식별자, 거절 사유를 받아 처리한다. 원격 호출 중 통신 문제는 원격 예외로, 심사 수행 불가나 업무 규칙 위반 등 도메인 사유는 여신 심사 관련 업무 예외로 호출자에게 전파하도록 계약되어 있다.

#### 메서드

| 이름 | 시그니처 | 반환타입 | 수정자 | 요약 |
| --- | --- | --- | --- | --- |
| performScreening | ScreeningResultDTO performScreening(String applicationId)             throws RemoteException, LoanScreeningException | - | - | 이 리모트 컴포넌트 인터페이스는 여신 신청에 대한 신용심사와 그에 따른 승인/거절 판단 업무를 처리하는 책임을 가진다. 이 작업은 입력으로 여신 신청을 식별하는 값을 받아 해당 신청 건에 대한 심사 결과 정보를 반환하도록 정의되어 있다. 원격 호출 과정에서 통신 계층 문제로 실패할 수 있어 원격 예외를 전파하며, 심사 수행 자체가 불가능하거나 업무 규칙 위반 등 도메인 사유가 발생하면 심사 예외를 전파하도록 계약이 명시되어 있다. |
| getCreditScreening | ScreeningResultDTO getCreditScreening(String customerId)             throws RemoteException, LoanScreeningException | - | - | 여신 신청에 대한 신용심사·승인·거절 업무를 처리하는 리모트 컴포넌트 인터페이스 맥락에서, 고객을 식별하는 값을 입력으로 받아 해당 고객의 신용심사 결과를 반환하는 조회 성격의 계약을 정의한다. 처리 결과는 심사 결과 정보를 담은 전용 전송 객체 형태로 제공되어, 호출 측이 심사 결과를 화면/업무 흐름에 활용할 수 있게 한다. 원격 호출 환경에서의 통신 오류는 원격 예외로 전달되며, 신용심사 업무 처리 중 발생 가능한 도메인 오류는 별도의 업무 예외로 구분해 호출자에게 전파한다. |
| approveApplication | void approveApplication(String applicationId, String approverEmployeeId,                             BigDecimal approvedAmount, BigDecimal approvedRate)             throws RemoteException, LoanScreeningException | - | - | 여신 신청에 대한 신용심사 업무 흐름에서, 특정 신청 건을 승인 상태로 확정하기 위한 원격 호출용 계약을 정의한다. 입력으로 신청 식별자, 승인 처리자(직원) 식별자, 최종 승인금액, 최종 승인금리를 받아 승인 결과를 반영하는 처리를 수행하도록 의도된다. 실행 중 원격 통신 문제는 원격 예외로, 심사/승인 규칙 위반이나 처리 실패는 여신 심사 관련 예외로 호출자에게 전달되도록 선언되어 있다. |
| rejectApplication | void rejectApplication(String applicationId, String approverEmployeeId, String reason)             throws RemoteException, LoanScreeningException | - | - | 이 원격 컴포넌트 인터페이스는 여신 신청에 대한 신용심사 흐름에서 승인/거절 같은 의사결정 처리를 제공하며, 이 범위는 그중 신청을 ‘거절’로 확정하는 작업을 정의한다. 입력으로 여신 신청을 특정하는 식별자, 거절 결정을 내리는 승인자 직원 식별자, 그리고 거절 사유를 받아 거절 처리가 가능하도록 한다. 원격 호출 환경에서의 통신 장애는 원격 예외로 전달되며, 심사 업무 규칙 위반이나 처리 실패는 심사 도메인 예외로 호출자에게 전달되도록 계약되어 있다. |

#### 필드

| 이름 | 타입 | 수정자 | 요약 |
| --- | --- | --- | --- |
| - | - | - | - |

#### 구조 관계

| 방향 | 관계 | 대상 | 속성 |
| --- | --- | --- | --- |
| → | DEPENDENCY | ScreeningResultDTO | source_member=getCreditScreening, usage=return |
| → | DEPENDENCY | ScreeningResultDTO | source_member=performScreening, usage=return |
| → | DEPENDENCY | LoanScreeningException | source_member=approveApplication, usage=parameter |
| → | DEPENDENCY | LoanScreeningException | source_member=rejectApplication, usage=local_var |
| ← | DEPENDENCY | LoanServlet | source_member=handleApproveApplication, usage=local_var |
| ← | DEPENDENCY | LoanServlet | source_member=handlePerformScreening, usage=local_var |
| ← | DEPENDENCY | LoanProcessSessionBean | source_member=requestScreening, usage=local_var |
| ← | DEPENDENCY | LoanScreeningSessionHome | source_member=create, usage=return |

#### 호출 관계

| 방향 | 대상 | 호출코드 |
| --- | --- | --- |
| ← | LoanServlet | - |
| ← | LoanProcessSessionBean | - |

#### 데이터 접근

| 대상 | 관계 | 근거 | 신뢰도 |
| --- | --- | --- | --- |
| ScreeningResultDTO | REFER_TO | - | 1.0 |
| LoanScreeningException | REFER_TO | - | 1.0 |
| ScreeningResultDTO | REFER_TO | - | 1.0 |
| LoanScreeningException | REFER_TO | - | 1.0 |
| LoanScreeningException | REFER_TO | - | 1.0 |
| LoanScreeningException | REFER_TO | - | 1.0 |

#### 요약 코드

```
없음
```

### LoanScreeningSessionBean

#### 기본 정보

| 항목 | 값 |
| --- | --- |
| 이름 | LoanScreeningSessionBean |
| 타입 | CLASS |
| FQN | com.banking.loan.session.LoanScreeningSessionBean |
| 패키지 | com.banking.loan.session |
| 스테레오타입 | COMMAND/READMODEL |
| 파일 | - |
| 라인 | - |
| 토큰 | - |

#### 요약

> com.banking.loan.session.LoanScreeningSessionBean은 여신 심사 Stateless 세션 빈으로, 신용평가·담보평가·DTI/LTV 분석을 통해 여신 승인 여부를 결정하며 신청 상태를 기존 상태 → STATUS_SCREENING으로 전이한 뒤 STATUS_SCREENING 또는 STATUS_SUBMITTED에서만 STATUS_APPROVED 또는 STATUS_REJECTED로 확정한다. 자동승인/거절 판단에는 기준값 creditScore<700, dtiRatio>=0.40(40%), ltvRatio>=0.80(80%)를 사용하고, 유효한 신용등급 정보가 없거나(creditScore=0, creditGrade="N/A", dtiRatio=0) 위 조건을 만족하면 실패 사유를 누적해 screeningResult="REJECTED"로 처리한다. 승인 시에는 approvedAmount/interestRate/screeningDate/approverEmployeeId/screeningResult="APPROVED"를 기록하고, 거절 시에는 approverEmployeeId/screeningDate/screeningResult="REJECTED"/remarks를 기록하며, LTV는 담보 목록 appraisedValue(감정가) 합계 대비 요청 금액 비율로 계산하되 담보가 없거나 예외 시 1(100%)을 반환해 보수적으로 심사 실패를 유도한다. 컨테이너 SessionContext를 ctx 필드로 주입받아 호출/트랜잭션/보안 맥락을 활용할 수 있고, 생명주기 훅인 패시베이션 시점 메서드는 비어 있어 추가 자원 정리나 상태 저장은 수행하지 않는다.

#### 메서드

| 이름 | 시그니처 | 반환타입 | 수정자 | 요약 |
| --- | --- | --- | --- | --- |
| performScreening | public ScreeningResultDTO performScreening(String applicationId) throws LoanScreeningException | - | - | 입력된 applicationId로 여신 신청 정보를 조회한 뒤 customerId, requestedAmount, loanType을 가져오고, customerId 기준으로 유효한 신용등급 정보가 있으면 creditScore/creditGrade/dtiRatio를 채우며 없으면 creditScore=0, creditGrade="N/A", dtiRatio=0으로 간주한다. 이어 담보 대비 신청금액 기반의 ltvRatio를 산출하고, 여신 신청의 status를 LoanConstants.STATUS_SCREENING으로 변경하여 심사 진행 상태를 확정한다. 자동승인 여부는 creditScore가 700 미만이거나 dtiRatio가 0.40 이상이거나 ltvRatio가 0.80 이상이거나 유효한 신용등급 정보가 없는 경우 실패로 판단하며, 각 실패 사유 문자열을 누적하고 모든 조건을 만족하면 "자동승인 요건 충족" 사유를 추가한다. 최종적으로 applicationId/customerId/creditScore/creditGrade/dtiRatio/ltvRatio/approved(자동승인 여부)/screeningDate(현재 시각)/reasons를 결과에 구성해 반환하고, 자동승인인 경우 approvedAmount=requestedAmount와 approvedRate=interestRate까지 함께 설정한다. 신청 조회(FinderException) 또는 JNDI 조회(NamingException) 실패 시 트랜잭션 롤백 표시를 하고, 예외를 여신 심사 예외로 감싸 applicationId 또는 오류 메시지와 함께 전파한다. |
| getCreditScreening | public ScreeningResultDTO getCreditScreening(String customerId) throws LoanScreeningException | - | - | 고객 식별자를 입력받아, 해당 고객의 유효한 신용등급 정보 중 가장 최근 평가 데이터를 조회한 뒤 신용심사 결과를 구성해 반환한다. 심사 결과에는 customerId(고객식별자)와 현재 시각 기준 screeningDate(심사일자)를 확정 반영하고, 신용등급 정보가 존재하면 creditScore(신용점수), creditGrade(신용등급), dtiRatio(DTI)를 채운다. 승인 여부는 신용점수가 700 미만이면 부적격 처리하고, DTI가 null이 아니면서 0.40 이상(>=)이면 부적격 처리하는 규칙으로 판단하며, 부적격 사유를 문자열 목록에 누적해 함께 반환한다. 유효한 신용등급 정보가 없으면 승인 여부를 false로 확정하고 '유효한 신용등급 정보 없음' 사유를 설정한다. 조회 과정에서 JNDI 조회 예외 또는 신용등급 조회 예외가 발생하면 각각의 상황을 메시지로 포함해 업무 예외로 감싸서 던진다. |
| approveApplication | public void approveApplication(String applicationId, String approverEmployeeId,                                     BigDecimal approvedAmount, BigDecimal approvedRate)             throws LoanScreeningException | - | - | 여신 심사를 수행하는 구성요소에서 특정 여신 신청 건을 승인 처리하기 위해, 신청 식별자로 신청 정보를 조회한 뒤 현재 status(상태)가 STATUS_SCREENING 또는 STATUS_SUBMITTED인 경우에만 후속 승인을 허용한다. status가 위 두 상태가 아니면 "승인 불가 상태" 예외를 발생시켜, SCREENING 또는 SUBMITTED 상태만 승인 가능하다는 업무 규칙을 강제한다. 승인 가능 상태라면 status를 STATUS_APPROVED로 확정 변경하고, approvedAmount(승인금액), interestRate(이자율), screeningDate(심사일자=현재 시각), approverEmployeeId(승인자 사원ID), screeningResult(심사결과="APPROVED")를 엔티티에 기록해 승인 결과를 확정한다. 조회 실패(FinderException) 또는 JNDI 조회 실패(NamingException)가 발생하면 트랜잭션을 롤백 전용으로 표시한 후, 원인 예외를 포함한 심사 예외로 감싸 재전파한다. |
| rejectApplication | public void rejectApplication(String applicationId, String approverEmployeeId, String reason)             throws LoanScreeningException | - | - | 여신 심사를 수행하는 Stateless 구성요소의 일부로, 특정 여신 신청 건을 '거절' 상태로 확정하고 심사 관련 정보를 기록한다. 먼저 신청 식별자로 여신 신청 정보를 조회한 뒤, 현재 status가 STATUS_SCREENING 또는 STATUS_SUBMITTED가 아니면 "SCREENING 또는 SUBMITTED 상태만 거절 가능" 규칙을 위반한 것으로 보고 예외를 발생시켜 거절 처리를 차단한다. 허용 상태인 경우 status를 STATUS_REJECTED로 변경하고, approverEmployeeId(승인자 사원ID), screeningDate(현재 시각), screeningResult를 "REJECTED", remarks에 거절 사유를 저장하여 심사 결과를 확정한다. 조회 실패(FinderException)나 JNDI 조회 실패(NamingException) 시에는 트랜잭션을 롤백 대상으로 표시한 뒤, 신청 식별자 또는 실패 메시지를 포함한 도메인 예외로 감싸서 상위로 전파한다. |
| getLoanApplicationHome | private LoanApplicationLocalHome getLoanApplicationHome() throws NamingException | - | - | 여신 심사 처리를 수행하는 구성요소에서, 여신 신청 정보를 다루는 로컬 홈 인터페이스를 획득하기 위한 조회성 유틸리티 동작을 제공한다. JNDI에 등록된 '여신 신청 엔티티'의 이름(상수로 정의된 JNDI 식별자)을 사용해 로컬 홈을 룩업하며, 룩업 결과를 해당 로컬 홈 타입으로 캐스팅해 반환한다. 룩업 과정에서 네이밍 조회 실패가 발생할 수 있으므로 NamingException을 호출자에게 전파한다. 이 동작은 객체/상태를 저장하거나 변경하지 않고, 이후 여신 신청 정보의 생성·조회 처리를 가능하게 하는 접근 경로만 마련한다. |
| getCreditRatingHome | private CreditRatingLocalHome getCreditRatingHome() throws NamingException | - | - | 여신 심사를 수행하는 구성 요소에서, 신용등급 정보를 다루는 BMP 엔티티에 접근하기 위한 로컬 홈 참조를 획득하는 역할을 한다. 서비스 로케이터의 캐시된 JNDI 룩업 기능을 사용해 'JNDI_CREDIT_RATING_ENTITY'로 지정된 엔티티의 로컬 홈을 조회하여 반환한다. 조회 결과는 로컬 홈 타입으로 명시적으로 변환되어 이후 신용등급 생성/조회 같은 엔티티 접근의 진입점으로 사용될 수 있다. JNDI 이름 해석에 실패할 수 있으므로 NamingException을 호출자에게 전달한다. |
| findLatestValidCreditRating | private CreditRatingLocal findLatestValidCreditRating(String customerId)             throws NamingException, FinderException | - | - | 여신 심사 과정에서 고객 식별자를 기준으로 신용등급 정보를 조회한 뒤, 유효 여부(isValid)가 참인 항목만을 대상으로 가장 최근 평가일자(ratingDate)를 가진 항목 1건을 선별해 반환한다. 먼저 신용등급 로컬 홈을 통해 고객별 신용등급 목록을 조회하고, 목록을 순회하면서 유효한 항목을 후보로 삼는다. 후보 간 우선순위는 ratingDate가 null이 아닌 경우에만 비교하며, 현재 후보의 ratingDate가 기존 후보의 ratingDate보다 이후(after)일 때 최신 후보로 교체한다. 조회/탐색 과정에서 이름 해석 실패나 엔티티 조회 실패가 발생할 수 있어 NamingException, FinderException을 호출자에게 그대로 전달한다. |
| calculateLtvRatio | private BigDecimal calculateLtvRatio(String applicationId, BigDecimal requestedAmount)             throws NamingException | - | - | 여신 승인 여부를 심사하는 과정에서, 특정 신청 건의 담보 가치 대비 요청 금액의 LTV(담보인정비율)를 산출하기 위한 값(비율)을 계산한다. 신청 식별자로 담보 목록을 조회한 뒤, 담보가 없거나 조회 결과가 비어 있으면 담보가 전혀 없다고 간주하여 비율을 1(100%)로 반환한다. 담보가 존재하면 각 담보의 appraisedValue(감정가) 중 null이 아닌 값만 합산해 총 담보 가치를 만들고, 요청 금액과 총 담보 가치로 LTV를 계산해 반환한다. 조회/계산 중 어떤 예외가 발생하더라도 심사 실패 방향으로 안전하게 처리하기 위해 동일하게 1(100%)을 반환한다. |
| setSessionContext | public void setSessionContext(SessionContext ctx) | - | - | 이 클래스는 신용평가·담보평가·DTI/LTV 분석을 통해 여신 승인 여부를 심사하는 무상태 세션 빈 구현체이며, 컨테이너가 제공하는 실행 환경 정보를 내부에 보관할 수 있도록 준비한다. 외부에서 전달받은 세션 실행 컨텍스트를 클래스의 내부 참조에 주입해 이후 트랜잭션/보안/롤백 등 컨테이너 기능을 사용할 수 있는 기반을 만든다. 별도의 검증·조건 분기나 다른 연산 없이 전달된 컨텍스트를 그대로 내부 상태로 설정하는 단순 설정 동작이다. |
| ejbCreate | public void ejbCreate() throws CreateException | - | - | 여신 심사 관련 Stateless 세션 빈의 생성 시점에 호출되는 생명주기 초기화 훅을 제공하지만, 본문이 비어 있어 별도의 초기화 작업을 수행하지 않는다. 따라서 신용평가/담보평가/DTI·LTV 분석과 같은 심사 규칙(예: 700점, DTI 0.40, LTV 0.80) 적용이나 데이터 접근은 이 구간에서 발생하지 않는다. 컨테이너가 생성 절차를 진행할 수 있도록 생성 예외만 선언하고, 내부 상태 설정이나 외부 자원 참조 없이 종료된다. |
| ejbRemove | public void ejbRemove() | - | - | 이 구성요소는 신용평가, 담보평가, DTI/LTV 분석을 통해 여신 승인 여부를 심사하는 무상태 세션 빈 구현체이며, 여기서는 인스턴스 제거 시점에 호출되는 생명주기 훅을 제공한다. 구현 내용이 비어 있어 제거 과정에서 추가적인 정리 작업(리소스 해제, 컨텍스트 정리, 상태 기록 등)을 수행하지 않는다. 따라서 상위에서 보유한 세션 컨텍스트나 자동 승인 기준값(신용점수 700, DTI 0.40, LTV 0.80)과도 상호작용하지 않으며, 외부 시스템/DB에 대한 호출이나 데이터 변경도 발생하지 않는다. |
| ejbActivate | public void ejbActivate() | - | - | 여신 승인 여부를 심사하는 세션 빈 구현체에서, 인스턴스가 비활성화 상태에서 다시 활성화될 때 호출되는 생명주기 콜백 지점을 제공한다. 그러나 본 범위에서는 활성화 시점에 수행할 초기화, 자원 재연결, 상태 복구 로직이 구현되어 있지 않아 아무 작업도 수행하지 않고 즉시 종료된다. 그 결과 활성화 이벤트가 발생하더라도 심사 기준(예: 700점, DTI 0.40, LTV 0.80) 적용이나 컨텍스트(SessionContext) 활용 등과 같은 도메인 동작에는 영향을 주지 않는다. |
| ejbPassivate | public void ejbPassivate() | - | - | 여신 심사 기능을 제공하는 Stateless 세션 빈의 생명주기 단계 중, 패시베이션 시점에 호출되는 훅을 제공한다. 그러나 본문이 비어 있어 패시베이션 시점에 수행되는 추가 작업(자원 정리, 상태 저장, 캐시 비우기 등)은 없다. 따라서 여신 승인 판단(신용평가, 담보평가, DTI/LTV 분석)과 관련된 규칙 적용이나 데이터 변경/조회는 이 범위에서 발생하지 않는다. |

#### 필드

| 이름 | 타입 | 수정자 | 요약 |
| --- | --- | --- | --- |
| serialVersionUID | long | - | 직렬화 가능한 여신 심사 Stateless 세션 빈 구현체에서 클래스 버전 호환성을 관리하기 위한 직렬화 식별자이며, 값은 1L로 고정된 상수이다. |
| AUTO_APPROVE_CREDIT_SCORE | int | - | 여신 심사에서 자동 승인 여부를 판단하기 위한 신용평가 점수 기준값(700점)을 정의한 정적 상수이다. |
| AUTO_APPROVE_DTI_LIMIT | BigDecimal | - | 여신 심사 과정에서 총부채상환비율(DTI)이 이 값(0.40, 즉 40%) 이하이면 자동 승인 판단에 사용할 기준 한도를 나타내는 상수입니다. |
| AUTO_APPROVE_LTV_LIMIT | BigDecimal | - | 여신 심사에서 담보대출비율(LTV)이 자동 승인될 수 있는 상한 기준값을 나타내는 상수로, 0.80(80%)를 임계치로 사용한다. |
| ctx | SessionContext | - | 여신 심사 처리를 수행하는 Stateless 세션 빈에서 EJB 컨테이너가 제공하는 세션 컨텍스트를 보관하는 필드로, 실행 중인 호출/트랜잭션/보안 등의 컨테이너 정보를 조회하거나 관리하는 데 사용된다. |

#### 구조 관계

| 방향 | 관계 | 대상 | 속성 |
| --- | --- | --- | --- |
| → | ASSOCIATION | SessionContext | source_member=setSessionContext |
| → | DEPENDENCY | ScreeningResultDTO | source_member=getCreditScreening, usage=return |
| → | DEPENDENCY | CollateralLocal | source_member=calculateLtvRatio, usage=cast |
| → | DEPENDENCY | CollateralLocalHome | source_member=calculateLtvRatio, usage=local_var |
| → | DEPENDENCY | CreditRatingLocal | source_member=findLatestValidCreditRating, usage=return |
| → | DEPENDENCY | CreditRatingLocal | source_member=getCreditScreening, usage=local_var |
| → | DEPENDENCY | CreditRatingLocalHome | source_member=getCreditRatingHome, usage=return |
| → | DEPENDENCY | CreditRatingLocalHome | source_member=findLatestValidCreditRating, usage=local_var |
| → | DEPENDENCY | LoanApplicationLocal | source_member=rejectApplication, usage=local_var |
| → | DEPENDENCY | LoanApplicationLocal | source_member=performScreening, usage=local_var |
| → | DEPENDENCY | LoanApplicationLocalHome | source_member=rejectApplication, usage=local_var |
| → | DEPENDENCY | LoanApplicationLocalHome | source_member=performScreening, usage=local_var |
| → | DEPENDENCY | LoanApplicationLocalHome | source_member=getLoanApplicationHome, usage=return |
| → | DEPENDENCY | LoanScreeningException | source_member=rejectApplication, usage=local_new |
| → | DEPENDENCY | LoanScreeningException | source_member=getCreditScreening, usage=local_new |
| → | DEPENDENCY | InterestCalculator | source_member=calculateLtvRatio, usage=field_call |
| → | DEPENDENCY | LoanConstants | source_member=getCreditRatingHome, usage=local_var |
| → | DEPENDENCY | LoanConstants | source_member=getLoanApplicationHome, usage=local_var |
| → | DEPENDENCY | LoanConstants | source_member=calculateLtvRatio, usage=field_call |
| → | DEPENDENCY | LoanConstants | source_member=rejectApplication, usage=local_var |
| → | DEPENDENCY | LoanConstants | source_member=performScreening, usage=local_var |
| → | DEPENDENCY | ServiceLocator | source_member=getCreditRatingHome, usage=local_var |
| → | DEPENDENCY | ServiceLocator | source_member=getLoanApplicationHome, usage=local_var |
| → | DEPENDENCY | ServiceLocator | source_member=calculateLtvRatio, usage=field_call |
| → | DEPENDENCY | SessionContext | source_member=setSessionContext, usage=parameter |

#### 호출 관계

| 방향 | 대상 | 호출코드 |
| --- | --- | --- |
| → | ScreeningResultDTO | - |
| → | CollateralLocal | - |
| → | CollateralLocalHome | - |
| → | CreditRatingLocal | - |
| → | CreditRatingLocalHome | - |
| → | LoanApplicationLocal | - |
| → | LoanApplicationLocalHome | - |
| → | ServiceLocator | - |
| → | SessionContext | - |
| → | ScreeningResultDTO | 92:             result.setApplicationId(applicationId); |
| → | ScreeningResultDTO | 93:             result.setCustomerId(customerId); |
| → | ScreeningResultDTO | 94:             result.setCreditScore(creditScore); |
| → | ScreeningResultDTO | 95:             result.setCreditGrade(creditGrade); |
| → | ScreeningResultDTO | 96:             result.setDtiRatio(dtiRatio); |
| → | ScreeningResultDTO | 97:             result.setLtvRatio(ltvRatio); |
| → | ScreeningResultDTO | 98:             result.setApproved(autoApproved); |
| → | ScreeningResultDTO | 103:                 result.setApprovedAmount(requestedAmount); |
| → | ScreeningResultDTO | 99:             result.setScreeningDate(new Date(System.currentTimeMillis())); |
| → | ScreeningResultDTO | 100:             result.setReasons(reasons); |
| → | LoanApplicationLocal | 45:             String customerId = application.getCustomerId(); |
| → | LoanApplicationLocal | 46:             BigDecimal requestedAmount = application.getRequestedAmount(); |
| → | LoanApplicationLocal | 47:             String loanType = application.getLoanType(); |
| → | LoanApplicationLocal | 104:                 result.setApprovedRate(application.getInterestRate()); |
| → | LoanApplicationLocal | 62:             application.setStatus(LoanConstants.STATUS_SCREENING); |
| → | LoanApplicationLocalHome | 43:             LoanApplicationLocal application = appHome.findByPrimaryKey(applicationId); |
| → | LoanScreeningSessionBean | 42:             LoanApplicationLocalHome appHome = getLoanApplicationHome(); |
| → | LoanScreeningSessionBean | 49:             CreditRatingLocal creditRating = findLatestValidCreditRating(customerId); |
| → | LoanScreeningSessionBean | 60:             BigDecimal ltvRatio = calculateLtvRatio(applicationId, requestedAmount); |
| → | SessionContext | 109:             ctx.setRollbackOnly(); |
| → | ScreeningResultDTO | 122:             result.setCustomerId(customerId); |
| → | ScreeningResultDTO | 143:                 result.setApproved(eligible); |
| → | ScreeningResultDTO | 123:             result.setScreeningDate(new Date(System.currentTimeMillis())); |
| → | ScreeningResultDTO | 144:                 result.setReasons(reasons); |
| → | CreditRatingLocal | 126:                 result.setCreditScore(creditRating.getCreditScore()); |
| → | CreditRatingLocal | 127:                 result.setCreditGrade(creditRating.getCreditGrade()); |
| → | CreditRatingLocal | 128:                 result.setDtiRatio(creditRating.getDti()); |
| → | LoanScreeningSessionBean | 119:             CreditRatingLocal creditRating = findLatestValidCreditRating(customerId); |
| → | LoanApplicationLocal | 176:             application.setInterestRate(approvedRate); |
| → | LoanApplicationLocal | 167:             String currentStatus = application.getStatus(); |
| → | LoanApplicationLocal | 174:             application.setStatus(LoanConstants.STATUS_APPROVED); |
| → | LoanApplicationLocal | 179:             application.setScreeningResult("APPROVED"); |
| → | LoanApplicationLocal | 177:             application.setScreeningDate(new Date(System.currentTimeMillis())); |
| → | LoanApplicationLocal | 175:             application.setApprovedAmount(approvedAmount); |
| → | LoanApplicationLocal | 178:             application.setApproverEmployeeId(approverEmployeeId); |
| → | LoanApplicationLocalHome | 165:             LoanApplicationLocal application = home.findByPrimaryKey(applicationId); |
| → | LoanScreeningSessionBean | 164:             LoanApplicationLocalHome home = getLoanApplicationHome(); |
| → | LoanApplicationLocal | 195:             String currentStatus = application.getStatus(); |
| → | LoanApplicationLocal | 202:             application.setStatus(LoanConstants.STATUS_REJECTED); |
| → | LoanApplicationLocal | 205:             application.setScreeningResult("REJECTED"); |
| → | LoanApplicationLocal | 204:             application.setScreeningDate(new Date(System.currentTimeMillis())); |
| → | LoanApplicationLocal | 203:             application.setApproverEmployeeId(approverEmployeeId); |
| → | LoanApplicationLocal | 206:             application.setRemarks(reason); |
| → | LoanApplicationLocalHome | 193:             LoanApplicationLocal application = home.findByPrimaryKey(applicationId); |
| → | LoanScreeningSessionBean | 192:             LoanApplicationLocalHome home = getLoanApplicationHome(); |
| → | CreditRatingLocalHome | 234:         Collection ratings = crHome.findByCustomerId(customerId); |
| → | LoanScreeningSessionBean | 233:         CreditRatingLocalHome crHome = getCreditRatingHome(); |
| → | CollateralLocal | 273:                 BigDecimal value = collateral.getAppraisedValue(); |
| → | CollateralLocalHome | 262:             Collection collaterals = collateralHome.findByApplicationId(applicationId); |
| → | ServiceLocator | 258:             com.banking.loan.entity.CollateralLocalHome collateralHome = 259:                     (com.banking.loan.entity.CollateralLocalHome) ServiceLocator.getInstance() 260:                   |

#### 데이터 접근

| 대상 | 관계 | 근거 | 신뢰도 |
| --- | --- | --- | --- |
| LOAN_APPLICATION | WRITES | - | - |
| CREDIT_RATING_ENTITY | READS | - | - |
| LOAN_APPLICATION | READS | - | - |
| ScreeningResultDTO | REFER_TO | - | 1.0 |
| CreditRatingLocal | REFER_TO | - | 1.0 |
| LoanApplicationLocal | REFER_TO | - | 1.0 |
| LoanApplicationLocalHome | REFER_TO | - | 1.0 |
| LoanScreeningException | REFER_TO | - | 1.0 |
| LoanConstants | REFER_TO | - | 1.0 |
| ejb-jar.xml | REFER_TO | - | 0.9 |
| ejb-jar.xml | REFER_TO | - | 0.9 |
| CREDIT_RATING_ENTITY | READS | - | - |
| ScreeningResultDTO | REFER_TO | - | 1.0 |
| CreditRatingLocal | REFER_TO | - | 1.0 |
| LoanScreeningException | REFER_TO | - | 1.0 |
| ejb-jar.xml | REFER_TO | - | 0.9 |
| LOAN_APPLICATION | WRITES | - | - |
| LOAN_APPLICATION | READS | - | - |
| LoanApplicationLocal | REFER_TO | - | 1.0 |
| LoanApplicationLocalHome | REFER_TO | - | 1.0 |
| LoanScreeningException | REFER_TO | - | 1.0 |
| LoanConstants | REFER_TO | - | 1.0 |
| ejb-jar.xml | REFER_TO | - | 0.9 |
| LOAN_APPLICATION | WRITES | - | - |
| LOAN_APPLICATION | READS | - | - |
| LoanApplicationLocal | REFER_TO | - | 1.0 |
| LoanApplicationLocalHome | REFER_TO | - | 1.0 |
| LoanScreeningException | REFER_TO | - | 1.0 |
| LoanConstants | REFER_TO | - | 1.0 |
| ejb-jar.xml | REFER_TO | - | 0.9 |
| LOAN_APPLICATION | READS | - | - |
| LoanApplicationLocal | REFER_TO | - | 1.0 |
| LoanApplicationLocalHome | REFER_TO | - | 1.0 |
| LoanConstants | REFER_TO | - | 1.0 |
| ServiceLocator | REFER_TO | - | 1.0 |
| ejb-jar.xml | REFER_TO | - | 0.9 |
| CREDIT_RATING_ENTITY | READS | - | - |
| CreditRatingLocal | REFER_TO | - | 1.0 |
| CreditRatingLocalHome | REFER_TO | - | 1.0 |
| LoanConstants | REFER_TO | - | 1.0 |
| ServiceLocator | REFER_TO | - | 1.0 |
| ejb-jar.xml | REFER_TO | - | 0.9 |
| CREDIT_RATING_ENTITY | READS | - | - |
| CreditRatingLocal | REFER_TO | - | 1.0 |
| CreditRatingLocalHome | REFER_TO | - | 1.0 |
| ejb-jar.xml | REFER_TO | - | 0.9 |
| COLLATERAL | READS | - | - |
| CollateralLocal | REFER_TO | - | 1.0 |
| CollateralLocalHome | REFER_TO | - | 1.0 |
| InterestCalculator | REFER_TO | - | 1.0 |
| LoanConstants | REFER_TO | - | 1.0 |
| ServiceLocator | REFER_TO | - | 1.0 |
| ejb-jar.xml | REFER_TO | - | 0.9 |

#### 요약 코드

```
없음
```

### LoanScreeningSessionHome

#### 기본 정보

| 항목 | 값 |
| --- | --- |
| 이름 | LoanScreeningSessionHome |
| 타입 | CLASS |
| FQN | com.banking.loan.session.LoanScreeningSessionHome |
| 패키지 | com.banking.loan.session |
| 스테레오타입 | COMMAND |
| 파일 | - |
| 라인 | - |
| 토큰 | - |

#### 요약

> 이 클래스는 여신 신청에 대한 신용심사, 승인, 거절 업무를 수행하는 원격 세션 빈에 접근하기 위한 리모트 홈 인터페이스이다. 클라이언트가 원격 세션 인스턴스를 생성(획득)하는 진입점인 create를 제공하며, 이후 심사 관련 기능 호출의 기반을 마련한다. 생성이 실패하면 CreateException을, 원격 통신 문제가 발생하면 RemoteException을 호출자에게 전달하도록 계약을 정의한다.

#### 메서드

| 이름 | 시그니처 | 반환타입 | 수정자 | 요약 |
| --- | --- | --- | --- | --- |
| create | LoanScreeningSession create() throws CreateException, RemoteException | - | - | 이 인터페이스는 여신 신청에 대한 신용심사, 승인, 거절 업무를 처리하는 원격 세션 컴포넌트에 접근하기 위한 홈 인터페이스 역할을 한다. 이 선언은 클라이언트가 원격 세션 인스턴스를 생성(획득)하여 이후 심사 관련 기능을 호출할 수 있도록 생성 요청 진입점을 제공한다. 생성 과정에서 인스턴스 생성 자체가 실패하면 CreateException을, 원격 통신 과정에 문제가 생기면 RemoteException을 호출자에게 전달하도록 계약을 정의한다. |

#### 필드

| 이름 | 타입 | 수정자 | 요약 |
| --- | --- | --- | --- |
| - | - | - | - |

#### 구조 관계

| 방향 | 관계 | 대상 | 속성 |
| --- | --- | --- | --- |
| → | DEPENDENCY | LoanScreeningSession | source_member=create, usage=return |
| ← | ASSOCIATION | LoanServlet | source_member=init |
| ← | ASSOCIATION | LoanServlet | source_member=handlePerformScreening |
| ← | DEPENDENCY | LoanProcessSessionBean | source_member=requestScreening, usage=cast |

#### 호출 관계

| 방향 | 대상 | 호출코드 |
| --- | --- | --- |
| ← | LoanServlet | - |
| ← | LoanProcessSessionBean | - |

#### 데이터 접근

| 대상 | 관계 | 근거 | 신뢰도 |
| --- | --- | --- | --- |
| LoanScreeningSession | REFER_TO | - | 1.0 |
| ejb-jar.xml | REFER_TO | - | 1.0 |

#### 요약 코드

```
없음
```

### InterestCalculator

#### 기본 정보

| 항목 | 값 |
| --- | --- |
| 이름 | InterestCalculator |
| 타입 | CLASS |
| FQN | com.banking.loan.util.InterestCalculator |
| 패키지 | com.banking.loan.util |
| 스테레오타입 | READMODEL |
| 파일 | - |
| 라인 | - |
| 토큰 | - |

#### 요약

> com.banking.loan.util.InterestCalculator는 이자 및 상환금액을 계산하는 유틸리티로, 모든 계산을 BigDecimal로 수행하고 최종 결과는 scale 2(SCALE=2)에서 ROUND_HALF_UP 반올림을 적용하며, 중간 계산 정밀도는 CALC_SCALE=10으로 유지한다. 원금/잔액/연이율/연체금액/penalty 이율/연소득/총 연간 부채상환액/담보가치 등이 null이거나 개월 수·일수·연체일수가 0 이하(<= 0)거나 연소득·담보가치가 0과 같으면(== 0) 계산을 진행하지 않고 0을 반환해 0으로 나눔 등 비정상 입력을 차단한다. 연이율이 0(== 0)일 때는 이자 없이 원금을 개월 수로 나눈 월 상환금을 반환하고, 0이 아니면 연이율을 12(TWELVE)로 나눠 월이율을 만든 뒤 원리금 균등/원금 균등 및 단순·연체 이자를 (1년=365일, DAYS_IN_YEAR) 기준으로 산출하며, 퍼센트 변환과 비율 계산에는 100(HUNDRED)을 사용한다. 또한 부채상환비율(DTI=총 연간 부채상환액÷연소득)과 담보인정비율(LTV=대출금액÷담보가치)을 소수점 2자리에서 반올림해 반환하고, 상환 공식에 필요한 거듭제곱은 반복 곱셈으로 base^exponent를 계산한다.

#### 메서드

| 이름 | 시그니처 | 반환타입 | 수정자 | 요약 |
| --- | --- | --- | --- | --- |
| calculateMonthlyPayment | public static BigDecimal calculateMonthlyPayment(BigDecimal principal,                                                       BigDecimal annualRate,                                                       int termMonths) | - | - | 이 코드는 이자 및 상환금액 계산을 위한 정밀 계산 규칙(소수점 2자리, ROUND_HALF_UP)을 전제로, 원금·연이율·개월 수로 월 상환금을 산출한다. 원금 또는 연이율이 null이거나 개월 수가 0 이하(<= 0)이면 계산을 진행하지 않고 0을 반환해 비정상 입력을 차단한다. 연이율이 0과 같으면(== 0) 이자 없이 원금을 개월 수로 나눈 값을 소수점 2자리로 반올림해 반환한다. 연이율이 0이 아니면 연이율을 12로 나눠 월이율을 소수점 10자리로 계산하고, (1+월이율)^개월 수를 구한 뒤 원금*월이율*(1+월이율)^n / ((1+월이율)^n - 1) 공식을 적용하여 최종 결과를 소수점 2자리로 반환한다. |
| calculateEqualPrincipalPayment | public static BigDecimal calculateEqualPrincipalPayment(BigDecimal principal,                                                              BigDecimal annualRate,                                                              int termMonths,                                                              int currentMonth) | - | - | 이자 및 상환금액을 소수점 정밀 계산으로 산출하는 계산 로직의 일부로, 원금 균등 방식에서 해당 월의 납입액(원금+이자)을 계산한다. 원금 또는 연이율이 null이거나, 전체 기간(개월) <= 0 또는 현재 회차(개월) <= 0이면 계산 불가로 보고 0을 반환한다. 매월 상환 원금은 (원금 ÷ 전체 기간)을 소수점 2자리에서 반올림(ROUND_HALF_UP)으로 산출하고, 월 이자율은 (연이율 ÷ 12)을 소수점 10자리에서 반올림(ROUND_HALF_UP)으로 산출한다. 이미 납입한 회차(현재 회차-1)만큼의 원금을 차감해 남은 원금을 구한 뒤, 남은 원금×월 이자율로 해당 월 이자를 계산하고 이를 소수점 2자리 반올림(ROUND_HALF_UP) 처리하여 원금 부분과 합산해 반환한다. |
| calculateInterest | public static BigDecimal calculateInterest(BigDecimal balance,                                                 BigDecimal annualRate,                                                 int days) | - | - | 이 클래스는 이자 및 상환금액 계산을 BigDecimal 기반으로 수행하며, 이 구간은 잔액·연이율·일수를 입력받아 단순 이자를 산출한다. 잔액 또는 연이율이 null이거나 일수가 0 이하(<= 0)이면 계산을 진행하지 않고 0을 반환해 잘못된 입력에 대한 안전한 기본값을 제공한다. 유효한 경우 잔액에 연이율과 일수 값을 곱한 뒤, 1년 일수 365로 나누어 일수 비례 이자를 계산한다. 나눗셈 결과는 소수점 2자리(scale 2)로 반올림(ROUND_HALF_UP)하여 금액 표준 형식으로 맞춘 값을 반환한다. |
| calculatePenaltyInterest | public static BigDecimal calculatePenaltyInterest(BigDecimal delinquentAmount,                                                        BigDecimal penaltyRate,                                                        int delinquentDays) | - | - | 이 클래스는 이자 및 상환금액을 BigDecimal로 계산하며 소수점 2자리와 ROUND_HALF_UP 반올림 규칙을 적용하는 계산 로직을 제공하고, 이 범위의 코드는 연체에 따른 페널티 이자를 산출한다. 연체금액 또는 페널티 이율이 null이거나 연체일수가 0 이하이면 계산이 무의미하므로 0을 반환한다. 유효한 입력이면 연체금액 × 페널티 이율 × 연체일수로 연체기간 동안의 누적 이자 성격의 값을 만든 뒤, 1년을 365일로 보고 365로 나눠 일수 비례 이자액으로 환산한다. 나눗셈 결과는 소수점 2자리(SCALE=2)로 맞추고 ROUND_HALF_UP 방식으로 반올림해 금액 단위로 확정한다. |
| calculateDTI | public static BigDecimal calculateDTI(BigDecimal annualIncome,                                            BigDecimal totalAnnualDebtPayment) | - | - | 이 클래스는 이자 및 상환금액 관련 계산을 BigDecimal 기반으로 수행하며, 기본적으로 소수점 2자리와 ROUND_HALF_UP 반올림 규칙을 적용한다. 이 범위의 로직은 연소득과 총 연간 부채상환액을 입력으로 받아, 부채상환액을 연소득으로 나눈 비율(부채상환비율)을 계산한다. 연소득이 null이거나 총 연간 부채상환액이 null이거나, 연소득이 0과 같으면(0으로 나누는 상황 포함) 계산을 진행하지 않고 0을 반환한다. 그 외에는 부채상환액 ÷ 연소득을 소수점 2자리로 계산하고 ROUND_HALF_UP 규칙으로 반올림한 값을 반환한다. |
| calculateLTV | public static BigDecimal calculateLTV(BigDecimal loanAmount,                                            BigDecimal collateralValue) | - | - | 이 클래스는 이자 및 상환금액 등 금융 계산을 BigDecimal로 처리하며 소수점 2자리와 반올림(ROUND_HALF_UP)을 적용하는 계산 규칙을 전제로 한다. 여기서는 대출금액과 담보가치를 입력으로 받아 담보가치 대비 대출금액 비율(LTV)을 계산한다. 대출금액이 null이거나 담보가치가 null이거나 담보가치가 0과 같으면(0으로 나눔 방지) 0을 반환한다. 그 외에는 대출금액을 담보가치로 나누고, 소수점 2자리(SCALE=2)에서 반올림(ROUND_HALF_UP)하여 비율 값을 반환한다. |
| pow | private static BigDecimal pow(BigDecimal base, int exponent) | - | - | 이 클래스는 이자 및 상환금액 계산을 위해 BigDecimal 기반의 정밀 계산을 수행하며, 이 구간은 입력된 값의 거듭제곱을 계산하는 보조 계산 로직을 담당한다. 지수(exponent)만큼 0부터 반복하면서 누적값에 입력값(base)을 계속 곱해 base^exponent 형태의 값을 만든다. 계산이 끝난 값은 소수점 10자리(CALC_SCALE=10)로 맞추고, 반올림 규칙은 ROUND_HALF_UP(ROUND_MODE)을 적용해 반환한다. 외부 저장소나 상태 변경 없이 순수하게 계산 결과만 산출한다. |

#### 필드

| 이름 | 타입 | 수정자 | 요약 |
| --- | --- | --- | --- |
| SCALE | int | - | 이자 및 상환금액 계산 시 BigDecimal 연산에 적용할 소수점 자리수(scale) 설정값으로, 모든 계산 결과를 소수점 2자리로 맞추기 위한 고정 상수(2)이다. |
| CALC_SCALE | int | - | 이 필드는 이자 및 상환금액을 BigDecimal로 계산할 때 사용할 소수점 스케일(정밀도)을 10으로 고정한 설정 상수이다. |
| ROUND_MODE | int | - | 이자 및 상환금액 계산 시 BigDecimal 반올림 규칙을 통일하기 위한 정적 상수로, 모든 계산에서 ROUND_HALF_UP(0.5 이상 올림) 모드를 사용하도록 설정한다. |
| TWELVE | BigDecimal | - | 이자 및 상환금액 계산에서 1년 12개월을 나타내는 값 12를 BigDecimal로 보관한 정적 상수로, 월 단위 환산(예: 연이율을 월이율로 변환) 등 계산에 사용된다. |
| HUNDRED | BigDecimal | - | 이자 및 상환금액 계산에서 퍼센트(%)를 소수로 변환하거나 비율 계산을 하기 위해 사용하는 기준값 100을 나타내는 BigDecimal 상수입니다. |
| DAYS_IN_YEAR | BigDecimal | - | 이자 및 상환금액 계산에서 1년의 기준 일수를 나타내는 상수로, 연 단위 이율을 일 단위로 환산하는 등 일수 기반 계산에 사용된다. 값은 365(BigDecimal)로 고정되어 있다. |

#### 구조 관계

| 방향 | 관계 | 대상 | 속성 |
| --- | --- | --- | --- |
| ← | DEPENDENCY | LoanExecutionSessionBean | source_member=executeLoan, usage=local_var |
| ← | DEPENDENCY | LoanLedgerSessionBean | source_member=calculateRemainingSchedule, usage=local_var |
| ← | DEPENDENCY | LoanScreeningSessionBean | source_member=calculateLtvRatio, usage=field_call |

#### 호출 관계

| 방향 | 대상 | 호출코드 |
| --- | --- | --- |
| → | InterestCalculator | 42:         BigDecimal power = pow(onePlusR, termMonths); |
| ← | LoanExecutionSessionBean | - |
| ← | LoanLedgerSessionBean | - |

#### 데이터 접근

| 대상 | 관계 | 근거 | 신뢰도 |
| --- | --- | --- | --- |
| - | - | - | - |

#### 요약 코드

```
없음
```

### LoanConstants

#### 기본 정보

| 항목 | 값 |
| --- | --- |
| 이름 | LoanConstants |
| 타입 | CLASS |
| FQN | com.banking.loan.util.LoanConstants |
| 패키지 | com.banking.loan.util |
| 스테레오타입 | READMODEL |
| 파일 | - |
| 라인 | - |
| 토큰 | - |

#### 요약

> com.banking.loan.util.LoanConstants는 대출 도메인 전반에서 사용하는 상태값·분류코드·임계치·비율 같은 기준 상수를 표준화해 비교/분기 및 계산 로직에서 재사용하도록 제공하는 유틸리티 클래스이다. 대출 신청 상태 흐름을 DRAFT → SUBMITTED → SCREENING → (APPROVED 또는 REJECTED) → EXECUTED로 정의하고 CANCELLED 등 부가 상태도 상수로 제공하며, 연체 등급은 delinquencyDays를 <=30(GRADE_1), <=60(GRADE_2), <=90(GRADE_3), <=120(GRADE_4), 121일 이상(GRADE_5)로 구간화한다. 또한 대출 유형별 최대 LTV를 일반 0.80(80%), 주택담보 0.70(70%), 사업 0.75(75%)로 고정하고 기본 페널티율 0.03(3%) 등 공통 계산 기준을 담는다. 아울러 JNDI 접두사 기반으로 대출 관련 세션/엔티티뿐 아니라 상환(Repayment) 엔티티, 신용등급(CreditRating) 엔티티, 그리고 데이터소스(LoanDS)까지 JNDI로 조회하기 위한 이름(lookup key) 상수를 일관되게 제공한다.

#### 메서드

| 이름 | 시그니처 | 반환타입 | 수정자 | 요약 |
| --- | --- | --- | --- | --- |
| getDelinquencyGrade | public static String getDelinquencyGrade(int delinquencyDays) | - | - | 입력된 연체일수(delinquencyDays)를 기준으로 미리 정의된 등급 구간(1~4등급 최대 연체일수 임계값)과 비교해 연체 등급 문자열을 결정해 반환한다. 연체일수가 1등급 최대 기준 이하(<=)이면 DELINQUENCY_GRADE_1을 반환하고, 그렇지 않으면 2등급/3등급/4등급 최대 기준 이하(<=)인지 순차적으로 검사해 각각 DELINQUENCY_GRADE_2, DELINQUENCY_GRADE_3, DELINQUENCY_GRADE_4를 반환한다. 어느 임계값에도 해당하지 않으면(즉 4등급 최대 기준 초과) 최종적으로 DELINQUENCY_GRADE_5를 반환한다. 외부 조회나 저장 없이, 연체일수에 대한 규칙 기반 분류 결과만 산출한다. |
| getMaxLtvByLoanType | public static BigDecimal getMaxLtvByLoanType(String loanType) | - | - | 대출 유형 값을 받아 해당 유형에서 허용되는 최대 LTV 값을 결정해 반환한다. 입력이 LOAN_TYPE_MORTGAGE와 같으면 MAX_LTV_MORTGAGE를 반환하고, LOAN_TYPE_BUSINESS와 같으면 MAX_LTV_BUSINESS를 반환한다. 그 외 모든 유형은 일반 케이스로 간주하여 MAX_LTV_GENERAL을 반환한다. 즉, 대출 유형별 최대 LTV 정책을 조건 분기로 고정 매핑해 조회성으로 제공한다. |

#### 필드

| 이름 | 타입 | 수정자 | 요약 |
| --- | --- | --- | --- |
| STATUS_DRAFT | String | - | 애플리케이션 상태들을 정의하는 상수 중 하나로, 초안 상태를 나타내는 문자열 값 "DRAFT"를 담아 상태 비교나 설정에 사용된다. |
| STATUS_SUBMITTED | String | - | 제출됨(SUBMITTED) 상태를 나타내는 문자열 상수로, 클래스 내에서 어떤 객체나 프로세스가 'SUBMITTED' 단계에 있음을 식별·비교하는 데 사용됩니다. |
| STATUS_SCREENING | String | - | "SCREENING" 상태를 나타내는 문자열 상수로, 클래스 내에서 진행 상태가 심사/검토(스크리닝) 단계임을 구분하거나 비교하는 데 사용된다. |
| STATUS_APPROVED | String | - | 승인됨(\"APPROVED\") 상태를 나타내는 문자열 상수로, 클래스 내에서 승인 상태를 비교하거나 설정할 때 기준값으로 사용된다. |
| STATUS_REJECTED | String | - | 거절됨(Rejected) 상태를 나타내는 문자열 상수로, 상태 필드나 상태 비교 로직에서 해당 값("REJECTED")을 일관되게 사용하기 위해 정의되어 있습니다. |
| STATUS_EXECUTED | String | - | 실행 완료 상태를 나타내는 문자열 상수로, 값은 "EXECUTED"이며 상태 비교나 상태 설정 등에 사용된다. |
| STATUS_CANCELLED | String | - | "CANCELLED"라는 문자열을 취소 상태로 표현하기 위한 정적 상수로, 클래스 내에서 상태값 비교나 설정 시 일관된 취소 상태 코드를 사용하도록 한다. |
| LEDGER_ACTIVE | String | - | 원장(Ledger)의 상태값들을 정의하는 상수 중 하나로, 원장이 활성 상태임을 나타내는 문자열 "ACTIVE"를 담는다. |
| LEDGER_COMPLETED | String | - | 원장(ledger) 처리 상태가 완료되었음을 나타내는 문자열 상수로, 상태값 "COMPLETED"를 표준화해 비교·설정에 사용된다. |
| LEDGER_DELINQUENT | String | - | 원장(ledger) 상태를 나타낼 때 사용되는 문자열 상수로, 연체 상태임을 의미하는 값 "DELINQUENT"를 담고 있습니다. |
| LEDGER_WRITTEN_OFF | String | - | 원장(ledger) 상태가 "WRITTEN_OFF"(상각/대손처리됨)임을 나타내는 문자열 상수로, 관련 로직에서 해당 상태를 비교·설정하는 기준값으로 사용됩니다. |
| DELINQUENCY_ACTIVE | String | - | 연체(Delinquency) 상태를 나타내는 상태값 상수로, 연체가 현재 활성(진행) 중인 경우를 의미하는 문자열 "ACTIVE"를 담는다. |
| DELINQUENCY_RESOLVED | String | - | 연체(Delinquency) 상태가 해결되었음을 나타내는 고정 문자열 상수로, 값은 "RESOLVED"입니다. |
| DELINQUENCY_COLLECTION | String | - | 연체(체납) 상태를 나타내는 문자열 상수로, 값은 "COLLECTION"이다. 클래스 내에서 연체 관련 구분값(예: 수금/추심 단계)을 일관되게 비교하거나 설정할 때 사용된다. |
| DELINQUENCY_WRITTEN_OFF | String | - | 연체(채무) 상태가 'WRITTEN_OFF'(상각 처리됨)임을 나타내기 위한 문자열 상수입니다. |
| LOAN_TYPE_GENERAL | String | - | 대출 유형(Loan Types)을 구분하기 위한 상수로, 일반 대출을 나타내는 문자열 값 "GENERAL"을 정의한다. |
| LOAN_TYPE_MORTGAGE | String | - | 대출 유형을 나타내는 문자열 상수로, 담보대출(모기지)을 의미하는 값 "MORTGAGE"를 정의한다. |
| LOAN_TYPE_BUSINESS | String | - | 대출 유형이 'BUSINESS'인 경우를 나타내는 문자열 상수로, 비즈니스(사업자) 대출을 식별하거나 분기 처리할 때 사용됩니다. |
| REPAYMENT_EQUAL_PRINCIPAL | String | - | 대출/상환 방식(Repayment Methods) 중 ‘원금균등상환’ 방식을 나타내는 문자열 상수로, 값은 "EQUAL_PRINCIPAL"이다. |
| REPAYMENT_EQUAL_INSTALLMENT | String | - | 원리금 균등분할 상환 방식을 나타내는 문자열 상수로, 값은 "EQUAL_INSTALLMENT"이며 클래스 내에서 상환 방식 식별/비교용 기준값으로 사용됩니다. |
| REPAYMENT_BULLET | String | - | 원금은 만기일에 일시 상환하는 ‘Bullet’ 방식의 상환 유형을 나타내는 문자열 상수(값: "BULLET")입니다. |
| CUSTOMER_INDIVIDUAL | String | - | 고객 유형(Customer Types) 중 개인 고객을 나타내는 문자열 상수로, 값은 "INDIVIDUAL"입니다. |
| CUSTOMER_CORPORATE | String | - | 고객 유형이 '기업(CORPORATE)'임을 나타내는 문자열 상수로, 코드 전반에서 기업 고객을 식별하거나 분기 처리할 때 기준 값으로 사용된다. |
| DELINQUENCY_GRADE_1 | String | - | 연체 등급(Delinquency Grades) 분류에서 1~30일 연체를 나타내는 등급 식별자 상수로, 문자열 값 "GRADE_1"을 통해 해당 구간의 연체 상태를 표현하는 데 사용된다. |
| DELINQUENCY_GRADE_2 | String | - | 연체 기간이 31~60일인 경우를 나타내는 구분값(상수)으로, 문자열 "GRADE_2"를 연체 등급 코드로 정의한다. |
| DELINQUENCY_GRADE_3 | String | - | 연체 기간이 61~90일인 경우를 나타내는 연체 등급 식별자 상수로, 값은 "GRADE_3"이다. |
| DELINQUENCY_GRADE_4 | String | - | 연체 기간이 91~120일 구간임을 나타내는 문자열 상수로, 연체 등급을 "GRADE_4" 값으로 식별하는 데 사용된다. |
| DELINQUENCY_GRADE_5 | String | - | 연체 기간이 121일 이상인 경우를 나타내는 연체 등급 상수로, 문자열 값 "GRADE_5"로 정의되어 연체 구간(예: 91~120일 다음 단계) 분류에 사용된다. |
| GRADE_1_MAX_DAYS | int | - | 121일 이상 같은 구간과 관련된 로직에서 1등급(Grade 1)에 해당하는 최대 일수 기준을 30일로 정의한 정적 상수입니다. |
| GRADE_2_MAX_DAYS | int | - | 2등급(Grade 2)에 해당하는 최대 허용 일수를 60일로 정의한 정적 상수입니다. |
| GRADE_3_MAX_DAYS | int | - | 3등급(Grade 3)에 대해 허용되는 최대 일수(최대 기간)를 90일로 고정해 두는 정수형 상수입니다. |
| GRADE_4_MAX_DAYS | int | - | 4학년(Grade 4)에 대해 허용되는 최대 일수(120일)를 나타내는 정수형 상수로, 관련 로직에서 상한값/제한값으로 사용됩니다. |
| DEFAULT_PENALTY_RATE | BigDecimal | - | 기본 페널티(위약금/지연 등) 적용 비율을 나타내는 상수로, 값은 0.03(3%)이다. |
| MAX_LTV_GENERAL | BigDecimal | - | 대출 유형별 최대 LTV(담보인정비율) 기준 중 일반(General) 대출에 적용되는 최대 비율을 나타내는 상수로, 값은 0.80(80%)이다. |
| MAX_LTV_MORTGAGE | BigDecimal | - | 주택담보대출에 적용되는 최대 담보인정비율(LTV) 상한값을 나타내는 상수로, 값은 0.70(70%)이다. |
| MAX_LTV_BUSINESS | BigDecimal | - | 사업(비즈니스) 용도의 최대 LTV(대출 대비 담보가치 비율) 한도를 0.75(75%)로 고정해 둔 BigDecimal 상수로, LTV 산정이나 대출 가능 한도 계산 시 상한 기준값으로 사용된다. |
| JNDI_PREFIX | String | - | JNDI 조회 시 사용하는 접두어 상수로, 애플리케이션의 환경 엔트리 네이밍 컨텍스트를 나타내는 "java:comp/env/" 값을 담는다. |
| JNDI_EJB_PREFIX | String | - | EJB를 JNDI로 조회할 때 사용하는 기본 이름(prefix) 문자열을 보관하는 상수로, "java:comp/env/ejb/" 경로를 기준으로 EJB 리소스의 JNDI 이름을 구성하는 데 사용된다. |
| JNDI_DATASOURCE_PREFIX | String | - | 애플리케이션 서버의 JNDI 환경에서 JDBC 데이터소스를 조회할 때 사용하는 이름 접두어("java:comp/env/jdbc/")를 담은 정적 상수로, 데이터소스 JNDI 이름을 구성하거나 룩업할 때 기준 문자열로 활용된다. |
| JNDI_LOAN_APPLICATION_SESSION | String | - | 세션 빈용 JNDI 이름들을 정의하는 상수 중 하나로, LoanApplicationSession EJB를 조회(lookup)하기 위한 JNDI 이름 문자열을 담는다. 값은 EJB JNDI 접두어(JNDI_EJB_PREFIX)에 "LoanApplicationSession"을 붙여 구성된다. |
| JNDI_LOAN_SCREENING_SESSION | String | - | EJB를 JNDI로 조회할 때 사용하는 대출 심사(Loan Screening) 세션의 JNDI 이름(식별 문자열) 상수로, "LoanScreeningSession"에 EJB 공통 접두사(JNDI_EJB_PREFIX)를 붙인 값을 담습니다. |
| JNDI_LOAN_EXECUTION_SESSION | String | - | EJB JNDI 이름을 구성할 때 사용하는 상수 문자열로, 기본 EJB 접두사(JNDI_EJB_PREFIX)에 "LoanExecutionSession"을 덧붙여 LoanExecutionSession 세션 빈을 JNDI로 조회하기 위한 식별자를 담는다. |
| JNDI_LOAN_LEDGER_SESSION | String | - | JNDI_EJB_PREFIX에 "LoanLedgerSession"을 붙여 만든 문자열 상수로, LoanLedgerSession EJB를 JNDI로 조회(lookup)할 때 사용하는 이름(경로)을 담고 있습니다. |
| JNDI_DELINQUENCY_MGMT_SESSION | String | - | 연체(Delinquency) 관리 세션 EJB를 JNDI로 조회할 때 사용하는 이름(식별자) 문자열 상수로, 기본 JNDI 접두사(JNDI_EJB_PREFIX)에 "DelinquencyMgmtSession"을 붙여 구성된다. |
| JNDI_DEBT_COLLECTION_SESSION | String | - | EJB JNDI 접두사(JNDI_EJB_PREFIX)에 "DebtCollectionSession"을 붙여 생성한, 채권/채무 추심 세션(EJB)을 JNDI로 조회할 때 사용하는 고정 문자열 식별자(이름) 상수입니다. |
| JNDI_LOAN_PROCESS_SESSION | String | - | EJB JNDI 접두사(JNDI_EJB_PREFIX)에 "LoanProcessSession"을 붙여 만든 문자열 상수로, 대출 처리(Loan Process) 세션 빈을 JNDI로 조회할 때 사용하는 이름(식별자)을 담는다. |
| JNDI_LOAN_APPLICATION_ENTITY | String | - | 엔티티 빈(Entity Bean)의 JNDI 이름들을 정의하는 섹션에서, 대출 신청 엔티티(LoanApplicationEntity)를 조회/룩업하기 위한 JNDI 이름 문자열 상수이다. 값은 공통 EJB JNDI 접두사(JNDI_EJB_PREFIX)에 "LoanApplicationEntity"를 덧붙여 구성된다. |
| JNDI_LOAN_LEDGER_ENTITY | String | - | JNDI_LOAN_LEDGER_ENTITY는 JNDI_EJB_PREFIX에 "LoanLedgerEntity"를 붙여 생성한 문자열 상수로, 대출원장(Loan Ledger) 관련 Entity EJB를 JNDI로 조회/룩업할 때 사용하는 이름(식별자)을 담습니다. |
| JNDI_CUSTOMER_ENTITY | String | - | EJB JNDI 접두사(JNDI_EJB_PREFIX)에 "CustomerEntity"를 붙여 만든 문자열 상수로, 고객 엔티티 EJB를 JNDI로 조회/참조할 때 사용하는 이름(키)을 담는다. |
| JNDI_COLLATERAL_ENTITY | String | - | EJB JNDI 프리픽스(JNDI_EJB_PREFIX)에 "CollateralEntity"를 덧붙여 만든 문자열로, CollateralEntity EJB/엔터티를 JNDI에서 조회(lookup)하기 위한 이름(키)을 나타내는 상수입니다. |
| JNDI_DELINQUENCY_ENTITY | String | - | 연체(Delinquency) 관련 엔티티 EJB를 JNDI로 조회할 때 사용하는 이름(룩업 키)을 정의한 정적 상수로, JNDI_EJB_PREFIX 뒤에 "DelinquencyEntity"를 붙여 최종 JNDI 문자열을 구성한다. |
| JNDI_REPAYMENT_ENTITY | String | - | JNDI_EJB_PREFIX에 "RepaymentEntity"를 붙여 만든 문자열 상수로, 상환(Repayment) 관련 Entity EJB를 JNDI를 통해 조회/참조할 때 사용하는 JNDI 이름(식별자)을 담는다. |
| JNDI_CREDIT_RATING_ENTITY | String | - | JNDI_EJB_PREFIX에 "CreditRatingEntity"를 붙여 만든 JNDI 이름 문자열 상수로, 신용등급(CreditRating) 관련 EJB/엔티티를 JNDI로 조회할 때 사용하는 식별자(lookup key)이다. |
| JNDI_DATASOURCE | String | - | 애플리케이션에서 사용할 데이터소스의 JNDI 이름을 나타내는 문자열 상수로, JNDI 접두어(JNDI_DATASOURCE_PREFIX)에 "LoanDS"를 붙인 값이다. |

#### 구조 관계

| 방향 | 관계 | 대상 | 속성 |
| --- | --- | --- | --- |
| ← | DEPENDENCY | LoanServlet | source_member=init, usage=field_call |
| ← | DEPENDENCY | DebtCollectionSessionBean | source_member=getLoanLedgerHome, usage=local_var |
| ← | DEPENDENCY | DebtCollectionSessionBean | source_member=isGrade3OrWorse, usage=local_var |
| ← | DEPENDENCY | DebtCollectionSessionBean | source_member=getRepaymentHome, usage=field_call |
| ← | DEPENDENCY | DebtCollectionSessionBean | source_member=getCollectionTargets, usage=field_call |
| ← | DEPENDENCY | DebtCollectionSessionBean | source_member=processCollectionPayment, usage=local_var |
| ← | DEPENDENCY | DelinquencyMgmtSessionBean | source_member=getLoanLedgerHome, usage=local_var |
| ← | DEPENDENCY | DelinquencyMgmtSessionBean | source_member=getDelinquencyHome, usage=local_var |
| ← | DEPENDENCY | DelinquencyMgmtSessionBean | source_member=calculateTotalPenalty, usage=local_var |
| ← | DEPENDENCY | DelinquencyMgmtSessionBean | source_member=registerDelinquency, usage=local_var |
| ← | DEPENDENCY | LoanApplicationSessionBean | source_member=getLoanApplicationHome, usage=local_var |
| ← | DEPENDENCY | LoanApplicationSessionBean | source_member=submitApplication, usage=local_var |
| ← | DEPENDENCY | LoanApplicationSessionBean | source_member=registerCollateral, usage=local_var |
| ← | DEPENDENCY | LoanApplicationSessionBean | source_member=createApplication, usage=field_call |
| ← | DEPENDENCY | LoanExecutionSessionBean | source_member=getLoanApplicationHome, usage=field_call |
| ← | DEPENDENCY | LoanExecutionSessionBean | source_member=getLedgersByCustomer, usage=local_var |
| ← | DEPENDENCY | LoanExecutionSessionBean | source_member=executeLoan, usage=local_var |
| ← | DEPENDENCY | LoanLedgerSessionBean | source_member=getLoanLedgerHome, usage=local_var |
| ← | DEPENDENCY | LoanLedgerSessionBean | source_member=getRepaymentHome, usage=cast |
| ← | DEPENDENCY | LoanLedgerSessionBean | source_member=getActiveLedgers, usage=field_call |
| ← | DEPENDENCY | LoanProcessSessionBean | source_member=getCustomerHome, usage=local_var |
| ← | DEPENDENCY | LoanProcessSessionBean | source_member=cancelProcess, usage=field_call |
| ← | DEPENDENCY | LoanProcessSessionBean | source_member=submitAndGetResult, usage=local_var |
| ← | DEPENDENCY | LoanScreeningSessionBean | source_member=getCreditRatingHome, usage=local_var |
| ← | DEPENDENCY | LoanScreeningSessionBean | source_member=getLoanApplicationHome, usage=local_var |
| ← | DEPENDENCY | LoanScreeningSessionBean | source_member=calculateLtvRatio, usage=field_call |
| ← | DEPENDENCY | LoanScreeningSessionBean | source_member=rejectApplication, usage=local_var |
| ← | DEPENDENCY | LoanScreeningSessionBean | source_member=performScreening, usage=local_var |

#### 호출 관계

| 방향 | 대상 | 호출코드 |
| --- | --- | --- |
| - | - | - |

#### 데이터 접근

| 대상 | 관계 | 근거 | 신뢰도 |
| --- | --- | --- | --- |
| - | - | - | - |

#### 요약 코드

```
없음
```

### ServiceLocator

#### 기본 정보

| 항목 | 값 |
| --- | --- |
| 이름 | ServiceLocator |
| 타입 | CLASS |
| FQN | com.banking.loan.util.ServiceLocator |
| 패키지 | com.banking.loan.util |
| 스테레오타입 | READMODEL |
| 파일 | - |
| 라인 | - |
| 토큰 | - |

#### 요약

> 이 클래스는 J2EE의 서비스 로케이터(Service Locator) 패턴을 구현하여 JNDI 룩업 결과를 캐싱함으로써 성능을 향상시키는 유틸리티이다. 전역에서 공유되는 단일 인스턴스(singleton)로 제공되며, JNDI 조회를 위한 초기 네이밍 컨텍스트(InitialContext)와 룩업 결과를 저장하는 캐시 맵을 내부에 유지한다. 리소스 요청 시에는 "캐시 조회 → 없을 때만 JNDI 룩업 → 결과를 캐시에 저장 → 반환" 흐름으로 반복적인 룩업 비용을 줄인다.

#### 메서드

| 이름 | 시그니처 | 반환타입 | 수정자 | 요약 |
| --- | --- | --- | --- | --- |
| getInstance | public static synchronized ServiceLocator getInstance() throws NamingException | - | - | JNDI 룩업 결과를 캐싱해 성능을 높이기 위한 로케이터 패턴 구현에서, 로케이터 접근을 위한 단일 인스턴스를 지연 초기화 방식으로 제공한다. 동시에 여러 스레드가 접근하더라도 인스턴스가 중복 생성되지 않도록 동기화로 임계 구역을 보호한다. 기존 인스턴스가 없을 때만 새 인스턴스를 생성해 보관하고, 이후에는 동일 인스턴스를 그대로 반환한다. 이 과정에서 네이밍 관련 예외가 발생할 수 있음을 호출자에게 전달한다. |
| getLocalHome | public EJBLocalHome getLocalHome(String jndiName) throws NamingException | - | - | J2EE의 Service Locator 패턴 취지에 맞게, 입력으로 받은 JNDI 이름에 대응하는 로컬 홈 객체를 캐시에서 먼저 찾아 반환하려고 시도한다. 캐시에 해당 항목이 없을 때에만 JNDI 룩업을 수행해 로컬 홈 객체를 획득한다. 새로 획득한 결과는 이후 재사용을 위해 캐시에 저장해 반복적인 룩업 비용을 줄인다. 최종적으로 캐시된 값 또는 새로 룩업한 값을 호출자에게 돌려주며, 이름 조회 실패 상황은 네이밍 예외로 상위에 전달한다. |
| getRemoteHome | public EJBHome getRemoteHome(String jndiName, Class homeClass) throws NamingException | - | - | 이 코드는 J2EE ServiceLocator 패턴의 의도에 맞춰, JNDI 이름을 키로 원격 홈 인터페이스 조회 결과를 캐시에 보관해 재사용함으로써 룩업 비용을 줄인다. 입력으로 받은 JNDI 이름에 대해 캐시를 먼저 조회하고, 이미 원격 홈 객체가 있으면 추가 작업 없이 그 값을 그대로 반환한다. 캐시에 없을 때만 초기 컨텍스트를 통해 JNDI 룩업을 수행한 뒤, 반환된 원격 참조를 요청된 홈 인터페이스 타입으로 안전하게 변환하고 캐시에 저장한다. 룩업 과정에서 네이밍 예외가 발생할 수 있으며, 이 경우 예외를 호출자에게 그대로 전달한다. |
| getDataSource | public DataSource getDataSource(String jndiName) throws NamingException | - | - | J2EE ServiceLocator 패턴 맥락에서, 전달받은 JNDI 이름에 해당하는 데이터 소스를 반환하되 JNDI 룩업 결과를 캐시에 보관해 이후 조회 성능을 높이려는 처리이다. 먼저 캐시에서 해당 JNDI 이름으로 데이터 소스를 찾아보고, 결과가 없을 때만 JNDI 컨텍스트를 통해 룩업을 수행한다. 새로 얻은 데이터 소스는 같은 JNDI 이름으로 캐시에 저장하여 다음 요청에서는 룩업 없이 재사용되도록 한다. 최종적으로 캐시에서 얻었거나 새로 룩업한 데이터 소스를 호출자에게 반환하며, 룩업 과정에서 발생할 수 있는 네이밍 예외는 호출자에게 전파한다. |

#### 필드

| 이름 | 타입 | 수정자 | 요약 |
| --- | --- | --- | --- |
| instance | ServiceLocator | - | JNDI 룩업 결과를 캐싱해 성능을 높이는 서비스 로케이터의 단일 인스턴스를 보관하기 위한 정적 필드로, 클래스 전역에서 동일한 ServiceLocator 객체(싱글턴)를 공유하도록 한다. |
| context | InitialContext | - | J2EE ServiceLocator에서 JNDI를 통해 리소스를 조회하기 위해 사용하는 초기 네이밍 컨텍스트(InitialContext) 객체를 보관한다. |
| cache | Map | - | J2EE ServiceLocator에서 JNDI 룩업 결과를 저장해 두는 캐시 맵으로, 동일한 리소스 조회 시 재검색을 피해서 성능을 높이기 위해 사용된다. |

#### 구조 관계

| 방향 | 관계 | 대상 | 속성 |
| --- | --- | --- | --- |
| → | DEPENDENCY | EJBLocalHome | source_member=getLocalHome, usage=return |
| ← | DEPENDENCY | LoanServlet | source_member=init, usage=local_var |
| ← | DEPENDENCY | DebtCollectionSessionBean | source_member=getLoanLedgerHome, usage=local_var |
| ← | DEPENDENCY | DebtCollectionSessionBean | source_member=getRepaymentHome, usage=field_call |
| ← | DEPENDENCY | DelinquencyMgmtSessionBean | source_member=getLoanLedgerHome, usage=local_var |
| ← | DEPENDENCY | DelinquencyMgmtSessionBean | source_member=getDelinquencyHome, usage=local_var |
| ← | DEPENDENCY | LoanApplicationSessionBean | source_member=getLoanApplicationHome, usage=cast |
| ← | DEPENDENCY | LoanApplicationSessionBean | source_member=registerCollateral, usage=local_var |
| ← | DEPENDENCY | LoanExecutionSessionBean | source_member=getLoanApplicationHome, usage=cast |
| ← | DEPENDENCY | LoanExecutionSessionBean | source_member=getLedgersByCustomer, usage=local_var |
| ← | DEPENDENCY | LoanExecutionSessionBean | source_member=executeLoan, usage=local_var |
| ← | DEPENDENCY | LoanLedgerSessionBean | source_member=getLoanLedgerHome, usage=local_var |
| ← | DEPENDENCY | LoanLedgerSessionBean | source_member=getRepaymentHome, usage=cast |
| ← | DEPENDENCY | LoanProcessSessionBean | source_member=getCustomerHome, usage=local_var |
| ← | DEPENDENCY | LoanProcessSessionBean | source_member=cancelProcess, usage=local_var |
| ← | DEPENDENCY | LoanProcessSessionBean | source_member=submitAndGetResult, usage=local_var |
| ← | DEPENDENCY | LoanScreeningSessionBean | source_member=getCreditRatingHome, usage=local_var |
| ← | DEPENDENCY | LoanScreeningSessionBean | source_member=getLoanApplicationHome, usage=local_var |
| ← | DEPENDENCY | LoanScreeningSessionBean | source_member=calculateLtvRatio, usage=field_call |

#### 호출 관계

| 방향 | 대상 | 호출코드 |
| --- | --- | --- |
| ← | LoanServlet | - |
| ← | LoanApplicationSessionBean | - |
| ← | LoanExecutionSessionBean | - |
| ← | LoanProcessSessionBean | - |
| ← | LoanScreeningSessionBean | - |

#### 데이터 접근

| 대상 | 관계 | 근거 | 신뢰도 |
| --- | --- | --- | --- |
| ServiceLocator | REFER_TO | - | 1.0 |

#### 요약 코드

```
없음
```

### LoanServlet

#### 기본 정보

| 항목 | 값 |
| --- | --- |
| 이름 | LoanServlet |
| 타입 | CLASS |
| FQN | com.banking.loan.web.LoanServlet |
| 패키지 | com.banking.loan.web |
| 스테레오타입 | COMMAND/READMODEL |
| 파일 | - |
| 라인 | - |
| 토큰 | - |

#### 요약

> 이 클래스는 여신 관리 시스템의 HTTP 서블릿으로, URL 패턴(GET /loan/applications, GET /loan/applications/{id}, POST /loan/applications, POST /loan/applications/{id}/submit, POST /loan/screening/{id}, POST /loan/screening/{id}/approve, POST /loan/execution/{id}, GET /loan/ledgers 등)에 따라 대출 신청/접수/심사/승인/실행 및 연체·추심 처리를 각각 담당하는 세션 빈(신청·심사·실행·원장·연체·추심) 홈 객체를 조회·생성해 비즈니스 로직을 위임한다. 초기화 시 JNDI로 각 세션 빈 홈 인터페이스를 조회·캐시하며 실패하면 "세션 빈 홈 인터페이스 JNDI 조회 실패"로 서블릿 예외를 던지고, 처리 결과는 공통 전송 로직을 통해 content-type을 text/plain;charset=UTF-8로 지정해 평문 UTF-8 문자열로 응답한다. 입력값 처리에서 amount/term/rate는 null이 아니고 길이가 0보다 큰 경우에만 변환·반영하며, 상태는 … → SUBMITTED → APPROVED로 전이시키고 연체 건은 연체ID 기준 추심 개시로 COLLECTION으로 전이시키되 입금액 amount가 null이거나 길이가 0이면 BigDecimal.ZERO(0)으로 간주해 입금 처리를 수행한다. 또한 요청 경로에서 ID를 뽑을 때 접두 이후 첫 '/' 위치가 0보다 큰 경우에는 '/' 이전만 ID로 자르고, 접미 기반 추출에서는 접미 위치가 0보다 큰 경우에만 접미 직전까지를 ID로 반환한다.

#### 메서드

| 이름 | 시그니처 | 반환타입 | 수정자 | 요약 |
| --- | --- | --- | --- | --- |
| init | public void init() throws ServletException | - | - | 서블릿 초기화 시점에 JNDI 룩업 결과 캐시를 제공하는 로케이터 단일 인스턴스를 얻어, 이후 URL 패턴별 업무 처리에 필요한 세션 빈 홈 인터페이스들을 미리 확보한다. LoanConstants.JNDI_LOAN_APPLICATION_SESSION, LoanConstants.JNDI_LOAN_SCREENING_SESSION, LoanConstants.JNDI_LOAN_EXECUTION_SESSION, LoanConstants.JNDI_LOAN_LEDGER_SESSION, LoanConstants.JNDI_DELINQUENCY_MGMT_SESSION, LoanConstants.JNDI_DEBT_COLLECTION_SESSION에 해당하는 JNDI 이름으로 원격 홈 객체를 조회하고, 각 홈 인터페이스 타입으로 변환해 클래스 필드에 보관한다. 초기화 과정에서 어떤 예외가 발생하더라도 이를 잡아 "세션 빈 홈 인터페이스 JNDI 조회 실패" 메시지로 서블릿 예외로 감싸 재던져, 초기화 실패가 명확히 드러나도록 한다. |
| doGet | protected void doGet(HttpServletRequest request, HttpServletResponse response)             throws ServletException, IOException | - | - | 여신 관리 시스템에서 GET 요청의 URL 경로를 해석해, 조회 성격의 업무(신청/원장/연체/추심 대상)를 경로 규칙에 따라 분기 처리한다. 요청 경로가 없으면 기본값을 "/"로 간주한 뒤, "/applications"는 신청 목록 조회, "/applications/{id}"는 신청 상세 조회로 연결하고, "/ledgers"는 원장 목록, "/ledgers/{id}"는 원장 상세 조회로 연결한다. 또한 "/delinquencies"는 활성 연체 목록, "/collections"는 추심 대상 목록 조회로 연결하며, 그 외 경로는 "ERROR: 지원하지 않는 경로" 메시지로 평문 응답을 반환한다. 처리 중 어떤 예외가 발생하더라도 예외 메시지를 포함한 "ERROR: ..." 형태의 평문 응답으로 통일해 클라이언트에 반환한다. |
| doPost | protected void doPost(HttpServletRequest request, HttpServletResponse response)             throws ServletException, IOException | - | - | POST 요청의 경로 정보를 기준으로 여신 업무를 분기 라우팅하여, 신청 생성("/applications"), 신청 접수("/applications/{id}/submit"), 심사 승인("/screening/{id}/approve"), 심사 수행("/screening/{id}"), 여신 실행("/execution/{id}"), 원장 상환 처리("/ledgers/{id}/repayment"), 추심 개시("/collections/{id}/initiate"), 추심 입금("/collections/{id}/payment")을 각각 수행하도록 위임한다. 경로 정보가 없으면 루트("/")로 간주하며, 접미 경로("/submit", "/approve", "/repayment", "/initiate", "/payment")가 붙는 패턴에서는 접두/접미 사이의 식별자를 추출해 해당 업무 처리에 전달한다. 심사 경로는 "/approve" 포함 여부로 ‘승인 확정’과 ‘심사 수행’을 구분하며, 그 외의 지원하지 않는 경로는 "ERROR: 지원하지 않는 경로: ..." 형태의 평문 응답으로 반환한다. 처리 중 어떤 예외든 포괄적으로 잡아 "ERROR: " + 예외 메시지 형태로 클라이언트에 오류를 응답한다. |
| handleGetApplications | private void handleGetApplications(HttpServletRequest request, HttpServletResponse response)             throws Exception | - | - | 여신 관리 시스템의 요청 처리 흐름에서, 여신 신청 목록을 조회해 평문(text/plain;charset=UTF-8)으로 응답하기 위한 로직이다. 요청 파라미터 customerId(고객 식별자)와 status(신청 상태)를 읽은 뒤, customerId가 null이 아니고 길이 > 0이면 해당 고객의 신청 목록을 조회하고, 그렇지 않고 status가 null이 아니고 길이 > 0이면 해당 상태의 신청 목록을 조회하며, 둘 다 비어 있으면 전체 신청 목록을 조회한다. 조회된 목록에 대해 총 건수(applications.size())를 헤더로 기록하고, 각 항목마다 applicationId, customerId, requestedAmount, status 값을 한 줄로 조합해 목록 본문을 구성한다. 최종적으로 구성된 문자열을 그대로 HTTP 응답 본문으로 전송하며, 조회/응답 과정의 예외는 상위로 전파한다. |
| handleGetApplication | private void handleGetApplication(String applicationId, HttpServletResponse response)             throws Exception | - | - | 여신 관리 시스템의 HTTP 요청 처리 흐름 중, 특정 여신 신청의 상세 정보를 조회해 클라이언트에 평문(text/plain;charset=UTF-8)으로 반환한다. 입력으로 받은 applicationId(신청 식별자)로 원격 세션 컴포넌트를 생성한 뒤, 해당 신청 건의 상세 데이터를 가져와 applicationId, customerId, applicationDate, loanType, requestedAmount, term, interestRate, status, screeningResult, approvedAmount를 순서대로 조회한다. 이렇게 조회한 값을 '=== 여신 신청 상세 ===' 헤더와 함께 줄바꿈 형식의 텍스트로 조립하여 응답 본문에 기록한다. 데이터는 읽기 전용으로 사용되며, 상태 변경이나 저장 확정 동작은 수행하지 않는다. |
| handleGetLedgers | private void handleGetLedgers(HttpServletResponse response) throws Exception | - | - | 여신 관리 시스템의 HTTP 요청 처리 흐름에서, 활성 상태의 여신 원장 목록을 조회해 클라이언트에 평문(text/plain;charset=UTF-8)으로 반환하는 역할을 수행한다. 원장 관리 기능을 제공하는 원격 세션 인스턴스를 획득한 뒤, ‘활성 원장’으로 분류되는 원장 목록을 컬렉션으로 조회한다. 응답 본문에는 "=== 활성 원장 목록 ===" 헤더와 함께 총 건수(목록 size)를 출력하고, 목록을 순회하면서 각 항목의 ledgerId(원장ID), customerId(고객ID), principalAmount(원금), outstandingBalance(잔액), status(상태)를 한 줄 형식으로 이어 붙여 사람이 읽기 쉬운 목록을 구성한다. 최종적으로 구성된 문자열을 응답으로 전송하며, 이 과정에서 데이터 저장이나 상태 변경은 수행하지 않는다. |
| handleGetLedger | private void handleGetLedger(String ledgerId, HttpServletResponse response) throws Exception | - | - | 여신 관리 시스템의 요청 처리 흐름에서, 입력으로 받은 ledgerId(원장 식별자)로 원장 상세 정보를 조회해 사용자에게 텍스트로 보여주기 위한 응답 내용을 구성한다. 원장 조회 기능을 제공하는 원격 컴포넌트를 생성한 뒤, ledgerId를 전달해 원장 정보를 가져오고 그 결과에서 ledgerId, customerId, principalAmount, outstandingBalance, interestRate, monthlyPayment, status 값을 읽어 사람이 읽을 수 있는 형식의 본문을 만든다. 만들어진 본문은 "=== 원장 상세 ===" 헤더와 함께 각 항목을 줄바꿈으로 구분해 나열되며, 최종적으로 HTTP 응답 본문으로 전송된다. 이 범위에서는 원장 데이터에 대한 변경(등록/수정/삭제) 없이 조회된 값을 표시하는 목적만 수행한다. |
| handleGetDelinquencies | private void handleGetDelinquencies(HttpServletResponse response) throws Exception | - | - | 여신 관리 흐름에서 원격 연체 관리 기능을 통해 현재 활성 상태의 연체 건 목록을 조회하고, 그 결과를 사람이 읽을 수 있는 텍스트 형태로 응답 본문에 구성해 반환한다. 먼저 연체 관리 원격 세션을 생성한 뒤 활성 연체 목록을 가져오며, 조회된 컬렉션의 size()를 이용해 총 건수를 헤더에 포함한다. 이후 각 연체 건을 순회하면서 delinquencyId(연체 식별자), ledgerId(원장ID), delinquencyAmount(연체금액), delinquencyGrade(등급), status(상태) 값을 한 줄 포맷으로 누적해 목록을 만든다. 최종적으로 누적된 문자열을 평문(text/plain;charset=UTF-8) 응답으로 전송하여, 활성 연체 현황을 클라이언트가 즉시 확인할 수 있게 한다. |
| handleGetCollectionTargets | private void handleGetCollectionTargets(HttpServletResponse response) throws Exception | - | - | 여신 관리 시스템 서블릿의 요청 처리 흐름 중, 채권 추심 업무에서 ‘추심 대상 목록’을 조회해 클라이언트에 텍스트로 반환하는 역할을 수행한다. 원격 채권 회수 컴포넌트를 생성한 뒤 추심 대상 컬렉션을 조회하고, 조회 결과의 총 건수(targets.size())를 헤더 형태로 먼저 기록한다. 이후 추심 대상 목록을 순회하면서 각 항목에서 delinquencyId(연체ID), ledgerId(원장ID), delinquencyAmount(연체금액), penaltyAmount(가산이자)를 읽어 사람이 확인 가능한 한 줄 요약 형태로 누적 문자열을 구성한다. 최종적으로 구성된 전체 문자열을 HTTP 응답 본문으로 전송하여 추심 대상 조회 결과를 평문으로 제공한다. |
| handleCreateApplication | private void handleCreateApplication(HttpServletRequest request, HttpServletResponse response)             throws Exception | - | - | 여신 관리 요청 처리 흐름에서 신규 여신 신청을 등록하기 위해, 원격 세션 컴포넌트 인스턴스를 획득한 뒤 신청 입력값을 구성해 생성 요청을 수행한다. HTTP 요청 파라미터에서 customerId, loanType, purpose를 추출해 신청 정보에 반영하고, amount/term/rate는 값이 null이 아니고 길이가 0보다 큰 경우에만 각각 requestedAmount(BigDecimal), term(int), interestRate(BigDecimal)로 변환해 설정한다. 이렇게 구성된 신청 정보를 전달해 생성 처리를 요청하고, 반환된 결과에서 applicationId와 status를 읽어 생성 완료 메시지 본문을 만든다. 마지막으로 생성 완료 메시지를 클라이언트에 평문 응답으로 전송한다. |
| handleSubmitApplication | private void handleSubmitApplication(String applicationId, HttpServletResponse response)             throws Exception | - | - | 여신 관리 시스템의 URL 패턴 처리 흐름 중 ‘신청 접수’ 요청을 수행하며, 입력으로 받은 신청ID에 대해 접수 처리를 원격 세션 컴포넌트에 위임한다. 원격 세션 인스턴스를 획득한 뒤 해당 신청ID로 접수 작업을 실행하여 신청의 처리 단계가 SUBMITTED 상태로 진행되도록 한다. 처리가 완료되면 클라이언트에게 "=== 여신 신청 접수 완료 ===" 문구와 함께 신청ID 및 상태값 SUBMITTED를 포함한 평문 응답을 UTF-8로 반환한다. 원격 호출/업무 규칙 위반 또는 I/O 문제 등으로 예외가 발생할 수 있으며, 이 예외는 상위로 전파된다. |
| handlePerformScreening | private void handlePerformScreening(String applicationId, HttpServletResponse response)             throws Exception | - | - | 여신 관리 시스템의 요청 처리 흐름에서, 입력으로 받은 신청 식별자(applicationId)에 대해 원격 세션을 통해 신용심사를 실제로 수행하고 그 결과를 받아온다. 반환된 심사 결과에서 applicationId(신청ID), creditScore(신용점수), creditGrade(신용등급), dtiRatio(DTI), ltvRatio(LTV), approved(자동승인 여부), reasons(사유)를 조회해 사람이 읽을 수 있는 텍스트 형식으로 조합한다. 조합된 문자열은 "=== 여신 심사 결과 ===" 헤더와 각 항목별 줄바꿈을 포함한 평문 응답으로 구성된다. 마지막으로 이 평문 내용을 HTTP 응답 본문으로 전송해 클라이언트가 심사 결과를 즉시 확인할 수 있게 한다. |
| handleApproveApplication | private void handleApproveApplication(String applicationId, HttpServletRequest request,                                            HttpServletResponse response) throws Exception | - | - | 여신 관리 시스템의 HTTP 요청 처리 흐름에서, 특정 여신 신청 건을 승인 상태로 확정하기 위해 원격 심사 기능을 호출하고 결과를 텍스트로 응답한다. 요청 파라미터에서 approverEmployeeId, approvedAmount, approvedRate 값을 읽어오며, approvedAmount/approvedRate가 null이거나 길이가 0이면 각각 0으로 간주해 금액/금리 값을 준비한다. 준비된 신청 식별자와 승인 처리자 식별자, 최종 승인금액, 최종 승인금리를 사용해 승인 확정 처리를 요청하여 신청 상태를 APPROVED로 반영하도록 한다. 처리가 끝나면 응답 본문에 "=== 여신 승인 완료 ==="와 신청ID, 상태(APPROVED)를 포함한 평문 메시지를 반환하며, 과정 중 발생하는 예외는 상위로 전파한다. |
| handleExecuteLoan | private void handleExecuteLoan(String applicationId, HttpServletResponse response)             throws Exception | - | - | 여신 관리 요청 처리 흐름에서, 신청 식별자를 입력으로 받아 승인된 여신의 실행(대출 원장 생성)을 원격 세션에 위임하고 그 결과로 생성된 원장 정보를 돌려받는다. 원격 호출 결과로 받은 원장 정보에서 ledgerId, principalAmount, interestRate, monthlyPayment, loanStartDate, maturityDate 값을 조회해 “=== 여신 실행 완료 ===” 형식의 텍스트 메시지로 조립한다. 조립된 메시지는 HTTP 응답 본문에 기록되어 클라이언트가 실행 결과(원장ID/대출금액/금리/월납입액/시작일/만기일)를 확인할 수 있게 한다. 원격 호출 실패나 실행 처리 실패는 예외로 상위로 전파되어 일관된 오류 처리 흐름에 맡긴다. |
| handleProcessRepayment | private void handleProcessRepayment(String ledgerId, HttpServletRequest request,                                          HttpServletResponse response) throws Exception | - | - | 여신 관리 서블릿의 요청 처리 흐름 중, 특정 원장 식별자(ledgerId)에 대한 상환 처리를 실행하고 결과를 텍스트로 응답하는 역할을 수행한다. 요청 파라미터에서 principalAmount, interestAmount, penaltyAmount, repaymentType을 추출한 뒤, 각 금액 문자열이 null이거나 길이가 0이면 0으로 간주하고 그렇지 않으면 숫자 금액으로 변환한다. repaymentType이 null이거나 길이가 0이면 기본값으로 "REGULAR"를 사용해 상환 유형을 확정한 뒤, 원장에 대해 원금·이자·가산이자와 상환 유형을 반영하는 상환 처리를 요청한다. 상환 처리 결과로 받은 repaymentId, principalAmount, interestAmount, penaltyAmount, totalAmount, transactionId를 조합해 "=== 상환 처리 완료 ===" 형식의 메시지를 구성하고, 이를 클라이언트에 응답으로 반환한다. |
| handleInitiateCollection | private void handleInitiateCollection(String delinquencyId, HttpServletResponse response)             throws Exception | - | - | 이 코드는 여신 관리 서블릿의 URL 처리 흐름 중 ‘추심 개시’ 요청을 받아, 입력으로 전달된 연체ID를 기준으로 추심 절차를 시작시키는 업무를 수행한다. 원격 세션 인스턴스를 생성한 뒤, 해당 연체ID에 대해 추심 개시를 요청하여 업무 상태가 ‘COLLECTION’으로 전이될 수 있는 처리를 유발한다. 처리가 끝나면 클라이언트에 평문 응답으로 “=== 추심 개시 완료 ===”, 연체ID, 그리고 상태값 “COLLECTION”을 포함한 결과 메시지를 반환한다. 원격 호출/생성 및 응답 출력 과정에서 발생할 수 있는 예외는 별도 처리 없이 상위로 전파한다. |
| handleCollectionPayment | private void handleCollectionPayment(String delinquencyId, HttpServletRequest request,                                           HttpServletResponse response) throws Exception | - | - | 여신 관리 시스템의 HTTP 요청 처리 흐름에서, 연체/추심 건에 대한 ‘추심 입금’ 업무를 수행하기 위해 원격 세션 컴포넌트를 생성해 호출한다. 요청 파라미터에서 amount(입금액)를 읽어오며, 값이 null이거나 길이가 0이면 BigDecimal.ZERO(0)으로 간주하고 그렇지 않으면 BigDecimal로 변환해 입금액을 확정한다. 이후 연체ID와 확정된 입금액을 입력으로 회수 입금 처리를 실행하여 추심 관련 상태 변경을 유도한다. 처리 완료 후에는 연체ID와 입금액을 포함한 완료 메시지를 평문 응답으로 반환해 클라이언트가 처리 결과를 확인할 수 있게 한다. |
| extractId | private String extractId(String pathInfo, String prefix) | - | - | 여신 관리 시스템에서 URL 패턴에 따라 업무를 분기하기 위해, 요청 경로 문자열에서 특정 접두 구간 이후의 식별자 값을 추출한다. 입력된 경로에서 접두 길이만큼을 제거한 나머지 문자열을 만든 뒤, 그 안에서 첫 번째 '/' 위치를 찾는다. '/'가 0보다 큰 위치에 존재하면(즉 식별자 뒤에 추가 경로가 이어지면) '/' 이전 구간만 잘라 식별자로 반환하고, 그렇지 않으면 나머지 전체를 식별자로 반환한다. 이 과정은 문자열 파싱만 수행하며 저장·갱신 같은 상태 변경은 발생하지 않는다. |
| extractIdBeforeSuffix | private String extractIdBeforeSuffix(String pathInfo, String prefix, String suffix) | - | - | 여신 관리 시스템에서 URL 패턴에 따라 업무를 분기 처리할 때, 경로 문자열에서 특정 접두 구간 이후의 식별자 값을 잘라내기 위해 사용되는 보조 로직이다. 입력된 경로에 지정된 접두 문자열이 포함되지 않으면, 별도 가공 없이 원본 경로를 그대로 반환한다. 접두 문자열이 존재하면 그 뒤쪽 문자열을 기준으로 지정된 접미 문자열의 위치를 찾아, 접미가 0보다 큰 위치에 발견될 때에만 접미 직전까지를 식별자로 반환한다. 접미가 없거나 접미가 바로 첫 글자 위치(인덱스 0)에 있는 경우에는 접두 이후 전체를 반환하여, 불완전한 ‘접미만 있는 형태’에 대해 과도한 절단을 피한다. |
| sendResponse | private void sendResponse(HttpServletResponse response, String content) throws IOException | - | - | 여신 관리 시스템의 HTTP 요청 처리 흐름에서, 클라이언트로 간단한 텍스트 응답을 반환하기 위한 공통 전송 로직을 제공한다. 응답의 콘텐츠 타입을 "text/plain;charset=UTF-8"로 지정해 평문이며 UTF-8 인코딩임을 명확히 한 뒤, 입력으로 받은 문자열 내용을 응답 본문에 그대로 기록한다. 출력 과정에서 발생할 수 있는 입출력 오류는 상위 호출자에게 예외로 전파하여, 호출자가 전체 응답 처리 실패를 일관되게 다룰 수 있게 한다. |

#### 필드

| 이름 | 타입 | 수정자 | 요약 |
| --- | --- | --- | --- |
| serialVersionUID | long | - | 서블릿(직렬화 가능한 클래스)의 직렬화 버전 관리를 위한 고정 식별자(SerialVersionUID)로, 역직렬화 시 클래스 변경에 따른 호환성을 확인하기 위해 1L로 지정되어 있다. |
| appSessionHome | LoanApplicationSessionHome | - | 여신 관리 서블릿에서 대출 신청(Loan Application) 관련 업무를 처리하기 위해 호출하는 세션 빈의 홈(lookup/생성) 객체 참조를 보관한다. |
| screeningSessionHome | LoanScreeningSessionHome | - | 여신(대출) 관리 서블릿에서 심사 관련 업무를 처리할 세션 빈(LoanScreeningSession) 홈/팩토리 역할의 컴포넌트 참조를 보관하는 필드이다. URL 패턴에 따라 심사 수행·승인 등 심사 단계 요청이 들어올 때 해당 세션 빈을 찾아 호출하는 데 사용된다. |
| executionSessionHome | LoanExecutionSessionHome | - | 여신 관리 서블릿에서 ‘여신 실행(loan execution)’ 업무 처리를 담당하는 세션 빈을 찾아 호출하기 위한 홈(접근) 객체를 보관하는 필드이다. 실행 관련 요청(URL 패턴)에 대해 해당 세션 빈을 통해 실행 처리 로직을 수행하는 데 사용된다. |
| ledgerSessionHome | LoanLedgerSessionHome | - | 여신 관리 서블릿에서 여신 원장(ledger) 관련 업무를 처리하는 세션 빈을 찾아 호출하기 위한 홈(접근) 객체를 보관한다. 특히 /loan/ledgers 등의 원장 조회·처리 요청을 적절한 세션 빈으로 위임하는 데 사용된다. |
| delinquencySessionHome | DelinquencyMgmtSessionHome | - | 여신 관리 시스템 서블릿이 URL 패턴에 따라 업무를 처리할 때, 연체(Delinquency) 관리 관련 세션 빈을 조회·생성하고 호출하기 위한 홈 인터페이스(세션 빈 진입점)를 보관하는 필드이다. |
| collectionSessionHome | DebtCollectionSessionHome | - | 여신 관리 서블릿이 URL 패턴별 업무 처리 과정에서 연체/채권 추심 관련 비즈니스 로직을 수행하는 세션 빈(EJB) 홈 객체를 보관하는 필드이다. |

#### 구조 관계

| 방향 | 관계 | 대상 | 속성 |
| --- | --- | --- | --- |
| → | ASSOCIATION | DebtCollectionSessionHome | source_member=init |
| → | ASSOCIATION | DebtCollectionSessionHome | source_member=handleCollectionPayment |
| → | ASSOCIATION | DelinquencyMgmtSessionHome | source_member=init |
| → | ASSOCIATION | LoanApplicationSessionHome | source_member=handleSubmitApplication |
| → | ASSOCIATION | LoanApplicationSessionHome | source_member=init |
| → | ASSOCIATION | LoanApplicationSessionHome | source_member=handleCreateApplication |
| → | ASSOCIATION | LoanApplicationSessionHome | source_member=handleGetApplication |
| → | ASSOCIATION | LoanExecutionSessionHome | source_member=init |
| → | ASSOCIATION | LoanLedgerSessionHome | source_member=init |
| → | ASSOCIATION | LoanLedgerSessionHome | source_member=handleGetLedger |
| → | ASSOCIATION | LoanScreeningSessionHome | source_member=init |
| → | ASSOCIATION | LoanScreeningSessionHome | source_member=handlePerformScreening |
| → | DEPENDENCY | DelinquencyDTO | source_member=handleGetDelinquencies, usage=cast |
| → | DEPENDENCY | DelinquencyDTO | source_member=handleGetCollectionTargets, usage=cast |
| → | DEPENDENCY | LoanApplicationDTO | source_member=handleGetApplications, usage=cast |
| → | DEPENDENCY | LoanApplicationDTO | source_member=handleCreateApplication, usage=local_new |
| → | DEPENDENCY | LoanApplicationDTO | source_member=handleGetApplication, usage=local_var |
| → | DEPENDENCY | LoanLedgerDTO | source_member=handleExecuteLoan, usage=local_var |
| → | DEPENDENCY | LoanLedgerDTO | source_member=handleGetLedger, usage=local_var |
| → | DEPENDENCY | RepaymentDTO | source_member=handleProcessRepayment, usage=local_var |
| → | DEPENDENCY | ScreeningResultDTO | source_member=handlePerformScreening, usage=local_var |
| → | DEPENDENCY | DebtCollectionSession | source_member=handleCollectionPayment, usage=local_var |
| → | DEPENDENCY | DelinquencyMgmtSession | source_member=handleGetDelinquencies, usage=local_var |
| → | DEPENDENCY | LoanApplicationSession | source_member=handleSubmitApplication, usage=local_var |
| → | DEPENDENCY | LoanApplicationSession | source_member=handleCreateApplication, usage=local_var |
| → | DEPENDENCY | LoanApplicationSession | source_member=handleGetApplication, usage=local_var |
| → | DEPENDENCY | LoanExecutionSession | source_member=handleExecuteLoan, usage=local_var |
| → | DEPENDENCY | LoanLedgerSession | source_member=handleGetLedger, usage=local_var |
| → | DEPENDENCY | LoanScreeningSession | source_member=handleApproveApplication, usage=local_var |
| → | DEPENDENCY | LoanScreeningSession | source_member=handlePerformScreening, usage=local_var |
| → | DEPENDENCY | LoanConstants | source_member=init, usage=field_call |
| → | DEPENDENCY | ServiceLocator | source_member=init, usage=local_var |
| → | DEPENDENCY | HttpServletResponse | source_member=handleSubmitApplication, usage=parameter |
| → | DEPENDENCY | HttpServletResponse | source_member=handleInitiateCollection, usage=parameter |

#### 호출 관계

| 방향 | 대상 | 호출코드 |
| --- | --- | --- |
| → | DelinquencyDTO | - |
| → | LoanApplicationDTO | - |
| → | LoanLedgerDTO | - |
| → | RepaymentDTO | - |
| → | ScreeningResultDTO | - |
| → | DebtCollectionSession | - |
| → | DebtCollectionSessionHome | - |
| → | DelinquencyMgmtSession | - |
| → | DelinquencyMgmtSessionHome | - |
| → | LoanApplicationSession | - |
| → | LoanApplicationSessionHome | - |
| → | LoanExecutionSession | - |
| → | LoanExecutionSessionHome | - |
| → | LoanLedgerSession | - |
| → | LoanLedgerSessionHome | - |
| → | LoanScreeningSession | - |
| → | LoanScreeningSessionHome | - |
| → | ServiceLocator | - |
| → | ServiceLocator | 65:             ServiceLocator locator = ServiceLocator.getInstance(); |
| → | LoanServlet | 99:                 handleGetApplications(request, response); |
| → | LoanServlet | 102:                 handleGetApplication(id, response); |
| → | LoanServlet | 104:                 handleGetLedgers(response); |
| → | LoanServlet | 107:                 handleGetLedger(id, response); |
| → | LoanServlet | 109:                 handleGetDelinquencies(response); |
| → | LoanServlet | 111:                 handleGetCollectionTargets(response); |
| → | LoanServlet | 101:                 String id = extractId(pathInfo, "/applications/"); |
| → | LoanServlet | 113:                 sendResponse(response, "ERROR: 지원하지 않는 경로: " + pathInfo); |
| → | LoanServlet | 129:                 handleCreateApplication(request, response); |
| → | LoanServlet | 132:                 handleSubmitApplication(id, response); |
| → | LoanServlet | 138:                 handlePerformScreening(id, response); |
| → | LoanServlet | 135:                 handleApproveApplication(id, request, response); |
| → | LoanServlet | 141:                 handleExecuteLoan(id, response); |
| → | LoanServlet | 144:                 handleProcessRepayment(id, request, response); |
| → | LoanServlet | 147:                 handleInitiateCollection(id, response); |
| → | LoanServlet | 150:                 handleCollectionPayment(id, request, response); |
| → | LoanServlet | 137:                 String id = extractId(pathInfo, "/screening/"); |
| → | LoanServlet | 131:                 String id = extractIdBeforeSuffix(pathInfo, "/applications/", "/submit"); |
| → | LoanServlet | 152:                 sendResponse(response, "ERROR: 지원하지 않는 경로: " + pathInfo); |
| → | LoanServlet | 191:         sendResponse(response, sb.toString()); |
| → | LoanApplicationDTO | 184:             sb.append("신청ID: ").append(dto.getApplicationId()) 185:               .append(" \| 고객ID: ").append(dto.getCustomerId()) 186:               .append(" \| 금액: ").append(dto.getRequestedAmo |
| → | LoanApplicationSessionHome | 163:         LoanApplicationSession session = appSessionHome.create(); |
| → | LoanServlet | 212:         sendResponse(response, sb.toString()); |
| → | LoanApplicationDTO | 201:         sb.append("신청ID: ").append(dto.getApplicationId()).append("\n"); |
| → | LoanApplicationDTO | 202:         sb.append("고객ID: ").append(dto.getCustomerId()).append("\n"); |
| → | LoanApplicationDTO | 203:         sb.append("신청일: ").append(dto.getApplicationDate()).append("\n"); |
| → | LoanApplicationDTO | 205:         sb.append("신청금액: ").append(dto.getRequestedAmount()).append("\n"); |
| → | LoanApplicationDTO | 204:         sb.append("유형: ").append(dto.getLoanType()).append("\n"); |
| → | LoanApplicationDTO | 206:         sb.append("기간(월): ").append(dto.getTerm()).append("\n"); |
| → | LoanApplicationDTO | 207:         sb.append("금리: ").append(dto.getInterestRate()).append("\n"); |
| → | LoanApplicationDTO | 208:         sb.append("상태: ").append(dto.getStatus()).append("\n"); |
| → | LoanApplicationDTO | 209:         sb.append("심사결과: ").append(dto.getScreeningResult()).append("\n"); |
| → | LoanApplicationDTO | 210:         sb.append("승인금액: ").append(dto.getApprovedAmount()).append("\n"); |
| → | LoanApplicationSession | 197:         LoanApplicationDTO dto = session.getApplication(applicationId); |
| → | LoanApplicationSessionHome | 196:         LoanApplicationSession session = appSessionHome.create(); |
| → | LoanServlet | 234:         sendResponse(response, sb.toString()); |
| → | LoanLedgerDTO | 226:             sb.append("원장ID: ").append(dto.getLedgerId()) 227:               .append(" \| 고객ID: ").append(dto.getCustomerId()) 228:               .append(" \| 원금: ").append(dto.getPrincipalAmount() |
| → | LoanLedgerSession | 217:         Collection ledgers = session.getActiveLedgers(); |
| → | LoanLedgerSessionHome | 216:         LoanLedgerSession session = ledgerSessionHome.create(); |
| → | LoanServlet | 251:         sendResponse(response, sb.toString()); |
| → | LoanLedgerDTO | 243:         sb.append("원장ID: ").append(dto.getLedgerId()).append("\n"); |
| → | LoanLedgerDTO | 244:         sb.append("고객ID: ").append(dto.getCustomerId()).append("\n"); |
| → | LoanLedgerDTO | 245:         sb.append("원금: ").append(dto.getPrincipalAmount()).append("\n"); |
| → | LoanLedgerDTO | 246:         sb.append("잔액: ").append(dto.getOutstandingBalance()).append("\n"); |
| → | LoanLedgerDTO | 247:         sb.append("금리: ").append(dto.getInterestRate()).append("\n"); |
| → | LoanLedgerDTO | 248:         sb.append("월납입액: ").append(dto.getMonthlyPayment()).append("\n"); |
| → | LoanLedgerDTO | 249:         sb.append("상태: ").append(dto.getStatus()).append("\n"); |
| → | LoanLedgerSession | 239:         LoanLedgerDTO dto = session.getLedger(ledgerId); |
| → | LoanLedgerSessionHome | 238:         LoanLedgerSession session = ledgerSessionHome.create(); |
| → | LoanServlet | 273:         sendResponse(response, sb.toString()); |
| → | DelinquencyDTO | 265:             sb.append("연체ID: ").append(dto.getDelinquencyId()) 266:               .append(" \| 원장ID: ").append(dto.getLedgerId()) 267:               .append(" \| 연체금액: ").append(dto.getDelinquencyA |
| → | DelinquencyMgmtSession | 256:         Collection delinquencies = session.getActiveDelinquencies(); |
| → | DelinquencyMgmtSessionHome | 255:         DelinquencyMgmtSession session = delinquencySessionHome.create(); |
| → | LoanServlet | 294:         sendResponse(response, sb.toString()); |
| → | DelinquencyDTO | 287:             sb.append("연체ID: ").append(dto.getDelinquencyId()) 288:               .append(" \| 원장ID: ").append(dto.getLedgerId()) 289:               .append(" \| 연체금액: ").append(dto.getDelinquencyA |
| → | DebtCollectionSession | 278:         Collection targets = session.getCollectionTargets(); |
| → | DebtCollectionSessionHome | 277:         DebtCollectionSession session = collectionSessionHome.create(); |
| → | LoanServlet | 330:         sendResponse(response, sb.toString()); |
| → | LoanApplicationDTO | 327:         sb.append("신청ID: ").append(created.getApplicationId()).append("\n"); |
| → | LoanApplicationDTO | 304:         dto.setCustomerId(request.getParameter("customerId")); |
| → | LoanApplicationDTO | 310:             dto.setRequestedAmount(new BigDecimal(amountStr)); |
| → | LoanApplicationDTO | 305:         dto.setLoanType(request.getParameter("loanType")); |
| → | LoanApplicationDTO | 306:         dto.setLoanPurpose(request.getParameter("purpose")); |
| → | LoanApplicationDTO | 315:             dto.setTerm(Integer.parseInt(termStr)); |
| → | LoanApplicationDTO | 320:             dto.setInterestRate(new BigDecimal(rateStr)); |
| → | LoanApplicationDTO | 328:         sb.append("상태: ").append(created.getStatus()).append("\n"); |
| → | LoanApplicationSession | 323:         LoanApplicationDTO created = session.createApplication(dto); |
| → | LoanApplicationSessionHome | 301:         LoanApplicationSession session = appSessionHome.create(); |
| → | LoanServlet | 338:         sendResponse(response, "=== 여신 신청 접수 완료 ===\n신청ID: " + applicationId + "\n상태: SUBMITTED\n"); |
| → | LoanApplicationSession | 336:         session.submitApplication(applicationId); |
| → | LoanApplicationSessionHome | 335:         LoanApplicationSession session = appSessionHome.create(); |
| → | LoanServlet | 356:         sendResponse(response, sb.toString()); |
| → | ScreeningResultDTO | 348:         sb.append("신청ID: ").append(result.getApplicationId()).append("\n"); |
| → | ScreeningResultDTO | 349:         sb.append("신용점수: ").append(result.getCreditScore()).append("\n"); |
| → | ScreeningResultDTO | 350:         sb.append("신용등급: ").append(result.getCreditGrade()).append("\n"); |
| → | ScreeningResultDTO | 351:         sb.append("DTI: ").append(result.getDtiRatio()).append("\n"); |
| → | ScreeningResultDTO | 352:         sb.append("LTV: ").append(result.getLtvRatio()).append("\n"); |
| → | ScreeningResultDTO | 353:         sb.append("자동승인: ").append(result.isApproved()).append("\n"); |
| → | ScreeningResultDTO | 354:         sb.append("사유: ").append(result.getReasons()).append("\n"); |
| → | LoanScreeningSession | 344:         ScreeningResultDTO result = session.performScreening(applicationId); |
| → | LoanScreeningSessionHome | 343:         LoanScreeningSession session = screeningSessionHome.create(); |
| → | LoanServlet | 374:         sendResponse(response, "=== 여신 승인 완료 ===\n신청ID: " + applicationId + "\n상태: APPROVED\n"); |
| → | LoanScreeningSession | 372:         session.approveApplication(applicationId, approverEmployeeId, approvedAmount, approvedRate); |
| → | LoanScreeningSessionHome | 361:         LoanScreeningSession session = screeningSessionHome.create(); |
| → | LoanServlet | 391:         sendResponse(response, sb.toString()); |
| → | LoanLedgerDTO | 384:         sb.append("원장ID: ").append(dto.getLedgerId()).append("\n"); |
| → | LoanLedgerDTO | 385:         sb.append("대출금액: ").append(dto.getPrincipalAmount()).append("\n"); |
| → | LoanLedgerDTO | 386:         sb.append("금리: ").append(dto.getInterestRate()).append("\n"); |
| → | LoanLedgerDTO | 388:         sb.append("시작일: ").append(dto.getLoanStartDate()).append("\n"); |
| → | LoanLedgerDTO | 389:         sb.append("만기일: ").append(dto.getMaturityDate()).append("\n"); |
| → | LoanLedgerDTO | 387:         sb.append("월납입액: ").append(dto.getMonthlyPayment()).append("\n"); |
| → | LoanExecutionSession | 380:         LoanLedgerDTO dto = session.executeLoan(applicationId); |
| → | LoanExecutionSessionHome | 379:         LoanExecutionSession session = executionSessionHome.create(); |
| → | LoanServlet | 425:         sendResponse(response, sb.toString()); |
| → | RepaymentDTO | 418:         sb.append("상환ID: ").append(dto.getRepaymentId()).append("\n"); |
| → | RepaymentDTO | 419:         sb.append("원금상환: ").append(dto.getPrincipalAmount()).append("\n"); |
| → | RepaymentDTO | 420:         sb.append("이자상환: ").append(dto.getInterestAmount()).append("\n"); |
| → | RepaymentDTO | 421:         sb.append("가산이자: ").append(dto.getPenaltyAmount()).append("\n"); |
| → | RepaymentDTO | 422:         sb.append("총액: ").append(dto.getTotalAmount()).append("\n"); |
| → | RepaymentDTO | 423:         sb.append("거래ID: ").append(dto.getTransactionId()).append("\n"); |
| → | LoanLedgerSession | 414:         RepaymentDTO dto = session.processRepayment(ledgerId, principal, interest, penalty, repaymentType); |
| → | LoanLedgerSessionHome | 396:         LoanLedgerSession session = ledgerSessionHome.create(); |
| → | LoanServlet | 433:         sendResponse(response, 434:                 "=== 추심 개시 완료 ===\n연체ID: " + delinquencyId + "\n상태: COLLECTION\n"); |
| → | DebtCollectionSession | 431:         session.initiateCollection(delinquencyId); |
| → | DebtCollectionSessionHome | 430:         DebtCollectionSession session = collectionSessionHome.create(); |
| → | LoanServlet | 447:         sendResponse(response, 448:                 "=== 추심 입금 처리 완료 ===\n연체ID: " + delinquencyId + "\n입금액: " + amount + "\n"); |
| → | DebtCollectionSession | 445:         session.processCollectionPayment(delinquencyId, amount); |
| → | DebtCollectionSessionHome | 439:         DebtCollectionSession session = collectionSessionHome.create(); |

#### 데이터 접근

| 대상 | 관계 | 근거 | 신뢰도 |
| --- | --- | --- | --- |
| DebtCollectionSession | REFER_TO | - | 1.0 |
| DebtCollectionSessionHome | REFER_TO | - | 1.0 |
| DelinquencyMgmtSession | REFER_TO | - | 1.0 |
| DelinquencyMgmtSessionHome | REFER_TO | - | 1.0 |
| LoanApplicationSession | REFER_TO | - | 1.0 |
| LoanApplicationSessionHome | REFER_TO | - | 1.0 |
| LoanExecutionSession | REFER_TO | - | 1.0 |
| LoanExecutionSessionHome | REFER_TO | - | 1.0 |
| LoanLedgerSession | REFER_TO | - | 1.0 |
| LoanLedgerSessionHome | REFER_TO | - | 1.0 |
| LoanScreeningSession | REFER_TO | - | 1.0 |
| LoanScreeningSessionHome | REFER_TO | - | 1.0 |
| LoanConstants | REFER_TO | - | 1.0 |
| ServiceLocator | REFER_TO | - | 1.0 |
| ejb-jar.xml | REFER_TO | - | 1.0 |
| ejb-jar.xml | REFER_TO | - | 1.0 |
| ejb-jar.xml | REFER_TO | - | 1.0 |
| ejb-jar.xml | REFER_TO | - | 1.0 |
| ejb-jar.xml | REFER_TO | - | 1.0 |
| ejb-jar.xml | REFER_TO | - | 1.0 |
| LoanApplicationDTO | REFER_TO | - | 1.0 |
| LoanApplicationSession | REFER_TO | - | 1.0 |
| ejb-jar.xml | REFER_TO | - | 1.0 |
| LoanApplicationDTO | REFER_TO | - | 1.0 |
| LoanApplicationSession | REFER_TO | - | 1.0 |
| ejb-jar.xml | REFER_TO | - | 1.0 |
| LoanLedgerDTO | REFER_TO | - | 1.0 |
| LoanLedgerSession | REFER_TO | - | 1.0 |
| ejb-jar.xml | REFER_TO | - | 1.0 |
| LoanLedgerDTO | REFER_TO | - | 1.0 |
| LoanLedgerSession | REFER_TO | - | 1.0 |
| ejb-jar.xml | REFER_TO | - | 1.0 |
| DelinquencyDTO | REFER_TO | - | 1.0 |
| DelinquencyMgmtSession | REFER_TO | - | 1.0 |
| ejb-jar.xml | REFER_TO | - | 1.0 |
| DelinquencyDTO | REFER_TO | - | 1.0 |
| DebtCollectionSession | REFER_TO | - | 1.0 |
| ejb-jar.xml | REFER_TO | - | 1.0 |
| LoanApplicationDTO | REFER_TO | - | 1.0 |
| LoanApplicationSession | REFER_TO | - | 1.0 |
| ejb-jar.xml | REFER_TO | - | 1.0 |
| LoanApplicationSession | REFER_TO | - | 1.0 |
| ejb-jar.xml | REFER_TO | - | 1.0 |
| ScreeningResultDTO | REFER_TO | - | 1.0 |
| LoanScreeningSession | REFER_TO | - | 1.0 |
| ejb-jar.xml | REFER_TO | - | 1.0 |
| LoanScreeningSession | REFER_TO | - | 1.0 |
| ejb-jar.xml | REFER_TO | - | 1.0 |
| LoanLedgerDTO | REFER_TO | - | 1.0 |
| LoanExecutionSession | REFER_TO | - | 1.0 |
| ejb-jar.xml | REFER_TO | - | 1.0 |
| RepaymentDTO | REFER_TO | - | 1.0 |
| LoanLedgerSession | REFER_TO | - | 1.0 |
| ejb-jar.xml | REFER_TO | - | 1.0 |
| DebtCollectionSession | REFER_TO | - | 1.0 |
| ejb-jar.xml | REFER_TO | - | 1.0 |
| DebtCollectionSession | REFER_TO | - | 1.0 |
| ejb-jar.xml | REFER_TO | - | 1.0 |

#### 요약 코드

```
없음
```


## 4. 외부 의존성 (EXTERNAL)

| 외부 엔티티 | 타입 | 참조 INTERNAL |
| --- | --- | --- |
| EJBLocalHome | CLASS | ServiceLocator |
| EntityContext | CLASS | CollateralBean, CreditRatingBean, CustomerBean, DelinquencyBean, LoanApplicationBean, LoanLedgerBean, RepaymentBean |
| HttpServletResponse | CLASS | LoanServlet |
| SessionContext | CLASS | DebtCollectionSessionBean, DelinquencyMgmtSessionBean, LoanApplicationSessionBean, LoanExecutionSessionBean, LoanLedgerSessionBean, LoanProcessSessionBean, LoanScreeningSessionBean |

## 5. Artifact 청크

### ejb-jar.xml

#### 기본 정보

| 항목 | 값 |
| --- | --- |
| 이름 | ejb-jar.xml |
| 파일 | ejb-jar.xml |
| 종류 | - |
| 요약 | - |

#### 관계

| 방향 | 관계 | 대상 |
| --- | --- | --- |
| → | REFER_TO | LoanApplicationBean |
| → | REFER_TO | LoanApplicationLocal |
| → | REFER_TO | LoanApplicationLocalHome |
| → | REFER_TO | LOAN_APPLICATION |
| ← | REFER_TO | LoanApplicationSessionBean |
| ← | REFER_TO | LoanApplicationSessionBean |
| ← | REFER_TO | LoanApplicationSessionBean |
| ← | REFER_TO | LoanApplicationSessionBean |
| ← | REFER_TO | LoanApplicationSessionBean |
| ← | REFER_TO | LoanApplicationSessionBean |
| ← | REFER_TO | LoanApplicationSessionBean |
| ← | REFER_TO | LoanApplicationSessionBean |
| ← | REFER_TO | LoanApplicationSessionBean |
| ← | REFER_TO | LoanExecutionSessionBean |
| ← | REFER_TO | LoanExecutionSessionBean |
| ← | REFER_TO | LoanScreeningSessionBean |
| ← | REFER_TO | LoanScreeningSessionBean |
| ← | REFER_TO | LoanScreeningSessionBean |
| ← | REFER_TO | LoanScreeningSessionBean |

### ejb-jar.xml

#### 기본 정보

| 항목 | 값 |
| --- | --- |
| 이름 | ejb-jar.xml |
| 파일 | ejb-jar.xml |
| 종류 | - |
| 요약 | - |

#### 관계

| 방향 | 관계 | 대상 |
| --- | --- | --- |
| → | REFER_TO | LoanLedgerBean |
| → | REFER_TO | LoanLedgerLocal |
| → | REFER_TO | LoanLedgerLocalHome |
| → | REFER_TO | LOAN_LEDGER |
| ← | REFER_TO | DebtCollectionSessionBean |
| ← | REFER_TO | DebtCollectionSessionBean |
| ← | REFER_TO | DebtCollectionSessionBean |
| ← | REFER_TO | DelinquencyMgmtSessionBean |
| ← | REFER_TO | DelinquencyMgmtSessionBean |
| ← | REFER_TO | LoanExecutionSessionBean |
| ← | REFER_TO | LoanExecutionSessionBean |
| ← | REFER_TO | LoanExecutionSessionBean |
| ← | REFER_TO | LoanLedgerSessionBean |
| ← | REFER_TO | LoanLedgerSessionBean |
| ← | REFER_TO | LoanLedgerSessionBean |
| ← | REFER_TO | LoanLedgerSessionBean |
| ← | REFER_TO | LoanLedgerSessionBean |
| ← | REFER_TO | LoanLedgerSessionBean |

### ejb-jar.xml

#### 기본 정보

| 항목 | 값 |
| --- | --- |
| 이름 | ejb-jar.xml |
| 파일 | ejb-jar.xml |
| 종류 | - |
| 요약 | - |

#### 관계

| 방향 | 관계 | 대상 |
| --- | --- | --- |
| → | REFER_TO | CustomerBean |
| → | REFER_TO | CustomerLocal |
| → | REFER_TO | CustomerLocalHome |
| → | REFER_TO | CUSTOMER |
| ← | REFER_TO | LoanProcessSessionBean |
| ← | REFER_TO | LoanProcessSessionBean |

### ejb-jar.xml

#### 기본 정보

| 항목 | 값 |
| --- | --- |
| 이름 | ejb-jar.xml |
| 파일 | ejb-jar.xml |
| 종류 | - |
| 요약 | - |

#### 관계

| 방향 | 관계 | 대상 |
| --- | --- | --- |
| → | REFER_TO | CollateralBean |
| → | REFER_TO | CollateralLocal |
| → | REFER_TO | CollateralLocalHome |
| → | REFER_TO | COLLATERAL |
| ← | REFER_TO | LoanApplicationSessionBean |
| ← | REFER_TO | LoanScreeningSessionBean |

### ejb-jar.xml

#### 기본 정보

| 항목 | 값 |
| --- | --- |
| 이름 | ejb-jar.xml |
| 파일 | ejb-jar.xml |
| 종류 | - |
| 요약 | - |

#### 관계

| 방향 | 관계 | 대상 |
| --- | --- | --- |
| → | REFER_TO | DelinquencyBean |
| → | REFER_TO | DelinquencyLocal |
| → | REFER_TO | DelinquencyLocalHome |
| → | REFER_TO | DELINQUENCY |
| ← | REFER_TO | DebtCollectionSessionBean |
| ← | REFER_TO | DebtCollectionSessionBean |
| ← | REFER_TO | DebtCollectionSessionBean |
| ← | REFER_TO | DebtCollectionSessionBean |
| ← | REFER_TO | DebtCollectionSessionBean |
| ← | REFER_TO | DelinquencyMgmtSessionBean |
| ← | REFER_TO | DelinquencyMgmtSessionBean |
| ← | REFER_TO | DelinquencyMgmtSessionBean |
| ← | REFER_TO | DelinquencyMgmtSessionBean |
| ← | REFER_TO | DelinquencyMgmtSessionBean |
| ← | REFER_TO | DelinquencyMgmtSessionBean |

### ejb-jar.xml

#### 기본 정보

| 항목 | 값 |
| --- | --- |
| 이름 | ejb-jar.xml |
| 파일 | ejb-jar.xml |
| 종류 | - |
| 요약 | - |

#### 관계

| 방향 | 관계 | 대상 |
| --- | --- | --- |
| → | REFER_TO | RepaymentBean |
| → | REFER_TO | RepaymentLocal |
| → | REFER_TO | RepaymentLocalHome |
| → | REFER_TO | REPAYMENT |
| ← | REFER_TO | DebtCollectionSessionBean |
| ← | REFER_TO | DebtCollectionSessionBean |
| ← | REFER_TO | LoanLedgerSessionBean |
| ← | REFER_TO | LoanLedgerSessionBean |

### ejb-jar.xml

#### 기본 정보

| 항목 | 값 |
| --- | --- |
| 이름 | ejb-jar.xml |
| 파일 | ejb-jar.xml |
| 종류 | - |
| 요약 | - |

#### 관계

| 방향 | 관계 | 대상 |
| --- | --- | --- |
| → | REFER_TO | CreditRatingBean |
| → | REFER_TO | CreditRatingLocal |
| → | REFER_TO | CreditRatingLocalHome |
| → | REFER_TO | CREDIT_RATING_ENTITY |
| ← | REFER_TO | CreditRatingBean |
| ← | REFER_TO | CreditRatingBean |
| ← | REFER_TO | CreditRatingBean |
| ← | REFER_TO | CreditRatingBean |
| ← | REFER_TO | CreditRatingBean |
| ← | REFER_TO | CreditRatingBean |
| ← | REFER_TO | CreditRatingBean |
| ← | REFER_TO | LoanScreeningSessionBean |
| ← | REFER_TO | LoanScreeningSessionBean |
| ← | REFER_TO | LoanScreeningSessionBean |
| ← | REFER_TO | LoanScreeningSessionBean |

### ejb-jar.xml

#### 기본 정보

| 항목 | 값 |
| --- | --- |
| 이름 | ejb-jar.xml |
| 파일 | ejb-jar.xml |
| 종류 | - |
| 요약 | - |

#### 관계

| 방향 | 관계 | 대상 |
| --- | --- | --- |
| → | REFER_TO | LoanApplicationSession |
| → | REFER_TO | LoanApplicationSessionBean |
| → | REFER_TO | LoanApplicationSessionHome |
| ← | REFER_TO | LoanServlet |
| ← | REFER_TO | LoanServlet |
| ← | REFER_TO | LoanServlet |
| ← | REFER_TO | LoanServlet |
| ← | REFER_TO | LoanServlet |
| ← | REFER_TO | LoanApplicationSessionHome |
| ← | REFER_TO | LoanProcessSessionBean |
| ← | REFER_TO | LoanProcessSessionBean |
| ← | REFER_TO | LoanProcessSessionBean |
| ← | REFER_TO | LoanProcessSessionBean |

### ejb-jar.xml

#### 기본 정보

| 항목 | 값 |
| --- | --- |
| 이름 | ejb-jar.xml |
| 파일 | ejb-jar.xml |
| 종류 | - |
| 요약 | - |

#### 관계

| 방향 | 관계 | 대상 |
| --- | --- | --- |
| → | REFER_TO | LoanScreeningSession |
| → | REFER_TO | LoanScreeningSessionBean |
| → | REFER_TO | LoanScreeningSessionHome |
| ← | REFER_TO | LoanServlet |
| ← | REFER_TO | LoanServlet |
| ← | REFER_TO | LoanServlet |
| ← | REFER_TO | LoanProcessSessionBean |
| ← | REFER_TO | LoanScreeningSessionHome |

### ejb-jar.xml

#### 기본 정보

| 항목 | 값 |
| --- | --- |
| 이름 | ejb-jar.xml |
| 파일 | ejb-jar.xml |
| 종류 | - |
| 요약 | - |

#### 관계

| 방향 | 관계 | 대상 |
| --- | --- | --- |
| → | REFER_TO | LoanExecutionSession |
| → | REFER_TO | LoanExecutionSessionBean |
| → | REFER_TO | LoanExecutionSessionHome |
| ← | REFER_TO | LoanServlet |
| ← | REFER_TO | LoanServlet |
| ← | REFER_TO | LoanExecutionSessionHome |

### ejb-jar.xml

#### 기본 정보

| 항목 | 값 |
| --- | --- |
| 이름 | ejb-jar.xml |
| 파일 | ejb-jar.xml |
| 종류 | - |
| 요약 | - |

#### 관계

| 방향 | 관계 | 대상 |
| --- | --- | --- |
| → | REFER_TO | LoanLedgerSession |
| → | REFER_TO | LoanLedgerSessionBean |
| → | REFER_TO | LoanLedgerSessionHome |
| ← | REFER_TO | LoanServlet |
| ← | REFER_TO | LoanServlet |
| ← | REFER_TO | LoanServlet |
| ← | REFER_TO | LoanServlet |
| ← | REFER_TO | LoanLedgerSessionHome |

### ejb-jar.xml

#### 기본 정보

| 항목 | 값 |
| --- | --- |
| 이름 | ejb-jar.xml |
| 파일 | ejb-jar.xml |
| 종류 | - |
| 요약 | - |

#### 관계

| 방향 | 관계 | 대상 |
| --- | --- | --- |
| → | REFER_TO | DelinquencyMgmtSession |
| → | REFER_TO | DelinquencyMgmtSessionBean |
| → | REFER_TO | DelinquencyMgmtSessionHome |
| ← | REFER_TO | LoanServlet |
| ← | REFER_TO | LoanServlet |
| ← | REFER_TO | DelinquencyMgmtSessionHome |

### ejb-jar.xml

#### 기본 정보

| 항목 | 값 |
| --- | --- |
| 이름 | ejb-jar.xml |
| 파일 | ejb-jar.xml |
| 종류 | - |
| 요약 | - |

#### 관계

| 방향 | 관계 | 대상 |
| --- | --- | --- |
| → | REFER_TO | DebtCollectionSession |
| → | REFER_TO | DebtCollectionSessionBean |
| → | REFER_TO | DebtCollectionSessionHome |
| ← | REFER_TO | LoanServlet |
| ← | REFER_TO | LoanServlet |
| ← | REFER_TO | LoanServlet |
| ← | REFER_TO | LoanServlet |
| ← | REFER_TO | DebtCollectionSessionHome |

### ejb-jar.xml

#### 기본 정보

| 항목 | 값 |
| --- | --- |
| 이름 | ejb-jar.xml |
| 파일 | ejb-jar.xml |
| 종류 | - |
| 요약 | - |

#### 관계

| 방향 | 관계 | 대상 |
| --- | --- | --- |
| → | REFER_TO | LoanProcessSession |
| → | REFER_TO | LoanProcessSessionBean |
| → | REFER_TO | LoanProcessSessionHome |
| ← | REFER_TO | LoanProcessSessionHome |


## 6. 설정 파일 (NONTARGET)

설정 파일 없음.


## 7. 데이터베이스 스키마

### COLLATERAL

#### 테이블 정보

| 항목 | 값 |
| --- | --- |
| 이름 | COLLATERAL |
| 스키마 | public |
| 설명 | 대출 신청에 대해 제공되는 담보(유형, 감정가, LTV 등) 정보를 저장하는 담보 엔티티 테이블. |
| 엔티티명 | - |
| 매핑 타입 | - |
| 테이블 타입 | - |
| DB | postgres |

#### 컬럼

| 컬럼명 | 타입 | Nullable | PK | 설명 |
| --- | --- | --- | --- | --- |
| COLLATERAL_ID | - | True | - | 담보 엔티티의 기본키(PK)로 담보를 유일하게 식별하는 ID. |
| APPLICATION_ID | - | True | - | 담보가 연결된 대출 신청을 식별하는 신청 ID(참조 키로 사용 가능). |
| COLLATERAL_TYPE | - | True | - | 담보의 종류/유형을 나타내는 코드 또는 분류 값. |
| DESCRIPTION | - | True | - | 담보에 대한 설명(비고/상세 내역). |
| APPRAISED_VALUE | - | True | - | 담보 감정가액(평가 금액). |
| APPRAISAL_DATE | - | True | - | 담보 감정(평가) 수행 일자. |
| LTV_RATIO | - | True | - | 담보 대비 대출비율(LTV) 값. |
| REGISTRATION_STATUS | - | True | - | 담보 등록/등기 등 처리 상태를 나타내는 상태 값. |

#### FK 관계

| 관계 | 대상 | FK타입 | 신뢰도 | 근거 |
| --- | --- | --- | --- | --- |
| - | - | - | - | - |

### CREDIT_RATING_ENTITY

#### 테이블 정보

| 항목 | 값 |
| --- | --- |
| 이름 | CREDIT_RATING_ENTITY |
| 스키마 | public |
| 설명 | 대출/금융 업무에서 신용등급(credit rating) 관련 정보를 저장하는 엔티티 테이블(BMP). |
| 엔티티명 | - |
| 매핑 타입 | - |
| 테이블 타입 | - |
| DB | postgres |

#### 컬럼

| 컬럼명 | 타입 | Nullable | PK | 설명 |
| --- | --- | --- | --- | --- |
| - | - | - | - | - |

#### FK 관계

| 관계 | 대상 | FK타입 | 신뢰도 | 근거 |
| --- | --- | --- | --- | --- |
| - | - | - | - | - |

### CUSTOMER

#### 테이블 정보

| 항목 | 값 |
| --- | --- |
| 이름 | CUSTOMER |
| 스키마 | public |
| 설명 | 고객 기본정보를 관리하는 테이블(고객 식별자, 인적/연락처/소득/신용등급 등). |
| 엔티티명 | - |
| 매핑 타입 | - |
| 테이블 타입 | - |
| DB | postgres |

#### 컬럼

| 컬럼명 | 타입 | Nullable | PK | 설명 |
| --- | --- | --- | --- | --- |
| CUSTOMER_ID | - | True | - | 고객 식별자(PK). |
| CUSTOMER_NAME | - | True | - | 고객 성명. |
| RESIDENT_ID | - | True | - | 주민등록번호 등 고객 실명 식별번호. |
| CUSTOMER_TYPE | - | True | - | 고객 유형 코드(개인/법인 등). |
| ADDRESS | - | True | - | 고객 주소. |
| PHONE_NUMBER | - | True | - | 고객 전화번호. |
| EMAIL | - | True | - | 고객 이메일 주소. |
| ANNUAL_INCOME | - | True | - | 고객 연소득 금액. |
| EMPLOYER_NAME | - | True | - | 직장명/고용주명. |
| CREDIT_GRADE | - | True | - | 신용등급/신용평가 등급 코드. |
| REGISTRATION_DATE | - | True | - | 고객 등록일자. |

#### FK 관계

| 관계 | 대상 | FK타입 | 신뢰도 | 근거 |
| --- | --- | --- | --- | --- |
| - | - | - | - | - |

### DELINQUENCY

#### 테이블 정보

| 항목 | 값 |
| --- | --- |
| 이름 | DELINQUENCY |
| 스키마 | public |
| 설명 | 고객/원장(대출) 기준의 연체(Delinquency) 정보를 저장하는 엔티티 테이블이다. |
| 엔티티명 | - |
| 매핑 타입 | - |
| 테이블 타입 | - |
| DB | postgres |

#### 컬럼

| 컬럼명 | 타입 | Nullable | PK | 설명 |
| --- | --- | --- | --- | --- |
| DELINQUENCY_ID | - | True | - | 연체 정보의 PK 식별자이다. |
| LEDGER_ID | - | True | - | 연체가 발생한 원장(계정/대출원장) 식별자이다. |
| CUSTOMER_ID | - | True | - | 연체 대상 고객 식별자이다. |
| DELINQUENCY_START_DATE | - | True | - | 연체 시작 일자이다. |
| DELINQUENCY_AMOUNT | - | True | - | 연체 금액이다. |
| DELINQUENCY_DAYS | - | True | - | 연체 일수이다. |
| DELINQUENCY_GRADE | - | True | - | 연체 등급(구분) 코드이다. |
| PENALTY_RATE | - | True | - | 연체/지연에 대한 가산(벌과) 이자율이다. |
| PENALTY_AMOUNT | - | True | - | 연체/지연에 대한 가산(벌과) 금액이다. |
| STATUS | - | True | - | 연체 상태 코드(예: 진행/해소 등)이다. |
| RESOLUTION_DATE | - | True | - | 연체 해소(정리) 일자이다. |

#### FK 관계

| 관계 | 대상 | FK타입 | 신뢰도 | 근거 |
| --- | --- | --- | --- | --- |
| - | - | - | - | - |

### LOAN_APPLICATION

#### 테이블 정보

| 항목 | 값 |
| --- | --- |
| 이름 | LOAN_APPLICATION |
| 스키마 | public |
| 설명 | 대출 신청 정보를 저장하는 대출신청 마스터 테이블. |
| 엔티티명 | - |
| 매핑 타입 | - |
| 테이블 타입 | - |
| DB | postgres |

#### 컬럼

| 컬럼명 | 타입 | Nullable | PK | 설명 |
| --- | --- | --- | --- | --- |
| APPLICATION_ID | - | True | - | 대출 신청 식별자(PK). |
| CUSTOMER_ID | - | True | - | 대출 신청 고객 식별자. |
| APPLICATION_DATE | - | True | - | 대출 신청 일자. |
| REQUESTED_AMOUNT | - | True | - | 고객이 요청한 대출 금액. |
| LOAN_TYPE | - | True | - | 대출 유형 코드. |
| LOAN_PURPOSE | - | True | - | 대출 사용 목적. |
| TERM | - | True | - | 대출 기간(만기/상환기간). |
| INTEREST_RATE | - | True | - | 적용 이자율. |
| STATUS | - | True | - | 대출 신청 상태 코드. |
| SCREENING_RESULT | - | True | - | 심사 결과(승인/거절/보류 등). |
| SCREENING_DATE | - | True | - | 심사 처리 일자. |
| APPROVED_AMOUNT | - | True | - | 승인된 대출 금액. |
| APPROVER_EMPLOYEE_ID | - | True | - | 승인 처리 직원 식별자. |
| REMARKS | - | True | - | 비고/메모. |

#### FK 관계

| 관계 | 대상 | FK타입 | 신뢰도 | 근거 |
| --- | --- | --- | --- | --- |
| - | - | - | - | - |

### LOAN_LEDGER

#### 테이블 정보

| 항목 | 값 |
| --- | --- |
| 이름 | LOAN_LEDGER |
| 스키마 | public |
| 설명 | 대출 원장(대출 실행/상환/잔액 등) 정보를 저장하는 엔티티 테이블. |
| 엔티티명 | - |
| 매핑 타입 | - |
| 테이블 타입 | - |
| DB | postgres |

#### 컬럼

| 컬럼명 | 타입 | Nullable | PK | 설명 |
| --- | --- | --- | --- | --- |
| LEDGER_ID | - | True | - | 대출원장 식별자(PK). |
| APPLICATION_ID | - | True | - | 대출 신청 식별자(신청 건과의 연계 키). |
| CUSTOMER_ID | - | True | - | 고객 식별자(대출 고객 참조 키). |
| PRINCIPAL_AMOUNT | - | True | - | 대출 원금(최초 실행 금액). |
| OUTSTANDING_BALANCE | - | True | - | 현재 미상환 잔액(원금/잔여금). |
| INTEREST_RATE | - | True | - | 적용 이자율. |
| LOAN_START_DATE | - | True | - | 대출 시작일(실행일). |
| MATURITY_DATE | - | True | - | 만기일. |
| REPAYMENT_METHOD | - | True | - | 상환 방식(예: 원리금균등/원금균등/만기일시 등). |
| MONTHLY_PAYMENT | - | True | - | 월 납입금(월 상환액). |
| STATUS | - | True | - | 대출 상태 코드(진행/완료/연체 등). |
| LAST_REPAYMENT_DATE | - | True | - | 최근 상환일. |
| NEXT_REPAYMENT_DATE | - | True | - | 다음 상환 예정일. |

#### FK 관계

| 관계 | 대상 | FK타입 | 신뢰도 | 근거 |
| --- | --- | --- | --- | --- |
| - | - | - | - | - |

### REPAYMENT

#### 테이블 정보

| 항목 | 값 |
| --- | --- |
| 이름 | REPAYMENT |
| 스키마 | public |
| 설명 | 대출 상환(Repayment) 내역을 저장하는 엔티티 테이블. |
| 엔티티명 | - |
| 매핑 타입 | - |
| 테이블 타입 | - |
| DB | postgres |

#### 컬럼

| 컬럼명 | 타입 | Nullable | PK | 설명 |
| --- | --- | --- | --- | --- |
| REPAYMENT_ID | - | True | - | 상환 내역의 PK(상환 식별자). |
| LEDGER_ID | - | True | - | 상환이 연결된 원장/계정(ledger) 식별자. |
| REPAYMENT_DATE | - | True | - | 상환 일자. |
| PRINCIPAL_AMOUNT | - | True | - | 상환 원금 금액. |
| INTEREST_AMOUNT | - | True | - | 상환 이자 금액. |
| PENALTY_AMOUNT | - | True | - | 연체/페널티 금액. |
| TOTAL_AMOUNT | - | True | - | 총 상환 금액(원금+이자+페널티 등 합계). |
| REPAYMENT_TYPE | - | True | - | 상환 유형 코드. |
| TRANSACTION_ID | - | True | - | 상환과 연계된 거래(트랜잭션) 식별자. |

#### FK 관계

| 관계 | 대상 | FK타입 | 신뢰도 | 근거 |
| --- | --- | --- | --- | --- |
| - | - | - | - | - |


## 8. DB Link

| DB Link 이름 |
| --- |
| - |

## 9. 횡단 분석

### 9.1. 테이블 접근 매트릭스

| 테이블 | 엔티티 | 접근유형 |
| --- | --- | --- |
| COLLATERAL | LoanApplicationSessionBean | READ, WRITE |
| COLLATERAL | LoanScreeningSessionBean | READ |
| COLLATERAL | ejb-jar.xml | REFER |
| CREDIT_RATING_ENTITY | CreditRatingBean | READ |
| CREDIT_RATING_ENTITY | LoanScreeningSessionBean | READ |
| CREDIT_RATING_ENTITY | ejb-jar.xml | REFER |
| CUSTOMER | LoanProcessSessionBean | READ |
| CUSTOMER | ejb-jar.xml | REFER |
| DELINQUENCY | DebtCollectionSessionBean | READ, WRITE |
| DELINQUENCY | DelinquencyMgmtSessionBean | READ, WRITE |
| DELINQUENCY | ejb-jar.xml | REFER |
| LOAN_APPLICATION | LoanApplicationSessionBean | READ, WRITE |
| LOAN_APPLICATION | LoanExecutionSessionBean | READ, WRITE |
| LOAN_APPLICATION | LoanScreeningSessionBean | READ, WRITE |
| LOAN_APPLICATION | ejb-jar.xml | REFER |
| LOAN_LEDGER | DebtCollectionSessionBean | READ, WRITE |
| LOAN_LEDGER | DelinquencyMgmtSessionBean | READ, WRITE |
| LOAN_LEDGER | LoanExecutionSessionBean | READ, WRITE |
| LOAN_LEDGER | LoanLedgerSessionBean | READ, WRITE |
| LOAN_LEDGER | ejb-jar.xml | REFER |
| REPAYMENT | DebtCollectionSessionBean | READ, WRITE |
| REPAYMENT | LoanLedgerSessionBean | READ, WRITE |
| REPAYMENT | ejb-jar.xml | REFER |

### 9.2. 호출 체인

| 진입점 | 타입 |
| --- | --- |
| LoanServlet | CLASS |
| CollateralBean | CLASS |
| CreditRatingBean | CLASS |
| CustomerBean | CLASS |
| DelinquencyBean | CLASS |
| LoanApplicationBean | CLASS |
| LoanLedgerBean | CLASS |
| RepaymentBean | CLASS |
| DebtCollectionSessionBean | CLASS |
| DelinquencyMgmtSessionBean | CLASS |
| LoanApplicationSessionBean | CLASS |
| LoanExecutionSessionBean | CLASS |
| LoanLedgerSessionBean | CLASS |
| LoanProcessSessionBean | CLASS |
| LoanScreeningSessionBean | CLASS |

### 9.3. 구조 관계 전체 목록

| 관계 | 소스 | 대상 | 속성 |
| --- | --- | --- | --- |
| ASSOCIATION | LoanServlet | DebtCollectionSessionHome | source_member=init |
| ASSOCIATION | LoanServlet | DebtCollectionSessionHome | source_member=handleCollectionPayment |
| ASSOCIATION | LoanServlet | DelinquencyMgmtSessionHome | source_member=init |
| ASSOCIATION | LoanServlet | LoanApplicationSessionHome | source_member=handleSubmitApplication |
| ASSOCIATION | LoanServlet | LoanApplicationSessionHome | source_member=init |
| ASSOCIATION | LoanServlet | LoanApplicationSessionHome | source_member=handleCreateApplication |
| ASSOCIATION | LoanServlet | LoanApplicationSessionHome | source_member=handleGetApplication |
| ASSOCIATION | LoanServlet | LoanExecutionSessionHome | source_member=init |
| ASSOCIATION | LoanServlet | LoanLedgerSessionHome | source_member=init |
| ASSOCIATION | LoanServlet | LoanLedgerSessionHome | source_member=handleGetLedger |
| ASSOCIATION | LoanServlet | LoanScreeningSessionHome | source_member=init |
| ASSOCIATION | LoanServlet | LoanScreeningSessionHome | source_member=handlePerformScreening |
| DEPENDENCY | LoanServlet | DelinquencyDTO | source_member=handleGetDelinquencies, usage=cast |
| DEPENDENCY | LoanServlet | DelinquencyDTO | source_member=handleGetCollectionTargets, usage=cast |
| DEPENDENCY | LoanServlet | LoanApplicationDTO | source_member=handleGetApplications, usage=cast |
| DEPENDENCY | LoanServlet | LoanApplicationDTO | source_member=handleCreateApplication, usage=local_new |
| DEPENDENCY | LoanServlet | LoanApplicationDTO | source_member=handleGetApplication, usage=local_var |
| DEPENDENCY | LoanServlet | LoanLedgerDTO | source_member=handleExecuteLoan, usage=local_var |
| DEPENDENCY | LoanServlet | LoanLedgerDTO | source_member=handleGetLedger, usage=local_var |
| DEPENDENCY | LoanServlet | RepaymentDTO | source_member=handleProcessRepayment, usage=local_var |
| DEPENDENCY | LoanServlet | ScreeningResultDTO | source_member=handlePerformScreening, usage=local_var |
| DEPENDENCY | LoanServlet | DebtCollectionSession | source_member=handleCollectionPayment, usage=local_var |
| DEPENDENCY | LoanServlet | DelinquencyMgmtSession | source_member=handleGetDelinquencies, usage=local_var |
| DEPENDENCY | LoanServlet | LoanApplicationSession | source_member=handleSubmitApplication, usage=local_var |
| DEPENDENCY | LoanServlet | LoanApplicationSession | source_member=handleCreateApplication, usage=local_var |
| DEPENDENCY | LoanServlet | LoanApplicationSession | source_member=handleGetApplication, usage=local_var |
| DEPENDENCY | LoanServlet | LoanExecutionSession | source_member=handleExecuteLoan, usage=local_var |
| DEPENDENCY | LoanServlet | LoanLedgerSession | source_member=handleGetLedger, usage=local_var |
| DEPENDENCY | LoanServlet | LoanScreeningSession | source_member=handleApproveApplication, usage=local_var |
| DEPENDENCY | LoanServlet | LoanScreeningSession | source_member=handlePerformScreening, usage=local_var |
| DEPENDENCY | LoanServlet | LoanConstants | source_member=init, usage=field_call |
| DEPENDENCY | LoanServlet | ServiceLocator | source_member=init, usage=local_var |
| DEPENDENCY | LoanServlet | HttpServletResponse | source_member=handleSubmitApplication, usage=parameter |
| DEPENDENCY | LoanServlet | HttpServletResponse | source_member=handleInitiateCollection, usage=parameter |
| ASSOCIATION | CollateralBean | EntityContext | source_member=setEntityContext |
| ASSOCIATION | CollateralBean | EntityContext | source_member=unsetEntityContext |
| DEPENDENCY | CollateralBean | EntityContext | source_member=setEntityContext, usage=parameter |
| DEPENDENCY | CollateralLocalHome | CollateralLocal | source_member=findByPrimaryKey, usage=return |
| DEPENDENCY | CollateralLocalHome | CollateralLocal | source_member=create, usage=return |
| DEPENDENCY | CreditRatingBean | EntityContext | source_member=setEntityContext, usage=parameter |
| DEPENDENCY | CreditRatingLocalHome | CreditRatingLocal | source_member=create, usage=return |
| DEPENDENCY | CreditRatingLocalHome | CreditRatingLocal | source_member=findByPrimaryKey, usage=return |
| ASSOCIATION | CustomerBean | EntityContext | source_member=unsetEntityContext |
| DEPENDENCY | CustomerBean | EntityContext | source_member=setEntityContext, usage=parameter |
| DEPENDENCY | CustomerLocalHome | CustomerLocal | source_member=findByPrimaryKey, usage=return |
| DEPENDENCY | CustomerLocalHome | CustomerLocal | source_member=create, usage=return |
| ASSOCIATION | DelinquencyBean | EntityContext | source_member=unsetEntityContext |
| DEPENDENCY | DelinquencyBean | EntityContext | source_member=setEntityContext, usage=parameter |
| DEPENDENCY | DelinquencyLocalHome | DelinquencyLocal | source_member=create, usage=return |
| DEPENDENCY | DelinquencyLocalHome | DelinquencyLocal | source_member=findByPrimaryKey, usage=return |
| ASSOCIATION | LoanApplicationBean | EntityContext | source_member=setEntityContext |
| ASSOCIATION | LoanApplicationBean | EntityContext | source_member=unsetEntityContext |
| DEPENDENCY | LoanApplicationLocalHome | LoanApplicationLocal | source_member=findByPrimaryKey, usage=return |
| DEPENDENCY | LoanApplicationLocalHome | LoanApplicationLocal | source_member=create, usage=return |
| ASSOCIATION | LoanLedgerBean | EntityContext | source_member=unsetEntityContext |
| DEPENDENCY | LoanLedgerBean | EntityContext | source_member=setEntityContext, usage=parameter |
| DEPENDENCY | LoanLedgerLocalHome | LoanLedgerLocal | source_member=findByPrimaryKey, usage=return |
| DEPENDENCY | LoanLedgerLocalHome | LoanLedgerLocal | source_member=create, usage=return |
| ASSOCIATION | RepaymentBean | EntityContext | source_member=unsetEntityContext |
| DEPENDENCY | RepaymentBean | EntityContext | source_member=setEntityContext, usage=parameter |
| DEPENDENCY | RepaymentLocalHome | RepaymentLocal | source_member=findByPrimaryKey, usage=return |
| DEPENDENCY | DebtCollectionSession | DelinquencyDTO | source_member=getCollectionDetail, usage=return |
| DEPENDENCY | DebtCollectionSession | DelinquencyException | source_member=processCollectionPayment, usage=return |
| DEPENDENCY | DebtCollectionSession | DelinquencyException | source_member=writeOff, usage=parameter |
| DEPENDENCY | DebtCollectionSession | DelinquencyException | source_member=getCollectionDetail, usage=parameter |
| DEPENDENCY | DebtCollectionSession | DelinquencyException | source_member=initiateCollection, usage=parameter |
| DEPENDENCY | DebtCollectionSession | DelinquencyException | source_member=getWrittenOffLedgers, usage=parameter |
| DEPENDENCY | DebtCollectionSession | DelinquencyException | source_member=getCollectionTargets, usage=parameter |
| ASSOCIATION | DebtCollectionSessionBean | SessionContext | source_member=initiateCollection |
| DEPENDENCY | DebtCollectionSessionBean | DelinquencyDTO | source_member=delinquencyEntityToDTO, usage=local_new |
| DEPENDENCY | DebtCollectionSessionBean | LoanLedgerDTO | source_member=getWrittenOffLedgers, usage=local_new |
| DEPENDENCY | DebtCollectionSessionBean | DelinquencyLocal | source_member=delinquencyEntityToDTO, usage=parameter |
| DEPENDENCY | DebtCollectionSessionBean | DelinquencyLocal | source_member=processCollectionPayment, usage=local_var |
| DEPENDENCY | DebtCollectionSessionBean | DelinquencyLocal | source_member=delinquencyEntitiesToDTOs, usage=cast |
| DEPENDENCY | DebtCollectionSessionBean | DelinquencyLocalHome | source_member=getDelinquencyHome, usage=return |
| DEPENDENCY | DebtCollectionSessionBean | DelinquencyLocalHome | source_member=getCollectionTargets, usage=local_var |
| DEPENDENCY | DebtCollectionSessionBean | DelinquencyLocalHome | source_member=processCollectionPayment, usage=local_var |
| DEPENDENCY | DebtCollectionSessionBean | LoanLedgerLocal | source_member=writeOff, usage=local_var |
| DEPENDENCY | DebtCollectionSessionBean | LoanLedgerLocal | source_member=processCollectionPayment, usage=local_var |
| DEPENDENCY | DebtCollectionSessionBean | LoanLedgerLocalHome | source_member=getLoanLedgerHome, usage=return |
| DEPENDENCY | DebtCollectionSessionBean | LoanLedgerLocalHome | source_member=writeOff, usage=local_var |
| DEPENDENCY | DebtCollectionSessionBean | LoanLedgerLocalHome | source_member=processCollectionPayment, usage=local_var |
| DEPENDENCY | DebtCollectionSessionBean | RepaymentLocalHome | source_member=getRepaymentHome, usage=return |
| DEPENDENCY | DebtCollectionSessionBean | RepaymentLocalHome | source_member=processCollectionPayment, usage=local_var |
| DEPENDENCY | DebtCollectionSessionBean | DelinquencyException | source_member=getCollectionTargets, usage=local_new |
| DEPENDENCY | DebtCollectionSessionBean | DelinquencyException | source_member=processCollectionPayment, usage=local_new |
| DEPENDENCY | DebtCollectionSessionBean | LoanConstants | source_member=getLoanLedgerHome, usage=local_var |
| DEPENDENCY | DebtCollectionSessionBean | LoanConstants | source_member=isGrade3OrWorse, usage=local_var |
| DEPENDENCY | DebtCollectionSessionBean | LoanConstants | source_member=getRepaymentHome, usage=field_call |
| DEPENDENCY | DebtCollectionSessionBean | LoanConstants | source_member=getCollectionTargets, usage=field_call |
| DEPENDENCY | DebtCollectionSessionBean | LoanConstants | source_member=processCollectionPayment, usage=local_var |
| DEPENDENCY | DebtCollectionSessionBean | ServiceLocator | source_member=getLoanLedgerHome, usage=local_var |
| DEPENDENCY | DebtCollectionSessionBean | ServiceLocator | source_member=getRepaymentHome, usage=field_call |
| DEPENDENCY | DebtCollectionSessionBean | SessionContext | source_member=setSessionContext, usage=parameter |
| DEPENDENCY | DebtCollectionSessionHome | DebtCollectionSession | source_member=create, usage=return |
| DEPENDENCY | DelinquencyMgmtSession | DelinquencyDTO | source_member=registerDelinquency, usage=return |
| DEPENDENCY | DelinquencyMgmtSession | DelinquencyDTO | source_member=getDelinquency, usage=return |
| DEPENDENCY | DelinquencyMgmtSession | DelinquencyException | source_member=updateDelinquencyStatus, usage=parameter |
| DEPENDENCY | DelinquencyMgmtSession | DelinquencyException | source_member=registerDelinquency, usage=local_var |
| DEPENDENCY | DelinquencyMgmtSession | DelinquencyException | source_member=resolveDelinquency, usage=parameter |
| DEPENDENCY | DelinquencyMgmtSession | DelinquencyException | source_member=getDelinquency, usage=parameter |
| DEPENDENCY | DelinquencyMgmtSession | DelinquencyException | source_member=getActiveDelinquencies, usage=parameter |
| DEPENDENCY | DelinquencyMgmtSessionBean | DelinquencyDTO | source_member=getDelinquency, usage=return |
| DEPENDENCY | DelinquencyMgmtSessionBean | DelinquencyDTO | source_member=entityToDTO, usage=local_new |
| DEPENDENCY | DelinquencyMgmtSessionBean | DelinquencyLocal | source_member=getDelinquency, usage=local_var |
| DEPENDENCY | DelinquencyMgmtSessionBean | DelinquencyLocal | source_member=calculateTotalPenalty, usage=local_var |
| DEPENDENCY | DelinquencyMgmtSessionBean | DelinquencyLocal | source_member=entityToDTO, usage=parameter |
| DEPENDENCY | DelinquencyMgmtSessionBean | DelinquencyLocal | source_member=entitiesToDTOs, usage=cast |
| DEPENDENCY | DelinquencyMgmtSessionBean | DelinquencyLocalHome | source_member=getDelinquencyHome, usage=return |
| DEPENDENCY | DelinquencyMgmtSessionBean | DelinquencyLocalHome | source_member=getDelinquency, usage=local_var |
| DEPENDENCY | DelinquencyMgmtSessionBean | DelinquencyLocalHome | source_member=getDelinquenciesByCustomer, usage=local_var |
| DEPENDENCY | DelinquencyMgmtSessionBean | DelinquencyLocalHome | source_member=registerDelinquency, usage=local_var |
| DEPENDENCY | DelinquencyMgmtSessionBean | LoanLedgerLocal | source_member=resolveDelinquency, usage=local_var |
| DEPENDENCY | DelinquencyMgmtSessionBean | LoanLedgerLocal | source_member=registerDelinquency, usage=local_var |
| DEPENDENCY | DelinquencyMgmtSessionBean | LoanLedgerLocalHome | source_member=getLoanLedgerHome, usage=return |
| DEPENDENCY | DelinquencyMgmtSessionBean | LoanLedgerLocalHome | source_member=resolveDelinquency, usage=local_var |
| DEPENDENCY | DelinquencyMgmtSessionBean | LoanLedgerLocalHome | source_member=registerDelinquency, usage=local_var |
| DEPENDENCY | DelinquencyMgmtSessionBean | DelinquencyException | source_member=getDelinquenciesByCustomer, usage=local_new |
| DEPENDENCY | DelinquencyMgmtSessionBean | DelinquencyException | source_member=registerDelinquency, usage=return |
| DEPENDENCY | DelinquencyMgmtSessionBean | LoanConstants | source_member=getLoanLedgerHome, usage=local_var |
| DEPENDENCY | DelinquencyMgmtSessionBean | LoanConstants | source_member=getDelinquencyHome, usage=local_var |
| DEPENDENCY | DelinquencyMgmtSessionBean | LoanConstants | source_member=calculateTotalPenalty, usage=local_var |
| DEPENDENCY | DelinquencyMgmtSessionBean | LoanConstants | source_member=registerDelinquency, usage=local_var |
| DEPENDENCY | DelinquencyMgmtSessionBean | ServiceLocator | source_member=getLoanLedgerHome, usage=local_var |
| DEPENDENCY | DelinquencyMgmtSessionBean | ServiceLocator | source_member=getDelinquencyHome, usage=local_var |
| DEPENDENCY | DelinquencyMgmtSessionBean | SessionContext | source_member=setSessionContext, usage=parameter |
| DEPENDENCY | DelinquencyMgmtSessionHome | DelinquencyMgmtSession | source_member=create, usage=return |
| DEPENDENCY | LoanApplicationSession | CollateralDTO | source_member=registerCollateral, usage=parameter |
| DEPENDENCY | LoanApplicationSession | LoanApplicationDTO | source_member=createApplication, usage=parameter |
| DEPENDENCY | LoanApplicationSession | LoanApplicationDTO | source_member=updateApplication, usage=parameter |
| DEPENDENCY | LoanApplicationSession | LoanApplicationDTO | source_member=getApplication, usage=return |
| DEPENDENCY | LoanApplicationSession | LoanApplicationException | source_member=getAllApplications, usage=parameter |
| DEPENDENCY | LoanApplicationSession | LoanApplicationException | source_member=cancelApplication, usage=local_var |
| DEPENDENCY | LoanApplicationSession | LoanApplicationException | source_member=submitApplication, usage=local_var |
| DEPENDENCY | LoanApplicationSession | LoanApplicationException | source_member=getApplication, usage=parameter |
| DEPENDENCY | LoanApplicationSession | LoanApplicationException | source_member=getApplicationsByCustomer, usage=return |
| DEPENDENCY | LoanApplicationSession | LoanApplicationException | source_member=getApplicationsByStatus, usage=parameter |
| ASSOCIATION | LoanApplicationSessionBean | SessionContext | source_member=setSessionContext |
| DEPENDENCY | LoanApplicationSessionBean | CollateralDTO | source_member=registerCollateral, usage=parameter |
| DEPENDENCY | LoanApplicationSessionBean | LoanApplicationDTO | source_member=getApplication, usage=return |
| DEPENDENCY | LoanApplicationSessionBean | LoanApplicationDTO | source_member=updateApplication, usage=parameter |
| DEPENDENCY | LoanApplicationSessionBean | LoanApplicationDTO | source_member=createApplication, usage=parameter |
| DEPENDENCY | LoanApplicationSessionBean | CollateralLocalHome | source_member=registerCollateral, usage=cast |
| DEPENDENCY | LoanApplicationSessionBean | LoanApplicationLocal | source_member=entitiesToDTOs, usage=cast |
| DEPENDENCY | LoanApplicationSessionBean | LoanApplicationLocal | source_member=getApplication, usage=local_var |
| DEPENDENCY | LoanApplicationSessionBean | LoanApplicationLocal | source_member=submitApplication, usage=local_var |
| DEPENDENCY | LoanApplicationSessionBean | LoanApplicationLocal | source_member=updateApplication, usage=local_var |
| DEPENDENCY | LoanApplicationSessionBean | LoanApplicationLocal | source_member=createApplication, usage=local_var |
| DEPENDENCY | LoanApplicationSessionBean | LoanApplicationLocalHome | source_member=getLoanApplicationHome, usage=return |
| DEPENDENCY | LoanApplicationSessionBean | LoanApplicationLocalHome | source_member=getApplicationsByCustomer, usage=local_var |
| DEPENDENCY | LoanApplicationSessionBean | LoanApplicationLocalHome | source_member=submitApplication, usage=local_var |
| DEPENDENCY | LoanApplicationSessionBean | LoanApplicationLocalHome | source_member=updateApplication, usage=local_var |
| DEPENDENCY | LoanApplicationSessionBean | LoanApplicationLocalHome | source_member=getApplicationsByStatus, usage=local_var |
| DEPENDENCY | LoanApplicationSessionBean | LoanApplicationException | source_member=getApplicationsByCustomer, usage=return |
| DEPENDENCY | LoanApplicationSessionBean | LoanApplicationException | source_member=submitApplication, usage=local_new |
| DEPENDENCY | LoanApplicationSessionBean | LoanApplicationException | source_member=registerCollateral, usage=local_new |
| DEPENDENCY | LoanApplicationSessionBean | LoanApplicationException | source_member=getApplicationsByStatus, usage=local_new |
| DEPENDENCY | LoanApplicationSessionBean | LoanConstants | source_member=getLoanApplicationHome, usage=local_var |
| DEPENDENCY | LoanApplicationSessionBean | LoanConstants | source_member=submitApplication, usage=local_var |
| DEPENDENCY | LoanApplicationSessionBean | LoanConstants | source_member=registerCollateral, usage=local_var |
| DEPENDENCY | LoanApplicationSessionBean | LoanConstants | source_member=createApplication, usage=field_call |
| DEPENDENCY | LoanApplicationSessionBean | ServiceLocator | source_member=getLoanApplicationHome, usage=cast |
| DEPENDENCY | LoanApplicationSessionBean | ServiceLocator | source_member=registerCollateral, usage=local_var |
| DEPENDENCY | LoanApplicationSessionBean | SessionContext | source_member=setSessionContext, usage=parameter |
| DEPENDENCY | LoanApplicationSessionHome | LoanApplicationSession | source_member=create, usage=return |
| DEPENDENCY | LoanExecutionSession | LoanLedgerDTO | source_member=getLedger, usage=return |
| DEPENDENCY | LoanExecutionSession | LoanLedgerDTO | source_member=executeLoan, usage=return |
| DEPENDENCY | LoanExecutionSession | LoanExecutionException | source_member=getLedgersByCustomer, usage=parameter |
| DEPENDENCY | LoanExecutionSessionBean | LoanLedgerDTO | source_member=getLedger, usage=return |
| DEPENDENCY | LoanExecutionSessionBean | LoanLedgerDTO | source_member=ledgerEntityToDTO, usage=local_new |
| DEPENDENCY | LoanExecutionSessionBean | LoanLedgerDTO | source_member=executeLoan, usage=return |
| DEPENDENCY | LoanExecutionSessionBean | LoanApplicationLocal | source_member=executeLoan, usage=local_var |
| DEPENDENCY | LoanExecutionSessionBean | LoanApplicationLocalHome | source_member=getLoanApplicationHome, usage=return |
| DEPENDENCY | LoanExecutionSessionBean | LoanApplicationLocalHome | source_member=executeLoan, usage=local_var |
| DEPENDENCY | LoanExecutionSessionBean | LoanExecutionException | source_member=getLedgersByCustomer, usage=local_new |
| DEPENDENCY | LoanExecutionSessionBean | InterestCalculator | source_member=executeLoan, usage=local_var |
| DEPENDENCY | LoanExecutionSessionBean | LoanConstants | source_member=getLoanApplicationHome, usage=field_call |
| DEPENDENCY | LoanExecutionSessionBean | LoanConstants | source_member=getLedgersByCustomer, usage=local_var |
| DEPENDENCY | LoanExecutionSessionBean | LoanConstants | source_member=executeLoan, usage=local_var |
| DEPENDENCY | LoanExecutionSessionBean | ServiceLocator | source_member=getLoanApplicationHome, usage=cast |
| DEPENDENCY | LoanExecutionSessionBean | ServiceLocator | source_member=getLedgersByCustomer, usage=local_var |
| DEPENDENCY | LoanExecutionSessionBean | ServiceLocator | source_member=executeLoan, usage=local_var |
| DEPENDENCY | LoanExecutionSessionBean | SessionContext | source_member=setSessionContext, usage=parameter |
| DEPENDENCY | LoanExecutionSessionHome | LoanExecutionSession | source_member=create, usage=return |
| DEPENDENCY | LoanLedgerSession | LoanLedgerDTO | source_member=calculateRemainingSchedule, usage=return |
| DEPENDENCY | LoanLedgerSession | LoanLedgerDTO | source_member=getLedger, usage=return |
| DEPENDENCY | LoanLedgerSession | RepaymentDTO | source_member=processRepayment, usage=return |
| DEPENDENCY | LoanLedgerSession | LoanExecutionException | source_member=getLedgersByCustomer, usage=parameter |
| DEPENDENCY | LoanLedgerSession | LoanExecutionException | source_member=processRepayment, usage=parameter |
| DEPENDENCY | LoanLedgerSession | LoanExecutionException | source_member=getActiveLedgers, usage=parameter |
| DEPENDENCY | LoanLedgerSessionBean | LoanLedgerDTO | source_member=getLedger, usage=return |
| DEPENDENCY | LoanLedgerSessionBean | LoanLedgerDTO | source_member=entityToDTO, usage=local_new |
| DEPENDENCY | LoanLedgerSessionBean | LoanLedgerDTO | source_member=calculateRemainingSchedule, usage=return |
| DEPENDENCY | LoanLedgerSessionBean | RepaymentDTO | source_member=processRepayment, usage=return |
| DEPENDENCY | LoanLedgerSessionBean | LoanLedgerLocal | source_member=getLedger, usage=local_var |
| DEPENDENCY | LoanLedgerSessionBean | LoanLedgerLocal | source_member=closeLedger, usage=local_var |
| DEPENDENCY | LoanLedgerSessionBean | LoanLedgerLocal | source_member=entityToDTO, usage=parameter |
| DEPENDENCY | LoanLedgerSessionBean | LoanLedgerLocal | source_member=processRepayment, usage=local_var |
| DEPENDENCY | LoanLedgerSessionBean | LoanLedgerLocal | source_member=entitiesToDTOs, usage=cast |
| DEPENDENCY | LoanLedgerSessionBean | LoanLedgerLocalHome | source_member=getLoanLedgerHome, usage=return |
| DEPENDENCY | LoanLedgerSessionBean | LoanLedgerLocalHome | source_member=getLedger, usage=local_var |
| DEPENDENCY | LoanLedgerSessionBean | LoanLedgerLocalHome | source_member=getActiveLedgers, usage=local_var |
| DEPENDENCY | LoanLedgerSessionBean | LoanLedgerLocalHome | source_member=processRepayment, usage=local_var |
| DEPENDENCY | LoanLedgerSessionBean | LoanLedgerLocalHome | source_member=calculateRemainingSchedule, usage=local_var |
| DEPENDENCY | LoanLedgerSessionBean | RepaymentLocal | source_member=processRepayment, usage=local_var |
| DEPENDENCY | LoanLedgerSessionBean | RepaymentLocalHome | source_member=getRepaymentHome, usage=return |
| DEPENDENCY | LoanLedgerSessionBean | RepaymentLocalHome | source_member=processRepayment, usage=local_var |
| DEPENDENCY | LoanLedgerSessionBean | LoanExecutionException | source_member=getLedger, usage=return |
| DEPENDENCY | LoanLedgerSessionBean | LoanExecutionException | source_member=getActiveLedgers, usage=local_new |
| DEPENDENCY | LoanLedgerSessionBean | LoanExecutionException | source_member=processRepayment, usage=local_var |
| DEPENDENCY | LoanLedgerSessionBean | LoanExecutionException | source_member=calculateRemainingSchedule, usage=local_new |
| DEPENDENCY | LoanLedgerSessionBean | InterestCalculator | source_member=calculateRemainingSchedule, usage=local_var |
| DEPENDENCY | LoanLedgerSessionBean | LoanConstants | source_member=getLoanLedgerHome, usage=local_var |
| DEPENDENCY | LoanLedgerSessionBean | LoanConstants | source_member=getRepaymentHome, usage=cast |
| DEPENDENCY | LoanLedgerSessionBean | LoanConstants | source_member=getActiveLedgers, usage=field_call |
| DEPENDENCY | LoanLedgerSessionBean | ServiceLocator | source_member=getLoanLedgerHome, usage=local_var |
| DEPENDENCY | LoanLedgerSessionBean | ServiceLocator | source_member=getRepaymentHome, usage=cast |
| DEPENDENCY | LoanLedgerSessionBean | SessionContext | source_member=setSessionContext, usage=parameter |
| DEPENDENCY | LoanLedgerSessionHome | LoanLedgerSession | source_member=create, usage=return |
| DEPENDENCY | LoanProcessSession | LoanApplicationDTO | source_member=getCurrentApplicationStatus, usage=return |
| DEPENDENCY | LoanProcessSession | LoanApplicationDTO | source_member=submitAndGetResult, usage=return |
| DEPENDENCY | LoanProcessSession | ScreeningResultDTO | source_member=requestScreening, usage=return |
| DEPENDENCY | LoanProcessSession | LoanApplicationException | source_member=addCollateral, usage=parameter |
| DEPENDENCY | LoanProcessSession | LoanApplicationException | source_member=cancelProcess, usage=parameter |
| DEPENDENCY | LoanProcessSession | LoanApplicationException | source_member=getCurrentApplicationStatus, usage=parameter |
| DEPENDENCY | LoanProcessSession | LoanApplicationException | source_member=initializeProcess, usage=parameter |
| DEPENDENCY | LoanProcessSession | LoanApplicationException | source_member=setLoanDetails, usage=parameter |
| DEPENDENCY | LoanProcessSession | LoanScreeningException | source_member=requestScreening, usage=local_var |
| DEPENDENCY | LoanProcessSessionBean | CollateralDTO | source_member=requestScreening, usage=cast |
| DEPENDENCY | LoanProcessSessionBean | LoanApplicationDTO | source_member=getCurrentApplicationStatus, usage=return |
| DEPENDENCY | LoanProcessSessionBean | LoanApplicationDTO | source_member=submitAndGetResult, usage=return |
| DEPENDENCY | LoanProcessSessionBean | ScreeningResultDTO | source_member=requestScreening, usage=return |
| DEPENDENCY | LoanProcessSessionBean | CustomerLocalHome | source_member=getCustomerHome, usage=return |
| DEPENDENCY | LoanProcessSessionBean | CustomerLocalHome | source_member=initializeProcess, usage=local_var |
| DEPENDENCY | LoanProcessSessionBean | LoanApplicationException | source_member=setLoanDetails, usage=local_new |
| DEPENDENCY | LoanProcessSessionBean | LoanApplicationException | source_member=addCollateral, usage=local_new |
| DEPENDENCY | LoanProcessSessionBean | LoanApplicationException | source_member=cancelProcess, usage=return |
| DEPENDENCY | LoanProcessSessionBean | LoanApplicationException | source_member=submitAndGetResult, usage=local_new |
| DEPENDENCY | LoanProcessSessionBean | LoanScreeningException | source_member=requestScreening, usage=local_var |
| DEPENDENCY | LoanProcessSessionBean | LoanApplicationSession | source_member=cancelProcess, usage=local_var |
| DEPENDENCY | LoanProcessSessionBean | LoanApplicationSession | source_member=submitAndGetResult, usage=local_var |
| DEPENDENCY | LoanProcessSessionBean | LoanApplicationSessionHome | source_member=cancelProcess, usage=local_var |
| DEPENDENCY | LoanProcessSessionBean | LoanApplicationSessionHome | source_member=submitAndGetResult, usage=local_var |
| DEPENDENCY | LoanProcessSessionBean | LoanScreeningSession | source_member=requestScreening, usage=local_var |
| DEPENDENCY | LoanProcessSessionBean | LoanScreeningSessionHome | source_member=requestScreening, usage=cast |
| DEPENDENCY | LoanProcessSessionBean | LoanConstants | source_member=getCustomerHome, usage=local_var |
| DEPENDENCY | LoanProcessSessionBean | LoanConstants | source_member=cancelProcess, usage=field_call |
| DEPENDENCY | LoanProcessSessionBean | LoanConstants | source_member=submitAndGetResult, usage=local_var |
| DEPENDENCY | LoanProcessSessionBean | ServiceLocator | source_member=getCustomerHome, usage=local_var |
| DEPENDENCY | LoanProcessSessionBean | ServiceLocator | source_member=cancelProcess, usage=local_var |
| DEPENDENCY | LoanProcessSessionBean | ServiceLocator | source_member=submitAndGetResult, usage=local_var |
| DEPENDENCY | LoanProcessSessionBean | SessionContext | source_member=setSessionContext, usage=parameter |
| COMPOSITION | LoanProcessSessionBean | CollateralDTO | source_member=addCollateral |
| DEPENDENCY | LoanProcessSessionHome | LoanProcessSession | source_member=create, usage=return |
| DEPENDENCY | LoanScreeningSession | ScreeningResultDTO | source_member=getCreditScreening, usage=return |
| DEPENDENCY | LoanScreeningSession | ScreeningResultDTO | source_member=performScreening, usage=return |
| DEPENDENCY | LoanScreeningSession | LoanScreeningException | source_member=approveApplication, usage=parameter |
| DEPENDENCY | LoanScreeningSession | LoanScreeningException | source_member=rejectApplication, usage=local_var |
| ASSOCIATION | LoanScreeningSessionBean | SessionContext | source_member=setSessionContext |
| DEPENDENCY | LoanScreeningSessionBean | ScreeningResultDTO | source_member=getCreditScreening, usage=return |
| DEPENDENCY | LoanScreeningSessionBean | CollateralLocal | source_member=calculateLtvRatio, usage=cast |
| DEPENDENCY | LoanScreeningSessionBean | CollateralLocalHome | source_member=calculateLtvRatio, usage=local_var |
| DEPENDENCY | LoanScreeningSessionBean | CreditRatingLocal | source_member=findLatestValidCreditRating, usage=return |
| DEPENDENCY | LoanScreeningSessionBean | CreditRatingLocal | source_member=getCreditScreening, usage=local_var |
| DEPENDENCY | LoanScreeningSessionBean | CreditRatingLocalHome | source_member=getCreditRatingHome, usage=return |
| DEPENDENCY | LoanScreeningSessionBean | CreditRatingLocalHome | source_member=findLatestValidCreditRating, usage=local_var |
| DEPENDENCY | LoanScreeningSessionBean | LoanApplicationLocal | source_member=rejectApplication, usage=local_var |
| DEPENDENCY | LoanScreeningSessionBean | LoanApplicationLocal | source_member=performScreening, usage=local_var |
| DEPENDENCY | LoanScreeningSessionBean | LoanApplicationLocalHome | source_member=rejectApplication, usage=local_var |
| DEPENDENCY | LoanScreeningSessionBean | LoanApplicationLocalHome | source_member=performScreening, usage=local_var |
| DEPENDENCY | LoanScreeningSessionBean | LoanApplicationLocalHome | source_member=getLoanApplicationHome, usage=return |
| DEPENDENCY | LoanScreeningSessionBean | LoanScreeningException | source_member=rejectApplication, usage=local_new |
| DEPENDENCY | LoanScreeningSessionBean | LoanScreeningException | source_member=getCreditScreening, usage=local_new |
| DEPENDENCY | LoanScreeningSessionBean | InterestCalculator | source_member=calculateLtvRatio, usage=field_call |
| DEPENDENCY | LoanScreeningSessionBean | LoanConstants | source_member=getCreditRatingHome, usage=local_var |
| DEPENDENCY | LoanScreeningSessionBean | LoanConstants | source_member=getLoanApplicationHome, usage=local_var |
| DEPENDENCY | LoanScreeningSessionBean | LoanConstants | source_member=calculateLtvRatio, usage=field_call |
| DEPENDENCY | LoanScreeningSessionBean | LoanConstants | source_member=rejectApplication, usage=local_var |
| DEPENDENCY | LoanScreeningSessionBean | LoanConstants | source_member=performScreening, usage=local_var |
| DEPENDENCY | LoanScreeningSessionBean | ServiceLocator | source_member=getCreditRatingHome, usage=local_var |
| DEPENDENCY | LoanScreeningSessionBean | ServiceLocator | source_member=getLoanApplicationHome, usage=local_var |
| DEPENDENCY | LoanScreeningSessionBean | ServiceLocator | source_member=calculateLtvRatio, usage=field_call |
| DEPENDENCY | LoanScreeningSessionBean | SessionContext | source_member=setSessionContext, usage=parameter |
| DEPENDENCY | LoanScreeningSessionHome | LoanScreeningSession | source_member=create, usage=return |
| DEPENDENCY | ServiceLocator | EJBLocalHome | source_member=getLocalHome, usage=return |

### 9.4. ETL 데이터 흐름

| 관계 | 소스 | 대상 |
| --- | --- | --- |
| - | - | - |