from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Prefetch
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.generic import DetailView, ListView, TemplateView

from .models import Class, ClassType, Definition, IndexType, Kin, RulePage, Talent, TalentType


# Create your views here.
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
            .prefetch_related(Prefetch("talents", queryset=talents_qs, to_attr="pref_talents"))
        )

        qs = Class.objects.filter(class_type__in=[ClassType.GUILD, ClassType.CLASSLESS]).prefetch_related(
            Prefetch("talents", queryset=talents_qs, to_attr="pref_talents"),
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
        def _grab_talent_type(kind, talents):
            return [t for t in talents if t.talent_type == kind]

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

        return context


class KinView(ListView):
    model = Kin
    template_name = "rulebook/kin.html"
    context_object_name = "kin_list"

    def get_queryset(self):
        return Kin.objects.prefetch_related("attributes", "kin_images")


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

        # Uses default model metadata sorting rules automatically
        context["kin_list"] = Kin.objects.all()

        return context


class CharacterCreationView(TemplateView):
    template_name = "rulebook/character_creation.html"


class TalentsView(TemplateView):
    template_name = "rulebook/talents.html"


def rulepage_list(request):
    pages = RulePage.objects.all()
    return render(request, "rulebook/rulepage_list.html", {"pages": pages, "sidebar_pages": pages})


def rulepage_detail(request, slug):
    page = get_object_or_404(RulePage, slug=slug)
    sidebar_pages = RulePage.objects.all()
    return render(request, "rulebook/rulepage_detail.html", {"page": page, "sidebar_pages": sidebar_pages})


def glossary_list(request):
    definitions = Definition.objects.filter(index_type=IndexType.GLOSSARY)
    sidebar_pages = RulePage.objects.all()
    return render(request, "rulebook/glossary.html", {"definitions": definitions, "sidebar_pages": sidebar_pages})


@staff_member_required
def definition_mentions(request):
    """
    Feeds CKEditor5's mention autocomplete (triggered by typing "[" in the
    admin editor). Restricted to staff since it's an authoring tool, not
    public-facing.

    Response shape: a JSON array of {"id": ..., "name": ...} objects.
    "id" is the literal text CKEditor inserts when an item is selected --
    already wrapped in [[double brackets]] so it's a valid shortcode the
    moment it's typed, no extra step needed. "name" is what's shown in the
    dropdown.
    """
    query = request.GET.get("query", "").strip()

    definitions = Definition.objects.all()
    if query:
        definitions = definitions.filter(term__icontains=query)
    definitions = definitions.order_by("term")[:10]

    results = [{"id": f"[[{d.slug}]]", "name": d.term} for d in definitions]
    return JsonResponse(results, safe=False)
