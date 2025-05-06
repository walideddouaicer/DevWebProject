from django.urls import path
from . import views

urlpatterns = [
    path('dashboard/', views.teacher_dashboard, name='teacher_dashboard'),
    path('evaluate/<int:project_id>/', views.evaluate_project, name='evaluate_project'),
    path('remark/<int:project_id>/', views.add_remark, name='add_remark'),
]

"""
URL patterns for the teacher app: dashboard, evaluation, and remarks.
""" 