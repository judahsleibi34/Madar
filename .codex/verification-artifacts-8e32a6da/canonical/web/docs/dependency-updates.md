# Dependency and build reproducibility

The frontend lockfile is authoritative and every build uses `npm ci`. The backend pins direct requirements and applies `backend/constraints.txt`, which captures the tested Linux/Python 3.12 container resolution. Base container images are digest-pinned. `scripts/check_dependency_locks.py` fails on unpinned Python requirements, mismatched constraints, Node lock drift, or Docker install-command drift.

## Approved update workflow

1. Work on a dedicated branch in an environment approved for package-index and vulnerability access.
2. Update only the intended direct dependencies. Use `npm install --package-lock-only <package>@<version>` for Node changes.
3. Build the backend without constraints in an isolated disposable environment only to resolve the proposed set, review `pip freeze`, then update `constraints.txt` deliberately. Check platform-specific packages (`numpy`, `scipy`, `pyarrow`, `psycopg-binary`, `pyroaring`, and `wasmtime`) on every supported container architecture; do not copy a developer workstation freeze blindly.
4. Run `python3 scripts/check_dependency_locks.py`, backend tests, `pip check`, frontend lint/tests/build, the runtime-only `npm audit --omit=dev --audit-level=high`, and an approved full development-dependency audit.
5. Rebuild all images with `--pull`, review base-image provenance, and update each tag/digest pair together.
6. Generate review artifacts with `scripts/generate_sbom.sh /absolute/private/output/directory`. The script uses the digest-pinned Node image and locked backend image, and the destination is created with owner-only permissions. Do not commit SBOMs that reveal private package names unless the repository policy explicitly allows it.

CI performs the runtime dependency audit because CI is the approved networked environment. This repository task did not run an online full CVE audit; the offline runtime audit reported zero shipped-package vulnerabilities, while the build tool reported development-only advisory debt that still requires the approved full audit and remediation review.
