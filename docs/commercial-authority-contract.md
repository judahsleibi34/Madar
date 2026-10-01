# Madar Commercial Authority & Launch Pricing Contract

**Document ID:** MADAR-COMMERCIAL-CONTRACT
**Version:** 2.0
**Status:** Approved commercial policy; schema-115 foundation implemented locally, production activation pending
**Document date:** 2026-09-30
**Target catalog:** `launch_2026`
**Currency:** USD
**Billing basis:** Monthly recurring subscription unless an approved tenant-specific order states otherwise
**Repository target:** `docs/commercial-authority-contract.md`

> **Important scope note**
>
> This is Madar's **normative internal commercial/product contract**. It defines the commercial
> source of truth that product, backend, database, admin tooling, billing, entitlement checks,
> migrations, tests, and customer-facing pricing must implement.
>
> It is **not** Madar's customer-facing Master Services Agreement, Terms of Service, Data Processing
> Agreement, privacy notice, tax advice, or legal opinion. Customer legal documents must be reviewed
> separately for the jurisdictions in which Madar operates.

---

## 1. Purpose

This Contract establishes one authoritative commercial model for Madar.

It defines:

1. the core Madar modules;
2. the launch/founding-customer price book;
3. bundle pricing;
4. price-lock and grandfathering rules;
5. module upgrade, downgrade, cancellation, suspension, and reactivation rules;
6. the separation between product assignment and effective commercial access;
7. the treatment of add-ons, storage, AI, future products, and third-party costs;
8. administrative authority and security requirements;
9. commercial history, idempotency, concurrency, and audit requirements;
10. catalog versioning and future pricing changes;
11. migration treatment for legacy plan names;
12. implementation and conformance requirements.

The objective is to prevent pricing, authorization, billing, UI, and historical records from
developing independent or contradictory definitions of what a tenant purchased.

---

## 2. Normative language

The key words **MUST**, **MUST NOT**, **REQUIRED**, **SHALL**, **SHALL NOT**, **SHOULD**,
**SHOULD NOT**, and **MAY** are normative.

- **MUST / SHALL**: mandatory for a conforming implementation.
- **MUST NOT / SHALL NOT**: prohibited.
- **SHOULD**: expected unless a documented exception is approved.
- **MAY**: optional and permitted.

When examples conflict with a normative rule, the normative rule controls.

---

## 3. Authority and order of precedence

When commercial sources disagree, they SHALL control in the following order:

1. an approved amendment to this Contract;
2. an approved tenant-specific commercial order, written exception, or manually granted commercial
   term that explicitly identifies the tenant, scope, effective dates, price/currency, and approving
   authority;
3. this Contract;
4. the canonical versioned commercial catalog and price-book configuration that implements this
   Contract;
5. commercial access/assignment records and immutable price snapshots produced under the applicable
   catalog version;
6. customer-facing pricing pages, dashboards, labels, and marketing copy;
7. legacy fields such as historical `plan`, `subscription_type`, or `payment_status` display values.

UI text, legacy fields, or stale cached data MUST NOT override the canonical commercial authority.

Historical payment/access records remain evidence of what occurred and MUST NOT be rewritten merely
because a later catalog version changes.

---

## 4. Definitions

### 4.1 Tenant
A Madar customer workspace or organization that owns tenant-scoped data and commercial state.

### 4.2 Core Module
One of the three independently saleable Madar products defined by this Contract:

- `forms`
- `website`
- `ecommerce`

### 4.3 Module Set
The non-empty set of Core Modules commercially assigned to a tenant for a given effective period.

Examples:

- `{forms}`
- `{website}`
- `{ecommerce}`
- `{forms, website}`
- `{forms, ecommerce}`
- `{website, ecommerce}`
- `{forms, website, ecommerce}`

### 4.4 Price Book
A versioned and effective-dated collection of commercial pricing rules.

The initial price book defined by this Contract is:

`launch_2026`

### 4.5 Launch Customer / Founding Customer
A tenant that enters a paid commercial relationship under `launch_2026` while that price book is
available for new sales.

A trial alone does not create founding-customer pricing rights unless the tenant converts to a paid
commercial assignment while `launch_2026` remains available for new sales.

### 4.6 Grandfathered Module
A Core Module acquired under `launch_2026` that has not subsequently been explicitly cancelled or
removed from the tenant's commercial assignment.

### 4.7 Grandfathered Module Set
The set of currently assigned Core Modules that individually remain grandfathered under
`launch_2026`.

### 4.8 Price Lock
The rule that a Grandfathered Module or Grandfathered Module Set continues to use the applicable
`launch_2026` pricing rules after `launch_2026` is closed to new sales.

### 4.9 Add-on
A separately priced capability, allowance, integration, usage pack, or service that is not one of the
three Core Modules.

### 4.10 Product Assignment
The canonical statement of **what** Core Modules and add-ons a tenant is assigned.

### 4.11 Commercial Access
The canonical statement of **whether** an assigned product is currently usable, based on commercial
access periods, review state, administrative hold, expiry, revocation, and other canonical ledger
state.

### 4.12 Commercial Hold
A reversible administrative suspension of commercial use. A Commercial Hold is not a payment,
cancellation, product removal, identity suspension, or deletion of customer data.

### 4.13 Cancellation
An explicit commercial action that removes a Core Module from the tenant's assignment effective on
a defined date. Cancellation may end grandfathering for that removed module as defined in this
Contract.

### 4.14 Reactivation
Removal of a Commercial Hold. Reactivation does not manufacture payment, extend expired access,
restore a cancelled module, or recreate a forfeited price lock.

### 4.15 Current Price Book
The price book available for new sales at the time a new non-grandfathered module is purchased.

### 4.16 Price Snapshot
An immutable commercial record containing at minimum the price book, catalog version, Module Set,
resolved recurring amount, currency, billing interval, effective dates, and the event/payment
reference that established that charge.

