# Madar release-safety instructions

## Permanent development workspace

In environments where `/opt/madar-development/worktrees/architecture` exists,
reuse that canonical architecture worktree. In the owner development environment
where `/opt/madar-development` is unavailable, use the existing owner checkout at
`/home/judah/Madar Projects/Madar` on `Judah_branch`. Preserve all uncommitted and
untracked owner work there. Do not create Madar clones, branches or worktrees merely
for another phase, and do not create evidence or scratch directories under
`/home/madar`.

The existing `/opt/madar-development/repository` checkout, when present, is
separate and may contain uncommitted work and active runtime dependencies.
Preserve it. Do not create an isolated worktree unless the project owner gives
separate explicit authorization. Preserve published branches/history.

Keep current private evidence in `/opt/madar-development/evidence/integration`,
historical evidence in `evidence/historical`, checkpoints in
`archives/checkpoints`, historical worktrees in `archives/worktrees`, and
temporary development files in `scratch`, all relative to that development root.
Use restricted permissions for private evidence and keep it out of Git.
Record relocation and integrity manifests under the root's `inventory` directory.

Before moving or retiring anything, inspect Git state, ignored/untracked files,
active process/service/container references and resource ownership. Prefer
Git-aware relocation and reversible archival. Never discard dirty work, remove
unknown data, delete branches or use broad Git/Docker cleanup. Preserve production,
backup, recovery and unrelated-project paths and dependencies. Historical paths
in old reports describe their original test environments; consult the private
relocation manifests rather than rewriting historical evidence.

In the owner development environment, start subsequent sessions with:

```bash
cd "/home/judah/Madar Projects/Madar"
codex
```

Workspace consolidation and passing CI grant no production authority. Keep the
canonical architecture PR draft until independent review permits otherwise;
do not merge, enable auto-deploy or perform production mutations without separate
authorization. The protected schema-150 operation remains blocked/incomplete.

## Release constraints

Before preparing or merging any PR targeting `main`, read [`docs/MADAR_AUTO_DEPLOY_MERGE_CONTRACT.md`](docs/MADAR_AUTO_DEPLOY_MERGE_CONTRACT.md) and treat its auto-deploy, migration, protected-path, and production-mutation rules as mandatory release constraints.

Before changing deployment, migrations, schema compatibility, Docker/Compose,
production runtime code, release-sensitive backend/frontend code, or opening a
PR targeting `main`, read [`docs/production-release-policy.md`](docs/production-release-policy.md).
Before changing automatic migration orchestration, also read
[`docs/automated-database-migration-architecture.md`](docs/automated-database-migration-architecture.md).
Before changing privileged control-plane installation or upgrade orchestration,
also read
[`docs/control-plane-upgrade-architecture.md`](docs/control-plane-upgrade-architecture.md).

The current implementation is authoritative. If deployment-gating code,
automatic migration orchestration, or compatibility metadata changes, update
the applicable policy and architecture documents in the same change. Run every
applicable release-policy check before declaring work ready, and report gates
that cannot be tested locally.

Never bypass a failed release gate or directly modify production to compensate
for a source-code rejection.

## Frontend architecture authority

For changes to `web/frontend`, hosted tenant frontend delivery, or
frontend-facing FastAPI contracts, read and follow
`docs/architecture/MADAR_FRONTEND_ARCHITECTURE_CONSTITUTION.md`
once its repository adoption gates are satisfied.

The approved constitution governs business-domain ownership, shared contracts,
Page Builder reuse, module boundaries, frontend state and styling boundaries,
and architecture change control.

It adds to—and does not replace—the security, QA, CI, release, migration,
deployment, and production-authorization rules in this file and its referenced
policies.

Architecture reporting must be included in addition to the mandatory QA
completion report.

No ADR or architectural exception may weaken backend tenant authorization,
release protections, published-content compatibility, or mandatory QA.

If applicable instructions conflict, follow the constitution's precedence
policy and stop for an explicit decision when the conflict remains unresolved.

