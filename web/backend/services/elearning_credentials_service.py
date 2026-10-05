"""Formal-completion credentials; immutable issuance is centralized in the DB hook."""
import base64
import io
import re
from uuid import UUID
from PIL import Image
from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, StrictBool, field_validator
from postgrest.exceptions import APIError
from database import service_supabase
from services.elearning_settings_service import settings_available, require_owned_image, get_settings
from services.upload_config import get_public_uploads_dir
from services.frontend_url import resolve_frontend_url_for_request

VARIABLES = {'learner_name', 'course_name', 'completion_date', 'issue_date', 'issuer_name', 'credential_id'}
PLACEHOLDER = re.compile(r'\{\{\s*([^{}]+?)\s*\}\}')


def validate_text(value):
    for match in PLACEHOLDER.finditer(value):
        if match[1].strip() not in VARIABLES:
            raise ValueError('Unknown certificate placeholder: ' + match[1].strip())
    rest = PLACEHOLDER.sub('', value)
    if '{{' in rest or '}}' in rest:
        raise ValueError('Invalid certificate placeholder')
    return value


class TemplateDesign(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    name: str = Field(min_length=1, max_length=120)
    title: str = Field(min_length=1, max_length=200)
    subtitle: str = Field(default='', max_length=200)
    body: str = Field(default='', max_length=1200)
    issuer_name: str = Field(min_length=1, max_length=200)
    signer_name: str = Field(default='', max_length=120)
    signer_title: str = Field(default='', max_length=120)
    logo_url: str = Field(default='', max_length=2048)
    signature_url: str = Field(default='', max_length=2048)
    _text = field_validator('name', 'title', 'subtitle', 'body', 'issuer_name', 'signer_name', 'signer_title')(validate_text)


class TemplatePayload(BaseModel):
    model_config = ConfigDict(extra='forbid')
    design: TemplateDesign
    expected_revision: int = Field(default=1, ge=1, strict=True)
    status: str = Field(default='active', pattern='^(active|archived)$')


class Configuration(BaseModel):
    model_config = ConfigDict(extra='forbid')
    enabled: StrictBool = False
    template_id: UUID | None = None
    title_override: str = Field(default='', max_length=200)
    issuer_override: str = Field(default='', max_length=200)
    _text = field_validator('title_override', 'issuer_override')(validate_text)


class Confirmation(BaseModel):
    model_config = ConfigDict(extra='forbid')
    confirmed: StrictBool


class Revocation(Confirmation):
    reason: str = Field(min_length=1, max_length=1000)


def available():
    if not settings_available(129):
        raise HTTPException(503, 'Certificates require a database upgrade')


def call(name, **args):
    available()
    try:
        return service_supabase.rpc(name, args).execute().data
    except APIError as error:
        code = {'P0002': 404, '42501': 403, '22023': 400, '23503': 400, '23514': 400, '40001': 409}.get(error.code)
        if code:
            raise HTTPException(code, error.message) from error
        raise


def admin(actor, course=None, action='list', identifier=None, payload=None):
    result = call('manage_elearning_certificates', p_tenant_id=actor.tenant_id, p_user_id=actor.user_id,
                p_course_id=str(course) if course else None, p_action=action,
                p_id=str(identifier) if identifier else None, p_payload=payload or {})
    if 'templates' in result:
        settings = get_settings(actor.tenant_id)
        result['branding'] = {'issuer_name': settings.get('primary_display_name', ''),
                              'logo_url': settings.get('logo_url', '') if settings.get('logo_url', '').startswith('/uploads/') else ''}
    return result


def image_snapshot(tenant, url):
    if not url:
        return ''
    # Only local, owned, registered images. Never fetch a user-supplied remote URL.
    if not url.startswith('/uploads/'):
        raise HTTPException(400, 'Select a managed tenant image')
    require_owned_image(tenant, url)
    root = get_public_uploads_dir()
    path = (root / url.removeprefix('/uploads/')).resolve()
    if not path.is_relative_to(root) or not path.is_file() or path.stat().st_size > 5_000_000:
        raise HTTPException(400, 'Certificate image is unavailable or too large')
    with Image.open(path) as source:
        if source.width * source.height > 20_000_000:
            raise HTTPException(400, 'Certificate image is too large')
        source.thumbnail((1000, 500))
        target = io.BytesIO()
        source.convert('RGBA').save(target, format='PNG')
    return base64.b64encode(target.getvalue()).decode('ascii')


def save_template(actor, payload, identifier=None):
    data = payload.model_dump(mode='json')
    design = data['design']
    # Reuse the tenant's configured learning logo when no explicit override exists.
    if not design['logo_url']:
        logo = get_settings(actor.tenant_id).get('logo_url', '')
        if logo.startswith('/uploads/'):
            design['logo_url'] = logo
    for kind in ('logo', 'signature'):
        design[kind + '_image'] = image_snapshot(actor.tenant_id, design[kind + '_url'])
    return admin(actor, action='template', identifier=identifier, payload=data)


def mine(actor, identifier=None):
    return call('get_elearning_my_certificates', p_tenant_id=actor.tenant_id, p_user_id=actor.user_id,
                p_id=str(identifier) if identifier else None)


def verification(token):
    # Uniform null response for malformed and unknown identifiers.
    if not re.fullmatch(r'[a-f0-9]{64}', token):
        return None
    data = call('verify_elearning_credential', p_token=token)
    if data:
        variables = {'learner_name': data['learner_name'], 'course_name': data['course_name'],
                     'completion_date': data['completed_at'][:10], 'issue_date': data['issued_at'][:10],
                     'issuer_name': data['issuer_name'], 'credential_id': data['credential_number']}
        data['issuer_name'] = PLACEHOLDER.sub(lambda match: variables[match[1].strip()], data['issuer_name'])
    return data


def presentation(row, origin=None):
    snapshot = row['snapshot']
    design = snapshot['design'].copy()
    variables = dict(learner_name=snapshot['learner_name'], course_name=snapshot['course_name'],
                     completion_date=row['completed_at'][:10], issue_date=row['issued_at'][:10],
                     issuer_name=design['issuer_name'], credential_id=row['credential_number'])
    for key in ('title', 'subtitle', 'body', 'issuer_name', 'signer_name', 'signer_title'):
        design[key] = PLACEHOLDER.sub(lambda match: variables[match[1].strip()], design.get(key, ''))
    return {**variables, 'credential_number': row['credential_number'], 'status': row['status'],
            'completed_at': row['completed_at'], 'issued_at': row['issued_at'], 'design': design,
            'verification_url': resolve_frontend_url_for_request(origin) + '/verify/credential/' + row['verification_token']}