---

## 5. Core product model

Madar SHALL be sold as a modular platform.

The commercial model SHALL NOT require customers to understand internal capability names, database
tables, legacy "Business" tiers, or authorization architecture.

The three Core Modules are:

1. **Madar Forms**
2. **Madar Website**
3. **Madar Commerce**

Bundle pricing is a pricing rule over a Module Set. A bundle is not a separate authorization model.

The effective tenant capabilities are the union of the capabilities belonging to the tenant's
assigned Core Modules and separately purchased add-ons, subject to canonical commercial access,
security, tenant permissions, operational availability, and any narrower capability-specific rules.

---

## 6. Madar Forms module

**Canonical module ID:** `forms`
**Launch standalone price:** **USD 15/month**

Madar Forms includes the platform's form/data-collection product, including at minimum where those
features exist in the current product:

- form creation and editing;
- public form publication and public form links;
- multi-page forms;
- supported form field types;
- response/submission collection;
- response management;
- drafts and resume flows;
- conditional logic;
- localization features;
- quiz/scoring features where enabled;
- server-side validation and submission integrity controls;
- standard form-related data import/analysis that is part of the base Forms product;
- standard form exports where implemented.

Forms does not, by itself, grant the general-purpose Website module or the Commerce module.

Forms does not automatically include variable-cost AI inference. AI remains a separate add-on or
usage product.

---

## 7. Madar Website module

**Canonical module ID:** `website`
**Launch standalone price:** **USD 20/month**

Madar Website includes the general-purpose website/page-builder and reservation stack, including at
minimum where those features exist in the current product:

- page/site builder;
- pages and reusable site content;
- website publication;
- Madar-hosted site address/subdomain;
- website settings, themes, media, and supported branding;
- website/public runtime;
- website forms/components that are technically necessary for the builder itself, but not the full
  standalone Madar Forms product unless `forms` is assigned;
- reservations;
- reservation management;
- internal calendar functionality used by the reservation product;
- scheduling/availability functionality;
- supported calendar synchronization/integration behavior;
- website/reservation analytics that are native to the Website product.

The Website module SHALL NOT grant Commerce merely because Commerce reuses website/public-runtime
infrastructure.

A general-purpose Website entitlement and an E-commerce entitlement MUST remain commercially
distinct.

---

## 8. Madar Commerce module

**Canonical module ID:** `ecommerce`
**Customer-facing name:** **Madar Commerce**
**Launch standalone price:** **USD 20/month**

Madar Commerce includes the commerce/storefront product, including at minimum where those features
exist in the current product:

- public storefront;
- product catalog;
- products;
- categories, tags, and brands;
- product options and variants;
- SKU/barcode support where implemented;
- inventory and stock management;
- low-stock/backorder behavior where implemented;
- cart functionality;
- checkout/order creation;
- order management;
- delivery areas and delivery pricing/configuration;
- storefront theme/landing configuration;
- customer loyalty capabilities that are part of the Commerce product;
- commerce-specific analytics and merchant operations where implemented;
- payment-provider integration when separately activated and production-approved.

Commerce includes the storefront/public pages technically required to operate a store.

Commerce does **not** automatically grant the general-purpose Website builder. A Commerce-only tenant
may operate its Commerce storefront without receiving the full `website` module.

Payment processor/acquirer charges and other third-party transaction costs are not included in the
USD 20 subscription unless an approved commercial document explicitly states otherwise.

This Contract defines no Madar platform transaction percentage fee. Any future platform transaction
fee requires an explicit contract amendment or new price-book term before activation.

---

## 9. Shared platform capabilities

The following classes of functionality are platform foundations rather than separately saleable Core
Modules unless a future contract explicitly changes them:

- authentication;
- account security and MFA;
- tenant membership and basic tenant administration;
- logout/session/security flows;
- core audit/security infrastructure;
- baseline in-app notification infrastructure;
- platform-admin tooling;
- required operational/health infrastructure.

A tenant MUST NOT lose authentication merely because commercial access is suspended or expired.

---

## 10. Launch price book

### 10.1 Price-book identifier

`launch_2026`

### 10.2 New-sales availability

`launch_2026` becomes available for new paid sales only when the corresponding implementation is
deployed and the commercial launch is explicitly activated.

Its new-sales closing date is intentionally **not hard-coded by this Contract**.

Instead:

- `sales_start_at` MUST be recorded when the launch price book is activated.
- `sales_end_at` SHALL remain null until the founders/commercial authority explicitly close the launch
  offer.
- Closing `launch_2026` to new sales MUST NOT remove it from renewals/grandfathered tenants.

### 10.3 Currency and interval

All prices in this section are:

- currency: `USD`;
- interval: monthly;
- exclusive of separately applicable taxes, third-party fees, usage-based add-ons, and custom
  services unless expressly stated otherwise.

### 10.4 Price table

| Active Core Module Set | Monthly launch price |
|---|---:|
| Forms only | **$15** |
| Website only | **$20** |
| Commerce only | **$20** |
| Forms + Website | **$30** |
| Forms + Commerce | **$30** |
| Website + Commerce | **$30** |
| Forms + Website + Commerce | **$40** |

### 10.5 Bundle rule

For `launch_2026`:

- one module uses its standalone module price;
- any two Core Modules cost USD 30/month;
- all three Core Modules cost USD 40/month.

The commercial system SHOULD derive the price from the Module Set rather than encode seven unrelated
customer-facing plans.

The resolved Module Set and amount MUST be snapshotted in commercial history.

---

## 11. Founding-customer / grandfathering policy

### 11.1 General rule

A tenant that purchases a Core Module under `launch_2026` acquires the launch price for that module
while the module remains continuously assigned.

Launch pricing is a real commercial commitment, not a UI label.

Future price books MUST NOT silently reprice grandfathered modules.

