# Ubiquitous Language: LegalConsentManagement

> The vocabulary of the **LegalConsentManagement** Bounded Context. Names defined here are authoritative inside this BC; cross-BC equivalents and intentionally-avoided aliases are called out per term.
>
> Generated: 2026-05-12T11:55:59Z


## Term: `LegalGuardianConsent`

**Definition.** The LegalGuardianConsent aggregate.

**Business Context.** Transaction consistency boundary in 'LegalConsentManagement'.

**Related Terms.**
- ConfirmLegalGuardianConsent
- SubmitLegalGuardianConsent
- LegalGuardianConsentObtained
- LegalGuardianConsentObtainingFailed
- LegalGuardianConsentSubmissionFailed
- LegalGuardianConsentSubmitted




## Term: `ConfirmLegalGuardianConsent`

**Definition.** 법정대리인이 미성년자 고객의 동의 요청을 확인하고 동의 또는 거부를 처리합니다.

**Business Context.** Operation invoked by an actor on the LegalGuardianConsent aggregate.

**Related Terms.**
- LegalGuardianConsentObtained
- LegalGuardianConsentObtainingFailed




## Term: `SubmitLegalGuardianConsent`

**Definition.** 고객이 법정대리인 동의 정보를 제출하여 동의 절차를 시작합니다.

**Business Context.** Operation invoked by an actor on the LegalGuardianConsent aggregate.

**Related Terms.**
- LegalGuardianConsentSubmitted
- LegalGuardianConsentSubmissionFailed




## Term: `LegalGuardianConsentObtained`

**Definition.** A legal guardian's consent has been successfully obtained for a minor customer, fulfilling the legal requirement for proceeding with minor-related services.

**Business Context.** Past-tense fact about LegalGuardianConsent; consumed by policies and read models.

**Related Terms.**
- LegalGuardianConsent




## Term: `LegalGuardianConsentObtainingFailed`

**Definition.** The attempt to obtain a legal guardian's consent for a minor customer has failed, preventing the fulfillment of legal requirements for minor-related services.

**Business Context.** Past-tense fact about LegalGuardianConsent; consumed by policies and read models.

**Related Terms.**
- LegalGuardianConsent




## Term: `LegalGuardianConsentSubmissionFailed`

**Definition.** The attempt to submit legal guardian consent was unsuccessful.

**Business Context.** Past-tense fact about LegalGuardianConsent; consumed by policies and read models.

**Related Terms.**
- LegalGuardianConsent




## Term: `LegalGuardianConsentSubmitted`

**Definition.** The customer has submitted legal guardian consent required for proceeding with membership tasks.

**Business Context.** Past-tense fact about LegalGuardianConsent; consumed by policies and read models.

**Related Terms.**
- LegalGuardianConsent




## Term: `LegalGuardianConsentHistory`

**Definition.** Provides a list of all legal guardian or parental consent attempts and their outcomes for a minor customer, including submission times, statuses, and any failure reasons. Supports auditing and review of consent compliance over time.

**Business Context.** Query projection consumed by clients.

**Related Terms.**
- LegalGuardianConsent




## Term: `LegalGuardianConsentStatus`

**Definition.** Displays the current status of legal guardian or parental consent for a minor customer, including whether consent has been obtained, is pending, or has failed. Used to inform customers and legal guardians about the progress and outcome of the consent process required for membership or related activities.

**Business Context.** Query projection consumed by clients.

**Related Terms.**
- LegalGuardianConsent




## Term: `id`

**Definition.** LegalGuardianConsent의 고유 식별자

**Business Context.** Property of LegalGuardianConsent; immutable after creation.

**Related Terms.**
- LegalGuardianConsent




## Term: `confirmedAt`

**Definition.** 동의가 확인된 일시 (확인된 경우에만)

**Business Context.** Property of LegalGuardianConsent; mutable through commands only.

**Related Terms.**
- LegalGuardianConsent




## Term: `consentType`

**Definition.** 동의의 유형 (예: 부모 동의, 법정대리인 동의 등)

**Business Context.** Property of LegalGuardianConsent; mutable through commands only.

**Related Terms.**
- LegalGuardianConsent




## Term: `legalGuardianId`

**Definition.** 동의를 제공하는 법정대리인의 고유 식별자

**Business Context.** Property of LegalGuardianConsent; mutable through commands only.

**Related Terms.**
- LegalGuardianConsent




## Term: `minorCustomerId`

**Definition.** 동의가 필요한 미성년자 회원의 고유 식별자

**Business Context.** Property of LegalGuardianConsent; mutable through commands only.

**Related Terms.**
- LegalGuardianConsent




## Term: `status`

**Definition.** 동의의 현재 상태 (예: 제출됨, 확인됨, 거부됨 등)

**Business Context.** Property of LegalGuardianConsent; mutable through commands only.

**Related Terms.**
- LegalGuardianConsent




## Term: `submittedAt`

**Definition.** 동의가 제출된 일시

**Business Context.** Property of LegalGuardianConsent; mutable through commands only.

**Related Terms.**
- LegalGuardianConsent




