from uuid import UUID
from fastapi import APIRouter, Request, Response
from routes.elearning_assessments_routes import owner
from routes.elearning_player_routes import member
from routes.elearning_structure_routes import operation
from services import elearning_credentials_service as service
from services.credential_pdf_service import render_certificate
from services.rate_limit_service import enforce_public_rate_limit

router = APIRouter(tags=['E-Learning Credentials'])
admin_path = '/elearning/courses/{course_id}/certificate'
learner_path = '/elearning/my-certificates'


@router.get('/elearning/certificate-templates')
def templates(request: Request, response: Response):
    actor = owner(request, response)
    return operation(lambda: service.admin(actor))


@router.post('/elearning/certificate-templates')
def create(payload: service.TemplatePayload, request: Request, response: Response):
    actor = owner(request, response)
    return operation(lambda: service.save_template(actor, payload))


@router.put('/elearning/certificate-templates/{template_id}')
def edit(template_id: UUID, payload: service.TemplatePayload, request: Request, response: Response):
    actor = owner(request, response)
    return operation(lambda: service.save_template(actor, payload, template_id))


@router.get(admin_path)
def configuration(course_id: UUID, request: Request, response: Response):
    actor = owner(request, response)
    return operation(lambda: service.admin(actor, course_id))


@router.put(admin_path)
def configure(course_id: UUID, payload: service.Configuration, request: Request, response: Response):
    actor = owner(request, response)
    return operation(lambda: service.admin(actor, course_id, 'configure', payload=payload.model_dump(mode='json')))


@router.post(admin_path + '/backfill')
def backfill(course_id: UUID, payload: service.Confirmation, request: Request, response: Response):
    actor = owner(request, response)
    return operation(lambda: service.admin(actor, course_id, 'backfill', payload=payload.model_dump()))


@router.post(admin_path + '/credentials/{credential_id}/revocation')
def revoke(course_id: UUID, credential_id: UUID, payload: service.Revocation, request: Request, response: Response):
    actor = owner(request, response)
    return operation(lambda: service.admin(actor, course_id, 'revoke', credential_id, payload.model_dump()))


def document(row, request, pdf):
    data = service.presentation(row, request.headers.get('origin'))
    if pdf:
        return Response(render_certificate(data), media_type='application/pdf', headers={
            'Content-Disposition': f'attachment; filename="{data["credential_number"]}.pdf"',
            'Cache-Control': 'private, no-store', 'X-Content-Type-Options': 'nosniff'})
    return data


@router.get(admin_path + '/credentials/{credential_id}')
def admin_view(course_id: UUID, credential_id: UUID, request: Request, response: Response, pdf: bool = False):
    actor = owner(request, response)
    return operation(lambda: document(service.admin(actor, course_id, 'view', credential_id), request, pdf))


@router.get(learner_path)
def mine(request: Request, response: Response):
    actor = member(request, response)
    return operation(lambda: service.mine(actor))


@router.get(learner_path + '/{credential_id}')
def learner_view(credential_id: UUID, request: Request, response: Response, pdf: bool = False):
    actor = member(request, response)
    return operation(lambda: document(service.mine(actor, credential_id), request, pdf))


@router.get('/verify/credential/{token}')
def verify(token: str, request: Request, response: Response):
    response.headers['Cache-Control'] = 'no-store'
    enforce_public_rate_limit(request, 'credential_verification')
    return operation(lambda: {'credential': service.verification(token)})
