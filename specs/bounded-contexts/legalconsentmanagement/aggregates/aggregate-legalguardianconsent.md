# Aggregate Design Spec: LegalGuardianConsent

> Bounded Context: **LegalConsentManagement** · Generated: 2026-05-12T11:55:59Z

## Description

_(not modeled — confirm)_

## Aggregate Root

`LegalGuardianConsent`

## Member Entities & Value Objects

- `LegalguardianconsentId` *(identifier — value object — primary key of LegalGuardianConsent)*


## Properties


| Field | Type | Mutability |
|---|---|---|
| `id` | `UUID` | immutable after creation |
| `confirmedAt` | `LocalDateTime` | mutable through commands only |
| `consentType` | `String` | mutable through commands only |
| `legalGuardianId` | `String` | mutable through commands only |
| `minorCustomerId` | `String` | mutable through commands only |
| `status` | `String` | mutable through commands only |
| `submittedAt` | `LocalDateTime` | mutable through commands only |



## Enforced Invariants


1. THE LegalGuardianConsent SHALL A minor member cannot proceed with registration or related activities unless a valid legal guardian or parental consent is obtained and recorded
2. THE LegalGuardianConsent SHALL Each consent record must be associated with exactly one minor member
3. THE LegalGuardianConsent SHALL Consent status must accurately reflect the latest submission and approval outcome
4. THE LegalGuardianConsent SHALL Consent can only be given by a verified legal guardian
5. THE LegalGuardianConsent SHALL Failed consent attempts must not allow membership progression for the minor



## Corrective Policies

_No corrective policies modeled._

## Commands


| Command | Preconditions | Postconditions | Events emitted |
|---|---|---|---|
| `ConfirmLegalGuardianConsent` | none | _(not modeled)_ | LegalGuardianConsentObtained, LegalGuardianConsentObtainingFailed |
| `SubmitLegalGuardianConsent` | none | _(not modeled)_ | LegalGuardianConsentSubmitted, LegalGuardianConsentSubmissionFailed |



## Domain Events Emitted

- `LegalGuardianConsentObtained` — A legal guardian's consent has been successfully obtained for a minor customer, fulfilling the legal requirement for proceeding with minor-related services.
- `LegalGuardianConsentObtainingFailed` — The attempt to obtain a legal guardian's consent for a minor customer has failed, preventing the fulfillment of legal requirements for minor-related services.
- `LegalGuardianConsentSubmissionFailed` — The attempt to submit legal guardian consent was unsuccessful.
- `LegalGuardianConsentSubmitted` — The customer has submitted legal guardian consent required for proceeding with membership tasks.


## Repository Interface

```python
class LegalGuardianConsentRepository(Protocol):
    def get(self, id: "LegalguardianconsentId") -> "LegalGuardianConsent": ...
    def save(self, aggregate: "LegalGuardianConsent") -> None: ...
    # Command: ConfirmLegalGuardianConsent
    # Command: SubmitLegalGuardianConsent
    
```

## Open Decisions

- Command `ConfirmLegalGuardianConsent` has no GWT modeled — confirm its preconditions / postconditions.
- Command `SubmitLegalGuardianConsent` has no GWT modeled — confirm its preconditions / postconditions.