## Mandatory Madar Continuous QA Contract

These rules apply automatically to every Codex coding task
within Madar. QA is part of development, not an optional
step after development.

### 1. Mandatory development lifecycle

Every code-changing task must follow:

UNDERSTAND -> PLAN -> BUILD -> TEST -> VALIDATE
-> FIX -> RETEST -> REPORT

Implementation alone does not mean a feature is complete.

### 2. Before development

- Inspect relevant code, architecture and existing tests.
- Preserve uncommitted and untracked work.
- Define acceptance criteria and expected behavior.
- Identify affected modules, APIs and user workflows.
- Identify functional and non-functional risks.
- Determine the relevant testing scope.

### 3. During development

- Implement changes in small, testable increments.
- Add or update tests for changed behavior.
- Run relevant tests after implementation.
- Check edge cases and invalid inputs.
- Verify error handling, loading and empty states.
- Preserve existing behavior unless changes are intended.

### 4. Mandatory functional QA

Assess and test applicable areas:

- Business logic and feature correctness
- Input validation and boundary conditions
- Forms, navigation and user journeys
- API request and response behavior
- Database integrity and consistency
- Authentication and authorization
- Tenant isolation and permission boundaries
- Integration between affected components
- Existing feature regression

### 5. Mandatory non-functional QA

Assess and test applicable areas:

- API latency and performance
- Frontend loading and rendering performance
- UI/UX consistency
- Desktop, tablet and mobile responsiveness
- Arabic, English and RTL layout behavior
- Accessibility and keyboard navigation
- Browser compatibility
- Security and sensitive data exposure
- Reliability, concurrency and error recovery

Use measurable performance baselines and thresholds
where available. Never claim unmeasured performance
has passed.

### 6. Automatic failure repair loop

When an applicable test fails:

1. Record the failure and reproduction steps.
2. Analyze the root cause.
3. Fix the underlying problem.
4. Rerun the failed test.
5. Run affected regression tests.
6. Repeat until verified or blocked.

Do not bypass, delete or weaken meaningful tests
merely to obtain a passing result.

After three unsuccessful repair attempts on the same
issue, stop and report the blocker.

### 7. Quality gates

GATE A - FAST
Run relevant lint, syntax, type and unit checks.

GATE B - FEATURE
Run relevant integration, API, browser, UI/UX,
accessibility and workflow tests.

GATE C - RELEASE
Run applicable regression, security, performance
and release-policy checks.

Select checks based on the scope and risk of the change.
Do not run expensive full suites unnecessarily.

### 8. Existing Madar testing infrastructure

Prefer reusing existing testing tools and configurations,
including applicable components in:

- QA testing/
- web/frontend/
- web/backend/
- mobile/

Inspect actual test commands and dependencies before
executing them. Do not assume tests are configured.

### 9. Mandatory QA completion report

Every completed coding task must report:

QA STATUS: PASS / FAIL / BLOCKED / NOT RUN
CHANGED FILES:
ACCEPTANCE CRITERIA:
TEST COMMANDS EXECUTED:
FUNCTIONAL VALIDATION:
NON-FUNCTIONAL VALIDATION:
REGRESSION RESULTS:
UNRESOLVED ISSUES:
NEXT ACTION:

Never report a test as passed unless it actually ran.
If a required test cannot execute, report the limitation.

### 10. Safety and approval

- Preserve all existing owner work.
- Reuse existing QA infrastructure when possible.
- Never test destructively against production.
- Never expose credentials or sensitive test data.
- Do not bypass existing Madar release protections.
- Do not commit, push, merge or deploy without approval.
- Do not automatically start another feature.

Existing release-safety instructions remain mandatory
and take precedence over conflicting QA actions.

### 11. Read-only tasks

For analysis, explanations and documentation-only tasks,
avoid unnecessary test execution.

Still identify relevant QA risks when appropriate.

### Core development principle

No code-changing task is complete without
proportionate QA verification and an evidence-based
completion report.
