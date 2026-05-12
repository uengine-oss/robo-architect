# Bounded Context Canvas: TermsAndAuthenticationManagement

> Generated: 2026-05-12T11:55:59Z

## Purpose

Handles member authentication (identity verification) and terms/consent management for critical membership actions (registration, withdrawal, dormancy reactivation, rejoin). Owns authentication workflows and terms consent records, ensuring that all high-risk or legally required actions are properly authorized and consented.

## Strategic Classification


- **Domain Type.** (not modeled — confirm)
- **Business Model.** (not modeled — confirm)
- **Evolution.** (not modeled — confirm)


## Inbound Communication


| From context | Channel | Message | Pattern |
|---|---|---|---|
| MembershipManagement | Event bus | MembershipWithdrawalRequested | Customer-Supplier *(inferred — confirm)* |
| MembershipManagement | Event bus | MemberAccountCreated | Customer-Supplier *(inferred — confirm)* |
| MembershipManagement | Event bus | MembershipWithdrawn | Customer-Supplier *(inferred — confirm)* |



## Outbound Communication


| To context | Channel | Message | Pattern |
|---|---|---|---|
| MembershipManagement | Event bus | HighRiskActionAuthenticationSucceeded | Customer-Supplier *(inferred — confirm)* |
| MembershipManagement | Event bus | TermsReconsented | Customer-Supplier *(inferred — confirm)* |



## Ubiquitous Language (summary)

See [`domain-terms.md`](./domain-terms.md) for the full glossary. Key terms in this BC:

- `AuthenticationHistory`
- `AuthenticationhistoryId`
- `TermsConsent`
- `TermsconsentId`


## Business Decisions

_(not modeled — confirm)_

## Assumptions

_(not modeled — confirm)_

## External Integrations


_No external-system integrations modeled for this BC._

