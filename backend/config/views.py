from django.http import JsonResponse
from django.db import connection


def health_check(request):
    checks = {"status": "healthy", "services": {}}

    # Database (critical — failure = unhealthy)
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        checks["services"]["database"] = "ok"
    except Exception as e:
        checks["services"]["database"] = f"error: {e}"
        checks["status"] = "unhealthy"

    # Redis (optional — failure = degraded, not unhealthy)
    try:
        from django.core.cache import cache

        cache.set("_health", "ok", 10)
        if cache.get("_health") == "ok":
            checks["services"]["redis"] = "ok"
        else:
            checks["services"]["redis"] = "degraded: value mismatch"
            if checks["status"] != "unhealthy":
                checks["status"] = "degraded"
    except Exception as e:
        checks["services"]["redis"] = f"degraded: {e}"
        if checks["status"] != "unhealthy":
            checks["status"] = "degraded"

    status_code = 200 if checks["status"] != "unhealthy" else 503
    return JsonResponse(checks, status=status_code)
