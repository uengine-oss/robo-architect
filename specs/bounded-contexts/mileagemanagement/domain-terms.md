# Domain Terms: MileageManagement

> Generated: 2026-06-02T00:00:00Z
> CHG-009: VIP/일반 회원 마일리지 차등 적립

## Glossary

| Term (EN) | Term (KO) | Definition |
|---|---|---|
| `MileageAccount` | 마일리지 계좌 | 회원별 마일리지 잔액·이력·등급 정보를 보관하는 집합체. 적립·사용·소멸 트랜잭션의 진입점. |
| `Mileage` | 마일리지 | 적립·사용·소멸되는 마일리지 단위 트랜잭션 집합체. |
| `MemberGrade` | 회원 등급 | **[CHG-009]** 마일리지 차등 적립의 기준. VIP 또는 REGULAR. |
| `VIP` | VIP 회원 | **[CHG-009]** 우수 회원 등급. 마일리지 기본 적립률 2% 적용. |
| `REGULAR` | 일반 회원 | **[CHG-009]** 일반 회원 등급. 마일리지 기본 적립률 1% 적용. |
| `AccumulationRate` | 적립 비율 | **[CHG-009]** 회원 등급별 마일리지 적립 비율 (예: VIP 2%, REGULAR 1%). |
| `AccumulationPolicy` | 적립 정책 | 등급별 적립 비율과 적용 기준을 정의하는 비즈니스 규칙 집합. |
| `MileageType` | 마일리지 유형 | 트랜잭션 유형: ACCUMULATE(적립), USE(사용), EXPIRE(소멸). |
| `SourceType` | 발생 원천 | 마일리지 발생 원인: PURCHASE(구매), EVENT(이벤트), ADMIN(관리자). |
| `MemberGradeUpdated` | 회원 등급 변경됨 | **[CHG-009]** MembershipManagement에서 발행하는 이벤트. MileageManagement가 구독하여 적립률을 동기화. |
| `GetMemberGrade` | 회원 등급 조회 | **[CHG-009]** MileageManagement가 MembershipManagement ACL을 통해 실시간 등급을 조회하는 쿼리. |
