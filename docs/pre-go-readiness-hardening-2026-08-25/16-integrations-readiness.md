# Released integrations readiness

## Launch scope

No real provider was contacted. Google/Microsoft calendar and other released integration paths were tested with fakes for OAuth state, callback ownership, scopes, encrypted token storage, refresh, expiration, disconnect, provider outage, tenant binding, and deletion cleanup.

Provider configuration is separate from licensing and provider health. An unconfigured provider cannot appear operational merely because a tenant is entitled. Disabled integrations do not block core application readiness.

## Microsoft revocation boundary

Local encrypted Microsoft credentials are removed durably. Provider-side grant revocation is not implemented and is explicitly reported as an unsupported retained condition during deletion. Microsoft calendar must remain disabled for production until its release gate includes a supported provider revocation mechanism and mocked tests. This does not block launch while the feature is disabled.

Google Drive, OCR, WhatsApp, unreleased mobile features, unrelated AI functions, and the future payment gateway remain roadmap items and were not implemented.
