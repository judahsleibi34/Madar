# systemd final state

`madar-auto-deploy.timer` is inactive and must remain so. It is still marked enabled, so a reboot can start the legacy timer. Root authentication is required to disable or replace it; avoid rebooting until the operator completes this step.

Root-owned installed files remain unchanged:

- `/etc/systemd/system/madar-auto-deploy.service`
- `/etc/systemd/system/madar-auto-deploy.service.d/storage-preparation.conf`
- `/etc/systemd/system/madar-auto-deploy.timer`
- `/usr/local/sbin/madar-auto-deploy`

The installed root service still includes the legacy privileged recursive storage-preparation drop-in, and the timer still uses `OnUnitActiveSec=2min`. Root installation was blocked because `sudo` requires interactive authentication.

The root wrapper resolves through the now-safe `/home/madar/docker_auto.sh` compatibility bridge, but this is not sufficient justification to enable the legacy unit.

Required operator command path: first prevent a legacy start on reboot, then run the tracked `web/deployment/bin/madar-install-control-plane --apply` with an explicit protected backup directory, inspect installed unit contents, daemon-reload, verify the proxy service/state directories, run a safe no-op, and only then enable/start the new timer. Do this only after rotating the exposed provider credential.
