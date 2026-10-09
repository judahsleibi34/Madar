"""Controller resumption ordering with fake host operations only."""
import copy
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
WEB=Path(os.getenv('MADAR_TEST_REPOSITORY_ROOT') or Path(__file__).resolve().parents[2]);sys.path.insert(0,str(WEB))
from deployment.lib.active_recovery_controller import ActiveRecoveryControllerRepair,ActiveRecoveryBackupTimers
from deployment.lib.control_plane_upgrade import BACKUP_TIMERS

class Operations:
    def __init__(self,base):
        self.calls=[];self.states={name:{'enabled':'enabled','active':'active'} for name in BACKUP_TIMERS}
        self.states.update({name.replace('.timer','.service'):{'enabled':'static','active':'inactive'} for name in BACKUP_TIMERS})
        self.states.update({'madar-auto-deploy.timer':{'enabled':'disabled','active':'inactive'},'madar-auto-deploy.service':{'enabled':'static','active':'inactive'}})
        self.stage=base/'stage';self.stage.mkdir();p=self.stage/'web/deployment/proxy/nginx.conf';p.parent.mkdir(parents=True);p.write_bytes(b'fixture nginx')
    def systemctl_state(self,name):return dict(self.states[name])
    def command(self,label,args):
        self.calls.append(label)
        if args[1]=='stop':self.states[args[2]]['active']='inactive'
        if args[1]=='start':self.states[args[2]]['active']='active'
    def resolve_candidate(self,*args,**kwargs):self.calls.append('resolve')
    def stage_candidate(self,*args):self.calls.append('stage');return self.stage.parent,self.stage
    def static_preflight(self,*args):self.calls.append('preflight');return 'a'*64
    def protected_tree_digest(self,*args):return 'a'*64
    def installer_dry_run(self,*args):self.calls.append('installer_dry_run')
    def installer_apply(self,*args):self.calls.append('installer_apply')
    def advance_production_checkout(self,*args):self.calls.append('advance_checkout')
    def verify_install(self,*args):self.calls.append('verify_install')

class ControllerResumeTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);base=Path(self.tmp.name)
        self.plan=SimpleNamespace(digest='a'*64,source_sha='b'*40,source_bundle_sha256='c'*64,
            retained_inputs={'proxy_configuration':hashlib.sha256(b'fixture nginx').hexdigest()})
        self.root=base/self.plan.digest;self.root.mkdir()
        (self.root/'authorization.json').write_text(json.dumps({'operation':'active-local-rollback-resumption','plan_sha256':self.plan.digest,'source_bundle_sha256':self.plan.source_bundle_sha256}))
        self.phase='controller_resume_pending';self.write_phase()
        self.route=base/'route.conf';self.route.write_bytes(b'upstream madar_backend_active { server 127.0.0.1:8201; }\nupstream madar_frontend_active { server 127.0.0.1:3200; }\n')
        for name,value in [('ROOT',base),('UPSTREAM',self.route),('protected',lambda path,**kw:path)]:
            p=patch('deployment.lib.active_recovery_controller.'+name,value);p.start();self.addCleanup(p.stop)
        p=patch('deployment.lib.active_recovery_controller.os.geteuid',return_value=0);p.start();self.addCleanup(p.stop)
        self.c=SimpleNamespace(backend_port=8201,frontend_port=3200,slot='green',contract=object(),require_write_authority=lambda *args:None)
        self.runtime=SimpleNamespace(json_http=lambda url:{'release_sha':self.plan.source_sha,'release_slot':'green'},denied=lambda url:None)
        self.ops=Operations(base);self.repair=ActiveRecoveryControllerRepair(self.plan,self.c,self.root,lambda:{'source_sha':self.plan.source_sha,'files':{'web/deployment/proxy/nginx.conf':self.plan.retained_inputs['proxy_configuration']}},operations=self.ops,runtime=self.runtime)
    def write_phase(self):
        events=[{'phase':phase,'plan_sha256':self.plan.digest} for phase in ('read_only_serving',self.phase)]
        (self.root/'events.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in events))
    def test_stages_and_installs_only_after_timers_quiesce(self):
        self.repair.install()
        self.assertEqual(self.ops.calls[:4],['continuation_backup_timer_stop']*4)
        self.assertLess(self.ops.calls.index('installer_dry_run'),self.ops.calls.index('installer_apply'))
        self.assertLess(self.ops.calls.index('installer_apply'),self.ops.calls.index('advance_checkout'))
        record=json.loads((self.root/'installed-controller.json').read_text())
        self.assertFalse(record['volatile_credential_reconstructed']);self.assertFalse(record['historical_authorization_reused'])
    def test_wrong_phase_or_public_source_rejects_before_effect(self):
        self.phase='read_only_handoff_pending';self.write_phase()
        with self.assertRaisesRegex(RuntimeError,'handoff_required'):self.repair.install()
        self.assertEqual(self.ops.calls,[])
    def test_active_backup_rejects_before_stopping_timers(self):
        self.ops.states[BACKUP_TIMERS[0].replace('.timer','.service')]['active']='active'
        with self.assertRaisesRegex(RuntimeError,'backup_operation_busy'):self.repair.install()
        self.assertEqual(self.ops.calls,[])
    def test_changed_nginx_bytes_rejects_before_install(self):
        (self.ops.stage/'web/deployment/proxy/nginx.conf').write_bytes(b'changed')
        with self.assertRaisesRegex(RuntimeError,'staged_bundle_mismatch'):self.repair.install()
        self.assertNotIn('installer_apply',self.ops.calls)
    def test_existing_timer_preimage_is_not_overwritten(self):
        (self.root/'backup-timer-preimage.json').write_bytes(b'old evidence')
        with self.assertRaises(FileExistsError):self.repair.install()
        self.assertEqual((self.root/'backup-timer-preimage.json').read_bytes(),b'old evidence')
        self.assertEqual(self.ops.calls,[])
    def test_no_timer_resumption_before_normal(self):
        self.repair.quiesce_backup_timers()
        with self.assertRaisesRegex(RuntimeError,'before_normal'):self.repair.restore_configured_backup_timers()
        self.assertNotIn('continuation_backup_timer_restore',self.ops.calls)


    def test_early_quiescence_preserves_preimage_through_installation(self):
        self.phase='detached_candidate_pending';self.write_phase()
        early=ActiveRecoveryBackupTimers(self.plan,self.root,self.repair.source_guard,operations=self.ops)
        early.quiesce()
        original=(self.root/'backup-timer-preimage.json').read_bytes()
        self.phase='controller_resume_pending';self.write_phase();self.repair.install()
        self.assertEqual((self.root/'backup-timer-preimage.json').read_bytes(),original)
        self.assertEqual(self.ops.calls.count('continuation_backup_timer_stop'),4)

    def test_early_quiescence_requires_fresh_authorization_and_phase(self):
        early=ActiveRecoveryBackupTimers(self.plan,self.root,self.repair.source_guard,operations=self.ops)
        self.phase='authorized';self.write_phase()
        with self.assertRaisesRegex(RuntimeError,'phase_denied'):early.quiesce()
        self.assertEqual(self.ops.calls,[])

    def test_timer_reactivation_after_early_quiescence_blocks_installation(self):
        self.phase='detached_candidate_pending';self.write_phase()
        early=ActiveRecoveryBackupTimers(self.plan,self.root,self.repair.source_guard,operations=self.ops)
        early.quiesce()
        self.ops.states[BACKUP_TIMERS[0]]['active']='active'
        self.phase='controller_resume_pending';self.write_phase()
        with self.assertRaisesRegex(RuntimeError,'timer_quiesce_failed'):self.repair.install()
        self.assertNotIn('installer_apply',self.ops.calls)
