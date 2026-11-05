"""Native root-parent/User=madar LoadCredential transport, no release authority.

Synthetic nonsecret lease metadata exercises the existing consumer with actual
PID/start/boot identity. No signing key, deployment token, database or VM exists.
This is a component test, never installed recovery acceptance.
"""
import argparse
import json
import os
from pathlib import Path
import pwd
import secrets
import subprocess
import sys
import time
import uuid


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--workspace',type=Path,required=True)
    root=parser.parse_args().workspace.absolute();owner=pwd.getpwnam('madar')
    if (os.geteuid()!=0 or owner.pw_uid!=1000 or root.exists() or root.is_symlink()
            or root.parent.parent!=Path('/opt/madar-development/scratch/codex-runs')
            or not root.parent.name.startswith('codex-') or root.parent.stat().st_uid!=owner.pw_uid
            or any(p.is_symlink() for p in root.parents)):
        raise RuntimeError('native_recovery_owned_unused_scope_required')
    root.mkdir(mode=0o700);web=Path(__file__).resolve().parents[2]
    sys.path.insert(0,str(web))
    from deployment.lib.completed_normal_admission import digest
    from deployment.lib.completed_normal_profile import RECONCILED
    lease={'version':1,'kind':'canonical-exceptional-operation-lease','request_id':str(uuid.uuid4()),
        'approval_sha256':'a'*64,'admission_sha256':'b'*64,'context_sha256':'c'*64,
        'operation_id':str(uuid.uuid4()),'attempt_id':str(uuid.uuid4()),
        'execution_expires_at':int(time.time())+120,'pid':os.getpid(),
        'process_start':Path('/proc/self/stat').read_text().rsplit(')',1)[1].split()[19],
        'boot_id':Path('/proc/sys/kernel/random/boot_id').read_text().strip()}
    source=root/'credential.json';unit='madar-test-codex-recovery-credential-'+secrets.token_hex(6)
    code="""import json,os,sys
from pathlib import Path
sys.path.insert(0,sys.argv[1])
from deployment.lib.control_plane_upgrade_authorization import require_canonical_operation_lease
assert os.geteuid()==1000
value=json.loads((Path(os.environ['CREDENTIALS_DIRECTORY'])/'native-metadata').read_bytes())
try:Path(sys.argv[2]).read_bytes()
except PermissionError:pass
else:raise RuntimeError('native_private_source_exposed')
try:require_canonical_operation_lease(value['state'],value['authorization'])
except RuntimeError:
 if value['accept']:raise
else:
 if not value['accept']:raise RuntimeError('native_invalid_lease_accepted')
print('native_case_pass')
"""
    results=[]
    try:
        for name,change,accept in [('current_parent',{},True),('expired',{'execution_expires_at':int(time.time())-1},False),
                ('wrong_boot',{'boot_id':str(uuid.uuid4())},False),('reused_pid',{'process_start':'0'},False)]:
            current=dict(lease,**change)
            packet={'accept':accept,'state':{'operation':RECONCILED.operation,'context_sha256':current['context_sha256'],
                'canonical_exceptional_approval_sha256':digest(current)},
                'authorization':{'operation':RECONCILED.operation,'context_sha256':current['context_sha256'],
                                 'canonical_exceptional_approval':current}}
            with source.open('w') as f:os.fchmod(f.fileno(),0o600);json.dump(packet,f)
            actual_unit=unit+'-'+name
            command=['systemd-run','--unit',actual_unit,'--wait','--collect','--pipe',
                '-p','User=madar','-p','RuntimeMaxSec=15','-p','TimeoutStartSec=15','-p','TimeoutStopSec=5',
                '-p','MemoryMax=256M','-p','CPUQuota=100%',
                '-p','LoadCredential=native-metadata:'+str(source),
                '/usr/bin/python3','-I','-B','-c',code,str(web),str(source)]
            try:
                result=subprocess.run(command,capture_output=True,text=True,timeout=25)
                if result.returncode or 'native_case_pass' not in result.stdout:
                    raise RuntimeError('native_recovery_credential_case_failed:'+name)
            finally:
                status=subprocess.run(['systemctl','is-active',actual_unit],capture_output=True,text=True,timeout=10)
                if status.stdout.strip() not in {'inactive','unknown'}:
                    subprocess.run(['systemctl','stop',actual_unit],check=True,capture_output=True,timeout=10)
                    raise RuntimeError('native_recovery_unit_not_retired')
            results.append(name)
    finally:
        if set(root.iterdir()) not in (set(),{source}):raise RuntimeError('native_recovery_unknown_owned_file')
        source.unlink(missing_ok=True);root.rmdir()
    print(json.dumps({'status':'COMPONENT_PASS','cases':results,'source_credentials_removed':True,
        'units_inactive':True,'release_authority_issued':False,'application_recovery_executed':False}))


if __name__=='__main__':main()
