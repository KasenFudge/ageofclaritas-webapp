from django.urls import path
from . import views

app_name = "rulebook"
urlpatterns = [
    path("", views.IndexView.as_view(), name="index"),
    path("classes/", views.ClassesView.as_view(), name="classes"),
    path("classes/wizard/", views.WizardDetailView.as_view(), name="wizard_detail"),
    path("classes/<str:classname>/", views.ClassDetailView.as_view(), name="class_detail"),
    path("kin/", views.KinView.as_view(), name="kin"),
    path("kin/<str:kin_name>/", views.KinDetailView.as_view(), name="kin_detail"),
    path("backgrounds/", views.BackgroundsView.as_view(), name="backgrounds"),
    path("modifiers/", views.ModifiersView.as_view(), name="modifiers"),
    path("techniques/", views.TechniquesView.as_view(), name="techniques"),
    path("character-creation/", views.CharacterCreationView.as_view(), name="character_creation"),
    path("definitions/", views.DefinitionsView.as_view(), name="definitions"),
    path("skills-and-abilities/", views.SkillsAndAbilitiesView.as_view(), name="skills_and_abilities"),
]