from django.urls import path

from . import views

app_name = "teacher"

urlpatterns = [
    path("dashboard/", views.dashboard, name="dashboard"),
    path("modules/", views.modules_list, name="modules_list"),
    # NEW MODULE DETAIL URLS
    path("modules/<int:module_id>/", views.module_detail, name="module_detail"),
    path("modules/<int:module_id>/projects/", views.module_projects, name="module_projects"),
    path("modules/<int:module_id>/management/", views.module_management, name="module_management"),
    # PROJECT REVIEW URLS
    path("projects/", views.student_projects, name="student_projects"),
    path("projects/<int:project_id>/", views.project_review, name="project_review"),
    path("projects/<int:project_id>/approve/", views.approve_project, name="approve_project"),
    path("projects/<int:project_id>/reject/", views.reject_project, name="reject_project"),
    path(
        "projects/<int:project_id>/request-revision/",
        views.request_revision,
        name="request_revision",
    ),
    path("projects/<int:project_id>/grade/", views.grade_project, name="grade_project"),
    path(
        "projects/<int:project_id>/comment/", views.add_teacher_comment, name="add_teacher_comment"
    ),
    path(
        "deliverables/<int:deliverable_id>/comment/",
        views.add_deliverable_comment,
        name="add_deliverable_comment",
    ),
    # Teacher Module Creation
    path("modules/create/", views.create_teacher_module, name="create_teacher_module"),
    path("modules/my/", views.my_modules, name="my_modules"),
    # Assignment Management URLs
    path("assignments/", views.assignments_dashboard, name="assignments_dashboard"),
    path("assignments/create/", views.assignment_create, name="assignment_create"),
    path(
        "assignments/<int:assignment_id>/",
        views.assignment_detail,
        name="assignment_detail",
    ),
    path(
        "assignments/<int:assignment_id>/edit/",
        views.assignment_edit,
        name="assignment_edit",
    ),
    path(
        "assignments/<int:assignment_id>/publish/",
        views.assignment_publish,
        name="assignment_publish",
    ),
    path(
        "assignments/<int:assignment_id>/progress/",
        views.assignment_progress,
        name="assignment_progress",
    ),
    path(
        "assignments/<int:assignment_id>/bulk-action/",
        views.bulk_project_action,
        name="bulk_project_action",
    ),
    # Assignment Students Management (for direct assignments)
    path(
        "assignments/<int:assignment_id>/students/",
        views.assignment_students,
        name="assignment_students",
    ),
    # Assignment Options Management (for choice-based assignments)
    path(
        "assignments/<int:assignment_id>/options/",
        views.assignment_options,
        name="assignment_options",
    ),
    path(
        "assignments/<int:assignment_id>/options/<int:option_id>/delete/",
        views.option_delete,
        name="option_delete",
    ),
    # ===== TEAM MANAGEMENT (REPLACES GROUP MANAGEMENT) =====
    path(
        "assignments/<int:assignment_id>/teams/",
        views.assignment_teams,
        name="assignment_teams",
    ),
    path(
        "modules/<int:module_id>/students/", views.get_module_students, name="get_module_students"
    ),
    # Module announcements
    path(
        "modules/<int:module_id>/announce/",
        views.post_module_announcement,
        name="post_module_announcement",
    ),
    # Excel exports
    path(
        "modules/<int:module_id>/export/", views.export_module_roster, name="export_module_roster"
    ),
    path(
        "assignments/<int:assignment_id>/export/",
        views.export_assignment_results,
        name="export_assignment_results",
    ),
]
