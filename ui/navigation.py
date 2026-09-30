"""Role-aware navigation, defined once for every layout (PLAN P5.6).

Each item: (label, url name, icon, badge context key or None, extra active prefixes).
An item is "current" when the request path starts with its URL (or an extra prefix).
"""

from django.urls import NoReverseMatch, reverse

NAVIGATION = {
    "student": [
        (
            None,
            [
                ("Tableau de bord", "student:dashboard", "layout-dashboard", None, ()),
                ("Devoirs", "student:assignments_dashboard", "clipboard-list", None, ()),
                ("Calendrier", "student:calendar", "calendar", None, ()),
                (
                    "Notifications",
                    "student:notifications",
                    "bell",
                    "unread_notifications_count",
                    (),
                ),
            ],
        ),
        (
            "Travail",
            [
                ("Mes projets", "student:dashboard", "folder", None, ("/student/projects/",)),
                ("Invitations", "student:invitations_list", "mail", "invitation_count", ()),
                ("Mes modules", "student:my_modules", "book-open", None, ()),
                ("Vitrine publique", "public:projects_showcase", "globe", None, ()),
            ],
        ),
    ],
    "teacher": [
        (
            None,
            [
                ("Tableau de bord", "teacher:dashboard", "layout-dashboard", None, ()),
                (
                    "À relire",
                    "teacher:student_projects",
                    "inbox",
                    "ungraded_projects_count",
                    ("/teacher/projects/",),
                ),
                (
                    "Devoirs",
                    "teacher:assignments_dashboard",
                    "clipboard-list",
                    "urgent_deadlines_count",
                    (),
                ),
                ("Modules", "teacher:modules_list", "book-open", None, ("/teacher/modules/",)),
            ],
        ),
        (
            "Autres",
            [
                ("Vitrine publique", "public:projects_showcase", "globe", None, ()),
            ],
        ),
    ],
    "admin": [
        (
            None,
            [
                ("Tableau de bord", "administrator:dashboard", "layout-dashboard", None, ()),
                (
                    "Inscriptions",
                    "administrator:pending_registrations",
                    "user-plus",
                    "pending_registrations_count",
                    (),
                ),
                (
                    "Signalements",
                    "administrator:reports_moderation",
                    "flag",
                    "reported_projects_count",
                    (),
                ),
            ],
        ),
        (
            "Gestion",
            [
                (
                    "Utilisateurs",
                    "administrator:users_list",
                    "users",
                    None,
                    ("/administrator/users/",),
                ),
                (
                    "Modules",
                    "administrator:modules_list",
                    "book-open",
                    None,
                    ("/administrator/modules/",),
                ),
                (
                    "Enseignants par module",
                    "administrator:assignments_management",
                    "user-cog",
                    None,
                    (),
                ),
                (
                    "Projets",
                    "administrator:projects_list",
                    "folder",
                    None,
                    ("/administrator/projects/",),
                ),
                ("Statistiques", "administrator:statistics", "bar-chart-3", None, ()),
                (
                    "Exports",
                    "administrator:exports",
                    "download",
                    None,
                    ("/administrator/exports/",),
                ),
            ],
        ),
    ],
}

HOME = {
    "student": "student:dashboard",
    "teacher": "teacher:dashboard",
    "admin": "administrator:dashboard",
}


def build_navigation(role, path, badges):
    """Groups of resolved items for the template; exactly one item is current."""
    groups, best = [], None
    for title, items in NAVIGATION.get(role, []):
        resolved = []
        for label, name, icon, badge_key, prefixes in items:
            try:
                url = reverse(name)
            except NoReverseMatch:
                continue
            item = {
                "label": label,
                "url": url,
                "icon": icon,
                "badge": badges.get(badge_key) if badge_key else None,
            }
            # Longest matching prefix wins, so only one item is highlighted.
            for prefix in (url, *prefixes):
                if path.startswith(prefix) and (best is None or len(prefix) > best[0]):
                    best = (len(prefix), item)
            resolved.append(item)
        groups.append({"title": title, "items": resolved})
    if best:
        best[1]["current"] = True
    return groups
