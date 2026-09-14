# Commerce P1-B architecture

P1-B extends Madar's existing i18next configuration with a `commerce` namespace for English (`en`) and Arabic (`ar`). Commerce components read the active application locale, apply `ltr` for English and `rtl` for Arabic, and use logical CSS properties for direction-sensitive layout. Money and timestamps are presentation-only transformations through `Intl.NumberFormat` and `Intl.DateTimeFormat`; the store currency, IDs, SKU values, canonical statuses, and persisted timestamps are unchanged.

Localized merchant data uses the requested locale first, then English/default content, then Arabic content. Public catalog responses remain responsible for presenting current localized product, category, attribute, option, and value fields. Delivery areas use `name_en`/`name_ar` with the same fallback. Historical order and option snapshots are never rebuilt from current catalog data; the UI selects a stored snapshot translation when one exists.

Low-stock visibility uses existing inventory fields and adds no schema. A tracked inventory unit is low when its quantity is greater than zero and less than or equal to a non-null threshold. Zero or less is out of stock unless backorder is enabled. Untracked inventory and a null threshold do not produce low-stock warnings. Simple products use product inventory; products with options aggregate active variants only. The catalog response includes low/out counts and flags in the same aggregate query path used for variants, avoiding per-product frontend requests.

Commerce analytics is a provider-neutral, non-blocking browser adapter. `trackCommerceEvent` schedules a `madar:commerce` custom event and optionally calls `window.madarAnalytics.track` when a provider is installed. Provider failures are swallowed and never affect rendering, cart changes, checkout, order creation, or confirmation. The baseline contract contains:

- `view_item_list`
- `view_item`
- `add_to_cart`
- `remove_from_cart`
- `view_cart`
- `begin_checkout`
- `purchase`

Payloads are recursively sanitized to exclude customer name, email, phone, address fields, delivery notes, confirmation tokens, and payment actors. Purchase is emitted only from a durable confirmation result and is deduplicated per order in session storage. This event deduplication is observational and does not change checkout idempotency or transaction behavior.

No database migration is required for P1-B. Production migration remains blocked until the remote Supabase migration ledger (observed through 090) is reconciled with `application_schema_state` (observed at 93); no remote push is part of this phase.
