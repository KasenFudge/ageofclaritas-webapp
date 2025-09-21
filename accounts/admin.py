from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User

from .models import Profile, Waiver, WaiverSignature
from django_summernote.admin import SummernoteModelAdmin

# Register your models here.

class ProfileInline(admin.StackedInline):
    model = Profile
    can_delete = False
    verbose_name_plural = 'Profile'
    fk_name = 'user'

class CustomUserAdmin(UserAdmin):
    inlines = [ProfileInline,]

    def get_inline_instances(self, request, obj=None):
        if not obj:
            return []
        return super().get_inline_instances(request, obj)
    
admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)

class WaiverSignatureInline(admin.TabularInline):
    model = WaiverSignature
    extra = 0
    readonly_fields = ('user', 'signed_at')
    
    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

@admin.register(Waiver)
class WaiverAdmin(SummernoteModelAdmin):
    summernote_fields = ['content',]
    inlines = [WaiverSignatureInline]