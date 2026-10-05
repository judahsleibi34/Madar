from uuid import UUID
from fastapi import APIRouter, Request, Response, Query
from services import elearning_participation_service as service
from services.elearning_access_service import require_elearning_access
from services.audit_service import record_audit_event
from routes.elearning_structure_routes import operation

router = APIRouter(prefix="/elearning", tags=["E-Learning"])


def mutate(request, member, action, target_id, callback):
    def execute():
        result = callback()
        record_audit_event(request=request, actor_user_id=member.user_id, tenant_id=member.tenant_id, action=f"elearning.participation.{action}", target_type="elearning", target_id=str(target_id))
        return result
    return operation(execute)


@router.get("/learners")
def list_learners(request: Request, response: Response, limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0)):
    member = require_elearning_access(request, response, "elearning.learners.view")
    return operation(lambda: service.list_learners(member.tenant_id, limit, offset))


@router.post("/learners")
def create_learner(payload: service.LearnerPayload, request: Request, response: Response):
    member = require_elearning_access(request, response, "elearning.learners.manage")
    return mutate(request, member, "learner_created", member.tenant_id, lambda: service.save_learner(member.tenant_id, member.user_id, payload))


@router.put("/learners/{learner_id}")
def update_learner(learner_id: UUID, payload: service.LearnerUpdate, request: Request, response: Response):
    member = require_elearning_access(request, response, "elearning.learners.manage")
    return mutate(request, member, "learner_updated", learner_id, lambda: service.save_learner(member.tenant_id, member.user_id, payload, learner_id))


@router.post("/courses/{course_id}/enrollments")
def enroll(course_id: UUID, payload: service.EnrollmentPayload, request: Request, response: Response):
    member = require_elearning_access(request, response, "elearning.learners.manage")
    return mutate(request, member, "enrolled", course_id, lambda: service.command(member.tenant_id, course_id, member.user_id, "enroll", payload.model_dump(mode="json")))


@router.post("/courses/{course_id}/enrollments/{enrollment_id}/archive")
def archive(course_id: UUID, enrollment_id: UUID, request: Request, response: Response):
    member = require_elearning_access(request, response, "elearning.learners.manage")
    return mutate(request, member, "enrollment_archived", enrollment_id, lambda: service.command(member.tenant_id, course_id, member.user_id, "archive_enrollment", {"enrollment_id": str(enrollment_id)}))


@router.put("/courses/{course_id}/enrollments/{enrollment_id}/lessons/{lesson_id}/completion")
def complete(course_id: UUID, enrollment_id: UUID, lesson_id: UUID, payload: service.CompletionPayload, request: Request, response: Response):
    member = require_elearning_access(request, response, "elearning.progress.manage")
    return mutate(request, member, "completion_recorded" if payload.completed else "completion_removed", lesson_id, lambda: service.command(member.tenant_id, course_id, member.user_id, "complete_lesson" if payload.completed else "uncomplete_lesson", {"enrollment_id": str(enrollment_id), "lesson_id": str(lesson_id)}))


@router.get("/courses/{course_id}/progress")
def progress(course_id: UUID, request: Request, response: Response):
    member = require_elearning_access(request, response, "elearning.progress.view")
    return operation(lambda: service.progress(member.tenant_id, course_id))


@router.get("/courses/{course_id}/enrollments")
def enrollment_report(course_id: UUID, request: Request, response: Response):
    member = require_elearning_access(request, response, "elearning.learners.view")
    return operation(lambda: service.enrollment_report(member.tenant_id, course_id))


@router.get("/courses/{course_id}/enrollment-candidates")
def enrollment_candidates(course_id: UUID, request: Request, response: Response, query: str = Query("", max_length=120), limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0)):
    member = require_elearning_access(request, response, "elearning.learners.manage")
    return operation(lambda: service.enrollment_candidates(member.tenant_id, course_id, query, limit, offset))


@router.post("/courses/{course_id}/enrollments/users")
def enroll_users(course_id: UUID, payload: service.UserEnrollmentPayload, request: Request, response: Response):
    member = require_elearning_access(request, response, "elearning.learners.manage")
    return mutate(request, member, "users_enrolled", course_id, lambda: service.manage_enrollments(member.tenant_id, course_id, member.user_id, payload))


@router.post("/courses/{course_id}/enrollments/{enrollment_id}/status")
def enrollment_status(course_id: UUID, enrollment_id: UUID, payload: service.EnrollmentStatusPayload, request: Request, response: Response):
    member = require_elearning_access(request, response, "elearning.learners.manage")
    return mutate(request, member, payload.action, enrollment_id, lambda: service.manage_enrollments(member.tenant_id, course_id, member.user_id, payload, enrollment_id))
