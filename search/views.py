from django.shortcuts import redirect
from urllib.parse import urlencode

# NOTE: the dedicated search app is still on the backlog. Until it is built,
# these views delegate to the public showcase (which already supports
# search + filters) instead of crashing with a 500 (they used to return None).


def search_projects(request):
    """Search projects: delegate to the public showcase search."""
    params = {}
    query = request.GET.get('q') or request.GET.get('search', '')
    if query:
        params['search'] = query
    url = '/projects/'
    if params:
        url += '?' + urlencode(params)
    return redirect(url)


def filter_projects(request):
    """Filter projects: delegate to the public showcase filters."""
    allowed = ('search', 'tag', 'type', 'sort', 'has_demo', 'has_github')
    params = {key: request.GET[key] for key in allowed if request.GET.get(key)}
    url = '/projects/'
    if params:
        url += '?' + urlencode(params)
    return redirect(url)
