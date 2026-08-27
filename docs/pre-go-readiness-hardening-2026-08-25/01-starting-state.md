# Starting state

## Source

- Node: `madarserver` (Node 1 only)
- Development repository: `/home/madar/saas/Madar-dev`
- Starting development SHA: `7db2e83390045a155ed61d12803dfa0b1f557383`
- Development branch: `builder-backend`
- Production repository: `/home/madar/saas/Madar`
- Observed production SHA: `0eaa9edd297d2fd6618d50ae5dfc4b08c94ba1df`
- Production was inspected read-only and remained unmodified.

The prior baseline was NO-GO, 79/100, with G15, G16, and G18 blocked. Backend had 1,032 passing tests and frontend had 738 passing tests plus one intentional skip.

## Recovered work

The interrupted session had already produced local subsystem commits, staging state under `/tmp/madar-pre-go-stage`, disposable PostgreSQL data, immutable images, drill logs, backup evidence, and two initial report files. This work was inspected and continued; it was not reset or overwritten.

The final application code SHA for this campaign is `9a3c67e6058768b71100349b89379b2b6052915a`. Report-only commits follow it.

## Initial operational boundaries

All staging services use unique Compose projects, loopback ports, disposable database/storage, isolated Redis, and synthetic identifiers. Production database and Redis were not used by fault or load drills. The real Cloudflare route was never changed.
