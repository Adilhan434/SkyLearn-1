import logging

from rest_framework import status
from rest_framework.exceptions import (
    APIException,
    AuthenticationFailed,
    NotAuthenticated,
    ValidationError,
)
from rest_framework.response import Response
from rest_framework.views import exception_handler, set_rollback


logger = logging.getLogger(__name__)


class CodedAPIException(APIException):
    """API exception with a stable frontend-facing error code."""

    status_code = status.HTTP_400_BAD_REQUEST
    error_code = "api_error"
    default_detail = "API request failed."

    def __init__(self, detail=None, *, fields=None, details=None):
        self.error_fields = fields
        self.error_details = details
        super().__init__(detail=detail)


ERROR_DEFAULTS = {
    status.HTTP_400_BAD_REQUEST: ("bad_request", "Bad request."),
    status.HTTP_401_UNAUTHORIZED: (
        "authentication_required",
        "Authentication is required.",
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

    if isinstance(exc, NotAuthenticated):
        response.data = build_error_payload(
            "authentication_required",
            "Authentication is required.",
        )
        return response

    if isinstance(exc, AuthenticationFailed):
        response.data = build_error_payload(
            "authentication_failed",
            str(exc.detail),
        )
        return response

    if isinstance(exc, CodedAPIException):
        payload = build_error_payload(
            exc.error_code,
            str(exc.detail),
            exc.error_fields,
        )
        if exc.error_details is not None:
            payload["error"]["details"] = exc.error_details
        response.data = payload
        return response

    code, default_message = ERROR_DEFAULTS.get(
        response.status_code,
        ("api_error", "API request failed."),
    )
    detail = response.data.get("detail") if isinstance(response.data, dict) else None
    message = str(detail) if detail else default_message
    response.data = build_error_payload(code, message)
    return response
