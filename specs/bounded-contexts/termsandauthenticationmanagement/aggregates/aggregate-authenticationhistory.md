# Aggregate Design Spec: AuthenticationHistory

> Bounded Context: **TermsAndAuthenticationManagement** · Generated: 2026-05-12T11:55:59Z

## Description

_(not modeled — confirm)_

## Aggregate Root

`AuthenticationHistory`

## Member Entities & Value Objects

- `AuthenticationhistoryId` *(identifier — value object — primary key of AuthenticationHistory)*


## Properties


| Field | Type | Mutability |
|---|---|---|
| `id` | `UUID` | immutable after creation |
| `attemptedAt` | `LocalDateTime` | mutable through commands only |
| `authenticationResult` | `String` | mutable through commands only |
| `authenticationType` | `String` | mutable through commands only |
| `isHighRiskAction` | `boolean` | mutable through commands only |
| `memberId` | `String` | mutable through commands only |



## Enforced Invariants


1. THE AuthenticationHistory SHALL All authentication attempts must be recorded for audit and compliance
2. THE AuthenticationHistory SHALL Authentication records must include the type, result, and timestamp of the attempt
3. THE AuthenticationHistory SHALL High-risk action authentication must be distinguished and auditable
4. THE AuthenticationHistory SHALL Authentication history must not be altered after recording, except for audit correction with trace



## Corrective Policies

_No corrective policies modeled._

## Commands


| Command | Preconditions | Postconditions | Events emitted |
|---|---|---|---|
| `ViewAuthenticationHistory` | none | _(not modeled)_ | AuthenticationHistoryViewed, AuthenticationHistoryViewFailed |



## Domain Events Emitted

- `AuthenticationHistoryViewFailed` — An attempt by a member policy manager to view authentication history failed.
- `AuthenticationHistoryViewed` — A member policy manager viewed the authentication history for audit and policy compliance purposes.


## Repository Interface

```python
class AuthenticationHistoryRepository(Protocol):
    def get(self, id: "AuthenticationhistoryId") -> "AuthenticationHistory": ...
    def save(self, aggregate: "AuthenticationHistory") -> None: ...
    # Command: ViewAuthenticationHistory
    
```

## Open Decisions

- Command `ViewAuthenticationHistory` has no GWT modeled — confirm its preconditions / postconditions.

