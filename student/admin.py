from django.contrib import admin

from .models import (
    CollaborationInvitation,
    Notification,
    Project,
    ProjectDeliverable,
    ProjectMilestone,
    ProjectReport,
    ShowcaseTag,
    StudentProfile,
    TeammateRequest,
)


@admin.register(StudentProfile)
class StudentProfileAdmin(admin.ModelAdmin):
    list_display = ("student_id", "user", "year_of_study", "department")
    search_fields = ("student_id", "user__username", "user__first_name", "user__last_name")
    list_filter = ("year_of_study", "department")
    list_select_related = ("user",)


class DeliverableInline(admin.TabularInline):
    model = ProjectDeliverable
    extra = 0
    fields = ("name", "version", "file_type", "upload_date")
    readonly_fields = fields
    can_delete = False


class MilestoneInline(admin.TabularInline):
    model = ProjectMilestone
    extra = 0


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "student",
        "module",
        "status",
        "is_public",
        "is_hidden_by_admin",
        "updated_at",
    )
    list_filter = ("status", "project_type", "is_public", "is_hidden_by_admin", "module")
    search_fields = ("title", "student__user__last_name", "student__student_id")
    list_select_related = ("student__user", "module")
    autocomplete_fields = ("student", "collaborators")
    readonly_fields = ("created_at", "updated_at", "view_count", "like_count", "report_count")
    inlines = [DeliverableInline, MilestoneInline]
    date_hierarchy = "created_at"


@admin.register(ProjectDeliverable)
class ProjectDeliverableAdmin(admin.ModelAdmin):
    list_display = ("name", "version", "project", "file_type", "upload_date")
    list_filter = ("file_type",)
    search_fields = ("name", "project__title")
    list_select_related = ("project",)


@admin.register(ShowcaseTag)
class ShowcaseTagAdmin(admin.ModelAdmin):
    list_display = ("name", "color")
    search_fields = ("name",)


@admin.register(ProjectReport)
class ProjectReportAdmin(admin.ModelAdmin):
    list_display = ("project", "reporter", "reason", "is_reviewed", "created_at")
    list_filter = ("reason", "is_reviewed")
    list_select_related = ("project", "reporter")


@admin.register(CollaborationInvitation)
class CollaborationInvitationAdmin(admin.ModelAdmin):
    list_display = ("project", "sender", "recipient", "status", "created_at")
    list_filter = ("status",)
    list_select_related = ("project", "sender__user", "recipient__user")


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("recipient", "notification_type", "is_read", "created_at")
    list_filter = ("notification_type", "is_read")
    list_select_related = ("recipient__user",)
    readonly_fields = ("created_at",)


@admin.register(TeammateRequest)
class TeammateRequestAdmin(admin.ModelAdmin):
    list_display = ("student", "assignment", "is_active", "updated_at")
    list_filter = ("is_active",)
