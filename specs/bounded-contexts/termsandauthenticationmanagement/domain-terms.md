# Ubiquitous Language: TermsAndAuthenticationManagement

> The vocabulary of the **TermsAndAuthenticationManagement** Bounded Context. Names defined here are authoritative inside this BC; cross-BC equivalents and intentionally-avoided aliases are called out per term.
>
> Generated: 2026-05-12T11:55:59Z


## Term: `AuthenticationHistory`

**Definition.** The AuthenticationHistory aggregate.

**Business Context.** Transaction consistency boundary in 'TermsAndAuthenticationManagement'.

**Related Terms.**
- ViewAuthenticationHistory
- AuthenticationHistoryViewFailed
- AuthenticationHistoryViewed




## Term: `ViewAuthenticationHistory`

**Definition.** Allows a 회원_정책_담당자 to view the authentication history of a member within a specified date range.

**Business Context.** Operation invoked by an actor on the AuthenticationHistory aggregate.

**Related Terms.**
- AuthenticationHistoryViewed
- AuthenticationHistoryViewFailed




## Term: `AuthenticationHistoryViewFailed`

**Definition.** An attempt by a member policy manager to view authentication history failed.

**Business Context.** Past-tense fact about AuthenticationHistory; consumed by policies and read models.

**Related Terms.**
- AuthenticationHistory




## Term: `AuthenticationHistoryViewed`

**Definition.** A member policy manager viewed the authentication history for audit and policy compliance purposes.

**Business Context.** Past-tense fact about AuthenticationHistory; consumed by policies and read models.

**Related Terms.**
- AuthenticationHistory




## Term: `AuthenticationHistoryList`

**Definition.** Provides a list of authentication attempts and their outcomes for audit, compliance, and user review. Includes details such as authentication method, timestamp, result, and related high-risk actions.

**Business Context.** Query projection consumed by clients.

**Related Terms.**
- AuthenticationHistory




## Term: `TermsConsentRecordList`

**Definition.** Displays the history of terms and consent records for a member, including consents given, re-consented, or withdrawn, supporting review and management of legal agreements.

**Business Context.** Query projection consumed by clients.

**Related Terms.**
- AuthenticationHistory




## Term: `WithdrawalFinalConsentStatus`

**Definition.** Shows the current status of a member's final withdrawal consent, confirming whether the member has submitted or confirmed their intent to withdraw membership.

**Business Context.** Query projection consumed by clients.

**Related Terms.**
- AuthenticationHistory




## Term: `id`

**Definition.** 인증 기록의 고유 식별자

**Business Context.** Property of AuthenticationHistory; immutable after creation.

**Related Terms.**
- AuthenticationHistory




## Term: `attemptedAt`

**Definition.** 인증 시도가 발생한 일시 (감사 및 추적 목적)

**Business Context.** Property of AuthenticationHistory; mutable through commands only.

**Related Terms.**
- AuthenticationHistory




## Term: `authenticationResult`

**Definition.** 인증 시도의 결과 (예: 성공, 실패)

**Business Context.** Property of AuthenticationHistory; mutable through commands only.

**Related Terms.**
- AuthenticationHistory




## Term: `authenticationType`

**Definition.** 인증 시도의 유형 (예: 로그인, 출금, 휴면 해제 등)

**Business Context.** Property of AuthenticationHistory; mutable through commands only.

**Related Terms.**
- AuthenticationHistory




## Term: `isHighRiskAction`

**Definition.** 해당 인증 시도가 고위험 작업(예: 출금, 재가입 등)과 관련 있는지 여부

**Business Context.** Property of AuthenticationHistory; mutable through commands only.

**Related Terms.**
- AuthenticationHistory




## Term: `memberId`

**Definition.** 인증 시도한 회원의 식별자

**Business Context.** Property of AuthenticationHistory; mutable through commands only.

**Related Terms.**
- AuthenticationHistory




## Term: `TermsConsent`

**Definition.** The TermsConsent aggregate.

**Business Context.** Transaction consistency boundary in 'TermsAndAuthenticationManagement'.

**Related Terms.**
- AuthenticateForHighRiskAction
- GiveTermsConsent
- ReconsentTerms
- RecordAuthenticationHistory
- SubmitWithdrawalFinalConsent
- WithdrawTermsConsent
- AuthenticationHistoryRecorded
- HighRiskActionAuthenticationSucceeded
- TermsConsentGiven
- TermsConsentWithdrawn
- TermsConsented
- TermsReconsented
- WithdrawalFinalConsentSubmitted




