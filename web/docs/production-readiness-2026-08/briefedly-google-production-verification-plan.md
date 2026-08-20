# Briefedly Google production verification plan

Official sources retrieved 2026-08-19; re-check immediately before submission because policy changes are external state.

## Current scope inventory

| Scope | Source use | Classification | Necessity decision |
|---|---|---|---|
| `openid` | identity claims in OAuth connection flow | OpenID identity/basic | retain only if identity-token behavior is actually required; current account identity also comes from Gmail profile |
| `email` | email identity claim | basic/non-sensitive identity | retain only if callback/account binding uses it; verify token response behavior |
| `https://www.googleapis.com/auth/gmail.readonly` | list/search/read messages, threads, bodies, headers/settings | **Restricted** | required for the present feature because Briefedly reads bodies for import/reporting; `gmail.metadata` cannot supply bodies |

Source locations: `backend/app/core/config.py`, Gmail OAuth/client, deployment examples, and deployment documentation. The permitted product framing is user-visible email productivity/reporting and generative summaries for the authorizing user's workspace. Google's current Workspace policy explicitly lists productivity summaries and user-benefit reporting as approved Gmail use cases; acceptance remains Google's decision.

## Applicable official requirements

- [OAuth 2.0 policies](https://developers.google.com/identity/protocols/oauth2/policies): separate projects by tier; accurate verified branding; minimum scopes; owned HTTPS domains; public homepage with functionality, terms, and privacy; encrypted tokens and revocation.
- [Gmail scopes](https://developers.google.com/workspace/gmail/api/auth/scopes): `gmail.readonly` is Restricted; server storage/transmission invokes security assessment.
- [Restricted-scope verification](https://developers.google.com/identity/protocols/oauth2/production-readiness/restricted-scope-verification): brand verification first; declare scopes; detailed justification; English demonstration video; annual assessment when restricted data passes through a third-party server.
- [Workspace user-data policy](https://developers.google.com/workspace/workspace-api-user-data-developer-policy): contextual consent/disclosure, Limited Use, deletion help, encryption at rest/in transit, key management, prompt-injection protection, restricted-scope CASA/security obligations, and prompt incident notice to Google.
- [OAuth best practices](https://developers.google.com/identity/protocols/oauth2/resources/best-practices): secure client credentials, state, PKCE/DPoP consideration, refresh-token invalidation, incremental authorization, and obsolete-client removal.

## Data use and Limited Use

Briefedly may use imported Gmail data only for the visible user-selected import, workspace analysis, source-linked reporting, lifecycle/export/delete, security, and other disclosed permitted purposes. It must not sell/advertise with the data, enable surveillance, or build/train/improve a general/shared AI model with Gmail data. Ollama processing must be inference for the requesting user's visible feature; prompts/responses must not enter model training, telemetry, or human review without explicit permitted consent. Record model/gateway no-training and no-content-log evidence.

## Engineering prerequisites

| Item | Owner type | Status | Evidence for submission/assessment |
|---|---|---|---|
| P0 DB/runtime/backup/Ollama closure | engineering/operations | BLOCKED BY P0 | role flags, off-host restore, current worker/schema/image |
| separate dev/staging/prod OAuth projects/clients | Google project owner | BLOCKED BY PROVIDER | project/client inventory without secrets |
| PKCE S256 with verifier stored server-side and one-time | backend | READY | interception/replay tests; no verifier logs |
| durable provider revocation retry/status | backend/worker | READY | timeout/retry/reconnect/delete tests |
| token/key rotation and DPoP feasibility decision | security/backend | READY | rotation drill; documented Google support/client library path |
| encrypted token and restricted data at rest | security/operations | PARTIAL | Fernet exists; KMS/equivalent key custody/rotation and DB/backup encryption proof needed |
| TLS on every external transfer | operations | PARTIAL | Google HTTPS and target Ollama HTTPS design; real path pending |
| deletion/export/retention worker | privacy/operations | BLOCKED BY P0 | live worker, job completion, backup aging proof |
| prompt-injection/evidence controls | AI/security | PARTIAL | strong structured evidence tests; adversarial/external test required |
| incident detection and Google notification decision | security/legal | READY | tested runbook and contacts |
| human-access controls | privacy/security | READY | explicit consent/support audit or proof operators cannot read content |

## Product and policy prerequisites

- Verified owned production domain and HTTPS homepage accurately describing Briefedly.
- Terms, privacy policy, support contact, deletion instructions, account closure, and incident/security contact linked from homepage and OAuth configuration.
- Prominent in-product disclosure immediately before Gmail consent, separate from terms: data types, import window/search, body/metadata storage, workspace sharing, Ollama inference, retention, deletion/revocation, and subprocessors.
- Affirmative consent; no pre-checked/implicit consent. Ordinary members' ability to read imported workspace email must be disclosed to the connecting owner.
- Limited Use affirmative statement and accurate retention/no-training language reviewed by counsel.
- Current subprocessor/location and data-flow diagrams.

## Likely Google evidence package

1. Verified branding/domain ownership and exact redirect URIs/origins.
2. Scope list and endpoint-by-endpoint justification explaining why metadata-only scope fails the user-visible body analysis.
3. English unlisted video from pre-consent disclosure through grant, import, report/source evidence, disconnect, delete/export.
4. Architecture/data-flow diagram including Google, Briefedly, DB/backups, Ollama gateway/model, browser, operators.
5. Privacy/terms/delete/support URLs and Limited Use statement.
6. Encryption/key-management, access control, vulnerability/patch, logging/redaction, backup/restore, incident, and deletion evidence.
7. CASA assessor artifacts/Letter of Validation as directed by Google; budget and lead time must be approved.

## Submission sequence

1. Counsel/product approve use, disclosures, retention, workspace-sharing model, and AI statement.
2. Engineering closes P0/P1 evidence and completes ASVS/WSTG remediation.
3. Create and validate the separate production Google project without real users.
4. Publish/verify branding and URLs.
5. Record demonstration from a synthetic/test mailbox.
6. Submit restricted-scope verification; respond to Trust & Safety.
7. Complete the required Google-designated CASA/security assessment and remediate findings.
8. Only after approval, perform a limited private Gmail beta with monitoring and revocation/deletion drill.

Owner: product owner + Google Cloud project owner + security lead. Current status: **REQUIRES EXTERNAL ASSESSMENT**; launch blocker for private/paying Gmail.
