# Runtime configuration remediation

The fail-closed production validator remains authoritative.

Validated production requirements now include:

- dedicated CSRF secret;
- exact 40-character release SHA;
- real build timestamp;
- explicit schema compatibility range 81–83;
- production-safe CORS/cookie/MFA/rate-limit settings;
- remote URL ingestion disabled unless its isolation contract is fully enabled;
- truthful optional email/provider state.

`madar-provision-production-config` is dry-run by default, changes only managed keys, makes an atomic protected backup, preserves owner/mode, and never displays values. The runtime validation command reports only status and non-secret metadata. Final validation reported `status=valid`, production environment, immutable identity configured, schema range 81–83, and email disabled.
