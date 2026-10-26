# Phase IX baseline — 2026-10-20

Parent draft PR217 is OPEN at `e5cbc740f437e24c4fde3bfcbd52933c03070d4c`.
Parent PR216 remains OPEN at `23254c786fdfa3731ff63cd004a4160b6d2f60fa`.
Main is `876b65e73ea8ceaf398145d8677019184798a95c`; protection=false,
rulesets empty. Corrected ancestry212→213→214→215→216→217 is retained;
212 already incorporates209–211. No merge, force push or branch removal occurred.

New dedicated worktree/branch:
`Madar-phase9-protected-release-execution-20261020` /
`codex/phase9-protected-release-execution-20261020`, based exactly on PR217.
All previous worktrees and evidence are preserved. Required local Git identity:
Saliba Rishmawi, `75858844+Saliba-codes@users.noreply.github.com`; published
GitHub author and committer mappings must be independently checked per commit.

Verified staging identity, passwordless sudo, four vCPUs,5,402MiB RAM and roughly
12GiB free disk. Retained provider stacks remain running; no unrelated service or
volume was removed. The retained privileged guest uses direct QEMU rather than
libvirt; `virsh` is absent. A new large full-provider stack was not launched before
resource and ownership inspection. Existing accepted runtime identities are
historical acceptance, not current PhaseIX source proof.

Bounded read-only production observation found schema146,a valid installed
controller source marker,and auto-deploy timer disabled/inactive. Private marker
and operational details stay outside Git. No customer rows, secrets or backups
were exported;no production database/service/controller/role/ingress mutation
occurred. Timer state alone is not exhaustive merge-hook safety evidence.

Schema150 remains an unregistered preparation profile. Complete protected
146→150 execution,private recovery/write handoff,boot/proxy recovery and automatic
full-provider staging were not established by PhaseVIII. This phase must retain
explicit refusals until actual combined engineering gates are satisfied.
