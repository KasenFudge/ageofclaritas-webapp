from django.db.models import Case, IntegerField, Prefetch, When
from django.shortcuts import get_object_or_404, render
from django.views.generic import DetailView, ListView, TemplateView

from .models import Class, ClassType, Definition, Kin, RulePage, RuleSection, RuleSubsection, Talent, TalentType

# Sidebar faction lists mix Faction/Elemental/Manifold class_types together, but should
# read as one alphabetical run per type (e.g. all Elemental factions, then all Manifold
# factions) rather than everything interleaved alphabetically by name.
SIDEBAR_FACTION_ORDER = Case(
    When(class_type=ClassType.FACTION, then=0),
    When(class_type=ClassType.ELEMENTAL, then=1),
    When(class_type=ClassType.MANIFOLD, then=2),
    output_field=IntegerField(),
)


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
                ).order_by(SIDEBAR_FACTION_ORDER, "name"),
                to_attr="sidebar_factions",
            )
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context["sidebar_guilds"] = self.object_list
        context["classless_record"] = Class.objects.filter(class_type=ClassType.CLASSLESS).first()

        return context


def _classes_with_talents_queryset():
    """Guild/Classless Class rows prefetched with their own talents (pref_talents)
    and, for guilds, their child Faction/Elemental/Manifold rows (pref_factions),
    each of those also prefetched with their own talents. Shared by ClassDetailView
    (a single class, fetched by slug) and skills_and_abilities (every class at once)."""
    talents_qs = Talent.objects.all()

    factions_qs = (
        Class.objects.filter(class_type__in=[ClassType.FACTION, ClassType.ELEMENTAL, ClassType.MANIFOLD])
        .order_by("name")
        .prefetch_related(Prefetch("talents", queryset=talents_qs, to_attr="pref_talents"))
    )

    return Class.objects.filter(class_type__in=[ClassType.GUILD, ClassType.CLASSLESS]).prefetch_related(
        Prefetch("talents", queryset=talents_qs, to_attr="pref_talents"),
        Prefetch("factions", queryset=factions_qs, to_attr="pref_factions"),
    )


def _build_class_talent_context(guild):
    """Group one Guild/Classless Class row's (and its factions') talents by
    type, mirroring the Skills/Abilities/Tier/Warrior-Title sections rendered
    by class_body.html. Requires `guild` to come from _classes_with_talents_queryset()."""

    # Helper to grab talents by type
    def _grab_talent_type(kind, talents):
        return [t for t in talents if t.talent_type == kind]

    context = {"guild": guild}

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


class ClassDetailView(DetailView):
    model = Class
    template_name = "rulebook/class_detail.html"
    context_object_name = "guild"
    slug_field = "slug"
    slug_url_kwarg = "class_slug"

    def get_object(self, queryset=None):
        slug = self.kwargs[self.slug_url_kwarg]
        return get_object_or_404(_classes_with_talents_queryset(), slug=slug)

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
                    .order_by(SIDEBAR_FACTION_ORDER, "name")
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

        context.update(_build_class_talent_context(guild))

        return context


def skills_and_abilities(request):
    all_classes = list(_classes_with_talents_queryset().order_by("name"))
    guilds = [c for c in all_classes if c.class_type == ClassType.GUILD]
    classless = next((c for c in all_classes if c.class_type == ClassType.CLASSLESS), None)

    classes = []
    if classless:
        classes.append(_build_class_talent_context(classless))
    classes.extend(_build_class_talent_context(guild) for guild in guilds)

    return render(
        request,
        "rulebook/skills_and_abilities.html",
        {"classes": classes, "classless_record": classless},
    )


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


def _sidebar_pages_queryset():
    """RulePage queryset with a 2-tier Page->Section prefetch, shared by every
    view that renders rulepage_sidebar.html."""
    return RulePage.objects.prefetch_related(
        Prefetch("sections", queryset=RuleSection.objects.order_by("priority", "title"), to_attr="sidebar_sections")
    )


def rulepage_list(request):
    pages = RulePage.objects.all()
    return render(request, "rulebook/rulepage_list.html", {"pages": pages, "sidebar_pages": _sidebar_pages_queryset()})


def rulepage_detail(request, slug):
    sections_qs = RuleSection.objects.prefetch_related(
        Prefetch(
            "subsections", queryset=RuleSubsection.objects.order_by("priority", "title"), to_attr="pref_subsections"
        )
    ).order_by("priority", "title")

    page = get_object_or_404(
        RulePage.objects.prefetch_related(Prefetch("sections", queryset=sections_qs, to_attr="pref_sections")),
        slug=slug,
    )
    return render(request, "rulebook/rulepage_detail.html", {"page": page, "sidebar_pages": _sidebar_pages_queryset()})


def glossary_list(request):
    definitions = Definition.objects.all()
    return render(
        request,
        "rulebook/glossary.html",
        {"definitions": definitions, "sidebar_pages": _sidebar_pages_queryset()},
    )
