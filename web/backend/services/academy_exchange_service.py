"""Opportunity rules and decisions; questions, answers and files remain Forms-owned."""
from typing import Literal
from fastapi import HTTPException
from pydantic import Field
from database import service_supabase
from services.academy_programme_service import Payload, available
from services.elearning_settings_service import settings_available
from services import elearning_forms_service as forms


def gate(actor, capability='forms'):
    if not settings_available(142):
        raise HTTPException(503, 'Exchange Forms require database schema142')
    available(actor, 'exchange')
    forms.gate(actor.tenant_id, capability)


def opportunity(actor, identifier):
    gate(actor)
    rows = service_supabase.table('academy_exchange_opportunities').select('*').eq('tenant_id', actor.tenant_id).eq('id', str(identifier)).limit(1).execute().data or []
    if not rows or not rows[0].get('application_form_id'):
        raise HTTPException(404, 'Forms-backed opportunity not found')
    return rows[0]


def detail(actor, identifier):
    row = opportunity(actor, identifier)
    # Domain availability is authoritative in SQL, including enrollment eligibility.
    responses = service_supabase.table('elearning_form_responses').select('id,submitted_at').eq('tenant_id', actor.tenant_id).eq('user_id', actor.user_id).eq('opportunity_id', str(identifier)).limit(1).execute().data or []
    application = None
    if responses:
        application = responses[0]
        decisions = service_supabase.table('academy_exchange_decisions').select('status,reviewed_at').eq('tenant_id', actor.tenant_id).eq('response_id', application['id']).limit(1).execute().data or []
        application['decision'] = decisions[0] if decisions else None
    # Do not use the bounded list as authority for detail: ask a guarded RPC.
    form = forms.definition(actor.tenant_id, row['application_form_id'])
    can_apply = row['status'] == 'published' and form['status'] == 'active'
    if can_apply:
        from datetime import datetime, timezone
        if row.get('deadline') and datetime.fromisoformat(row['deadline'].replace('Z', '+00:00')) <= datetime.now(timezone.utc):
            can_apply = False
        can_apply = bool(forms.rpc('exchange_opportunity_available', {'p_tenant': actor.tenant_id, 'p_user': actor.user_id, 'p_opportunity': str(identifier)}))
    if not can_apply and not application:
        raise HTTPException(403, 'Opportunity unavailable or learner ineligible')
    if can_apply and not application:
        forms.public_access(actor.tenant_id, form, actor)
    return {'opportunity': {k: v for k, v in row.items() if k not in {'tenant_id', 'created_by'}}, 'form': {'id': form['id'], 'version': form['version'], 'schema': form['schema']} if can_apply and not application else None, 'application': application, 'can_apply': can_apply and not application}


class Decision(Payload):
    status: Literal['under_review', 'approved', 'not_approved']
    revision: int = Field(ge=1, strict=True)
    note: str = Field(min_length=1, max_length=4000)


def review(actor, identifier, payload):
    gate(actor, 'response_management')
    return forms.rpc('review_exchange_response', {'p_tenant': actor.tenant_id, 'p_admin': actor.user_id, 'p_response': str(identifier), 'p_revision': payload.revision, 'p_status': payload.status, 'p_note': payload.note})


def review_context(actor, response):
    gate(actor, 'response_management')
    decision = service_supabase.table('academy_exchange_decisions').select('*').eq('tenant_id', actor.tenant_id).eq('response_id', response['id']).limit(1).execute().data or []
    row = opportunity(actor, response['opportunity_id'])
    history = service_supabase.table('academy_exchange_decision_history').select('old_status,new_status,actor_id,note,created_at').eq('tenant_id', actor.tenant_id).eq('response_id', response['id']).order('created_at').execute().data or []
    return {'opportunity_id': row['id'], 'title': row['title'], 'decision': decision[0] if decision else None, 'history': history}
