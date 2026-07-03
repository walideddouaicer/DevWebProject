from django.urls import path
from . import views

app_name = 'search'

urlpatterns = [
    path('', views.search_projects, name='search'),
    path('search/', views.search_projects, name='search_projects'),
    path('filter/', views.filter_projects, name='filter_projects'),
]
