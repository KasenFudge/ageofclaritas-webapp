from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Case, IntegerField, When
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

        super().save(*args, **kwargs)

    @property
    def has_special_rules(self):
        return bool(self.special_rules)

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
        if not self.slug:
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
        if not self.slug:
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
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.kin_for.name})"


class IndexType(models.TextChoices):
    CLASS = "class", "Class"
    TALENT = "talent", "Talent"
    KIN = "kin", "Kin"
    ATTRIBUTE = "attribute", "Attribute"
    MECHANIC = "mechanic", "Game Mechanic"
    GLOSSARY = "glossary", "Glossary Term"


class RulePage(models.Model):
    title = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True, blank=True)
    content = models.TextField(blank=True, default="", help_text="CKEditor HTML content.")

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title

    class Meta:
        ordering = ["title"]


class Definition(models.Model):
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=100, unique=True, blank=True)
    short_description = models.CharField(max_length=300, blank=True, default="")
    description = models.TextField(blank=True, default="")

    index_type = models.CharField(max_length=15, choices=IndexType.choices, default=IndexType.GLOSSARY)
    target_url = models.CharField(max_length=255, blank=True, default="")

    # True = no backing model, this row IS the source of truth (edited directly here).
    # False = mirrored from Class/Talent/Kin/Attribute/RulePage via signal, read-only in admin.
    source_id = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="PK of the source row when this Definition is synced from another model. Null for glossary terms.",
    )

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"[{self.get_index_type_display()}] {self.name}"

    class Meta:
        ordering = ["name"]
        # NULL source_id (glossary terms) doesn't collide with itself in Postgres/SQLite/MySQL --
        # each is treated as distinct, so any number of glossary rows can coexist here.
        unique_together = ("index_type", "source_id")
