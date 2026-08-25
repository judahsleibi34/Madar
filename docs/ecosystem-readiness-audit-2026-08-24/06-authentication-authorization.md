# Authentication and authorization

## Sessions and browser security

Access and refresh tokens are separated but both stored as HttpOnly cookies. Secure cookies are enabled in production and SameSite is explicitly configured. The readable CSRF cookie contains a signed, session-bound token, not a bearer session. Frontend `apiClient.js` adds CSRF to unsafe methods and performs single-flight refresh handling. No localStorage bearer token path was found.

Exact allowed frontend origins are configured. Signup, login, password and public routes have rate limits. Password reset requests are hashed/stateful with expiry and consumption protection; a legacy reset-link compatibility cutoff remains configuration-controlled. Logout revokes provider session context and push bindings. Sensitive privilege changes are server-authorized and audited.

## MFA/AAL2

Sensitive system-admin routes call `require_system_admin(... require_aal2=True)` and ultimately require `current_level == "aal2"`; AAL lookup failure denies these actions (`services/auth_service.py:564-576`). Admin account-access sessions cannot bypass that requirement.

Login enforcement is weaker. In `routes/auth_routes.py:881-927`, an admin requiring MFA receives an MFA challenge only when verified-factor lookup returns at least one factor. Lookup exceptions are converted to an empty list; an empty list sets `mfa_enrollment_recommended` and issues normal authentication cookies. The test `test_admin_with_no_verified_factor_is_not_locked_out_yet` codifies this behavior. Production readiness checks only the enforcement flag, not actual enrollment.

Factor removal has a second gap: `routes/mfa_routes.py:144-158` converts AAL lookup errors to `{}`, and `:364-374` denies only when a nonempty current level is not AAL2. Missing assurance therefore reaches `unenroll`. This must be `current_level != "aal2"`.

## Authorization

Tenant context is derived from the authenticated local user/membership, not accepted client tenant IDs. Builder, calendar, website and billing routes apply server-side roles/capabilities. Frontend guards improve UX but are not relied upon as the authority. Admin support access is short-lived, audited and route-allowlisted; billing, publish, MFA and password changes reject support context.

## Gate result

G4 is **FAIL (High)** until MFA-required admin login denies no-factor/lookup-failure states, factor deletion fails closed, every production admin is verified as enrolled, and browser/API tests demonstrate AAL1 denial and session revocation.
