from django.urls import path
from . import views

urlpatterns = [
    path('search/', views.search_projects, name='search_projects'),
    path('filter/', views.filter_projects, name='filter_projects'),
]

"""
URL patterns for the search app: search and filter.
""" 