## Term: `AuthenticateForHighRiskAction`

**Definition.** 회원 탈퇴 등 고위험 업무 진행 시 추가 인증을 수행합니다.

**Business Context.** Operation invoked by an actor on the TermsConsent aggregate.

**Related Terms.**
- HighRiskActionAuthenticationSucceeded




## Term: `GiveTermsConsent`

**Definition.** 고객이 약관 및 고지 내용을 확인하고 동의할 때 사용합니다. 신규 약관 동의, 업무별 약관 동의, 재가입 전 동의 등 다양한 상황에서 약관 동의 내역을 생성합니다.

**Business Context.** Operation invoked by an actor on the TermsConsent aggregate.

**Related Terms.**
- TermsConsented
- TermsConsentGiven




## Term: `ReconsentTerms`

**Definition.** 고객이 재동의가 필요한 약관에 대해 재동의할 때 사용합니다.

**Business Context.** Operation invoked by an actor on the TermsConsent aggregate.

**Related Terms.**
- TermsReconsented




## Term: `RecordAuthenticationHistory`

**Definition.** 인증 시스템이 인증 이력을 저장할 때 사용합니다.

**Business Context.** Operation invoked by an actor on the TermsConsent aggregate.

**Related Terms.**
- AuthenticationHistoryRecorded




## Term: `SubmitWithdrawalFinalConsent`

**Definition.** 고객이 회원 탈퇴를 진행할 때 최종적으로 동의 의사를 제출합니다.

**Business Context.** Operation invoked by an actor on the TermsConsent aggregate.

**Related Terms.**
- WithdrawalFinalConsentSubmitted




## Term: `WithdrawTermsConsent`

**Definition.** 회원이 기존에 동의한 약관 동의를 철회할 때 사용합니다.

**Business Context.** Operation invoked by an actor on the TermsConsent aggregate.

**Related Terms.**
- TermsConsentWithdrawn




## Term: `AuthenticationHistoryRecorded`

**Definition.** An authentication attempt's history was successfully recorded for audit and tracking purposes.

**Business Context.** Past-tense fact about TermsConsent; consumed by policies and read models.

**Related Terms.**
- TermsConsent




## Term: `HighRiskActionAuthenticationSucceeded`

**Definition.** The member successfully completed the additional authentication required for high-risk actions during membership withdrawal.

**Business Context.** Past-tense fact about TermsConsent; consumed by policies and read models.

**Related Terms.**
- TermsConsent




## Term: `TermsConsentGiven`

**Definition.** The customer has successfully agreed to the required terms and conditions for the relevant business process (e.g., registration, reactivation, rejoining).

**Business Context.** Past-tense fact about TermsConsent; consumed by policies and read models.

**Related Terms.**
- TermsConsent




## Term: `TermsConsentWithdrawn`

**Definition.** A member has successfully withdrawn their consent to specific terms.

**Business Context.** Past-tense fact about TermsConsent; consumed by policies and read models.

**Related Terms.**
- TermsConsent




## Term: `TermsConsented`

**Definition.** The customer has confirmed and consented to the required terms and notices for service use.

**Business Context.** Past-tense fact about TermsConsent; consumed by policies and read models.

**Related Terms.**
- TermsConsent




## Term: `TermsReconsented`

**Definition.** The customer has successfully re-consented to the required terms and conditions necessary for dormant account reactivation.

**Business Context.** Past-tense fact about TermsConsent; consumed by policies and read models.

**Related Terms.**
- TermsConsent




## Term: `WithdrawalFinalConsentSubmitted`

**Definition.** The member has submitted their final consent for withdrawal, clearly expressing their intent at the last step of the withdrawal process.

**Business Context.** Past-tense fact about TermsConsent; consumed by policies and read models.

**Related Terms.**
- TermsConsent




## Term: `id`

**Definition.** TermsConsent의 고유 식별자

**Business Context.** Property of TermsConsent; immutable after creation.

**Related Terms.**
- TermsConsent




## Term: `memberId`

**Definition.** 동의한 회원의 고유 식별자

**Business Context.** Property of TermsConsent; mutable through commands only.

**Related Terms.**
- TermsConsent




