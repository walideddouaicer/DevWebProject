from django.urls import path
from . import views

urlpatterns = [
    path('', views.project_list, name='project_list'),
    path('<int:project_id>/', views.project_detail, name='project_detail'),
    path('submit/', views.submit_project, name='submit_project'),
]

"""
URL patterns for the projects app: list, detail, and submission.
""" 