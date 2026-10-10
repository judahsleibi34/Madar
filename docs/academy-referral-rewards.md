# Academy referral rewards

Owners/admins configure E-Learning Settings → Referral rewards: enable the
program, enter a positive amount with at most two decimal places, and select
US dollar (USD), Israeli new shekel (ILS), or euro (EUR). Previously saved
currencies remain selectable. Default: disabled, 0.00 USD. The account
page displays a personal link, pending/earned/reversed referral history, and
separate balances for each currency. Lesson score remains separate from money.

A new Academy registration using `?ref=<opaque UUID>` records attribution.
Navigation within the Academy keeps the code in tenant-scoped session storage;
successful signup clears it. Existing users cannot claim a referral, users
cannot refer themselves, and codes from another tenant are rejected. Invalid
attribution fails within the existing signup compensation path. The verification
and membership requirements remain mandatory.

The amount/currency at signup are immutable terms for that referral. The first
successful paid learning checkout credits the sender within the existing
verified payment transaction. Duplicate/stale events, concurrent purchases,
renewals and later purchases cannot generate a second reward. Refund/reversal
of that checkout reverses the reward; a later purchase does not requalify the
learner. A disabled program stops new attributions and personal link issuance,
but existing referrals retain their promised terms. Local simulated checkout
rewards are labeled separately and never mixed with real balances. The API
exposes no referred learner names, email addresses or user IDs to the sender.

This is an earned-reward ledger. It does not transfer money, implement payouts
or make the reward balance spendable. Existing live-payment/provider guards
remain intact. Production needs an accepted schema136 bridge and approved
migration; the active schema115 release still selects no migrations. The
additional 136 candidate manifest and SQL are checksum pinned, mirrored and
retained without selecting them for production.

Run the isolated rehearsal using:

```bash
web/backend/madar_env/bin/python web/scripts/rehearse_migration_136.py
```

It replays the full migration history in a marked disposable loopback database,
checks migration rollback and tests first purchase, replay, concurrent purchase,
refund, fixed terms, tenant/account isolation and restricted SQL access. It does
not change the local application's records. The local development application
was upgraded separately after verifying its schema134 collision was an identical
out-of-order function from migration135, preserving the function and applying
the tracked 135/136 SQL transactionally. No production database was touched.

## Demo deployment status (2026-10-10)

The requested public demo domain is `madardemo.com`. Its DNS lookup did not
resolve during preparation, and no demo-server SSH configuration was available
in this workspace. Hosting and DNS access must be supplied before publication.

A read-only query confirmed the local application's core schema is 136 and
all three referral tables exist. The public `api.madarportal.com/health/version`
reported release `dd77c996e537a1d8ac8554d73796990c47b05525`, slot blue, with
compatibility bounds 115..115. That endpoint does not establish the public
database's actual schema; the authoritative database/release state still needs
inspection on its host. The committed active release remains non-migrating
schema115. Pushing these sources does not select the retained 136 bridge.

The new landing template is a development preview until published through the
normal Builder API. The earlier local publication was rejected for expired
commercial access. Demo publication requires a valid demo workspace entitlement;
the commercial check must remain enabled. Local seeded courses, enrollments and
settings are database records and are not included in a Git commit.

For a separate demo installation, inspect its existing data and schema, use an
isolated demo database and an explicitly accepted schema136 runtime, publish
the template through the Builder, then verify authentication, enrollment,
progress and referral behavior on the final domain. An existing production
database needs the reviewed bridge, verified backup and governed upgrade;
never apply SQL manually or change compatibility bounds to evade a gate.

The two new retained artifacts under `web/deployment/releases` are protected
paths. Ordinary production auto-deploy intentionally refuses such changes until
the exact-SHA control-plane upgrade has been approved and completed. No
production deployment, database migration or demo DNS change was performed
during this preparation.
