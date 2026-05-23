from django.contrib import admin
from django import forms
from django.core.exceptions import ValidationError

from .models import(
    Event, EventRegistration, EventPriceTier, EventMedia,
    Survey, Question, SurveyQuestion, Choice,
    Response, Answer
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

class ResponseInline(admin.StackedInline):
    model = Response
    exclude = ['user']  # User is shown in the Header of each row
    readonly_fields = ['submitted_at']

    extra = 0  # This inline is readonly, don't display empty data
    
    def has_add_permission(self, request, obj = ...):
        return False
    
    def has_change_permission(self, request, obj = ...):
        return False

# --- Question & Choice Editing ---
class ChoiceInline(admin.TabularInline):
    model = Choice
    extra = 0
    fields = ["position", "label"]
    ordering = ["position"]
    show_change_link = False

@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ["text", "question_type"]
    list_filter = ["question_type"]
    search_fields = ["text"]
    inlines = [ChoiceInline]

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.prefetch_related("choices")

# --- Survey builder ---
class SurveyQuestionInline(admin.TabularInline):
    model = SurveyQuestion
    extra = 0
    ordering = ["position"]
    fields = ["position", "question", "is_required"]
    autocomplete_fields = ["question"]
    show_change_link = True

    # Only allow linking to existing Questions (no green "+" etc.)
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        formfield = super().formfield_for_foreignkey(db_field, request, **kwargs)
        if db_field.name == "question":
            w = formfield.widget
            if hasattr(w, "can_add_related"): w.can_add_related = False
            if hasattr(w, "can_change_related"): w.can_change_related = True
            if hasattr(w, "can_delete_related"): w.can_delete_related = False
            if hasattr(w, "can_view_related"): w.can_view_related = True
        return formfield

@admin.register(Survey)
class SurveyAdmin(admin.ModelAdmin):
    list_display = ["title", "survey_type", "event", "is_active", "event__downtime_due"]
    list_filter = ["survey_type", "is_active", "event", "event__event_type"]
    search_fields = ["title", "event__title"]
    autocomplete_fields = ["event"]
    readonly_fields = ["created_at"]
    inlines = [SurveyQuestionInline]


# --- Survey Responses and Answers

class AnswerInline(admin.StackedInline):
    model = Answer
    extra = 0
    can_delete = False
    show_change_link = False
    readonly_fields = ["survey_question", "text_response", "selected_choices"]
    fields = ["survey_question", "text_response", "selected_choices"]

    def has_add_permission(self, request):
        return False

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related(
            "survey_question", "survey_question__question",
            "response", "response__survey"
        ).prefetch_related("selected_choices")


@admin.register(Response)
class ResponseAdmin(admin.ModelAdmin):
    list_display = ["survey", "user", "submitted_at"]
    list_display_links = ["survey", "user"] 
    list_filter   = ["survey", "survey__survey_type", "submitted_at"]
    date_hierarchy = "submitted_at"
    
    search_fields = [
        "user__user__username",
        "user__user__first_name",
        "user__user__last_name",
        "survey__title",
        "answers__text_response"
        ]
    
    ordering = ["-submitted_at"]
    list_per_page = 50
    list_select_related = ("survey", "user", "user__user")

    readonly_fields = ["survey", "user", "submitted_at"]
    preserve_filters = True
    empty_value_display = "—"
    
    inlines = []
    def get_inlines(self, request, obj):
        return [AnswerInline] if obj else []

    actions = None
    save_on_top = False
    save_as = False

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False  # makes the change view read-only (view-only)

    def has_delete_permission(self, request, obj=None):
        return False

    def has_view_permission(self, request, obj=None):
        return True