"""Opt-in commit-unknown diagnostics on a marked disposable PostgreSQL database.

Metadata RPCs commit natively under service_role, then their response is lost.
External storage is an owned temporary filesystem, not a live provider. Required
safety assertions intentionally expose any referenced-byte cleanup after commit.
No authorization or full-provider acceptance is claimed by these diagnostics.
"""
import asyncio
import io
import os
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch
from uuid import uuid4

from fastapi import HTTPException, UploadFile
from psycopg import sql
from psycopg.types.json import Jsonb
from starlette.datastructures import Headers
from tests.disposable_database_support import connect_disposable_database

DSN = os.getenv('LEARNING_PRIVATE_UPLOAD_SYNTHETIC_DATABASE_DSN')
MARKER = 'madar-phase7-private-upload-ack-synthetic'
MARKERS = {MARKER, 'madar-notification-synthetic-rehearsal'}


class SyntheticAcknowledgementLost(RuntimeError):
    pass


def connect():
    db = connect_disposable_database(DSN, markers=MARKERS)
    db.execute("set statement_timeout='5s'")
    return db


class ApplicationRead:
    def __init__(self):
        self.filters = []
    def select(self, *_args): return self
    def eq(self, key, value): self.filters.append((key, value)); return self
    def limit(self, _amount): return self
    def execute(self):
        if {key for key, _ in self.filters} != {'tenant_id', 'id', 'kind'}:
            raise AssertionError('The real service must scope the application read')
        clauses = sql.SQL(' and ').join(sql.SQL('{}=%s').format(sql.Identifier(key)) for key, _ in self.filters)
        with connect() as db:
            db.execute('set role service_role')
            rows = [row[0] for row in db.execute(
                sql.SQL('select to_jsonb(a) from public.academy_applications a where ') + clauses,
                [value for _, value in self.filters])]
        return SimpleNamespace(data=rows)


