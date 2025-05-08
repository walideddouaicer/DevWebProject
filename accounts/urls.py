from django.urls import path
from . import views

app_name = 'accounts'

urlpatterns = [
    path('profile/', views.profile_view, name='profile'),
]

"""
URL patterns for the accounts app: user profile management.
""" 