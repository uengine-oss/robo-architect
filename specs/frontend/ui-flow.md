# UI Flow

> Causal ordering of UI screens, mirroring the event-modeling flow.
> Upstream Bounded Contexts' screens appear before downstream ones; within
> a User Story, screens appear in the story's wireframe order. Each entry
> links back to the canonical scene-graph and SVG.
>
> Generated: 2026-05-12T11:55:59Z


## 1. 회원가입을 진행한다 (MembershipManagement / `US-6-001`)

Triggered by: _entry point — user starts here._

Wireframe assets:

- Element tree: see [`../bounded-contexts/membershipmanagement/requirements.md`](../bounded-contexts/membershipmanagement/requirements.md) § "Wireframe: registermembership"
- SVG: [`../bounded-contexts/membershipmanagement/requirements.assets/US-6-001-registermembership.svg`](../bounded-contexts/membershipmanagement/requirements.assets/US-6-001-registermembership.svg)


## 2. 업무처리 동의 또는 확인을 한다 (LegalConsentManagement / `US-2-006`)

Triggered by: `MemberAccountCreated` (from MembershipManagement).

Wireframe assets:

- Element tree: see [`../bounded-contexts/legalconsentmanagement/requirements.md`](../bounded-contexts/legalconsentmanagement/requirements.md) § "Wireframe: confirmlegalguardianconsent"
- SVG: [`../bounded-contexts/legalconsentmanagement/requirements.assets/US-2-006-confirmlegalguardianconsent.svg`](../bounded-contexts/legalconsentmanagement/requirements.assets/US-2-006-confirmlegalguardianconsent.svg)


## 3. 업무처리 동의 또는 확인을 한다 (LegalConsentManagement / `US-2-006`)

Triggered by: previous screen in the same User Story.

Wireframe assets:

- Element tree: see [`../bounded-contexts/legalconsentmanagement/requirements.md`](../bounded-contexts/legalconsentmanagement/requirements.md) § "Wireframe: legalguardianconsenthistory"
- SVG: [`../bounded-contexts/legalconsentmanagement/requirements.assets/US-2-006-legalguardianconsenthistory.svg`](../bounded-contexts/legalconsentmanagement/requirements.assets/US-2-006-legalguardianconsenthistory.svg)


## 4. 업무처리 동의 또는 확인을 한다 (LegalConsentManagement / `US-2-006`)

Triggered by: previous screen in the same User Story.

Wireframe assets:

- Element tree: see [`../bounded-contexts/legalconsentmanagement/requirements.md`](../bounded-contexts/legalconsentmanagement/requirements.md) § "Wireframe: legalguardianconsentstatus"
- SVG: [`../bounded-contexts/legalconsentmanagement/requirements.assets/US-2-006-legalguardianconsentstatus.svg`](../bounded-contexts/legalconsentmanagement/requirements.assets/US-2-006-legalguardianconsentstatus.svg)


## 5. 탈퇴 최종 동의를 제출한다 (TermsAndAuthenticationManagement / `US-11-006`)

Triggered by: `MemberAccountCreated` (from MembershipManagement).

Wireframe assets:

- Element tree: see [`../bounded-contexts/termsandauthenticationmanagement/requirements.md`](../bounded-contexts/termsandauthenticationmanagement/requirements.md) § "Wireframe: withdrawalfinalconsentstatus"
- SVG: [`../bounded-contexts/termsandauthenticationmanagement/requirements.assets/US-11-006-withdrawalfinalconsentstatus.svg`](../bounded-contexts/termsandauthenticationmanagement/requirements.assets/US-11-006-withdrawalfinalconsentstatus.svg)


## 6. 인증 이력을 조회한다 (TermsAndAuthenticationManagement / `US-21-006`)

Triggered by: _entry point — user starts here._

Wireframe assets:

- Element tree: see [`../bounded-contexts/termsandauthenticationmanagement/requirements.md`](../bounded-contexts/termsandauthenticationmanagement/requirements.md) § "Wireframe: authenticationhistorylist"
- SVG: [`../bounded-contexts/termsandauthenticationmanagement/requirements.assets/US-21-006-authenticationhistorylist.svg`](../bounded-contexts/termsandauthenticationmanagement/requirements.assets/US-21-006-authenticationhistorylist.svg)


## 7. 인증 이력을 조회한다 (TermsAndAuthenticationManagement / `US-21-006`)

Triggered by: previous screen in the same User Story.

Wireframe assets:

