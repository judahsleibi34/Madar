from uuid import UUID
from fastapi import APIRouter, Request, Response, Query
from services.tenant_service import require_active_tenant_member
from services import elearning_player_service as service
from services.audit_service import record_audit_event
from routes.elearning_structure_routes import operation

router = APIRouter(prefix="/elearning/my-learning", tags=["My Learning"])


def member(request, response):
    response.headers["Cache-Control"] = "private, no-store"
    return require_active_tenant_member(request, response, allow_admin_account_access=False, allow_learner=True)


@router.get("")
def my_learning(request: Request, response: Response, limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0)):
    actor = member(request, response)
    return operation(lambda: service.my_learning(actor, limit, offset))


@router.get("/courses/{course_id}")
def course(course_id: UUID, request: Request, response: Response):
    actor = member(request, response)
    return operation(lambda: service.course(actor, course_id))


@router.get("/courses/{course_id}/lessons/{lesson_id}")
def lesson(course_id: UUID, lesson_id: UUID, request: Request, response: Response):
    actor = member(request, response)
    return operation(lambda: service.course(actor, course_id, lesson_id))


@router.post("/courses/{course_id}/lessons/{lesson_id}/completion")
def complete(course_id: UUID, lesson_id: UUID, request: Request, response: Response):
    actor = member(request, response)
    def execute():
        snapshot = service.course(actor, course_id, lesson_id, complete=True)
        record_audit_event(request=request, actor_user_id=actor.user_id, tenant_id=actor.tenant_id,
                           action="elearning.learner.completed", target_type="elearning_lesson", target_id=str(lesson_id))
        return snapshot
    return operation(execute)
