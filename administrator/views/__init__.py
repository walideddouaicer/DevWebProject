"""View package (split from the old monolithic modules in PLAN P3.1)."""

from .dashboard import (  # noqa: F401
    dashboard,
    statistics,
)
from .exports import (  # noqa: F401
    export_projects,
    export_statistics,
    export_users,
    exports,
)
from .imports import (  # noqa: F401
    download_student_import_template,
    download_teacher_import_template,
    import_students,
    import_teachers,
)
from .modules import (  # noqa: F401
    assign_teacher_to_module,
    assignments_management,
    module_create,
    module_delete,
    module_detail,
    module_edit,
    modules_list,
    remove_assignment,
    remove_student_from_module,
)
from .projects import (  # noqa: F401
    moderate_project,
    project_detail,
    projects_list,
    reports_moderation,
)
from .users import (  # noqa: F401
    approve_registration,
    pending_registrations,
    reject_registration,
    toggle_user_active,
    users_list,
)
