from django.contrib import admin
from .models import TeacherProfile, ModuleAssignment, ModuleEnrollment, Module

# Add a nice admin interface for TeacherProfile
class TeacherProfileAdmin(admin.ModelAdmin):
    list_display = ('teacher_id', 'user', 'department')
    search_fields = ('teacher_id', 'user__username', 'user__first_name', 'user__last_name')
    list_filter = ('department',)

# Module admin interface
class ModuleAssignmentInline(admin.TabularInline):
    model = ModuleAssignment
    extra = 1

class ModuleEnrollmentInline(admin.TabularInline):
    model = ModuleEnrollment
    extra = 1

class ModuleAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'academic_year', 'semester', 'is_active', 'get_enrolled_students_count', 'get_assigned_teachers_count')
    list_filter = ('academic_year', 'semester', 'is_active')
    search_fields = ('code', 'name', 'description')
    inlines = [ModuleAssignmentInline, ModuleEnrollmentInline]
    
    def get_enrolled_students_count(self, obj):
        return obj.get_enrolled_students_count()
    get_enrolled_students_count.short_description = 'Students Enrolled'
    
    def get_assigned_teachers_count(self, obj):
        return obj.get_assigned_teachers_count()
    get_assigned_teachers_count.short_description = 'Teachers Assigned'

# Module Assignment admin
class ModuleAssignmentAdmin(admin.ModelAdmin):
    list_display = ('teacher', 'module', 'assigned_at', 'is_active')
    list_filter = ('is_active', 'assigned_at', 'module__academic_year')
    search_fields = ('teacher__user__username', 'module__code', 'module__name')

# Module Enrollment admin  
class ModuleEnrollmentAdmin(admin.ModelAdmin):
    list_display = ('student', 'module', 'enrolled_at', 'is_active')
    list_filter = ('is_active', 'enrolled_at', 'module__academic_year')
    search_fields = ('student__user__username', 'module__code', 'module__name')

# Register all models
admin.site.register(TeacherProfile, TeacherProfileAdmin)
admin.site.register(Module, ModuleAdmin)
admin.site.register(ModuleAssignment, ModuleAssignmentAdmin)
admin.site.register(ModuleEnrollment, ModuleEnrollmentAdmin)