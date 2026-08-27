# Supply chain, provenance, and release gates

## Dependency audits

- Final backend image `pip-audit`: no known vulnerabilities found.
- Production frontend dependency audit (`npm audit --omit=dev`): zero findings across 34 production dependencies.
- Remediated backend packages include `aiohttp 3.14.3`, `cryptography 50`, `h2 4.4.1`, `hpack 4.2`, `starlette 1.3.1`, and `pip 26.2.1`.

## Secret scan

Current tracked source scanning covered 1,348 files and found no credential signature. Reasonable history scanning reviewed approximately 6.15 million patch lines; matches were false positives in historical vendored cryptography test markers and SPDX/package metadata. No secret value is reproduced here.

## SBOM and provenance

- Backend pip-inspect SBOM: 144 packages; SHA-256 `46da6ffdbd2d6e9c15afede1e9056fef2b72bb2710dac20e0b53cdc667fe0b62`.
- Frontend CycloneDX SBOM: 29 components; SHA-256 `d69f0d222a21b96bb499e65f0e8c527feeca3212c3c79c28f0960e3639f3c04b`.
- Candidate images preserve Git SHA, immutable digest, dependency locks, build timestamp, schema range, and target schema.

## Mandatory release gates

Checked-in release tooling/documentation requires backend no-network suite, frontend tests/lint/build, migration parity, secret/dependency scans, Compose validation, immutable image build, SHA/version verification, schema compatibility, protected readiness, and targeted tenant/security tests before promotion. Production deployment remains a separately authorized operator action.
