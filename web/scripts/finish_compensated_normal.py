#!/usr/bin/env python3
"""Stdlib-first exact-hash gate: verified current recovery backup, then NORMAL.

Execute once only after operator approval of the exact source package and plan.
A stale-only preparation observation never permits routing, workers or writes.
The unchanged normal bootstrap must pass FULL readiness after verified freshness.
"""
import argparse,hashlib,json,os,pathlib,sys,traceback

def main():
    if os.geteuid()!=0 or not sys.flags.isolated or not sys.flags.dont_write_bytecode:
        raise RuntimeError('compensated_finish_isolated_root_required')
    parser=argparse.ArgumentParser();parser.add_argument('mode',choices=('verify','execute'))
    for name in ('source-package','approved-source','approved-plan'):parser.add_argument('--'+name,required=True)
    args=parser.parse_args();package=pathlib.Path(args.source_package)
    entry=package/'source/web/scripts/resume_active_recovery.py'
    for p in (entry,*entry.parents):
        st=p.lstat()
        if p.is_symlink() or st.st_uid!=0 or st.st_mode&0o022:raise RuntimeError('compensated_finish_source_untrusted')
    raw=entry.read_bytes()
    if hashlib.sha256(raw).hexdigest()!='87f923981c58df49aa9752c9248bec561359552fa564f434acdcf31a1803f373':
        raise RuntimeError('compensated_finish_bootstrap_changed')
    scope={'__name__':'measured_normal_bootstrap','__file__':str(entry)};exec(compile(raw,str(entry),'exec'),scope)
    saved,source=scope['measure'](package,args.approved_source,args.approved_plan)
    sys.path[:0]=[str(source/'web'),str(source/'web/scripts')]
    from deployment.lib.active_recovery_resumption import ResumptionPlan,ROOT
    from deployment.lib.active_recovery_operations import ProductionActiveRecoveryOperations
    from deployment.lib.active_recovery_backup_freshness import declaration,execute_recovery_backup,RecoveryBackupContext,BASE,MARKER,LATEST
    from deployment.lib.provider_recovery_runtime import readonly_configuration,file_digest
    plan=ResumptionPlan(**saved);plan.validate()
    if plan.digest!=args.approved_plan or not declaration(plan):raise RuntimeError('compensated_finish_plan_invalid')
    if (ROOT/plan.digest).exists() or (BASE/plan.digest).exists():raise RuntimeError('compensated_finish_attempt_already_used')
    expected=declaration(plan)
    if (file_digest(readonly_configuration(MARKER,private=False))!=expected['marker_sha256']
            or file_digest(readonly_configuration(LATEST,private=False))!=expected['latest_sha256']):
        raise RuntimeError('compensated_finish_backup_preimages_changed')
    ops=ProductionActiveRecoveryOperations(plan,package);ops.backup_preparation=True
    ops.verify_actual_execution_evidence(plan);ops.verify_active_rollback_inputs(plan)
    ops.verify_emergency_installation(plan);ops.verify_restricted_fallback(plan)
    ops.require_no_normal_write_authority();ops.require_all_consumers_stopped()
    RecoveryBackupContext(plan,BASE/plan.digest,package,ops).read_only_feasibility()
    if args.mode=='verify':
        print(json.dumps({'operation':'verify-backup-first-compensated-continuation','production_modified':False,
            'plan_sha256':plan.digest,'normal_activation_requires_new_verified_recovery_backup':True}));return
    # Lock and remeasure immediately before the first approved backup effect.
    with ops.upgrade_lock(),ops.deploy_lock():execute_recovery_backup(plan,package,ops)
    # No read-only preparation allowance carries into normal authorization.
    sys.argv=[str(entry),'execute','--source-package',str(package),'--approved-source',args.approved_source,'--approved-plan',args.approved_plan]
    scope['main']()

if __name__=='__main__':
    try:main()
    except Exception as error:
        frames=[{'file':pathlib.Path(f.filename).name,'function':f.name,'line':f.lineno} for f in traceback.extract_tb(error.__traceback__)[-16:]]
        print(json.dumps({'operation':'backup-first-compensated-continuation','status':'failed','exception_type':type(error).__name__,'traceback':frames,'messages_redacted':True}),flush=True)
        raise SystemExit(1)