### 11.2 Existing module price protection

After `launch_2026` closes to new sales:

- a continuously maintained Forms module remains eligible for `launch_2026`;
- a continuously maintained Website module remains eligible for `launch_2026`;
- a continuously maintained Commerce module remains eligible for `launch_2026`.

Where two or three currently assigned modules are all grandfathered, the `launch_2026` bundle rule
continues to apply to that grandfathered set.

Examples:

- founding Website customer remains Website at $20;
- founding Forms + Website customer remains at $30;
- founding all-three customer remains at $40;
- founding all-three customer who later removes Commerce retains Forms + Website at the launch
  two-module price of $30 because both remaining modules were continuously maintained.

### 11.3 Adding a module while launch pricing is open

If `launch_2026` is still available for new sales when a founding tenant adds another Core Module,
the new Module Set is priced under the launch bundle table.

Examples:

- Website $20 -> add Forms -> $30;
- Commerce $20 -> add Website -> $30;
- Forms + Website $30 -> add Commerce -> $40.

The new price and Module Set MUST be recorded as a new effective commercial price snapshot. Historical
snapshots MUST remain unchanged.

### 11.4 Adding a module after launch pricing closes

A Core Module that was not previously grandfathered and is added after `launch_2026` closes SHALL use
the then-current price book unless an explicit approved tenant-specific offer states otherwise.

A grandfathered tenant does not obtain a perpetual option to purchase future modules at launch
prices merely because the tenant originally joined during launch.

Cross-price-book discounts MUST NOT be inferred.

Default mixed-price-book treatment is:

1. preserve the valid price lock for the continuously maintained grandfathered module set;
2. price the newly added non-grandfathered module under the Current Price Book;
3. apply a cross-price-book bundle only when a later approved price book or tenant-specific offer
   explicitly defines one.

### 11.5 Removing a module

Removing a Core Module:

- ends access to that module on the effective cancellation date;
- ends that module's launch price lock;
- does not remove launch price protection from other continuously maintained grandfathered modules;
- does not delete historical data merely because commercial access ended.

### 11.6 Re-adding a removed module

If a previously removed/cancelled Core Module is re-added after `launch_2026` has closed:

- the module is priced under the Current Price Book;
- the prior launch price for that removed module is not automatically restored.

An authorized platform admin MAY restore a prior commercial term only through an explicit,
audited, reasoned tenant-specific commercial correction/grant.

### 11.7 Full cancellation

If all Core Modules are cancelled, the tenant no longer retains an automatic right to purchase
future service under `launch_2026`.

A later re-subscription uses the Current Price Book unless an explicit approved exception applies.

### 11.8 Nonpayment, expiration, and administrative hold

Past due, expired access, or a Commercial Hold MAY deny product use.

Those states MUST NOT, by themselves, silently destroy a grandfathered price lock.

Grandfathering ends through an explicit module cancellation/removal, full cancellation, an approved
commercial correction, or another expressly documented commercial event.

This prevents a temporary payment dispute, administrative review, or operational hold from
accidentally destroying a founding customer's commercial terms.

### 11.9 Tenant scope

Grandfathering belongs to the tenant/commercial subscription, not to:

- an individual user;
- an email address;
- a device;
- a different tenant created later.

Price locks are not automatically transferable between unrelated tenants.

---

## 12. Future price books

Madar SHALL support future pricing without rewriting historical catalog meaning.

Future pricing MUST use a new effective-dated price book or price-book version.

Examples may include:

- `standard_2027`;
- `standard_v2`;
- region-specific or channel-specific price books if later approved.

Core module identifiers SHOULD remain stable when the product meaning remains materially the same.

Madar SHOULD NOT clone module identities merely because list prices change.

A new price book MUST define:

- identifier/version;
- new-sales effective date/time;
- currency;
- billing interval;
- standalone prices;
- bundle rules;
- add-on interaction;
- eligibility;
- grandfathering/migration policy;
- customer communication requirements;
- implementation/migration plan.

A later price book MAY use a substantially different packaging model, but it MUST include an explicit
migration/compatibility policy for existing module assignments.

---

## 13. Add-ons and excluded services

Launch Core Module grandfathering does **not** automatically freeze prices for:

- AI usage or AI analytics;
- extra storage;
- additional workspace members/seats;
- hosted email/mailboxes;
- OCR;
- additional or premium domains;
- third-party provider services;
- SMS/WhatsApp or other paid communication providers;
- external database/ERP/customer-system integrations;
- custom development;
- premium support/SLA services;
- new Madar products created after this Contract;
- usage-based or metered services.

Each add-on MUST have its own canonical identifier, price/effective-date rule, allowance, and
historical record.

An add-on is grandfathered only if its own commercial terms expressly say so.

---

## 14. AI

AI MUST remain commercially separate from the three Core Modules unless a later price-book amendment
explicitly includes an AI allowance.

AI usage MUST be metered using the canonical AI accounting mechanism.

The commercial system MUST be able to distinguish:

- included allowance, if any;
- recurring AI add-on;
- one-time usage pack;
- actual usage;
- reserved usage;
- finalized usage.

Unlimited AI MUST NOT be inferred from Website, Forms, Commerce, or "all three" launch pricing.

---

## 15. Storage

### 15.1 Included launch storage

Until a later approved storage contract supersedes this section, the target included tenant storage
allowances are:

| Module set contains | Included tenant storage |
|---|---:|
| Forms only | **1 GiB** |
| Website (without Commerce) | **2 GiB** |
| Commerce | **5 GiB** |

For bundles, included storage is the **maximum** allowance among the active modules, not the sum.

Examples:

- Forms + Website -> 2 GiB;
- Forms + Commerce -> 5 GiB;
- Website + Commerce -> 5 GiB;
- all three -> 5 GiB.

Extra storage is a separate add-on and does not change module identity.

