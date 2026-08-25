# Data ownership and disposition inventory

This is a technical lifecycle map, not legal advice. “Policy required” means Madar must obtain an explicit retention decision before changing the listed class.

| System / data class | User closure | Tenant closure | Mechanism / policy |
| --- | --- | --- | --- |
| `users`, account profile, pending onboarding | Delete platform row after manifests and external cleanup are captured | Delete all tenant platform rows | Saga; auth identity remains until late phase |
| `tenant_memberships`, invitations, roles | Membership cascades; shared tenant content remains tenant-owned | Delete/cascade with tenant | User closure is not tenant closure |
| `tenants`, hostname/settings/bindings | Retain tenant | Delete tenant; lifecycle gate and public resolver disable it first | No fallback hostname resolution |
| Builder projects, pages, publications, forms | Retain tenant-owned shared content; creator/uploader references follow schema semantics | Delete/cascade with tenant | Provider asset manifests are captured before DB removal |
| Form submissions and quiz attempts/results | Shared tenant records follow existing owner-reference semantics | Delete/cascade | Any alternative retention/anonymization requires policy approval |
| Reservations, calendars, tasks, sync jobs | User references follow schema; user connections are revoked | Stop jobs, revoke connections, delete/cascade | No new sync after freeze |
| Notification preferences/events/outbox/deliveries/push subscriptions | Stop user work and delete/cascade or null user references | Stop tenant work and delete/cascade | Retained delivery metadata requires policy review if independently preserved |
| Managed storage registry, avatars, builder assets | Delete user-owned objects | Delete all tenant objects | Manifested Supabase bucket and host-file steps; missing is idempotent success |
| Host datasets/generated artifacts | Delete user-owned paths | Delete all tenant paths | Registry-derived paths only; root containment and symlink refusal |
| Supabase Auth identity/MFA/provider sessions | Delete late, after app cleanup | Delete every captured tenant subject late | Local account freeze blocks application sessions immediately |
| Google calendar credentials/grant | Revoke provider grant, then clear encrypted local token | Same for all tenant connections | Provider failure retries; token values never logged |
| Microsoft calendar credentials/grant | Clear encrypted local material | Same | Provider-side revocation is not implemented; retained limitation is explicit |
| Other OAuth/provider credentials | None found beyond current calendar implementation | Same | New integrations must register a deletion adapter before launch |
| Analytics and usage aggregates | User-specific linkage follows existing schema; policy gap for visitor identifiers | Tenant rows cascade | Retention/anonymization policy for aggregate/visitor fields requires approval |
| Security/audit events | Retain security metadata; minimize/pseudonymize under approved policy | Same | Current workflow declares retained class; policy required before broader change |
| Subscription history and billing webhook replay records | Retain independently of user authorization state | Billing replay metadata may survive tenant FK deletion | Commercial/retention policy required; never used to grant capability after closure |
| Deletion request/step/subject/resource evidence | Retain redacted workflow evidence | Same | Needed to prove completion; duration and purge policy require approval |

No file path is derived from a request parameter. Resource manifests come from tenant/user-scoped database records captured in the same transaction that freezes the target.
