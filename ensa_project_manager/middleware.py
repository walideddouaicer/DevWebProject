"""Health check endpoint (PLAN P4.4).

Answered before any other middleware so container health probes work over plain HTTP
with any Host header (no DisallowedHost, no HTTPS redirect, no session/DB writes).
"""

from django.db import connection
from django.http import JsonResponse


class HealthCheckMiddleware:
    PATH = "/healthz"

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path_info.rstrip("/") != self.PATH:
            return self.get_response(request)
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
        except Exception:
            return JsonResponse({"status": "error", "database": "unreachable"}, status=503)
        return JsonResponse({"status": "ok", "database": "ok"})
