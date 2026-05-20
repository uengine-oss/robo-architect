# Bounded Context Canvas: MembershipManagement

> Generated: 2026-05-12T11:55:59Z

## Purpose

Handles the full lifecycle of membership including registration, status management (active, dormant, withdrawn), login, rejoin, dormant/reactivation, and withdrawal processes. Owns member status, account state transitions, and core membership data.

## Strategic Classification


- **Domain Type.** (not modeled — confirm)
- **Business Model.** (not modeled — confirm)
- **Evolution.** (not modeled — confirm)


## Inbound Communication


| From context | Channel | Message | Pattern |
|---|---|---|---|
| TermsAndAuthenticationManagement | Event bus | HighRiskActionAuthenticationSucceeded | Customer-Supplier *(inferred — confirm)* |
| TermsAndAuthenticationManagement | Event bus | TermsReconsented | Customer-Supplier *(inferred — confirm)* |



## Outbound Communication


| To context | Channel | Message | Pattern |
|---|---|---|---|
| TermsAndAuthenticationManagement | Event bus | MembershipWithdrawalRequested | Customer-Supplier *(inferred — confirm)* |
| TermsAndAuthenticationManagement | Event bus | MemberAccountCreated | Customer-Supplier *(inferred — confirm)* |
| LegalConsentManagement | Event bus | MemberAccountCreated | Customer-Supplier *(inferred — confirm)* |
| TermsAndAuthenticationManagement | Event bus | MembershipWithdrawn | Customer-Supplier *(inferred — confirm)* |



## Ubiquitous Language (summary)

See [`domain-terms.md`](./domain-terms.md) for the full glossary. Key terms in this BC:

- `MemberAccount`
- `MemberaccountId`


## Business Decisions

_(not modeled — confirm)_

## Assumptions

_(not modeled — confirm)_

## External Integrations


_No external-system integrations modeled for this BC._

