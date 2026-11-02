"""Preserved business records in the independently owned historical KVM fixture.

This constructs synthetic DATA before enrollment, not migration history or
authority. SQL supplies initial business records; real historical application
APIs perform calendar creation and reservation status changes and verify reads.
The original Auth/MFA/private-object fixture must already exist. A durable intent
prevents a failed or interrupted construction from silently reseeding records.
"""
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
from datetime import datetime, timedelta, timezone
import urllib.error
import urllib.parse
import urllib.request

ROOT = Path('/opt/madar-test/origin146')
RELEASE_STATE = Path('/var/lib/madar/releases/state.json')
SOURCE = 'b0fdfe049510724c06a04706390cd174ea57a1d1'


def require(value, code):
    if not value:
        raise RuntimeError('running146_business_' + code)


def owned_inputs():
    # Refuse before reading credentials, invoking Docker or opening a database.
    require(os.geteuid() == 0 and subprocess.check_output(
        ['systemd-detect-virt']).strip() == b'kvm', 'owned_kvm_required')
    from deployment.lib.provider_recovery_runtime import protected
    from deployment.lib.isolated_release_environment import observe_effect_fence
    observe_effect_fence()
    state = json.loads(protected(ROOT/'private.json', private=True).read_bytes())
    require(Path('/sys/class/dmi/id/product_uuid').read_text().strip().lower()
            == state['guest_uuid'] and subprocess.check_output(['hostname']).strip()
            == b'madar-release-test', 'guest_identity_changed')
    require(state['origin_source_sha'] == SOURCE, 'historical_source_required')
    probes = json.loads(protected(ROOT/'original-provider-probes.json', private=True).read_bytes())
    require(probes['system_identifier'] == state['database_system_identifier']
            and len(probes['subjects']) == 2, 'original_accounts_required')
    from deployment.lib.historical_origin import bootstrap_record
    adopted = bootstrap_record(Path('/var/lib/madar/releases/origin-bootstrap-adopted.json'))
    require(adopted['phase'] == 'bootstrap_adopted' and adopted['release_sha'] == SOURCE,
            'truthful_bootstrap_required')
    return state, probes


def insert(db, table, values):
    from psycopg import sql
    from psycopg.types.json import Jsonb
    args = [Jsonb(v) if isinstance(v, (dict, list)) else v for v in values.values()]
    query = sql.SQL('INSERT INTO public.{} ({}) VALUES ({}) RETURNING id').format(
        sql.Identifier(table), sql.SQL(',').join(map(sql.Identifier, values)),
        sql.SQL(',').join(sql.Placeholder() for _ in values))
    return str(db.execute(query, args).fetchone()[0])


def api(subject, *, application_base='http://127.0.0.1:8001'):
    """Use genuine password sessions, current membership and server CSRF."""
    require(application_base in {'http://127.0.0.1:8001', 'http://proxy:8001'}, 'private_application_endpoint_required')
    from http.cookies import SimpleCookie
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    cookies = {}; csrf = None

    def request(method, path, body=None, expected=200):
        nonlocal csrf
        require(path.startswith('/') and not path.startswith('//'), 'api_path_invalid')
        if method != 'GET' and path != '/auth/login':
            request('GET', '/auth/user_status')
        headers = {'Content-Type': 'application/json', 'Origin': 'https://hardening.test',
                   'X-Forwarded-Proto': 'https', 'X-Calendar-Cache-Bypass': '1',
                   'Cookie': '; '.join(k+'='+v for k, v in cookies.items())}
        if csrf:
            headers['X-CSRF-Token'] = csrf
        try:
            response = opener.open(urllib.request.Request(application_base+path,
                data=json.dumps(body).encode() if body is not None else None,
                method=method, headers=headers), timeout=25)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            raw = response.read(2*1024**2+1)
            require(len(raw) <= 2*1024**2, 'api_response_budget')
            if response.status != expected:
                from deployment.lib.migration_executor import atomic_json
                try:
                    failure = json.loads(raw).get('detail')
                except (ValueError, AttributeError):
                    failure = 'non-JSON error'
                atomic_json(ROOT/'business-last-http-error.json', {
                    'status': response.status, 'path': path.split('?')[0],
                    'detail': failure})
            require(response.status == expected, 'api_status_'+str(response.status)+'_'+path.split('?')[0])
            if expected != 200 and expected != 201:
                return None
            parsed = json.loads(raw)
            jar = SimpleCookie()
            for value in response.headers.get_all('Set-Cookie', []):
                jar.load(value)
            cookies.update({k: v.value for k, v in jar.items()})
            csrf = parsed.get('csrf_token', csrf)
            return parsed

    result = request('POST', '/auth/login', {k: subject[k] for k in ('email', 'password')})
    require(result.get('user', {}).get('id') == subject['user_id'] and csrf,
            'original_application_login_failed')
    request('GET', '/auth/user_status')
    return request


