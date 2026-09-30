# Admin views use the shared role decorator (anonymous -> login?next=, wrong role -> 403).
from accounts.permissions import admin_required  # noqa: F401
