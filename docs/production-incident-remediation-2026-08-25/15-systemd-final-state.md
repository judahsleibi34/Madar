# systemd final state

On 2026-08-26 the root-owned legacy auto-deploy control plane was replaced by
the reviewed immutable release controller. The effective timer is enabled and
active after a successful manual no-op and three successful timer-driven
no-ops.

Effective service contract:

- `ExecStart=/usr/local/sbin/madar-auto-deploy`;
- `User=madar`, `Group=madar`, `UMask=0077`;
- `WorkingDirectory=/home/madar/saas/Madar`;
- controller root `/usr/local/lib/madar/web/deployment` is root-owned and
  traversable by group `madar`;
- release state `/home/madar/.local/state/madar/releases`;
- traffic driver `docker-nginx`;
- active upstream file
  `/home/madar/.local/state/madar/proxy/active-upstreams.conf`;
- 45-minute oneshot timeout.

The timer uses `OnActiveSec=2min`, `OnUnitInactiveSec=2min`, a bounded random
delay, and `Persistent=true`. `OnActiveSec` was added after the first installed
timer correctly remained stopped but could not seed a mid-boot first firing
from `OnBootSec`.

The old privileged storage-preparation drop-in and `/home/madar/docker_auto.sh`
were removed from their live locations after protected backup. The installed
`/usr/local/sbin/madar-auto-deploy` delegates only to the immutable controller.
No Madar cron entry or second enabled auto-deploy unit was found.

The Docker proxy has `unless-stopped` restart policy. The deployment service
wants and starts `madar-release-proxy.service` after Docker, and all durable
release/proxy state is under `/home/madar/.local`. This is statically safe for
a future reboot. A controlled reboot drill remains recommended because the
shared production host was not rebooted during this change.

Protected root backups were created at:

- `/root/madar-systemd-backup-20260826T111200Z`;
- `/root/madar-systemd-backup-20260826T114500Z`;
- `/root/madar-systemd-backup-20260826T113000Z`.

The installer creates a restricted `SHA256SUMS` manifest. The operator's gated
command verified the first two manifests before the manual service invocation;
no secret material was copied into the reports.
