from django.db.models import F
from django.shortcuts import render, get_object_or_404
from django.views import generic
from .models import Class, Talent, Kin, Attribute

# Create your views here.
def Index(request):
    return render(request, "rulebook/index.html")

class ClassesView(generic.ListView):
    template_name = "rulebook/classes.html"

    def get_queryset(self):
        return Class.objects.order_by("class_name")

class KinView(generic.ListView):
    template_name = "rulebook/kins.html"

    def get_queryset(self):
        return Kin.objects.order_by("kin_name")