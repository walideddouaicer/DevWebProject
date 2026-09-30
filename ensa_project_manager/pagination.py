"""Shared pagination helper (PLAN P3.5)."""

from django.core.paginator import Paginator

DEFAULT_PER_PAGE = 25


def paginate(request, items, per_page=DEFAULT_PER_PAGE):
    """Page of `items` for ?page=N (invalid/out-of-range pages fall back gracefully)."""
    return Paginator(items, per_page).get_page(request.GET.get("page"))
