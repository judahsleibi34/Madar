"""Filesystem fences: real separate process, held marker and unsafe path refusal."""
import multiprocessing
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from fastapi import HTTPException
from services.account_work_fence import account_lock, AccountWorkBusy, publish_hold


def hold_shared(ready,release):
    with account_lock(1,2):
        ready.set();release.wait(10)


class AccountWorkFenceTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.env=patch.dict(os.environ,{'DATA_UPLOAD_DIR':self.temp.name});self.env.start();self.addCleanup(self.env.stop)
        self.registration=patch('services.account_work_fence._registration_allowed',return_value=True);self.registration.start();self.addCleanup(self.registration.stop)

    def test_other_process_blocks_enrollment_until_work_finishes(self):
        context=multiprocessing.get_context('fork');ready=context.Event();release=context.Event()
        process=context.Process(target=hold_shared,args=(ready,release));process.start()
        try:
            self.assertTrue(ready.wait(5))
            with self.assertRaises(AccountWorkBusy):
                with account_lock(1,2,exclusive=True):pass
        finally:
            release.set();process.join(5)
            if process.is_alive():process.terminate();process.join()
        self.assertEqual(process.exitcode,0)
        with account_lock(1,2,exclusive=True):pass

    def test_hold_prevents_new_work_and_scopes_are_independent(self):
        with account_lock(1,2,exclusive=True) as marker:publish_hold(marker,{'action':'deactivate'})
        with self.assertRaises(HTTPException):
            with account_lock(1,2):pass
        with account_lock(1,3):pass
        with account_lock(2,2):pass
        with account_lock(1,2,exclusive=True) as marker:marker.unlink()
        with account_lock(1,2):pass

    def test_symlink_coordination_directory_is_refused(self):
        folder=Path(self.temp.name)/'.account_fences';folder.symlink_to('/tmp',target_is_directory=True)
        with self.assertRaises(AccountWorkBusy):
            with account_lock(1,2):pass

    def test_successful_finalization_retires_account_identifiers(self):
        from services.account_work_fence import finish_account_fence
        with account_lock(1,2,exclusive=True) as marker:
            publish_hold(marker,{'request_id':'private-operation','action':'delete'})
            lock=marker.with_suffix('.lock')
            self.assertEqual(finish_account_fence(marker,lambda:'verified'),'verified')
            self.assertFalse(marker.exists());self.assertFalse(lock.exists())
        self.assertEqual([p.name for p in (Path(self.temp.name)/'.account_fences').iterdir()],['.registry.lock'])

    def test_retired_account_cannot_recreate_lock_inode(self):
        from services.account_work_fence import finish_account_fence
        with account_lock(1,2,exclusive=True) as marker:
            publish_hold(marker,{'request_id':'private-operation','action':'delete'})
            finish_account_fence(marker,lambda:'verified')
        with patch('services.account_work_fence._registration_allowed',return_value=False):
            with self.assertRaises(HTTPException):
                with account_lock(1,2):pass
        folder=Path(self.temp.name)/'.account_fences'
        self.assertEqual([path.name for path in folder.iterdir()],['.registry.lock'])

    def test_failed_finalization_restores_hold_before_registration_reopens(self):
        from services.account_work_fence import finish_account_fence
        def fail():raise RuntimeError('disposable acknowledgement failure')
        with account_lock(1,2,exclusive=True) as marker:
            publish_hold(marker,{'action':'delete'})
            with self.assertRaises(RuntimeError):finish_account_fence(marker,fail)
            self.assertTrue(marker.exists());self.assertTrue(marker.with_suffix('.lock').exists())
        with self.assertRaises(HTTPException):
            with account_lock(1,2):pass

    def test_request_action_can_transition_its_read_scope_to_exclusive(self):
        from starlette.requests import Request
        from services.account_work_fence import protect_request,release_request_scope
        request=Request({'type':'http','state':{'account_work_middleware':True}})
        protect_request(request,1,2)
        release_request_scope(request,1,2)
        with account_lock(1,2,exclusive=True):pass
        self.assertEqual(request.scope['state']['account_work_contexts'],{})

    def test_all_registered_private_multipart_families_authenticate_before_body(self):
        import asyncio
        from services.account_work_fence import AccountWorkFenceMiddleware
        paths=['/users/2/data/upload','/users/2/data/projects/p/datasets/upload','/users/2/avatar','/builder/assets/upload','/ecommerce/product-media/upload','/elearning/assessment-attempts/11111111-1111-4111-8111-111111111111/recordings/22222222-2222-4222-8222-222222222222']
        for path in paths:
            events=[]
            def authenticate(*args,**kwargs):
                self.assertFalse(kwargs['allow_refresh']);events.append('authenticated')
            async def receive():events.append('body');return {'type':'http.request','body':b'','more_body':False}
            async def send(message):pass
            async def parser(scope,receive,send):await receive()
            with self.subTest(path=path),patch('services.project_dataset_service.schema_version',return_value=167),patch('services.auth_service.get_authenticated_user_row',side_effect=authenticate):
                asyncio.run(AccountWorkFenceMiddleware(parser)({'type':'http','method':'POST','path':path,'headers':[(b'content-type',b'multipart/form-data; boundary=fixture')]},receive,send))
            self.assertEqual(events,['authenticated','body'])

    def test_notification_keeps_pending_account_mail_and_fences_membership_home(self):
        from types import SimpleNamespace
        from unittest.mock import Mock
        from services import account_work_fence as fence
        client=Mock();client.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value=SimpleNamespace(data=[{'id':2,'tenant_id':7,'account_status':'pending_verification'}])
        sent=[]
        @fence.notification_work
        def deliver(row,*,client):sent.append('existing mail semantics')
        with patch.object(fence,'account_lock',wraps=fence.account_lock) as locks:
            deliver({'user_id':2,'tenant_id':1},client=client)
        self.assertEqual(sent,['existing mail semantics'])
        self.assertEqual({call.args for call in locks.call_args_list},{(1,2),(7,2)})
        with account_lock(7,2,exclusive=True) as marker:publish_hold(marker,{'action':'deactivate'})
        with self.assertRaises(HTTPException):deliver({'user_id':2,'tenant_id':1},client=client)
        self.assertEqual(len(sent),1)


