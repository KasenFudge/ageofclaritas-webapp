from django.urls import path
from . import views

app_name = "rulebook"
urlpatterns = [
    path("", views.IndexView.as_view(), name="index"),
    path("classes/", views.ClassesView.as_view(), name="classes"),
    path("classes/<str:classname>/", views.ClassDetailView.as_view(), name="class_detail"),
    path("kin/", views.KinView.as_view(), name="kin"),
    path("kin/<str:kin_name>/", views.KinDetailView.as_view(), name="kin_detail"),
    path("character-creation/", views.CharacterCreationView.as_view(), name="character_creation"),
    path("talents/", views.TalentsView.as_view(), name="talents"),
    path("definitions/", views.DefinitionsView.as_view(), name="definitions"),

]