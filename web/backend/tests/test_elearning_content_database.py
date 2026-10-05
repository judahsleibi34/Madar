"""Actual SQL security, atomic ordering and lifecycle on a marked local rehearsal."""
import json
import os
import unittest
from uuid import uuid4
import psycopg
from psycopg.conninfo import conninfo_to_dict

DSN=os.getenv('ELEARNING_SYNTHETIC_DATABASE_DSN')


@unittest.skipUnless(DSN,'Requires marked disposable local E-Learning database')
class ELearningContentDatabaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if conninfo_to_dict(DSN).get('host') not in {'localhost','127.0.0.1','::1'}: raise RuntimeError('Requires loopback database')
        with psycopg.connect(DSN) as db:
            marker=db.execute("select shobj_description(oid,'pg_database') from pg_database where datname=current_database()").fetchone()[0]
            if marker!='madar-elearning-synthetic-rehearsal': raise RuntimeError('Requires marked disposable database')

    def setUp(self):
        self.db=psycopg.connect(DSN);self.addCleanup(self.db.close)
        self.tenant=self.db.execute("insert into public.tenants(brand_name,owner_name) values('Content test','Local') returning tenant_id").fetchone()[0]
        auth=uuid4();email=f'{auth}@example.com'
        self.db.execute('insert into auth.users(id,email) values(%s,%s)',(auth,email))
        self.user=self.db.execute("insert into public.users(auth_id,first_name,last_name,email,tenant_id,account_status,email_verified) values(%s,'Content','Test',%s,%s,'active',true) returning id",(auth,email,self.tenant)).fetchone()[0]
        self.db.execute("insert into public.tenant_memberships(tenant_id,user_id,auth_id,role,status) values(%s,%s,%s,'owner','active')",(self.tenant,self.user,auth))
        self.course=self.db.execute("insert into public.elearning_courses(tenant_id,name) values(%s,'Content test') returning id",(self.tenant,)).fetchone()[0]
        self.section=self.db.execute("select public.manage_elearning_structure(%s,%s,%s,1,'create_section',null,'{\"name\":\"First\"}')",(self.tenant,self.course,self.user)).fetchone()[0]['sections'][0]['id']
        self.lesson=self.db.execute("select public.manage_elearning_structure(%s,%s,%s,2,'create_lesson',null,%s::jsonb)",(self.tenant,self.course,self.user,json.dumps({'section_id':self.section,'name':'Mixed'}))).fetchone()[0]['sections'][0]['lessons'][0]['id']
        self.revision=1

    def command(self,action='create',entity=None,payload=None,**overrides):
        args={'tenant':self.tenant,'course':self.course,'lesson':self.lesson,'user':self.user,'revision':self.revision,**overrides}
        result=self.db.execute('select public.manage_elearning_content(%s,%s,%s,%s,%s,%s,%s,%s::jsonb)',(args['tenant'],args['course'],args['lesson'],args['user'],args['revision'],action,entity,json.dumps(payload or {'type':'text','content':{'version':1,'body':'Welcome'}}))).fetchone()[0]
        self.revision=result['revision'];self.db.execute('set constraints all immediate');self.db.execute('set constraints all deferred')
        self.assertEqual([b['position'] for b in result['blocks']],list(range(len(result['blocks']))))
        return result

    def media(self,kind='audio',tenant=None):
        owner=tenant or self.tenant;extension='mp3' if kind=='audio' else 'mp4';filename=uuid4().hex+'.'+extension
        return str(self.db.execute("insert into public.builder_assets(tenant_id,storage_key,managed_filename,mime_type,size_bytes,sha256) values(%s,%s,%s,%s,128,%s) returning id",(owner,f'tenant_{owner}/builder_assets/{filename}',filename,'audio/mpeg' if kind=='audio' else 'video/mp4','a'*64)).fetchone()[0])

    def test_mixed_blocks_edit_order_duplicate_archive_restore_and_delete(self):
        text=self.command()['blocks'][0]['id']
        for kind in ('audio','video'):
            data=self.command(payload={'type':kind,'title':kind,'media_id':self.media(kind),'content':{'version':1,'caption':'Listen or watch'}})
            self.assertTrue(data['blocks'][-1]['media']['url'].startswith(f'/uploads/tenant_{self.tenant}/'))
        video=data['blocks'][-1]['id']
        data=self.command('reorder',video,{'direction':'up'});self.assertEqual(data['blocks'][1]['id'],video)
        data=self.command('update',text,{'type':'text','title':'Edited','content':{'version':1,'body':'Updated'}});self.assertEqual(data['blocks'][0]['content']['body'],'Updated')
        data=self.command('duplicate',text,{});copy=data['blocks'][1]['id'];self.assertNotEqual(copy,text);self.assertEqual(data['blocks'][1]['content'],data['blocks'][0]['content'])
        data=self.command('archive',copy,{'confirmed':True});self.assertIsNotNone(data['blocks'][-1]['archived_at'])
        data=self.command('restore',copy,{});self.assertIsNone(data['blocks'][-1]['archived_at'])
        data=self.command('delete',copy,{'confirmed':True});self.assertEqual(len(data['blocks']),3)
        loaded=self.db.execute('select public.get_elearning_content(%s,%s,%s)',(self.tenant,self.course,self.lesson)).fetchone()[0]
        self.assertEqual(loaded,data)

    def test_tenant_cross_course_lesson_and_block_attachment_protection(self):
        block=self.command()['blocks'][0]['id']
        other=self.db.execute("insert into public.elearning_courses(tenant_id,name) values(%s,'Other') returning id",(self.tenant,)).fetchone()[0]
        for kwargs in ({'tenant':self.tenant+10000},{'course':other},{'lesson':uuid4()}):
            with self.assertRaises(psycopg.errors.NoDataFound),self.db.transaction(): self.command(**kwargs)
        with self.assertRaises(psycopg.errors.NoDataFound),self.db.transaction(): self.command('duplicate',uuid4(),{})
        self.assertIsNone(self.db.execute('select public.get_elearning_content(%s,%s,%s)',(self.tenant,other,self.lesson)).fetchone()[0])
        with self.assertRaises(psycopg.errors.ForeignKeyViolation),self.db.transaction():
            self.db.execute("insert into public.elearning_content_blocks(tenant_id,course_id,lesson_id,type,content,position) values(%s,%s,%s,'text','{}',0)",(self.tenant,other,self.lesson))
            self.db.execute('set constraints all immediate')
        self.assertEqual(self.db.execute('select id from public.elearning_content_blocks where lesson_id=%s',(self.lesson,)).fetchall(),[( __import__('uuid').UUID(block),)])

    def test_invalid_type_media_ownership_soft_deleted_and_mime(self):
        stranger=self.db.execute("insert into public.tenants(brand_name,owner_name) values('Other','Local') returning tenant_id").fetchone()[0]
        foreign=self.media(tenant=stranger);video=self.media('video');audio=self.media()
        self.db.execute("update public.builder_assets set status='soft_deleted' where id=%s",(audio,))
        cases=[{'type':'quiz','content':{'version':1}}, {'type':'text','content':{'version':1,'body':' '}}, {'type':'audio','media_id':foreign,'content':{'version':1}}, {'type':'audio','media_id':video,'content':{'version':1}}, {'type':'audio','media_id':audio,'content':{'version':1}}, {'type':'video','media_id':str(uuid4()),'content':{'version':1}}]
        for payload in cases:
            with self.subTest(payload=payload),self.assertRaises(psycopg.errors.InvalidParameterValue),self.db.transaction(): self.command(payload=payload)
        self.assertEqual(self.db.execute('select count(*) from public.elearning_content_blocks').fetchone()[0],0)

    def test_permissions_stale_revision_confirmation_and_archived_parent(self):
        block=self.command()['blocks'][0]['id']
        for action in ('archive','delete'):
            with self.assertRaises(psycopg.errors.InvalidParameterValue),self.db.transaction(): self.command(action,block,{})
        with self.assertRaisesRegex(psycopg.errors.RaiseException,'conflict'),self.db.transaction(): self.command(revision=1)
        self.db.execute("update public.tenant_memberships set role='member' where tenant_id=%s",(self.tenant,))
        with self.assertRaises(psycopg.errors.InsufficientPrivilege),self.db.transaction(): self.command()
        self.db.execute("update public.tenant_memberships set role='owner' where tenant_id=%s",(self.tenant,))
        self.db.execute("update public.elearning_courses set status='archived' where id=%s",(self.course,))
        with self.assertRaisesRegex(psycopg.errors.RaiseException,'parent_archived'),self.db.transaction(): self.command()
        for role in ('anon','authenticated','service_role'):
            self.assertFalse(self.db.execute("select has_table_privilege(%s,'public.elearning_content_blocks','INSERT,UPDATE,DELETE')",(role,)).fetchone()[0])
        for role in ('anon','authenticated'):
            self.assertFalse(self.db.execute("select has_function_privilege(%s,'public.manage_elearning_content(integer,uuid,uuid,integer,integer,text,uuid,jsonb)','EXECUTE')",(role,)).fetchone()[0])

    def test_parent_deletion_and_structure_duplication_keep_content_safe(self):
        self.command();revision=self.db.execute('select structure_revision from public.elearning_courses where id=%s',(self.course,)).fetchone()[0]
        with self.assertRaises(psycopg.errors.ForeignKeyViolation),self.db.transaction():
            self.db.execute("select public.manage_elearning_structure(%s,%s,%s,%s,'delete_lesson',%s,'{\"confirmed\":true}')",(self.tenant,self.course,self.user,revision,self.lesson))
            self.db.execute('set constraints all immediate')
        copied=self.db.execute("select public.manage_elearning_structure(%s,%s,%s,%s,'duplicate_lesson',%s,'{}')",(self.tenant,self.course,self.user,revision,self.lesson)).fetchone()[0]
        new_lesson=copied['sections'][0]['lessons'][1]['id']
        self.assertEqual(self.db.execute('select public.get_elearning_content(%s,%s,%s)',(self.tenant,self.course,new_lesson)).fetchone()[0]['blocks'][0]['content']['body'],'Welcome')
        copied=self.db.execute("select public.manage_elearning_structure(%s,%s,%s,%s,'duplicate_section',%s,'{}')",(self.tenant,self.course,self.user,copied['revision'],self.section)).fetchone()[0]
        for lesson in copied['sections'][1]['lessons']:
            self.assertEqual(len(self.db.execute('select public.get_elearning_content(%s,%s,%s)',(self.tenant,self.course,lesson['id'])).fetchone()[0]['blocks']),1)
        result=self.db.execute("select public.delete_elearning_course(%s,%s,%s,1,%s,'Content test',true)",(self.tenant,self.course,self.user,copied['revision'])).fetchone()[0]
        self.assertTrue(result['deleted']);self.assertEqual(self.db.execute('select count(*) from public.elearning_content_blocks').fetchone()[0],0)

    def test_tenant_purge_removes_content_but_ordinary_lesson_delete_is_restricted(self):
        self.command(payload={"type":"audio","media_id":self.media(),"content":{"version":1}})
        self.db.execute('update public.users set tenant_id=null where tenant_id=%s',(self.tenant,))
        self.db.execute('delete from public.tenants where tenant_id=%s',(self.tenant,))
        self.db.execute('set constraints all immediate')
        self.assertEqual(self.db.execute('select count(*) from public.elearning_content_blocks where tenant_id=%s',(self.tenant,)).fetchone()[0],0)

    def test_content_commands_serialize_concurrent_edits(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier
        self.db.commit()
        barrier=Barrier(2)
        def create(body):
            with psycopg.connect(DSN) as db:
                barrier.wait(timeout=5)
                try:
                    db.execute("select public.manage_elearning_content(%s,%s,%s,%s,1,'create',null,%s::jsonb)",(self.tenant,self.course,self.lesson,self.user,json.dumps({'type':'text','content':{'version':1,'body':body}})))
                    return 'created'
                except psycopg.errors.RaiseException as error:
                    if 'elearning_content_conflict' not in str(error): raise
                    return 'conflict'
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures=[pool.submit(create,body) for body in ('First','Second')]
            self.assertEqual(sorted(f.result(timeout=10) for f in futures),['conflict','created'])
        data=self.db.execute('select public.get_elearning_content(%s,%s,%s)',(self.tenant,self.course,self.lesson)).fetchone()[0]
        self.assertEqual(data['revision'],2);self.assertEqual(len(data['blocks']),1);self.assertEqual(data['blocks'][0]['position'],0)
        # Remove only this committed synthetic fixture; other tests use rollback.
        self.db.execute('update public.users set tenant_id=null where tenant_id=%s',(self.tenant,))
        self.db.execute('delete from public.tenants where tenant_id=%s',(self.tenant,));self.db.commit()

    def test_blocks_cannot_be_taken_from_another_lesson_and_delete_rolls_back(self):
        block=self.command()['blocks'][0]['id']
        revision=self.db.execute('select structure_revision from public.elearning_courses where id=%s',(self.course,)).fetchone()[0]
        data=self.db.execute("select public.manage_elearning_structure(%s,%s,%s,%s,'create_lesson',null,%s::jsonb)",(self.tenant,self.course,self.user,revision,json.dumps({'section_id':self.section,'name':'Other lesson'}))).fetchone()[0]
        other=data['sections'][0]['lessons'][1]['id']
        with self.assertRaises(psycopg.errors.NoDataFound),self.db.transaction(): self.command('duplicate',block,{},lesson=other,revision=1)
        self.db.execute('create table public.synthetic_content_guard(lesson_id uuid references public.elearning_lessons(id))')
        self.db.execute('insert into public.synthetic_content_guard values(%s)',(self.lesson,))
        with self.assertRaises(psycopg.errors.ForeignKeyViolation),self.db.transaction():
            self.db.execute("select public.delete_elearning_course(%s,%s,%s,1,%s,'Content test',true)",(self.tenant,self.course,self.user,data['revision']))
        self.assertEqual(self.db.execute('select id from public.elearning_content_blocks where lesson_id=%s',(self.lesson,)).fetchone()[0].hex,block.replace('-',''))