### 15.2 Safety ceilings

Any implementation-level per-user safety ceiling is an operational abuse/safety control, not a
customer-facing substitute for the tenant's commercial storage allowance.

The product MUST NOT advertise a tenant allowance that a normal authorized operator cannot
practically use because of an undocumented lower safety ceiling.

Before marketing higher storage allowances, engineering MUST reconcile any per-user ceiling with the
commercial tenant allowance.

---

## 16. Workspace operators and seats

The launch contract includes **one workspace operator/member seat** unless a separately approved
catalog entry states otherwise.

Additional member/seat products MUST NOT be sold as generally available until the corresponding
invitation/member-management workflow is production-ready.

Future seat pricing is an add-on and is not automatically covered by Core Module grandfathering.

---

## 17. Forms, submissions, and reservation volume

The launch price book SHALL NOT impose a normal customer-facing hard count on:

- number of forms;
- ordinary form submissions;
- ordinary reservation requests;

unless a future contract explicitly adds a metered limit.

Platform anti-abuse controls, rate limits, fair-use protections, security limits, and infrastructure
capacity controls MAY still apply.

"Unlimited" marketing language, if used, MUST be qualified by the actual fair-use/abuse policy and
MUST NOT override operational safety controls.

---

## 18. Custom domains

The Madar-hosted standard site/subdomain may be included with Website and Commerce where technically
supported.

A future custom-domain product MUST define:

- whether the first customer-owned custom domain is included;
- additional-domain pricing;
- certificate/TLS responsibility;
- domain-verification requirements;
- detach/reassignment behavior;
- effect of commercial suspension.

Custom-domain availability MUST NOT be inferred until the product is production-ready and the
commercial catalog explicitly enables it.

---

## 19. Commercial authority model

Madar SHALL preserve the architectural separation between product assignment and effective access.

### 19.1 Product assignment answers

> **What has this tenant purchased/been assigned?**

For this Contract, the assignment is principally the tenant's Core Module Set and add-ons.

### 19.2 Commercial access answers

> **Is the assigned product currently usable?**

Commercial access is determined by the canonical commercial ledger/state, including:

- current revision;
- review state;
- current access period;
- expiry;
- revocation;
- Commercial Hold;
- current dated add-ons;
- applicable commercial transition time.

### 19.3 Effective capability rule

Conceptually:

`effective capabilities = capabilities(module set + valid add-ons) ∩ effective commercial access ∩ tenant/user authorization`

Product assignment alone MUST NOT manufacture payment evidence or a valid access period.

Payment/access evidence alone MUST NOT grant a Core Module that is not assigned.

---

## 20. Review-required and legacy state

Unknown, malformed, ambiguous, or unreviewed legacy commercial state MUST NOT be guessed into a paid
assignment.

Legacy tenants without provable commercial assignment MUST remain `NEEDS_REVIEW` or the canonical
equivalent until deliberately resolved.

Legacy display fields MUST NOT grant capabilities.

---

## 21. Temporary commercial-enforcement compatibility mode

While the operator compatibility flag keeps ordinary commercial enforcement disabled:

1. the system MUST still resolve enough canonical state to detect an explicit Commercial Hold;
2. an explicit Commercial Hold MUST deny commercial capabilities;
3. an unheld verified tenant MAY retain the temporary compatibility behavior;
4. malformed/unverifiable commercial state MUST NOT be used to bypass a known hold;
5. enabling full commercial enforcement is a separate governed activation and MUST NOT occur merely
   because this Contract or its implementation is deployed.

The compatibility flag MUST NOT become a permanent substitute for reviewed tenant commercial state.

---

## 22. Commercial Hold

A Commercial Hold is an administrative restriction and SHALL be reversible.

A hold MUST:

- be tenant-scoped;
- record time;
- record actor;
- record reason;
- increment canonical commercial revision;
- append durable commercial/audit history;
- deny paid product use on the next relevant request;
- preserve authentication;
- preserve tenant membership;
- preserve historical commercial/payment records;
- preserve customer data;
- preserve the assigned Module Set;
- preserve grandfathered price rights unless an explicit cancellation/correction separately changes
  them.

A hold MUST NOT:

- delete data;
- disable `auth.users`;
- silently cancel modules;
- truncate a legitimate paid period merely to represent temporary suspension;
- manufacture or erase payment evidence.

---

## 23. Reactivation

Reactivation clears the current Commercial Hold.

Reactivation:

- MUST be authorized and audited;
- MUST increment canonical commercial revision;
- MUST preserve suspension history;
- MUST NOT extend an expired access period;
- MUST NOT recreate a cancelled module;
- MUST NOT restore a forfeited launch price lock unless an explicit approved commercial correction
  does so;
- MUST NOT imply payment was received.

If valid access remains, capabilities may resume immediately.

If access expired while the tenant was held, removing the hold does not make the expired period
valid.

---

## 24. Cancellation and data preservation

A commercial downgrade or cancellation MUST block new use of removed premium capabilities when
effective.

Cancellation MUST NOT automatically destroy historical business records required for legitimate
operations, audit, accounting, customer service, refund/COD/order handling, or data retention.

Historical forms, site content, reservations, orders, payment evidence, and audit records MUST be
retained or deleted according to the product's data lifecycle policy, not because a plan changed.

---

## 25. Legacy plan retirement and migration

The customer-facing legacy plan ladder:

- Forms
- Website
- Business
- Business Plus

is superseded for **new commercial sales** by the modular model in this Contract once the new price
book is activated.

Legacy product identifiers MUST NOT be destructively deleted from historical records.

### 25.1 No blind name-based migration

Existing tenants MUST NOT automatically receive a new Module Set solely from the text of a legacy
plan name when doing so could grant or remove material capabilities.

Each active legacy tenant SHALL be reviewed against:

