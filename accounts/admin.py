# accounts/admin.py
from django.contrib import admin
from django.contrib.auth.models import User
from django.contrib import messages
from django.utils import timezone
from .models import PendingRegistration

@admin.action(description='Approve selected registrations')
def approve_registrations(modeladmin, request, queryset):
    """Approve pending registrations and create user accounts"""
    approved_count = 0
    
    for registration in queryset.filter(is_approved=False):
        try:
            # Create User account - FIXED VERSION
            user = User.objects.create(
                username=registration.username,
                email=registration.email,
                first_name=registration.first_name,
                last_name=registration.last_name,
                is_active=True
            )
            # The password in registration is already hashed, so set it directly
            user.password = registration.password
            user.save()
            
            # Create role-specific profile
            if registration.role == 'student':
                from student.models import StudentProfile
                StudentProfile.objects.create(
                    user=user,
                    student_id=registration.student_id,
                    year_of_study=registration.year_of_study,
                    department=registration.department
                )
            elif registration.role == 'teacher':
                from teacher.models import TeacherProfile
                TeacherProfile.objects.create(
                    user=user,
                    teacher_id=registration.teacher_id,
                    department=registration.department
                )
            
            # Mark as approved
            registration.is_approved = True
            registration.approved_by = request.user
            registration.approved_at = timezone.now()
            registration.save()
            
            # Send approval email
            from .utils import send_approval_email
            send_approval_email(registration)
            
            approved_count += 1
            
        except Exception as e:
            messages.error(request, f"Error approving {registration.username}: {str(e)}")
    
    messages.success(request, f"Successfully approved {approved_count} registrations.")

@admin.action(description='Reject selected registrations')
def reject_registrations(modeladmin, request, queryset):
    """Reject pending registrations"""
    rejected_count = queryset.filter(is_approved=False).delete()[0]
    messages.success(request, f"Rejected {rejected_count} registrations.")

class PendingRegistrationAdmin(admin.ModelAdmin):
    list_display = ('username', 'first_name', 'last_name', 'email', 'role', 'is_approved', 'created_at')
    list_filter = ('role', 'is_approved', 'created_at', 'department')
    search_fields = ('username', 'first_name', 'last_name', 'email', 'student_id', 'teacher_id')
    readonly_fields = ('password', 'created_at', 'approved_at')
    actions = [approve_registrations, reject_registrations]
    
    fieldsets = (
        ('User Information', {
            'fields': ('username', 'first_name', 'last_name', 'email', 'password')
        }),
        ('Role & Details', {
            'fields': ('role', 'student_id', 'teacher_id', 'department', 'year_of_study')
        }),
        ('Approval Status', {
            'fields': ('is_approved', 'approved_by', 'created_at', 'approved_at')
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('approved_by')

admin.site.register(PendingRegistration, PendingRegistrationAdmin)