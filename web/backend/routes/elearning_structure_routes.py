import logging
from uuid import UUID
from fastapi import APIRouter, HTTPException, Request, Response
from services.elearning_access_service import require_elearning_access
from services.audit_service import record_audit_event
from services import elearning_structure_service as service

router = APIRouter(prefix="/elearning/courses", tags=["E-Learning"])
logger = logging.getLogger(__name__)


def operation(callback):
    try: return callback()
    except HTTPException: raise
    except Exception:
        logger.exception("elearning.structure.operation_failed")
        raise HTTPException(503, "Learning structure is temporarily unavailable")


@router.get("/{course_id}/structure")
def get_structure(course_id: UUID, request: Request, response: Response):
    member = require_elearning_access(request, response, "elearning.structure.view")
    return operation(lambda: service.get_structure(member.tenant_id, course_id))


@router.post("/{course_id}/structure/commands")
def execute_command(course_id: UUID, payload: service.StructureCommand, request: Request, response: Response):
    member = require_elearning_access(request, response, "elearning.structure.manage")
    def execute():
        structure = service.execute_command(member.tenant_id, course_id, member.user_id, payload)
        record_audit_event(request=request, actor_user_id=member.user_id, tenant_id=member.tenant_id,
                           action=f"elearning.structure.{payload.action}", target_type="elearning_course", target_id=str(course_id))
        return structure
    return operation(execute)


@router.get("/{course_id}/lessons/{lesson_id}")
def get_lesson(course_id: UUID, lesson_id: UUID, request: Request, response: Response):
    member = require_elearning_access(request, response, "elearning.structure.view")
    return operation(lambda: service.get_lesson(member.tenant_id, course_id, lesson_id))
