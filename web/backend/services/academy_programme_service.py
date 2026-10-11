"""Academy programmes reuse learning identities, verified sales and reward history."""
from decimal import Decimal
from typing import Literal
from uuid import UUID
from fastapi import HTTPException
from postgrest.exceptions import APIError
from pydantic import BaseModel, ConfigDict, Field, StrictBool, field_validator
from database import service_supabase
from services.academy_capability_service import require_capability, capabilities, permitted_settings, permitted_wallet
from services.elearning_settings_service import settings_available, get_settings


class Payload(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)


class Application(Payload):
    kind: Literal['affiliate', 'tuition', 'exchange']
    details: dict[str, str | bool] = Field(max_length=20)
    idempotency_key: UUID

    @field_validator('details')
    @classmethod
    def details_bound(cls, value):
        if any(len(str(item)) > 4000 for item in value.values()):
            raise ValueError('Application field too long')
        if value.get('terms_accepted') is not True:
            raise ValueError('Programme terms must be accepted')
        return value


class Withdrawal(Payload):
    amount: Decimal = Field(gt=0, max_digits=14, decimal_places=2)
    payment_method: str = Field(min_length=1, max_length=120)
    payment_information: str = Field(min_length=1, max_length=4000)
    ownership_confirmed: StrictBool
    idempotency_key: UUID


class Review(Payload):
    status: Literal['under_review', 'approved', 'not_approved', 'suspended', 'processing', 'paid', 'rejected']
    revision: int = Field(ge=1, strict=True)
    note: str = Field(min_length=1, max_length=4000)


def available(actor, capability=None):
    if not settings_available(139):
        raise HTTPException(503, detail={'code': 'academy_programmes_upgrade_required'})
    if capability: require_capability(actor.tenant_id, capability)
    if not get_settings(actor.tenant_id)['programmes_enabled']:
        raise HTTPException(403, detail={'code': 'academy_programmes_disabled'})


def programme_rpc(name, actor, **args):
    available(actor)
    try:
        return service_supabase.rpc(name, {'p_tenant': actor.tenant_id, 'p_user': actor.user_id, **args}).execute().data
    except APIError as error:
        status = {'42501': 403, '22023': 422, '23505': 409, '40001': 409, 'P0002': 404}.get(error.code)
        if status:
            raise HTTPException(status, detail={'code': 'academy_workflow_rejected', 'message': 'The request is unavailable, invalid, or has changed. Refresh and try again.'}) from error
        raise


def records(actor, table, admin=False, kind=None, status=None, limit=100, offset=0, opportunity_id=None):
    if table == 'academy_applications' and kind is None:
        for module in ('affiliate', 'tuition', 'exchange'): available(actor, module)
    else: available(actor, kind or 'withdrawal')
    if admin and actor.role not in {'owner', 'admin'}:
        raise HTTPException(403, 'Owner or admin access required')
    query = service_supabase.table(table).select('*').eq('tenant_id', actor.tenant_id)
    if not admin: query = query.eq('user_id', actor.user_id)
    if kind: query = query.eq('kind', kind)
    if opportunity_id: query = query.eq('opportunity_id', str(opportunity_id))
    if status: query = query.eq('status', status)
    return query.order('created_at', desc=True).range(offset, offset + limit - 1).execute().data or []


def account(actor):
    available(actor)
    grants = capabilities(actor.tenant_id)
    result = {'capabilities': grants, 'settings': permitted_settings(actor.tenant_id, get_settings(actor.tenant_id), grants), 'wallet': None,
              'applications': [], 'withdrawals': []}
    if grants['wallet']: result['wallet'] = permitted_wallet(programme_rpc('academy_wallet', actor), grants)
    for kind in ('affiliate', 'tuition', 'exchange'):
        if grants[kind]: result['applications'].extend(records(actor, 'academy_applications', kind=kind))
    if grants['withdrawal']: result['withdrawals'] = records(actor, 'academy_withdrawals')
    if not any(grants[kind] for kind in ('affiliate', 'tuition', 'exchange', 'wallet')):
        require_capability(actor.tenant_id, 'wallet')
    # Support/exchange eligibility is computed by the same SQL projection, even
    # when the member has no commerce wallet entitlement. Do not disclose money.
    if result['wallet'] is None:
        values = service_supabase.rpc('academy_wallet', {'p_tenant': actor.tenant_id, 'p_user': actor.user_id}).execute().data
        visible = permitted_wallet(values, grants)
        result['eligibility'] = {key: visible[key] for key in ('tuition_eligible', 'exchange_eligible', 'verified_sales', 'threshold', 'remaining_sales') if key in visible and (key != 'verified_sales' or grants['tuition'])}
    return result


