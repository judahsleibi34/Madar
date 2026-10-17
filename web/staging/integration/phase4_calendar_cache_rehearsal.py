#!/usr/bin/env python3
"""Synthetic native-auth calendar revocation rehearsal; INSPECT by default.

Runs two temporary source-overlay APIs on the retained synthetic provider only.
No external delivery, payment, retained-service restart or production authority.
Immutable synthetic commercial evidence is retained and identified privately.
"""
import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import secrets
import subprocess
import time
from urllib.parse import urlencode

import independent_recovery as recovery
import manage
import smoke

OWNER = 'phase4-calendar-cache-20261017-attempt3'
SCOPE = Path.home() / OWNER
BASELINE = Path.home() / 'schema148-readiness-20261017/revisions/32c77afd'
BASELINE_SHA = '32c77afd01a012c7d21240316d4a46e52c3cbf14'
PORTS = {'baseline': 19086, 'candidate': 19087}
BASES = {}


def main(mode):
    manage.require_staging_host()
    if SCOPE.is_symlink() or not SCOPE.is_dir() or SCOPE.stat().st_mode & 0o077:
        raise RuntimeError('Private owned calendar rehearsal scope required')
    binding = json.loads((SCOPE / 'source-binding.json').read_text())
    candidate = SCOPE / 'candidate'
    route = candidate / 'web/backend/routes/calendar_routes.py'
    if binding['route_sha256'] != hashlib.sha256(route.read_bytes()).hexdigest():
        raise RuntimeError('Candidate route source changed')
    runtime = Path.home() / 'madar-independent-recovery-20261017-attempt3'
    recovery.TARGET_PROJECT = runtime.name
    with recovery.target_context(runtime):
        manage.state(); manage.attest_resources(); manage.require_database_marker()
        if manage.sql("select schema_version from public.application_schema_state where contract_key='core';") != '148':
            raise RuntimeError('Synthetic schema148 required')
        row = json.loads(manage.docker('inspect', runtime.name + '-backend-1'))[0]
        networks = row['NetworkSettings']['Networks']
        if len(networks) != 1:
            raise RuntimeError('Ambiguous provider network')
        network = next(iter(networks))
        if not json.loads(manage.docker('network', 'inspect', network))[0]['Internal']:
            raise RuntimeError('Synthetic internal provider network required')
        if mode == 'INSPECT':
            print(json.dumps({'scope': OWNER, 'schema': 148, 'mode': mode, 'production_modified': False})); return
        if (SCOPE / 'result.json').exists() or (SCOPE / 'execution.json').exists():
            raise RuntimeError('Calendar rehearsal scope already consumed')
        available = int(next(line.split()[1] for line in Path('/proc/meminfo').read_text().splitlines() if line.startswith('MemAvailable:')))
        if available < 2300 * 1024:
            raise RuntimeError('Calendar rehearsal memory headroom insufficient')
        (SCOPE / 'execution.json').write_text(json.dumps({'owner': OWNER, 'source': binding}))
        values = dict(line.split('=', 1) for line in (runtime / 'application.env').read_text().splitlines())
        values.update({'CALENDAR_FEATURE_ENABLED': 'true', 'CALENDAR_SYNC_WORKER_ENABLED': 'true',
                       'CALENDAR_CREDENTIALS_SECRET': secrets.token_hex(32),
                       'FRONTEND_URLS': 'http://127.0.0.1:19086,http://127.0.0.1:19087',
                       'CSRF_TRUSTED_ORIGINS': 'http://127.0.0.1:19086,http://127.0.0.1:19087',
                       'COMMERCIAL_ENTITLEMENTS_ENFORCED': 'true'})
        if values.get('MADAR_BUSINESS_WRITE_AUTHORITY') or values.get('MADAR_BUSINESS_WRITE_CONTRACT'):
            raise RuntimeError('Protected runtime authority cannot be adopted by a source-overlay test')
        containers = []
        started = time.monotonic()
        try:
            for role, source in (('baseline', BASELINE), ('candidate', candidate)):
                env = {**values, 'MADAR_RELEASE_SHA': BASELINE_SHA if role == 'baseline' else binding['base_sha']}
                path = SCOPE / (role + '.env')
                descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
                with os.fdopen(descriptor, 'w') as output:
                    output.write(''.join(key + '=' + value + '\n' for key, value in env.items()))
                name = OWNER + '-' + role
                container = manage.docker('run', '--detach', '--name', name, '--label', 'com.madar.staging.owner=' + OWNER,
                    '--memory', '768m', '--cpus', '.5', '--pids-limit', '256', '--restart', 'no', '--read-only',
                    '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges:true', '--network', network,
                    '--env-file', str(path),
                    '--tmpfs', '/tmp:rw,nosuid,nodev,size=128m,mode=1777',
                    '--mount', 'type=bind,src=' + str(source / 'web/backend') + ',dst=/app,readonly',
                    row['Image']).decode().strip()
                containers.append(container)
                actual = json.loads(manage.docker('inspect', container))[0]
                if set(actual['NetworkSettings']['Networks']) != {network}:
                    raise RuntimeError('Temporary API network changed')
                address = actual['NetworkSettings']['Networks'][network]['IPAddress']
                import ipaddress
                if not ipaddress.ip_address(address).is_private:
                    raise RuntimeError('Temporary API is not private')
                # Docker29 does not publish host ports on an internal-only
                # network. Use only the measured temporary private endpoint.
                BASES[role] = 'http://' + address + ':8000'
            for role in PORTS:
                smoke.APPLICATION = BASES[role]
                for attempt in range(90):
                    try:
                        smoke.http('GET', '/health/live', application=True); break
                    except Exception:
                        if attempt == 89: raise
                        time.sleep(1)
            result = exercise(values['SUPABASE_SERVICE_KEY'])
            result.update({'scope': OWNER, 'baseline_source_sha': BASELINE_SHA, 'candidate_source': binding,
                'source_class': 'source-overlay-on-previously-accepted-dependency-image',
                'production_modified': False, 'elapsed_seconds': round(time.monotonic() - started, 3),
                'limitations': ['synthetic fixture, no production artifact acceptance',
                               'immutable synthetic commercial ledger fixtures retained privately',
                               'authoritative recomputation increases calendar read workload']})
            (SCOPE / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
            print(json.dumps(result, sort_keys=True))
        finally:
            for identifier in containers:
                measured = json.loads(manage.docker('inspect', identifier))[0]
                if measured['Id'] != identifier or measured['Config']['Labels'].get('com.madar.staging.owner') != OWNER:
                    raise RuntimeError('Temporary API cleanup ownership mismatch')
                manage.docker('rm', '--force', identifier)


def exercise(service):
    token = secrets.token_hex(8)
    tenant = int(manage.sql("insert into public.tenants(brand_name,owner_name) values('Phase4 calendar synthetic','Fixture') returning tenant_id;"))
    users = []
    for role in ('owner', 'member'):
        email, password = 'phase4-calendar-' + role + '-' + token + '@example.com', secrets.token_urlsafe(24)
        auth, _ = smoke.http('POST', '/auth/v1/admin/users', token=service,
                            body={'email': email, 'password': password, 'email_confirm': True})
        user = int(manage.sql("insert into public.users(auth_id,first_name,last_name,email,tenant_id,account_status,email_verified,email_verified_at) values(" +
            smoke.literal(auth['id']) + ",'Synthetic','Calendar'," + smoke.literal(email) + ',' + str(tenant) + ",'active',true,now()) returning id;"))
        manage.sql("insert into public.tenant_memberships(tenant_id,user_id,auth_id,role,status) values(" +
                   f"{tenant},{user}," + smoke.literal(auth['id']) + ',' + smoke.literal(role) + ",'active');")
        session, _ = smoke.http('POST', '/auth/v1/token?grant_type=password', body={'email': email, 'password': password})
        users.append({'id': user, 'auth_id': auth['id'], 'cookies': {'madar_access_token': session['access_token'], 'madar_refresh_token': session['refresh_token']}})
    owner, member = users
    book = 'phase4_calendar_' + token
    manage.sql("insert into public.commercial_price_books(id,version,effective_from,currency,billing_interval,standalone_minor,sales_start_at) values(" +
        smoke.literal(book) + ",'synthetic-calendar','2026-01-01','USD','month','{\"website\":2000}',now()-interval '1 day');" +
        f"update public.tenant_commercial_state set review_state='reviewed',reviewed_by={owner['id']},reviewed_at=now() where tenant_id={tenant};" +
        "insert into public.tenant_subscriptions(tenant_id,plan_id,module_basis,state,catalog_version,currency,price_minor,source) values(" + str(tenant) +
        ",null,jsonb_build_object('website',jsonb_build_object('price_book_id'," + smoke.literal(book) + ",'acquired_at',now()::text,'paid_since',null)),'active','synthetic-calendar','USD',2000,'synthetic_fixture');" +
        "insert into public.commercial_access_periods(tenant_id,plan_id,module_ids,price_snapshot,valid_from,valid_until,source_type,reason,created_by) values(" +
        str(tenant) + ",null,array['website'],'{}',now()-interval '1 day',now()+interval '1 day','complimentary','Synthetic calendar permission regression'," + str(owner['id']) + ');')
    (SCOPE / 'fixture-identities.json').write_text(json.dumps({'tenant': tenant, 'users': [{k: v for k, v in u.items() if k != 'cookies'} for u in users], 'price_book': book}))
    smoke.APPLICATION = BASES['candidate']
    status, headers = smoke.http('GET', '/auth/user_status', application=True, headers=smoke.cookie_header(owner['cookies']))
    owner['cookies'].update(smoke.cookies(headers))
    mutation = {**smoke.cookie_header(owner['cookies']), 'Origin': 'http://127.0.0.1:19087', 'X-CSRF-Token': status['csrf_token']}
    calendar, _ = smoke.http('POST', '/calendar/calendars', application=True, body={'name': 'Private synthetic calendar'}, headers=mutation, expected=(201,))
    calendar_id = calendar['calendar']['id']
    smoke.http('PUT', '/calendar/calendars/' + calendar_id + '/members', application=True,
               body={'user_id': member['id'], 'role': 'editor'}, headers=mutation)
    start = datetime.now(timezone.utc).replace(microsecond=0) + timedelta(days=1)
    secret = 'Synthetic confidential event ' + token
    created, _ = smoke.http('POST', '/calendar/events', application=True, headers=mutation, expected=(201,),
        body={'calendar_id': calendar_id, 'title': secret, 'starts_at': start.isoformat(), 'ends_at': (start + timedelta(hours=1)).isoformat(), 'visibility': 'private'})
    query = '/calendar/bootstrap?' + urlencode({'start': (start - timedelta(hours=1)).isoformat(), 'end': (start + timedelta(hours=2)).isoformat()})
    before = {}
    for role in PORTS:
        smoke.APPLICATION = BASES[role]
        before[role], _ = smoke.http('GET', query, application=True, headers=smoke.cookie_header(member['cookies']))
        assert any(event.get('title') == secret for event in before[role]['events'])
    smoke.http('PUT', '/calendar/calendars/' + calendar_id + '/members', application=True,
               body={'user_id': member['id'], 'role': 'availability'}, headers=mutation)
    after = {}; elapsed = {}
    for role in PORTS:
        smoke.APPLICATION = BASES[role]; measured = time.monotonic()
        after[role], headers = smoke.http('GET', query, application=True, headers=smoke.cookie_header(member['cookies']))
        elapsed[role] = round((time.monotonic() - measured) * 1000, 3)
    stale = any(event.get('title') == secret for event in after['baseline']['events'])
    safe = not any(event.get('title') == secret for event in after['candidate']['events'])
    assert stale, 'Baseline did not reproduce stale authorized details'
    assert safe, 'Candidate exposed details after downgrade'
    assert next(c for c in after['candidate']['calendars'] if c['id'] == calendar_id)['access_role'] == 'availability'
    # A calendar membership change must not alter the user's tenant membership.
    assert manage.sql(f"select role from public.tenant_memberships where tenant_id={tenant} and user_id={member['id']};") == 'member'
    return {'status': 'PASS', 'native_authentication': True, 'commercial_enforcement': True,
            'baseline_stale_private_details_reproduced': stale, 'candidate_private_details_denied': safe,
            'candidate_role': 'availability', 'single_request_elapsed_ms': elapsed,
            'latency_samples_not_benchmark': True}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('INSPECT', 'REHEARSE'), nargs='?', default='INSPECT')
    main(parser.parse_args().mode)
