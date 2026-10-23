"""One domain transaction; no REST fallback, arbitrary SQL or retry interface.

The separately configured application connection uses the existing authenticator
→ service_role boundary. It does not discover provider/root credentials or grant
roles. Membership/ACL/version decisions are reobserved and locked in PostgreSQL.
"""
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import os
from uuid import UUID

from fastapi import HTTPException
import psycopg
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict
from psycopg.types.json import Jsonb

FIELDS = frozenset({'tenant_id','calendar_id','created_by','title','description','location',
    'starts_at','ends_at','timezone','all_day','status','visibility','transparency','recurrence_rule','project_id'})


def configuration():
    """Validate without connecting or disclosing credentials."""
    dsn=os.getenv('MADAR_CALENDAR_DATABASE_DSN','')
    identity=os.getenv('MADAR_CALENDAR_DATABASE_SYSTEM_IDENTIFIER','')
    try:
        parameters=conninfo_to_dict(dsn)
        if (not dsn or not identity.isascii() or not identity.isdecimal()
                or parameters.get('user')!='authenticator' or not parameters.get('host')
                or not parameters.get('dbname') or not parameters.get('password') or parameters.get('service')):
            raise ValueError()
    except Exception:
        raise RuntimeError('calendar_transaction_configuration_invalid') from None
    return dsn,identity


def connect():
    try:
        dsn,_=configuration()
        return psycopg.connect(dsn,autocommit=True,connect_timeout=5,
            application_name='madar-calendar-mutation',options='-c search_path=pg_catalog,public,extensions')
    except Exception:
        raise HTTPException(503,detail={'code':'calendar_transaction_unavailable'}) from None


def _verify_connection(db):
    actor=db.execute('select session_user,rolsuper,rolcreaterole,rolcreatedb,rolreplication '
        'from pg_catalog.pg_roles where rolname=session_user').fetchone()
    if not actor or actor[0]!='authenticator' or any(actor[1:]):
        raise HTTPException(503,detail={'code':'calendar_transaction_role_invalid'})
    db.execute('set local role service_role')
    db.execute("set local lock_timeout='5s'")
    db.execute("set local statement_timeout='10s'")
    identity=db.execute('select system_identifier::text from pg_catalog.pg_control_system()').fetchone()[0]
    if identity!=os.getenv('MADAR_CALENDAR_DATABASE_SYSTEM_IDENTIFIER'):
        raise HTTPException(503,detail={'code':'calendar_transaction_database_mismatch'})


@contextmanager
def _transaction():
    committing=False
    try:
        with connect() as db:
            with db.transaction():
                _verify_connection(db)
                yield db
                committing=True
    except HTTPException:raise
    except psycopg.Error:
        raise HTTPException(503,detail={'code':'calendar_commit_unknown' if committing else 'calendar_transaction_failed'}) from None


def transport_status():
    """Read-only acceptance of the real transport, cluster and required ACLs."""
    try:configuration()
    except RuntimeError:return 'misconfigured'
    try:
        with connect() as db:
            with db.transaction():
                db.execute('set transaction read only')
                _verify_connection(db)
                permissions={
                    'users':('SELECT',),'tenants':('SELECT',),'tenant_memberships':('SELECT',),
                    'calendars':('SELECT',),'calendar_memberships':('SELECT',),'builder_projects':('SELECT',),
                    'calendar_events':('SELECT','INSERT','UPDATE'),
                    'calendar_event_attendees':('SELECT','INSERT','DELETE'),
                    'calendar_event_reminders':('SELECT','INSERT','DELETE'),
                    'calendar_event_changes':('INSERT',),'audit_logs':('INSERT',)}
                for table,privileges in permissions.items():
                    if not all(db.execute('select has_table_privilege(current_user,%s,%s)',
                            ('public.'+table,privilege)).fetchone()[0] for privilege in privileges):
                        return 'misconfigured'
                sequence=db.execute("select pg_get_serial_sequence('public.audit_logs','id')").fetchone()[0]
                if sequence and not db.execute('select has_sequence_privilege(current_user,%s,%s)',
                        (sequence,'USAGE')).fetchone()[0]:return 'misconfigured'
        return 'ok'
    except (HTTPException,psycopg.Error):return 'unavailable'


def conflict():
    raise HTTPException(409,detail={'code':'calendar_version_conflict',
        'message':'This event changed in another session. Refresh before trying again.'})


