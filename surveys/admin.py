from django.contrib import admin

from .models import Answer, Choice, Question, Response, Survey, SurveyQuestion

# ==========================================
# INLINES
# ==========================================


class ChoiceInline(admin.TabularInline):
    model = Choice
    extra = 0
    fields = ["position", "label"]
    ordering = ["position"]


class SurveyQuestionInline(admin.TabularInline):
    model = SurveyQuestion
    extra = 0
    ordering = ["position"]
    fields = ["position", "question", "is_required"]
    autocomplete_fields = ["question"]
    show_change_link = True

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        formfield = super().formfield_for_foreignkey(db_field, request, **kwargs)
        if db_field.name == "question":
            w = formfield.widget
            if hasattr(w, "can_add_related"):
                w.can_add_related = False
            if hasattr(w, "can_change_related"):
                w.can_change_related = True
            if hasattr(w, "can_delete_related"):
                w.can_delete_related = False
            if hasattr(w, "can_view_related"):
                w.can_view_related = True
        return formfield


class AnswerInline(admin.StackedInline):
    model = Answer
    extra = 0
    can_delete = False
    readonly_fields = ["survey_question", "text_response", "selected_choices"]
    fields = ["survey_question", "text_response", "selected_choices"]

    def has_add_permission(self, request, obj=None):
        return False

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related("survey_question", "survey_question__question", "response", "response__survey")
            .prefetch_related("selected_choices")
        )


# ==========================================
# ADMIN REGISTRATIONS
# ==========================================


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ["text", "question_type"]
    list_filter = ["question_type"]
    search_fields = ["text"]
    inlines = [ChoiceInline]

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related("choices")


@admin.register(Survey)
class SurveyAdmin(admin.ModelAdmin):
    # Added string reference safety checks for linked events
    list_display = ["title", "survey_type", "event", "is_active"]
    list_filter = ["survey_type", "is_active", "event"]
    search_fields = ["title", "event__title"]
    readonly_fields = ["created_at"]
    inlines = [SurveyQuestionInline]


@admin.register(Response)
class ResponseAdmin(admin.ModelAdmin):
    list_display = ["survey", "user", "submitted_at"]
    list_display_links = ["survey", "user"]
    list_filter = ["survey", "survey__survey_type", "submitted_at"]
    date_hierarchy = "submitted_at"

    search_fields = ["user__username", "user__first_name", "user__last_name", "survey__title", "answers__text_response"]

    ordering = ["-submitted_at"]
    list_per_page = 50
    list_select_related = ("survey", "user")
    readonly_fields = ["survey", "user", "submitted_at"]
    empty_value_display = "—"

    def get_inlines(self, request, obj):
        return [AnswerInline] if obj else []

    def has_add_permission(self, request):
        return False

    # Makes the panel completely read-only
    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
