"""Reviewed tenant access and append-only manual receipts; no provider calls."""
from __future__ import annotations

import calendar
import logging
import os
from datetime import datetime, timezone
from typing import Literal
from uuid import UUID

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, StrictInt, field_validator, model_validator

from database import service_supabase
from services.commercial_catalog import CATALOG_VERSION, get_product
from services.commercial_metrics import record_commercial_metric

logger = logging.getLogger(__name__)
PlanId = Literal['forms', 'website', 'business', 'business_plus']


class CommercialCommand(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    idempotency_key: str = Field(min_length=16, max_length=128, pattern=r'^[A-Za-z0-9_-]+$')
    reason: str = Field(min_length=3, max_length=1000)


class AccessGrant(CommercialCommand):
    plan_id: PlanId
    valid_from: datetime
    valid_until: datetime
    supersedes_period_id: UUID | None = None

    @field_validator('valid_from', 'valid_until')
    @classmethod
    def aware_time(cls, value):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError('A timezone is required')
        return value.astimezone(timezone.utc)

    @model_validator(mode='after')
    def valid_period(self):
        if self.valid_until <= self.valid_from:
            raise ValueError('Paid through must follow valid from')
        return self


class ManualPayment(AccessGrant):
    method: Literal['cash', 'bank_transfer', 'other_manual']
    actual_minor: StrictInt = Field(gt=0, le=1_000_000_000_000)
    currency: Literal['USD'] = 'USD'
    billing_months: StrictInt = Field(default=1, ge=1, le=120)
    paid_at: datetime
    receipt_reference: str = Field(min_length=1, max_length=200)
    override_reason: str | None = Field(default=None, min_length=3, max_length=1000)

    @field_validator('paid_at')
    @classmethod
    def aware_paid_at(cls, value):
        return AccessGrant.aware_time(value)

    @model_validator(mode='after')
    def monthly_period(self):
        month_index = self.valid_from.year * 12 + self.valid_from.month - 1 + self.billing_months
        year, month = divmod(month_index, 12)
        month += 1
        if year > 9999:
            raise ValueError('Billing period is out of range')
        expected_end = self.valid_from.replace(year=year, month=month, day=min(self.valid_from.day, calendar.monthrange(year, month)[1]))
        if self.valid_until != expected_end and not self.override_reason:
            raise ValueError('Nonstandard period requires an explicit override reason; no proration is inferred')
        return self


class PaymentCorrection(CommercialCommand):
    payment_id: UUID
    actual_minor: StrictInt = Field(gt=0, le=1_000_000_000_000)
    paid_at: datetime
    receipt_reference: str = Field(min_length=1, max_length=200)
    override_reason: str | None = Field(default=None, min_length=3, max_length=1000)

    @field_validator('paid_at')
    @classmethod
    def aware_paid_at(cls, value):
        return AccessGrant.aware_time(value)


class AccessRevocation(CommercialCommand):
    period_id: UUID


def _unavailable():
    record_commercial_metric("resolution_failure")
    return HTTPException(status_code=503, detail={'code': 'commercial_access_unavailable', 'message': 'Commercial access could not be verified.'})


def read_commercial_snapshot(tenant_id: int) -> dict | None:
    # Legacy unit fixtures explicitly opt into the new DB contract. Production
    # never uses this fixture branch; isolated application E2E enables lookups.
    if os.getenv('APP_ENV', '').lower() == 'test' and os.getenv('COMMERCIAL_ACCESS_TEST_LOOKUPS', '').lower() not in {'true', '1'}:
        return None
    try:
        data = service_supabase.rpc('resolve_commercial_access', {'p_tenant_id': int(tenant_id)}).execute().data
    except Exception as error:
        if getattr(error, 'code', None) in {'PGRST202', '42883'}:
            try:
                rows = service_supabase.table('application_schema_state').select('schema_version').eq('contract_key', 'core').limit(1).execute().data
                if len(rows or []) == 1 and rows[0]['schema_version'] == 98:
                    return None  # Explicit schema-98 compatibility bridge only.
            except Exception:
                pass
        logger.warning('commercial.snapshot_unavailable', extra={'tenant_id': tenant_id, 'error_type': type(error).__name__})
        raise _unavailable() from None
    if (not isinstance(data, dict) or data.get('tenant_id') != int(tenant_id)
        or type(data.get('revision')) is not int or data['revision'] < 1
        or data.get('review_state') not in {'reviewed', 'review_required'}
        or not isinstance(data.get('addons'), list)):
        raise _unavailable()
    return data


def execute_commercial_command(*, tenant_id: int, actor_user_id: int, aal: str, request_id: str,
                               operation: str, command: CommercialCommand) -> dict:
    expected_models = {'manual_payment': ManualPayment, 'correct_payment': PaymentCorrection,
                       'complimentary': AccessGrant, 'revoke': AccessRevocation, 'review_inactive': CommercialCommand}
    if operation not in expected_models or type(command) is not expected_models[operation] or aal != 'aal2':
        raise HTTPException(status_code=403, detail='Platform administrator AAL2 is required')
    payload = {'request': command.model_dump(mode='json', exclude={'idempotency_key'}), 'quote': {}}
    if isinstance(command, AccessGrant):
        product = get_product(command.plan_id)
        if not product or product['type'] != 'base_plan':
            raise HTTPException(status_code=400, detail='Unknown commercial plan')
        if isinstance(command, ManualPayment):
            expected = product['price_minor'] * command.billing_months
            payload['quote'] = {'expected_minor': expected, 'catalog_version': CATALOG_VERSION}
    try:
        result = service_supabase.rpc('apply_commercial_access_command', {
            'p_tenant_id': tenant_id, 'p_actor_user_id': actor_user_id, 'p_aal': aal,
            'p_operation': operation, 'p_idempotency_key': command.idempotency_key,
            'p_request_id': request_id[:128], 'p_payload': payload,
        }).execute().data
    except Exception as error:
        record_commercial_metric('command_failure')
        code = getattr(error, 'code', None)
        if code == '42501':
            raise HTTPException(status_code=403, detail='Platform administrator AAL2 is required') from None
        if code == 'P0002':
            raise HTTPException(status_code=404, detail='Commercial record was not found') from None
        if code in {'23505', '23P01'}:
            raise HTTPException(status_code=409, detail={'code': 'commercial_command_conflict', 'message': 'The request conflicts with an existing command, correction, or access period.'}) from None
        if code in {'22023', '23514', '23502', '22P02', '22007', '22008'}:
            raise HTTPException(status_code=422, detail='Commercial command validation failed') from None
        logger.warning('commercial.command_unavailable', extra={'tenant_id': tenant_id, 'operation': operation, 'error_type': type(error).__name__})
        raise _unavailable() from None
    if not isinstance(result, dict) or result.get('tenant_id') != tenant_id or result.get('operation') != operation:
        raise _unavailable()
    record_commercial_metric('command_success')
    return result
