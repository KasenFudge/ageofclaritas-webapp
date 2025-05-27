from django.db import models
from django.contrib import admin
from enum import Enum

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

class Class(models.Model):
    name = models.CharField()
    base_class = models.ForeignKey("self", on_delete=models.CASCADE, related_name="factions", null=True)
    has_special_rules = models.BooleanField(default=False)
    special_rules = models.CharField(null=True, blank=True, default=None)

    def __str__(self):
        return self.name
    
    def save(self, *args, **kwargs):
        if not self.has_special_rules:
            self.special_rules = None
        super().save(*args, **kwargs)

class Talent(models.Model):
    name = models.CharField()
    description = models.TextField(blank=True, default='')
    is_rankless = models.BooleanField(default=False)
    class_for = models.ForeignKey(Class, on_delete=models.CASCADE, null=True)
    talent_type = models.CharField(
        max_length=15,
        choices = TalentType.choices,
        default = TalentType.ABILITY
    )

    def __str__(self):
        return self.name
    
class Kin(models.Model):
    name = models.CharField()
    short_description = models.TextField(blank=True, default="")
    description = models.TextField(blank=True, default="")
    size = models.CharField(blank=True, default="")

    def __str__(self):
        return self.name

class Kin_Image(models.Model):
    image = models.ImageField(upload_to="images/Kin/", blank=True)
    kin_for = models.ForeignKey(Kin, on_delete=models.CASCADE)

class Attribute(models.Model):
    name = models.CharField()
    description = models.TextField()
    kin_for = models.ForeignKey(Kin, on_delete=models.CASCADE)
    can_start_with = models.BooleanField(default=True)

    def __str__(self):
        return self.name
    
class Definition(models.Model):
    name = models.CharField()
    description = models.TextField()