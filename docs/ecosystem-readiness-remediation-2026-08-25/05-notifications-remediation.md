# Notification and SMTP remediation

## Channel semantics

Email is disabled unless `EMAIL_CHANNEL_ENABLED=true`. Disabled delivery is terminal `revoked` with `email_channel_disabled`; absent/invalid SMTP while enabled is a permanent controlled failure, not an infinite retry. Transient provider/network errors receive bounded retry behavior and permanent recipient/provider errors dead-letter.

The database resolver may fan out an email delivery according to durable preferences; a disabled worker consumes it to a terminal revoked state. This is the selected controlled-fail policy: disabled work does not accumulate as retry/dead poison and remains observable. No SMTP credentials were created and no customer message was sent.

Protected diagnostics expose counts for pending, processing, sent and dead, oldest queued age, last success and safe last error code by channel. Readiness distinguishes worker health from email/push states (`configured`, `disabled`, `degraded`, `unavailable`). Optional SMTP does not make core API readiness false, but it can no longer appear operational.

## Promotion condition

If launch claims email notifications, configure a real provider with securely stored credentials and exercise fake-recipient staging delivery, retry, dead-letter and alert paths. Otherwise keep the channel explicitly disabled and ensure product capability copy reflects that condition. Connect `madar_alert_hook.sh` to an approved provider before production.