def seed(db, subjects, *, resume=False):
    from deployment.lib.migration_executor import atomic_json
    state = json.loads(RELEASE_STATE.read_bytes())
    require(not state.get('known_good_release', {}).get('historical_origin'), 'already_enrolled')
    require(not (ROOT/'business-fixture.json').exists(), 'already_created')
    intent = {'kind': 'synthetic-original-data', 'source_sha': SOURCE,
              'tenant_ids': [s['tenant_id'] for s in subjects]}
    progress = ROOT/'business-seed-progress.json'
    if resume:
        from deployment.lib.provider_recovery_runtime import protected
        require(json.loads(protected(ROOT/'business-seed-intent.json', private=True).read_bytes())
                == intent, 'seed_intent_changed')
        records = json.loads(protected(progress, private=True).read_bytes())
        require(isinstance(records, list) and len(records) <= len(subjects), 'seed_progress_invalid')
    else:
        atomic_json(ROOT/'business-seed-intent.json', intent, exclusive=True)
        records = []
        atomic_json(progress, records, exclusive=True)
    for index, subject in enumerate(subjects):
        tenant, user = subject['tenant_id'], subject['user_id']
        form = {'id': 'preserved-contact', 'title': 'Preserved contact',
                'fields': [{'id': 'message', 'type': 'text', 'label': 'Message'}]}
        schema = {'version': 1, 'defaultPageId': 'home', 'pages': [{'id': 'home', 'name': 'Home', 'slug': '/',
                   'elements': []}], 'forms': [form]}
        # No payment, credential, permission, policy or migration-state writes.
        # The fixture provenance explicitly distinguishes SQL setup from APIs.
        if index >= len(records):
            with db.transaction():
                # Synthetic commercial DATA, using the existing native calendar
                # fixture's ledger shape. No fictional administrator command/AAL2
                # audit is generated and enforcement remains enabled in the app.
                from psycopg.types.json import Jsonb
                book = 'original_business_'+secrets.token_hex(8)
                now = datetime.now(timezone.utc)
                db.execute("INSERT INTO public.commercial_price_books(id,version,effective_from,currency,"
                    "billing_interval,standalone_minor,bundle_minor,sales_start_at) VALUES(%s,'synthetic-original',%s,"
                    "'USD','month',%s,%s,%s)", (book, now-timedelta(days=1), Jsonb({'website': 2000, 'forms': 1500}),
                    Jsonb({'2': 3000}), now-timedelta(days=1)))
                db.execute("UPDATE public.tenant_commercial_state SET review_state='reviewed',reviewed_by=%s,"
                    "reviewed_at=%s WHERE tenant_id=%s", (user, now, tenant))
                db.execute("INSERT INTO public.tenant_subscriptions(tenant_id,plan_id,module_basis,state,catalog_version,"
                    "currency,price_minor,source) VALUES(%s,NULL,%s,'active','synthetic-original','USD',2000,'synthetic_fixture')",
                    (tenant, Jsonb({module: {'price_book_id': book, 'acquired_at': now.isoformat(), 'paid_since': None}
                                   for module in ('website', 'forms')})))
                db.execute("INSERT INTO public.commercial_access_periods(tenant_id,plan_id,module_ids,price_snapshot,"
                    "valid_from,valid_until,source_type,reason,created_by) VALUES(%s,NULL,ARRAY['website','forms'],'{}',%s,%s,"
                    "'complimentary','Synthetic original business preservation fixture',%s)",
                    (tenant, now-timedelta(hours=1), now+timedelta(days=1), user))
                project = insert(db, 'builder_projects', {'tenant_id': tenant, 'owner_user_id': user,
                    'name': 'Preserved synthetic site', 'slug': 'preserved-'+secrets.token_hex(6),
                    'draft_schema': schema, 'published_schema': schema, 'status': 'published',
                    'published_version': 1, 'published_revision': 0, 'last_published_at': now})
                submission = insert(db, 'builder_form_submissions', {'tenant_id': tenant,
                    'project_id': project, 'form_id': form['id'], 'form_title': form['title'],
                    'form_version': 1, 'answers': {'message': 'Original tenant '+str(tenant)},
                    'field_snapshot': form['fields']})
                reservation = insert(db, 'builder_reservations', {'tenant_id': tenant,
                    'project_id': project, 'block_id': 'preserved-slot', 'block_type': 'reservationBlock',
                    'reservation_title': 'Preserved appointment', 'customer_name': 'Synthetic customer',
                    'starts_at': '2035-01-02T10:00:00Z', 'ends_at': '2035-01-02T11:00:00Z',
                    'timezone': 'UTC', 'status': 'new', 'customer_email': None,
                    'payload': {'fixture': 'preserved-before-migration'}, 'field_snapshot': []})
                event = insert(db, 'notification_events', {'tenant_id': tenant, 'event_type': 'fixture.original',
                    'source_type': 'fixture', 'source_id': project, 'title': 'Preserved notification',
                    'body': 'Synthetic in-app record only'})
                notification = insert(db, 'user_notifications', {'event_id': event, 'tenant_id': tenant,
                    'user_id': user, 'event_type': 'fixture.original', 'title': 'Preserved notification',
                    'body': 'Synthetic in-app record only'})
                pending = insert(db, 'notification_outbox', {'tenant_id': tenant, 'user_id': user,
                    'channel': 'internal', 'template': 'fixture.original', 'available_at': '2035-01-01T00:00:00Z',
                    'payload': {'notification_id': notification}, 'deduplication_key': 'original-'+project})
            records.append({'tenant_id': tenant, 'user_id': user, 'project': project,
                'submission': submission, 'reservation': reservation,
                'notification_event': event, 'notification': notification, 'pending_outbox': pending})
            atomic_json(progress, records)
        record = records[index]
        require(record['tenant_id'] == tenant and record['user_id'] == user, 'seed_progress_subject_changed')
        project, reservation = record['project'], record['reservation']
        app = api(subject)
        if 'calendar' not in record:
            record['calendar'] = app('POST', '/calendar/calendars', {'name': 'Preserved calendar',
                'timezone': 'UTC', 'visibility': 'private'}, expected=201)['calendar']['id']
            atomic_json(progress, records)
        if 'event' not in record:
            record['event'] = app('POST', '/calendar/events', {'calendar_id': record['calendar'],
                'title': 'Preserved event', 'starts_at': '2035-01-02T12:00:00Z',
                'ends_at': '2035-01-02T13:00:00Z', 'timezone': 'UTC', 'project_id': project},
                expected=201)['event']['id']
            atomic_json(progress, records)
        if not record.get('status_transition_accepted'):
            changed = app('PATCH', '/builder/reservations/'+reservation+'/status', {'status': 'confirmed'})
            require(changed['reservation']['status'] == 'confirmed', 'reservation_transition_failed')
            record['status_transition_accepted'] = True
            atomic_json(progress, records)
    return records