- Element tree: see [`../bounded-contexts/termsandauthenticationmanagement/requirements.md`](../bounded-contexts/termsandauthenticationmanagement/requirements.md) § "Wireframe: viewauthenticationhistory"
- SVG: [`../bounded-contexts/termsandauthenticationmanagement/requirements.assets/US-21-006-viewauthenticationhistory.svg`](../bounded-contexts/termsandauthenticationmanagement/requirements.assets/US-21-006-viewauthenticationhistory.svg)


## 8. 재동의가 필요한 약관에 동의한다 (TermsAndAuthenticationManagement / `US-5-003`)

Triggered by: _entry point — user starts here._

Wireframe assets:

- Element tree: see [`../bounded-contexts/termsandauthenticationmanagement/requirements.md`](../bounded-contexts/termsandauthenticationmanagement/requirements.md) § "Wireframe: reconsentterms"
- SVG: [`../bounded-contexts/termsandauthenticationmanagement/requirements.assets/US-5-003-reconsentterms.svg`](../bounded-contexts/termsandauthenticationmanagement/requirements.assets/US-5-003-reconsentterms.svg)


## 9. 휴면 해제를 신청한다 (MembershipManagement / `US-1-003`)

Triggered by: `TermsReconsented` (from TermsAndAuthenticationManagement).

Wireframe assets:

- Element tree: see [`../bounded-contexts/membershipmanagement/requirements.md`](../bounded-contexts/membershipmanagement/requirements.md) § "Wireframe: requestdormantaccountreactivation"
- SVG: [`../bounded-contexts/membershipmanagement/requirements.assets/US-1-003-requestdormantaccountreactivation.svg`](../bounded-contexts/membershipmanagement/requirements.assets/US-1-003-requestdormantaccountreactivation.svg)



---

## Unreferenced Screens (review)

The following bound UIs are not reached by any cross-BC or intra-BC flow.
Review and either add the missing flow in the event-storming canvas or
confirm they are intentional standalone screens.

- **회원 탈퇴를 철회한다** (MembershipManagement / `US-1-004`) — `cancelwithdrawal` — (unreferenced flow — review)
- **회원가입 시 약관에 동의한다** (MembershipManagement / `US-15-003`) — `agreetoterms` — (unreferenced flow — review)
- **회원가입 처리 결과를 조회한다** (MembershipManagement / `US-15-007`) — `membershipregistrationresult` — (unreferenced flow — review)
- **기본 프로필을 생성한다** (MembershipManagement / `US-16-003`) — `createprofile` — (unreferenced flow — review)
- **회원가입 완료 후 정회원 세션으로 전환한다** (MembershipManagement / `US-16-004`) — `switchmembersession` — (unreferenced flow — review)
- **회원정보를 조회한다** (MembershipManagement / `US-2-003`) — `memberprofile` — (unreferenced flow — review)
- **회원정보를 변경한다** (MembershipManagement / `US-2-004`) — `updatememberinformation` — (unreferenced flow — review)
- **약관 동의 이력을 조회한다** (MembershipManagement / `US-2-009`) — `termsconsenthistory` — (unreferenced flow — review)
- **프로필 정보를 변경한다** (MembershipManagement / `US-23-002`) — `updateprofileinformation` — (unreferenced flow — review)
- **휴면 상태 해제 시 개인정보 및 서비스 이용 데이터를 복원한다** (MembershipManagement / `US-23-007`) — `dormantaccountrestorationresult` — (unreferenced flow — review)
- **탈퇴 완료 시 모든 세션과 토큰을 종료한다** (MembershipManagement / `US-25-008`) — `terminateallsessionsandtokens` — (unreferenced flow — review)
- **탈퇴 결과 안내를 받는다** (MembershipManagement / `US-26-006`) — `membershipwithdrawalresult` — (unreferenced flow — review)
- **탈퇴한 계정을 복원한다** (MembershipManagement / `US-27-002`) — `restorememberaccount` — (unreferenced flow — review)
- **재가입을 한다** (MembershipManagement / `US-3-004`) — `rejoinmembership` — (unreferenced flow — review)
- **회원 상태를 조회한다** (MembershipManagement / `US-3-005`) — `membershipstatus` — (unreferenced flow — review)
- **회원 탈퇴 사유를 입력 또는 선택한다** (MembershipManagement / `US-5-006`) — `submitwithdrawalreason` — (unreferenced flow — review)
- **기존 회원 이력을 조회한다** (MembershipManagement / `US-6-002`) — `membershiphistory` — (unreferenced flow — review)
- **약관 동의 이력을 조회하거나 철회한다** (TermsAndAuthenticationManagement / `US-14-008`) — `termsconsentrecordlist` — (unreferenced flow — review)
- **인증 이력을 저장한다** (TermsAndAuthenticationManagement / `US-22-003`) — `recordauthenticationhistory` — (unreferenced flow — review)


