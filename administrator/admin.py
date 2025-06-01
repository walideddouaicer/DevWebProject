# administrator/admin.py
from django.contrib import admin
from .models import AdminProfile

class AdminProfileAdmin(admin.ModelAdmin):
    list_display = ('admin_id', 'user', 'department', 'role')
    search_fields = ('admin_id', 'user__username', 'user__first_name', 'user__last_name')
    list_filter = ('department', 'role')

# Register the model
admin.site.register(AdminProfile, AdminProfileAdmin)