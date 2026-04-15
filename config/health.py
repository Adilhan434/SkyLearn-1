from django.db import connection
from django.http import JsonResponse


def liveness(request):
    """Basic liveness probe — app process is running."""
    return JsonResponse({"status": "ok"})


def readiness(request):
    """Readiness probe — app can serve traffic (DB is reachable)."""
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        return JsonResponse({"status": "ok"})
    except Exception:
        return JsonResponse({"status": "unavailable"}, status=503)
