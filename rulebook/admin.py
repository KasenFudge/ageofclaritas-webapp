from django.contrib import admin
from django_summernote.admin import SummernoteModelAdmin, SummernoteModelAdminMixin

from .models import Attribute, Class, ClassType, Definition, Kin, Kin_Image, Talent

# ==========================================
# CLASS & TALENT ADMINISTRATION
# ==========================================


class TalentInline(SummernoteModelAdminMixin, admin.TabularInline):
    model = Talent
    summernote_fields = ("description",)

    def get_extra(self, request, obj=None, **kwargs):
        if obj is None:  # Check if creating a new object
            return 5  # Display five extra forms on creation
        return 0  # No extra forms on editing existing objects


class BaseClassFilter(admin.RelatedFieldListFilter):
    def field_choices(self, field, request, model_admin):
        qs = field.remote_field.model.objects.filter(class_type=ClassType.GUILD).order_by("name")
        return [(c.pk, str(c)) for c in qs]


@admin.register(Class)
class ClassAdmin(SummernoteModelAdmin):
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "guild":
            kwargs["queryset"] = Class.objects.filter(class_type=ClassType.GUILD).order_by("name")
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    summernote_fields = (
        "description",
        "special_rules",
    )
    inlines = [TalentInline]
    ordering = ["name"]
    search_fields = ["name"]
    list_filter = [("guild", BaseClassFilter), "class_type"]

    list_display = ("name", "class_type", "guild")

    prepopulated_fields = {"slug": ("name",)}


# ==========================================
# KIN & ATTRIBUTE ADMINISTRATION
# ==========================================


class AttributeInline(SummernoteModelAdminMixin, admin.TabularInline):
    model = Attribute
    summernote_fields = ("description",)

    def get_extra(self, request, obj=None, **kwargs):
        if obj is None:  # Check if creating a new object
            return 3  # Display three extra forms on creation
        return 0  # No extra forms on editing existing objects


class KinImageInline(admin.TabularInline):
    model = Kin_Image
    verbose_name_plural = "Kin Art"

    def get_extra(self, request, obj=None, **kwargs):
        if obj is None:  # Check if creating a new object
            return 2  # Display two extra forms on creation
        return 0  # No extra forms on editing existing objects


@admin.register(Kin)
class KinAdmin(SummernoteModelAdmin):
    # Enable rich text editing for both long and short descriptions
    summernote_fields = ("description", "short_description")
    inlines = [AttributeInline, KinImageInline]
    ordering = ["name"]
    search_fields = ["name"]

    list_display = ("name",)

    prepopulated_fields = {"slug": ("name",)}


# ==========================================
# RULEBOOK DEFINITIONS
# ==========================================


@admin.register(Definition)
class DefinitionAdmin(SummernoteModelAdmin):
    summernote_fields = (
        "name",
        "description",
    )
    list_display = ("name",)
