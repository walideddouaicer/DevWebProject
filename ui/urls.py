from django.urls import path

from . import views

app_name = "ui"

urlpatterns = [
    path("preferences/theme/", views.set_theme, name="set_theme"),
]
