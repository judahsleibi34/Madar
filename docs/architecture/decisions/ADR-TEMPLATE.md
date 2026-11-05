# MADAR Frontend Architecture Decision Record

**ADR ID:** ADR-PENDING
**Title:** Replace with a concise decision title
**Status:** PROPOSED
**Decision owner:** PENDING OWNER DECISION
**Affected business domains:** PENDING
**Affected technical modules:** PENDING
**Prepared:** YYYY-MM-DD
**Product-owner approval:** NOT APPROVED
**Approval date:** N/A
**Re-evaluation trigger/date:** PENDING
**Constitutional impact:** None / amendment proposed

Status values are `PROPOSED`, `APPROVED`, `SUPERSEDED`, `REJECTED`, or `WITHDRAWN`. Only the Madar product owner may mark a frontend architecture ADR `APPROVED`. Approval is architectural only and cannot waive security, tenant authorization, QA, CI, migration, deployment, or production-release requirements. An approved ADR may justify or authorize a constitutional amendment, but it does not itself override a constitutional **MUST** or **MUST NOT**. A binding change requires a separately versioned constitutional amendment, documented impact review, explicit product-owner approval, and recorded effective date and scope.

## Context and evidence

Describe the verified current state, the decision pressure, affected users and consumers, and the evidence inspected. Separate verified facts, interpretations, and unknowns. Link to relevant contracts and tests without including secrets or private evidence.

## Decision

State the exact architectural decision, its boundaries, and what it does not authorize. If it proposes a constitutional amendment, identify the affected requirement and the separate versioned amendment required before that requirement changes.

## Alternatives considered

List credible alternatives, including retaining the current design, and explain why each was accepted or rejected.

## Ownership and consumers

Identify the accountable business domain, technical module, shared-capability owner, and all known consumers. Use `PENDING OWNER DECISION` rather than inferring unresolved ownership.

## Contracts and compatibility

Identify public contracts, private implementation boundaries, persisted schemas and identifiers, API shapes, versioning, supported historical content, and migration or fallback behavior.

For Page Builder changes, cover editor, preview, published website, hosted runtime, academy consumers, forms where relevant, themes, accessibility, Arabic/English, and RTL/LTR behavior.

## Tenant, security, and authorization impact

Explain tenant scope, FastAPI's existing backend authority, verified server-side isolation/authentication/authorization, permissions, entitlements, data ownership, public access, browser storage/cache isolation, data exposure, and security review requirements. Frontend modules, visibility, and plugin/extension metadata are never backend authorization. A proposed backend service-ownership or authorization-architecture change requires an ADR, security review, compatibility validation, and product-owner approval.

## Commercial and lifecycle impact

Record commercial-module, subscription, product-lifecycle, hosted-exposure, and deployment implications. Mark unresolved packaging or lifecycle decisions `PENDING OWNER DECISION`.

## Implementation and dependency impact

Describe dependency direction, new or changed public entry points, cross-domain coordination, plugin/extension behavior, state and styling ownership, and any legacy compatibility constraint. An approved ADR does not itself authorize implementation.

## QA, CI, and release impact

List applicable unit, integration, browser, compatibility, tenant/security, RTL/accessibility, performance, and release checks. Preserve all root `AGENTS.md` and release-policy requirements. Never claim an unexecuted check passed.

- **Existing architecture checks:** PENDING
- **Proposed architecture checks:** PENDING
- **Accountable CI enforcement owner:** PENDING OWNER DECISION
- **Planned verification milestones:** PENDING OWNER DECISION
- **Review trigger/date:** PENDING OWNER DECISION

Future architecture CI automation is not a prerequisite for Constitution v0.2 adoption.

## Rollback, migration, and failure handling

Describe safe withdrawal before release, forward compatibility after persisted or published changes, rollback limits, and failure/recovery behavior. Do not prescribe production mutation outside existing release authority.

## Risks and unresolved questions

List residual risks, evidence gaps, and every decision still requiring product-owner input.

## Approval record

- **Product-owner decision:** NOT APPROVED
- **Decision date:** N/A
- **Approved scope:** N/A
- **Conditions:** N/A
- **Related exception IDs:** None
- **Related constitutional amendment:** None
- **Supersedes / superseded by:** None
