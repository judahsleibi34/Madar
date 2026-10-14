from typing import Literal
from uuid import UUID
from fastapi import APIRouter, Request, Response, Query
from routes.elearning_assessments_routes import owner
from routes.elearning_player_routes import member
from routes.elearning_structure_routes import operation
from services import academy_programme_service as service
from services.audit_service import record_audit_event

router = APIRouter(prefix='/elearning/programmes', tags=['Academy Programmes'])


@router.get('/capabilities')
def capabilities(request: Request, response: Response):
    actor = member(request, response)
    from services.academy_capability_service import capabilities as grants
    allowed = grants(actor.tenant_id)
    config = service.get_settings(actor.tenant_id) if service.settings_available() else {}
    programme_flags={key:bool(config.get('programmes_enabled') and config.get(flag)) for key,flag in [('tuition','tuition_support_enabled'),('exchange','exchange_programme_enabled'),('affiliate','affiliates_enabled')]}
    from services.elearning_academy_service import member_profile
    academy = member_profile(actor.tenant_id) if config.get('enabled') and config.get('academy_enabled') else None
    if academy:
        from services.elearning_academy_service import institution_for_member
        institution = institution_for_member(actor.tenant_id, actor.user_id)
        if institution:
            academy = {**academy, 'institution': institution}
    return {'academy': academy, 'form_reviews_available':service.settings_available(144), 'exchange_intake_available':bool((academy or {}).get('application_paths',{}).get('exchange') or (service.settings_available(142) and config.get('exchange_opportunities_enabled'))), 'programme_flags':programme_flags, 'capabilities': allowed, 'can_manage': actor.role in {'owner', 'admin'},
            'support_programme_name': config.get('support_programme_name', 'Support Programme') if allowed['tuition'] else None,
            'exchange_programme_name': config.get('exchange_programme_name', 'Exchange Programme') if allowed['exchange'] else None}


@router.get('/account')
def account(request: Request, response: Response):
    actor = member(request, response)
    return operation(lambda: service.account(actor))


@router.post('/applications')
def submit(payload: service.Application, request: Request, response: Response):
    actor = member(request, response)
    return operation(lambda: service.submit(actor, payload))


@router.post('/withdrawals')
def withdraw(payload: service.Withdrawal, request: Request, response: Response):
    actor = member(request, response)
    return operation(lambda: service.withdraw(actor, payload))


@router.get('/management/{entity_type}')
def records(entity_type: Literal['application', 'withdrawal'], request: Request, response: Response,
            kind: Literal['affiliate', 'tuition', 'exchange'] | None = None,
            status: str | None = Query(None, max_length=30), limit: int = Query(100, ge=1, le=100), offset: int = Query(0, ge=0), opportunity_id: UUID | None = None):
    actor = owner(request, response)
    def execute():
        if opportunity_id and (entity_type != 'application' or kind != 'exchange'):
            from fastapi import HTTPException
            raise HTTPException(422, 'Opportunity filter requires exchange applications')
        items = service.records(actor, 'academy_applications' if entity_type == 'application' else 'academy_withdrawals', True, kind, status, limit, offset, opportunity_id)
        allowed = service.capabilities(actor.tenant_id)
        config = service.get_settings(actor.tenant_id)
        names = {field: config[field] for capability, field in [('tuition', 'support_programme_name'), ('exchange', 'exchange_programme_name')] if allowed[capability] and field in config}
        return {'capabilities': allowed, 'settings': names, 'items': items}
    return operation(execute)


@router.post('/management/{entity_type}/{entity_id}/review')
def review(entity_type: Literal['application', 'withdrawal'], entity_id: UUID, payload: service.Review, request: Request, response: Response):
    actor = owner(request, response)
    def execute():
        result = service.review(actor, entity_type, entity_id, payload)
        record_audit_event(request=request, actor_user_id=actor.user_id, tenant_id=actor.tenant_id,
                           action='academy.' + entity_type + '.' + payload.status, target_type=entity_type, target_id=str(entity_id))
        return result
    return operation(execute)


@router.get('/reports')
def reports(request: Request, response: Response, course_id: UUID | None = None, user_id: int | None = Query(None, ge=1),
            section_id: UUID | None = None, status: str | None = Query(None, max_length=30),
            date_from: str | None = Query(None, max_length=40), date_to: str | None = Query(None, max_length=40), export: bool = False):
    from datetime import datetime
    from fastapi import HTTPException
    actor = owner(request, response)
    for value in (date_from, date_to):
        if value:
            try: datetime.fromisoformat(value.replace('Z', '+00:00'))
            except ValueError as error: raise HTTPException(422, 'Invalid date') from error
    def execute():
        result = service.report(actor, p_course=str(course_id) if course_id else None, p_user=user_id,
                                p_section=str(section_id) if section_id else None, p_status=status,
                                p_from=date_from, p_to=date_to)
        if export:
            return Response(service.csv_export(result), media_type='text/csv', headers={'Content-Disposition': 'attachment; filename="academy-progress.csv"', 'Cache-Control': 'private, no-store'})
        return result
    return operation(execute)


@router.get('/courses/{course_id}/cefr')
def cefr_configuration(course_id: UUID, request: Request, response: Response):
    actor = owner(request, response)
    def execute():
        if not service.settings_available(139):
            from fastapi import HTTPException
            raise HTTPException(503, 'Learning certificate upgrade required')
        return {'items': service.service_supabase.table('elearning_section_certificates').select('*').eq('tenant_id', actor.tenant_id).eq('course_id', str(course_id)).execute().data or []}
    return operation(execute)


@router.put('/courses/{course_id}/cefr')
def configure_cefr(course_id: UUID, payload: service.CEFRConfiguration, request: Request, response: Response):
    actor = owner(request, response)
    return operation(lambda: service.configure_cefr(actor, course_id, payload))


@router.get('/finance/{kind}')
def finance(kind: Literal['referrals', 'rewards', 'transactions'], request: Request, response: Response,
            limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0)):
    actor = owner(request, response)
    def execute():
        service.read_access(actor, kind)
        return service.service_supabase.rpc('academy_owner_finance', {'p_tenant': actor.tenant_id, 'p_admin': actor.user_id,
                                            'p_kind': kind, 'p_limit': limit, 'p_offset': offset}).execute().data
    return operation(execute)


@router.get('/management/members/{user_id}')
def member_profile(user_id: int, request: Request, response: Response):
    actor = owner(request, response)
    def execute():
        service.available(actor, 'wallet')
        result = service.service_supabase.rpc('academy_owner_member_profile', {'p_tenant': actor.tenant_id, 'p_admin': actor.user_id, 'p_user': user_id}).execute().data
        from services.academy_capability_service import permitted_wallet
        allowed = service.capabilities(actor.tenant_id)
        result['wallet'] = permitted_wallet(result['wallet'], allowed)
        if not allowed['tuition'] or not allowed['exchange']:
            kinds = [key for key in ('affiliate', 'tuition', 'exchange') if allowed[key]]
            applications = service.service_supabase.table('academy_applications').select('id').eq('tenant_id', actor.tenant_id).eq('user_id', user_id).in_('kind', kinds).execute().data or []
            ids = {str(row['id']) for row in applications}
            result['history'] = [row for row in result['history'] if row['entity_type'] == 'withdrawal' or str(row['entity_id']) in ids]
        return result
    return operation(execute)
