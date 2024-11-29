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
    summernote_fields = ("description",)
    inlines = [TalentInline]

admin.site.register(Class, ClassAdmin)

# Kin Information

class AttributeInline(SummernoteModelAdminMixin, admin.TabularInline):
    model = Attribute
    summernote_fields = ("description",)

    def get_extra(self, request, obj=None, **kwargs):
        if obj is None:  # Check if creating a new object
            return 2  # Display three extra forms on creation
        else:
            return 0  # No extra forms on editing existing objects

class KinImageInline(admin.TabularInline):
    model = Kin_Image

class KinAdmin(SummernoteModelAdmin):
    summernote_fields = ("description",)
    inlines = [AttributeInline, KinImageInline]

admin.site.register(Kin, KinAdmin)

# Rulebook Definitions

class DefinitionAdmin(SummernoteModelAdmin):
    summernote_fields = ("name", "description",)

admin.site.register(Definition, DefinitionAdmin)