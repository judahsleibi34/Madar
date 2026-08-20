# AI/Ollama security and capacity plan

## Invariant architecture

```text
Briefedly backend/worker
  -> HTTPS, normal certificate validation, bearer token
    -> constrained gateway on Node B
      -> loopback/internal Ollama
        -> pinned model on RTX 4060
```

Remote production HTTP remains rejected. No RFC1918/Tailscale bypass, query token, certificate skip, unauthenticated fallback, public 11434, or prompt/body logging is permitted.

## Identity and network controls

- Gateway certificate SAN matches configured hostname and chains to an image trust anchor. Test wrong CA, name, expiry, not-yet-valid, and rotation overlap.
- Gateway compares a >=32-character independent token using supported constant-time authentication; rejects missing/wrong/expired tokens without proxying.
- Token is present only in API/worker secret delivery, not frontend, URL, logs, process args, model service, or metrics.
- Tailscale grant allows only `tag:node-b-app` (or the final source identity) to the gateway port. Raw Ollama is loopback.
- Rotate gateway token with bounded dual-token overlap, then prove old token fails.

## Failure and abuse matrix

| Scenario | Expected behavior | Evidence |
|---|---|---|
| gateway/DNS/TLS down | job controlled retry/backoff then terminal status; API remains available | integration and live preflight |
| Ollama restart/model absent | model-readiness fails; no false healthy; queued jobs bounded | gateway/model health test |
| malformed/truncated/oversized JSON | schema reject, no report completion, bounded retries | existing plus fuzz tests |
| prompt/body/output too large | preflight token/byte cap; output cap; explicit truncation accounting | boundary tests |
| concurrent jobs | global + workspace semaphore; fair queue; lease renewed | Node B benchmark |
| VRAM/RAM/temperature limit | shed/reject AI before API/DB; alert; no CPU fallback surprise | GPU telemetry/load test |
| injected email instructions | treated as quoted evidence; no tool/network/secret access | adversarial corpus |
| fabricated evidence ID | output rejected or item marked unsupported | source-ID mapping tests |
| cross-workspace leakage | prompt built only from scoped rows; no shared prompt cache/state | isolation test |
| gateway logs | token/body/email/report absent; only bounded metadata/request ID | log inspection test |

## Node B benchmark suite

Do not execute before commissioning. Record exact model digest, quantization, context, driver, Ollama version, GPU VRAM, CPU/RAM, thermals, and power.

Run synthetic, non-customer corpora at small/median/max prompt sizes and 1/2/4 concurrent requests. Measure queue wait, time-to-first-token if available, completion latency, throughput, GPU/VRAM/RAM/CPU, errors, temperature/throttle, and API impact. Repeat model missing, gateway restart, Ollama restart, GPU reset, and full queue. Establish concurrency and timeout from evidence; do not infer capacity from RTX model name.

## Integrity and policy

- Report remains advisory, uncertainty-bearing, and source-linked; it cannot authorize, execute, send, delete, or change business state.
- Google Gmail data is inference-only for the visible user feature and must not train/improve a general model. Disable telemetry/content retention or document provider behavior.
- Model upgrades are change-controlled: license, checksum, adversarial regression, quality/evidence benchmark, capacity, rollback.
- Per-workspace/user usage and global capacity are metered atomically. Metrics avoid workspace names, email, prompts, and outputs.

Status: code transport policy is `IMPLEMENTED IN DEV`; real gateway, token rotation, Tailscale policy, GPU/capacity, and log proof are `BLOCKED BY HARDWARE`/`BLOCKED BY P0`.
