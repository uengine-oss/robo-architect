# Ubiquitous Language: MembershipManagement

> The vocabulary of the **MembershipManagement** Bounded Context. Names defined here are authoritative inside this BC; cross-BC equivalents and intentionally-avoided aliases are called out per term.
>
> Generated: 2026-05-12T11:55:59Z


## Term: `MemberAccount`

**Definition.** The MemberAccount aggregate.

**Business Context.** Transaction consistency boundary in 'MembershipManagement'.

**Related Terms.**
- AgreeToTerms
- CancelWithdrawal
- CreateProfile
- ObtainParentalConsent
- ReactivateDormantAccount
- RegisterMembership
- RejoinMembership
- RequestDormantAccountReactivation
- RestoreMemberAccount
- SubmitWithdrawalReason
- SwitchMemberSession
- TerminateAllSessionsAndTokens
- UpdateMemberInformation
- UpdateProfileInformation
- WithdrawMembership
- AccountRestored
- AllSessionsAndTokensTerminated
- DormantAccountReactivated
- DormantAccountReactivationRequested
- DormantAccountRestored
- DormantStatusDeactivated
- DuplicateIdentificationChecked
- IdentityVerified
- MemberAccountCreated
- MemberDataDeleted
- MemberInformationChanged
- MemberSessionSwitched
- MembershipReenrollmentCompleted
- MembershipRegistered
- MembershipRejoined
- MembershipWithdrawalCancelled
- MembershipWithdrawalReasonSubmitted
- MembershipWithdrawalRequested
- MembershipWithdrawalStatusChanged
- MembershipWithdrawn
- ParentalConsentObtained
- PersonalDataRestored
- PersonalInformationDestroyed
- ProfileCreated
- ProfileInformationUpdated
- ReenrollmentResultNotified
- ServiceUsageDataRestored
- SessionCreatedOrSwitched
- SessionCreatedOrSwitchedAfterRejoin
- SessionRestoredAfterDormancy
- TermsAgreed
- WithdrawalFinalConsentGiven




## Term: `AgreeToTerms`

**Definition.** Records the member's agreement to terms and conditions, including re-consent.

**Business Context.** Operation invoked by an actor on the MemberAccount aggregate.

**Related Terms.**
- TermsAgreed




## Term: `CancelWithdrawal`

**Definition.** Cancels a pending membership withdrawal within the grace period.

**Business Context.** Operation invoked by an actor on the MemberAccount aggregate.

**Related Terms.**
- MembershipWithdrawalCancelled




## Term: `CreateProfile`

**Definition.** Creates a basic profile for the member after account creation.

**Business Context.** Operation invoked by an actor on the MemberAccount aggregate.

**Related Terms.**
- ProfileCreated




## Term: `ObtainParentalConsent`

**Definition.** Obtains parental/legal guardian consent for underage member registration.

**Business Context.** Operation invoked by an actor on the MemberAccount aggregate.

**Related Terms.**
- ParentalConsentObtained




## Term: `ReactivateDormantAccount`

**Definition.** Reactivates a dormant member account, restoring access and data.

**Business Context.** Operation invoked by an actor on the MemberAccount aggregate.

**Related Terms.**
- DormantAccountRestored
- SessionRestoredAfterDormancy
- DormantAccountReactivated
- DormantStatusDeactivated




## Term: `RegisterMembership`

**Definition.** Completes the membership registration process, including personal info, identification, terms agreement, and (if underage) parental consent.

**Business Context.** Operation invoked by an actor on the MemberAccount aggregate.

**Related Terms.**
- DuplicateIdentificationChecked
- IdentityVerified
- ParentalConsentObtained
- TermsAgreed
- ProfileCreated
- MemberAccountCreated
- MembershipRegistered




## Term: `RejoinMembership`

**Definition.** Processes member rejoining, including information entry, terms agreement, and restoration of previous data if applicable.

**Business Context.** Operation invoked by an actor on the MemberAccount aggregate.

**Related Terms.**
- MembershipRejoined
- SessionCreatedOrSwitchedAfterRejoin
- MembershipReenrollmentCompleted
- ReenrollmentResultNotified




## Term: `RequestDormantAccountReactivation`

**Definition.** Requests reactivation of a dormant account.

**Business Context.** Operation invoked by an actor on the MemberAccount aggregate.

**Related Terms.**
- DormantAccountReactivationRequested




## Term: `RestoreMemberAccount`

**Definition.** Restores a withdrawn or dormant member account, including personal and service usage data.

