from django.urls import path
from . import views

app_name = 'public'

urlpatterns = [
    path('', views.homepage, name='homepage'),

    # NEW: Public showcase URLs
    path('projects/', views.public_projects_showcase, name='projects_showcase'),
    path('projects/<int:project_id>/', views.public_project_detail, name='project_detail'),
    path('projects/<int:project_id>/report/', views.report_project, name='report_project'),
    

    # NEW: Regular form submission for comments
    path('projects/<int:project_id>/comment/', views.add_project_comment, name='add_project_comment'),
    
    # AJAX endpoints
    path('api/projects/<int:project_id>/like/', views.toggle_project_like, name='toggle_project_like'),
    path('api/projects/<int:project_id>/comment/', views.add_public_comment, name='add_public_comment'),

    path('features/', views.features, name='features'),
    path('about/', views.about, name='about'),
    path('explore/', views.explore_projects, name='explore_projects'),  # Future social feature
]