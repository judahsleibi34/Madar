# Staging validation

Passwordless explicit-config SSH/sudo, ownership markers, native providers and
resource capacity were verified. Retained original and independent recovered
stacks were preserved. Temporary tests use exact names/labels and disposable
marked PostgreSQL, bounded memory/CPU, no production endpoints and no real sends.

Executed:66 native148 cases;109 successor executions (87 distinct plus22 repeated
business cases); provider-role crash/drain/restart/recovery; native two-process
calendar permission proof;501-event180-read workload; isolated alert delivery;
complete network-disabled backend suites; frontend tests/lint/production build.

Calendar attempts retain diagnostic evidence: initial internal-network published
ports were unusable; test assertion used role instead of access_role; extracted
public source permissions blocked one API startup; that owned process was
interrupted to run finally cleanup. The harness now uses measured private
endpoints, bounds startup by wall time and rejects an exited container immediately.
No security or business assertion was weakened. Raw fixture logs/env remain private.

Frozen final-source CI images/runtime identity are independent of these source
overlay tests and are recorded in PR212 after documentation/source freeze. Do not
substitute old32c77afd or3ab2bd50 images for a newer source SHA.