- current purchased/assigned capabilities;
- current commercial records;
- paid-through/access evidence;
- any approved manual commercial terms;
- actual intended customer contract.

The review SHALL assign an explicit Core Module Set and price-book treatment.

### 25.2 Historical preservation

Historical legacy assignments remain auditable.

Migration MUST NOT rewrite historical payments as if the new module model existed at the time.

### 25.3 New sales

After modular launch activation, new tenants MUST NOT be sold `business` or `business_plus` as the
primary customer-facing pricing products.

---

## 26. Payment/access evidence

Manual payment, complimentary access, future automated provider settlement, and corrections MUST use
the same canonical commercial ledger.

Manual payment records MUST preserve:

- tenant;
- amount;
- currency;
- covered dates;
- payment method/category;
- reference/receipt where applicable;
- actor;
- timestamp;
- catalog/price-book context;
- resulting access period;
- correction linkage where applicable.

Complimentary access MUST NOT be recorded as fake payment.

Future CyberSource or another payment provider MUST append to the same canonical commercial model.
It MUST NOT create another paid/unpaid authority.

---

## 27. Price snapshots and historical truth

Every commercial event that creates or changes recurring module pricing MUST record enough immutable
context to reconstruct the charge later.

At minimum:

- tenant ID;
- Core Module Set;
- add-ons relevant to the charge;
- price-book ID;
- catalog version;
- currency;
- billing interval;
- resolved recurring amount;
- effective start;
- effective end, when known;
- event/payment reference;
- previous revision;
- resulting revision.

A future catalog release MUST NOT cause an old invoice/payment to be recalculated using new prices.

---

## 28. Idempotency and concurrency

Sensitive commercial mutations MUST be idempotent and revision-safe.

Commands MUST support durable idempotency keys.

Required behavior:

- same operation + same idempotency key + same request -> replay the original result;
- same key + materially different request -> conflict;
- stale expected commercial revision -> conflict and no partial mutation;
- successful mutation -> new canonical revision and durable audit/event history.

Silent last-write-wins behavior is prohibited for platform-admin commercial changes.

---

## 29. Administrative authorization

Human platform-admin commercial mutations MUST require:

- authenticated platform-admin identity;
- server-side authorization;
- AAL2 or the current canonical privileged assurance requirement;
- explicit reason where the operation changes access, price, grandfathering, cancellation, or
  suspension;
- request/correlation ID;
- idempotency key for state-changing commercial commands.

A browser-supplied role/AAL assertion MUST NOT be trusted as authoritative.

Future granular Billing Admin/Support Admin RBAC MAY replace broad platform-admin authorization, but
must retain server-side enforcement and appropriate step-up authentication.

Ordinary tenant admins MUST NOT be able to self-grant paid modules, alter price books, or restore
grandfathered terms.

---

## 30. Audit requirements

Commercial audit/event records MUST preserve, where applicable:

- actor;
- actor authority/role;
- tenant;
- action;
- AAL;
- request/correlation ID;
- idempotency key;
- previous revision;
- resulting revision;
- previous commercial state;
- resulting commercial state;
- Module Set before/after;
- price book before/after;
- recurring amount before/after;
- reason;
- safe reference;
- timestamp.

Secrets, tokens, raw payment credentials, and unnecessary personal data MUST NOT be logged.

Financial/commercial history SHALL use append/correction semantics instead of silent destructive
editing.

---

## 31. API error semantics

Authenticated commercial APIs SHALL use stable machine-readable error codes.

The expected HTTP classes are:

| Condition | HTTP status |
|---|---:|
| authentication required | 401 |
| unauthorized role / AAL2 required | 403 |
| explicit commercial suspension | 403 |
| commercial review required | 403 |
| payment/access grant required | 402 |
| dated commercial access expired | 402 |
| stale commercial revision | 409 |
| idempotency conflict | 409 |
| malformed/unverifiable commercial state | 503 |
| commercial dependency unavailable | 503 |

Public/anonymous surfaces MUST NOT expose internal tenant, price-book, payment, hold, reason, or
revision details.

Where a public paid feature is unavailable for commercial reasons, the public response SHALL use the
generic safe public error contract defined by the application.

---

## 32. Public-surface enforcement

Commercial checks for public product surfaces MUST use the same canonical authority as authenticated
product checks.

At minimum:

- Website/public runtime -> Website capability;
- public Forms -> Forms capability;
- reservations -> Website reservation capability;
- storefront/cart/checkout/order creation -> Commerce capability.

A Website tenant MUST NOT receive Commerce solely because Commerce reuses website infrastructure.

A Commerce tenant MUST NOT receive the full general Website builder solely because Commerce has a
storefront.

Explicit Commercial Hold MUST deny relevant paid public activity even while ordinary commercial
enforcement compatibility mode is enabled.

Historical privileged operations that must remain available for legitimate support/accounting MAY
use narrow explicit exemptions, but SHALL NOT create a general commercial bypass.

---

## 33. Caching and immediacy

Commercial state MUST be fresh enough that:

- suspension takes effect on the next relevant request;
- reactivation takes effect on the next relevant request;
- access expiry does not remain valid because of a stale arbitrary TTL;
- a tenant switch cannot reuse another tenant's entitlement state.

Any future commercial cache MUST be revision-aware and transition-time-aware.

Public runtime optimizations MUST preserve the canonical commercial snapshot without introducing a
second independent source of truth.

---

## 34. Customer-facing launch messaging

Customer-facing launch pricing SHOULD state the commitment clearly and narrowly.

Approved meaning:

> **Founding Customer Launch Pricing**
>
> Join Madar during the launch period and keep the launch price for the Madar core modules you
> continue to maintain. If you remove a module and later add it again after launch pricing has ended,
> the newly added module uses the then-current price. Future products, add-ons, usage-based services,
> third-party fees, and custom services are priced separately.

Marketing MUST NOT say:

