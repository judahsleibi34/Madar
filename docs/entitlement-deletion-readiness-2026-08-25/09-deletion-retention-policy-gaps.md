# Retention policy gaps

The technical workflow deliberately does not invent legal or commercial retention terms. These decisions remain explicit conditions:

1. Approve duration and minimization/pseudonymization fields for security/audit metadata.
2. Approve treatment and duration for billing history and billing webhook replay metadata.
3. Approve retention/anonymization of analytics aggregates, visitor identifiers, IP/user-agent-derived data, form submissions, quiz results, and reservations where deletion is not desired.
4. Approve retention and purge duration for redacted deletion workflow evidence.
5. Decide whether Microsoft provider-grant revocation must be implemented before enabling Microsoft calendar for customers; current code removes encrypted local credentials and reports provider revocation as unsupported.
6. Define the operator procedure for failed-manual-intervention reset without editing request state ad hoc.
7. Register deletion adapters and disposition policy before releasing any new external integration.

Until approved, the completion report lists retained classes. It never silently claims those classes were deleted. These are product/operations policy gates, not inferred legal requirements.
