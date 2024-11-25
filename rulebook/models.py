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
    class_name = models.CharField(max_length=40)
    class_description = models.CharField()

    def __str__(self):
        return self.class_name

class Talent(models.Model):
    talent_name = models.CharField(max_length=40)
    talent_description = models.CharField()
    talent_rankless = models.CharField(null=True)
    talent_rank1 = models.CharField(null=True)
    talent_rank2 = models.CharField(null=True)
    talent_rank3 = models.CharField(null=True)
    is_rankless = models.BooleanField(default=False)
    talent_class = models.ForeignKey(Class, on_delete=models.CASCADE)
    talent_type = TalentType

    def __str__(self):
        return self.talent_name