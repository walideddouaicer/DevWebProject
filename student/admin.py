from django.contrib import admin
from .models import StudentProfile, Project, ProjectDeliverable, ProjectMilestone

# Add a nice admin interface for StudentProfile
class StudentProfileAdmin(admin.ModelAdmin):
    list_display = ('student_id', 'user', 'year_of_study', 'department')
    search_fields = ('student_id', 'user__username')
    list_filter = ('year_of_study', 'department')

# Register all models
admin.site.register(StudentProfile, StudentProfileAdmin)
admin.site.register(Project)
admin.site.register(ProjectDeliverable)
admin.site.register(ProjectMilestone)