def submit(actor, payload):
    available(actor, payload.kind)
    if payload.kind == 'exchange':
        historical = service_supabase.table('academy_applications').select('id').eq('tenant_id',actor.tenant_id).eq('user_id',actor.user_id).eq('kind','exchange').eq('idempotency_key',str(payload.idempotency_key)).limit(1).execute().data or []
        if not historical:
            raise HTTPException(409,detail={'code':'exchange_use_learning_forms'})
    return {'id': programme_rpc('academy_submit_application', actor, p_kind=payload.kind, p_details=payload.details, p_key=str(payload.idempotency_key))}


def withdraw(actor, payload):
    available(actor, 'withdrawal')
    return {'id': programme_rpc('academy_request_withdrawal', actor, p_amount=str(payload.amount), p_method=payload.payment_method,
                      p_information=payload.payment_information, p_confirm=payload.ownership_confirmed, p_key=str(payload.idempotency_key))}


def review(actor, entity_type, entity_id, payload):
    available(actor)
    if actor.role not in {'owner', 'admin'}: raise HTTPException(403, 'Owner or admin access required')
    table = 'academy_withdrawals' if entity_type == 'withdrawal' else 'academy_applications'
    rows = service_supabase.table(table).select('kind' if entity_type == 'application' else 'id').eq('tenant_id', actor.tenant_id).eq('id', str(entity_id)).limit(1).execute().data or []
    if not rows: raise HTTPException(404, 'Request not found')
    require_capability(actor.tenant_id, rows[0]['kind'] if entity_type == 'application' else 'withdrawal')
    try:
        service_supabase.rpc('academy_review', {'p_tenant': actor.tenant_id, 'p_admin': actor.user_id,
                            'p_type': entity_type, 'p_id': str(entity_id), 'p_status': payload.status,
                            'p_revision': payload.revision, 'p_note': payload.note}).execute()
    except APIError as error:
        status = {'42501': 403, '22023': 422, '40001': 409, 'P0002': 404}.get(error.code)
        if status: raise HTTPException(status, detail={'code': 'academy_review_rejected'}) from error
        raise
    return {'success': True}


def report(actor, **filters):
    require_capability(actor.tenant_id, 'reports')
    if not settings_available(139): raise HTTPException(503, detail={'code': 'academy_programmes_upgrade_required'})
    if actor.role not in {'owner', 'admin'}: raise HTTPException(403, 'Owner or admin access required')
    result = service_supabase.rpc('academy_owner_report', {'p_tenant': actor.tenant_id, 'p_admin': actor.user_id, **filters}).execute().data
    grants = capabilities(actor.tenant_id)
    if not grants['rewards']: result['rewards'] = []
    if 'applications' in result: result['applications'] = [row for row in result['applications'] if grants.get(row['kind'], False)]
    return result


def csv_export(result):
    import csv
    import io
    output = io.StringIO()
    columns = ['course_id', 'course_name', 'user_id', 'name', 'email', 'enrollment_status', 'progress_status', 'completed_lessons', 'total_lessons', 'progress_percent', 'enrolled_at']
    writer = csv.DictWriter(output, fieldnames=columns, extrasaction='ignore')
    writer.writeheader()
    for row in result['enrollments']:
        # Spreadsheet formula injection, including leading whitespace/control.
        writer.writerow({key: "'" + value if isinstance(value, str) and value.lstrip().startswith(('=', '+', '-', '@')) else value for key, value in row.items()})
    return output.getvalue()


class CEFRConfiguration(Payload):
    section_id: UUID
    level: Literal['A1', 'A2', 'B1', 'B2', 'C1']
    template_id: UUID
    enabled: StrictBool = True


def configure_cefr(actor, course_id, payload):
    if not settings_available(139): raise HTTPException(503, 'Learning certificate upgrade required')
    if actor.role not in {'owner', 'admin'}: raise HTTPException(403, 'Owner or admin access required')
    try:
        service_supabase.rpc('configure_elearning_cefr', {'p_tenant': actor.tenant_id, 'p_admin': actor.user_id,
                             'p_course': str(course_id), 'p_section': str(payload.section_id), 'p_level': payload.level,
                             'p_template': str(payload.template_id), 'p_enabled': payload.enabled}).execute()
    except APIError as error:
        if error.code in {'22023', '23505', '23503', '23514', '42501'}:
            raise HTTPException(422 if error.code != '42501' else 403, detail={'code': 'cefr_configuration_rejected'}) from error
        raise
    return {'success': True}
