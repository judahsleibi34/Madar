"""Disposable historical146 construction through the existing release lifecycle.

No enrollment, completion or migration authority is produced by this fixture.
Root verifies the owned guest before reading private construction configuration;
the actual application lifecycle runs irreversibly as the madar operator.
"""
import os
from pathlib import Path


def enter_operator_lifecycle(state_root):
    import pwd, stat
    root = Path(state_root)
    if os.geteuid() != 0:
        raise RuntimeError('running146_root_constructor_required')
    operator = pwd.getpwnam('madar')
    if operator.pw_uid != 1000 or operator.pw_gid != 1000:
        raise RuntimeError('running146_operator_identity_invalid')
    metadata = root.lstat()
    if (not stat.S_ISDIR(metadata.st_mode) or metadata.st_uid != operator.pw_uid
            or metadata.st_mode & 0o777 != 0o700):
        raise RuntimeError('running146_initial_operator_directory_invalid')
    if any((root / name).exists() or (root / name).is_symlink()
           for name in ('state.json', 'worker-ownership.json', 'deploy.lock')):
        raise RuntimeError('running146_existing_operator_state_refused')
    os.initgroups(operator.pw_name, operator.pw_gid)
    os.setgid(operator.pw_gid)
    os.setuid(operator.pw_uid)
    os.umask(0o077)
    os.environ.update(HOME=operator.pw_dir, USER=operator.pw_name,
                      LOGNAME=operator.pw_name, PATH=os.defpath)
    if os.geteuid() != operator.pw_uid or os.getegid() != operator.pw_gid:
        raise RuntimeError('running146_operator_transition_failed')


def main():
    import os,json,sys,subprocess,importlib.machinery,importlib.util
    from pathlib import Path
    root=Path('/opt/madar-test/controller');sys.path.insert(0,str(root/'web'))
    from deployment.lib.environment_file import load_environment_file
    assert subprocess.check_output(['hostname']).strip()==b'madar-release-test' and subprocess.check_output(['systemd-detect-virt']).strip()==b'kvm'
    load_environment_file(Path('/etc/madar/production.env'))
    from deployment.lib.isolated_release_environment import observe_effect_fence
    observe_effect_fence()
    private=json.loads(Path('/opt/madar-test/origin146/private.json').read_bytes())
    assert Path('/sys/class/dmi/id/product_uuid').read_text().strip().lower()==private['guest_uuid']
    state_root=Path('/var/lib/madar/releases');assert not (state_root/'state.json').exists()
    sha='b0fdfe049510724c06a04706390cd174ea57a1d1';realm=json.loads(Path('/opt/madar-test/origin146/private.json').read_bytes())['realm_id'];prefix='madar'
    # Resolve private constructor inputs as root, then irrevocably run the real
    # release lifecycle under its intended operator. No already created/signed
    # release state is reowned or made readable as a compatibility workaround.
    enter_operator_lifecycle(state_root)
    loader=importlib.machinery.SourceFileLoader('origin_real_release',str(root/'web/deployment/bin/madar-release-deploy'));m=importlib.util.module_from_spec(importlib.util.spec_from_loader(loader.name,loader));loader.exec_module(m)
    compat=m.Compatibility.load(state_root/'releases'/sha/'web/deployment/releases/release.json')
    ops=m.DockerGitOperations(Path('/srv/madar/production'),state_root,Path('/etc/madar/production.env'),compat,compose_file=Path('/opt/madar-test/origin146/application.json'),container_prefix=prefix,project_prefix=prefix)
    ops.verify_source(sha);images=ops.build(sha,'blue');assert compat.accepts_schema(ops.schema_version())
    print('actual historical bootstrap kernel',flush=True)
    ops.preflight(sha,'blue',images,146)
    # Initial ephemeral kernel has no consuming workers or alleged completion.
    # This lets the genuine lifecycle observe its existing stable route while it
    # prepares the accepted green origin; the kernel is stopped after adoption.
    ops._compose(sha,'blue',images,'up','-d','--no-build','--wait','--wait-timeout','180','redis','parser-worker','remote-ingestion-worker','backend','frontend',workers_active=False)
    ops.validate_candidate_core(sha,'blue')
    print('actual prepare_release',flush=True)
    prepared=m.prepare_release(sha=sha,slot='green',state_root=state_root,compatibility=compat,operations=ops)
    (state_root/'origin-bootstrap-prepared.json').write_text(json.dumps(prepared,sort_keys=True,indent=2)+'\n')
    print('actual activate_prepared_release',flush=True)
    activated=m.activate_prepared_release(sha=sha,slot='green',state_root=state_root,operations=ops)
    (state_root/'origin-bootstrap-activated.json').write_text(json.dumps(activated,sort_keys=True,indent=2)+'\n')
    print('actual switch_traffic',flush=True);ops.switch_traffic('green')
    print('actual adopt_prepared_release',flush=True)
    adopted=m.adopt_prepared_release(sha=sha,slot='green',state_root=state_root,compatibility=compat,operations=ops)
    (state_root/'origin-bootstrap-adopted.json').write_text(json.dumps(adopted,sort_keys=True,indent=2)+'\n')
    ops=m.DockerGitOperations(Path('/srv/madar/production'),state_root,Path('/etc/madar/production.env'),compat,compose_file=Path('/opt/madar-test/origin146/application.json'),container_prefix=prefix,project_prefix=prefix)
    ops.release_root=state_root/'releases'/sha
    import time
    end=time.monotonic()+30
    while time.monotonic()<end:
     serving=ops.resolve_serving_slot({'blue':sha,'green':sha})
     if serving=='green':break
     if serving!='blue':raise RuntimeError('bootstrap_route_visibility_ambiguous')
     time.sleep(.25)
    else:raise RuntimeError('bootstrap_green_route_visibility_timeout')
    ops.stop_candidate('blue',expected_serving={'blue':sha,'green':sha})
    print(json.dumps({'status':'BOOTSTRAP_ADOPTED','source_sha':sha,'schema':ops.schema_version(),'slot':'green','lifecycle_receipt':adopted,'authority_claimed_from_historical_completion':False}),flush=True)


if __name__ == '__main__':
    main()
