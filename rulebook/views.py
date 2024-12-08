from django.db.models import F
from django.http import Http404
from django.shortcuts import render, get_object_or_404
from django.views.generic import TemplateView, DetailView, ListView
from .models import Class, Kin

# Create your views here.
def Index(request):
    return render(request, "rulebook/index.html")

class ClassesView(TemplateView):
    template_name = "rulebook/classes.html"
    title = "Classes"

    def get_queryset(self):
        return Class.objects.order_by("name")

class ClassDetailView(ListView):
    model = Class
    template_name = "rulebook/class_detail.html"
    context_object_name = "class_data"

    allowed_names = ['Cleric', 'Noble', 'Ranger', 'Rogue', 'Spellbinder', 'Warrior']

    def get_queryset(self):
        # Filter classes that have subclasses and are within allowed names
        return Class.objects.prefetch_related('subclasses', 'talent_set').filter(
            name__in=self.allowed_names,
            subclasses__isnull=False
        ).distinct()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Get the name parameter from the URL
        class_name = self.kwargs.get('classname').capitalize()

        # Validate the name against the allowed list
        if class_name not in self.allowed_names:
            raise Http404(f"The class '{class_name}' does not exist.")

        # Fetch the base class
        base_class = get_object_or_404(self.get_queryset(), name=class_name)
        base_talents = base_class.talent_set.all()

        # Fetch subclasses and their talents
        subclasses = base_class.subclasses.all()
        subclass_talents = {
            subclass.name: subclass.talent_set.all()
            for subclass in subclasses
        }
        

        # Add to context
        context['base_class'] = base_class
        context['base_talents'] = base_talents
        context['subclasses'] = subclasses
        context['subclass_talents'] = subclass_talents

        return context


class KinView(ListView):
    template_name = "rulebook/kins.html"

    def get_queryset(self):
        return Kin.objects.order_by("name")