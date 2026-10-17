# Notification reconciliation — inspection only

RECONCILE_REPORT classifies canonical pending/processing/sent/dead counts, plus a
bounded500-row processing sample with opaque delivery-reference hashes, channel,
attempts and valid/expired-or-missing lease. Revocation is represented by existing
dead/error semantics, not an invented canonical status. Every processing outcome
is labeled uncertain until independent provider evidence is reviewed. Counts may
exceed the bounded sample; truncation cannot become clearance.

Never infer external acceptance from provider_message_id alone, expired leases,
absence of a live process or canonical pending status. Acknowledgement may have
failed after SMTP/push acceptance. Do not reset uncertain rows to pending, mark
sent, delete them, or invoke an unfenced RPC to satisfy migration147. The read-only
tool never performs any such mutation. Root/operator reconciliation approval and
any required customer-data change are separate controlled production operations.
Migration147 and live admission both refuse all remaining processing rows.

Future operator review must preserve original state/provider receipts, establish
stable delivery identity, classify known accepted/known rejected/unknown outcomes,
review duplicate risk and approve the exact resolution. If evidence is missing,
BLOCK the release. This session uses synthetic outcomes only.
