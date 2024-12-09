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
        return Class.objects.prefetch_related('talent_set', 'subclasses', 'subclasses__talent_set').filter(
            name__in=self.allowed_names
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
        base_skills = base_class.talent_set.filter(talent_type='skill').order_by('name')
        base_abilities = base_class.talent_set.filter(talent_type='ability').order_by('name')

        # Force Void Ability to be first for Spellbinder
        if base_class.name == 'Spellbinder':
            void = base_abilities.filter(name="Void").first()

            if void:
                # Remove the ability from the list
                base_abilities = base_abilities.exclude(id=void.id)
                # Add it to the front
                base_abilities = [void] + list(base_abilities)

        # Fetch subclasses and their talents
        subclasses_ref = base_class.subclasses.all()
        subclasses = [
            (subclass, {
                'skills': subclass.talent_set.filter(talent_type='skill').order_by('name'),
                'abilities': subclass.talent_set.filter(talent_type='ability').order_by('name'),
            })
            for subclass in subclasses_ref
        ]

        # Fetch Warrior titles (Only for Warriors, empty elsewhere)
        weapon_titles = base_class.talent_set.filter(talent_type='weapon').order_by('name')
        armor_titles = base_class.talent_set.filter(talent_type='armor').order_by('name')
        support_titles = base_class.talent_set.filter(talent_type='support').order_by('name')
        other_titles = base_class.talent_set.filter(talent_type='other').order_by('name')
        

        # Add to context
        context['base_class'] = base_class
        context['base_skills'] = base_skills
        context['base_abilities'] = base_abilities
        context['subclasses'] = subclasses
        context['weapon_titles'] = weapon_titles
        context['armor_titles'] = armor_titles
        context['support_titles'] = support_titles
        context['other_titles'] = other_titles

        return context

class WizardDetailView(ListView):
    model = Class
    template_name = "rulebook/wizard_detail.html"
    context_object_name = "wizard_data"


    elemental_names = ['Hydromancy', 'Kairomancy', 'Pyromancy']
    manifold_names = ['Kinesiomancy', 'Avlomancy', 'Neuromancy']

    def get_queryset(self):
        # Get all wizard schools for context processing
        elemental_classes = Class.objects.prefetch_related('talent_set').filter(name__in=self.elemental_names)
        manifold_classes = Class.objects.prefetch_related('talent_set').filter(name__in=self.manifold_names)
        return elemental_classes | manifold_classes  # Combine the querysets for overall context
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Retrieve elemental and manifold classes
        elemental_classes = Class.objects.prefetch_related('talent_set').filter(name__in=self.elemental_names).order_by('name')
        manifold_classes = Class.objects.prefetch_related('talent_set').filter(name__in=self.manifold_names).order_by('name')

        elementals = [
            (elemental, {
                'tier_1': elemental.talent_set.filter(talent_type='tier_1').order_by('name'),
                'tier_2': elemental.talent_set.filter(talent_type='tier_2').order_by('name'),
                'tier_3': elemental.talent_set.filter(talent_type='tier_3').order_by('name'),
            })
            for elemental in elemental_classes
        ]

        manifolds = [
            (manifold, {
                'tier_1': manifold.talent_set.filter(talent_type='tier_1').order_by('name'),
                'tier_2': manifold.talent_set.filter(talent_type='tier_2').order_by('name'),
                'tier_3': manifold.talent_set.filter(talent_type='tier_3').order_by('name'),
            })
            for manifold in manifold_classes
        ]

        context['elementals'] = elementals
        context['manifolds'] = manifolds

        return context


class KinView(ListView):
    template_name = "rulebook/kins.html"

    def get_queryset(self):
        return Kin.objects.order_by("name")