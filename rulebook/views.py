from django.db.models import Prefetch
from django.shortcuts import get_object_or_404
from django.views.generic import DetailView, ListView, TemplateView

from .models import Class, ClassType, Kin, Talent, TalentType


# Macro to set the current app
def SetCurrentApp(context):
    context["current_app"] = "rulebook"


# Macro to set the title of the page
def SetPageTitle(context, title):
    context["title"] = title


# Create your views here.
class IndexView(TemplateView):
    template_name = "rulebook/index.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        SetCurrentApp(context)
        SetPageTitle(context, "Rulebook")

        return context


class ClassesView(ListView):
    template_name = "rulebook/classes.html"
    context_object_name = "guilds"

    def get_queryset(self):
        return Class.objects.filter(class_type=ClassType.GUILD).prefetch_related(
            Prefetch(
                "factions",
                queryset=Class.objects.filter(
                    class_type__in=[ClassType.FACTION, ClassType.ELEMENTAL, ClassType.MANIFOLD]
                ).order_by("name"),
                to_attr="sidebar_factions",
            )
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context["sidebar_guilds"] = self.object_list
        context["classless_record"] = Class.objects.filter(class_type=ClassType.CLASSLESS).first()

        SetCurrentApp(context)
        SetPageTitle(context, "Classes")

        return context


class ClassDetailView(DetailView):
    model = Class
    template_name = "rulebook/class_detail.html"
    context_object_name = "guild"
    slug_field = "slug"
    slug_url_kwarg = "class_slug"

    def get_object(self, queryset=None):
        slug = self.kwargs[self.slug_url_kwarg]

        talents_qs = Talent.objects.all()

        factions_qs = (
            Class.objects.filter(class_type__in=[ClassType.FACTION, ClassType.ELEMENTAL, ClassType.MANIFOLD])
            .order_by("name")
            .prefetch_related(Prefetch("talent_set", queryset=talents_qs, to_attr="pref_talents"))
        )

        qs = Class.objects.filter(class_type__in=[ClassType.GUILD, ClassType.CLASSLESS]).prefetch_related(
            Prefetch("talent_set", queryset=talents_qs, to_attr="pref_talents"),
            Prefetch("factions", queryset=factions_qs, to_attr="pref_factions"),
        )

        return get_object_or_404(qs, slug=slug)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        guild = self.object

        context["sidebar_guilds"] = (
            Class.objects.filter(class_type=ClassType.GUILD)
            .order_by("name")
            .prefetch_related(
                Prefetch(
                    "factions",
                    queryset=Class.objects.filter(
                        class_type__in=[ClassType.FACTION, ClassType.ELEMENTAL, ClassType.MANIFOLD]
                    )
                    .order_by("name")
                    .only("name", "slug", "class_type"),
                    to_attr="sidebar_factions",
                )
            )
            .only("name", "slug", "class_type")
        )
        context["classless_record"] = Class.objects.filter(class_type=ClassType.CLASSLESS).first()

        # Give context ClassType and TalentType for comparison
        context["ClassType"] = ClassType
        context["TalentType"] = TalentType

        # Helper to grab talents by type
        def _grab_talent_type(kind, talent_set):
            return [t for t in talent_set if t.talent_type == kind]

        # Base Class Talent Set
        talents = getattr(guild, "pref_talents", [])
        context["guild_skills"] = _grab_talent_type(TalentType.SKILL, talents)
        context["guild_abilities"] = _grab_talent_type(TalentType.ABILITY, talents)

        # Factions
        all_factions = getattr(guild, "pref_factions", [])
        factions = [f for f in all_factions if f.class_type == ClassType.FACTION]
        elementals = [f for f in all_factions if f.class_type == ClassType.ELEMENTAL]
        manifolds = [f for f in all_factions if f.class_type == ClassType.MANIFOLD]

        context["factions"] = [
            {
                "faction": faction,
                "skills": _grab_talent_type(TalentType.SKILL, faction.pref_talents),
                "abilities": _grab_talent_type(TalentType.ABILITY, faction.pref_talents),
            }
            for faction in factions
        ]

        context["elementals"] = [
            {
                "faction": faction,
                "tier_1": _grab_talent_type(TalentType.TIER_1, faction.pref_talents),
                "tier_2": _grab_talent_type(TalentType.TIER_2, faction.pref_talents),
                "tier_3": _grab_talent_type(TalentType.TIER_3, faction.pref_talents),
            }
            for faction in elementals
        ]

        context["manifolds"] = [
            {
                "faction": faction,
                "tier_1": _grab_talent_type(TalentType.TIER_1, faction.pref_talents),
                "tier_2": _grab_talent_type(TalentType.TIER_2, faction.pref_talents),
                "tier_3": _grab_talent_type(TalentType.TIER_3, faction.pref_talents),
            }
            for faction in manifolds
        ]

        # Warrior Titles
        context["weapon_titles"] = _grab_talent_type(TalentType.WEAPON_WARRIOR_TITLE, talents)
        context["armor_titles"] = _grab_talent_type(TalentType.ARMOR_WARRIOR_TITLE, talents)
        context["support_titles"] = _grab_talent_type(TalentType.SUPPORT_WARRIOR_TITLE, talents)
        context["misc_titles"] = _grab_talent_type(TalentType.MISC_WARRIOR_TITLE, talents)

        # Overarching Page Information
        SetCurrentApp(context)
        SetPageTitle(context, guild.name)

        return context


class KinView(ListView):
    model = Kin
    template_name = "rulebook/kin.html"
    context_object_name = "kin_list"

    def get_queryset(self):
        return Kin.objects.prefetch_related("attributes", "kin_images")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        SetCurrentApp(context)
        SetPageTitle(context, "Kin")

        return context


class KinDetailView(DetailView):
    model = Kin
    template_name = "rulebook/kin_detail.html"
    context_object_name = "kin"
    slug_field = "slug"
    slug_url_kwarg = "kin_slug"

    def get_object(self, queryset=None):
        slug = self.kwargs.get(self.slug_url_kwarg)

        return get_object_or_404(Kin.objects.prefetch_related("attributes", "kin_images"), slug=slug)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Self.object is already the cached target row from get_object()!
        kin = self.object

        SetCurrentApp(context)
        SetPageTitle(context, kin.name)

        # Uses default model metadata sorting rules automatically
        context["kin_list"] = Kin.objects.all()

        return context


class CharacterCreationView(TemplateView):
    template_name = "rulebook/character_creation.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        SetCurrentApp(context)
        SetPageTitle(context, "Character Creation")

        return context


class TalentsView(TemplateView):
    template_name = "rulebook/talents.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        SetCurrentApp(context)
        SetPageTitle(context, "Talents")

        return context


class DefinitionsView(TemplateView):
    template_name = "rulebook/definitions.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        SetCurrentApp(context)
        SetPageTitle(context, "Definitions")

        return context
