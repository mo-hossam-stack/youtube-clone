from django.conf import settings
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.http import JsonResponse


def health_live(request):
    """Liveness: the process is running. No external dependencies."""
    return JsonResponse({"status": "alive"})


def _database_status():
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        return True, "ok"
    except Exception as e:
        return False, f"error: {e}"


def _migrations_status():
    try:
        executor = MigrationExecutor(connection)
        plan = executor.migration_plan(executor.loader.graph.leaf_nodes())
        if plan:
            return False, f"pending: {len(plan)}"
        return True, "ok"
    except Exception as e:
        return False, f"error: {e}"


def _redis_status():
    try:
        from django.core.cache import cache

        cache.set("_health", "ok", 10)
        if cache.get("_health") == "ok":
            return True, "ok"
        return False, "degraded: value mismatch"
    except Exception as e:
        return False, f"degraded: {e}"


def health_ready(request):
    """Readiness: required dependencies are available and migrations are applied."""
    services = {}
    critical_ok = True

    database_ok, database_msg = _database_status()
    services["database"] = database_msg
    if not database_ok:
        critical_ok = False

    migrations_ok, migrations_msg = _migrations_status()
    services["migrations"] = migrations_msg
    if not migrations_ok:
        critical_ok = False

    redis_ok, redis_msg = _redis_status()
    services["redis"] = redis_msg
    if settings.REDIS_URL and not redis_ok:
        critical_ok = False

    if not critical_ok:
        status = "unhealthy"
    elif not redis_ok:
        status = "degraded"
    else:
        status = "healthy"

    return JsonResponse(
        {"status": status, "services": services},
        status=200 if critical_ok else 503,
    )


def health_check(request):
    """Backward-compatible alias for the readiness check."""
    return health_ready(request)
