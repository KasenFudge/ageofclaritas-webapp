from django.contrib import admin

from .models import Class, Talent, Kin, Kin_Image, Attribute
from django_summernote.admin import SummernoteModelAdmin

# Class Information
class TalentInline(admin.StackedInline):
    model = Talent

    def get_extra(self, request, obj=None, **kwargs):
        if obj is None:  # Check if creating a new object
            return 5  # Display five extra forms on creation
        else:
            return 0  # No extra forms on editing existing objects
        

class ClassAdmin(SummernoteModelAdmin):
    summernote_fields = ("name", "description")
    inlines = [TalentInline]

admin.site.register(Class, ClassAdmin)

# Kin Information

class AttributeInline(admin.TabularInline):
    model = Attribute

    def get_extra(self, request, obj=None, **kwargs):
        if obj is None:  # Check if creating a new object
            return 3  # Display three extra forms on creation
        else:
            return 0  # No extra forms on editing existing objects

class KinImageInline(admin.TabularInline):
    model = Kin_Image

class KinAdmin(SummernoteModelAdmin):
    summernote_fields = ("name", "description", "size")
    inlines = [AttributeInline, KinImageInline]

admin.site.register(Kin, KinAdmin)