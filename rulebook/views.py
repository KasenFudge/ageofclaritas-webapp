from django.db.models import Prefetch, Case, When, IntegerField
from django.http import Http404
from django.shortcuts import render, get_object_or_404
from django.views.generic import TemplateView, DetailView, ListView
from .models import Class, ClassType, Talent, TalentType, Kin

# Macro to set the current app
def SetCurrentApp(context):
    context['current_app'] = 'rulebook'

# Create your views here.
class IndexView(TemplateView):
    template_name = "rulebook/index.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        SetCurrentApp(context)
        context['title'] = 'Rulebook'
        return context

class ClassesView(TemplateView):
    template_name = "rulebook/classes.html"
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        SetCurrentApp(context)
        context['title'] = 'Classes'
        return context

class ClassDetailView(DetailView):
    model = Class
    template_name = "rulebook/class_detail.html"
    context_object_name = "base_class"
    slug_field = "name"
    slug_url_kwarg = "classname"

    def get_object(self, queryset=None):
        slug = self.kwargs[self.slug_url_kwarg]

        # Get every Talent
        talents_qs = Talent.objects.annotate(
            priority=Case(
                When(name="Void", then=0),
                default=1,
                output_field=IntegerField(),
            )
        ).order_by("priority", "name")

        # Get every Faction for the base class (excluding itself) and its associated talents
        factions_qs = (
            Class.objects
                .filter(class_type__in=[ClassType.FACTION, ClassType.ELEMENTAL, ClassType.MANIFOLD])
                .order_by("name")
                .prefetch_related(Prefetch("talent_set", queryset=talents_qs, to_attr="pref_talents"))
        )

        # Finally get the base class and its associated talents and factions
        qs = (
            Class.objects
                .filter(class_type=ClassType.BASE_CLASS)
                .prefetch_related(
                    Prefetch("talent_set", queryset=talents_qs, to_attr="pref_talents"),
                    Prefetch("factions", queryset=factions_qs, to_attr="pref_factions"),
                )
        )
        
        # Return getting the object or fail for non Base Class classes.
        return get_object_or_404(qs, name__iexact=slug)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        base_class = self.object

        # Give context ClassType and TalentType for comparison
        context["ClassType"] = ClassType
        context["TalentType"] = TalentType

        # Helper to grab talents by type
        def _grab_talent_type(kind, talent_set):
            return [t for t in talent_set if t.talent_type == kind]

        # Base Class Talent Set
        talents = base_class.pref_talents
        context['base_skills'] = _grab_talent_type(TalentType.SKILL, talents)
        context['base_abilities'] = _grab_talent_type(TalentType.ABILITY, talents)

        # Factions
        all_factions = base_class.pref_factions
        factions = [f for f in all_factions if f.class_type == ClassType.FACTION]
        elementals = [f for f in all_factions if f.class_type == ClassType.ELEMENTAL]
        manifolds = [f for f in all_factions if f.class_type == ClassType.MANIFOLD]

        context['factions'] = [
            {
                'faction': faction,
                'skills': _grab_talent_type(TalentType.SKILL, faction.pref_talents),
                'abilities': _grab_talent_type(TalentType.ABILITY, faction.pref_talents),
            } 
            for faction in factions
        ]

        context['elementals'] = [
            {
                'faction': faction,
                'tier_1': _grab_talent_type(TalentType.TIER_1, faction.pref_talents),
                'tier_2': _grab_talent_type(TalentType.TIER_2, faction.pref_talents),
                'tier_3': _grab_talent_type(TalentType.TIER_3, faction.pref_talents),
            }
            for faction in elementals
        ]

        context['manifolds'] = [
            {
                'faction': faction,
                'tier_1': _grab_talent_type(TalentType.TIER_1, faction.pref_talents),
                'tier_2': _grab_talent_type(TalentType.TIER_2, faction.pref_talents),
                'tier_3': _grab_talent_type(TalentType.TIER_3, faction.pref_talents),
            }
            for faction in manifolds
        ]

        # Warrior Titles
        context['weapon_titles'] = _grab_talent_type(TalentType.WEAPON_WARRIOR_TITLE, talents)
        context['armor_titles'] = _grab_talent_type(TalentType.ARMOR_WARRIOR_TITLE, talents)
        context['support_titles'] = _grab_talent_type(TalentType.SUPPORT_WARRIOR_TITLE, talents)
        context['misc_titles'] = _grab_talent_type(TalentType.MISC_WARRIOR_TITLE, talents)

        # Add to context
        SetCurrentApp(context)
        context['title'] = base_class.name
        return context

class KinView(ListView):
    model = Kin
    template_name = "rulebook/kin.html"
    context_object_name = "kin_list"

    def get_queryset(self):
        return Kin.objects.prefetch_related("attribute_set", "kin_image_set").order_by("name")
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        SetCurrentApp(context)
        context['title'] = 'Kin'
        return context

class KinDetailView(DetailView):
    model = Kin
    template_name = "rulebook/kin_detail.html"
    context_object_name = "kin"

    def get_object(self):
        kin_name = self.kwargs.get("kin_name").capitalize()
        return Kin.objects.prefetch_related("attribute_set", "kin_image_set").get(name__iexact=kin_name)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        kin_name = self.kwargs.get('kin_name').capitalize()
        kin = get_object_or_404(self.get_queryset(), name=kin_name)
        kin_list = self.get_queryset().order_by('name')


        SetCurrentApp(context)
        context['title'] = kin.name
        context['kin_list'] = kin_list
        return context

class CharacterCreationView(TemplateView):
    template_name = "rulebook/character_creation.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context['title'] = 'Character Creation'
        SetCurrentApp(context)
        return context

class TalentsView(TemplateView):
    template_name = "rulebook/talents.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context['title'] = 'Talents'
        SetCurrentApp(context)
        return context

class DefinitionsView(TemplateView):
    template_name = "rulebook/definitions.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context['title'] = 'Definitions'
        SetCurrentApp(context)
        return context
