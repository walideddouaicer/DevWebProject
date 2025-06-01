# administrator/urls.py
from django.urls import path
from . import views

app_name = 'administrator'

urlpatterns = [
    # Dashboard
    path('dashboard/', views.dashboard, name='dashboard'),
    
    # Project Management
    path('projects/', views.projects_list, name='projects_list'),
    path('projects/<int:project_id>/', views.project_detail, name='project_detail'),
    
    # Module Management
    path('modules/', views.modules_list, name='modules_list'),
    path('modules/create/', views.module_create, name='module_create'),
    path('modules/<int:module_id>/', views.module_detail, name='module_detail'),
    path('modules/<int:module_id>/edit/', views.module_edit, name='module_edit'),
    path('modules/<int:module_id>/delete/', views.module_delete, name='module_delete'),
    
    # Teacher-Module Assignment Management
    path('assignments/', views.assignments_management, name='assignments_management'),
    path('assignments/assign/', views.assign_teacher_to_module, name='assign_teacher_to_module'),
    path('assignments/<int:assignment_id>/remove/', views.remove_assignment, name='remove_assignment'),
    
    # User Management
    path('users/', views.users_overview, name='users_overview'),
    path('users/students/', views.students_list, name='students_list'),
    path('users/teachers/', views.teachers_list, name='teachers_list'),
    
    # Statistics & Reports
    path('statistics/', views.statistics, name='statistics'),
    path('exports/', views.exports, name='exports'),
    path('exports/projects/', views.export_projects, name='export_projects'),
    path('exports/statistics/', views.export_statistics, name='export_statistics'),
]