# Source freeze and external acceptance receipts

A commit cannot contain its own SHA or later CI/runtime receipts without changing
its identity. The source-freeze commit therefore retains executed earlier scoped
reports and the final acceptance procedure. Its later exact-SHA GitHub runs,
authenticated artifact receipt, runtime image IDs and native/browser acceptance
are recorded in the draft PR acceptance update and final response. Private local
receipts remain outside Git; no later documentation commit relabels accepted
images. Pending gates here are not presumed passed. Production authorization is
always a separate protected decision.