- "everything Madar ever builds for $40 forever";
- "all future features included forever";
- "lifetime pricing" without the continuous-module and exclusion terms;
- "unlimited" where actual commercial or fair-use limits materially contradict that statement.

Any customer-facing promise that is more generous than this Contract MUST be approved and recorded as
a tenant-specific commercial term before it is relied upon operationally.

---

## 35. Customer legal documents

Before launch pricing is offered under a binding customer agreement, Madar SHOULD maintain separate
customer legal documents appropriate to its markets, typically including:

- Terms of Service or Master Services Agreement;
- Order Form/subscription confirmation containing the purchased modules and price;
- privacy notice;
- Data Processing Agreement where applicable;
- payment/renewal/cancellation disclosures required by applicable law;
- acceptable/fair-use policy where "unlimited" is marketed.

Tenant-specific pricing guarantees SHOULD appear in the applicable Order Form/subscription record and
must not depend solely on transient website copy.

Legal documents MUST be reviewed for applicable jurisdictions before they are treated as final legal
terms.

---

## 36. Change control

This Contract MUST be version controlled.

A material commercial change requires:

1. documented business approval;
2. new Contract version or approved amendment;
3. effective date;
4. catalog/price-book version;
5. explicit grandfathering/migration treatment;
6. database/application migration plan where required;
7. test updates;
8. customer communication plan where existing customers are affected;
9. immutable preservation of historical price/payment records;
10. governed production activation.

Changing a hard-coded number in application code without updating the canonical commercial contract
is non-conforming.

---

## 37. Implementation requirements

A conforming implementation SHALL provide one canonical path from commercial contract to runtime
authorization.

At minimum:

- stable Core Module IDs;
- versioned/effective-dated price books;
- explicit Module Set assignment;
- canonical capability mapping;
- canonical commercial access ledger;
- reviewed legacy migration;
- immutable price snapshots;
- durable idempotency;
- expected-revision conflict protection;
- AAL2-protected platform-admin mutations;
- audit history;
- separate add-on catalog;
- tenant-scoped grandfathering state or equivalent derivable history;
- public and authenticated capability enforcement;
- safe anonymous errors;
- no authorization dependence on legacy display fields.

Pricing SHOULD be data/configuration driven rather than duplicated across backend, frontend, SQL, and
marketing code.

---

## 38. Required conformance tests

Before production activation, automated tests SHALL prove at minimum:

### 38.1 Launch pricing

1. Forms only resolves to USD 15/month.
2. Website only resolves to USD 20/month.
3. Commerce only resolves to USD 20/month.
4. Every two-module combination resolves to USD 30/month.
5. All three modules resolve to USD 40/month.
6. Module order does not affect bundle price.
7. An empty set is not treated as a paid bundle.

### 38.2 Module boundaries

8. Forms-only cannot use general Website publishing.
9. Forms-only cannot use Commerce.
10. Website can publish a website.
11. Website can use reservations/calendar capabilities included by this Contract.
12. Website cannot use Commerce.
13. Commerce can operate its storefront/catalog/cart/order path.
14. Commerce-only does not obtain the full general Website builder.
15. Forms + Website gets both module capability sets.
16. Forms + Commerce gets both module capability sets.
17. Website + Commerce gets both module capability sets.
18. All three gets all three capability sets.

### 38.3 Grandfathering

19. Founding single-module tenant retains launch price after new-sales close.
20. Founding two-module tenant retains USD 30.
21. Founding all-three tenant retains USD 40.
22. All-three tenant removes Commerce -> remaining grandfathered Forms + Website resolves to USD 30.
23. Removed module loses its launch price lock.
24. Re-adding that module after launch closes uses Current Price Book.
25. Adding a module while launch remains open uses launch bundle pricing.
26. Full cancellation removes automatic right to future launch pricing.
27. Commercial Hold does not erase grandfathering.
28. Reactivation does not recreate a cancelled module.

### 38.4 Commercial authority

29. Assignment without valid access does not manufacture paid access when enforcement is enabled.
30. Valid access without assigned module does not grant that module.
31. Hold denies relevant commercial capability even during compatibility bypass.
32. Reactivation restores access only when valid access remains.
33. Expired access remains expired after hold removal.
34. Same user: suspended Tenant A and active Tenant B do not bleed commercial state.

### 38.5 History and security

35. Price-book/catalog changes do not rewrite old price snapshots.
36. Stale expected revision conflicts.
37. Idempotent retry replays original result.
38. Same idempotency key with changed payload conflicts.
39. Tenant admin cannot self-grant modules.
40. Platform admin AAL1 cannot execute sensitive commercial mutation.
41. Platform admin AAL2 can execute an authorized mutation.
42. Audit records preserve before/after module/price state.
43. Public denial does not expose commercial internals.

---

## 39. Legacy migration acceptance criteria

The modular price book SHALL NOT be activated for production new sales until:

- all active legacy tenants are inventoried;
- each tenant has an explicit reviewed Module Set or a documented approved exception;
- the target price-book/grandfathering treatment is recorded;
- no legacy plan-name field is relied upon as authorization truth;
- migration rehearsal passes against the current production-compatible schema;
- entitlement/capability tests pass;
- admin inspection/mutation is available and AAL2 protected;
- historical payment/access evidence remains intact;
- deployment/recovery plan is approved.

Global ordinary commercial enforcement remains a separate activation gate.

---

## 40. Non-goals

This Contract does not itself define:

- final tax treatment;
- jurisdiction-specific subscription law;
- refund law/policy;
- annual billing discounts;
- chargeback policy;
- SLA/uptime credits;
- a permanent free plan;
- a trial duration;
- final hosted-email pricing;
- final OCR pricing;
- final AI unit economics;
- final extra-seat pricing;
- final custom-domain pricing;
- payment processor fees;
- a future Enterprise plan;
- a future standard-price amount;
- customer-specific ERP/integration quotes.

