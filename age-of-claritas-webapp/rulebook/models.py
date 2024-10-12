from django.db import models

# Create your models here.
from django.db import models
from django.contrib import admin
from enum import Enum

class ClassFrom(Enum):
    "CLASSLESS"
    "CLERIC"
    "NOBLE"
    "RANGER"
    "ROGUE"
    "SPELLBINDER"
    "WARRIOR"
    "WIZARD"

class TalentType(Enum):
    "SKILL"
    "ABILITY"
    "WARRIOR_TITLE"
    "TIER_1"
    "TIER_2"
    "TIER_3"
    "ATTRIBUTE"

class Talent(models.Model):
    talent_name = models.CharField(max_length=50)
    talent_description = models.CharField()
    talent_class = ClassFrom
    talent_type = TalentType
