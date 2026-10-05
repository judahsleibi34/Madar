import logging
from uuid import UUID
from fastapi import APIRouter, File, HTTPException, Query, Request, Response, UploadFile
from services.elearning_access_service import require_elearning_access
from services.audit_service import record_audit_event
from services import elearning_courses_service as service

router = APIRouter(prefix="/elearning/courses", tags=["E-Learning"])
logger = logging.getLogger(__name__)


def operation(action, callback):
    try:
        return callback()
    except HTTPException:
        raise
    except Exception:
        logger.exception("elearning.courses.%s_failed", action)
        raise HTTPException(status_code=503, detail="Courses are temporarily unavailable")


def audit(request, context, action, course):
    record_audit_event(request=request, actor_user_id=context.user_id, tenant_id=context.tenant_id,
                       action=f"elearning.course_{action}", target_type="elearning_course", target_id=course["id"])


@router.get("")
def list_courses(request: Request, response: Response, limit: int = Query(default=50, ge=1, le=100), offset: int = Query(default=0, ge=0)):
    context = require_elearning_access(request, response, "elearning.courses.view")
    def read():
        available = service.courses_available()
        return {"available": available, **(service.list_courses(context.tenant_id, limit, offset) if available else {"courses": [], "has_more": False})}
    return operation("list", read)


@router.post("")
def create_course(payload: service.CoursePayload, request: Request, response: Response):
    context = require_elearning_access(request, response, "elearning.courses.manage")
    def create():
        service.require_courses_available()
        course = service.create_course(context.tenant_id, context.user_id, payload)
        audit(request, context, "created", course)
        return {"course": course}
    return operation("create", create)


@router.post("/cover/upload")
async def upload_cover(request: Request, response: Response, file: UploadFile = File(...)):
    from routes.builder_routes import upload_builder_asset
    request.scope["madar_asset_usage"] = "elearning_course_cover"
    return await upload_builder_asset(request=request, response=response, file=file)


@router.get("/{course_id}")
def get_course(course_id: UUID, request: Request, response: Response):
    context = require_elearning_access(request, response, "elearning.courses.view")
    def read():
        service.require_courses_available()
        return {"course": service.get_course(context.tenant_id, course_id)}
    return operation("read", read)


@router.put("/{course_id}")
def update_course(course_id: UUID, payload: service.CourseUpdate, request: Request, response: Response):
    context = require_elearning_access(request, response, "elearning.courses.manage")
    def update():
        service.require_courses_available()
        course = service.update_course(context.tenant_id, course_id, payload)
        audit(request, context, "updated", course)
        return {"course": course}
    return operation("update", update)


@router.post("/{course_id}/duplicate")
def duplicate_course(course_id: UUID, payload: service.CourseCommand, request: Request, response: Response):
    context = require_elearning_access(request, response, "elearning.courses.manage")
    def duplicate():
        service.require_courses_available()
        course = service.duplicate_course(context.tenant_id, context.user_id, course_id, payload.expected_revision)
        audit(request, context, "duplicated", course)
        return {"course": course}
    return operation("duplicate", duplicate)


@router.post("/{course_id}/archive")
def archive_course(course_id: UUID, payload: service.CourseCommand, request: Request, response: Response):
    context = require_elearning_access(request, response, "elearning.courses.manage")
    def archive():
        service.require_courses_available()
        course = service.archive_course(context.tenant_id, course_id, payload.expected_revision)
        audit(request, context, "archived", course)
        return {"course": course}
    return operation("archive", archive)


@router.delete("/{course_id}")
def delete_course(course_id: UUID, payload: service.CourseDelete, request: Request, response: Response):
    context = require_elearning_access(request, response, "elearning.courses.manage")
    def delete():
        result = service.delete_course(context.tenant_id, context.user_id, course_id, payload)
        audit(request, context, "deleted", result)
        return result
    return operation("delete", delete)
