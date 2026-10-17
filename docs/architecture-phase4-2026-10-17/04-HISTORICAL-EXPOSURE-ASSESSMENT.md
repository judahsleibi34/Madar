# Privacy-preserving historical triage

`web/scripts/audit_historical_exposure.py` scans reachable main/PR209/210/211
textual source/configuration/document blobs without network access. It never
emits candidate values, changes history, revokes credentials or publishes raw
findings. New private reports use0700 directories and0600 files outside Git.
A real temporary-Git regression proves deleting a token in a later commit does
not remove its historical candidate.

The expanded run examined12,551 blobs /247,090,273 bytes with zero omissions
within the selected suffix scope. It found346 credential-assignment candidates,
11 credential-shaped URIs, one private-key marker and470 private-network metadata
matches. No JWT, GitHub token or AWS access-key match was found. These are pattern
matches, not verified active secrets. See sanitized evidence summary.

Reviewed credential-like cases were code expressions, mock/test literals,
vendor parser markers and synthetic/interpolated staging defaults. No active
credential exposure was confirmed. No production credential was rotated or
external credential validation attempted. Arbitrary binary contents, omitted
suffixes, obfuscated values and credentials outside these patterns remain outside
certified coverage. A zero-match category is not proof of absence.

Historical operational metadata remains reachable, including earlier versions
of forward-redacted reports. Raw references and value hashes stay private; no
private endpoint, queue record, backup path or credential value is included
here. No history rewrite was performed. If further private review confirms a
genuine credential, independently authorize containment/rotation, record affected
blob/commit references and handle public-history remediation as a separate incident.

Historical customer-record classification beyond selected source/reports was not
completed. This scan does not certify data-free repository history.