def _authorize(db,context,calendar_ids):
    member=db.execute("""select m.role from public.tenant_memberships m join public.users u on u.id=m.user_id
        join public.tenants t on t.tenant_id=m.tenant_id
        where m.tenant_id=%s and m.user_id=%s and m.auth_id=%s and u.auth_id=m.auth_id
        and m.status='active' and u.account_status='active' and t.lifecycle_state='active' for share of m,u,t""",
        (context.tenant_id,context.user_id,UUID(context.auth_id))).fetchone()
    if not member:raise HTTPException(403,detail='Active tenant membership required')
    ids=sorted({UUID(str(i)) for i in calendar_ids})
    calendars=db.execute("""select id,owner_user_id from public.calendars where tenant_id=%s and id=any(%s)
        order by id for share""",(context.tenant_id,ids)).fetchall()
    if len(calendars)!=len(ids):raise HTTPException(404,detail='Calendar not found')
    for calendar,owner in calendars:
        if member[0] in ('owner','admin') or owner==context.user_id:continue
        access=db.execute('select role from public.calendar_memberships where tenant_id=%s and calendar_id=%s '
            'and user_id=%s for share',(context.tenant_id,calendar,context.user_id)).fetchone()
        if not access or access[0] not in ('editor','owner'):
            raise HTTPException(403,detail='Calendar access denied')


def _write(db,changes,*,event=None,tenant=None,version=None):
    fields=list(changes)
    values=[Jsonb(value) if key=='recurrence_exclusions' else value for key,value in changes.items()]
    if event is None:
        query=sql.SQL('insert into public.calendar_events ({}) values ({}) returning to_jsonb(calendar_events)').format(
            sql.SQL(',').join(map(sql.Identifier,fields)),sql.SQL(',').join(sql.Placeholder() for _ in fields))
    else:
        query=sql.SQL('update public.calendar_events e set {} where id=%s and tenant_id=%s and version=%s '
            'and deleted_at is null returning to_jsonb(e)').format(
                sql.SQL(',').join(sql.SQL('{}=%s').format(sql.Identifier(k)) for k in fields))
        values.extend([event,tenant,version])
    result=db.execute(query,values).fetchone()
    if not result:conflict()
    return result[0]


def _children(db,context,event,payload):
    for table in ('calendar_event_attendees','calendar_event_reminders'):
        db.execute(sql.SQL('delete from public.{} where tenant_id=%s and event_id=%s').format(sql.Identifier(table)),
            (context.tenant_id,event['id']))
    for attendee in payload.attendees:
        db.execute('insert into public.calendar_event_attendees(tenant_id,event_id,email,display_name,is_external) '
            'values(%s,%s,%s,%s,true)',(context.tenant_id,event['id'],attendee.email.strip().lower(),attendee.display_name))
    for reminder in payload.reminders:
        scheduled=payload.starts_at.astimezone(timezone.utc)-timedelta(minutes=reminder.minutes_before)
        db.execute('insert into public.calendar_event_reminders(tenant_id,event_id,channel,minutes_before,scheduled_for) '
            'values(%s,%s,%s,%s,%s)',(context.tenant_id,event['id'],reminder.channel,reminder.minutes_before,scheduled))


def _change(db,context,event,action,scope,before,after):
    db.execute('insert into public.calendar_event_changes(tenant_id,event_id,changed_by,action,scope,before_data,after_data) '
        'values(%s,%s,%s,%s,%s,%s,%s)',(context.tenant_id,event,context.user_id,action,scope,
            Jsonb(before) if before is not None else None,Jsonb(after)))


def mutate_event(context,event_id,payload,row,*,expected_version,scope,occurrence_start,audit):
    if scope not in {'event','series','occurrence','future'} or not set(row)<=FIELDS:
        raise HTTPException(400,detail='Invalid calendar mutation')
    if row.get('tenant_id')!=context.tenant_id or row.get('created_by')!=context.user_id:
        raise HTTPException(403,detail='Calendar mutation identity mismatch')
    with _transaction() as db:
        original=db.execute('select to_jsonb(e) from public.calendar_events e where id=%s and tenant_id=%s '
            'for update',(UUID(str(event_id)),context.tenant_id)).fetchone()
        if not original:raise HTTPException(404,detail='Event not found')
        before=original[0]
        if before['version']!=expected_version or before['deleted_at'] is not None:conflict()
        _authorize(db,context,[before['calendar_id'],row['calendar_id']])
        if row.get('project_id'):
            project=db.execute('select id from public.builder_projects where id=%s and tenant_id=%s for share',
                (row['project_id'],context.tenant_id)).fetchone()
            if not project:raise HTTPException(404,detail='Project not found')
        if scope in {'occurrence','future'}:
            if not before['recurrence_rule'] or occurrence_start is None or occurrence_start.tzinfo is None:
                raise HTTPException(400,detail='A recurring occurrence must be selected')
            occurrence=occurrence_start.astimezone(timezone.utc)
            if occurrence<datetime.fromisoformat(before['starts_at']):
                raise HTTPException(400,detail='Occurrence precedes series')
            if scope=='occurrence':
                exclusions=list(before.get('recurrence_exclusions') or [])
                if occurrence.isoformat() not in exclusions:exclusions.append(occurrence.isoformat())
                parent_changes={'recurrence_exclusions':exclusions}
                replacement=dict(row,recurrence_rule=None,recurrence_parent_id=str(event_id),
                    recurrence_original_start=occurrence.isoformat(),version=1)
            else:
                parts=[p for p in before['recurrence_rule'].split(';') if p and not p.upper().startswith(('UNTIL=','COUNT='))]
                parts.append('UNTIL='+(occurrence-timedelta(seconds=1)).strftime('%Y%m%dT%H%M%SZ'))
                parent_changes={'recurrence_rule':';'.join(parts)}
                replacement=dict(row,recurrence_parent_id=None,recurrence_original_start=None,version=1)
            parent=_write(db,dict(parent_changes,version=expected_version+1),event=event_id,
                tenant=context.tenant_id,version=expected_version)
            event=_write(db,replacement)
            _children(db,context,event,payload)
            _change(db,context,event_id,'updated',scope,before,parent)
            _change(db,context,event['id'],'created',scope,None,event)
            result={'event':event,'series':parent}
        else:
            event=_write(db,dict(row,version=expected_version+1),event=event_id,
                tenant=context.tenant_id,version=expected_version)
            _children(db,context,event,payload)
            _change(db,context,event_id,'updated',scope,before,event)
            result={'event':event}
        _audit(db,context,event_id,'updated',{'scope':scope},audit)
        return result


