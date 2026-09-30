"""View package (split from the old monolithic modules in PLAN P3.1)."""

from .assignments import (  # noqa: F401
    assignment_detail,
    assignments_dashboard,
    can_student_create_assignment_project,
    check_module_access,
    create_assignment_project_direct,
    get_existing_assignment_project,
    get_student_or_error,
    handle_choice_based_assignment_project,
    handle_direct_assignment_project,
    requires_module_access,
    select_project_option_direct,
    teammates_board,
    toggle_teammate_request,
)
from .calendar import (  # noqa: F401
    calendar_ics,
    calendar_view,
    collect_student_events,
)
from .deliverables import (  # noqa: F401
    add_deliverable_comment,
    can_download,
    deliverable_download,
    upload_deliverable,
)
from .milestones import (  # noqa: F401
    add_milestone,
    toggle_milestone,
)
from .modules import (  # noqa: F401
    join_module,
    leave_module,
    my_modules,
)
from .notifications import (  # noqa: F401
    mark_all_notifications_read,
    mark_notification_read,
    notifications,
)
from .profile import (  # noqa: F401
    account_settings,
    delete_profile_picture,
    profile_edit,
    profile_settings,
    profile_view,
)
from .projects import (  # noqa: F401
    add_comment,
    dashboard,
    make_project_private,
    make_project_public,
    project_create,
    project_delete,
    project_detail,
    project_edit,
    project_reopen,
    project_submit,
    project_submit_confirmation,
)
from .team import (  # noqa: F401
    add_collaborator,
    cancel_invitation,
    invitations_list,
    remove_collaborator,
    respond_to_invitation,
)
