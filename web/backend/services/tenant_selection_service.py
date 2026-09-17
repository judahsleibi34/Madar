"""Request-scoped tenant selection. A browser supplies a selector, never authority."""
import logging

from fastapi import HTTPException

from database import service_supabase
from services.tenant_lifecycle_service import tenant_is_active

logger = logging.getLogger(__name__)
TENANT_HEADER = 'X-Madar-Tenant-ID'


def select_request_tenant(request, user):
    selected = request.headers.get(TENANT_HEADER)
    if selected is None:
        return user
    # Platform and delegated-admin sessions retain their separately governed
    # account context. Tenant selection cannot change an admin's privileges.
    if str(user.get('user_type') or '').strip().lower() == 'admin':
        return user
    if not selected.isascii() or not selected.isdecimal() or not 0 < int(selected) <= 2147483647:
        raise HTTPException(status_code=400, detail='Invalid workspace selector')
    tenant_id = int(selected)
    if not user.get('id') or not user.get('auth_id'):
        raise HTTPException(status_code=403, detail='Active workspace membership required')
    try:
        rows = service_supabase.table('tenant_memberships').select('tenant_id,user_id,auth_id,role,status').eq('tenant_id', tenant_id).eq('user_id', user['id']).eq('auth_id', str(user['auth_id'])).eq('status', 'active').limit(2).execute().data or []
    except Exception as error:
        logger.warning('tenant.selection_unavailable', extra={'error_type': type(error).__name__})
        raise HTTPException(status_code=503, detail='Workspace membership could not be verified') from None
    if len(rows) != 1 or rows[0].get('tenant_id') != tenant_id or rows[0].get('user_id') != user['id'] or str(rows[0].get('auth_id')) != str(user['auth_id']) or rows[0].get('status') != 'active' or rows[0].get('role') not in {'owner', 'admin', 'member'} or not tenant_is_active(tenant_id):
        raise HTTPException(status_code=403, detail='Active workspace membership required')
    return {**user, 'tenant_id': tenant_id}


def list_user_tenants(user):
    try:
        rows = service_supabase.table('tenant_memberships').select('tenant_id,role,status,tenants!inner(tenant_id,brand_name,lifecycle_state)').eq('user_id', user['id']).eq('auth_id', str(user['auth_id'])).eq('status', 'active').eq('tenants.lifecycle_state', 'active').order('tenant_id').limit(1001).execute().data or []
    except Exception as error:
        logger.warning('tenant.list_unavailable', extra={'error_type': type(error).__name__})
        raise HTTPException(status_code=503, detail='Workspaces could not be verified') from None
    if len(rows)>1000:
        raise HTTPException(status_code=503, detail='Workspace list requires administrative review')
    return [{'tenant_id': row['tenant_id'], 'name': row['tenants']['brand_name'], 'role': row['role']} for row in rows if row['role'] in {'owner','admin','member'} and row['tenants']['tenant_id']==row['tenant_id']]
