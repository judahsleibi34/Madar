# Actual native deletion acceptance

Exact source a8fac208586a331d79ce5d02cc5adf32410d57f3,fresh locked CI images,
new independently restored148origin upgraded through captured149/150. The11service
native stack includesPostgreSQL17,GoTrue,PostgREST,Storage,Redis,backend,freshfrontend,
gateway,notification and deletion workers. Bindings are loopback21080/21443/21081;
labels,marker,source images and runtime code hashes were checked before acceptance.

The service-role PostgREST request path created synthetic user and tenant deletion
requests with frozen identity/resources. The actual deletion container completed
all ten authoritative steps on first claim for each;each recorded two confirmed
effects. Independent GoTrue admin lookup and Storage read verified actual absence.
A foreign tenant,user and private object remained unchanged. Restarting only that
owned deletion container recovered consuming=true. These are runtime effects,not
mocked handler success,stopped-worker evidence or container health alone.

Original restored password/TOTP/private object survived;new Auth/login/MFA/AAL2,
CSRF,refresh rotation,invalidJWT/private Storage/notification replay/worker delivery
andfrontendproxy/readiness checks passed. Browser smoke passed nine auth/admin/
mobile groups with zero page errors/external requests. This is selected product
coverage,not complete forms/builder/commerce UI or production-route acceptance.

Native PostgreSQL37case suite additionally exercises full user/tenant graph with
simulated Auth boundaries,crash/reclaim/retry/manual states,foreign resource scope,
quota and grant enforcement. Real integration credential revocation,host filesystem
deletion and lost provider response were not exercised by the native happy-path
full stack;their unit/native synthetic tests and explicit limitations remain.
Later source changes require fresh exact images/acceptance and are not retroactively
covered by the a8fac208 receipt. Full restore150 rehearsal is a separate gate.

## Final fresh candidate acceptance

Exact36bb910fa028d380a0fb130bb8beeb1b0990bd2d fresh locked CI images passed
schema150_candidate_refresh.py REHEARSE on the already independently restored
owned150cluster in311.759s. Before activation,the SAME database system identity,
original roles/grants/rows/sequences/object bytes were preserved. No database
restore,migration or source overlay occurred during this refresh;the independent
full restoration at8e17remains distinct evidence. Auth/MFA/Storage/notification
acceptance and original identity/password/TOTP/private object preservation passed.

Actual live worker completed user and tenant deletion,all ten steps,first request
attempt,two confirmed effects each;both terminal states are
completed_with_retained_records. Actual Auth identities/Storage bytes were absent,
foreign tenant preserved,and worker restart consumption passed. Integration
revocation,host-file deletion and lost external response remain outside this
full-stack happy-path fixture. The private final schema150-candidate-refresh.json
binds source,run39128295629,images and runtime code hashes.

Browser exact36bb910f acceptance also PASS:Chromium151.0.7922.34,nine groups
(password→restrictedMFA,nativeTOTP,adminpage/API,Secure/HttpOnly/SameSitecookies,
pendingcookie removal,script cannot read accesscookie,authenticated refresh,
anonymous admin denied,mobile labels/keyboard/width),zero page errors and zero
external hosts. Temporary loopback SSH tunnel was closed after validation.
