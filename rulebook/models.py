from django.db import models
from django.contrib import admin
from enum import Enum

# Create your models here.

class TalentType(Enum):
    SKILL = 'skill'
    ABILITY = 'ability'
    WEAPON_WARRIOR_TITLE = 'weapon'
    ARMOR_WARRIOR_TITLE = 'armor'
    SUPPORT_WARRIOR_TITLE = 'support'
    OTHER_WARRIOR_TITLE = 'other'
    TIER_1 = 'tier_1'
    TIER_2 = 'tier_2'
    TIER_3 = 'tier_3'

class Class(models.Model):
    name = models.CharField()
    subclasses = models.ManyToManyField("self", symmetrical=False, related_name="parent_classes", blank=True)

    def __str__(self):
        return self.name

class Talent(models.Model):
    name = models.CharField()
    description = models.TextField(blank=True, default='')
    is_rankless = models.BooleanField(default=False)
    class_for = models.ForeignKey(Class, on_delete=models.CASCADE, null=True)
    talent_type = models.CharField(
        max_length=15,
        choices = [(member.value, member.name) for member in TalentType],
        default='ability'
    )

    def __str__(self):
        return self.name
    
class Kin(models.Model):
    name = models.CharField()
    description = models.TextField()
    size = models.CharField()

    def __str__(self):
        return self.name

class Kin_Image(models.Model):
    image = models.ImageField(upload_to="images/", default="static/images/4guysHouseOctavious.jpg")
    kin_for = models.ForeignKey(Kin, on_delete=models.CASCADE)

class Attribute(models.Model):
    name = models.CharField()
    description = models.TextField()
    kin_for = models.ForeignKey(Kin, on_delete=models.CASCADE)

    def __str__(self):
        return self.name
    
class Definition(models.Model):
    name = models.CharField()
    description = models.TextField()