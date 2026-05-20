# Aggregate Design Spec: MemberAccount

> Bounded Context: **MembershipManagement** · Generated: 2026-05-12T11:55:59Z

## Description

_(not modeled — confirm)_

## Aggregate Root

`MemberAccount`

## Member Entities & Value Objects

- `MemberaccountId` *(identifier — value object — primary key of MemberAccount)*


## Properties


| Field | Type | Mutability |
|---|---|---|
| `id` | `UUID` | immutable after creation |
| `identityVerified` | `boolean` | mutable through commands only |
| `parentalConsentId` | `UUID` | mutable through commands only |
| `status` | `String` | mutable through commands only |
| `termsAgreement` | `Object` | mutable through commands only |
| `uniqueIdentifier` | `String` | mutable through commands only |



## Enforced Invariants


1. THE MemberAccount SHALL A MemberAccount must have a unique identification (e.g., email, phone, or username)
2. THE MemberAccount SHALL A MemberAccount must have a valid status at all times (ACTIVE, DORMANT, WITHDRAWN, etc.)
3. THE MemberAccount SHALL A MemberAccount cannot be both ACTIVE and DORMANT or WITHDRAWN at the same time
4. THE MemberAccount SHALL A MemberAccount must have valid identity verification and terms agreement before activation
5. THE MemberAccount SHALL A MemberAccount for minors must have valid parental consent before activation
6. THE MemberAccount SHALL A MemberAccount can only be restored or rejoined if eligibility checks pass
7. THE MemberAccount SHALL A MemberAccount's withdrawal or dormancy must trigger correct state transitions and data handling



## Corrective Policies

- **RequestHighRiskAuthenticationOnWithdrawal** — When 회원 탈퇴 요청됨 in MembershipManagement then AuthenticateForHighRiskAction in TermsAndAuthenticationManagement (ensure high-risk authentication before withdrawal)
- **RequestParentalConsentOnMinorRegistration** — When 회원 계정 생성됨 in MembershipManagement then SubmitLegalGuardianConsent in LegalConsentManagement (for minor members requiring legal guardian consent)
- **RequestTermsConsentOnRegistration** — When 회원 계정 생성됨 in MembershipManagement then GiveTermsConsent in TermsAndAuthenticationManagement (ensure terms consent is collected after account creation)
- **RevokeTermsConsentOnWithdrawal** — When 회원 탈퇴 완료됨 in MembershipManagement then WithdrawTermsConsent in TermsAndAuthenticationManagement (revoke terms consent after withdrawal)
- **SubmitLegalConsentOnParentalConsentComplete** — When 법정대리인 동의 완료됨 in LegalConsentManagement then ObtainParentalConsent in MembershipManagement (register guardian consent in membership system)


## Commands


| Command | Preconditions | Postconditions | Events emitted |
|---|---|---|---|
| `AgreeToTerms` | none | _(not modeled)_ | TermsAgreed |
| `CancelWithdrawal` | none | _(not modeled)_ | MembershipWithdrawalCancelled |
| `CreateProfile` | none | _(not modeled)_ | ProfileCreated |
| `ObtainParentalConsent` | none | _(not modeled)_ | ParentalConsentObtained |
| `ReactivateDormantAccount` | none | _(not modeled)_ | DormantAccountRestored, SessionRestoredAfterDormancy, DormantAccountReactivated, DormantStatusDeactivated |
| `RegisterMembership` | none | _(not modeled)_ | DuplicateIdentificationChecked, IdentityVerified, ParentalConsentObtained, TermsAgreed, ProfileCreated, MemberAccountCreated, MembershipRegistered |
| `RejoinMembership` | none | _(not modeled)_ | MembershipRejoined, SessionCreatedOrSwitchedAfterRejoin, MembershipReenrollmentCompleted, ReenrollmentResultNotified |
| `RequestDormantAccountReactivation` | none | _(not modeled)_ | DormantAccountReactivationRequested |
| `RestoreMemberAccount` | none | _(not modeled)_ | AccountRestored, PersonalDataRestored, ServiceUsageDataRestored |
| `SubmitWithdrawalReason` | none | _(not modeled)_ | MembershipWithdrawalReasonSubmitted |
| `SwitchMemberSession` | none | _(not modeled)_ | MemberSessionSwitched, SessionCreatedOrSwitchedAfterRejoin, SessionCreatedOrSwitched |
| `TerminateAllSessionsAndTokens` | none | _(not modeled)_ | AllSessionsAndTokensTerminated |
| `UpdateMemberInformation` | none | _(not modeled)_ | MemberInformationChanged |
| `UpdateProfileInformation` | none | _(not modeled)_ | ProfileInformationUpdated |
| `WithdrawMembership` | none | _(not modeled)_ | AllSessionsAndTokensTerminated, MembershipWithdrawn, MemberDataDeleted, WithdrawalFinalConsentGiven, MembershipWithdrawalStatusChanged, MembershipWithdrawalRequested, MembershipWithdrawalReasonSubmitted, PersonalInformationDestroyed |



## Domain Events Emitted

