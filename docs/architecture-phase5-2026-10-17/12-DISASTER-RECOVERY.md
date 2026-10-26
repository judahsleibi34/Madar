# Schema149 backup and independent component restore

A new native149 drill PASS in109.487s. Original full role DDL was captured and
fsynced BEFORE temporary NOLOGIN. Providers/ingress/objects/workers were fenced,
sessions drained, and stable149 database plus object bytes captured. A new
network=none PostgreSQL17 cluster restored original roles and the database;
rows/sequences/Auth/MFA/Storage tables,149/2/2, original role state and restricted
queue grants matched. A separately owned object volume restored byte-for-byte.
The owned temporary PostgreSQL container was removed; private archives and useful
owned object evidence remain. Exact original source providers were recovered.

Two rejected attempts were preserved, not counted as PASS: the generic production
fence() correctly expected origin146 while this component backup begins at149;
then a backup role file was incorrectly placed in the strict journal directory.
The corrected component uses ordered effects plus explicit149 quiescence and a
separate private archive directory. Core source146 checks and journal validation
were not weakened. The first fenced attempt was explicitly recovered before
retry. No historical journal or approval was overwritten.

The native backup uses parent213 source5fb997bf149 runtime; Phase V final fresh
images are accepted separately. Restored tables/objects and native source restart
are proven; the independent restored database was NOT attached to a complete new
application provider stack. Full149 restored-application acceptance, WAL/PITR,
object versioning consistency, off-host recovery and replica receiver admission
remain unproven here. Earlier componentPITR is historical, not a149 or RPO/RTO
certification. No production backup/replica paths or customer data were used.
