# Provider ordering model — concrete adapter unfinished

New schema150_provider_lifecycle.py uses the existing root-private append-only
journal and nonblocking directory flock. It requires exact146→150 source/context/
controller/cluster/inventory bindings and fresh existing protected authority for
every boundary. Only fixed code-owned effects exist; no arbitrary SQL/shell input,
CLI,parallel issuer or privileged executor is introduced.149 bindings/history are
unchanged. Six fences cover boot,ingress,supervisors,objects,roles and sessions;
NOLOGIN alone is explicitly insufficient.

The newly explicit phases resolve the previous ordering cycle:

1. Positive identity/scope probes and durable original preimages before fencing.
2. Persistent fencing/drain and exact quiescence before every SQL boundary.
3. After150:restore ORIGINAL roles/start providers privately/run native probes,
   while ingress,workers and boot barriers remain fenced and target grant ABSENT.
4. Existing protected write handoff independently issues/establishes its fresh
   accepted150NORMAL authority;this module observes it and never issues it.
5. Resume accepted workers,restore ingress,clear boot fence,last.

Interrupted effects retain durable intent. Re-entry may reconcile one fixed
intent only after actual authorized observation;it never blindly repeats effects
or consumes old approval. Concurrent actors fail the directory lock. Missing
preimage,unknown writer/session,orphan processing step,prepared transaction,
changed protocol/source/authority or out-of-order activation rejects.

Sixteen new adversarial model tests and13retained149 lifecycle tests PASS.
Effects are injected test actors;this is NOT real provider/systemd/host reboot
acceptance or a completed concrete production adapter. Source registration and
NORMAL activation remain blocked. The installed production controller is unchanged.
