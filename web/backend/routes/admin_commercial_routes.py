"""Platform-only commercial review and append-only manual activation."""
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Path, Query, Request, Response

from database import service_supabase
from services.auth_service import get_current_aal, require_system_admin
from services.commercial_access_service import (
    AccessGrant, AccessRevocation, CommercialCommand, ManualPayment, PaymentCorrection,
    execute_commercial_command, read_commercial_snapshot,
)
from services.entitlement_service import get_tenant_entitlements
from services.rate_limit_service import enforce_rate_limit

router = APIRouter(prefix='/admin/commercial', tags=['Admin Commercial Access'])


def _admin(request, response, *, tenant_id=None, mutation=False):
    _, user = require_system_admin(request, response, require_aal2=True)
    response.headers['Cache-Control'] = 'private, no-store'
    if mutation:
        enforce_rate_limit(request, 'commercial_admin_user', identifier=str(user['id']), limit=30, window_seconds=60, include_client_ip=False)
        enforce_rate_limit(request, 'commercial_admin_tenant', identifier=str(tenant_id), limit=20, window_seconds=60, include_client_ip=False)
    return user


def _apply(operation, command, tenant_id, request, response):
    user = _admin(request, response, tenant_id=tenant_id, mutation=True)
    result = execute_commercial_command(tenant_id=tenant_id, actor_user_id=user['id'],
        aal=get_current_aal(request).get('current_level'),
        request_id=str(getattr(request.state, 'request_id', None) or uuid4()),
        operation=operation, command=command)
    return {'success': True, 'result': result}


@router.get('/review')
def review_queue(request: Request, response: Response, offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100)):
    _admin(request, response)
    result = service_supabase.table('tenant_commercial_state').select('tenant_id,revision,review_state,tenants!inner(lifecycle_state)', count='exact').eq('review_state', 'review_required').eq('tenants.lifecycle_state', 'active').order('tenant_id').range(offset, offset+limit-1).execute()
    return {'success': True, 'tenants': [{'tenant_id': r['tenant_id'], 'revision': r['revision'], 'review_state': r['review_state']} for r in result.data or []], 'total': result.count}


@router.get('/tenants/{tenant_id}')
def commercial_history(request: Request, response: Response, tenant_id: int = Path(gt=0), offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100)):
    _admin(request, response)
    tenants = service_supabase.table('tenants').select('tenant_id').eq('tenant_id', tenant_id).limit(1).execute().data
    if not tenants:
        raise HTTPException(status_code=404, detail='Tenant was not found')
    snapshot = read_commercial_snapshot(tenant_id)
    if snapshot is None:
        raise HTTPException(status_code=503, detail='Commercial access migration is not available yet')
    history = {}
    has_more = False
    for key, table in [('payments','commercial_manual_payments'), ('periods','commercial_access_periods'), ('events','commercial_access_events')]:
        columns = '*' if key != 'events' else 'id,tenant_id,operation,actor_user_id,aal,request_id,revision,result,created_at'
        history[key] = service_supabase.table(table).select(columns).eq('tenant_id', tenant_id).order('created_at', desc=True).order('id').range(offset, offset+limit).execute().data or []
        has_more = has_more or len(history[key]) > limit
        history[key] = history[key][:limit]
    return {'success': True, 'commercial': snapshot, 'entitlements': get_tenant_entitlements(tenant_id, preview=True), 'history': history, 'history_limit': limit, 'history_offset': offset, 'history_has_more': has_more}


@router.post('/tenants/{tenant_id}/manual-payments')
def record_manual_payment(command: ManualPayment, request: Request, response: Response, tenant_id: int = Path(gt=0)):
    return _apply('manual_payment', command, tenant_id, request, response)


@router.post('/tenants/{tenant_id}/payment-corrections')
def correct_manual_payment(command: PaymentCorrection, request: Request, response: Response, tenant_id: int = Path(gt=0)):
    return _apply('correct_payment', command, tenant_id, request, response)


@router.post('/tenants/{tenant_id}/complimentary-grants')
def grant_complimentary(command: AccessGrant, request: Request, response: Response, tenant_id: int = Path(gt=0)):
    return _apply('complimentary', command, tenant_id, request, response)


@router.post('/tenants/{tenant_id}/revocations')
def revoke_access(command: AccessRevocation, request: Request, response: Response, tenant_id: int = Path(gt=0)):
    return _apply('revoke', command, tenant_id, request, response)


@router.post('/tenants/{tenant_id}/review-inactive')
def review_inactive(command: CommercialCommand, request: Request, response: Response, tenant_id: int = Path(gt=0)):
    return _apply('review_inactive', command, tenant_id, request, response)
