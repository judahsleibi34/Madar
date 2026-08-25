# Quiz/test security remediation

## Result

`MADAR-FORM-001` is fixed in development code and migration 082. Public clients no longer receive answer/rubric/scoring secrets, and the server owns attempt identity, timing, publication version, ordering, attempt limits, scoring and completion.

## Implementation

- `web/backend/services/public_quiz_service.py` is the canonical recursive redactor and grading implementation. It removes key variants including correct/expected answers, answer keys, weights, rubrics, scoring modes and pass thresholds from any public publication subtree.
- Every public schema path in `web/backend/routes/public_site_routes.py` passes through `build_authorized_public_schema`; the legacy generic submission endpoint refuses quiz-mode submissions.
- Start creates a private attempt containing tenant, project, form, immutable publication version/hash, server order, server deadline, subject hash and private grading snapshot.
- Finalize accepts only `answers`. Pydantic rejects extra client fields such as score, pass/fail, deadline, order or attempt number. The RPC row-locks the attempt and verifies tenant/project/form/publication before accepting the server result.
- Migration `082_create_public_quiz_attempts.sql` is identical in both migration trees, enables RLS, revokes public/anon/authenticated table and function access, grants only service-role RPC execution, serializes attempt-count creation with a transaction advisory lock, and makes finalize idempotent.
- The minimal frontend change calls start/finalize and displays only the returned server result. Appearance/layout were not changed.

## Isolated database proof

Migration 082 was applied twice to disposable PostgreSQL 17. Evidence: schema state 82; 14 constraints; three indexes; two RPCs; zero anon table privileges. A second limited attempt returned `quiz_attempt_limit_reached`; duplicate finalize returned the first result with `duplicate=true` and created only one form submission; expiration returned `quiz_attempt_expired` and persisted `expired`.

The first isolated exercise exposed a PL/pgSQL variable/column ambiguity for `submission_id`; both migration mirrors were corrected to `saved_submission_id` and the complete exercise then passed. No remote or production database was touched.

## Security limits

Browser `visibilitychange`, blur and lifecycle events are advisory and manipulable. They preserve the product’s close-on-leave experience but are not represented as tamper-proof anti-cheat. Security derives from non-disclosure, server deadline, attempt state and server scoring. Migration 082 must be promoted using the compatibility sequence in `06-deployment-redesign.md`.