def functional(subjects, records, *, member_subjects=None, application_base='http://127.0.0.1:8001'):
    require(len(records) == len(subjects) == 2, 'two_tenants_required')
    for index, subject in enumerate(subjects):
        app = api(subject, application_base=application_base); owned, other = records[index], records[1-index]
        project = app('GET', '/builder/projects/'+owned['project'])['project']
        require(project['tenant_id'] == subject['tenant_id'] and project['status'] == 'published'
                and project['published_schema']['forms'], 'project_data_changed')
        app('GET', '/builder/projects/'+other['project'], expected=404)
        submissions = app('GET', '/builder/projects/'+owned['project']+'/form-submissions')
        require(owned['submission'] in json.dumps(submissions), 'submission_missing')
        reservation = app('GET', '/builder/reservations/'+owned['reservation'])['reservation']
        require(reservation['status'] == 'confirmed', 'reservation_data_changed')
        app('GET', '/builder/reservations/'+other['reservation'], expected=404)
        query = urllib.parse.urlencode({'start': '2035-01-01T00:00:00Z', 'end': '2035-01-04T00:00:00Z'})
        workspace = app('GET', '/calendar/bootstrap?'+query)
        require(owned['event'] in json.dumps(workspace) and other['event'] not in json.dumps(workspace),
                'calendar_tenant_integrity_failed')
        site = app('GET', '/public/sites/'+owned['site_subdomain']+'/runtime')
        require(owned['project'] in json.dumps(site) and other['project'] not in json.dumps(site),
                'published_site_integrity_failed')
        if member_subjects is None:
            from deployment.lib.provider_recovery_runtime import protected
            member = json.loads(protected(ROOT/('member-'+str(subject['tenant_id'])+'.json'), private=True).read_bytes())
        else:
            require(len(member_subjects) == len(subjects), 'member_inventory_invalid')
            member = member_subjects[index]
        require(member['user_id'] == owned['member_user_id'] and member['tenant_id'] == subject['tenant_id'],
                'member_identity_changed')
        member_app = api(member, application_base=application_base)
        require(member_app('GET', '/builder/projects/'+owned['project'])['project']['tenant_id']
                == subject['tenant_id'], 'member_project_unavailable')
        member_app('GET', '/builder/projects/'+other['project'], expected=404)


