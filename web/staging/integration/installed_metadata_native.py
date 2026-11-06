"""Actual root installation / madar metadata consumption; no release authority."""
import argparse
import json
import os
from pathlib import Path
import pwd
import shutil
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--workspace', required=True, type=Path)
    root = parser.parse_args().workspace.absolute()
    owner = pwd.getpwnam('madar')
    if (os.geteuid() != 0 or (owner.pw_uid, owner.pw_gid) != (1000, 1000)
            or root.parent.parent != Path('/opt/madar-development/scratch/codex-runs')
            or not root.parent.name.startswith('codex-') or root.exists()
            or root.is_symlink() or root.parent.stat().st_uid != 1000
            or any(p.is_symlink() for p in root.parents)):
        raise RuntimeError('native_metadata_owned_unused_scope_required')
    root.mkdir(mode=0o750); os.chown(root, 0, 1000)
    web = Path(__file__).resolve().parents[2]
    name = 'schema-146-160-coordinated.json'
    source = web/'deployment/releases'/name
    target = root/name
    code = '''import os,sys
from pathlib import Path
sys.path.insert(0,sys.argv[1])
from deployment.lib.completed_normal_profile import verify_installed_metadata,RECONCILED
os.setgroups([]);os.setgid(1000);os.setuid(1000)
assert os.geteuid()==1000
try: verify_installed_metadata(RECONCILED,releases=Path(sys.argv[2]))
except RuntimeError as e:
 assert str(e)=='completed_upgrade_installed_metadata_invalid'
 sys.exit(42)
'''
    checks = []
    def observe(label, expected):
        result = subprocess.run([sys.executable, '-I', '-B', '-c', code, str(web), str(root)],
                                capture_output=True, timeout=15)
        if result.returncode != expected:
            raise RuntimeError('native_metadata_child_unexpected_result:'+label)
        checks.append(label)
    try:
        observe('missing_descriptor_refused_by_actual_madar', 42)
        subprocess.run(['install', '-o', 'root', '-g', 'root', '-m', '0644', str(source), str(target)], check=True)
        observe('root_installed0644_loaded_by_actual_madar', 0)
        observe('new_child_reobserves_persistent_metadata', 0)
        target.chmod(0o600); observe('root_private_descriptor_refused', 42)
        target.chmod(0o644); target.write_text('{}'); observe('partial_install_refused', 42)
        target.write_bytes(source.read_bytes()); os.chown(target, 1000, 1000)
        observe('operator_owned_descriptor_refused', 42)
        os.chown(target, 0, 0); target.unlink(); target.symlink_to(source)
        observe('linked_descriptor_refused', 42)
        target.unlink()
    finally:
        for item in root.iterdir():
            if item.is_symlink() or item.stat().st_uid not in {0, 1000} or item.stat().st_nlink != 1:
                raise RuntimeError('native_metadata_cleanup_identity_changed')
        shutil.rmtree(root)
    print(json.dumps({'status':'COMPONENT_PASS','checks':checks,'workspace_removed':not root.exists(),
                      'systemd_credentials_tested':False,'vm_reboot_tested':False,
                      'migration_or_deployment_authority_issued':False}))


if __name__ == '__main__': main()