Those items require separate approved terms before they become commercially enforceable.

---

## 41. Approved launch commercial decision summary

The approved launch model is:

| Offering | Launch monthly price |
|---|---:|
| Madar Forms | **$15** |
| Madar Website | **$20** |
| Madar Commerce | **$20** |
| Any two Core Modules | **$30** |
| All three Core Modules | **$40** |

Founding customers retain `launch_2026` pricing for Core Modules they continuously maintain.

Future products, add-ons, usage-based services, third-party costs, and custom services are excluded
unless their own terms explicitly provide a price lock.

The legacy customer-facing `Business` / `Business Plus` ladder is retired for new sales when this
price book is activated.

---

## 42. Commercial implementation invariant

No production code, migration, admin action, payment-provider callback, marketing page, or customer
dashboard may create a second interpretation of Madar's commercial state.

There SHALL be one chain of authority:

**Contract -> Versioned Catalog/Price Book -> Product Assignment -> Commercial Ledger -> Effective Capabilities -> Customer/Admin UI**

If any lower layer disagrees with a higher layer, the discrepancy is a defect to be corrected; it is
not a new commercial rule.

---

## Appendix A — Price-resolution examples

### A.1 Founding Forms customer

- purchased during launch;
- active modules: `{forms}`;
- monthly amount: `$15`;
- after launch closes: `$15` while Forms remains assigned.

### A.2 Founding Website + Forms customer

- active modules: `{website, forms}`;
- launch amount: `$30`;
- later standard prices change;
- customer retains `$30` while both modules remain grandfathered.

### A.3 Founding Complete customer

- active modules: `{forms, website, ecommerce}`;
- launch amount: `$40`;
- customer remains on `$40` while all three are continuously maintained.

### A.4 Founding Complete customer downgrades

Before:

`{forms, website, ecommerce}` -> `$40`

After Commerce cancellation:

`{forms, website}` -> `$30`

Forms and Website remain grandfathered. Commerce price lock ends.

### A.5 Re-add after launch

A founding Complete tenant cancels Commerce after launch closes.

Later the tenant adds Commerce again.

Result:

- grandfathered Forms + Website terms remain protected;
- Commerce is a new non-grandfathered purchase under the Current Price Book;
- old `$40 all-three` launch bundle is not automatically restored.

### A.6 Administrative hold

Tenant has `{forms, website, ecommerce}` at grandfathered `$40`.

Admin applies a commercial hold.

Result:

- product use is restricted;
- assignment remains;
- historical access/payment records remain;
- `$40` grandfathered term remains;
- removing the hold does not imply payment if the access period expired.

---

## Appendix B — Professional drafting principles used

This Contract intentionally follows these drafting principles:

- define recurring terms once and use them consistently;
- separate scope/product definition from compensation/pricing;
- state an order of precedence for conflicting documents;
- state amendment/change-control rules;
- describe obligations and outcomes precisely enough to test;
- use versioned/effective-dated commercial terms rather than silently rewriting history;
- separate master/internal rules from tenant-specific commercial exceptions;
- preserve immutable historical evidence;
- avoid relying on marketing copy or legacy display fields as authority.

---

## Appendix C — Implementation note for the current repository state

The current commercial-authority implementation work already established these foundation rules and
they remain part of this Contract:

- product assignment and commercial access are separate authorities;
- canonical ledger state controls effective commercial usability;
- an explicit commercial hold is reversible and precedes temporary enforcement bypass;
- commercial commands use revision/idempotency protection;
- platform-admin commercial mutations require server-side privileged authorization and AAL2;
- public commercial denials do not expose internal commercial details;
- E-commerce is a distinct capability and must not be inferred from Website publishing;
- Website includes the current reservation/calendar commercial capability set;
- commercial history and payment evidence are preserved rather than destructively rewritten.

The modular `launch_2026` price book defined by Version 2.0 supersedes the old customer-facing
Forms/Website/Business/Business Plus pricing ladder for new sales once activated.


## Appendix D — Current schema-115 engineering implementation

### Representation and authority

`tenant_subscriptions.module_basis` is a per-module object of `price_book_id`,
`acquired_at`, and `paid_since`. A null basis identifies an unresolved legacy
assignment. One current subscription container holds an arbitrary non-empty
module subset; it is not a mutually exclusive plan. Explicit module changes
cancel the current row and append its successor transactionally, copying the
basis only for continuously maintained modules. An empty module command means
full cancellation and appends an explicit zero-recurring-amount event; it is
never a paid bundle. Legacy rows and old financial records remain readable.

`commercial_price_books` holds immutable definitions, version/effective metadata,
USD/month, standalone and within-book bundle rules, and governed sales windows.
The launch book is prepared with null sales_start_at and no closing date. Reviewed
assignments and complimentary grants can be prepared before launch; they do not
establish founding rights. A first manual payment for an unprotected module
requires its price book to be open. `resolve_module_price` resolves each book's
subset independently and sums the approved group charges. It does not infer a
cross-book discount. Future price books require separately approved definitions;
no standard/future amount is seeded in production migrations.

Manual payment sets `paid_since` for currently assigned covered modules. An
unpaid trial or complimentary grant never sets it. Removing a module drops its
current basis; re-addition acquires a fresh basis under an available book. Past
due/expired access and admin holds do not change module bases. Full cancellation
leaves historical bases in canceled records but no current rights to reuse them.

The ledger access period records `module_ids` and immutable `price_snapshot`.
Effective capabilities are the union for the intersection of current assignments
and currently covered modules, plus dated valid add-ons. New module assignment
alone cannot extend old coverage. Removing a module denies it immediately while
leaving coverage evidence untouched. Historical single-plan periods cannot be
assumed to cover new modules; reviewed modular coverage must be explicitly
recorded. No production tenant is marked reviewed by this migration.

