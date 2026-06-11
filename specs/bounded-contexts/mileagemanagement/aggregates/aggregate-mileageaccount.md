# Aggregate Design Spec: MileageAccount

> Bounded Context: **MileageManagement** · Generated: 2026-06-02T00:00:00Z
> CHG-009: VIP/일반 회원 마일리지 차등 적립

## Description

회원별 마일리지 계좌를 표현하는 집합체. 잔액·이력·등급 정보를 보관하고 적립/사용/소멸 트랜잭션의 진입점 역할을 한다.
**CHG-009**: `memberGrade` 속성을 추가하여 MembershipManagement로부터 동기화된 회원 등급 정보를 보관하고, 적립 시 차등 비율 계산의 기준으로 사용한다.

## Aggregate Root

`MileageAccount`

## Member Entities & Value Objects

- `MileageAccountId` *(identifier — value object — primary key)*
- `MemberGrade` *(value object — VIP / REGULAR, CHG-009 추가)*
- `AccumulationRateSnapshot` *(value object — 마지막 동기화 시점의 적립률, CHG-009 추가)*

## Properties

| Field | Type | Mutability | Description |
|---|---|---|---|
| `id` | `UUID` | immutable after creation | 마일리지 계좌 ID |
| `memberId` | `UUID` | immutable after creation | 연결된 회원 ID |
| `memberGrade` | `MemberGrade` | mutable through commands only | **[CHG-009]** 회원 등급 (VIP/REGULAR) — MemberGradeUpdated 이벤트로 동기화 |
| `gradeUpdatedAt` | `DateTime` | mutable through commands only | **[CHG-009]** 회원 등급 마지막 동기화 일시 |
| `currentBalance` | `Long` | mutable through commands only | 현재 마일리지 잔액 |
| `totalAccumulated` | `Long` | mutable through commands only | 누적 적립 합계 |
| `totalUsed` | `Long` | mutable through commands only | 누적 사용 합계 |
| `totalExpired` | `Long` | mutable through commands only | 누적 소멸 합계 |
| `status` | `String` | mutable through commands only | 계좌 상태 (ACTIVE / SUSPENDED / CLOSED) |
| `createdAt` | `DateTime` | immutable after creation | 계좌 생성 일시 |

## Enforced Invariants

1. **[CHG-009]** `memberGrade`는 반드시 VIP 또는 REGULAR 중 하나여야 한다
2. **[CHG-009]** 적립 시 사용되는 `accumulationRate`는 `memberGrade` 기준 정책값과 일치해야 한다
3. `currentBalance`는 음수가 될 수 없다 (`currentBalance = totalAccumulated - totalUsed - totalExpired`)
4. `status`가 ACTIVE가 아니면 적립·사용이 불가하다
5. `memberId`는 null이 될 수 없다

## Corrective Policies (CHG-009 추가)

- **SyncMemberGradeOnGradeChanged** — MembershipManagement에서 `MemberGradeUpdated` 이벤트 수신 시 `UpdateMemberGrade` 커맨드를 실행하여 `memberGrade`와 `gradeUpdatedAt`을 최신화한다

## Commands

| Command | Preconditions | Postconditions | Events emitted |
|---|---|---|---|
| `OpenMileageAccount` | memberId 존재, 계좌 미존재 | 계좌 생성됨, memberGrade 초기화됨 | `MileageAccountOpened` |
| `UpdateMemberGrade` | **[CHG-009]** 유효한 MemberGrade | memberGrade·gradeUpdatedAt 갱신됨 | `MemberGradeUpdatedInMileage` |
| `AccumulateMileage` | status=ACTIVE, 등급 확인됨 | balance 증가, 등급별 적립률 적용됨 | `MileageAccumulatedToAccount` |
| `UseMileage` | status=ACTIVE, balance >= 사용금액 | balance 감소됨 | `MileageUsedFromAccount` |
| `ExpireMileage` | 만료 대상 마일리지 존재 | balance 감소, expired 증가 | `MileageExpiredFromAccount` |
| `SuspendMileageAccount` | status=ACTIVE | status=SUSPENDED | `MileageAccountSuspended` |
| `CloseMileageAccount` | status=ACTIVE 또는 SUSPENDED | status=CLOSED | `MileageAccountClosed` |

## Domain Events Emitted

- `MileageAccountOpened` — 새 마일리지 계좌가 개설되었다. 초기 회원 등급 포함.
- `MemberGradeUpdatedInMileage` — **[CHG-009]** MembershipManagement로부터 수신된 회원 등급 변경이 마일리지 계좌에 반영되었다.
- `MileageAccumulatedToAccount` — **[CHG-009]** 회원 등급별 차등 적립률이 적용되어 마일리지가 계좌에 적립되었다.
- `MileageUsedFromAccount` — 마일리지가 계좌에서 사용되었다.
- `MileageExpiredFromAccount` — 만료된 마일리지가 소멸되었다.
- `MileageAccountSuspended` — 마일리지 계좌가 정지되었다.
- `MileageAccountClosed` — 마일리지 계좌가 해지되었다.

## Repository Interface

```python
class MileageAccountRepository(Protocol):
    def get(self, id: "MileageAccountId") -> "MileageAccount": ...
    def get_by_member(self, member_id: "UUID") -> "MileageAccount": ...
    def save(self, aggregate: "MileageAccount") -> None: ...
    # Command: OpenMileageAccount
    # Command: UpdateMemberGrade  [CHG-009]
    # Command: AccumulateMileage
    # Command: UseMileage
    # Command: ExpireMileage
    # Command: SuspendMileageAccount
    # Command: CloseMileageAccount
```

## Open Decisions

- 회원 등급 동기화 지연(Eventually Consistent) 허용 범위 결정 필요
- 등급 변경 전 적립된 마일리지에 대한 소급 정산 정책 결정 필요 (현재: 소급 미적용)
