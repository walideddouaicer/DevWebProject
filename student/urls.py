from django.urls import path
from . import views

urlpatterns = [
    path('dashboard/', views.student_dashboard, name='student_dashboard'),
    path('history/', views.project_history, name='project_history'),
]

"""
URL patterns for the student app: dashboard and project history.
""" 