def complete_original_data(db, state, subjects, records):
    """Finish fixture setup before enrollment; never change an enrolled origin."""
    from deployment.lib.migration_executor import atomic_json
    from deployment.lib.provider_recovery_runtime import protected
    release = json.loads(RELEASE_STATE.read_bytes())
    require(not release.get('known_good_release', {}).get('historical_origin'), 'already_enrolled')
    for subject, record in zip(subjects, records, strict=True):
        tenant = subject['tenant_id']
        if 'website_settings_id' not in record:
            slug = 'preserved-'+secrets.token_hex(8)
            record['website_settings_id'] = insert(db, 'website_settings', {'tenant_id': tenant,
                'user_id': subject['user_id'], 'subdomain': slug, 'standard_path_slug': slug,
                'published_project_id': record['project'], 'brand': 'Preserved synthetic site'})
            record['site_subdomain'] = slug
            atomic_json(ROOT/'business-fixture.json', {'version': 1, 'records': records,
                'provenance': {'initial_business_data': 'synthetic SQL before enrollment',
                    'calendar_and_reservation_transition': 'historical application APIs'}})
        private = ROOT/('member-'+str(tenant)+'.json')
        if not private.exists():
            # These are fresh synthetic test users, through the real Auth API.
            # No password or token enters command arguments, stdout or evidence.
            email = 'original-member-'+secrets.token_hex(8)+'@example.com'
            password = secrets.token_urlsafe(32)
            gateway = json.loads(subprocess.check_output(['docker', 'inspect', 'supabase-envoy']))[0]
            address = gateway['NetworkSettings']['Networks']['madar-local-supabase_default']['IPAddress']
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            request = urllib.request.Request('http://'+address+':8000/auth/v1/admin/users',
                data=json.dumps({'email': email, 'password': password, 'email_confirm': True}).encode(),
                headers={'Content-Type': 'application/json', 'apikey': state['anon_key'],
                         'Authorization': 'Bearer '+state['service_key']}, method='POST')
            with opener.open(request, timeout=15) as response:
                person = json.load(response)
            atomic_json(private, {'email': email, 'password': password, 'auth_id': person['id'],
                                 'tenant_id': tenant}, exclusive=True)
        member = json.loads(protected(private, private=True).read_bytes())
        require(member['tenant_id'] == tenant, 'member_tenant_changed')
        if 'user_id' not in member:
            # Unknown interrupted insert outcomes are not blindly replayed.
            require(db.execute('SELECT count(*) FROM public.users WHERE auth_id=%s',
                               (member['auth_id'],)).fetchone()[0] == 0, 'member_insert_outcome_requires_inspection')
            with db.transaction():
                member['user_id'] = int(insert(db, 'users', {'auth_id': member['auth_id'],
                    'tenant_id': tenant, 'email': member['email'], 'first_name': 'Original',
                    'last_name': 'Member', 'account_status': 'active', 'email_verified': True,
                    'email_verified_at': datetime.now(timezone.utc)}))
                db.execute("INSERT INTO public.tenant_memberships(tenant_id,user_id,auth_id,role,status) "
                    "VALUES(%s,%s,%s,'member','active')", (tenant, member['user_id'], member['auth_id']))
            atomic_json(private, member)
        record['member_user_id'] = member['user_id']
    atomic_json(ROOT/'business-fixture.json', {'version': 1, 'records': records,
        'provenance': {'initial_business_data': 'synthetic SQL before enrollment',
            'members': 'genuine Auth API and synthetic local membership records',
            'calendar_and_reservation_transition': 'historical application APIs'}})


