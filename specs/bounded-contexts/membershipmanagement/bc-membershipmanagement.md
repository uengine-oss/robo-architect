# Bounded Context Canvas: MembershipManagement

> Generated: 2026-05-12T11:55:59Z
> Last updated: 2026-06-02T00:00:00Z — CHG-009: VIP/일반 회원 마일리지 차등 적립

## Purpose

Handles the full lifecycle of membership including registration, status management (active, dormant, withdrawn), login, rejoin, dormant/reactivation, and withdrawal processes. Owns member status, account state transitions, and core membership data.
**[CHG-009]** 회원 등급(VIP/일반) 정보의 원천(Source of Truth)을 소유하며, 등급 변경 시 `MemberGradeUpdated` 이벤트를 발행하여 MileageManagement에 전파한다.

## Strategic Classification


- **Domain Type.** (not modeled — confirm)
- **Business Model.** (not modeled — confirm)
- **Evolution.** (not modeled — confirm)


## Inbound Communication


| From context | Channel | Message | Pattern |
|---|---|---|---|
| TermsAndAuthenticationManagement | Event bus | HighRiskActionAuthenticationSucceeded | Customer-Supplier *(inferred — confirm)* |
| TermsAndAuthenticationManagement | Event bus | TermsReconsented | Customer-Supplier *(inferred — confirm)* |



## Outbound Communication


| To context | Channel | Message | Pattern |
|---|---|---|---|
| TermsAndAuthenticationManagement | Event bus | MembershipWithdrawalRequested | Customer-Supplier *(inferred — confirm)* |
| TermsAndAuthenticationManagement | Event bus | MemberAccountCreated | Customer-Supplier *(inferred — confirm)* |
| LegalConsentManagement | Event bus | MemberAccountCreated | Customer-Supplier *(inferred — confirm)* |
| TermsAndAuthenticationManagement | Event bus | MembershipWithdrawn | Customer-Supplier *(inferred — confirm)* |
| **MileageManagement** | **Event bus** | **MemberGradeUpdated** | **Customer-Supplier — [CHG-009]** 회원 등급 변경 시 마일리지 적립률 동기화를 위해 발행 |
| **MileageManagement** | **ACL (Query)** | **GetMemberGrade** | **Customer-Supplier — [CHG-009]** MileageManagement가 실시간 등급 조회 시 제공하는 API |



## Ubiquitous Language (summary)

See [`domain-terms.md`](./domain-terms.md) for the full glossary. Key terms in this BC:

- `MemberAccount`
- `MemberaccountId`
- `MemberGrade` — **[CHG-009]** 회원 등급 (VIP / REGULAR). 마일리지 차등 적립의 기준이 되는 값.


## Business Decisions

- **[CHG-009]** 회원 등급(VIP/일반) 결정 및 변경 권한은 MembershipManagement BC에 있다
- **[CHG-009]** 신규 가입 회원의 초기 등급은 REGULAR(일반)이다
- **[CHG-009]** 등급 변경 시 MileageManagement에 이벤트(`MemberGradeUpdated`)를 발행해야 한다

## Assumptions

_(not modeled — confirm)_

## External Integrations


_No external-system integrations modeled for this BC._

