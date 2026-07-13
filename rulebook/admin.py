from django.contrib import admin
from django.db import models
from django_ckeditor_5.widgets import CKEditor5Widget

from .models import Attribute, Class, ClassType, Kin, Kin_Image, RulePage, Talent

# Centralized CKEditor 5 mapping for TextFields
CKEDITOR_5_OVERRIDE = {models.TextField: {"widget": CKEditor5Widget(config_name="default")}}


# ==========================================
# CLASS & TALENT ADMINISTRATION
# ==========================================
class TalentInline(admin.StackedInline):
    model = Talent
    formfield_overrides = CKEDITOR_5_OVERRIDE

    def get_extra(self, request, obj=None, **kwargs):
        if obj is None:  # Check if creating a new object
            return 5  # Display five extra forms on creation
        return 0  # No extra forms on editing existing objects


class BaseClassFilter(admin.RelatedFieldListFilter):
    def field_choices(self, field, request, model_admin):
        qs = field.remote_field.model.objects.filter(class_type=ClassType.GUILD).order_by("name")
        return [(c.pk, str(c)) for c in qs]


@admin.register(Class)
class ClassAdmin(admin.ModelAdmin):
    formfield_overrides = CKEDITOR_5_OVERRIDE

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "guild":
            kwargs["queryset"] = Class.objects.filter(class_type=ClassType.GUILD).order_by("name")
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    inlines = [TalentInline]
    ordering = ["name"]
    search_fields = ["name"]
    list_filter = [("guild", BaseClassFilter), "class_type"]

    list_display = ("name", "class_type", "guild")
    prepopulated_fields = {"slug": ("name",)}


# ==========================================
# KIN & ATTRIBUTE ADMINISTRATION
# ==========================================
class AttributeInline(admin.TabularInline):
    model = Attribute
    formfield_overrides = CKEDITOR_5_OVERRIDE

    def get_extra(self, request, obj=None, **kwargs):
        if obj is None:  # Check if creating a new object
            return 3  # Display three extra forms on creation
        return 0  # No extra forms on editing existing objects


class KinImageInline(admin.StackedInline):
    model = Kin_Image
    verbose_name_plural = "Kin Art"

    def get_extra(self, request, obj=None, **kwargs):
        if obj is None:  # Check if creating a new object
            return 2  # Display two extra forms on creation
        return 0  # No extra forms on editing existing objects


@admin.register(Kin)
class KinAdmin(admin.ModelAdmin):
    formfield_overrides = CKEDITOR_5_OVERRIDE
    inlines = [AttributeInline, KinImageInline]
    ordering = ["name"]
    search_fields = ["name"]

    list_display = ("name",)
    prepopulated_fields = {"slug": ("name",)}


# ==========================================
# RULEBOOK PAGE & DEFINITION ADMINISTRATION
# ==========================================
@admin.register(RulePage)
class RulePageAdmin(admin.ModelAdmin):
    list_display = ("title", "slug")
    search_fields = ["title"]
    prepopulated_fields = {"slug": ("title",)}
