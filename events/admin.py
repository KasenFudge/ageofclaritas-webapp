from django.contrib import admin
from django import forms
from django.core.exceptions import ValidationError

from .models import(
    Event, EventRegistration, EventPriceTier, EventMedia,
)


# ==========================================
# EVENT ADMINISTRATION
# ==========================================

class PriceTierInline(admin.StackedInline):
    model = EventPriceTier
    # Creates 0 instances of this inline on opening the Event Editor
    extra = 0
    # Classes this Inline inherits: 
    # "collapse": UX will be collapsible
    classes = ["collapse",]

    verbose_name_plural = "Price Tiers: Only include if special pricing rules exist."

    fields = ['label', 'min_age', 'max_age', 'price_cents']

# A custom sidebar gate filter to handle reading into your JSON payload field
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
            # Uses Django's __contains lookup to find records where the weapon_rental dictionary exists in the array
            return queryset.filter(additional_items__contains=[{"type": "weapon_rental"}])
        if self.value() == 'no':
            return queryset.exclude(additional_items__contains=[{"type": "weapon_rental"}])
        return queryset

@admin.register(EventRegistration)
class EventRegistrationAdmin(admin.ModelAdmin):
    list_display = [
        "user", 
        "event", 
        "formatted_arrival_time", 
        "weapon_rental_display", 
        "formatted_final_price", 
        "checked_in"
    ]
    
    list_filter = ["event", "checked_in", WeaponRentalFilter, "arrival_time"]
    
    search_fields = ["user__username", "user__first_name", "user__last_name", "event__title"]
    
    # Sorts by arrival time, then by last name, then by first name
    ordering = ["arrival_time", "user__last_name", "user__first_name"]
    list_per_page = 50
    list_select_related = ("event", "user")

    # Custom column renderer: Formats full datetime values into crisp event passes
    @admin.display(ordering="arrival_time", description="Scheduled Arrival")
    def formatted_arrival_time(self, obj):
        return obj.arrival_time.strftime("%a, %b %d — %I:%M %p")
    
    # Custom column renderer: Converts database integer cents into currency displays
    @admin.display(ordering="final_price_cents", description="Price Paid")
    def formatted_final_price(self, obj):
        if obj.final_price_cents is None:
            return "—"
        return f"${obj.final_price_cents / 100:.2f}"

    # Safely extracts weapon rental flags out of the JSON data structure for the list view rows
    @admin.display(boolean=True, description="Weapon Rental")
    def weapon_rental_display(self, obj):
        if isinstance(obj.additional_items, list):
            return any(item.get("type") == "weapon_rental" for item in obj.additional_items if isinstance(item, dict))
        return False

class EventRegistrationInline(admin.StackedInline):
    model = EventRegistration
    # Creates 0 instances of this inline on opening the Event Editor
    extra = 0

    fields = ['user', 'checked_in']
    readonly_fields = ['arrival_time']

class EventMediaInline(admin.StackedInline):
    model = EventMedia

    def get_extra(self, request, obj=None, **kwargs):
        return 0  # Require Pictures to be added fully manually since it may not always be applicable

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
    list_filter = ['event_type', 'start_time',]
    search_fields = ['title',]