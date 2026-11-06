"""Native UID/file-ownership regression; no Docker, database or release authority.

Run as root with an unused directory under the operator's exact disposable run.
Every file is synthetic. The child uses the real constructor privilege drop and
real historical admission access check, without monkeypatching identity or I/O.
"""
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
    parser.add_argument('--workspace', type=Path, required=True)
    args = parser.parse_args()
    root = args.workspace.absolute()
    owner = pwd.getpwnam('madar')
    if (os.geteuid() != 0 or owner.pw_uid != 1000 or owner.pw_gid != 1000
            or root.parent.parent != Path('/opt/madar-development/scratch/codex-runs')
            or not root.parent.name.startswith('codex-') or root.exists()
            or root.is_symlink() or root.parent.stat().st_uid != owner.pw_uid):
        raise RuntimeError('native_operator_owned_unused_scope_required')
    if any(p.is_symlink() for p in root.parents):
        raise RuntimeError('native_operator_symlink_parent_refused')
    root.mkdir(mode=0o700)
    os.chown(root, owner.pw_uid, owner.pw_gid)
    web = Path(__file__).resolve().parents[2]
    env = dict(os.environ, PYTHONPATH=str(web)+':'+str(Path(__file__).parent),
               PYTHONDONTWRITEBYTECODE='1')
    results = []

    def run(code, path, expected=0):
        result = subprocess.run([sys.executable, '-B', '-c', code, str(path)],
                                env=env, capture_output=True, text=True, timeout=15)
        if result.returncode != expected:
            raise RuntimeError('native_operator_child_failed:' + str(result.returncode))
        return result.stdout.strip()

    def fresh(name):
        path = root / name
        path.mkdir(mode=0o700)
        os.chown(path, owner.pw_uid, owner.pw_gid)
        return path

    prefix = "from pathlib import Path; import os,sys; from running146_origin_lifecycle import enter_operator_lifecycle; p=Path(sys.argv[1]); "
    try:
        path = fresh('correct')
        run(prefix + "enter_operator_lifecycle(p); assert os.geteuid()==1000; "
            "[(p/n).write_text('{}\\n') for n in ('state.json','worker-ownership.json','deploy.lock')]; "
            "from deployment.lib.historical_origin import require_operator_state; require_operator_state(p)", path)
        assert all(p.stat().st_uid == 1000 and p.stat().st_mode & 0o777 == 0o600 for p in path.iterdir())
        results.append('actual_uid1000_private_state_creation_and_admission')
        # Root-owned legacy data is readable by root but must fail admission.
        os.chown(path/'state.json', 0, 0)
        run(prefix + "from deployment.lib.historical_origin import require_operator_state; "
            "\ntry: require_operator_state(p)\nexcept RuntimeError as e: assert str(e)=='historical_origin_operator_state_inaccessible'\nelse: raise AssertionError('foreign state accepted')", path)
        assert (path/'state.json').stat().st_uid == 0
        results.append('root_owned_state_refused_without_repair')
        # The real operator also cannot read the root-private fixture file.
        run(prefix + "os.setgroups([]); os.setgid(1000); os.setuid(1000); "
            "\ntry: (p/'state.json').read_bytes()\nexcept PermissionError: pass\nelse: raise AssertionError('root-private file readable')", path)
        results.append('actual_operator_root_private_read_denied')
        # Re-entry refuses already created state rather than reowning it.
        run(prefix + "\ntry: enter_operator_lifecycle(p)\nexcept RuntimeError as e: assert str(e)=='running146_existing_operator_state_refused'\nelse: raise AssertionError('reentry accepted')", path)
        results.append('existing_state_reentry_refused')
        wrong = fresh('wrong-owner'); os.chown(wrong, 0, 0)
        run(prefix + "\ntry: enter_operator_lifecycle(p)\nexcept RuntimeError as e: assert str(e)=='running146_initial_operator_directory_invalid'\nelse: raise AssertionError('root directory accepted')", wrong)
        results.append('incorrect_initial_owner_refused')
        interrupted = fresh('interrupted')
        run(prefix + "enter_operator_lifecycle(p); (p/'state.json').write_text('{}'); os._exit(23)", interrupted, 23)
        run(prefix + "\ntry: enter_operator_lifecycle(p)\nexcept RuntimeError as e: assert str(e)=='running146_existing_operator_state_refused'\nelse: raise AssertionError('partial construction overwritten')", interrupted)
        results.append('interrupted_partial_construction_refuses_reentry')
        # A new child process reobserves persistent access; this is not a VM reboot.
        good = fresh('restart')
        run(prefix + "enter_operator_lifecycle(p); [(p/n).write_text('{}') for n in ('state.json','worker-ownership.json','deploy.lock')]", good)
        run(prefix + "os.setgroups([]); os.setgid(1000); os.setuid(1000); from deployment.lib.historical_origin import require_operator_state; require_operator_state(p)", good)
        results.append('new_operator_process_reobserves_persistent_state')
    finally:
        for item in root.rglob('*'):
            if item.is_symlink() or item.stat().st_uid not in {0, 1000} or (item.is_file() and item.stat().st_nlink != 1):
                raise RuntimeError('native_operator_cleanup_ownership_changed')
        shutil.rmtree(root)
    print(json.dumps({'status':'COMPONENT_PASS','checks':results,'workspace_removed':not root.exists(),
                      'systemd_credentials_tested':False,'vm_reboot_tested':False,
                      'migration_or_deployment_authority_issued':False}))


if __name__ == '__main__':
    main()
