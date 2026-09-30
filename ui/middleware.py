"""HTMX integration (PLAN P5.8).

For HTMX requests, Django messages can't be rendered by a full page reload, so they are
moved into an `HX-Trigger: {"toast": [...]}` header; static/js/app.js shows them.
Redirects are left alone (the next full page renders the messages normally).
"""

import json

from django.contrib import messages


class HtmxMessagesMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if request.headers.get("HX-Request") != "true" or 300 <= response.status_code < 400:
            return response
        if "HX-Redirect" in response or "HX-Location" in response:
            return response
        toasts = [{"message": str(m), "level": m.level_tag} for m in messages.get_messages(request)]
        if toasts:
            existing = response.get("HX-Trigger")
            triggers = json.loads(existing) if existing and existing.startswith("{") else {}
            triggers["toast"] = toasts
            response["HX-Trigger"] = json.dumps(triggers)
        return response
