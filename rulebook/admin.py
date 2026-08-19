from django.contrib import admin
from django.db import models
from django_ckeditor_5.widgets import CKEditor5Widget

from .models import Attribute, Class, ClassType, Definition, Kin, Kin_Image, RulePage, Talent

# Centralized CKEditor 5 mapping for TextFields
CKEDITOR_5_OVERRIDE = {models.TextField: {"widget": CKEditor5Widget(config_name="default")}}


# ==========================================
# CLASS & TALENT ADMINISTRATION
# ==========================================
class TalentInline(admin.StackedInline):
    model = Talent
    formfield_overrides = CKEDITOR_5_OVERRIDE
    readonly_fields = ("slug",)
    fields = [("name", "slug"), "class_for", "description", "is_rankless", "priority", "talent_type"]

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
    readonly_fields = ("slug",)
    fields = [("name", "slug"), "description", "guild", "class_type", "special_rules"]


# ==========================================
# KIN & ATTRIBUTE ADMINISTRATION
# ==========================================
class AttributeInline(admin.TabularInline):
    model = Attribute
    formfield_overrides = CKEDITOR_5_OVERRIDE
    readonly_fields = ("slug",)

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
    readonly_fields = ("slug",)
    fields = [("name", "slug"), "short_description", "description", "size"]


# ==========================================
# RULEBOOK PAGE & DEFINITION ADMINISTRATION
# ==========================================
@admin.register(RulePage)
class RulePageAdmin(admin.ModelAdmin):
    formfield_overrides = CKEDITOR_5_OVERRIDE
    list_display = ("title", "slug")
    search_fields = ["title"]
    readonly_fields = ("slug",)
    fields = [("title", "slug"), "content"]


@admin.register(Definition)
class DefinitionAdmin(admin.ModelAdmin):
    formfield_overrides = CKEDITOR_5_OVERRIDE
    list_display = ("term", "index_type", "slug", "source_id")
    list_filter = ["index_type"]
    search_fields = ["term"]
    ordering = ["index_type", "term"]
    readonly_fields = ("slug",)
    fields = [("term", "slug"), "index_type", "description", "target_url", "source_id"]
