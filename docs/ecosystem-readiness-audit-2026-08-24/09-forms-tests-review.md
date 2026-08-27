# Forms and test/quiz review

## Ordinary forms

Public form identity is derived from the bound published project and form ID. The server filters fields from the published snapshot, bounds answer sizes/types, records tenant/project/version, hashes IP-linked idempotency keys, and inserts through `create_builder_form_submission_safe`. Migration 054 verifies the tenant/project is published, serializes idempotent requests and rejects key reuse with a different request hash. Public form rate limit defaults to 20 requests per five minutes per composed public key. Live production was not mutated.

File fields currently submit client metadata (name/type/size), not a durable attachment upload. This should be labeled as unsupported rather than presented as an uploaded attachment.

## Quiz/test mode — High blocker

The answer key is stored as `quizCorrectAnswer` in the builder form schema. `build_authorized_public_schema` removes `responses` only (`public_site_routes.py:554-562`), and `build_public_form` removes `responses/submissions` only (`:693-697`). Consequently the answer key is sent to unauthenticated clients.

Production evidence:

- five published projects contain answer-key fields;
- 68 published fields contain `quizCorrectAnswer`;
- a safe public GET returned `public_response_contains_quiz_answer_key_field=true` without printing any answer.

Scoring exists in frontend `PageBuilder.quiz.js`. Focus/fullscreen handling exists only in builder preview/workspace (`BuilderFormPreviewPage.jsx:132-139`, `PageBuilder.jsx:5678-5685`). The actual tenant public runtime has no equivalent enforced test session. The backend submission payload sets `quiz_result` to `None` (`public_site_routes.py:2376-2404`) and does not enforce answer secrecy, timer, attempt count, focus loss, close state, randomization, server scoring or pass threshold.

DevTools can read the answer key, suppress visibility/fullscreen handlers, alter local state or call the form API directly. Reload resets client state. Browser focus detection is inherently advisory and must never be described as tamper-proof anti-cheat.

## Required design

Create a server-owned test session/attempt record with opaque attempt ID, start/deadline, state transitions, server-selected randomized question order and idempotent finalization. Public schema must omit answers/scoring rubrics. Score server-side against a private snapshot. Focus events may be recorded as untrusted telemetry and used under an explicit product policy, not as security proof. Add direct-API bypass, replay, concurrent finalize and answer-redaction tests.

G9 is **FAIL (High)** while current quiz/test UI is published.
