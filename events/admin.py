from django.contrib import admin
from .models import Event, EventRegistration, EventPriceTier, EventMedia

# ==========================================
# INLINES
# ==========================================

class PriceTierInline(admin.StackedInline):
    model = EventPriceTier
    extra = 0
    classes = ["collapse"]
    verbose_name_plural = "Price Tiers: Only include if special pricing rules exist."
    fields = ['label', 'min_age', 'max_age', 'price_cents']


class EventRegistrationInline(admin.StackedInline):
    model = EventRegistration
    extra = 0
    fields = ['user', 'checked_in']
    # Explicitly set user as read-only to prevent administrative accidents
    readonly_fields = ['user'] 


class EventMediaInline(admin.StackedInline):
    model = EventMedia
    extra = 0


# ==========================================
# ADVANCED PAYLOAD FILTERS
# ==========================================

class WeaponRentalFilter(admin.SimpleListFilter):
    title = 'Weapon Rental'
    parameter_name = 'weapon_rental'

    def lookups(self, request, model_admin):
        return (
            ('yes', 'Yes'),
            ('no', 'No'),
        )

    def queryset(self, request, queryset):
        if self.value() == 'yes':
            return queryset.filter(additional_items__contains=[{"type": "weapon_rental"}])
        if self.value() == 'no':
            return queryset.exclude(additional_items__contains=[{"type": "weapon_rental"}])
        return queryset


# ==========================================
# ADMIN REGISTRATIONS
# ==========================================

@admin.register(EventRegistration)
class EventRegistrationAdmin(admin.ModelAdmin):
    list_display = [
        "user", 
        "event", 
        "formatted_arrival_time", 
        "weapon_rental_display", 
        "formatted_final_price",
        "payment_status",
        "checked_in"
    ]
    list_filter = ["event", "checked_in", WeaponRentalFilter, "arrival_time"]
    search_fields = ["user__username", "user__first_name", "user__last_name", "event__title"]
    ordering = ["arrival_time", "user__last_name", "user__first_name"]
    list_per_page = 50
    list_select_related = ("event", "user")

    readonly_fields = ["user", "event", "arrival_time", "base_price_cents", "discounts", "additional_items"]

    fieldsets = (
        ("Attendance", {
            "fields": ("checked_in", "arrival_time"),
            "description": "Core check-in utility for game masters managing player check-ins at the gate."
        }),
        ("Registration Context", {
            "fields": (("user", "event"),),
            "description": "The specific player account and timeline anchor linked to this pass."
        }),
        ("Financial & Transaction Ledger", {
            "fields": ("final_price_cents", "base_price_cents"),
            "description": "Calculated total base cost plus applicable age tier modifications processed at checkout."
        }),
        ("Meta Payload Data", {
            "fields": ("discounts", "additional_items"),
            "classes": ("collapse",),
            "description": "Raw JSON configurations detailing applied discount arrays and additional items."
        }),
    )

    @admin.display(ordering="arrival_time", description="Scheduled Arrival")
    def formatted_arrival_time(self, obj):
        return obj.arrival_time.strftime("%a, %b %d — %I:%M %p")
    
    @admin.display(ordering="final_price_cents", description="Price Paid")
    def formatted_final_price(self, obj):
        if obj.final_price_cents is None:
            return "—"
        return f"${obj.final_price_cents / 100:.2f}"

    @admin.display(boolean=True, description="Weapon Rental")
    def weapon_rental_display(self, obj):
        if isinstance(obj.additional_items, list):
            return any(item.get("type") == "weapon_rental" for item in obj.additional_items if isinstance(item, dict))
        return False


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    prepopulated_fields = {'slug': ('title',)}
    fieldsets = (
        ("Event Info", {
            "fields": [('title', 'slug'), 'event_type', 'registration_available', 'event_image'],
        }),
        ("Event Date/Time", {
            "fields": ['start_time', 'end_time', 'downtime_due'],
        }),
        ("Event Price", {
            "fields": ['base_price_cents'],
        }),
        ("General Picture Information", {
            "fields": ['photographer'],
        })
    )
    inlines = [PriceTierInline, EventRegistrationInline, EventMediaInline]
    list_filter = ['event_type', 'start_time']
    search_fields = ['title']