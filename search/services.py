"""Role-aware global search.

What a query finds depends on who asks:
  - visitor : public showcase projects
  - student : own/team projects, enrolled modules, public projects
  - teacher : projects and students of their modules, their modules, public projects
  - admin   : every project, module, student and teacher
"""

from dataclasses import dataclass, field

from django.db.models import Prefetch, Q
from django.urls import reverse
from django.utils.http import urlencode

from accounts.permissions import get_profiles, get_role, teacher_module_ids

MIN_QUERY_LENGTH = 2


@dataclass
class Result:
    title: str
    url: str
    subtitle: str = ""
    status: str = ""  # project status key, rendered as a chip
    badge: str = ""


@dataclass
class Section:
    key: str
    title: str
    icon: str
    items: list = field(default_factory=list)


def _project_q(query):
    return (
        Q(title__icontains=query)
        | Q(description__icontains=query)
        | Q(technologies__icontains=query)
    )


def _member_project_q(query):
    """Projects the user works with also match their module code/name."""
    return _project_q(query) | Q(module__code__icontains=query) | Q(module__name__icontains=query)


def _person_q(query):
    return (
        Q(user__first_name__icontains=query)
        | Q(user__last_name__icontains=query)
        | Q(user__username__icontains=query)
    )


def _module_label(project):
    return f" · {project.module.code}" if project.module_id else ""


def _project_owner(project, role, student):
    if role != "student":
        return project.student.get_full_name()
    return "Mon projet" if project.student_id == student.id else "Équipe"


def search(user, query, limit=25):
    """Return (role, [Section]) for ``query`` as seen by ``user``."""
    from student.models import Project, StudentProfile
    from teacher.models import Module, ModuleEnrollment, TeacherProfile

    role = get_role(user) or "public"
    query = (query or "").strip()
    if len(query) < MIN_QUERY_LENGTH:
        return role, []

    profiles = get_profiles(user)
    student, teacher = profiles["student"], profiles["teacher"]
    module_ids = teacher_module_ids(teacher) if role == "teacher" else []
    sections = []

    # Projects the user works with ------------------------------------------------
    projects = Project.objects.none()
    if role == "admin":
        projects = Project.objects.filter(_member_project_q(query))
    elif role == "teacher":
        projects = Project.objects.filter(_member_project_q(query), module_id__in=module_ids)
    elif role == "student":
        projects = (
            Project.objects.filter(_member_project_q(query))
            .filter(Q(student=student) | Q(collaborators=student))
            .distinct()
        )
    url_name = {
        "admin": "administrator:project_detail",
        "teacher": "teacher:project_review",
        "student": "student:project_detail",
    }.get(role)
    items = [
        Result(
            title=p.title,
            url=reverse(url_name, args=[p.id]),
            subtitle=_project_owner(p, role, student) + _module_label(p),
            status=p.status,
        )
        for p in projects.select_related("student__user", "module").order_by("-updated_at")[:limit]
    ]
    if items:
        sections.append(
            Section("projects", "Mes projets" if role == "student" else "Projets", "folder", items)
        )

    # Public showcase (admins already see everything above) -----------------------
    if role != "admin":
        public = (
            Project.objects.filter(
                _project_q(query) | Q(public_description__icontains=query),
                is_public=True,
                is_hidden_by_admin=False,
            )
            .select_related("student__user")
            .order_by("-like_count", "-updated_at")
        )
        items = [
            Result(
                title=p.title,
                url=reverse("public:project_detail", args=[p.id]),
                subtitle=f"par {p.student.get_full_name()}",
                badge=f"{p.like_count} j'aime" if p.like_count else "",
            )
            for p in public[:limit]
        ]
        if items:
            sections.append(Section("public", "Vitrine", "globe", items))

    # Modules --------------------------------------------------------------------
    module_q = Q(name__icontains=query) | Q(code__icontains=query)
    modules = Module.objects.none()
    if role == "admin":
        modules = Module.objects.filter(module_q)
    elif role == "teacher":
        modules = Module.objects.filter(module_q, id__in=module_ids)
    elif role == "student":
        modules = Module.objects.filter(
            module_q, enrollments__student=student, enrollments__is_active=True
        ).distinct()
    items = []
    for m in modules.order_by("code")[:limit]:
        if role == "admin":
            url = reverse("administrator:module_detail", args=[m.id])
            badge = "" if m.is_active else "Archivé"
        elif role == "teacher":
            url, badge = reverse("teacher:module_detail", args=[m.id]), ""
        else:
            url, badge = reverse("student:my_modules"), "Inscrit"
        items.append(
            Result(
                title=f"{m.code} — {m.name}",
                url=url,
                subtitle=" · ".join(filter(None, [m.academic_year, m.get_semester_display()])),
                badge=badge,
            )
        )
    if items:
        sections.append(Section("modules", "Modules", "book-open", items))

    # People ---------------------------------------------------------------------
    items = []
    if role == "admin":
        users_url = reverse("administrator:users_list")
        students = StudentProfile.objects.filter(
            _person_q(query) | Q(student_id__icontains=query)
        ).select_related("user")
        for s in students.order_by("user__last_name")[:limit]:
            items.append(
                Result(
                    title=s.get_full_name(),
                    url=f"{users_url}?{urlencode({'type': 'students', 'search': s.student_id})}",
                    subtitle=" · ".join(filter(None, ["Étudiant", s.student_id, s.department])),
                    badge=s.get_year_of_study_display(),
                )
            )
        teachers = TeacherProfile.objects.filter(
            _person_q(query) | Q(teacher_id__icontains=query)
        ).select_related("user")
        for t in teachers.order_by("user__last_name")[:limit]:
            items.append(
                Result(
                    title=t.user.get_full_name() or t.user.username,
                    url=f"{users_url}?{urlencode({'type': 'teachers', 'search': t.user.username})}",
                    subtitle=" · ".join(filter(None, ["Enseignant", t.department])),
                    badge=t.teacher_id or "",
                )
            )
    elif role == "teacher":
        students = (
            StudentProfile.objects.filter(
                _person_q(query) | Q(student_id__icontains=query),
                module_enrollments__module_id__in=module_ids,
                module_enrollments__is_active=True,
            )
            .select_related("user")
            .prefetch_related(
                Prefetch(
                    "module_enrollments",
                    queryset=ModuleEnrollment.objects.filter(
                        module_id__in=module_ids, is_active=True
                    )
                    .select_related("module")
                    .order_by("module__code"),
                    to_attr="shared_enrollments",
                )
            )
            .distinct()
            .order_by("user__last_name")
        )
        for s in students[:limit]:
            enrollment = s.shared_enrollments[0]
            items.append(
                Result(
                    title=s.get_full_name(),
                    url=reverse("teacher:module_detail", args=[enrollment.module_id]),
                    subtitle=" · ".join(filter(None, [s.student_id, s.department])),
                    badge=", ".join(e.module.code for e in s.shared_enrollments),
                )
            )
    if items:
        sections.append(Section("people", "Personnes", "users", items))

    return role, sections
