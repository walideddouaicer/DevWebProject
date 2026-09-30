"""View package (split from the old monolithic modules in PLAN P3.1)."""

from .assignments import (  # noqa: F401
    assignment_create,
    assignment_detail,
    assignment_edit,
    assignment_options,
    assignment_progress,
    assignment_publish,
    assignment_students,
    assignment_teams,
    assignments_dashboard,
    bulk_project_action,
    export_assignment_results,
    get_teacher_or_error,
    option_delete,
)
from .dashboard import (  # noqa: F401
    dashboard,
)
from .modules import (  # noqa: F401
    check_teacher_module_access,
    create_teacher_module,
    export_module_roster,
    get_module_students,
    module_detail,
    module_management,
    module_projects,
    modules_list,
    my_modules,
    post_module_announcement,
)
from .review import (  # noqa: F401
    add_deliverable_comment,
    add_teacher_comment,
    approve_project,
    grade_project,
    project_review,
    reject_project,
    request_revision,
    student_projects,
)
