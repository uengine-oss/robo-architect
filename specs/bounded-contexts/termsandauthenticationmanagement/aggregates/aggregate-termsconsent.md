# Aggregate Design Spec: TermsConsent

> Bounded Context: **TermsAndAuthenticationManagement** · Generated: 2026-05-12T11:55:59Z

## Description

_(not modeled — confirm)_

## Aggregate Root

`TermsConsent`

## Member Entities & Value Objects

- `TermsconsentId` *(identifier — value object — primary key of TermsConsent)*


## Properties


| Field | Type | Mutability |
|---|---|---|
| `id` | `UUID` | immutable after creation |
| `memberId` | `String` | mutable through commands only |



## Enforced Invariants


1. THE TermsConsent SHALL A member cannot consent to the same terms more than once for the same business process without withdrawal
2. THE TermsConsent SHALL Withdrawal of consent must be reflected immediately and prevent further use of the withdrawn terms
3. THE TermsConsent SHALL Consent to required terms is mandatory for proceeding with related membership actions (registration, reactivation, rejoin, withdrawal)
4. THE TermsConsent SHALL Consent records must be auditable and immutable except for explicit withdrawal



## Corrective Policies

- **ReactivateDormantAccountOnTermsReconsent** — When 약관 재동의 완료됨 in TermsAndAuthenticationManagement then ReactivateDormantAccount in MembershipManagement (reactivate dormant account after terms reconsent)
- **RecordAuthenticationOnHighRiskAction** — When 고위험 업무 추가 인증 성공 in TermsAndAuthenticationManagement then WithdrawMembership in MembershipManagement (ensure withdrawal only after successful high-risk authentication)
- **SubmitWithdrawalFinalConsentOnHighRiskAuthSuccess** — When 고위험 업무 추가 인증 성공 in TermsAndAuthenticationManagement then SubmitWithdrawalFinalConsent in TermsAndAuthenticationManagement (submit final withdrawal consent after successful high-risk authentication)


## Commands


| Command | Preconditions | Postconditions | Events emitted |
|---|---|---|---|
| `AuthenticateForHighRiskAction` | none | _(not modeled)_ | HighRiskActionAuthenticationSucceeded |
| `GiveTermsConsent` | none | _(not modeled)_ | TermsConsented, TermsConsentGiven |
| `ReconsentTerms` | none | _(not modeled)_ | TermsReconsented |
| `RecordAuthenticationHistory` | none | _(not modeled)_ | AuthenticationHistoryRecorded |
| `SubmitWithdrawalFinalConsent` | none | _(not modeled)_ | WithdrawalFinalConsentSubmitted |
| `WithdrawTermsConsent` | none | _(not modeled)_ | TermsConsentWithdrawn |



## Domain Events Emitted

- `AuthenticationHistoryRecorded` — An authentication attempt's history was successfully recorded for audit and tracking purposes.
- `HighRiskActionAuthenticationSucceeded` — The member successfully completed the additional authentication required for high-risk actions during membership withdrawal.
- `TermsConsentGiven` — The customer has successfully agreed to the required terms and conditions for the relevant business process (e.g., registration, reactivation, rejoining).
- `TermsConsentWithdrawn` — A member has successfully withdrawn their consent to specific terms.
- `TermsConsented` — The customer has confirmed and consented to the required terms and notices for service use.
- `TermsReconsented` — The customer has successfully re-consented to the required terms and conditions necessary for dormant account reactivation.
- `WithdrawalFinalConsentSubmitted` — The member has submitted their final consent for withdrawal, clearly expressing their intent at the last step of the withdrawal process.


## Repository Interface

```python
class TermsConsentRepository(Protocol):
    def get(self, id: "TermsconsentId") -> "TermsConsent": ...
    def save(self, aggregate: "TermsConsent") -> None: ...
    # Command: AuthenticateForHighRiskAction
    # Command: GiveTermsConsent
    # Command: ReconsentTerms
    # Command: RecordAuthenticationHistory
    # Command: SubmitWithdrawalFinalConsent
    # Command: WithdrawTermsConsent
    
```

## Open Decisions

- Command `AuthenticateForHighRiskAction` has no GWT modeled — confirm its preconditions / postconditions.
- Command `GiveTermsConsent` has no GWT modeled — confirm its preconditions / postconditions.
- Command `ReconsentTerms` has no GWT modeled — confirm its preconditions / postconditions.
- Command `RecordAuthenticationHistory` has no GWT modeled — confirm its preconditions / postconditions.
- Command `SubmitWithdrawalFinalConsent` has no GWT modeled — confirm its preconditions / postconditions.
- Command `WithdrawTermsConsent` has no GWT modeled — confirm its preconditions / postconditions.

