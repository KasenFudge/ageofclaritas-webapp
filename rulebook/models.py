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
    "ATTRIBUTE"

class Class(models.Model):
    class_name = models.CharField(max_length=50)
    class_description = models.CharField()

    def __str__(self):
        return self.class_name

class Talent(models.Model):
    talent_name = models.CharField(max_length=50)
    talent_description = models.CharField()
    talent_class = models.ForeignKey(Class, on_delete=models.CASCADE)
    talent_type = TalentType
