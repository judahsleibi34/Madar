# Product verification and limits

Executed frontend:233 files,1713PASS/1SKIP, lint and production /api-origin build.
New native product coverage: actual GoTrue login, two users, calendar creation,
sharing, private event creation, editor→availability downgrade and501-event reads.
These exercise API/provider/database boundaries rather than browser UI.

Final fresh-source browser/Auth/MFA acceptance is recorded after source freeze
in PR212's acceptance update; this file does not presume its result. Historical
32c77afd browser checks are not relabelled as final-source acceptance.

Forms concurrent edit/delete, builder draft/publish/public routing, asset
upload/replace/delete, complete checkout, onboarding and role-management browser
workflows were NOT newly executed in this session. Existing component tests and
prior synthetic smoke tests do not establish complete product E2E coverage.
Screenshots/credentials/cookies/TOTP secrets are not committed.
