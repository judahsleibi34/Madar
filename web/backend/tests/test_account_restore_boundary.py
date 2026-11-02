"""Candidate restore-suppression component checks; no restore authority."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

from services import account_restore_boundary as boundary


class RestoreBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.env=patch.dict(os.environ,{'ACCOUNT_ERASURE_RESTORE_FLOOR_FILE':str(self.root/'control'/'floor.json'),'DATA_UPLOAD_DIR':str(self.root/'uploads'),'PRIVATE_CHARTS_DIR':str(self.root/'charts'),'PUBLIC_UPLOADS_DIR':str(self.root/'public')})
        self.env.start();self.addCleanup(self.env.stop)
        self.client=Mock();self.client.rpc.return_value.execute.return_value.data={'committed_epoch':0,'erasure_in_progress':False}

    def test_generation_and_snapshot_hash_refuse_stale_or_inflight_restore(self):
        before=boundary.capture_boundary(self.client)
        old=boundary.seal_snapshot(before,before,'a'*64)
        boundary.publish_floor(1)
        with self.assertRaisesRegex(boundary.RestoreBoundaryError,'incomplete'):boundary.capture_boundary(self.client)
        self.client.rpc.return_value.execute.return_value.data={'committed_epoch':1,'erasure_in_progress':False}
        after=boundary.capture_boundary(self.client)
        with self.assertRaisesRegex(boundary.RestoreBoundaryError,'resurrect'):boundary.verify_restore(old,'a'*64,self.client)
        with self.assertRaisesRegex(boundary.RestoreBoundaryError,'crossed'):boundary.seal_snapshot(before,after,'a'*64)
        current=boundary.seal_snapshot(after,after,'b'*64)
        with self.assertRaisesRegex(boundary.RestoreBoundaryError,'mismatch'):boundary.verify_restore(current,'c'*64,self.client)
        self.assertFalse(boundary.verify_restore(current,'b'*64,self.client)['restore_execution_authorized'])

    def test_floor_is_atomic_private_monotonic_and_visible_in_another_process(self):
        boundary.publish_floor(3)
        floor=Path(os.environ['ACCOUNT_ERASURE_RESTORE_FLOOR_FILE'])
        self.assertEqual(floor.stat().st_mode&0o777,0o600)
        result=subprocess.run([sys.executable,'-c','from services.account_restore_boundary import read_floor; print(read_floor())'],capture_output=True,text=True,env=os.environ,check=True)
        self.assertEqual(result.stdout.strip(),'3')
        with self.assertRaisesRegex(boundary.RestoreBoundaryError,'regress'):boundary.publish_floor(2)
        self.assertEqual(json.loads(floor.read_bytes()),{'version':1,'epoch':3})
        self.assertEqual(list(floor.parent.glob('.restore-floor-*')),[])

    def test_path_symlinks_hardlinks_permissions_and_payload_are_rejected(self):
        boundary.publish_floor(1)
        floor=Path(os.environ['ACCOUNT_ERASURE_RESTORE_FLOOR_FILE'])
        os.link(floor,self.root/'alias')
        with self.assertRaisesRegex(boundary.RestoreBoundaryError,'identity'):boundary.read_floor()
        (self.root/'alias').unlink()
        floor.chmod(0o644)
        with self.assertRaisesRegex(boundary.RestoreBoundaryError,'identity'):boundary.read_floor()
        floor.chmod(0o600);floor.write_text('{"version":1,"epoch":true}')
        with self.assertRaisesRegex(boundary.RestoreBoundaryError,'invalid'):boundary.read_floor()
        floor.unlink();floor.symlink_to(self.root/'unrelated')
        with self.assertRaisesRegex(boundary.RestoreBoundaryError,'unsafe'):boundary.read_floor()
        with patch.dict(os.environ,{'ACCOUNT_ERASURE_RESTORE_FLOOR_FILE':str(self.root/'uploads'/'floor')}):
            with self.assertRaisesRegex(boundary.RestoreBoundaryError,'independent'):boundary.floor_binding()
        floor.unlink();link=self.root/'link';link.symlink_to(floor.parent,target_is_directory=True)
        with patch.dict(os.environ,{'ACCOUNT_ERASURE_RESTORE_FLOOR_FILE':str(link/'child'/'floor')}):
            with self.assertRaisesRegex(boundary.RestoreBoundaryError,'unsafe'):boundary.floor_binding()

    def test_in_progress_or_missing_state_never_certifies_a_snapshot(self):
        self.client.rpc.return_value.execute.return_value.data={'committed_epoch':0,'erasure_in_progress':True}
        with self.assertRaisesRegex(boundary.RestoreBoundaryError,'in_progress'):boundary.capture_boundary(self.client)
        self.client.rpc.return_value.execute.return_value.data={'committed_epoch':0}
        with self.assertRaisesRegex(boundary.RestoreBoundaryError,'unavailable'):boundary.capture_boundary(self.client)

    def test_failed_floor_fsync_leaves_no_temporary_file_or_regressed_floor(self):
        boundary.publish_floor(3)
        with patch.object(boundary.os,'fsync',side_effect=OSError('fixture disk full')):
            with self.assertRaisesRegex(OSError,'fixture'):boundary.publish_floor(4)
        self.assertEqual(boundary.read_floor(),3)
        floor=Path(os.environ['ACCOUNT_ERASURE_RESTORE_FLOOR_FILE'])
        self.assertEqual(list(floor.parent.glob('.restore-floor-*')),[])
        manifest={'version':1,'epoch':3,'archive_sha256':'not-a-sha'}
        self.client.rpc.return_value.execute.return_value.data={'committed_epoch':3,'erasure_in_progress':False}
        with self.assertRaisesRegex(boundary.RestoreBoundaryError,'integrity_required'):
            boundary.verify_restore(manifest,'not-a-sha',self.client)
