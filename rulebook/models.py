from django.db import models
from django.contrib import admin
from enum import Enum

# Create your models here.

class TalentType(Enum):
    "SKILL"
    "ABILITY"
    "WARRIOR_TITLE"
    "TIER_1"
    "TIER_2"
    "TIER_3"

class Class(models.Model):
    name = models.CharField(max_length=40)
    description = models.CharField()
    # image = models.ImageField()

    def __str__(self):
        return self.name

class Talent(models.Model):
    name = models.CharField(max_length=40)
    description = models.CharField()
    rankless_effect = models.CharField(null=True)
    rank1_effect = models.CharField(null=True)
    rank2_effect = models.CharField(null=True)
    rank3_effect = models.CharField(null=True)
    is_rankless = models.BooleanField(default=False)
    class_for = models.ForeignKey(Class, on_delete=models.CASCADE)
    type_of = TalentType

    def __str__(self):
        return self.name
    
class Kin(models.Model):
    name = models.CharField(max_length=40)
    description = models.CharField()
    size = models.CharField()

    def __str__(self):
        return self.name

class Kin_Image(models.Model):
    image = models.ImageField()
    kin_for = models.ForeignKey(Kin, on_delete=models.CASCADE)

class Attribute(models.Model):
    name = models.CharField(max_length=40)
    description = models.CharField()
    kin_for = models.ForeignKey(Kin, on_delete=models.CASCADE)

    def __str__(self):
        return self.name