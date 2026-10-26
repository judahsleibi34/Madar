"""Configuration and route boundaries; native transaction assertions live separately."""
from datetime import datetime,timedelta,timezone
import os
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock,patch
from uuid import uuid4

from fastapi import HTTPException
from services import calendar_mutation_service as service
import routes.calendar_routes as routes


class CalendarTransactionBoundaryTests(TestCase):
    def test_missing_or_privileged_connection_configuration_never_opens_database(self):
        for dsn,identifier in (('',''),('host=localhost dbname=synthetic user=postgres','123'),
                ('host=localhost dbname=synthetic user=authenticator',''),
                ('dbname=synthetic user=authenticator','123'),
                ('host=localhost dbname=synthetic user=authenticator','123')):
            with self.subTest(dsn=dsn),patch.dict(os.environ,{'MADAR_CALENDAR_DATABASE_DSN':dsn,
                    'MADAR_CALENDAR_DATABASE_SYSTEM_IDENTIFIER':identifier}),patch.object(service.psycopg,'connect') as connect:
                with self.assertRaises(HTTPException) as failure:service.connect()
                self.assertEqual(failure.exception.status_code,503)
                connect.assert_not_called()

    def test_connection_failure_does_not_expose_credentials_or_retry(self):
        with patch.dict(os.environ,{'MADAR_CALENDAR_DATABASE_DSN':'host=localhost dbname=synthetic user=authenticator password=synthetic-private',
                'MADAR_CALENDAR_DATABASE_SYSTEM_IDENTIFIER':'123'}),\
                patch.object(service.psycopg,'connect',side_effect=service.psycopg.OperationalError('synthetic-private')) as connect:
            with self.assertRaises(HTTPException) as failure:service.connect()
            self.assertNotIn('synthetic-private',str(failure.exception.detail))
            self.assertEqual(connect.call_count,1)

    def test_route_delegates_all_edit_effects_to_one_transaction_without_rest_fallback(self):
        event=uuid4();calendar=uuid4();now=datetime.now(timezone.utc)
        context=SimpleNamespace(tenant_id=7,user_id=11)
        payload=routes.EventWrite(calendar_id=calendar,title='Edit',starts_at=now,ends_at=now+timedelta(hours=1))
        before={'id':str(event),'calendar_id':str(calendar),'version':3}
        with patch.object(routes,'require_calendar_feature'),patch.object(routes,'require_active_tenant_member',return_value=context),\
                patch.object(routes,'tenant_event',return_value=before),patch.object(routes,'require_calendar_access'),\
                patch.object(routes,'normalized_event_row',return_value={'tenant_id':7,'calendar_id':str(calendar)}),\
                patch.object(routes,'event_conflicts',return_value=[]),patch.object(routes,'service_supabase') as rest,\
                patch.object(routes,'invalidate_calendar_workspace_cache') as cache,\
                patch.object(routes,'mutate_event',side_effect=HTTPException(503,detail={'code':'calendar_commit_unknown'})) as mutate:
            with self.assertRaises(HTTPException):routes.update_event(str(event),payload,None,None,scope='series')
            mutate.assert_called_once()
            self.assertEqual(mutate.call_args.kwargs['expected_version'],3)
            rest.table.assert_not_called()
            cache.assert_called_once_with(7)

    def test_calendar_enabled_startup_requires_transport_and_redacts_the_dsn(self):
        from services.runtime_config import validate_runtime_configuration,redacted_configuration_inventory
        with patch.dict(os.environ,{'APP_ENV':'production','CALENDAR_FEATURE_ENABLED':'true'},clear=True):
            with self.assertRaisesRegex(RuntimeError,'calendar_transaction_configuration_invalid'):
                validate_runtime_configuration()
        with patch.dict(os.environ,{'MADAR_CALENDAR_DATABASE_DSN':'private-calendar-dsn'},clear=True):
            inventory=redacted_configuration_inventory({'MADAR_CALENDAR_DATABASE_DSN'})
            self.assertNotIn('private-calendar-dsn',str(inventory))
            self.assertEqual(next(row for row in inventory if row['name']=='MADAR_CALENDAR_DATABASE_DSN')['classification'],'secret')

    def test_calendar_readiness_requires_actual_transport_even_without_provider_sync(self):
        from services.readiness_service import check_calendar_configuration
        with patch.dict(os.environ,{'CALENDAR_FEATURE_ENABLED':'true','CALENDAR_SYNC_REQUIRED':'false'}):
            for state in ('misconfigured','unavailable','ok'):
                with self.subTest(state=state),patch.object(service,'transport_status',return_value=state) as probe:
                    self.assertEqual(check_calendar_configuration(),state)
                    probe.assert_called_once_with()
