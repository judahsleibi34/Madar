"""Resource sampler for the explicitly disposable Phase 6 backend container."""
import json
import hashlib
import os
from pathlib import Path
import shutil
import sys
import time

import psutil


ROOT = Path('/tmp/madar-private-reports')


def scoped_action(payload, *, tenant_id, project_id):
    """Fault injection restricted to a resolved synthetic dataset/cache."""
    if os.getenv('APP_ENV') != 'test':
        raise RuntimeError('disposable test environment required')
    from data_analysis import services as data_services
    from services import project_dataset_service, parquet_cache_service
    persistent = project_dataset_service.resolve_project_dataset_version(
        tenant_id=tenant_id, project_id=project_id, user_id=tenant_id,
        dataset_id=payload['dataset_id'], version_id=payload['version_id'],
    )
    source = Path(data_services.authorize_dataset_input_path(
        persistent['storage_identifier'], tenant_id=str(tenant_id), user_id=str(tenant_id),
        require_small=False,
    ))
    directory = parquet_cache_service._identity_dir(
        tenant_id=tenant_id, user_id=tenant_id, project_id=project_id,
        dataset_id=payload['dataset_id'], version_id=payload['version_id'], create=False,
    )
    artifacts = list(directory.glob('*.parquet'))
    action = payload.get('action', 'evidence')
    if action == 'disk-refusal':
        import asyncio
        from unittest.mock import patch
        from services.request_body_limits import RequestBodyLimitMiddleware
        received = []
        sent = []

        async def app(*_args):
            raise RuntimeError('disk refusal must precede spooling')

        async def receive():
            received.append(True)
            return {'type': 'http.request', 'body': b'', 'more_body': False}

        async def send(message):
            sent.append(message)

        # Exercise real disk_usage with an intentionally unavailable operator
        # free-space budget. Never fill the host disk to inject this fault.
        with patch.dict(os.environ, {'STORAGE_DISK_FREE_FLOOR_BYTES': str(shutil.disk_usage('/tmp').free + 1)}):
            asyncio.run(RequestBodyLimitMiddleware(app)({
                'type': 'http', 'method': 'POST', 'path': '/users/7001/data/upload',
                'headers': [(b'content-type', b'multipart/form-data; boundary=x'),
                            (b'content-length', b'100')],
            }, receive, send))
        return {'status': sent[0]['status'], 'body_reads': len(received)}
    if action == 'corrupt':
        if len(artifacts) != 1 or artifacts[0].is_symlink():
            raise ValueError('expected one owned regular artifact')
        artifacts[0].write_bytes(b'controlled synthetic cache corruption')
    elif action == 'symlink':
        if len(artifacts) != 1 or artifacts[0].is_symlink():
            raise ValueError('expected one owned regular artifact')
        artifacts[0].unlink()
        artifacts[0].symlink_to(source)
    elif action != 'evidence':
        raise ValueError('unsupported scoped fault')
    digest = hashlib.sha256()
    with source.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return dict(source_bytes=source.stat().st_size, source_sha256=digest.hexdigest(),
                artifacts=len(artifacts), cache_bytes=sum(p.lstat().st_size for p in artifacts),
                partials=len(list(source.parent.glob('*.uploading'))),
                version_id=persistent['version']['id'])


def tree_bytes(root):
    size = 0
    for path in root.rglob('*'):
        try:
            if path.is_file() and not path.is_symlink():
                size += path.stat().st_size
        except OSError:
            pass
    return size


def main():
    if os.getenv('APP_ENV') != 'test':
        raise RuntimeError('disposable test environment required')
    if sys.argv[1] == 'finish':
        (ROOT / 'scalability-monitor.stop').touch()
        for _ in range(50):
            if (ROOT / 'scalability-metrics.json').is_file():
                return
            time.sleep(.1)
        raise RuntimeError('monitor completion missing')
    uploads = Path(os.environ['DATA_UPLOAD_DIR'])
    initial_free = shutil.disk_usage('/tmp').free
    stats = dict(peak_combined_rss_bytes=0, peak_upload_bytes=0, peak_cache_bytes=0,
                 peak_disk_free_reduction_bytes=0, max_backend_worker_count=0, samples=0,
                 peak_deleted_tmp_descriptors=0, final_deleted_tmp_descriptors=0)
    deadline = time.monotonic() + 15 * 60
    while time.monotonic() < deadline and not (ROOT / 'scalability-monitor.stop').exists():
        rss = workers = deleted_temporary = 0
        for process in psutil.process_iter(['pid', 'cmdline', 'memory_info']):
            try:
                args = ' '.join(process.info['cmdline'] or [])
                if process.pid == os.getpid() or 'scalability_checkpoint_fixture' in args:
                    continue
                if any(key in args for key in ('uvicorn', 'spawn_main', 'adaptive_analytics_worker',
                                                'parquet_conversion_worker')):
                    rss += process.info['memory_info'].rss
                    for descriptor in Path(f'/proc/{process.pid}/fd').glob('*'):
                        try:
                            target = os.readlink(descriptor)
                            if target.startswith('/tmp/') and target.endswith(' (deleted)'):
                                deleted_temporary += 1
                        except OSError:
                            pass
                    if 'spawn_main' in args:
                        workers += 1
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        stats['peak_combined_rss_bytes'] = max(stats['peak_combined_rss_bytes'], rss)
        stats['max_backend_worker_count'] = max(stats['max_backend_worker_count'], workers)
        stats['peak_upload_bytes'] = max(stats['peak_upload_bytes'], tree_bytes(uploads))
        stats['peak_cache_bytes'] = max(stats['peak_cache_bytes'], tree_bytes(uploads / '.parquet_cache'))
        stats['peak_disk_free_reduction_bytes'] = max(
            stats['peak_disk_free_reduction_bytes'], initial_free - shutil.disk_usage('/tmp').free)
        stats['samples'] += 1
        stats['peak_deleted_tmp_descriptors'] = max(stats['peak_deleted_tmp_descriptors'], deleted_temporary)
        stats['final_deleted_tmp_descriptors'] = deleted_temporary
        time.sleep(.1)
    (ROOT / 'scalability-metrics.json').write_text(json.dumps(stats, sort_keys=True))


if __name__ == '__main__':
    main()
