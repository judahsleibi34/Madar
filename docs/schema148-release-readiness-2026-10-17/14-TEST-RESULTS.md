# Executed validation — evolving record

Staging dedicated VM, current uncommitted continuation source:

- Focused admission/controller suite:10 PASS,0.055s.
- New native coordinated executor suite:16 PASS,11.634s. Each test clones a marked
  disposable schema146 database and uses the actual executor, exact147/148 SQL,
  native locks/transactions/grants/journal. Authorization and supervisor transport
  are explicit fixtures; they create no real authority or production receipts.
- Existing native upgrade:5 PASS,0.068s; fencing:17 PASS,6.826s;
  business:22 PASS,2.811s.60 native cases executed in total.
- First broad run3715/741 skips found1 protocol-bool validation failure and4
  errors:2 missing source-fixture paths,2 from a misplaced legacy-path block.
  Strict typing/source fixtures/legacy scope corrected; assertions retained.
  Initial Docker mountpoint failure was staging harness preparation, not a code
  defect. Focused discovery also needed its explicit repository import path.
- Corrected broad rerun:3717 collected,743 conditional skips,2974 executed PASS,
  43.403s; external attempts/sites empty. Final committed-source evidence supersedes
  these initial counts. No production operation or external notification/payment used.

Command: BACKEND_TEST_IMAGE=madar-schema136-preparation-test:working bash
web/scripts/rehearse_migration_148.sh on madar-staging. It includes coordinated
admission tests before existing147/148 suites. Private logs are retained under
/home/staging-admin/schema148-readiness-20261017/. Source policy/lock/mirror/
transition/forward-release checks pass; historical013/014 warnings retained.
