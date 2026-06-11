# Aggregate Design Spec: Mileage

> Bounded Context: **MileageManagement** · Generated: 2026-06-02T00:00:00Z
> CHG-009: VIP/일반 회원 마일리지 차등 적립

## Description

마일리지 적립·사용·소멸의 단위 트랜잭션을 표현하는 집합체.
**CHG-009**: 회원 등급(VIP/일반)에 따라 적립 비율이 차등 적용되며, 적립 계산 시 `MemberGrade`를 참조하여 적립 금액을 결정한다.

## Aggregate Root

`Mileage`

## Member Entities & Value Objects

- `MileageId` *(identifier — value object — primary key)*
- `MileageAmount` *(value object — 적립/사용/소멸 금액)*
- `AccumulationRate` *(value object — 적립 비율: VIP 2%, REGULAR 1%)*
- `MileageType` *(value object — ACCUMULATE / USE / EXPIRE)*
- `MemberGrade` *(value object — VIP / REGULAR)*

## Properties

| Field | Type | Mutability | Description |
|---|---|---|---|
| `id` | `UUID` | immutable after creation | 마일리지 트랜잭션 ID |
| `mileageAccountId` | `UUID` | immutable after creation | 소유 마일리지 계좌 ID |
| `memberId` | `UUID` | immutable after creation | 회원 ID |
| `memberGrade` | `MemberGrade` | immutable after creation | 적립 시점 회원 등급 (VIP/REGULAR) |
| `type` | `MileageType` | immutable after creation | 트랜잭션 유형 (ACCUMULATE/USE/EXPIRE) |
| `baseAmount` | `Long` | immutable after creation | 적립 기준 금액 (구매금액/이벤트 보상금액) |
| `accumulationRate` | `AccumulationRate` | immutable after creation | 적용된 적립 비율 |
| `mileageAmount` | `Long` | immutable after creation | 실제 적립/사용/소멸된 마일리지 |
| `sourceType` | `String` | immutable after creation | 발생 원천 (PURCHASE / EVENT / ADMIN) |
| `sourceReferenceId` | `UUID` | immutable after creation | 원천 거래 참조 ID |
| `occurredAt` | `DateTime` | immutable after creation | 트랜잭션 발생 일시 |

## Enforced Invariants

1. **[CHG-009]** `mileageAmount`는 `baseAmount × accumulationRate`로 계산되어야 한다
2. **[CHG-009]** `memberGrade`가 VIP이면 `accumulationRate`는 최소 0.02(2%) 이상이어야 한다
3. **[CHG-009]** `memberGrade`가 REGULAR이면 `accumulationRate`는 최소 0.01(1%) 이상이어야 한다
4. `mileageAmount`는 0 초과여야 한다
5. `memberId`와 `mileageAccountId`는 null이 될 수 없다
6. `occurredAt`은 미래 일시가 될 수 없다

## Business Rules (CHG-009 추가)

### 등급별 차등 적립 정책

```
적립 마일리지 = baseAmount × accumulationRate(memberGrade)

accumulationRate:
  VIP     → 2.0% (기본값, 정책 변경 가능)
  REGULAR → 1.0% (기본값, 정책 변경 가능)
```

- 적립 시점의 회원 등급을 스냅샷으로 저장 (등급 변동 시 소급 적용 없음)
- 적립률은 `MileageAccumulationPolicy`에서 관리하며 변경 이력을 추적

## Commands

| Command | Preconditions | Postconditions | Events emitted |
|---|---|---|---|
| `AccumulateMileage` | 회원 등급 정보 확인됨, baseAmount > 0 | 차등 적립률 적용 후 마일리지 생성됨 | `MileageAccumulated` |
| `UseMileage` | 잔액 충분, 회원 계좌 활성 상태 | 마일리지 차감됨 | `MileageUsed` |
| `ExpireMileage` | 만료 기준 충족 | 마일리지 소멸됨 | `MileageExpired` |

## Domain Events Emitted

- `MileageAccumulated` — 회원 등급에 따라 차등 적립률이 적용되어 마일리지가 적립되었다. `memberGrade`, `accumulationRate`, `mileageAmount` 포함.
- `MileageUsed` — 마일리지가 사용되었다.
- `MileageExpired` — 마일리지가 만료·소멸되었다.

## Repository Interface

```python
class MileageRepository(Protocol):
    def get(self, id: "MileageId") -> "Mileage": ...
    def save(self, aggregate: "Mileage") -> None: ...
    def find_by_account(self, account_id: "UUID") -> list["Mileage"]: ...
    # Command: AccumulateMileage
    # Command: UseMileage
    # Command: ExpireMileage
```

## Open Decisions

- 이벤트 참여 마일리지의 `baseAmount` 산정 기준을 정의해야 함 (이벤트 유형별 고정 보상액 vs 등급별 차등 보상액)
- VIP 적립률 2%, 일반 1%는 초기값이며 관리자 정책 UI 설계 필요
