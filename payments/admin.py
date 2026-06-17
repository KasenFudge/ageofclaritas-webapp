# Register your models here.
from django.contrib import admin

from events.models import EventRegistration

from .models import Transaction


class EventRegistrationInline(admin.TabularInline):
    model = EventRegistration

    # 1. Choose the relevant descriptive columns to display in the inline table row
    fields = ("user", "event", "final_price_display")

    # 2. Enforce the same fields to be fully read-only
    readonly_fields = ("user", "event", "final_price_display")

    # 3. Completely hide extra blank placeholder rows and block deletion/addition privileges
    extra = 0
    can_delete = False

    @admin.display(description="Price Paid")
    def final_price_display(self, obj):
        return f"${obj.final_price_cents / 100:.2f}"

    # 4. Strict structural overrides to block UI manipulation buttons
    def has_add_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    # Choose which columns to display in the overview list
    list_display = ("id", "stripe_session_id", "total_amount_display", "payment_status", "payment_method", "created_at")
    list_filter = ("payment_status", "payment_method", "created_at")
    search_fields = ("id", "stripe_session_id")
    ordering = ("-created_at",)

    readonly_fields = (
        "stripe_session_id",
        "total_amount_cents",
        "payment_status",
        "payment_method",
        "created_at",
    )
    inlines = [EventRegistrationInline]

    # Convert cents to a human-readable dollar format for the overview table
    @admin.display(description="Total Amount")
    def total_amount_display(self, obj):
        return f"${obj.total_amount_cents / 100:.2f}"

    # Strictly block manual entry creation buttons
    def has_add_permission(self, request):
        return False

    # Strictly block manual record deletions
    def has_delete_permission(self, request, obj=None):
        return False

    # Completely remove the "Save" or "Save and continue editing" buttons from the UI
    def has_change_permission(self, request, obj=None):
        # We return True so an admin can click INTO a record to view details,
        # but because everything is marked read-only above, Django automatically hides the save buttons.
        return True
