from django.shortcuts import render
from django.views.generic import TemplateView, DetailView, ListView

# Create your views here.
class IndexView(TemplateView):
    template_name = "accounts/index.html"