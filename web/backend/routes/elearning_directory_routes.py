import logging
from uuid import UUID
from fastapi import APIRouter, HTTPException, Query, Request, Response
from services.elearning_access_service import require_elearning_access
from services.audit_service import record_audit_event
from services import elearning_directory_service as service

logger = logging.getLogger(__name__)
router = APIRouter(tags=["E-Learning"])


def operation(callback):
    try:
        return callback()
    except HTTPException:
        raise
    except Exception:
        logger.exception("elearning.directory.operation_failed")
        raise HTTPException(503, "Group and instructor management is temporarily unavailable")


def register_directory(kind, payload_type, update_type):
    routes = APIRouter(prefix=f"/elearning/{kind}")

    def context(request, response, action):
        return require_elearning_access(request, response, f"elearning.{kind}.{action}")

    def mutation(request, member, action, callback):
        def execute():
            service.require_available()
            item = callback()
            record_audit_event(request=request, actor_user_id=member.user_id, tenant_id=member.tenant_id,
                               action=f"elearning.{kind}_{action}", target_type=f"elearning_{kind}", target_id=item["id"])
            return {"item": item}
        return operation(execute)

    @routes.get("")
    def list_items(request: Request, response: Response, limit: int = Query(default=50, ge=1, le=100), offset: int = Query(default=0, ge=0)):
        member = context(request, response, "view")
        def read():
            available = service.directory_available()
            return {"available": available, **(service.list_items(kind, member.tenant_id, limit, offset) if available else {"items": [], "has_more": False})}
        return operation(read)

    @routes.get("/{item_id}")
    def get_item(item_id: UUID, request: Request, response: Response):
        member = context(request, response, "view")
        def read():
            service.require_available()
            return {"item": service.get_item(kind, member.tenant_id, item_id)}
        return operation(read)

    @routes.post("")
    def create_item(payload: payload_type, request: Request, response: Response):
        member = context(request, response, "manage")
        return mutation(request, member, "created", lambda: service.create_item(kind, member.tenant_id, member.user_id, payload))

    @routes.put("/{item_id}")
    def update_item(item_id: UUID, payload: update_type, request: Request, response: Response):
        member = context(request, response, "manage")
        return mutation(request, member, "updated", lambda: service.update_item(kind, member.tenant_id, item_id, payload))

    @routes.post("/{item_id}/archive")
    def archive_item(item_id: UUID, payload: service.ArchiveCommand, request: Request, response: Response):
        member = context(request, response, "manage")
        return mutation(request, member, "archived", lambda: service.update_fields(kind, member.tenant_id, item_id, {"status": "archived"}, payload.expected_revision))

    @routes.delete("/{item_id}")
    def delete_item(item_id: UUID, payload: service.DeleteCommand, request: Request, response: Response):
        member = context(request, response, "manage")
        delete = service.delete_group if kind == "groups" else service.delete_instructor
        return mutation(request, member, "deleted", lambda: delete(member.tenant_id, member.user_id, item_id, payload))

    router.include_router(routes)


register_directory("groups", service.GroupPayload, service.GroupUpdate)
register_directory("instructors", service.InstructorPayload, service.InstructorUpdate)