**Business Context.** Operation invoked by an actor on the MemberAccount aggregate.

**Related Terms.**
- AccountRestored
- PersonalDataRestored
- ServiceUsageDataRestored




## Term: `SubmitWithdrawalReason`

**Definition.** Submits the reason for membership withdrawal.

**Business Context.** Operation invoked by an actor on the MemberAccount aggregate.

**Related Terms.**
- MembershipWithdrawalReasonSubmitted




## Term: `SwitchMemberSession`

**Definition.** Switches or creates a member session after registration or rejoin.

**Business Context.** Operation invoked by an actor on the MemberAccount aggregate.

**Related Terms.**
- MemberSessionSwitched
- SessionCreatedOrSwitchedAfterRejoin
- SessionCreatedOrSwitched




## Term: `TerminateAllSessionsAndTokens`

**Definition.** Terminates all login sessions and authentication tokens for a withdrawn member.

**Business Context.** Operation invoked by an actor on the MemberAccount aggregate.

**Related Terms.**
- AllSessionsAndTokensTerminated




## Term: `UpdateMemberInformation`

**Definition.** Updates the member's account information.

**Business Context.** Operation invoked by an actor on the MemberAccount aggregate.

**Related Terms.**
- MemberInformationChanged




## Term: `UpdateProfileInformation`

**Definition.** Updates the member's profile information.

**Business Context.** Operation invoked by an actor on the MemberAccount aggregate.

**Related Terms.**
- ProfileInformationUpdated




## Term: `WithdrawMembership`

**Definition.** Processes the member's withdrawal request, including reason submission and final consent.

**Business Context.** Operation invoked by an actor on the MemberAccount aggregate.

**Related Terms.**
- AllSessionsAndTokensTerminated
- MembershipWithdrawn
- MemberDataDeleted
- WithdrawalFinalConsentGiven
- MembershipWithdrawalStatusChanged
- MembershipWithdrawalRequested
- MembershipWithdrawalReasonSubmitted
- PersonalInformationDestroyed




## Term: `AccountRestored`

**Definition.** A previously existing customer account has been successfully restored, allowing the customer to resume service.

**Business Context.** Past-tense fact about MemberAccount; consumed by policies and read models.

**Related Terms.**
- MemberAccount




## Term: `AllSessionsAndTokensTerminated`

**Definition.** All user sessions and authentication tokens were terminated upon account withdrawal to ensure security and prevent further access.

**Business Context.** Past-tense fact about MemberAccount; consumed by policies and read models.

**Related Terms.**
- MemberAccount




## Term: `DormantAccountReactivated`

**Definition.** A dormant member account has been successfully reactivated, restoring normal membership status and service access.

**Business Context.** Past-tense fact about MemberAccount; consumed by policies and read models.

**Related Terms.**
- MemberAccount




## Term: `DormantAccountReactivationRequested`

**Definition.** A dormant member has requested to reactivate their dormant account and return to normal membership status.

**Business Context.** Past-tense fact about MemberAccount; consumed by policies and read models.

**Related Terms.**
- MemberAccount




## Term: `DormantAccountRestored`

**Definition.** The dormant account data has been successfully restored, allowing the member to resume service use.

**Business Context.** Past-tense fact about MemberAccount; consumed by policies and read models.

**Related Terms.**
- MemberAccount




## Term: `DormantStatusDeactivated`

**Definition.** The member's dormant status has been deactivated, allowing service use to resume.

**Business Context.** Past-tense fact about MemberAccount; consumed by policies and read models.

**Related Terms.**
- MemberAccount




## Term: `DuplicateIdentificationChecked`

**Definition.** The system checked whether the identification information provided during registration is already used by another account.

**Business Context.** Past-tense fact about MemberAccount; consumed by policies and read models.

**Related Terms.**
- MemberAccount




## Term: `IdentityVerified`

**Definition.** The member's identity has been successfully verified during registration.

**Business Context.** Past-tense fact about MemberAccount; consumed by policies and read models.

**Related Terms.**
- MemberAccount




## Term: `MemberAccountCreated`

**Definition.** A new integrated member account was successfully created, providing the customer with a unique member ID and account.

**Business Context.** Past-tense fact about MemberAccount; consumed by policies and read models.

**Related Terms.**
- MemberAccount




## Term: `MemberDataDeleted`

**Definition.** The withdrawn member's data was deleted in accordance with legal or policy requirements.

**Business Context.** Past-tense fact about MemberAccount; consumed by policies and read models.

**Related Terms.**
- MemberAccount




