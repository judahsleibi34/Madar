# Rollback state

Rollback is based on retained immutable artifacts and traffic selection, never source rebuild.

- Active target: green `4faf63a6...`, schema 83.
- Retained compatible target: blue `ab684468...`, attested schema compatibility 81–83.
- Archived preincident images: explicit `rollback-0eaa9edd...` tags, retained for evidence but not the schema-83 automatic target.

Immediately before the corrective cutover, the controller attested the running
blue SHA and schema compatibility. The first corrective candidate failure was
pre-switch, so blue traffic and consumers were untouched. The successful
cutover stopped blue shared consumers only after green was ready. On a
post-switch failure the controller stops candidate consumers, restores retained
consumers, validates, and switches the proxy back.

This path passed staging fault tests. A disruptive production rollback was not manufactured after successful promotion because it would temporarily duplicate or pause shared queue consumers without adding evidence beyond the real pre-switch recoveries and staging proof.