def main():
    sys.path.insert(0, '/opt/madar-test/controller/web')
    state, probes = owned_inputs()
    require(sys.argv[1:] in (['--seed'], ['--resume'], ['--observe'], ['--complete-business']), 'explicit_mode_required')
    import psycopg
    from deployment.lib.migration_executor import atomic_json
    from deployment.lib.historical_origin import preservation_roots
    row = json.loads(subprocess.check_output(['docker', 'inspect', 'supabase-db']))[0]
    require(row['State']['Running'] and row['Config']['Labels'].get('com.madar.test.realm')
            == state['realm_id'], 'database_owner_changed')
    address = row['NetworkSettings']['Networks']['madar-local-supabase_default']['IPAddress']
    with psycopg.connect(host=address, port=5432, dbname='postgres', user='supabase_admin',
            password=state['database_password'], connect_timeout=5, autocommit=True) as db:
        identity = db.execute("SELECT system_identifier::text,schema_version,shobj_description(d.oid,'pg_database') "
            "FROM pg_control_system(),public.application_schema_state,pg_database d "
            "WHERE contract_key='core' AND d.datname=current_database()").fetchone()
        require(identity == (state['database_system_identifier'], 146, 'madar-isolated-'+state['realm_id']),
                'schema146_database_required')
        if sys.argv[1:] in (['--seed'], ['--resume']):
            records = seed(db, probes['subjects'], resume=sys.argv[1:] == ['--resume'])
            atomic_json(ROOT/'business-fixture.json', {'version': 1, 'records': records,
                'provenance': {'initial_business_data': 'synthetic SQL before enrollment',
                    'calendar_and_reservation_transition': 'historical application APIs'}}, exclusive=True)
        else:
            records = json.loads((ROOT/'business-fixture.json').read_bytes())['records']
        if sys.argv[1:] != ['--observe']:
            complete_original_data(db, state, probes['subjects'], records)
        functional(probes['subjects'], records)
        fingerprints = preservation_roots(db)
        result = {'source_sha': SOURCE, 'schema': 146, 'database_system_identifier': identity[0],
            'records': records, 'fingerprints': fingerprints, 'functional': True,
            'migration_executed': False, 'deployment_authority_issued': False}
        atomic_json(ROOT/'business-acceptance.json', result)
        print(json.dumps({k: v for k, v in result.items() if k != 'fingerprints'}, sort_keys=True))


if __name__ == '__main__':
    main()
