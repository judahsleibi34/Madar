# Current governed release architecture

The serving production release was independently verified at schema146.
Serving application/controller identity differs from Git HEAD; exact operational
identifiers are retained in the private operator handoff rather than exported to
Git. The public [inspection summary](evidence/production-inspection-summary.json)
records the readiness states without topology, resource identities or queue data.

The existing completed-NORMAL coordinator owns source packet verification,
root-issued single-use authorization, exact image identities, deployment/upgrade
locks, candidate READ_ONLY authority, maintenance proxy state, owned worker and
boot actor fencing, current-data backups/restore and Node1 replica evidence,
SQL execution, preservation, target grant, promotion and compatible boot recovery.
`web/deployment/lib/completed_normal_{admission,execution,migration,evidence,forward}.py`
and the protected installer are authoritative. Existing profiles1–4 remain exact.

`web/deployment/releases/release.json` is still the historical target146.
Unselected PR210 bridge candidates remain unchanged. This continuation adds a
separate146..148 profile, not a broader automatic-migration policy. It does not
install controller code or activate a release descriptor. Backup sender/receiver
source recognizes explicit148;147 is an incomplete forward-repair state.

Protected control-plane documentation remains in the four root release-policy
files updated alongside source. Synthetic test authorization mocks are not real
credentials or receipts. No deployment actor, installed binary, protected state,
production backup or routing configuration was changed in this session.
