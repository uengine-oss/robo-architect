# Menu Structure — Agent-Designed

> **This file does NOT define the menu structure.** It is the input the
> `frontend-engineer` agent reads to *design* the menu IA from the wider
> event-modeling flow, not from BC boundaries.
>
> The menu must follow the **user's workflow** — the business flow
> captured in [`ui-flow.md`](./ui-flow.md) — not arbitrary BC slicing.
> BC labels in the inventory below are for traceability (so generated
> code can cite the owning BC), not for grouping.
>
> Generated: 2026-05-12T11:55:59Z

## How to use this file

1. **Read [`ui-flow.md`](./ui-flow.md) first.** It carries the causal
   order of UI screens across the whole event-modeling flow — the
   user-journey shape lives there. **This is the only structural
   input.**
2. For each UI in the inventory below, follow the relative link to its
   element tree (in the BC's `requirements.md`) and its scene-graph /
   SVG assets. Understand the *business task* the user is performing,
   not just which BC owns it.
3. **Naming is the only thing BC artifacts are for.** For each UI,
   open the owning BC's
   `../bounded-contexts/<bc-slug>/domain-terms.md` and pull the
   Aggregate / Command / Event / ReadModel / Property names verbatim.
   Use those for component names, store names, type names, route
   segments, and API path segments. Entries under "Aliases to AVOID"
   are forbidden. Do not read other BC files (`bc-*.md`,
   `aggregate-*.md`) — that would re-introduce BC-centric thinking
   into the frontend's structure.
4. **Design the menu IA from the workflow**, not from BC boundaries.
   Concretely:
   - Top-level menu entries should reflect user roles, modes, or
     workflow stages — not BC names.
   - Group sub-entries by sub-flow (consecutive UIs the same user
     traverses), not by BC.
   - Entry-point UIs (marked **Entry point** below) are the natural
     candidates for top-level entries — they have no upstream flow,
     so a user lands on them directly.
   - Unreferenced UIs (marked **(unreferenced — review)**) need user
     confirmation before placement; do not silently bury them in the
     menu.
5. Cross-reference [`framework.md`](./framework.md) for the routing
   library's defaults; that decides *how* routes are physically
   declared (Vue Router config, React Router `<Outlet>`, SvelteKit
   file-based, …) — not which routes exist.

## Inventory of bound UIs

### RegisterMembership · **Entry point**

- Workflow position: user-journey entry (no upstream trigger)
- User Story: `US-6-001` — 회원가입을 진행한다
- Actor: 고객
- Bound to: Command `RegisterMembership`
- Owning Bounded Context (for traceability only): **MembershipManagement** (`membershipmanagement`)
- Wireframe assets:
  - Element tree: [`../bounded-contexts/membershipmanagement/requirements.md`](../bounded-contexts/membershipmanagement/requirements.md) § "Wireframe: registermembership"
  - SVG: [`../bounded-contexts/membershipmanagement/requirements.assets/US-6-001-registermembership.svg`](../bounded-contexts/membershipmanagement/requirements.assets/US-6-001-registermembership.svg)

### ConfirmLegalGuardianConsent

- Workflow position: reached from an upstream flow — see `ui-flow.md` for the trigger
- User Story: `US-2-006` — 업무처리 동의 또는 확인을 한다
- Actor: 법정대리인
- Bound to: Command `ConfirmLegalGuardianConsent`
- Owning Bounded Context (for traceability only): **LegalConsentManagement** (`legalconsentmanagement`)
- Wireframe assets:
  - Element tree: [`../bounded-contexts/legalconsentmanagement/requirements.md`](../bounded-contexts/legalconsentmanagement/requirements.md) § "Wireframe: confirmlegalguardianconsent"
  - SVG: [`../bounded-contexts/legalconsentmanagement/requirements.assets/US-2-006-confirmlegalguardianconsent.svg`](../bounded-contexts/legalconsentmanagement/requirements.assets/US-2-006-confirmlegalguardianconsent.svg)

### LegalGuardianConsentHistory

- Workflow position: reached from an upstream flow — see `ui-flow.md` for the trigger
- User Story: `US-2-006` — 업무처리 동의 또는 확인을 한다
- Actor: 법정대리인
- Bound to: ReadModel `LegalGuardianConsentHistory`
- Owning Bounded Context (for traceability only): **LegalConsentManagement** (`legalconsentmanagement`)
- Wireframe assets:
  - Element tree: [`../bounded-contexts/legalconsentmanagement/requirements.md`](../bounded-contexts/legalconsentmanagement/requirements.md) § "Wireframe: legalguardianconsenthistory"
  - SVG: [`../bounded-contexts/legalconsentmanagement/requirements.assets/US-2-006-legalguardianconsenthistory.svg`](../bounded-contexts/legalconsentmanagement/requirements.assets/US-2-006-legalguardianconsenthistory.svg)

### LegalGuardianConsentStatus

- Workflow position: reached from an upstream flow — see `ui-flow.md` for the trigger
- User Story: `US-2-006` — 업무처리 동의 또는 확인을 한다
- Actor: 법정대리인
- Bound to: ReadModel `LegalGuardianConsentStatus`
- Owning Bounded Context (for traceability only): **LegalConsentManagement** (`legalconsentmanagement`)
- Wireframe assets:
  - Element tree: [`../bounded-contexts/legalconsentmanagement/requirements.md`](../bounded-contexts/legalconsentmanagement/requirements.md) § "Wireframe: legalguardianconsentstatus"
  - SVG: [`../bounded-contexts/legalconsentmanagement/requirements.assets/US-2-006-legalguardianconsentstatus.svg`](../bounded-contexts/legalconsentmanagement/requirements.assets/US-2-006-legalguardianconsentstatus.svg)

### WithdrawalFinalConsentStatus

- Workflow position: reached from an upstream flow — see `ui-flow.md` for the trigger
- User Story: `US-11-006` — 탈퇴 최종 동의를 제출한다
- Actor: 회원
- Bound to: ReadModel `WithdrawalFinalConsentStatus`
- Owning Bounded Context (for traceability only): **TermsAndAuthenticationManagement** (`termsandauthenticationmanagement`)
- Wireframe assets:
  - Element tree: [`../bounded-contexts/termsandauthenticationmanagement/requirements.md`](../bounded-contexts/termsandauthenticationmanagement/requirements.md) § "Wireframe: withdrawalfinalconsentstatus"
  - SVG: [`../bounded-contexts/termsandauthenticationmanagement/requirements.assets/US-11-006-withdrawalfinalconsentstatus.svg`](../bounded-contexts/termsandauthenticationmanagement/requirements.assets/US-11-006-withdrawalfinalconsentstatus.svg)

### AuthenticationHistoryList · **Entry point**

- Workflow position: user-journey entry (no upstream trigger)
- User Story: `US-21-006` — 인증 이력을 조회한다
- Actor: 회원_정책_담당자
- Bound to: ReadModel `AuthenticationHistoryList`
- Owning Bounded Context (for traceability only): **TermsAndAuthenticationManagement** (`termsandauthenticationmanagement`)
- Wireframe assets:
  - Element tree: [`../bounded-contexts/termsandauthenticationmanagement/requirements.md`](../bounded-contexts/termsandauthenticationmanagement/requirements.md) § "Wireframe: authenticationhistorylist"
  - SVG: [`../bounded-contexts/termsandauthenticationmanagement/requirements.assets/US-21-006-authenticationhistorylist.svg`](../bounded-contexts/termsandauthenticationmanagement/requirements.assets/US-21-006-authenticationhistorylist.svg)

### ViewAuthenticationHistory

- Workflow position: reached from an upstream flow — see `ui-flow.md` for the trigger
- User Story: `US-21-006` — 인증 이력을 조회한다
- Actor: 회원_정책_담당자
- Bound to: Command `ViewAuthenticationHistory`
- Owning Bounded Context (for traceability only): **TermsAndAuthenticationManagement** (`termsandauthenticationmanagement`)
- Wireframe assets:
  - Element tree: [`../bounded-contexts/termsandauthenticationmanagement/requirements.md`](../bounded-contexts/termsandauthenticationmanagement/requirements.md) § "Wireframe: viewauthenticationhistory"
  - SVG: [`../bounded-contexts/termsandauthenticationmanagement/requirements.assets/US-21-006-viewauthenticationhistory.svg`](../bounded-contexts/termsandauthenticationmanagement/requirements.assets/US-21-006-viewauthenticationhistory.svg)

### ReconsentTerms · **Entry point**

- Workflow position: user-journey entry (no upstream trigger)
- User Story: `US-5-003` — 재동의가 필요한 약관에 동의한다
- Actor: 고객
- Bound to: Command `ReconsentTerms`
- Owning Bounded Context (for traceability only): **TermsAndAuthenticationManagement** (`termsandauthenticationmanagement`)
- Wireframe assets:
  - Element tree: [`../bounded-contexts/termsandauthenticationmanagement/requirements.md`](../bounded-contexts/termsandauthenticationmanagement/requirements.md) § "Wireframe: reconsentterms"
  - SVG: [`../bounded-contexts/termsandauthenticationmanagement/requirements.assets/US-5-003-reconsentterms.svg`](../bounded-contexts/termsandauthenticationmanagement/requirements.assets/US-5-003-reconsentterms.svg)

### RequestDormantAccountReactivation

- Workflow position: reached from an upstream flow — see `ui-flow.md` for the trigger
- User Story: `US-1-003` — 휴면 해제를 신청한다
- Actor: 휴면_회원
- Bound to: Command `RequestDormantAccountReactivation`
- Owning Bounded Context (for traceability only): **MembershipManagement** (`membershipmanagement`)
- Wireframe assets:
  - Element tree: [`../bounded-contexts/membershipmanagement/requirements.md`](../bounded-contexts/membershipmanagement/requirements.md) § "Wireframe: requestdormantaccountreactivation"
  - SVG: [`../bounded-contexts/membershipmanagement/requirements.assets/US-1-003-requestdormantaccountreactivation.svg`](../bounded-contexts/membershipmanagement/requirements.assets/US-1-003-requestdormantaccountreactivation.svg)

### CancelWithdrawal · **(unreferenced — review)**

- Workflow position: island — no flow reaches this UI
- User Story: `US-1-004` — 회원 탈퇴를 철회한다
- Actor: 회원
- Bound to: Command `CancelWithdrawal`
- Owning Bounded Context (for traceability only): **MembershipManagement** (`membershipmanagement`)
- Wireframe assets:
  - Element tree: [`../bounded-contexts/membershipmanagement/requirements.md`](../bounded-contexts/membershipmanagement/requirements.md) § "Wireframe: cancelwithdrawal"
  - SVG: [`../bounded-contexts/membershipmanagement/requirements.assets/US-1-004-cancelwithdrawal.svg`](../bounded-contexts/membershipmanagement/requirements.assets/US-1-004-cancelwithdrawal.svg)

### AgreeToTerms · **(unreferenced — review)**

- Workflow position: island — no flow reaches this UI
- User Story: `US-15-003` — 회원가입 시 약관에 동의한다
- Actor: 회원
- Bound to: Command `AgreeToTerms`
- Owning Bounded Context (for traceability only): **MembershipManagement** (`membershipmanagement`)
- Wireframe assets:
  - Element tree: [`../bounded-contexts/membershipmanagement/requirements.md`](../bounded-contexts/membershipmanagement/requirements.md) § "Wireframe: agreetoterms"
  - SVG: [`../bounded-contexts/membershipmanagement/requirements.assets/US-15-003-agreetoterms.svg`](../bounded-contexts/membershipmanagement/requirements.assets/US-15-003-agreetoterms.svg)

### MembershipRegistrationResult · **(unreferenced — review)**

- Workflow position: island — no flow reaches this UI
- User Story: `US-15-007` — 회원가입 처리 결과를 조회한다
- Actor: 회원
- Bound to: ReadModel `MembershipRegistrationResult`
- Owning Bounded Context (for traceability only): **MembershipManagement** (`membershipmanagement`)
- Wireframe assets:
  - Element tree: [`../bounded-contexts/membershipmanagement/requirements.md`](../bounded-contexts/membershipmanagement/requirements.md) § "Wireframe: membershipregistrationresult"
  - SVG: [`../bounded-contexts/membershipmanagement/requirements.assets/US-15-007-membershipregistrationresult.svg`](../bounded-contexts/membershipmanagement/requirements.assets/US-15-007-membershipregistrationresult.svg)

### CreateProfile · **(unreferenced — review)**

- Workflow position: island — no flow reaches this UI
- User Story: `US-16-003` — 기본 프로필을 생성한다
- Actor: 고객
- Bound to: Command `CreateProfile`
- Owning Bounded Context (for traceability only): **MembershipManagement** (`membershipmanagement`)
- Wireframe assets:
  - Element tree: [`../bounded-contexts/membershipmanagement/requirements.md`](../bounded-contexts/membershipmanagement/requirements.md) § "Wireframe: createprofile"
  - SVG: [`../bounded-contexts/membershipmanagement/requirements.assets/US-16-003-createprofile.svg`](../bounded-contexts/membershipmanagement/requirements.assets/US-16-003-createprofile.svg)

### SwitchMemberSession · **(unreferenced — review)**

- Workflow position: island — no flow reaches this UI
- User Story: `US-16-004` — 회원가입 완료 후 정회원 세션으로 전환한다
- Actor: 시스템
- Bound to: Command `SwitchMemberSession`
- Owning Bounded Context (for traceability only): **MembershipManagement** (`membershipmanagement`)
- Wireframe assets:
  - Element tree: [`../bounded-contexts/membershipmanagement/requirements.md`](../bounded-contexts/membershipmanagement/requirements.md) § "Wireframe: switchmembersession"
  - SVG: [`../bounded-contexts/membershipmanagement/requirements.assets/US-16-004-switchmembersession.svg`](../bounded-contexts/membershipmanagement/requirements.assets/US-16-004-switchmembersession.svg)

### MemberProfile · **(unreferenced — review)**

- Workflow position: island — no flow reaches this UI
- User Story: `US-2-003` — 회원정보를 조회한다
- Actor: 회원
- Bound to: ReadModel `MemberProfile`
- Owning Bounded Context (for traceability only): **MembershipManagement** (`membershipmanagement`)
- Wireframe assets:
  - Element tree: [`../bounded-contexts/membershipmanagement/requirements.md`](../bounded-contexts/membershipmanagement/requirements.md) § "Wireframe: memberprofile"
  - SVG: [`../bounded-contexts/membershipmanagement/requirements.assets/US-2-003-memberprofile.svg`](../bounded-contexts/membershipmanagement/requirements.assets/US-2-003-memberprofile.svg)

### UpdateMemberInformation · **(unreferenced — review)**

- Workflow position: island — no flow reaches this UI
- User Story: `US-2-004` — 회원정보를 변경한다
- Actor: 회원
- Bound to: Command `UpdateMemberInformation`
- Owning Bounded Context (for traceability only): **MembershipManagement** (`membershipmanagement`)
- Wireframe assets:
  - Element tree: [`../bounded-contexts/membershipmanagement/requirements.md`](../bounded-contexts/membershipmanagement/requirements.md) § "Wireframe: updatememberinformation"
  - SVG: [`../bounded-contexts/membershipmanagement/requirements.assets/US-2-004-updatememberinformation.svg`](../bounded-contexts/membershipmanagement/requirements.assets/US-2-004-updatememberinformation.svg)

### TermsConsentHistory · **(unreferenced — review)**

- Workflow position: island — no flow reaches this UI
- User Story: `US-2-009` — 약관 동의 이력을 조회한다
- Actor: 회원
- Bound to: ReadModel `TermsConsentHistory`
- Owning Bounded Context (for traceability only): **MembershipManagement** (`membershipmanagement`)
- Wireframe assets:
  - Element tree: [`../bounded-contexts/membershipmanagement/requirements.md`](../bounded-contexts/membershipmanagement/requirements.md) § "Wireframe: termsconsenthistory"
  - SVG: [`../bounded-contexts/membershipmanagement/requirements.assets/US-2-009-termsconsenthistory.svg`](../bounded-contexts/membershipmanagement/requirements.assets/US-2-009-termsconsenthistory.svg)

### UpdateProfileInformation · **(unreferenced — review)**

- Workflow position: island — no flow reaches this UI
- User Story: `US-23-002` — 프로필 정보를 변경한다
- Actor: 회원
- Bound to: Command `UpdateProfileInformation`
- Owning Bounded Context (for traceability only): **MembershipManagement** (`membershipmanagement`)
- Wireframe assets:
  - Element tree: [`../bounded-contexts/membershipmanagement/requirements.md`](../bounded-contexts/membershipmanagement/requirements.md) § "Wireframe: updateprofileinformation"
  - SVG: [`../bounded-contexts/membershipmanagement/requirements.assets/US-23-002-updateprofileinformation.svg`](../bounded-contexts/membershipmanagement/requirements.assets/US-23-002-updateprofileinformation.svg)

### DormantAccountRestorationResult · **(unreferenced — review)**

- Workflow position: island — no flow reaches this UI
- User Story: `US-23-007` — 휴면 상태 해제 시 개인정보 및 서비스 이용 데이터를 복원한다
- Actor: 회원
- Bound to: ReadModel `DormantAccountRestorationResult`
- Owning Bounded Context (for traceability only): **MembershipManagement** (`membershipmanagement`)
- Wireframe assets:
  - Element tree: [`../bounded-contexts/membershipmanagement/requirements.md`](../bounded-contexts/membershipmanagement/requirements.md) § "Wireframe: dormantaccountrestorationresult"
  - SVG: [`../bounded-contexts/membershipmanagement/requirements.assets/US-23-007-dormantaccountrestorationresult.svg`](../bounded-contexts/membershipmanagement/requirements.assets/US-23-007-dormantaccountrestorationresult.svg)

### TerminateAllSessionsAndTokens · **(unreferenced — review)**

- Workflow position: island — no flow reaches this UI
- User Story: `US-25-008` — 탈퇴 완료 시 모든 세션과 토큰을 종료한다
- Actor: 시스템
- Bound to: Command `TerminateAllSessionsAndTokens`
- Owning Bounded Context (for traceability only): **MembershipManagement** (`membershipmanagement`)
- Wireframe assets:
  - Element tree: [`../bounded-contexts/membershipmanagement/requirements.md`](../bounded-contexts/membershipmanagement/requirements.md) § "Wireframe: terminateallsessionsandtokens"
  - SVG: [`../bounded-contexts/membershipmanagement/requirements.assets/US-25-008-terminateallsessionsandtokens.svg`](../bounded-contexts/membershipmanagement/requirements.assets/US-25-008-terminateallsessionsandtokens.svg)

### MembershipWithdrawalResult · **(unreferenced — review)**

- Workflow position: island — no flow reaches this UI
- User Story: `US-26-006` — 탈퇴 결과 안내를 받는다
- Actor: 회원
- Bound to: ReadModel `MembershipWithdrawalResult`
- Owning Bounded Context (for traceability only): **MembershipManagement** (`membershipmanagement`)
- Wireframe assets:
  - Element tree: [`../bounded-contexts/membershipmanagement/requirements.md`](../bounded-contexts/membershipmanagement/requirements.md) § "Wireframe: membershipwithdrawalresult"
  - SVG: [`../bounded-contexts/membershipmanagement/requirements.assets/US-26-006-membershipwithdrawalresult.svg`](../bounded-contexts/membershipmanagement/requirements.assets/US-26-006-membershipwithdrawalresult.svg)

### RestoreMemberAccount · **(unreferenced — review)**

- Workflow position: island — no flow reaches this UI
- User Story: `US-27-002` — 탈퇴한 계정을 복원한다
- Actor: 회원
- Bound to: Command `RestoreMemberAccount`
- Owning Bounded Context (for traceability only): **MembershipManagement** (`membershipmanagement`)
- Wireframe assets:
  - Element tree: [`../bounded-contexts/membershipmanagement/requirements.md`](../bounded-contexts/membershipmanagement/requirements.md) § "Wireframe: restorememberaccount"
  - SVG: [`../bounded-contexts/membershipmanagement/requirements.assets/US-27-002-restorememberaccount.svg`](../bounded-contexts/membershipmanagement/requirements.assets/US-27-002-restorememberaccount.svg)

### RejoinMembership · **(unreferenced — review)**

- Workflow position: island — no flow reaches this UI
- User Story: `US-3-004` — 재가입을 한다
- Actor: 회원
- Bound to: Command `RejoinMembership`
- Owning Bounded Context (for traceability only): **MembershipManagement** (`membershipmanagement`)
- Wireframe assets:
  - Element tree: [`../bounded-contexts/membershipmanagement/requirements.md`](../bounded-contexts/membershipmanagement/requirements.md) § "Wireframe: rejoinmembership"
  - SVG: [`../bounded-contexts/membershipmanagement/requirements.assets/US-3-004-rejoinmembership.svg`](../bounded-contexts/membershipmanagement/requirements.assets/US-3-004-rejoinmembership.svg)

### MembershipStatus · **(unreferenced — review)**

- Workflow position: island — no flow reaches this UI
- User Story: `US-3-005` — 회원 상태를 조회한다
- Actor: 회원
- Bound to: ReadModel `MembershipStatus`
- Owning Bounded Context (for traceability only): **MembershipManagement** (`membershipmanagement`)
- Wireframe assets:
  - Element tree: [`../bounded-contexts/membershipmanagement/requirements.md`](../bounded-contexts/membershipmanagement/requirements.md) § "Wireframe: membershipstatus"
  - SVG: [`../bounded-contexts/membershipmanagement/requirements.assets/US-3-005-membershipstatus.svg`](../bounded-contexts/membershipmanagement/requirements.assets/US-3-005-membershipstatus.svg)

### SubmitWithdrawalReason · **(unreferenced — review)**

- Workflow position: island — no flow reaches this UI
- User Story: `US-5-006` — 회원 탈퇴 사유를 입력 또는 선택한다
- Actor: 회원
- Bound to: Command `SubmitWithdrawalReason`
- Owning Bounded Context (for traceability only): **MembershipManagement** (`membershipmanagement`)
- Wireframe assets:
  - Element tree: [`../bounded-contexts/membershipmanagement/requirements.md`](../bounded-contexts/membershipmanagement/requirements.md) § "Wireframe: submitwithdrawalreason"
  - SVG: [`../bounded-contexts/membershipmanagement/requirements.assets/US-5-006-submitwithdrawalreason.svg`](../bounded-contexts/membershipmanagement/requirements.assets/US-5-006-submitwithdrawalreason.svg)

### MembershipHistory · **(unreferenced — review)**

- Workflow position: island — no flow reaches this UI
- User Story: `US-6-002` — 기존 회원 이력을 조회한다
- Actor: 회원
- Bound to: ReadModel `MembershipHistory`
- Owning Bounded Context (for traceability only): **MembershipManagement** (`membershipmanagement`)
- Wireframe assets:
  - Element tree: [`../bounded-contexts/membershipmanagement/requirements.md`](../bounded-contexts/membershipmanagement/requirements.md) § "Wireframe: membershiphistory"
  - SVG: [`../bounded-contexts/membershipmanagement/requirements.assets/US-6-002-membershiphistory.svg`](../bounded-contexts/membershipmanagement/requirements.assets/US-6-002-membershiphistory.svg)

### TermsConsentRecordList · **(unreferenced — review)**

- Workflow position: island — no flow reaches this UI
- User Story: `US-14-008` — 약관 동의 이력을 조회하거나 철회한다
- Actor: 회원
- Bound to: ReadModel `TermsConsentRecordList`
- Owning Bounded Context (for traceability only): **TermsAndAuthenticationManagement** (`termsandauthenticationmanagement`)
- Wireframe assets:
  - Element tree: [`../bounded-contexts/termsandauthenticationmanagement/requirements.md`](../bounded-contexts/termsandauthenticationmanagement/requirements.md) § "Wireframe: termsconsentrecordlist"
  - SVG: [`../bounded-contexts/termsandauthenticationmanagement/requirements.assets/US-14-008-termsconsentrecordlist.svg`](../bounded-contexts/termsandauthenticationmanagement/requirements.assets/US-14-008-termsconsentrecordlist.svg)

### RecordAuthenticationHistory · **(unreferenced — review)**

- Workflow position: island — no flow reaches this UI
- User Story: `US-22-003` — 인증 이력을 저장한다
- Actor: 인증_시스템
- Bound to: Command `RecordAuthenticationHistory`
- Owning Bounded Context (for traceability only): **TermsAndAuthenticationManagement** (`termsandauthenticationmanagement`)
- Wireframe assets:
  - Element tree: [`../bounded-contexts/termsandauthenticationmanagement/requirements.md`](../bounded-contexts/termsandauthenticationmanagement/requirements.md) § "Wireframe: recordauthenticationhistory"
  - SVG: [`../bounded-contexts/termsandauthenticationmanagement/requirements.assets/US-22-003-recordauthenticationhistory.svg`](../bounded-contexts/termsandauthenticationmanagement/requirements.assets/US-22-003-recordauthenticationhistory.svg)



## See also

- [`ui-flow.md`](./ui-flow.md) — causal order of UI screens across the entire event-modeling flow (the only structural input).
- [`framework.md`](./framework.md) — declared framework + routing/styling conventions (*how* routes are declared, not *which* routes exist).
- `../bounded-contexts/<bc>/domain-terms.md` — Ubiquitous Language dictionary for each BC. Open only the one matching the UI you are implementing, and only to pull names — not for IA.
