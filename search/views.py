from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.http import urlencode

from .services import MIN_QUERY_LENGTH, search

PAGE_LIMIT = 25
QUICK_LIMIT = 4


def search_projects(request):
    """Global search page (every role, visitors included)."""
    query = request.GET.get("q", "").strip()[:100]
    role, sections = search(request.user, query, limit=PAGE_LIMIT)
    context = {
        "query": query,
        "role": role,
        "sections": sections,
        "total_results": sum(len(s.items) for s in sections),
        "too_short": 0 < len(query) < MIN_QUERY_LENGTH,
        "base_template": "layouts/public.html" if role == "public" else "layouts/app.html",
    }
    return render(request, "search/results.html", context)


def quick_search(request):
    """Top-bar dropdown (HTMX partial): a few results per section."""
    query = request.GET.get("q", "").strip()[:100]
    _, sections = search(request.user, query, limit=QUICK_LIMIT)
    context = {
        "query": query,
        "sections": sections,
        "too_short": len(query) < MIN_QUERY_LENGTH,
    }
    return render(request, "search/partials/quick_results.html", context)


def filter_projects(request):
    """Legacy endpoint: delegate to the public showcase filters."""
    allowed = ("search", "tag", "type", "sort", "has_demo", "has_github")
    params = {key: request.GET[key] for key in allowed if request.GET.get(key)}
    url = reverse("public:projects_showcase")
    return redirect(f"{url}?{urlencode(params)}" if params else url)
