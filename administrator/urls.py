from django.urls import path
from . import views

urlpatterns = [
    path('dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('statistics/', views.statistics_view, name='statistics'),
    path('users/', views.manage_users, name='manage_users'),
]

"""
URL patterns for the administrator app: dashboard, statistics, and user management.
""" 