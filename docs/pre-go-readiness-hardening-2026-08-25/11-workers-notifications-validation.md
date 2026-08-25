# Workers and notifications validation

## Worker behavior

Notification and deletion workers run only in the active staging slot. Stopping both caused readiness 503 with separate unavailable components; restarting them restored readiness 200. Release SHA, process state, queue age, and recent activity are observable. Candidate/inactive consumers remain stopped during blue/green validation.

Tests cover restart recovery, lease retry, duplicate jobs, database/Redis interruption, provider timeout, permanent failure, bounded retry, dead-letter handling, tenant scope, and backlog recovery. The calendar worker remains visible as deliberately disabled when its feature is not configured rather than disappearing from diagnostics.

## Email truthfulness

SMTP credentials were not invented. Email is `disabled`, readiness reports it as disabled, and enqueue logic does not create guaranteed poison deliveries. A configured fake provider exercises success/transient/permanent paths without sending real email. Push and each provider channel have separate configured/degraded/disabled states.

Operational metrics expose pending, retrying, sent, dead, oldest age, provider configuration, last success, and safe error class. They do not expose recipients or message bodies.