## Term: `MemberInformationChanged`

**Definition.** A member's information has been successfully changed to reflect the latest data.

**Business Context.** Past-tense fact about MemberAccount; consumed by policies and read models.

**Related Terms.**
- MemberAccount




## Term: `MemberSessionSwitched`

**Definition.** A completed member's session was switched to enable automatic login after registration.

**Business Context.** Past-tense fact about MemberAccount; consumed by policies and read models.

**Related Terms.**
- MemberAccount




## Term: `MembershipReenrollmentCompleted`

**Definition.** The member's reenrollment process has been completed, resulting in account restoration or new account creation and the member is now in a normal active state.

**Business Context.** Past-tense fact about MemberAccount; consumed by policies and read models.

**Related Terms.**
- MemberAccount




## Term: `MembershipRegistered`

**Definition.** The customer has successfully completed the membership registration process and is now recognized as a registered member.

**Business Context.** Past-tense fact about MemberAccount; consumed by policies and read models.

**Related Terms.**
- MemberAccount




## Term: `MembershipRejoined`

**Definition.** A member who was previously withdrawn or dormant has successfully rejoined, either by restoring their previous account or by registering a new account.

**Business Context.** Past-tense fact about MemberAccount; consumed by policies and read models.

**Related Terms.**
- MemberAccount




## Term: `MembershipWithdrawalCancelled`

**Definition.** A member cancelled their account withdrawal request during the grace period, allowing continued use of the service.

**Business Context.** Past-tense fact about MemberAccount; consumed by policies and read models.

**Related Terms.**
- MemberAccount




## Term: `MembershipWithdrawalReasonSubmitted`

**Definition.** 회원이 탈퇴 사유를 입력 또는 선택하여 제출하였다.

**Business Context.** Past-tense fact about MemberAccount; consumed by policies and read models.

**Related Terms.**
- MemberAccount




## Term: `MembershipWithdrawalRequested`

**Definition.** The customer has requested to withdraw their membership from the service.

**Business Context.** Past-tense fact about MemberAccount; consumed by policies and read models.

**Related Terms.**
- MemberAccount




## Term: `MembershipWithdrawalStatusChanged`

**Definition.** 회원의 계정이 탈퇴 상태로 전환되어 서비스 이용이 제한되었음

**Business Context.** Past-tense fact about MemberAccount; consumed by policies and read models.

**Related Terms.**
- MemberAccount




## Term: `MembershipWithdrawn`

**Definition.** The member's account has been fully withdrawn and service usage has been terminated.

**Business Context.** Past-tense fact about MemberAccount; consumed by policies and read models.

**Related Terms.**
- MemberAccount




## Term: `ParentalConsentObtained`

**Definition.** The legal guardian's consent was successfully obtained for the minor member during registration.

**Business Context.** Past-tense fact about MemberAccount; consumed by policies and read models.

**Related Terms.**
- MemberAccount




## Term: `PersonalDataRestored`

**Definition.** 회원의 휴면 상태 해제 시 개인정보가 복원되었다.

**Business Context.** Past-tense fact about MemberAccount; consumed by policies and read models.

**Related Terms.**
- MemberAccount




## Term: `PersonalInformationDestroyed`

**Definition.** 개인정보가 탈퇴 또는 재가입 후 파기 처리되어 더 이상 보관되지 않음이 확정됨.

**Business Context.** Past-tense fact about MemberAccount; consumed by policies and read models.

**Related Terms.**
- MemberAccount




## Term: `ProfileCreated`

**Definition.** A basic profile has been successfully created for the customer, enabling personalized services and benefits.

**Business Context.** Past-tense fact about MemberAccount; consumed by policies and read models.

**Related Terms.**
- MemberAccount




## Term: `ProfileInformationUpdated`

**Definition.** The member's profile information, such as contact details and notification preferences, was successfully updated.

**Business Context.** Past-tense fact about MemberAccount; consumed by policies and read models.

**Related Terms.**
- MemberAccount




## Term: `ReenrollmentResultNotified`

**Definition.** The member has been notified of the result of their reenrollment, including related history and any follow-up actions.

**Business Context.** Past-tense fact about MemberAccount; consumed by policies and read models.

**Related Terms.**
- MemberAccount




## Term: `ServiceUsageDataRestored`

**Definition.** 회원의 휴면 상태 해제 시 서비스 이용 데이터가 복원되었다.

**Business Context.** Past-tense fact about MemberAccount; consumed by policies and read models.

**Related Terms.**
- MemberAccount




