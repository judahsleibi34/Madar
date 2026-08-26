# Final production readiness

## Current service

**PRODUCTION HEALTHY. CORRECTIVE PROMOTION SUCCESSFUL.** The active release
`4faf63a6...` is immutable, externally reachable, schema compatible, fully
ready with required workers, and contains the corrected canonical API origin.
The login request path now reaches `https://api.madarportal.com/auth/login`;
credential-free validation proves correct JSON/CORS behavior.

## Deployment readiness

Manual controlled immutable promotion and critical login-path gate: **GO**.

Unattended automatic promotion: **NO-GO until the tracked root systemd units are installed and the safe no-op is verified**. The timer is inactive but remains enabled at boot, so the host must not be rebooted before the root operator disables/replaces the legacy unit.

## Security readiness

**NO-GO until the previously exposed provider credential is rotated.** The application/configuration fixes do not reduce the risk of an already exposed credential.

## Deferred product/DR readiness

- Billing entitlement gate remains blocked on authorized commercial assignments.
- Full DR remains blocked on physical media and a replacement-host restore drill.
- Payment gateway is future work.

The current release may continue serving while the immediate operator actions are completed, but these conditions must not be represented as a fully unconditional production GO.
