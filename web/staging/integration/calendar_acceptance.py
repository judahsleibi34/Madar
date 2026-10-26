"""Actual HTTP/domain-SQL acceptance on the owned synthetic staging database."""
from datetime import datetime, timedelta, timezone
import json
import secrets
from uuid import UUID, uuid4

import manage
from smoke import http, literal, cookie_header, cookies, application_origin


def main():
    manage.require_database_marker()
    env = dict(line.split('=', 1) for line in (manage.RUNTIME / 'application.env').read_text().splitlines())
    suffix = secrets.token_hex(8)
    email, password = 'calendar-' + suffix + '@example.invalid', secrets.token_urlsafe(24)
    auth, _ = http('POST', '/auth/v1/admin/users', token=env['SUPABASE_SERVICE_KEY'],
        body={'email': email, 'password': password, 'email_confirm': True})
    auth_id = str(UUID(auth['id']))
    tenant = int(manage.sql("insert into public.tenants(brand_name,owner_name) values('Synthetic calendar','Fixture') returning tenant_id"))
    user = int(manage.sql("insert into public.users(auth_id,first_name,last_name,email,tenant_id,account_status,email_verified,email_verified_at) "
        f"values({literal(auth_id)},'Calendar','Owner',{literal(email)},{tenant},'active',true,now()) returning id"))
    manage.sql(f"insert into public.tenant_memberships(tenant_id,user_id,auth_id,role,status) values({tenant},{user},{literal(auth_id)},'owner','active')")
    session, _ = http('POST', '/auth/v1/token?grant_type=password', body={'email': email, 'password': password})
    jar = {'madar_access_token': session['access_token'], 'madar_refresh_token': session['refresh_token']}
    status, response_headers = http('GET', '/auth/user_status', application=True, headers=cookie_header(jar))
    jar.update(cookies(response_headers))
    headers = {**cookie_header(jar), 'Origin': application_origin(), 'X-CSRF-Token': status['csrf_token']}
    # Preserve commercial enforcement: deny the unentitled fixture first.
    http('POST', '/calendar/calendars', application=True, headers=headers,
        body={'name': 'Unentitled fixture'}, expected=(403,))
    seed_calendar_entitlement(tenant, suffix)
    calendar, _ = http('POST', '/calendar/calendars', application=True, headers=headers,
        body={'name': 'Synthetic transaction calendar'}, expected=(201,))
    start = datetime.now(timezone.utc) + timedelta(days=3)
    payload = {'calendar_id': calendar['calendar']['id'], 'title': 'Original recurring fixture',
        'starts_at': start.isoformat(), 'ends_at': (start + timedelta(hours=1)).isoformat(),
        'recurrence_rule': 'FREQ=DAILY;COUNT=4', 'attendees': [{'email': 'attendee@example.invalid'}],
        'reminders': [{'channel': 'in_app', 'minutes_before': 10}]}
    created, _ = http('POST', '/calendar/events', application=True, headers=headers, body=payload, expected=(201,))
    event = created['event']
    update = {**payload, 'expected_version': event['version'], 'title': 'Accepted recurring fixture'}
    http('PUT', '/calendar/events/' + event['id'] + '?scope=series', application=True, headers=headers, body=update)
    http('PUT', '/calendar/events/' + event['id'] + '?scope=series', application=True, headers=headers, body=update, expected=(409,))
    event_id = literal(str(UUID(event['id'])))
    assert manage.sql(f'select count(*) from calendar_event_attendees where event_id={event_id}') == '1'
    assert manage.sql(f'select count(*) from calendar_event_reminders where event_id={event_id}') == '1'
    assert int(manage.sql(f'select count(*) from calendar_event_changes where event_id={event_id}')) == 2
    assert int(manage.sql(f'select count(*) from audit_logs where target_id={event_id}')) == 2
    ready, _ = http('GET', '/health/ready', application=True)
    assert ready['ready'] is True
    result = {'status': 'PASS', 'http_create_recurring_edit_and_stale_conflict': True,
        'atomic_children_reminders_change_audit_observed': True, 'cluster_pinned_transport': True,
        'external_provider_sync_tested': False}
    manage.private_write('calendar-acceptance.json', json.dumps(result) + '\n')
    return result


def seed_calendar_entitlement(tenant, suffix):
    """Existing commercial commands, confined to this marked synthetic DB."""
    manage.require_database_marker()
    fixture=json.loads((manage.RUNTIME / 'smoke-fixture.json').read_text())
    actor=int(fixture['admin_user_id'])
    book='staging_calendar_' + suffix
    manage.sql("insert into public.commercial_price_books(id,version,effective_from,currency,billing_interval,standalone_minor,bundle_minor,sales_start_at) "
        f"values({literal(book)},{literal(book)},now()-interval '1 day','USD','month',"
        "'{\"forms\":1500,\"website\":2000,\"ecommerce\":2500}','{\"2\":3000,\"3\":4000}',now()-interval '1 day')")
    now=datetime.now(timezone.utc)
    for operation,request in (
        ('assign_modules',{'module_ids':['website'],'price_books':{'website':book}}),
        ('complimentary',{'module_ids':['website'],'valid_from':(now-timedelta(hours=1)).isoformat(),
            'valid_until':(now+timedelta(days=1)).isoformat()})):
        revision=int(manage.sql(f"select public.resolve_commercial_access({tenant})->>'revision'"))
        payload={'request':{'reason':'Synthetic staging calendar acceptance','expected_revision':revision,**request},'quote':{}}
        manage.sql(f"select public.apply_commercial_access_command({tenant},{actor},'aal2',{literal(operation)},"
            f"{literal(str(uuid4()))},'fresh-staging',{literal(json.dumps(payload))}::jsonb)")
