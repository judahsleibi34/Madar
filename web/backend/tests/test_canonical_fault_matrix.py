import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import unittest

root=Path(os.getenv('MADAR_TEST_REPOSITORY_ROOT') or Path(__file__).resolve().parents[2])
spec=importlib.util.spec_from_file_location('canonical_fault_matrix',root/'staging/integration/canonical_fault_matrix.py')
f=importlib.util.module_from_spec(spec);spec.loader.exec_module(f)

def observation(boundary):
    phase,committed=f.BOUNDARIES[boundary]
    return dict(phase=phase,normal_completion=False,approval_consumed=True,
                schema=160 if committed else 146,committed=list(range(147,161)) if committed else [],
                executor_status='completed' if committed else None,migration_intent=committed)

def idle_child():
    # Popen returning is not proof that exec has settled its command line.
    # Synchronize through the child's actual executable before pinning identity.
    child=subprocess.Popen([sys.executable,'-c','import time; print("ready",flush=True); time.sleep(60)'],
                           start_new_session=True,stdout=subprocess.PIPE,text=True)
    if child.stdout.readline() != 'ready\n':
        child.kill();child.wait();raise RuntimeError('native_fixture_not_ready')
    child.stdout.close()
    return child


class Boundaries(unittest.TestCase):
    def test_four_finite_boundaries(self):
        self.assertEqual(len(f.BOUNDARIES),4)
        for name in f.BOUNDARIES:
            value=observation(name);self.assertTrue(f.matches(name,value))
            for key,bad in [('approval_consumed',False),('normal_completion',True),('schema',999),('committed',[147]),('phase','normal_completed')]:
                self.assertFalse(f.matches(name,dict(value,**{key:bad})))
    def test_real_pinned_child_and_descendant_exit(self):
        child=subprocess.Popen([sys.executable,'-c','import subprocess,time; p=subprocess.Popen(["sleep","60"]); print(p.pid,flush=True); time.sleep(60)'],start_new_session=True,stdout=subprocess.PIPE,text=True)
        descendant=int(child.stdout.readline());events=[]
        try:
            identity=f.process_identity(child.pid)
            f.interrupt_exact_process(child.pid,identity,boundary='committed_sql',observe=lambda:observation('committed_sql'),guard=lambda:None,record=lambda n,v:events.append(n),timeout=1)
            self.assertEqual(child.wait(timeout=5),-9)
            self.assertEqual(events,['stop_intent','kill_intent','leader_exited'])
            # A zombie has no running execution; reaping belongs to its parent.
            p=Path('/proc')/str(descendant)/'stat'
            try:state=p.read_text().rsplit(')',1)[1].split()[0]
            except (FileNotFoundError,ProcessLookupError):state=None  # Reaped during procfs read.
            self.assertIn(state,(None,'Z'))
        finally:
            if child.poll() is None:os.killpg(child.pid,9);child.wait()
            child.stdout.close()
    def test_changed_boundary_resumes_exact_child_without_kill(self):
        child=idle_child();calls=[]
        def observe():
            calls.append(1)
            return observation('before_sql') if len(calls)==1 else observation('committed_sql')
        try:
            with self.assertRaisesRegex(RuntimeError,'fault_boundary_changed'):
                f.interrupt_exact_process(child.pid,f.process_identity(child.pid),boundary='before_sql',observe=observe,guard=lambda:None,record=lambda *a:None,timeout=1)
            self.assertIsNone(child.poll())
            self.assertNotEqual(Path('/proc',str(child.pid),'stat').read_text().rsplit(')',1)[1].split()[0],'T')
        finally:os.killpg(child.pid,9);child.wait()
    def test_wrong_identity_refuses_without_signal(self):
        child=idle_child()
        try:
            start,argv,group=f.process_identity(child.pid)
            with self.assertRaisesRegex(RuntimeError,'identity_changed'):
                f.interrupt_exact_process(child.pid,(start+1,argv,group),boundary='before_sql',observe=lambda:observation('before_sql'),guard=lambda:None,record=lambda *a:None,timeout=1)
            self.assertIsNone(child.poll())
        finally:os.killpg(child.pid,9);child.wait()
    def test_missing_boundary_times_out_without_signal(self):
        child=idle_child()
        try:
            with self.assertRaisesRegex(RuntimeError,'boundary_(not_observed|deadline_expired)'):
                f.interrupt_exact_process(child.pid,f.process_identity(child.pid),boundary='before_sql',observe=lambda:observation('committed_sql'),guard=lambda:None,record=lambda *a:None,timeout=.1)
            self.assertIsNone(child.poll())
        finally:os.killpg(child.pid,9);child.wait()

    def test_slow_observation_or_record_cannot_signal_after_deadline(self):
        for delay_at in ('observe', 'stop_intent', 'kill_intent'):
            with self.subTest(delay_at=delay_at):
                child=idle_child();now=[0];events=[]
                def observe():
                    if delay_at=='observe':now[0]=2
                    return observation('before_sql')
                def record(name,value):
                    events.append(name)
                    if delay_at==name:now[0]=2
                try:
                    with self.assertRaisesRegex(RuntimeError,'deadline_expired'):
                        f.interrupt_exact_process(child.pid,f.process_identity(child.pid),boundary='before_sql',
                            observe=observe,guard=lambda:None,record=record,timeout=1,clock=lambda:now[0])
                    self.assertIsNone(child.poll())
                    self.assertNotEqual(Path('/proc',str(child.pid),'stat').read_text().rsplit(')',1)[1].split()[0],'T')
                    self.assertNotIn('leader_exited',events)
                finally:os.killpg(child.pid,9);child.wait()

    def test_diagnostic_failure_resumes_without_killing(self):
        child=idle_child()
        def record(name,value):
            if name=='kill_intent':raise OSError('owned evidence unavailable')
        try:
            with self.assertRaises(OSError):
                f.interrupt_exact_process(child.pid,f.process_identity(child.pid),boundary='before_sql',observe=lambda:observation('before_sql'),guard=lambda:None,record=record,timeout=1)
            self.assertIsNone(child.poll())
        finally:os.killpg(child.pid,9);child.wait()
    def test_real_adapter_refuses_nonroot_without_reading_policy(self):
        if os.geteuid()==0:self.skipTest('requires actual nonroot execution user')
        adapter=Path(f.__file__).with_name('canonical_fault_adapter.py')
        result=subprocess.run([sys.executable,'-I','-B',str(adapter),'--plan','/tmp/untrusted.json'],capture_output=True,timeout=5)
        self.assertNotEqual(result.returncode,0)
        self.assertIn(b'canonical_fault_root_required',result.stderr)
