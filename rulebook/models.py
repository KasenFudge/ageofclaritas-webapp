from django.db import models
from django.contrib import admin
from django.core.exceptions import ValidationError
from django.utils.text import slugify

# Create your models here.

class TalentType(models.TextChoices):
    SKILL = 'skill', 'Skill'
    ABILITY = 'ability', 'Ability'
    WEAPON_WARRIOR_TITLE = 'weapon', 'Weapon Title'
    ARMOR_WARRIOR_TITLE = 'armor', 'Armor Title'
    SUPPORT_WARRIOR_TITLE = 'support', 'Support Title'
    MISC_WARRIOR_TITLE = 'misc', 'Misc. Title'
    TIER_1 = 'tier_1', 'Tier 1'
    TIER_2 = 'tier_2', 'Tier 2'
    TIER_3 = 'tier_3', 'Tier 3'

class ClassType(models.TextChoices):
    __empty__ = 'Choose a Class Type...'
    GUILD = 'guild', 'Guild'
    FACTION = 'faction', 'Faction'
    ELEMENTAL = 'elemental', 'Elemental'
    MANIFOLD = 'manifold', 'Manifold'
    CLASSLESS = 'classless', 'Classless'

class Class(models.Model):
    name = models.CharField(max_length=20, unique=True)
    slug = models.SlugField(max_length=25, unique=True, blank=True)
    description = models.TextField(blank=True, default='')
    
    guild = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        related_name="factions",
        null=True,
        blank=True
    )
    class_type = models.CharField(
        max_length=15,
        choices=ClassType.choices
    )
    has_special_rules = models.BooleanField(default=False)
    special_rules = models.TextField(null=True, blank=True)

    def __str__(self):
        return self.name
    
    def save(self, *args, **kwargs):
        if not self.has_special_rules:
            self.special_rules = None
        if self.class_type == ClassType.GUILD:
            self.guild = None
        if self.class_type not in [ClassType.GUILD, ClassType.CLASSLESS] and not self.guild:
            raise ValidationError("Factions must be assigned to a Guild")
        
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = "Class"
        verbose_name_plural = "Classes"
        ordering = ["name"]

class Talent(models.Model):
    name = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True, default='')
    is_rankless = models.BooleanField(default=False)

    priority = models.IntegerField(
        default=100, 
        help_text="Lower numbers float to the top (e.g., 0, 1, 2). Default is 100."
    )
    
    class_for = models.ForeignKey(
        Class,
        on_delete=models.CASCADE,
        null=True
    )
    talent_type = models.CharField(
        max_length=15,
        choices = TalentType.choices,
        default = TalentType.ABILITY
    )

    class Meta:
        ordering = ["priority", "name"]

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
    kin_for = models.ForeignKey(
        Kin,
        on_delete=models.CASCADE,
        related_name="kin_images"
    )

class Attribute(models.Model):
    name = models.CharField(max_length=50)
    description = models.TextField()
    kin_for = models.ForeignKey(
        Kin,
        on_delete=models.CASCADE,
        related_name="attributes"
    )
    can_start_with = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        unique_together = ("name", "kin_for")

    def __str__(self):
        return f"{self.name} ({self.kin_for.name})"
    
# TODO: Might not use this, plan is to incorporate 
class Definition(models.Model):
    name = models.CharField()
    description = models.TextField()