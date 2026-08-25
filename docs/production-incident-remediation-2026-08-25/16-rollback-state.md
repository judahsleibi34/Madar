# Rollback state

Rollback is based on retained immutable artifacts and traffic selection, never source rebuild.

- Active target: blue `ab684468...`, schema 83.
- Retained compatible target: green `ab684468...`, declared schema compatibility 81–83.
- Archived preincident images: explicit `rollback-0eaa9edd...` tags, retained for evidence but not the schema-83 automatic target.

Immediately before blue startup, the controller attested the running green SHA and schema compatibility. Each pre-switch blue failure restored green queue consumers and left the stable proxy on green. The successful cutover stopped green shared consumers only after blue was ready. On a post-switch failure the controller stops candidate consumers, restores retained consumers, validates, and switches the proxy back.

This path passed staging fault tests. A disruptive production rollback was not manufactured after successful promotion because it would temporarily duplicate or pause shared queue consumers without adding evidence beyond the real pre-switch recoveries and staging proof.
