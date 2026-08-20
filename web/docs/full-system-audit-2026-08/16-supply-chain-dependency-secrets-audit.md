# Supply chain, dependencies, and secrets audit

## Dependency controls

Madar Python has 76 exact pins and no Git dependencies. Briefedly runtime inputs and constraints are exact-pinned. Both frontends use lockfiles. Read-only `npm audit --omit=dev` on 2026-08-18 reported zero known production advisories for both projects. This is a point-in-time registry result, not proof of absence.

Most primary images are digest-pinned: Madar Python/Node/Nginx/Redis and Briefedly Python/Node/Nginx/Postgres. Exceptions include Sleibi's tag-only Nginx, Nginx Proxy Manager `latest`, shared PostgreSQL `17`, and dormant CV-reranker images. Build contexts have `.dockerignore`; no evidence showed `.env` or `.git` copied into primary runtime images.

No global vulnerability scanner was installed. Python advisory scanning and image SBOM/scanning were therefore not performed. Add CI-generated SBOMs, signed/attested immutable images, Dependabot/Renovate review, pip-audit/OSV, and container scanning off the production host.

## Secret locations and permissions

Primary production/development `.env` files are 600 and ignored/untracked. Cloudflare credential JSON is 400; account cert/current configs are 600. Mailcow current config/key is 600. Backups containing environment values are generally 600. Some old dumps and dev backups are 664 but protected by home-directory traversal; normalize nonetheless.

Secret scope is excessive:

- Madar backend receives Supabase service role plus direct PostgreSQL superuser URL.
- Briefedly DB container receives the entire backend env file, including application/encryption/Gmail/AI secrets it does not need.
- Briefedly app DB role is superuser.
- Shared database password is hardcoded in Compose.
- Environment files contain duplicated Google variable assignments (empty followed by populated), creating parser/order ambiguity.
- Some systemd/tunnel backup configs are more readable than current files.

## Git history

Briefedly commit `9e9b8076e9441fcc2c50a0bd66e191ddc80bbfbe` tracked a backend env file containing multiple live-secret classes (Meta, Gemini, DB, application, encryption, admin/job material). Fingerprint comparison indicates current values differ, suggesting rotation, but provider-side revocation cannot be proven from Git. Do not reproduce the values.

Madar history contains tracked frontend env files (apparently public client variables) and large historical virtualenv/browser/certificate artifacts. These inflate clone/supply-chain surface and may contain forgotten metadata. A coordinated history cleanup is optional only after all historical credentials are revoked; rewriting history is not itself credential rotation.

## Audit credential incident

During a read-only environment-key diagnostic, colon-delimited entries bypassed the intended redaction and several Madar Supabase credential values appeared in the controlled audit tool transcript. A later direct Compose read displayed the shared PostgreSQL password. No value is reproduced in these reports. Treat the transcript as a new exposure surface: restrict transcript access, preserve minimal incident evidence, rotate/revoke affected DB/service/anon/shared credentials, revoke sessions where appropriate, and review provider logs. This occurred without modifying production state.
