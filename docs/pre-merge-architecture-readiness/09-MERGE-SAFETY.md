# Merge safety: conditional, not established

Can Saliba and Judah merge while production auto-deployment remains disabled?
**Do not proceed on the evidence available here.** Engineering acceptance is
incomplete, Full Provider Staging refuses Class D, and external merge/push
integrations still require administrator verification.

Read-only observation on2026-10-21 found main at
876b65e73ea8ceaf398145d8677019184798a95c, unprotected. The inspected deployment
timer was disabled/inactive and its service inactive. No state was changed.
This snapshot does not prove that every external deployment actor is disabled.

Source workflows validate/build on pull requests and main pushes with read-only
permissions; none supplies production write authority. Main push will still
trigger those checks/builds. Existing auto-deploy entrypoints/timer can matter
if separately enabled; source integration and runtime activation remain distinct.

Webhook API inspection is denied without administrator hook visibility. The
earlier confirmation about PR edit/close events does not establish push/merge
safety. An administrator must verify webhooks, installed apps, external polling
and protected environments, then configure required reviews/checks, restricted
bypass/force-push/deletion and deployment permissions.

Do not treat docs, green application checks, passwordless sudo or repository
push permission as branch protection or deployment authorization. PR220 remains
draft and unmerged; no production migration/controller/timer change is authorized.
