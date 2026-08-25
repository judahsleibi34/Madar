# Administrator MFA remediation

## State model

- Non-admin users retain the existing normal authentication path.
- An admin with a verified factor receives only a pending challenge state until exact AAL2 verification.
- An admin with no verified factor receives an enrollment-only pending cookie. Allowed operations are restricted to status, enrollment, verification and logout; ordinary admin cookies are not issued.
- Factor lookup/provider error returns a controlled 503 and no privileged session.
- Factor removal verifies current-account ownership and exact `current_level == "aal2"`; missing, unknown and AAL1 results fail closed. Removing the final verified admin factor is denied and the attempt is audited.

Evidence is concentrated in `web/backend/routes/auth_routes.py`, `mfa_routes.py`, and `admin_profile_routes.py`. Existing sensitive admin APIs retain `require_aal2=True`.

## Recovery policy

There is intentionally no hidden public break-glass bypass. If all verified factors are lost, recovery requires an authenticated Node 1 operator to verify identity, preserve an audit/incident record, use the upstream auth-provider administrative recovery procedure, and force fresh enrollment before restoring ordinary access. Production promotion must turn this policy into an operator runbook and conduct a non-production drill; that remaining operational item does not justify a fail-open API.

## Verification

Tests cover no factor, verified/unverified factors, provider error/malformed response, AAL1/AAL2/missing AAL, enrollment-only access, login verification, factor ownership, last-admin-factor denial, refresh/privilege behavior and logout contracts. No real administrator or production factor was changed.
