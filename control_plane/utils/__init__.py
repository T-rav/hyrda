"""Utility modules for control plane."""

from .audit import (
    AuditAction,
    log_admin_action,
    log_agent_action,
    log_group_action,
    log_permission_action,
    log_user_action,
)
from .errors import error_response, success_response
from .idempotency import (
    check_idempotency,
    get_idempotency_key,
    require_idempotency,
    store_idempotency,
)
from .pagination import (
    build_pagination_response,
    get_pagination_params,
    paginate_query,
)
from .permissions import get_current_user, require_admin, require_permission
from .rate_limit import check_rate_limit, get_rate_limit_key, rate_limit
from .validation import (
    sanitize_text_input,
    validate_agent_name,
    validate_display_name,
    validate_email,
    validate_group_name,
    validate_required_field,
)

__all__ = [
    "error_response",
    "success_response",
    "get_current_user",
    "require_admin",
    "require_permission",
    "validate_agent_name",
    "validate_group_name",
    "validate_display_name",
    "validate_email",
    "validate_required_field",
    "sanitize_text_input",
    "log_admin_action",
    "log_agent_action",
    "log_group_action",
    "log_permission_action",
    "log_user_action",
    "AuditAction",
    "get_pagination_params",
    "paginate_query",
    "build_pagination_response",
    "get_idempotency_key",
    "check_idempotency",
    "store_idempotency",
    "require_idempotency",
    "rate_limit",
    "check_rate_limit",
    "get_rate_limit_key",
]
