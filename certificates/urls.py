from django.urls import path
from . import views

urlpatterns = [
    path('generate/<int:project_id>/', views.generate_certificate, name='generate_certificate'),
    path('download/<int:certificate_id>/', views.download_certificate, name='download_certificate'),
]

"""
URL patterns for the certificates app: generate and download certificates.
""" 