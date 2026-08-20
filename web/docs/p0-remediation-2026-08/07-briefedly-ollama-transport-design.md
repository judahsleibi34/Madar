# Briefedly Ollama transport design

## Selected design

Use an authenticated HTTPS gateway in front of Ollama:

```text
Briefedly backend/worker
  -> HTTPS with normal certificate validation
    -> gateway requiring bearer application token
      -> loopback/internal Ollama API
```

This is the smallest design that preserves strict production validation and provides server identity plus application authentication. Tailscale may remain an additional network boundary, but is not treated as application authentication or sufficient server identity by itself.

## Development implementation

- Remote production Ollama endpoints must use HTTPS.
- Remote HTTPS requires a token of at least 32 characters, stored as `SecretStr`.
- Userinfo in the URL is rejected.
- Query strings and fragments are rejected.
- HTTP is permitted only for loopback/localhost or the explicit internal container hostname.
- Backend and worker use the same settings validation path.
- The report provider sends the token only in the `Authorization: Bearer` header.
- Tests verify rejection of insecure remote HTTP and transmission of the header.

## Gateway requirements

- certificate chains to a trust anchor available inside backend and worker images;
- gateway binds only to the constrained interface/tailnet path required;
- Ollama binds to loopback/internal interface and is not publicly exposed;
- constant-time token validation where gateway software supports it;
- token stored in protected backend/worker configuration only;
- timeouts shorter than job lease/retry bounds;
- no prompt, email body, token, or response logging at the proxy;
- health check distinguishes gateway reachability from model readiness;
- Tailscale ACL permits only the server-to-gateway flow;
- failure is closed and produces a controlled retry/error, never an insecure fallback.

## Why current production is rejected

The live URL is raw HTTP to a Tailscale address and has no application authentication. Current source correctly treats it as a remote HTTP endpoint and rejects startup in production. The validator was not weakened to trust RFC1918 or Tailscale address ranges.

## Preflight result

Backend and worker both started with a synthetic authenticated-HTTPS configuration, proving identical validation and configuration plumbing. Actual TLS handshake, certificate identity, token acceptance, and model request could not be tested because no final gateway/token was available.

BRF-DEP-001 remains partially fixed and blocks production reconciliation.