def _audit(db,context,event_id,action,metadata,audit):
    db.execute('insert into public.audit_logs(tenant_id,actor_user_id,action,target_type,target_id,metadata,ip,user_agent) '
        'values(%s,%s,%s,%s,%s,%s,%s,%s)',(context.tenant_id,context.user_id,'calendar.event_'+action,
            'calendar_event',str(event_id),Jsonb(metadata),audit.get('ip'),audit.get('user_agent')))


def create_event(context,payload,row,*,audit):
    if not set(row)<=FIELDS or row.get('tenant_id')!=context.tenant_id or row.get('created_by')!=context.user_id:
        raise HTTPException(403,detail='Calendar mutation identity mismatch')
    with _transaction() as db:
        _authorize(db,context,[row['calendar_id']])
        if row.get('project_id'):
            project=db.execute('select id from public.builder_projects where id=%s and tenant_id=%s for share',
                (row['project_id'],context.tenant_id)).fetchone()
            if not project:raise HTTPException(404,detail='Project not found')
        event=_write(db,dict(row,version=1))
        _children(db,context,event,payload)
        _change(db,context,event['id'],'created','event',None,event)
        _audit(db,context,event['id'],'created',{'calendar_id':row['calendar_id']},audit)
        return event


def delete_event(context,event_id,*,expected_version,scope,occurrence_start,audit):
    if scope not in {'event','series','occurrence','future'}:
        raise HTTPException(400,detail='Invalid calendar mutation')
    with _transaction() as db:
        original=db.execute('select to_jsonb(e) from public.calendar_events e where id=%s and tenant_id=%s '
            'for update',(UUID(str(event_id)),context.tenant_id)).fetchone()
        if not original:raise HTTPException(404,detail='Event not found')
        before=original[0]
        if before['version']!=expected_version or before['deleted_at'] is not None:conflict()
        _authorize(db,context,[before['calendar_id']])
        action='deleted'
        if scope in {'occurrence','future'}:
            if not before['recurrence_rule'] or occurrence_start is None or occurrence_start.tzinfo is None:
                raise HTTPException(400,detail='A recurring occurrence must be selected')
            occurrence=occurrence_start.astimezone(timezone.utc)
            if occurrence<datetime.fromisoformat(before['starts_at']):
                raise HTTPException(400,detail='Occurrence precedes series')
            if scope=='occurrence':
                exclusions=list(before.get('recurrence_exclusions') or [])
                if occurrence.isoformat() not in exclusions:exclusions.append(occurrence.isoformat())
                changes={'recurrence_exclusions':exclusions}
            else:
                parts=[p for p in before['recurrence_rule'].split(';') if p and not p.upper().startswith(('UNTIL=','COUNT='))]
                parts.append('UNTIL='+(occurrence-timedelta(seconds=1)).strftime('%Y%m%dT%H%M%SZ'))
                changes={'recurrence_rule':';'.join(parts)}
            action='cancelled'
        else:changes={'deleted_at':datetime.now(timezone.utc).isoformat()}
        event=_write(db,dict(changes,version=expected_version+1),event=event_id,
            tenant=context.tenant_id,version=expected_version)
        _change(db,context,event_id,action,scope,before,event)
        _audit(db,context,event_id,'deleted',{'scope':scope},audit)
        return event
