# Version6 exact source admission — deliberately non-executable in production

The explicit OUTBOX profile selects source146,target149,migrations147/148/149,
READ_ONLY range146..149, NORMAL target149 only. Its exact combined metadata and
SQL hashes are enforced independently of historical version5. The ordinary
automatic loader rejects the coordinated chain; fresh protected authorization
is mandatory even to construct its admitted manifest. Both queues, deletion
processing, every other client session (including idle), prepared transactions,
queue locks and protocol/schema/cluster identity are checked before each step.

Seven focused successor admission tests PASS, in addition to retained148 profile
and forward-preservation tests. A new11-case native suite exercises the full
locked executor on disposable clones: successful149/2/2 and restricted ACLs,
transaction failures at147/148/149, lost commit responses at all three boundaries,
provider resurrection, idle-session refusal, separately authorized forward
continuation and149 SQL-file substitution. Full retained/new native run122PASS,
0skip. Authorization, provider and consumer transports are explicit test fixtures;
real PostgreSQL, commits, ACLs and journals are not mocked.

The provider state machine is implemented separately with durable private
intent/preimage records, not a second issuer. The installed production adapter
is still absent. `schema149_controller.py` deliberately rejects coordinator
construction, migration witness/guard and target activation. This prevents a new
profile from silently adopting148 positive probes, legacy backup role handling
or fabricated provider evidence. No caller attribute or local PASS packet enables
it. The write handoff separately rejects activation. Full deletion ownership is
also absent at149. These are real blockers, not successful admission.

Installer/frozen-source inventories include the new source modules and exact
metadata for future independent review; no installed controller was modified.
