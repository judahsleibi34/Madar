# Approved emergency routing operation — failed closed

All three requested safeguards and fresh live bindings passed read-only before
execution. The approved package and plan were unchanged. The exact hash-gated
bootstrap was executed once with the actual operator approval, issuing a new
root-private authorization at 2026-10-08T20:51:29.586521+00:00.

The operation exited 1 (RuntimeError). Its built-in documented compensation
completed at 20:51:35 UTC and recorded maintenance. No repair retry, source
modification, cutover or unrelated operation followed.

Actual post-compensation results:
- https://madarportal.com/: HTTP 503.
- https://api.madarportal.com/: HTTP 503.
- Stable local proxy ports 3000 and 8001: HTTP 503.
- madar-release-proxy: running, unhealthy; serving the validated 503 maintenance
  configuration. Docker restart policy remains unless-stopped; startup gate is
  closed because repair status is maintenance.
- Emergency relay: active/running; installed approved source digest unchanged.
- Registered restricted local fallback remains healthy at backend
  10.254.202.5:8000 and frontend 10.254.202.4:8080.
- Native local Supabase connectivity verified; read-only SQL schema remains 115.
- Both protected transactions remain local_rollback_active.
- Business writes remain disabled; backend denied the nonexistent-path POST
  before business routing with provider_recovery_read_only.
- All six canonical consumers and retained matching workers remain stopped.
- All original protected/runtime input hashes still match the approved plan.
  This operation performed no customer database writes, migrations or restores.

Failure diagnosis from read-only logs: the immediate post-reload frontend check
at 20:51:33 received 502 from an old Nginx worker targeting the reversed frontend
IP. The candidate reload signal occurred that same second. Root requests returned
200 at 20:51:34 before compensation switched both endpoints to 503 at 20:51:35.
This strongly indicates an asynchronous reload verification race: verify_public
checks root availability immediately, before its later proxy-health wait.
The generic RuntimeError/audit records do not preserve the original exception,
so this diagnosis is based on source control flow and actual proxy logs.

Preserved evidence:
- The original reversed routing bytes are retained under the new protected
  attempt directory, with SHA256
  6bc37595f2a95faf0093e8548e47d8cd0d4cde3db79a0388b2cfeffee02ed625.
- New protected namespace:
  /var/lib/madar-control-plane/emergency-routing/87842c3173fe1d6c479f5186d3d0ce59aedbf48cf46515282a925a8cd8365fb6/
- Audit events: fresh_authorization_installed, reconcile_started,
  reconcile_failed_closed (maintenance), installation_failed (maintenance).
- Exact bootstrap command and actual tool completion are recorded in
  .incident-response/emergency-routing-2026-10-08/approved-execution.json.
- This report is an agent-written incident summary, not independent acceptance
  evidence or a protected PASS receipt.

Public availability has NOT been restored. Work stopped after the authorized
compensation and read-only outcome verification. Any corrected wait/check logic
or subsequent publication requires review and a newly approved operation; the
approved package, original receipts and checkpoint manifests remain unchanged.
Historical authorization/checkpoint provenance and normal writable production
blockers remain unresolved.