- `AccountRestored` — A previously existing customer account has been successfully restored, allowing the customer to resume service.
- `AllSessionsAndTokensTerminated` — All user sessions and authentication tokens were terminated upon account withdrawal to ensure security and prevent further access.
- `DormantAccountReactivated` — A dormant member account has been successfully reactivated, restoring normal membership status and service access.
- `DormantAccountReactivationRequested` — A dormant member has requested to reactivate their dormant account and return to normal membership status.
- `DormantAccountRestored` — The dormant account data has been successfully restored, allowing the member to resume service use.
- `DormantStatusDeactivated` — The member's dormant status has been deactivated, allowing service use to resume.
- `DuplicateIdentificationChecked` — The system checked whether the identification information provided during registration is already used by another account.
- `IdentityVerified` — The member's identity has been successfully verified during registration.
- `MemberAccountCreated` — A new integrated member account was successfully created, providing the customer with a unique member ID and account.
- `MemberDataDeleted` — The withdrawn member's data was deleted in accordance with legal or policy requirements.
- `MemberInformationChanged` — A member's information has been successfully changed to reflect the latest data.
- `MemberSessionSwitched` — A completed member's session was switched to enable automatic login after registration.
- `MembershipReenrollmentCompleted` — The member's reenrollment process has been completed, resulting in account restoration or new account creation and the member is now in a normal active state.
- `MembershipRegistered` — The customer has successfully completed the membership registration process and is now recognized as a registered member.
- `MembershipRejoined` — A member who was previously withdrawn or dormant has successfully rejoined, either by restoring their previous account or by registering a new account.
- `MembershipWithdrawalCancelled` — A member cancelled their account withdrawal request during the grace period, allowing continued use of the service.
- `MembershipWithdrawalReasonSubmitted` — 회원이 탈퇴 사유를 입력 또는 선택하여 제출하였다.
- `MembershipWithdrawalRequested` — The customer has requested to withdraw their membership from the service.
- `MembershipWithdrawalStatusChanged` — 회원의 계정이 탈퇴 상태로 전환되어 서비스 이용이 제한되었음
- `MembershipWithdrawn` — The member's account has been fully withdrawn and service usage has been terminated.
- `ParentalConsentObtained` — The legal guardian's consent was successfully obtained for the minor member during registration.
- `PersonalDataRestored` — 회원의 휴면 상태 해제 시 개인정보가 복원되었다.
- `PersonalInformationDestroyed` — 개인정보가 탈퇴 또는 재가입 후 파기 처리되어 더 이상 보관되지 않음이 확정됨.
- `ProfileCreated` — A basic profile has been successfully created for the customer, enabling personalized services and benefits.
- `ProfileInformationUpdated` — The member's profile information, such as contact details and notification preferences, was successfully updated.
- `ReenrollmentResultNotified` — The member has been notified of the result of their reenrollment, including related history and any follow-up actions.
- `ServiceUsageDataRestored` — 회원의 휴면 상태 해제 시 서비스 이용 데이터가 복원되었다.
- `SessionCreatedOrSwitched` — A login session was either created for the user or an existing session was switched to the user, enabling immediate service use after login.
- `SessionCreatedOrSwitchedAfterRejoin` — A login session was created or switched immediately after a member rejoined (re-registered) to enable immediate service use.
- `SessionRestoredAfterDormancy` — The user's session was restored immediately after dormant account reactivation and data restoration, allowing service use without additional login.
- `TermsAgreed` — The member has agreed to the terms and conditions during registration.
- `WithdrawalFinalConsentGiven` — 회원이 탈퇴 최종 동의를 완료하여 탈퇴 의사가 명확히 확인되었음


## Repository Interface

```python
class MemberAccountRepository(Protocol):
    def get(self, id: "MemberaccountId") -> "MemberAccount": ...
    def save(self, aggregate: "MemberAccount") -> None: ...
    # Command: AgreeToTerms
    # Command: CancelWithdrawal
    # Command: CreateProfile
    # Command: ObtainParentalConsent
    # Command: ReactivateDormantAccount
    # Command: RegisterMembership
    # Command: RejoinMembership
    # Command: RequestDormantAccountReactivation
    # Command: RestoreMemberAccount
    # Command: SubmitWithdrawalReason
    # Command: SwitchMemberSession
    # Command: TerminateAllSessionsAndTokens
    # Command: UpdateMemberInformation
    # Command: UpdateProfileInformation
    # Command: WithdrawMembership
    
```

## Open Decisions

- Command `AgreeToTerms` has no GWT modeled — confirm its preconditions / postconditions.
- Command `CancelWithdrawal` has no GWT modeled — confirm its preconditions / postconditions.
- Command `CreateProfile` has no GWT modeled — confirm its preconditions / postconditions.
- Command `ObtainParentalConsent` has no GWT modeled — confirm its preconditions / postconditions.
- Command `ReactivateDormantAccount` has no GWT modeled — confirm its preconditions / postconditions.
- Command `RegisterMembership` has no GWT modeled — confirm its preconditions / postconditions.
- Command `RejoinMembership` has no GWT modeled — confirm its preconditions / postconditions.
- Command `RequestDormantAccountReactivation` has no GWT modeled — confirm its preconditions / postconditions.
- Command `RestoreMemberAccount` has no GWT modeled — confirm its preconditions / postconditions.
- Command `SubmitWithdrawalReason` has no GWT modeled — confirm its preconditions / postconditions.
- Command `SwitchMemberSession` has no GWT modeled — confirm its preconditions / postconditions.
- Command `TerminateAllSessionsAndTokens` has no GWT modeled — confirm its preconditions / postconditions.
- Command `UpdateMemberInformation` has no GWT modeled — confirm its preconditions / postconditions.
- Command `UpdateProfileInformation` has no GWT modeled — confirm its preconditions / postconditions.
- Command `WithdrawMembership` has no GWT modeled — confirm its preconditions / postconditions.

