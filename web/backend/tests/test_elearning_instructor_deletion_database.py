"""Instructor deletion preserves identities, groups and learning history."""
import os
import unittest
import psycopg
from tests import test_elearning_relationships_database as relationships

@unittest.skipUnless(os.getenv('ELEARNING_SYNTHETIC_DATABASE_DSN'), 'Requires marked disposable local DB')
class InstructorDeletionDatabaseTests(unittest.TestCase):
    setUpClass = relationships.RelationshipsDatabaseTests.setUpClass
    setUp = relationships.RelationshipsDatabaseTests.setUp
    command = relationships.RelationshipsDatabaseTests.command
    media = relationships.RelationshipsDatabaseTests.media
    snapshot = relationships.RelationshipsDatabaseTests.snapshot
    relate = relationships.RelationshipsDatabaseTests.relate
    valid = relationships.RelationshipsDatabaseTests.valid
    access = relationships.RelationshipsDatabaseTests.access
    grant_group = relationships.RelationshipsDatabaseTests.grant_group

    def delete(self, tenant=None, actor=None, revision=1, confirmed=True):
        return self.db.execute('select public.delete_elearning_instructor(%s,%s,%s,%s,%s)',(tenant or self.tenant,actor or self.user,self.instructor,revision,confirmed)).fetchone()[0]

    def test_delete_assignments_preserves_user_and_progress(self):
        self.snapshot(lesson=self.lesson,complete=True); self.grant_group()
        self.db.execute('update public.elearning_instructors set user_id=%s where id=%s',(self.learner,self.instructor))
        self.relate('assign_instructor',target=self.instructor)
        self.relate('assign_instructor',kind='course',entity=self.course,target=self.instructor)
        for args,error in [({'actor':self.learner},psycopg.errors.InsufficientPrivilege),({'revision':2},psycopg.errors.SerializationFailure),({'confirmed':False},psycopg.errors.InvalidParameterValue)]:
            with self.assertRaises(error),self.db.transaction(): self.delete(**args)
        other=self.db.execute("insert into public.tenants(brand_name,owner_name) values('Other','Local') returning tenant_id").fetchone()[0]
        auth=self.db.execute('select auth_id from public.users where id=%s',(self.user,)).fetchone()[0]
        self.db.execute("insert into public.tenant_memberships(tenant_id,user_id,auth_id,role,status) values(%s,%s,%s,'owner','active')",(other,self.user,auth))
        with self.assertRaises(psycopg.errors.NoDataFound),self.db.transaction(): self.delete(tenant=other)
        self.assertEqual(self.delete()['id'],str(self.instructor))
        for table in ['elearning_course_instructors','elearning_group_instructors']:
            self.assertEqual(self.db.execute(f'select count(*) from public.{table} where instructor_id=%s',(self.instructor,)).fetchone()[0],0)
        self.assertTrue(self.db.execute('select 1 from public.users where id=%s',(self.learner,)).fetchone())
        self.assertTrue(self.db.execute('select 1 from public.elearning_groups where id=%s',(self.a,)).fetchone())
        self.assertTrue(self.access()); self.assertEqual(self.snapshot()['progress']['progress_percent'],50)

    def test_delete_rpc_is_not_public(self):
        for role in ['anon','authenticated']:
            with self.assertRaises(psycopg.errors.InsufficientPrivilege),self.db.transaction():
                self.db.execute(f'set local role {role}');self.delete()
