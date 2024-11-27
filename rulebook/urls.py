from django.urls import path
from . import views

app_name = "rulebook"
urlpatterns = [
    path("", views.Index, name="index"),
    path("Classes/", views.ClassesView.as_view(), name="classes"),
    path("Kin/", views.KinView.as_view(), name="kin"),
]