# Residual P0 risk register

## R-P0-001 — Exposed credentials remain valid

Severity: CRITICAL
Status: BLOCKED

Supabase-related credentials, Briefedly’s bootstrap/runtime database credential, and the separately re-exposed host PostgreSQL administrator credential have not been rotated/revoked. Old-key invalidation is unproven.

Required action: complete provider/DB rotations only after off-host recovery and replacement paths are proven; then verify old authentication fails and review security logs.

## R-P0-002 — Madar runtime still receives catastrophic direct DB privilege

Severity: CRITICAL
Status: BLOCKED IN PRODUCTION

Development removes the direct URL, but current production containers remain unchanged. A backend/worker compromise can still obtain the credential from its environment.

Required action: gated Compose cutover followed by provider rotation/revocation.

## R-P0-003 — Briefedly live runtime remains superuser/object owner

Severity: CRITICAL
Status: BLOCKED IN PRODUCTION

The tested role split is not deployed. Live application compromise retains cluster-wide control.

Required action: execute the reviewed role/migration sequence after all gates pass.

## R-P0-004 — No off-host recovery

Severity: CRITICAL
Status: BLOCKED

Current backups are on the same physical host. Disk loss, ransomware, or host-account compromise can destroy production and backups together.

Required action: provision encrypted versioned/immutable off-host storage and prove remote restore.

## R-P0-005 — Madar full-platform restore not demonstrated

Severity: HIGH
Status: PARTIAL

Public schema and files restore, but Supabase Vault/Auth/PostgREST/Storage recovery is not demonstrated.

Required action: provider-compatible isolated recovery exercise.

## R-P0-006 — Mailcow has no current coherent backup

Severity: HIGH
Status: BLOCKED

The supported backup method needs review/maintenance controls; no new Mailcow recovery point exists.

Required action: approved consistent backup plus isolated recovery drill including custom configuration and cryptographic material.

## R-P0-007 — Briefedly stale production

Severity: HIGH
Status: BLOCKED

Production is five migrations behind, lacks a worker, uses old images, lacks current headers, and cannot start current code with live Ollama transport.

Required action: provision gateway/off-host recovery, then controlled reconciliation.

## R-P0-008 — Failed/incomplete local backup can be mistaken for good

Severity: MEDIUM
Status: OPEN

A failed Madar run left a zero-byte dump directory. Automation must publish an atomic success marker only after all verification and remote confirmation complete.

## R-P0-009 — Production-derived recovery artifacts require strict custody

Severity: MEDIUM
Status: MITIGATED LOCALLY

Disposable restored clones and the temporary restored asset directory were removed after evidence capture. The required local backup copies remain beneath mode-0700 parent directories with mode-0600 dump/manifest files. They are still co-resident with production and therefore remain exposed to host loss or account compromise until encrypted off-host custody exists.

## R-P0-010 — Frontend Page Builder regressions

Severity: MEDIUM
Status: PRE-EXISTING / P1 HANDOFF

Two known renderer tests fail. They do not block the P0 database design but remain a product regression before broader release.
