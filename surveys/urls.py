from django.urls import path

from . import views

app_name = "surveys"
urlpatterns = [
    path("<int:pk>/", views.respond_view, name="respond"),
    path("<int:pk>/<int:user_id>/", views.respond_view, name="respond_sub"),
]
