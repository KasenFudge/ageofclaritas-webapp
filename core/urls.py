from django.urls import path

from . import views

app_name = "core"
urlpatterns = [
    path("", views.IndexView.as_view(), name="index"),
    path("what-is-larp/", views.WhatIsLarpView.as_view(), name="what_is_larp"),
    path("our-team/", views.TeamMemberView.as_view(), name="our_team"),
]
