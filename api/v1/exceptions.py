import logging

from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import exception_handler, set_rollback


logger = logging.getLogger(__name__)

ERROR_DEFAULTS = {
    status.HTTP_400_BAD_REQUEST: ("bad_request", "Bad request."),
    status.HTTP_401_UNAUTHORIZED: (
        "authentication_failed",
        "Authentication failed.",
    ),
    status.HTTP_403_FORBIDDEN: ("permission_denied", "Permission denied."),
    status.HTTP_404_NOT_FOUND: ("not_found", "Resource not found."),
    status.HTTP_405_METHOD_NOT_ALLOWED: (
        "method_not_allowed",
        "Method not allowed.",
    ),
    status.HTTP_500_INTERNAL_SERVER_ERROR: (
        "internal_server_error",
        "An internal server error occurred.",
    ),
}


def _stringify_errors(value):
    if isinstance(value, dict):
        return {key: _stringify_errors(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_stringify_errors(item) for item in value]
    return str(value)


def build_error_payload(code, message, fields=None):
    return {
        "error": {
            "code": code,
            "message": message,
            "fields": fields or {},
        }
    }


def api_exception_handler(exc, context):
    response = exception_handler(exc, context)

    if response is None:
        set_rollback()
        request = context.get("request")
        logger.exception(
            "Unhandled API exception on %s",
            getattr(request, "path", "<unknown>"),
            exc_info=exc,
        )
        code, message = ERROR_DEFAULTS[status.HTTP_500_INTERNAL_SERVER_ERROR]
        return Response(
            build_error_payload(code, message),
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    if isinstance(exc, ValidationError):
        response.data = build_error_payload(
            "validation_error",
            "Validation failed.",
            _stringify_errors(response.data),
        )
        return response

    code, default_message = ERROR_DEFAULTS.get(
        response.status_code,
        ("api_error", "API request failed."),
    )
    detail = response.data.get("detail") if isinstance(response.data, dict) else None
    message = str(detail) if detail else default_message
    response.data = build_error_payload(code, message)
    return response