### Capability ownership

Forms: forms, public_form_links, response_management, response_overview,
data_import, standard_data_analysis, data_exports, expanded_data_analysis,
data_cleaning, charts. These existing Forms/data-workspace operations no longer
require a retired Business tier.

Website: page_builder, website_publish, image_uploads, standard_hosted_address,
reservations, reservation_management, internal_calendar, reservation_analytics.

Commerce: ecommerce, image_uploads, standard_hosted_address. Existing commerce
routes use ecommerce for catalog/products/variants/inventory/cart/checkout,
delivery, loyalty configuration and merchant writes. Shared image/address
capabilities do not confer the general Website builder. Standalone public Forms
requires Forms; full standalone form operations are not included in Website.
Website-native public form components are permitted only after the server proves
the requested form belongs to its currently bound published website snapshot,
with one commercial resolution; other standalone projects are denied.
Website-native rendering/media/reservation functionality remains in Website.

Neither core modules nor bundles automatically include AI, OCR, hosted email,
premium domains, extra storage/seats, priority support or future services. Existing
approved add-on catalog, token accounting and operational provider gates remain.
Legacy Business/Business Plus definitions are historical display data only.

### Commands, security, history and errors

The existing `apply_commercial_access_command` RPC remains the sole commercial
ledger mutation boundary. It now supports `assign_modules` alongside suspend,
reactivate, manual_payment, complimentary, correct_payment, revoke and
review_inactive. Human API mutations use the shared server-side platform-admin
AAL2 guard. Commands require tenant, actor, reason, request ID, durable key and
expected revision. Tenant/state locks serialize opposite changes; replay precedes
stale revision checking. Module order is normalized before fingerprinting.
A reused key with changed content conflicts. Successful mutation, revision,
commercial event and audit are transactional. The UI must use the same service.

Payment/event evidence cannot be updated/deleted. Period evidence cannot be
rewritten; only canonical revocation/supersession fields can change. New immutable
snapshots retain tenant, modules, book groups/version, catalog version, core
recurring amount, USD/month, dates, relevant add-ons, safe reference and before/
after revision. Add-on charges are separate from the core bundle and never
silently included in its price lock. Corrections preserve original pricing context.
No subscription field, user plan/payment display field or legacy webhook state
can independently grant paid capabilities.

HTTP: authentication 401; permission/AAL2, suspension and required review 403;
missing/expired paid access or legitimate entitlement purchase boundary 402;
stale revision/idempotency 409; invalid/unverifiable state/dependency 503.
Anonymous denials use generic 503 tenant_service_unavailable, no-store and no
commercial diagnostics. Auth/MFA/logout/membership and tenant switching have no
commercial identity suspension. Platform-admin inspection is separate from a
normal tenant workspace and no general admin bypass is added.

### Bypass, immediacy and public performance

A fresh canonical ledger snapshot is evaluated before the temporary operator
bypass. A hard hold denies capabilities even when
COMMERCIAL_ENTITLEMENTS_ENFORCED=false; verified unheld tenants retain existing
all-capabilities compatibility. This deployment does not activate global
commercial enforcement. Under normal enforcement, legacy/unreviewed assignments
fail closed until explicit module review. Public store payload caches are
reauthorized once per request and do not retain commercial snapshots.

Schema 115 `get_public_site_runtime_context` returns its internal ledger snapshot
in the same SQL statement as tenant/publication context. Anonymous hosted
/runtime performs ONE PostgREST RPC. The backend validates tenant, contract,
revision and required fields, consumes/removes the snapshot and never exposes it
in anonymous JSON. Holds/restoration become visible on the next request; expiry
uses statement time and never waits for a job or TTL. Schema 114's compatible
bridge retains two RPCs until upgrade. No new browser bootstrap or polling is added;
the deferred visits request, asset RPC, tenant entry split and public icon path
are unchanged.

### Storage and historical administration

Included storage is max(assigned AND covered module allowance): Forms 1 GiB,
Website 2 GiB, Commerce 5 GiB; current storage add-ons are then added. The
independent user safety row remains, with reservation ceiling
max(1 GiB, effective tenant quota), so a normal operator can consume the advertised
workspace allowance. SQL refreshes existing safety rows on reservation. Tenant
quota, disk floor, reservations and byte accounting remain enforced. Downgrade
or hold never deletes stored objects.

Read-only historical commerce inspection remains authorized by tenant membership.
Order status/COD collection/loyalty revocation retain narrow historical-operation
exemptions. Storage inspection reports zero effective quota for the precise
suspended/review commercial denials; malformed/dependency state still fails closed.
There is no new refund, notification or payment-provider project in this pass.

### API and deployment preparation

/admin/billing/tenants/{id}/modules GET exposes tenant, ledger, module basis,
pricing, effective capabilities and privileged hold reason. POST executes reviewed
module assignment/cancellation. /admin/billing/price-books exposes definition and
sales-window metadata. Existing commercial-state, access-history, suspend,
reactivate, manual-payment, complimentary, correction and revocation APIs remain;
new grants/payments accept module_ids. Billing entitlements/current-plan expose
module and pricing metadata. Legacy plan assignment/request endpoints return
modular_assignment_required. Customer-facing modular purchase selection and
commercial activation are separate next-phase work; no full admin UI is added.

Migration 115 is unpublished and paired byte-for-byte in both migration trees.
No applied migration through 114 changes. The manifest checksum and schema-114
bridge metadata must be validated after amendments. This remains a protected
release requiring the existing governed control-plane path after review, source
schema attestation, known-good bridge and verified backup. No production action
is performed. The prior schema-114 binary cannot enforce new holds/modules at
115: forward repair remains mandatory after advancement. Future Billing Admin
RBAC can replace the shared authorization seam. Future payment providers must
use the same ledger with their own trustworthy machine authority, never spoof
human AAL2 or create another paid state.
