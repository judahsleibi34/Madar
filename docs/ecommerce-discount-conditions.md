# Multi-product discount conditions

Schema 100 adds up to ten conditions, each selecting one to one hundred
store-owned active/inactive products, a percentage (0.01–100%), an audience and
lifetime or fixed-period validity (1–3650 days). At least one condition must be
a loyalty reward. Saving from the editor activates loyalty settings; there is no
separate enable switch. Existing unlocked rewards keep their historical terms.

Normal offers need no points and remain a fallback for all customers, including
guests. Verified customers who unlock rewards also qualify for their snapshotted
loyalty offers. For each product, checkout takes the higher eligible percentage,
never stacks offers, and favors loyalty on equal percentages. Products not in an
eligible condition are unchanged. Variants of a selected product are included.

Normal fixed periods begin when a rule version is saved. Loyalty fixed periods
begin when the reward is unlocked. A lifetime offer and an expiring offer can
coexist, including different percentages for the same product.

One threshold unlocks one bundle covering all loyalty conditions. It does not
spend the threshold once per product. Individual conditions can expire without
expiring lifetime offers in that bundle. Revocation restores its threshold once.
Historical rewards are not rewritten by later product/percentage/validity edits.
Order and line-item price, discount source and winning entitlement snapshots
remain authoritative; client cart calculations are previews only.

The new save RPC validates tenant products and uses legacy atomic rule versioning.
Old rules and entitlements with empty condition arrays retain their original
single-product 10% behavior. Before schema 100, only exactly representable legacy
settings may fall back; no extra products or percentages are silently dropped.
Missing loyalty storage does not hide the draft editor, but Save is disabled.

Migration 100 is mirrored and checksum-pinned in the 097–100 manifest. Apply only
through the reviewed release/migration workflow, after bridge acceptance and a
verified backup. The isolated rehearsal does not modify the application database.
