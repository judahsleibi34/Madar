"""Real SQL uniqueness, tenant isolation and group deletion on disposable DBs."""
import os
import unittest
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4
import psycopg
from tests import test_elearning_relationships_database as relationships

@unittest.skipUnless(os.getenv('ELEARNING_SYNTHETIC_DATABASE_DSN'), 'Requires marked disposable local DB')
class GroupManagementDatabaseTests(unittest.TestCase):
    setUpClass = relationships.RelationshipsDatabaseTests.setUpClass
    setUp = relationships.RelationshipsDatabaseTests.setUp
    command = relationships.RelationshipsDatabaseTests.command
    media = relationships.RelationshipsDatabaseTests.media
    snapshot = relationships.RelationshipsDatabaseTests.snapshot
    relate = relationships.RelationshipsDatabaseTests.relate
    valid = relationships.RelationshipsDatabaseTests.valid
    access = relationships.RelationshipsDatabaseTests.access
    grant_group = relationships.RelationshipsDatabaseTests.grant_group
    revoke_manual = relationships.RelationshipsDatabaseTests.revoke_manual

    def delete(self, tenant=None, actor=None, revision=1, confirmed=True):
        return self.db.execute('select public.delete_elearning_group(%s,%s,%s,%s,%s)', (tenant or self.tenant, actor or self.user, self.a, revision, confirmed)).fetchone()[0]

    def test_name_identity_and_archived_names(self):
        for name in [' group   a ', 'GROUP A', 'Group\tA']:
            with self.assertRaises(psycopg.errors.UniqueViolation), self.db.transaction():
                self.db.execute('insert into public.elearning_groups(tenant_id,name) values(%s,%s)', (self.tenant,name))
        other = self.db.execute("insert into public.tenants(brand_name,owner_name) values('Other','Local') returning tenant_id").fetchone()[0]
        self.db.execute("insert into public.elearning_groups(tenant_id,name) values(%s,'Group A')", (other,))
        with self.assertRaises(psycopg.errors.UniqueViolation), self.db.transaction():
            self.db.execute("update public.elearning_groups set name='Group A' where id=%s", (self.b,))
        self.db.execute("update public.elearning_groups set status='archived' where id=%s", (self.a,))
        with self.assertRaises(psycopg.errors.UniqueViolation), self.db.transaction():
            self.db.execute("insert into public.elearning_groups(tenant_id,name) values(%s,'Group A')", (self.tenant,))

    def test_delete_preserves_progress_and_other_access(self):
        self.snapshot(lesson=self.lesson, complete=True)
        self.grant_group(); self.grant_group(self.b)
        self.relate('assign_instructor', target=self.instructor)
        for args, error in [({'actor':self.learner}, psycopg.errors.InsufficientPrivilege), ({'revision':2}, psycopg.errors.SerializationFailure), ({'confirmed':False}, psycopg.errors.InvalidParameterValue)]:
            with self.assertRaises(error), self.db.transaction(): self.delete(**args)
        other = self.db.execute("insert into public.tenants(brand_name,owner_name) values('Other','Local') returning tenant_id").fetchone()[0]
        # Authorized owner in another tenant still cannot guess the group URL.
        auth = self.db.execute('select auth_id from public.users where id=%s',(self.user,)).fetchone()[0]
        self.db.execute("insert into public.tenant_memberships(tenant_id,user_id,auth_id,role,status) values(%s,%s,%s,'owner','active')",(other,self.user,auth))
        with self.assertRaises(psycopg.errors.NoDataFound), self.db.transaction(): self.delete(tenant=other)
        self.assertEqual(self.delete()['id'],str(self.a))
        self.assertTrue(self.access())
        self.assertEqual({v['type'] for v in self.valid()},{'manual','group'})
        self.assertEqual(self.snapshot()['progress']['progress_percent'],50)
        for table, column in [('elearning_group_members','group_id'),('elearning_group_courses','group_id'),('elearning_group_instructors','group_id'),('elearning_access_grants','source_group_id')]:
            self.assertEqual(self.db.execute(f'select count(*) from public.{table} where {column}=%s',(self.a,)).fetchone()[0],0)
        self.assertTrue(self.db.execute('select 1 from public.users where id=%s',(self.learner,)).fetchone())
        self.assertTrue(self.db.execute('select 1 from public.elearning_enrollments where id=%s',(self.enrollment,)).fetchone())
        self.revoke_manual()
        self.a=self.b
        self.delete()
        self.assertFalse(self.access())
        self.assertTrue(self.db.execute('select 1 from public.elearning_enrollments where id=%s',(self.enrollment,)).fetchone())

    def test_delete_rpc_is_not_public(self):
        for role in ['anon','authenticated']:
            with self.assertRaises(psycopg.errors.InsufficientPrivilege), self.db.transaction():
                self.db.execute(f'set local role {role}')
                self.delete()

    def test_concurrent_duplicate_inserts(self):
        # This fixture is committed only in the disposable rehearsal DB.
        self.db.commit()
        barrier=Barrier(2); name=f'Concurrent {uuid4()}'
        def insert(value):
            with psycopg.connect(os.environ['ELEARNING_SYNTHETIC_DATABASE_DSN']) as db:
                barrier.wait(timeout=10)
                try: db.execute('insert into public.elearning_groups(tenant_id,name) values(%s,%s)',(self.tenant,value)); return 'created'
                except psycopg.errors.UniqueViolation: db.rollback(); return 'duplicate'
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(insert,[name,name.upper()]))
        self.assertCountEqual(results,['created','duplicate'])
