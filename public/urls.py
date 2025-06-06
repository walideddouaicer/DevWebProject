from django.urls import path
from . import views

app_name = 'public'

urlpatterns = [
    path('', views.homepage, name='homepage'),
    path('features/', views.features, name='features'),
    path('about/', views.about, name='about'),
    path('explore/', views.explore_projects, name='explore_projects'),  # Future social feature
]