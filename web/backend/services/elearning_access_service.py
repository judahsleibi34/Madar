"""E-Learning permissions use the existing active tenant membership authority."""
from fastapi import HTTPException
from services.tenant_service import require_active_tenant_member

# Explicit aliases prepare future features without introducing another role store.
ELEARNING_PERMISSIONS = {
    "elearning.view", "elearning.manage",
    "elearning.learners.view", "elearning.learners.manage",
    "elearning.progress.view", "elearning.progress.manage",
    "elearning.courses.view", "elearning.courses.manage",
    "elearning.structure.view", "elearning.structure.manage",
    "elearning.groups.view", "elearning.groups.manage",
    "elearning.instructors.view", "elearning.instructors.manage",
}


def authorize_elearning_context(context, permission):
    if permission not in ELEARNING_PERMISSIONS:
        raise ValueError("Unknown E-Learning permission")
    if context.role not in {"owner", "admin"}:
        raise HTTPException(status_code=403, detail="Tenant owner or admin access required")
    return context


def require_elearning_access(request, response, permission):
    context = require_active_tenant_member(request, response, allow_admin_account_access=False)
    return authorize_elearning_context(context, permission)
