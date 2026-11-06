# MADAR Frontend Architecture Exception Register

**Status:** APPROVED GOVERNANCE ARTIFACT — contains no approved exceptions
**Governing constitution:** `MADAR_FRONTEND_ARCHITECTURE_CONSTITUTION.md`; v0.2 is committed locally, while v0.2.2 is product-owner approved for the local governance record as of 2026-11-06. Repository-wide adoption remains pending independent review and authorized merge.
**Final architectural approving authority:** Madar product owner

This register records time-limited deviations only where the constitution expressly permits an exception or from an approved lower-level architecture rule. An exception does not amend a constitutional **MUST** or **MUST NOT** and does not grant authority to bypass security, tenant authorization, QA, CI, migration, deployment, production-release, or other higher-level requirements. A binding constitutional change requires the versioned amendment procedure. File presence, a proposed row, or implementation does not constitute approval.

Until the approved constitution completes its repository adoption gates, this file remains a prepared governance artifact. Approval of this empty register does not approve any exception. No current legacy implementation is automatically an approved exception. Legacy behavior remains preserved and must be classified through review before an exception, ADR, or migration decision is assigned.

## Status values

- `PROPOSED`: awaiting product-owner decision; grants no authority.
- `APPROVED`: explicitly approved by the product owner within the recorded scope and dates.
- `EXPIRED`: review or expiry date passed; grants no authority for new work.
- `CLOSED`: deviation removed or no longer applicable.
- `SUPERSEDED`: replaced by an identified ADR, amendment, or newer exception.
- `REJECTED`: product owner declined the deviation.

## Required record fields

Every exception must record:

1. Stable exception ID and title.
2. Constitution rule or approved domain contract affected.
3. Exact files, modules, domains, contracts, and consumers in scope.
4. Rationale and why normal compliance is not currently proportionate.
5. Risks, tenant/security impact, and compatibility impact.
6. Safeguards and validation evidence.
7. Accountable owner and affected-domain reviewers.
8. Product-owner decision and approval date.
9. Finite review or expiry date.
10. Closure, renewal, remediation, or supersession outcome.

An exception cannot silently establish a public contract, expand beyond its recorded scope, or be copied into new code. Renewal requires fresh evidence and explicit product-owner approval. Expiry does not authorize automatic deletion; it requires review and a recorded outcome.

## Exception index

| ID | Title | Rule | Scope | Owner | Status | Approval date | Review/expiry | Record |
|---|---|---|---|---|---|---|---|---|
| _None_ | No architectural exceptions approved | — | — | — | — | — | — | — |

## Exception record template

### EXC-PENDING — Replace with concise title

- **Status:** PROPOSED
- **Affected rule:** PENDING
- **Scope:** PENDING
- **Affected domains/modules:** PENDING
- **Affected public contracts/consumers:** PENDING
- **Rationale:** PENDING
- **Risk and compatibility impact:** PENDING
- **Tenant/security impact:** PENDING
- **Safeguards:** PENDING
- **Validation evidence:** PENDING
- **Accountable owner:** PENDING OWNER DECISION
- **Affected-domain reviewers:** PENDING
- **Product-owner decision:** NOT APPROVED
- **Approval date:** N/A
- **Review/expiry date:** PENDING
- **Closure or supersession:** N/A
