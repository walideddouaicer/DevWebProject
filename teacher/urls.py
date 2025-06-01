from django.urls import path
from . import views

app_name = 'teacher'

urlpatterns = [
    path('dashboard/', views.dashboard, name='dashboard'),
    path('modules/', views.modules_list, name='modules_list'),
    
    # NEW MODULE DETAIL URLS
    path('modules/<int:module_id>/', views.module_detail, name='module_detail'),
    path('modules/<int:module_id>/projects/', views.module_projects, name='module_projects'),
    path('modules/<int:module_id>/management/', views.module_management, name='module_management'),
    
    # PROJECT REVIEW URLS
    path('projects/', views.student_projects, name='student_projects'),
    path('projects/<int:project_id>/', views.project_review, name='project_review'),
    path('projects/<int:project_id>/approve/', views.approve_project, name='approve_project'),
    path('projects/<int:project_id>/reject/', views.reject_project, name='reject_project'),
    path('projects/<int:project_id>/comment/', views.add_teacher_comment, name='add_teacher_comment'),
]