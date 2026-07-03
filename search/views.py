# Global role-aware search (ROADMAP #6).
#
# One search page for everyone; what it finds depends on who is asking:
#   - Public visitor : public showcase projects
#   - Student        : own/collaborated projects, enrolled modules, public projects
#   - Teacher        : projects & students of their modules, their modules
#   - Administrator  : all projects, modules, students and teachers

from django.shortcuts import render, redirect
from django.db.models import Q
from urllib.parse import urlencode

MAX_PER_SECTION = 25


def _project_q(query):
    return (
        Q(title__icontains=query) |
        Q(description__icontains=query) |
        Q(technologies__icontains=query)
    )


def _person_q(query):
    return (
        Q(user__first_name__icontains=query) |
        Q(user__last_name__icontains=query) |
        Q(user__username__icontains=query)
    )


def search_projects(request):
    """Global search page, scoped by the requesting user's role."""
    from student.models import Project, StudentProfile
    from teacher.models import Module, TeacherProfile, ModuleAssignment
    from administrator.models import AdminProfile

    query = request.GET.get('q', '').strip()

    role = 'public'
    student = teacher = None
    if request.user.is_authenticated:
        if AdminProfile.objects.filter(user=request.user).exists():
            role = 'admin'
        else:
            teacher = TeacherProfile.objects.filter(user=request.user).first()
            if teacher:
                role = 'teacher'
            else:
                student = StudentProfile.objects.filter(user=request.user).first()
                if student:
                    role = 'student'

    sections = []  # [{key, title, icon, items: [{title, subtitle, badge, url}]}]

    if query:
        # ------------------------------------------------------ Projects
        project_items = []

        if role == 'admin':
            projects = Project.objects.filter(_project_q(query))
            for p in projects.select_related('student__user', 'module')[:MAX_PER_SECTION]:
                project_items.append({
                    'title': p.title,
                    'subtitle': f"{p.student.get_full_name()}" + (f" — {p.module.code}" if p.module else ""),
                    'badge': p.get_status_display(),
                    'url': f"/administrator/projects/{p.id}/",
                })

        elif role == 'teacher':
            module_ids = ModuleAssignment.objects.filter(
                teacher=teacher, is_active=True
            ).values_list('module_id', flat=True)
            projects = Project.objects.filter(
                _project_q(query), module_id__in=module_ids
            )
            for p in projects.select_related('student__user', 'module')[:MAX_PER_SECTION]:
                project_items.append({
                    'title': p.title,
                    'subtitle': f"{p.student.get_full_name()}" + (f" — {p.module.code}" if p.module else ""),
                    'badge': p.get_status_display(),
                    'url': f"/teacher/projects/{p.id}/",
                })

        elif role == 'student':
            own = Project.objects.filter(
                _project_q(query)
            ).filter(
                Q(student=student) | Q(collaborators=student)
            ).distinct()
            for p in own.select_related('module')[:MAX_PER_SECTION]:
                project_items.append({
                    'title': p.title,
                    'subtitle': "Mon projet" + (f" — {p.module.code}" if p.module else ""),
                    'badge': p.get_status_display(),
                    'url': f"/student/projects/{p.id}/",
                })

        if project_items:
            sections.append({
                'key': 'projects',
                'title': "Mes projets" if role == 'student' else "Projets",
                'icon': 'fa-project-diagram',
                'items': project_items,
            })

        # Public showcase projects (everyone; skipped for admin who already sees all)
        if role != 'admin':
            public_projects = Project.objects.filter(
                _project_q(query) | Q(public_description__icontains=query),
                is_public=True,
                is_hidden_by_admin=False,
            ).select_related('student__user')
            public_items = [{
                'title': p.title,
                'subtitle': f"par {p.student.get_full_name()}",
                'badge': f"❤ {p.like_count}",
                'url': f"/projects/{p.id}/",
            } for p in public_projects[:MAX_PER_SECTION]]
            if public_items:
                sections.append({
                    'key': 'public',
                    'title': "Vitrine publique",
                    'icon': 'fa-globe',
                    'items': public_items,
                })

        # ------------------------------------------------------ Modules
        module_q = Q(name__icontains=query) | Q(code__icontains=query)
        module_items = []

        if role == 'admin':
            modules = Module.objects.filter(module_q)
            module_items = [{
                'title': f"{m.code} — {m.name}",
                'subtitle': f"{m.academic_year} · {m.get_semester_display()}",
                'badge': "Actif" if m.is_active else "Inactif",
                'url': f"/administrator/modules/{m.id}/",
            } for m in modules[:MAX_PER_SECTION]]
        elif role == 'teacher':
            modules = Module.objects.filter(
                module_q,
                assignments__teacher=teacher,
                assignments__is_active=True,
            ).distinct()
            module_items = [{
                'title': f"{m.code} — {m.name}",
                'subtitle': f"{m.academic_year} · {m.get_semester_display()}",
                'badge': f"{m.get_enrolled_students_count()} étudiants",
                'url': f"/teacher/modules/{m.id}/",
            } for m in modules[:MAX_PER_SECTION]]
        elif role == 'student':
            modules = Module.objects.filter(
                module_q,
                enrollments__student=student,
                enrollments__is_active=True,
            ).distinct()
            module_items = [{
                'title': f"{m.code} — {m.name}",
                'subtitle': f"{m.academic_year} · {m.get_semester_display()}",
                'badge': "Inscrit",
                'url': "/student/modules/",
            } for m in modules[:MAX_PER_SECTION]]

        if module_items:
            sections.append({
                'key': 'modules',
                'title': "Modules",
                'icon': 'fa-book',
                'items': module_items,
            })

        # ------------------------------------------------------ People
        people_items = []

        if role == 'admin':
            students = StudentProfile.objects.filter(
                _person_q(query) | Q(student_id__icontains=query)
            ).select_related('user')
            for s in students[:MAX_PER_SECTION]:
                people_items.append({
                    'title': s.get_full_name(),
                    'subtitle': f"Étudiant · {s.student_id} · {s.department}",
                    'badge': s.get_year_of_study_display(),
                    'url': f"/administrator/users/list/?type=students&search={query}",
                })
            teachers = TeacherProfile.objects.filter(
                _person_q(query) | Q(teacher_id__icontains=query)
            ).select_related('user')
            for t in teachers[:MAX_PER_SECTION]:
                people_items.append({
                    'title': t.user.get_full_name() or t.user.username,
                    'subtitle': f"Enseignant · {t.department}",
                    'badge': t.teacher_id or "—",
                    'url': f"/administrator/users/list/?type=teachers&search={query}",
                })

        elif role == 'teacher':
            module_ids = ModuleAssignment.objects.filter(
                teacher=teacher, is_active=True
            ).values_list('module_id', flat=True)
            students = StudentProfile.objects.filter(
                _person_q(query) | Q(student_id__icontains=query),
                module_enrollments__module_id__in=module_ids,
                module_enrollments__is_active=True,
            ).select_related('user').distinct()
            for s in students[:MAX_PER_SECTION]:
                enrolled = s.module_enrollments.filter(
                    module_id__in=module_ids, is_active=True
                ).select_related('module').first()
                people_items.append({
                    'title': s.get_full_name(),
                    'subtitle': f"Étudiant · {s.student_id} · {s.department}",
                    'badge': enrolled.module.code if enrolled else "",
                    'url': f"/teacher/modules/{enrolled.module_id}/" if enrolled else "",
                })

        if people_items:
            sections.append({
                'key': 'people',
                'title': "Personnes",
                'icon': 'fa-users',
                'items': people_items,
            })

    total_results = sum(len(s['items']) for s in sections)

    context = {
        'query': query,
        'role': role,
        'sections': sections,
        'total_results': total_results,
    }
    return render(request, 'search/results.html', context)


def filter_projects(request):
    """Legacy endpoint: delegate to the public showcase filters."""
    allowed = ('search', 'tag', 'type', 'sort', 'has_demo', 'has_github')
    params = {key: request.GET[key] for key in allowed if request.GET.get(key)}
    url = '/projects/'
    if params:
        url += '?' + urlencode(params)
    return redirect(url)
