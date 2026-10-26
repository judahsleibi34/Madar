# Provider database binding: independent pure review

`test_schema150_provider_database_bindings.py` independently exercises
`require_provider_database_bindings` with synthetic Docker observations. No
daemon, SQL connection, provider request, privileged operation or production
credential is used. The fixture covers the actual three native role/URI contracts:
PostgREST/authenticator, GoTrue/supabase_auth_admin and Storage/supabase_storage_admin.

The review identified unsupported blank URI query overrides being discarded by
query parsing, and duplicate database aliases on the shared network. The parent
implemented fail-closed parsing and unique alias ownership before the first
test run; **no failing baseline execution is claimed for those two findings**.
Their unchanged required-rejection assertions now pass.

A subsequent fault fixture set `HostConfig.ExtraHosts=['db:172.25.0.99']` for
each provider. The function incorrectly accepted all three observations despite
the provider's explicit resolver override: **13 tests,3 failing subcases,0 errors**.
This demonstrates an admission false positive using synthetic configuration;
no actual connection to a foreign cluster was attempted. The parent then
rejected resolver overrides and resolution-file mounts. The same rejection
assertions now pass, with additional DNS/search/network-mode and mounted
`/etc`,hosts,resolv.conf,nsswitch.conf cases. Adapter source was edited only by
the parent; this review owns the independent tests and this note.

Final local execution:

```text
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover \
  -s web/backend/tests -p 'test_schema150_provider_database_bindings.py' -v
```

**15 PASS,0 failures,0 skips**. Coverage includes exact container identity,
same-schema foreign database rejection, required roles/password/database/port,
exact shared network IDs, ambiguous network/alias rejection, unsupported and
malformed URI/query/environment inputs, read-only observation behavior and
credential/endpoint redaction in exceptions.

A separate ordering test calls the actual `_database_identity` measurement with
an unexpected PostgreSQL system identifier at schema146 and synthetic successful
HTTP responses. It proves HTTP success cannot bypass cluster identity rejection:
the HTTP transport is never called. Authority issuance is isolated for that
component test; it does not certify root authorization, full coordinator wiring,
or effective native provider identity. The pure URI validator is complementary
to the controller's exact-container/image/system-identifier measurement, not a
substitute for it. Fresh privileged/native acceptance remains a separate gate.

A fresh independent review reproduced another false-positive using ambient
`PGHOSTADDR` while the URI still named the measured DB alias. A local libpq
parameter inspection (no connection) confirmed that this distinct parameter can
be supplied from the environment. The adapter now rejects ambient PG* connection
settings while retaining the reviewed PGRST_* namespace. The unchanged binding
assertions plus a new test cover ten override keys across all three providers.
This is helper/libpq-parameter evidence, not a native foreign-cluster connection.