@unittest.skipUnless(DSN, 'Opt-in committed-metadata/private-byte acknowledgement diagnostic')
class LearningPrivateUploadAcknowledgementDatabaseTests(unittest.TestCase):
    def setUp(self):
        self.db = connect(); self.addCleanup(self.db.close)
        self.assertEqual(self.db.execute(
            "select schema_version from public.application_schema_state where contract_key='core'"
        ).fetchone()[0], 150)
        self.tenant = self.db.execute(
            "insert into public.tenants(brand_name,owner_name) values('Private upload diagnostic','Synthetic') returning tenant_id"
        ).fetchone()[0]
        auth = uuid4(); email = str(auth) + '@example.invalid'
        self.db.execute('insert into auth.users(id,email) values(%s,%s)', (auth, email))
        self.user = self.db.execute(
            "insert into public.users(auth_id,first_name,last_name,email,tenant_id,account_status,email_verified) "
            "values(%s,'Synthetic','Upload',%s,%s,'active',true) returning id", (auth, email, self.tenant)
        ).fetchone()[0]
        self.db.execute(
            "insert into public.tenant_memberships(tenant_id,user_id,auth_id,role,status) values(%s,%s,%s,'owner','active')",
            (self.tenant, self.user, auth))
        self.db.execute(
            "insert into public.elearning_settings(tenant_id,settings) values(%s,%s)",
            (self.tenant, Jsonb({'programmes_enabled': True, 'tuition_support_enabled': True})))
        self.actor = SimpleNamespace(tenant_id=self.tenant, user_id=self.user, role='owner')
        directory = tempfile.TemporaryDirectory(); self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.stored = []
        self.committed = []
        # These fixtures are retained in this disposable-only database until its
        # owning container is removed. Restrictive audit FKs are not bypassed.

    def file(self):
        from PIL import Image
        content = io.BytesIO(); Image.new('RGB', (1, 1), 'white').save(content, format='PNG')
        return UploadFile(io.BytesIO(content.getvalue()), filename='synthetic.png',
                          headers=Headers({'content-type': 'image/png'}))

    def object_path(self, key):
        path = self.root / key
        if not path.resolve().is_relative_to(self.root.resolve()):
            raise AssertionError('Only owned temporary object paths are allowed')
        return path

    def store(self, *, storage_key, content, **_kwargs):
        path = self.object_path(storage_key)
        path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(content)
        self.stored.append(storage_key)

    def remove(self, *, storage_key):
        self.object_path(storage_key).unlink(missing_ok=True)

    def rpc_lost(self, name, body):
        if name not in {'manage_academy_document', 'submit_elearning_form'}:
            raise AssertionError('Unexpected mutation in diagnostic')
        arguments = sql.SQL(',').join(sql.SQL('{}=>%s').format(sql.Identifier(key)) for key in body)
        values = [Jsonb(value) if isinstance(value, (dict, list)) else value for value in body.values()]
        with connect() as db:
            db.execute('set role service_role')
            result = db.execute(sql.SQL('select public.{}({})').format(sql.Identifier(name), arguments), values).fetchone()[0]
        self.committed.append(result)
        # The autocommitted connection is CLOSED before fault injection; the
        # independent observer below must see the committed metadata afterward.
        raise SyntheticAcknowledgementLost('synthetic response lost after metadata commit')

    def assert_referenced_bytes_survive(self, table):
        self.assertEqual(len(self.committed), 1, 'Native metadata RPC must have committed')
        self.assertEqual(len(self.stored), 1)
        key = self.stored[0]
        row = self.db.execute(sql.SQL('select storage_key from public.{} where tenant_id=%s').format(
            sql.Identifier(table)), (self.tenant,)).fetchall()
        self.assertEqual(row, [(key,)], 'Independent observer must see persisted file metadata')
        self.assertTrue(self.object_path(key).is_file(),
                        'Persisted metadata references bytes removed by commit-unknown cleanup')

    def test_committed_academy_document_lost_reply_preserves_referenced_bytes(self):
        from services import academy_owner_service as service
        application = self.db.execute(
            "insert into public.academy_applications(tenant_id,user_id,kind,details,idempotency_key) "
            "values(%s,%s,'tuition','{}',%s) returning id", (self.tenant, self.user, uuid4())
        ).fetchone()[0]
        client = SimpleNamespace(table=lambda name: ApplicationRead() if name == 'academy_applications' else None,
                                 rpc=lambda name, body: SimpleNamespace(execute=lambda: self.rpc_lost(name, body)))
        with patch.object(service, 'service_supabase', client), patch.object(service, 'require_upgrade'), \
                patch.object(service, 'available'), patch.object(service, 'require_private_storage'), \
                patch.object(service, 'reserve_storage', return_value='synthetic-reservation'), \
                patch.object(service, 'finish_storage'), patch.object(service, 'release_storage', return_value=True), \
                patch.object(service, 'store_builder_asset', side_effect=self.store), \
                patch.object(service, 'delete_builder_asset', side_effect=self.remove):
            with self.assertRaises(HTTPException) as uncertain:
                asyncio.run(service.upload_document(self.actor, application, self.file()))
            self.assertEqual(uncertain.exception.status_code, 503)
            self.assertEqual(uncertain.exception.detail['code'], 'private_upload_outcome_unknown')
        self.assert_referenced_bytes_survive('academy_application_documents')

    def test_committed_learning_form_lost_reply_preserves_referenced_bytes(self):
        from services import elearning_forms_service as service
        definition = {'title': 'Synthetic private file', 'access': 'public', 'notifyOwner': False,
                      'sections': [{'id': 'page', 'title': 'Page', 'fields': [
                          {'id': 'proof', 'type': 'file', 'label': 'Proof', 'required': True}]}]}
        form = self.db.execute(
            "select public.manage_elearning_form(%s,%s,null,1,'Synthetic file form','active',%s)",
            (self.tenant, self.user, Jsonb(definition))).fetchone()[0]
        form['schema'] = definition
        payload = {'version': form['version'], 'idempotency_key': str(uuid4()), 'answers': {}}
        with patch.object(service, 'public_access'), patch.object(service, 'require_private_storage'), \
                patch.object(service, 'reserve_storage', return_value='synthetic-reservation'), \
                patch.object(service, 'finish_storage'), patch.object(service, 'release_storage', return_value=True), \
                patch.object(service, 'store_builder_asset', side_effect=self.store), \
                patch.object(service, 'delete_builder_asset', side_effect=self.remove), \
                patch.object(service, 'rpc', side_effect=self.rpc_lost):
            with self.assertRaises(HTTPException) as uncertain:
                asyncio.run(service.submit(self.tenant, form, self.actor, payload, [('proof', self.file())]))
            self.assertEqual(uncertain.exception.status_code, 503)
            self.assertEqual(uncertain.exception.detail['code'], 'private_upload_outcome_unknown')
        self.assert_referenced_bytes_survive('elearning_form_files')


if __name__ == '__main__':
    unittest.main()
