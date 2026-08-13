# Register your models here.
from django.contrib import admin, messages
from django.db import transaction as db_transaction
from django.db.models import Prefetch

from events.models import EventRegistration

from .models import PaymentStatus, Transaction


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
    list_display = (
        "id",
        "stripe_session_id",
        "registration_display",
        "total_amount_display",
        "payment_status",
        "payment_method",
        "created_at",
    )
    list_filter = ("payment_status", "payment_method", "created_at")
    search_fields = ("id", "stripe_session_id")
    ordering = ("-created_at",)

    inlines = [EventRegistrationInline]

    # Prefetch the attached registration (plus its user/event)
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.prefetch_related(
            Prefetch("registrations", queryset=EventRegistration.objects.select_related("user", "event"))
        )

    actions = [
        "force_mark_succeeded",
        "force_mark_failed",
        "force_mark_refunded",
    ]

    # Convert cents to a human-readable dollar format for the overview table
    @admin.display(description="Total Amount")
    def total_amount_display(self, obj):
        return f"${obj.total_amount_cents / 100:.2f}"

    # Show who/what this transaction is for
    @admin.display(description="For")
    def registration_display(self, obj):
        first_reg = obj.registrations.first()
        return str(first_reg) if first_reg else "—"

    # -------------------------------------------------------------
    # Manual overrides for when the webhook missed something and you've
    # already confirmed the real status in the Stripe dashboard yourself.
    # Restricted to one row at a time so a bulk selection can't force
    # a whole batch of transactions by accident.
    # -------------------------------------------------------------
    def _force_status(self, request, queryset, target_status, label):
        if queryset.count() != 1:
            self.message_user(
                request,
                "Select exactly one transaction to force - this is a manual override, not a bulk action.",
                level=messages.ERROR,
            )
            return

        txn = queryset.first()
        with db_transaction.atomic():
            locked = Transaction.objects.select_for_update().get(pk=txn.pk)
            locked.payment_status = target_status
            locked.save(update_fields=["payment_status"])

        self.message_user(request, f"Transaction #{txn.pk} set to {label}.", level=messages.SUCCESS)

    @admin.action(description="Force mark as SUCCEEDED (I've already confirmed this in Stripe)")
    def force_mark_succeeded(self, request, queryset):
        self._force_status(request, queryset, PaymentStatus.SUCCEEDED, "SUCCEEDED")

    @admin.action(description="Force mark as FAILED (I've already confirmed this in Stripe)")
    def force_mark_failed(self, request, queryset):
        self._force_status(request, queryset, PaymentStatus.FAILED, "FAILED")

    @admin.action(description="Force mark as REFUNDED (I've already confirmed this in Stripe)")
    def force_mark_refunded(self, request, queryset):
        self._force_status(request, queryset, PaymentStatus.REFUNDED, "REFUNDED")

    # Force all fields to be read-only when viewing an individual record detail page
    def get_readonly_fields(self, request, obj=None):
        return [field.name for field in self.model._meta.fields]

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
