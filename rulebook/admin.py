from django.contrib import admin

from .models import Class, Talent, Kin, Kin_Image, Attribute, Definition
from django_summernote.admin import SummernoteModelAdmin, SummernoteModelAdminMixin

# Class Information
class TalentInline(SummernoteModelAdminMixin, admin.TabularInline):
    model = Talent
    summernote_fields = ("description",)

    def get_extra(self, request, obj=None, **kwargs):
        if obj is None:  # Check if creating a new object
            return 5  # Display five extra forms on creation
        else:
            return 0  # No extra forms on editing existing objects

class ClassAdmin(SummernoteModelAdmin):
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        base_class_names = ['Cleric', 'Noble', 'Ranger', 'Rogue', 'Spellbinder', 'Warrior', 'Commoner']

        if db_field.name == "base_class":
            kwargs["queryset"] = Class.objects.filter(name__in=base_class_names)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)
    
    summernote_fields = ("special_rules",)
    inlines = [TalentInline]

admin.site.register(Class, ClassAdmin)

# Kin Information

class AttributeInline(SummernoteModelAdminMixin, admin.TabularInline):
    model = Attribute
    summernote_fields = ("description",)

    def get_extra(self, request, obj=None, **kwargs):
        if obj is None:  # Check if creating a new object
            return 3  # Display three extra forms on creation
        else:
            return 0  # No extra forms on editing existing objects

class KinImageInline(admin.TabularInline):
    model = Kin_Image

    def get_extra(self, request, obj=None, **kwargs):
        if obj is None:  # Check if creating a new object
            return 2  # Display three extra forms on creation
        else:
            return 0  # No extra forms on editing existing objects

class KinAdmin(SummernoteModelAdmin):
    summernote_fields = ("description",)
    inlines = [AttributeInline, KinImageInline]

admin.site.register(Kin, KinAdmin)

# Rulebook Definitions

class DefinitionAdmin(SummernoteModelAdmin):
    summernote_fields = ("name", "description",)

admin.site.register(Definition, DefinitionAdmin)