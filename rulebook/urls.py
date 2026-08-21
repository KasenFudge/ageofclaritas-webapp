from django.urls import path

from . import views

app_name = "rulebook"
urlpatterns = [
    path("classes/", views.ClassesView.as_view(), name="classes"),
    path("classes/<str:class_slug>/", views.ClassDetailView.as_view(), name="class_detail"),
    path("skills-and-abilities/", views.skills_and_abilities, name="skills_and_abilities"),
    path("kin/", views.KinView.as_view(), name="kin"),
    path("kin/<str:kin_slug>/", views.KinDetailView.as_view(), name="kin_detail"),
    path("character-creation/", views.CharacterCreationView.as_view(), name="character_creation"),
    path("mechanics/", views.rulepage_list, name="rulepage_list"),
    path("mechanics/<slug:slug>/", views.rulepage_detail, name="rulepage_detail"),
    path("glossary/", views.glossary_list, name="glossary"),
]
