# Production readiness — NOT READY

The43-gate machine-readable model in schema148_readiness.py defaults missing
checks to NOT TESTED. PASS needs exact source/digest; operational observations
must match environment and be no older than300 seconds. Staging evidence becomes
PARTIAL for production. Invalid/stale/future/wrong-source evidence fails or blocks.
Reports cannot satisfy independent operator authorization and never emit
AUTHORIZED FOR PRODUCTION or grant a credential. All technical gates PASS can
only yield TECHNICALLY READY FOR OPERATOR REVIEW; human/protected gates remain.

schema148_preflight.py defaults VALIDATE_SOURCE. INSPECT/RECONCILE_REPORT require
explicit expected host/cluster/container/database identity and use bounded BEGIN
READ ONLY SQL. No mode can execute SQL mutations, reconcile providers, alter
workers or issue authority. Its report is evidence, not a protected receipt.

Current production remains146. The new profile/controller is source-only.
Required current-data rehearsal and accepted target148 controller/images, complete
consumer/supervisor inventory, backup/independent restore/replica, exact-source CI,
maintenance/business-impact approval and fresh protected authorization are not
implied by synthetic staging. Main protection is still absent and this identity
has no admin permission. No production mutation is authorized or performed.
