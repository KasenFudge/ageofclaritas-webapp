from django.urls import path
from . import views

app_name = "rulebook"
urlpatterns = [
    path("", views.Index, name="index"),
    path("classes/", views.ClassesView.as_view(), name="classes"),
    path("classes/wizard/", views.WizardDetailView.as_view(), name="wizard_detail"),
    path("classes/<str:classname>/", views.ClassDetailView.as_view(), name="class_detail"),
    path("kin/", views.KinView.as_view(), name="kin"),
]