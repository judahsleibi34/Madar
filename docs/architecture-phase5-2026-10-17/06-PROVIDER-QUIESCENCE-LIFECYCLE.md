# Persistent provider lifecycle and native interruption evidence

The new ProviderMaintenance state machine binds operation/context/source/controller/
cluster/inventory. It captures positive identity/credential probes and private
preimages BEFORE ingress fencing, then journals/fsyncs intent before each of six
effects. Unknown/partial records and interrupted effects require fresh authorized
observation and reconciliation; they are never blindly replayed. Every activation
effect rechecks149/2/2 and the protected gates. Thirteen focused tests PASS.

An actual owned149 provider rehearsal also PASS: positive Auth/PostgREST/Storage
and denial probes; ingress closed; backend/notification/deletion supervisors and
Auth/Storage/PostgREST writers stopped; exact role NOLOGIN; known session drain;
all six short-lived effect children interrupted after intent; quiescence; native
PostgreSQL restart preserving the fence; unchanged database/object roots; exact
all-role preimages restored; native provider restart acceptance. The deletion
worker remains stopped. This target is separate from both retained148 stacks.

The first native preflight rejected before fencing because PostgreSQL inet text
includes a mask and did not equal measured container IPs. Using PostgreSQL
host(client_addr) fixes representation, without relaxing address/role identity.
The empty rejected journal and known empty probe table were explicitly reconciled;
no migration or fence had occurred. The successful second run is separate evidence.

The native adapter has no real protected controller grant, installed boot actor
or Node1 replica receipt. Its attempted protected activation correctly rejects.
An explicitly named staging-only recovery restores this one synthetic project's
original roles/services after149/2/2 and preservation checks. It does not fabricate
missing booleans, replay root authority or assert real reboot acceptance.

Remaining production integration: preserve ORIGINAL role preimages in independent
backups; replace live-provider positive probes with maintenance-specific current
observations after fencing; control actual ingress/systemd/boot/pools/object writers;
install only through the existing protected controller and fresh operation; validate
current-data/replica/restart acceptance. The production source adapter deliberately
rejects until those boundaries are implemented and independently reviewed.
