# Functionality and performance scope

The native150 rehearsal completed208test executions across its component
suites, including original147–149 assertions and the new setup-failure test.
These overlap by subject and are not208unique product scenarios.

Native business invariants passed. No current-source preserved running
application upgraded through the protected coordinator. Earlier fresh150
provider/browser results are historical evidence, not acceptance of this head.

Representative HTTP p50/p95/p99, throughput, error rate, queue latency and
baseline comparisons were not executed. The critical release path is blocked;
there is no completed release whose service interruption/recovery time can be
measured. Component restore time8.702seconds is a single synthetic observation,
not an application RTO or production-capacity claim.

Development-host tests used bounded disposable PostgreSQL17 containers. The
staging VM had approximately4.6GiB available RAM and9.6GiB free disk; its retained
stacks were stopped and left untouched. No competing full staging stack was
launched or unrelated workload interrupted.
