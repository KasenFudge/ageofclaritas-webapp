from django.db.models import F
from django.shortcuts import render, get_object_or_404
from django.views import generic
from .models import Class, Kin

# Create your views here.
def Index(request):
    return render(request, "rulebook/index.html")

class ClassesView(generic.ListView):
    template_name = "rulebook/classes.html"
    title = "Classes"

    def get_queryset(self):
        return Class.objects.order_by("name")

class ClassDetailView(generic.ListView):
    template_name = "rulebook/class_detail.html"

class KinView(generic.ListView):
    template_name = "rulebook/kins.html"

    def get_queryset(self):
        return Kin.objects.order_by("name")