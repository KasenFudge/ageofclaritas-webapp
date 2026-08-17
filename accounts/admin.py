from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.db import models
from django.utils import timezone
from django_ckeditor_5.widgets import CKEditor5Widget

from .models import CustomUser, Waiver, WaiverSignature

# Centralized CKEditor 5 mapping for TextFields
CKEDITOR_5_OVERRIDE = {models.TextField: {"widget": CKEditor5Widget(config_name="default")}}


@admin.action(description="Mark selected players as Veterans")
def make_veteran(modeladmin, request, queryset):
    queryset.update(is_veteran=True)


@admin.action(description="Remove Veteran status from selected players")
def remove_veteran(modeladmin, request, queryset):
    queryset.update(is_veteran=False)


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    # Display fields in the grid layout
    list_display = ("username", "full_name", "email", "is_active", "is_student", "is_veteran", "is_staff")

    # Enable filtering by student status and core flags on the right sidebar
    list_filter = ("is_veteran", "is_student", "is_staff", "is_active")

    # Add the make/remove veteran actions to the dropdown on the user list.
    # A single row can be selected to fix one player, not just bulk operations.
    actions = [make_veteran, remove_veteran]

    search_fields = ("username", "email", "first_name", "last_name")

    # Explicitly register dynamic or computed fields as read-only
    readonly_fields = ("display_age",)

    # Form fieldsets for editing an existing user
    fieldsets = UserAdmin.fieldsets + (
        (
            "Personal Info (Custom)",
            {
                "fields": ("date_of_birth", "parent_account", "pending_guardian"),
            },
        ),
        (
            "Student Status Tracking",
            {
                "fields": ("is_student", "student_status_expires"),
            },
        ),
    )

    # Form fieldsets for creating a new user through the admin panel
    add_fieldsets = UserAdmin.add_fieldsets + (
        (
            "Personal Info (Custom)",
            {
                "fields": ("email", "date_of_birth", "parent_account"),
            },
        ),
    )

    # Show first + last name together in the list grid; sortable by last name
    @admin.display(description="Full Name", ordering="last_name")
    def full_name(self, obj):
        return obj.get_full_name() or "—"

    # Helper method to calculate age cleanly inside the admin grid
    @admin.display(description="Age")
    def display_age(self, obj):
        if obj.date_of_birth:
            return obj.age_on(timezone.localdate())
        return "N/A"


# Used for context of who has signed specific waiver
class WaiverSignatureInline(admin.TabularInline):
    model = WaiverSignature
    extra = 0
    readonly_fields = ("user", "signed_at")

    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False


# Used for management & audits (i.e. can search for user instead of looking at active waiver)
@admin.register(WaiverSignature)
class WaiverSignatureAdmin(admin.ModelAdmin):
    list_display = ("user", "waiver", "signed_at")
    list_filter = ("waiver", "signed_at")
    search_fields = ("user__username", "user__email", "waiver__title")
    readonly_fields = ("user", "waiver", "signed_at")


@admin.register(Waiver)
class WaiverAdmin(admin.ModelAdmin):
    formfield_overrides = CKEDITOR_5_OVERRIDE
    list_display = ("title", "effective_date", "is_active")
    list_editable = ("is_active",)
    inlines = [WaiverSignatureInline]
