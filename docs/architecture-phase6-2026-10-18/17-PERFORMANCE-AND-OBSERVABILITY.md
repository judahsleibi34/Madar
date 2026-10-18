# Measured scope and operational signals

No general application performance improvement or production capacity is claimed.
Fresh a8fac208 full native acceptance took305.324s,end-to-end including artifact
import/restore/provider startup/probes/deletion. This is an execution duration,
not an API latency benchmark,RTO certificate or before/after comparison.
The staging VM has4vCPU,5402MiB RAM and HDD-backed storage; observed after acceptance
2616MiB memory available,1035MiB swap used and26GiB disk free. Containers/tests
retain explicit CPU/RAM/PID limits;heavy image/restore stages are sequential.
No staging quota was increased to manufacture a favorable measurement.

Deletion worker emits bounded ownership-loss,processed/failure counters and
consumption status. Healthy READ_ONLY standby is distinguished from actual
consumption;backend readiness requires positive consuming=true. Native worker
restart acceptance proves real processing recovery for that fixture. Unknown
external outcomes enter manual intervention rather than falsely incrementing
completion state. Model controller admission failures remain fail-closed.

A complete deletion-alert collection/evaluation/delivery/retry/dedup/recovery
pipeline has NOT been newly exercised in PhaseVI. Prior-phase isolated alert
proof is not relabeled current production alert deployment. Stuck requests,
manual intervention,oldest queue age,protocol mismatch and backup/WAL/restore
alerts remain prioritized work. Avoid tenant/user labels and credential output.
Representative API p50/p95/p99,business throughput and cross-process cache
consistency are NOT TESTED in this phase;prior mixed results remain unchanged.

The later actual150→independent150 full application restore took394.893s. It
includes private fencing/backup/configuration,image import,restoration,provider
startup and functional probes. The64.209s provider/database restart drill is a
separate maintenance observation. Neither duration certifies RTO/RPO or API SLOs.
