from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Case, IntegerField, When
from django.urls import NoReverseMatch, reverse
from django.utils.html import strip_tags
from django.utils.text import slugify

# Create your models here.


class TalentType(models.TextChoices):
    SKILL = "skill", "Skill"
    ABILITY = "ability", "Ability"
    WEAPON_WARRIOR_TITLE = "weapon", "Weapon Title"
    ARMOR_WARRIOR_TITLE = "armor", "Armor Title"
    SUPPORT_WARRIOR_TITLE = "support", "Support Title"
    MISC_WARRIOR_TITLE = "misc", "Misc. Title"
    TIER_1 = "tier_1", "Tier 1"
    TIER_2 = "tier_2", "Tier 2"
    TIER_3 = "tier_3", "Tier 3"


class ClassType(models.TextChoices):
    __empty__ = "Choose a Class Type..."
    GUILD = "guild", "Guild"
    FACTION = "faction", "Faction"
    ELEMENTAL = "elemental", "Elemental"
    MANIFOLD = "manifold", "Manifold"
    CLASSLESS = "classless", "Classless"


class Class(models.Model):
    name = models.CharField(max_length=20, unique=True)
    slug = models.SlugField(max_length=25, unique=True, blank=True)
    description = models.TextField(blank=True, default="")

    guild = models.ForeignKey("self", on_delete=models.CASCADE, related_name="factions", null=True, blank=True)
    class_type = models.CharField(max_length=15, choices=ClassType.choices)
    special_rules = models.TextField(null=True, blank=True)

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if self.class_type == ClassType.GUILD:
            self.guild = None

        self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    @property
    def has_special_rules(self):
        """
        bool(self.special_rules) alone isn't reliable if this field is ever edited through
        a rich-text widget: "clearing" the content there commonly leaves behind markup like
        "<p><br></p>" or "<p>&nbsp;</p>" rather than a true empty string, and both of those
        are non-empty strings that bool() would still treat as truthy. Strip tags and
        normalize whitespace entities first so only genuinely visible content counts.
        """
        if not self.special_rules:
            return False
        text = strip_tags(self.special_rules).replace("&nbsp;", " ").replace("\xa0", " ")
        return bool(text.strip())

    def clean(self):
        super().clean()

        # Factions must have a parent guild
        if self.class_type not in [ClassType.GUILD, ClassType.CLASSLESS] and not self.guild:
            raise ValidationError("Factions must be assigned to a Guild")

    class Meta:
        verbose_name = "Class"
        verbose_name_plural = "Classes"
        ordering = ["name"]


class Talent(models.Model):
    name = models.CharField(max_length=50, unique=True)
    slug = models.SlugField(max_length=55, unique=True, blank=True)
    class_for = models.ForeignKey(Class, on_delete=models.CASCADE, related_name="talents")
    description = models.TextField(blank=True, default="")
    is_rankless = models.BooleanField(default=False)

    priority = models.IntegerField(
        default=100, help_text="Lower numbers float to the top (e.g., 0, 1, 2). Default is 100."
    )

    talent_type = models.CharField(max_length=15, choices=TalentType.choices, default=TalentType.ABILITY)

    class Meta:
        ordering = [
            Case(
                When(talent_type=TalentType.SKILL, then=0),
                When(talent_type=TalentType.ABILITY, then=1),
                When(talent_type=TalentType.WEAPON_WARRIOR_TITLE, then=2),
                When(talent_type=TalentType.ARMOR_WARRIOR_TITLE, then=3),
                When(talent_type=TalentType.SUPPORT_WARRIOR_TITLE, then=4),
                When(talent_type=TalentType.MISC_WARRIOR_TITLE, then=5),
                When(talent_type=TalentType.TIER_1, then=6),
                When(talent_type=TalentType.TIER_2, then=7),
                When(talent_type=TalentType.TIER_3, then=8),
                output_field=IntegerField(),
            ),
            "priority",
            "name",
        ]

    def save(self, *args, **kwargs):
        self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Kin(models.Model):
    name = models.CharField(max_length=20, unique=True)
    slug = models.SlugField(max_length=25, unique=True, blank=True)
    short_description = models.TextField(blank=True, default="")
    description = models.TextField(blank=True, default="")
    size = models.CharField(max_length=80, blank=True, default="")

    def save(self, *args, **kwargs):
        self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Kin"
        verbose_name_plural = "Kin"
        ordering = ["name"]


class Kin_Image(models.Model):
    image = models.ImageField(upload_to="images/Kin/", blank=True)
    kin_for = models.ForeignKey(Kin, on_delete=models.CASCADE, related_name="kin_images")


