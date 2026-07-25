from django.http import JsonResponse

from .exceptions import ERROR_DEFAULTS, build_error_payload


class ApiV1ErrorMiddleware:
    """Normalize errors produced before a DRF view handles the request."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if not request.path.startswith("/api/v1/"):
            return response

        if response.status_code not in ERROR_DEFAULTS:
            return response

        data = getattr(response, "data", None)
        if isinstance(data, dict) and "error" in data:
            return response

        code, message = ERROR_DEFAULTS[response.status_code]
        normalized = JsonResponse(
            build_error_payload(code, message),
            status=response.status_code,
        )
        for header, value in response.items():
            if header.lower() not in {"content-length", "content-type"}:
                normalized[header] = value
        normalized.cookies.update(response.cookies)
        return normalized
