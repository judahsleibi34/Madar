# Production baseline

Before remediation:

- Repository branch: `main`.
- HEAD: `0eaa9edd297d2fd6618d50ae5dfc4b08c94ba1df`.
- Backend readiness: all required legacy components healthy.
- Frontend: HTTP 200 on loopback port 3000.
- `madar-auto-deploy.timer`: inactive.
- `madar-auto-deploy.service`: failed after successful rollback.
- Database schema: 81.
- Environment file: owner `madar:madar`, mode `0600`.

The timer remained inactive throughout remediation. Production traffic was not changed until the controlled proxy cutover.
