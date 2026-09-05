from django.urls import path

from . import views

app_name = "core"
urlpatterns = [
    path("", views.IndexView.as_view(), name="index"),
    path("what-is-larp/", views.WhatIsLarpView.as_view(), name="what_is_larp"),
    path("junior-landing/", views.JuniorLandingView.as_view(), name="junior_landing"),
    path("faq/", views.FaqView.as_view(), name="faq"),
    path("our-team/", views.TeamMemberView.as_view(), name="our_team"),
]
