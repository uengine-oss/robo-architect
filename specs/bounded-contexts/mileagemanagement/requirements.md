# Requirements: MileageManagement

> User Stories with EARS acceptance criteria.
>
> Generated: 2026-06-02T00:00:00Z
> CHG-009: VIP/일반 회원 마일리지 차등 적립

---

## Feature: 마일리지_적립

> **CHG-009**: 마일리지 적립 정책이 회원 등급(VIP/일반)에 따라 분기되어야 함.
> VIP 회원: 구매/이벤트 기준금액의 2% 적립 / 일반 회원: 1% 적립

---

## Aggregate: MileageAccount

### 회원: 상품을 구매하여 마일리지를 적립한다

As a 회원, I want to 상품을 구매하여 마일리지를 적립한다, so that 구매 금액에 비례한 마일리지 혜택을 받아 재구매 시 활용할 수 있도록

**Acceptance Criteria.**

1. the system SHALL 회원의 구매 완료 이벤트 수신 시 마일리지 적립을 자동으로 처리한다
2. **[CHG-009]** the system SHALL VIP 회원의 경우 구매 금액의 2%를 마일리지로 적립한다
3. **[CHG-009]** the system SHALL 일반 회원의 경우 구매 금액의 1%를 마일리지로 적립한다
4. **[CHG-009]** the system SHALL 적립 시점의 회원 등급을 기준으로 적립률을 결정하며, 이후 등급 변경 시 소급 적용하지 않는다
5. **[CHG-009]** the system SHALL 적립 내역에 회원 등급(VIP/일반)과 적용된 적립률을 함께 기록한다
6. the system SHALL 마일리지 적립 후 회원의 마일리지 계좌 잔액이 갱신된다
7. the system SHALL 마일리지 적립 완료 시 적립 내역 알림을 회원에게 발송한다
8. the system SHALL 구매 취소 시 적립된 마일리지를 회수한다
9. the system SHALL 적립 오류 시 재처리 큐에 등록하고 운영자에게 알린다


### 회원: 이벤트 참여로 마일리지를 적립한다

As a 회원, I want to 이벤트 참여로 마일리지를 적립한다, so that 이벤트 참여를 통해 추가 마일리지 혜택을 받을 수 있도록

**Acceptance Criteria.**

1. the system SHALL 이벤트 참여 완료 시 해당 이벤트의 기준 보상 금액을 기반으로 마일리지를 적립한다
2. **[CHG-009]** the system SHALL VIP 회원의 경우 이벤트 기준 보상 금액의 2%를 마일리지로 적립한다
3. **[CHG-009]** the system SHALL 일반 회원의 경우 이벤트 기준 보상 금액의 1%를 마일리지로 적립한다
4. **[CHG-009]** the system SHALL 이벤트 참여 마일리지 적립에도 상품 구매 마일리지와 동일한 등급별 차등 정책이 적용된다
5. **[CHG-009]** the system SHALL 이벤트 적립 내역에 회원 등급(VIP/일반)과 적용 적립률이 기록된다
6. the system SHALL 이벤트 참여 조건이 충족된 경우에만 마일리지를 적립한다
7. the system SHALL 이벤트 기간 외 참여 시 마일리지가 적립되지 않는다
8. the system SHALL 중복 참여 방지 정책에 따라 동일 이벤트 중복 적립을 방지한다


### 회원: 마일리지 적립 내역을 조회한다

As a 회원, I want to 마일리지 적립 내역을 조회한다, so that 내 마일리지 적립 이력과 등급별 혜택을 확인할 수 있도록

**Acceptance Criteria.**

1. the system SHALL 회원의 마일리지 적립·사용·소멸 내역을 목록으로 제공한다
2. **[CHG-009]** the system SHALL 각 내역에 적립 시점의 회원 등급(VIP/일반)과 적용된 적립률을 표시한다
3. the system SHALL 발생 일시, 원천 유형(구매/이벤트), 금액 기준, 마일리지 금액을 포함한다
4. the system SHALL 조회 기간 필터를 지원한다


### 회원: 마일리지를 사용한다

As a 회원, I want to 마일리지를 사용한다, so that 적립된 마일리지를 구매 대금 일부로 활용할 수 있도록

**Acceptance Criteria.**

1. the system SHALL 현재 마일리지 잔액 이내에서만 사용할 수 있다
2. the system SHALL 마일리지 사용 후 잔액이 즉시 갱신된다
3. the system SHALL 마일리지 사용 내역이 저장된다
4. the system SHALL 최소 사용 단위 정책이 적용된다


---

## Aggregate: Mileage

### 시스템: 마일리지 적립률 정책을 관리한다

As a 운영자, I want to 마일리지 적립률 정책을 관리한다, so that 회원 등급별 마일리지 적립 비율을 유연하게 조정할 수 있도록

**Acceptance Criteria.**

1. **[CHG-009]** the system SHALL VIP 회원 적립률과 일반 회원 적립률을 각각 독립적으로 설정할 수 있다
2. **[CHG-009]** the system SHALL 적립률 변경 이력이 저장되어 감사 추적이 가능하다
3. **[CHG-009]** the system SHALL 적립률 변경은 변경 이후 신규 적립 트랜잭션에만 적용된다 (소급 적용 없음)
4. the system SHALL 적립률은 0% 초과 100% 이하의 값이어야 한다


---

## Context Integration: 회원 등급 동기화 (CHG-009)

### 시스템: MembershipManagement로부터 회원 등급 변경을 수신한다

As a 시스템, I want to MembershipManagement로부터 회원 등급 변경을 수신한다, so that 마일리지 계좌의 회원 등급 정보를 항상 최신 상태로 유지하여 올바른 적립률을 적용하기 위해

**Acceptance Criteria.**

1. **[CHG-009]** the system SHALL MembershipManagement에서 `MemberGradeUpdated` 이벤트 수신 시 해당 회원의 MileageAccount.memberGrade를 갱신한다
2. **[CHG-009]** the system SHALL 등급 변경 전 이미 적립된 마일리지는 변경되지 않는다
3. **[CHG-009]** the system SHALL 이벤트 처리 실패 시 재처리 메커니즘이 동작한다
4. **[CHG-009]** the system SHALL 등급 동기화 이력이 `gradeUpdatedAt`으로 기록된다
