# Integration preview

The preview preserves the exact published histories and applies the intended
merge order without updating main. It is a review vehicle, not authorization
to integrate or deploy. Original PRs remain open.

`git diff 12b88f6f origin/codex/schema148-release-readiness-20261017`
was empty. Subsequent focused corrections are new commits on the preview.
Migration001–148 and active release.json remain unchanged. A separate outbox
successor branch is deliberately excluded from the schema148 preview.

New exact-head CI source guards remove PR-head/merge-ref ambiguity. The
candidate artifact workflow now runs for main-target PRs without conditional
path filtering. Every final accepted artifact must bind the final tested source;
previous32c77afd/9a89f4b6 images are historical evidence only.

Before integration: independent review, exact-source checks/artifacts, provider
lifecycle completion, current-data rehearsal, and separately controlled
production admission remain necessary. Do not merge this draft automatically.
