"""Governed stable-proxy publication before enabling Auth email callbacks.

An installed controller update does not replace a running single-file bind
mount. Validate the exact canonical config before the existing service recreates
the proxy. Upstreams, slots, provider state and worker ownership are untouched.
"""
import os
import re

from deployment.lib.provider_recovery_runtime import protected


def require_safe_proxy_source(config):
    formats = re.findall(r'log_format\s+[^;]+;', config, re.S)
    if (not formats or any(any(value in item for value in ('$request_uri', '$http_referer',
            '$http_cookie', '$http_authorization', '$args', '$query_string'))
            or re.search(r'\$request\b', item) for item in formats)
            or not re.search(r'access_log\s+/dev/stdout\s+madar_path_only;', config)):
        raise RuntimeError('local_auth_proxy_logging_unsafe')
    for path in ('/auth/v1/verify', '/api/auth/v1/verify'):
        block = re.search(r'location\s*=\s*' + re.escape(path) + r'\s*\{([^}]+)\}', config)
        if not block or not re.search(r'access_log\s+off;', block[1]) or not re.search(r'error_log\s+/dev/stderr\s+crit;', block[1]):
            raise RuntimeError('local_auth_proxy_callback_logging_unsafe')


def ensure_callback_safe_proxy(ops, contract):
    if os.geteuid() != 0:
        raise RuntimeError('local_auth_proxy_root_required')
    recovery = ops.recovery
    path = protected(recovery.paths.controller / 'proxy/nginx.conf')
    expected = path.read_text().strip()
    canonical = ops.command(['git', '-C', str(recovery.paths.repository), 'show',
                             contract.sha + ':web/deployment/proxy/nginx.conf']).strip()
    if expected != canonical:
        raise RuntimeError('local_auth_proxy_canonical_source_changed')
    require_safe_proxy_source(expected)
    active = ops.command(['docker', 'exec', recovery.paths.proxy, 'nginx', '-T'])
    if expected in active:
        return
    if recovery.paths.proxy != 'madar-release-proxy':
        raise RuntimeError('local_auth_proxy_production_scope_invalid')
    row = ops.inspect(recovery.paths.proxy)
    if (row['HostConfig'].get('NetworkMode') != 'host'
            or not any(m.get('Source') == str(path) and m.get('Destination') == '/etc/nginx/nginx.conf'
                       and m.get('RW') is False for m in row['Mounts'])):
        raise RuntimeError('local_auth_proxy_mount_provenance_invalid')
    # Preflight the exact canonical file in a disposable, networkless nginx
    # container before stopping anything. No active upstream/config file is
    # rewritten, and the currently mounted legacy inode remains untouched.
    compose = protected(recovery.paths.controller / 'proxy/docker-compose.yml').read_text()
    match = re.search(r'^\s*image:\s*(nginx:alpine@sha256:[0-9a-f]{64})\s*$', compose, re.M)
    if not match:
        raise RuntimeError('local_auth_proxy_pinned_image_missing')
    name = recovery.paths.prefix + '-proxy-preflight-' + os.urandom(8).hex()
    ops.command(['docker', 'run', '--rm', '--pull=never', '--name', name,
                 '--network', 'none', '--read-only', '--user', '101:101',
                 '--cap-drop=ALL', '--security-opt', 'no-new-privileges:true',
                 '--mount', 'type=bind,src=' + str(path) + ',dst=/etc/nginx/nginx.conf,readonly',
                 '--mount', 'type=bind,src=' + str(recovery.paths.upstream.parent) + ',dst=/etc/nginx/madar,readonly',
                 '--tmpfs', '/tmp:rw,noexec,nosuid,size=16m,uid=101,gid=101',
                 match[1], 'nginx', '-t'])
    # Use the installed, attested systemd/Compose service. Its pinned image,
    # loopback bindings and directory-mounted active upstream remain intact.
    ops.command(['systemctl', 'restart', 'madar-release-proxy.service'])
    active = ops.command(['docker', 'exec', recovery.paths.proxy, 'nginx', '-T'])
    if expected not in active:
        raise RuntimeError('local_auth_proxy_publication_failed')
    state = recovery.paths.state / 'provider-recovery.json'
    import json
    recovery.smoke_recovery(recovery.contract, json.loads(state.read_text())['slot'])
    ops.require_all_workers_off()