## Term: `SessionCreatedOrSwitched`

**Definition.** A login session was either created for the user or an existing session was switched to the user, enabling immediate service use after login.

**Business Context.** Past-tense fact about MemberAccount; consumed by policies and read models.

**Related Terms.**
- MemberAccount




## Term: `SessionCreatedOrSwitchedAfterRejoin`

**Definition.** A login session was created or switched immediately after a member rejoined (re-registered) to enable immediate service use.

**Business Context.** Past-tense fact about MemberAccount; consumed by policies and read models.

**Related Terms.**
- MemberAccount




## Term: `SessionRestoredAfterDormancy`

**Definition.** The user's session was restored immediately after dormant account reactivation and data restoration, allowing service use without additional login.

**Business Context.** Past-tense fact about MemberAccount; consumed by policies and read models.

**Related Terms.**
- MemberAccount




## Term: `TermsAgreed`

**Definition.** The member has agreed to the terms and conditions during registration.

**Business Context.** Past-tense fact about MemberAccount; consumed by policies and read models.

**Related Terms.**
- MemberAccount




## Term: `WithdrawalFinalConsentGiven`

**Definition.** 회원이 탈퇴 최종 동의를 완료하여 탈퇴 의사가 명확히 확인되었음

**Business Context.** Past-tense fact about MemberAccount; consumed by policies and read models.

**Related Terms.**
- MemberAccount




## Term: `DormantAccountRestorationResult`

**Definition.** Provides the result and details of dormant account restoration, including restored information, reactivation status, and any next steps.

**Business Context.** Query projection consumed by clients.

**Related Terms.**
- MemberAccount




## Term: `MemberProfile`

**Definition.** Retrieves the profile information of a member, including contact details, notification preferences, and personalization settings.

**Business Context.** Query projection consumed by clients.

**Related Terms.**
- MemberAccount




## Term: `MembershipHistory`

**Definition.** Retrieves the history of membership lifecycle events for a member, including registration, dormancy, withdrawal, rejoin, and restoration actions.

**Business Context.** Query projection consumed by clients.

**Related Terms.**
- MemberAccount




## Term: `MembershipRegistrationResult`

**Definition.** Displays the result and status of the most recent membership registration attempt, including processing status, completion, and any errors.

**Business Context.** Query projection consumed by clients.

**Related Terms.**
- MemberAccount




## Term: `MembershipStatus`

**Definition.** Provides the current membership status (active, dormant, withdrawn, etc.) and account state transitions for a member. Used to check eligibility for registration, login, dormancy, or withdrawal.

**Business Context.** Query projection consumed by clients.

**Related Terms.**
- MemberAccount




## Term: `MembershipWithdrawalResult`

**Definition.** Shows the result and status of the membership withdrawal process, including completion, grace period, and eligibility for reversal or rejoin.

**Business Context.** Query projection consumed by clients.

**Related Terms.**
- MemberAccount




## Term: `TermsConsentHistory`

**Definition.** Shows the history of terms and conditions consents given by the member, including initial agreement and re-consent for service usage.

**Business Context.** Query projection consumed by clients.

**Related Terms.**
- MemberAccount




## Term: `id`

**Definition.** MemberAccount의 고유 식별자

**Business Context.** Property of MemberAccount; immutable after creation.

**Related Terms.**
- MemberAccount




## Term: `identityVerified`

**Definition.** 회원 계정 활성화를 위한 본인 인증 완료 여부

**Business Context.** Property of MemberAccount; mutable through commands only.

**Related Terms.**
- MemberAccount




## Term: `parentalConsentId`

**Definition.** 미성년자 회원 활성화를 위한 법정대리인 동의 ID

**Business Context.** Property of MemberAccount; mutable through commands only.

**Related Terms.**
- MemberAccount




## Term: `status`

**Definition.** 회원 계정의 상태 (예: ACTIVE, DORMANT, WITHDRAWN 등)

**Business Context.** Property of MemberAccount; mutable through commands only.

**Related Terms.**
- MemberAccount




## Term: `termsAgreement`

**Definition.** 회원 계정 활성화를 위한 약관 동의 정보

**Business Context.** Property of MemberAccount; mutable through commands only.

**Related Terms.**
- MemberAccount




## Term: `uniqueIdentifier`

**Definition.** 이메일, 휴대폰, 또는 사용자명 등 회원 계정의 고유 식별 정보

**Business Context.** Property of MemberAccount; mutable through commands only.

**Related Terms.**
- MemberAccount




