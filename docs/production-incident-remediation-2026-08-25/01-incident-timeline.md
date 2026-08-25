# Incident timeline

All times are UTC on 2026-08-25.

- The legacy timer detected remote `main` at `eb22f736...` while production served `0eaa9edd...`.
- The legacy deployer checked out the candidate, built mutable/default Compose images, and recreated the live stack.
- Candidate backend startup failed before readiness because the new production configuration contract was not satisfied.
- The legacy script reset the checkout, rebuilt old source, and recreated the previous stack. Journal evidence records rollback frontend/backend health passing and rollback completion at approximately 14:09.
- The two-minute timer retried the unchanged remote SHA, producing repeated build/recreate windows and Cloudflare 502 responses while the stable origin ports were absent.
- The operator stopped `madar-auto-deploy.timer`; production recovered on `0eaa9edd...`.
- Disposable candidate validation reproduced, in order, missing dedicated CSRF configuration, missing immutable release identity, and unsafe remote-ingestion configuration.
- Development fixes and exact candidate tests were completed. Immutable artifacts for `ab684468...` were built and validated in staging.
- A verified manifest backup began at `15:43:21`; schema 81 was confirmed.
- Green was prepared inactive, promoted through the stable proxy, and adopted as known-good without an in-place rebuild.
- Migrations 82 and 83 were applied with the locked executor; schema 83 was verified.
- Initial blue creation attempts failed safely before traffic switch because Docker's default address pools were exhausted. Deterministic slot IPAM fixed this.
- One subsequent blue attempt failed safely during worker cutover because the backend lacked the deletion-worker health URL. Green workers were restored and traffic was unchanged.
- The explicit health URL and bounded candidate-readiness diagnostics were added.
- At `16:24:19`, traffic switched to blue. The observation period completed at `16:25:22`; blue was recorded known-good and the failed-SHA record was cleared.
- The production checkout was fast-forwarded to the exact running application SHA without container recreation.
