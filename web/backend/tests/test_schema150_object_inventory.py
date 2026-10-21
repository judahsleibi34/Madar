"""Owned temporary filesystem measurements; no provider/controller authority."""
import copy
import hashlib
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, os.getenv('MADAR_TEST_REPOSITORY_ROOT') or str(Path(__file__).resolve().parents[2]))
from deployment.lib import schema150_object_inventory as objects


class ObjectInventoryTests(unittest.TestCase):
    def test_unrelated_ancestor_sibling_change_does_not_invalidate_root_identity(self):
        roots, base = self.roots()
        target = Path(roots['avatars']['source'])
        actual_open = os.open
        changed = []
        def open_with_sibling(path, flags, *args, **kwargs):
            if path == base.name and not changed:
                changed.append(True)
                (base / 'unrelated-sibling').mkdir()
            return actual_open(path, flags, *args, **kwargs)
        with patch.object(objects.os, 'open', side_effect=open_with_sibling):
            descriptor = objects._open_root(str(target))
        try:
            self.assertEqual(os.fstat(descriptor).st_ino, target.stat().st_ino)
        finally: os.close(descriptor)
        self.assertEqual(changed, [True])

    def test_ancestor_permission_change_during_open_still_refuses(self):
        roots, base = self.roots()
        actual_open = os.open
        def open_changed(path, flags, *args, **kwargs):
            if path == base.name: base.chmod(0o750)
            return actual_open(path, flags, *args, **kwargs)
        with patch.object(objects.os, 'open', side_effect=open_changed):
            with self.assertRaisesRegex(RuntimeError, 'object_path_changed'):
                objects._open_root(roots['avatars']['source'])

    def test_measured_root_content_change_during_open_still_refuses(self):
        roots, base = self.roots()
        target = Path(roots['avatars']['source'])
        actual_open = os.open
        def open_changed(path, flags, *args, **kwargs):
            if path == target.name: (target / 'late-object').write_bytes(b'synthetic')
            return actual_open(path, flags, *args, **kwargs)
        with patch.object(objects.os, 'open', side_effect=open_changed):
            with self.assertRaisesRegex(RuntimeError, 'object_path_changed'):
                objects._open_root(str(target))

    def test_replaced_ancestor_with_same_permissions_still_refuses(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory) / 'ancestor'
            target = base / 'objects'
            target.mkdir(parents=True)
            original_mode = base.stat().st_mode & 0o777
            actual_open = os.open
            def open_replaced(path, flags, *args, **kwargs):
                if path == base.name:
                    base.rename(base.with_name('original'))
                    base.mkdir(mode=original_mode)
                    (base / 'objects').mkdir()
                return actual_open(path, flags, *args, **kwargs)
            with patch.object(objects.os, 'open', side_effect=open_replaced):
                with self.assertRaisesRegex(RuntimeError, 'object_path_changed'):
                    objects._open_root(str(target))

    def roots(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        base=Path(temporary.name)
        roots={}
        for role in sorted(objects.REQUIRED_OBJECT_ROOTS):
            root=base/role;root.mkdir()
            # A private shell umask may already create0700. Give the fixture an
            # explicit preimage so the chmod0700 regression actually changes it.
            # The enclosing TemporaryDirectory remains private in either case.
            root.chmod(0o750)
            roots[role]={'type':'volume' if role in ('database','provider_storage') else 'bind',
                         'source':str(root),'content_sha256':'a'*64}
        return roots,base

    def test_identity_preimage_never_reads_database_or_live_object_contents(self):
        roots,_=self.roots()
        for role in roots:(Path(roots[role]['source'])/'payload').write_text('synthetic-'+role)
        with patch.object(objects,'_scan_once',side_effect=AssertionError('live bytes must not be measured')):
            measured=objects.measure_roots(roots)
        self.assertEqual(measured['phase'],'identity')
        for value in measured['roots'].values():
            self.assertIsNone(value['content'])
            self.assertEqual(set(value['identity']),{'device','inode','mode','uid','gid','mount_id'})
            self.assertIs(type(value['identity']['mount_id']),int)

    def test_fenced_two_pass_capture_and_preservation_ignore_historical_hash_reference(self):
        roots,_=self.roots();root=Path(roots['provider_storage']['source'])
        (root/'nested').mkdir();(root/'nested'/'private.bin').write_bytes(b'synthetic-private-object')
        prepared=objects.measure_roots(roots)
        captured=objects.measure_roots(roots,phase='fenced',previous=prepared)
        self.assertIsNone(captured['roots']['database']['content'])
        content=captured['roots']['provider_storage']['content']
        self.assertEqual((content['entries'],content['files'],content['bytes']),(2,1,24))
        self.assertNotEqual(content['sha256'],roots['provider_storage']['content_sha256'])
        self.assertEqual(objects.measure_roots(roots,phase='fenced',previous=captured),captured)
        self.assertNotIn('private.bin',str(captured))
        (root/'nested'/'private.bin').write_bytes(b'changed-object')
        with self.assertRaisesRegex(RuntimeError,'preservation_changed'):
            objects.measure_roots(roots,phase='fenced',previous=captured)

    def test_database_files_are_not_scanned_even_when_special_or_changed(self):
        roots,_=self.roots();database=Path(roots['database']['source'])
        os.mkfifo(database/'synthetic-wal-pipe')
        prepared=objects.measure_roots(roots)
        first=objects.measure_roots(roots,phase='fenced',previous=prepared)
        (database/'mutable-page').write_bytes(b'live-database-content')
        second=objects.measure_roots(roots,phase='fenced',previous=first)
        self.assertEqual(first,second)

    def test_root_replacement_changed_mode_and_missing_volume_mountpoint_refuse(self):
        roots,base=self.roots();previous=objects.measure_roots(roots)
        path=Path(roots['avatars']['source']);path.rename(base/'original-avatars');path.mkdir()
        with self.assertRaisesRegex(RuntimeError,'root_identity_changed'):
            objects.measure_roots(roots,previous=previous)
        path.rmdir();(base/'original-avatars').rename(path)
        path.chmod(0o700)
        with self.assertRaisesRegex(RuntimeError,'root_identity_changed'):
            objects.measure_roots(roots,previous=previous)
        roots['provider_storage']['source']='logical-volume-name'
        with self.assertRaises(RuntimeError):objects.measure_roots(roots)

    def test_symlink_root_ancestor_child_and_hardlinked_objects_refuse(self):
        roots,base=self.roots();target=Path(roots['avatars']['source']);other=base/'alias'
        other.symlink_to(target,target_is_directory=True)
        bad=copy.deepcopy(roots);bad['avatars']['source']=str(other)
        with self.assertRaises(RuntimeError):objects.measure_roots(bad)
        nested=target/'nested';nested.mkdir();(nested/'payload').write_text('synthetic')
        ancestor=base/'symlink-parent';ancestor.symlink_to(base,target_is_directory=True)
        bad=copy.deepcopy(roots);bad['avatars']['source']=str(ancestor/'avatars')
        with self.assertRaises(RuntimeError):objects.measure_roots(bad)
        (target/'symlink').symlink_to(nested/'payload')
        with self.assertRaisesRegex(RuntimeError,'special_or_linked_file'):objects.measure_roots(roots,phase='fenced')
        (target/'symlink').unlink();os.link(nested/'payload',nested/'second-hardlink')
        with self.assertRaisesRegex(RuntimeError,'special_or_linked_file'):objects.measure_roots(roots,phase='fenced')

    def test_special_files_never_block_or_get_read(self):
        roots,_=self.roots();os.mkfifo(Path(roots['avatars']['source'])/'blocked-pipe')
        with self.assertRaisesRegex(RuntimeError,'special_or_linked_file'):objects.measure_roots(roots,phase='fenced')

    def test_path_traversal_unknown_roots_overlap_and_previous_phase_regression_refuse(self):
        roots,base=self.roots()
        for source in ('/',str(base/'avatars'/'..'/'avatars'),str(base/'avatars')+'/',str(base/'avatars')+'\\bad'):
            bad=copy.deepcopy(roots);bad['avatars']['source']=source
            with self.subTest(source=source),self.assertRaises(RuntimeError):objects.measure_roots(bad)
        bad=copy.deepcopy(roots);bad['unknown']=bad['avatars']
        with self.assertRaises(RuntimeError):objects.measure_roots(bad)
        bad=copy.deepcopy(roots);bad['avatars']['source']=roots['builder_assets']['source']
        with self.assertRaisesRegex(RuntimeError,'root_overlap'):objects.measure_roots(bad)
        captured=objects.measure_roots(roots,phase='fenced')
        with self.assertRaisesRegex(RuntimeError,'phase_regression'):objects.measure_roots(roots,previous=captured)
        bad=copy.deepcopy(captured);bad['roots']['database']['content']={'pretend':'database-snapshot'}
        with self.assertRaisesRegex(RuntimeError,'previous_invalid'):objects.measure_roots(roots,phase='fenced',previous=bad)

    def test_file_size_total_bytes_entry_depth_and_deadline_bounds(self):
        roots,_=self.roots();root=Path(roots['avatars']['source']);(root/'payload').write_bytes(b'synthetic')
        for key,value,code in (('MAX_FILE_BYTES',2,'file_limit'),('MAX_CONTENT_BYTES',2,'content_limit'),
                               ('MAX_ENTRIES',0,'entry_limit'),('MAX_SECONDS',-1,'measurement_timeout')):
            with self.subTest(key=key),patch.object(objects,key,value),self.assertRaisesRegex(RuntimeError,code):
                objects.measure_roots(roots,phase='fenced')
        (root/'nested').mkdir()
        with patch.object(objects,'MAX_DEPTH',0),self.assertRaisesRegex(RuntimeError,'depth_limit'):
            objects.measure_roots(roots,phase='fenced')

    def test_nested_mount_or_file_mount_change_refuses(self):
        roots,_=self.roots();root=Path(roots['avatars']['source']);(root/'payload').write_text('synthetic')
        actual=objects._mount_id
        def changed(descriptor):
            identifier=actual(descriptor)
            return identifier+1 if os.readlink('/proc/self/fd/'+str(descriptor)).endswith('/payload') else identifier
        with patch.object(objects,'_mount_id',side_effect=changed),self.assertRaisesRegex(RuntimeError,'file_changed'):
            objects.measure_roots(roots,phase='fenced')
        previous=objects.measure_roots(roots)
        with patch.object(objects,'_mount_id',side_effect=lambda descriptor:actual(descriptor)+1):
            with self.assertRaisesRegex(RuntimeError,'root_identity_changed'):objects.measure_roots(roots,previous=previous)

    def test_content_mutation_and_root_swap_between_forest_passes_fail_closed(self):
        roots,base=self.roots();root=Path(roots['avatars']['source']);payload=root/'payload';payload.write_text('synthetic-before')
        actual=objects._scan_once;calls=[]
        def mutate(descriptor,identity,budget):
            result=actual(descriptor,identity,budget);calls.append(descriptor)
            if len(calls)==2:payload.write_text('synthetic-after')
            return result
        with patch.object(objects,'_scan_once',side_effect=mutate),self.assertRaisesRegex(RuntimeError,'content_changed'):
            objects.measure_roots(roots,phase='fenced')
        calls.clear()
        def swap(descriptor,identity,budget):
            result=actual(descriptor,identity,budget);calls.append(descriptor)
            if len(calls)==1:
                root.rename(base/'old-avatars');root.mkdir()
            return result
        with patch.object(objects,'_scan_once',side_effect=swap),self.assertRaisesRegex(RuntimeError,'root_identity_changed'):
            objects.measure_roots(roots,phase='fenced')

    def test_file_mutation_during_read_detected_by_actual_stat_even_same_size(self):
        roots,_=self.roots();payload=Path(roots['avatars']['source'])/'payload';payload.write_bytes(b'first-content')
        actual=objects._hash_file
        def mutate(descriptor,size,budget):
            digest=actual(descriptor,size,budget)
            if os.readlink('/proc/self/fd/'+str(descriptor))==str(payload):payload.write_bytes(b'other-content')
            return digest
        with patch.object(objects,'_hash_file',side_effect=mutate),self.assertRaisesRegex(RuntimeError,'file_changed'):
            objects.measure_roots(roots,phase='fenced')


    def test_previous_measurement_strict_primitives_scope_and_phase_cannot_supply_caller_pass(self):
        roots,_=self.roots();previous=objects.measure_roots(roots,phase='fenced')
        for kind in ('bool-identity','bool-count','unknown-root','missing-field','bad-digest','pretend-db-content'):
            bad=copy.deepcopy(previous)
            if kind=='bool-identity':bad['roots']['avatars']['identity']['mode']=True
            elif kind=='bool-count':bad['roots']['avatars']['content']['files']=True
            elif kind=='unknown-root':bad['roots']['unreviewed']=bad['roots']['avatars']
            elif kind=='missing-field':bad['roots']['avatars'].pop('content')
            elif kind=='bad-digest':bad['roots']['avatars']['content']['sha256']='PASS'
            else:bad['roots']['database']['content']={'PASS':True}
            with self.subTest(kind=kind),self.assertRaisesRegex(RuntimeError,'previous_invalid'):
                objects.measure_roots(roots,phase='fenced',previous=bad)


if __name__=='__main__':unittest.main()
