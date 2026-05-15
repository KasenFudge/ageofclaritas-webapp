from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User

from .models import CustomUser, Waiver, WaiverSignature
from django_summernote.admin import SummernoteModelAdmin

# Register your models here.
@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    # Fields to display in the list view (the main table)
    list_display = ('username', 'email', 'date_of_birth', 'age', 'is_staff')
    
    # Add filters on the right sidebar
    list_filter = ('is_staff', 'is_superuser', 'is_active', 'groups')

    # We append our custom fields to the standard UserAdmin fieldsets
    # Fieldsets for the "Edit User" page
    fieldsets = UserAdmin.fieldsets + (
        ('Personal Info (Custom)', {
            'fields': ('date_of_birth', 'parent_account'),
        }),
    )

    # Fieldsets for the "Add User" page
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Personal Info (Custom)', {
            'fields': ('email', 'date_of_birth', 'parent_account'),
        }),
    )

    search_fields = ('username', 'email', 'first_name', 'last_name')    
    ordering = ('username',)

# Used for context of who has signed specifc waiver
class WaiverSignatureInline(admin.TabularInline):
    model = WaiverSignature
    extra = 0
    readonly_fields = ('user', 'signed_at')

    can_delete = False
    
    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

# Used for management & audits (i.e. can search for user instead of looking at active waiver)
@admin.register(WaiverSignature)
class WaiverSignatureAdmin(admin.ModelAdmin):
    list_display = ('user', 'waiver', 'signed_at')
    list_filter = ('waiver', 'signed_at')
    search_fields = ('user__username', 'user__email', 'waiver__title')
    readonly_fields = ('user', 'waiver', 'signed_at')

@admin.register(Waiver)
class WaiverAdmin(SummernoteModelAdmin):
    list_display = ('title', 'effective_date', 'is_active')
    list_editable = ('is_active',)
    summernote_fields = ('content',)
    inlines = [WaiverSignatureInline]