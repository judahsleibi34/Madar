"""Native root-file/nonroot-reader component probe; never release authority.

Run only in a disposable network-none container with /run tmpfs and SETUID/GID.
Uses the actual backend loader and validator, no mocked ownership or imports.
This does not start an application, issue approval, or prove upgrade acceptance.
"""
from pathlib import Path
import json
import os
import subprocess
import sys
import tempfile


def main():
    if len(sys.argv) == 3 and sys.argv[1] == "--read":
        assert os.getuid() == 65534
        from services import business_write_authority, provider_recovery
        business_write_authority.AUTHORITY_PATH = Path(sys.argv[2])
        try:
            provider_recovery.validate_configuration()
            assert business_write_authority.restricted()
            assert not provider_recovery.worker_consumption_allowed()
        except (RuntimeError, ValueError, OSError):
            return 2
        return 0
    assert os.getuid() == 0 and Path('/.dockerenv').is_file()
    assert set(os.listdir('/sys/class/net')) == {'lo'}, 'isolated_network_required'
    with tempfile.TemporaryDirectory(prefix='madar-runtime-fixture-', dir='/run') as folder:
        root = Path(folder)
        root.chmod(0o755)
        path = root/'authority.json'
        grant = dict(version=3, schema=160, release_sha='b'*40,
            contract_digest='a'*64, mode='READ_ONLY', compatible_min=146,
            compatible_max=160, origin_schema=146, controller_sha='c'*40,
            operation='completed-normal-schema146-160-coordinated-release',
            migration_manifest_sha256='7633a15a9f531874409577fb9696e472631d3bbde63ae2603be0a4d23ef7c08f')
        url='http://madar-schema160-'+'a'*16+'-blue-provider-gateway:8000'
        env=dict(os.environ, MADAR_BUSINESS_WRITE_AUTHORITY=str(path),
            MADAR_BUSINESS_WRITE_CONTRACT=grant['contract_digest'],
            MADAR_RELEASE_SHA=grant['release_sha'], MADAR_RECOVERY_PROFILE='',
            MADAR_RELEASE_CONTROLLER_SHA=grant['controller_sha'],
            MADAR_RELEASE_MIGRATION_MANIFEST_SHA256=grant['migration_manifest_sha256'],
            SUPABASE_URL=url, MADAR_SUPABASE_CLIENT_NETWORK='madar-supabase-client',
            SCHEMA_COMPATIBLE_MIN='146', SCHEMA_COMPATIBLE_MAX='160', SCHEMA_EXCLUDED_VERSIONS='')
        cases=[('exact',{},None,0o644,0),
            ('wrong_context',{'SUPABASE_URL':url.replace('a'*16,'d'*16)},None,0o644,2),
            ('old_gateway',{'SUPABASE_URL':'http://madar-supabase:8000'},None,0o644,2),
            ('wrong_network',{'MADAR_SUPABASE_CLIENT_NETWORK':'foreign'},None,0o644,2),
            ('wrong_controller',{'MADAR_RELEASE_CONTROLLER_SHA':'d'*40},None,0o644,2),
            ('writable_grant',{},None,0o666,2),
            ('malformed',{},'{',0o644,2),
            ('missing',{},'',0o644,2)]
        for name, changes, raw, mode, expected in cases:
            path.write_text(json.dumps(grant) if raw is None else raw)
            path.chmod(mode)
            if name=='missing':path.unlink()
            result=subprocess.run([sys.executable,'-B',__file__,'--read',str(path)],
                env=dict(env,**changes),user=65534,group=65534,extra_groups=[],
                capture_output=True,timeout=20)
            assert result.returncode==expected, 'runtime_native_case_failed:'+name
        print(json.dumps({'status':'COMPONENT_PASS','cases':len(cases),
            'reader_uid':65534,'real_root_owned_files':True,'release_authority_issued':False}))
    return 0


if __name__=='__main__':
    raise SystemExit(main())
