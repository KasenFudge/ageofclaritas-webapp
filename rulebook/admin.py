from django.contrib import admin

# Register your models here.
from .models import Class, Talent, Kin, Kin_Image, Attribute

class TalentInline(admin.StackedInline):
    model = Talent

class ClassAdmin(admin.ModelAdmin):
    fields = ["name", "description"]
    inlines = [TalentInline]

admin.site.register(Class, ClassAdmin)
# admin.site.register(Kin)