# Bounded Context Canvas: MileageManagement

> Generated: 2026-06-02T00:00:00Z
> CHG-009: VIP/일반 회원 마일리지 차등 적립

## Purpose

마일리지의 적립·사용·소멸·조회 등 마일리지 전 생애주기를 관리한다.
회원 등급(VIP/일반)에 따라 차등 적립 비율을 적용하며, MembershipManagement로부터 회원 등급 정보를 수신하여 적립 정책에 반영한다.

## Strategic Classification

- **Domain Type.** Supporting Domain
- **Business Model.** 고객 충성도 강화 및 재구매 촉진
- **Evolution.** Custom Built

## Inbound Communication

| From context | Channel | Message | Pattern |
|---|---|---|---|
| MembershipManagement | Event bus | MemberGradeUpdated | Customer-Supplier |
| MembershipManagement | ACL (Anti-Corruption Layer) | GetMemberGrade (Query) | Customer-Supplier |

> **CHG-009**: MembershipManagement가 회원 등급(VIP/일반) 변경 이벤트(`MemberGradeUpdated`)를 발행하고, MileageManagement는 이를 구독하여 내부 적립 비율 정책에 반영한다. 실시간 조회가 필요한 경우 ACL을 통해 등급 정보를 직접 조회한다.

## Outbound Communication

| To context | Channel | Message | Pattern |
|---|---|---|---|
| MembershipManagement | Event bus | MileageAccumulated | Customer-Supplier |
| MembershipManagement | Event bus | MileageUsed | Customer-Supplier |

## Ubiquitous Language (summary)

See [`domain-terms.md`](./domain-terms.md) for the full glossary. Key terms in this BC:

- `MileageAccount` — 회원별 마일리지 계좌; 잔액·이력·등급적립비율을 보관
- `Mileage` — 적립·사용·소멸되는 마일리지 단위 집합체
- `MemberGrade` — 회원 등급 (VIP / REGULAR)
- `AccumulationRate` — 등급별 적립 비율 (VIP: 2%, REGULAR: 1% 기본값)

## Business Decisions

- VIP 회원 기본 적립률: 구매 금액의 2%
- 일반 회원 기본 적립률: 구매 금액의 1%
- 이벤트 참여 마일리지도 동일한 차등 정책 적용
- 적립률은 관리자 정책으로 변경 가능 (MileageAccumulationPolicy)

## Assumptions

- 회원 등급 정보의 원천(Single Source of Truth)은 MembershipManagement BC이다
- MileageManagement는 등급 정보를 로컬 캐시(MileageAccount.memberGrade)로 보관하며 `MemberGradeUpdated` 이벤트로 동기화한다

## External Integrations

_No external-system integrations modeled for this BC._
