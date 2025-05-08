from django.contrib import admin
from .models import StudentProfile, Project, ProjectDeliverable

class ProjectDeliverableInline(admin.TabularInline):
    model = ProjectDeliverable
    extra = 1  # Show one empty form by default

class ProjectAdmin(admin.ModelAdmin):
    list_display = ('title', 'project_type', 'student', 'status', 'start_date')
    list_filter = ('project_type', 'status', 'start_date')
    search_fields = ('title', 'description', 'technologies')
    inlines = [ProjectDeliverableInline]

# StudentProfile is already registered, so we don't register it again
# admin.site.register(StudentProfile)  

admin.site.register(Project, ProjectAdmin)
admin.site.register(ProjectDeliverable)