class AccountJobDatabaseBindingTests(unittest.TestCase):
    def test_sync_async_and_file_jobs_keep_their_own_database_client(self):
        from contextlib import nullcontext
        from services import account_work_fence as fence
        from unittest.mock import sentinel
        import asyncio
        calls=[]
        @fence.scoped_work('row','owner_user_id')
        def sync(row,*,client):calls.append('sync')
        @fence.scoped_work('row','owner_user_id')
        async def asynchronous(row,*,client):calls.append('async')
        @fence.account_file_work
        def file_job(*,tenant_id,user_id,client):calls.append('file')
        with patch.object(fence,'account_lock',side_effect=lambda *a,**k:nullcontext()) as lock:
            row={'tenant_id':1,'owner_user_id':2}
            sync(row,client=sentinel.database)
            asyncio.run(asynchronous(row,client=sentinel.database))
            file_job(tenant_id=1,user_id=2,client=sentinel.database)
        self.assertEqual(calls,['sync','async','file'])
        self.assertEqual(len(lock.call_args_list),3)
        for call in lock.call_args_list:
            self.assertEqual(call.args,(1,2));self.assertIs(call.kwargs['client'],sentinel.database)
    def test_registration_refusal_prevents_all_job_effects(self):
        from services import account_work_fence as fence
        calls=[]
        @fence.scoped_work('row','owner_user_id')
        def job(row,*,client):calls.append('effect')
        with patch.object(fence,'account_lock',side_effect=AccountWorkBusy('wrong_database_or_account')):
            with self.assertRaises(AccountWorkBusy):job({'tenant_id':1,'owner_user_id':2},client=object())
        self.assertEqual(calls,[])


class CalendarJobDatabaseBindingTests(unittest.TestCase):
    def test_calendar_schema_observation_uses_the_job_client_and_refuses_unknown_schema(self):
        from services import account_work_fence as fence
        from unittest.mock import sentinel
        calls=[]
        @fence.calendar_work
        def job(row,*,client):calls.append('effect')
        with patch('services.project_dataset_service.schema_version',return_value=160) as schema:
            job({'tenant_id':1},client=sentinel.database)
            schema.assert_called_once_with(client=sentinel.database)
        self.assertEqual(calls,['effect'])
        with patch('services.project_dataset_service.schema_version',return_value=0):
            with self.assertRaises(HTTPException):job({'tenant_id':1},client=sentinel.database)
        self.assertEqual(calls,['effect'])
