from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils import timezone
from django_summernote.admin import SummernoteModelAdmin

from .models import CustomUser, Waiver, WaiverSignature


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    # Display fields in the grid layout (Added is_student)
    list_display = ("username", "email", "date_of_birth", "display_age", "is_student", "is_staff")

    # Enable filtering by student status and core flags on the right sidebar
    list_filter = ("is_student", "is_staff", "is_superuser", "is_active", "groups")

    search_fields = ("username", "email", "first_name", "last_name")
    ordering = ("username",)

    # Explicitly register dynamic or computed fields as read-only
    readonly_fields = ("display_age",)

    # Form fieldsets for editing an existing user
    fieldsets = UserAdmin.fieldsets + (
        (
            "Personal Info (Custom)",
            {
                "fields": ("date_of_birth", "parent_account"),
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

    # Helper method to calculate age cleanly inside the admin grid
    @admin.display(description="Age")
    def display_age(self, obj):
        if obj.date_of_birth:
            return obj.age_on(timezone.localdate())
        return "N/A"


# Used for context of who has signed specifc waiver
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
class WaiverAdmin(SummernoteModelAdmin):
    list_display = ("title", "effective_date", "is_active")
    list_editable = ("is_active",)
    summernote_fields = ("content",)
    inlines = [WaiverSignatureInline]