class Attribute(models.Model):
    name = models.CharField(max_length=50, unique=True)
    slug = models.SlugField(max_length=55, unique=True, blank=True)
    kin_for = models.ForeignKey(Kin, on_delete=models.CASCADE, related_name="attributes")
    description = models.TextField()
    can_start_with = models.BooleanField(default=True)

    priority = models.IntegerField(
        default=100, help_text="Lower numbers float to the top (e.g., 0, 1, 2). Default is 100."
    )

    def save(self, *args, **kwargs):
        self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.kin_for.name})"


class IndexType(models.TextChoices):
    # Mirrored from their own models by signals.py -- term/description/
    # target_url are kept in sync with the source row (see sync_index).
    CLASS = "class", "Class"
    TALENT = "talent", "Talent"
    KIN = "kin", "Kin"
    ATTRIBUTE = "attribute", "Attribute"

    # Hand-authored: no source model, so these exist only as Definition rows.
    GLOSSARY = "glossary", "Glossary"


class RulePage(models.Model):
    title = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True, blank=True)
    content = models.TextField(blank=True, default="", help_text="CKEditor HTML content.")

    priority = models.IntegerField(
        default=100, help_text="Lower numbers float to the top (e.g., 0, 1, 2). Default is 100."
    )

    def save(self, *args, **kwargs):
        self.slug = slugify(self.title)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title

    class Meta:
        ordering = ["priority", "title"]


class RuleSection(models.Model):
    page = models.ForeignKey(RulePage, on_delete=models.CASCADE, related_name="sections")
    title = models.CharField(max_length=100)
    slug = models.SlugField(max_length=115, blank=True)
    content = models.TextField(blank=True, default="", help_text="CKEditor HTML content.")

    priority = models.IntegerField(
        default=100, help_text="Lower numbers float to the top (e.g., 0, 1, 2). Default is 100."
    )

    @staticmethod
    def build_slug(title):
        return f"section-{slugify(title)}"

    def save(self, *args, **kwargs):
        self.slug = self.build_slug(self.title)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.page.title} - {self.title}"

    class Meta:
        ordering = ["priority", "title"]
        unique_together = ("page", "slug")


class RuleSubsection(models.Model):
    section = models.ForeignKey(RuleSection, on_delete=models.CASCADE, related_name="subsections")
    title = models.CharField(max_length=100)
    slug = models.SlugField(max_length=115, blank=True)
    content = models.TextField(blank=True, default="", help_text="CKEditor HTML content.")

    priority = models.IntegerField(
        default=100, help_text="Lower numbers float to the top (e.g., 0, 1, 2). Default is 100."
    )

    @staticmethod
    def build_slug(title):
        return f"subsection-{slugify(title)}"

    def save(self, *args, **kwargs):
        self.slug = self.build_slug(self.title)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.section.title} - {self.title}"

    class Meta:
        ordering = ["priority", "title"]
        unique_together = ("section", "slug")


class Definition(models.Model):
    term = models.CharField(max_length=100)
    slug = models.SlugField(max_length=140, unique=True, blank=True)
    tag = models.CharField(
        max_length=50,
        blank=True,
        default="",
        help_text=(
            "Optional short label shown as a badge next to the term on the Glossary page. "
            "For Class/Talent/Kin/Attribute rows this is auto-filled with the Index Type's "
            "label the first time it's blank, but never overwritten once set by hand -- edit freely."
        ),
    )
    description = models.TextField(blank=True, default="")

    index_type = models.CharField(max_length=30, choices=IndexType.choices, default=IndexType.GLOSSARY)
    target_url = models.CharField(max_length=255, blank=True, default="")

    # Mirrored (Class/Talent/Kin/Attribute) rows use source_id for their real
    # pk; hand-authored rows leave it null.
    source_id = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="PK of the source row when this Definition is synced from another model. Null for hand-authored entries.",
    )

    @staticmethod
    def build_slug(index_type, term):
        return f"{slugify(index_type)}-{slugify(term)}"

    def save(self, *args, **kwargs):
        self.slug = self.build_slug(self.index_type, self.term)

        if not self.target_url:
            try:
                self.target_url = f"{reverse('rulebook:glossary')}#{self.slug}"
            except NoReverseMatch:
                pass

        super().save(*args, **kwargs)

    def __str__(self):
        return f"[{self.get_index_type_display()}] {self.term}"

    class Meta:
        ordering = ["term"]
        unique_together = ("index_type", "source_id")
